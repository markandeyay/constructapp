"""Composition of an AAV cassette from real parts (section 6.7).

Nothing is invented here. Every base in the output comes from either a curated
record in `data/parts` or from the transgene sequence the user supplied, and
`AAVDesign.provenance` names the source of each one (section 11.1).

The seven steps of section 6.7 map onto `AAVComposer.compose` in order:
resolve the transgene, select a promoter, select a polyA, include WPRE only if
asked for and only if it fits, load the serotype ITR pair, assemble in
functional order with every element annotated, and return the candidate with
full provenance.

Two selection rules are stated here rather than buried, because they are
judgment calls rather than appendix values.

1. **The composer always picks the most compact compatible part in a
   category.** Section 6.7 says to prefer the shortest compatible promoter when
   `self_complementary` is set, and to default to the shortest functional polyA
   when capacity is tight. This implementation applies that rule
   unconditionally, for one reason: the capability's central constraint is a
   hard length budget, the registry quantifies length exactly, and it does not
   quantify promoter strength at all. Ranking on a strength order would mean
   inventing one, which section 3.3 constraint 1 forbids. So the composer
   optimises the quantity it can measure, records the longer alternatives in
   `AAVDesign.notes`, and lets `promoter_preference` and `polya_preference`
   override. An exact `tissue_specificity` match always outranks a ubiquitous
   part regardless of length.
2. **An explicit `promoter_preference` is honoured even when it is
   incompatible with `target_tissue`.** Section 6.7 reads "the user's
   preference if given and compatible", which could be taken to mean silently
   substituting a different promoter when the preference does not match the
   target. This implementation keeps the user's part, records why in
   `AAVDesign.notes`, and lets `aav.promoter_tissue_match` report the WARN that
   section 6.4 check 8 exists to produce. Silently discarding a stated choice
   would hide the very mistake the check is there to surface. Logged as a spec
   challenge in PROGRESS.md.
"""

from __future__ import annotations

import hashlib
from typing import Callable

from packages.core.part_registry import PartCategory, PartRecord, list_parts
from packages.core.schemas.aav import (
    AAVDesign,
    AAVRequest,
    CassetteElement,
    CassetteElementRole,
)
from packages.core.schemas.capability import CapabilityKind
from packages.validation.aav.constants import AAVThresholds, DEFAULT_THRESHOLDS
from packages.validation.aav.itr import UnknownSerotype, serotype_itr_references

# A resolver turns a transgene name into (sequence, provenance entry).
TransgeneResolver = Callable[[str], tuple[str, str]]


class TransgeneUnavailable(LookupError):
    """No sequence is available for the requested transgene.

    Section 6.3 allows `transgene_sequence` to be absent and resolved by name.
    This build ships no transgene corpus and a validator must not need a
    database, so the default resolver refuses rather than inventing a sequence
    (section 3.3 constraint 1 and the section 4.3 rule that a part with a
    placeholder sequence is dangerous because it will be exported as orderable
    DNA). Wire a resolver to enable retrieval by name.
    """

    def __init__(self, name: str) -> None:
        super().__init__(
            f"no sequence was supplied for transgene {name!r} and no transgene resolver is configured, so "
            "the cassette cannot be composed. Supply transgene_sequence on the request, or configure "
            "AAVComposer(transgene_resolver=...) with a resolver that returns real sequence and its "
            "provenance. A placeholder sequence is not an option: the output is exported as orderable DNA."
        )


def _refuse(name: str) -> tuple[str, str]:
    raise TransgeneUnavailable(name)


