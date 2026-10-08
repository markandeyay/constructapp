"""The AAV validator: section 5.3 interface over the section 6.4 checks.

Pure function of its input. No database, no network, no model call, no
randomness (section 3.3 constraint 3). The same design yields the same report,
byte for byte, apart from `evaluated_at`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from packages.core.part_registry import PartRecord, list_parts
from packages.core.schemas.aav import AAVDesign, coerce_design
from packages.core.schemas.capability import (
    CapabilityKind,
    CheckResult,
    ValidationReport,
)

from .checks import CHECK_IDS, CHECKS, CheckContext
from .constants import AAV_VALIDATOR_VERSION, AAVThresholds, DEFAULT_THRESHOLDS


class AAVValidator:
    """Runs the fourteen section 6.4 checks against one cassette.

    `thresholds` is the configurable threshold set (section 3.3 constraint 2).
    `parts` allows a caller or a test to supply a part registry explicitly;
    the default is the registry in data/parts.
    """

    kind: CapabilityKind = CapabilityKind.AAV
    version: str = AAV_VALIDATOR_VERSION

    def __init__(
        self,
        thresholds: AAVThresholds = DEFAULT_THRESHOLDS,
        parts: list[PartRecord] | None = None,
    ) -> None:
        self.thresholds = thresholds
        self._parts = parts

    # -- thresholds ---------------------------------------------------------

    def thresholds_for(self, design: AAVDesign) -> AAVThresholds:
        """The thresholds actually applied to one design.

        The only per design adjustment is the section 6.3 `packaging_limit_bp`
        override, which replaces the target of the band that matches the
        design's modality and moves the soft and hard limits with it, keeping
        the default band widths. See `AAVThresholds.with_packaging_limit`.
        """
        return self.thresholds.with_packaging_limit(design.packaging_limit_bp, design.self_complementary)

    def parameters_used(self, design: AAVDesign) -> dict[str, Any]:
        """Every threshold the verdict was measured against (section 5.4 rule 3)."""
        applied = self.thresholds_for(design)
        parameters = applied.as_mapping()
        parameters["validator_version"] = self.version
        parameters["serotype"] = design.serotype
        parameters["self_complementary"] = design.self_complementary
        parameters["target_tissue"] = design.target_tissue
        parameters["packaging_limit_bp_override"] = design.packaging_limit_bp
        target, soft, hard = applied.band(design.self_complementary)
        parameters["applied_target_bp"] = target
        parameters["applied_soft_limit_bp"] = soft
        parameters["applied_hard_limit_bp"] = hard
        return parameters

    # -- validation ---------------------------------------------------------

    def run_checks(self, design: AAVDesign) -> list[CheckResult]:
        """The fourteen checks, in section 6.4 order."""
        context = CheckContext.build(design, self.thresholds_for(design), self._parts or list_parts())
        results = [function(context) for _check_id, function in CHECKS]  # type: ignore[operator]
        produced = [item.check_id for item in results]
        if produced != list(CHECK_IDS):
            raise AssertionError(
                "the AAV validator must produce exactly the fourteen section 6.4 check ids in order; "
                f"got {produced}"
            )
        return results

    def validate(self, design: Any, evaluated_at: datetime | None = None) -> ValidationReport:
        """Section 5.3: validate one design and return its report.

        Accepts an `AAVDesign`, an `AAVRequest`, an `AAVValidationInput` or a
        mapping of any of those, so the gold-set runner can hand it a case
        `input` directly. `overall` is computed by the shared
        `ValidationReport.from_checks` helper, never recomputed here
        (section 5.4 rule 1).
        """
        resolved = coerce_design(design)
        return ValidationReport.from_checks(
            capability=CapabilityKind.AAV,
            checks=self.run_checks(resolved),
            validator_version=self.version,
            evaluated_at=evaluated_at,
        )


def build_validator() -> AAVValidator:
    """Zero argument factory, as `CapabilitySpec.validator_ref` requires."""
    return AAVValidator()
