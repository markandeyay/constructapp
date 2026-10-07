"""Loader and validator for the AAV part registry in `data/parts/`.

Source: section 4.3 of the engine capability system design. Each JSON file under
`data/parts/<category>/` is one part record. The top-level fields are exactly
those of the section 4.3 example. A `provenance` object is added alongside them
to carry the GenBank accession, feature type, coordinates and retrieval date
that `data/parts/PROVENANCE.md` tabulates.

The loader refuses a record that would be unsafe to export as DNA: the sequence
must be non-empty A, C, G and T only, `length_bp` must equal the real sequence
length (the sequence is authoritative, Appendix B lengths are planning figures),
and the record must carry a source and a citation. There is no placeholder
path: a part with no real sequence is simply not in the registry.
"""

from __future__ import annotations

import json
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator

from .schemas.models import SchemaModel, normalize_dna

DEFAULT_PARTS_DIR = Path(__file__).resolve().parents[2] / "data" / "parts"


class PartCategory(str, Enum):
    ITR = "itr"
    PROMOTER = "promoter"
    POLYA = "polya"
    ENHANCER = "enhancer"
    INTRON = "intron"


# Values of `tissue_specificity` match the AAVRequest `target_tissue` vocabulary
# of section 6.3, so a promoter can be compared with the request directly.
# None means the part carries no tissue claim (everything except promoters).
TISSUE_SPECIFICITY_VALUES = frozenset(
    {"cns_neuron", "cns_astrocyte", "retina", "liver", "muscle", "cardiac", "ubiquitous"}
)


class PartProvenance(SchemaModel):
    accession: str = Field(min_length=1)  # GenBank accession.version
    record_title: str = Field(min_length=1)
    feature_type: str = Field(min_length=1)
    feature_note: str | None = None
    coordinates: tuple[int, int]  # 1-based, inclusive, as in the GenBank FEATURES table
    strand: int  # 1 means the part is the plus strand slice of the record
    retrieved_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    retrieved_via: str = Field(min_length=1)

    @model_validator(mode="after")
    def coordinates_ordered(self) -> PartProvenance:
        start, end = self.coordinates
        if start < 1 or end < start:
            raise ValueError("coordinates must satisfy 1 <= start <= end")
        if self.strand not in (1, -1):
            raise ValueError("strand must be 1 or -1")
        return self


class PartRecord(SchemaModel):
    id: str = Field(min_length=1)  # "<category>.<name>", for example "promoter.cmv"
    name: str = Field(min_length=1)
    category: PartCategory
    length_bp: int = Field(gt=0)
    sequence: str
    host_compatibility: list[str] = Field(min_length=1)
    tissue_specificity: str | None = None
    source: str = Field(min_length=1)
    notes: str
    citation: str = Field(min_length=1)
    provenance: PartProvenance

    @field_validator("sequence", mode="before")
    @classmethod
    def validate_sequence(cls, value: Any) -> str:
        return normalize_dna(value)

    @field_validator("tissue_specificity")
    @classmethod
    def known_tissue(cls, value: str | None) -> str | None:
        if value is not None and value not in TISSUE_SPECIFICITY_VALUES:
            raise ValueError(f"tissue_specificity {value!r} is not one of {sorted(TISSUE_SPECIFICITY_VALUES)}")
        return value

    @model_validator(mode="after")
    def consistent(self) -> PartRecord:
        if self.length_bp != len(self.sequence):
            raise ValueError(f"length_bp {self.length_bp} does not match the sequence length {len(self.sequence)}")
        if not self.id.startswith(f"{PartCategory(self.category).value}."):
            raise ValueError(f"id {self.id!r} must start with its category {PartCategory(self.category).value!r}")
        start, end = self.provenance.coordinates
        if end - start + 1 != len(self.sequence):
            raise ValueError("provenance coordinates do not span the sequence length")
        if self.tissue_specificity is not None and PartCategory(self.category) is not PartCategory.PROMOTER:
            raise ValueError("only promoters carry a tissue_specificity")
        return self


def load_part_file(path: Path) -> PartRecord:
    """Load and validate one part JSON file; the file location must agree with the record."""
    record = PartRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
    expected_id = f"{path.parent.name}.{path.stem}"
    if record.id != expected_id:
        raise ValueError(f"{path}: id {record.id!r} must equal {expected_id!r}")
    if PartCategory(record.category).value != path.parent.name:
        raise ValueError(f"{path}: category {record.category!r} does not match directory {path.parent.name!r}")
    return record


def load_part_registry(parts_dir: Path | str | None = None) -> dict[str, PartRecord]:
    """Load every part under `parts_dir` (default: data/parts), keyed by part id.

    Raises on the first invalid record or on a duplicate id. The result is
    ordered by category then id so iteration is deterministic.
    """
    root = Path(parts_dir) if parts_dir is not None else DEFAULT_PARTS_DIR
    if not root.is_dir():
        raise FileNotFoundError(f"part registry directory not found: {root}")
    registry: dict[str, PartRecord] = {}
    for path in sorted(root.glob("*/*.json")):
        record = load_part_file(path)
        if record.id in registry:
            raise ValueError(f"duplicate part id {record.id!r}")
        registry[record.id] = record
    return registry


@lru_cache(maxsize=1)
def _default_registry() -> dict[str, PartRecord]:
    return load_part_registry()


def get_part(part_id: str) -> PartRecord:
    """Return a part from the default registry, raising KeyError with the known ids if absent."""
    registry = _default_registry()
    if part_id not in registry:
        raise KeyError(f"unknown part id {part_id!r} (known: {', '.join(sorted(registry))})")
    return registry[part_id]


def list_parts(category: PartCategory | str | None = None) -> list[PartRecord]:
    """Parts in the default registry, optionally restricted to one category, ordered by id."""
    parts = sorted(_default_registry().values(), key=lambda part: part.id)
    if category is None:
        return parts
    wanted = PartCategory(category)
    return [part for part in parts if PartCategory(part.category) is wanted]
