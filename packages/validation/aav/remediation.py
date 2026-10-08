"""The remediation engine of section 6.6.

When a cassette does not fit, this module computes the fix. It does not stop at
"too long", because a validator that only rejects is not a tool.

The five steps of section 6.6, implemented in `build_remediation`:

1. Compute the overage, `total - target`, against the band that applies to the
   modality (single stranded or self complementary).
2. For every substitutable element, enumerate the part registry for parts in
   the same category with compatible host and tissue annotations.
3. Compute the bp saved by each candidate change.
4. Report the minimum set of changes that closes the overage, preferring fewer
   changes, then preferring to preserve the user's stated
   `promoter_preference`.
5. If no combination of registry changes closes the gap, say so explicitly,
   report the remaining deficit, and suggest a shorter transgene variant or a
   dual vector approach.

Determinism: the search is an exhaustive enumeration over a sorted candidate
list with a total ordering on the result, so the same design always yields the
same ranked plans. There is no randomness and no model call (section 3.3
constraint 3).

Scope of the changes considered. Promoter, polyA, 5' enhancer, intron and WPRE
can be substituted with a shorter registry part of the same category, and the
three optional roles of section 6.2 (enhancer, intron, WPRE) can also simply be
dropped. The engine never proposes touching:

* the ITRs, because they are required in cis (section 6.2) and the registry
  carries one reference pair per serotype, so there is nothing shorter to
  substitute; and
* the transgene coding sequence, because that is the payload the user asked
  for. Shortening it is step 5's explicit, separate suggestion, reported with
  the exact length that would fit.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product

from packages.core.part_registry import PartCategory, PartRecord, list_parts
from packages.core.schemas.aav import (
    OPTIONAL_ROLES,
    ROLE_PART_CATEGORY,
    AAVDesign,
    CassetteElement,
    CassetteElementRole,
    ElementChange,
    RemediationPlan,
    RemediationReport,
)

from .constants import AAVThresholds, DEFAULT_THRESHOLDS

# Roles the engine will consider changing. Ordered as in section 6.2 so the
# enumeration, and therefore the output, is stable.
SUBSTITUTABLE_ROLES: tuple[CassetteElementRole, ...] = (
    CassetteElementRole.ENHANCER,
    CassetteElementRole.PROMOTER,
    CassetteElementRole.INTRON,
    CassetteElementRole.WPRE,
    CassetteElementRole.POLYA,
)

# Host compatibility assumed for an element that carries no registry part, so a
# substitution can still be offered for it. Every part in data/parts declares
# this host, and the capability is a mammalian gene therapy vector designer.
DEFAULT_HOST = "mammalian_general"


def short_label(part_id: str) -> str:
    """A short, conventional label for a part id, for example promoter.cag to CAG."""
    local = part_id.split(".", 1)[1] if "." in part_id else part_id
    return local.upper()


def describe_part(part_id: str | None, name: str, length_bp: int) -> str:
    """How an element is named in a remediation message.

    Both the short label and the registry id appear, so the text reads well and
    is still unambiguous about which record is meant.
    """
    if part_id is None:
        return f"{name} (user supplied, {length_bp:,} bp)"
    return f"{short_label(part_id)} ({part_id}, {length_bp:,} bp)"


# Registry note sentences that carry build metadata rather than a biological
# tradeoff, and are therefore dropped from the remediation text.
_NOTE_NOISE = ("the sense strand contains", "see provenance.md", "literature describing the element")


def _first_sentences(text: str | None, count: int = 2) -> str:
    """The first `count` useful sentences of a registry note, as the tradeoff detail."""
    if not text:
        return ""
    sentences: list[str] = []
    remaining = text.strip()
    while remaining:
        index = remaining.find(". ")
        if index == -1:
            sentences.append(remaining)
            break
        sentences.append(remaining[: index + 1])
        remaining = remaining[index + 2 :]
    useful = [
        sentence.strip()
        for sentence in sentences
        if not any(marker in sentence.lower() for marker in _NOTE_NOISE)
    ]
    return " ".join(useful[:count]).strip()


def _host_compatible(candidate: PartRecord, current: PartRecord | None) -> bool:
    """Section 6.6 step 2: the same or compatible `host_compatibility`."""
    required = set(current.host_compatibility) if current is not None else {DEFAULT_HOST}
    return bool(set(candidate.host_compatibility) & required)


def _tissue_compatible(candidate: PartRecord, design: AAVDesign, thresholds: AAVThresholds) -> bool:
    """Section 6.6 step 2: the same or compatible `tissue_specificity`.

    Only promoters carry a tissue annotation in this registry. A promoter
    candidate is admissible when its annotation is accepted for the design's
    `target_tissue` by the configurable `tissue_compatibility` table, which is
    the same table `aav.promoter_tissue_match` uses. Substituting a promoter
    for one that would itself raise that warning is not a fix.
    """
    if candidate.tissue_specificity is None:
        return True
    allowed = thresholds.tissue_compatibility.get(design.target_tissue, frozenset())
    return candidate.tissue_specificity in allowed


def _promoter_tradeoff(current: PartRecord | None, candidate: PartRecord) -> str:
    current_tissue = current.tissue_specificity if current is not None else None
    note = _first_sentences(candidate.notes)
    if current_tissue is not None and candidate.tissue_specificity == current_tissue:
        lead = (
            f"{short_label(candidate.id)} is annotated {candidate.tissue_specificity} like "
            f"{short_label(current.id)}, so tissue specificity is preserved."
        )
    elif candidate.tissue_specificity == "ubiquitous" and current_tissue not in (None, "ubiquitous"):
        lead = (
            f"{short_label(candidate.id)} is ubiquitous while {short_label(current.id)} is "
            f"{current_tissue} specific, so expression would no longer be restricted to that cell type."
        )
    elif current_tissue is None:
        lead = f"{short_label(candidate.id)} is annotated {candidate.tissue_specificity}."
    else:
        lead = (
            f"{short_label(candidate.id)} is annotated {candidate.tissue_specificity} and "
            f"{short_label(current.id)} is {current_tissue}; confirm the intended cell type."
        )
    return f"{lead} Registry note: {note}" if note else lead


def _substitution_tradeoff(
    role: CassetteElementRole, current: PartRecord | None, candidate: PartRecord
) -> str:
    if role is CassetteElementRole.PROMOTER:
        return _promoter_tradeoff(current, candidate)
    note = _first_sentences(candidate.notes)
    lead = f"{short_label(candidate.id)} replaces the same functional role."
    return f"{lead} Registry note: {note}" if note else lead


def _removal_tradeoff(role: CassetteElementRole, current: PartRecord | None, name: str) -> str:
    note = _first_sentences(current.notes) if current is not None else ""
    lead = (
        f"{role.value} is optional in the section 6.2 cassette order, so {name} can be dropped outright."
    )
    return f"{lead} Registry note: {note}" if note else lead


@dataclass(frozen=True)
class _Candidate:
    """One possible change to one element, keyed by the element's position."""

    element_index: int
    change: ElementChange

    @property
    def sort_key(self) -> tuple[int, str, str]:
        return (
            self.element_index,
            self.change.kind,
            self.change.to_part_id or "",
        )


