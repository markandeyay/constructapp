"""The section 11.1 item 1 sequence provenance assertion."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.application.screening import (
    AssertionVerdict,
    AttributedSegment,
    AttributedSequence,
    ExportSubject,
    SequenceOrigin,
    assert_provenance,
)
from packages.core.schemas.capability import CapabilityKind
from tests.screening.support import (
    FAKE_PARTS,
    POLYA_ID,
    POLYA_SOURCE,
    PROMOTER_ID,
    PROMOTER_SEQUENCE,
    PROMOTER_SOURCE,
    USER_SOURCE,
    attributed_subject,
    subject_with_unattributed_base,
)


def test_fully_attributed_subject_is_attributed() -> None:
    result = assert_provenance(attributed_subject(), parts=FAKE_PARTS)
    assert result.verdict is AssertionVerdict.ATTRIBUTED
    assert result.permits_export is True
    assert result.findings == []
    assert result.bases_attributed == result.bases_checked
    assert result.unattributed_bases == 0


def test_an_unattributable_base_is_unattributed_and_names_the_span() -> None:
    result = assert_provenance(subject_with_unattributed_base(), parts=FAKE_PARTS)
    assert result.verdict is AssertionVerdict.UNATTRIBUTED
    assert result.permits_export is False
    gaps = [finding for finding in result.findings if finding.kind == "unattributed_span"]
    assert len(gaps) == 1
    assert (gaps[0].start, gaps[0].end) == (len(PROMOTER_SEQUENCE), len(PROMOTER_SEQUENCE) + 10)
    assert gaps[0].bases == "GGGGGGGGGG"
    assert result.unattributed_bases == 10


def test_a_gap_at_the_end_of_a_sequence_is_found_too() -> None:
    subject = attributed_subject()
    original = subject.sequences[0]
    extended = original.model_copy(update={"sequence": original.sequence + "ACGTACGT"})
    result = assert_provenance(
        subject.model_copy(update={"sequences": [extended]}), parts=FAKE_PARTS
    )
    assert result.verdict is AssertionVerdict.UNATTRIBUTED
    gap = next(finding for finding in result.findings if finding.kind == "unattributed_span")
    assert gap.bases == "ACGTACGT"
    assert gap.end == len(extended.sequence)


def test_a_subject_with_no_sequence_is_unknown_not_a_pass() -> None:
    subject = attributed_subject().model_copy(update={"sequences": []})
    result = assert_provenance(subject, parts=FAKE_PARTS)
    assert result.verdict is AssertionVerdict.UNKNOWN
    assert result.permits_export is False
    assert "not a pass" in result.reason


def test_overlapping_segments_are_a_contradiction_not_an_attribution() -> None:
    subject = attributed_subject()
    original = subject.sequences[0]
    shifted = [original.segments[0].model_copy(update={"end": original.segments[0].end + 5})]
    shifted.extend(original.segments[1:])
    result = assert_provenance(
        subject.model_copy(update={"sequences": [original.model_copy(update={"segments": shifted})]}),
        parts=FAKE_PARTS,
    )
    assert result.verdict is AssertionVerdict.UNATTRIBUTED
    assert any(finding.kind == "segment_overlap" for finding in result.findings)


def test_a_segment_that_leaves_the_sequence_attributes_nothing() -> None:
    subject = attributed_subject()
    original = subject.sequences[0]
    last = original.segments[-1]
    segments = list(original.segments[:-1])
    segments.append(last.model_copy(update={"end": len(original.sequence) + 7}))
    result = assert_provenance(
        subject.model_copy(update={"sequences": [original.model_copy(update={"segments": segments})]}),
        parts=FAKE_PARTS,
    )
    assert result.verdict is AssertionVerdict.UNATTRIBUTED
    assert any(finding.kind == "segment_out_of_range" for finding in result.findings)
    assert any(finding.kind == "unattributed_span" for finding in result.findings)


def test_a_source_absent_from_the_designs_provenance_is_a_finding() -> None:
    subject = attributed_subject().model_copy(
        update={"declared_provenance": [PROMOTER_SOURCE, POLYA_SOURCE]}
    )
    result = assert_provenance(subject, parts=FAKE_PARTS)
    assert result.verdict is AssertionVerdict.UNATTRIBUTED
    finding = next(f for f in result.findings if f.kind == "source_not_declared")
    assert USER_SOURCE in finding.message


def test_an_unknown_registry_part_is_a_finding() -> None:
    subject = attributed_subject()
    original = subject.sequences[0]
    first = original.segments[0].model_copy(
        update={"part_id": "promoter.not_in_the_registry", "source": "part:promoter.not_in_the_registry"}
    )
    segments = [first, *original.segments[1:]]
    declared = ["part:promoter.not_in_the_registry", USER_SOURCE, POLYA_SOURCE]
    result = assert_provenance(
        subject.model_copy(
            update={
                "sequences": [original.model_copy(update={"segments": segments})],
                "declared_provenance": declared,
            }
        ),
        parts=FAKE_PARTS,
    )
    assert result.verdict is AssertionVerdict.UNATTRIBUTED
    assert any(finding.kind == "registry_part_unknown" for finding in result.findings)


def test_a_registry_span_that_does_not_reproduce_its_record_is_a_finding() -> None:
    """A modified curated element is a novel element, not a curated one."""
    subject = attributed_subject()
    original = subject.sequences[0]
    mutated = "T" + original.sequence[1:]
    result = assert_provenance(
        subject.model_copy(update={"sequences": [original.model_copy(update={"sequence": mutated})]}),
        parts=FAKE_PARTS,
    )
    assert result.verdict is AssertionVerdict.UNATTRIBUTED
    finding = next(f for f in result.findings if f.kind == "registry_part_mismatch")
    assert PROMOTER_ID in finding.message


def test_a_registry_part_is_accepted_reverse_complemented() -> None:
    """A 3' ITR is the reverse complement of its own registry record."""
    from packages.core.sequence import reverse_complement

    polya = FAKE_PARTS[POLYA_ID].sequence
    flipped = reverse_complement(polya)
    subject = ExportSubject(
        capability=CapabilityKind.AAV,
        design_id="flipped",
        validator_version="v1",
        sequences=[
            AttributedSequence(
                name="cassette",
                sequence=flipped,
                segments=[
                    AttributedSegment(
                        start=0,
                        end=len(flipped),
                        origin=SequenceOrigin.REGISTRY_PART,
                        source=POLYA_SOURCE,
                        part_id=POLYA_ID,
                    )
                ],
            )
        ],
        declared_provenance=[POLYA_SOURCE],
        adapter="tests.screening.test_provenance",
    )
    assert assert_provenance(subject, parts=FAKE_PARTS).verdict is AssertionVerdict.ATTRIBUTED


