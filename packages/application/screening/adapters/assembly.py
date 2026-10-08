"""Attribution adapter for the primer and assembly capability (section 7).

The orderable DNA this capability produces is its primers, so those are the
sequences the subject carries. The fragments and the vector backbone are the
user's own input going in, not sequence this system composed, and they are
named as the sources of the spans that came from them.

Section 4.2 states the structure the adapter relies on: "A primer is a
subsequence of a known template plus an optional tail." `Primer.sequence` is
`tail + binding`, so the two parts are already separated, and
`packages/generation/assembly/designer.py` states in its own module docstring
that every base it emits is a fragment base, a vector backbone base, an
Appendix D recognition sequence, a fusion overhang from a junction or a
standard, or a spacer nucleotide from its documented rule.

How each part is proved rather than assumed:

* `binding` is compared against the named fragment at the recorded interval,
  forward for a forward primer and reverse complement for a reverse one. A
  binding region that does not reproduce its template is not attributed.
* A Gibson `tail` is matched against the design's own `gibson_homology`
  junctions and then verified to be a suffix of the upstream fragment, so a
  homology arm is attributed to the fragment it was copied from.
* A Type IIS `tail` is split at the enzyme's recognition sequence, which must
  occur exactly once. The site itself is a rule derived span citing Appendix D.
  The spacer nucleotides before it, and the `top_cut_offset` filler bases after
  it, are rule derived spans citing the documented spacer rule. Any remaining
  bases must reproduce one of the design's own junction overhangs, which is
  attributed to the published standard it came from or to the downstream
  fragment whose first bases it is.
* Anything the adapter cannot split this way is left uncovered, so the export
  is blocked with the primer name, the coordinates and the bases.
"""

from __future__ import annotations

from packages.core.schemas.assembly import AssemblyDesign, Junction, Primer
from packages.core.schemas.capability import CapabilityKind
from packages.core.sequence import reverse_complement
from packages.validation.assembly.enzymes import TypeIISEnzyme, get_enzyme

from ..attribution import AttributedSegment, AttributedSequence, ExportSubject, SequenceOrigin

ADAPTER_NAME = "screening.adapters.assembly"

#: The fragment name the designer gives the vector backbone when it takes part
#: in the assembly. Kept in step with `designer.VECTOR_BACKBONE_NAME`.
VECTOR_BACKBONE_NAME = "vector_backbone"

#: The provenance token the designer records for a supplied vector backbone.
VECTOR_BACKBONE_SOURCE = "user_input:vector_backbone"

#: The rule that fixes the identity of a Type IIS primer tail's spacer and
#: filler nucleotides. Appendix D fixes how many are needed; their identity is
#: set by the documented deterministic scan in
#: `packages/generation/assembly/designer.py::_filler`, which takes the first
#: base in A, C, G, T order that adds no new copy of the recognition site.
SPACER_RULE = (
    "Type IIS primer tail spacer: Appendix D cut offsets fix how many nucleotides sit between "
    "the recognition site and the cut, and their identity is fixed by the documented A, C, G, T "
    "scan in packages/generation/assembly/designer.py::_filler, which takes the first base that "
    "adds no new copy of the recognition site"
)


def _fragment_source(design: AssemblyDesign, name: str) -> tuple[str, str] | None:
    """The sequence and provenance token for a named fragment, or None when unknown.

    A fragment and a supplied vector backbone are both sequence the user put in
    the request, so both are `USER_INPUT`. The token is the one the designer
    already records in `AssemblyDesign.provenance`, so the two agree.
    """
    if name == VECTOR_BACKBONE_NAME and design.request.vector_backbone:
        return design.request.vector_backbone, VECTOR_BACKBONE_SOURCE
    for fragment in design.request.fragments:
        if fragment.name == name:
            return fragment.sequence, f"fragment:{fragment.name}:{fragment.source}"
    return None


