from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator


DNA_ALPHABET = frozenset("ACGT")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_dna(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("DNA sequence must be a string")
    sequence = "".join(value.upper().split())
    if not sequence:
        raise ValueError("DNA sequence must not be empty")
    invalid = sorted(set(sequence) - DNA_ALPHABET)
    if invalid:
        raise ValueError(f"DNA sequence contains non-ACGT characters: {''.join(invalid)}")
    return sequence


class SchemaModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
    )


class PlasmidSource(str, Enum):
    ADDGENE = "addgene"
    GENBANK = "genbank"
    CURATED = "curated"
    LITERATURE = "literature"
    GENERATED = "generated"


class SequenceTopology(str, Enum):
    CIRCULAR = "circular"
    LINEAR = "linear"


class FeatureType(str, Enum):
    ORI = "ORI"
    PROMOTER = "promoter"
    GOI = "GOI"
    MARKER = "marker"
    MCS = "MCS"
    TERMINATOR = "terminator"
    OTHER = "other"


class ValidationStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class FeatureRegion(SchemaModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def end_after_start(self) -> FeatureRegion:
        if self.end <= self.start:
            raise ValueError("region end must be greater than start")
        return self


class AnnotatedFeature(FeatureRegion):
    type: FeatureType
    strand: Literal[-1, 0, 1]
    name: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class AnnotatedSequence(SchemaModel):
    sequence: str
    topology: SequenceTopology
    features: list[AnnotatedFeature] = Field(default_factory=list)
    vector_profile: str = Field(default="unknown", min_length=1)
    annotation_complete: bool

    @field_validator("sequence", mode="before")
    @classmethod
    def validate_sequence(cls, value: Any) -> str:
        return normalize_dna(value)

    @model_validator(mode="after")
    def features_within_sequence(self) -> AnnotatedSequence:
        length = len(self.sequence)
        for feature in self.features:
            if feature.end > length:
                raise ValueError(f"feature {feature.name!r} ends outside the sequence")
        return self

    @property
    def annotation_incomplete(self) -> bool:
        return not self.annotation_complete


class Plasmid(SchemaModel):
    id: str = Field(min_length=1)
    source: PlasmidSource
    name: str = Field(min_length=1)
    sequence: str
    length: int = Field(gt=0)
    organism: str | None = None
    vector_type: str | None = None
    markers: list[str] = Field(default_factory=list)
    promoters: list[str] = Field(default_factory=list)
    publication_doi: str | None = None
    use_cases: list[str] = Field(default_factory=list)
    annotation_complete: bool
    raw_ref: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("sequence", mode="before")
    @classmethod
    def validate_sequence(cls, value: Any) -> str:
        return normalize_dna(value)

    @model_validator(mode="after")
    def length_matches_sequence(self) -> Plasmid:
        if self.length != len(self.sequence):
            raise ValueError("length must match sequence length")
        return self


class TextSpan(SchemaModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str | None = None

    @model_validator(mode="after")
    def end_after_start(self) -> TextSpan:
        if self.end <= self.start:
            raise ValueError("span end must be greater than start")
        return self


class Provenance(SchemaModel):
    doi: str | None = None
    sentence_span: TextSpan


class ExperimentalContext(SchemaModel):
    id: str = Field(min_length=1)
    plasmid_ids: list[str] = Field(min_length=1)
    organism: str
    cell_line: str | None = None
    vector_type: str | None = None
    genes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    promoter_type: str | None = None
    inducer: str | None = None
    application: str | None = None
    assay: str | None = None
    provenance: Provenance
    extraction_confidence: float = Field(ge=0.0, le=1.0)


class DesignSpec(SchemaModel):
    organism: str
    cell_line: str | None = None
    vector_type: str | None = None
    genes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    promoter_type: str | None = None
    inducer: str | None = None
    markers: list[str] = Field(default_factory=list)
    source: PlasmidSource | None = None
    publication_doi: str | None = None
    application: str | None = None
    cloning_method: str | None = None
    constraints: list[str] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: str | None = None

    @model_validator(mode="after")
    def clarification_has_question(self) -> DesignSpec:
        if self.clarification_needed and not self.clarification_question:
            raise ValueError("clarification_question is required when clarification_needed is true")
        return self


class ValidationCheck(SchemaModel):
    name: str = Field(min_length=1)
    status: ValidationStatus
    message: str = Field(min_length=1)
    region: FeatureRegion | None = None
    failure_context: Literal["design_construct_failure", "source_record_uncertainty"] | None = None


class ValidationReport(SchemaModel):
    overall: ValidationStatus
    checks: list[ValidationCheck] = Field(min_length=1)
    generated_by_model_version: str = Field(min_length=1)


class RetrievedPlasmid(SchemaModel):
    plasmid: Plasmid
    score: float = Field(ge=0.0)
    matched_fields: list[str] = Field(default_factory=list)


class PlasmidRecommendation(SchemaModel):
    plasmid_id: str = Field(min_length=1)
    rank: int = Field(ge=1)
    score: float = Field(ge=0.0)
    why_relevant: str = Field(min_length=1)
    suggested_adaptations: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class RetrievalResult(SchemaModel):
    spec: DesignSpec
    retrieved: list[RetrievedPlasmid] = Field(default_factory=list)
    recommendations: list[PlasmidRecommendation] = Field(default_factory=list)
    generated_by: str = Field(min_length=1)
    clarification_needed: bool = False
    clarification_question: str | None = None

    @model_validator(mode="after")
    def clarification_has_question(self) -> RetrievalResult:
        if self.clarification_needed and not self.clarification_question:
            raise ValueError("clarification_question is required when clarification_needed is true")
        return self


class SequenceSpan(SchemaModel):
    """Where one half open span of a generated sequence came from.

    This exists so the section 11.1 provenance gate can be told not merely which
    template a candidate was grounded in, but which bases of the candidate came
    from which bases of that template. The second part is what makes the claim
    checkable: a gate holding only a template id can confirm that an id was
    recorded, while a gate holding coordinates can fetch the named record and
    compare the bases.

    `start` and `end` index the generated sequence. `source_start` and
    `source_end` index the source record. The two ranges are required to be the
    same length, which is what makes a mislabelled span detectable rather than
    merely wrong: a span claiming 300 bases of a template for 200 bases of
    output is rejected when it is constructed, not silently believed.

    `source` is the provenance token, for example `retrieved_template:<id>`, and
    must be a token the design also records in its own provenance. `source_id` is
    the bare id, carried separately so a verifier can look the record up without
    parsing the token.

    Bases with no span are not an error here. They are unattributed, and the gate
    blocks on them. A generator that splices in sequence of its own invention
    should emit no span for those bases rather than inventing a source for them.
    """

    start: int = Field(ge=0)
    end: int = Field(gt=0)
    source: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_start: int = Field(ge=0)
    source_end: int = Field(gt=0)

    @model_validator(mode="after")
    def spans_ordered_and_equal_length(self) -> SequenceSpan:
        if self.end <= self.start:
            raise ValueError(
                f"span ({self.start}, {self.end}) must satisfy start < end "
                "(zero-based, end exclusive)"
            )
        if self.source_end <= self.source_start:
            raise ValueError(
                f"source span ({self.source_start}, {self.source_end}) must satisfy "
                "start < end (zero-based, end exclusive)"
            )
        produced = self.end - self.start
        consumed = self.source_end - self.source_start
        if produced != consumed:
            raise ValueError(
                f"span ({self.start}, {self.end}) covers {produced:,} bp but claims "
                f"{consumed:,} bp of {self.source!r}; a span must account for the same "
                "number of bases on both sides or it cannot be verified"
            )
        return self


class GeneratedSequence(SchemaModel):
    annotated_sequence: AnnotatedSequence
    model_version: str = Field(min_length=1)
    parent_template_ids: list[str] = Field(default_factory=list)

    #: Section 11.1. Per span attribution of the generated bases, empty when the
    #: generator records none. An empty list is not a claim that the sequence is
    #: unattributable, it is the absence of a claim, and the gate treats it as
    #: such: nothing is covered, so nothing may be exported.
    sequence_spans: list[SequenceSpan] = Field(default_factory=list)


class OutcomeReport(SchemaModel):
    design_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    construct_validated: bool | None = None
    sequencing_result: str | None = None
    expression_result: str | None = None
    functional_result: str | None = None
    training_consent: bool = False
    outcome_label: Literal["positive", "negative", "ambiguous"] = "ambiguous"
    provenance: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    reported_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def has_observed_result(self) -> OutcomeReport:
        if (
            self.construct_validated is None
            and not self.sequencing_result
            and not self.expression_result
            and not self.functional_result
        ):
            raise ValueError("at least one outcome observation is required")
        return self


class Match(SchemaModel):
    id: str = Field(min_length=1)
    score: float = Field(ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Vector(RootModel[list[float]]):
    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def non_empty(self) -> Vector:
        if not self.root:
            raise ValueError("vector must not be empty")
        return self
