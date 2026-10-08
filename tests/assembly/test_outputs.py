"""The section 7.7 outputs: order table, protocol, junction map.

Source: section 7.7 of the engine capability system design. The two requirements
with teeth are tested directly: the order table must be copy-pasteable and
CSV-exportable, and the annealing temperature must be derived from the computed
Tm rather than assumed.
"""

from __future__ import annotations

import csv
import io

import pytest

from packages.core.sequence.tm import melting_temperature
from packages.generation.assembly.designer import compose
from packages.generation.assembly.outputs import (
    ORDER_TABLE_COLUMNS,
    annealing_temperature,
    build_outputs,
    order_table,
    order_table_csv,
    order_table_text,
    protocol,
)
from packages.validation.assembly import constants
from packages.validation.assembly.settings import settings_for
from packages.validation.assembly.validator import AssemblyValidator
from tests.assembly.fixtures import clean_golden_gate_request, clean_request

VALIDATOR = AssemblyValidator()


def outputs_for(request):
    design = compose(request)
    return design, build_outputs(design, VALIDATOR.validate(design))


# ---------------------------------------------------------------------------
# The order table
# ---------------------------------------------------------------------------


def test_the_order_table_has_the_section_7_7_columns() -> None:
    """Section 7.7: primer name, sequence 5' to 3', length, Tm, GC%, notes."""
    assert ORDER_TABLE_COLUMNS == (
        "Primer name",
        "Sequence (5' to 3')",
        "Length (nt)",
        "Tm (C)",
        "GC (%)",
        "Notes",
    )


def test_the_order_table_has_one_row_per_primer_with_the_orderable_sequence() -> None:
    design, out = outputs_for(clean_request())
    assert len(out.order_table) == len(design.primers)
    for row, primer in zip(out.order_table, design.primers, strict=True):
        assert row.name == primer.name
        # What gets ordered is the whole oligo, tail included.
        assert row.sequence_5_to_3 == primer.tail + primer.binding
        assert row.length_nt == primer.length_nt
        assert 0 <= row.gc_percent <= 100


def test_the_order_table_tm_is_the_binding_region_tm_and_says_so() -> None:
    """Two numbers were possible, so the table states which one it reports."""
    design, out = outputs_for(clean_request())
    for row, primer in zip(out.order_table, design.primers, strict=True):
        expected = melting_temperature(
            primer.binding,
            primer_conc_nm=design.request.primer_conc_nm,
            monovalent_salt_mm=design.request.monovalent_salt_mm,
            divalent_salt_mm=design.request.divalent_salt_mm,
            dntp_mm=design.request.dntp_mm,
        )
        assert row.tm_c == pytest.approx(round(expected, 1))
        if primer.tail:
            assert "binding region" in row.notes


def test_the_order_table_exports_as_parseable_csv() -> None:
    """Section 7.7: "it must be copy-pasteable and CSV-exportable"."""
    _, out = outputs_for(clean_golden_gate_request())
    rows = list(csv.reader(io.StringIO(out.order_table_csv)))
    assert rows[0] == list(ORDER_TABLE_COLUMNS)
    assert len(rows) == len(out.order_table) + 1
    for parsed, row in zip(rows[1:], out.order_table, strict=True):
        assert parsed[0] == row.name
        assert parsed[1] == row.sequence_5_to_3
        assert int(parsed[2]) == row.length_nt
        assert float(parsed[3]) == pytest.approx(row.tm_c)


def test_csv_survives_a_note_containing_a_comma() -> None:
    """Written with the csv module, so a note cannot corrupt the file."""
    design = compose(clean_request())
    noted = design.primers[0].model_copy(update={"notes": ["one, two", 'a "quoted" note']})
    design = design.model_copy(update={"primers": [noted, *design.primers[1:]]})
    rows = order_table(design)
    parsed = list(csv.reader(io.StringIO(order_table_csv(rows))))
    assert len(parsed) == len(rows) + 1
    assert "one, two" in parsed[1][-1]


def test_the_order_table_renders_as_aligned_text() -> None:
    _, out = outputs_for(clean_request())
    text = order_table_text(out.order_table)
    lines = text.splitlines()
    assert lines[0].startswith("Primer name")
    assert set(lines[1]) <= {"-", " "}
    assert len(lines) == len(out.order_table) + 2
    for row in out.order_table:
        assert any(row.sequence_5_to_3 in line for line in lines[2:])


# ---------------------------------------------------------------------------
# The protocol
# ---------------------------------------------------------------------------


def test_the_annealing_temperature_is_derived_from_the_computed_tm() -> None:
    """Section 7.7's hard requirement: derived, not assumed."""
    request = clean_request()
    design = compose(request)
    settings = settings_for(request)
    value, rule = annealing_temperature(design, settings)

    lowest = min(
        melting_temperature(
            primer.binding,
            primer_conc_nm=request.primer_conc_nm,
            monovalent_salt_mm=request.monovalent_salt_mm,
            divalent_salt_mm=request.divalent_salt_mm,
            dntp_mm=request.dntp_mm,
        )
        for primer in design.primers
    )
    expected = min(
        max(lowest - settings.annealing_offset_below_min_tm_c, settings.annealing_min_c),
        settings.annealing_max_c,
    )
    assert value == pytest.approx(round(expected, 1))
    assert f"{lowest:.1f} C" in rule
    assert "nearest-neighbor" in rule


def test_the_annealing_temperature_moves_with_the_target_tm() -> None:
    """If it were assumed rather than derived, it would not move."""
    cool = compose(clean_request(target_tm_c=52.0))
    warm = compose(clean_request(target_tm_c=68.0))
    cool_value, _ = annealing_temperature(cool, settings_for(cool.request))
    warm_value, _ = annealing_temperature(warm, settings_for(warm.request))
    assert warm_value > cool_value


