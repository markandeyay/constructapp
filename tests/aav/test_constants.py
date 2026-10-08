"""The section 6.5 constants, their sources, and the section 5.4 rule 4 pin.

Section 3.3 constraint 1 makes an undocumented constant a build failure rather
than a style issue, so "every constant has a docstring naming its source" is a
test here, not a review note.
"""

from __future__ import annotations

import pytest

from packages.core.schemas.capability import thresholds_fingerprint
from packages.validation.aav import constants as module
from packages.validation.aav.constants import (
    AAV_MIN_GENOME_BP,
    AAV_SC_HARD_LIMIT_BP,
    AAV_SC_SOFT_LIMIT_BP,
    AAV_SC_TARGET_BP,
    AAV_SS_HARD_LIMIT_BP,
    AAV_SS_SOFT_LIMIT_BP,
    AAV_SS_TARGET_BP,
    AAV_VALIDATOR_VERSION,
    CHECK_CITATIONS,
    ITR_IDENTITY_THRESHOLD,
    KOZAK_CONSENSUS_MOTIF,
    KOZAK_ELEMENT_RULE,
    KOZAK_ELEMENT_SOURCE,
    KOZAK_MINUS3_PURINES,
    KOZAK_PREFERRED_MINUS3,
    KOZAK_UPSTREAM_ELEMENT,
    MAX_DIRECT_REPEAT_BP,
    MAX_HOMOPOLYMER_RUN,
    PINNED_THRESHOLD_FINGERPRINTS,
    AAVThresholds,
)
from packages.validation.aav.checks import CHECK_IDS

# Every constant this capability measures against, and the section of the
# system design or the literature its docstring must name.
DOCUMENTED_CONSTANTS = (
    "AAV_SS_TARGET_BP",
    "AAV_SS_SOFT_LIMIT_BP",
    "AAV_SS_HARD_LIMIT_BP",
    "AAV_SC_TARGET_BP",
    "AAV_SC_SOFT_LIMIT_BP",
    "AAV_SC_HARD_LIMIT_BP",
    "AAV_MIN_GENOME_BP",
    "ITR_IDENTITY_THRESHOLD",
    "MAX_DIRECT_REPEAT_BP",
    "MAX_HOMOPOLYMER_RUN",
    "ITR_D_ELEMENT_BP",
    "ITR_ORIENTATION_MARGIN",
    "ITR_INTERNAL_MOTIF_BP",
    "KOZAK_CONSENSUS_MOTIF",
    "KOZAK_MINUS3_PURINES",
    "KOZAK_PLUS4_BASE",
    "POLYA_SIGNAL_MOTIFS",
    "TISSUE_COMPATIBILITY",
    "REMEDIATION_MAX_PLANS",
    "REMEDIATION_MAX_CHANGES",
)


class TestSectionSixFiveValues:
    """The values section 6.5 fixes, reproduced exactly."""

    def test_single_stranded_band(self):
        assert (AAV_SS_TARGET_BP, AAV_SS_SOFT_LIMIT_BP, AAV_SS_HARD_LIMIT_BP) == (4_700, 4_900, 5_200)

    def test_self_complementary_band(self):
        assert (AAV_SC_TARGET_BP, AAV_SC_SOFT_LIMIT_BP, AAV_SC_HARD_LIMIT_BP) == (2_400, 2_500, 2_600)

    def test_minimum_genome(self):
        assert AAV_MIN_GENOME_BP == 2_000

    def test_structural_thresholds(self):
        assert ITR_IDENTITY_THRESHOLD == 0.95
        assert MAX_DIRECT_REPEAT_BP == 20
        assert MAX_HOMOPOLYMER_RUN == 8

    def test_the_self_complementary_band_is_about_half_the_single_stranded_one(self):
        """Section 6.2: a self complementary genome is effectively duplicated."""
        assert AAV_SC_TARGET_BP == pytest.approx(AAV_SS_TARGET_BP / 2, abs=100)


# The constants that encode a biological claim. Section 3.3 constraint 1
# requires each of these to name an appendix or section of the system design,
# or primary literature. The rest are method or presentation parameters, and
# each must say so in its own docstring rather than be left ambiguous.
BIOLOGICAL_CONSTANTS = frozenset(
    {
        "AAV_SS_TARGET_BP",
        "AAV_SS_SOFT_LIMIT_BP",
        "AAV_SS_HARD_LIMIT_BP",
        "AAV_SC_TARGET_BP",
        "AAV_SC_SOFT_LIMIT_BP",
        "AAV_SC_HARD_LIMIT_BP",
        "AAV_MIN_GENOME_BP",
        "ITR_IDENTITY_THRESHOLD",
        "MAX_DIRECT_REPEAT_BP",
        "MAX_HOMOPOLYMER_RUN",
        "ITR_D_ELEMENT_BP",
        "KOZAK_CONSENSUS_MOTIF",
        "KOZAK_MINUS3_PURINES",
        "KOZAK_PLUS4_BASE",
        "POLYA_SIGNAL_MOTIFS",
        "TISSUE_COMPATIBILITY",
    }
)

