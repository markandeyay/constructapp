"""Shared fixtures for the guide RNA tests.

Every sequence here is either synthetic or constructed in the test body, and
the timestamp is fixed so the whole suite is deterministic (section 3.3
constraint 3).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest

from packages.core.schemas.grna import GuideRNADesign, GuideRNARequest, GuideSpec, OffTargetSpace
from packages.validation.grna import GuideRNAValidator

FIXED_TIME = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)

#: A synthetic target with SpCas9 and Cas12a sites, long enough for 30 nt
#: contexts and for a coding sequence annotation.
TARGET = (
    "ACGTTGCAATTTCGGCACTAGGTACCAGGTTACGAACCGGTTAAGGCCTTAAGGCCGGTTAACCGG"
    "ACGTACGTAGCTGACTGACGATCGGATCCTTAGGCATCAGCTAGCTAGGACTGACTGGCATCAGCA"
    "TCAGGTACGTACGTAAGGCCTTAAGGACGTCTGACTGACGTACGTACGGTTACGTACGATCGATCG"
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_by_path(module_name: str, path: Path) -> ModuleType:
    """Import a module from its file, bypassing name resolution.

    `tests/services/api/__init__.py` makes `tests/services` a namespace path
    entry for `services`, which shadows the real `services.api` package during
    a pytest run. The pre-existing API tests work around it the same way. This
    helper keeps that workaround in one place.
    """
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_routes_module() -> ModuleType:
    """The real `services/api/routes/__init__.py`, with its delimited regions."""
    return _load_by_path(
        "construct_api_routes", REPO_ROOT / "services" / "api" / "routes" / "__init__.py"
    )


def load_grna_route_module() -> ModuleType:
    """The real `services/api/routes/grna.py`."""
    return _load_by_path(
        "construct_api_routes_grna", REPO_ROOT / "services" / "api" / "routes" / "grna.py"
    )


@pytest.fixture
def validator() -> GuideRNAValidator:
    return GuideRNAValidator(evaluated_at=FIXED_TIME)


def make_request(**overrides: object) -> GuideRNARequest:
    """A valid request, with any field overridden by keyword."""
    payload: dict[str, object] = {
        "target_sequence": TARGET,
        "target_name": "TEST_TARGET",
        "nuclease": "SpCas9",
        "edit_intent": "knockout",
        "off_target_space": OffTargetSpace(scope="construct_only"),
        "max_guides_returned": 5,
    }
    payload.update(overrides)
    return GuideRNARequest(**payload)  # type: ignore[arg-type]


def make_design(spacer: str, pam: str, **overrides: object) -> GuideRNADesign:
    """A design for one explicit guide, with request fields overridable."""
    strand = overrides.pop("strand", 1)
    spacer_start = overrides.pop("spacer_start", None)
    return GuideRNADesign(
        request=make_request(**overrides),
        guide=GuideSpec(spacer=spacer, pam=pam, strand=strand, spacer_start=spacer_start),  # type: ignore[arg-type]
    )


def severity_of(report: object, check_id: str) -> str:
    """The severity of one named check, as a plain string."""
    for check in report.checks:  # type: ignore[attr-defined]
        if check.check_id == check_id:
            return str(check.severity.value)
    raise AssertionError(f"check {check_id!r} is missing from the report")


def message_of(report: object, check_id: str) -> str:
    for check in report.checks:  # type: ignore[attr-defined]
        if check.check_id == check_id:
            return check.message
    raise AssertionError(f"check {check_id!r} is missing from the report")
