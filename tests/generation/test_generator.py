from __future__ import annotations

import pytest

from packages.core.schemas import DesignSpec, GeneratedSequence, Plasmid, RetrievedPlasmid
from packages.generation import CARBON_500M_MODEL, CARBON_GENERATOR_VERSION, FAKE_GENERATOR_VERSION, FakeGenerator, MarkerSwap
from packages.generation.generator import CarbonGenerator, carbon_dna_prompt, splice_generated_segment


def _template() -> RetrievedPlasmid:
    plasmid = Plasmid(
        id="curated:pUC19",
        source="curated",
        name="pUC19c",
        sequence="AAAACCCCGGGGTTTT",
        length=16,
        organism="Cloning vector pUC19c",
        vector_type="bacterial_cloning_vector",
        markers=["AmpR"],
        promoters=["lac promoter region"],
        use_cases=["bacterial_cloning"],
        annotation_complete=True,
        raw_ref="raw/curated/pUC19.gb",
    )
    return RetrievedPlasmid(plasmid=plasmid, score=1.0, matched_fields=["semantic", "exact_name"])


def test_fake_generator_returns_top_template_as_schema_valid_candidate() -> None:
    generator = FakeGenerator()
    spec = DesignSpec(organism="Escherichia coli", vector_type="bacterial_cloning_vector")

    generated = generator.generate(spec, [_template()], n=2)

    assert len(generated) == 2
    assert all(isinstance(candidate, GeneratedSequence) for candidate in generated)
    assert all(candidate.model_version == FAKE_GENERATOR_VERSION for candidate in generated)
    assert all(candidate.parent_template_ids == ["curated:pUC19"] for candidate in generated)
    assert all(candidate.annotated_sequence.sequence == _template().plasmid.sequence for candidate in generated)
    assert all(candidate.annotated_sequence.topology == "circular" for candidate in generated)
    assert all(candidate.annotated_sequence.annotation_complete is False for candidate in generated)


def test_fake_generator_applies_explicit_marker_swap_deterministically() -> None:
    generator = FakeGenerator(marker_swap=MarkerSwap(original_sequence="CCCC", replacement_sequence="ATAT"))
    spec = DesignSpec(organism="Escherichia coli", vector_type="bacterial_cloning_vector")

    first = generator.generate(spec, [_template()])
    second = generator.generate(spec, [_template()])

    assert first == second
    assert first[0].annotated_sequence.sequence == "AAAAATATGGGGTTTT"


def test_fake_generator_attributes_the_whole_verbatim_candidate_to_the_template() -> None:
    generator = FakeGenerator()
    spec = DesignSpec(organism="Escherichia coli", vector_type="bacterial_cloning_vector")

    candidate = generator.generate(spec, [_template()])[0]

    assert [span.model_dump() for span in candidate.sequence_spans] == [
        {
            "start": 0,
            "end": 16,
            "source": "retrieved_template:curated:pUC19",
            "source_id": "curated:pUC19",
            "source_start": 0,
            "source_end": 16,
        }
    ]


def test_fake_generator_leaves_swapped_bases_unattributed() -> None:
    # The replacement is deliberately shorter than the original so that candidate
    # and template coordinates diverge after the swap: a span pair that is only
    # right for an equal-length replacement would pass unnoticed otherwise.
    generator = FakeGenerator(marker_swap=MarkerSwap(original_sequence="CCCC", replacement_sequence="AT"))
    spec = DesignSpec(organism="Escherichia coli", vector_type="bacterial_cloning_vector")

    candidate = generator.generate(spec, [_template()])[0]

    assert candidate.annotated_sequence.sequence == "AAAAATGGGGTTTT"
    assert [(span.start, span.end, span.source_start, span.source_end) for span in candidate.sequence_spans] == [
        (0, 4, 0, 4),
        (6, 14, 8, 16),
    ]
    assert all(span.source == "retrieved_template:curated:pUC19" for span in candidate.sequence_spans)
    # Candidate bases 4 and 5 are the replacement, and no span may claim them.
    covered = {position for span in candidate.sequence_spans for position in range(span.start, span.end)}
    assert covered == set(range(0, 4)) | set(range(6, 14))


