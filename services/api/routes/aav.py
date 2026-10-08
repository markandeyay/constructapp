"""API surface for the AAV vector designer (section 4.1 insertion point four).

Three endpoints, all synchronous and all deterministic, because composition and
validation are pure functions over sequences and need no database:

* `POST /v1/aav/design`   compose a cassette from a request, validate it,
                          return the report, the four artifacts, the length
                          budget and the remediation plan.
* `POST /v1/aav/validate` validate a cassette that already exists, with the
                          same report and the same artifacts.
* `GET  /v1/aav/parts`    the registry parts available to the designer, so the
                          UI can populate the promoter and polyA selectors
                          without duplicating the registry.

A composition problem the user can fix, such as an unknown part id, an
unregistered serotype or a transgene with no sequence, is a 422 with the
message from the composer, which already says what to do. It is never turned
into a silent pass.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from packages.application.screening.adapters.aav import aav_subject
from packages.core.part_registry import PartCategory, list_parts
from packages.core.schemas.aav import AAVDesign, AAVRequest
from packages.generation.aav.designer import AAVDesigner
from packages.validation.aav.remediation import remediation_entries
from services.api.routes._screening import screen_export, sequence_payloads, withhold_artifacts

router = APIRouter(prefix="/v1/aav", tags=["aav"])

# 422 as a literal: the Starlette constant for it was renamed, and depending on
# the installed version either spelling raises a deprecation warning.
UNPROCESSABLE = 422

PREFIX = "/v1/aav"


def _bundle_payload(bundle: Any) -> dict[str, Any]:
    """One response shape for both the design and the validate paths."""
    payload = {
        "design_id": bundle.design.design_id,
        "capability": "aav",
        "topology": "linear",
        "design": bundle.design.model_dump(mode="json"),
        "report": bundle.report.model_dump(mode="json"),
        "result": bundle.result.model_dump(mode="json"),
        "length_budget": bundle.budget.model_dump(mode="json"),
        "length_budget_text": bundle.budget.to_text(),
        "remediation": {
            **bundle.remediation.model_dump(mode="json"),
            "entries": remediation_entries(bundle.remediation),
        },
        "notes": list(bundle.design.notes),
        "export_blocked": False,
        "export_block_reason": None,
    }

    # Section 11.1: screen before any export action. The gate verifies that every
    # base traces to a curated part record, a retrieved template, the user's own
    # input or a named published rule, and writes one audit entry either way. A
    # refusal withholds the artifacts and keeps the report, because section 11.1
    # blocks the export rather than the design.
    payloads, export_format = sequence_payloads(bundle.result.artifacts or {})
    if export_format is None:
        return payload

    subject = aav_subject(
        bundle.design,
        validator_version=bundle.report.validator_version,
        declared_provenance=list(bundle.result.provenance or []),
    )
    allowed, reason = screen_export(
        subject,
        payloads,
        export_format=export_format,
        validation_overall=bundle.report.overall,
    )
    if not allowed:
        return withhold_artifacts(payload, reason or "export blocked by the provenance gate")
    return payload


@router.post("/design", status_code=status.HTTP_200_OK)
def design_cassette(request: AAVRequest) -> dict[str, Any]:
    """Compose a cassette from a natural request and validate it (sections 6.7 and 6.4)."""
    try:
        bundle = AAVDesigner().design(request)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=UNPROCESSABLE, detail=str(exc)) from None
    return _bundle_payload(bundle)


@router.post("/validate", status_code=status.HTTP_200_OK)
def validate_cassette(design: AAVDesign) -> dict[str, Any]:
    """Validate a cassette that already exists, without recomposing it."""
    try:
        bundle = AAVDesigner().evaluate(design)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=UNPROCESSABLE, detail=str(exc)) from None
    return _bundle_payload(bundle)


@router.get("/parts", status_code=status.HTTP_200_OK)
def available_parts() -> dict[str, Any]:
    """The registry parts the designer can use, grouped by category.

    Sequences are deliberately not returned: this endpoint exists to populate
    selectors, and the sequence of every part is already in `data/parts` with
    its provenance.
    """
    grouped: dict[str, list[dict[str, Any]]] = {category.value: [] for category in PartCategory}
    for part in list_parts():
        grouped[PartCategory(part.category).value].append(
            {
                "id": part.id,
                "name": part.name,
                "length_bp": part.length_bp,
                "tissue_specificity": part.tissue_specificity,
                "host_compatibility": list(part.host_compatibility),
                "source": part.source,
                "citation": part.citation,
                "notes": part.notes,
            }
        )
    return {"categories": grouped, "total": sum(len(items) for items in grouped.values())}
