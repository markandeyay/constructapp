from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import BaseModel, ValidationError

from packages.core.schemas.capability import (
    CapabilityGenerator,
    CapabilityKind,
    CapabilityValidator,
    CheckResult,
    DesignResult,
    Severity,
    ValidationReport,
    assert_version_matches_thresholds,
    overall_from_checks,
    thresholds_fingerprint,
    worst_severity,
)


def check(severity: Severity, check_id: str = "x.check") -> CheckResult:
    return CheckResult(check_id=check_id, label="Label", severity=severity, message="Do the thing.")


def checks_of(*severities: Severity) -> list[CheckResult]:
    return [check(severity, f"x.check_{index}") for index, severity in enumerate(severities)]


def report_of(*severities: Severity, capability: CapabilityKind = CapabilityKind.AAV) -> ValidationReport:
    return ValidationReport.from_checks(capability, checks_of(*severities), "1.0.0")


def test_capability_kind_values_match_the_spec() -> None:
    assert {kind.name: kind.value for kind in CapabilityKind} == {
        "PLASMID": "plasmid",
        "AAV": "aav",
        "ASSEMBLY": "assembly",
        "GUIDE_RNA": "guide_rna",
    }


def test_severity_values_match_the_spec() -> None:
    assert {item.name: item.value for item in Severity} == {
        "PASS": "pass",
        "WARN": "warn",
        "FAIL": "fail",
        "UNKNOWN": "unknown",
    }


@pytest.mark.parametrize(
    ("severities", "expected"),
    [
        ([Severity.PASS], Severity.PASS),
        ([Severity.PASS, Severity.WARN], Severity.WARN),
        ([Severity.WARN, Severity.FAIL, Severity.PASS], Severity.FAIL),
        ([Severity.FAIL, Severity.WARN], Severity.FAIL),
    ],
)
def test_overall_is_the_worst_severity(severities: list[Severity], expected: Severity) -> None:
    assert worst_severity(severities) is expected


@pytest.mark.parametrize(
    ("severities", "expected"),
    [
        ([Severity.UNKNOWN, Severity.PASS], Severity.PASS),
        ([Severity.UNKNOWN, Severity.WARN], Severity.WARN),
        ([Severity.UNKNOWN, Severity.FAIL], Severity.FAIL),
        ([Severity.PASS, Severity.UNKNOWN, Severity.WARN, Severity.UNKNOWN], Severity.WARN),
    ],
)
def test_unknown_never_changes_the_verdict(severities: list[Severity], expected: Severity) -> None:
    assert worst_severity(severities) is expected


def test_no_evaluable_check_is_unknown_never_pass() -> None:
    assert worst_severity([]) is Severity.UNKNOWN
    assert worst_severity([Severity.UNKNOWN, Severity.UNKNOWN]) is Severity.UNKNOWN


def test_worst_severity_accepts_string_values() -> None:
    assert worst_severity(["pass", "fail", "unknown"]) is Severity.FAIL


def test_overall_from_checks_matches_worst_severity() -> None:
    assert overall_from_checks(checks_of(Severity.PASS, Severity.WARN)) is Severity.WARN


def test_report_from_checks_derives_overall() -> None:
    report = report_of(Severity.PASS, Severity.UNKNOWN, Severity.WARN)
    assert report.overall is Severity.WARN
    assert [item.check_id for item in report.unknown_checks] == ["x.check_1"]


def test_report_rejects_an_overall_that_disagrees_with_its_checks() -> None:
    with pytest.raises(ValidationError, match="overall"):
        ValidationReport(
            capability=CapabilityKind.AAV,
            overall=Severity.PASS,
            checks=checks_of(Severity.FAIL),
            evaluated_at=datetime.now(timezone.utc),
            validator_version="1.0.0",
        )


def test_report_rejects_a_pass_overall_when_every_check_is_unknown() -> None:
    with pytest.raises(ValidationError, match="overall"):
        ValidationReport(
            capability=CapabilityKind.AAV,
            overall=Severity.PASS,
            checks=checks_of(Severity.UNKNOWN),
            evaluated_at=datetime.now(timezone.utc),
            validator_version="1.0.0",
        )


def test_report_requires_checks_and_a_version() -> None:
    with pytest.raises(ValidationError):
        ValidationReport.from_checks(CapabilityKind.AAV, [], "1.0.0")
    with pytest.raises(ValidationError):
        ValidationReport.from_checks(CapabilityKind.AAV, checks_of(Severity.PASS), "")


def test_report_rejects_duplicate_check_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate check_id"):
        ValidationReport.from_checks(
            CapabilityKind.AAV, [check(Severity.PASS, "dup"), check(Severity.WARN, "dup")], "1.0.0"
        )


def test_report_keeps_enum_members_and_dumps_plain_values() -> None:
    report = report_of(Severity.FAIL)
    assert report.capability is CapabilityKind.AAV
    assert report.overall is Severity.FAIL
    dumped = report.model_dump(mode="json")
    assert dumped["capability"] == "aav"
    assert dumped["overall"] == "fail"
    assert dumped["checks"][0]["severity"] == "fail"