def test_an_empty_registry_leaves_registry_claims_unverified_and_blocks() -> None:
    result = assert_provenance(attributed_subject(), parts={})
    assert result.permits_export is False
    assert any(finding.kind == "registry_part_unknown" for finding in result.findings)


def test_a_registry_that_cannot_be_loaded_is_unknown_not_a_pass(monkeypatch) -> None:
    import packages.application.screening.provenance as module

    def boom() -> dict[str, object]:
        raise OSError("data/parts is not readable")

    monkeypatch.setattr(module, "load_part_registry", boom)
    result = assert_provenance(attributed_subject())
    assert result.verdict is AssertionVerdict.UNKNOWN
    assert result.permits_export is False
    assert "not a pass" in result.reason


def test_a_published_rule_segment_must_name_its_rule() -> None:
    with pytest.raises(ValidationError, match="must name its rule"):
        AttributedSegment(
            start=0,
            end=4,
            origin=SequenceOrigin.PUBLISHED_RULE,
            source="enzyme:BsaI:Appendix D GGTCTC(1/5)",
        )


def test_a_registry_segment_must_name_its_part() -> None:
    with pytest.raises(ValidationError, match="must carry part_id"):
        AttributedSegment(
            start=0,
            end=4,
            origin=SequenceOrigin.REGISTRY_PART,
            source="part:promoter.cag",
        )


def test_a_published_rule_segment_needs_no_declared_provenance_entry() -> None:
    """Its rule is carried on the segment and written into the provenance by the gate."""
    sequence = "GGTCTC"
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
                        rule="Appendix D BsaI recognition sequence GGTCTC",
                    )
                ],
            )
        ],
        declared_provenance=["strategy:golden_gate"],
        adapter="tests.screening.test_provenance",
    )
    result = assert_provenance(subject, parts=FAKE_PARTS)
    assert result.verdict is AssertionVerdict.ATTRIBUTED
    assert result.rules_applied == ["Appendix D BsaI recognition sequence GGTCTC"]


def test_the_assertion_is_deterministic() -> None:
    subject = attributed_subject()
    first = assert_provenance(subject, parts=FAKE_PARTS)
    second = assert_provenance(subject, parts=FAKE_PARTS)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
