"""Attribution adapter for the guide RNA capability (section 8).

Section 4.2: "A guide RNA is a 20-mer window from a supplied target that sits
next to a PAM." So a spacer is the user's own sequence, and the only other DNA
the capability emits is the published cloning vector overhangs and scaffolds
that `packages/validation/grna/vectors.py` records with their accessions.

The subject carries two kinds of sequence per returned guide: the spacer
itself, which appears in the exported guide table, and every cloning oligo,
which is what a lab orders.

How each part is proved rather than assumed:

* A spacer is located on the user's own `target_sequence` at the placement the
  design recorded, forward for a plus strand guide and reverse complement for a
  minus strand one. A spacer that is not there is not attributed, so a
  mis-placed guide blocks its own export.
* A cloning oligo's 5' overhang and 3' addition are compared against the
  published record for the vector the plan names. A sequence that is not in
  that record is not attributed.
* The documented single G or single C that the published U6 and T7 protocols
  add when a spacer does not begin with G is a rule derived span of exactly one
  base, citing that rule. Anything longer than one base is not attributed.
* A guide independent oligo, the constant T7 scaffold oligo, is compared
  against the recorded template for that nuclease and attributed to the source
  the record names. Anything else is left uncovered and blocks.
"""

from __future__ import annotations

from packages.core.schemas.capability import CapabilityKind
from packages.core.schemas.grna import CloningOligo, CloningPlan, GuideRNAResult, RankedGuide
from packages.core.sequence import reverse_complement
from packages.validation.grna.vectors import CLONING_VECTORS, IVT_TEMPLATES

from ..attribution import AttributedSegment, AttributedSequence, ExportSubject, SequenceOrigin

ADAPTER_NAME = "screening.adapters.grna"

#: The published protocol rule that adds a single G to a spacer that does not
#: begin with one, and the matching C on the antisense oligo. Recorded in
#: `packages/generation/grna/cloning.py` with the same wording.
FIVE_PRIME_G_RULE = (
    "published U6 and T7 protocol rule: efficient transcription needs the transcript to begin "
    "with G, so a single G is prepended when the spacer does not, with a matching C appended to "
    "the antisense oligo"
)


def _target_source(result: GuideRNAResult) -> str:
    """The provenance token the designer records for the user's target sequence."""
    return f"user_input:target_sequence:{result.target_name}"


def _spacer_is_on_target(target: str, guide: RankedGuide) -> bool:
    """Whether the spacer really is the recorded window of the user's target."""
    placement = guide.placement
    if placement.spacer_end > len(target) or placement.spacer_start < 0:
        return False
    window = target[placement.spacer_start : placement.spacer_end]
    expected = window if placement.strand == 1 else reverse_complement(window)
    return expected == guide.spacer


def _published_fragments(result: GuideRNAResult, plan: CloningPlan) -> dict[str, str]:
    """Published overhang and scaffold sequences for the vector the plan names.

    Maps each sequence to the rule that records it, so a matched overhang cites
    the record it was read from rather than being accepted because it is short.
    """
    out: dict[str, str] = {}
    vector = CLONING_VECTORS.get(plan.vector_id)
    if vector is not None:
        rule = (
            f"published cloning overhang for {vector.name} ({vector.accession}), read from "
            f"{vector.source}"
        )
        for sequence in (vector.forward_overhang, vector.reverse_overhang, vector.suffix):
            if sequence:
                out[sequence] = rule
    template = IVT_TEMPLATES.get(result.nuclease)
    if template is not None:
        rule = (
            f"published T7 in-vitro transcription template for {result.nuclease}, read from "
            f"{template.source}"
        )
        for sequence in (template.target_prefix, template.target_suffix):
            if sequence:
                out[sequence] = rule
    return out


def _oligo_sequence(
    result: GuideRNAResult,
    guide: RankedGuide,
    plan: CloningPlan,
    oligo: CloningOligo,
    *,
    spacer_attributable: bool,
) -> AttributedSequence:
    sequence = oligo.sequence
    published = _published_fragments(result, plan)
    segments: list[AttributedSegment] = []

    prefix = oligo.five_prime_overhang
    suffix = oligo.three_prime_addition
    core_start = len(prefix)
    core_end = len(sequence) - len(suffix)

    if prefix:
        rule = published.get(prefix)
        if rule is not None:
            segments.append(
                AttributedSegment(
                    start=0,
                    end=core_start,
                    origin=SequenceOrigin.PUBLISHED_RULE,
                    source=f"cloning_vector:{plan.vector_id}:{plan.vector_name}",
                    rule=rule,
                    detail="5' cloning overhang",
                )
            )
    if suffix:
        rule = published.get(suffix)
        if rule is not None:
            segments.append(
                AttributedSegment(
                    start=core_end,
                    end=len(sequence),
                    origin=SequenceOrigin.PUBLISHED_RULE,
                    source=f"cloning_vector:{plan.vector_id}:{plan.vector_name}",
                    rule=rule,
                    detail="3' addition from the published protocol",
                )
            )

    core = sequence[core_start:core_end]
    segments.extend(
        _core_segments(
            result,
            guide,
            plan,
            core,
            offset=core_start,
            spacer_attributable=spacer_attributable,
        )
    )
    return AttributedSequence(
        name=f"oligo:{oligo.name}",
        sequence=sequence,
        segments=segments,
        role=oligo.role,
    )