def _candidates_for_element(
    index: int,
    element: CassetteElement,
    design: AAVDesign,
    parts: dict[str, PartRecord],
    thresholds: AAVThresholds,
) -> list[_Candidate]:
    role = CassetteElementRole(element.role)
    if role not in SUBSTITUTABLE_ROLES:
        return []
    current = parts.get(element.part_id) if element.part_id else None
    category = PartCategory(ROLE_PART_CATEGORY[role])
    out: list[_Candidate] = []
    for part in sorted(parts.values(), key=lambda record: record.id):
        if PartCategory(part.category) is not category:
            continue
        if part.id == element.part_id:
            continue
        saved = element.length_bp - part.length_bp
        if saved <= 0:
            continue
        if not _host_compatible(part, current):
            continue
        if not _tissue_compatible(part, design, thresholds):
            continue
        out.append(
            _Candidate(
                index,
                ElementChange(
                    kind="substitute",
                    role=role,
                    from_part_id=element.part_id,
                    from_name=describe_part(element.part_id, element.name, element.length_bp),
                    from_bp=element.length_bp,
                    to_part_id=part.id,
                    to_name=describe_part(part.id, part.name, part.length_bp),
                    to_bp=part.length_bp,
                    saved_bp=saved,
                    tradeoff=_substitution_tradeoff(role, current, part),
                ),
            )
        )
    if role in OPTIONAL_ROLES:
        out.append(
            _Candidate(
                index,
                ElementChange(
                    kind="remove",
                    role=role,
                    from_part_id=element.part_id,
                    from_name=describe_part(element.part_id, element.name, element.length_bp),
                    from_bp=element.length_bp,
                    saved_bp=element.length_bp,
                    tradeoff=_removal_tradeoff(
                        role, current, describe_part(element.part_id, element.name, element.length_bp)
                    ),
                ),
            )
        )
    return sorted(out, key=lambda candidate: candidate.sort_key)


