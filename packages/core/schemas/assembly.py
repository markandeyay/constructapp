"""Request and result schemas for the primer and assembly capability.

Source: sections 7.2 and 7.7 of the engine capability system design, on the
shared contract in `capability.py` (section 5.1).

`AssemblyRequest` reproduces section 7.2 field for field, with the same names,
the same types and the same defaults. Five optional fields are added after
those, each defaulted so a section 7.2 request still validates unchanged, and
each needed by a requirement stated elsewhere in section 7:

* `overhang_standard`: Appendix D requires a published modular standard's
  overhang set to be used verbatim when the assembly follows that standard.
  There is nowhere in section 7.2 to say which standard.
* `host_codon_usage`: section 7.6 requires the domestication report to compare
  host codon frequencies. There is nowhere in section 7.2 to supply the table.
* `thresholds`: section 3.3 constraint 2 requires every threshold to be
  configurable. This is where a caller configures them.
* `hairpin_engine`: open question Q6. Lets a caller, or a test, pin the
  secondary structure engine instead of taking whatever the environment has.
* `coding_regions` on `Fragment`: section 7.6 requires a silent substitution to
  preserve the amino acid, which is only defined inside a coding sequence and
  only with a known reading frame.

Coordinates are zero-based, start inclusive, end exclusive, matching
`FeatureRegion` in `models.py` and `CheckResult.coordinates`.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from packages.core.sequence import clean_sequence

from .capability import CapabilityKind, CapabilityModel, ValidationReport

Strategy = Literal["gibson", "golden_gate", "pcr_cloning"]
FragmentRole = Literal["insert", "vector", "linker"]
PrimerDirection = Literal["forward", "reverse"]
HairpinEngine = Literal["auto", "viennarna", "window"]


def _dna(value: str) -> str:
    """Normalise a DNA string, rejecting anything that is not A, C, G or T.

    Ambiguity codes are rejected rather than accepted: an ordered primer is
    made of four bases, and silently carrying an N into a Tm calculation or a
    recognition site search would produce a number with no meaning.
    """
    return clean_sequence(value)


class AssemblyThresholds(CapabilityModel):
    """Per-request overrides for the thresholds in `validation/assembly/constants.py`.

    Section 3.3 constraint 2: "Every threshold is configurable." Any field left
    None takes the cited default from that module. A field set here is used
    instead and appears in `parameters_used` with the same name, so a report
    always shows what it was actually measured against.
    """

    primer_tm_warn_tolerance_c: float | None = Field(default=None, gt=0)
    primer_tm_fail_tolerance_c: float | None = Field(default=None, gt=0)
    primer_pair_max_tm_delta_c: float | None = Field(default=None, gt=0)
    primer_gc_min_fraction: float | None = Field(default=None, ge=0, le=1)
    primer_gc_max_fraction: float | None = Field(default=None, ge=0, le=1)
    primer_min_length_nt: int | None = Field(default=None, ge=2)
    primer_max_length_nt: int | None = Field(default=None, ge=2)
    primer_max_total_length_nt: int | None = Field(default=None, ge=2)
    primer_three_prime_window_nt: int | None = Field(default=None, ge=1)
    primer_three_prime_max_gc_in_window: int | None = Field(default=None, ge=0)
    primer_max_homopolymer_run_nt: int | None = Field(default=None, ge=2)
    hairpin_min_loop_nt: int | None = Field(default=None, ge=1)
    hairpin_dg_warn_kcal_per_mol: float | None = None
    hairpin_three_prime_dg_fail_kcal_per_mol: float | None = None
    hairpin_window_stem_warn_bp: int | None = Field(default=None, ge=1)
    hairpin_window_stem_three_prime_fail_bp: int | None = Field(default=None, ge=1)
    three_prime_involvement_window_nt: int | None = Field(default=None, ge=1)
    max_self_complementarity_any_bp: float | None = Field(default=None, ge=0)
    max_self_complementarity_end_bp: float | None = Field(default=None, ge=0)
    max_pair_complementarity_any_bp: float | None = Field(default=None, ge=0)
    max_pair_complementarity_end_bp: float | None = Field(default=None, ge=0)
    gibson_overlap_min_bp: int | None = Field(default=None, ge=1)
    gibson_overlap_max_bp: int | None = Field(default=None, ge=1)
    gibson_overlap_design_bp: int | None = Field(default=None, ge=1)
    gibson_overlap_min_tm_c: float | None = None
    gibson_junction_max_shared_homology_bp: int | None = Field(default=None, ge=1)
    golden_gate_primer_spacer_nt: int | None = Field(default=None, ge=0)
    golden_gate_default_overhang_nt: int | None = Field(default=None, ge=1)
    amplicon_min_bp: int | None = Field(default=None, ge=1)
    amplicon_max_bp: int | None = Field(default=None, ge=1)
    annealing_offset_below_min_tm_c: float | None = None
    annealing_min_c: float | None = None
    annealing_max_c: float | None = None

    @model_validator(mode="after")
    def windows_ordered(self) -> AssemblyThresholds:
        pairs = (
            ("primer_gc_min_fraction", "primer_gc_max_fraction"),
            ("primer_min_length_nt", "primer_max_length_nt"),
            ("gibson_overlap_min_bp", "gibson_overlap_max_bp"),
            ("amplicon_min_bp", "amplicon_max_bp"),
            ("annealing_min_c", "annealing_max_c"),
        )
        for low_name, high_name in pairs:
            low = getattr(self, low_name)
            high = getattr(self, high_name)
            if low is not None and high is not None and low > high:
                raise ValueError(f"{low_name} must not exceed {high_name}")
        return self


class OverhangStandardSpec(CapabilityModel):
    """A published modular assembly standard's overhang set, supplied by a caller.

    Appendix D: "If the assembly follows a published modular standard, use that
    standard's defined overhang set rather than generating overhangs, and cite
    the standard." `citation` is mandatory and is carried into the design's
    `provenance`, so an assembly can never claim to follow a standard without
    naming it. No standard is bundled with this build: see the note in
    `packages/validation/assembly/enzymes.py`.
    """

    name: str = Field(min_length=1)
    citation: str = Field(min_length=1)
    overhangs: list[str] = Field(min_length=1)

    @field_validator("overhangs")
    @classmethod
    def clean_overhangs(cls, value: list[str]) -> list[str]:
        cleaned = [_dna(item) for item in value]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("an overhang standard must not repeat an overhang")
        return cleaned


class HostCodonUsageSpec(CapabilityModel):
    """A host codon usage table supplied by a caller, with its host and source.

    Section 7.6 asks for "the host codon frequency of both" codons in a
    domestication edit, and Appendix E says to "name the table and the host".
    No table ships with this build, so without one the frequency comparison is
    reported as UNKNOWN with a reason rather than invented. See
    `packages/validation/assembly/codon_usage.py`.

    `frequencies` maps a codon to its relative usage within its synonymous
    family, so the values for one amino acid sum to 1.
    """

    host: str = Field(min_length=1)
    citation: str = Field(min_length=1)
    frequencies: dict[str, float] = Field(min_length=1)


class Fragment(CapabilityModel):
    """One fragment going into the assembly: sequence, role and source (section 7.2).

    `coding_regions` are zero-based half-open intervals on `sequence` whose
    first base is the first base of a codon. They are needed only for Golden
    Gate domestication (section 7.6), which must preserve the amino acid when a
    recognition site falls inside a coding sequence. A fragment with no
    declared coding region is domesticated with any minimal site-destroying
    edit, which section 7.6 states is correct outside a coding sequence.
    """

    name: str = Field(min_length=1)
    sequence: str = Field(min_length=1)
    role: FragmentRole = "insert"
    source: str = Field(min_length=1)
    coding_regions: list[tuple[int, int]] = Field(default_factory=list)
    is_circular: bool = False

    @field_validator("sequence")
    @classmethod
    def normalise_sequence(cls, value: str) -> str:
        return _dna(value)

    @model_validator(mode="after")
    def coding_regions_in_frame(self) -> Fragment:
        for start, end in self.coding_regions:
            if start < 0 or end <= start or end > len(self.sequence):
                raise ValueError(
                    f"coding region ({start}, {end}) is not inside fragment {self.name!r} "
                    f"of {len(self.sequence)} bp (zero-based, end exclusive)"
                )
            if (end - start) % 3 != 0:
                raise ValueError(
                    f"coding region ({start}, {end}) of fragment {self.name!r} is "
                    f"{end - start} bp, which is not a whole number of codons"
                )
        return self

    @property
    def length_bp(self) -> int:
        return len(self.sequence)


class AssemblyRequest(CapabilityModel):
    """Section 7.2, field for field, plus the five documented optional additions."""

    strategy: Strategy
    fragments: list[Fragment] = Field(min_length=1)  # sequence + role + source
    vector_backbone: str | None = None
    enzyme: str | None = None  # required for golden_gate
    target_tm_c: float = 60.0
    primer_conc_nm: float = 500.0
    monovalent_salt_mm: float = 50.0
    divalent_salt_mm: float = 1.5
    dntp_mm: float = 0.2
    # Additions, each defaulted so a section 7.2 request validates unchanged.
    overhang_standard: OverhangStandardSpec | None = None
    host_codon_usage: HostCodonUsageSpec | None = None
    thresholds: AssemblyThresholds | None = None
    hairpin_engine: HairpinEngine = "auto"

    @field_validator("vector_backbone")
    @classmethod
    def normalise_backbone(cls, value: str | None) -> str | None:
        return _dna(value) if value else None

    @field_validator("primer_conc_nm")
    @classmethod
    def positive_primer_concentration(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("primer_conc_nm must be positive: Tm depends on ln(strand concentration)")
        return value

    @field_validator("monovalent_salt_mm")
    @classmethod
    def positive_monovalent_salt(cls, value: float) -> float:
        if value <= 0:
            raise ValueError(
                "monovalent_salt_mm must be positive: the Appendix A salt correction uses ln([Na+])"
            )
        return value

    @model_validator(mode="after")
    def enzyme_required_for_golden_gate(self) -> AssemblyRequest:
        if self.strategy == "golden_gate" and not (self.enzyme or "").strip():
            raise ValueError("strategy 'golden_gate' requires `enzyme` (section 7.2)")
        return self

    @model_validator(mode="after")
    def fragment_names_unique(self) -> AssemblyRequest:
        names = [fragment.name for fragment in self.fragments]
        if len(set(names)) != len(names):
            raise ValueError("fragment names must be unique: they identify primers in the order table")
        return self

    @property
    def template_set(self) -> dict[str, str]:
        """Every sequence a primer could bind, for section 7.5 check 9.

        The fragments plus the vector backbone when one is supplied. Check 9
        requires a primer's binding region to occur exactly once across this
        set, so the set has to be exactly what will be in the tube.
        """
        templates = {fragment.name: fragment.sequence for fragment in self.fragments}
        if self.vector_backbone:
            templates["vector_backbone"] = self.vector_backbone
        return templates


class Primer(CapabilityModel):
    """One designed primer.

    `sequence` is `tail + binding`, written 5' to 3', which is how it is
    ordered and how the section 7.7 order table prints it. `tail` is the 5'
    addition that does not bind the template: a Gibson homology arm, or a Type
    IIS site plus spacer plus fusion overhang, or a restriction site. `binding`
    is the part that anneals, and it is what the Tm, GC, length, specificity
    and 3' stability checks are measured on, because that is the part that has
    to anneal.

    `binding_start` and `binding_end` locate the binding region on the named
    fragment, zero-based and end exclusive, on the forward strand of that
    fragment regardless of the primer's direction.
    """

    name: str = Field(min_length=1)
    fragment: str = Field(min_length=1)
    direction: PrimerDirection
    tail: str = ""
    binding: str = Field(min_length=1)
    binding_start: int = Field(ge=0)
    binding_end: int = Field(gt=0)
    notes: list[str] = Field(default_factory=list)

    @field_validator("tail")
    @classmethod
    def normalise_tail(cls, value: str) -> str:
        return _dna(value) if value else ""

    @field_validator("binding")
    @classmethod
    def normalise_binding(cls, value: str) -> str:
        return _dna(value)

    @model_validator(mode="after")
    def binding_interval_ordered(self) -> Primer:
        if self.binding_end <= self.binding_start:
            raise ValueError("binding_end must be greater than binding_start")
        if self.binding_end - self.binding_start != len(self.binding):
            raise ValueError(
                f"primer {self.name!r}: binding region is {len(self.binding)} nt but the interval "
                f"({self.binding_start}, {self.binding_end}) spans {self.binding_end - self.binding_start}"
            )
        return self

    @property
    def sequence(self) -> str:
        return f"{self.tail}{self.binding}"

    @property
    def length_nt(self) -> int:
        return len(self.tail) + len(self.binding)


class Junction(CapabilityModel):
    """One join between two fragments.

    `sequence` is the terminal homology arm for Gibson, the fusion overhang for
    Golden Gate, or the restriction site for simple PCR cloning. `overhang_source`
    records whether a Golden Gate overhang was taken from the fragment junction
    itself (the scarless case) or from a published standard's defined set, which
    Appendix D requires to be used verbatim and cited when one applies.
    """

    index: int = Field(ge=0)
    left_fragment: str = Field(min_length=1)
    right_fragment: str = Field(min_length=1)
    kind: Literal["gibson_homology", "golden_gate_overhang", "restriction_site"]
    sequence: str = Field(min_length=1)
    overhang_source: Literal["fragment_junction", "overhang_standard"] | None = None
    overhang_standard_name: str | None = None

    @field_validator("sequence")
    @classmethod
    def normalise_sequence(cls, value: str) -> str:
        return _dna(value)

    @property
    def length_bp(self) -> int:
        return len(self.sequence)


class Amplicon(CapabilityModel):
    """One expected PCR product, for section 7.5 check 19."""

    name: str = Field(min_length=1)
    fragment: str = Field(min_length=1)
    forward_primer: str = Field(min_length=1)
    reverse_primer: str = Field(min_length=1)
    length_bp: int = Field(gt=0)


class DomesticationEdit(CapabilityModel):
    """One proposed silent edit from the section 7.6 domestication report.

    Section 7.6: "Report the position, the original codon, the proposed codon,
    the amino acid preserved, and the host codon frequency of both."

    `in_coding_sequence` says which rule was applied. Inside a coding sequence
    the edit is a synonymous codon substitution and `amino_acid` is the residue
    preserved. Outside one, section 7.6 allows any site-destroying substitution
    and prefers the minimal edit, so `original_codon` and `proposed_codon` hold
    the single base changed, `amino_acid` is None, and `codon_position` is None.

    `host_frequency_original` and `host_frequency_proposed` are None whenever no
    host codon usage table was available, and `host_frequency_status` is then
    `"unknown"` with `host_frequency_reason` giving the reason. Section 3.3
    constraint 4: a quantity that could not be evaluated is reported as unknown
    with a reason, never as a number and never omitted.
    """

    fragment: str = Field(min_length=1)
    site_start: int = Field(ge=0)
    site_end: int = Field(gt=0)
    site_strand: int
    recognition_site: str = Field(min_length=1)
    edit_position: int = Field(ge=0)
    original_base: str = Field(min_length=1, max_length=1)
    proposed_base: str = Field(min_length=1, max_length=1)
    in_coding_sequence: bool
    codon_position: int | None = None
    original_codon: str | None = None
    proposed_codon: str | None = None
    amino_acid: str | None = None
    host_frequency_status: Literal["known", "unknown"] = "unknown"
    host_frequency_original: float | None = None
    host_frequency_proposed: float | None = None
    host_frequency_table: str | None = None
    host_frequency_reason: str | None = None

    @model_validator(mode="after")
    def frequency_consistent(self) -> DomesticationEdit:
        if self.host_frequency_status == "known":
            if self.host_frequency_original is None or self.host_frequency_proposed is None:
                raise ValueError("host_frequency_status 'known' needs both frequencies")
            if not self.host_frequency_table:
                raise ValueError("a known host frequency must name the table it came from")
        elif not self.host_frequency_reason:
            raise ValueError("host_frequency_status 'unknown' needs a reason (section 3.3 constraint 4)")
        return self

    @property
    def summary(self) -> str:
        """One line for the structured `CheckResult.remediation` list."""
        where = (
            f"codon {self.original_codon} to {self.proposed_codon} at codon position "
            f"{self.codon_position}, {self.amino_acid} preserved"
            if self.in_coding_sequence
            else f"base {self.original_base} to {self.proposed_base}, outside any coding sequence"
        )
        frequency = (
            f"host frequency {self.host_frequency_original:.4f} to {self.host_frequency_proposed:.4f} "
            f"in {self.host_frequency_table}"
            if self.host_frequency_status == "known"
            else "host codon frequency UNKNOWN"
        )
        return (
            f"{self.fragment} position {self.edit_position}: {self.original_base} to "
            f"{self.proposed_base} destroys the {self.recognition_site} site at "
            f"{self.site_start}..{self.site_end} (strand {self.site_strand:+d}); {where}; {frequency}"
        )


class UndomesticatableSite(CapabilityModel):
    """A recognition site for which no acceptable edit exists.

    Reported rather than silently dropped, because a domestication report that
    lists four of five sites reads as a complete plan and is not one.
    """

    fragment: str = Field(min_length=1)
    site_start: int = Field(ge=0)
    site_end: int = Field(gt=0)
    site_strand: int
    recognition_site: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class DomesticationReport(CapabilityModel):
    """The section 7.6 report produced when check 14 finds an internal site."""

    enzyme: str = Field(min_length=1)
    recognition_site: str = Field(min_length=1)
    sites_found: int = Field(ge=0)
    edits: list[DomesticationEdit] = Field(default_factory=list)
    unresolved: list[UndomesticatableSite] = Field(default_factory=list)
    host_codon_usage_table: str | None = None
    host_codon_usage_status: Literal["known", "unknown"] = "unknown"
    notes: list[str] = Field(default_factory=list)

    @property
    def fully_resolved(self) -> bool:
        return self.sites_found > 0 and not self.unresolved


class AssemblyDesign(CapabilityModel):
    """A primer and assembly design: the request plus everything composed from it.

    This is the model the validator validates and the model the gold-set runner
    parses a case `input` into. `primers`, `junctions` and `amplicons` may be
    left empty, in which case the validator composes them from the request with
    the deterministic designer before validating, and records that it did so.
    That is deliberate: a gold case that targets a fragment-level check (an
    internal Type IIS site, a duplicated overhang) supplies fragments only,
    while a case that targets a primer-level check (a large pair Tm difference,
    an extendable 3' hetero-dimer) pins the exact primers. Both are needed.
    """

    request: AssemblyRequest
    primers: list[Primer] = Field(default_factory=list)
    junctions: list[Junction] = Field(default_factory=list)
    amplicons: list[Amplicon] = Field(default_factory=list)
    fragment_order: list[str] = Field(default_factory=list)
    domestication: DomesticationReport | None = None
    provenance: list[str] = Field(default_factory=list)
    composed: bool = False

    def fragment(self, name: str) -> Fragment:
        for item in self.request.fragments:
            if item.name == name:
                return item
        raise KeyError(f"fragment {name!r} is not in the request")

    def primer_pairs(self) -> list[tuple[Primer, Primer]]:
        """Forward and reverse primers grouped by fragment, in fragment order.

        A fragment with only one primer yields no pair, so the pair checks
        (section 7.5 checks 2 and 8) skip it rather than comparing a primer
        with itself.
        """
        pairs: list[tuple[Primer, Primer]] = []
        for fragment in self.request.fragments:
            forward = next(
                (p for p in self.primers if p.fragment == fragment.name and p.direction == "forward"), None
            )
            reverse = next(
                (p for p in self.primers if p.fragment == fragment.name and p.direction == "reverse"), None
            )
            if forward is not None and reverse is not None:
                pairs.append((forward, reverse))
        return pairs


class OrderTableRow(CapabilityModel):
    """One row of the section 7.7 order table.

    Section 7.7: "primer name, sequence written 5' to 3', length, Tm, GC%, and
    a notes column. This is the artifact a lab actually uses, so it must be
    copy-pasteable and CSV-exportable."
    """

    name: str = Field(min_length=1)
    sequence_5_to_3: str = Field(min_length=1)
    length_nt: int = Field(gt=0)
    tm_c: float
    gc_percent: float
    notes: str = ""


class ThermocyclingStep(CapabilityModel):
    """One step of a thermocycling or incubation program."""

    label: str = Field(min_length=1)
    temperature_c: float
    seconds: int = Field(gt=0)
    cycles: int = Field(default=1, gt=0)


class Protocol(CapabilityModel):
    """The section 7.7 protocol.

    `annealing_temperature_c` is derived from the computed primer Tm values, not
    assumed, as section 7.7 requires, and `annealing_rule` states the rule that
    derived it so the number can be checked.
    """

    strategy: Strategy
    reaction_composition: list[str] = Field(min_length=1)
    annealing_temperature_c: float
    annealing_rule: str = Field(min_length=1)
    pcr_program: list[ThermocyclingStep] = Field(min_length=1)
    assembly_program: list[ThermocyclingStep] = Field(default_factory=list)
    expected_outcome: str = Field(min_length=1)
    sources: list[str] = Field(min_length=1)


class JunctionMapEntry(CapabilityModel):
    """One labelled join in the section 7.7 junction map."""

    index: int = Field(ge=0)
    left_fragment: str = Field(min_length=1)
    right_fragment: str = Field(min_length=1)
    label: str = Field(min_length=1)
    sequence: str = Field(min_length=1)
    length_bp: int = Field(gt=0)
    detail: str = Field(min_length=1)


class AssemblyOutputs(CapabilityModel):
    """Everything section 7.7 lists, assembled into one payload.

    `order_table` and `order_table_csv` required at least one row until the
    section 11.1 provenance gate reached this capability. That constraint
    encoded an assumption that is no longer true: a composed assembly always has
    primers, but an assembly whose primers cannot all be attributed has an order
    table that must not be handed over. Both fields are therefore allowed to be
    empty, and empty means withheld rather than absent.

    A caller must read `AssemblyResponse.export_blocked` instead of inferring
    from a non-empty table that an export was permitted. Nothing fills these
    fields with a placeholder row: section 4.3 forbids a placeholder sequence
    precisely because it would be exported as orderable DNA.
    """

    order_table: list[OrderTableRow] = Field(default_factory=list)
    order_table_csv: str = ""
    protocol: Protocol
    junction_map: list[JunctionMapEntry] = Field(default_factory=list)
    junction_map_text: str = ""
    domestication: DomesticationReport | None = None
    report: ValidationReport

    @property
    def capability(self) -> CapabilityKind:
        return CapabilityKind.ASSEMBLY


class AssemblyResponse(CapabilityModel):
    """What the section 7 API endpoint returns."""

    design_id: str = Field(min_length=1)
    design: AssemblyDesign
    outputs: AssemblyOutputs
    provenance: list[str] = Field(min_length=1)
    parameters_used: dict[str, Any] = Field(min_length=1)

    #: Section 11.1. True when the provenance gate refused this design's order
    #: table, in which case `outputs.order_table` and `outputs.order_table_csv`
    #: are empty and `export_block_reason` names the span that could not be
    #: attributed. The design and the validation report are still populated,
    #: because the gate blocks the export and not the design.
    export_blocked: bool = False
    export_block_reason: str | None = None


DesignInput = Annotated[AssemblyDesign, Field(description="Section 7 assembly design")]
