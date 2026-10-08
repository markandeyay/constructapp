"""Convert the curated plasmid gold records into multi-capability runner cases.

Source (unchanged by this script):

* `data/eval/validation/curated_known_good.jsonl`, 36 records, each already
  tiered A or B, and each Tier B record already carrying its warning
  justifications.
* `data/eval/validation/curated_known_bad.jsonl`, 52 records, each already
  carrying `expected_failing_checks` with exactly one entry.

Output, in the case format `tests/gold/runner.py` reads:

* `tests/gold/plasmid/tier_a.json`
* `tests/gold/plasmid/tier_b.json`
* `tests/gold/plasmid/known_bad.json`

The conversion is mechanical and total. It invents no expectation: every
`expect_check`, every tier and every justification comes from the source record,
and the case input is the record's `design_spec` and `annotated_sequence`
verbatim. What it adds is the runner's field names, a case id, and the
provenance fields that keep each case traceable back to the record it came from.

It refuses rather than guesses. A known-bad record without exactly one
`expected_failing_checks` entry, an entry naming a check the adapter does not
report, a tier that is not A or B, a Tier B record with no warning, or a
duplicate case id all raise. Running it twice writes byte-identical files, so a
reviewer can regenerate and diff; `tests/gold/test_plasmid_gold_cases.py` does
exactly that.

Usage, from the repository root::

    python scripts/convert_plasmid_gold.py
    python scripts/convert_plasmid_gold.py --output-dir tests/gold/plasmid
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.validation.plasmid.constants import CHECK_IDS  # noqa: E402

DEFAULT_GOOD_PATH = Path("data/eval/validation/curated_known_good.jsonl")
DEFAULT_BAD_PATH = Path("data/eval/validation/curated_known_bad.jsonl")
DEFAULT_OUTPUT_DIR = Path("tests/gold/plasmid")

CAPABILITY = "plasmid"
SECTION_9_3 = (
    "Section 9.3 requires a known-bad case to name the check that must catch it and to report no "
    "unexpected FAIL, so the case cannot pass for the wrong reason."
)

_SLUG = re.compile(r"[^a-z0-9]+")


def slug(value: str) -> str:
    """A stable, readable case-id fragment: lowercase, single underscores."""
    return _SLUG.sub("_", value.lower()).strip("_")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def case_input(record: dict[str, Any]) -> dict[str, Any]:
    """The two blocks the plasmid validator takes, copied with no edit.

    These are the same two blocks `packages.validation.eval` feeds the raw
    engine, which is why converting the set cannot move a verdict.
    """
    return {
        "design_spec": record["design_spec"],
        "annotated_sequence": record["annotated_sequence"],
    }


def known_bad_case(record: dict[str, Any], source_file: Path) -> dict[str, Any]:
    source_case_id = str(record["case_id"])
    expected = record.get("expected_failing_checks") or []
    if len(expected) != 1:
        raise ValueError(
            f"{source_case_id}: expected exactly one entry in expected_failing_checks, got {expected!r}. "
            "A case that names zero or several checks cannot carry the section 9.3 named-check assertion."
        )
    check_id = str(expected[0])
    if check_id not in CHECK_IDS:
        raise ValueError(
            f"{source_case_id}: expected_failing_checks names {check_id!r}, which the plasmid validator "
            f"does not report. Known check ids: {', '.join(CHECK_IDS)}."
        )
    citation = record.get("rationale_citation") or {}
    source_rationale = str(citation.get("rationale", "")).strip()
    defect_type = str(record.get("defect_type", "")).strip()
    check_category = str(record.get("check_category", "")).strip()
    source_plasmid_id = str(record.get("source_plasmid_id", "")).strip()
    rationale = " ".join(
        part
        for part in (
            source_rationale,
            f"Defect injected: {defect_type} (category {check_category})." if defect_type else "",
            f"The case names {check_id} as the check that must catch it. {SECTION_9_3}",
            (
                f"The construct is the known-good source record {source_plasmid_id} with only that defect "
                "applied, so the sole difference from a passing construct is the defect under test; the "
                "exact edit is recorded in construction_procedure."
                if source_plasmid_id
                else ""
            ),
        )
        if part
    )
    return {
        "case_id": f"{CAPABILITY}.bad.{slug(source_case_id.removeprefix('ckb_'))}",
        "capability": CAPABILITY,
        "expect_overall": "fail",
        "expect_check": check_id,
        "expect_severity": "fail",
        "rationale": rationale,
        "defect_type": record.get("defect_type"),
        "check_category": record.get("check_category"),
        "rationale_citation": citation,
        "construction_procedure": record.get("construction_procedure"),
        "source_plasmid_id": record.get("source_plasmid_id"),
        "source_case_id": source_case_id,
        "source_record_path": record.get("source_record_path"),
        "converted_from": source_file.as_posix(),
        "input": case_input(record),
    }


def known_good_case(record: dict[str, Any], source_file: Path) -> dict[str, Any]:
    tier = str(record.get("tier", ""))
    if tier not in ("A", "B"):
        raise ValueError(f"{record.get('plasmid_id')!r}: tier must be 'A' or 'B', got {tier!r}")
    plasmid_id = str(record["plasmid_id"])
    case: dict[str, Any] = {
        "case_id": f"{CAPABILITY}.good.{tier.lower()}.{slug(plasmid_id)}",
        "capability": CAPABILITY,
        "tier": tier,
        "rationale": str(record.get("rationale", "")).strip(),
        "name": record.get("name"),
        "accession": record.get("accession"),
        "vector_profile": record.get("vector_profile"),
        "tier_label": record.get("tier_label"),
        "known_good_basis": record.get("known_good_basis"),
        "citation_source_evidence": record.get("citation_source_evidence"),
        "feature_evidence": record.get("feature_evidence"),
        "source_plasmid_id": plasmid_id,
        "converted_from": source_file.as_posix(),
        "input": case_input(record),
    }
    if tier == "B":
        case["expected_warnings"] = expected_warnings(record)
    elif record.get("expected_warnings"):
        raise ValueError(
            f"{plasmid_id}: a Tier A record declares expected_warnings. Tier A must validate with no "
            "warnings, so this record is mis-tiered in the source and is not converted."
        )
    return case


def expected_warnings(record: dict[str, Any]) -> list[dict[str, str]]:
    """The documented warnings, with the justification the source record gives.

    The source carries two parallel pieces of prose: a short `rationale` on each
    `expected_warnings` entry, and a longer entry in `warn_justifications`. Both
    are kept, joined, because the runner wants one `justification` string per
    warning and dropping either would lose a reason a reviewer wrote down.
    """
    plasmid_id = record.get("plasmid_id")
    entries = record.get("expected_warnings") or []
    if not entries:
        raise ValueError(f"{plasmid_id!r}: Tier B requires at least one expected warning, found none")
    extra = [str(item).strip() for item in (record.get("warn_justifications") or [])]
    converted: list[dict[str, str]] = []
    for index, entry in enumerate(entries):
        check_id = str(entry.get("check", ""))
        if check_id not in CHECK_IDS:
            raise ValueError(f"{plasmid_id!r}: expected warning names unknown check {check_id!r}")
        status = str(entry.get("status", "WARN"))
        if status != "WARN":
            raise ValueError(
                f"{plasmid_id!r}: expected warning on {check_id} has status {status!r}, not WARN. "
                "A Tier B record documents warnings only."
            )
        parts = [str(entry.get("rationale", "")).strip()]
        # One justification per warning when the counts line up; otherwise every
        # justification is attached, because none of them may be dropped.
        parts.extend([extra[index]] if len(extra) == len(entries) else extra)
        justification = " ".join(part for part in parts if part)
        if not justification:
            raise ValueError(f"{plasmid_id!r}: expected warning on {check_id} has no justification")
        converted.append({"check": check_id, "justification": justification})
    return converted


def write_cases(path: Path, cases: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def convert(
    good_path: Path = DEFAULT_GOOD_PATH,
    bad_path: Path = DEFAULT_BAD_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    good = [known_good_case(record, good_path) for record in read_jsonl(good_path)]
    bad = [known_bad_case(record, bad_path) for record in read_jsonl(bad_path)]
    tier_a = [case for case in good if case["tier"] == "A"]
    tier_b = [case for case in good if case["tier"] == "B"]

    seen: set[str] = set()
    for case in (*tier_a, *tier_b, *bad):
        if case["case_id"] in seen:
            raise ValueError(f"duplicate case_id {case['case_id']!r}; the runner rejects duplicates")
        seen.add(case["case_id"])

    written = {
        "tier_a": write_cases(output_dir / "tier_a.json", tier_a),
        "tier_b": write_cases(output_dir / "tier_b.json", tier_b),
        "known_bad": write_cases(output_dir / "known_bad.json", bad),
    }
    by_check: dict[str, int] = {}
    for case in bad:
        by_check[case["expect_check"]] = by_check.get(case["expect_check"], 0) + 1
    return {
        "output_dir": output_dir.as_posix(),
        "files": {name: path.as_posix() for name, path in written.items()},
        "tier_a": len(tier_a),
        "tier_b": len(tier_b),
        "known_bad": len(bad),
        "total": len(tier_a) + len(tier_b) + len(bad),
        "known_bad_by_check": dict(sorted(by_check.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--known-good-path", type=Path, default=DEFAULT_GOOD_PATH)
    parser.add_argument("--known-bad-path", type=Path, default=DEFAULT_BAD_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    summary = convert(args.known_good_path, args.known_bad_path, args.output_dir)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
