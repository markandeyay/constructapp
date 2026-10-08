"""Capability registry so the UI and the API can enumerate capabilities.

Source: section 13.3 of the engine capability system design. WP-02 creates the
file with three reserved, delimited regions inside `CAPABILITY_REGISTRY`. Each
capability package writes only inside its own region:

* WP-03 (AAV) writes between its two WP-03 delimiter lines.
* WP-04 (assembly) writes between its two WP-04 delimiter lines.
* WP-05 (guide RNA) writes between its two WP-05 delimiter lines.

A merge conflict inside a delimited region means a package wrote outside its
own, which is a spec violation to be reported rather than resolved by hand.

Entries refer to code by dotted path (`package.module:attribute`) instead of by
import, so registering a capability never imports its generator, validator or
schemas. That keeps the registry importable on its own and rules out import
cycles. Use `resolve_reference` to load a referenced object when it is needed.
Spec fields that name code are dotted paths. `validator_factory()` and `design_model` are what
the gold-set runner (tests/gold/runner.py) calls. A region entry is a single inline `CapabilityKind.X: CapabilitySpec(...)`
expression, so a package needs no import line outside its region.
"""

from __future__ import annotations

import importlib
from typing import Any

from pydantic import Field

from .schemas.capability import CapabilityKind, CapabilityModel


class CapabilitySpec(CapabilityModel):
    """Static description of one capability, enough to list it and to find its code."""

    kind: CapabilityKind
    label: str = Field(min_length=1)  # shown in the capability selector (section 10.1)
    description: str = Field(min_length=1)
    request_schema: str | None = None  # dotted path of the request model
    result_schema: str | None = None  # dotted path of the result model
    generator: str | None = None  # dotted path of the generator
    validator_ref: str | None = None  # dotted path of a zero-argument callable returning a CapabilityValidator
    design_model_ref: str | None = None  # dotted path of the pydantic model a design is parsed into
    api_route: str | None = None  # route prefix the capability is served under
    notes: str | None = None

    def validator_factory(self) -> Any:
        """Build the capability validator, or raise LookupError if none is registered.

        The gold-set runner calls this. It stays lazy so registering a capability
        never imports its code.
        """
        if self.validator_ref is None:
            raise LookupError(f"capability {CapabilityKind(self.kind).value!r} registers no validator")
        return resolve_reference(self.validator_ref)()

    @property
    def design_model(self) -> Any:
        """The pydantic model a gold case input is parsed into, or None if not registered."""
        return resolve_reference(self.design_model_ref) if self.design_model_ref else None


PLASMID_SPEC = CapabilitySpec(
    kind=CapabilityKind.PLASMID,
    label="Plasmid",
    description=(
        "Natural language plasmid design: retrieve grounded templates, compose a candidate, "
        "validate it with the deterministic constraint engine."
    ),
    request_schema="packages.core.schemas.models:DesignSpec",
    result_schema="packages.core.schemas.models:GeneratedSequence",
    generator="packages.generation.generator:SequenceGenerator",
    validator_ref="packages.validation.plasmid.validator:build_validator",
    design_model_ref="packages.core.schemas.plasmid:PlasmidDesign",
    api_route="/v1/sessions",
    notes=(
        "Pre-dates the shared contract. Its generator still uses the original interface, not "
        "CapabilityGenerator. Its verdicts still come from packages.validation.engine.ConstraintEngine, "
        "which decides every plasmid check; validator_ref points at the adapter in "
        "packages.validation.plasmid, which only reshapes that engine's report into the section 5.1 "
        "ValidationReport of CheckResult objects. design_model is PlasmidDesign, which carries the two "
        "inputs the engine already takes, so a gold case input is a curated record's design_spec and "
        "annotated_sequence unchanged and the plasmid gold set runs through the same runner, and the "
        "same section 9.3 assertions, as the other three capabilities."
    ),
)


