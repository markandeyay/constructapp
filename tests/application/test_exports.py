from __future__ import annotations

import pytest

from packages.application.exports import export_annotated_sequence, read_annotated_sequence
from packages.core.schemas import AnnotatedFeature, AnnotatedSequence


def example_annotated_sequence() -> AnnotatedSequence:
    return AnnotatedSequence(
        sequence="ATGCGTACGTTAGCGATCGATCGTACGTAGCTAGCTAGCA",
        topology="circular",
        features=[
            AnnotatedFeature(type="promoter", start=0, end=6, strand=1, name="P_lac", confidence=0.95),
            AnnotatedFeature(type="marker", start=8, end=20, strand=-1, name="AmpR", confidence=0.91),
            AnnotatedFeature(type="MCS", start=22, end=32, strand=0, name="MCS", confidence=0.55),
        ],
        vector_profile="bacterial_cloning_vector",
        annotation_complete=True,
    )


def feature_signature(sequence: AnnotatedSequence) -> list[tuple[str, int, int, int, str, float]]:
    return [
        (str(feature.type), feature.start, feature.end, feature.strand, feature.name, feature.confidence)
        for feature in sequence.features
    ]


def test_export_annotated_sequence_rejects_unknown_format() -> None:
    with pytest.raises(ValueError, match="unsupported export format"):
        export_annotated_sequence(example_annotated_sequence(), format="embl")


def test_genbank_roundtrip_preserves_sequence_topology_and_features() -> None:
    annotated = example_annotated_sequence()

    payload = export_annotated_sequence(annotated, format="genbank")
    restored = read_annotated_sequence(payload, format="genbank")

    assert "LOCUS" in payload
    assert "FEATURES" in payload
    assert "complement(9..20)" in payload
    assert restored.sequence == annotated.sequence
    assert restored.topology == annotated.topology
    assert restored.vector_profile == annotated.vector_profile
    assert restored.annotation_complete is annotated.annotation_complete
    assert feature_signature(restored) == feature_signature(annotated)


def test_fasta_roundtrip_preserves_sequence_and_topology_metadata() -> None:
    annotated = example_annotated_sequence()

    payload = export_annotated_sequence(annotated, format="fasta")
    restored = read_annotated_sequence(payload, format="fasta")

    assert payload.startswith(">annotated_sequence ")
    assert "construct_meta=" in payload
    assert restored.sequence == annotated.sequence
    assert restored.topology == annotated.topology
    assert restored.vector_profile == annotated.vector_profile
    assert restored.annotation_complete is annotated.annotation_complete
    assert restored.features == []
