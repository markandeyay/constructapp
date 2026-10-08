"""The pre-export gate: what blocks an export, and what a permitted one records."""

from __future__ import annotations

import pytest

from packages.application.screening import (
    DECISION_BLOCKED,
    DECISION_EXPORTED,
    AssertionVerdict,
    BackendOutcome,
    ExportBlocked,
    InMemoryExportAuditLog,
    NoExternalScreeningBackend,
    ScreeningPolicy,
    evaluate_export,
    screen_and_export,
    screen_design,
)
from packages.core.schemas.capability import (
    CapabilityKind,
    CheckResult,
    DesignResult,
    Severity,
    ValidationReport,
)
from tests.screening.support import (
    FAKE_PARTS,
    FindingBackend,
    NoFindingsBackend,
    RaisingBackend,
    UnreachableBackend,
    attributed_subject,
    fixed_clock,
    subject_with_unattributed_base,
)

PAYLOADS = {"genbank": "LOCUS test\n//\n"}


def _export(subject, **kwargs):
    log = kwargs.pop("audit_log", None)
    if log is None:
        log = InMemoryExportAuditLog()
    return (
        screen_and_export(
            subject,
            export_format="genbank",
            payloads=PAYLOADS,
            parts=FAKE_PARTS,
            audit_log=log,
            now=fixed_clock,
            **kwargs,
        ),
        log,
    )


def test_a_fully_attributed_design_exports() -> None:
    result, log = _export(attributed_subject())
    assert result.payloads == PAYLOADS
    assert result.record.allowed is True
    assert result.record.blocked_reasons == []
    assert log.entries()[0].decision == DECISION_EXPORTED


def test_an_unattributable_base_blocks_the_export() -> None:
    log = InMemoryExportAuditLog()
    with pytest.raises(ExportBlocked) as raised:
        _export(subject_with_unattributed_base(), audit_log=log)
    blocked = raised.value
    assert blocked.record.allowed is False
    assert blocked.record.provenance.verdict is AssertionVerdict.UNATTRIBUTED
    assert "section 11.1 item 1" in " ".join(blocked.record.blocked_reasons)
    assert any(
        "GGGGGGGGGG" in (finding.bases or "")
        for finding in blocked.record.provenance.findings
    )
    # A blocked export is still recorded. Section 11.1 item 4.
    assert len(log.entries()) == 1
    assert log.entries()[0].decision == DECISION_BLOCKED
    assert log.entries()[0].blocked_reasons


def test_a_blocked_export_releases_no_payload() -> None:
    with pytest.raises(ExportBlocked):
        _export(subject_with_unattributed_base())


def test_a_subject_with_no_sequence_blocks() -> None:
    subject = attributed_subject().model_copy(update={"sequences": []})
    with pytest.raises(ExportBlocked) as raised:
        _export(subject)
    assert raised.value.record.provenance.verdict is AssertionVerdict.UNKNOWN


def test_with_no_backend_the_gate_turns_only_on_the_two_assertions() -> None:
    record = screen_design(attributed_subject(), parts=FAKE_PARTS)
    assert record.allowed is True
    assert record.screening.outcome is BackendOutcome.NO_EXTERNAL_SCREENING_RAN
    assert record.screening.external_screening_ran is False
    assert record.provenance.verdict is AssertionVerdict.ATTRIBUTED
    assert record.composition.verdict is AssertionVerdict.SATISFIED


def test_a_configured_backend_that_fails_blocks_by_default() -> None:
    for backend in (RaisingBackend(), UnreachableBackend()):
        with pytest.raises(ExportBlocked) as raised:
            _export(attributed_subject(), backend=backend)
        reasons = " ".join(raised.value.record.blocked_reasons)
        assert "did not screen this design" in reasons
        assert raised.value.record.screening.external_screening_ran is False


def test_a_configured_backend_that_fails_can_be_policed_not_to_block() -> None:
    policy = ScreeningPolicy(block_when_configured_backend_fails=False)
    result, log = _export(attributed_subject(), backend=RaisingBackend(), policy=policy)
    assert result.record.allowed is True
    # The outcome still says it was not screened. The policy changes the gate,
    # never the record.
    assert log.entries()[0].external_screening_ran is False
    assert log.entries()[0].screening.outcome is BackendOutcome.BACKEND_ERROR_NOT_SCREENED


def test_backend_findings_block_by_default() -> None:
    with pytest.raises(ExportBlocked) as raised:
        _export(attributed_subject(), backend=FindingBackend())
    assert "finding(s)" in " ".join(raised.value.record.blocked_reasons)


def test_a_backend_that_ran_and_found_nothing_permits_the_export() -> None:
    result, log = _export(attributed_subject(), backend=NoFindingsBackend())
    assert result.record.allowed is True
    assert log.entries()[0].external_screening_ran is True


def test_no_policy_flag_can_let_an_unattributable_design_through() -> None:
    """Section 11.1 item 1 blocks without qualification, so there is no flag for it."""
    fields = set(ScreeningPolicy.model_fields)
    assert fields == {"block_on_backend_findings", "block_when_configured_backend_fails"}
    policy = ScreeningPolicy(
        block_on_backend_findings=False, block_when_configured_backend_fails=False
    )
    with pytest.raises(ExportBlocked):
        _export(subject_with_unattributed_base(), policy=policy)


def test_the_screening_result_is_recorded_in_the_designs_provenance() -> None:
    subject = attributed_subject()
    record = screen_design(subject, parts=FAKE_PARTS)
    design = DesignResult(
        capability=CapabilityKind.AAV,
        design_id=subject.design_id,
        report=ValidationReport.from_checks(
            CapabilityKind.AAV,
            [
                CheckResult(
                    check_id="aav.required_elements",
                    label="Required elements",
                    severity=Severity.PASS,
                    message="Promoter, coding sequence and polyA are all present.",
                )
            ],
            subject.validator_version,
        ),
        artifacts={"genbank": PAYLOADS["genbank"]},
        provenance=list(subject.declared_provenance),
        parameters_used={"packaging_limit_bp": 4700},
    )
    updated = record.record_in_design(design)
    assert "provenance_assertion:attributed" in updated.provenance
    assert "composition_assertion:satisfied" in updated.provenance
    assert (
        f"screening:{NoExternalScreeningBackend.backend_id}:no_external_screening_ran"
        in updated.provenance
    )
    assert any("no external sequence screening backend" in e for e in updated.provenance)
    # Original list preserved, entries appended, recording twice is idempotent.
    assert updated.provenance[: len(design.provenance)] == design.provenance
    assert record.record_in_design(updated).provenance == updated.provenance


def test_evaluate_export_never_raises_and_always_records() -> None:
    log = InMemoryExportAuditLog()
    record, entry = evaluate_export(
        subject_with_unattributed_base(),
        export_format="fasta",
        payloads=PAYLOADS,
        parts=FAKE_PARTS,
        audit_log=log,
        now=fixed_clock,
    )
    assert record.allowed is False
    assert entry.decision == DECISION_BLOCKED
    assert len(log.entries()) == 1


def test_the_gate_is_deterministic() -> None:
    subject = attributed_subject()
    first = screen_design(subject, parts=FAKE_PARTS)
    second = screen_design(subject, parts=FAKE_PARTS)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
