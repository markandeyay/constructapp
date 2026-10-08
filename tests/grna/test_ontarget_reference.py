"""The on-target model: pinned against the reference implementation, and gated by its domain.

The expected values below were produced on 2026-10-07 by running the reference
implementation of the model, `crisporEffScores.py` functions `calcDoenchScores`
and its coefficient table `doenchParams`, fetched from
https://raw.githubusercontent.com/maximilianh/crisporWebsite/master/crisporEffScores.py
That tool is published as Genome Biol 2016;17(1):148, doi:10.1186/s13059-016-1012-2,
PMID 27380939, and the model itself is Nat Biotechnol 2014;32(12):1262-1267,
doi:10.1038/nbt.3026, PMID 25184501.

`logit` is the model's linear predictor at full precision and `reference_int`
is the integer the reference implementation returns, which is the float score
truncated. Pinning both means a transcription error in the coefficient table,
in the GC term or in the term matching is a test failure.
"""

from __future__ import annotations

import math

import pytest

from packages.validation.grna import RULE_SET_1_NAME, heuristic_score, rule_set_1_logit
from packages.validation.grna.ontarget import (
    HEURISTIC_NAME,
    RULE_SET_1_CITATION,
    RULE_SET_1_DOMAIN,
    RULE_SET_1_TERMS,
    score_on_target,
)

from .conftest import make_request

#: (30 nt context, reference logit, reference integer score).
REFERENCE_VALUES = [
    ("AAGGCTGAGGGTGACGATCCCGCAAAAGCG", -0.9641164200000001, 27),
    ("GGGGCCACTAGGGACAGGATTGGTGACAGA", -2.38253107, 8),
    ("ACGTACGTACGTACGTACGTAGGACGTACG", 1.2251862000000002, 77),
    ("GCGCGCGCGCGCGCGCGCGCGGGGCGCGCG", -1.5688001100000004, 17),
    ("TTTTTTTTTTTTTTTTTTTTTGGTTTTTTT", -2.54807057, 7),
    ("CTACGATCGATCGGGTTACGGATCCAGGTT", -3.86766599, 2),
]


class TestRuleSet1MatchesTheReferenceImplementation:
    @pytest.mark.parametrize(("context", "expected_logit", "expected_int"), REFERENCE_VALUES)
    def test_logit_matches(self, context: str, expected_logit: float, expected_int: int) -> None:
        logit, _fired = rule_set_1_logit(context)
        assert logit == pytest.approx(expected_logit, abs=1e-9)

    @pytest.mark.parametrize(("context", "expected_logit", "expected_int"), REFERENCE_VALUES)
    def test_score_matches_the_reference_integer(
        self, context: str, expected_logit: float, expected_int: int
    ) -> None:
        logit, _fired = rule_set_1_logit(context)
        score = 100.0 / (1.0 + math.exp(-logit))
        assert int(score) == expected_int

    def test_the_coefficient_table_has_the_published_shape(self) -> None:
        """40 single-nucleotide terms and 30 dinucleotide terms, 70 in all."""
        singles = [term for term in RULE_SET_1_TERMS if len(term[1]) == 1]
        doubles = [term for term in RULE_SET_1_TERMS if len(term[1]) == 2]
        assert len(RULE_SET_1_TERMS) == 70
        assert len(singles) == 39
        assert len(doubles) == 31
        assert all(0 <= index <= 29 for index, _sub, _weight in RULE_SET_1_TERMS)

    def test_context_length_is_enforced_rather_than_padded(self) -> None:
        with pytest.raises(ValueError, match="30 nt context"):
            rule_set_1_logit("ACGT")


