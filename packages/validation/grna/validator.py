"""The guide RNA validator (sections 5.3, 8.5 and 8.6).

Implements the `CapabilityValidator` protocol from `packages.core.schemas.capability`:
`kind`, `version`, and `validate(design) -> ValidationReport`.

Properties this validator holds to:

* Deterministic (section 3.3 constraint 3). It is a pure function of the design
  and the thresholds. No randomness, no model call, no database. The only
  non-deterministic value in the contract is `ValidationReport.evaluated_at`,
  and the constructor accepts a fixed value so a test can pin it.
* `overall` comes from the shared helper `ValidationReport.from_checks`
  (section 5.4 rule 1), never from local logic.
* Every run reports all ten checks, so a verdict never omits a check silently.
  A check that cannot be evaluated is UNKNOWN with the reason.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from packages.core.schemas.capability import (
    CapabilityKind,
    CheckResult,
    ValidationReport,
)
from packages.core.schemas.grna import GuideRNADesign, OffTargetSummary

from .checks import ALL_CHECKS, build_context
from .enumeration import resolve_placement
from .constants import (
    DEFAULT_THRESHOLDS,
    VALIDATOR_VERSION,
    GuideRNAThresholds,
    fingerprint_payload,
)
from .nuclease import geometry_facts, get_nuclease
from .offtarget import search_off_targets


class GuideRNAValidator:
    """Runs the section 8.5 checks and the section 8.6 off-target check on one guide."""

    kind = CapabilityKind.GUIDE_RNA
    version = VALIDATOR_VERSION

    def __init__(
        self,
        thresholds: GuideRNAThresholds = DEFAULT_THRESHOLDS,
        evaluated_at: datetime | None = None,
    ) -> None:
        self.thresholds = thresholds
        self._evaluated_at = evaluated_at

    def validate(
        self,
        design: GuideRNADesign,
        off_target: OffTargetSummary | None = None,
    ) -> ValidationReport:
        """Validate one guide RNA design.

        `off_target` lets a caller that already searched the declared space
        (the generator does, once per request rather than once per guide) pass
        the summary in. When it is omitted the search runs here, so the
        validator is complete on its own and a gold case needs nothing extra.
        """
        if not isinstance(design, GuideRNADesign):
            design = GuideRNADesign.model_validate(design)
        if off_target is not None:
            summary = off_target
        else:
            # The guide's own site must be resolved before the search, or the
            # on-target match in the target sequence would be counted as a
            # perfect off-target and fail the section 8.6 check.
            resolved = resolve_placement(design.request, design.guide)
            summary = search_off_targets(
                design.request,
                design.guide.spacer,
                resolved.placement,
                thresholds=self.thresholds,
            )
        context = build_context(design, summary, self.thresholds)
        checks: list[CheckResult] = [check(context) for check in ALL_CHECKS]
        return ValidationReport.from_checks(
            capability=CapabilityKind.GUIDE_RNA,
            checks=checks,
            validator_version=self.version,
            evaluated_at=self._evaluated_at,
        )

    def parameters_used(self, nuclease: str | None = None) -> dict[str, Any]:
        """Every threshold and every geometry value a verdict was measured against.

        Section 5.4 rule 3. Fed into `DesignResult.parameters_used` by the
        generator and into the API response, so a user can see the numbers.
        """
        payload = fingerprint_payload(self.thresholds)
        payload["validator_version"] = self.version
        if nuclease is not None:
            facts = geometry_facts(get_nuclease(nuclease))
            payload["nuclease_applied"] = {
                "nuclease": facts.nuclease,
                "pam_motif": facts.pam_motif,
                "pam_position": facts.pam_position,
                "spacer_length_nt": facts.spacer_length_nt,
                "alternative_pams": list(facts.alternative_pams),
                "cut_description": facts.cut_description,
                "citation": facts.citation,
            }
        return payload


def build_validator() -> GuideRNAValidator:
    """Zero-argument factory, which is what `CapabilitySpec.validator_factory` calls."""
    return GuideRNAValidator()
