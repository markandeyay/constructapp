from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from packages.application.design_jobs import GenerationDesignJobHandler
from packages.application.designs import InMemoryDesignStore, PostgresDesignStore
from packages.core.schemas import AnnotatedSequence, GeneratedSequence, SequenceSpan


@dataclass
class FakePipeline:
    calls: list[str]
    result: Any | None = None

    def run(self, free_text: str) -> Any:
        self.calls.append(free_text)
        return self.result if self.result is not None else object()


def _annotated_sequence() -> AnnotatedSequence:
    return AnnotatedSequence(
        sequence="ACGT" * 10,
        topology="circular",
        vector_profile="bacterial_cloning_vector",
        annotation_complete=True,
        features=[],
    )


def test_generation_design_job_handler_uses_accumulated_context(monkeypatch) -> None:
    design_store = InMemoryDesignStore()
    pipeline = FakePipeline(calls=[], result=SimpleNamespace(reannotated_sequence=_annotated_sequence()))
    monkeypatch.setattr(
        "packages.application.design_jobs.spike_result_as_dict",
        lambda result: {
            "design_spec": {"organism": "Escherichia coli"},
            "annotated_sequence": result.reannotated_sequence.model_dump(mode="json"),
            "validation_report": {"overall": "PASS"},
            "retrieved_templates": [],
            "recommendations": [{"why_relevant": "Template is relevant."}],
        },
    )

    result = GenerationDesignJobHandler(pipeline=pipeline, design_store=design_store)(
        job_id="job-ctx",
        session_id="session-1",
        action="refine",
        payload={"instruction": "switch marker", "context": ["build vector", "switch marker"]},
    )

    assert pipeline.calls == ["build vector\nswitch marker"]
    assert result["design_spec"] == {"organism": "Escherichia coli"}
    assert result["recommendation_text"] == "Template is relevant."
    assert result["design_id"]
    stored = design_store.get(result["design_id"])
    assert stored is not None
    assert stored.job_id == "job-ctx"
    assert stored.session_id == "session-1"


def _sequence_span() -> SequenceSpan:
    return SequenceSpan(
        start=0,
        end=12,
        source="retrieved_template:curated:pUC19",
        source_id="curated:pUC19",
        source_start=0,
        source_end=12,
    )


def test_generation_design_job_handler_stores_and_returns_generated_provenance(monkeypatch) -> None:
    design_store = InMemoryDesignStore()
    generated = GeneratedSequence(
        annotated_sequence=_annotated_sequence(),
        model_version="fake-template-generator-v1",
        parent_template_ids=["curated:pUC19"],
        sequence_spans=[_sequence_span()],
    )
    pipeline = FakePipeline(
        calls=[],
        result=SimpleNamespace(reannotated_sequence=_annotated_sequence(), generated=generated),
    )
    monkeypatch.setattr(
        "packages.application.design_jobs.spike_result_as_dict",
        lambda result: {
            "design_spec": {"organism": "Escherichia coli"},
            "annotated_sequence": result.reannotated_sequence.model_dump(mode="json"),
            "validation_report": {"overall": "PASS"},
            "retrieved_templates": [],
            "recommendations": [],
            "generated": result.generated.model_dump(mode="json"),
        },
    )

    result = GenerationDesignJobHandler(pipeline=pipeline, design_store=design_store)(
        job_id="job-spans",
        session_id="session-1",
        action="design",
        payload={"text": "build a cloning vector"},
    )

    stored = design_store.get(result["design_id"])
    assert stored is not None
    assert stored.template_ids == ["curated:pUC19"]
    assert stored.sequence_spans == [_sequence_span()]
    assert result["template_ids"] == ["curated:pUC19"]
    assert result["sequence_spans"] == [_sequence_span().model_dump(mode="json")]


def test_in_memory_design_store_round_trips_provenance_and_defaults_to_empty() -> None:
    store = InMemoryDesignStore()

    with_provenance = store.create(
        session_id="session-1",
        job_id="job-1",
        annotated_sequence=_annotated_sequence(),
        template_ids=["curated:pUC19"],
        sequence_spans=[_sequence_span()],
    )
    without_provenance = store.create(
        session_id="session-1",
        job_id="job-2",
        annotated_sequence=_annotated_sequence(),
    )

    assert store.get(with_provenance.design_id) == with_provenance
    assert with_provenance.template_ids == ["curated:pUC19"]
    assert with_provenance.sequence_spans == [_sequence_span()]
    # A caller that says nothing about provenance gets no provenance, not a claim.
    assert without_provenance.template_ids == []
    assert without_provenance.sequence_spans == []


