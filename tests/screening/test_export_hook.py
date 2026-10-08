"""The export hook in `packages/application/exports.py`, end to end on a real design.

This is the section 11.1 path a capability's export action goes through: the
capability's own codec renders the artifact, the hook screens the design,
writes the audit entry, and releases the payload only if the gate permits.
"""

from __future__ import annotations

import pytest

from packages.application.exports import (
    SUPPORTED_EXPORT_FORMATS,
    export_annotated_sequence,
    export_screened_design,
)
from packages.application.screening import (
    DECISION_BLOCKED,
    DECISION_EXPORTED,
    BackendOutcome,
    ExportBlocked,
    InMemoryExportAuditLog,
    JsonlExportAuditLog,
)
from packages.application.screening.adapters.aav import aav_subject
from packages.core.schemas.aav import AAVRequest, CassetteElementRole
from packages.core.schemas.capability import CapabilityKind
from tests.screening.support import (
    FAKE_PARTS,
    RaisingBackend,
    attributed_subject,
    fixed_clock,
)

SYNTHETIC_CDS = "ATG" + "GCTACGGAT" * 40 + "TAA"


def _designed():
    from packages.generation.aav.designer import AAVDesigner

    request = AAVRequest(
        transgene_name="synthetic_reporter",
        transgene_sequence=SYNTHETIC_CDS,
        target_tissue="liver",
        promoter_preference="promoter.efs",
    )
    return AAVDesigner().design(request)


def test_a_real_aav_design_exports_through_the_hook() -> None:
    bundle = _designed()
    subject = aav_subject(bundle.design, validator_version=bundle.report.validator_version)
    log = InMemoryExportAuditLog()
    payloads = {
        "genbank": bundle.result.artifacts["genbank"],
        "fasta": bundle.result.artifacts["fasta"],
    }
    exported = export_screened_design(
        subject,
        format="genbank",
        payloads=payloads,
        validation_overall=bundle.report.overall,
        audit_log=log,
        now=fixed_clock,
    )
    assert exported.record.allowed is True
    entry = log.entries()[0]
    assert entry.decision == DECISION_EXPORTED
    assert entry.capability is CapabilityKind.AAV
    assert entry.validator_version == bundle.report.validator_version
    assert entry.validation_overall == bundle.report.overall
    assert entry.external_screening_ran is False
    assert entry.screening.outcome is BackendOutcome.NO_EXTERNAL_SCREENING_RAN
    assert entry.sequences[0].length_bp == bundle.design.total_bp


def test_the_hook_releases_the_payload_byte_for_byte() -> None:
    """The bytes released are the bytes audited, including the trailing newline."""
    bundle = _designed()
    subject = aav_subject(bundle.design, validator_version=bundle.report.validator_version)
    from packages.generation.aav.export import to_genbank

    # Taken from the codec rather than from `DesignResult.artifacts`, because
    # that field is a pydantic string and the contract's base model strips
    # whitespace, so the stored copy has already lost its final newline.
    payloads = {"genbank": to_genbank(bundle.design)}
    assert payloads["genbank"].endswith("\n")
    exported = export_screened_design(
        subject, format="genbank", payloads=payloads, now=fixed_clock
    )
    assert exported.payloads["genbank"] == payloads["genbank"]
    assert exported.payloads["genbank"].endswith("\n")


def test_a_cassette_with_an_unattributable_element_is_blocked_by_the_hook() -> None:
    bundle = _designed()
    design = bundle.design
    index = next(
        i for i, element in enumerate(design.elements)
        if element.role is CassetteElementRole.CDS
    )
    elements = list(design.elements)
    elements[index] = elements[index].model_copy(
        update={"source": None, "sequence": elements[index].sequence}
    )
    broken = design.model_copy(update={"elements": elements})
    subject = aav_subject(broken, validator_version=bundle.report.validator_version)
    log = InMemoryExportAuditLog()
    with pytest.raises(ExportBlocked, match="blocked by pre-export screening"):
        export_screened_design(
            subject,
            format="genbank",
            payloads={"genbank": bundle.result.artifacts["genbank"]},
            audit_log=log,
            now=fixed_clock,
        )
    assert log.entries()[0].decision == DECISION_BLOCKED


def test_the_hook_validates_the_export_format() -> None:
    with pytest.raises(ValueError, match="unsupported export format"):
        export_screened_design(
            attributed_subject(),
            format="embl",
            payloads={"embl": "x"},
            parts=FAKE_PARTS,
            now=fixed_clock,
        )


@pytest.mark.parametrize("export_format", sorted(SUPPORTED_EXPORT_FORMATS))
def test_the_hook_accepts_every_supported_format(export_format: str) -> None:
    exported = export_screened_design(
        attributed_subject(),
        format=export_format,
        payloads={export_format: "payload"},
        parts=FAKE_PARTS,
        now=fixed_clock,
    )
    assert exported.export_format == export_format


def test_the_hook_writes_to_a_jsonl_log_on_disk(tmp_path) -> None:
    bundle = _designed()
    subject = aav_subject(bundle.design, validator_version=bundle.report.validator_version)
    log = JsonlExportAuditLog(tmp_path / "export_audit.jsonl")
    export_screened_design(
        subject,
        format="fasta",
        payloads={"fasta": bundle.result.artifacts["fasta"]},
        audit_log=log,
        now=fixed_clock,
    )
    with pytest.raises(ExportBlocked):
        export_screened_design(
            subject,
            format="fasta",
            payloads={"fasta": bundle.result.artifacts["fasta"]},
            backend=RaisingBackend(),
            audit_log=log,
            now=fixed_clock,
        )
    entries = log.entries()
    assert [entry.decision for entry in entries] == [DECISION_EXPORTED, DECISION_BLOCKED]
    assert entries[1].external_screening_ran is False


def test_the_plasmid_codec_is_unchanged_and_does_not_claim_to_be_the_gate() -> None:
    """`export_annotated_sequence` is still the codec. Its docstring says so."""
    assert "not the export gate" in (export_annotated_sequence.__doc__ or "")
    assert "cannot run the section 11.1 provenance assertion" in (
        export_annotated_sequence.__doc__ or ""
    )