def _preserves_preference(design: AAVDesign, changes: tuple[ElementChange, ...]) -> bool:
    """Whether a plan leaves the user's stated `promoter_preference` in place."""
    if not design.promoter_preference:
        return True
    for change in changes:
        if CassetteElementRole(change.role) is not CassetteElementRole.PROMOTER:
            continue
        if change.kind == "remove" or change.to_part_id != design.promoter_preference:
            return False
    return True


def build_remediation(
    design: AAVDesign,
    thresholds: AAVThresholds = DEFAULT_THRESHOLDS,
    parts: list[PartRecord] | None = None,
    *,
    self_complementary: bool | None = None,
) -> RemediationReport:
    """Run the section 6.6 algorithm against one design.

    `thresholds` must already carry any `packaging_limit_bp` override, which
    the validator applies before calling here, so that the overage is measured
    against exactly the target the report will quote.

    `self_complementary` chooses which band the overage is measured against,
    defaulting to the design's own modality. It is passed explicitly because
    `aav.packaging_limit` always measures against the single stranded band and
    `aav.sc_capacity` against the halved one, so each needs its remediation
    computed against the target its own message quotes.
    """
    registry = {record.id: record for record in (parts if parts is not None else list_parts())}
    modality_sc = design.self_complementary if self_complementary is None else self_complementary
    target, soft, hard = thresholds.band(modality_sc)
    total = design.total_bp
    overage = max(0, total - target)

    candidates: list[_Candidate] = []
    for index, element in enumerate(design.elements):
        candidates.extend(_candidates_for_element(index, element, design, registry, thresholds))

    by_index: dict[int, list[_Candidate]] = {}
    for candidate in candidates:
        by_index.setdefault(candidate.element_index, []).append(candidate)

    # The largest saving available if every element were changed at once. Used
    # for step 5, and for the longest transgene that could still fit.
    max_available = sum(max(change.change.saved_bp for change in group) for group in by_index.values())
    preference_saving = sum(
        max(
            (
                item.change.saved_bp
                for item in group
                if _preserves_preference(design, (item.change,))
            ),
            default=0,
        )
        for group in by_index.values()
    )

    cds = design.first_with_role(CassetteElementRole.CDS)
    cds_bp = cds.length_bp if cds is not None else 0
    fixed_remainder = total - max_available - cds_bp
    max_transgene = max(0, target - fixed_remainder)

    plans: list[RemediationPlan] = []
    if overage > 0:
        indices = sorted(by_index)
        limit = max(1, min(thresholds.remediation_max_changes, len(indices)))
        for size in range(1, limit + 1):
            for chosen in combinations(indices, size):
                for picks in product(*(by_index[index] for index in chosen)):
                    saved = sum(pick.change.saved_bp for pick in picks)
                    if saved < overage:
                        continue
                    changes = tuple(pick.change for pick in picks)
                    plans.append(
                        RemediationPlan(
                            changes=list(changes),
                            saved_bp=saved,
                            resulting_bp=total - saved,
                            resulting_headroom_bp=target - (total - saved),
                            preserves_promoter_preference=_preserves_preference(design, changes),
                        )
                    )
        plans = _rank(plans)[: thresholds.remediation_max_plans]

    remaining = 0 if (plans or overage == 0) else max(0, overage - max_available)
    return RemediationReport(
        total_bp=total,
        target_bp=target,
        soft_limit_bp=soft,
        hard_limit_bp=hard,
        overage_bp=overage,
        plans=plans,
        max_available_saving_bp=max_available,
        preference_preserving_saving_bp=preference_saving,
        promoter_preference=design.promoter_preference,
        remaining_deficit_bp=remaining,
        max_transgene_bp=max_transgene,
        considered_change_count=len(candidates),
    )


