"""Section 3.3 and section 14.1 obligations on the thresholds themselves.

Source: section 3.3 constraints 1, 2, 5 and 6, section 5.4 rules 3 and 4, and the
section 14.1 per-package checklist item "Every constant has a docstring naming
its source".

The source-naming obligation is checked mechanically here rather than left to
review: every module-level constant in `constants.py` must carry a comment block
that names where its value came from. A constant added later without one fails
this test.
"""

from __future__ import annotations

import ast
import dataclasses
import re
from pathlib import Path

import pytest

from packages.core.schemas.capability import (
    assert_version_matches_thresholds,
    thresholds_fingerprint,
)
from packages.core.schemas.assembly import AssemblyThresholds
from packages.validation.assembly import constants
from packages.validation.assembly.checks import ALL_CHECK_IDS
from packages.validation.assembly.settings import DEFAULT_SETTINGS, Settings, settings_for
from tests.assembly.fixtures import clean_request

CONSTANTS_PATH = Path(constants.__file__)

# The files this work package authored. Used by the section 3.3 constraint 5 and
# 6 checks below.
AUTHORED_FILES: tuple[Path, ...] = tuple(
    sorted(
        {
            *Path("packages/validation/assembly").glob("*.py"),
            *Path("packages/generation/assembly").glob("*.py"),
            *Path("tests/assembly").glob("*.py"),
            Path("packages/core/schemas/assembly.py"),
            Path("packages/core/sequence/tm.py"),
            Path("services/api/routes/assembly.py"),
        }
    )
)

# This file defines the patterns it searches for, so it excludes itself from the
# two content scans below. Everything else this package authored is scanned.
SELF = Path(__file__).resolve()

# Words that count as naming a source. One of these must appear in the comment
# block above a constant.
_SOURCE_MARKERS = (
    "SPEC",
    "TOOL DEFAULT",
    "CHOSEN DEFAULT",
    "Source:",
    "Appendix",
    "section ",
    "Primer3",
    "NEB",
    "ViennaRNA",
    "protocol",
    "SantaLucia",
    "von Ahsen",
    "Gibson et al",
)


_ASSIGNMENT = re.compile(r"^[A-Z][A-Z_0-9]*\s*[:=]")


def _comment_block_above(lines: list[str], line_number: int) -> str:
    """The comment block governing a one-based line number.

    A shared comment often sits above a run of related constants (a min and a
    max, or the whole protocol block), so the walk upwards steps past sibling
    constant assignments and stops at the first blank line or other statement.
    That is the same grouping a reader sees.
    """
    block: list[str] = []
    index = line_number - 2  # zero-based, the line above
    while index >= 0:
        stripped = lines[index].strip()
        if stripped.startswith("#"):
            block.append(stripped.lstrip("#").strip())
            index -= 1
            continue
        if not block and _ASSIGNMENT.match(stripped):
            index -= 1  # a sibling under the same comment
            continue
        break
    return " ".join(reversed(block))


def _module_constants() -> list[tuple[str, int]]:
    tree = ast.parse(CONSTANTS_PATH.read_text(encoding="utf-8"))
    found: list[tuple[str, int]] = []
    for node in tree.body:
        targets = []
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
        elif isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
        for name in targets:
            if name.isupper():
                found.append((name, node.lineno))
    return found


def test_every_constant_names_its_source() -> None:
    """Section 14.1: "Every constant has a docstring naming its source".

    Mechanical, so a constant added without a source fails rather than slipping
    through review.
    """
    lines = CONSTANTS_PATH.read_text(encoding="utf-8").splitlines()
    missing: list[str] = []
    for name, line_number in _module_constants():
        comment = _comment_block_above(lines, line_number)
        if not comment or not any(marker in comment for marker in _SOURCE_MARKERS):
            missing.append(f"{name} (line {line_number})")
    assert missing == [], "constants with no source named in the comment above them: " + ", ".join(missing)


