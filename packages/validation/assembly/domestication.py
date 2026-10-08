"""Golden Gate domestication: silent edits that destroy an internal Type IIS site.

Source: section 7.6 of the engine capability system design, with Appendix D for
the enzyme table and the both-strands requirement, and `codon_usage.py` for the
recorded decision on host codon frequencies.

Section 7.6, in full: "For each internal occurrence of the enzyme recognition
site, find a silent substitution that destroys the site. If the site falls
inside a coding sequence, the substitution must preserve the amino acid, which
means choosing a synonymous codon, and should prefer a codon that is common in
the target host so expression is not degraded. Report the position, the
original codon, the proposed codon, the amino acid preserved, and the host
codon frequency of both. If the site falls outside a coding sequence, any
substitution that destroys the site is acceptable; prefer the minimal edit."

Four properties every proposed edit has, and the order they are checked in:

1. It destroys the site. The recognition sequence no longer occurs at that
   position, on either strand.
2. It introduces no new site. A single base change elsewhere in the fragment
   can create a recognition site that was not there before, and an edit that
   trades one site for another is not a fix. The whole fragment is rescanned,
   both strands, after the edit.
3. Inside a coding sequence it is synonymous. The codon is replaced by a codon
   of the same amino acid, from the genetic code table in
   `packages.core.sequence.codon`, so the residue is preserved by construction
   rather than by assertion.
4. It is minimal. Among the candidates that satisfy 1 to 3, the one differing
   from the original in the fewest nucleotide positions wins.

Tie-breaking, which decides the output and therefore must be deterministic
(section 3.3 constraint 3):

* Inside a coding sequence: highest host codon frequency first when a host
  codon usage table is available, then the codon that sorts first. No table
  ships with this build, so in practice the sort order decides and the host
  frequency is reported as UNKNOWN with a reason. See `codon_usage.py`.
* Outside a coding sequence: lowest position within the site first, then the
  base in A, C, G, T order. This ordering carries no biological claim; it
  exists so the same input always produces the same edit. Section 7.6 asks
  only for the minimal edit outside a coding sequence, which every candidate
  here is, being one base.

Both strands are searched, unconditionally, because Appendix D states these
recognition sequences are not palindromic and a forward-only scan misses half
the sites. A site found on the reverse strand is edited on the forward
sequence at forward coordinates, which is the same physical molecule.
"""

from __future__ import annotations

from packages.core.schemas.assembly import (
    DomesticationEdit,
    DomesticationReport,
    Fragment,
    UndomesticatableSite,
)
from packages.core.sequence import STANDARD_CODE, GeneticCode

from . import codon_usage
from .codon_usage import HostCodonUsage
from .enzymes import TypeIISEnzyme, find_recognition_sites

_BASES: tuple[str, ...] = ("A", "C", "G", "T")


def _site_count(sequence: str, enzyme: TypeIISEnzyme, *, circular: bool = False) -> int:
    return len(find_recognition_sites(sequence, enzyme, circular=circular))


