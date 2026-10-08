"""Claude backed intent parsing and grounded recommendation.

A drop in alternative to `gemini_client`, implementing the same two consumer
interfaces so `LLMIntentParser` and `LLMRecommendationGenerator` cannot tell the
difference:

* `AnthropicIntentClient.__call__(messages, schema) -> str`
* `AnthropicRecommendationClient.complete_json(system_prompt, user_prompt, schema) -> str`

Both return a JSON string, because both consumers immediately `json.loads` it and
validate the result against a pydantic model. Nothing here parses or interprets
the payload; a malformed response is the consumer's `ValueError`, not a silently
repaired object.

Three things differ from the Gemini client, each forced by the API rather than
chosen:

**Structured output comes from a forced tool call.** The Messages API has no
"respond in this JSON schema" parameter. The schema is therefore declared as a
tool's `input_schema` and the model is required to call it through
`tool_choice`, so the response arrives as that tool's validated input. Reading
JSON back out of prose would be guesswork by comparison.

**`system` is a parameter, not a message.** `LLMIntentParser` builds a message
list whose first entry has role "system". Anthropic takes the system prompt
separately, so system entries are lifted out and concatenated, and the remaining
user and assistant turns pass through in order.

**The model is an allowlist, not a default.** See `ALLOWED_MODELS`.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

#: The only models this client may use. An id outside this set raises when the
#: client is constructed, so a misconfiguration is a startup failure rather than
#: a silent and expensive call made once per design request.
#:
#: Opus is excluded deliberately and by operator instruction. Excluding it here
#: rather than merely defaulting away from it means editing an environment
#: variable cannot reach it: there is no value of ANTHROPIC_MODEL that selects
#: Opus, which is the difference between a policy and a preference.
ALLOWED_MODELS = frozenset({"claude-sonnet-5-5", "claude-haiku-5-5"})

#: Intent parsing and recommendation are structured extraction over a short
#: context, which Sonnet does well, and this runs once per design request.
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"

#: Matches the Gemini client's ladder, so a provider swap does not change how
#: long a caller can be kept waiting.
ANTHROPIC_RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)
TRANSIENT_ANTHROPIC_STATUS_CODES = frozenset({429, 500, 502, 503, 504, 529})
ANTHROPIC_UNAVAILABLE_MESSAGE = (
    "The language model is temporarily unavailable. Please try again in a moment."
)

#: The forced tool. The name is visible to the model and says what it is for.
STRUCTURED_OUTPUT_TOOL = "emit_structured_result"

#: Enough for a DesignSpec or a recommendation set, which are small objects. A
#: truncated structured response is a hard failure below, not a partial parse.
DEFAULT_MAX_TOKENS = 4096


class AnthropicModelNotAllowedError(ValueError):
    """Raised at construction when a model outside `ALLOWED_MODELS` is requested."""

    def __init__(self, model: str) -> None:
        allowed = ", ".join(sorted(ALLOWED_MODELS))
        super().__init__(
            f"model {model!r} is not permitted by this build; allowed models are: {allowed}. "
            "This is enforced rather than defaulted, so there is no configuration that "
            "selects a model outside the list."
        )
        self.model = model


class AnthropicUnavailableError(RuntimeError):
    """Transient upstream failure, shaped like the Gemini client's equivalent.

    The message is a JSON envelope because the API error handler reads these
    fields; see `GeminiUnavailableError`, which this deliberately mirrors so the
    two providers surface an outage identically to the user.
    """

    def __init__(self) -> None:
        super().__init__(
            json.dumps(
                {
                    "code": "language_model_unavailable",
                    "message": ANTHROPIC_UNAVAILABLE_MESSAGE,
                    "retryable": True,
                }
            )
        )


def validate_model(model: str) -> str:
    """The single place a model id is checked. Raises rather than falling back."""
    normalized = (model or "").strip()
    if normalized not in ALLOWED_MODELS:
        raise AnthropicModelNotAllowedError(normalized)
    return normalized


@dataclass
class AnthropicJsonClient:
    """Returns schema conformant JSON from Claude, or raises.

    `workspace_id` is required when the API key is scoped to an organization
    rather than to a single workspace; such a key is rejected by the API unless
    every request names a workspace. A key already scoped to one workspace needs
    no id, so this stays optional and is simply omitted when absent.
    """

    api_key: str
    model: str = DEFAULT_ANTHROPIC_MODEL
    workspace_id: str | None = None
    max_tokens: int = DEFAULT_MAX_TOKENS
    sdk_client: Any | None = None
    sleep: Callable[[float], None] = time.sleep
    retry_delays: tuple[float, ...] = ANTHROPIC_RETRY_DELAYS_SECONDS
    #: Every call records the model it used, so spend is attributable after the
    #: fact rather than inferred from a configuration file.
    calls: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.model = validate_model(self.model)

    @classmethod
    def from_env(cls) -> AnthropicJsonClient:
        api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for AnthropicJsonClient")
        # An operator may pin a different ALLOWED model, and nothing else.
        model = (os.environ.get("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL).strip()
        workspace_id = (os.environ.get("ANTHROPIC_WORKSPACE_ID") or "").strip() or None
        return cls(api_key=api_key, model=model, workspace_id=workspace_id)

    def generate_json(
        self,
        *,
        prompt: str,
        schema: Mapping[str, Any],
        system_instruction: str | None = None,
    ) -> str:
        """Single turn convenience wrapper, matching the Gemini client's signature."""
        return self.generate_json_messages(
            messages=[{"role": "user", "content": prompt}],
            schema=schema,
            system_instruction=system_instruction,
        )

    def generate_json_messages(
        self,
        *,
        messages: Sequence[Mapping[str, str]],
        schema: Mapping[str, Any],
        system_instruction: str | None = None,
    ) -> str:
        """The real entry point: a full conversation plus a required output schema."""
        system_text, turns = _split_system(messages, system_instruction)
        if not turns:
            raise ValueError("Anthropic client needs at least one user or assistant turn")

        response = self._create_with_retry(
            system=system_text,
            messages=turns,
            schema=schema,
        )
        self.calls.append(getattr(response, "model", self.model))
        return _structured_payload(response)

    def _create_with_retry(
        self,
        *,
        system: str | None,
        messages: list[dict[str, Any]],
        schema: Mapping[str, Any],
    ) -> Any:
        client = self._client()
        tool = {
            "name": STRUCTURED_OUTPUT_TOOL,
            "description": (
                "Return the result as this tool's input. Every field required by the "
                "schema must be present."
            ),
            "input_schema": dict(schema),
        }
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            # Zero temperature, because an intent parser that returns a different
            # DesignSpec for the same sentence is not one anybody can validate.
            "temperature": 0,
            "messages": messages,
            "tools": [tool],
            "tool_choice": {"type": "tool", "name": STRUCTURED_OUTPUT_TOOL},
        }
        if system:
            request["system"] = system

        for attempt in range(len(self.retry_delays) + 1):
            try:
                return client.messages.create(**request)
            except Exception as exc:
                if not _is_transient_api_error(exc):
                    raise
                if attempt >= len(self.retry_delays):
                    raise AnthropicUnavailableError() from exc
                self.sleep(self.retry_delays[attempt])
        raise AssertionError("Anthropic retry loop exited unexpectedly")

    def _client(self) -> Any:
        if self.sdk_client is not None:
            return self.sdk_client
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - only when the dependency is absent
            raise RuntimeError("anthropic is required for AnthropicJsonClient") from exc
        headers = {"anthropic-workspace-id": self.workspace_id} if self.workspace_id else None
        self.sdk_client = anthropic.Anthropic(api_key=self.api_key, default_headers=headers)
        return self.sdk_client


