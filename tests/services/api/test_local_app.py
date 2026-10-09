from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
import importlib

import pytest
from starlette.testclient import TestClient

from packages.application import InMemoryJobStore, InMemoryOutcomeStore, InMemorySessionStore
from packages.application.designs import InMemoryDesignStore
from packages.core.schemas import AnnotatedSequence
from packages.retrieval.gemini_client import GeminiIntentClient, GeminiRecommendationClient
from packages.retrieval.intent_parser import FakeIntentParser, LLMIntentParser
from packages.retrieval.recommender import LLMRecommendationGenerator, TemplateRecommendationGenerator


local_app = importlib.import_module("services.api.local_app")


def _annotated_sequence() -> AnnotatedSequence:
    return AnnotatedSequence(
        sequence="ACGT" * 12,
        topology="circular",
        vector_profile="bacterial_cloning_vector",
        annotation_complete=True,
        features=[],
    )


def test_load_env_defaults_only_fills_missing_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("GOOGLE_API_KEY=file-key\nDATABASE_URL=postgresql://from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_API_KEY", "process-key")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    local_app._load_env_defaults(dotenv)

    assert local_app.os.environ["GOOGLE_API_KEY"] == "process-key"
    assert local_app.os.environ["DATABASE_URL"] == "postgresql://from-dotenv"


def test_build_application_stores_prefers_postgres_only_when_tables_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_app, "_tables_available", lambda database_url, tables, require_vector_extension=False: True)
    postgres = local_app._build_application_stores("postgresql://example")
    assert type(postgres["session_store"]).__name__ == "PostgresSessionStore"
    assert type(postgres["job_store"]).__name__ == "PostgresJobStore"

    monkeypatch.setattr(local_app, "_tables_available", lambda database_url, tables, require_vector_extension=False: False)
    memory = local_app._build_application_stores("postgresql://example")
    assert isinstance(memory["session_store"], InMemorySessionStore)
    assert isinstance(memory["job_store"], InMemoryJobStore)
    assert isinstance(memory["design_store"], InMemoryDesignStore)
    assert isinstance(memory["outcome_store"], InMemoryOutcomeStore)


def test_build_local_pipeline_selects_gemini_or_offline_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    config = local_app.EmbedCorpusConfig(database_url="postgresql://example", use_fake=False)
    monkeypatch.setattr(local_app, "build_embedder", lambda config: object())
    monkeypatch.setattr(local_app, "build_vector_store", lambda config, embedder: object())
    monkeypatch.setattr(local_app, "HybridRetriever", lambda **kwargs: kwargs)

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    live = local_app._build_local_pipeline(config)
    assert isinstance(live.parser, LLMIntentParser)
    assert isinstance(live.parser._call_llm, GeminiIntentClient)
    assert isinstance(live.recommendation_generator, LLMRecommendationGenerator)
    assert isinstance(live.recommendation_generator.client, GeminiRecommendationClient)

    monkeypatch.setenv("GOOGLE_API_KEY", "")
    offline = local_app._build_local_pipeline(config)
    assert isinstance(offline.parser, FakeIntentParser)
    assert isinstance(offline.recommendation_generator, TemplateRecommendationGenerator)


