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
chosen. All three were established by calling the live API, not from
documentation:

**Structured output uses `output_config`, the native JSON schema feature.** An
earlier version of this module declared the schema as a tool and forced it with
`tool_choice`, which is the usual way to get schema conformant JSON from the
Messages API. The live API rejects it for these models: `tool_choice: type "tool"
and "any" are not supported for this model`. The native format parameter is both
supported and a better fit, since the payload arrives as text already conforming
to the schema rather than as a tool call to unwrap.

**`temperature` is not sent, because it is deprecated for these models.** The API
rejects the request outright with `temperature is deprecated for this model`.
This has a consequence worth stating rather than glossing: the Gemini client
pins temperature to zero, and this one cannot, so identical input is not
guaranteed to produce an identical DesignSpec. The schema constrains the SHAPE of
the output and says nothing about its content. Section 3.3 constraint 3 is not
weakened by this, because that constraint governs validators and no validator
calls a model; the deterministic engine decides every verdict either way. What is
affected is intent parsing, where the model's reading of a free text request may
vary between calls.

**`system` is a parameter, not a message.** `LLMIntentParser` builds a message
list whose first entry has role "system". Anthropic takes the system prompt
separately, so system entries are lifted out and concatenated, and the remaining
user and assistant turns pass through in order.

And the model is an allowlist, not a default. See `ALLOWED_MODELS`.
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


#: JSON Schema keywords the structured output dialect rejects. Established from
#: the live API, which answers for example
#: `output_config.format.schema: For 'integer' type, property 'minimum' is not
#: supported` with a 400.
#:
#: These are all VALUE constraints, not structural ones. Stripping them changes
#: what the model is told, not what is accepted: both consumers validate the
#: returned payload against a pydantic model that still carries every one of
#: these rules, so a rank of 0 or an empty plasmid_id is still rejected, just one
#: layer later and as a `ValueError` rather than as a schema violation. The
#: alternative, weakening the pydantic models to match this dialect, would have
#: removed a real check from the whole system to satisfy one provider.
UNSUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "pattern",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minProperties",
        "maxProperties",
    }
)


def sanitize_schema(schema: Any) -> Any:
    """Recursively drop keywords the structured output dialect does not accept.

    Structure is preserved exactly: types, properties, required, items, enum and
    additionalProperties all survive, so the model is still told the shape it has
    to produce and which values are permitted where an enum says so.
    """
    if isinstance(schema, Mapping):
        return {
            key: sanitize_schema(value)
            for key, value in schema.items()
            if key not in UNSUPPORTED_SCHEMA_KEYWORDS
        }
    if isinstance(schema, (list, tuple)):
        return [sanitize_schema(item) for item in schema]
    return schema


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
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
            # The native structured output format. No `temperature` key: these
            # models reject it as deprecated, which the module docstring covers.
            "output_config": {
                "format": {"type": "json_schema", "schema": sanitize_schema(dict(schema))},
            },
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
    """The schema conforming JSON text from a response, as a string.

    `output_config` makes the model's text blocks the structured payload, so the
    text is concatenated and returned without being parsed here. The caller
    parses and validates it against a pydantic model, and a payload that does not
    survive that is the caller's error to report.

    Truncation is checked first and explicitly. A `max_tokens` stop leaves
    syntactically invalid JSON, and the resulting error would otherwise surface as
    an unhelpful decode failure several layers away from its cause.

    A `tool_use` block is still read, so a response produced by the older forced
    tool request shape is understood rather than rejected. Nothing in this module
    sends that shape any more, and these models refuse it, but a cached or
    replayed response costs one branch to keep working.
    """
    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "max_tokens":
        raise ValueError(
            "Anthropic client response was truncated before the structured result was "
            "complete; raise max_tokens"
        )

    text_parts: list[str] = []
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == (
            STRUCTURED_OUTPUT_TOOL
        ):
            return json.dumps(getattr(block, "input", None))
        text = getattr(block, "text", None)
        if isinstance(text, str):
            text_parts.append(text)

    payload = "".join(text_parts).strip()
    if payload:
        return payload
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