def _rank(plans: list[RemediationPlan]) -> list[RemediationPlan]:
    """Order plans by the section 6.6 step 4 preference, with a documented third key.

    1. Fewer changes first ("preferring fewer substitutions").
    2. Then plans that keep the user's stated `promoter_preference`.
    3. Then the larger total saving, which gives the most headroom and matches
       the worked example in section 6.6, where the single largest substitution
       is the headline recommendation and the smaller alternatives follow.
    4. Then a lexical key over the changes, purely so the order is total and
       the output is byte stable.
    """

    def key(plan: RemediationPlan) -> tuple[int, int, int, tuple[tuple[str, str, str], ...]]:
        return (
            plan.change_count,
            0 if plan.preserves_promoter_preference else 1,
            -plan.saved_bp,
            tuple(
                (CassetteElementRole(change.role).value, change.kind, change.to_part_id or "")
                for change in plan.changes
            ),
        )

    return sorted(plans, key=key)


# ---------------------------------------------------------------------------
# Rendering: the human readable message and the structured entries
# ---------------------------------------------------------------------------


def _plan_sentence(plan: RemediationPlan, target_bp: int) -> str:
    verb = "One change closes it" if plan.change_count == 1 else f"{plan.change_count} changes close it"
    return (
        f"{verb}: {plan.describe()}, bringing the cassette to {plan.resulting_bp:,} bp, "
        f"{plan.resulting_headroom_bp:,} bp under the {target_bp:,} bp target. "
        + " ".join(change.tradeoff for change in plan.changes)
    )


