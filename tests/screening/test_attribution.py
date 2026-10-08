"""The attribution data model: what it refuses to represent.

Every refusal here exists so that a span cannot claim to be attributed without
saying where its bases came from. The four origins are the union of section
11.1 item 1 and section 4.2, and there is no fifth.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.application.screening import (
    AttributedSegment,
    AttributedSequence,
    ExportSubject,
    SequenceOrigin,
)
from packages.core.schemas.capability import CapabilityKind


def test_there_are_exactly_four_origins() -> None:
    assert {origin.value for origin in SequenceOrigin} == {
        "registry_part",
        "retrieved_template",
        "user_input",
        "published_rule",
    }


def test_a_span_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        AttributedSegment(
            start=10, end=4, origin=SequenceOrigin.USER_INPUT, source="user_input:x"
        )


def test_a_blank_source_is_refused() -> None:
    with pytest.raises(ValidationError):
        AttributedSegment(start=0, end=4, origin=SequenceOrigin.USER_INPUT, source="   ")


def test_a_sequence_must_be_acgt() -> None:
    with pytest.raises(ValidationError, match="must be A, C, G or T only"):
        AttributedSequence(name="cassette", sequence="ACGTN")


def test_a_sequence_is_normalised_to_upper_case() -> None:
    assert AttributedSequence(name="cassette", sequence="acgt").sequence == "ACGT"


def test_an_empty_sequence_is_refused() -> None:
    with pytest.raises(ValidationError):
        AttributedSequence(name="cassette", sequence="")


def test_bases_outside_the_sequence_raise_rather_than_truncate() -> None:
    item = AttributedSequence(name="cassette", sequence="ACGT")
    segment = AttributedSegment(
        start=0, end=10, origin=SequenceOrigin.USER_INPUT, source="user_input:x"
    )
    with pytest.raises(IndexError, match="leaves sequence"):
        item.bases(segment)


def test_a_subject_reports_its_total_and_finds_its_sequences_by_name() -> None:
    subject = ExportSubject(
        capability=CapabilityKind.AAV,
        design_id="d",
        validator_version="v",
        sequences=[
            AttributedSequence(name="a", sequence="ACGT"),
            AttributedSequence(name="b", sequence="ACGTAC"),
        ],
        adapter="test",
    )
    assert subject.total_bp == 10
    assert subject.sequence("b").length_bp == 6
    with pytest.raises(KeyError):
        subject.sequence("c")


def test_a_subject_must_name_its_adapter() -> None:
    with pytest.raises(ValidationError):
        ExportSubject(
            capability=CapabilityKind.AAV, design_id="d", validator_version="v", adapter=""
        )
