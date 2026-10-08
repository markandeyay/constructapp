"""On-target activity prediction (section 8.4).

Two scorers live here and they are never conflated.

1. **Rule Set 1**, a published position-dependent logistic regression model.
   This is a faithful implementation: the intercept, the GC terms and all 70
   position-specific nucleotide and dinucleotide coefficients were read from a
   reference implementation, not recalled, and the implementation is pinned by
   a test against values computed with that reference implementation.

   Citation: Nat Biotechnol 2014;32(12):1262-1267, doi:10.1038/nbt.3026,
   PMID 25184501, PMCID PMC4262738, titled "Rational design of highly active
   sgRNAs for CRISPR-Cas9-mediated gene inactivation". The model is commonly
   called Rule Set 1 and is the scoring behind the original public sgRNA
   designer.

   Coefficient source: the reference implementation in the CRISPOR guide
   selection tool, file `crisporEffScores.py`, table `doenchParams` and function
   `calcDoenchScores`, retrieved 2026-10-07 from
   https://raw.githubusercontent.com/maximilianh/crisporWebsite/master/crisporEffScores.py
   whose own comment records that the table was transcribed from the
   publication and later corrected. CRISPOR itself is published as
   Genome Biol 2016;17(1):148, doi:10.1186/s13059-016-1012-2, PMID 27380939.
   Appendix E requires a coefficient to be read rather than recalled, and this
   is the read copy. `tests/grna/test_ontarget_reference.py` pins the output of
   this implementation against values produced by that reference
   implementation, so a transcription error is a test failure.

   **Validity domain**, from the publication's own abstract and methods:
   SpCas9 with an NGG PAM and a 20 nt spacer; sgRNAs delivered and expressed
   from a lentiviral construct in mammalian cell lines; activity measured as
   the production of null alleles by antibody staining and flow cytometry;
   trained on 1,841 sgRNAs tiling all target sites of six endogenous mouse
   genes and three endogenous human genes. The model consumes a 30 nt context,
   namely 4 nt 5' of the spacer, the 20 nt spacer, the 3 nt PAM, and 3 nt 3' of
   the PAM.

   Outside that domain the score is withheld or caveated, never extrapolated
   (section 8.4). `_domain_status` is the single place that decision is made:

   * nuclease other than SpCas9: no score. The model has no SaCas9 or Cas12a
     training data.
   * in-vitro-transcribed guide: no score. That is a different validity domain
     and a different published model addresses it (CRISPRscan,
     Nat Methods 2015;12(10):982-988, doi:10.1038/nmeth.3543, PMID 26322839),
     which this build does not implement.
   * non-mammalian or cell-free context: no score.
   * 30 nt context unavailable because the guide sits too close to an end of
     the supplied target: no score, with the reason.
   * edit intent of activation or interference: score returned with an explicit
     caveat, because the model was trained on knockout activity and
     transcriptional activation or interference activity is governed by other
     factors such as distance to the transcription start site and chromatin
     accessibility.
   * alternative NAG PAM: score returned with an explicit caveat, because the
     model's PAM term was fitted on NGG.

2. **The Construct sequence-feature heuristic**, a transparent fallback used
   only where Rule Set 1 is out of domain, so that guides can still be ranked.
   It is labelled `labeled_heuristic` in every payload it appears in, its
   weights are stated in `constants.HeuristicWeights`, and it is composed of
   the section 8.5 sequence features. Section 8.4 permits exactly this and
   section 16 bans describing it as a published score. It is not one.

Both scorers return `OnTargetScore`, which carries the model name, the model
kind, the citation, the validity domain, the status, the caveats, the per
feature reasoning section 8.7 requires, and a disclaimer saying the number is a
prediction rather than a measurement (section 16).
"""

from __future__ import annotations

import math
from typing import Sequence