@dataclass(frozen=True)
class AnthropicIntentClient:
    """Adapts `LLMIntentParser`'s `call_llm(messages, schema)` contract."""

    client: AnthropicJsonClient

    def __call__(self, messages: list[dict[str, str]], schema: Mapping[str, Any]) -> str:
        return self.client.generate_json_messages(messages=messages, schema=schema)


@dataclass(frozen=True)
class AnthropicRecommendationClient:
    """Adapts `LLMRecommendationGenerator`'s `complete_json` contract."""

    client: AnthropicJsonClient

    def complete_json(
        self, *, system_prompt: str, user_prompt: str, schema: Mapping[str, Any]
    ) -> str:
        return self.client.generate_json(
            prompt=user_prompt,
            schema=schema,
            system_instruction=system_prompt,
        )


def _split_system(
    messages: Sequence[Mapping[str, str]], system_instruction: str | None
) -> tuple[str | None, list[dict[str, Any]]]:
    """Lift system entries out of a message list and keep the rest in order.

    `LLMIntentParser` puts its system prompt in the message list, which the
    Anthropic API does not accept. Several system entries are joined rather than
    the last one winning, because dropping one would quietly discard part of a
    prompt, and a prompt that is silently shortened is worse than an error.
    """
    system_parts: list[str] = []
    if system_instruction and system_instruction.strip():
        system_parts.append(system_instruction.strip())

    turns: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role", "user")).strip().lower() or "user"
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        if role == "system":
            system_parts.append(content)
            continue
        if role not in {"user", "assistant"}:
            # An unknown role is treated as the user speaking rather than
            # dropped, so no part of a prompt disappears without a trace.
            role = "user"
        turns.append({"role": role, "content": content})

    return ("\n\n".join(system_parts) or None), turns


def _structured_payload(response: Any) -> str:
    """Pull the forced tool call's input out of a response, as a JSON string.

    Raises when the model answered in prose instead of calling the tool, which
    `tool_choice` should make impossible; it is checked because a stop reason of
    `max_tokens` can truncate a response into exactly that shape, and a
    truncated structured result must fail rather than be half parsed.
    """
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == (
            STRUCTURED_OUTPUT_TOOL
        ):
            return json.dumps(getattr(block, "input", None))

    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "max_tokens":
        raise ValueError(
            "Anthropic client response was truncated before the structured result was "
            "complete; raise max_tokens"
        )
    raise ValueError(
        f"Anthropic client returned no structured payload (stop_reason={stop_reason!r})"
    )


def _is_transient_api_error(exc: Exception) -> bool:
    """True for a retryable upstream failure, false for anything we caused.

    A connection error is retryable because it says nothing about the request. A
    4xx other than 429 is not: a bad schema or a rejected key fails the same way
    every time, and retrying it three times only delays the error.
    """
    try:
        import anthropic
    except ImportError:
        return False
    if isinstance(exc, anthropic.APIConnectionError):
        return True
    status = getattr(exc, "status_code", None)
    return isinstance(status, int) and status in TRANSIENT_ANTHROPIC_STATUS_CODES
