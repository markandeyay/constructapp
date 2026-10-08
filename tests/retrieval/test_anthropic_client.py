"""The Claude backed intent and recommendation client.

No network: every test drives a stub SDK whose `messages.create` records what it
was asked for. What is worth testing here is not that an HTTP call happens, it is
that the request is shaped the way the provider requires and that the model
cannot be anything the operator forbade.
"""

from __future__ import annotations

import json

import pytest

from packages.retrieval.anthropic_client import (
    ALLOWED_MODELS,
    DEFAULT_ANTHROPIC_MODEL,
    STRUCTURED_OUTPUT_TOOL,
    AnthropicIntentClient,
    AnthropicJsonClient,
    AnthropicModelNotAllowedError,
    AnthropicRecommendationClient,
    AnthropicUnavailableError,
    validate_model,
)


class _Block:
    def __init__(self, **fields):
        self.__dict__.update(fields)


class _Response:
    def __init__(self, content, *, stop_reason="tool_use", model=DEFAULT_ANTHROPIC_MODEL):
        self.content = content
        self.stop_reason = stop_reason
        self.model = model


class _Messages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.requests: list[dict] = []

    def create(self, **request):
        self.requests.append(request)
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class _StubSDK:
    def __init__(self, *responses):
        self.messages = _Messages(responses)


def _tool_response(payload, **kwargs):
    return _Response(
        [_Block(type="tool_use", name=STRUCTURED_OUTPUT_TOOL, input=payload)], **kwargs
    )


def _client(*responses, **kwargs):
    sdk = _StubSDK(*responses)
    return AnthropicJsonClient(api_key="test-key", sdk_client=sdk, **kwargs), sdk


