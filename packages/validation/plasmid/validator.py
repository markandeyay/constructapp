"""The plasmid `CapabilityValidator`: an adapter, not a second opinion.

The plasmid capability pre-dates the shared contract (section 5). Its verdicts
come from `packages.validation.engine.ConstraintEngine`, which has been green
against the curated gold set since Phase 3. This module wraps that engine so it
satisfies the section 5.3 interface and emits a section 5.1 `ValidationReport`
of `CheckResult` objects, which is what the multi-capability gold runner in
`tests/gold/runner.py` needs in order to apply the three section 9.3
assertions to plasmid cases.

**It reshapes output. It does not re-decide biology.** Every verdict in the
report is the engine's own:

* one `CheckResult` per engine `ValidationCheck`, in the engine's order;
* `severity` is a total, lossless mapping of the engine's `status`
  (`SEVERITY_BY_ENGINE_STATUS`), so no check moves up or down;
* `message` is the engine's message verbatim;
* `coordinates` is the engine's `region`, converted to the contract's
  `(start, end)` tuple with no arithmetic;
* `overall` comes from `ValidationReport.from_checks`, the shared helper
  (section 5.4 rule 1). The engine computes its own overall the same way, so
  the two agree, and `tests/validation/test_plasmid_adapter.py` asserts that
  over all 88 curated records.

Where the contract wants something the engine cannot express, the adapter says
so rather than inventing a value (section 3.3 constraint 4):

* `observed`, `threshold` and `tier` stay `None` on every check. The engine
  reports a prose message, not a measured quantity against a named bound, and
  the contract makes those fields optional precisely so an adapter does not
  have to fabricate them. The thresholds that were applied are reported, as
  rule 3 requires, through `parameters_used`.
* `remediation` stays `None`. The engine's messages already carry the
  actionable instruction inline (rule 2); there is no structured fix list to
  surface, and inventing one would be writing new content under the engine's
  name.
* `ValidationCheck.failure_context`, which the engine sets on some
  regulatory failures, has no field in the contract's `CheckResult` and
  `CheckResult` forbids extra fields. It is dropped from the report and read
  instead through `failure_contexts`, so nothing has to be invented and
  nothing is silently lost.
* A check the engine emits under a name this adapter has no mapping for, or at
  a status it has no mapping for, becomes UNKNOWN with the reason. A mapped
  check the engine did not emit at all also becomes UNKNOWN. UNKNOWN never
  improves a verdict (rule 1), so neither case can read as a pass.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from packages.core.schemas import ValidationCheck
from packages.core.schemas import ValidationReport as EngineValidationReport
from packages.core.schemas.capability import (
    CapabilityKind,
    CheckResult,
    DesignResult,
    Severity,
    ValidationReport,
)
from packages.core.schemas.plasmid import PlasmidDesign
from packages.validation.codon import HOST_CODON_WEIGHTS
from packages.validation.common import CHECK_VERSION, host_context
from packages.validation.engine import ConstraintEngine, ConstraintEngineProtocol
from packages.validation.regulatory import (
    AUXILIARY_PROMOTERS,
    BACTERIAL_ORIS,
    BACTERIAL_PROMOTERS,
    MAMMALIAN_PROMOTERS,
    MAMMALIAN_REPLICATION,
    YEAST_ORIS,
    YEAST_PROMOTERS,
)
from packages.validation.repeats import repeat_profile_for
from packages.validation.restriction import restriction_context_from_spec

from .constants import (
    CHECK_CITATIONS,
    CHECK_ID_BY_ENGINE_NAME,
    CHECK_IDS,
    CHECK_LABELS,
    SEVERITY_BY_ENGINE_STATUS,
    VALIDATOR_VERSION,
    mirrored_values,
)

#: The provenance token for a sequence handed straight to the validator
#: (section 5.4 rule 5: `user_input:<field name>`).
SUPPLIED_SEQUENCE_PROVENANCE = "user_input:annotated_sequence"


def _label_for(check_id: str) -> str:
    return CHECK_LABELS.get(check_id, check_id.replace("_", " ").capitalize())


class PlasmidValidator:
    """`CapabilityValidator` over the deterministic plasmid constraint engine."""

    kind = CapabilityKind.PLASMID
    version = VALIDATOR_VERSION

    def __init__(
        self,
        engine: ConstraintEngineProtocol | None = None,
        evaluated_at: datetime | None = None,
    ) -> None:
        self.engine = engine if engine is not None else ConstraintEngine()
        self._evaluated_at = evaluated_at

    # -- section 5.3 -------------------------------------------------------

    def validate(self, design: PlasmidDesign | Any) -> ValidationReport:
        """Run the engine on one design and reshape its report to the contract."""
        design = self._coerce(design)
        engine_report = self.engine.validate(design.annotated_sequence, design.design_spec)
        return self.adapt(engine_report)

    def adapt(self, engine_report: EngineValidationReport) -> ValidationReport:
        """Reshape an engine report. Separated so a test can feed one in directly."""
        checks: list[CheckResult] = []
        seen: set[str] = set()
        for engine_check in engine_report.checks:
            result = self._adapt_check(engine_check)
            if result.check_id in seen:
                # The engine never does this, but a duplicate would silently
                # drop a verdict in the contract report, whose ids are unique.
                continue
            seen.add(result.check_id)
            checks.append(result)
        for check_id in CHECK_IDS:
            if check_id in seen:
                continue
            checks.append(
                CheckResult(
                    check_id=check_id,
                    label=_label_for(check_id),
                    severity=Severity.UNKNOWN,
                    message=(
                        f"The constraint engine did not report {check_id}, so this construct was not "
                        "checked for it. Re-run validation with the full engine check set before "
                        "treating the report as complete."
                    ),
                    citation=CHECK_CITATIONS.get(check_id),
                )
            )
        return ValidationReport.from_checks(
            capability=CapabilityKind.PLASMID,
            checks=checks,
            validator_version=self.version,
            evaluated_at=self._evaluated_at,
        )

    # -- section 5.4 rules 3 and 5 ----------------------------------------

    def parameters_used(self, design: PlasmidDesign | Any) -> dict[str, Any]:
        """Every threshold the engine applied to this design (rule 3).

        Read live from the engine wherever the engine exposes it, so the numbers
        reported here are the numbers the verdict was measured against.
        """
        design = self._coerce(design)
        spec = design.design_spec
        context = host_context(spec)
        restriction = restriction_context_from_spec(spec)
        profile = repeat_profile_for(spec)
        payload: dict[str, Any] = {
            "validator_version": self.version,
            "engine_version": CHECK_VERSION,
            "host_class_resolved": context.host_class,
            "topology": str(design.annotated_sequence.topology),
            "sequence_length_bp": len(design.annotated_sequence.sequence),
            "restriction_site_conflicts": {
                "enzymes_requested": sorted(restriction.enzymes),
                "enzymes_to_avoid": sorted(restriction.avoid_enzymes),
                "recognition_families": {
                    name: sorted(family) for name, family in sorted(restriction.recognition_families.items())
                },
                **mirrored_values("restriction_site_conflicts"),
            },
            "repeat_and_instability": {
                **asdict(profile),
                **mirrored_values("repeat_and_instability"),
            },
            "codon_usage": {
                "codon_table": context.host_class if context.host_class in HOST_CODON_WEIGHTS else None,
                "codon_table_available": context.host_class in HOST_CODON_WEIGHTS,
                **mirrored_values("codon_usage"),
            },
            "regulatory_compatibility": {
                "bacterial_promoter_tokens": sorted(BACTERIAL_PROMOTERS),
                "mammalian_promoter_tokens": sorted(MAMMALIAN_PROMOTERS),
                "yeast_promoter_tokens": sorted(YEAST_PROMOTERS),
                "auxiliary_promoter_tokens": sorted(AUXILIARY_PROMOTERS),
                "bacterial_origin_tokens": sorted(BACTERIAL_ORIS),
                "yeast_origin_tokens": sorted(YEAST_ORIS),
                "mammalian_replication_tokens": sorted(MAMMALIAN_REPLICATION),
            },
        }
        return payload

    def provenance(self, design: PlasmidDesign | Any) -> list[str]:
        """Where the bases came from (rule 5). Never empty.

        A design that declares its own provenance keeps it. Otherwise the
        sequence was supplied to the validator rather than composed from
        registry parts, and that is what is recorded: `user_input:<field name>`,
        plus the declared source of the design spec when there is one.
        """
        design = self._coerce(design)
        if design.provenance:
            return list(design.provenance)
        tokens = [SUPPLIED_SEQUENCE_PROVENANCE]
        source = design.design_spec.source
        if source is not None:
            tokens.append(f"design_spec:source={str(source)}")
        return tokens

    def design_result(self, design: PlasmidDesign | Any, design_id: str | None = None) -> DesignResult:
        """The validated design as a contract `DesignResult`.

        Building it here is what proves the section 5.4 rules hold: the model
        rejects an empty `provenance` (rule 5) and an empty `parameters_used`
        (rule 3), so this method cannot return without both being populated.
        """
        design = self._coerce(design)
        resolved_id = design_id or design.design_id or "plasmid-design"
        return DesignResult(
            capability=CapabilityKind.PLASMID,
            design_id=resolved_id,
            report=self.validate(design),
            artifacts={"sequence": design.annotated_sequence.sequence},
            provenance=self.provenance(design),
            parameters_used=self.parameters_used(design),
        )

    def failure_contexts(self, design: PlasmidDesign | Any) -> dict[str, str]:
        """The engine's `failure_context` per check id, which `CheckResult` cannot hold.

        Kept reachable rather than invented into another field: the contract has
        no place for it, so the adapter does not pretend otherwise.
        """
        design = self._coerce(design)
        report = self.engine.validate(design.annotated_sequence, design.design_spec)
        return {
            CHECK_ID_BY_ENGINE_NAME.get(check.name, check.name): str(check.failure_context)
            for check in report.checks
            if check.failure_context is not None
        }

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _coerce(design: PlasmidDesign | Any) -> PlasmidDesign:
        if isinstance(design, PlasmidDesign):
            return design
        return PlasmidDesign.model_validate(design)

    def _adapt_check(self, check: ValidationCheck) -> CheckResult:
        check_id = CHECK_ID_BY_ENGINE_NAME.get(check.name)
        coordinates = (check.region.start, check.region.end) if check.region is not None else None
        if check_id is None:
            return CheckResult(
                check_id=check.name,
                label=_label_for(check.name),
                severity=Severity.UNKNOWN,
                message=(
                    f"The constraint engine reported a check named {check.name!r} that this adapter has no "
                    "stable check id for, so its verdict cannot be attributed. Add the mapping in "
                    "packages/validation/plasmid/constants.py before relying on this report. "
                    f"Engine message: {check.message}"
                ),
                coordinates=coordinates,
            )
        severity = SEVERITY_BY_ENGINE_STATUS.get(str(check.status))
        if severity is None:
            return CheckResult(
                check_id=check_id,
                label=_label_for(check_id),
                severity=Severity.UNKNOWN,
                message=(
                    f"The constraint engine reported {check_id} at status {str(check.status)!r}, which this "
                    "adapter cannot map to a contract severity, so the verdict is not evaluable. "
                    f"Engine message: {check.message}"
                ),
                coordinates=coordinates,
                citation=CHECK_CITATIONS.get(check_id),
            )
        return CheckResult(
            check_id=check_id,
            label=_label_for(check_id),
            severity=Severity(severity),
            message=check.message,
            coordinates=coordinates,
            citation=CHECK_CITATIONS.get(check_id),
        )


def build_validator() -> PlasmidValidator:
    """Zero-argument factory, which is what `CapabilitySpec.validator_factory` calls."""
    return PlasmidValidator()
