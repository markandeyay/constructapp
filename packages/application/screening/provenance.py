"""The sequence provenance assertion (section 11.1 item 1).

"Every base in the output traces to a registry part, a retrieved template, or
the user's own supplied input. A design containing unattributable sequence is
blocked from export."

This module answers one question about an `ExportSubject`: is every base of
every exported sequence covered by a span that names where it came from. It is
a gate, not a warning. Only the `ATTRIBUTED` verdict permits an export, and
section 3.3 constraint 4 decides the rest: a subject whose attribution cannot
be evaluated at all returns `UNKNOWN` with a reason, which also blocks, and
never `ATTRIBUTED` by default.

What is checked, in order, with every failure collected rather than the first
one raised, so a blocked export can be fixed in one pass:

1. The subject carries at least one sequence. A subject with none is `UNKNOWN`:
   there is nothing to attribute, so there is no evidence of attribution.
2. Every segment lies inside its sequence.
3. No two segments of one sequence overlap. An overlap means two different
   sources both claim the same base, which is a contradiction, not a pass.
4. The segments cover the sequence completely. Every uncovered span is
   reported with its coordinates and its bases, because that span is the
   unattributable sequence section 11.1 blocks on.
5. Every segment that names a sequence record as its source, meaning every
   `REGISTRY_PART`, `RETRIEVED_TEMPLATE` and `USER_INPUT` segment, has that
   source in the design's `declared_provenance`, so the provenance list a user
   reads is the list the bases actually came from. A `PUBLISHED_RULE` segment
   is exempt from this one check and only from this one: its rule is carried on
   the segment itself, every distinct rule is listed in `rules_applied`, and
   `ScreeningRecord.record_in_design` writes each rule into the design's
   provenance, so a rule derived base still ends up named in the list a user
   reads. The exemption exists because a capability's provenance list records
   the sources it drew sequence from and does not enumerate the rules its
   composer applied base by base.
6. Every `REGISTRY_PART` segment names a part id that resolves in the curated
   registry, and its bases equal that record's sequence, forward or reverse
   complement. A span that claims a registry part but does not reproduce it is
   a modified element, not a curated one.
7. Every `RETRIEVED_TEMPLATE` segment that carries source coordinates is
   compared against the template record it names, base for base, at those
   coordinates. This is the same standard check 6 applies to a registry part,
   extended to a record the span covers only part of, which is why the segment
   carries `source_start` and `source_end`: without them the bases could not be
   located in the record and the claim could only be believed.

   A template span whose record was not supplied, or which carries no source
   coordinates, is `UNKNOWN` rather than a pass. Stated plainly because it is
   the difference between a verified attribution and a recorded assertion: a
   span saying "these bases came from template X" is evidence only once someone
   has fetched X and looked.

Determinism (section 3.3 constraint 3): this is a pure function of the subject,
the on-disk part registry and the template sequences passed in. There is no
randomness and no model call.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping

from pydantic import Field

from packages.core.part_registry import PartRecord, load_part_registry
from packages.core.schemas.capability import CapabilityModel
from packages.core.sequence import reverse_complement

from .attribution import AttributedSequence, AttributedSegment, ExportSubject, SequenceOrigin


class AssertionVerdict(str, Enum):
    """The outcome of an assertion. Only `ATTRIBUTED` and `SATISFIED` permit export.

    `UNKNOWN` exists because section 3.3 constraint 4 forbids a default pass:
    an assertion that could not be evaluated says so, with a reason, and the
    export is still blocked.
    """

    ATTRIBUTED = "attributed"
    UNATTRIBUTED = "unattributed"
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNKNOWN = "unknown"


#: The only verdicts that permit an export. Everything else blocks, including
#: UNKNOWN (section 3.3 constraint 4).
PERMITTING_VERDICTS = frozenset({AssertionVerdict.ATTRIBUTED, AssertionVerdict.SATISFIED})


class AttributionFinding(CapabilityModel):
    """One reason a subject is not fully attributed.

    `bases` is populated for an uncovered span so that the person reading a
    blocked export can see the actual unattributable sequence, truncated for
    readability when it is long.
    """

    sequence_name: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    start: int | None = None
    end: int | None = None
    bases: str | None = None
    message: str = Field(min_length=1)


class ProvenanceAssertion(CapabilityModel):
    """The result of the section 11.1 item 1 assertion over one subject."""

    verdict: AssertionVerdict
    sequences_checked: int = Field(ge=0)
    bases_checked: int = Field(ge=0)
    bases_attributed: int = Field(ge=0)
    origins_used: list[SequenceOrigin] = Field(default_factory=list)
    rules_applied: list[str] = Field(default_factory=list)
    findings: list[AttributionFinding] = Field(default_factory=list)
    reason: str = Field(min_length=1)

    @property
    def permits_export(self) -> bool:
        """True only for `ATTRIBUTED`. UNKNOWN blocks, per section 3.3 constraint 4."""
        return self.verdict in PERMITTING_VERDICTS

    @property
    def unattributed_bases(self) -> int:
        return self.bases_checked - self.bases_attributed


_MAX_REPORTED_BASES = 60


def _show(bases: str) -> str:
    if len(bases) <= _MAX_REPORTED_BASES:
        return bases
    head = bases[: _MAX_REPORTED_BASES - 20]
    tail = bases[-17:]
    return f"{head}...{tail}"


def _uncovered_spans(item: AttributedSequence) -> list[tuple[int, int]]:
    """The spans of `item.sequence` that no segment covers, left to right."""
    spans = sorted((segment.start, segment.end) for segment in item.segments)
    gaps: list[tuple[int, int]] = []
    cursor = 0
    for start, end in spans:
        if start > cursor:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < len(item.sequence):
        gaps.append((cursor, len(item.sequence)))
    return gaps


def _overlaps(item: AttributedSequence) -> list[tuple[AttributedSegment, AttributedSegment]]:
    ordered = sorted(item.segments, key=lambda segment: (segment.start, segment.end))
    found: list[tuple[AttributedSegment, AttributedSegment]] = []
    for earlier, later in zip(ordered, ordered[1:]):
        if later.start < earlier.end:
            found.append((earlier, later))
    return found


def _registry_match(segment: AttributedSegment, bases: str, record: PartRecord) -> str | None:
    """None when the bases reproduce the record, else why they do not."""
    if bases == record.sequence:
        return None
    if bases == reverse_complement(record.sequence):
        return None
    if len(bases) != len(record.sequence):
        return (
            f"claims registry part {segment.part_id!r} of {record.length_bp:,} bp but covers "
            f"{len(bases):,} bp"
        )
    return (
        f"claims registry part {segment.part_id!r} but the bases differ from the registry "
        "record in neither orientation; a modified element is not a curated one"
    )


def _template_match(segment: AttributedSegment, bases: str, template: str) -> str | None:
    """None when the bases reproduce the named template at the claimed coordinates.

    Deliberately stricter than the registry comparison in one respect and looser
    in another. Stricter: the coordinates must be inside the record, so a span
    claiming bases past the end of its template is reported rather than silently
    clamped by Python slicing. Looser: no reverse complement fallback, because a
    template span records a copy from a specific orientation of a specific range,
    and a range that matches only when flipped is not the range the span claims.
    """
    if segment.source_start is None or segment.source_end is None:
        return None
    if segment.source_end > len(template):
        return (
            f"claims bases ({segment.source_start}, {segment.source_end}) of template "
            f"{segment.template_id!r}, which is only {len(template):,} bp long"
        )
    expected = template[segment.source_start : segment.source_end]
    if bases == expected:
        return None
    differing = sum(1 for left, right in zip(bases, expected) if left != right)
    return (
        f"claims bases ({segment.source_start}, {segment.source_end}) of template "
        f"{segment.template_id!r} but differs from that record in {differing:,} of "
        f"{len(expected):,} positions; a modified template is not the template it names"
    )


def assert_provenance(
    subject: ExportSubject,
    *,
    parts: dict[str, PartRecord] | None = None,
    templates: Mapping[str, str] | None = None,
) -> ProvenanceAssertion:
    """Run the section 11.1 item 1 assertion. Only `ATTRIBUTED` permits an export.

    `parts` overrides the curated registry, which the tests use and which a
    caller with a pinned registry snapshot can use. When it is None the
    on-disk registry in `data/parts` is loaded; if that load fails the verdict
    is `UNKNOWN` with the loader's message, because a registry claim that
    cannot be checked is not a verified one.

    `templates` maps a retrieved template id to that template's full sequence, so
    a `RETRIEVED_TEMPLATE` span carrying source coordinates can be compared
    against the record it names instead of being taken on trust. A span that
    names a template absent from this mapping is UNKNOWN and blocks, on the same
    reasoning as a missing registry: an unverifiable claim is not a verified one
    (section 3.3 constraint 4).

    A span with no source coordinates cannot be located in its record, so it
    cannot be verified either. That is also UNKNOWN rather than a pass. The
    distinction matters because the three capabilities wired before this one emit
    template spans without coordinates nowhere, and user input spans everywhere,
    and a user input span has nothing external to compare against by definition.
    """
    if not subject.sequences:
        return ProvenanceAssertion(
            verdict=AssertionVerdict.UNKNOWN,
            sequences_checked=0,
            bases_checked=0,
            bases_attributed=0,
            reason=(
                f"subject {subject.design_id!r} carries no sequence to attribute, so attribution "
                "could not be evaluated. Section 3.3 constraint 4: this is not a pass. The export "
                f"is blocked. The adapter {subject.adapter!r} must emit the exported sequences, or "
                "the design must not be exported."
            ),
        )

    registry: dict[str, PartRecord] | None = parts
    registry_reason: str | None = None
    if registry is None:
        try:
            registry = load_part_registry()
        except Exception as exc:  # noqa: BLE001 - any loader failure is an unknown, not a pass
            registry = None
            registry_reason = f"the curated part registry could not be loaded: {exc}"

    findings: list[AttributionFinding] = []
    declared = set(subject.declared_provenance)
    bases_checked = 0
    bases_attributed = 0
    origins: list[SequenceOrigin] = []
    rules: list[str] = []
    needs_registry = False
    needs_templates = False
    unverifiable_templates: list[str] = []

    for item in subject.sequences:
        bases_checked += item.length_bp
        in_range: list[AttributedSegment] = []
        for segment in item.segments:
            if segment.end > item.length_bp:
                findings.append(
                    AttributionFinding(
                        sequence_name=item.name,
                        kind="segment_out_of_range",
                        start=segment.start,
                        end=segment.end,
                        message=(
                            f"segment ({segment.start}, {segment.end}) from {segment.source!r} "
                            f"leaves sequence {item.name!r} of {item.length_bp:,} bp. Fix the "
                            "adapter coordinates; a span outside the sequence attributes nothing."
                        ),
                    )
                )
                continue
            in_range.append(segment)
            if segment.origin not in origins:
                origins.append(segment.origin)
            if segment.origin is SequenceOrigin.PUBLISHED_RULE and segment.rule and segment.rule not in rules:
                rules.append(segment.rule)
            if segment.origin is SequenceOrigin.REGISTRY_PART:
                needs_registry = True
            if segment.origin is SequenceOrigin.RETRIEVED_TEMPLATE:
                needs_templates = True
                # A template span that cannot be located in its record cannot be
                # compared against it. Collected as an unverifiable claim rather
                # than waved through: section 3.3 constraint 4.
                if not (segment.template_id or "").strip() or segment.source_start is None:
                    unverifiable_templates.append(
                        f"segment ({segment.start}, {segment.end}) of {item.name!r} names "
                        f"template source {segment.source!r} but carries "
                        + (
                            "no template id"
                            if not (segment.template_id or "").strip()
                            else "no source coordinates"
                        )
                        + ", so its bases could not be located in that record and the claim "
                        "could not be verified"
                    )

        checked = item.model_copy(update={"segments": in_range})

        for earlier, later in _overlaps(checked):
            findings.append(
                AttributionFinding(
                    sequence_name=item.name,
                    kind="segment_overlap",
                    start=later.start,
                    end=min(earlier.end, later.end),
                    message=(
                        f"segments {earlier.source!r} ({earlier.start}, {earlier.end}) and "
                        f"{later.source!r} ({later.start}, {later.end}) both claim bases "
                        f"{later.start} to {min(earlier.end, later.end)} of {item.name!r}. Two "
                        "sources for one base is a contradiction, not an attribution."
                    ),
                )
            )

        for start, end in _uncovered_spans(checked):
            bases = item.sequence[start:end]
            findings.append(
                AttributionFinding(
                    sequence_name=item.name,
                    kind="unattributed_span",
                    start=start,
                    end=end,
                    bases=_show(bases),
                    message=(
                        f"{end - start:,} bp of {item.name!r} at ({start}, {end}) trace to no "
                        "registry part, no retrieved template, no user supplied input and no "
                        f"named rule: {_show(bases)}. Section 11.1 blocks this design from export. "
                        "Attribute the span or remove it from the design."
                    ),
                )
            )

        covered = sum(end - start for start, end in _covered_spans(checked))
        bases_attributed += covered

        for segment in in_range:
            if segment.origin is not SequenceOrigin.PUBLISHED_RULE and segment.source not in declared:
                findings.append(
                    AttributionFinding(
                        sequence_name=item.name,
                        kind="source_not_declared",
                        start=segment.start,
                        end=segment.end,
                        message=(
                            f"segment ({segment.start}, {segment.end}) of {item.name!r} names "
                            f"source {segment.source!r}, which is not in the design's recorded "
                            "provenance. The provenance a user reads must be the provenance the "
                            "bases came from. Add the source to DesignResult.provenance."
                        ),
                    )
                )
            if segment.origin is not SequenceOrigin.REGISTRY_PART:
                continue
            if registry is None:
                continue
            record = registry.get(segment.part_id or "")
            if record is None:
                findings.append(
                    AttributionFinding(
                        sequence_name=item.name,
                        kind="registry_part_unknown",
                        start=segment.start,
                        end=segment.end,
                        message=(
                            f"segment ({segment.start}, {segment.end}) of {item.name!r} claims "
                            f"registry part {segment.part_id!r}, which is not in the curated "
                            "registry. Section 11.1 item 2: functional elements come from the "
                            "curated registry."
                        ),
                    )
                )
                continue
            mismatch = _registry_match(segment, checked.bases(segment), record)
            if mismatch is not None:
                findings.append(
                    AttributionFinding(
                        sequence_name=item.name,
                        kind="registry_part_mismatch",
                        start=segment.start,
                        end=segment.end,
                        message=(
                            f"segment ({segment.start}, {segment.end}) of {item.name!r} "
                            f"{mismatch}. Section 11.1 item 2."
                        ),
                    )
                )

        # Template spans, compared against the records they name. Separate loop
        # from the registry one above only because it needs a different record
        # source; the standard applied is the same, which is that a span naming a
        # record must reproduce that record at the coordinates it claims.
        if templates is not None:
            for segment in in_range:
                if segment.origin is not SequenceOrigin.RETRIEVED_TEMPLATE:
                    continue
                template_id = (segment.template_id or "").strip()
                if not template_id or segment.source_start is None:
                    continue  # already collected as unverifiable above
                record_sequence = templates.get(template_id)
                if record_sequence is None:
                    unverifiable_templates.append(
                        f"segment ({segment.start}, {segment.end}) of {item.name!r} claims "
                        f"template {template_id!r}, whose record was not supplied to the "
                        "assertion, so its bases could not be compared against it"
                    )
                    continue
                mismatch = _template_match(segment, checked.bases(segment), record_sequence)
                if mismatch is not None:
                    findings.append(
                        AttributionFinding(
                            sequence_name=item.name,
                            kind="retrieved_template_mismatch",
                            start=segment.start,
                            end=segment.end,
                            message=(
                                f"segment ({segment.start}, {segment.end}) of {item.name!r} "
                                f"{mismatch}. Section 11.1 item 1."
                            ),
                        )
                    )

    if needs_templates and templates is None:
        return ProvenanceAssertion(
            verdict=AssertionVerdict.UNKNOWN,
            sequences_checked=len(subject.sequences),
            bases_checked=bases_checked,
            bases_attributed=0,
            origins_used=origins,
            rules_applied=rules,
            findings=findings,
            reason=(
                "this design claims bases from a retrieved template, but no template records "
                "were supplied to the assertion, so those claims could not be verified against "
                "the records they name. Section 3.3 constraint 4: this is UNKNOWN, not a pass, "
                "and the export is blocked."
            ),
        )

    if unverifiable_templates:
        return ProvenanceAssertion(
            verdict=AssertionVerdict.UNKNOWN,
            sequences_checked=len(subject.sequences),
            bases_checked=bases_checked,
            bases_attributed=0,
            origins_used=origins,
            rules_applied=rules,
            findings=findings,
            reason=(
                f"{len(unverifiable_templates)} template claim(s) could not be verified: "
                + "; ".join(unverifiable_templates)
                + ". Section 3.3 constraint 4: an unverified claim is UNKNOWN, not a pass, and "
                "the export is blocked."
            ),
        )

    if needs_registry and registry is None:
        return ProvenanceAssertion(
            verdict=AssertionVerdict.UNKNOWN,
            sequences_checked=len(subject.sequences),
            bases_checked=bases_checked,
            bases_attributed=0,
            origins_used=origins,
            rules_applied=rules,
            findings=findings,
            reason=(
                f"{registry_reason or 'no curated part registry was supplied'}, and this design "
                "claims registry parts, so those claims could not be verified. Section 3.3 "
                "constraint 4: this is UNKNOWN, not a pass, and the export is blocked."
            ),
        )

    if findings:
        unattributed = sum(
            (finding.end or 0) - (finding.start or 0)
            for finding in findings
            if finding.kind == "unattributed_span"
        )
        return ProvenanceAssertion(
            verdict=AssertionVerdict.UNATTRIBUTED,
            sequences_checked=len(subject.sequences),
            bases_checked=bases_checked,
            bases_attributed=bases_attributed,
            origins_used=origins,
            rules_applied=rules,
            findings=findings,
            reason=(
                f"{len(findings)} attribution problem(s) across {len(subject.sequences)} "
                f"sequence(s), {unattributed:,} bp of {bases_checked:,} bp unattributable. "
                "Section 11.1 item 1 blocks this design from export. Every problem is listed in "
                "findings with its coordinates."
            ),
        )

    return ProvenanceAssertion(
        verdict=AssertionVerdict.ATTRIBUTED,
        sequences_checked=len(subject.sequences),
        bases_checked=bases_checked,
        bases_attributed=bases_attributed,
        origins_used=origins,
        rules_applied=rules,
        findings=[],
        reason=(
            f"every one of {bases_checked:,} bp across {len(subject.sequences)} sequence(s) is "
            "covered by a span naming a curated registry part, a retrieved template, a user "
            "supplied input or a named rule, each source is in the design's recorded provenance, "
            "every registry span reproduces its registry record base for base, and every "
            "template span reproduces the named template at the coordinates it claims."
        ),
    )


def _covered_spans(item: AttributedSequence) -> list[tuple[int, int]]:
    """The merged spans of `item.sequence` that at least one segment covers."""
    spans = sorted((segment.start, segment.end) for segment in item.segments)
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged
