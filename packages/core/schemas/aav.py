"""Request, cassette and output schemas for the AAV vector designer.

Source: sections 6.1 through 6.8 of the engine capability system design.
`AAVRequest` reproduces the section 6.3 schema field for field. Everything else
here is the cassette representation the generator produces (section 6.7) and the
output shapes section 6.8 requires: a linear element layout with coordinates, a
length budget table, and the structured remediation plan of section 6.6.

Three deliberate design points:

* `AAVDesign` enforces as little biology as possible. It is the input to the
  validator, so it must be able to hold a cassette that is wrong: elements out
  of order, an ITR missing, a coding sequence with a premature stop. The
  section 6.4 checks are what reject those, not this schema. The only invariants
  here are the ones without which nothing can be measured at all: every element
  carries real A, C, G, T sequence and the element list is not empty.
* Coordinates are derived, never stored. `AAVDesign.layout()` lays the elements
  end to end in list order, so a design can never carry coordinates that
  disagree with its own sequences. Zero-based, start inclusive, end exclusive,
  the same convention as `FeatureRegion` and `CheckResult.coordinates`.
* AAV cassettes are linear (sections 6.8 and 10.2). Nothing here has a topology
  field and nothing here is circular.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import Field, RootModel, field_validator

from .capability import CapabilityModel
from .models import normalize_dna

# The section 6.3 `target_tissue` vocabulary. The part registry uses the same
# strings for `tissue_specificity` (see packages/core/part_registry.py), so a
# promoter record and a request can be compared directly.
TargetTissue = Literal[
    "cns_neuron",
    "cns_astrocyte",
    "retina",
    "liver",
    "muscle",
    "cardiac",
    "ubiquitous",
]

TARGET_TISSUES: tuple[str, ...] = (
    "cns_neuron",
    "cns_astrocyte",
    "retina",
    "liver",
    "muscle",
    "cardiac",
    "ubiquitous",
)


class AAVRequest(CapabilityModel):
    """Section 6.3, reproduced field for field.

    No field is added and none is removed. `transgene_sequence` is optional
    because section 6.3 allows retrieval by name; the composer refuses to
    invent one and says so (see packages/generation/aav/composer.py).
    """

    transgene_name: str = Field(min_length=1)
    transgene_sequence: str | None = None  # if absent, retrieve by name
    target_tissue: TargetTissue
    serotype: str = "AAV2"  # ITR source; AAV2 ITRs are standard
    self_complementary: bool = False
    promoter_preference: str | None = None  # part id; else auto-selected
    include_wpre: bool = True
    polya_preference: str | None = None
    packaging_limit_bp: int | None = Field(default=None, gt=0)  # override; default from constants

    @field_validator("transgene_sequence")
    @classmethod
    def clean_transgene(cls, value: str | None) -> str | None:
        return normalize_dna(value) if value is not None else None


class CassetteElementRole(str, Enum):
    """The functional slots of section 6.2, in their required order.

    `5' ITR -> [enhancer] -> promoter -> [intron] -> transgene CDS -> [WPRE]
    -> polyA -> 3' ITR`

    `ENHANCER` and `WPRE` are separate roles even though both are category
    `enhancer` in the part registry, because section 6.2 places a 5' enhancer
    before the promoter and places WPRE after the coding sequence. Collapsing
    them into one role would make `aav.element_order` unable to tell a
    correctly placed WPRE from a misplaced one.

    `KOZAK` is an addition to the section 6.2 list. Section 6.2 names the
    functional order and does not enumerate a translation initiation context
    element. The role is justified on four grounds. The element sits
    immediately 5' of the CDS, so it inverts none of the relations section 6.2
    fixes. `aav.element_order` needs a rank for it. It must be its own role
    rather than bases prepended to the CDS element, because the CDS element's
    bases must stay exactly the coding sequence (`aav.cds_integrity` reads
    it). And section 11.1 requires the 6 bp to be attributed to their own
    source rather than absorbed into the user's transgene. Logged as a spec
    challenge in PROGRESS.md.
    """

    ITR_5 = "itr_5"
    ENHANCER = "enhancer"
    PROMOTER = "promoter"
    INTRON = "intron"
    KOZAK = "kozak"
    CDS = "cds"
    WPRE = "wpre"
    POLYA = "polya"
    ITR_3 = "itr_3"


# Position of each role in the section 6.2 functional order. `aav.element_order`
# compares the design's roles against this ranking.
FUNCTIONAL_ORDER: dict[CassetteElementRole, int] = {
    CassetteElementRole.ITR_5: 0,
    CassetteElementRole.ENHANCER: 1,
    CassetteElementRole.PROMOTER: 2,
    CassetteElementRole.INTRON: 3,
    CassetteElementRole.KOZAK: 4,
    CassetteElementRole.CDS: 5,
    CassetteElementRole.WPRE: 6,
    CassetteElementRole.POLYA: 7,
    CassetteElementRole.ITR_3: 8,
}

# Roles a cassette cannot do without (section 6.4 check 4 names promoter, CDS
# and polyA; checks 2 and 3 cover the ITRs separately).
REQUIRED_ROLES: tuple[CassetteElementRole, ...] = (
    CassetteElementRole.PROMOTER,
    CassetteElementRole.CDS,
    CassetteElementRole.POLYA,
)

# Roles that may simply be dropped when the cassette is over budget. The
# remediation engine of section 6.6 treats removal of these as a candidate
# change; it never proposes removing a promoter, a coding sequence, a polyA or
# an ITR, because the cassette would then fail checks 2, 3 or 4. KOZAK is
# deliberately absent: the engine must never propose removing the initiation
# context element to save 6 bp, which would reintroduce the defect it fixes.
# It is absent from REQUIRED_ROLES too, because a transgene that carries its
# own 5' context is a correct cassette without it.
OPTIONAL_ROLES: tuple[CassetteElementRole, ...] = (
    CassetteElementRole.ENHANCER,
    CassetteElementRole.INTRON,
    CassetteElementRole.WPRE,
)

# Registry category that supplies each role, for the substitution search of
# section 6.6 step 2 ("registry parts in the same category"). This dict is
# deliberately not total over the enum: KOZAK has no registry category.
# `SUBSTITUTABLE_ROLES` in packages/validation/aav/remediation.py gates every
# lookup (`_candidates_for_element` returns before indexing this dict), so a
# role with no registry category is never looked up.
ROLE_PART_CATEGORY: dict[CassetteElementRole, str] = {
    CassetteElementRole.ITR_5: "itr",
    CassetteElementRole.ENHANCER: "enhancer",
    CassetteElementRole.PROMOTER: "promoter",
    CassetteElementRole.INTRON: "intron",
    CassetteElementRole.CDS: "cds",
    CassetteElementRole.WPRE: "enhancer",
    CassetteElementRole.POLYA: "polya",
    CassetteElementRole.ITR_3: "itr",
}


class CassetteElement(CapabilityModel):
    """One element of the cassette: what it is, where it came from, its bases.

    `part_id` is the registry id for anything taken from `data/parts`, and None
    for the transgene coding sequence, which comes from the user or from
    retrieval. Section 11.1 requires that every base be attributable, so an
    element with no `part_id` must carry a `source` saying where it came from.
    """

    role: CassetteElementRole
    name: str = Field(min_length=1)  # display label, for example "CAG promoter"
    sequence: str
    part_id: str | None = None  # registry part id, None for the transgene
    source: str | None = None  # required when part_id is None (section 11.1)
    notes: str | None = None

    @field_validator("sequence", mode="before")
    @classmethod
    def clean(cls, value: Any) -> str:
        return normalize_dna(value)

    @property
    def length_bp(self) -> int:
        return len(self.sequence)

    @property
    def attribution(self) -> str:
        """The provenance entry for this element (section 5.4 rule 5)."""
        if self.part_id:
            return f"part:{self.part_id}"
        return f"{self.source or 'unattributed'}"


class LayoutElement(CapabilityModel):
    """One element with its coordinates in the linear cassette (section 6.8).

    `start` and `end` are zero-based with `end` exclusive, matching
    `CheckResult.coordinates`. `start_1based` and `end_1based` are the inclusive
    form a GenBank FEATURES table and a human both expect.
    """

    index: int = Field(ge=0)
    role: CassetteElementRole
    name: str
    part_id: str | None
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    length_bp: int = Field(gt=0)

    @property
    def start_1based(self) -> int:
        return self.start + 1

    @property
    def end_1based(self) -> int:
        return self.end


class AAVDesign(CapabilityModel):
    """A composed AAV cassette, and the input to the validator.

    Deliberately permissive: see the module docstring. The request level
    settings that a check needs are carried here (`serotype`,
    `self_complementary`, `target_tissue`, `promoter_preference`,
    `packaging_limit_bp`) so that validation is a pure function of this object
    and needs neither the original request nor a database.
    """

    design_id: str = Field(default="aav-design", min_length=1)
    transgene_name: str = Field(min_length=1)
    target_tissue: TargetTissue
    serotype: str = Field(default="AAV2", min_length=1)
    self_complementary: bool = False
    promoter_preference: str | None = None
    polya_preference: str | None = None
    packaging_limit_bp: int | None = Field(default=None, gt=0)
    elements: list[CassetteElement] = Field(min_length=1)
    provenance: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def cassette_sequence(self) -> str:
        """The cassette read 5' to 3', elements laid end to end in list order."""
        return "".join(element.sequence for element in self.elements)

    @property
    def total_bp(self) -> int:
        """Total length, 5' ITR start through 3' ITR end inclusive (check 1)."""
        return sum(element.length_bp for element in self.elements)

    def layout(self) -> tuple[LayoutElement, ...]:
        """Coordinates for every element, derived from the element order."""
        out: list[LayoutElement] = []
        cursor = 0
        for index, element in enumerate(self.elements):
            end = cursor + element.length_bp
            out.append(
                LayoutElement(
                    index=index,
                    role=element.role,
                    name=element.name,
                    part_id=element.part_id,
                    start=cursor,
                    end=end,
                    length_bp=element.length_bp,
                )
            )
            cursor = end
        return tuple(out)

    def elements_with_role(self, role: CassetteElementRole) -> list[CassetteElement]:
        return [element for element in self.elements if element.role == role]

    def first_with_role(self, role: CassetteElementRole) -> CassetteElement | None:
        matches = self.elements_with_role(role)
        return matches[0] if matches else None

    def interior_span(self) -> tuple[int, int] | None:
        """The region strictly between the two ITRs, or None if both are not present.

        Used by `aav.itr_internal_sites`, which asks whether an ITR motif is
        duplicated *inside* the cassette; the ITRs themselves do not count.
        """
        layout = self.layout()
        left = next((item for item in layout if item.role == CassetteElementRole.ITR_5), None)
        right = next((item for item in layout if item.role == CassetteElementRole.ITR_3), None)
        if left is None or right is None or right.start <= left.end:
            return None
        return left.end, right.start


class AAVValidationInput(RootModel[AAVDesign | AAVRequest]):
    """Either a composed cassette or a request that still needs composing.

    This is what the capability registry exposes as `design_model`, so a gold
    case (section 9.3) can supply whichever is natural. A case about element
    order or a missing ITR has to spell out the cassette; a case about the
    packaging limit is more readable as a request. Discrimination is
    unambiguous because both models forbid unknown fields and only `AAVDesign`
    has `elements`.
    """

    def as_design(self) -> AAVDesign:
        return coerce_design(self.root)


def coerce_design(value: Any) -> AAVDesign:
    """Normalise anything the validator may be handed into an `AAVDesign`.

    Accepts an `AAVDesign`, an `AAVValidationInput` wrapper, an `AAVRequest`, or
    a plain mapping of either. A request is resolved through the composer,
    which is imported inside this function and never at module import, so that
    `packages.validation.aav` carries no import time dependency on
    `packages.generation.aav`.
    """
    if isinstance(value, AAVDesign):
        return value
    if isinstance(value, AAVValidationInput):
        return coerce_design(value.root)
    if isinstance(value, AAVRequest):
        from packages.generation.aav.composer import AAVComposer

        return AAVComposer().compose(value)
    if isinstance(value, dict):
        return coerce_design(AAVValidationInput.model_validate(value).root)
    raise TypeError(
        "an AAV design must be an AAVDesign, an AAVRequest, an AAVValidationInput or a mapping of one, "
        f"got {type(value).__name__}"
    )


class LengthBudgetRow(CapabilityModel):
    """One row of the section 6.8 length budget table."""

    index: int = Field(ge=0)
    role: CassetteElementRole
    name: str
    part_id: str | None
    # The element's source token for a row that carries no registry part, for
    # example the transgene or a published rule element.
    source: str | None = None
    length_bp: int = Field(gt=0)
    running_total_bp: int = Field(gt=0)
    headroom_bp: int  # may be negative: that is the overage


class LengthBudget(CapabilityModel):
    """Every element, its bp, the running total, and the remaining headroom.

    Section 10.2 calls this the clearest artifact in the product, so it is a
    first class output rather than a rendering detail.
    """

    rows: list[LengthBudgetRow] = Field(min_length=1)
    total_bp: int = Field(gt=0)
    target_bp: int = Field(gt=0)
    soft_limit_bp: int = Field(gt=0)
    hard_limit_bp: int = Field(gt=0)
    headroom_bp: int  # target_bp - total_bp; negative means over the target
    self_complementary: bool
    limit_basis: str = Field(min_length=1)  # which band was applied, and why

    def to_text(self) -> str:
        """A fixed width table. Deterministic, so it can be snapshot tested."""
        header = f"{'#':>2}  {'element':<26} {'part':<30} {'bp':>7} {'running':>9} {'headroom':>9}"
        lines = [header, "-" * len(header)]
        for row in self.rows:
            lines.append(
                f"{row.index + 1:>2}  {row.name[:26]:<26} {(row.part_id or row.source or 'user supplied')[:30]:<30} "
                f"{row.length_bp:>7,} {row.running_total_bp:>9,} {row.headroom_bp:>9,}"
            )
        lines.append("-" * len(header))
        lines.append(
            f"{'':>2}  {'TOTAL':<26} {'':<30} {self.total_bp:>7,} {self.total_bp:>9,} {self.headroom_bp:>9,}"
        )
        lines.append("")
        lines.append(self.limit_basis)
        lines.append(
            f"target {self.target_bp:,} bp, soft limit {self.soft_limit_bp:,} bp, "
            f"hard limit {self.hard_limit_bp:,} bp"
        )
        return "\n".join(lines)


class ElementChange(CapabilityModel):
    """One proposed change to one element (section 6.6 steps 2 and 3)."""

    kind: Literal["substitute", "remove"]
    role: CassetteElementRole
    from_part_id: str | None
    from_name: str
    from_bp: int = Field(gt=0)
    to_part_id: str | None = None
    to_name: str | None = None
    to_bp: int = Field(default=0, ge=0)
    saved_bp: int = Field(gt=0)
    tradeoff: str = Field(min_length=1)  # the biological cost, in words

    def describe(self) -> str:
        """One readable clause. `from_name` and `to_name` already carry their bp."""
        if self.kind == "remove":
            return f"drop {self.from_name}, which saves {self.saved_bp:,} bp"
        return f"replace {self.from_name} with {self.to_name}, which saves {self.saved_bp:,} bp"


class RemediationPlan(CapabilityModel):
    """A set of changes that together bring the cassette under the target."""

    changes: list[ElementChange] = Field(min_length=1)
    saved_bp: int = Field(gt=0)
    resulting_bp: int = Field(gt=0)
    resulting_headroom_bp: int
    preserves_promoter_preference: bool

    @property
    def change_count(self) -> int:
        return len(self.changes)

    def describe(self) -> str:
        return "; ".join(change.describe() for change in self.changes)


class RemediationReport(CapabilityModel):
    """The output of the section 6.6 engine, structured so it can be asserted."""

    total_bp: int = Field(gt=0)
    target_bp: int = Field(gt=0)
    soft_limit_bp: int = Field(gt=0)
    hard_limit_bp: int = Field(gt=0)
    overage_bp: int = Field(ge=0)
    plans: list[RemediationPlan] = Field(default_factory=list)
    max_available_saving_bp: int = Field(ge=0)
    preference_preserving_saving_bp: int = Field(ge=0)
    """Largest saving reachable without touching a stated `promoter_preference`.

    Reported so the message can say out loud when the user's promoter choice
    cannot be kept, which section 6.6 step 4 asks the engine to prefer and
    which it should therefore explain when it cannot deliver."""
    promoter_preference: str | None = None
    remaining_deficit_bp: int = Field(ge=0)  # nonzero only when no plan closes the gap
    max_transgene_bp: int = Field(ge=0)  # the longest CDS that would fit after every saving
    considered_change_count: int = Field(ge=0)

    @property
    def solved(self) -> bool:
        return bool(self.plans)
