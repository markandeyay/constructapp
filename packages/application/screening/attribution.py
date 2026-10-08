"""Base level attribution: the data model the provenance assertion runs on.

Source: section 11.1 item 1 of the engine capability system design, read
together with section 4.2.

Section 11.1 item 1 requires that "every base in the output traces to a
registry part, a retrieved template, or the user's own supplied input" and that
"a design containing unattributable sequence is blocked from export". Section
4.2 states the same property with a third category: "every base in the output
traces to either the user's input, a curated part record, or a published rule."

`DesignResult.provenance` is a list of source tokens. It says which sources a
design drew on; it cannot say which base came from which source, so on its own
it cannot support a base level claim. This module adds the missing structure: a
sequence plus a list of half open spans, each naming its origin and its source
token. The provenance assertion in `provenance.py` then checks that the spans
cover the sequence completely, that each source is declared in the design's own
provenance, and that each registry span really does reproduce the registry
record it names.

The union of the two specification sections gives exactly four permitted
origins and no fifth. A span that cannot be placed in one of the four is not
representable, and a base covered by no span is unattributable, which blocks
the export. Nothing here can mark a base as attributed without naming where it
came from.

Coordinates are zero-based, start inclusive, end exclusive, the same convention
as `FeatureRegion` in `packages/core/schemas/models.py` and
`CheckResult.coordinates`.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator, model_validator

from packages.core.schemas.capability import CapabilityKind, CapabilityModel


class SequenceOrigin(str, Enum):
    """Where the bases of one span came from. These four and no others.

    `REGISTRY_PART`, `RETRIEVED_TEMPLATE` and `USER_INPUT` are the three
    categories section 11.1 item 1 names. `PUBLISHED_RULE` is the third
    category in section 4.2's wording of the same property, and it covers bases
    whose identity is fixed by a rule rather than copied from a sequence
    record: a Type IIS recognition site from Appendix D, a published cloning
    vector overhang, a spacer nucleotide chosen by a documented deterministic
    rule. A `PUBLISHED_RULE` span must name its rule, and every such span is
    listed individually in the audit entry, so rule derived bases are visible
    rather than absorbed into a general pass.
    """

    REGISTRY_PART = "registry_part"
    RETRIEVED_TEMPLATE = "retrieved_template"
    USER_INPUT = "user_input"
    PUBLISHED_RULE = "published_rule"


#: Origins that section 11.1 item 2 treats as curated composition: bases copied
#: out of a record in `data/parts`. Used by `composition.py`.
REGISTRY_ORIGINS = frozenset({SequenceOrigin.REGISTRY_PART})


class AttributedSegment(CapabilityModel):
    """One half open span of an exported sequence, and where its bases came from.

    `source` is the provenance token for the span and must be one of the tokens
    in the design's own `provenance` list, so the two cannot disagree. For a
    registry part the token is `part:<registry id>`, which is what
    `CassetteElement.attribution` already produces; `part_id` carries the bare
    id so the assertion can look the record up and compare bases.

    `rule` is required when `origin` is `PUBLISHED_RULE` and must name the rule
    the bases follow, for example "Appendix D BsaI recognition site GGTCTC".
    Without it a rule derived span would be an unchecked claim.
    """

    start: int = Field(ge=0)
    end: int = Field(gt=0)
    origin: SequenceOrigin
    source: str = Field(min_length=1)
    part_id: str | None = None
    rule: str | None = None
    detail: str | None = None

    @field_validator("source")
    @classmethod
    def source_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a segment source must not be blank")
        return value

    @model_validator(mode="after")
    def span_ordered(self) -> AttributedSegment:
        if self.end <= self.start:
            raise ValueError(
                f"segment ({self.start}, {self.end}) must satisfy start < end "
                "(zero-based, end exclusive)"
            )
        return self

    @model_validator(mode="after")
    def published_rule_names_its_rule(self) -> AttributedSegment:
        if self.origin is SequenceOrigin.PUBLISHED_RULE and not (self.rule or "").strip():
            raise ValueError(
                "a published_rule segment must name its rule; a rule derived base with no "
                "named rule is not attributable (section 4.2)"
            )
        return self

    @model_validator(mode="after")
    def registry_segment_names_a_part(self) -> AttributedSegment:
        if self.origin is SequenceOrigin.REGISTRY_PART and not (self.part_id or "").strip():
            raise ValueError(
                "a registry_part segment must carry part_id so the record can be looked up "
                "and compared base for base (section 11.1 item 2)"
            )
        return self

    @property
    def length_bp(self) -> int:
        return self.end - self.start


class AttributedSequence(CapabilityModel):
    """One exported sequence with its attribution spans.

    `name` identifies the sequence inside the design, for example "cassette",
    "primer:insert_F" or "oligo:guide_1_sense". It appears verbatim in the
    audit entry and in any blocking message, so a reader can tell which
    sequence was the problem.

    Segments are not required to be sorted or complete here. Completeness is
    the question the provenance assertion answers, and an adapter that cannot
    prove where a span came from is expected to emit no segment for it, leaving
    a gap that blocks the export, rather than guessing.
    """

    name: str = Field(min_length=1)
    sequence: str = Field(min_length=1)
    segments: list[AttributedSegment] = Field(default_factory=list)
    role: str | None = None

    @field_validator("sequence")
    @classmethod
    def sequence_is_dna(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("an attributed sequence must not be empty")
        unexpected = sorted(set(cleaned) - set("ACGT"))
        if unexpected:
            raise ValueError(
                "an attributed sequence must be A, C, G or T only; found "
                + ", ".join(repr(char) for char in unexpected)
            )
        return cleaned

    @property
    def length_bp(self) -> int:
        return len(self.sequence)

    def bases(self, segment: AttributedSegment) -> str:
        """The bases a segment covers. Raises when the span leaves the sequence."""
        if segment.end > len(self.sequence):
            raise IndexError(
                f"segment ({segment.start}, {segment.end}) leaves sequence {self.name!r} "
                f"of {len(self.sequence)} bp"
            )
        return self.sequence[segment.start : segment.end]


class ExportSubject(CapabilityModel):
    """Everything the pre-export screening step needs about one design.

    Built from a capability's own design object by an adapter in
    `adapters/`, so no capability package has to know this module exists.

    `declared_provenance` is the design's `DesignResult.provenance` verbatim.
    Every segment source must appear in it: the point is that the recorded
    provenance list and the base level attribution agree, so that the list a
    user reads is the list the sequence was actually built from.
    """

    capability: CapabilityKind
    design_id: str = Field(min_length=1)
    validator_version: str = Field(min_length=1)
    sequences: list[AttributedSequence] = Field(default_factory=list)
    declared_provenance: list[str] = Field(default_factory=list)
    adapter: str = Field(min_length=1)

    @property
    def total_bp(self) -> int:
        return sum(item.length_bp for item in self.sequences)

    def sequence(self, name: str) -> AttributedSequence:
        for item in self.sequences:
            if item.name == name:
                return item
        raise KeyError(f"no sequence named {name!r} in subject {self.design_id!r}")
