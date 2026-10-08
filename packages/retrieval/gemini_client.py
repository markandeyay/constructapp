from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol


#: Pinned to an exact version rather than an alias such as gemini-flash-latest,
#: because an alias moves under the build and would change intent parsing
#: behaviour with no commit to point at.
#:
#: Was gemini-2.5-flash. That id now returns 404 for a newly issued key, with the
#: message that it is "no longer available to new users", so the Gemini path was
#: dead on arrival for anyone setting the project up fresh. The id below is the
#: replacement the API itself names in that error, and it was verified end to end
#: through LLMIntentParser against the real STRICT_DESIGN_SPEC_SCHEMA.
#:
#: Note that listing the models a key may use still shows gemini-2.5-flash.
#: Appearing in that listing is not permission to call it.
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)
TRANSIENT_GEMINI_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
GEMINI_UNAVAILABLE_MESSAGE = "The language model is temporarily unavailable. Please try again in a moment."


class GeminiModelClient(Protocol):
    def generate_content(self, *, model: str, contents: Any, config: Any) -> Any: ...


class GeminiUnavailableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            json.dumps(
                {
                    "code": "language_model_unavailable",
                    "message": GEMINI_UNAVAILABLE_MESSAGE,
                    "retryable": True,
                }
            )
        )


@dataclass
class GeminiJsonClient:
    api_key: str
    model: str = DEFAULT_GEMINI_MODEL
    sdk_client: Any | None = None
    sleep: Callable[[float], None] = time.sleep
    retry_delays: tuple[float, ...] = GEMINI_RETRY_DELAYS_SECONDS

    @classmethod
    def from_env(cls) -> GeminiJsonClient:
        api_key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is required for GeminiJsonClient")
        return cls(api_key=api_key)

    def generate_json(
        self,
        *,
        prompt: str,
        schema: Mapping[str, Any],
        system_instruction: str | None = None,
    ) -> str:
        client = self._client()
        config = self._build_config(schema=schema, system_instruction=system_instruction)
        response = self._generate_with_retry(client=client, prompt=prompt, config=config)
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            return json.dumps(parsed)
        raise ValueError("Gemini client returned no structured JSON payload")

    def _generate_with_retry(self, *, client: Any, prompt: str, config: Any) -> Any:
        for attempt in range(len(self.retry_delays) + 1):
            try:
                return client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
            except Exception as exc:
                if not _is_transient_api_error(exc):
                    raise
                if attempt >= len(self.retry_delays):
                    raise GeminiUnavailableError() from exc
                self.sleep(self.retry_delays[attempt])
        raise AssertionError("Gemini retry loop exited unexpectedly")

    def _client(self) -> Any:
        if self.sdk_client is not None:
            return self.sdk_client
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - exercised only when dependency is missing
            raise RuntimeError("google-genai is required for GeminiJsonClient") from exc
        self.sdk_client = genai.Client(api_key=self.api_key)
        return self.sdk_client

    def _build_config(self, *, schema: Mapping[str, Any], system_instruction: str | None) -> Any:
        try:
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - exercised only when dependency is missing
            raise RuntimeError("google-genai is required for GeminiJsonClient") from exc
        return types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_json_schema=dict(schema),
            system_instruction=system_instruction,
        )


@dataclass(frozen=True)
class GeminiIntentClient:
    client: GeminiJsonClient

    def __call__(self, messages: list[dict[str, str]], schema: Mapping[str, Any]) -> str:
        return self.client.generate_json(prompt=_render_messages(messages), schema=schema)


@dataclass(frozen=True)
class GeminiRecommendationClient:
    client: GeminiJsonClient

    def complete_json(self, *, system_prompt: str, user_prompt: str, schema: Mapping[str, Any]) -> str:
        return self.client.generate_json(
            prompt=user_prompt,
            schema=schema,
            system_instruction=system_prompt,
        )


def _render_messages(messages: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for message in messages:
        role = str(message.get("role", "user")).strip() or "user"
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        parts.append(f"{role.upper()}:\n{content}")
    return "\n\n".join(parts)


def _is_transient_api_error(exc: Exception) -> bool:
    try:
        from google.genai import errors
    except ImportError:
        return False
    return isinstance(exc, errors.APIError) and int(exc.code) in TRANSIENT_GEMINI_STATUS_CODES
