"""Identifiers, labels and the threshold mirror for the plasmid adapter.

This file declares no biological rule and decides no verdict. Every number in
it already exists in the constraint engine; nothing here is new, and nothing
here is read by a check. Two kinds of value live here:

* **Live reads.** Where the engine exposes the value it applied through a
  function (`repeat_profile_for`, `restriction_context_from_spec`,
  `host_context`), the adapter calls that function and reports what comes back.
  Those values cannot drift, because there is only one copy.

* **Mirrored literals.** A few of the engine's thresholds are written inline in
  the body of a check rather than named, so there is no function to call. They
  are restated here under `MIRRORED_THRESHOLDS`, each with the exact source
  line it mirrors, purely so section 5.4 rule 3 can be satisfied (a user must
  be able to see what the verdict was measured against).
  `tests/validation/test_plasmid_adapter.py` reads the engine's source and
  fails if a mirrored literal no longer appears there, so a threshold edit in
  the engine cannot leave this file quietly wrong.

The check ids are the ids the curated gold data has used since the set was
built, which are also the engine's own `ValidationCheck.name` values. The
mapping is therefore the identity, and it is written out in full anyway so that
a future rename has one place to record itself.
"""

from __future__ import annotations

from typing import Any, Mapping

from packages.validation.common import CHECK_VERSION

ADAPTER_VERSION = "plasmid-adapter-1.0.0"
"""The adapter's own version. Bumped when the adapter changes how it shapes a
report. It says nothing about the engine's thresholds, which is why
`VALIDATOR_VERSION` carries the engine version too."""

VALIDATOR_VERSION = f"{ADAPTER_VERSION}+{CHECK_VERSION}"
"""`ValidationReport.validator_version` (section 5.4 rule 4).

The engine owns every threshold a plasmid verdict is measured against, and it
versions them with `CHECK_VERSION`. Embedding that string means a threshold
change in the engine changes this version without anyone having to remember to
edit this file, which is exactly what rule 4 asks for.
"""

SECTION_8_2 = "SYSTEM_DESIGN.md section 8.2 (deterministic constraint checks)"
SECTION_8_3 = "SYSTEM_DESIGN.md section 8.3 (check severities and report shape)"

# Engine ValidationCheck.name -> contract CheckResult.check_id.
# Identity today. A rename belongs here and nowhere else.
CHECK_ID_BY_ENGINE_NAME: dict[str, str] = {
    "restriction_site_conflicts": "restriction_site_conflicts",
    "repeat_and_instability": "repeat_and_instability",
    "codon_usage": "codon_usage",
    "regulatory_compatibility": "regulatory_compatibility",
}

#: Reporting order, matching `ConstraintEngine.checks`. Every run reports all
#: four, so a verdict never omits a check silently.
CHECK_IDS: tuple[str, ...] = (
    "restriction_site_conflicts",
    "repeat_and_instability",
    "codon_usage",
    "regulatory_compatibility",
)

#: Human readable names for the UI (`CheckResult.label`).
CHECK_LABELS: dict[str, str] = {
    "restriction_site_conflicts": "Restriction site conflicts",
    "repeat_and_instability": "Repeats and synthesis instability",
    "codon_usage": "Codon usage for the requested host",
    "regulatory_compatibility": "Regulatory element compatibility",
}

#: Why each check exists (`CheckResult.citation`). These are document
#: references, not thresholds, so they are safe to state here.
CHECK_CITATIONS: dict[str, str] = {
    "restriction_site_conflicts": SECTION_8_2,
    "repeat_and_instability": SECTION_8_2,
    "codon_usage": SECTION_8_2,
    "regulatory_compatibility": SECTION_8_2,
}

#: Engine `ValidationStatus` -> contract `Severity` value. The engine has no
#: UNKNOWN, so this mapping is total and lossless, and no verdict moves.
SEVERITY_BY_ENGINE_STATUS: dict[str, str] = {
    "PASS": "pass",
    "WARN": "warn",
    "FAIL": "fail",
}

#: Thresholds the engine writes inline. Key is the check id; each entry records
#: the value, and `source` names the module and the expression it mirrors.
MIRRORED_THRESHOLDS: dict[str, dict[str, Any]] = {
    "restriction_site_conflicts": {
        "mcs_padding_bp": 6,
        "source": "packages/validation/restriction.py: overlaps_any(..., padding=6)",
    },
    "repeat_and_instability": {
        "gc_window_bp": 100,
        "gc_fail_below_fraction": 0.20,
        "gc_fail_above_fraction": 0.80,
        "source": "packages/validation/repeats.py: first_gc_extreme(dna, window=100, low=0.20, high=0.80)",
    },
    "codon_usage": {
        "cai_fail_below": 0.55,
        "cai_warn_below": 0.75,
        "source": "packages/validation/codon.py: worst_score < 0.55 (FAIL) and worst_score < 0.75 (WARN)",
    },
}

#: Source expressions that must still appear in the engine, one per mirrored
#: literal. The adapter's test asserts each one, so an engine threshold edit
#: fails rather than silently contradicting `parameters_used`.
MIRROR_GUARDS: tuple[tuple[str, str], ...] = (
    ("packages/validation/restriction.py", "padding=6"),
    ("packages/validation/repeats.py", "window=100, low=0.20, high=0.80"),
    ("packages/validation/codon.py", "worst_score < 0.55"),
    ("packages/validation/codon.py", "worst_score < 0.75"),
)


def mirrored_values(check_id: str) -> Mapping[str, Any]:
    """The mirrored literals for one check, without the `source` annotation."""
    entry = MIRRORED_THRESHOLDS.get(check_id, {})
    return {key: value for key, value in entry.items() if key != "source"}