def test_build_local_app_runs_design_synchronously(monkeypatch: pytest.MonkeyPatch) -> None:
    stores = {
        "session_store": InMemorySessionStore(),
        "job_store": InMemoryJobStore(),
        "design_store": InMemoryDesignStore(),
        "outcome_store": InMemoryOutcomeStore(),
    }
    pipeline = SimpleNamespace(run=lambda free_text: SimpleNamespace(reannotated_sequence=_annotated_sequence()))
    monkeypatch.setattr(local_app, "_load_env_defaults", lambda path: None)
    monkeypatch.setattr(local_app, "_assert_corpus_ready", lambda database_url: None)
    migration_calls: list[bool] = []
    monkeypatch.setattr(local_app, "_run_app_migrations", lambda: migration_calls.append(True))
    monkeypatch.setattr(local_app, "_build_application_stores", lambda database_url: stores)
    monkeypatch.setattr(local_app, "_build_local_pipeline", lambda config: pipeline)
    monkeypatch.setattr(
        local_app.EmbedCorpusConfig,
        "from_env",
        classmethod(
            lambda cls, **kwargs: cls(
                database_url="postgresql://example",
                use_fake=False,
                local_files_only=False,
                batch_size=1,
                limit=None,
                hf_cache_dir=None,
            )
        ),
    )
    monkeypatch.setattr(
        "packages.application.design_jobs.spike_result_as_dict",
        lambda result: {
            "design_spec": {"organism": "Escherichia coli", "vector_type": "bacterial_cloning_vector"},
            "annotated_sequence": result.reannotated_sequence.model_dump(mode="json"),
            "validation_report": {"overall": "PASS"},
            "retrieved_templates": [],
            "recommendations": [{"why_relevant": "Stored design is relevant."}],
        },
    )

    client = TestClient(local_app.build_local_app())
    session_id = client.post("/v1/sessions").json()["session_id"]

    accepted = client.post(f"/v1/sessions/{session_id}/design", json={"goal": "build a cloning vector"})
    job_id = accepted.json()["job_id"]
    polled = client.get(f"/v1/jobs/{job_id}")

    assert accepted.status_code == 202
    assert polled.status_code == 200
    result = polled.json()["result"]
    assert result["design_id"]
    assert result["recommendation_text"] == "Stored design is relevant."
    design = client.get(f"/v1/designs/{result['design_id']}").json()
    assert design["job_id"] == job_id
    assert design["annotated_sequence"]["vector_profile"] == "bacterial_cloning_vector"
    assert migration_calls == [True]


def test_queue_backend_defaults_to_inline_and_rejects_unknown_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(local_app.QUEUE_BACKEND_ENV, raising=False)
    assert local_app.queue_backend() == "inline"
    monkeypatch.setenv(local_app.QUEUE_BACKEND_ENV, " Celery ")
    assert local_app.queue_backend() == "celery"
    monkeypatch.setenv(local_app.QUEUE_BACKEND_ENV, "celry")
    with pytest.raises(RuntimeError, match="CONSTRUCT_QUEUE_BACKEND"):
        local_app.queue_backend()


def _stub_runtime(monkeypatch: pytest.MonkeyPatch, stores: dict[str, Any], built: list[bool]) -> None:
    def fake_runtime(*, with_handler: bool = True) -> Any:
        built.append(with_handler)
        return local_app.EmbedCorpusConfig(database_url="postgresql://example", use_fake=False), stores, (
            object() if with_handler else None
        )

    monkeypatch.setattr(local_app, "build_job_runtime", fake_runtime)
    monkeypatch.setattr(local_app, "_build_template_reader", lambda database_url: (lambda ids: {}))


def test_build_local_app_celery_backend_wires_celery_queue_without_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.application import PostgresJobStore
    from services.worker import CeleryJobQueue

    monkeypatch.setenv(local_app.QUEUE_BACKEND_ENV, "celery")
    built: list[bool] = []
    stores = {
        "session_store": InMemorySessionStore(),
        "job_store": PostgresJobStore("postgresql://example"),
        "design_store": InMemoryDesignStore(),
        "outcome_store": InMemoryOutcomeStore(),
    }
    _stub_runtime(monkeypatch, stores, built)
    monkeypatch.setattr("services.worker.build_celery_app", lambda **kwargs: object())

    app = local_app.build_local_app()

    assert isinstance(app.state.job_queue, CeleryJobQueue)
    # The API never runs a job in this mode, so it must not pay for the pipeline.
    assert built == [False]


def test_build_local_app_celery_backend_refuses_in_memory_job_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(local_app.QUEUE_BACKEND_ENV, "celery")
    stores = {
        "session_store": InMemorySessionStore(),
        "job_store": InMemoryJobStore(),
        "design_store": InMemoryDesignStore(),
        "outcome_store": InMemoryOutcomeStore(),
    }
    _stub_runtime(monkeypatch, stores, [])
    with pytest.raises(RuntimeError, match="Postgres-backed stores"):
        local_app.build_local_app()


def test_build_local_app_defaults_to_inline_fake_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.application import FakeJobQueue

    monkeypatch.delenv(local_app.QUEUE_BACKEND_ENV, raising=False)
    stores = {
        "session_store": InMemorySessionStore(),
        "job_store": InMemoryJobStore(),
        "design_store": InMemoryDesignStore(),
        "outcome_store": InMemoryOutcomeStore(),
    }
    built: list[bool] = []
    _stub_runtime(monkeypatch, stores, built)

    app = local_app.build_local_app()

    assert isinstance(app.state.job_queue, FakeJobQueue)
    assert built == [True]