def test_every_constant_is_labelled_spec_tool_default_or_chosen_default() -> None:
    """The provenance class of each threshold is explicit, for WP-10's review.

    Only the threshold constants carry the label; the validator identity and the
    derived tables do not have a provenance class.
    """
    lines = CONSTANTS_PATH.read_text(encoding="utf-8").splitlines()
    exempt = {"VALIDATOR_VERSION", "THRESHOLD_FINGERPRINTS", "CITATIONS"}
    unlabelled: list[str] = []
    for name, line_number in _module_constants():
        if name in exempt:
            continue
        comment = _comment_block_above(lines, line_number)
        if not any(label in comment for label in ("SPEC", "TOOL DEFAULT", "CHOSEN DEFAULT", "PROTOCOL")):
            unlabelled.append(name)
    assert unlabelled == [], "thresholds with no provenance label: " + ", ".join(unlabelled)


def test_every_chosen_default_is_also_configurable() -> None:
    """Section 3.3 constraint 2: every threshold is configurable.

    Every key of `thresholds()` must have a field on `AssemblyThresholds`, or a
    caller cannot override it and the constraint is not actually met.
    """
    overridable = set(AssemblyThresholds.model_fields)
    missing = set(constants.thresholds()) - overridable
    assert missing == set(), "thresholds with no override field: " + ", ".join(sorted(missing))


def test_settings_covers_exactly_the_threshold_table() -> None:
    """One source of truth: `Settings`, `thresholds()` and the override model agree."""
    assert set(DEFAULT_SETTINGS.as_parameters()) == set(constants.thresholds())
    assert DEFAULT_SETTINGS.as_parameters() == constants.thresholds()
    assert DEFAULT_SETTINGS.overridden() == {}


def test_an_override_is_applied_and_reported_as_overridden() -> None:
    """Section 5.4 rule 3: a reader can tell a default from a caller's own number."""
    request = clean_request(thresholds=AssemblyThresholds(primer_tm_warn_tolerance_c=1.5))
    settings = settings_for(request)
    assert settings.primer_tm_warn_tolerance_c == 1.5
    assert settings.overridden() == {"primer_tm_warn_tolerance_c": 1.5}
    # Everything else is untouched.
    assert settings.primer_gc_min_fraction == constants.PRIMER_GC_MIN_FRACTION


def test_an_inverted_window_is_refused() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        AssemblyThresholds(primer_gc_min_fraction=0.8, primer_gc_max_fraction=0.2)


def test_the_threshold_fingerprint_is_pinned_to_the_validator_version() -> None:
    """Section 5.4 rule 4: a threshold change without a version bump fails here."""
    assert_version_matches_thresholds(
        constants.VALIDATOR_VERSION, constants.thresholds(), constants.THRESHOLD_FINGERPRINTS
    )


def test_changing_a_threshold_changes_the_fingerprint() -> None:
    """The mechanism actually detects a change, rather than being decorative."""
    baseline = thresholds_fingerprint(constants.thresholds())
    altered = dict(constants.thresholds())
    altered["primer_tm_warn_tolerance_c"] = 99.0
    assert thresholds_fingerprint(altered) != baseline
    with pytest.raises(AssertionError, match="thresholds changed"):
        assert_version_matches_thresholds(
            constants.VALIDATOR_VERSION, altered, constants.THRESHOLD_FINGERPRINTS
        )


def test_an_unpinned_version_fails_loudly() -> None:
    with pytest.raises(AssertionError, match="no pinned threshold fingerprint"):
        assert_version_matches_thresholds("assembly-9.9.9", constants.thresholds(), constants.THRESHOLD_FINGERPRINTS)


def test_every_check_has_a_citation() -> None:
    """Section 5.1: `citation` says why the threshold exists, for all nineteen."""
    assert set(constants.CITATIONS) == set(ALL_CHECK_IDS)
    for check_id, citation in constants.CITATIONS.items():
        assert len(citation) > 40, f"{check_id} citation is too thin to check"