from packages.core.schemas.grna import (
    GuideRNARequest,
    OnTargetScore,
    ScoreContribution,
)
from packages.core.sequence import clean_sequence, gc_content, gc_count, homopolymer_runs

from .constants import PROXIMAL_GC_CITATION, DEFAULT_THRESHOLDS, GuideRNAThresholds
from .nuclease import NucleaseSpec, get_nuclease
from .selfcomp import longest_self_complementary_stem

RULE_SET_1_NAME = "Rule Set 1 sgRNA on-target activity model"

RULE_SET_1_CITATION = (
    "Nat Biotechnol 2014;32(12):1262-1267, doi:10.1038/nbt.3026, PMID 25184501, "
    "PMCID PMC4262738. Coefficients read 2026-10-07 from the reference implementation "
    "crisporEffScores.py (doenchParams, calcDoenchScores) of the CRISPOR tool, "
    "Genome Biol 2016;17(1):148, doi:10.1186/s13059-016-1012-2, PMID 27380939."
)

RULE_SET_1_DOMAIN = (
    "SpCas9, NGG PAM, 20 nt spacer, 30 nt context required (4 nt 5' flank, 20 nt spacer, "
    "3 nt PAM, 3 nt 3' flank). Trained on 1,841 sgRNAs tiling six endogenous mouse and three "
    "endogenous human genes, expressed from a lentiviral construct in mammalian cell lines, "
    "with activity read out as null allele production by antibody staining and flow cytometry. "
    "Not applicable to SaCas9 or Cas12a, to in-vitro-transcribed guides, to non-mammalian or "
    "cell-free systems, or to transcriptional activation or interference."
)

HEURISTIC_NAME = "Construct sequence-feature heuristic v1 (labeled heuristic, not a published score)"

HEURISTIC_CITATION = (
    "No publication. This is a transparent heuristic composed of the section 8.5 sequence "
    "features with the stated weights in packages.validation.grna.constants.HeuristicWeights, "
    "permitted as a fallback by section 8.4 of the engine capability system design. One feature, "
    f"PAM-proximal GC, has weak observational support: {PROXIMAL_GC_CITATION}"
)

HEURISTIC_DOMAIN = (
    "Any nuclease and any expression system, because it makes no claim beyond the sequence "
    "features it combines. It is not calibrated against measured activity for any system and its "
    "numeric value is not comparable to a published score."
)

PREDICTION_DISCLAIMER = (
    "Predicted activity, not a measurement. Confirm at the bench before relying on it."
)

HEURISTIC_DISCLAIMER = (
    "Labeled heuristic, not a published score and not a measurement. It ranks guides by stated "
    "sequence features only."
)

CRISPRSCAN_POINTER = (
    "In-vitro-transcribed guides are a different validity domain, addressed by CRISPRscan "
    "(Nat Methods 2015;12(10):982-988, doi:10.1038/nmeth.3543, PMID 26322839), which this build "
    "does not implement."
)

# ---------------------------------------------------------------------------
# Rule Set 1 coefficients
# ---------------------------------------------------------------------------
# Read, not recalled. See the module docstring for the retrieval record. Each
# entry is (zero-based index into the 30 nt context, matched subsequence,
# coefficient). A single-character subsequence is a position-specific
# nucleotide term and a two-character one is a position-specific dinucleotide
# term.

RULE_SET_1_INTERCEPT = 0.59763615
"""Intercept of the logistic regression. Read from the reference implementation
named in the module docstring, which gives it as `intercept = 0.59763615`."""

RULE_SET_1_GC_HIGH = -0.1665878
"""Coefficient applied per G or C above `RULE_SET_1_GC_PIVOT` in the spacer.
Read from the reference implementation (`gcHigh`)."""

RULE_SET_1_GC_LOW = -0.2026259
"""Coefficient applied per G or C at or below `RULE_SET_1_GC_PIVOT` in the
spacer. Read from the reference implementation (`gcLow`)."""