class TestValidityDomainGating:
    """Section 8.4: outside the trained context, caveat or withhold. Never extrapolate."""

    CONTEXT = "ACGTACGTACGTACGTACGTAGGACGTACG"
    SPACER = CONTEXT[4:24]

    def _score(self, **overrides: object):
        request = make_request(**overrides)
        return score_on_target(request, self.SPACER, self.CONTEXT, False)

    def test_in_domain_request_gets_a_score(self) -> None:
        published, heuristic = self._score()
        assert published.model_name == RULE_SET_1_NAME
        assert published.model_kind == "published_model"
        assert published.status == "in_domain"
        assert published.score is not None
        assert published.citation == RULE_SET_1_CITATION
        assert published.validity_domain == RULE_SET_1_DOMAIN
        assert "predicted" in published.disclaimer.lower()
        assert "not a measurement" in published.disclaimer.lower()
        assert heuristic.model_kind == "labeled_heuristic"

    @pytest.mark.parametrize("nuclease", ["SaCas9", "LbCas12a", "AsCas12a"])
    def test_other_nucleases_get_no_published_score(self, nuclease: str) -> None:
        published, heuristic = self._score(nuclease=nuclease)
        assert published.status == "out_of_domain"
        assert published.score is None
        assert any(nuclease in caveat for caveat in published.caveats)
        assert heuristic.score is not None, "the labeled heuristic still ranks these guides"

    def test_in_vitro_transcription_gets_no_published_score(self) -> None:
        published, _ = self._score(expression_system="t7_in_vitro")
        assert published.status == "out_of_domain"
        assert published.score is None
        assert any("in-vitro-transcribed" in caveat for caveat in published.caveats)
        assert any("CRISPRscan" in caveat for caveat in published.caveats)

    @pytest.mark.parametrize("host", ["non_mammalian", "cell_free"])
    def test_non_mammalian_host_gets_no_published_score(self, host: str) -> None:
        published, _ = self._score(host_context=host)
        assert published.status == "out_of_domain"
        assert published.score is None

    def test_missing_context_window_gets_no_published_score(self) -> None:
        request = make_request()
        published, heuristic = score_on_target(request, self.SPACER, None, False)
        assert published.status == "out_of_domain"
        assert published.score is None
        assert any("30 nt context" in caveat for caveat in published.caveats)
        assert heuristic.score is not None

    @pytest.mark.parametrize("intent", ["activation", "interference"])
    def test_transcriptional_intents_are_caveated_not_withheld(self, intent: str) -> None:
        published, _ = self._score(edit_intent=intent)
        assert published.status == "in_domain_with_caveat"
        assert published.score is not None
        assert any("knockout activity" in caveat for caveat in published.caveats)

    def test_alternative_pam_is_caveated(self) -> None:
        request = make_request()
        published, _ = score_on_target(request, self.SPACER, self.CONTEXT, True)
        assert published.status == "in_domain_with_caveat"
        assert any("NAG" in caveat for caveat in published.caveats)

    def test_out_of_domain_result_cannot_carry_a_score(self) -> None:
        """The schema itself refuses the combination, so it cannot leak into a payload."""
        from packages.core.schemas.grna import OnTargetScore

        with pytest.raises(ValueError, match="out_of_domain"):
            OnTargetScore(
                model_name="x",
                model_kind="published_model",
                citation="x",
                validity_domain="x",
                status="out_of_domain",
                score=50.0,
                caveats=["x"],
                disclaimer="x",
            )


class TestTheHeuristicIsLabelled:
    """Section 8.4 and section 16: a heuristic is never presented as a published score."""

    def test_name_and_kind_say_heuristic(self) -> None:
        score = heuristic_score("ACGTACGTACGTACGTACGT", nuclease="SpCas9")
        assert score.model_kind == "labeled_heuristic"
        assert "heuristic" in score.model_name.lower()
        assert "not a published score" in score.model_name.lower()
        assert "not a published score" in score.disclaimer.lower()
        assert score.citation.startswith("No publication.")

    def test_every_weight_is_reported_so_the_number_can_be_rebuilt(self) -> None:
        score = heuristic_score("ACGTACGTACGTACGTACGT", nuclease="SpCas9")
        from packages.validation.grna import DEFAULT_THRESHOLDS

        total = DEFAULT_THRESHOLDS.heuristic.base + sum(item.weight for item in score.reasoning)
        assert score.score == pytest.approx(max(0.0, min(100.0, total)), abs=0.01)

    def test_sequence_features_move_the_score_in_the_stated_direction(self) -> None:
        good = heuristic_score("ACGTACGTACGTACGTACGT", nuclease="SpCas9")  # GC 0.50
        terminator = heuristic_score("ACGTTTTTACGTACGTACGT", nuclease="SpCas9")
        assert terminator.score is not None and good.score is not None
        assert terminator.score < good.score

    def test_alternative_pam_lowers_the_heuristic(self) -> None:
        plain = heuristic_score("ACGTACGTACGTACGTACGT", nuclease="SpCas9")
        alternative = heuristic_score(
            "ACGTACGTACGTACGTACGT", nuclease="SpCas9", pam_is_alternative=True
        )
        assert alternative.score < plain.score

    def test_the_heuristic_name_differs_from_the_published_model_name(self) -> None:
        assert HEURISTIC_NAME != RULE_SET_1_NAME
        assert "Rule Set 1" not in HEURISTIC_NAME


class TestDeterminism:
    def test_same_input_same_output(self) -> None:
        request = make_request()
        context = "ACGTACGTACGTACGTACGTAGGACGTACG"
        first = score_on_target(request, context[4:24], context, False)
        second = score_on_target(request, context[4:24], context, False)
        assert first[0].model_dump() == second[0].model_dump()
        assert first[1].model_dump() == second[1].model_dump()