def test_check_result_fields_and_defaults() -> None:
    result = CheckResult(
        check_id="aav.packaging_limit",
        label="Packaging limit",
        severity="warn",
        message="Shorten the cassette.",
        coordinates=(0, 10),
        observed="4,912 bp",
        threshold="4,700 bp",
        citation="why",
        tier="B",
    )
    assert result.severity is Severity.WARN
    assert result.coordinates == (0, 10)
    bare = check(Severity.PASS)
    assert (bare.coordinates, bare.observed, bare.threshold, bare.citation, bare.tier) == (None, None, None, None, None)


def test_check_result_rejects_bad_input() -> None:
    with pytest.raises(ValidationError):
        CheckResult(check_id="", label="L", severity=Severity.PASS, message="m")
    with pytest.raises(ValidationError):
        CheckResult(check_id="a", label="L", severity=Severity.PASS, message="  ")
    with pytest.raises(ValidationError):
        CheckResult(check_id="a", label="L", severity=Severity.PASS, message="m", tier="C")
    with pytest.raises(ValidationError):
        CheckResult(check_id="a", label="L", severity=Severity.PASS, message="m", coordinates=(5, 5))
    with pytest.raises(ValidationError):
        CheckResult(check_id="a", label="L", severity=Severity.PASS, message="m", unexpected="field")


def design_of(report: ValidationReport, **overrides: object) -> DesignResult:
    values: dict[str, object] = {
        "capability": CapabilityKind.AAV,
        "design_id": "design-1",
        "report": report,
        "artifacts": {"fasta": ">x\nACGT"},
        "provenance": ["promoter.cmv", "itr.aav2_itr_left"],
        "parameters_used": {"aav_ss_target_bp": 4700},
    }
    values.update(overrides)
    return DesignResult(**values)


def test_design_result_round_trips() -> None:
    result = design_of(report_of(Severity.PASS))
    restored = DesignResult.model_validate(result.model_dump(mode="json"))
    assert restored == result


def test_design_result_requires_parameters_used() -> None:
    with pytest.raises(ValidationError):
        design_of(report_of(Severity.PASS), parameters_used={})


def test_design_result_requires_provenance() -> None:
    with pytest.raises(ValidationError):
        design_of(report_of(Severity.PASS), provenance=[])
    with pytest.raises(ValidationError, match="blank"):
        design_of(report_of(Severity.PASS), provenance=["promoter.cmv", " "])


def test_design_result_report_must_match_capability() -> None:
    with pytest.raises(ValidationError, match="capability"):
        design_of(report_of(Severity.PASS), capability=CapabilityKind.ASSEMBLY)


class _Generator:
    kind = CapabilityKind.AAV

    def compose(self, request: BaseModel) -> BaseModel:
        return request


class _Validator:
    kind = CapabilityKind.AAV
    version = "1.0.0"

    def validate(self, design: BaseModel) -> ValidationReport:
        return report_of(Severity.PASS)


def test_protocols_recognise_conforming_classes() -> None:
    assert isinstance(_Generator(), CapabilityGenerator)
    assert isinstance(_Validator(), CapabilityValidator)
    assert not isinstance(object(), CapabilityGenerator)
    assert not isinstance(_Generator(), CapabilityValidator)


def test_fingerprint_is_stable_and_order_independent() -> None:
    first = thresholds_fingerprint({"a": 1, "b": 2.5})
    assert first == thresholds_fingerprint({"b": 2.5, "a": 1})
    assert len(first) == 64


def test_fingerprint_changes_when_any_threshold_changes() -> None:
    base = {"limit": 4700, "soft": 4900}
    assert thresholds_fingerprint(base) != thresholds_fingerprint({"limit": 4701, "soft": 4900})
    assert thresholds_fingerprint(base) != thresholds_fingerprint({"limit": 4700})


def test_version_pin_passes_when_thresholds_match() -> None:
    thresholds = {"limit": 4700}
    assert_version_matches_thresholds("1.0.0", thresholds, {"1.0.0": thresholds_fingerprint(thresholds)})


def test_version_pin_fails_when_thresholds_change_without_a_bump() -> None:
    pinned = {"1.0.0": thresholds_fingerprint({"limit": 4700})}
    with pytest.raises(AssertionError, match="Bump the version"):
        assert_version_matches_thresholds("1.0.0", {"limit": 4800}, pinned)


def test_version_pin_fails_for_an_unpinned_version() -> None:
    with pytest.raises(AssertionError, match="no pinned"):
        assert_version_matches_thresholds("1.1.0", {"limit": 4700}, {})


def test_remediation_is_optional_and_carried_through() -> None:
    assert check(Severity.FAIL).remediation is None
    fixed = CheckResult(
        check_id="aav.packaging_limit",
        label="Packaging limit",
        severity=Severity.FAIL,
        message="Replace the CAG promoter with EFS.",
        remediation=["replace promoter.cag with promoter.efs (saves 1,427 bp)"],
    )
    assert CheckResult.model_validate(fixed.model_dump(mode="json")).remediation == fixed.remediation