def test_the_annealing_temperature_is_clamped_to_the_polymerase_range() -> None:
    """A pathological Tm must not produce an impossible thermocycler step."""
    request = clean_request(target_tm_c=20.0, monovalent_salt_mm=1.0)
    design = compose(request)
    settings = settings_for(request)
    value, rule = annealing_temperature(design, settings)
    assert settings.annealing_min_c <= value <= settings.annealing_max_c
    if value == settings.annealing_min_c:
        assert "clamped" in rule


def test_the_pcr_program_uses_the_derived_annealing_temperature() -> None:
    design, out = outputs_for(clean_request())
    anneal = next(step for step in out.protocol.pcr_program if "Anneal" in step.label)
    assert anneal.temperature_c == out.protocol.annealing_temperature_c
    assert "derived from the computed Tm" in anneal.label


def test_the_pcr_program_extension_time_follows_the_amplicon_length() -> None:
    design, out = outputs_for(clean_request())
    longest = max(amplicon.length_bp for amplicon in design.amplicons)
    extend = next(step for step in out.protocol.pcr_program if step.label.startswith("Extend"))
    assert extend.temperature_c == constants.PCR_EXTENSION_C
    assert str(longest) in extend.label
    assert extend.seconds >= 1


@pytest.mark.parametrize(
    ("strategy", "expected_label"),
    [("gibson", "NEBuilder HiFi"), ("golden_gate", "Digest"), ("pcr_cloning", "Restriction digest")],
)
def test_each_strategy_gets_its_own_assembly_program(strategy: str, expected_label: str) -> None:
    request = clean_golden_gate_request() if strategy == "golden_gate" else clean_request(strategy=strategy)
    _, out = outputs_for(request)
    assert out.protocol.strategy == strategy
    assert any(expected_label in step.label for step in out.protocol.assembly_program)


def test_the_golden_gate_program_cycles_digestion_and_ligation() -> None:
    _, out = outputs_for(clean_golden_gate_request())
    labels = [step.label for step in out.protocol.assembly_program]
    assert labels == ["Digest", "Ligate", "Final digest"]
    digest, ligate, final = out.protocol.assembly_program
    assert digest.temperature_c == constants.GOLDEN_GATE_DIGEST_C
    assert ligate.temperature_c == constants.GOLDEN_GATE_LIGATE_C
    assert final.temperature_c == constants.GOLDEN_GATE_FINAL_DIGEST_C
    assert digest.cycles == ligate.cycles == constants.GOLDEN_GATE_CYCLES


def test_the_protocol_names_its_sources_and_the_lot_caveat() -> None:
    """A protocol number with no source is not usable at a bench."""
    _, out = outputs_for(clean_request())
    joined = " ".join(out.protocol.sources)
    assert "NEB Q5" in joined
    assert "Gibson et al. 2009" in joined
    assert "SantaLucia" in joined
    assert any("lot insert" in line for line in out.protocol.reaction_composition)


def test_the_protocol_states_the_expected_outcome_with_sizes() -> None:
    design, out = outputs_for(clean_request())
    for amplicon in design.amplicons:
        assert str(amplicon.length_bp) in out.protocol.expected_outcome


def test_an_empty_primer_set_cannot_produce_a_protocol() -> None:
    """Section 3.3 constraint 4: refuse rather than invent an annealing temperature."""
    design = compose(clean_request()).model_copy(update={"primers": []})
    with pytest.raises(ValueError, match="at least one primer"):
        protocol(design)


# ---------------------------------------------------------------------------
# The junction map
# ---------------------------------------------------------------------------


def test_the_gibson_junction_map_labels_the_homology_arms() -> None:
    design, out = outputs_for(clean_request())
    assert len(out.junction_map) == len(design.junctions)
    for entry in out.junction_map:
        assert "homology arm" in entry.label
        assert "Overlap Tm" in entry.detail
        assert entry.length_bp == len(entry.sequence)


def test_the_golden_gate_junction_map_labels_the_overhangs_and_their_origin() -> None:
    design, out = outputs_for(clean_golden_gate_request())
    for entry in out.junction_map:
        assert "overhang" in entry.label
        assert "scarless" in entry.detail
        assert "complementary overhang" in entry.detail


def test_the_junction_map_text_shows_the_order_and_every_junction() -> None:
    design, out = outputs_for(clean_golden_gate_request())
    text = out.junction_map_text
    assert "Assembly order:" in text
    for name in design.fragment_order:
        assert name in text
    for entry in out.junction_map:
        assert entry.sequence in text


def test_a_design_with_no_junctions_says_so_rather_than_rendering_an_empty_map() -> None:
    _, out = outputs_for(clean_request(strategy="pcr_cloning"))
    assert out.junction_map == []
    assert "No junctions" in out.junction_map_text


# ---------------------------------------------------------------------------
# The bundle
# ---------------------------------------------------------------------------


def test_build_outputs_carries_every_section_7_7_artifact() -> None:
    design, out = outputs_for(clean_golden_gate_request())
    assert out.order_table and out.order_table_csv
    assert out.protocol is not None
    assert out.junction_map
    assert out.domestication is design.domestication
    assert out.report.capability.value == "assembly"
    assert out.capability.value == "assembly"


def test_outputs_are_deterministic() -> None:
    """Section 3.3 constraint 3."""
    first_design, first = outputs_for(clean_golden_gate_request())
    second_design, second = outputs_for(clean_golden_gate_request())
    assert first.order_table_csv == second.order_table_csv
    assert first.protocol.annealing_temperature_c == second.protocol.annealing_temperature_c
    assert first.junction_map_text == second.junction_map_text
    assert first_design.primers == second_design.primers
