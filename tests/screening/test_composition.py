"""The section 11.1 item 2 registry-only composition assertion."""

from __future__ import annotations

from packages.application.screening import (
    AssertionVerdict,
    AttributedSegment,
    AttributedSequence,
    ExportSubject,
    SequenceOrigin,
    assert_registry_only_composition,
)
from packages.core.schemas.capability import CapabilityKind
from tests.screening.support import (
    FAKE_PARTS,
    POLYA_ID,
    PROMOTER_ID,
    attributed_subject,
)


def test_a_curated_composition_is_satisfied_and_lists_what_it_used() -> None:
    result = assert_registry_only_composition(attributed_subject(), parts=FAKE_PARTS)
    assert result.verdict is AssertionVerdict.SATISFIED
    assert result.permits_export is True
    assert sorted(result.registry_parts_used) == sorted([PROMOTER_ID, POLYA_ID])
    assert result.user_inputs_used == ["user_input:transgene_sequence"]
    assert result.violations == []
    assert "No element was synthesized de novo" in result.reason


def test_a_part_id_outside_the_registry_is_a_violation() -> None:
    subject = attributed_subject()
    original = subject.sequences[0]
    first = original.segments[0].model_copy(
        update={"part_id": "promoter.invented", "source": "part:promoter.invented"}
    )
    changed = subject.model_copy(
        update={
            "sequences": [original.model_copy(update={"segments": [first, *original.segments[1:]]})]
        }
    )
    result = assert_registry_only_composition(changed, parts=FAKE_PARTS)
    assert result.verdict is AssertionVerdict.VIOLATED
    assert result.permits_export is False
    assert any("promoter.invented" in violation for violation in result.violations)


def test_a_modified_curated_element_is_a_violation() -> None:
    subject = attributed_subject()
    original = subject.sequences[0]
    mutated = original.sequence[:5] + "T" + original.sequence[6:]
    changed = subject.model_copy(
        update={"sequences": [original.model_copy(update={"sequence": mutated})]}
    )
    result = assert_registry_only_composition(changed, parts=FAKE_PARTS)
    assert result.verdict is AssertionVerdict.VIOLATED
    assert any("novel element" in violation for violation in result.violations)


def test_a_rule_derived_element_is_recorded_with_its_rule() -> None:
    sequence = "GGTCTC"
    rule = "Appendix D BsaI recognition sequence GGTCTC, cut notation GGTCTC(1/5)"
    subject = ExportSubject(
        capability=CapabilityKind.ASSEMBLY,
        design_id="rule-only",
        validator_version="v1",
        sequences=[
            AttributedSequence(
                name="primer:test_F",
                sequence=sequence,
                segments=[
                    AttributedSegment(
                        start=0,
                        end=len(sequence),
                        origin=SequenceOrigin.PUBLISHED_RULE,
                        source="enzyme:BsaI:Appendix D GGTCTC(1/5)",
                        rule=rule,
                    )
                ],
            )
        ],
        declared_provenance=["enzyme:BsaI:Appendix D GGTCTC(1/5)"],
        adapter="tests.screening.test_composition",
    )
    result = assert_registry_only_composition(subject, parts=FAKE_PARTS)
    assert result.verdict is AssertionVerdict.SATISFIED
    assert result.rules_used == [rule]
    assert result.registry_parts_used == []


def test_a_subject_with_no_sequence_is_unknown_not_a_pass() -> None:
    subject = attributed_subject().model_copy(update={"sequences": []})
    result = assert_registry_only_composition(subject, parts=FAKE_PARTS)
    assert result.verdict is AssertionVerdict.UNKNOWN
    assert result.permits_export is False


def test_a_registry_that_cannot_be_loaded_is_unknown_not_a_pass(monkeypatch) -> None:
    import packages.application.screening.composition as module

    def boom() -> dict[str, object]:
        raise OSError("data/parts is not readable")

    monkeypatch.setattr(module, "load_part_registry", boom)
    result = assert_registry_only_composition(attributed_subject())
    assert result.verdict is AssertionVerdict.UNKNOWN
    assert result.permits_export is False


def test_the_assertion_is_deterministic() -> None:
    subject = attributed_subject()
    first = assert_registry_only_composition(subject, parts=FAKE_PARTS)
    second = assert_registry_only_composition(subject, parts=FAKE_PARTS)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