RULE_SET_1_GC_PIVOT = 10
"""The spacer G or C count the GC term measures distance from, in either
direction. Read from the reference implementation, which branches on
`gcCount <= 10`. For a 20 nt spacer this is a GC fraction of 0.50."""

RULE_SET_1_CONTEXT_LENGTH = 30
"""Length of the context window the model consumes: 4 nt 5' flank, 20 nt
spacer, 3 nt PAM, 3 nt 3' flank. Read from the reference implementation, which
asserts `len(seq) == 30`."""

RULE_SET_1_SPACER_SLICE = (4, 24)
"""Where the 20 nt spacer sits inside the 30 nt context, zero-based and end
exclusive. Read from the reference implementation, which slices `seq[4:24]` for
the GC term."""

RULE_SET_1_TERMS: tuple[tuple[int, str, float], ...] = (
    (1, "G", -0.2753771),
    (2, "A", -0.3238875),
    (2, "C", 0.17212887),
    (3, "C", -0.1006662),
    (4, "C", -0.2018029),
    (4, "G", 0.24595663),
    (5, "A", 0.03644004),
    (5, "C", 0.09837684),
    (6, "C", -0.7411813),
    (6, "G", -0.3932644),
    (11, "A", -0.466099),
    (14, "A", 0.08537695),
    (14, "C", -0.013814),
    (15, "A", 0.27262051),
    (15, "C", -0.1190226),
    (15, "T", -0.2859442),
    (16, "A", 0.09745459),
    (16, "G", -0.1755462),
    (17, "C", -0.3457955),
    (17, "G", -0.6780964),
    (18, "A", 0.22508903),
    (18, "C", -0.5077941),
    (19, "G", -0.4173736),
    (19, "T", -0.054307),
    (20, "G", 0.37989937),
    (20, "T", -0.0907126),
    (21, "C", 0.05782332),
    (21, "T", -0.5305673),
    (22, "T", -0.8770074),
    (23, "C", -0.8762358),
    (23, "G", 0.27891626),
    (23, "T", -0.4031022),
    (24, "A", -0.0773007),
    (24, "C", 0.28793562),
    (24, "T", -0.2216372),
    (27, "G", -0.6890167),
    (27, "T", 0.11787758),
    (28, "C", -0.1604453),
    (29, "G", 0.38634258),
    (1, "GT", -0.6257787),
    (4, "GC", 0.30004332),
    (5, "AA", -0.8348362),
    (5, "TA", 0.76062777),
    (6, "GG", -0.4908167),
    (11, "GG", -1.5169074),
    (11, "TA", 0.7092612),
    (11, "TC", 0.49629861),
    (11, "TT", -0.5868739),
    (12, "GG", -0.3345637),
    (13, "GA", 0.76384993),
    (13, "GC", -0.5370252),
    (16, "TG", -0.7981461),
    (18, "GG", -0.6668087),
    (18, "TC", 0.35318325),
    (19, "CC", 0.74807209),
    (19, "TG", -0.3672668),
    (20, "AC", 0.56820913),
    (20, "CG", 0.32907207),
    (20, "GA", -0.8364568),
    (20, "GG", -0.7822076),
    (21, "TC", -1.029693),
    (22, "CG", 0.85619782),
    (22, "CT", -0.4632077),
    (23, "AA", -0.5794924),
    (23, "AG", 0.64907554),
    (24, "AG", -0.0773007),
    (24, "CG", 0.28793562),
    (24, "TG", -0.2216372),
    (26, "GT", 0.11787758),
    (28, "GG", -0.69774),
)


