"""Primer secondary structure: hairpins, self-dimers and hetero-dimers.

Source: section 7.4 of the engine capability system design, and open question
Q6 on ViennaRNA.

Section 7.4 states the biology that drives the scoring: "3' end involvement is
what matters, because a 3' dimer is extendable and produces primer-dimer
artifact that consumes the reaction." Every function here therefore reports two
numbers, one for the structure anywhere in the oligo and one for the structure
involving the 3' end, and the thresholds in `constants.py` are separate for the
two.

Section 7.4 also sets the scope: "A full free energy minimization is out of
scope. A sliding-window complementarity score with explicit 3' weighting is
sufficient and defensible, provided the scoring is documented. If ViennaRNA is
installable in the environment, prefer it for hairpin free energy and record
that choice."

THE Q6 DECISION, RECORDED. ViennaRNA is installable in this environment
(version 2.7.2, importable as `RNA`) and it is preferred for hairpin free
energy, with DNA parameters loaded rather than the default RNA parameters: a
primer is DNA, and folding it against RNA stacking parameters would report the
wrong energy with no warning. The DNA parameter set is the one ViennaRNA
distributes as `dna_mathews2004.par` and loads through
`RNA.params_load_DNA_Mathews2004()`.

ViennaRNA is an optional dependency, not a required one. It is imported
lazily and, when it is absent, the hairpin check falls back to the documented
sliding-window stem score below and says so in its message and in
`parameters_used`. Both paths are deterministic. Which path ran is never
inferred by the reader: `HairpinResult.engine` names it.

SCORING, DOCUMENTED. The complementarity score used for dimers, and for the
hairpin fallback, is a gapless sliding-window score in units of base pairs:

* Two oligos are scanned at every relative offset. The first is read 5' to 3'
  and the second is reversed, so that a base of one sits opposite the base of
  the other it would pair with. Only Watson-Crick pairs count (A with T, G with
  C); an ambiguity code or any other character never pairs.
* `any_score` is the best gapless local score over all offsets, where a
  complementary position scores +1 and a non-complementary position scores -1,
  and the best contiguous stretch within the overlap is taken. This is the same
  construction and the same units as Primer3's PRIMER_MAX_SELF_ANY and
  PRIMER_PAIR_MAX_COMPL_ANY, whose defaults of 8.00 are the thresholds in
  `constants.py`. The two numbers are not guaranteed identical to Primer3's,
  because Primer3's alignment implementation differs in detail, so the score
  definition used is recorded in `parameters_used` rather than claimed to be
  Primer3's output.
* `three_prime_score` is the longest run of consecutive complementary base
  pairs that includes the 3'-terminal base of the query oligo, maximised over
  offsets, in base pairs. An offset at which the 3'-terminal base is not itself
  paired scores zero, because an unpaired 3' terminus is not extendable and
  that is the whole reason section 7.4 singles the 3' end out. This is the
  explicit 3' weighting section 7.4 asks for, and the thresholds are Primer3's
  PRIMER_MAX_SELF_END and PRIMER_PAIR_MAX_COMPL_END defaults of 3.00, in the
  same base pair units.

A gapless scan is used rather than the shared `local_align` utility because
`local_align` admits gaps and has no 3' anchoring, and a gapped primer dimer is
not the failure mode being measured: an extendable 3' dimer is a contiguous
duplex.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache

from packages.core.sequence import clean_sequence, reverse_complement

# Watson-Crick pairs. Nothing else pairs: an ambiguity code in a primer is a
# synthesis instruction, not a base, and treating it as a wildcard would
# understate or overstate structure with no way for the reader to tell which.
_WATSON_CRICK: dict[str, str] = {"A": "T", "T": "A", "G": "C", "C": "G"}

# Engine labels reported in `HairpinResult.engine` and in `parameters_used`.
ENGINE_VIENNARNA = "viennarna_dna_mathews2004"
ENGINE_WINDOW = "sliding_window_stem_bp"


def _pairs(first: str, second: str) -> bool:
    return _WATSON_CRICK.get(first) == second


@dataclass(frozen=True)
class ComplementarityResult:
    """Scores for one oligo pair, in base pairs. See the module docstring.

    `any_score` is the best gapless local complementarity score at any offset.
    `three_prime_score` is the longest contiguous complementary run anchored at
    the query's 3'-terminal base. `three_prime_partner` records whose 3' end
    the run is anchored at, which matters for a hetero-dimer where either
    primer's 3' end may be the extendable one.
    """

    any_score: int
    three_prime_score: int
    three_prime_partner: str = "query"

    @property
    def three_prime_involved(self) -> bool:
        return self.three_prime_score > 0


def complementarity(first: str, second: str) -> ComplementarityResult:
    """Gapless sliding-window complementarity between two oligos, both 5' to 3'.

    Scoring is documented in the module docstring. `first` is the query whose
    3' end anchors `three_prime_score`. Passing the same sequence twice gives
    the self-dimer scores.
    """
    top = clean_sequence(first, allow_ambiguous=True)
    bottom = clean_sequence(second, allow_ambiguous=True)
    if not top or not bottom:
        raise ValueError("complementarity needs two non-empty sequences")
    # The second oligo is reversed so index arithmetic aligns bases that would
    # pair: top[i] sits opposite bottom_reversed[j] in an antiparallel duplex.
    reversed_bottom = bottom[::-1]
    best_any = 0
    best_three_prime = 0
    last_index = len(top) - 1
    for offset in range(-(len(reversed_bottom) - 1), len(top)):
        # Gapless local maximum (Kadane) over the aligned region.
        running = 0
        local_best = 0
        # Contiguous complementary run that is live at the query's 3' base.
        run = 0
        three_prime_run = 0
        for index in range(len(top)):
            partner_index = index - offset
            if partner_index < 0 or partner_index >= len(reversed_bottom):
                run = 0
                continue
            if _pairs(top[index], reversed_bottom[partner_index]):
                running = max(0, running) + 1
                run += 1
            else:
                running = max(0, running) - 1
                if running < 0:
                    running = 0
                run = 0
            local_best = max(local_best, running)
            if index == last_index and run > 0:
                three_prime_run = run
        best_any = max(best_any, local_best)
        best_three_prime = max(best_three_prime, three_prime_run)
    return ComplementarityResult(any_score=best_any, three_prime_score=best_three_prime)


def self_dimer(sequence: str) -> ComplementarityResult:
    """Self-dimer scores for one primer (section 7.5 check 7)."""
    return complementarity(sequence, sequence)


def hetero_dimer(forward: str, reverse: str) -> ComplementarityResult:
    """Hetero-dimer scores for a primer pair (section 7.5 check 8).

    Both primers' 3' ends are tested and the worse of the two is reported, with
    `three_prime_partner` naming which primer's 3' end the run is anchored at.
    Either extendable 3' end consumes the reaction, so reporting only the
    forward primer's would miss half the cases.
    """
    from_forward = complementarity(forward, reverse)
    from_reverse = complementarity(reverse, forward)
    best_any = max(from_forward.any_score, from_reverse.any_score)
    if from_reverse.three_prime_score > from_forward.three_prime_score:
        return ComplementarityResult(best_any, from_reverse.three_prime_score, "reverse")
    return ComplementarityResult(best_any, from_forward.three_prime_score, "forward")


@dataclass(frozen=True)
class HairpinResult:
    """The best hairpin found in one oligo.

    `engine` is `ENGINE_VIENNARNA` or `ENGINE_WINDOW` and says which metric the
    other fields carry, because the two are not interchangeable:

    * `ENGINE_VIENNARNA`: `delta_g_kcal_per_mol` is the minimum free energy of
      the fold in kcal/mol at 37 C under ViennaRNA's DNA parameters, and
      `structure` is its dot-bracket notation. `stem_bp` is the number of
      paired positions in that structure.
    * `ENGINE_WINDOW`: `delta_g_kcal_per_mol` is None, because no free energy
      was computed and reporting one would be an invented number.
      `stem_bp` is the length of the longest contiguous complementary stem in
      base pairs and is the quantity the threshold is read against.

    `three_prime_involved` is whether any paired position falls within the
    3'-terminal window from `constants.THREE_PRIME_INVOLVEMENT_WINDOW_NT`,
    which is what escalates a hairpin from WARN to FAIL in section 7.5 check 6.

    `five_prime_arm` and `three_prime_arm` locate the two halves of the stem on
    the oligo, zero-based and end exclusive, so a caller that knows where the
    5' tail ends can say which segment of the oligo each arm lies in. That is
    what makes a surviving WARN actionable: an arm in the template-binding
    region can be walked along the template, an arm inside a fixed tail cannot
    be moved at all. Use `arm_segments` to turn them into that label.

    `three_prime_anchored` is the companion result described in
    `window_hairpin`, present only when the longest stem in the oligo is not
    3'-involved but some shorter stem is. The reason it exists is that the two
    conditions carry different severities: section 7.5 check 6 makes a
    3'-involved stem a FAIL at a threshold that an internal stem only WARNs at,
    so a single result chosen by stem length alone can hide the more severe
    finding behind the longer one. A caller applying the thresholds must look at
    this field before concluding there is no 3' FAIL. It is always None on the
    free energy engine, which reports one minimum free energy structure for the
    whole oligo and so has nothing to hide a 3' pairing behind.
    """

    engine: str
    stem_bp: int
    three_prime_involved: bool
    delta_g_kcal_per_mol: float | None = None
    structure: str | None = None
    loop_nt: int | None = None
    coordinates: tuple[int, int] | None = None
    five_prime_arm: tuple[int, int] | None = None
    three_prime_arm: tuple[int, int] | None = None
    three_prime_anchored: HairpinResult | None = None

    @property
    def worst_three_prime(self) -> HairpinResult | None:
        """The most 3'-involved stem this scan found, or None if there is none.

        This is the result a threshold carrying 3' FAIL severity must be read
        against. It is `three_prime_anchored` when a longer internal stem would
        otherwise mask it, this result itself when this result is already the
        3'-involved one, and None when no stem touches the 3' window.
        """
        if self.three_prime_anchored is not None:
            return self.three_prime_anchored
        return self if self.three_prime_involved else None


@lru_cache(maxsize=1)
def viennarna_version() -> str | None:
    """ViennaRNA's version if it is importable with DNA parameters, else None.

    Importing and loading the DNA parameter set is done once and cached, so the
    engine choice is fixed for the life of the process and two validations in
    one run cannot disagree about which engine was available.
    """
    try:
        import RNA  # noqa: PLC0415 - optional dependency, imported lazily on purpose
    except ImportError:
        return None
    try:
        # ViennaRNA defaults to RNA stacking parameters. A primer is DNA, so the
        # DNA parameter set is loaded explicitly: see the Q6 note in the module
        # docstring. Source: dna_mathews2004.par as distributed with ViennaRNA.
        RNA.params_load_DNA_Mathews2004()
    except Exception:  # pragma: no cover - a build of RNA without DNA parameters
        return None
    return str(getattr(RNA, "__version__", "unknown"))


def hairpin_engine_available() -> bool:
    """Whether a free energy hairpin engine is available (open question Q6)."""
    return viennarna_version() is not None


def window_hairpin(sequence: str, *, min_loop_nt: int, three_prime_window_nt: int) -> HairpinResult:
    """Longest contiguous hairpin stem, in base pairs, by sliding-window scan.

    This is the documented fallback of section 7.4 and open question Q6, used
    when no free energy engine is available. It is also used directly by the
    tests, so the fallback path is exercised whether or not ViennaRNA is
    installed in the environment running them.

    A hairpin is a stem of `k` consecutive base pairs between position `i` and
    position `j` of the same oligo, read towards each other, closing a loop of
    `j - i - 2k + 1` unpaired nucleotides. Only stems closing a loop of at
    least `min_loop_nt` are considered, because a shorter loop cannot form: 3
    nucleotides is the standard minimum in nucleic acid secondary structure
    models and is ViennaRNA's own minimum.

    TWO RESULTS, NOT ONE, AND WHY. The longest stem in an oligo and the longest
    stem that sequesters the 3' end are different findings carrying different
    severities: section 7.5 check 6 FAILs a 3'-involved stem at a threshold an
    internal stem only WARNs at, because a stem that sequesters the 3' end is
    the one that genuinely stops the polymerase extending. Selecting a single
    result by stem length therefore lets a longer internal stem mask a shorter
    3'-anchored one, and the FAIL is never reported. So the scan tracks both and
    returns the longest stem with the longest 3'-involved stem attached as
    `three_prime_anchored` whenever that is a different stem. Read
    `HairpinResult.worst_three_prime` to apply a 3' threshold; reading only
    `stem_bp` and `three_prime_involved` reproduces the masking bug.

    The thresholds themselves are deliberately not known here. This function
    reports what it found and the caller in `checks.py` applies
    `HAIRPIN_WINDOW_STEM_WARN_BP` and
    `HAIRPIN_WINDOW_STEM_THREE_PRIME_FAIL_BP` to it, which keeps every
    threshold in `constants.py` as section 3.3 constraint 2 requires.

    The scan covers the whole oligo including any 5' tail. That is deliberate.
    The 3' terminus can only ever be sequestered by a stem whose other arm lies
    upstream, which for a tailed assembly primer is often the tail itself, so
    skipping the tail would hide exactly the class of hairpin that stops a
    primer working. The arm coordinates are reported instead, so the caller can
    tell the reader which arm it is able to move.
    """
    cleaned = clean_sequence(sequence, allow_ambiguous=True)
    if min_loop_nt < 1:
        raise ValueError("min_loop_nt must be at least 1")
    if three_prime_window_nt < 1:
        raise ValueError("three_prime_window_nt must be at least 1")
    total = len(cleaned)
    best = HairpinResult(engine=ENGINE_WINDOW, stem_bp=0, three_prime_involved=False)
    best_three_prime: HairpinResult | None = None
    three_prime_start = max(0, total - three_prime_window_nt)
    for left in range(total):
        for right in range(total - 1, left, -1):
            stem = 0
            while (
                left + stem < right - stem
                and _pairs(cleaned[left + stem], cleaned[right - stem])
                and (right - stem) - (left + stem) - 1 >= min_loop_nt
            ):
                stem += 1
            if stem == 0:
                continue
            loop = (right - stem + 1) - (left + stem)
            involved = (right >= three_prime_start) or (right - stem + 1 >= three_prime_start)
            found = HairpinResult(
                engine=ENGINE_WINDOW,
                stem_bp=stem,
                three_prime_involved=involved,
                delta_g_kcal_per_mol=None,
                structure=None,
                loop_nt=loop,
                coordinates=(left, right + 1),
                five_prime_arm=(left, left + stem),
                three_prime_arm=(right + 1 - stem, right + 1),
            )
            # The longest stem anywhere in the oligo, with 3' involvement
            # breaking a tie because the 3'-involved stem is the worse finding
            # at equal length.
            if stem > best.stem_bp or (
                stem == best.stem_bp and involved and not best.three_prime_involved
            ):
                best = found
            # The longest 3'-involved stem, tracked independently so that a
            # longer internal stem cannot displace it.
            if involved and (best_three_prime is None or stem > best_three_prime.stem_bp):
                best_three_prime = found
    if best_three_prime is None or best_three_prime.stem_bp == best.stem_bp:
        # Either nothing touches the 3' window, or the stem already reported is
        # as long as the longest 3'-involved one, in which case `best` carries
        # the 3' involvement itself and a companion would be a duplicate.
        return best
    # `replace` rather than rebuilding field by field, so a field added to
    # HairpinResult later cannot be silently dropped here.
    return replace(best, three_prime_anchored=best_three_prime)


def viennarna_hairpin(sequence: str, *, three_prime_window_nt: int) -> HairpinResult:
    """Minimum free energy fold from ViennaRNA with DNA parameters.

    Raises RuntimeError when ViennaRNA is not available, so a caller can never
    read a missing engine as a clean result (section 3.3 constraint 4).

    The free energy is ViennaRNA's minimum free energy at its default folding
    temperature of 37 C, under the DNA parameter set
    (`RNA.params_load_DNA_Mathews2004()`, the distributed
    `dna_mathews2004.par`). A primer that does not fold at all reports 0.0
    kcal/mol and an empty structure, which is a real result, not an absent one.
    """
    if viennarna_version() is None:
        raise RuntimeError(
            "ViennaRNA is not importable, so no hairpin free energy can be computed. "
            "Use window_hairpin, which is the documented fallback for open question Q6."
        )
    import RNA  # noqa: PLC0415 - optional dependency

    cleaned = clean_sequence(sequence, allow_ambiguous=True)
    if three_prime_window_nt < 1:
        raise ValueError("three_prime_window_nt must be at least 1")
    fold = RNA.fold_compound(cleaned)
    structure, delta_g = fold.mfe()
    paired = [index for index, symbol in enumerate(structure) if symbol in "()"]
    three_prime_start = max(0, len(cleaned) - three_prime_window_nt)
    five_prime_arm, three_prime_arm = _outermost_helix(structure)
    return HairpinResult(
        engine=ENGINE_VIENNARNA,
        stem_bp=len(paired) // 2,
        three_prime_involved=any(index >= three_prime_start for index in paired),
        delta_g_kcal_per_mol=float(delta_g),
        structure=structure,
        loop_nt=None,
        coordinates=(paired[0], paired[-1] + 1) if paired else None,
        five_prime_arm=five_prime_arm,
        three_prime_arm=three_prime_arm,
    )


def _outermost_helix(structure: str) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
    """The two arms of the outermost helix of a dot-bracket structure.

    Reported as the contiguous run of opening brackets that starts at the first
    paired position, and the contiguous run of closing brackets that ends at the
    last paired position. A multi-branch fold has more helices than this, so the
    arms are the outermost stem rather than a complete description of the fold;
    `structure` carries the complete description and is what the message prints.
    The arms exist so a caller can name the oligo segment the stem sits in.
    """
    opens = [index for index, symbol in enumerate(structure) if symbol == "("]
    closes = [index for index, symbol in enumerate(structure) if symbol == ")"]
    if not opens or not closes:
        return None, None
    start = opens[0]
    end = start
    while end + 1 < len(structure) and structure[end + 1] == "(":
        end += 1
    last = closes[-1]
    first = last
    while first - 1 >= 0 and structure[first - 1] == ")":
        first -= 1
    return (start, end + 1), (first, last + 1)


def arm_segments(result: HairpinResult, *, tail_nt: int) -> str | None:
    """Where each arm of the stem lies on the oligo, as readable text.

    `tail_nt` is the length of the primer's fixed 5' tail, so the oligo is the
    tail over `[0, tail_nt)` followed by the template-binding region. Returns
    None when the result carries no arm coordinates, which is the case for an
    oligo with no stem at all.

    Positions in the returned text are 1-based and inclusive, which is how an
    oligo is read off a synthesis order, and the text says so. The point of the
    label is that the two segments differ in what the user can do about them:
    the binding region can be walked along the template, whereas a Gibson
    homology arm or a Type IIS site plus overhang is fixed by the assembly
    standard and cannot be moved at all.
    """
    if result.five_prime_arm is None or result.three_prime_arm is None:
        return None
    parts = []
    for label, (start, end) in (
        ("5' arm", result.five_prime_arm),
        ("3' arm", result.three_prime_arm),
    ):
        parts.append(f"{label} at {start + 1} to {end} in {_segment_name(start, end, tail_nt=tail_nt)}")
    return ", ".join(parts)


def _segment_name(start: int, end: int, *, tail_nt: int) -> str:
    """Name the oligo segment the half-open interval `[start, end)` lies in."""
    if tail_nt <= 0:
        return "the template-binding region"
    if end <= tail_nt:
        return "the fixed 5' tail"
    if start >= tail_nt:
        return "the template-binding region"
    return "the fixed 5' tail and the template-binding region"


def arms_are_movable(result: HairpinResult, *, tail_nt: int) -> bool:
    """Whether both arms lie wholly in the template-binding region.

    True means the stem can be broken by walking the primer along the template,
    which is a remedy the user can act on. False means at least one arm sits in
    the fixed tail, where the assembly standard fixes the sequence and only the
    other arm can be redesigned. Saying which of the two it is, is the whole
    reason the arms are reported.
    """
    if result.five_prime_arm is None or result.three_prime_arm is None:
        return False
    return all(
        start >= tail_nt for start, _ in (result.five_prime_arm, result.three_prime_arm)
    )


def hairpin(
    sequence: str,
    *,
    min_loop_nt: int,
    three_prime_window_nt: int,
    engine: str = "auto",
) -> HairpinResult:
    """Best hairpin in one oligo, preferring the free energy engine (Q6).

    `engine` is `"auto"` (prefer ViennaRNA, fall back to the sliding-window
    score), `"viennarna"` (require ViennaRNA, raise if absent) or `"window"`
    (always use the documented sliding-window score). The default is `"auto"`
    because section 7.4 says to prefer ViennaRNA when it is installable, and
    the explicit values exist so a test can pin one engine and stay
    deterministic regardless of the environment it runs in.
    """
    if engine not in ("auto", "viennarna", "window"):
        raise ValueError(f"engine must be 'auto', 'viennarna' or 'window', not {engine!r}")
    if engine == "window":
        return window_hairpin(sequence, min_loop_nt=min_loop_nt, three_prime_window_nt=three_prime_window_nt)
    if engine == "viennarna":
        return viennarna_hairpin(sequence, three_prime_window_nt=three_prime_window_nt)
    if hairpin_engine_available():
        return viennarna_hairpin(sequence, three_prime_window_nt=three_prime_window_nt)
    return window_hairpin(sequence, min_loop_nt=min_loop_nt, three_prime_window_nt=three_prime_window_nt)


def longest_shared_complementarity(first: str, second: str) -> int:
    """Longest contiguous stretch of `first` complementary to `second`, in bp.

    Used by section 7.5 check 13 (Gibson junction uniqueness): two junctions
    can mis-assemble when one junction's homology arm is complementary to
    another's over a long enough stretch. Implemented as the longest common
    substring between `first` and the reverse complement of `second`, which is
    the same quantity stated the other way round.
    """
    top = clean_sequence(first, allow_ambiguous=True)
    other = reverse_complement(clean_sequence(second, allow_ambiguous=True))
    if not top or not other:
        return 0
    previous = [0] * (len(other) + 1)
    best = 0
    for i in range(1, len(top) + 1):
        current = [0] * (len(other) + 1)
        for j in range(1, len(other) + 1):
            if top[i - 1] == other[j - 1]:
                current[j] = previous[j - 1] + 1
                best = max(best, current[j])
        previous = current
    return best
