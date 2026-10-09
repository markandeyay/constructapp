from __future__ import annotations

from pathlib import Path

from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from packages.data_pipeline.parse.sequence_parser import normalize_feature_type, parse_genbank_text, parse_seqrecord


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "parser"


def feature_by_type(annotated, feature_type: str):  # type: ignore[no-untyped-def]
    return [feature for feature in annotated.features if str(feature.type) == feature_type]


def record_with_features(features: list[SeqFeature]) -> SeqRecord:
    record = SeqRecord(Seq("A" * 1000), id="synthetic", description="synthetic construct")
    record.annotations["topology"] = "circular"
    record.features = features
    return record


def test_puc19_trusted_annotations_detect_expected_components() -> None:
    annotated = parse_genbank_text((FIXTURES / "puc19.gb").read_text(encoding="utf-8"))

    promoter = feature_by_type(annotated, "promoter")[0]
    mcs = feature_by_type(annotated, "MCS")[0]
    ori = feature_by_type(annotated, "ORI")[0]
    marker = feature_by_type(annotated, "marker")[0]

    assert (promoter.start, promoter.end, promoter.name) == (237, 395, "lac promoter")
    assert (mcs.start, mcs.end, mcs.name) == (395, 452, "pUC19 MCS")
    assert (ori.start, ori.end, ori.name) == (866, 1455, "pMB1/pUC origin")
    assert (marker.start, marker.end, marker.name) == (1628, 2417, "bla")
    assert all(feature.confidence == 0.95 for feature in [promoter, mcs, ori, marker])
    assert annotated.vector_profile == "bacterial_cloning_vector"
    assert annotated.annotation_complete is True


def test_reference_matching_finds_unannotated_puc19_components() -> None:
    from Bio import SeqIO

    record = SeqIO.read(FIXTURES / "puc19.gb", "genbank")
    record.features = [record.features[0]]
    annotated = parse_seqrecord(record)

    assert any(feature.name == "pUC19 MCS" and feature.start == 395 for feature in annotated.features)
    assert any(feature.name == "AmpR/bla" and feature.start == 1628 for feature in annotated.features)
    assert any(feature.name == "pMB1/pUC origin" and feature.start == 866 for feature in annotated.features)


def test_motif_heuristic_flags_restriction_site_dense_mcs_candidate() -> None:
    from Bio.Seq import Seq
    from Bio.SeqRecord import SeqRecord

    sequence = "A" * 120 + "GAATTCAAGCTTGGATCCCTGCAGGTCGACTCTAGACCCGGG" + "A" * 120
    record = SeqRecord(Seq(sequence), id="motif", description="motif-only")
    record.annotations["topology"] = "circular"

    annotated = parse_seqrecord(record)

    mcs_features = feature_by_type(annotated, "MCS")
    assert len(mcs_features) == 1
    assert 100 <= mcs_features[0].start <= 130
    assert mcs_features[0].confidence == 0.55


def test_annotation_normalization_does_not_match_short_aliases_inside_words() -> None:
    origin_like = SeqFeature(
        FeatureLocation(0, 10),
        type="misc_feature",
        qualifiers={"note": ["xpmb1x maintenance protein"]},
    )
    mcs_like = SeqFeature(
        FeatureLocation(0, 10),
        type="misc_feature",
        qualifiers={"note": ["xmcsx binding protein"]},
    )

    assert normalize_feature_type(origin_like) is None
    assert normalize_feature_type(mcs_like) is None


def test_annotation_normalization_preserves_high_impact_other_features() -> None:
    features = [
        SeqFeature(FeatureLocation(10, 60), type="repeat_region", qualifiers={"note": ["5' LTR"]}),
        SeqFeature(FeatureLocation(100, 150), type="misc_feature", qualifiers={"note": ["WPRE"]}),
        SeqFeature(FeatureLocation(200, 250), type="misc_RNA", qualifiers={"note": ["sgRNA scaffold"]}),
        SeqFeature(FeatureLocation(300, 350), type="misc_feature", qualifiers={"note": ["EMCV IRES"]}),
        SeqFeature(FeatureLocation(400, 430), type="misc_feature", qualifiers={"note": ["P2A self-cleaving peptide"]}),
        SeqFeature(FeatureLocation(500, 510), type="regulatory", qualifiers={"note": ["ribosome binding site"]}),
        SeqFeature(FeatureLocation(520, 530), type="regulatory", qualifiers={"note": ["lac operator"]}),
    ]

    annotated = parse_seqrecord(record_with_features(features))

    other_names = {feature.name for feature in feature_by_type(annotated, "other")}
    assert {
        "5' LTR",
        "WPRE",
        "sgRNA scaffold",
        "EMCV IRES",
        "P2A self-cleaving peptide",
        "ribosome binding site",
        "lac operator",
    } <= other_names


def test_real_feature_ltr_plus_wpre_classifies_as_viral_transfer_vector() -> None:
    features = [
        SeqFeature(FeatureLocation(10, 60), type="repeat_region", qualifiers={"note": ["5' LTR"]}),
        SeqFeature(FeatureLocation(100, 150), type="misc_feature", qualifiers={"note": ["WPRE"]}),
    ]

    annotated = parse_seqrecord(record_with_features(features))

    assert annotated.vector_profile == "lentiviral_or_retroviral_transfer_vector"
    assert annotated.annotation_complete is False


def test_wpre_alone_is_preserved_but_not_lentiviral() -> None:
    feature = SeqFeature(FeatureLocation(100, 150), type="misc_feature", qualifiers={"note": ["WPRE"]})

    annotated = parse_seqrecord(record_with_features([feature]))

    assert feature_by_type(annotated, "other")[0].name == "WPRE"
    assert annotated.vector_profile == "unknown"


def test_polya_signal_maps_to_terminator() -> None:
    feature = SeqFeature(FeatureLocation(100, 150), type="polyA_signal", qualifiers={"note": ["SV40 polyA signal"]})

    annotated = parse_seqrecord(record_with_features([feature]))

    terminator = feature_by_type(annotated, "terminator")[0]
    assert terminator.name == "SV40 polyA signal"


def test_u6_promoter_alone_does_not_classify_as_crispr() -> None:
    feature = SeqFeature(FeatureLocation(100, 150), type="promoter", qualifiers={"note": ["U6 promoter"]})

    annotated = parse_seqrecord(record_with_features([feature]))

    assert feature_by_type(annotated, "promoter")[0].name == "U6 promoter"
    assert annotated.vector_profile == "unknown"


def test_transferase_names_do_not_emit_ltr_other_feature() -> None:
    feature = SeqFeature(
        FeatureLocation(0, 10),
        type="misc_feature",
        qualifiers={"note": ["alpha-glucosyltransferase family protein"]},
    )

    assert normalize_feature_type(feature) is None


def test_aacc1_marker_alias_normalizes_as_marker() -> None:
    feature = SeqFeature(
        FeatureLocation(0, 10),
        type="CDS",
        qualifiers={"product": ["gentamycin acetyltransferase-3-1 aacC1"]},
    )

    assert normalize_feature_type(feature) == "marker"


def test_kan_and_aminoglycoside_marker_aliases_normalize_as_marker() -> None:
    kan = SeqFeature(
        FeatureLocation(0, 10),
        type="CDS",
        qualifiers={"gene": ["KAN"]},
    )
    aminoglycoside = SeqFeature(
        FeatureLocation(20, 30),
        type="CDS",
        qualifiers={"product": ["aminoglycoside phosphotransferase"]},
    )

    assert normalize_feature_type(kan) == "marker"
    assert normalize_feature_type(aminoglycoside) == "marker"