def test_postgres_design_store_round_trips_provenance_through_the_payload_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_at = datetime(2026, 6, 2, tzinfo=UTC)
    inserts: list[tuple[Any, ...]] = []
    annotated = _annotated_sequence()

    class FakeCursor:
        def __init__(self, row: Any) -> None:
            self.row = row

        def fetchone(self) -> Any:
            return self.row

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb

        def execute(self, query: str, params: tuple[Any, ...] | None = None) -> FakeCursor:
            if "INSERT INTO designs" in query:
                assert params is not None
                inserts.append(params)
                return FakeCursor(None)
            payload = inserts[0][3].obj
            return FakeCursor(
                (
                    "design-1",
                    "session-1",
                    "job-1",
                    annotated.model_dump(mode="json"),
                    payload,
                    created_at,
                    created_at,
                )
            )

    monkeypatch.setattr("packages.application.designs.psycopg.connect", lambda _: FakeConnection())

    store = PostgresDesignStore("postgresql://example")
    store.create(
        session_id="session-1",
        job_id="job-1",
        annotated_sequence=annotated,
        design_id="design-1",
        template_ids=["curated:pUC19"],
        sequence_spans=[_sequence_span()],
    )
    loaded = store.get("design-1")

    assert inserts[0][3].obj == {
        "template_ids": ["curated:pUC19"],
        "sequence_spans": [_sequence_span().model_dump(mode="json")],
    }
    assert loaded is not None
    assert loaded.template_ids == ["curated:pUC19"]
    assert loaded.sequence_spans == [_sequence_span()]


def test_postgres_design_store_loads_records_written_before_provenance_existed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_at = datetime(2026, 6, 2, tzinfo=UTC)
    annotated = _annotated_sequence()
    # Rows predating this field hold an empty payload, and one row holds NULL
    # because the column is nullable. Neither may fail the read.
    legacy_payloads: list[Any] = [{}, None]

    class FakeCursor:
        def __init__(self, row: Any) -> None:
            self.row = row

        def fetchone(self) -> Any:
            return self.row

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb

        def execute(self, query: str, params: tuple[Any, ...] | None = None) -> FakeCursor:
            del query, params
            return FakeCursor(
                (
                    "design-old",
                    "session-1",
                    "job-1",
                    annotated.model_dump(mode="json"),
                    legacy_payloads.pop(0),
                    created_at,
                    created_at,
                )
            )

    monkeypatch.setattr("packages.application.designs.psycopg.connect", lambda _: FakeConnection())

    store = PostgresDesignStore("postgresql://example")
    empty_payload = store.get("design-old")
    null_payload = store.get("design-old")

    for loaded in (empty_payload, null_payload):
        assert loaded is not None
        assert loaded.design_id == "design-old"
        assert loaded.annotated_sequence.vector_profile == "bacterial_cloning_vector"
        assert loaded.template_ids == []
        assert loaded.sequence_spans == []


def test_generation_design_job_handler_rejects_invalid_action_and_empty_text() -> None:
    pipeline = FakePipeline(calls=[])
    handler = GenerationDesignJobHandler(pipeline=pipeline, design_store=InMemoryDesignStore())

    for action, payload in [("delete", {"text": "no"}), ("design", {})]:
        try:
            handler(job_id="job-1", session_id="session-1", action=action, payload=payload)
        except ValueError:
            pass
        else:
            raise AssertionError("expected invalid queued design job to fail")


def test_generation_design_job_handler_returns_clarification_as_result() -> None:
    class ClarifyingPipeline:
        def run(self, free_text: str) -> Any:
            assert free_text == "make a viral vector"
            raise ValueError("intent clarification required: Which viral vector system should this use?")

    design_store = InMemoryDesignStore()
    result = GenerationDesignJobHandler(ClarifyingPipeline(), design_store)(
        job_id="job-clarify",
        session_id="session-1",
        action="design",
        payload={"text": "make a viral vector"},
    )

    assert result["design_id"] is None
    assert result["clarification_question"] == "Which viral vector system should this use?"
    assert result["design_spec"]["clarification_needed"] is True
    assert design_store.records == {}