def _term_description(index: int, subsequence: str) -> str:
    """Plain words for one model term, for the section 8.7 reasoning column.

    The model indexes a 30 nt context. Positions 4 to 23 inclusive are the
    spacer, 24 to 26 are the PAM and the rest are flanks, so a term is
    described relative to whichever of those it falls in.
    """
    spacer_start, spacer_end = RULE_SET_1_SPACER_SLICE
    width = len(subsequence)
    if index + width <= spacer_start:
        where = f"5' flank position {index + 1} of 4"
    elif index >= spacer_end + 3:
        where = f"3' flank position {index - spacer_end - 2}"
    elif index >= spacer_end:
        where = f"PAM position {index - spacer_end + 1}"
    elif index + width <= spacer_end:
        where = f"spacer position {index - spacer_start + 1}"
    else:
        where = f"context positions {index + 1} to {index + width} (spans a boundary)"
    kind = "nucleotide" if width == 1 else "dinucleotide"
    return f"{subsequence} {kind} at {where}"


def _domain_status(
    request: GuideRNARequest,
    spec: NucleaseSpec,
    context_30mer: str | None,
    pam_is_alternative: bool,
) -> tuple[str, list[str]]:
    """Decide whether Rule Set 1 applies, and collect every caveat (section 8.4).

    Returns `("in_domain" | "in_domain_with_caveat" | "out_of_domain", caveats)`.
    Order of the returned caveats is fixed so output is deterministic.
    """
    blocking: list[str] = []
    caveats: list[str] = []

    if not spec.supports_published_on_target_model:
        blocking.append(
            f"{RULE_SET_1_NAME} was trained on SpCas9 data and has no {spec.name} training set, "
            f"so no score is returned for {spec.name}. Rank {spec.name} guides by the labeled "
            "heuristic and by the off-target summary instead."
        )
    if request.expression_system == "t7_in_vitro":
        blocking.append(
            f"The request specifies an in-vitro-transcribed guide, which is outside the "
            f"expression context {RULE_SET_1_NAME} was trained on. {CRISPRSCAN_POINTER}"
        )
    elif request.expression_system == "other":
        blocking.append(
            "The expression system is stated as other, so it cannot be confirmed inside the "
            f"expression context {RULE_SET_1_NAME} was trained on. Set expression_system to "
            "u6_plasmid if the guide is plasmid expressed in mammalian cells."
        )
    if request.host_context in ("non_mammalian", "cell_free"):
        blocking.append(
            f"The host context is {request.host_context}, and {RULE_SET_1_NAME} was trained in "
            "mammalian cell lines, so no score is returned. Supplying a mammalian host context "
            "is the only way this model applies."
        )
    if context_30mer is None and not blocking:
        blocking.append(
            f"{RULE_SET_1_NAME} needs a 30 nt context (4 nt 5' of the spacer, the spacer, the "
            "PAM, and 3 nt 3' of the PAM) and the guide sits too close to an end of the supplied "
            "target for that window to exist. Supply more flanking sequence around the target to "
            "score this guide."
        )

    if blocking:
        return "out_of_domain", blocking

    if request.edit_intent in ("activation", "interference"):
        caveats.append(
            f"Edit intent is {request.edit_intent}. {RULE_SET_1_NAME} was trained on knockout "
            "activity, so this score describes predicted cutting, not predicted transcriptional "
            "effect. Transcriptional activation and interference also depend on distance to the "
            "transcription start site and on chromatin accessibility, which this model does not "
            "consider. Treat the number as a cutting prediction only."
        )
    if pam_is_alternative:
        caveats.append(
            "This guide uses the alternative NAG PAM. The model's PAM term was fitted on NGG, so "
            "the score overstates activity here. Prefer an NGG guide when one is available."
        )
    if request.host_context == "other_mammalian":
        caveats.append(
            "The host context is a mammalian system other than the human and mouse cell lines "
            "the model was trained in, so transfer is plausible but unverified."
        )
    return ("in_domain_with_caveat" if caveats else "in_domain"), caveats


