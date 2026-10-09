"""Guide RNA composition and ranking (sections 8.3, 8.4, 8.6, 8.7).

This is the section 5.2 generator for the guide RNA capability. It composes
nothing new: every base it emits comes from the user's target sequence or from
a published vector record, which is what section 4.2 means by composition
rather than generation and what makes the provenance in section 11.1 complete.

What it does, in order:

1. Enumerate every valid guide on both strands at the correct PAM offset
   (section 8.3, delegated to `packages.validation.grna.enumeration`).
2. Score each one with the published Rule Set 1 model and with the labelled
   fallback heuristic, both carrying their own name, citation, validity domain
   and status (section 8.4).
3. Rank cheaply, take a candidate pool, and search the declared off-target
   space only for the pool. The off-target search is a linear scan of the
   declared space, so searching it for every guide of a long target would cost
   time that buys nothing: guides far down the ranking are not going to be
   returned. The pool size is a parameter, the behaviour is stated in the
   result notes, and guides outside the pool are reported as not searched
   rather than as clean.
4. Validate each pooled guide, which runs the nine section 8.5 checks and the
   section 8.6 off-target check.
5. Rank the pool by the full verdict and return the requested number of rows,
   each with its reasoning (section 8.7).

Determinism (section 3.3 constraint 3): every sort key ends in the spacer
sequence, so no two rows can tie; there is no randomness and no model call; the
only clock reading is `ValidationReport.evaluated_at`, which the constructor
can pin.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any

from packages.core.schemas.capability import (
    CapabilityKind,
    DesignResult,
    Severity,
)
from packages.core.schemas.grna import (
    GuideRNADesign,
    GuideRNARequest,
    GuideRNAResult,
    OnTargetScore,
    RankedGuide,
)
from packages.core.sequence import clean_sequence
from packages.validation.grna import (
    DEFAULT_THRESHOLDS,
    GuideRNAThresholds,
    GuideRNAValidator,
    enumerate_guides,
    geometry_facts,
    get_nuclease,
    score_on_target,
    search_off_targets,
)
from packages.validation.grna.enumeration import EnumeratedGuide
from packages.validation.grna.offtarget import collect_sources, space_statement

from .cloning import cloning_plan

#: Order used when ranking by verdict. FAIL sorts last. UNKNOWN sorts after
#: WARN because an unevaluated guide is less useful than a caveated one, and
#: section 5.4 rule 1 forbids letting it look like a pass.
SEVERITY_ORDER: dict[Severity, int] = {
    Severity.PASS: 0,
    Severity.WARN: 1,
    Severity.UNKNOWN: 2,
    Severity.FAIL: 3,
}

DEFAULT_CANDIDATE_POOL_MULTIPLIER = 4
DEFAULT_CANDIDATE_POOL_FLOOR = 30
MAX_REJECTED_REPORTED = 50


def _ranking_score(published: OnTargetScore, heuristic: OnTargetScore) -> tuple[int, float, str]:
    """The ordering tier, the number used for ordering, and which model produced it.

    The published score is used when it exists. When it is withheld because the
    request is outside the model's validity domain, the labelled heuristic is
    used instead.

    The two scales are never compared. A guide carrying a published score sorts
    in tier 0 and a guide ranked by the heuristic sorts in tier 1, so a
    heuristic number can never outrank a published one just by being larger.
    Within a tier the comparison is between numbers from the same model. Each
    row records which model ordered it.
    """
    if published.score is not None:
        return 0, published.score, published.model_name
    assert heuristic.score is not None  # the heuristic always produces a number
    return 1, heuristic.score, heuristic.model_name


def _flags(report: Any, guide: EnumeratedGuide) -> list[str]:
    """Short tokens for the section 8.7 flags column, in a fixed order."""
    flags: list[str] = []
    if guide.pam_is_alternative:
        flags.append("alternative_pam")
    if guide.placement.strand == -1:
        flags.append("reverse_strand")
    for check in report.checks:
        if check.severity == Severity.FAIL:
            flags.append(f"fail:{check.check_id}")
    for check in report.checks:
        if check.severity == Severity.WARN:
            flags.append(f"warn:{check.check_id}")
    for check in report.checks:
        if check.severity == Severity.UNKNOWN:
            flags.append(f"unknown:{check.check_id}")
    return flags


def _reasoning(
    guide: EnumeratedGuide,
    published: OnTargetScore,
    heuristic: OnTargetScore,
    report: Any,
    off_target: Any,
    ranked_by: str,
) -> list[str]:
    """The per guide explanation section 8.7 calls the differentiator.

    Section 8.7: "Per guide, the reasoning: which features drove the score up or
    down. A score with no explanation is not usable, and the explanation is the
    differentiator."

    So the list states, in order: what the score is and which model said so,
    which features pushed it up, which pushed it down, what the off-target
    search covered and found, and every check that is not a plain pass.
    """
    lines: list[str] = []
    strand = "forward" if guide.placement.strand == 1 else "reverse"
    lines.append(
        f"Spacer {guide.spacer} with PAM {guide.pam} on the {strand} strand at target positions "
        f"{guide.placement.spacer_start} to {guide.placement.spacer_end}, cut site at "
        f"{guide.placement.cut_site}"
        + (
            f" and {guide.placement.cut_site_staggered} (staggered cut)"
            if guide.placement.cut_site_staggered is not None
            else ""
        )
        + "."
    )
    if published.score is not None:
        lines.append(
            f"{published.model_name}: {published.score:.1f} out of 100. "
            f"{published.disclaimer} Validity domain: {published.validity_domain}"
        )
    else:
        lines.append(
            f"{published.model_name}: no score. " + " ".join(published.caveats)
        )
    for caveat in published.caveats if published.score is not None else []:
        lines.append(f"Caveat on the published score: {caveat}")

    up = [item for item in published.reasoning if item.direction == "up"]
    down = [item for item in published.reasoning if item.direction == "down"]
    if up:
        lines.append(
            "Features that drove the published score up: "
            + "; ".join(f"{item.feature} ({item.weight:+.3f})" for item in up)
        )
    if down:
        lines.append(
            "Features that drove the published score down: "
            + "; ".join(f"{item.feature} ({item.weight:+.3f})" for item in down)
        )

    lines.append(
        f"{heuristic.model_name}: {heuristic.score:.1f} out of 100. "
        + "; ".join(f"{item.feature} {item.weight:+.1f} ({item.detail})" for item in heuristic.reasoning)
    )
    lines.append(f"Ranked by: {ranked_by}.")
    lines.append(off_target.space_statement)
    if off_target.searched:
        others = [hit for hit in off_target.hits if not hit.is_on_target]
        if off_target.specificity_score is not None:
            lines.append(
                f"{off_target.specificity_model_name}: {off_target.specificity_score:.0f} out of "
                f"100 across the searched space. {off_target.disclaimer}"
            )
        else:
            lines.append(
                f"{off_target.specificity_model_name} is withheld here. "
                + " ".join(off_target.notes)
            )
        if others:
            closest = min(others, key=lambda hit: (hit.mismatches, hit.start))
            lines.append(
                f"{len(others)} site(s) in the searched space within "
                f"{off_target.max_mismatches_searched} mismatches; the closest is in "
                f"{closest.source_label} at position {closest.start} with {closest.mismatches} "
                f"mismatch(es), {closest.seed_mismatches} of them inside the "
                f"{off_target.seed_region_nt} nt PAM-proximal seed."
            )
        else:
            lines.append("No other site in the searched space matches next to a valid PAM.")
    for check in report.checks:
        if check.severity != Severity.PASS:
            lines.append(f"{Severity(check.severity).value.upper()} {check.check_id}: {check.message}")
    return lines


class GuideRNAGenerator:
    """Section 5.2 generator for the guide RNA capability."""

    kind = CapabilityKind.GUIDE_RNA

    def __init__(
        self,
        thresholds: GuideRNAThresholds = DEFAULT_THRESHOLDS,
        evaluated_at: datetime | None = None,
        candidate_pool_size: int | None = None,
    ) -> None:
        self.thresholds = thresholds
        self.evaluated_at = evaluated_at
        self.candidate_pool_size = candidate_pool_size
        self.validator = GuideRNAValidator(thresholds=thresholds, evaluated_at=evaluated_at)

    # -- helpers ---------------------------------------------------------

    def _pool_size(self, request: GuideRNARequest) -> int:
        if self.candidate_pool_size is not None:
            return self.candidate_pool_size
        return max(
            DEFAULT_CANDIDATE_POOL_FLOOR,
            request.max_guides_returned * DEFAULT_CANDIDATE_POOL_MULTIPLIER,
        )

    def _design_id(self, request: GuideRNARequest) -> str:
        """Deterministic identifier: a digest of the inputs that change the output.

        Not a random identifier, because section 3.3 constraint 3 requires the
        same input to produce the same output, identifiers included.
        """
        payload = "|".join(
            [
                request.target_name,
                clean_sequence(request.target_sequence),
                request.nuclease,
                request.edit_intent,
                request.expression_system,
                request.host_context,
                request.off_target_space.scope,
                request.off_target_space.fasta_path or "",
                clean_sequence(request.delivery_construct_sequence)
                if request.delivery_construct_sequence
                else "",
                request.cloning_vector or "",
                str(request.max_guides_returned),
                self.validator.version,
            ]
        )
        return "grna_" + sha256(payload.encode("utf-8")).hexdigest()[:16]

    # -- composition -----------------------------------------------------

    def compose(self, request: GuideRNARequest) -> GuideRNAResult:
        """Enumerate, score, search, validate, rank (sections 8.3, 8.4, 8.6, 8.7)."""
        if not isinstance(request, GuideRNARequest):
            request = GuideRNARequest.model_validate(request)
        # Called for its exception, not its value: get_nuclease raises KeyError
        # naming every supported nuclease, and running it here means an unknown
        # name is rejected with that message before any enumeration happens. Do
        # not delete this as a no-op; the result is genuinely unused but the
        # check is the point.
        get_nuclease(request.nuclease)
        guides = enumerate_guides(request.target_sequence, request.nuclease)

        scored: list[tuple[EnumeratedGuide, OnTargetScore, OnTargetScore, int, float, str]] = []
        for guide in guides:
            published, heuristic = score_on_target(
                request,
                guide.spacer,
                guide.placement.context_30mer,
                guide.pam_is_alternative,
                thresholds=self.thresholds,
            )
            tier, value, ranked_by = _ranking_score(published, heuristic)
            scored.append((guide, published, heuristic, tier, value, ranked_by))

        scored.sort(
            key=lambda item: (
                item[0].pam_is_alternative,
                item[3],
                -item[4],
                item[0].placement.spacer_start,
                -item[0].placement.strand,
                item[0].spacer,
            )
        )
        pool_size = self._pool_size(request)
        pool = scored[:pool_size]
        deferred = scored[pool_size:]

        rows: list[tuple[tuple[Any, ...], RankedGuide]] = []
        for guide, published, heuristic, tier, value, ranked_by in pool:
            off_target = search_off_targets(
                request,
                guide.spacer,
                guide.placement,
                thresholds=self.thresholds,
            )
            design = GuideRNADesign(request=request, guide=guide.to_spec())
            report = self.validator.validate(design, off_target=off_target)
            plan = cloning_plan(request, guide.spacer, guide.guide_id)
            row = RankedGuide(
                rank=1,  # replaced after the final sort
                guide_id=guide.guide_id,
                spacer=guide.spacer,
                pam=guide.pam,
                pam_motif=guide.pam_motif,
                pam_is_alternative=guide.pam_is_alternative,
                strand=guide.placement.strand,
                placement=guide.placement,
                on_target=published,
                off_target=off_target,
                report=report,
                flags=_flags(report, guide),
                reasoning=_reasoning(
                    guide, published, heuristic, report, off_target, ranked_by
                ),
                cloning=plan,
            )
            key = (
                SEVERITY_ORDER[Severity(report.overall)],
                guide.pam_is_alternative,
                tier,
                -value,
                -(off_target.specificity_score or 0.0),
                guide.placement.spacer_start,
                -guide.placement.strand,
                guide.spacer,
            )
            rows.append((key, row))

        rows.sort(key=lambda item: item[0])
        ordered = [row for _, row in rows]

        failing = [row for row in ordered if Severity(row.report.overall) == Severity.FAIL]
        passing = [row for row in ordered if Severity(row.report.overall) != Severity.FAIL]
        returned = passing[: request.max_guides_returned]
        for index, row in enumerate(returned, start=1):
            row.rank = index

        rejected: list[dict[str, Any]] = []
        for row in failing[:MAX_REJECTED_REPORTED]:
            rejected.append(
                {
                    "guide_id": row.guide_id,
                    "spacer": row.spacer,
                    "pam": row.pam,
                    "strand": row.strand,
                    "reason": "validation failed",
                    "failing_checks": [
                        {"check_id": check.check_id, "message": check.message}
                        for check in row.report.checks
                        if check.severity == Severity.FAIL
                    ],
                }
            )
        for guide, _published, _heuristic, _tier, _value, _ranked_by in deferred[
            :MAX_REJECTED_REPORTED
        ]:
            rejected.append(
                {
                    "guide_id": guide.guide_id,
                    "spacer": guide.spacer,
                    "pam": guide.pam,
                    "strand": guide.placement.strand,
                    "reason": (
                        "ranked below the candidate pool, so the declared off-target space was "
                        "not searched for it. This is not a statement that it is clean."
                    ),
                    "failing_checks": [],
                }
            )

        statement = self._space_statement(request)
        notes = self._notes(request, guides, pool, deferred, returned, failing)
        return GuideRNAResult(
            design_id=self._design_id(request),
            target_name=request.target_name,
            nuclease=request.nuclease,
            guides_enumerated=len(guides),
            guides_returned=returned,
            off_target_space_statement=statement,
            rejected=rejected,
            notes=notes,
            parameters_used=self.parameters_used(request),
            provenance=self.provenance(request, returned),
        )

    def _space_statement(self, request: GuideRNARequest) -> str:
        """The section 8.6 sentence for the whole result, generated once.

        It describes the declared space itself, so it does not depend on which
        guides came back, and it is identical to the sentence on every row.
        """
        sources = collect_sources(request)
        total = sum(source.length for source in sources)
        over_limit = (
            self.thresholds.off_target_max_search_bp
            if total > self.thresholds.off_target_max_search_bp
            else None
        )
        return space_statement(
            request.off_target_space,
            sources,
            has_delivery_construct=bool(request.delivery_construct_sequence),
            over_limit_bp=over_limit,
        )

    def _notes(
        self,
        request: GuideRNARequest,
        guides: list[EnumeratedGuide],
        pool: list[tuple[Any, ...]],
        deferred: list[tuple[Any, ...]],
        returned: list[RankedGuide],
        failing: list[RankedGuide],
    ) -> list[str]:
        """Statements that belong with the whole result, not with one row."""
        notes = [
            f"Both strands of the {len(clean_sequence(request.target_sequence))} nt target were "
            f"scanned: {sum(1 for g in guides if g.placement.strand == 1)} forward-strand and "
            f"{sum(1 for g in guides if g.placement.strand == -1)} reverse-strand guides were "
            "enumerated.",
        ]
        alternative = sum(1 for guide in guides if guide.pam_is_alternative)
        if alternative:
            spec = get_nuclease(request.nuclease)
            notes.append(
                f"{alternative} of the enumerated guides use an alternative PAM "
                f"({', '.join(a.motif for a in spec.alternative_pams)}), which is tolerated at "
                "substantially reduced efficiency and is reported as a warning, never as a "
                "primary PAM."
            )
        if deferred:
            notes.append(
                f"The declared off-target space was searched for the top {len(pool)} guides by "
                f"predicted activity. {len(deferred)} lower-ranked guides were not searched, and "
                "they are listed as not searched rather than as clean. Raise the candidate pool "
                "size to search more of them."
            )
        if failing:
            notes.append(
                f"{len(failing)} guide(s) failed validation and are listed separately with the "
                "check that rejected each one."
            )
        scored_rows = [row for row in returned if row.on_target.score is not None]
        withheld_rows = [row for row in returned if row.on_target.score is None]
        if returned and not withheld_rows:
            notes.append(
                "Every returned guide carries a score from the published on-target model, and the "
                "ranking used that score. It is a prediction, not a measurement."
            )
        elif returned and not scored_rows:
            notes.append(
                "The published on-target model is outside its validity domain for every returned "
                "guide, so no published score is shown and the ranking used the labeled "
                "heuristic. The heuristic is a stated combination of sequence features, not a "
                "published score, and its numeric value is not comparable to one."
            )
        elif returned:
            notes.append(
                f"{len(scored_rows)} returned guide(s) carry a published on-target score and "
                f"{len(withheld_rows)} do not, because the model's 30 nt context window does not "
                "exist for them. Guides with a published score are ranked above guides ranked by "
                "the labeled heuristic, so the two scales are never compared against each other."
            )
        if not returned:
            notes.append(
                "No guide passed validation for this request. Every enumerated guide is listed "
                "with the check that rejected it, so the reason is visible rather than implied."
            )
        return notes

    # -- contract surfaces -----------------------------------------------

    def parameters_used(self, request: GuideRNARequest) -> dict[str, Any]:
        """Section 5.4 rule 3: every threshold that was applied."""
        payload = self.validator.parameters_used(request.nuclease)
        payload["candidate_pool_size"] = self._pool_size(request)
        payload["max_guides_returned"] = request.max_guides_returned
        payload["off_target_scope"] = request.off_target_space.scope
        payload["expression_system"] = request.expression_system
        payload["host_context"] = request.host_context
        payload["edit_intent"] = request.edit_intent
        return payload

    def provenance(self, request: GuideRNARequest, returned: list[RankedGuide]) -> list[str]:
        """Section 5.4 rule 5: every part and template behind the output.

        A guide spacer is a window of the user's own target, and the only other
        sequences in the output are the published vector overhangs and
        scaffolds, so every base is attributable (section 11.1).
        """
        entries = [
            f"user_input:target_sequence:{request.target_name}",
            f"nuclease_geometry:{geometry_facts(get_nuclease(request.nuclease)).citation}",
        ]
        if request.delivery_construct_sequence:
            entries.append(
                "user_input:delivery_construct_sequence:"
                f"{request.delivery_construct_name or 'unnamed'}"
            )
        if request.off_target_space.scope == "supplied_fasta" and request.off_target_space.fasta_path:
            entries.append(f"user_input:off_target_fasta:{request.off_target_space.fasta_path}")
        seen: set[str] = set()
        for row in returned:
            if row.cloning is None:
                continue
            key = f"cloning_vector:{row.cloning.vector_id}:{row.cloning.vector_name}"
            if key not in seen:
                seen.add(key)
                entries.append(key)
                entries.append(f"cloning_vector_source:{row.cloning.vector_source}")
        from packages.validation.grna import MIT_CITATION
        from packages.validation.grna.ontarget import HEURISTIC_CITATION, RULE_SET_1_CITATION

        entries.append(f"on_target_model:{RULE_SET_1_CITATION}")
        entries.append(f"on_target_fallback:{HEURISTIC_CITATION}")
        entries.append(f"off_target_model:{MIT_CITATION}")
        return entries

    def design_result(self, request: GuideRNARequest) -> tuple[GuideRNAResult, DesignResult]:
        """The section 5.1 `DesignResult` beside the capability-specific result.

        `artifacts` carries the two things a user takes away: the ranked table
        as tab separated text, and the oligo order table. Both repeat the
        off-target space statement verbatim, because section 8.6 requires it in
        every export.
        """
        result = self.compose(request)
        report = (
            result.guides_returned[0].report
            if result.guides_returned
            else self.validator.validate(
                GuideRNADesign(
                    request=request,
                    guide=_placeholder_guide(request),
                )
            )
        )
        artifacts = {
            "guide_table.tsv": render_guide_table(result),
            "oligo_order_table.tsv": render_oligo_table(result),
            "off_target_space.txt": result.off_target_space_statement,
        }
        return result, DesignResult(
            capability=CapabilityKind.GUIDE_RNA,
            design_id=result.design_id,
            report=report,
            artifacts=artifacts,
            provenance=result.provenance,
            parameters_used=result.parameters_used,
        )


def _placeholder_guide(request: GuideRNARequest):
    """A guide spec for the empty case, so a report still exists and still fails loudly.

    When no guide could be enumerated there is nothing to validate, but the
    contract requires a report. This builds a spec from the first window of the
    target so the checks run and say exactly what is wrong with it, rather than
    returning an empty report that could read as a pass.
    """
    from packages.core.schemas.grna import GuideSpec

    spec = get_nuclease(request.nuclease)
    target = clean_sequence(request.target_sequence)
    spacer = target[: spec.spacer_length] or "A" * spec.spacer_length
    pam_start = spec.spacer_length
    pam = target[pam_start : pam_start + spec.pam_length] or "N" * spec.pam_length
    return GuideSpec(spacer=spacer, pam=pam, strand=1, spacer_start=0)


def render_guide_table(result: GuideRNAResult) -> str:
    """The section 8.7 ranked guide table as tab separated text.

    Columns: rank, spacer written 5' to 3', PAM, strand, coordinates, on-target
    score with its model, off-target summary, flags. The off-target space
    statement is the first line of the file, verbatim (section 8.6).
    """
    lines = [
        result.off_target_space_statement,
        "\t".join(
            [
                "rank",
                "spacer_5_to_3",
                "pam",
                "strand",
                "target_start",
                "target_end",
                "cut_site",
                "on_target_score",
                "on_target_model",
                "on_target_model_kind",
                "off_target_sites",
                "off_target_specificity",
                "flags",
            ]
        ),
    ]
    for row in result.guides_returned:
        others = [hit for hit in row.off_target.hits if not hit.is_on_target]
        score = "withheld" if row.on_target.score is None else f"{row.on_target.score:.1f}"
        specificity = (
            "withheld"
            if row.off_target.specificity_score is None
            else f"{row.off_target.specificity_score:.0f}"
        )
        lines.append(
            "\t".join(
                [
                    str(row.rank),
                    row.spacer,
                    row.pam,
                    "+" if row.strand == 1 else "-",
                    str(row.placement.spacer_start),
                    str(row.placement.spacer_end),
                    str(row.placement.cut_site),
                    score,
                    row.on_target.model_name,
                    row.on_target.model_kind,
                    str(len(others)),
                    specificity,
                    ";".join(row.flags),
                ]
            )
        )
    return "\n".join(lines) + "\n"


def render_oligo_table(result: GuideRNAResult) -> str:
    """The orderable oligo table as tab separated text (section 8.7).

    The off-target space statement is the first line here too, because section
    8.6 requires it in every export and this file is the one a lab pastes into
    an order form.
    """
    lines = [
        result.off_target_space_statement,
        "\t".join(
            ["rank", "guide_id", "oligo_name", "sequence_5_to_3", "length_nt", "role", "vector", "notes"]
        ),
    ]
    for row in result.guides_returned:
        if row.cloning is None:
            continue
        for oligo in row.cloning.oligos:
            lines.append(
                "\t".join(
                    [
                        str(row.rank),
                        row.guide_id,
                        oligo.name,
                        oligo.sequence,
                        str(oligo.length_nt),
                        oligo.role,
                        row.cloning.vector_name,
                        " ".join(oligo.notes),
                    ]
                )
            )
    return "\n".join(lines) + "\n"


def build_generator() -> GuideRNAGenerator:
    """Zero-argument factory for the capability registry."""
    return GuideRNAGenerator()
