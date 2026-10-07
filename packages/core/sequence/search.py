"""Sequence search primitives: exact, mismatch-tolerant, IUPAC motif, repeats, runs.

Source: section 13.4 of the engine capability system design (sequence search
primitives needed by the primer and guide RNA capabilities, and by the AAV
repeat and homopolymer checks). These are plain string algorithms with no
tunable biological constants: every length, mismatch count and window is a
required argument supplied, and cited, by the calling capability.

All positions are zero-based. Intervals are start inclusive, end exclusive.
"""

from __future__ import annotations

from dataclasses import dataclass

from .dna import IUPAC_CODES, clean_sequence, reverse_complement


@dataclass(frozen=True)
class Hit:
    """A match of a pattern against a sequence.

    `strand` is +1 when the pattern matches the supplied sequence and -1 when it
    matches the reverse complement. For strand -1, `start` and `end` are given
    on the supplied (forward) sequence so they can be used directly as
    coordinates. `mismatches` is 0 for exact search.
    """

    start: int
    end: int
    strand: int
    mismatches: int = 0


def find_exact(sequence: str, pattern: str, *, circular: bool = False) -> list[int]:
    """Start positions of every occurrence of `pattern`, overlapping ones included.

    With `circular`, occurrences that span the origin are found and reported by
    their start position in the supplied sequence. The pattern may not be longer
    than the sequence in circular mode.
    """
    text = clean_sequence(sequence)
    needle = clean_sequence(pattern)
    if circular:
        if len(needle) > len(text):
            raise ValueError("pattern is longer than the circular sequence")
        text_scan = text + text[: len(needle) - 1]
        limit = len(text)
    else:
        text_scan = text
        limit = len(text) - len(needle) + 1
    hits: list[int] = []
    index = text_scan.find(needle)
    while index != -1 and index < limit:
        hits.append(index)
        index = text_scan.find(needle, index + 1)
    return hits


def find_both_strands(sequence: str, pattern: str, *, circular: bool = False) -> list[Hit]:
    """Exact matches of `pattern` on the sequence and on its reverse complement.

    A palindromic pattern matches both strands at the same place and is reported
    twice, once per strand, because both strands are genuinely cut or bound.
    """
    text = clean_sequence(sequence)
    needle = clean_sequence(pattern)
    hits = [Hit(pos, pos + len(needle), 1) for pos in find_exact(text, needle, circular=circular)]
    for pos in find_exact(text, reverse_complement(needle), circular=circular):
        hits.append(Hit(pos, pos + len(needle), -1))
    return sorted(hits, key=lambda hit: (hit.start, -hit.strand))


def hamming_distance(first: str, second: str) -> int:
    """Number of differing positions between two equal-length sequences."""
    a = clean_sequence(first, allow_ambiguous=True)
    b = clean_sequence(second, allow_ambiguous=True)
    if len(a) != len(b):
        raise ValueError("hamming distance needs sequences of equal length")
    return sum(1 for x, y in zip(a, b) if x != y)


def find_with_mismatches(
    sequence: str,
    pattern: str,
    *,
    max_mismatches: int,
    both_strands: bool = True,
) -> list[Hit]:
    """Substitution-only matches of `pattern` within `max_mismatches`.

    This is a Hamming-distance scan: no insertions or deletions. `max_mismatches`
    is required because the tolerance is a design choice of the caller (for
    example the off-target search in section 8.6). Hits on the reverse strand
    are reported with strand -1 and forward coordinates.
    """
    if max_mismatches < 0:
        raise ValueError("max_mismatches must not be negative")
    text = clean_sequence(sequence)
    needle = clean_sequence(pattern)
    width = len(needle)
    targets = [(1, needle)]
    if both_strands:
        targets.append((-1, reverse_complement(needle)))
    hits: list[Hit] = []
    for strand, target in targets:
        for start in range(len(text) - width + 1):
            window = text[start : start + width]
            mismatches = 0
            for a, b in zip(window, target):
                if a != b:
                    mismatches += 1
                    if mismatches > max_mismatches:
                        break
            if mismatches <= max_mismatches:
                hits.append(Hit(start, start + width, strand, mismatches))
    return sorted(hits, key=lambda hit: (hit.start, -hit.strand))


