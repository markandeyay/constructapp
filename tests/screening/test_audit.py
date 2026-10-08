"""The section 11.1 item 4 export audit log.

"Every export records what was exported, when, the validator version, and the
screening result." One test per clause, plus the properties that make the log
usable as evidence: it is append only, it is readable back, and an entry whose
screening outcome means nothing was screened says so in a plain boolean.
"""

from __future__ import annotations

import json

from packages.application.screening import (
    AUDIT_LOG_PATH_ENV,
    DECISION_BLOCKED,
    DECISION_EXPORTED,
    NO_BACKEND_ID,
    BackendOutcome,
    InMemoryExportAuditLog,
    JsonlExportAuditLog,
    default_audit_log_path,
    evaluate_export,
    sha256_hex,
)
from packages.core.schemas.capability import CapabilityKind, Severity
from tests.screening.support import (
    FAKE_PARTS,
    FIXED_TIME,
    NoFindingsBackend,
    RaisingBackend,
    attributed_subject,
    fixed_clock,
    subject_with_unattributed_base,
)

PAYLOADS = {"fasta": ">test\nACGT\n", "genbank": "LOCUS test\n//\n"}


def _entry(subject=None, **kwargs):
    log = InMemoryExportAuditLog()
    evaluate_export(
        subject or attributed_subject(),
        export_format="genbank",
        payloads=PAYLOADS,
        parts=FAKE_PARTS,
        audit_log=log,
        now=fixed_clock,
        **kwargs,
    )
    return log.entries()[0]


def test_the_entry_records_what_was_exported() -> None:
    entry = _entry()
    assert entry.capability is CapabilityKind.AAV
    assert entry.design_id == "test-design"
    assert entry.export_format == "genbank"
    assert [artifact.name for artifact in entry.artifacts] == ["fasta", "genbank"]
    assert entry.artifacts[1].sha256 == sha256_hex(PAYLOADS["genbank"])
    assert entry.artifacts[1].bytes_written == len(PAYLOADS["genbank"].encode("utf-8"))
    assert [item.name for item in entry.sequences] == ["cassette"]
    assert entry.sequences[0].length_bp == attributed_subject().sequences[0].length_bp
    assert entry.sequences[0].sha256 == sha256_hex(attributed_subject().sequences[0].sequence)
    assert entry.adapter == "tests.screening.support"


def test_the_entry_records_when() -> None:
    assert _entry().recorded_at == FIXED_TIME


def test_the_entry_records_the_validator_version() -> None:
    entry = _entry(validation_overall=Severity.WARN)
    assert entry.validator_version == "test-validator-1"
    assert entry.validation_overall is Severity.WARN


def test_the_entry_records_the_screening_result() -> None:
    entry = _entry()
    assert entry.screening.backend_id == NO_BACKEND_ID
    assert entry.screening.outcome is BackendOutcome.NO_EXTERNAL_SCREENING_RAN
    assert entry.external_screening_ran is False
    assert "no external screening examined this design" in entry.screening.detail


def test_a_no_findings_entry_names_the_backend_and_its_version() -> None:
    entry = _entry(backend=NoFindingsBackend())
    assert entry.screening.backend_id == "test.no_findings_backend"
    assert entry.screening.backend_version == "2.1"
    assert entry.external_screening_ran is True


def test_a_failed_backend_entry_does_not_read_as_screened() -> None:
    entry = _entry(backend=RaisingBackend())
    assert entry.screening.outcome is BackendOutcome.BACKEND_ERROR_NOT_SCREENED
    assert entry.external_screening_ran is False
    assert entry.decision == DECISION_BLOCKED


def test_the_entry_records_both_assertions_it_gated_on() -> None:
    entry = _entry()
    assert entry.provenance_assertion.verdict.value == "attributed"
    assert entry.composition_assertion.verdict.value == "satisfied"
    assert entry.declared_provenance == attributed_subject().declared_provenance


def test_a_blocked_export_is_recorded_with_its_reasons() -> None:
    entry = _entry(subject_with_unattributed_base())
    assert entry.decision == DECISION_BLOCKED
    assert entry.blocked_reasons
    assert entry.provenance_assertion.verdict.value == "unattributed"
    gap = next(
        finding
        for finding in entry.provenance_assertion.findings
        if finding.kind == "unattributed_span"
    )
    assert gap.bases == "GGGGGGGGGG"


def test_the_json_line_is_one_line_of_sorted_json() -> None:
    entry = _entry()
    line = entry.to_json_line()
    assert "\n" not in line
    payload = json.loads(line)
    assert list(payload) == sorted(payload)
    assert payload["decision"] == DECISION_EXPORTED
    assert payload["external_screening_ran"] is False
    assert payload["screening"]["outcome"] == "no_external_screening_ran"


def test_the_json_line_is_byte_identical_between_runs() -> None:
    assert _entry().to_json_line() == _entry().to_json_line()


def test_the_jsonl_log_appends_and_reads_back(tmp_path) -> None:
    path = tmp_path / "nested" / "export_audit.jsonl"
    log = JsonlExportAuditLog(path)
    evaluate_export(
        attributed_subject(),
        export_format="genbank",
        payloads=PAYLOADS,
        parts=FAKE_PARTS,
        audit_log=log,
        now=fixed_clock,
    )
    evaluate_export(
        subject_with_unattributed_base(),
        export_format="fasta",
        payloads=PAYLOADS,
        parts=FAKE_PARTS,
        audit_log=log,
        now=fixed_clock,
    )
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    entries = log.entries()
    assert [entry.decision for entry in entries] == [DECISION_EXPORTED, DECISION_BLOCKED]
    assert entries[0].recorded_at == FIXED_TIME


def test_a_missing_jsonl_log_reads_back_as_empty(tmp_path) -> None:
    assert JsonlExportAuditLog(tmp_path / "absent.jsonl").entries() == []


def test_the_log_path_is_configurable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(AUDIT_LOG_PATH_ENV, str(tmp_path / "configured.jsonl"))
    assert default_audit_log_path() == tmp_path / "configured.jsonl"
    monkeypatch.delenv(AUDIT_LOG_PATH_ENV)
    assert default_audit_log_path().as_posix().endswith("data/audit/export_audit.jsonl")
