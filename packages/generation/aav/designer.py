"""End to end AAV design: compose, validate, produce the section 6.8 outputs.

One call takes an `AAVRequest` and returns a `DesignResult` carrying the
validation report, the four artifacts, the full provenance and every threshold
that was applied (sections 5.1 and 6.8).
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.core.part_registry import PartRecord
from packages.core.schemas.aav import AAVDesign, AAVRequest, LengthBudget, RemediationReport
from packages.core.schemas.capability import CapabilityKind, DesignResult, ValidationReport
from packages.validation.aav.constants import AAVThresholds, DEFAULT_THRESHOLDS
from packages.validation.aav.remediation import build_remediation
from packages.validation.aav.validator import AAVValidator

from .composer import AAVComposer, TransgeneResolver, _refuse
from .export import to_fasta, to_genbank
from .layout import length_budget, linear_map_json

# Artifact keys in `DesignResult.artifacts`, which section 5.1 types as
# format to payload. All four are inline payloads rather than paths, so a
# response is self contained.
ARTIFACT_GENBANK = "genbank"
ARTIFACT_FASTA = "fasta"
ARTIFACT_LENGTH_BUDGET = "length_budget"
ARTIFACT_LINEAR_MAP = "linear_map_json"


@dataclass(frozen=True)
class AAVDesignBundle:
    """Everything one design run produced, before it is flattened into a DesignResult."""

    design: AAVDesign
    report: ValidationReport
    budget: LengthBudget
    remediation: RemediationReport
    result: DesignResult


class AAVDesigner:
    """Compose a cassette, validate it, and build its outputs."""

    kind: CapabilityKind = CapabilityKind.AAV

    def __init__(
        self,
        thresholds: AAVThresholds = DEFAULT_THRESHOLDS,
        parts: list[PartRecord] | None = None,
        transgene_resolver: TransgeneResolver = _refuse,
    ) -> None:
        self.thresholds = thresholds
        self.composer = AAVComposer(thresholds, parts, transgene_resolver)
        self.validator = AAVValidator(thresholds, parts)

    def design(self, request: AAVRequest) -> AAVDesignBundle:
        """Section 6.7 composition followed by section 6.4 validation."""
        design = self.composer.compose(request)
        return self.evaluate(design)

    def evaluate(self, design: AAVDesign) -> AAVDesignBundle:
        """Validate an existing cassette and build its outputs.

        Used by the validate-only path, so a cassette that was not composed
        here, for example a gold case or a design a user edited, gets exactly
        the same report and the same artifacts.
        """
        applied = self.validator.thresholds_for(design)
        report = self.validator.validate(design)
        budget = length_budget(design, self.thresholds)
        remediation = build_remediation(
            design,
            applied,
            self.composer.parts(),
            self_complementary=design.self_complementary,
        )
        result = DesignResult(
            capability=CapabilityKind.AAV,
            design_id=design.design_id,
            report=report,
            artifacts={
                ARTIFACT_GENBANK: to_genbank(design),
                ARTIFACT_FASTA: to_fasta(design),
                ARTIFACT_LENGTH_BUDGET: budget.to_text(),
                ARTIFACT_LINEAR_MAP: linear_map_json(design, self.thresholds),
            },
            provenance=design.provenance or _fallback_provenance(design),
            parameters_used=self.validator.parameters_used(design),
        )
        return AAVDesignBundle(
            design=design, report=report, budget=budget, remediation=remediation, result=result
        )


def _fallback_provenance(design: AAVDesign) -> list[str]:
    """Provenance for a design that arrived without any (section 5.4 rule 5).

    Derived from the elements themselves rather than left empty, because rule 5
    requires that no base in the output be unattributable and the contract
    rejects an empty list. An element with neither a part id nor a source is
    recorded as unattributed, which is visible rather than hidden.
    """
    entries = [element.attribution for element in design.elements]
    seen: set[str] = set()
    out: list[str] = []
    for entry in entries:
        if entry not in seen:
            seen.add(entry)
            out.append(entry)
    return out
