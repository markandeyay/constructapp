from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from packages.core.part_registry import (
    DEFAULT_PARTS_DIR,
    PartCategory,
    PartRecord,
    get_part,
    list_parts,
    load_part_registry,
)
from packages.core.sequence import global_identity, reverse_complement

PROVENANCE = (DEFAULT_PARTS_DIR / "PROVENANCE.md").read_text(encoding="utf-8")
EM_DASH = chr(0x2014)

# The files named in section 4.3. Each must be shipped or be named in PROVENANCE.md as not shipped.
SPEC_LAYOUT = [
    "itr.aav2_itr_left",
    "itr.aav2_itr_right",
    "promoter.cmv",
    "promoter.cag",
    "promoter.ef1a",
    "promoter.efs",
    "promoter.hsyn1",
    "promoter.cbh",
    "polya.bgh",
    "polya.sv40",
    "polya.synthetic_short",
    "enhancer.wpre",
    "intron.chimeric",
]


@pytest.fixture(scope="module")
def registry() -> dict[str, PartRecord]:
    return load_part_registry()


def test_registry_loads_and_is_not_empty(registry: dict[str, PartRecord]) -> None:
    assert registry


def test_every_spec_layout_part_is_shipped_or_declared_omitted(registry: dict[str, PartRecord]) -> None:
    omitted_section = PROVENANCE.split("## Parts attempted and not shipped", 1)[1]
    for part_id in SPEC_LAYOUT:
        assert part_id in registry or part_id in omitted_section, part_id


def test_required_itrs_are_present(registry: dict[str, PartRecord]) -> None:
    assert "itr.aav2_itr_left" in registry and "itr.aav2_itr_right" in registry


def test_sequences_are_real_dna_with_matching_lengths(registry: dict[str, PartRecord]) -> None:
    for part in registry.values():
        assert re.fullmatch("[ACGT]+", part.sequence), part.id
        assert part.length_bp == len(part.sequence), part.id
        assert set(part.sequence) == set("ACGT"), f"{part.id} lacks one of the four bases, likely a placeholder"


def test_no_two_parts_share_a_sequence(registry: dict[str, PartRecord]) -> None:
    sequences = [part.sequence for part in registry.values()]
    assert len(set(sequences)) == len(sequences)


def test_every_part_carries_source_citation_and_provenance(registry: dict[str, PartRecord]) -> None:
    for part in registry.values():
        assert part.source.strip() and part.citation.strip() and part.notes.strip(), part.id
        accession = part.provenance.accession
        assert accession in part.source, part.id
        assert re.fullmatch(r"[A-Z]{1,2}_?\d+\.\d+", accession), part.id
        start, end = part.provenance.coordinates
        assert end - start + 1 == part.length_bp


def test_promoter_tissue_vocabulary_matches_the_request_schema(registry: dict[str, PartRecord]) -> None:
    for part in registry.values():
        if part.category == PartCategory.PROMOTER.value:
            assert part.tissue_specificity is not None, part.id
        else:
            assert part.tissue_specificity is None, part.id
    assert get_part("promoter.hsyn1").tissue_specificity == "cns_neuron"


def test_itrs_are_inverted_not_tandem(registry: dict[str, PartRecord]) -> None:
    left = registry["itr.aav2_itr_left"].sequence
    right = registry["itr.aav2_itr_right"].sequence
    assert len(left) == len(right) == 145
    assert global_identity(left, reverse_complement(right)) > global_identity(left, right)


def test_every_part_is_listed_in_provenance_with_its_coordinates_and_length(registry: dict[str, PartRecord]) -> None:
    for part in registry.values():
        rows = [line for line in PROVENANCE.splitlines() if line.startswith(f"| {part.id} |")]
        assert len(rows) >= 1, part.id
        row = rows[0]
        start, end = part.provenance.coordinates
        assert part.provenance.accession in row, part.id
        assert f"{start}..{end}" in row, part.id
        assert f"| {part.length_bp} |" in row, part.id
        assert part.provenance.retrieved_on in row, part.id


def test_data_files_contain_no_em_dash() -> None:
    for path in DEFAULT_PARTS_DIR.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".md", ".py"}:
            assert EM_DASH not in path.read_text(encoding="utf-8"), path


def test_list_parts_and_get_part() -> None:
    assert {part.id for part in list_parts("itr")} == {"itr.aav2_itr_left", "itr.aav2_itr_right"}
    assert all(part.category == "promoter" for part in list_parts(PartCategory.PROMOTER))
    with pytest.raises(KeyError, match="unknown part id"):
        get_part("promoter.does_not_exist")


def write_part(root: Path, record: dict, category: str = "promoter", stem: str = "x") -> None:
    directory = root / category
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.json").write_text(json.dumps(record), encoding="utf-8")


def valid_record() -> dict:
    return json.loads((DEFAULT_PARTS_DIR / "promoter" / "efs.json").read_text(encoding="utf-8")) | {"id": "promoter.x"}


def test_loader_accepts_a_valid_record(tmp_path: Path) -> None:
    write_part(tmp_path, valid_record())
    assert list(load_part_registry(tmp_path)) == ["promoter.x"]


@pytest.mark.parametrize(
    "mutation",
    [
        {"sequence": "ACGTN" * 20},
        {"sequence": "ACGT" * 5},  # length_bp no longer matches
        {"sequence": ""},
        {"id": "promoter.other"},  # id does not match the file name
        {"id": "polya.x"},  # id does not match the category
        {"source": ""},
        {"citation": ""},
        {"tissue_specificity": "everywhere"},
        {"length_bp": 0},
    ],
)
def test_loader_rejects_unsafe_records(tmp_path: Path, mutation: dict) -> None:
    write_part(tmp_path, valid_record() | mutation)
    with pytest.raises(ValueError):
        load_part_registry(tmp_path)


def test_loader_rejects_a_record_missing_provenance(tmp_path: Path) -> None:
    record = valid_record()
    del record["provenance"]
    write_part(tmp_path, record)
    with pytest.raises(ValueError):
        load_part_registry(tmp_path)


def test_loader_rejects_a_non_promoter_with_tissue_specificity(tmp_path: Path) -> None:
    record = valid_record() | {"id": "polya.x", "category": "polya"}
    write_part(tmp_path, record, category="polya")
    with pytest.raises(ValueError):
        load_part_registry(tmp_path)


def test_missing_directory_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_part_registry(tmp_path / "absent")


@pytest.mark.skipif(os.environ.get("CONSTRUCT_VERIFY_PARTS") != "1", reason="needs network access to NCBI")
def test_registry_matches_genbank() -> None:
    result = subprocess.run(
        [sys.executable, str(DEFAULT_PARTS_DIR / "build_parts.py"), "--verify"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