def _binding_segment(design: AssemblyDesign, primer: Primer) -> AttributedSegment | None:
    """The span of the primer that anneals, attributed to its template.

    Returns None when the binding region does not reproduce the named fragment
    at the recorded interval, in which case the span stays uncovered and the
    export is blocked.
    """
    resolved = _fragment_source(design, primer.fragment)
    if resolved is None:
        return None
    sequence, source = resolved
    if primer.binding_end > len(sequence):
        return None
    region = sequence[primer.binding_start : primer.binding_end]
    expected = region if primer.direction == "forward" else reverse_complement(region)
    if expected != primer.binding:
        return None
    start = len(primer.tail)
    return AttributedSegment(
        start=start,
        end=start + len(primer.binding),
        origin=SequenceOrigin.USER_INPUT,
        source=source,
        detail=(
            f"binding region, {primer.direction} primer on {primer.fragment} "
            f"({primer.binding_start}, {primer.binding_end})"
        ),
    )


def _gibson_tail_segment(design: AssemblyDesign, primer: Primer) -> AttributedSegment | None:
    """A Gibson homology arm, attributed to the upstream fragment it was copied from."""
    for junction in design.junctions:
        if junction.kind != "gibson_homology":
            continue
        if junction.right_fragment != primer.fragment or junction.sequence != primer.tail:
            continue
        resolved = _fragment_source(design, junction.left_fragment)
        if resolved is None:
            return None
        sequence, source = resolved
        if not sequence.endswith(primer.tail):
            return None
        return AttributedSegment(
            start=0,
            end=len(primer.tail),
            origin=SequenceOrigin.USER_INPUT,
            source=source,
            detail=(
                f"Gibson terminal homology arm, the last {len(primer.tail)} bp of "
                f"{junction.left_fragment}"
            ),
        )
    return None


def _overhang_segment(
    design: AssemblyDesign,
    primer: Primer,
    start: int,
    bases: str,
) -> AttributedSegment | None:
    """A fusion overhang inside a Type IIS tail, attributed to where it came from.

    A standard's overhang is rule derived and cites the standard. A junction
    overhang is the first bases of the downstream fragment, so it is attributed
    to that fragment and verified to be its prefix.
    """
    for junction in design.junctions:
        if junction.kind != "golden_gate_overhang":
            continue
        if bases not in (junction.sequence, reverse_complement(junction.sequence)):
            continue
        if junction.overhang_source == "overhang_standard":
            standard = design.request.overhang_standard
            if standard is None or standard.name != junction.overhang_standard_name:
                return None
            return AttributedSegment(
                start=start,
                end=start + len(bases),
                origin=SequenceOrigin.PUBLISHED_RULE,
                source=f"overhang_standard:{standard.name}:{standard.citation}",
                rule=(
                    f"fusion overhang from the {standard.name} standard, used verbatim as "
                    f"Appendix D requires, cited as {standard.citation}"
                ),
                detail=f"junction {junction.index} fusion overhang",
            )
        resolved = _fragment_source(design, junction.right_fragment)
        if resolved is None:
            return None
        sequence, source = resolved
        if not _is_junction_prefix(sequence, bases):
            return None
        return AttributedSegment(
            start=start,
            end=start + len(bases),
            origin=SequenceOrigin.USER_INPUT,
            source=source,
            detail=(
                f"junction {junction.index} fusion overhang, the first {len(bases)} bp of "
                f"{junction.right_fragment}"
            ),
        )
    return None


def _is_junction_prefix(sequence: str, bases: str) -> bool:
    """Whether `bases`, in either orientation, is the first bases of `sequence`."""
    width = len(bases)
    head = sequence[:width]
    return bases in (head, reverse_complement(head))


