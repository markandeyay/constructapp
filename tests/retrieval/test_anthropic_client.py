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


def _text_response(text, **kwargs):
    """What `output_config` really returns: the schema conforming JSON as text."""
    return _Response([_Block(type="text", text=text)], stop_reason="end_turn", **kwargs)


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
    def test_the_schema_is_sent_through_output_config(self):
        """The native structured output parameter, not a forced tool.

        The forced tool approach is the usual way to get schema conformant JSON
        out of the Messages API, and the live API rejects it for these models:
        `tool_choice: type "tool" and "any" are not supported for this model`.
        So no tool is declared at all.
        """
        schema = {"type": "object", "properties": {"organism": {"type": "string"}}}
        client, sdk = _client(_text_response('{"organism": "e_coli"}'))

        client.generate_json(prompt="build a vector", schema=schema)

        request = sdk.messages.requests[0]
        assert request["output_config"] == {
            "format": {"type": "json_schema", "schema": schema}
        }
        assert "tools" not in request
        assert "tool_choice" not in request

    def test_temperature_is_not_sent_because_the_model_rejects_it(self):
        """These models answer `temperature is deprecated for this model` with a 400.

        Pinned by a test because sending it is a total request failure, not a
        degradation, so a well meaning reintroduction of temperature=0 for
        determinism would break every call.
        """
        client, sdk = _client(_text_response('{"organism": "e_coli"}'))
        client.generate_json(prompt="p", schema={"type": "object"})
        assert "temperature" not in sdk.messages.requests[0]

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

    def test_an_empty_response_raises(self):
        client, _ = _client(_Response([], stop_reason="end_turn"))
        with pytest.raises(ValueError, match="no structured payload"):
            client.generate_json(prompt="p", schema={"type": "object"})

    def test_non_json_text_is_passed_through_for_the_caller_to_reject(self):
        """This client does not parse the payload, so it cannot pre judge it.

        With `output_config` the text blocks ARE the structured result, so there
        is no way to distinguish prose from a payload here without parsing. The
        consumers parse and validate, and the next test shows the real parser
        rejecting it, which is where the error belongs.
        """
        client, _ = _client(_text_response("I think you want a plasmid"))
        assert client.generate_json(prompt="p", schema={"type": "object"}) == (
            "I think you want a plasmid"
        )

    def test_the_intent_parser_rejects_a_non_json_payload(self):
        from packages.retrieval.intent_parser import LLMIntentParser

        client, _ = _client(_text_response("not json at all"))
        parser = LLMIntentParser(AnthropicIntentClient(client))
        with pytest.raises(ValueError, match="invalid JSON"):
            parser.parse("a vector")

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


class TestSchemaSanitizing:
    """The structured output dialect rejects JSON Schema value constraints.

    Established from the live API, which answers a pydantic generated schema with
    `output_config.format.schema: For 'integer' type, property 'minimum' is not
    supported`. The real recommendation schema hits this, so it is not
    hypothetical.
    """

    def test_value_constraints_are_removed(self):
        from packages.retrieval.anthropic_client import sanitize_schema

        cleaned = sanitize_schema(
            {
                "type": "object",
                "properties": {
                    "rank": {"type": "integer", "minimum": 1, "title": "Rank"},
                    "name": {"type": "string", "minLength": 1, "pattern": "^x"},
                    "tags": {"type": "array", "items": {"type": "string"}, "minItems": 2},
                },
                "required": ["rank"],
                "additionalProperties": False,
            }
        )

        assert "minimum" not in cleaned["properties"]["rank"]
        assert "minLength" not in cleaned["properties"]["name"]
        assert "pattern" not in cleaned["properties"]["name"]
        assert "minItems" not in cleaned["properties"]["tags"]

    def test_structure_and_enums_survive(self):
        """Shape and permitted values are what the model actually needs told."""
        from packages.retrieval.anthropic_client import sanitize_schema

        cleaned = sanitize_schema(
            {
                "type": "object",
                "properties": {
                    "rank": {"type": "integer", "minimum": 1},
                    "source": {"type": "string", "enum": ["addgene", "genbank"]},
                    "tags": {"type": "array", "items": {"type": "string", "maxLength": 4}},
                },
                "required": ["rank", "source"],
                "additionalProperties": False,
            }
        )

        assert cleaned["type"] == "object"
        assert cleaned["required"] == ["rank", "source"]
        assert cleaned["additionalProperties"] is False
        assert cleaned["properties"]["source"]["enum"] == ["addgene", "genbank"]
        assert cleaned["properties"]["rank"]["type"] == "integer"
        assert cleaned["properties"]["tags"]["items"]["type"] == "string"

    def test_the_real_recommendation_schema_becomes_acceptable(self):
        from packages.retrieval.anthropic_client import (
            UNSUPPORTED_SCHEMA_KEYWORDS,
            sanitize_schema,
        )
        from packages.retrieval.recommender import RECOMMENDATION_RESPONSE_SCHEMA

        def keywords(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    yield key
                    yield from keywords(value)
            elif isinstance(node, list):
                for item in node:
                    yield from keywords(item)

        before = set(keywords(RECOMMENDATION_RESPONSE_SCHEMA)) & UNSUPPORTED_SCHEMA_KEYWORDS
        assert before, "this test is pointless if the real schema has nothing to strip"
        after = set(keywords(sanitize_schema(RECOMMENDATION_RESPONSE_SCHEMA))) & (
            UNSUPPORTED_SCHEMA_KEYWORDS
        )
        assert after == set()

    def test_the_sanitized_schema_is_what_gets_sent(self):
        client, sdk = _client(_text_response('{"rank": 1}'))
        client.generate_json(
            prompt="p", schema={"type": "object", "properties": {"rank": {"type": "integer", "minimum": 1}}}
        )
        sent = sdk.messages.requests[0]["output_config"]["format"]["schema"]
        assert "minimum" not in sent["properties"]["rank"]

    def test_stripping_does_not_weaken_the_real_check(self):
        """The constraint still exists, it is just enforced one layer later.

        A rank of 0 is rejected by the pydantic model on the return path, so the
        rule is not lost by being removed from the wire format.
        """
        import pytest as _pytest
        from pydantic import ValidationError

        from packages.core.schemas.models import PlasmidRecommendation

        with _pytest.raises(ValidationError):
            PlasmidRecommendation.model_validate(
                {"plasmid_id": "curated:x", "rank": 0, "score": 0.5, "why_relevant": "because"}
            )