def test_fake_generator_omits_empty_flank_spans_for_edge_swaps() -> None:
    spec = DesignSpec(organism="Escherichia coli", vector_type="bacterial_cloning_vector")

    leading = FakeGenerator(marker_swap=MarkerSwap(original_sequence="AAAA", replacement_sequence="TT"))
    trailing = FakeGenerator(marker_swap=MarkerSwap(original_sequence="TTTT", replacement_sequence="AA"))

    leading_candidate = leading.generate(spec, [_template()])[0]
    trailing_candidate = trailing.generate(spec, [_template()])[0]

    assert [(span.start, span.end, span.source_start, span.source_end) for span in leading_candidate.sequence_spans] == [
        (2, 14, 4, 16)
    ]
    assert [(span.start, span.end, span.source_start, span.source_end) for span in trailing_candidate.sequence_spans] == [
        (0, 12, 0, 12)
    ]


def test_marker_swap_apply_with_offset_reports_the_match_index() -> None:
    swap = MarkerSwap(original_sequence="CCCC", replacement_sequence="AT")

    swapped, match_index = swap.apply_with_offset("AAAACCCCGGGGTTTT")

    assert (swapped, match_index) == ("AAAAATGGGGTTTT", 4)
    assert swap.apply("AAAACCCCGGGGTTTT") == swapped
    with pytest.raises(ValueError, match="exactly one"):
        swap.apply_with_offset("AAAACCCCGGGGCCCC")


def test_carbon_generator_attributes_only_the_kept_template_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CarbonGenerator, "_generate_segment", lambda self, tokenizer, model, prompt: "ATAT")
    generator = CarbonGenerator(tokenizer=object(), model=object(), prompt_bases=6)
    spec = DesignSpec(organism="Escherichia coli")

    candidate = generator.generate(spec, [_template()])[0]

    assert candidate.annotated_sequence.sequence == "AAAACCCCGGGGATAT"
    # The four sampled bases are the model's own, so the span stops at base 12.
    assert [(span.start, span.end, span.source_start, span.source_end) for span in candidate.sequence_spans] == [
        (0, 12, 0, 12)
    ]
    assert candidate.sequence_spans[0].source_id == "curated:pUC19"


def test_carbon_generator_records_no_spans_when_the_splice_keeps_no_template(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CarbonGenerator, "_generate_segment", lambda self, tokenizer, model, prompt: "ACGT" * 8)
    generator = CarbonGenerator(tokenizer=object(), model=object(), prompt_bases=6)
    spec = DesignSpec(organism="Escherichia coli")

    candidate = generator.generate(spec, [_template()])[0]

    assert candidate.annotated_sequence.sequence == "ACGT" * 4
    assert candidate.sequence_spans == []


def test_fake_generator_returns_empty_without_templates_and_rejects_invalid_n() -> None:
    generator = FakeGenerator()
    spec = DesignSpec(organism="Escherichia coli")

    assert generator.generate(spec, []) == []
    with pytest.raises(ValueError, match="n must be positive"):
        generator.generate(spec, [_template()], n=0)


def test_marker_swap_requires_one_exact_original_sequence_match() -> None:
    generator = FakeGenerator(marker_swap=MarkerSwap(original_sequence="ACAC", replacement_sequence="ATAT"))
    spec = DesignSpec(organism="Escherichia coli", vector_type="bacterial_cloning_vector")

    with pytest.raises(ValueError, match="exactly one"):
        generator.generate(spec, [_template()])


def test_carbon_prompt_uses_dna_prefix_aligned_to_sixmers() -> None:
    prompt = carbon_dna_prompt("acgt" * 20, prompt_bases=50)

    assert prompt.startswith("<dna>")
    dna = prompt.removeprefix("<dna>")
    assert len(dna) == 48
    assert set(dna) == {"A", "C", "G", "T"}


def test_carbon_splice_replaces_template_suffix_with_generated_segment() -> None:
    assert splice_generated_segment("AAAACCCCGGGGTTTT", "atat") == "AAAACCCCGGGGATAT"


def test_carbon_generator_constants_are_explicit_spike_metadata() -> None:
    assert CARBON_500M_MODEL == "HuggingFaceBio/Carbon-500M"
    assert CARBON_GENERATOR_VERSION == "carbon-500m-cpu-spike-v1"
