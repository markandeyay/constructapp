"""The section 11.1 item 3 screening hook, and what each backend outcome says.

The property every test here defends: nothing that did not examine a design can
produce a result that reads as though something did. Section 3.3 constraint 4
and the section 16 row that governs what may be claimed about section 11.
"""

from __future__ import annotations

from packages.application.screening import (
    NO_BACKEND_ID,
    NOT_SCREENED_OUTCOMES,
    BackendFinding,
    BackendOutcome,
    NoExternalScreeningBackend,
    ScreeningBackend,
    ScreeningResult,
    run_screening_backend,
)
from tests.screening.support import (
    FindingBackend,
    NoFindingsBackend,
    RaisingBackend,
    UnreachableBackend,
    attributed_subject,
)


def test_the_default_backend_records_that_no_external_screening_ran() -> None:
    subject = attributed_subject()
    result = run_screening_backend(NoExternalScreeningBackend(), subject)
    assert result.outcome is BackendOutcome.NO_EXTERNAL_SCREENING_RAN
    assert result.external_screening_ran is False
    assert result.backend_id == NO_BACKEND_ID
    assert result.findings == []
    assert result.sequences_submitted == 0
    assert result.bases_submitted == 0
    assert "no external screening examined this design" in result.detail
    assert "must not be read as a screening result" in result.detail


def test_the_default_backends_provenance_entries_say_nothing_was_screened() -> None:
    result = NoExternalScreeningBackend().screen(attributed_subject())
    entries = result.provenance_entries
    assert entries[0] == f"screening:{NO_BACKEND_ID}:no_external_screening_ran"
    assert any("no external sequence screening backend examined this design" in e for e in entries)


def test_the_default_backend_is_deterministic() -> None:
    subject = attributed_subject()
    backend = NoExternalScreeningBackend()
    first = backend.screen(subject)
    second = backend.screen(subject)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_a_backend_that_raises_does_not_report_no_findings() -> None:
    result = run_screening_backend(RaisingBackend(), attributed_subject())
    assert result.outcome is BackendOutcome.BACKEND_ERROR_NOT_SCREENED
    assert result.outcome in NOT_SCREENED_OUTCOMES
    assert result.external_screening_ran is False
    assert result.findings == []
    assert "RuntimeError" in result.detail
    assert "is not a no-findings result" in result.detail


def test_an_unreachable_backend_does_not_report_no_findings() -> None:
    result = run_screening_backend(UnreachableBackend(), attributed_subject())
    assert result.outcome is BackendOutcome.BACKEND_UNREACHABLE_NOT_SCREENED
    assert result.outcome in NOT_SCREENED_OUTCOMES
    assert result.external_screening_ran is False
    assert result.findings == []
    assert "could not be reached" in result.detail
    assert "connection timed out" in result.detail


def test_a_failing_backend_still_records_what_was_submitted() -> None:
    subject = attributed_subject()
    for backend in (RaisingBackend(), UnreachableBackend()):
        result = run_screening_backend(backend, subject)
        assert result.sequences_submitted == len(subject.sequences)
        assert result.bases_submitted == subject.total_bp
        assert result.backend_id == backend.backend_id


def test_a_backend_that_ran_and_found_nothing_is_recorded_as_its_own_statement() -> None:
    result = run_screening_backend(NoFindingsBackend(), attributed_subject())
    assert result.outcome is BackendOutcome.BACKEND_REPORTED_NO_FINDINGS
    assert result.external_screening_ran is True
    assert result.provenance_entries == [
        "screening:test.no_findings_backend:backend_reported_no_findings"
    ]


def test_a_backend_that_found_something_carries_the_findings_through() -> None:
    result = run_screening_backend(FindingBackend(), attributed_subject())
    assert result.outcome is BackendOutcome.BACKEND_REPORTED_FINDINGS
    assert [finding.code for finding in result.findings] == ["TEST_FINDING"]


def test_a_backend_that_contradicts_itself_is_recorded_as_an_error() -> None:
    """No findings plus findings is not a no-findings result."""

    class ContradictoryBackend:
        backend_id = "test.contradictory"
        backend_version = "1"

        def screen(self, subject) -> ScreeningResult:
            return ScreeningResult(
                backend_id=self.backend_id,
                backend_version=self.backend_version,
                outcome=BackendOutcome.BACKEND_REPORTED_NO_FINDINGS,
                findings=[
                    BackendFinding(sequence_name="cassette", code="X", detail="something")
                ],
                detail="no findings",
                sequences_submitted=1,
                bases_submitted=10,
            )

    result = run_screening_backend(ContradictoryBackend(), attributed_subject())
    assert result.outcome is BackendOutcome.BACKEND_ERROR_NOT_SCREENED
    assert result.external_screening_ran is False
    assert len(result.findings) == 1


def test_only_the_placeholder_may_report_that_no_external_screening_ran() -> None:
    class ImpostorBackend:
        backend_id = "test.impostor"
        backend_version = "1"

        def screen(self, subject) -> ScreeningResult:
            return ScreeningResult(
                backend_id=self.backend_id,
                backend_version=self.backend_version,
                outcome=BackendOutcome.NO_EXTERNAL_SCREENING_RAN,
                findings=[],
                detail="nothing ran",
                sequences_submitted=0,
                bases_submitted=0,
            )

    result = run_screening_backend(ImpostorBackend(), attributed_subject())
    assert result.outcome is BackendOutcome.BACKEND_ERROR_NOT_SCREENED


def test_a_backend_returning_the_wrong_type_is_recorded_as_an_error() -> None:
    class BrokenBackend:
        backend_id = "test.broken"
        backend_version = "1"

        def screen(self, subject):  # type: ignore[no-untyped-def]
            return {"outcome": "fine"}

    result = run_screening_backend(BrokenBackend(), attributed_subject())
    assert result.outcome is BackendOutcome.BACKEND_ERROR_NOT_SCREENED
    assert "not a ScreeningResult" in result.detail


def test_the_default_backend_satisfies_the_documented_interface() -> None:
    assert isinstance(NoExternalScreeningBackend(), ScreeningBackend)
    assert isinstance(NoFindingsBackend(), ScreeningBackend)


def test_every_not_screened_outcome_reports_that_nothing_was_screened() -> None:
    for outcome in NOT_SCREENED_OUTCOMES:
        result = ScreeningResult(
            backend_id="test",
            backend_version="1",
            outcome=outcome,
            detail="x",
            sequences_submitted=0,
            bases_submitted=0,
        )
        assert result.external_screening_ran is False
        assert any("no external sequence screening backend" in e for e in result.provenance_entries)
