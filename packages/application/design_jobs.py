from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from packages.application.designs import DesignStore
from packages.generation.spike import GenerationSpikePipeline, spike_result_as_dict


CLARIFICATION_ERROR_PREFIX = "intent clarification required:"


class DesignPipeline(Protocol):
    def run(self, free_text: str) -> Any: ...


@dataclass(frozen=True)
class GenerationDesignJobHandler:
    """Run the retrieval-grounded generation pipeline behind the worker queue."""

    pipeline: DesignPipeline
    design_store: DesignStore

    def __call__(self, *, job_id: str, session_id: str, action: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if action not in {"design", "refine"}:
            raise ValueError(f"unsupported design job action: {action}")
        context = payload.get("context")
        if isinstance(context, list) and context:
            free_text = "\n".join(str(item) for item in context)
        else:
            free_text = str(payload.get("text") or payload.get(action) or "").strip()
        if not free_text:
            raise ValueError("design job requires non-empty text")
        try:
            result = self.pipeline.run(free_text)
        except ValueError as exc:
            clarification = _clarification_from_error(exc)
            if clarification is None:
                raise
            return {
                "design_id": None,
                "design_spec": {
                    "clarification_needed": True,
                    "clarification_question": clarification,
                },
                "clarification_question": clarification,
                "annotated_sequence": None,
                "validation_report": None,
                "retrieved_templates": [],
                "recommendations": [],
                "recommendation_text": None,
                # Kept in the clarification shape too so both branches return the
                # same keys: a caller reading the result should not have to know
                # which branch produced it to know which keys exist.
                "template_ids": [],
                "sequence_spans": [],
            }
        serialized = spike_result_as_dict(result)
        # Taken from the typed candidate rather than from `serialized`, because the
        # spans have to reach the store as SequenceSpan objects: round-tripping
        # them through the dict would hand the store unvalidated JSON.
        # DesignPipeline only promises `run() -> Any`, so a pipeline that exposes
        # no candidate records no attribution rather than a guessed one.
        generated = getattr(result, "generated", None)
        template_ids = list(generated.parent_template_ids) if generated is not None else []
        sequence_spans = list(generated.sequence_spans) if generated is not None else []
        design = self.design_store.create(
            session_id=session_id,
            job_id=job_id,
            annotated_sequence=result.reannotated_sequence,
            template_ids=template_ids,
            sequence_spans=sequence_spans,
        )
        return {
            "design_id": design.design_id,
            "design_spec": serialized["design_spec"],
            "clarification_question": None,
            "annotated_sequence": serialized["annotated_sequence"],
            "validation_report": serialized["validation_report"],
            "retrieved_templates": serialized["retrieved_templates"],
            "recommendations": serialized["recommendations"],
            "recommendation_text": _recommendation_text(serialized["recommendations"]),
            # The job result is the only form of this design most callers ever
            # see, so the attribution travels with it instead of being readable
            # only out of the design store.
            "template_ids": template_ids,
            "sequence_spans": [span.model_dump(mode="json") for span in sequence_spans],
        }


def build_generation_design_job_handler(pipeline: GenerationSpikePipeline, design_store: DesignStore) -> GenerationDesignJobHandler:
    return GenerationDesignJobHandler(pipeline=pipeline, design_store=design_store)


def _clarification_from_error(exc: ValueError) -> str | None:
    message = str(exc).strip()
    if not message.lower().startswith(CLARIFICATION_ERROR_PREFIX):
        return None
    clarification = message[len(CLARIFICATION_ERROR_PREFIX) :].strip()
    return clarification or "Could you clarify the design goal?"


def _recommendation_text(recommendations: list[dict[str, Any]]) -> str | None:
    if not recommendations:
        return None
    first = recommendations[0].get("why_relevant")
    return str(first) if isinstance(first, str) and first.strip() else None