# Phrases that declare a constant to be a method or presentation parameter
# rather than a biological one.
NON_BIOLOGICAL_MARKERS = (
    "method parameter, not a biological constant",
    "presentation limit, not a biological one",
    "search bound, not a biological one",
    "window length for",
)

# Phrases that count as naming a source.
SOURCE_MARKERS = (
    "section 6.5",
    "section 6.2",
    "section 6.3",
    "section 6.4",
    "section 6.6",
    "Section 6.6",
    "source:",
    "doi:",
    "nature 1976",
    "genome research 2000",
    "nucleic acids research 1987",
    "journal of virology 1983",
    "appendix b",
    "cited on `kozak_consensus_motif`",
    "same table",
    "set equal to `max_direct_repeat_bp`",
)


class TestEveryConstantNamesItsSource:
    @pytest.mark.parametrize("name", DOCUMENTED_CONSTANTS)
    def test_constant_exists(self, name):
        assert hasattr(module, name)

    @pytest.mark.parametrize("name", DOCUMENTED_CONSTANTS)
    def test_constant_has_a_docstring(self, name):
        """Python attaches no docstring to a plain assignment, so this reads the source.

        A string literal must immediately follow the assignment, which is the
        convention the constants module uses throughout.
        """
        assert module.__doc__, "the constants module itself must be documented"
        assert _constant_docstring(name), f"{name} has no docstring"

    @pytest.mark.parametrize("name", sorted(BIOLOGICAL_CONSTANTS))
    def test_biological_constant_names_a_section_or_a_paper(self, name):
        text = _constant_docstring(name).lower()
        assert any(marker.lower() in text for marker in SOURCE_MARKERS), (
            f"{name} encodes a biological claim but its docstring names no source: {text[:160]}"
        )

    @pytest.mark.parametrize("name", sorted(set(DOCUMENTED_CONSTANTS) - BIOLOGICAL_CONSTANTS))
    def test_non_biological_constant_declares_itself_as_such(self, name):
        text = _constant_docstring(name)
        assert any(marker in text for marker in NON_BIOLOGICAL_MARKERS), (
            f"{name} is not in BIOLOGICAL_CONSTANTS, so its docstring must say it is a method or "
            f"presentation parameter: {text[:160]}"
        )

    @pytest.mark.parametrize("name", DOCUMENTED_CONSTANTS)
    def test_constant_docstring_says_it_is_configurable(self, name):
        assert "onfigurable" in _constant_docstring(name), name

    @pytest.mark.parametrize("name", DOCUMENTED_CONSTANTS)
    def test_constant_is_overridable_on_the_threshold_object(self, name):
        field = name.lower().removeprefix("aav_")
        assert field in AAVThresholds.__dataclass_fields__, f"{name} is not overridable as {field}"


# The constants that describe the element the composer writes. They are a
# generation choice, not a validation bound, so they are deliberately not
# threshold fields: the enumeration above (which requires an overridable
# threshold field) does not apply to them, and this one asserts the opposite.
COMPOSED_ELEMENT_CONSTANTS = (
    "KOZAK_PREFERRED_MINUS3",
    "KOZAK_UPSTREAM_ELEMENT",
    "KOZAK_ELEMENT_SOURCE",
    "KOZAK_ELEMENT_RULE",
)