def rule_set_1_logit(context_30mer: str) -> tuple[float, list[tuple[int, str, float]]]:
    """The model's linear predictor and every term that fired.

    Reproduces the reference implementation exactly: start from the intercept,
    add the GC term computed from the 20 nt spacer, then add every
    position-specific term whose subsequence matches the context.
    """
    context = clean_sequence(context_30mer)
    if len(context) != RULE_SET_1_CONTEXT_LENGTH:
        raise ValueError(
            f"{RULE_SET_1_NAME} needs a {RULE_SET_1_CONTEXT_LENGTH} nt context, got {len(context)}"
        )
    spacer_start, spacer_end = RULE_SET_1_SPACER_SLICE
    spacer = context[spacer_start:spacer_end]
    gc = gc_count(spacer)
    gc_weight = RULE_SET_1_GC_LOW if gc <= RULE_SET_1_GC_PIVOT else RULE_SET_1_GC_HIGH
    gc_term = abs(RULE_SET_1_GC_PIVOT - gc) * gc_weight
    total = RULE_SET_1_INTERCEPT + gc_term
    fired: list[tuple[int, str, float]] = []
    for index, subsequence, weight in RULE_SET_1_TERMS:
        if context[index : index + len(subsequence)] == subsequence:
            total += weight
            fired.append((index, subsequence, weight))
    return total, fired


def _rule_set_1_reasoning(
    context_30mer: str,
    fired: Sequence[tuple[int, str, float]],
    max_terms: int,
) -> list[ScoreContribution]:
    """The per guide reasoning section 8.7 requires, straight from the model terms.

    The GC term always appears because it always applies. The remaining
    contributions are the fired position-specific terms, largest absolute
    weight first, with the position and the sign spelled out. Ties break on
    index then subsequence so the list is deterministic.
    """
    spacer_start, spacer_end = RULE_SET_1_SPACER_SLICE
    spacer = clean_sequence(context_30mer)[spacer_start:spacer_end]
    gc = gc_count(spacer)
    gc_weight = RULE_SET_1_GC_LOW if gc <= RULE_SET_1_GC_PIVOT else RULE_SET_1_GC_HIGH
    gc_term = abs(RULE_SET_1_GC_PIVOT - gc) * gc_weight
    contributions = [
        ScoreContribution(
            feature="spacer GC count",
            detail=(
                f"{gc} of {len(spacer)} spacer bases are G or C; the model penalises distance "
                f"from {RULE_SET_1_GC_PIVOT} G or C bases in either direction"
            ),
            weight=round(gc_term, 6),
            direction="down" if gc_term < 0 else ("up" if gc_term > 0 else "neutral"),
        )
    ]
    ordered = sorted(fired, key=lambda term: (-abs(term[2]), term[0], term[1]))
    for index, subsequence, weight in ordered[:max_terms]:
        contributions.append(
            ScoreContribution(
                feature=_term_description(index, subsequence),
                detail=(
                    "model coefficient fired because the context carries "
                    f"{subsequence} at that position"
                ),
                weight=round(weight, 6),
                direction="up" if weight > 0 else ("down" if weight < 0 else "neutral"),
            )
        )
    return contributions


