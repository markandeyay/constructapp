"""The attribution adapters, run against each capability's real output.

These tests use the real curated registry in `data/parts` and the real
composers, because the point of an adapter is that the design a capability
actually produces can be attributed base by base. A fixture that attributes
itself proves nothing.
"""

from __future__ import annotations

import random

import pytest

from packages.application.screening import (
    AssertionVerdict,
    SequenceOrigin,
    assert_provenance,
    screen_design,
)
from packages.application.screening.adapters import (
    NoAttributionAdapter,
    classify_source,
    subject_for_design,
)
from packages.application.screening.adapters.aav import CASSETTE_SEQUENCE_NAME, aav_subject
from packages.core.schemas.aav import AAVRequest, CassetteElementRole
from packages.core.schemas.assembly import AssemblyRequest, Fragment
from packages.core.schemas.capability import CapabilityKind
from packages.core.schemas.grna import GuideRNARequest, OffTargetSpace

# A deterministic synthetic coding sequence. It stands in for the transgene,
# which section 6.3 treats as user input, and carries no biological claim.
SYNTHETIC_CDS = "ATG" + "GCTACGGAT" * 40 + "TAA"


def _fragment_sequence(length: int, seed: str) -> str:
    """A deterministic synthetic fragment, written from a repeating motif."""
    motif = seed * (length // len(seed) + 1)
    return motif[:length]


def _aav_bundle(**overrides):
    from packages.generation.aav.designer import AAVDesigner

    request = AAVRequest(
        transgene_name="synthetic_reporter",
        transgene_sequence=SYNTHETIC_CDS,
        target_tissue="liver",
        promoter_preference="promoter.efs",
        **overrides,
    )
    return AAVDesigner().design(request)


# -- AAV ---------------------------------------------------------------------


def test_a_composed_aav_cassette_is_fully_attributed() -> None:
    bundle = _aav_bundle()
    subject = aav_subject(bundle.design, validator_version=bundle.report.validator_version)
    assert subject.capability is CapabilityKind.AAV
    assert [item.name for item in subject.sequences] == [CASSETTE_SEQUENCE_NAME]
    result = assert_provenance(subject)
    assert result.verdict is AssertionVerdict.ATTRIBUTED, result.reason
    assert result.bases_attributed == bundle.design.total_bp


def test_every_aav_element_becomes_one_span_in_cassette_order() -> None:
    bundle = _aav_bundle()
    subject = aav_subject(bundle.design, validator_version=bundle.report.validator_version)
    segments = subject.sequences[0].segments
    assert len(segments) == len(bundle.design.elements)
    assert [segment.start for segment in segments] == [
        item.start for item in bundle.design.layout()
    ]
    registry = [s for s in segments if s.origin is SequenceOrigin.REGISTRY_PART]
    user = [s for s in segments if s.origin is SequenceOrigin.USER_INPUT]
    assert len(user) == 1
    assert user[0].source == "user_input:transgene_sequence"
    assert {segment.part_id for segment in registry} <= set(bundle.design.provenance and [
        entry.split("part:", 1)[1] for entry in bundle.design.provenance if entry.startswith("part:")
    ])


def test_the_kozak_element_is_a_published_rule_span_that_names_its_rule() -> None:
    bundle = _aav_bundle()
    subject = aav_subject(bundle.design, validator_version=bundle.report.validator_version)
    segments = subject.sequences[0].segments
    rule_spans = [s for s in segments if s.origin is SequenceOrigin.PUBLISHED_RULE]
    assert len(rule_spans) == 1
    span = rule_spans[0]
    assert span.source == "published_rule:kozak_1987"
    assert span.end - span.start == 6
    assert span.rule and "doi:10.1093/nar/15.20.8125" in span.rule
    result = assert_provenance(subject)
    assert result.verdict is AssertionVerdict.ATTRIBUTED, result.reason
    assert result.bases_attributed == bundle.design.total_bp


def test_a_kozak_element_with_no_source_leaves_a_gap_and_blocks() -> None:
    bundle = _aav_bundle()
    design = bundle.design
    elements = [
        element.model_copy(update={"source": None}) if element.role is CassetteElementRole.KOZAK else element
        for element in design.elements
    ]
    subject = aav_subject(design.model_copy(update={"elements": elements}), validator_version="v")
    assert assert_provenance(subject).verdict is AssertionVerdict.UNATTRIBUTED


def test_a_kozak_element_with_other_bases_is_not_attributed_to_the_rule() -> None:
    bundle = _aav_bundle()
    design = bundle.design
    elements = [
        element.model_copy(update={"sequence": "TTTTTT"}) if element.role is CassetteElementRole.KOZAK else element
        for element in design.elements
    ]
    subject = aav_subject(design.model_copy(update={"elements": elements}), validator_version="v")
    assert not [s for s in subject.sequences[0].segments if s.origin is SequenceOrigin.PUBLISHED_RULE]
    result = assert_provenance(subject)
    assert result.verdict is AssertionVerdict.UNATTRIBUTED
    assert any("TTTTTT" in finding.message for finding in result.findings)


def test_an_aav_cassette_with_an_undeclared_source_blocks() -> None:
    """A transgene resolver that returns an unprefixed token is caught here."""
    bundle = _aav_bundle()
    design = bundle.design
    index = next(
        i for i, element in enumerate(design.elements)
        if element.role is CassetteElementRole.CDS
    )
    elements = list(design.elements)
    elements[index] = elements[index].model_copy(update={"source": "somewhere"})
    broken = design.model_copy(update={"elements": elements})
    subject = aav_subject(broken, validator_version=bundle.report.validator_version)
    result = assert_provenance(subject)
    assert result.verdict is AssertionVerdict.UNATTRIBUTED
    gap = next(f for f in result.findings if f.kind == "unattributed_span")
    assert gap.end - gap.start == len(SYNTHETIC_CDS)


def test_the_dispatcher_finds_the_aav_adapter() -> None:
    bundle = _aav_bundle()
    subject = subject_for_design(
        bundle.design, validator_version=bundle.report.validator_version
    )
    assert subject.adapter == "screening.adapters.aav"


# -- assembly ----------------------------------------------------------------


def _assembly_design(strategy: str, enzyme: str | None):
    from packages.generation.assembly.designer import compose

    request = AssemblyRequest(
        strategy=strategy,  # type: ignore[arg-type]
        fragments=[
            Fragment(
                name="insert",
                sequence=_fragment_sequence(600, "ACGGTATCCAGTTACGAAT"),
                source="synthetic test fragment",
            ),
            Fragment(
                name="linker",
                sequence=_fragment_sequence(400, "TTGACCATGCAAGTCCGTA"),
                source="synthetic test fragment",
                role="linker",
            ),
        ],
        vector_backbone=_fragment_sequence(900, "GATCCAAGTTGCACGATTC"),
        enzyme=enzyme,
    )
    return compose(request)


@pytest.mark.parametrize(
    ("strategy", "enzyme"),
    [
        ("gibson", None),
        ("golden_gate", "BsaI"),
        ("golden_gate", "BbsI"),
        ("golden_gate", "SapI"),
        ("pcr_cloning", "BsaI"),
        ("pcr_cloning", None),
    ],
)
def test_every_assembly_primer_is_fully_attributed(strategy: str, enzyme: str | None) -> None:
    from packages.application.screening.adapters.assembly import assembly_subject

    design = _assembly_design(strategy, enzyme)
    subject = assembly_subject(design, validator_version="assembly-1")
    assert len(subject.sequences) == len(design.primers) > 0
    result = assert_provenance(subject)
    assert result.verdict is AssertionVerdict.ATTRIBUTED, result.reason


def test_a_type_iis_tail_splits_into_the_site_the_spacer_and_the_overhang() -> None:
    from packages.application.screening.adapters.assembly import assembly_subject
    from packages.validation.assembly.enzymes import get_enzyme

    design = _assembly_design("golden_gate", "BsaI")
    enzyme = get_enzyme("BsaI")
    subject = assembly_subject(design, validator_version="assembly-1")
    primer = next(p for p in design.primers if p.tail)
    item = subject.sequence(f"primer:{primer.name}")
    rules = [s.rule for s in item.segments if s.origin is SequenceOrigin.PUBLISHED_RULE]
    assert any(enzyme.recognition in (rule or "") for rule in rules)
    site = next(
        s
        for s in item.segments
        if s.origin is SequenceOrigin.PUBLISHED_RULE and item.bases(s) == enzyme.recognition
    )
    assert site.rule is not None and enzyme.cut_notation in site.rule


def test_a_primer_whose_binding_region_does_not_match_its_template_blocks() -> None:
    from packages.application.screening.adapters.assembly import assembly_subject

    design = _assembly_design("gibson", None)
    primers = list(design.primers)
    broken = primers[0].model_copy(update={"binding": "A" * len(primers[0].binding)})
    primers[0] = broken
    subject = assembly_subject(
        design.model_copy(update={"primers": primers}), validator_version="assembly-1"
    )
    result = assert_provenance(subject)
    assert result.verdict is AssertionVerdict.UNATTRIBUTED
    assert any(
        finding.sequence_name == f"primer:{broken.name}" and finding.kind == "unattributed_span"
        for finding in result.findings
    )


def test_an_assembly_with_no_primers_blocks_as_unknown() -> None:
    from packages.application.screening.adapters.assembly import assembly_subject

    design = _assembly_design("gibson", None)
    subject = assembly_subject(design.model_copy(update={"primers": []}), validator_version="v1")
    result = assert_provenance(subject)
    assert result.verdict is AssertionVerdict.UNKNOWN
    assert result.permits_export is False


# -- guide RNA ---------------------------------------------------------------

def _guide_target(length: int = 420, seed: int = 20261008) -> str:
    """A deterministic pseudo-random target sequence.

    A repeating motif produces almost no valid guide, because the feature
    checks reject repeats, so the target is drawn from `random.Random` with a
    fixed seed. Python's Mersenne Twister is reproducible for a given seed on
    every platform and version, so this sequence is the same on every run,
    which section 3.3 constraint 3 requires of the tests as well as the code.
    """
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(length))