class TestComposedElementConstants:
    @pytest.mark.parametrize("name", COMPOSED_ELEMENT_CONSTANTS)
    def test_constant_exists_and_has_a_docstring(self, name):
        assert hasattr(module, name)
        assert _constant_docstring(name), f"{name} has no docstring"

    @pytest.mark.parametrize("name", COMPOSED_ELEMENT_CONSTANTS)
    def test_docstring_names_its_source(self, name):
        text = _constant_docstring(name).lower()
        assert any(marker.lower() in text for marker in SOURCE_MARKERS), (
            f"{name} docstring names no source: {text[:160]}"
        )

    @pytest.mark.parametrize("name", COMPOSED_ELEMENT_CONSTANTS)
    def test_constant_is_not_a_threshold_field(self, name):
        assert name.lower() not in AAVThresholds.__dataclass_fields__
        assert name.lower() not in AAVThresholds().as_mapping()

    def test_the_element_is_the_cited_motif_prefix_with_a_as_the_purine(self):
        assert KOZAK_UPSTREAM_ELEMENT == "GCCACC"
        assert len(KOZAK_UPSTREAM_ELEMENT) == 6

    def test_the_element_is_derived_from_the_cited_motif(self):
        assert len(KOZAK_UPSTREAM_ELEMENT) == len(KOZAK_CONSENSUS_MOTIF[:6])
        assert matches(KOZAK_UPSTREAM_ELEMENT, KOZAK_CONSENSUS_MOTIF[:6])

    def test_the_preferred_purine_is_one_the_check_accepts(self):
        assert KOZAK_PREFERRED_MINUS3 in KOZAK_MINUS3_PURINES
        assert KOZAK_UPSTREAM_ELEMENT[-3] in KOZAK_MINUS3_PURINES

    def test_the_source_token_and_rule_text(self):
        assert KOZAK_ELEMENT_SOURCE == "published_rule:kozak_1987"
        assert KOZAK_CONSENSUS_MOTIF in KOZAK_ELEMENT_RULE
        assert "doi:10.1093/nar/15.20.8125" in KOZAK_ELEMENT_RULE


def matches(element: str, motif: str) -> bool:
    from packages.core.sequence import matches_iupac

    return matches_iupac(element, motif)