def render_remediation_message(report: RemediationReport, modality: str) -> str:
    """The section 6.6 output as prose, for `CheckResult.message` (section 5.4 rule 2).

    Modelled on the worked example in section 6.6: the measured length, the
    target, the overage, where the design sits relative to the soft limit and
    the hard ceiling, then the recommended change with its numbers and its
    biological tradeoff, then an alternative, then step 5 when nothing closes
    the gap. It also says out loud when the user's stated promoter preference
    cannot be kept, because step 4 asks the engine to prefer keeping it.
    """
    headroom_to_hard = report.hard_limit_bp - report.total_bp
    relative_to_soft = (
        f"{report.total_bp - report.soft_limit_bp:,} bp above the {report.soft_limit_bp:,} bp soft limit"
        if report.total_bp > report.soft_limit_bp
        else f"{report.soft_limit_bp - report.total_bp:,} bp under the {report.soft_limit_bp:,} bp soft limit"
    )
    relative_to_hard = (
        f"{headroom_to_hard:,} bp under the hard ceiling of {report.hard_limit_bp:,} bp"
        if headroom_to_hard >= 0
        else f"{-headroom_to_hard:,} bp over the hard ceiling of {report.hard_limit_bp:,} bp"
    )
    parts = [
        f"Cassette is {report.total_bp:,} bp. The {modality} packaging target is {report.target_bp:,} bp, "
        f"so the design is {report.overage_bp:,} bp over the target, {relative_to_soft}, and "
        f"{relative_to_hard}."
    ]
    if not report.plans:
        parts.append(
            f"No combination of part registry substitutions closes the gap: the largest saving available "
            f"across every substitutable element is {report.max_available_saving_bp:,} bp, which still "
            f"leaves {report.remaining_deficit_bp:,} bp over the target. The transgene itself needs a "
            f"shorter variant (at most {report.max_transgene_bp:,} bp of coding sequence would fit once "
            f"every available saving is applied) or the payload needs splitting across a dual vector "
            f"approach."
        )
        return " ".join(parts)
    parts.append(_plan_sentence(report.plans[0], report.target_bp))
    first = report.plans[0]
    alternative = next((plan for plan in report.plans[1:] if plan.changes != first.changes), None)
    if alternative is not None:
        parts.append(
            f"Alternative: {alternative.describe()}, giving {alternative.resulting_bp:,} bp, "
            f"{alternative.resulting_headroom_bp:,} bp under the target."
        )
    if report.promoter_preference and not any(plan.preserves_promoter_preference for plan in report.plans):
        parts.append(
            f"No option keeps the stated promoter preference {report.promoter_preference}: the savings "
            f"available without touching the promoter total {report.preference_preserving_saving_bp:,} bp "
            f"against a {report.overage_bp:,} bp overage, so the promoter has to change or the transgene "
            f"has to shrink to at most {report.max_transgene_bp:,} bp."
        )
    if len(report.plans) > 2:
        parts.append(
            f"{len(report.plans)} ranked options are reported in the structured remediation field."
        )
    return " ".join(parts)


def remediation_entries(report: RemediationReport) -> list[str]:
    """The structured form for `CheckResult.remediation`.

    One line per ranked plan, in `key=value` records separated by pipes, so the
    gold harness and the UI can assert a specific substitution and its bp
    without matching prose (the reason the field exists; see the WP-02 note in
    PROGRESS.md). The readable version of the same content stays in
    `CheckResult.message`, as section 5.4 rule 2 requires.
    """
    entries: list[str] = [
        f"overage_bp={report.overage_bp}"
        f" | total_bp={report.total_bp}"
        f" | target_bp={report.target_bp}"
        f" | soft_limit_bp={report.soft_limit_bp}"
        f" | hard_limit_bp={report.hard_limit_bp}"
        f" | plans={len(report.plans)}"
        f" | max_available_saving_bp={report.max_available_saving_bp}"
        f" | preference_preserving_saving_bp={report.preference_preserving_saving_bp}"
        f" | promoter_preference={report.promoter_preference or 'none'}"
        f" | max_transgene_bp={report.max_transgene_bp}"
    ]
    for rank, plan in enumerate(report.plans, start=1):
        actions = "; ".join(
            (
                f"remove {change.from_part_id or 'user supplied'}"
                if change.kind == "remove"
                else f"substitute {change.from_part_id or 'user supplied'} -> {change.to_part_id}"
            )
            + f" (saves {change.saved_bp} bp)"
            for change in plan.changes
        )
        entries.append(
            f"plan={rank}"
            f" | changes={plan.change_count}"
            f" | saves_bp={plan.saved_bp}"
            f" | result_bp={plan.resulting_bp}"
            f" | headroom_bp={plan.resulting_headroom_bp}"
            f" | preserves_promoter_preference={'yes' if plan.preserves_promoter_preference else 'no'}"
            f" | actions={actions}"
            f" | tradeoff={' '.join(change.tradeoff for change in plan.changes)}"
        )
    if not report.plans:
        entries.append(
            f"plan=none"
            f" | remaining_deficit_bp={report.remaining_deficit_bp}"
            f" | max_transgene_bp={report.max_transgene_bp}"
            f" | actions=shorten the transgene to at most {report.max_transgene_bp} bp, or split the payload "
            f"across a dual vector approach"
        )
    return entries
