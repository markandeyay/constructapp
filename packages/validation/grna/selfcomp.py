"""Internal self-complementarity of a spacer (section 8.5 check 6).

Section 8.5 check 6 asks for "no internal self-complementarity that would
disrupt the scaffold fold", with severity WARN. It names no threshold and no
method, and no published threshold exists for it.

Section 7.4 of the same design document, writing about primer hairpins, states
the method that is acceptable here:

    A full free energy minimisation is out of scope. A sliding-window
    complementarity score with explicit 3' weighting is sufficient and
    defensible, provided the scoring is documented.

So this module finds the longest perfectly complementary stem the spacer can
form with itself, subject to a minimum loop length, and reports it. There is no
free energy term and none is claimed. The threshold at which a stem is reported
(`max_self_complement_stem_nt`) and the minimum loop (`min_hairpin_loop_nt`)
are both configurable parameters documented in `constants.py` as Construct
conventions, not as published values.

Deterministic: the search is an exhaustive scan in a fixed order and ties are
broken by the earliest 5' stem start.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.core.sequence import clean_sequence, reverse_complement


@dataclass(frozen=True)
class Stem:
    """One self-complementary stem: `left` pairs with `right`, both zero-based.

    `left_start` to `left_start + length` pairs with
    `right_start` to `right_start + length`, reading the second span in reverse.
    `loop` is the number of unpaired nucleotides between the two spans.
    """

    left_start: int
    right_start: int
    length: int
    loop: int
    stem_sequence: str

    @property
    def left_end(self) -> int:
        return self.left_start + self.length

    @property
    def right_end(self) -> int:
        return self.right_start + self.length


def longest_self_complementary_stem(sequence: str, *, min_loop_nt: int) -> Stem | None:
    """The longest perfectly complementary intramolecular stem in `sequence`.

    A stem of length `n` starting at `i` on the 5' side pairs with the span of
    length `n` ending at `j` on the 3' side when
    `sequence[i:i+n] == reverse_complement(sequence[j-n:j])`, and the loop
    `j - n - (i + n)` is at least `min_loop_nt`.

    Returns None when no stem of at least 2 bp closes a long enough loop. Only
    the longest stem is returned because that is what the check reports; the
    check is a WARN and does not need an exhaustive structure.
    """
    text = clean_sequence(sequence)
    size = len(text)
    if min_loop_nt < 0:
        raise ValueError("min_loop_nt must not be negative")
    best: Stem | None = None
    for left_start in range(size):
        for right_end in range(size, left_start, -1):
            span = right_end - left_start
            # A stem of length n on each side plus a loop of at least min_loop_nt.
            max_length = (span - min_loop_nt) // 2
            for length in range(max_length, 1, -1):
                left = text[left_start : left_start + length]
                right = text[right_end - length : right_end]
                if left != reverse_complement(right):
                    continue
                loop = right_end - length - (left_start + length)
                candidate = Stem(
                    left_start=left_start,
                    right_start=right_end - length,
                    length=length,
                    loop=loop,
                    stem_sequence=left,
                )
                if best is None or (candidate.length, -candidate.left_start) > (
                    best.length,
                    -best.left_start,
                ):
                    best = candidate
                break  # longer stems at this pair of bounds were already tried
    return best