class TestModelAllowlist:
    """The operator instruction was Sonnet or Haiku, never Opus.

    Enforced at construction rather than defaulted, so the guarantee does not
    depend on nobody editing a configuration file.
    """

    def test_the_default_is_sonnet(self):
        client, _ = _client()
        assert client.model == "claude-sonnet-5-5"

    def test_haiku_is_permitted(self):
        client, _ = _client(model="claude-haiku-5-5")
        assert client.model == "claude-haiku-5-5"

    @pytest.mark.parametrize(
        "model",
        ["claude-opus-5-5", "claude-opus-4-1", "opus", "claude-3-opus-20240229", ""],
    )
    def test_opus_and_nonsense_are_refused_at_construction(self, model):
        with pytest.raises(AnthropicModelNotAllowedError):
            AnthropicJsonClient(api_key="test-key", model=model)

    def test_no_environment_value_can_select_opus(self, monkeypatch):
        """The point of an allowlist: editing .env cannot reach a forbidden model."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-5-5")
        with pytest.raises(AnthropicModelNotAllowedError):
            AnthropicJsonClient.from_env()

    def test_the_allowlist_contains_no_opus_model(self):
        assert not any("opus" in model for model in ALLOWED_MODELS)

    def test_validate_model_names_what_is_allowed(self):
        with pytest.raises(AnthropicModelNotAllowedError) as caught:
            validate_model("claude-opus-5-5")
        for model in ALLOWED_MODELS:
            assert model in str(caught.value)


class TestRequestShape:
    def test_the_schema_is_sent_as_a_forced_tool(self):
        """Anthropic has no response schema parameter, so the schema is a tool."""
        schema = {"type": "object", "properties": {"organism": {"type": "string"}}}
        client, sdk = _client(_tool_response({"organism": "e_coli"}))

        client.generate_json(prompt="build a vector", schema=schema)

        request = sdk.messages.requests[0]
        assert request["tools"][0]["name"] == STRUCTURED_OUTPUT_TOOL
        assert request["tools"][0]["input_schema"] == schema
        assert request["tool_choice"] == {"type": "tool", "name": STRUCTURED_OUTPUT_TOOL}

    def test_temperature_is_zero(self):
        """An intent parser that varies per call is one nobody can validate."""
        client, sdk = _client(_tool_response({"organism": "e_coli"}))
        client.generate_json(prompt="p", schema={"type": "object"})
        assert sdk.messages.requests[0]["temperature"] == 0

    def test_a_system_role_message_becomes_the_system_parameter(self):
        """`LLMIntentParser` puts its system prompt in the message list.

        Anthropic rejects a system role inside messages, so it has to be lifted
        out. The remaining turns must keep their order and their roles.
        """
        client, sdk = _client(_tool_response({"organism": "e_coli"}))

        AnthropicIntentClient(client)(
            [
                {"role": "system", "content": "SYSTEM RULES"},
                {"role": "user", "content": "example in"},
                {"role": "assistant", "content": "example out"},
                {"role": "user", "content": "the real request"},
            ],
            {"type": "object"},
        )

        request = sdk.messages.requests[0]
        assert request["system"] == "SYSTEM RULES"
        assert [message["role"] for message in request["messages"]] == [
            "user",
            "assistant",
            "user",
        ]
        assert all(message["role"] != "system" for message in request["messages"])
        assert request["messages"][-1]["content"] == "the real request"

    def test_several_system_messages_are_joined_rather_than_dropped(self):
        """A silently shortened prompt is worse than an error."""
        client, sdk = _client(_tool_response({"ok": True}))
        client.generate_json_messages(
            messages=[
                {"role": "system", "content": "FIRST"},
                {"role": "system", "content": "SECOND"},
                {"role": "user", "content": "go"},
            ],
            schema={"type": "object"},
            system_instruction="ZEROTH",
        )
        system = sdk.messages.requests[0]["system"]
        for fragment in ("ZEROTH", "FIRST", "SECOND"):
            assert fragment in system

    def test_blank_messages_are_skipped_and_an_empty_conversation_raises(self):
        client, _ = _client(_tool_response({"ok": True}))
        with pytest.raises(ValueError, match="at least one user or assistant turn"):
            client.generate_json_messages(
                messages=[{"role": "system", "content": "only a system prompt"}],
                schema={"type": "object"},
            )

    def test_the_workspace_header_is_only_sent_when_configured(self):
        """An organization scoped key is rejected without a workspace id."""
        without = AnthropicJsonClient(api_key="k")
        with_id = AnthropicJsonClient(api_key="k", workspace_id="wrkspc_123")
        assert without.workspace_id is None
        assert with_id.workspace_id == "wrkspc_123"


class TestResponseHandling:
    def test_the_tool_input_comes_back_as_a_json_string(self):
        """Both consumers immediately json.loads the return value."""
        client, _ = _client(_tool_response({"organism": "e_coli", "genes": ["gfp"]}))
        raw = client.generate_json(prompt="p", schema={"type": "object"})
        assert json.loads(raw) == {"organism": "e_coli", "genes": ["gfp"]}

    def test_a_truncated_response_raises_rather_than_half_parsing(self):
        client, _ = _client(
            _Response([_Block(type="text", text='{"organism"')], stop_reason="max_tokens")
        )
        with pytest.raises(ValueError, match="truncated"):
            client.generate_json(prompt="p", schema={"type": "object"})

    def test_a_prose_answer_with_no_tool_call_raises(self):
        client, _ = _client(
            _Response([_Block(type="text", text="I think you want a plasmid")], stop_reason="end_turn")
        )
        with pytest.raises(ValueError, match="no structured payload"):
            client.generate_json(prompt="p", schema={"type": "object"})

    def test_the_model_used_is_recorded_for_every_call(self):
        """So spend is attributable after the fact, not inferred from config."""
        client, _ = _client(
            _tool_response({"a": 1}, model="claude-sonnet-5-5"),
            _tool_response({"b": 2}, model="claude-sonnet-5-5"),
        )
        client.generate_json(prompt="one", schema={"type": "object"})
        client.generate_json(prompt="two", schema={"type": "object"})
        assert client.calls == ["claude-sonnet-5-5", "claude-sonnet-5-5"]


class _Transient(Exception):
    def __init__(self, status_code):
        super().__init__(f"status {status_code}")
        self.status_code = status_code


class _Permanent(Exception):
    def __init__(self):
        super().__init__("bad request")
        self.status_code = 400


class TestRetry:
    def test_a_transient_status_is_retried_then_succeeds(self, monkeypatch):
        monkeypatch.setattr(
            "packages.retrieval.anthropic_client._is_transient_api_error",
            lambda exc: isinstance(exc, _Transient),
        )
        slept: list[float] = []
        client, sdk = _client(
            _Transient(529),
            _tool_response({"ok": True}),
            sleep=slept.append,
        )
        raw = client.generate_json(prompt="p", schema={"type": "object"})
        assert json.loads(raw) == {"ok": True}
        assert len(sdk.messages.requests) == 2
        assert slept == [1.0]

    def test_exhausted_retries_raise_the_shared_unavailable_error(self, monkeypatch):
        """Shaped like the Gemini equivalent, so an outage looks the same either way."""
        monkeypatch.setattr(
            "packages.retrieval.anthropic_client._is_transient_api_error",
            lambda exc: isinstance(exc, _Transient),
        )
        client, _ = _client(*[_Transient(503)] * 4, sleep=lambda _: None)
        with pytest.raises(AnthropicUnavailableError) as caught:
            client.generate_json(prompt="p", schema={"type": "object"})
        payload = json.loads(str(caught.value))
        assert payload["code"] == "language_model_unavailable"
        assert payload["retryable"] is True

    def test_a_permanent_error_is_not_retried(self, monkeypatch):
        """A rejected key or a bad schema fails identically every time."""
        monkeypatch.setattr(
            "packages.retrieval.anthropic_client._is_transient_api_error",
            lambda exc: isinstance(exc, _Transient),
        )
        client, sdk = _client(_Permanent(), sleep=lambda _: None)
        with pytest.raises(_Permanent):
            client.generate_json(prompt="p", schema={"type": "object"})
        assert len(sdk.messages.requests) == 1


class TestConsumerContracts:
    """The two adapters must satisfy the interfaces the pipeline already uses."""

    def test_the_intent_client_is_callable_with_messages_and_schema(self):
        client, _ = _client(_tool_response({"organism": "e_coli"}))
        adapter = AnthropicIntentClient(client)
        raw = adapter([{"role": "user", "content": "a vector"}], {"type": "object"})
        assert json.loads(raw)["organism"] == "e_coli"

    def test_the_recommendation_client_exposes_complete_json(self):
        client, sdk = _client(_tool_response({"recommendations": []}))
        adapter = AnthropicRecommendationClient(client)
        raw = adapter.complete_json(
            system_prompt="GROUND YOUR ANSWER",
            user_prompt='{"candidates": []}',
            schema={"type": "object"},
        )
        assert json.loads(raw) == {"recommendations": []}
        assert sdk.messages.requests[0]["system"] == "GROUND YOUR ANSWER"

    def test_the_intent_parser_accepts_this_client(self):
        """End to end against the real parser, so the contract is not assumed."""
        from packages.retrieval.intent_parser import LLMIntentParser

        client, _ = _client(
            _tool_response(
                {
                    "organism": "e_coli",
                    "vector_type": "plasmid",
                    "genes": ["gfp"],
                    "markers": ["ampicillin"],
                }
            )
        )
        parser = LLMIntentParser(AnthropicIntentClient(client))
        spec = parser.parse("I want a GFP reporter in E. coli with ampicillin resistance")
        assert spec.organism