def heuristic_score(
    spacer: str,
    *,
    nuclease: str,
    pam_is_alternative: bool = False,
    u6_driven: bool = True,
    thresholds: GuideRNAThresholds = DEFAULT_THRESHOLDS,
) -> OnTargetScore:
    """The labelled fallback heuristic (section 8.4).

    Composed of the section 8.5 sequence features with the weights in
    `constants.HeuristicWeights`. Every contribution is reported, so the number
    can be reconstructed from the reasoning list by hand. Clamped to 0 to 100.
    """
    spec = get_nuclease(nuclease)
    sequence = clean_sequence(spacer)
    weights = thresholds.heuristic
    contributions: list[ScoreContribution] = []
    total = weights.base

    fraction = gc_content(sequence)
    if thresholds.spacer_gc_min <= fraction <= thresholds.spacer_gc_max:
        delta = weights.gc_in_window
        detail = (
            f"GC fraction {fraction:.2f} is inside the configured window "
            f"{thresholds.spacer_gc_min:.2f} to {thresholds.spacer_gc_max:.2f} (Appendix C)"
        )
    else:
        distance = (
            thresholds.spacer_gc_min - fraction
            if fraction < thresholds.spacer_gc_min
            else fraction - thresholds.spacer_gc_max
        )
        steps = max(0, int(distance / weights.gc_step))
        delta = max(
            weights.gc_penalty_floor,
            weights.gc_outside_window + steps * weights.gc_per_extra_step,
        )
        detail = (
            f"GC fraction {fraction:.2f} is outside the configured window "
            f"{thresholds.spacer_gc_min:.2f} to {thresholds.spacer_gc_max:.2f} (Appendix C), "
            f"by {distance:.2f}"
        )
    total += delta
    contributions.append(
        ScoreContribution(
            feature="spacer GC fraction",
            detail=detail,
            weight=delta,
            direction="up" if delta > 0 else "down",
        )
    )

    runs = [
        run
        for run in homopolymer_runs(sequence, min_length=thresholds.max_homopolymer_run + 1)
    ]
    if runs:
        delta = weights.per_long_homopolymer * len(runs)
        detail = (
            f"{len(runs)} homopolymer run(s) longer than the configured maximum of "
            f"{thresholds.max_homopolymer_run} (Appendix C): "
            + ", ".join(f"{run.base * run.length} at {run.start}" for run in runs)
        )
    else:
        delta = weights.no_long_homopolymer
        detail = (
            f"no homopolymer run longer than the configured maximum of "
            f"{thresholds.max_homopolymer_run} (Appendix C)"
        )
    total += delta
    contributions.append(
        ScoreContribution(
            feature="homopolymer runs",
            detail=detail,
            weight=delta,
            direction="up" if delta > 0 else "down",
        )
    )

    motif = thresholds.u6_terminator_motif
    if motif in sequence:
        delta = weights.u6_terminator_present
        detail = (
            f"the spacer contains {motif}, which terminates U6 transcription (Appendix C)"
            + ("" if u6_driven else " and is only a concern under a U6 promoter")
        )
    else:
        delta = weights.no_u6_terminator
        detail = f"the spacer does not contain the U6 terminator motif {motif} (Appendix C)"
    total += delta
    contributions.append(
        ScoreContribution(
            feature="U6 terminator motif",
            detail=detail,
            weight=delta,
            direction="up" if delta > 0 else "down",
        )
    )

    stem = longest_self_complementary_stem(sequence, min_loop_nt=thresholds.min_hairpin_loop_nt)
    if stem is not None and stem.length >= thresholds.max_self_complement_stem_nt:
        delta = weights.self_complement_stem_present
        detail = (
            f"a {stem.length} bp self-complementary stem ({stem.stem_sequence}) at or above the "
            f"configured reporting length of {thresholds.max_self_complement_stem_nt} bp "
            "(Construct convention)"
        )
    else:
        longest = 0 if stem is None else stem.length
        delta = weights.no_self_complement_stem
        detail = (
            f"longest internal self-complementary stem is {longest} bp, under the configured "
            f"reporting length of {thresholds.max_self_complement_stem_nt} bp "
            "(Construct convention)"
        )
    total += delta
    contributions.append(
        ScoreContribution(
            feature="internal self-complementarity",
            detail=detail,
            weight=delta,
            direction="up" if delta > 0 else "down",
        )
    )

    window = weights.proximal_gc_window_nt
    proximal = (
        sequence[-window:] if spec.pam_side == "three_prime" else sequence[:window]
    )
    proximal_gc = gc_count(proximal)
    if proximal_gc >= weights.proximal_gc_min_count:
        delta = weights.proximal_gc_adequate
        contributions.append(
            ScoreContribution(
                feature="PAM-proximal GC content",
                detail=(
                    f"{proximal_gc} of the {window} PAM-proximal bases are G or C, at or above "
                    f"the configured count of {weights.proximal_gc_min_count}"
                ),
                weight=delta,
                direction="up",
            )
        )
        total += delta
    else:
        contributions.append(
            ScoreContribution(
                feature="PAM-proximal GC content",
                detail=(
                    f"{proximal_gc} of the {window} PAM-proximal bases are G or C, under the "
                    f"configured count of {weights.proximal_gc_min_count}; no adjustment applied"
                ),
                weight=0.0,
                direction="neutral",
            )
        )

    if pam_is_alternative:
        delta = weights.alternative_pam
        total += delta
        contributions.append(
            ScoreContribution(
                feature="alternative PAM",
                detail=(
                    "the guide uses an alternative PAM, tolerated at substantially reduced "
                    "efficiency (Appendix C)"
                ),
                weight=delta,
                direction="down",
            )
        )

    score = max(0.0, min(100.0, total))
    return OnTargetScore(
        model_name=HEURISTIC_NAME,
        model_kind="labeled_heuristic",
        citation=HEURISTIC_CITATION,
        validity_domain=HEURISTIC_DOMAIN,
        status="in_domain_with_caveat",
        score=round(score, 2),
        score_scale="0 to 100, higher is more favourable on the stated sequence features only",
        caveats=[
            "This is a labeled heuristic composed of stated sequence features, not a published "
            "model and not a measurement. Its weights are a Construct convention and it is not "
            "calibrated against measured activity for any system.",
        ],
        reasoning=contributions,
        disclaimer=HEURISTIC_DISCLAIMER,
    )


