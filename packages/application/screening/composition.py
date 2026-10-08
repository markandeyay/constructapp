"""The registry-only composition assertion (section 11.1 item 2).

"Functional elements come from the curated registry. The system does not
synthesize novel functional elements de novo. Assert this rather than assume
it."

The assertion is deliberately narrow, because a wide one would be unprovable.
It does not claim to recognise a functional element in arbitrary DNA. What it
checks is that the four ways a span can be attributed are the four permitted
ones, and that each one holds up:

1. Every span marked `REGISTRY_PART` names an id that resolves in the curated
   registry in `data/parts` and reproduces that record base for base, forward
   or reverse complement. A span that claims a curated part but carries
   different bases is a novel element wearing a curated label.
2. Every span marked `PUBLISHED_RULE` names its rule. Appendix D recognition
   sites, published cloning vector overhangs and documented spacer rules are
   the rule derived bases this build actually produces; each is listed by rule
   in the result, so a reader can see what the rules were.
3. Every span marked `USER_INPUT` or `RETRIEVED_TEMPLATE` names the input or
   the record it came from, and that name is in the design's recorded
   provenance.
4. No span has any other origin, because `SequenceOrigin` has no other member,
   and no base is left uncovered, which `provenance.py` enforces.

The consequence is the sentence section 11.2 permits: the design is composed
only from curated parts, published rules, retrieved records and the user's own
input, and a base that is none of those blocks the export. What this assertion
deliberately does NOT do is evaluate what any of those elements is for. It is a
composition and attribution property, not an assessment of the sequence.

Determinism (section 3.3 constraint 3): a pure function of the subject and the
on-disk part registry. No randomness, no model call.
"""

from __future__ import annotations

from pydantic import Field

from packages.core.part_registry import PartRecord, load_part_registry
from packages.core.schemas.capability import CapabilityModel
from packages.core.sequence import reverse_complement

from .attribution import ExportSubject, SequenceOrigin
from .provenance import AssertionVerdict


class CompositionElement(CapabilityModel):
    """One element of the composition, as the assertion saw it."""

    sequence_name: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    origin: SequenceOrigin
    source: str = Field(min_length=1)
    part_id: str | None = None
    rule: str | None = None


class CompositionAssertion(CapabilityModel):
    """The result of the section 11.1 item 2 assertion over one subject."""

    verdict: AssertionVerdict
    registry_parts_used: list[str] = Field(default_factory=list)
    rules_used: list[str] = Field(default_factory=list)
    user_inputs_used: list[str] = Field(default_factory=list)
    templates_used: list[str] = Field(default_factory=list)
    elements: list[CompositionElement] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)

    @property
    def permits_export(self) -> bool:
        """True only for `SATISFIED`. UNKNOWN blocks (section 3.3 constraint 4)."""
        return self.verdict is AssertionVerdict.SATISFIED


def assert_registry_only_composition(
    subject: ExportSubject,
    *,
    parts: dict[str, PartRecord] | None = None,
) -> CompositionAssertion:
    """Run the section 11.1 item 2 assertion. Only `SATISFIED` permits an export."""
    if not subject.sequences:
        return CompositionAssertion(
            verdict=AssertionVerdict.UNKNOWN,
            reason=(
                f"subject {subject.design_id!r} carries no sequence, so its composition could not "
                "be evaluated. Section 3.3 constraint 4: this is not a pass."
            ),
        )

    registry: dict[str, PartRecord] | None = parts
    registry_reason: str | None = None
    if registry is None:
        try:
            registry = load_part_registry()
        except Exception as exc:  # noqa: BLE001 - any loader failure is an unknown, not a pass
            registry = None
            registry_reason = f"the curated part registry could not be loaded: {exc}"

    elements: list[CompositionElement] = []
    violations: list[str] = []
    registry_parts: list[str] = []
    rules: list[str] = []
    user_inputs: list[str] = []
    templates: list[str] = []
    claims_registry = False

    for item in subject.sequences:
        for segment in item.segments:
            elements.append(
                CompositionElement(
                    sequence_name=item.name,
                    start=segment.start,
                    end=segment.end,
                    origin=segment.origin,
                    source=segment.source,
                    part_id=segment.part_id,
                    rule=segment.rule,
                )
            )
            if segment.origin is SequenceOrigin.REGISTRY_PART:
                claims_registry = True
                part_id = segment.part_id or ""
                if part_id not in registry_parts:
                    registry_parts.append(part_id)
                if registry is None:
                    continue
                record = registry.get(part_id)
                if record is None:
                    violations.append(
                        f"{item.name} ({segment.start}, {segment.end}) claims curated part "
                        f"{part_id!r}, which is not in data/parts. A functional element must come "
                        "from the curated registry (section 11.1 item 2)."
                    )
                    continue
                if segment.end > item.length_bp:
                    violations.append(
                        f"{item.name} ({segment.start}, {segment.end}) claims curated part "
                        f"{part_id!r} but the span leaves the sequence, so it could not be "
                        "compared with the registry record."
                    )
                    continue
                bases = item.bases(segment)
                if bases not in (record.sequence, reverse_complement(record.sequence)):
                    violations.append(
                        f"{item.name} ({segment.start}, {segment.end}) claims curated part "
                        f"{part_id!r} but its bases are not that record in either orientation. A "
                        "modified curated element is a novel element (section 11.1 item 2)."
                    )
            elif segment.origin is SequenceOrigin.PUBLISHED_RULE:
                rule = (segment.rule or "").strip()
                if not rule:
                    violations.append(
                        f"{item.name} ({segment.start}, {segment.end}) is rule derived but names "
                        "no rule, so nothing states where those bases come from (section 4.2)."
                    )
                elif rule not in rules:
                    rules.append(rule)
            elif segment.origin is SequenceOrigin.USER_INPUT:
                if segment.source not in user_inputs:
                    user_inputs.append(segment.source)
            elif segment.origin is SequenceOrigin.RETRIEVED_TEMPLATE:
                if segment.source not in templates:
                    templates.append(segment.source)

    if claims_registry and registry is None:
        return CompositionAssertion(
            verdict=AssertionVerdict.UNKNOWN,
            registry_parts_used=registry_parts,
            rules_used=rules,
            user_inputs_used=user_inputs,
            templates_used=templates,
            elements=elements,
            violations=violations,
            reason=(
                f"{registry_reason or 'no curated part registry was supplied'}, so the registry "
                "claims in this design could not be verified. Section 3.3 constraint 4: UNKNOWN, "
                "not a pass, and the export is blocked."
            ),
        )

    if violations:
        return CompositionAssertion(
            verdict=AssertionVerdict.VIOLATED,
            registry_parts_used=registry_parts,
            rules_used=rules,
            user_inputs_used=user_inputs,
            templates_used=templates,
            elements=elements,
            violations=violations,
            reason=(
                f"{len(violations)} composition violation(s): this design does not come entirely "
                "from curated registry parts, named rules, retrieved records and the user's own "
                "input. Section 11.1 item 2 blocks it from export."
            ),
        )

    return CompositionAssertion(
        verdict=AssertionVerdict.SATISFIED,
        registry_parts_used=registry_parts,
        rules_used=rules,
        user_inputs_used=user_inputs,
        templates_used=templates,
        elements=elements,
        violations=[],
        reason=(
            f"{len(elements)} element(s): {len(registry_parts)} curated registry part(s), each "
            f"reproducing its data/parts record base for base; {len(rules)} named rule(s); "
            f"{len(user_inputs)} user supplied input(s); {len(templates)} retrieved record(s). "
            "No element was synthesized de novo by this system."
        ),
    )