GUIDE_TARGET = _guide_target()


def _grna_result(nuclease: str, expression_system: str):
    from packages.generation.grna.designer import build_generator

    request = GuideRNARequest(
        target_sequence=GUIDE_TARGET,
        target_name="synthetic_target",
        nuclease=nuclease,  # type: ignore[arg-type]
        edit_intent="knockout",
        expression_system=expression_system,  # type: ignore[arg-type]
        off_target_space=OffTargetSpace(scope="construct_only"),
    )
    return build_generator().compose(request)


@pytest.mark.parametrize(
    ("nuclease", "expression_system"),
    [
        ("SpCas9", "u6_plasmid"),
        ("SaCas9", "u6_plasmid"),
        ("SpCas9", "t7_in_vitro"),
        ("LbCas12a", "u6_plasmid"),
    ],
)
def test_every_guide_spacer_and_oligo_is_fully_attributed(
    nuclease: str, expression_system: str
) -> None:
    from packages.application.screening.adapters.grna import grna_subject

    result = _grna_result(nuclease, expression_system)
    subject = grna_subject(
        result, validator_version="grna-1", target_sequence=GUIDE_TARGET
    )
    assert subject.sequences
    assertion = assert_provenance(subject)
    assert assertion.verdict is AssertionVerdict.ATTRIBUTED, assertion.reason
    spacers = [item for item in subject.sequences if item.name.startswith("spacer:")]
    assert len(spacers) == len(result.guides_returned)
    for item in spacers:
        assert [segment.origin for segment in item.segments] == [SequenceOrigin.USER_INPUT]