CAPABILITY_REGISTRY: dict[CapabilityKind, CapabilitySpec] = {
    CapabilityKind.PLASMID: PLASMID_SPEC,
    # ==== WP-03: AAV. Only WP-03 writes here. ====
    CapabilityKind.AAV: CapabilitySpec(
        kind=CapabilityKind.AAV,
        label="AAV vector",
        description=(
            "Compose a recombinant AAV cassette from curated ITR, promoter, polyA and enhancer parts, "
            "check it against the banded packaging limit and the fourteen structural checks of section "
            "6.4, and when it does not fit, compute the specific element substitution that makes it fit."
        ),
        request_schema="packages.core.schemas.aav:AAVRequest",
        result_schema="packages.core.schemas.capability:DesignResult",
        generator="packages.generation.aav.composer:AAVComposer",
        validator_ref="packages.validation.aav.validator:build_validator",
        design_model_ref="packages.core.schemas.aav:AAVValidationInput",
        api_route="/v1/aav",
        notes=(
            "design_model is AAVValidationInput, which accepts either a fully specified AAVDesign "
            "cassette or an AAVRequest that is composed first, so a gold case can use whichever is "
            "natural: a case about element order has to spell out the cassette, a case about the "
            "packaging limit reads better as a request. Remediation is reported in "
            "CheckResult.remediation on aav.packaging_limit and aav.sc_capacity, so a gold case asserts "
            "it with must_also_report: [\"remediation\"]."
        ),
    ),
    # ==== /WP-03 ====
    # ==== WP-04: assembly. Only WP-04 writes here. ====
    CapabilityKind.ASSEMBLY: CapabilitySpec(
        kind=CapabilityKind.ASSEMBLY,
        label="Assembly and primers",
        description=(
            "Primer and assembly design for Gibson, Golden Gate and simple PCR cloning: "
            "nearest-neighbor melting temperatures with salt correction, secondary structure and "
            "dimer checks, Golden Gate domestication, and an order table plus a bench protocol."
        ),
        request_schema="packages.core.schemas.assembly:AssemblyRequest",
        result_schema="packages.core.schemas.assembly:AssemblyResponse",
        generator="packages.generation.assembly.designer:AssemblyGenerator",
        validator_ref="packages.validation.assembly.validator:build_validator",
        design_model_ref="packages.core.schemas.assembly:AssemblyDesign",
        api_route="/v1/assembly",
        notes=(
            "Section 7. A gold case input is an AssemblyDesign. Supplying only `request` lets the "
            "deterministic designer compose the primers before validation, which is what a "
            "fragment-level case wants; pinning `primers` targets a primer-level check directly."
        ),
    ),
    # ==== /WP-04 ====
    # ==== WP-05: guide RNA. Only WP-05 writes here. ====
    CapabilityKind.GUIDE_RNA: CapabilitySpec(
        kind=CapabilityKind.GUIDE_RNA,
        label="Guide RNA",
        description=(
            "CRISPR guide RNA design: enumerate every valid guide on both strands at the correct "
            "PAM offset, predict on-target activity with a named published model, search the "
            "declared off-target space, and rank with the reasoning shown."
        ),
        request_schema="packages.core.schemas.grna:GuideRNARequest",
        result_schema="packages.core.schemas.grna:GuideRNAResult",
        generator="packages.generation.grna.designer:GuideRNAGenerator",
        validator_ref="packages.validation.grna.validator:build_validator",
        design_model_ref="packages.core.schemas.grna:GuideRNADesign",
        api_route="/v1/grna",
        notes=(
            "Off-target search is scoped to the delivery construct, the target, and any sequence "
            "set the user supplies. It is not genome-wide, and the searched space is stated "
            "verbatim in every view and every export (section 8.6). On-target activity comes from "
            "a published model with a stated validity domain, reported as a prediction; outside "
            "that domain the score is withheld and a labeled heuristic ranks the guides "
            "(section 8.4)."
        ),
    ),
    # ==== /WP-05 ====
}


def list_capabilities() -> list[CapabilitySpec]:
    """Every registered capability, in `CapabilityKind` declaration order."""
    return [CAPABILITY_REGISTRY[kind] for kind in CapabilityKind if kind in CAPABILITY_REGISTRY]


def get_capability(kind: CapabilityKind | str) -> CapabilitySpec:
    """Return the spec for `kind`, raising KeyError with the registered kinds if absent."""
    try:
        return CAPABILITY_REGISTRY[CapabilityKind(kind)]
    except (KeyError, ValueError):
        registered = ", ".join(sorted(item.value for item in CAPABILITY_REGISTRY))
        raise KeyError(f"capability {kind!r} is not registered (registered: {registered})") from None


def resolve_reference(reference: str) -> Any:
    """Load the object behind a `package.module:attribute` reference."""
    module_name, separator, attribute = reference.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError(f"reference {reference!r} must have the form 'package.module:attribute'")
    return getattr(importlib.import_module(module_name), attribute)