def score_on_target(
    request: GuideRNARequest,
    spacer: str,
    context_30mer: str | None,
    pam_is_alternative: bool,
    *,
    thresholds: GuideRNAThresholds = DEFAULT_THRESHOLDS,
    max_reasoning_terms: int = 8,
) -> tuple[OnTargetScore, OnTargetScore]:
    """Score one guide, returning `(published, heuristic)`.

    The published result always describes Rule Set 1, including when it is out
    of domain, in which case it carries no score and states why. The heuristic
    result is always present, always labelled, and is what ranking falls back
    on when the published score is withheld. Both are surfaced, so a reader can
    see exactly which number is which (section 10.4).
    """
    spec = get_nuclease(request.nuclease)
    status, caveats = _domain_status(request, spec, context_30mer, pam_is_alternative)
    heuristic = heuristic_score(
        spacer,
        nuclease=request.nuclease,
        pam_is_alternative=pam_is_alternative,
        u6_driven=request.expression_system == "u6_plasmid",
        thresholds=thresholds,
    )
    if status == "out_of_domain":
        published = OnTargetScore(
            model_name=RULE_SET_1_NAME,
            model_kind="published_model",
            citation=RULE_SET_1_CITATION,
            validity_domain=RULE_SET_1_DOMAIN,
            status="out_of_domain",
            score=None,
            caveats=caveats,
            reasoning=[],
            disclaimer=(
                "No prediction. This request falls outside the model's stated validity domain and "
                "the score is withheld rather than extrapolated."
            ),
        )
        return published, heuristic

    assert context_30mer is not None  # guaranteed by _domain_status
    logit, fired = rule_set_1_logit(context_30mer)
    score = 100.0 / (1.0 + math.exp(-logit))
    published = OnTargetScore(
        model_name=RULE_SET_1_NAME,
        model_kind="published_model",
        citation=RULE_SET_1_CITATION,
        validity_domain=RULE_SET_1_DOMAIN,
        status=status,
        score=round(score, 2),
        caveats=caveats,
        reasoning=_rule_set_1_reasoning(context_30mer, fired, max_reasoning_terms),
        disclaimer=PREDICTION_DISCLAIMER,
    )
    return published, heuristic