def matches_iupac(window: str, motif: str) -> bool:
    """True when `window` (unambiguous bases) satisfies the IUPAC `motif` at every position."""
    if len(window) != len(motif):
        return False
    for base, code in zip(window.upper(), motif.upper()):
        allowed = IUPAC_CODES.get(code)
        if allowed is None:
            raise ValueError(f"unsupported IUPAC code {code!r} in motif {motif!r}")
        if base not in allowed:
            return False
    return True


def find_iupac(sequence: str, motif: str, *, both_strands: bool = True) -> list[Hit]:
    """Occurrences of an IUPAC motif such as a PAM (Appendix C, for example `NGG`).

    For strand -1 the motif is matched against the reverse complement of the
    sequence, and `start` and `end` are forward coordinates of the matched
    window. Overlapping occurrences are all reported.
    """
    text = clean_sequence(sequence)
    pattern = clean_sequence(motif, allow_ambiguous=True)
    width = len(pattern)
    hits: list[Hit] = []
    for start in range(len(text) - width + 1):
        if matches_iupac(text[start : start + width], pattern):
            hits.append(Hit(start, start + width, 1))
    if both_strands:
        reverse = reverse_complement(text)
        total = len(text)
        for start in range(len(reverse) - width + 1):
            if matches_iupac(reverse[start : start + width], pattern):
                hits.append(Hit(total - start - width, total - start, -1))
    return sorted(hits, key=lambda hit: (hit.start, -hit.strand))


@dataclass(frozen=True)
class Run:
    """A homopolymer run: `length` copies of `base` from `start` to `end`."""

    start: int
    end: int
    base: str

    @property
    def length(self) -> int:
        return self.end - self.start


def homopolymer_runs(sequence: str, *, min_length: int) -> list[Run]:
    """Every maximal run of one repeated base that is at least `min_length` long.

    `min_length` is required: the length at which a run becomes a problem is a
    configurable threshold owned by the calling capability (for example
    MAX_HOMOPOLYMER_RUN in section 6.5, where a run is flagged when it is
    longer than the maximum).
    """
    if min_length < 2:
        raise ValueError("min_length must be at least 2")
    text = clean_sequence(sequence, allow_ambiguous=True)
    runs: list[Run] = []
    start = 0
    for index in range(1, len(text) + 1):
        if index == len(text) or text[index] != text[start]:
            if index - start >= min_length:
                runs.append(Run(start, index, text[start]))
            start = index
    return runs


@dataclass(frozen=True)
class Repeat:
    """A direct repeat: the same `length` bases at `first` and at `second` (first < second)."""

    first: int
    second: int
    length: int


def direct_repeats(sequence: str, *, min_length: int) -> list[Repeat]:
    """Maximal non-overlapping direct repeats of at least `min_length` bases.

    A repeat is reported once, at its maximal extent: it cannot be extended to the
    left or to the right while both copies still match and stay non-overlapping.
    Homopolymers and short tandem units therefore yield a repeat only when two
    full, separate copies of at least `min_length` bases exist. `min_length` is
    required because the length at which a repeat risks recombination is a
    configurable threshold (MAX_DIRECT_REPEAT_BP in section 6.5, where a repeat
    is flagged when it is longer than the maximum).

    Cost is quadratic in the worst case, which is acceptable for AAV cassettes
    of a few kilobases.
    """
    if min_length < 1:
        raise ValueError("min_length must be at least 1")
    text = clean_sequence(sequence, allow_ambiguous=True)
    size = len(text)
    positions: dict[str, list[int]] = {}
    for index in range(size - min_length + 1):
        positions.setdefault(text[index : index + min_length], []).append(index)
    repeats: list[Repeat] = []
    for starts in positions.values():
        for left_index, first in enumerate(starts):
            for second in starts[left_index + 1 :]:
                if first > 0 and second > 0 and text[first - 1] == text[second - 1]:
                    continue  # not left-maximal: reported from the earlier start
                length = min_length
                while second + length < size and text[first + length] == text[second + length] and first + length < second:
                    length += 1
                if first + length > second:
                    length = second - first  # keep the two copies non-overlapping
                    if length < min_length:
                        continue
                repeats.append(Repeat(first, second, length))
    return sorted(repeats, key=lambda repeat: (repeat.first, repeat.second))
