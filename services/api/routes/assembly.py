"""API surface for the primer and assembly capability (section 4.1).

Source: sections 4.1, 7.2 and 7.7 of the engine capability system design.

The endpoints are pure functions of the request body. They touch no database,
which is what lets the capability be exercised without the stack running, and
they call no model, so the same body always produces the same response
(section 3.3 constraint 3). An invalid request is rejected with a 422 carrying
the reason, and an unsupported enzyme or a template too short to design against
is rejected with a 400 naming what to do instead: section 3.3 constraint 4
forbids returning a design that was not actually designed.
"""

from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, HTTPException, status

from packages.application.screening.adapters.assembly import assembly_subject
from packages.core.schemas.assembly import (
    AssemblyDesign,
    AssemblyRequest,
    AssemblyResponse,
)
from packages.core.schemas.capability import CapabilityKind, ValidationReport
from packages.generation.assembly.designer import compose, host_codon_usage_from_request
from packages.generation.assembly.outputs import build_outputs, order_table_text
from packages.validation.assembly.checks import ALL_CHECK_IDS, APPLICABLE_CHECKS
from packages.validation.assembly.constants import CITATIONS, VALIDATOR_VERSION
from packages.validation.assembly.settings import settings_for
from packages.validation.assembly.validator import AssemblyValidator, parameters_used
from services.api.routes._screening import screen_export

router = APIRouter(prefix="/v1/assembly", tags=["assembly"])


def _design_id(request: AssemblyRequest) -> str:
    """A stable identifier for a request: the same request gets the same id.

    A hash of the canonical request rather than a random or time-based value, so
    the endpoint stays deterministic (section 3.3 constraint 3) and two calls
    with the same body are recognisably the same design.
    """
    canonical = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return "assembly-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def design_assembly(request: AssemblyRequest) -> AssemblyResponse:
    """Compose, validate and build the section 7.7 outputs for one request."""
    try:
        design = compose(request, host_codon_usage=host_codon_usage_from_request(request))
    except KeyError as exc:  # unsupported enzyme, named in the message
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc).strip("'\"")) from exc
    except ValueError as exc:  # template too short, overhang standard too small
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    report = AssemblyValidator().validate(design)
    outputs = build_outputs(design, report)
    settings = settings_for(request)
    response = AssemblyResponse(
        design_id=_design_id(request),
        design=design,
        outputs=outputs,
        provenance=design.provenance,
        parameters_used=parameters_used(request, settings, report),
    )

    # Section 11.1: screen before any export action. The order table is the
    # orderable DNA this capability produces, so it is what the gate guards. Each
    # primer is attributed from its template span plus, for Golden Gate, the
    # named overhang rule that produced its tail; a primer whose tail cannot be
    # traced to that rule leaves a span uncovered and blocks.
    subject = assembly_subject(
        design,
        validator_version=report.validator_version,
        declared_provenance=list(design.provenance or []),
    )
    allowed, reason = screen_export(
        subject,
        {"order_table.csv": outputs.order_table_csv},
        export_format="csv",
        validation_overall=report.overall,
    )
    if not allowed:
        # Withhold the table in both renderings. The design, the protocol, the
        # junction map and the report all survive: section 11.1 blocks the
        # export, and the researcher needs the report to act on the reason.
        response.outputs.order_table = []
        response.outputs.order_table_csv = ""
        response.export_blocked = True
        response.export_block_reason = reason or "export blocked by the provenance gate"
    return response


@router.post("/design", response_model=AssemblyResponse)
def post_design(request: AssemblyRequest) -> AssemblyResponse:
    """Design primers and a protocol for one assembly (sections 7.1 to 7.7)."""
    return design_assembly(request)


@router.post("/validate", response_model=ValidationReport)
def post_validate(design: AssemblyDesign) -> ValidationReport:
    """Validate a design against the nineteen section 7.5 checks.

    A design with no primers is composed first by the deterministic designer, so
    a caller can validate a fragment set without designing primers by hand.
    """
    try:
        return AssemblyValidator().validate(design)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc).strip("'\"")) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/order-table.csv")
def post_order_table_csv(request: AssemblyRequest) -> dict[str, str]:
    """The order table as CSV and as aligned text, which section 7.7 requires.

    Returned as JSON fields rather than as a file download so the web surface
    can show the text in a copy box and offer the CSV for download from the same
    call. Section 7.7: "it must be copy-pasteable and CSV-exportable."
    """
    response = design_assembly(request)
    if response.export_blocked:
        # This endpoint exists only to hand over the table, so there is nothing
        # to return but the refusal. A 409 rather than a 200 with an empty body:
        # a caller downloading a file needs the refusal to be unmistakable, and
        # unlike the design endpoint there is no report here to read instead.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "export_blocked",
                "message": response.export_block_reason
                or "export blocked by the provenance gate",
                "retryable": False,
            },
        )
    return {
        "filename": f"{response.design_id}-order-table.csv",
        "csv": response.outputs.order_table_csv,
        "text": order_table_text(response.outputs.order_table),
    }


@router.get("/checks")
def get_checks() -> dict[str, object]:
    """The section 7.5 check catalogue, so the UI can explain a report.

    Lists every check_id in section 7.5 table order with its citation, and which
    checks each strategy runs. A check that a strategy does not run is omitted
    from that strategy's report rather than reported as a pass, so the UI needs
    this list to say what was not examined.
    """
    return {
        "validator_version": VALIDATOR_VERSION,
        "capability": CapabilityKind.ASSEMBLY.value,
        "checks": [{"check_id": check_id, "citation": CITATIONS[check_id]} for check_id in ALL_CHECK_IDS],
        "applicable_by_strategy": {
            strategy: list(check_ids) for strategy, check_ids in APPLICABLE_CHECKS.items()
        },
    }