class AAVComposer:
    """Section 5.2 generator for the AAV capability."""

    kind: CapabilityKind = CapabilityKind.AAV

    def __init__(
        self,
        thresholds: AAVThresholds = DEFAULT_THRESHOLDS,
        parts: list[PartRecord] | None = None,
        transgene_resolver: TransgeneResolver = _refuse,
    ) -> None:
        self.thresholds = thresholds
        self._parts = list(parts) if parts is not None else None
        self.transgene_resolver = transgene_resolver

    # -- registry helpers ---------------------------------------------------

    def parts(self) -> list[PartRecord]:
        return self._parts if self._parts is not None else list_parts()

    def _registry(self) -> dict[str, PartRecord]:
        return {record.id: record for record in self.parts()}

    def _in_category(self, category: PartCategory) -> list[PartRecord]:
        return sorted(
            (record for record in self.parts() if PartCategory(record.category) is category),
            key=lambda record: (record.length_bp, record.id),
        )

    def _require(self, part_id: str, category: PartCategory) -> PartRecord:
        registry = self._registry()
        record = registry.get(part_id)
        if record is None:
            known = ", ".join(part.id for part in self._in_category(category))
            raise KeyError(
                f"part {part_id!r} is not in the registry; registered {PartCategory(category).value} parts "
                f"are: {known}"
            )
        if PartCategory(record.category) is not category:
            raise KeyError(
                f"part {part_id!r} is a {record.category} part, but a {PartCategory(category).value} part "
                f"is required here"
            )
        return record

    # -- step 2: promoter ---------------------------------------------------

    def select_promoter(self, request: AAVRequest, notes: list[str]) -> PartRecord:
        allowed = self.thresholds.tissue_compatibility.get(request.target_tissue, frozenset())
        if request.promoter_preference:
            chosen = self._require(request.promoter_preference, PartCategory.PROMOTER)
            if chosen.tissue_specificity not in allowed:
                notes.append(
                    f"promoter_preference {chosen.id} is annotated {chosen.tissue_specificity} and the "
                    f"target tissue is {request.target_tissue}, which the compatibility table does not "
                    f"accept. The stated preference was kept rather than silently substituted; "
                    f"aav.promoter_tissue_match reports it."
                )
            return chosen
        candidates = [
            record
            for record in self._in_category(PartCategory.PROMOTER)
            if record.tissue_specificity in allowed
        ]
        if not candidates:
            raise LookupError(
                f"no registry promoter is compatible with target tissue {request.target_tissue!r} "
                f"(accepted annotations: {', '.join(sorted(allowed)) or 'none'}). Supply "
                f"promoter_preference explicitly, or add a compatible promoter to data/parts/promoter."
            )
        candidates.sort(
            key=lambda record: (
                0 if record.tissue_specificity == request.target_tissue else 1,
                record.length_bp,
                record.id,
            )
        )
        chosen = candidates[0]
        others = [record for record in candidates[1:]]
        if others:
            notes.append(
                f"promoter {chosen.id} was auto-selected as the most compact part compatible with "
                f"{request.target_tissue} ({chosen.length_bp:,} bp). Longer compatible alternatives, which "
                f"may express more strongly: "
                + ", ".join(f"{record.id} ({record.length_bp:,} bp)" for record in others)
                + ". Set promoter_preference to choose one."
            )
        return chosen

    # -- step 3: polyA ------------------------------------------------------

    def select_polya(self, request: AAVRequest, notes: list[str]) -> PartRecord:
        if request.polya_preference:
            return self._require(request.polya_preference, PartCategory.POLYA)
        candidates = self._in_category(PartCategory.POLYA)
        if not candidates:
            raise LookupError("the part registry carries no polyA part; add one to data/parts/polya")
        chosen = candidates[0]
        others = candidates[1:]
        if others:
            notes.append(
                f"polyA {chosen.id} was auto-selected as the most compact functional signal "
                f"({chosen.length_bp:,} bp). Alternatives: "
                + ", ".join(f"{record.id} ({record.length_bp:,} bp)" for record in others)
                + ". Set polya_preference to choose one."
            )
        return chosen

    # -- compose ------------------------------------------------------------

    def compose(self, request: AAVRequest) -> AAVDesign:
        """Section 6.7, steps 1 through 7."""
        if not isinstance(request, AAVRequest):
            request = AAVRequest.model_validate(request)
        notes: list[str] = []
        provenance: list[str] = []

        # Step 1: resolve the transgene.
        if request.transgene_sequence:
            transgene = request.transgene_sequence
            transgene_source = "user_input:transgene_sequence"
        else:
            transgene, transgene_source = self.transgene_resolver(request.transgene_name)
        provenance.append(transgene_source)

        # Step 5: the serotype ITR pair. Done early so an unknown serotype
        # fails before anything else is selected.
        try:
            reference = serotype_itr_references(request.serotype, self.thresholds, self.parts())
        except UnknownSerotype as exc:
            raise LookupError(str(exc)) from None

        promoter = self.select_promoter(request, notes)
        polya = self.select_polya(request, notes)

        thresholds = self.thresholds.with_packaging_limit(
            request.packaging_limit_bp, request.self_complementary
        )
        target, _soft, _hard = thresholds.band(request.self_complementary)

        # Step 4: WPRE only if requested and only if it fits.
        wpre: PartRecord | None = None
        base_total = (
            reference.left.length_bp
            + promoter.length_bp
            + len(transgene)
            + polya.length_bp
            + reference.right.length_bp
        )
        if request.include_wpre:
            candidates = self._in_category(PartCategory.ENHANCER)
            wpre_part = next((record for record in candidates if record.id == "enhancer.wpre"), None)
            if wpre_part is None:
                notes.append(
                    "include_wpre was requested but the registry carries no enhancer.wpre record, so WPRE "
                    "was omitted."
                )
            elif base_total + wpre_part.length_bp <= target:
                wpre = wpre_part
            else:
                notes.append(
                    f"include_wpre was requested but WPRE ({wpre_part.id}, {wpre_part.length_bp:,} bp) was "
                    f"omitted because adding it would take the cassette to "
                    f"{base_total + wpre_part.length_bp:,} bp against the {target:,} bp target. The cassette "
                    f"is {base_total:,} bp without it."
                )

        # Steps 6 and 7: assemble in functional order and record provenance.
        elements: list[CassetteElement] = [
            CassetteElement(
                role=CassetteElementRole.ITR_5,
                name=reference.left.name,
                sequence=reference.left.sequence,
                part_id=reference.left.id,
                notes=reference.left.source,
            ),
            CassetteElement(
                role=CassetteElementRole.PROMOTER,
                name=promoter.name,
                sequence=promoter.sequence,
                part_id=promoter.id,
                notes=promoter.source,
            ),
            CassetteElement(
                role=CassetteElementRole.CDS,
                name=f"{request.transgene_name} coding sequence",
                sequence=transgene,
                part_id=None,
                source=transgene_source,
                notes=f"transgene {request.transgene_name}",
            ),
        ]
        if wpre is not None:
            elements.append(
                CassetteElement(
                    role=CassetteElementRole.WPRE,
                    name=wpre.name,
                    sequence=wpre.sequence,
                    part_id=wpre.id,
                    notes=wpre.source,
                )
            )
        elements.append(
            CassetteElement(
                role=CassetteElementRole.POLYA,
                name=polya.name,
                sequence=polya.sequence,
                part_id=polya.id,
                notes=polya.source,
            )
        )
        elements.append(
            CassetteElement(
                role=CassetteElementRole.ITR_3,
                name=reference.right.name,
                sequence=reference.right.sequence,
                part_id=reference.right.id,
                notes=reference.right.source,
            )
        )

        provenance.extend(element.attribution for element in elements if element.part_id)
        provenance.append(f"serotype_reference:{reference.left.provenance.accession}")

        return AAVDesign(
            design_id=stable_design_id(elements),
            transgene_name=request.transgene_name,
            target_tissue=request.target_tissue,
            serotype=request.serotype,
            self_complementary=request.self_complementary,
            promoter_preference=request.promoter_preference,
            polya_preference=request.polya_preference,
            packaging_limit_bp=request.packaging_limit_bp,
            elements=elements,
            provenance=_dedupe(provenance),
            notes=notes,
        )


def _dedupe(values: list[str]) -> list[str]:
    """Order preserving de-duplication, so provenance lists each source once."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def stable_design_id(elements: list[CassetteElement]) -> str:
    """A deterministic design id derived from the cassette itself.

    The same request always yields the same id (section 3.3 constraint 3), so a
    design can be referred to, cached and compared without a clock or a random
    source.
    """
    digest = hashlib.sha256("".join(element.sequence for element in elements).encode("ascii")).hexdigest()
    return f"aav-{digest[:12]}"