def test_a_guide_placed_off_its_own_target_blocks() -> None:
    from packages.application.screening.adapters.grna import grna_subject

    result = _grna_result("SpCas9", "u6_plasmid")
    guides = list(result.guides_returned)
    guide = guides[0]
    moved = guide.placement.model_copy(
        update={
            "spacer_start": guide.placement.spacer_start + 1,
            "spacer_end": guide.placement.spacer_end + 1,
        }
    )
    guides[0] = guide.model_copy(update={"placement": moved})
    subject = grna_subject(
        result.model_copy(update={"guides_returned": guides}),
        validator_version="grna-1",
        target_sequence=GUIDE_TARGET,
    )
    assertion = assert_provenance(subject)
    assert assertion.verdict is AssertionVerdict.UNATTRIBUTED
    assert any(f"spacer:{guide.guide_id}" == finding.sequence_name for finding in assertion.findings)


def test_a_grna_oligo_cites_the_published_vector_it_came_from() -> None:
    from packages.application.screening.adapters.grna import grna_subject

    result = _grna_result("SpCas9", "u6_plasmid")
    subject = grna_subject(
        result, validator_version="grna-1", target_sequence=GUIDE_TARGET
    )
    oligos = [item for item in subject.sequences if item.name.startswith("oligo:")]
    assert oligos
    rules = {
        segment.rule
        for item in oligos
        for segment in item.segments
        if segment.origin is SequenceOrigin.PUBLISHED_RULE
    }
    assert any("published cloning overhang" in (rule or "") for rule in rules)


def test_the_screened_guide_run_exports() -> None:
    from packages.application.screening.adapters.grna import grna_subject

    result = _grna_result("SpCas9", "u6_plasmid")
    subject = grna_subject(
        result, validator_version="grna-1", target_sequence=GUIDE_TARGET
    )
    assert screen_design(subject).allowed is True


# -- the dispatcher ----------------------------------------------------------


def test_an_unknown_design_type_fails_loudly() -> None:
    with pytest.raises(NoAttributionAdapter, match="no attribution adapter"):
        subject_for_design(object(), validator_version="v1")


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("part:promoter.cag", SequenceOrigin.REGISTRY_PART),
        ("user_input:transgene_sequence", SequenceOrigin.USER_INPUT),
        ("retrieved_template:genbank:NC_001401.2", SequenceOrigin.RETRIEVED_TEMPLATE),
        ("serotype_reference:NC_001401.2", None),
        ("part:", None),
        ("", None),
        ("somewhere", None),
    ],
)
def test_classify_source_only_accepts_tokens_that_declare_themselves(
    token: str, expected: SequenceOrigin | None
) -> None:
    assert classify_source(token) is expected
