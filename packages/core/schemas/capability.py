"""Shared capability contract implemented by every Construct capability.

Source: section 5 of the engine capability system design (5.1 schemas, 5.2 and
5.3 interfaces, 5.4 binding rules). Field names and types follow section 5.1
literally because the AAV, assembly and guide RNA packages all import them.

Where the section 5.4 rules can be enforced by code instead of prose, they are:

* Rule 1: `ValidationReport.overall` is computed by `worst_severity` and a
  report whose stored `overall` disagrees with its checks is rejected. UNKNOWN
  never improves a verdict, and a report with no evaluable check is itself
  UNKNOWN, never PASS.
* Rule 3: `DesignResult.parameters_used` must not be empty.
* Rule 4: `thresholds_fingerprint` and `assert_version_matches_thresholds` let a
  capability pin each `validator_version` to the exact thresholds it shipped
  with, so a threshold edit without a version bump fails a test.
* Rule 5: `DesignResult.provenance` must not be empty. A sequence supplied by
  the user is recorded as `user_input:<field name>`.

Rule 2 (messages are actionable) cannot be checked mechanically. It stays a
review obligation, and `CheckResult.message` only rejects blank text.

Coordinates use the same convention as `FeatureRegion` in `models.py`:
zero-based, start inclusive, end exclusive.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Any, Iterable, Literal, Mapping, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import SchemaModel, utc_now


class CapabilityModel(SchemaModel):
    """Base for capability contract models.

    `SchemaModel` sets `use_enum_values=True`, which would turn `Severity` and
    `CapabilityKind` fields into plain strings on assignment. The contract
    types the fields as enums (section 5.1), so this base keeps the enum
    members. Both compare equal to their string values, and JSON output is
    unchanged.
    """

    model_config = ConfigDict(use_enum_values=False)


class CapabilityKind(str, Enum):
    PLASMID = "plasmid"  # existing
    AAV = "aav"  # section 6
    ASSEMBLY = "assembly"  # section 7
    GUIDE_RNA = "guide_rna"  # section 8


class Severity(str, Enum):
    PASS = "pass"
    WARN = "warn"  # Tier B: surfaced, explained, not a failure
    FAIL = "fail"
    UNKNOWN = "unknown"  # could not evaluate; never silently a pass


# Ordering used by rule 1. UNKNOWN is deliberately absent: it has no rank
# because it must never move a verdict in either direction.
_SEVERITY_RANK: dict[Severity, int] = {Severity.PASS: 0, Severity.WARN: 1, Severity.FAIL: 2}


class CheckResult(CapabilityModel):
    check_id: str = Field(min_length=1)  # stable, e.g. "aav.packaging_limit"
    label: str = Field(min_length=1)  # human readable, for the UI
    severity: Severity
    message: str = Field(min_length=1)  # actionable: says what to do, not just what is wrong
    coordinates: tuple[int, int] | None = None
    observed: str | None = None  # "4,912 bp"
    threshold: str | None = None  # "4,700 bp"
    citation: str | None = None  # why this threshold exists
    tier: Literal["A", "B"] | None = None
    # Not in section 5.1. Added for the section 6.5 / 6.6 / 9.3 remediation requirement
    # (see PROGRESS.md Spec challenges): structured fix suggestions so the gold harness can
    # assert them without matching prose. The readable substitution text must still appear in
    # `message` (rule 2). Optional and defaulted, so existing constructions are unaffected.
    remediation: list[str] | None = None

    @field_validator("coordinates")
    @classmethod
    def coordinates_ordered(cls, value: tuple[int, int] | None) -> tuple[int, int] | None:
        if value is None:
            return value
        start, end = value
        if start < 0 or end <= start:
            raise ValueError("coordinates must satisfy 0 <= start < end (zero-based, end exclusive)")
        return value


def worst_severity(severities: Iterable[Severity | str]) -> Severity:
    """Compute `ValidationReport.overall` from severities (section 5.4 rule 1).

    The result is the worst of the non-UNKNOWN severities, ranked
    PASS < WARN < FAIL. UNKNOWN entries are ignored, so they can neither
    improve nor worsen the verdict. If nothing evaluable is present (no
    severities, or only UNKNOWN), the result is UNKNOWN rather than PASS,
    because a report with no evidence must not read as a clean one
    (section 3.3 constraint 4).
    """
    evaluated = [Severity(item) for item in severities]
    ranked = [item for item in evaluated if item is not Severity.UNKNOWN]
    if not ranked:
        return Severity.UNKNOWN
    return max(ranked, key=_SEVERITY_RANK.__getitem__)


def overall_from_checks(checks: Iterable[CheckResult]) -> Severity:
    """`worst_severity` applied to a check list. Capabilities call this, never reimplement it."""
    return worst_severity(check.severity for check in checks)


class ValidationReport(CapabilityModel):
    capability: CapabilityKind
    overall: Severity  # worst non-UNKNOWN severity present
    checks: list[CheckResult] = Field(min_length=1)
    evaluated_at: datetime
    validator_version: str = Field(min_length=1)  # bump when any threshold changes

    @model_validator(mode="after")
    def overall_matches_checks(self) -> ValidationReport:
        expected = overall_from_checks(self.checks)
        if self.overall != expected:
            raise ValueError(
                f"overall is {Severity(self.overall).value!r} but the checks give {expected.value!r}; "
                "build the report with ValidationReport.from_checks"
            )
        return self

    @model_validator(mode="after")
    def check_ids_unique(self) -> ValidationReport:
        seen: set[str] = set()
        for check in self.checks:
            if check.check_id in seen:
                raise ValueError(f"duplicate check_id {check.check_id!r} in one report")
            seen.add(check.check_id)
        return self

    @classmethod
    def from_checks(
        cls,
        capability: CapabilityKind,
        checks: list[CheckResult],
        validator_version: str,
        evaluated_at: datetime | None = None,
    ) -> ValidationReport:
        """Build a report with `overall` derived from the checks (rule 1)."""
        return cls(
            capability=capability,
            overall=overall_from_checks(checks),
            checks=checks,
            evaluated_at=evaluated_at or utc_now(),
            validator_version=validator_version,
        )

    @property
    def unknown_checks(self) -> list[CheckResult]:
        """Checks that could not be evaluated. The UI shows these separately (rule 1)."""
        return [check for check in self.checks if check.severity == Severity.UNKNOWN]


class DesignResult(CapabilityModel):
    capability: CapabilityKind
    design_id: str = Field(min_length=1)
    report: ValidationReport
    artifacts: dict[str, str]  # format -> path or inline payload
    provenance: list[str] = Field(min_length=1)  # every part id and template used (rule 5)
    parameters_used: dict[str, Any] = Field(min_length=1)  # every threshold that was applied (rule 3)

    @field_validator("provenance")
    @classmethod
    def provenance_entries_not_blank(cls, value: list[str]) -> list[str]:
        if any(not entry.strip() for entry in value):
            raise ValueError("provenance entries must not be blank")
        return value

    @model_validator(mode="after")
    def report_matches_capability(self) -> DesignResult:
        if self.report.capability != self.capability:
            raise ValueError("report.capability must equal the result capability")
        return self


@runtime_checkable
class CapabilityGenerator(Protocol):
    kind: CapabilityKind

    def compose(self, request: BaseModel) -> BaseModel: ...


@runtime_checkable
class CapabilityValidator(Protocol):
    kind: CapabilityKind
    version: str

    def validate(self, design: BaseModel) -> ValidationReport: ...


def thresholds_fingerprint(thresholds: Mapping[str, Any]) -> str:
    """Stable SHA-256 of a threshold mapping (section 5.4 rule 4).

    Keys are sorted and values are serialised as JSON, so the fingerprint does
    not depend on dict order. Any change to a value, a key, or the set of keys
    changes the fingerprint.
    """
    canonical = json.dumps(thresholds, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def assert_version_matches_thresholds(
    version: str,
    thresholds: Mapping[str, Any],
    pinned: Mapping[str, str],
) -> None:
    """Fail when thresholds changed without a `validator_version` bump (rule 4).

    `pinned` maps each released `validator_version` to the fingerprint of the
    thresholds it shipped with. A capability keeps that mapping next to its
    constants and calls this from a test. Shipping a new version means adding
    a new entry. Editing a threshold under an existing version changes the
    fingerprint and this raises.
    """
    if version not in pinned:
        raise AssertionError(
            f"validator_version {version!r} has no pinned threshold fingerprint; "
            f"add {version!r}: {thresholds_fingerprint(thresholds)!r} to the pin table"
        )
    actual = thresholds_fingerprint(thresholds)
    if pinned[version] != actual:
        raise AssertionError(
            f"thresholds changed under validator_version {version!r}: pinned {pinned[version]}, "
            f"current {actual}. Bump the version and pin the new fingerprint."
        )
