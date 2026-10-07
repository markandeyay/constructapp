"""Pairwise alignment primitives with linear gap cost.

Sources:

* Global alignment: Needleman and Wunsch 1970, J Mol Biol 48:443-453,
  doi:10.1016/0022-2836(70)90057-4.
* Local alignment: Smith and Waterman 1981, J Mol Biol 147:195-197,
  doi:10.1016/0022-2836(81)90087-5.

Scores are not biological constants. A caller that needs a biologically
meaningful score (for example a nearest-neighbor stability, section 7.4) supplies
its own function; these routines only find the best alignment under the scoring
they are given. `AlignmentScoring` has no defaults for that reason. The named
`UNIT_COST_SCORING` is a convention (match +1, mismatch -1, gap -1) with no
biological meaning, offered for similarity and identity measurements such as the
ITR identity check in section 6.4 check 2, where the caller states the threshold
it applies to the resulting identity.

Ties between equally scoring paths are broken deterministically (diagonal, then
up, then left), so the same inputs always return the same alignment.

Memory and time are proportional to the product of the two lengths, which suits
parts and primers (tens to a few thousand bases). Do not run it on chromosomes.
"""

from __future__ import annotations

from dataclasses import dataclass

from .dna import clean_sequence


@dataclass(frozen=True)
class AlignmentScoring:
    """Score for a matched pair, a mismatched pair, and each gap position.

    `gap` is applied per gap position (linear gap cost) and is normally negative.
    """

    match: int
    mismatch: int
    gap: int


# A convention for similarity measurement, not a fitted biological model.
UNIT_COST_SCORING = AlignmentScoring(match=1, mismatch=-1, gap=-1)


@dataclass(frozen=True)
class Alignment:
    """Result of a pairwise alignment.

    `aligned_a` and `aligned_b` have equal length and use `-` for a gap.
    `start_a`/`end_a` and `start_b`/`end_b` are zero-based half-open intervals of
    the aligned region in each input (the whole input for a global alignment).
    """

    score: int
    aligned_a: str
    aligned_b: str
    start_a: int
    end_a: int
    start_b: int
    end_b: int

    @property
    def length(self) -> int:
        """Number of alignment columns."""
        return len(self.aligned_a)

    @property
    def matches(self) -> int:
        return sum(1 for x, y in zip(self.aligned_a, self.aligned_b) if x == y and x != "-")

    @property
    def mismatches(self) -> int:
        return sum(1 for x, y in zip(self.aligned_a, self.aligned_b) if x != y and x != "-" and y != "-")

    @property
    def gaps(self) -> int:
        return sum(1 for x, y in zip(self.aligned_a, self.aligned_b) if x == "-" or y == "-")

    @property
    def identity(self) -> float:
        """Matches divided by alignment columns, 0.0 for an empty alignment."""
        return self.matches / self.length if self.length else 0.0


def global_align(first: str, second: str, scoring: AlignmentScoring) -> Alignment:
    """Needleman-Wunsch global alignment of two sequences."""
    a = clean_sequence(first, allow_ambiguous=True)
    b = clean_sequence(second, allow_ambiguous=True)
    rows, cols = len(a) + 1, len(b) + 1
    score = [[0] * cols for _ in range(rows)]
    for i in range(1, rows):
        score[i][0] = i * scoring.gap
    for j in range(1, cols):
        score[0][j] = j * scoring.gap
    for i in range(1, rows):
        for j in range(1, cols):
            pair = scoring.match if a[i - 1] == b[j - 1] else scoring.mismatch
            score[i][j] = max(score[i - 1][j - 1] + pair, score[i - 1][j] + scoring.gap, score[i][j - 1] + scoring.gap)
    i, j = len(a), len(b)
    out_a: list[str] = []
    out_b: list[str] = []
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            pair = scoring.match if a[i - 1] == b[j - 1] else scoring.mismatch
            if score[i][j] == score[i - 1][j - 1] + pair:
                out_a.append(a[i - 1])
                out_b.append(b[j - 1])
                i, j = i - 1, j - 1
                continue
        if i > 0 and score[i][j] == score[i - 1][j] + scoring.gap:
            out_a.append(a[i - 1])
            out_b.append("-")
            i -= 1
        else:
            out_a.append("-")
            out_b.append(b[j - 1])
            j -= 1
    return Alignment(score[len(a)][len(b)], "".join(reversed(out_a)), "".join(reversed(out_b)), 0, len(a), 0, len(b))


def local_align(first: str, second: str, scoring: AlignmentScoring) -> Alignment:
    """Smith-Waterman local alignment: the best scoring aligned region of the two sequences.

    Returns an empty alignment (score 0, empty strings) when no positive scoring
    region exists. When several regions tie, the one ending first in `first`,
    then in `second`, is returned.
    """
    a = clean_sequence(first, allow_ambiguous=True)
    b = clean_sequence(second, allow_ambiguous=True)
    rows, cols = len(a) + 1, len(b) + 1
    score = [[0] * cols for _ in range(rows)]
    best, best_i, best_j = 0, 0, 0
    for i in range(1, rows):
        for j in range(1, cols):
            pair = scoring.match if a[i - 1] == b[j - 1] else scoring.mismatch
            value = max(0, score[i - 1][j - 1] + pair, score[i - 1][j] + scoring.gap, score[i][j - 1] + scoring.gap)
            score[i][j] = value
            if value > best:
                best, best_i, best_j = value, i, j
    if best == 0:
        return Alignment(0, "", "", 0, 0, 0, 0)
    i, j = best_i, best_j
    out_a: list[str] = []
    out_b: list[str] = []
    while i > 0 and j > 0 and score[i][j] > 0:
        pair = scoring.match if a[i - 1] == b[j - 1] else scoring.mismatch
        if score[i][j] == score[i - 1][j - 1] + pair:
            out_a.append(a[i - 1])
            out_b.append(b[j - 1])
            i, j = i - 1, j - 1
        elif score[i][j] == score[i - 1][j] + scoring.gap:
            out_a.append(a[i - 1])
            out_b.append("-")
            i -= 1
        else:
            out_a.append("-")
            out_b.append(b[j - 1])
            j -= 1
    return Alignment(best, "".join(reversed(out_a)), "".join(reversed(out_b)), i, best_i, j, best_j)


def edit_distance(first: str, second: str) -> int:
    """Levenshtein distance: the fewest substitutions, insertions and deletions."""
    a = clean_sequence(first, allow_ambiguous=True)
    b = clean_sequence(second, allow_ambiguous=True)
    previous = list(range(len(b) + 1))
    for i, base_a in enumerate(a, start=1):
        current = [i]
        for j, base_b in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (base_a != base_b)))
        previous = current
    return previous[-1]


def global_identity(first: str, second: str, scoring: AlignmentScoring = UNIT_COST_SCORING) -> float:
    """Identity of the global alignment of two sequences, matches over alignment columns.

    Used for comparisons such as an ITR against its serotype reference. Identity
    is lower than 1.0 whenever the lengths differ, because every gap column
    counts against it.
    """
    return global_align(first, second, scoring).identity