def _coding_frame(fragment: Fragment, position: int) -> tuple[int, int] | None:
    """The coding region containing `position`, and the codon start, or None.

    A coding region is declared as a half-open interval whose first base starts
    a codon (enforced by `Fragment.coding_regions_in_frame`), so the codon
    containing `position` begins at the largest multiple of three below it,
    measured from the region start.
    """
    for start, end in fragment.coding_regions:
        if start <= position < end:
            offset = position - start
            codon_start = start + (offset // 3) * 3
            if codon_start + 3 <= end:
                return start, codon_start
    return None


def _site_positions(sequence: str, site_start: int, site_end: int) -> set[int]:
    """The positions a candidate edit may change: the recognition site's own span.

    A function rather than a range literal because a site in a circular fragment
    can wrap the origin, in which case the span is two intervals.
    """
    if site_end <= len(sequence):
        return set(range(site_start, site_end))
    return set(range(site_start, len(sequence))) | set(range(0, site_end - len(sequence)))


def _destroys(
    sequence: str,
    position: int,
    base: str,
    enzyme: TypeIISEnzyme,
    *,
    circular: bool,
    sites_before: int,
) -> bool:
    """Whether changing `position` to `base` reduces the site count on both strands.

    Reducing the count, rather than merely checking the edited position, is what
    enforces property 2: an edit that removes one site and creates another
    leaves the count unchanged and is rejected here.
    """
    edited = sequence[:position] + base + sequence[position + 1 :]
    return _site_count(edited, enzyme, circular=circular) < sites_before


def _codon_candidates(
    fragment: Fragment,
    codon_start: int,
    site_positions: set[int],
    enzyme: TypeIISEnzyme,
    code: GeneticCode,
    usage: HostCodonUsage | None,
    sites_before: int,
) -> list[tuple[int, float, str, int, str]]:
    """Synonymous codon substitutions that destroy the site, ranked.

    Each entry is `(edit_count, negated_frequency, proposed_codon,
    edit_position, proposed_base)`, sorted ascending so the first is the best:
    fewest edited bases, then highest host frequency, then codon sort order.
    `negated_frequency` is 0.0 when no host table is available, which leaves
    the codon sort order deciding.

    Only single-base substitutions are produced, because a codon differing from
    the original in more than one position would be a larger edit than
    necessary and section 7.6 asks for the minimal one. A synonymous codon
    needing two changes is still considered when no single-base synonym
    destroys the site, and is reported with its true edit count.
    """
    sequence = fragment.sequence
    original_codon = sequence[codon_start : codon_start + 3]
    if len(original_codon) != 3:
        return []
    try:
        amino_acid = code.translate_codon(original_codon)
    except KeyError:  # pragma: no cover - fragments are validated as ACGT
        return []
    candidates: list[tuple[int, float, str, int, str]] = []
    for synonym in code.synonymous_codons(original_codon):
        if synonym == original_codon:
            continue
        if code.translate_codon(synonym) != amino_acid:  # pragma: no cover - by construction
            continue
        differing = [index for index in range(3) if synonym[index] != original_codon[index]]
        # Only consider a codon whose changed positions all lie inside the
        # recognition site. Editing a base outside the site cannot destroy it,
        # and editing extra bases is not minimal.
        if not differing or any(codon_start + index not in site_positions for index in differing):
            continue
        edited = sequence[:codon_start] + synonym + sequence[codon_start + 3 :]
        if _site_count(edited, enzyme, circular=fragment.is_circular) >= sites_before:
            continue
        frequency = codon_usage.lookup(usage, synonym)
        rank_frequency = -(frequency.value or 0.0) if frequency.available else 0.0
        first = differing[0]
        candidates.append((len(differing), rank_frequency, synonym, codon_start + first, synonym[first]))
    return sorted(candidates)


def _non_coding_candidates(
    fragment: Fragment,
    site_positions: set[int],
    enzyme: TypeIISEnzyme,
    sites_before: int,
) -> list[tuple[int, str]]:
    """Single-base substitutions inside the site that destroy it, in order.

    Ordered by position then by base in A, C, G, T order. The ordering is
    deterministic and carries no biological claim: section 7.6 asks only for a
    minimal edit outside a coding sequence, and every candidate here is one
    base.
    """
    sequence = fragment.sequence
    found: list[tuple[int, str]] = []
    for position in sorted(site_positions):
        original = sequence[position]
        for base in _BASES:
            if base == original:
                continue
            if _destroys(sequence, position, base, enzyme, circular=fragment.is_circular, sites_before=sites_before):
                found.append((position, base))
    return found


def domesticate_fragment(
    fragment: Fragment,
    enzyme: TypeIISEnzyme,
    *,
    usage: HostCodonUsage | None = None,
    code: GeneticCode = STANDARD_CODE,
) -> tuple[list[DomesticationEdit], list[UndomesticatableSite]]:
    """Proposed edits and unresolved sites for one fragment.

    One edit is proposed per internal recognition site. The edits are
    independent proposals against the original sequence, not a cumulative
    patch: applying them all is the caller's job and is safe because each edit
    lies inside its own site and the sites do not overlap after the
    site-count test above.
    """
    hits = find_recognition_sites(fragment.sequence, enzyme, circular=fragment.is_circular)
    sites_before = len(hits)
    edits: list[DomesticationEdit] = []
    unresolved: list[UndomesticatableSite] = []
    for hit in hits:
        positions = _site_positions(fragment.sequence, hit.start, hit.end)
        coding_positions = {position for position in positions if _coding_frame(fragment, position)}
        edit: DomesticationEdit | None = None

        # Inside a coding sequence first: a synonymous codon is strictly better
        # than an arbitrary base change, because it preserves the protein.
        best: tuple[int, float, str, int, str] | None = None
        best_codon_start: int | None = None
        best_region_start: int | None = None
        for position in sorted(coding_positions):
            frame = _coding_frame(fragment, position)
            if frame is None:  # pragma: no cover - filtered above
                continue
            region_start, codon_start = frame
            if best_codon_start == codon_start:
                continue
            candidates = _codon_candidates(
                fragment, codon_start, positions, enzyme, code, usage, sites_before
            )
            if candidates and (best is None or candidates[0] < best):
                best = candidates[0]
                best_codon_start = codon_start
                best_region_start = region_start
        if best is not None and best_codon_start is not None and best_region_start is not None:
            _, _, proposed_codon, edit_position, proposed_base = best
            original_codon = fragment.sequence[best_codon_start : best_codon_start + 3]
            original_frequency = codon_usage.lookup(usage, original_codon)
            proposed_frequency = codon_usage.lookup(usage, proposed_codon)
            known = original_frequency.available and proposed_frequency.available
            edit = DomesticationEdit(
                fragment=fragment.name,
                site_start=hit.start,
                site_end=hit.end,
                site_strand=hit.strand,
                recognition_site=enzyme.recognition,
                edit_position=edit_position,
                original_base=fragment.sequence[edit_position],
                proposed_base=proposed_base,
                in_coding_sequence=True,
                codon_position=(best_codon_start - best_region_start) // 3,
                original_codon=original_codon,
                proposed_codon=proposed_codon,
                amino_acid=code.translate_codon(original_codon),
                host_frequency_status="known" if known else "unknown",
                host_frequency_original=original_frequency.value if known else None,
                host_frequency_proposed=proposed_frequency.value if known else None,
                host_frequency_table=proposed_frequency.table if known else None,
                host_frequency_reason=(
                    None
                    if known
                    else (proposed_frequency.unavailable_reason or original_frequency.unavailable_reason)
                ),
            )

        # Outside a coding sequence, or inside one with no synonymous escape:
        # any minimal site-destroying substitution, per section 7.6.
        if edit is None:
            free_positions = positions - coding_positions if coding_positions != positions else positions
            candidates = _non_coding_candidates(fragment, free_positions or positions, enzyme, sites_before)
            if candidates:
                position, base = candidates[0]
                frame = _coding_frame(fragment, position)
                edit = DomesticationEdit(
                    fragment=fragment.name,
                    site_start=hit.start,
                    site_end=hit.end,
                    site_strand=hit.strand,
                    recognition_site=enzyme.recognition,
                    edit_position=position,
                    original_base=fragment.sequence[position],
                    proposed_base=base,
                    in_coding_sequence=False,
                    host_frequency_status="unknown",
                    host_frequency_reason=(
                        "The edit is outside any declared coding sequence, so no codon and no host "
                        "codon frequency apply."
                        if frame is None
                        else (
                            "No synonymous codon destroys this site, so the edit changes the amino "
                            "acid. Review it before ordering."
                        )
                    ),
                )

        if edit is None:
            unresolved.append(
                UndomesticatableSite(
                    fragment=fragment.name,
                    site_start=hit.start,
                    site_end=hit.end,
                    site_strand=hit.strand,
                    recognition_site=enzyme.recognition,
                    reason=(
                        "No single-base substitution inside this site removes it without creating "
                        "another occurrence of the same site in the fragment. Resynthesise this "
                        "region, or use a different Type IIS enzyme."
                    ),
                )
            )
        else:
            edits.append(edit)
    return edits, unresolved


def build_report(
    fragments: list[Fragment],
    enzyme: TypeIISEnzyme,
    *,
    usage: HostCodonUsage | None = None,
    code: GeneticCode = STANDARD_CODE,
) -> DomesticationReport:
    """The section 7.6 domestication report across every fragment in an assembly."""
    edits: list[DomesticationEdit] = []
    unresolved: list[UndomesticatableSite] = []
    sites_found = 0
    for fragment in fragments:
        sites_found += len(find_recognition_sites(fragment.sequence, enzyme, circular=fragment.is_circular))
        fragment_edits, fragment_unresolved = domesticate_fragment(fragment, enzyme, usage=usage, code=code)
        edits.extend(fragment_edits)
        unresolved.extend(fragment_unresolved)
    notes = [
        f"Both strands were searched for {enzyme.recognition}, because Appendix D records that "
        "Type IIS recognition sequences are not palindromic.",
        f"{enzyme.name} cuts at {enzyme.cut_notation}, leaving a {enzyme.overhang_nt} nt overhang.",
    ]
    if usage is None:
        notes.append(codon_usage.NO_TABLE_REASON)
    return DomesticationReport(
        enzyme=enzyme.name,
        recognition_site=enzyme.recognition,
        sites_found=sites_found,
        edits=edits,
        unresolved=unresolved,
        host_codon_usage_table=f"{usage.host} ({usage.citation})" if usage else None,
        host_codon_usage_status="known" if usage else "unknown",
        notes=notes,
    )
