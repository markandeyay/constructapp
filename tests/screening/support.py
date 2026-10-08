"""Shared fixtures for the provenance and pre-export screening tests.

The sequences here are deterministic synthetic test payloads written out
literally rather than drawn from `random`, so they are byte identical on every
platform. Section 3.3 constraint 3 makes determinism a property of the tests as
well as of the code.

`FAKE_PARTS` is a two-record stand-in for the curated registry, so the
assertions about registry lookup and base-for-base comparison do not depend on
the real `data/parts` contents. Tests that do want the real registry use the
AAV designer and say so.
"""

from __future__ import annotations

from datetime import datetime, timezone

from packages.application.screening import (
    AttributedSegment,
    AttributedSequence,
    BackendFinding,
    BackendOutcome,
    ExportSubject,
    ScreeningBackend,
    ScreeningBackendUnreachable,
    ScreeningResult,
    SequenceOrigin,
)
from packages.core.part_registry import PartCategory, PartProvenance, PartRecord
from packages.core.schemas.capability import CapabilityKind

PROMOTER_SEQUENCE = "ACGTACGTACGTACGTACGT"
POLYA_SEQUENCE = "TTTTGGGGCCCCAAAATTTT"
USER_CDS = "ATGGCTGCTGCTGCTGCTTAA"

PROMOTER_ID = "promoter.test_fixture"
POLYA_ID = "polya.test_fixture"

USER_SOURCE = "user_input:transgene_sequence"
PROMOTER_SOURCE = f"part:{PROMOTER_ID}"
POLYA_SOURCE = f"part:{POLYA_ID}"

FIXED_TIME = datetime(2026, 10, 8, 1, 30, 0, tzinfo=timezone.utc)


def fixed_clock() -> datetime:
    """A pinned clock, so an audit entry is byte identical between runs."""
    return FIXED_TIME


def _part(part_id: str, category: PartCategory, name: str, sequence: str) -> PartRecord:
    return PartRecord(
        id=part_id,
        name=name,
        category=category,
        length_bp=len(sequence),
        sequence=sequence,
        host_compatibility=["mammalian_general"],
        tissue_specificity="ubiquitous" if category is PartCategory.PROMOTER else None,
        source="test fixture, not a biological record",
        notes="Synthetic test payload. Not a curated part and never exported as one.",
        citation="test fixture",
        provenance=PartProvenance(
            accession="TEST000000.0",
            record_title="screening test fixture",
            feature_type="regulatory",
            feature_note="test fixture",
            coordinates=(1, len(sequence)),
            strand=1,
            retrieved_on="2026-10-08",
            retrieved_via="written literally in tests/screening/support.py",
        ),
    )


#: A stand-in curated registry with two records.
FAKE_PARTS: dict[str, PartRecord] = {
    PROMOTER_ID: _part(PROMOTER_ID, PartCategory.PROMOTER, "test promoter", PROMOTER_SEQUENCE),
    POLYA_ID: _part(POLYA_ID, PartCategory.POLYA, "test polyA", POLYA_SEQUENCE),
}


def attributed_subject(
    *,
    design_id: str = "test-design",
    validator_version: str = "test-validator-1",
) -> ExportSubject:
    """A subject every base of which is attributed: two registry parts plus user input."""
    sequence = PROMOTER_SEQUENCE + USER_CDS + POLYA_SEQUENCE
    cut_one = len(PROMOTER_SEQUENCE)
    cut_two = cut_one + len(USER_CDS)
    return ExportSubject(
        capability=CapabilityKind.AAV,
        design_id=design_id,
        validator_version=validator_version,
        sequences=[
            AttributedSequence(
                name="cassette",
                sequence=sequence,
                segments=[
                    AttributedSegment(
                        start=0,
                        end=cut_one,
                        origin=SequenceOrigin.REGISTRY_PART,
                        source=PROMOTER_SOURCE,
                        part_id=PROMOTER_ID,
                    ),
                    AttributedSegment(
                        start=cut_one,
                        end=cut_two,
                        origin=SequenceOrigin.USER_INPUT,
                        source=USER_SOURCE,
                    ),
                    AttributedSegment(
                        start=cut_two,
                        end=len(sequence),
                        origin=SequenceOrigin.REGISTRY_PART,
                        source=POLYA_SOURCE,
                        part_id=POLYA_ID,
                    ),
                ],
            )
        ],
        declared_provenance=[PROMOTER_SOURCE, USER_SOURCE, POLYA_SOURCE],
        adapter="tests.screening.support",
    )


def subject_with_unattributed_base(*, extra: str = "GGGGGGGGGG") -> ExportSubject:
    """The same subject with `extra` bases spliced in that no segment covers.

    This is the section 11.1 item 1 case: sequence in the output that traces to
    no registry part, no template, no user input and no rule.
    """
    subject = attributed_subject(design_id="test-design-with-gap")
    original = subject.sequences[0]
    cut = len(PROMOTER_SEQUENCE)
    spliced = original.sequence[:cut] + extra + original.sequence[cut:]
    shift = len(extra)
    segments = []
    for segment in original.segments:
        if segment.start < cut:
            segments.append(segment)
        else:
            segments.append(
                segment.model_copy(update={"start": segment.start + shift, "end": segment.end + shift})
            )
    return subject.model_copy(
        update={
            "sequences": [original.model_copy(update={"sequence": spliced, "segments": segments})]
        }
    )


class RaisingBackend:
    """A configured backend that raises. It must never produce a no-findings result."""

    backend_id = "test.raising_backend"
    backend_version = "1"

    def screen(self, subject: ExportSubject) -> ScreeningResult:
        raise RuntimeError("the screening service rejected the request")


class UnreachableBackend:
    """A configured backend that cannot reach its service."""

    backend_id = "test.unreachable_backend"
    backend_version = "1"

    def screen(self, subject: ExportSubject) -> ScreeningResult:
        raise ScreeningBackendUnreachable("connection timed out after 5 s")


class NoFindingsBackend:
    """A configured backend that ran and returned nothing."""

    backend_id = "test.no_findings_backend"
    backend_version = "2.1"

    def screen(self, subject: ExportSubject) -> ScreeningResult:
        return ScreeningResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            outcome=BackendOutcome.BACKEND_REPORTED_NO_FINDINGS,
            findings=[],
            detail="The test backend examined the submitted sequences and returned no findings.",
            sequences_submitted=len(subject.sequences),
            bases_submitted=subject.total_bp,
        )


class FindingBackend:
    """A configured backend that ran and returned one finding."""

    backend_id = "test.finding_backend"
    backend_version = "2.1"

    def screen(self, subject: ExportSubject) -> ScreeningResult:
        return ScreeningResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            outcome=BackendOutcome.BACKEND_REPORTED_FINDINGS,
            findings=[
                BackendFinding(
                    sequence_name=subject.sequences[0].name,
                    code="TEST_FINDING",
                    detail="the test backend's own words, carried through unchanged",
                )
            ],
            detail="The test backend examined the submitted sequences and returned 1 finding.",
            sequences_submitted=len(subject.sequences),
            bases_submitted=subject.total_bp,
        )


BACKENDS: tuple[ScreeningBackend, ...] = (
    RaisingBackend(),
    UnreachableBackend(),
    NoFindingsBackend(),
    FindingBackend(),
)
