"""Guide enumeration and placement resolution (section 8.3).

Section 8.3, verbatim:

    For the chosen nuclease, scan both strands for every valid PAM and extract
    the corresponding protospacer at the correct offset and orientation.

    * Cas12a's PAM is 5' of the spacer, not 3' like Cas9. Hard-coding a 3'
      offset will silently produce garbage guides for Cas12a.
    * Scan both strands. A guide targeting the reverse strand is equally valid,
      and reporting only forward-strand guides halves the design space for no
      reason.

How both requirements are met structurally rather than by care:

* Both strands are scanned by scanning one *view* of the target per strand. The
  reverse-strand view is `reverse_complement(target)`, so the offset rule is
  written once and applied twice. A reverse-strand guide can therefore not be
  forgotten without deleting a loop iteration.
* The offset rule itself lives in `nuclease.spacer_interval` and
  `nuclease.pam_interval`, which branch on `NucleaseSpec.pam_side`. There is no
  3' offset anywhere in this module.

PAM matching uses the shared `find_iupac` utility so `N`, `R` and `V` are
expanded in one place (Appendix C).

Everything here is deterministic: enumeration order is PAM motif order
(primary before alternative), then strand +1 before strand -1, then ascending
guide-strand position, and the returned list is finally sorted by forward
coordinates with explicit tie-breaks.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.core.schemas.grna import GuideRNARequest, GuideSpec, Placement
from packages.core.sequence import clean_sequence, find_iupac, reverse_complement

from .nuclease import (
    NucleaseSpec,
    cut_sites,
    get_nuclease,
    pam_interval,
    pam_matches,
    spacer_interval,
    strand_view,
    to_forward,
    to_forward_position,
)

#: Number of nucleotides 5' of the spacer that the Rule Set 1 on-target model
#: needs as context, and number 3' of the PAM. Source: the model's own input
#: specification, a 30 nt window made of 4 nt 5' flank, the 20 nt spacer, the
#: 3 nt PAM and a 3 nt 3' flank. See `ontarget.py` for the citation.
CONTEXT_FLANK_5 = 4
CONTEXT_FLANK_3 = 3


@dataclass(frozen=True)
class EnumeratedGuide:
    """One candidate guide, with its placement already resolved."""

    spacer: str
    pam: str
    pam_motif: str
    pam_is_alternative: bool
    placement: Placement

    @property
    def guide_id(self) -> str:
        """Stable, deterministic identifier: strand, start and spacer."""
        strand = "fwd" if self.placement.strand == 1 else "rev"
        return f"{strand}_{self.placement.spacer_start}_{self.spacer}"

    def to_spec(self) -> GuideSpec:
        return GuideSpec(
            spacer=self.spacer,
            pam=self.pam,
            strand=self.placement.strand,
            spacer_start=self.placement.spacer_start,
        )


def _context_30mer(view: str, spec: NucleaseSpec, spacer_start: int, spacer_end: int) -> str | None:
    """The guide-strand context window the published on-target model requires.

    Returns None when the target does not extend far enough, which is a real
    condition and becomes an UNKNOWN score rather than a padded guess.
    """
    if spec.pam_side != "three_prime":
        return None
    start = spacer_start - CONTEXT_FLANK_5
    end = spacer_end + spec.pam_length + CONTEXT_FLANK_3
    if start < 0 or end > len(view):
        return None
    return view[start:end]


def _place(
    view: str,
    target_length: int,
    spec: NucleaseSpec,
    strand: int,
    spacer_start: int,
    spacer_end: int,
) -> Placement:
    """Build a `Placement` from a resolved guide-strand spacer interval."""
    pam_start_view, pam_end_view = pam_interval(spec, spacer_start, spacer_end)
    primary_cut_view, staggered_cut_view = cut_sites(spec, spacer_start, spacer_end)
    spacer_fwd = to_forward(target_length, strand, spacer_start, spacer_end)
    pam_fwd = to_forward(target_length, strand, pam_start_view, pam_end_view)
    return Placement(
        strand=strand,
        spacer_start=spacer_fwd[0],
        spacer_end=spacer_fwd[1],
        pam_start=pam_fwd[0],
        pam_end=pam_fwd[1],
        pam_observed=view[pam_start_view:pam_end_view],
        pam_side=spec.pam_side,
        cut_site=to_forward_position(target_length, strand, primary_cut_view),
        cut_site_staggered=(
            None
            if staggered_cut_view is None
            else to_forward_position(target_length, strand, staggered_cut_view)
        ),
        context_30mer=_context_30mer(view, spec, spacer_start, spacer_end),
    )


def enumerate_guides(target_sequence: str, nuclease: str) -> list[EnumeratedGuide]:
    """Every valid guide on both strands of `target_sequence` for `nuclease`.

    A position is discarded only when the spacer would run off the end of the
    sequence. Overlapping guides are all returned, because they are all real.
    """
    spec = get_nuclease(nuclease)
    target = clean_sequence(target_sequence)
    length = len(target)
    found: list[EnumeratedGuide] = []
    for motif, is_alternative in spec.pam_motifs():
        for strand in (1, -1):
            view = strand_view(target, strand)
            for hit in find_iupac(view, motif, both_strands=False):
                spacer_start, spacer_end = spacer_interval(spec, hit.start, hit.end)
                if spacer_start < 0 or spacer_end > length:
                    continue
                placement = _place(view, length, spec, strand, spacer_start, spacer_end)
                found.append(
                    EnumeratedGuide(
                        spacer=view[spacer_start:spacer_end],
                        pam=view[hit.start : hit.end],
                        pam_motif=motif,
                        pam_is_alternative=is_alternative,
                        placement=placement,
                    )
                )
    found.sort(
        key=lambda guide: (
            guide.placement.spacer_start,
            -guide.placement.strand,
            guide.pam_is_alternative,
            guide.spacer,
        )
    )
    return found


@dataclass(frozen=True)
class ResolvedPlacement:
    """The outcome of locating a `GuideSpec` on its target.

    `placement` is None when the spacer could not be located, and `reason` then
    says why. A check that needs coordinates reports UNKNOWN with that reason
    rather than guessing (section 3.3 constraint 4).
    """

    placement: Placement | None
    reason: str | None = None
    ambiguous_positions: tuple[int, ...] = ()


def resolve_placement(request: GuideRNARequest, guide: GuideSpec) -> ResolvedPlacement:
    """Work out where `guide` sits on `request.target_sequence`.

    Two modes:

    * `guide.spacer_start` given: trusted as the authoritative position, so a
      gold case can assert a deliberately wrong placement and see it caught.
    * `guide.spacer_start` absent: the spacer is located on the strand the guide
      declares. Exactly one occurrence must exist; zero or several is reported
      as a reason rather than resolved by picking one.

    The PAM interval and the cut sites always come from the nuclease geometry,
    never from the caller, which is what makes a wrong PAM offset visible.
    """
    spec = get_nuclease(request.nuclease)
    target = clean_sequence(request.target_sequence)
    length = len(target)
    spacer = clean_sequence(guide.spacer)
    view = strand_view(target, guide.strand)

    if guide.spacer_start is None:
        occurrences = tuple(
            index for index in range(len(view) - len(spacer) + 1) if view.startswith(spacer, index)
        )
        if not occurrences:
            other = reverse_complement(spacer)
            hint = (
                " The reverse complement of the spacer does occur in the target, so the strand "
                "may be stated the wrong way round."
                if other in view or other in target
                else ""
            )
            return ResolvedPlacement(
                None,
                reason=(
                    f"The spacer {spacer} does not occur on the "
                    f"{'forward' if guide.strand == 1 else 'reverse'} strand of target "
                    f"{request.target_name}.{hint} Supply spacer_start, or correct the spacer."
                ),
            )
        if len(occurrences) > 1:
            return ResolvedPlacement(
                None,
                reason=(
                    f"The spacer {spacer} occurs {len(occurrences)} times on the "
                    f"{'forward' if guide.strand == 1 else 'reverse'} strand of target "
                    f"{request.target_name}, so its position is ambiguous. Supply spacer_start to "
                    "say which occurrence is meant."
                ),
                ambiguous_positions=occurrences,
            )
        start_view = occurrences[0]
    else:
        # spacer_start is a forward coordinate; convert it to the guide-strand view.
        forward_start = guide.spacer_start
        forward_end = forward_start + len(spacer)
        if forward_end > length:
            return ResolvedPlacement(
                None,
                reason=(
                    f"spacer_start {forward_start} plus a {len(spacer)} nt spacer runs past the end "
                    f"of the {length} nt target {request.target_name}. Correct spacer_start."
                ),
            )
        start_view = forward_start if guide.strand == 1 else length - forward_end

    end_view = start_view + len(spacer)
    pam_start_view, pam_end_view = pam_interval(spec, start_view, end_view)
    if pam_start_view < 0 or pam_end_view > length:
        side = "5' of the spacer" if spec.pam_side == "five_prime" else "3' of the spacer"
        return ResolvedPlacement(
            None,
            reason=(
                f"{spec.name} places its {spec.pam_motif} PAM {side}, and there are not "
                f"{spec.pam_length} nucleotides there: the spacer sits at the edge of the "
                f"{length} nt target. Move the guide inwards or supply more flanking sequence."
            ),
        )
    return ResolvedPlacement(_place(view, length, spec, guide.strand, start_view, end_view))


def seed_positions(spec: NucleaseSpec, spacer_length: int, seed_region_nt: int) -> frozenset[int]:
    """The 1-based spacer positions inside the PAM-proximal seed window.

    Appendix C: the seed is 8 to 12 nt PAM-proximal, configurable. Which end
    that is depends entirely on `pam_side`, so a Cas12a seed is the 5' end of
    the spacer and a Cas9 seed is the 3' end.
    """
    width = min(seed_region_nt, spacer_length)
    if spec.pam_side == "three_prime":
        return frozenset(range(spacer_length - width + 1, spacer_length + 1))
    return frozenset(range(1, width + 1))


def pam_at(
    target: str,
    spec: NucleaseSpec,
    strand: int,
    spacer_start_forward: int,
    spacer_length: int,
) -> tuple[str, bool, bool] | None:
    """The PAM the target actually carries for a candidate protospacer.

    Returns `(pam, matches, is_alternative)`, or None when the PAM window falls
    outside the sequence. Used by the off-target search, where a protospacer
    match only matters if a usable PAM sits beside it.
    """
    sequence = clean_sequence(target)
    length = len(sequence)
    view = strand_view(sequence, strand)
    start_view = (
        spacer_start_forward
        if strand == 1
        else length - (spacer_start_forward + spacer_length)
    )
    end_view = start_view + spacer_length
    pam_start_view, pam_end_view = pam_interval(spec, start_view, end_view)
    if pam_start_view < 0 or pam_end_view > length:
        return None
    pam = view[pam_start_view:pam_end_view]
    matches, is_alternative = pam_matches(spec, pam)
    return pam, matches, is_alternative
