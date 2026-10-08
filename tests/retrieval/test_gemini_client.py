from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from google.genai import errors

from packages.retrieval.gemini_client import (
    DEFAULT_GEMINI_MODEL,
    GEMINI_UNAVAILABLE_MESSAGE,
    GeminiJsonClient,
    GeminiRecommendationClient,
    GeminiUnavailableError,
)


class FakeModels:
    def __init__(self, response) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def generate_content(self, *, model: str, contents: object, config: object) -> object:
        self.calls.append({"model": model, "contents": contents, "config": config})
        return self.response


class SequencedModels:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    def generate_content(self, *, model: str, contents: object, config: object) -> object:
        del model, contents, config
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_gemini_json_client_uses_injected_sdk_text_response(monkeypatch) -> None:
    models = FakeModels(SimpleNamespace(text='{"ok": true}', parsed=None))
    sdk_client = SimpleNamespace(models=models)
    monkeypatch.setattr(
        GeminiJsonClient,
        "_build_config",
        lambda self, *, schema, system_instruction: {
            "schema": schema,
            "system_instruction": system_instruction,
        },
    )

    payload = GeminiJsonClient(api_key="test-key", sdk_client=sdk_client).generate_json(
        prompt="hello",
        schema={"type": "object"},
        system_instruction="system",
    )

    assert json.loads(payload) == {"ok": True}
    assert models.calls[0]["model"] == DEFAULT_GEMINI_MODEL
    assert models.calls[0]["contents"] == "hello"


def test_gemini_recommendation_client_falls_back_to_parsed_payload(monkeypatch) -> None:
    models = FakeModels(SimpleNamespace(text=None, parsed={"recommendations": []}))
    sdk_client = SimpleNamespace(models=models)
    monkeypatch.setattr(
        GeminiJsonClient,
        "_build_config",
        lambda self, *, schema, system_instruction: {
            "schema": schema,
            "system_instruction": system_instruction,
        },
    )

    client = GeminiRecommendationClient(GeminiJsonClient(api_key="test-key", sdk_client=sdk_client))
    payload = client.complete_json(system_prompt="grounding", user_prompt="{}", schema={"type": "object"})

    assert json.loads(payload) == {"recommendations": []}
    assert models.calls[0]["config"]["system_instruction"] == "grounding"


def test_gemini_json_client_retries_transient_errors_then_succeeds(monkeypatch) -> None:
    transient = errors.ServerError(503, {"error": {"message": "high demand"}})
    models = SequencedModels([transient, transient, SimpleNamespace(text='{"ok": true}', parsed=None)])
    delays: list[float] = []
    monkeypatch.setattr(GeminiJsonClient, "_build_config", lambda self, **kwargs: kwargs)

    payload = GeminiJsonClient(
        api_key="test-key",
        sdk_client=SimpleNamespace(models=models),
        sleep=delays.append,
    ).generate_json(prompt="hello", schema={"type": "object"})

    assert json.loads(payload) == {"ok": True}
    assert models.calls == 3
    assert delays == [1.0, 2.0]


def test_gemini_json_client_surfaces_retryable_error_after_three_retries(monkeypatch) -> None:
    transient = errors.ServerError(503, {"error": {"message": "high demand"}})
    models = SequencedModels([transient, transient, transient, transient])
    delays: list[float] = []
    monkeypatch.setattr(GeminiJsonClient, "_build_config", lambda self, **kwargs: kwargs)

    with pytest.raises(GeminiUnavailableError) as caught:
        GeminiJsonClient(
            api_key="test-key",
            sdk_client=SimpleNamespace(models=models),
            sleep=delays.append,
        ).generate_json(prompt="hello", schema={"type": "object"})

    assert models.calls == 4
    assert delays == [1.0, 2.0, 4.0]
    assert json.loads(str(caught.value)) == {
        "code": "language_model_unavailable",
        "message": GEMINI_UNAVAILABLE_MESSAGE,
        "retryable": True,
    }