def _type_iis_tail_segments(
    design: AssemblyDesign,
    primer: Primer,
    enzyme: TypeIISEnzyme,
) -> list[AttributedSegment]:
    """Split a Type IIS primer tail into its rule derived and copied parts.

    Returns an empty list when the tail does not split cleanly, so the span
    stays uncovered and the export is blocked rather than guessed at.
    """
    tail = primer.tail
    site = enzyme.recognition
    if tail.count(site) != 1:
        return []
    index = tail.index(site)
    segments: list[AttributedSegment] = []
    if index:
        segments.append(
            AttributedSegment(
                start=0,
                end=index,
                origin=SequenceOrigin.PUBLISHED_RULE,
                source=f"enzyme:{enzyme.name}:Appendix D {enzyme.cut_notation}",
                rule=SPACER_RULE,
                detail=f"{index} bp spacer 5' of the {enzyme.name} recognition site",
            )
        )
    segments.append(
        AttributedSegment(
            start=index,
            end=index + len(site),
            origin=SequenceOrigin.PUBLISHED_RULE,
            source=f"enzyme:{enzyme.name}:Appendix D {enzyme.cut_notation}",
            rule=f"Appendix D {enzyme.name} recognition sequence {site}, cut notation {enzyme.cut_notation}",
            detail=f"{enzyme.name} recognition site",
        )
    )
    cursor = index + len(site)
    rest = tail[cursor:]
    if not rest:
        return segments
    filler_width = enzyme.top_cut_offset
    if len(rest) < filler_width:
        return []
    if filler_width:
        segments.append(
            AttributedSegment(
                start=cursor,
                end=cursor + filler_width,
                origin=SequenceOrigin.PUBLISHED_RULE,
                source=f"enzyme:{enzyme.name}:Appendix D {enzyme.cut_notation}",
                rule=SPACER_RULE,
                detail=(
                    f"{filler_width} bp between the {enzyme.name} recognition site and the top "
                    "strand cut, per Appendix D"
                ),
            )
        )
    cursor += filler_width
    remainder = tail[cursor:]
    if not remainder:
        return segments
    overhang = _overhang_segment(design, primer, cursor, remainder)
    if overhang is None:
        return []
    segments.append(overhang)
    return segments


def _primer_sequence(design: AssemblyDesign, primer: Primer, enzyme: TypeIISEnzyme | None) -> AttributedSequence:
    segments: list[AttributedSegment] = []
    if primer.tail:
        if design.request.strategy == "gibson":
            tail_segment = _gibson_tail_segment(design, primer)
            if tail_segment is not None:
                segments.append(tail_segment)
        elif enzyme is not None:
            segments.extend(_type_iis_tail_segments(design, primer, enzyme))
    binding = _binding_segment(design, primer)
    if binding is not None:
        segments.append(binding)
    return AttributedSequence(
        name=f"primer:{primer.name}",
        sequence=primer.sequence,
        segments=segments,
        role=f"{primer.direction}_primer",
    )


def assembly_subject(
    design: AssemblyDesign,
    *,
    validator_version: str,
    declared_provenance: list[str] | None = None,
) -> ExportSubject:
    """Build the `ExportSubject` for one assembly design.

    The subject carries one sequence per primer, which is the orderable DNA
    section 7.7 puts in the order table. A design with no primers produces a
    subject with no sequences, which the provenance assertion reports as
    UNKNOWN and which blocks: there is nothing to attribute, so there is no
    evidence of attribution.
    """
    enzyme: TypeIISEnzyme | None = None
    if design.request.enzyme:
        try:
            enzyme = get_enzyme(design.request.enzyme)
        except Exception:  # noqa: BLE001 - an unknown enzyme leaves tails unattributed, which blocks
            enzyme = None
    sequences = [_primer_sequence(design, primer, enzyme) for primer in design.primers]
    return ExportSubject(
        capability=CapabilityKind.ASSEMBLY,
        design_id=f"assembly:{design.request.strategy}",
        validator_version=validator_version,
        sequences=sequences,
        declared_provenance=list(
            declared_provenance if declared_provenance is not None else design.provenance
        ),
        adapter=ADAPTER_NAME,
    )


__all__ = ["ADAPTER_NAME", "SPACER_RULE", "assembly_subject"]


def junctions_of(design: AssemblyDesign) -> list[Junction]:
    """The design's junctions, exposed for tests that assert the tail split."""
    return list(design.junctions)
