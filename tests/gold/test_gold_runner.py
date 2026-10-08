"""Unit tests for the gold-set runner. These prove it catches wrong-reason passes."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.gold import runner


def chk(check_id: str, severity: str, **extra):
    return SimpleNamespace(check_id=check_id, severity=severity, **extra)


def rep(*checks, overall=None, **extra):
    sevs = [c.severity for c in checks]
    return SimpleNamespace(overall=overall or runner.recompute_overall(sevs), checks=list(checks), **extra)


def bad_case(**over):
    case = {
        "case_id": "aav.bad.x",
        "capability": "aav",
        "expect_overall": "fail",
        "expect_check": "aav.packaging_limit",
        "expect_severity": "fail",
        "input": {},
    }
    case.update(over)
    return case


def good_case(tier="A", **over):
    case = {"case_id": "aav.good.x", "capability": "aav", "tier": tier, "input": {}}
    if tier == "B":
        case["expected_warnings"] = [{"check": "aav.kozak_context", "justification": "intentional weak Kozak"}]
    case.update(over)
    return case


# ---- known-bad: the three assertions --------------------------------------


def test_bad_case_correct_reason_agrees():
    out = runner.judge_case(bad_case(), rep(chk("aav.packaging_limit", "fail"), chk("aav.itr_present_both", "pass")))
    assert out.correct, out.problems


def test_bad_case_failing_for_the_wrong_check_is_a_disagreement():
    # Overall is FAIL as expected, but the named check passed and a different one failed.
    report = rep(chk("aav.packaging_limit", "pass"), chk("aav.cds_integrity", "fail"))
    out = runner.judge_case(bad_case(), report)
    assert not out.correct
    text = " | ".join(out.problems)
    assert "named check aav.packaging_limit: expected 'fail', got 'pass'" in text
    assert "unexpected FAIL" in text and "aav.cds_integrity" in text


def test_bad_case_overall_matches_but_named_check_missing():
    out = runner.judge_case(bad_case(), rep(chk("aav.cds_integrity", "fail")))
    assert not out.correct
    assert any("was not reported at all" in p for p in out.problems)


def test_accidentally_right_extra_fail_is_caught_even_when_named_check_fails():
    report = rep(chk("aav.packaging_limit", "fail"), chk("aav.element_order", "fail"))
    out = runner.judge_case(bad_case(), report)
    assert not out.correct
    assert any("aav.element_order" in p for p in out.problems)


def test_allowed_extra_fail_is_honoured_when_declared():
    report = rep(chk("aav.packaging_limit", "fail"), chk("aav.element_order", "fail"))
    out = runner.judge_case(bad_case(allowed_extra_fail=["aav.element_order"]), report)
    assert out.correct, out.problems


def test_wrong_overall_is_a_disagreement():
    out = runner.judge_case(bad_case(expect_overall="warn"), rep(chk("aav.packaging_limit", "fail")))
    assert not out.correct
    assert any("overall severity" in p for p in out.problems)


def test_warn_expected_case_agrees_and_fail_there_is_caught():
    case = bad_case(expect_overall="warn", expect_check="aav.packaging_limit", expect_severity="warn")
    assert runner.judge_case(case, rep(chk("aav.packaging_limit", "warn"))).correct
    assert not runner.judge_case(case, rep(chk("aav.packaging_limit", "fail"))).correct


def test_unknown_on_named_check_is_never_a_match():
    case = bad_case(expect_overall="pass", expect_severity="unknown")
    out = runner.judge_case(case, rep(chk("aav.packaging_limit", "unknown"), chk("aav.itr_present_both", "pass")))
    assert not out.correct
    assert any("UNKNOWN never counts" in p for p in out.problems)


def test_inconsistent_declared_overall_is_flagged():
    report = SimpleNamespace(overall="pass", checks=[chk("aav.packaging_limit", "fail")])
    out = runner.judge_case(bad_case(expect_overall="pass"), report)
    assert not out.correct
    assert any("worst non-UNKNOWN" in p for p in out.problems)


def test_unknown_does_not_lower_recomputed_overall():
    assert runner.recompute_overall(["unknown", "warn"]) == "warn"
    assert runner.recompute_overall(["unknown"]) == "unknown"
    assert runner.recompute_overall([]) == "unknown"


def test_must_also_report():
    case = bad_case(must_also_report=["remediation_suggestion"])
    without = rep(chk("aav.packaging_limit", "fail"))
    with_it = rep(chk("aav.packaging_limit", "fail", remediation_suggestion="swap CAG for EFS"))
    assert not runner.judge_case(case, without).correct
    assert runner.judge_case(case, with_it).correct
    as_check = bad_case(must_also_report=["aav.minimum_genome_size"])
    assert runner.judge_case(as_check, rep(chk("aav.packaging_limit", "fail"), chk("aav.minimum_genome_size", "pass"))).correct
    assert not runner.judge_case(as_check, rep(chk("aav.packaging_limit", "fail"), chk("aav.minimum_genome_size", "unknown"))).correct
    sev_form = bad_case(must_also_report=[{"check": "aav.x", "severity": "warn"}])
    assert runner.judge_case(sev_form, rep(chk("aav.packaging_limit", "fail"), chk("aav.x", "warn"))).correct


# ---- known-good tiering ---------------------------------------------------


def test_tier_a_clean_agrees():
    assert runner.judge_case(good_case("A"), rep(chk("a", "pass"))).correct


def test_tier_a_with_a_warning_is_a_disagreement():
    out = runner.judge_case(good_case("A"), rep(chk("a", "pass"), chk("aav.kozak_context", "warn")))
    assert not out.correct
    assert any("Tier A must validate with no warnings" in p for p in out.problems)


def test_tier_a_with_unknown_is_a_disagreement():
    out = runner.judge_case(good_case("A"), rep(chk("a", "pass"), chk("b", "unknown")))
    assert not out.correct


def test_tier_a_with_expected_unknown_is_allowed():
    assert runner.judge_case(good_case("A", expected_unknown=["b"]), rep(chk("a", "pass"), chk("b", "unknown"))).correct


def test_tier_b_documented_warning_present_is_the_expected_outcome():
    assert runner.judge_case(good_case("B"), rep(chk("aav.kozak_context", "warn"), chk("a", "pass"))).correct


def test_tier_b_missing_or_undocumented_warning_is_a_disagreement():
    missing = runner.judge_case(good_case("B"), rep(chk("a", "pass")))
    assert not missing.correct and any("documented warning(s) not reported" in p for p in missing.problems)
    extra = runner.judge_case(good_case("B"), rep(chk("aav.kozak_context", "warn"), chk("other", "warn")))
    assert not extra.correct and any("undocumented warning" in p for p in extra.problems)


def test_known_good_with_fail_is_a_disagreement():
    assert not runner.judge_case(good_case("B"), rep(chk("aav.kozak_context", "warn"), chk("x", "fail"))).correct


def test_malformed_cases_are_disagreements_not_passes():
    assert not runner.judge_case({"case_id": "m", "input": {}}, rep(chk("a", "pass"))).correct
    both = good_case("A", expect_check="x")
    assert not runner.judge_case(both, rep(chk("a", "pass"))).correct
    b_without_docs = good_case("B", expected_warnings=[])
    assert not runner.judge_case(b_without_docs, rep(chk("aav.kozak_context", "warn"))).correct
    assert not runner.judge_case(good_case("C"), rep(chk("a", "pass"))).correct


def test_dict_reports_and_enum_like_severity_are_accepted():
    enum_like = SimpleNamespace(value="FAIL")
    report = {"overall": enum_like, "checks": [{"check_id": "aav.packaging_limit", "severity": enum_like}]}
    assert runner.judge_case(bad_case(), report).correct


# ---- discovery, zero cases, resolver failures, exit codes -----------------


def write(root: Path, rel: str, payload) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def resolver_returning(report_for):
    def resolver(capability):
        return lambda case_input: report_for(case_input)

    return resolver


def test_zero_cases_reports_zero_and_exits_zero(tmp_path):
    result = runner.evaluate_all(tmp_path, resolver=lambda c: pytest.fail("resolver must not be called"))
    assert [c["capability"] for c in result["capabilities"]] == ["aav", "assembly", "grna", "plasmid"]
    assert all(c["total"] == 0 and c["accuracy"] is None for c in result["capabilities"])
    assert runner.exit_code(result) == 0
    assert "0 cases found" in runner.render_text(result)
    assert runner.exit_code(result, require_cases=True) == 1


def test_main_exits_zero_with_no_cases(tmp_path):
    assert runner.main(["--gold-root", str(tmp_path), "--no-write"]) == 0


def test_end_to_end_disagreement_listed_and_exit_nonzero(tmp_path):
    write(tmp_path, "aav/b.json", bad_case(case_id="aav.bad.b", input={"n": 1}))
    write(tmp_path, "aav/a.json", [good_case("A", case_id="aav.good.a", input={"n": 2})])
    reports = {
        1: rep(chk("aav.packaging_limit", "pass"), chk("aav.cds_integrity", "fail")),  # wrong reason
        2: rep(chk("aav.packaging_limit", "pass")),
    }
    result = runner.evaluate_all(tmp_path, resolver_returning(lambda i: reports[i["n"]]))
    aav = result["capabilities"][0]
    assert aav["total"] == 2 and aav["correct"] == 1 and aav["known_bad"]["correct"] == 0
    assert [d["case_id"] for d in aav["disagreements"]] == ["aav.bad.b"]
    assert runner.exit_code(result) == 1
    text = runner.render_text(result)
    assert "aav.bad.b" in text and "aav.packaging_limit" in text and "aav.cds_integrity" in text


def test_discovery_order_is_sorted_and_reproducible(tmp_path):
    for name in ("z", "a", "m"):
        write(tmp_path, f"aav/{name}.json", good_case("A", case_id=f"aav.good.{name}"))
    first = runner.evaluate_all(tmp_path, resolver_returning(lambda i: rep(chk("a", "pass"))))
    second = runner.evaluate_all(tmp_path, resolver_returning(lambda i: rep(chk("a", "pass"))))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert [p.name for p in runner.discover(tmp_path, "aav")] == ["a.json", "m.json", "z.json"]


def test_unavailable_validator_is_unevaluable_not_a_pass(tmp_path):
    write(tmp_path, "grna/c.json", bad_case(case_id="grna.bad.c", capability="grna"))

    def resolver(capability):
        raise runner.ValidatorUnavailable("no validator registered")

    result = runner.evaluate_all(tmp_path, resolver)
    grna = next(c for c in result["capabilities"] if c["capability"] == "grna")
    assert grna["correct"] == 0 and len(grna["disagreements"]) == 1
    assert "validator unavailable" in grna["disagreements"][0]["problems"][0]
    assert runner.exit_code(result) == 1


def test_validator_exception_is_a_disagreement(tmp_path):
    write(tmp_path, "aav/x.json", bad_case())

    def boom(case_input):
        raise RuntimeError("kaput")

    result = runner.evaluate_all(tmp_path, resolver_returning(boom))
    assert result["disagreement_count"] == 1 and runner.exit_code(result) == 1


def test_duplicate_ids_wrong_capability_and_bad_json_are_errors(tmp_path):
    write(tmp_path, "aav/a.json", bad_case())
    write(tmp_path, "aav/b.json", bad_case())
    write(tmp_path, "aav/c.json", bad_case(case_id="aav.bad.c", capability="assembly"))
    (tmp_path / "aav" / "d.json").write_text("{not json", encoding="utf-8")
    ok = rep(chk("aav.packaging_limit", "fail"))
    result = runner.evaluate_all(tmp_path, resolver_returning(lambda i: ok))
    problems = " | ".join(p for d in result["capabilities"][0]["disagreements"] for p in d["problems"])
    assert "duplicate case_id" in problems
    assert "does not match directory" in problems
    assert "cannot load case file" in problems


def test_grna_directory_accepts_guide_rna_kind(tmp_path):
    write(tmp_path, "grna/g.json", bad_case(case_id="grna.bad.g", capability="guide_rna"))
    ok = rep(chk("aav.packaging_limit", "fail"))
    result = runner.evaluate_all(tmp_path, resolver_returning(lambda i: ok))
    assert result["disagreement_count"] == 0


def test_default_resolver_without_registry_is_unavailable_not_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_REGISTRY_MODULES", ("no.such.module",))
    write(tmp_path, "aav/x.json", bad_case())
    result = runner.evaluate_all(tmp_path)
    assert result["disagreement_count"] == 1
    assert "registry not found" in result["capabilities"][0]["disagreements"][0]["problems"][0]


def test_json_report_is_written_without_timestamp(tmp_path):
    result = runner.evaluate_all(tmp_path / "none")
    path = runner.write_json(result, tmp_path / "out")
    assert json.loads(path.read_text(encoding="utf-8"))["total"] == 0