def _core_segments(
    result: GuideRNAResult,
    guide: RankedGuide,
    plan: CloningPlan,
    core: str,
    *,
    offset: int,
    spacer_attributable: bool,
) -> list[AttributedSegment]:
    """The spans of an oligo's core, which is the spacer plus at most one added base."""
    if not core:
        return []
    template = IVT_TEMPLATES.get(result.nuclease)
    if template is not None and core == template.constant_oligo:
        return [
            AttributedSegment(
                start=offset,
                end=offset + len(core),
                origin=SequenceOrigin.PUBLISHED_RULE,
                source=f"cloning_vector:{plan.vector_id}:{plan.vector_name}",
                rule=(
                    f"published constant T7 scaffold oligo for {result.nuclease}, read from "
                    f"{template.source}. It carries no guide specific sequence."
                ),
                detail="constant scaffold oligo",
            )
        ]
    if not spacer_attributable:
        return []
    for written, orientation in ((guide.spacer, "sense"), (reverse_complement(guide.spacer), "antisense")):
        index = core.find(written)
        if index < 0:
            continue
        lead = core[:index]
        trail = core[index + len(written) :]
        if len(lead) > 1 or len(trail) > 1:
            return []
        if lead and lead != "G":
            return []
        if trail and trail != "C":
            return []
        segments: list[AttributedSegment] = []
        if lead:
            segments.append(
                AttributedSegment(
                    start=offset,
                    end=offset + 1,
                    origin=SequenceOrigin.PUBLISHED_RULE,
                    source=f"cloning_vector:{plan.vector_id}:{plan.vector_name}",
                    rule=FIVE_PRIME_G_RULE,
                    detail="single G added by the published protocol rule",
                )
            )
        segments.append(
            AttributedSegment(
                start=offset + index,
                end=offset + index + len(written),
                origin=SequenceOrigin.USER_INPUT,
                source=_target_source(result),
                detail=(
                    f"spacer {guide.guide_id}, {orientation} orientation, from the user's target "
                    f"at ({guide.placement.spacer_start}, {guide.placement.spacer_end})"
                ),
            )
        )
        if trail:
            segments.append(
                AttributedSegment(
                    start=offset + index + len(written),
                    end=offset + index + len(written) + 1,
                    origin=SequenceOrigin.PUBLISHED_RULE,
                    source=f"cloning_vector:{plan.vector_id}:{plan.vector_name}",
                    rule=FIVE_PRIME_G_RULE,
                    detail="matching C added by the published protocol rule",
                )
            )
        return segments
    return []


def grna_subject(
    result: GuideRNAResult,
    *,
    validator_version: str,
    target_sequence: str,
    declared_provenance: list[str] | None = None,
) -> ExportSubject:
    """Build the `ExportSubject` for one guide RNA design run.

    `target_sequence` is the user's own target from the request. It is required
    rather than optional: a spacer can only be attributed by locating it on the
    sequence the user supplied, and a subject built without it would attribute
    nothing, which blocks.
    """
    target = target_sequence.strip().upper()
    sequences: list[AttributedSequence] = []
    for guide in result.guides_returned:
        attributable = _spacer_is_on_target(target, guide)
        spacer_segments: list[AttributedSegment] = []
        if attributable:
            spacer_segments.append(
                AttributedSegment(
                    start=0,
                    end=len(guide.spacer),
                    origin=SequenceOrigin.USER_INPUT,
                    source=_target_source(result),
                    detail=(
                        f"spacer window ({guide.placement.spacer_start}, "
                        f"{guide.placement.spacer_end}) on strand {guide.placement.strand:+d}"
                    ),
                )
            )
        sequences.append(
            AttributedSequence(
                name=f"spacer:{guide.guide_id}",
                sequence=guide.spacer,
                segments=spacer_segments,
                role="spacer",
            )
        )
        if guide.cloning is None:
            continue
        for oligo in guide.cloning.oligos:
            sequences.append(
                _oligo_sequence(
                    result,
                    guide,
                    guide.cloning,
                    oligo,
                    spacer_attributable=attributable,
                )
            )
    return ExportSubject(
        capability=CapabilityKind.GUIDE_RNA,
        design_id=result.design_id,
        validator_version=validator_version,
        sequences=sequences,
        declared_provenance=list(
            declared_provenance if declared_provenance is not None else result.provenance
        ),
        adapter=ADAPTER_NAME,
    )


__all__ = ["ADAPTER_NAME", "FIVE_PRIME_G_RULE", "grna_subject"]
