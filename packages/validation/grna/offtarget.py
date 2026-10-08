"""Off-target search over a declared space, scoped honestly (section 8.6).

Section 8.6 is blunt about the architecture and this module follows it exactly:

    A genome-wide off-target search needs a prebuilt index that this build does
    not have. Pretending otherwise is the fastest way to lose credibility with
    anyone who has used a real guide design tool.

Section 3.2 lists genome-wide off-target search as an explicit non-goal. So the
search here is a direct two-strand scan of a space the user declares, the real
size of that space is measured, and `space_statement` generates one sentence
that states what was covered and says it is not genome-wide. That sentence is
shown verbatim in the UI and in every export, and nothing in this module ever
produces the words genome-wide, comprehensive or exhaustive as a description of
what was searched (section 16).

Scoring is the published MIT specificity score.

    Citation: Nat Biotechnol 2013;31(9):827-832, doi:10.1038/nbt.2647,
    PMID 23873081, PMCID PMC3969858, titled "DNA targeting specificity of
    RNA-guided Cas9 nucleases".

    Coefficient source: the reference implementation in the CRISPOR guide
    selection tool, file `crispor.py`, weight vector `hitScoreM` and functions
    `calcHitScore` and `calcMitGuideScore`, retrieved 2026-10-07 from
    https://raw.githubusercontent.com/maximilianh/crisporWebsite/master/crispor.py
    CRISPOR itself is published as Genome Biol 2016;17(1):148,
    doi:10.1186/s13059-016-1012-2, PMID 27380939. Appendix E requires a
    coefficient to be read rather than recalled; this is the read copy, and
    `tests/grna/test_offtarget_reference.py` pins this implementation's output
    against values produced by that reference implementation.

The weight vector encodes exactly the principle section 8.6 insists on. Index 0
is the PAM-distal end of the 20 nt protospacer and index 19 is the PAM-proximal
end. The weights are 0 at several PAM-distal positions and rise to 0.851 near
the PAM, and a mismatch at position `i` multiplies the site score by
`1 - weight[i]`. A mismatch at the PAM-distal end therefore costs nothing while
a PAM-proximal mismatch costs most of the score, which is the seed region
effect. A model that weighted all positions equally would be wrong, and
`tests/grna/test_offtarget_reference.py` asserts the asymmetry directly.

Validity domain: the model was derived from SpCas9 data. The CRISPOR tool,
which is the reference implementation used here, states in its own interface
that this model and the related CFD model were developed for SpCas9 and that there is not
enough data to support their usefulness for Cas12a, and it uses a separate
published model for SaCas9. Applying this score to SaCas9 or Cas12a would be
the silent extrapolation section 8.4 forbids, so for those nucleases the per
site score and the aggregate specificity are withheld, every hit is still
reported with its mismatch positions and its seed mismatch count, and severity
still comes from the documented mismatch-structure rule in `checks.py`. The
search protects the user either way; only the published number is withheld.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packages.core.schemas.grna import (
    GuideRNARequest,
    OffTargetHit,
    OffTargetSpace,
    OffTargetSummary,
    Placement,
)
from packages.core.sequence import clean_sequence, find_with_mismatches, reverse_complement

from .constants import DEFAULT_THRESHOLDS, GuideRNAThresholds
from .enumeration import pam_at, seed_positions
from .nuclease import NucleaseSpec, get_nuclease

MIT_MODEL_NAME = "MIT specificity score (mismatch-position-weighted)"

MIT_CITATION = (
    "Nat Biotechnol 2013;31(9):827-832, doi:10.1038/nbt.2647, PMID 23873081, "
    "PMCID PMC3969858. Position weights and the three-term site score read 2026-10-07 from the "
    "reference implementation crispor.py (hitScoreM, calcHitScore, calcMitGuideScore) of the "
    "CRISPOR tool, Genome Biol 2016;17(1):148, doi:10.1186/s13059-016-1012-2, PMID 27380939."
)

MIT_DOMAIN = (
    "SpCas9 with a 20 nt spacer. Derived from SpCas9 mismatch tolerance data. Not applicable to "
    "SaCas9 or to Cas12a: the reference implementation states that this model and the related CFD "
    "model were developed for SpCas9 and that there is not enough data to support their use for "
    "Cas12a, and it scores SaCas9 with a separate published model."
)

MIT_DISCLAIMER = (
    "Predicted binding likelihood for sites inside the searched space only, not a measurement "
    "and not a statement about the genome."
)

NOT_GENOME_WIDE = "This is not a genome-wide search."

#: Position weights of the MIT specificity score, read from the reference
#: implementation named in the module docstring. Index 0 is PAM-distal and
#: index 19 is PAM-proximal for a 20 nt protospacer. A mismatch at index `i`
#: multiplies the site score by `1 - MIT_POSITION_WEIGHTS[i]`.
MIT_POSITION_WEIGHTS: tuple[float, ...] = (
    0.0,
    0.0,
    0.014,
    0.0,
    0.0,
    0.395,
    0.317,
    0.0,
    0.389,
    0.079,
    0.445,
    0.508,
    0.613,
    0.851,
    0.732,
    0.828,
    0.615,
    0.804,
    0.685,
    0.583,
)

MIT_SPACER_LENGTH = 20
"""The protospacer length the weight vector is defined for. The reference
implementation truncates longer guides to their 20 PAM-proximal nucleotides and
pads shorter ones, but this build does not use either path: a nuclease whose
spacer is not 20 nt is out of this model's validity domain anyway, so the score
is withheld rather than fudged."""

MIT_MAX_DISTANCE = 19
"""Maximum distance between mismatch positions in a 20 nt protospacer, used by
the second term of the site score. Read from the reference implementation
(`maxDist = 19`)."""


def mit_hit_score(spacer: str, protospacer: str) -> float:
    """Predicted cleavage likelihood at one site, on a 0 to 100 scale.

    Faithful reproduction of the reference implementation's three terms:

    1. the product over mismatched positions of `1 - weight[position]`, which is
       where the PAM-proximal seed effect lives;
    2. a term in the mean distance between consecutive mismatches, which
       penalises mismatches that are spread out less than mismatches that are
       clustered. With fewer than two mismatches it is 1, a special case the
       reference implementation notes is not in the publication;
    3. a term in the inverse square of the mismatch count. With zero mismatches
       it is 1, the other special case noted there.

    A perfect match scores 100. Higher means a more dangerous site.
    """
    guide = clean_sequence(spacer)
    site = clean_sequence(protospacer)
    if len(guide) != MIT_SPACER_LENGTH or len(site) != MIT_SPACER_LENGTH:
        raise ValueError(
            f"{MIT_MODEL_NAME} is defined for {MIT_SPACER_LENGTH} nt protospacers, got "
            f"{len(guide)} and {len(site)}"
        )
    distances: list[int] = []
    mismatch_count = 0
    last_position: int | None = None
    product = 1.0
    for position in range(MIT_SPACER_LENGTH):
        if guide[position] != site[position]:
            mismatch_count += 1
            if last_position is not None:
                distances.append(position - last_position)
            product *= 1.0 - MIT_POSITION_WEIGHTS[position]
            last_position = position
    if mismatch_count < 2:
        distance_term = 1.0
    else:
        mean_distance = sum(distances) / len(distances)
        distance_term = 1.0 / (((MIT_MAX_DISTANCE - mean_distance) / MIT_MAX_DISTANCE) * 4 + 1)
    count_term = 1.0 if mismatch_count == 0 else 1.0 / (mismatch_count**2)
    return product * distance_term * count_term * 100.0


def mit_guide_specificity(hit_scores: list[float]) -> float:
    """Aggregate guide specificity from the off-target site scores, 0 to 100.

    Faithful reproduction of the reference implementation's aggregate,
    `100 / (100 + sum of site scores)` rescaled to 0 to 100 and rounded to a
    whole number. Higher means fewer predicted off-target events in the
    searched space. The on-target site is excluded from the sum, which is why
    `search_off_targets` marks it rather than dropping it.

    With an empty searched space this returns 100, which means only that
    nothing was found in what was searched. The space statement is what says
    how much that is worth.
    """
    total = sum(hit_scores)
    return float(round((100.0 / (100.0 + total)) * 100.0))


# ---------------------------------------------------------------------------
# The searched space
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchSource:
    """One sequence inside the declared off-target space."""

    source_id: str
    label: str
    sequence: str

    @property
    def length(self) -> int:
        return len(self.sequence)


def parse_fasta(path: str | Path) -> list[tuple[str, str]]:
    """Minimal FASTA reader returning `(record_id, sequence)` in file order.

    Records with an empty sequence are skipped. The sequence is upper-cased and
    whitespace is removed; validation of the alphabet is left to
    `clean_sequence` at the point of use, so a malformed record fails loudly
    with its own identifier in the message.
    """
    text = Path(path).read_text(encoding="utf-8")
    records: list[tuple[str, str]] = []
    record_id: str | None = None
    chunks: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            if record_id is not None and chunks:
                records.append((record_id, "".join(chunks)))
            record_id = stripped[1:].split()[0] if len(stripped) > 1 else f"record_{len(records) + 1}"
            chunks = []
        elif stripped:
            chunks.append(stripped.upper())
    if record_id is not None and chunks:
        records.append((record_id, "".join(chunks)))
    return records


def collect_sources(request: GuideRNARequest) -> list[SearchSource]:
    """The sequences the declared scope says to search, in a fixed order.

    Section 8.6:

    * `construct_only` searches the delivery construct and the target sequence.
    * `supplied_fasta` searches a user-provided sequence set, in addition to the
      construct and the target, because a supplied set never makes the construct
      itself less relevant.
    * `none` searches nothing.
    """
    space = request.off_target_space
    if space.scope == "none":
        return []
    sources = [
        SearchSource(
            source_id="target",
            label=f"target sequence {request.target_name}",
            sequence=clean_sequence(request.target_sequence),
        )
    ]
    if request.delivery_construct_sequence:
        name = request.delivery_construct_name or "unnamed"
        sources.append(
            SearchSource(
                source_id="delivery_construct",
                label=f"delivery construct {name}",
                sequence=clean_sequence(request.delivery_construct_sequence),
            )
        )
    if space.scope == "supplied_fasta":
        assert space.fasta_path is not None  # enforced by the schema
        for record_id, sequence in parse_fasta(space.fasta_path):
            sources.append(
                SearchSource(
                    source_id=f"fasta:{record_id}",
                    label=f"supplied sequence {record_id}",
                    sequence=clean_sequence(sequence),
                )
            )
    return sources


def format_size(base_pairs: int) -> str:
    """Human readable size, used in the space statement so the figure is real."""
    if base_pairs < 1_000:
        return f"{base_pairs} bp"
    if base_pairs < 1_000_000:
        return f"{base_pairs / 1_000:.1f} kb"
    return f"{base_pairs / 1_000_000:.1f} Mb"


def space_statement(
    space: OffTargetSpace,
    sources: list[SearchSource],
    *,
    has_delivery_construct: bool,
    over_limit_bp: int | None = None,
) -> str:
    """The sentence shown verbatim in the UI and in every export (section 8.6).

    It is generated from the sequences that were actually searched and their
    real total size. It always ends with the statement that the search is not
    genome-wide, and it never claims coverage that was not achieved. When the
    delivery construct was not supplied the sentence says so, because the
    absence changes what the search means.
    """
    total = sum(source.length for source in sources)
    count = len(sources)

    if space.scope == "none":
        return (
            "No off-target search was performed. The off-target risk of this guide is unknown. "
            + NOT_GENOME_WIDE
        )
    if over_limit_bp is not None:
        return (
            f"No off-target search was performed: the requested space totals {format_size(total)} "
            f"across {count} sequence{'s' if count != 1 else ''}, above the configured limit of "
            f"{format_size(over_limit_bp)}. The off-target risk of this guide is unknown. "
            + NOT_GENOME_WIDE
        )

    fasta_total = sum(
        source.length for source in sources if source.source_id.startswith("fasta:")
    )
    if space.scope == "construct_only":
        if has_delivery_construct:
            covered = "the delivery construct and the target sequence"
        else:
            covered = "the target sequence only"
    else:
        if has_delivery_construct:
            covered = (
                "the delivery construct, the target sequence and the supplied "
                f"{format_size(fasta_total)} sequence set"
            )
        else:
            covered = (
                f"the target sequence and the supplied {format_size(fasta_total)} sequence set"
            )
    sentence = (
        f"Off-target search covered {covered}, {format_size(total)} in total across {count} "
        f"sequence{'s' if count != 1 else ''}."
    )
    if not has_delivery_construct:
        sentence += (
            " No delivery construct sequence was supplied, so self-targeting of the delivery "
            "construct was not searched."
        )
    return f"{sentence} {NOT_GENOME_WIDE}"


# ---------------------------------------------------------------------------
# The search
# ---------------------------------------------------------------------------


def _mismatch_positions(spacer: str, protospacer: str) -> tuple[int, ...]:
    """1-based positions along the spacer, written 5' to 3', that differ."""
    return tuple(
        index + 1
        for index, (a, b) in enumerate(zip(spacer, protospacer))
        if a != b
    )


def search_off_targets(
    request: GuideRNARequest,
    spacer: str,
    placement: Placement | None,
    *,
    thresholds: GuideRNAThresholds = DEFAULT_THRESHOLDS,
) -> OffTargetSummary:
    """Search the declared space for sites this guide could bind.

    A candidate is reported only when a usable PAM for the nuclease sits beside
    it at the correct offset, because a protospacer with no PAM is not a target.
    The guide's own on-target site is reported with `is_on_target` set and is
    excluded from the aggregate specificity.

    Hit order is deterministic: source order, then start, then strand, then
    mismatch count.
    """
    spec = get_nuclease(request.nuclease)
    guide = clean_sequence(spacer)
    space = request.off_target_space
    has_construct = bool(request.delivery_construct_sequence)
    sources = collect_sources(request)
    total_bases = sum(source.length for source in sources)
    seed = seed_positions(spec, len(guide), thresholds.seed_region_nt)
    in_domain = spec.supports_published_off_target_model and len(guide) == MIT_SPACER_LENGTH

    def summary(
        hits: list[OffTargetHit],
        statement: str,
        searched: bool,
        notes: list[str],
    ) -> OffTargetSummary:
        off_target_scores = [
            hit.hit_score
            for hit in hits
            if not hit.is_on_target and hit.hit_score is not None
        ]
        if searched and in_domain:
            specificity: float | None = mit_guide_specificity(off_target_scores)
            status = "in_domain"
        else:
            specificity = None
            status = "out_of_domain"
            if not in_domain:
                notes = notes + [
                    f"The {MIT_MODEL_NAME} is withheld for {spec.name}: {MIT_DOMAIN} Every hit is "
                    "still reported with its mismatch positions and its seed mismatch count, and "
                    "the severity rule is nuclease independent."
                ]
            if not searched:
                notes = notes + [
                    "No search was performed, so no specificity score can be computed."
                ]
        return OffTargetSummary(
            scope=space.scope,
            space_statement=statement,
            searched_sequence_count=len(sources) if searched else 0,
            searched_bases=total_bases if searched else 0,
            searched_sequences=[source.label for source in sources] if searched else [],
            max_mismatches_searched=thresholds.off_target_max_mismatches if searched else 0,
            seed_region_nt=thresholds.seed_region_nt,
            hits=hits,
            specificity_model_name=MIT_MODEL_NAME,
            specificity_citation=MIT_CITATION,
            specificity_validity_domain=MIT_DOMAIN,
            specificity_status=status,
            specificity_score=specificity,
            disclaimer=MIT_DISCLAIMER,
            searched=searched,
            notes=notes,
        )

    if space.scope == "none":
        return summary(
            [],
            space_statement(space, [], has_delivery_construct=has_construct),
            searched=False,
            notes=[
                "Off-target scope is 'none'. No off-target claim can be made about this guide. "
                "Set the scope to 'construct_only' to search the delivery construct and the "
                "target, or to 'supplied_fasta' to search a sequence set you provide."
            ],
        )
    if total_bases > thresholds.off_target_max_search_bp:
        return summary(
            [],
            space_statement(
                space,
                sources,
                has_delivery_construct=has_construct,
                over_limit_bp=thresholds.off_target_max_search_bp,
            ),
            searched=False,
            notes=[
                f"The declared space is {format_size(total_bases)}, above the configured limit of "
                f"{format_size(thresholds.off_target_max_search_bp)}. Raise "
                "off_target_max_search_bp and accept the longer run time, or supply a smaller "
                "sequence set. The search was not truncated silently."
            ],
        )

    hits: list[OffTargetHit] = []
    for source in sources:
        for hit in find_with_mismatches(
            source.sequence,
            guide,
            max_mismatches=thresholds.off_target_max_mismatches,
            both_strands=True,
        ):
            window = source.sequence[hit.start : hit.end]
            protospacer = window if hit.strand == 1 else reverse_complement(window)
            pam_result = pam_at(source.sequence, spec, hit.strand, hit.start, len(guide))
            if pam_result is None:
                continue
            pam, matches, is_alternative = pam_result
            if not matches:
                continue
            positions = _mismatch_positions(guide, protospacer)
            is_on_target = (
                source.source_id == "target"
                and placement is not None
                and hit.strand == placement.strand
                and hit.start == placement.spacer_start
                and hit.mismatches == 0
            )
            hits.append(
                OffTargetHit(
                    source_id=source.source_id,
                    source_label=source.label,
                    start=hit.start,
                    end=hit.end,
                    strand=hit.strand,
                    protospacer=protospacer,
                    pam=pam,
                    pam_is_alternative=is_alternative,
                    mismatches=len(positions),
                    mismatch_positions=positions,
                    seed_mismatches=sum(1 for position in positions if position in seed),
                    hit_score=round(mit_hit_score(guide, protospacer), 4) if in_domain else None,
                    hit_score_status="in_domain" if in_domain else "out_of_domain",
                    is_on_target=bool(is_on_target),
                )
            )
    hits.sort(
        key=lambda item: (
            0 if item.source_id == "target" else (1 if item.source_id == "delivery_construct" else 2),
            item.source_id,
            item.start,
            -item.strand,
            item.mismatches,
        )
    )
    return summary(
        hits,
        space_statement(space, sources, has_delivery_construct=has_construct),
        searched=True,
        notes=[],
    )


def seed_label(spec: NucleaseSpec, spacer_length: int, seed_region_nt: int) -> str:
    """Which spacer positions make up the seed, in words, for messages."""
    width = min(seed_region_nt, spacer_length)
    if spec.pam_side == "three_prime":
        return f"positions {spacer_length - width + 1} to {spacer_length} (the PAM-proximal {width} nt)"
    return f"positions 1 to {width} (the PAM-proximal {width} nt)"