def _constant_docstring(name: str) -> str:
    """The string literal that follows `name = ...` in the constants module."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(module))
    body = tree.body
    for index, node in enumerate(body):
        targets = getattr(node, "targets", None) or ([node.target] if hasattr(node, "target") else [])
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            following = body[index + 1] if index + 1 < len(body) else None
            if (
                isinstance(following, ast.Expr)
                and isinstance(following.value, ast.Constant)
                and isinstance(following.value.value, str)
            ):
                return following.value.value
            return ""
    return ""


class TestThresholdObject:
    def test_defaults_match_the_module_constants(self):
        thresholds = AAVThresholds()
        assert thresholds.ss_target_bp == AAV_SS_TARGET_BP
        assert thresholds.max_homopolymer_run == MAX_HOMOPOLYMER_RUN

    def test_band_selection(self):
        thresholds = AAVThresholds()
        assert thresholds.band(False) == (4_700, 4_900, 5_200)
        assert thresholds.band(True) == (2_400, 2_500, 2_600)

    def test_override_moves_the_band_and_keeps_the_widths(self):
        moved = AAVThresholds().with_packaging_limit(5_000, False)
        assert moved.band(False) == (5_000, 5_200, 5_500)
        assert moved.band(True) == (2_400, 2_500, 2_600)

    def test_override_applies_to_the_self_complementary_band_when_requested(self):
        moved = AAVThresholds().with_packaging_limit(3_000, True)
        assert moved.band(True) == (3_000, 3_100, 3_200)
        assert moved.band(False) == (4_700, 4_900, 5_200)

    def test_no_override_returns_the_same_object(self):
        thresholds = AAVThresholds()
        assert thresholds.with_packaging_limit(None, False) is thresholds

    def test_an_inverted_band_is_rejected(self):
        with pytest.raises(ValueError, match="target <= soft limit <= hard limit"):
            AAVThresholds(ss_target_bp=5_000, ss_soft_limit_bp=4_000)

    def test_an_impossible_identity_threshold_is_rejected(self):
        with pytest.raises(ValueError, match="itr_identity_threshold"):
            AAVThresholds(itr_identity_threshold=1.5)

    def test_as_mapping_covers_every_field(self):
        mapping = AAVThresholds().as_mapping()
        for field in AAVThresholds.__dataclass_fields__:
            assert field in mapping, field

    def test_as_mapping_is_json_serialisable(self):
        import json

        json.dumps(AAVThresholds().as_mapping())


class TestVersionPin:
    """Section 5.4 rule 4: a threshold edited without a version bump must fail a test."""

    def test_the_shipped_thresholds_match_the_pinned_fingerprint(self):
        from packages.core.schemas.capability import assert_version_matches_thresholds

        assert_version_matches_thresholds(
            AAV_VALIDATOR_VERSION, AAVThresholds().as_mapping(), PINNED_THRESHOLD_FINGERPRINTS
        )

    def test_the_itr_orientation_severity_change_bumped_the_version(self):
        """Rule 4 covers a severity change too: a stored PASS must stay readable.

        aav-1.0.0 reported PASS on a D outward ITR pair and aav-1.1.0 reports
        WARN. No threshold value moved, so the two versions share a fingerprint,
        and that is the record of what did change.
        """
        assert AAV_VALIDATOR_VERSION != "aav-1.0.0"
        assert AAV_VALIDATOR_VERSION in PINNED_THRESHOLD_FINGERPRINTS
        assert "aav-1.0.0" in PINNED_THRESHOLD_FINGERPRINTS
        assert (
            PINNED_THRESHOLD_FINGERPRINTS[AAV_VALIDATOR_VERSION]
            == PINNED_THRESHOLD_FINGERPRINTS["aav-1.0.0"]
        )

    def test_changing_a_threshold_changes_the_fingerprint(self):
        baseline = thresholds_fingerprint(AAVThresholds().as_mapping())
        changed = thresholds_fingerprint(AAVThresholds(ss_target_bp=4_701).as_mapping())
        assert baseline != changed

    def test_the_version_is_stamped_on_the_report(self):
        from packages.validation.aav import AAVValidator

        from tests.aav.support import build_design

        assert AAVValidator().validate(build_design()).validator_version == AAV_VALIDATOR_VERSION


class TestCitations:
    def test_every_check_has_a_citation(self):
        assert set(CHECK_CITATIONS) == set(CHECK_IDS)

    def test_citations_name_a_section_or_a_paper(self):
        for check_id, citation in CHECK_CITATIONS.items():
            assert "section" in citation.lower(), check_id
            assert len(citation) > 40, check_id

    def test_the_literature_backed_checks_name_their_paper(self):
        assert "Kozak" in CHECK_CITATIONS["aav.kozak_context"]
        assert "doi:10.1093/nar/15.20.8125" in CHECK_CITATIONS["aav.kozak_context"]
        assert "Proudfoot" in CHECK_CITATIONS["aav.polya_present_functional"]
        assert "Beaudoing" in CHECK_CITATIONS["aav.polya_present_functional"]
        assert "doi:10.1128/JVI.45.2.555-564.1983" in CHECK_CITATIONS["aav.itr_orientation"]


class TestMotifsAreVerifiedAgainstTheRegistry:
    """The constants that claim an in-repository fact must actually hold."""

    def test_the_polya_hexamer_positions_claimed_in_the_docstring(self):
        from packages.core.part_registry import get_part
        from packages.core.sequence import find_exact

        assert find_exact(get_part("polya.bgh").sequence, "AATAAA") == [90]
        assert find_exact(get_part("polya.sv40").sequence, "AATAAA") == [31, 60]

    def test_the_d_element_relation_claimed_in_the_docstring(self):
        from packages.core.part_registry import get_part
        from packages.core.sequence import reverse_complement

        left = get_part("itr.aav2_itr_left").sequence
        right = get_part("itr.aav2_itr_right").sequence
        width = AAVThresholds().itr_d_element_bp
        assert reverse_complement(left[-width:]) == right[:width]
        assert left[-width:] == "CTCCATCACTAGGGGTTCCT"
        assert right[:width] == "AGGAACCCCTAGTGATGGAG"
        # The docstring claims the relation holds out to at least 25 nt.
        assert reverse_complement(left[-25:]) == right[:25]

    def test_the_cmv_enhancer_repeat_claimed_in_the_docstring(self):
        from packages.core.part_registry import get_part
        from packages.core.sequence import find_exact

        motif = "ACGGTAAATGGCCCGCCTGGC"
        for part_id in ("promoter.cmv", "promoter.cag", "promoter.cbh"):
            assert len(find_exact(get_part(part_id).sequence, motif)) == 2, part_id

    def test_the_homopolymer_runs_claimed_in_the_docstring(self):
        from packages.core.part_registry import get_part
        from packages.core.sequence import homopolymer_runs

        cag = homopolymer_runs(get_part("promoter.cag").sequence, min_length=9)
        cbh = homopolymer_runs(get_part("promoter.cbh").sequence, min_length=9)
        assert [(run.base, run.length) for run in cag] == [("G", 14)]
        assert [(run.base, run.length) for run in cbh] == [("G", 16)]

    def test_the_hairpin_core_relation_claimed_in_the_itr_module(self):
        from packages.core.part_registry import get_part
        from packages.core.sequence import global_identity, reverse_complement

        left = get_part("itr.aav2_itr_left").sequence
        right = get_part("itr.aav2_itr_right").sequence
        core, d_element = left[:125], left[125:]
        assert right == reverse_complement(d_element) + core
        assert global_identity(core, reverse_complement(core)) == pytest.approx(0.859, abs=1e-3)
        assert sum(1 for a, b in zip(left, reverse_complement(right)) if a != b) == 17
