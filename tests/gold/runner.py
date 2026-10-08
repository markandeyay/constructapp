"""Per-capability gold-set runner (spec sections 9.2, 9.3, 9.5, 3.4).

Case files are JSON under ``tests/gold/<capability>/``. A file holds either one
case object or a list of case objects. Discovery is sorted, so output order is
reproducible. The runner is deterministic and needs no database.

Known-bad case (section 9.3)::

    {
      "case_id": "aav.bad.over_hard_limit",
      "capability": "aav",
      "expect_overall": "fail",
      "expect_check": "aav.packaging_limit",
      "expect_severity": "fail",
      "rationale": "...",
      "must_also_report": ["remediation_suggestion"],
      "allowed_extra_fail": [],
      "input": {}
    }

A known-bad case is correct only when ALL of these hold:

1. the report overall severity equals ``expect_overall``;
2. the check named by ``expect_check`` is present and reports ``expect_severity``;
3. no OTHER check reports FAIL (unless listed in ``allowed_extra_fail``);
4. every ``must_also_report`` entry is satisfied (see ``_must_report``).

Known-good case (sections 3.4 and 9.2)::

    {"case_id": "aav.good.a1", "capability": "aav", "tier": "A", "input": {}}
    {"case_id": "aav.good.b1", "capability": "aav", "tier": "B",
     "expected_warnings": [{"check": "aav.kozak_context", "justification": "..."}],
     "input": {}}

Tier A must validate with no WARN, no FAIL and no UNKNOWN. Tier B must have no
FAIL, and the set of WARN checks must equal the documented ``expected_warnings``
set: the documented warnings being present is the expected outcome.

Rule from section 3.3 (4) and 5.4 (1): UNKNOWN never improves a verdict. An
UNKNOWN check is therefore a disagreement for a known-good case unless it is
listed in ``expected_unknown``, and an UNKNOWN on the check a known-bad case
names is a disagreement, never a match. The runner also recomputes the overall
severity from the checks (worst non-UNKNOWN) and flags a validator whose
declared overall disagrees.

Exit status: 0 when every case agrees, 1 on any disagreement or unevaluable
case. A capability with zero cases reports zero explicitly; add
``--require-cases`` to make zero cases an error.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

DEFAULT_GOLD_ROOT = Path("tests/gold")
DEFAULT_OUTPUT_DIR = Path("data/eval/capabilities")

# Capabilities that must always appear in the report, in this order, even when
# their directory does not exist yet. Value is the CapabilityKind value used by
# the registry (section 5.1); the directory name is the key.
EXPECTED_CAPABILITIES: dict[str, str] = {
    "aav": "aav",
    "assembly": "assembly",
    "grna": "guide_rna",
    # Plasmid pre-dates the shared contract and reaches the runner through the
    # adapter in packages.validation.plasmid. It is listed here, not left to
    # directory discovery, so that losing tests/gold/plasmid/ reports a
    # capability with zero cases instead of quietly reporting three.
    "plasmid": "plasmid",
}

# Severity order used to recompute overall (section 5.4 rule 1). UNKNOWN is not
# ranked: it is excluded from the worst-severity calculation.
_RANK = {"pass": 0, "warn": 1, "fail": 2}
_VALID = {"pass", "warn", "fail", "unknown"}

# Registry module locations tried by the default resolver. Contract owned by WP-02.
_REGISTRY_MODULES = (
    "packages.core.capability_registry",
    "packages.core.schemas.registry",
    "packages.core.registry",
)


class ValidatorUnavailable(Exception):
    """The validator for a capability could not be resolved. Never a pass."""


# A runner takes the case ``input`` dict and returns a report-like object
# (attributes or dict keys: ``overall``, ``checks`` with ``check_id`` and ``severity``).
CaseRunner = Callable[[dict[str, Any]], Any]
Resolver = Callable[[str], CaseRunner]


@dataclass
class CaseOutcome:
    case_id: str
    source: str
    set: str  # "known_good", "known_bad" or "malformed"
    tier: str | None
    expected: str
    actual: str
    problems: list[str] = field(default_factory=list)
    unknown_checks: list[str] = field(default_factory=list)

    @property
    def correct(self) -> bool:
        return not self.problems

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "source": self.source,
            "set": self.set,
            "tier": self.tier,
            "expected": self.expected,
            "actual": self.actual,
            "correct": self.correct,
            "problems": list(self.problems),
            "unknown_checks": list(self.unknown_checks),
        }


# ---------------------------------------------------------------------------
# Report normalisation
# ---------------------------------------------------------------------------


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _sev(value: Any) -> str:
    value = getattr(value, "value", value)
    return str(value).lower() if value is not None else "<missing>"


def _checks(report: Any) -> list[tuple[str, str, Any]]:
    out = []
    for check in _get(report, "checks", None) or []:
        out.append((str(_get(check, "check_id", "<no check_id>")), _sev(_get(check, "severity")), check))
    return out


def recompute_overall(check_severities: list[str]) -> str:
    """Worst non-UNKNOWN severity; ``unknown`` when nothing could be evaluated."""
    ranked = [s for s in check_severities if s in _RANK]
    if not ranked:
        return "unknown"
    return max(ranked, key=lambda s: _RANK[s])


def _has_value(value: Any) -> bool:
    return value not in (None, "", [], {}, ())


def _must_report(report: Any, checks: list[tuple[str, str, Any]], item: Any) -> bool:
    """Whether a ``must_also_report`` entry is satisfied by the report.

    A string name is satisfied when any of these holds: a check with that
    ``check_id`` is present and not UNKNOWN; any check carries a non-empty
    attribute or key of that name; the report carries a non-empty attribute or
    key of that name. An object ``{"check": id, "severity": s}`` requires that
    check at that severity. Anything else is unsatisfied: the runner never
    passes a requirement it could not verify.
    """
    if isinstance(item, dict):
        want_check = item.get("check")
        want_sev = str(item.get("severity", "")).lower()
        return any(cid == want_check and sev == want_sev for cid, sev, _ in checks)
    if not isinstance(item, str) or not item:
        return False
    if any(cid == item and sev != "unknown" for cid, sev, _ in checks):
        return True
    if any(_has_value(_get(check, item)) for _, _, check in checks):
        return True
    return _has_value(_get(report, item))


# ---------------------------------------------------------------------------
# Case evaluation (pure function of case + report, so it is directly testable)
# ---------------------------------------------------------------------------


def _normalise_ids(value: Any) -> list[str] | None:
    if value is None:
        return []
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return list(value)
    return None


def judge_case(case: dict[str, Any], report: Any, source: str = "") -> CaseOutcome:
    """Compare one report with one case and list every disagreement."""
    case_id = str(case.get("case_id", "<missing case_id>"))
    checks = _checks(report)
    by_id: dict[str, str] = {}
    for cid, sev, _ in checks:
        # Duplicate check ids: keep the worst, so a hidden FAIL cannot be shadowed.
        prev = by_id.get(cid)
        if prev is None or _RANK.get(sev, -1) > _RANK.get(prev, -1):
            by_id[cid] = sev
    declared = _sev(_get(report, "overall"))
    recomputed = recompute_overall([sev for _, sev, _ in checks])
    unknown = sorted(cid for cid, sev, _ in checks if sev == "unknown")
    fails = sorted({cid for cid, sev, _ in checks if sev == "fail"})
    warns = sorted({cid for cid, sev, _ in checks if sev == "warn"})
    problems: list[str] = []

    if declared not in _VALID:
        problems.append(f"report overall {declared!r} is not a valid severity")
    elif declared != recomputed:
        problems.append(
            f"report overall is {declared!r} but its checks imply {recomputed!r}; "
            "overall must be the worst non-UNKNOWN severity"
        )
    for cid, sev, _ in checks:
        if sev not in _VALID:
            problems.append(f"check {cid} has invalid severity {sev!r}")

    has_tier = "tier" in case
    has_expect = "expect_check" in case
    if has_tier == has_expect:
        problems.append("malformed case: exactly one of 'tier' (known-good) or 'expect_check' (known-bad) is required")
        return CaseOutcome(case_id, source, "malformed", None, "well-formed case", f"overall={declared}", problems, unknown)

    allowed_unknown = _normalise_ids(case.get("expected_unknown"))
    if allowed_unknown is None:
        problems.append("malformed case: 'expected_unknown' must be a list of check ids")
        allowed_unknown = []

    if has_tier:
        return _judge_good(case, case_id, source, declared, by_id, warns, fails, unknown, allowed_unknown, problems)
    return _judge_bad(case, case_id, source, report, checks, declared, by_id, fails, unknown, problems)


def _judge_good(
    case: dict[str, Any],
    case_id: str,
    source: str,
    declared: str,
    by_id: dict[str, str],
    warns: list[str],
    fails: list[str],
    unknown: list[str],
    allowed_unknown: list[str],
    problems: list[str],
) -> CaseOutcome:
    tier = case.get("tier")
    if tier not in ("A", "B"):
        problems.append(f"malformed case: tier must be 'A' or 'B', got {tier!r}")
        return CaseOutcome(case_id, source, "malformed", None, "tier A or B", f"overall={declared}", problems, unknown)
    expected_warn = case.get("expected_warnings", [])
    documented: list[str] = []
    if tier == "B":
        if not isinstance(expected_warn, list) or not expected_warn:
            problems.append("malformed case: Tier B requires a non-empty 'expected_warnings' list")
        else:
            for entry in expected_warn:
                if not isinstance(entry, dict) or not entry.get("check") or not entry.get("justification"):
                    problems.append("malformed case: each expected_warnings entry needs 'check' and 'justification'")
                else:
                    documented.append(str(entry["check"]))
    elif expected_warn:
        problems.append("malformed case: Tier A must not declare expected_warnings (use Tier B)")

    if fails:
        problems.append(f"unexpected FAIL on known-good case: {', '.join(fails)}")
    stray_unknown = [cid for cid in unknown if cid not in allowed_unknown]
    if stray_unknown:
        problems.append(
            f"UNKNOWN check(s) {', '.join(stray_unknown)}: an unevaluated check cannot show a case is clean "
            "(list in 'expected_unknown' if intentional)"
        )
    if tier == "A":
        if warns:
            problems.append(f"Tier A must validate with no warnings, got WARN on: {', '.join(warns)}")
        if declared != "pass" and not fails and not warns:
            problems.append(f"Tier A overall must be 'pass', got {declared!r}")
        expected = "tier A: pass, no WARN, no FAIL, no UNKNOWN"
    else:
        missing = [cid for cid in documented if cid not in warns]
        extra = [cid for cid in warns if cid not in documented]
        if missing:
            problems.append(f"documented warning(s) not reported: {', '.join(missing)}")
        if extra:
            problems.append(f"undocumented warning(s) reported: {', '.join(extra)}")
        expected = f"tier B: no FAIL, WARN exactly on {', '.join(sorted(documented)) or '(none documented)'}"
    actual = f"overall={declared}; WARN={warns or '[]'}; FAIL={fails or '[]'}; UNKNOWN={unknown or '[]'}"
    return CaseOutcome(case_id, source, "known_good", tier, expected, actual, problems, unknown)


def _judge_bad(
    case: dict[str, Any],
    case_id: str,
    source: str,
    report: Any,
    checks: list[tuple[str, str, Any]],
    declared: str,
    by_id: dict[str, str],
    fails: list[str],
    unknown: list[str],
    problems: list[str],
) -> CaseOutcome:
    expect_overall = str(case.get("expect_overall", "")).lower()
    expect_check = case.get("expect_check")
    expect_severity = str(case.get("expect_severity", "")).lower()
    for name, value in (("expect_overall", expect_overall), ("expect_severity", expect_severity)):
        if value not in _VALID:
            problems.append(f"malformed case: {name} {value!r} is not a valid severity")
    if not isinstance(expect_check, str) or not expect_check:
        problems.append("malformed case: expect_check must be a check id string")
    extra_allowed = _normalise_ids(case.get("allowed_extra_fail"))
    if extra_allowed is None:
        problems.append("malformed case: 'allowed_extra_fail' must be a list of check ids")
        extra_allowed = []
    must = case.get("must_also_report", [])
    if not isinstance(must, list):
        problems.append("malformed case: 'must_also_report' must be a list")
        must = []

    # Assertion 1: overall severity.
    if expect_overall in _VALID and declared != expect_overall:
        problems.append(f"overall severity: expected {expect_overall!r}, got {declared!r}")

    # Assertion 2: the NAMED check reports the expected severity.
    actual_for_check = by_id.get(expect_check) if isinstance(expect_check, str) else None
    if isinstance(expect_check, str) and expect_check:
        if actual_for_check is None:
            problems.append(
                f"named check {expect_check} was not reported at all "
                f"(checks present: {', '.join(sorted(by_id)) or 'none'})"
            )
        elif actual_for_check == "unknown":
            problems.append(f"named check {expect_check} was UNKNOWN; UNKNOWN never counts as a match")
        elif expect_severity in _VALID and actual_for_check != expect_severity:
            problems.append(f"named check {expect_check}: expected {expect_severity!r}, got {actual_for_check!r}")

    # Assertion 3: no unexpected FAIL anywhere in the report.
    unexpected = [cid for cid in fails if cid != expect_check and cid not in extra_allowed]
    if unexpected:
        problems.append(
            f"unexpected FAIL on check(s) other than {expect_check}: {', '.join(unexpected)} "
            "(the case may be failing for the wrong reason)"
        )

    # Optional: required report content.
    for item in must:
        if not _must_report(report, checks, item):
            problems.append(f"must_also_report not satisfied: {item!r}")

    expected = (
        f"overall={expect_overall}; {expect_check}={expect_severity}; no other FAIL"
        + (f" except {', '.join(extra_allowed)}" if extra_allowed else "")
    )
    shown = {cid: by_id[cid] for cid in sorted(by_id) if by_id[cid] != "pass"}
    actual = f"overall={declared}; {expect_check}={actual_for_check}; non-pass checks={shown or '{}'}"
    return CaseOutcome(case_id, source, "known_bad", None, expected, actual, problems, unknown)


# ---------------------------------------------------------------------------
# Discovery and execution
# ---------------------------------------------------------------------------


def discover(gold_root: Path, capability: str) -> list[Path]:
    directory = gold_root / capability
    if not directory.is_dir():
        return []
    return sorted(directory.rglob("*.json"), key=lambda p: p.as_posix())


def _canonical_kind(capability: str) -> str:
    return EXPECTED_CAPABILITIES.get(capability, capability)


def load_cases(paths: list[Path], root: Path) -> tuple[list[tuple[str, dict[str, Any]]], list[CaseOutcome]]:
    """Return ``(source, case)`` pairs plus an outcome for every unreadable file."""
    cases: list[tuple[str, dict[str, Any]]] = []
    errors: list[CaseOutcome] = []
    for path in paths:
        try:
            source = path.relative_to(root).as_posix()
        except ValueError:
            source = path.as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(CaseOutcome(source, source, "malformed", None, "readable JSON", "unreadable", [f"cannot load case file: {exc}"]))
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict):
                cases.append((source, item))
            else:
                errors.append(CaseOutcome(source, source, "malformed", None, "a case object", type(item).__name__, ["case entry is not a JSON object"]))
    return cases, errors


def registry_resolver(capability: str) -> CaseRunner:
    """Resolve a validator through the WP-02 capability registry.

    The registry spec is expected to expose ``validator`` (a CapabilityValidator)
    and optionally ``design_model`` (a pydantic model the case ``input`` is parsed
    into). Anything missing raises ``ValidatorUnavailable`` so the cases are
    reported as unevaluable rather than silently passing.
    """
    kind = _canonical_kind(capability)
    registry = None
    tried = []
    for module_name in _REGISTRY_MODULES:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            tried.append(f"{module_name} ({exc.__class__.__name__})")
            continue
        registry = getattr(module, "CAPABILITY_REGISTRY", None)
        if registry is not None:
            break
        tried.append(f"{module_name} (no CAPABILITY_REGISTRY)")
    if registry is None:
        raise ValidatorUnavailable("capability registry not found; tried " + "; ".join(tried))
    spec = next((v for k, v in registry.items() if _sev(k) == kind), None)
    if spec is None:
        raise ValidatorUnavailable(f"capability {kind!r} has no registry entry")
    validator = _get(spec, "validator")
    if validator is None and callable(_get(spec, "validator_factory")):
        validator = spec.validator_factory()
    if validator is None or not callable(getattr(validator, "validate", None)):
        raise ValidatorUnavailable(f"registry entry for {kind!r} exposes no validator")
    model = _get(spec, "design_model")

    def run(case_input: dict[str, Any]) -> Any:
        design = model.model_validate(case_input) if model is not None else case_input
        return validator.validate(design)

    return run


def evaluate_capability(
    capability: str,
    gold_root: Path = DEFAULT_GOLD_ROOT,
    resolver: Resolver = registry_resolver,
) -> dict[str, Any]:
    paths = discover(gold_root, capability)
    cases, outcomes = load_cases(paths, gold_root)
    seen: set[str] = set()
    runner: CaseRunner | None = None
    resolve_error: str | None = None
    if cases:
        try:
            runner = resolver(capability)
        except ValidatorUnavailable as exc:
            resolve_error = str(exc)
        except Exception as exc:  # resolver bugs must also be loud, never a pass
            resolve_error = f"resolver raised {exc.__class__.__name__}: {exc}"

    kind = _canonical_kind(capability)
    for source, case in cases:
        cid = str(case.get("case_id", "<missing case_id>"))
        label = "known_good" if "tier" in case else ("known_bad" if "expect_check" in case else "malformed")
        tier = case.get("tier") if isinstance(case.get("tier"), str) else None
        pre: list[str] = []
        if cid in seen:
            pre.append(f"duplicate case_id {cid!r}")
        seen.add(cid)
        if case.get("capability") not in (capability, kind):
            pre.append(f"case capability {case.get('capability')!r} does not match directory {capability!r}")
        if "input" not in case or not isinstance(case.get("input"), dict):
            pre.append("malformed case: 'input' object is required")
        if pre:
            outcomes.append(CaseOutcome(cid, source, label, tier, "well-formed case", "not evaluated", pre))
            continue
        if runner is None:
            outcomes.append(
                CaseOutcome(cid, source, label, tier, "a validator verdict", "UNEVALUABLE", [f"validator unavailable: {resolve_error}"])
            )
            continue
        try:
            report = runner(case["input"])
        except Exception as exc:
            outcomes.append(
                CaseOutcome(cid, source, label, tier, "a validator verdict", "validator raised", [f"validator raised {exc.__class__.__name__}: {exc}"])
            )
            continue
        outcomes.append(judge_case(case, report, source))

    outcomes.sort(key=lambda o: (o.source, o.case_id))
    return summarize(capability, outcomes)


def _bucket(outcomes: list[CaseOutcome]) -> dict[str, Any]:
    total = len(outcomes)
    correct = sum(1 for o in outcomes if o.correct)
    return {"total": total, "correct": correct, "accuracy": (correct / total) if total else None}


def summarize(capability: str, outcomes: list[CaseOutcome]) -> dict[str, Any]:
    good = [o for o in outcomes if o.set == "known_good"]
    return {
        "capability": capability,
        **_bucket(outcomes),
        "known_good": _bucket(good),
        "tier_a": _bucket([o for o in good if o.tier == "A"]),
        "tier_b": _bucket([o for o in good if o.tier == "B"]),
        "known_bad": _bucket([o for o in outcomes if o.set == "known_bad"]),
        "malformed": sum(1 for o in outcomes if o.set == "malformed"),
        "unknown_check_reports": sum(len(o.unknown_checks) for o in outcomes),
        "disagreements": [o.as_dict() for o in outcomes if not o.correct],
    }


def evaluate_all(
    gold_root: Path = DEFAULT_GOLD_ROOT,
    resolver: Resolver = registry_resolver,
    capabilities: list[str] | None = None,
) -> dict[str, Any]:
    names = list(capabilities) if capabilities else list(EXPECTED_CAPABILITIES)
    if not capabilities and gold_root.is_dir():
        for child in sorted(p.name for p in gold_root.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))):
            if child not in names and child != "__pycache__":
                names.append(child)
    results = [evaluate_capability(name, gold_root, resolver) for name in names]
    total = sum(r["total"] for r in results)
    correct = sum(r["correct"] for r in results)
    return {
        "gold_root": gold_root.as_posix(),
        "capabilities": results,
        "total": total,
        "correct": correct,
        "disagreement_count": sum(len(r["disagreements"]) for r in results),
        "accuracy": (correct / total) if total else None,
    }


# ---------------------------------------------------------------------------
# Reporting (section 9.5)
# ---------------------------------------------------------------------------


def _fmt_bucket(label: str, bucket: dict[str, Any]) -> str:
    acc = "n/a" if bucket["accuracy"] is None else f"{bucket['accuracy']:.3f}"
    return f"  {label:<11} {bucket['correct']}/{bucket['total']}  accuracy {acc}"


def render_text(result: dict[str, Any], require_cases: bool = False) -> str:
    lines = ["Capability gold sets (curated; no held-out split)", ""]
    for cap in result["capabilities"]:
        lines.append(f"[{cap['capability']}]")
        if cap["total"] == 0:
            lines.append("  0 cases found. This capability is NOT covered by any gold set yet.")
            if require_cases:
                lines.append("  --require-cases is set: zero cases is an error.")
        else:
            lines.append(_fmt_bucket("all cases", cap))
            lines.append(_fmt_bucket("known-good", cap["known_good"]))
            lines.append(_fmt_bucket("  tier A", cap["tier_a"]))
            lines.append(_fmt_bucket("  tier B", cap["tier_b"]))
            lines.append(_fmt_bucket("known-bad", cap["known_bad"]))
            if cap["malformed"]:
                lines.append(f"  malformed or unreadable case entries: {cap['malformed']}")
            if cap["unknown_check_reports"]:
                lines.append(f"  UNKNOWN check reports (never counted as pass): {cap['unknown_check_reports']}")
        if cap["disagreements"]:
            lines.append(f"  DISAGREEMENTS ({len(cap['disagreements'])}):")
            for item in cap["disagreements"]:
                lines.append(f"    - case {item['case_id']}  ({item['source']})")
                lines.append(f"        expected: {item['expected']}")
                lines.append(f"        actual:   {item['actual']}")
                for problem in item["problems"]:
                    lines.append(f"        problem:  {problem}")
        lines.append("")
    acc = "n/a" if result["accuracy"] is None else f"{result['accuracy']:.3f}"
    lines.append(
        f"TOTAL {result['correct']}/{result['total']} cases agree (accuracy {acc}); "
        f"{result['disagreement_count']} disagreement(s)"
    )
    return "\n".join(lines)


def exit_code(result: dict[str, Any], require_cases: bool = False) -> int:
    if result["disagreement_count"]:
        return 1
    if require_cases and any(cap["total"] == 0 for cap in result["capabilities"]):
        return 1
    return 0


def write_json(result: dict[str, Any], output_dir: Path) -> Path:
    """Write a timestamp-free report so repeated runs are byte identical."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "capability_gold.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the per-capability gold sets (no database needed).")
    parser.add_argument("--gold-root", type=Path, default=DEFAULT_GOLD_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--capability", action="append", help="Limit to one capability directory (repeatable).")
    parser.add_argument("--require-cases", action="store_true", help="Treat a capability with zero cases as an error.")
    parser.add_argument("--no-write", action="store_true", help="Do not write the JSON report.")
    args = parser.parse_args(argv)
    result = evaluate_all(args.gold_root, registry_resolver, args.capability)
    print(render_text(result, args.require_cases))
    if not args.no_write:
        print(f"report: {write_json(result, args.output_dir)}")
    return exit_code(result, args.require_cases)


if __name__ == "__main__":
    sys.exit(main())
