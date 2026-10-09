from __future__ import annotations

"""Deterministic API app used by the browser-level full-stack E2E target."""

from collections.abc import Sequence
from typing import Any, Mapping

from packages.application import FakeJobQueue, InMemoryDesignStore, InMemoryJobStore, InMemorySessionStore
from packages.core.schemas import AnnotatedFeature, AnnotatedSequence, SequenceSpan, SequenceTopology
from services.api.app import RateLimitConfig, create_app


DESIGN_ID = "e2e-design"

#: The template this fixture's candidate is grounded in. The browser journey ends
#: in a GenBank download, and that download now passes through the section 11.1
#: provenance gate, which verifies a plasmid span against the template record it
#: names. So this fixture has to supply both halves: a span saying where the
#: candidate's bases came from, and the record to compare them against. Supplying
#: only the span would be refused, which is the gate working correctly.
#:
#: Both halves come from `_annotated_sequence()` below, so the fixture is
#: self consistent by construction and the journey exercises the real gate rather
#: than bypassing it. This is a deterministic test fixture, not corpus data: the
#: template id is local to this app and resolves nowhere else.
TEMPLATE_ID = "curated:e2e-template"

_sessions = InMemorySessionStore()
_designs = InMemoryDesignStore()


def _annotated_sequence() -> AnnotatedSequence:
    sequence = "ATGC" * 300
    return AnnotatedSequence(
        sequence=sequence,
        topology=SequenceTopology.CIRCULAR,
        vector_profile="e2e_reporter_vector",
        annotation_complete=True,
        features=[
            AnnotatedFeature(start=0, end=180, type="promoter", strand=1, name="CMV promoter", confidence=0.95),
            AnnotatedFeature(start=210, end=780, type="GOI", strand=1, name="EGFP", confidence=0.98),
            AnnotatedFeature(start=820, end=980, type="terminator", strand=1, name="SV40 polyA", confidence=0.91),
            AnnotatedFeature(start=1000, end=1160, type="ORI", strand=1, name="pUC origin", confidence=0.93),
        ],
    )


def _handle_design_job(*, job_id: str, session_id: str, action: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    annotated = _annotated_sequence()
    _designs.create(
        session_id=session_id,
        job_id=job_id,
        design_id=DESIGN_ID,
        annotated_sequence=annotated,
        template_ids=[TEMPLATE_ID],
        sequence_spans=[
            SequenceSpan(
                start=0,
                end=len(annotated.sequence),
                source=f"retrieved_template:{TEMPLATE_ID}",
                source_id=TEMPLATE_ID,
                source_start=0,
                source_end=len(annotated.sequence),
            )
        ],
    )
    return {
        "design_id": DESIGN_ID,
        "design_spec": {"organism": "Homo sapiens", "vector_type": "e2e_reporter_vector"},
        "clarification_question": None,
        "recommendation_text": "Generated deterministic full-stack E2E reporter plasmid.",
        "annotated_sequence": annotated.model_dump(mode="json"),
        "retrieved_templates": [
            {
                "source_id": "curated:e2e-template",
                "source": "curated",
                "name": "E2E Reporter Template",
                "vector_profile": "e2e_reporter_vector",
                "score": 0.99,
            }
        ],
        "recommendations": [],
        "validation_report": {
            "overall": "PASS",
            "checks": [
                {"name": "Sequence assembly", "status": "PASS", "message": "Deterministic E2E sequence assembled."}
            ],
            "generated_by_model_version": "e2e-deterministic-v1",
        },
    }


def _template_reader(template_ids: Sequence[str]) -> Mapping[str, str]:
    """The record the gate compares the candidate against.

    Returns the fixture's own template only. An id this fixture does not know is
    absent from the result rather than guessed at, so the gate reports UNKNOWN for
    it and refuses, which is the behaviour a real deployment has when a corpus
    lookup comes back empty.
    """
    sequence = _annotated_sequence().sequence
    return {template_id: sequence for template_id in template_ids if template_id == TEMPLATE_ID}


app = create_app(
    session_store=_sessions,
    job_queue=FakeJobQueue(store=InMemoryJobStore(), handler=_handle_design_job),
    design_store=_designs,
    rate_limit_config=RateLimitConfig(enabled=False),
    template_reader=_template_reader,
)
