"""The assembly capability validator (section 5.3, implementing section 7.5).

Source: sections 5.3, 5.4 and 7.5 of the engine capability system design.

The validator is a pure function of the design. It touches no database, makes
no network call and calls no model (section 3.3 constraint 3), so the same
design produces the same report every time and the report can be computed from
a request in a test with nothing else running.
"""

from __future__ import annotations

from typing import Any

from packages.core.schemas.assembly import AssemblyDesign, AssemblyRequest
from packages.core.schemas.capability import CapabilityKind, ValidationReport
from packages.core.sequence.tm import DIVALENT_TO_MONOVALENT_COEFFICIENT, sodium_equivalent_mm

from . import structure
from .checks import APPLICABLE_CHECKS, run_all
from .constants import VALIDATOR_VERSION
from .settings import Settings, settings_for


def ensure_composed(design: AssemblyDesign) -> AssemblyDesign:
    """Fill in primers, junctions and amplicons when a design arrives without them.

    A gold case, or an API caller, may supply fragments and a strategy and
    nothing else. Composing the design before validating it is deterministic
    and uses the same designer the generator uses, so the verdict is the verdict
    on the design the generator would have produced. A design that already
    carries primers is left exactly as supplied, which is what lets a gold case
    pin an exact primer pair to target a specific check.
    """
    if design.primers:
        return design
    # Imported here rather than at module scope: the designer imports this
    # package for its thresholds, and a top-level import would be circular.
    from packages.generation.assembly.designer import compose, host_codon_usage_from_request

    composed = compose(design.request, host_codon_usage=host_codon_usage_from_request(design.request))
    return composed.model_copy(
        update={"provenance": composed.provenance + ["composed_by:validator (no primers supplied)"]}
    )


def parameters_used(
    request: AssemblyRequest,
    settings: Settings,
    report: ValidationReport | None = None,
) -> dict[str, Any]:
    """Everything the verdict was measured against (section 5.4 rule 3).

    This is deliberately more than the threshold table: the reaction conditions
    that feed the Tm calculation change every Tm in the report, so a reader who
    cannot see them cannot reproduce a single number in it.

    `applicable_checks` is the section 7.5 checks the requested strategy runs.
    When `report` is given, `checks_evaluated` is the subset that actually had
    something to examine, and `checks_not_evaluated` is the difference with the
    reason it is empty: a Gibson junction check on a single-fragment assembly
    has no junction to inspect. Neither list ever reports an unexamined check as
    a pass (section 3.3 constraint 4).
    """
    equivalent, divalent_applied = sodium_equivalent_mm(
        request.monovalent_salt_mm, request.divalent_salt_mm, request.dntp_mm
    )
    hairpin_version = structure.viennarna_version()
    parameters: dict[str, Any] = {
        "validator_version": VALIDATOR_VERSION,
        "strategy": request.strategy,
        "applicable_checks": list(APPLICABLE_CHECKS[request.strategy]),
        "target_tm_c": request.target_tm_c,
        "primer_conc_nm": request.primer_conc_nm,
        "monovalent_salt_mm": request.monovalent_salt_mm,
        "divalent_salt_mm": request.divalent_salt_mm,
        "dntp_mm": request.dntp_mm,
        "sodium_equivalent_mm": equivalent,
        "divalent_conversion": (
            "von Ahsen et al. 2001, Clin Chem 47:1956-1961: "
            "[Na_eq] = [Na+] + 120 * sqrt([Mg2+] - [dNTP])"
            if divalent_applied
            else (
                "not applied: dNTP concentration is at or above the magnesium concentration, so no "
                "free magnesium contributes"
            )
        ),
        "divalent_to_monovalent_coefficient": DIVALENT_TO_MONOVALENT_COEFFICIENT,
        "tm_model": (
            "nearest-neighbor thermodynamics, SantaLucia 1998 unified parameters (Appendix A), with "
            "the Appendix A monovalent entropy salt correction"
        ),
        "tm_measured_on": "primer template-binding region, excluding any 5' tail",
        "hairpin_engine_requested": request.hairpin_engine,
        "hairpin_engine_available": (
            f"ViennaRNA {hairpin_version} with DNA parameters (dna_mathews2004)"
            if hairpin_version
            else "none; the documented sliding-window stem score is used"
        ),
        "dimer_score_definition": (
            "gapless sliding-window complementarity in base pairs; 'any' is the best gapless local "
            "score at any offset, '3 prime' is the longest contiguous complementary run anchored at "
            "a 3' terminal base. Thresholds are the Primer3 defaults in the same units."
        ),
        "host_codon_usage": (
            f"{request.host_codon_usage.host} ({request.host_codon_usage.citation})"
            if request.host_codon_usage
            else "none bundled with this build; host codon frequencies are reported as UNKNOWN"
        ),
        "overhang_standard": (
            f"{request.overhang_standard.name} ({request.overhang_standard.citation})"
            if request.overhang_standard
            else "none supplied; Golden Gate overhangs are taken from the fragment junctions"
        ),
    }
    if report is not None:
        evaluated = [check.check_id for check in report.checks]
        parameters["checks_evaluated"] = evaluated
        parameters["checks_not_evaluated"] = [
            check_id for check_id in APPLICABLE_CHECKS[request.strategy] if check_id not in evaluated
        ]
        parameters["checks_not_evaluated_reason"] = (
            "A check applicable to the strategy but with nothing to examine in this design, for "
            "example a junction check on a single-fragment assembly. Omitted rather than reported "
            "as a pass."
        )
    parameters.update(settings.as_parameters())
    parameters["thresholds_overridden"] = settings.overridden()
    return parameters


class AssemblyValidator:
    """`CapabilityValidator` for the assembly capability (section 5.3)."""

    kind = CapabilityKind.ASSEMBLY
    version = VALIDATOR_VERSION

    def validate(self, design: AssemblyDesign) -> ValidationReport:  # type: ignore[override]
        """Run every applicable section 7.5 check and build the report.

        `overall` is computed by the shared contract helper, never by this
        module, so section 5.4 rule 1 is enforced in one place.
        """
        prepared = ensure_composed(design)
        settings = settings_for(prepared.request)
        checks = run_all(prepared, settings)
        return ValidationReport.from_checks(
            capability=CapabilityKind.ASSEMBLY,
            checks=checks,
            validator_version=self.version,
        )


def build_validator() -> AssemblyValidator:
    """Zero-argument factory, which is what `CapabilitySpec.validator_ref` names."""
    return AssemblyValidator()