def test_the_threshold_values_are_the_documented_ones() -> None:
    """A direct guard on the values a reviewer will look up against the sources."""
    assert constants.PRIMER_TM_WARN_TOLERANCE_C == 3.0  # Primer3 57 / 60 / 63
    assert constants.PRIMER_PAIR_MAX_TM_DELTA_C == 5.0
    assert (constants.PRIMER_GC_MIN_FRACTION, constants.PRIMER_GC_MAX_FRACTION) == (0.40, 0.60)
    assert (constants.PRIMER_MIN_LENGTH_NT, constants.PRIMER_MAX_LENGTH_NT) == (18, 27)  # Primer3
    assert constants.PRIMER_MAX_HOMOPOLYMER_RUN_NT == 5  # Primer3 PRIMER_MAX_POLY_X
    assert constants.MAX_SELF_COMPLEMENTARITY_ANY_BP == 8.0  # Primer3 PRIMER_MAX_SELF_ANY
    assert constants.MAX_SELF_COMPLEMENTARITY_END_BP == 3.0  # Primer3 PRIMER_MAX_SELF_END
    assert constants.MAX_PAIR_COMPLEMENTARITY_ANY_BP == 8.0  # Primer3 PRIMER_PAIR_MAX_COMPL_ANY
    assert constants.MAX_PAIR_COMPLEMENTARITY_END_BP == 3.0  # Primer3 PRIMER_PAIR_MAX_COMPL_END
    assert (constants.GIBSON_OVERLAP_MIN_BP, constants.GIBSON_OVERLAP_MAX_BP) == (15, 40)
    assert constants.GIBSON_OVERLAP_MIN_TM_C == 48.0  # NEBuilder Assembly Tool
    assert constants.HAIRPIN_MIN_LOOP_NT == 3  # ViennaRNA minimum loop size
    assert (constants.AMPLICON_MIN_BP, constants.AMPLICON_MAX_BP) == (100, 10_000)
    assert constants.PCR_EXTENSION_S_PER_KB == 30  # NEB Q5, 20 to 30 s per kb
    assert (constants.ANNEALING_MIN_C, constants.ANNEALING_MAX_C) == (50.0, 72.0)  # NEB Q5 range


# ---------------------------------------------------------------------------
# Section 3.3 constraints 5 and 6, and section 14.1's grep
# ---------------------------------------------------------------------------


def test_no_em_dash_in_any_file_this_package_authored() -> None:
    """Section 3.3 constraint 5: no em dash in any string, comment, docstring or document."""
    dashes = (chr(0x2014), chr(0x2013))
    offenders: list[str] = []
    for path in AUTHORED_FILES:
        if not path.exists() or path.resolve() == SELF:
            continue
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            if any(dash in line for dash in dashes):
                offenders.append(f"{path}:{number}")
    assert offenders == [], "em dash or en dash found at: " + ", ".join(offenders)


def test_no_retired_brand_token_in_any_file_this_package_authored() -> None:
    """Section 2.3 and the section 14.1 grep gate."""
    pattern = re.compile("|".join(("plasmid" + "ai", "plasmid" + "_ai", "P" + "MR")), re.IGNORECASE)
    offenders: list[str] = []
    for path in AUTHORED_FILES:
        if not path.exists() or path.resolve() == SELF:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line):
                offenders.append(f"{path}:{number}")
    assert offenders == [], "retired brand token found at: " + ", ".join(offenders)


def test_the_progress_file_exists_and_records_the_tm_comparison() -> None:
    """Deliverable 2: the Appendix A.1 table, side by side, with the tool and version."""
    path = Path("progress/WP-04.md")
    assert path.exists(), "progress/WP-04.md is a required deliverable"
    text = path.read_text(encoding="utf-8")
    assert "Biopython" in text
    assert "1.87" in text
    assert "DNA_NN3" in text
    assert "saltcorr" in text
    for sequence in (
        "GTAAAACGACGGCCAGTGAA",
        "GCGGCCGCGGCCGCGGCCGC",
        "AATTAATTAATTAATTAATT",
        "ACGTACGTACGTACGTAC",
    ):
        assert sequence in text, f"{sequence} is missing from the recorded Appendix A.1 table"
    assert chr(0x2014) not in text and chr(0x2013) not in text


def test_settings_is_frozen_so_a_check_cannot_mutate_a_threshold() -> None:
    """Determinism: one check must not be able to change what a later one measures."""
    settings = settings_for(clean_request())
    assert isinstance(settings, Settings)
    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.primer_tm_warn_tolerance_c = 1.0  # type: ignore[misc]
