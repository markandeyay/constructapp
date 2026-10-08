"""The plasmid gold cases are the curated records, converted and nothing else.

Three things are worth holding:

1. the committed cases are exactly what the conversion script produces, so a
   reviewer can regenerate and diff rather than trust the diff;
2. the counts are the whole curated set, so a case cannot quietly go missing;
3. every case runs through the multi-capability runner and agrees, which is what
   subjects the plasmid set to the three section 9.3 assertions.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.convert_plasmid_gold import DEFAULT_BAD_PATH, DEFAULT_GOOD_PATH, convert
from tests.gold import runner

GOLD_DIR = Path("tests/gold/plasmid")
FILES = ("tier_a.json", "tier_b.json", "known_bad.json")


def _load(name: str) -> list[dict]:
    return json.loads((GOLD_DIR / name).read_text(encoding="utf-8"))


def test_committed_cases_match_a_fresh_conversion(tmp_path: Path) -> None:
    convert(DEFAULT_GOOD_PATH, DEFAULT_BAD_PATH, tmp_path)
    for name in FILES:
        assert (tmp_path / name).read_text(encoding="utf-8") == (GOLD_DIR / name).read_text(
            encoding="utf-8"
        ), f"{name} is not what scripts/convert_plasmid_gold.py produces; regenerate it"


def test_counts_cover_the_whole_curated_set() -> None:
    tier_a, tier_b, known_bad = (_load(name) for name in FILES)
    assert len(tier_a) == 25
    assert len(tier_b) == 11
    assert len(known_bad) == 52
    assert len(tier_a) + len(tier_b) + len(known_bad) == 88


def test_every_known_bad_case_names_one_check_and_the_four_are_balanced() -> None:
    known_bad = _load("known_bad.json")
    by_check: dict[str, int] = {}
    for case in known_bad:
        assert case["expect_overall"] == "fail"
        assert case["expect_severity"] == "fail"
        assert case["rationale"]
        assert case["source_case_id"]
        by_check[case["expect_check"]] = by_check.get(case["expect_check"], 0) + 1
    assert by_check == {
        "codon_usage": 13,
        "regulatory_compatibility": 13,
        "repeat_and_instability": 13,
        "restriction_site_conflicts": 13,
    }


def test_tier_b_cases_document_every_warning_with_a_justification() -> None:
    for case in _load("tier_b.json"):
        assert case["expected_warnings"]
        for warning in case["expected_warnings"]:
            assert warning["check"]
            assert warning["justification"]


def test_tier_a_cases_declare_no_warning() -> None:
    for case in _load("tier_a.json"):
        assert "expected_warnings" not in case


def test_plasmid_gold_set_agrees_through_the_multi_capability_runner() -> None:
    result = runner.evaluate_capability("plasmid", Path("tests/gold"))
    assert result["disagreements"] == []
    assert result["total"] == 88
    assert result["correct"] == 88
    assert result["tier_a"]["total"] == 25
    assert result["tier_b"]["total"] == 11
    assert result["known_bad"]["total"] == 52
    assert result["malformed"] == 0
    assert result["unknown_check_reports"] == 0
