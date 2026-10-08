"""The plasmid adapter changes no verdict, and says so where it cannot speak.

The first test is the one that matters: it drives the raw engine and the adapter
over every curated record, 88 of them, and asserts that the check set, the
per-check verdicts, the messages, the coordinates and the overall verdict all
agree. If the adapter ever starts re-deciding biology, this fails.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from packages.core.schemas import AnnotatedSequence, DesignSpec, ValidationCheck
from packages.core.schemas import ValidationReport as EngineValidationReport
from packages.core.schemas.capability import CapabilityKind, Severity, overall_from_checks
from packages.core.schemas.plasmid import PlasmidDesign
from packages.validation.engine import ConstraintEngine
from packages.validation.plasmid.constants import (
    CHECK_ID_BY_ENGINE_NAME,
    CHECK_IDS,
    MIRROR_GUARDS,
    SEVERITY_BY_ENGINE_STATUS,
)
from packages.validation.plasmid.validator import PlasmidValidator, build_validator

CURATED_GOOD = Path("data/eval/validation/curated_known_good.jsonl")
CURATED_BAD = Path("data/eval/validation/curated_known_bad.jsonl")


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _curated_designs() -> list[tuple[str, PlasmidDesign]]:
    designs: list[tuple[str, PlasmidDesign]] = []
    for path, id_field in ((CURATED_GOOD, "plasmid_id"), (CURATED_BAD, "case_id")):
        for record in _records(path):
            designs.append(
                (
                    str(record[id_field]),
                    PlasmidDesign(
                        design_spec=DesignSpec.model_validate(record["design_spec"]),
                        annotated_sequence=AnnotatedSequence.model_validate(record["annotated_sequence"]),
                    ),
                )
            )
    return designs


CURATED_DESIGNS = _curated_designs()


def test_curated_record_count_is_the_whole_set() -> None:
    assert len(CURATED_DESIGNS) == 88


def test_adapter_changes_no_verdict_on_any_curated_record() -> None:
    """Raw engine versus adapter, over all 88 curated records. Nothing may differ."""
    engine = ConstraintEngine()
    validator = PlasmidValidator(engine=engine)
    compared = 0
    for case_id, design in CURATED_DESIGNS:
        engine_report = engine.validate(design.annotated_sequence, design.design_spec)
        adapted = validator.validate(design)

        engine_names = [check.name for check in engine_report.checks]
        adapted_ids = [check.check_id for check in adapted.checks]
        assert adapted_ids == [CHECK_ID_BY_ENGINE_NAME[name] for name in engine_names], case_id

        for engine_check, result in zip(engine_report.checks, adapted.checks):
            assert result.severity.value == SEVERITY_BY_ENGINE_STATUS[str(engine_check.status)], (
                case_id,
                engine_check.name,
            )
            assert result.message == engine_check.message, (case_id, engine_check.name)
            if engine_check.region is None:
                assert result.coordinates is None, (case_id, engine_check.name)
            else:
                assert result.coordinates == (engine_check.region.start, engine_check.region.end), (
                    case_id,
                    engine_check.name,
                )

        assert adapted.overall.value == str(engine_report.overall).lower(), case_id
        assert adapted.overall == overall_from_checks(adapted.checks), case_id
        assert adapted.capability == CapabilityKind.PLASMID
        assert not adapted.unknown_checks, case_id
        compared += 1
    assert compared == 88


def test_every_curated_overall_distribution_is_preserved() -> None:
    """A counting check, so a silent whole-set shift cannot hide behind per-case equality."""
    engine = ConstraintEngine()
    validator = PlasmidValidator(engine=engine)
    engine_counts: dict[str, int] = {}
    adapter_counts: dict[str, int] = {}
    for _, design in CURATED_DESIGNS:
        engine_overall = str(engine.validate(design.annotated_sequence, design.design_spec).overall).lower()
        engine_counts[engine_overall] = engine_counts.get(engine_overall, 0) + 1
        adapted_overall = validator.validate(design).overall.value
        adapter_counts[adapted_overall] = adapter_counts.get(adapted_overall, 0) + 1
    assert engine_counts == adapter_counts
    assert sum(engine_counts.values()) == 88


def test_report_shape_follows_the_contract() -> None:
    _, design = CURATED_DESIGNS[0]
    report = build_validator().validate(design)
    assert [check.check_id for check in report.checks] == list(CHECK_IDS)
    assert report.validator_version.startswith("plasmid-adapter-")
    assert "phase3-validation-v1" in report.validator_version
    for check in report.checks:
        assert check.label
        assert check.message
        assert check.citation
        # Not invented: the engine reports prose, not a measured quantity.
        assert check.observed is None
        assert check.threshold is None
        assert check.remediation is None


def test_validator_accepts_a_plain_dict_input() -> None:
    record = _records(CURATED_BAD)[0]
    report = build_validator().validate(
        {"design_spec": record["design_spec"], "annotated_sequence": record["annotated_sequence"]}
    )
    assert report.overall == Severity.FAIL


def test_parameters_used_reports_the_thresholds_that_were_applied() -> None:
    _, design = CURATED_DESIGNS[0]
    validator = build_validator()
    parameters = validator.parameters_used(design)
    assert parameters
    for check_id in CHECK_IDS:
        assert check_id in parameters
    assert parameters["engine_version"] == "phase3-validation-v1"
    assert parameters["repeat_and_instability"]["direct_fail"] > 0
    assert parameters["repeat_and_instability"]["gc_window_bp"] == 100
    assert parameters["codon_usage"]["cai_fail_below"] == 0.55
    assert parameters["restriction_site_conflicts"]["mcs_padding_bp"] == 6


def test_repeat_profile_in_parameters_used_is_read_live_from_the_engine() -> None:
    """The reported profile follows the spec, so it cannot be a stale copy."""
    base = CURATED_DESIGNS[0][1]
    validator = build_validator()
    idt = base.model_copy(
        update={"design_spec": base.design_spec.model_copy(update={"constraints": ["supplier=IDT gBlocks"]})}
    )
    assert validator.parameters_used(idt)["repeat_and_instability"]["name"] == "idt_gblocks"
    twist = base.model_copy(
        update={"design_spec": base.design_spec.model_copy(update={"constraints": ["supplier=Twist"]})}
    )
    assert validator.parameters_used(twist)["repeat_and_instability"]["name"] == "twist_default"


def test_mirrored_thresholds_still_exist_in_the_engine_source() -> None:
    """Guards the only numbers the adapter restates rather than reads."""
    for module_path, expression in MIRROR_GUARDS:
        source = Path(module_path).read_text(encoding="utf-8")
        assert expression in source, f"{expression!r} no longer appears in {module_path}"


def test_provenance_is_never_empty_and_records_a_supplied_sequence() -> None:
    _, design = CURATED_DESIGNS[0]
    validator = build_validator()
    assert validator.provenance(design)[0] == "user_input:annotated_sequence"
    declared = design.model_copy(update={"provenance": ["curated:pUC19"]})
    assert validator.provenance(declared) == ["curated:pUC19"]


def test_design_result_satisfies_rules_three_and_five() -> None:
    _, design = CURATED_DESIGNS[0]
    result = build_validator().design_result(design, design_id="plasmid-gold-0")
    assert result.capability == CapabilityKind.PLASMID
    assert result.design_id == "plasmid-gold-0"
    assert result.provenance
    assert result.parameters_used
    assert result.report.capability == CapabilityKind.PLASMID


def test_failure_context_stays_reachable_even_though_the_contract_has_no_field() -> None:
    record = next(
        item
        for item in _records(CURATED_BAD)
        if item["expected_failing_checks"] == ["regulatory_compatibility"]
    )
    design = PlasmidDesign(
        design_spec=DesignSpec.model_validate(record["design_spec"]),
        annotated_sequence=AnnotatedSequence.model_validate(record["annotated_sequence"]),
    )
    contexts = build_validator().failure_contexts(design)
    # Only asserts the accessor works and reports engine values, not a particular verdict.
    assert all(key in CHECK_IDS for key in contexts)


def _engine_report(checks: list[ValidationCheck], overall: str) -> EngineValidationReport:
    return EngineValidationReport(
        overall=overall, checks=checks, generated_by_model_version="phase3-validation-v1"
    )


def test_a_check_the_adapter_cannot_map_becomes_unknown_with_a_reason() -> None:
    report = PlasmidValidator().adapt(
        _engine_report(
            [ValidationCheck(name="some_future_check", status="PASS", message="all good")],
            "PASS",
        )
    )
    unmapped = next(check for check in report.checks if check.check_id == "some_future_check")
    assert unmapped.severity == Severity.UNKNOWN
    assert "no stable check id" in unmapped.message
    # The four mapped checks are missing, so they are UNKNOWN too, and the
    # report as a whole is UNKNOWN rather than a pass (rule 1).
    assert {check.severity for check in report.checks} == {Severity.UNKNOWN}
    assert report.overall == Severity.UNKNOWN


def test_a_missing_mapped_check_becomes_unknown_and_cannot_improve_a_verdict() -> None:
    report = PlasmidValidator().adapt(
        _engine_report(
            [ValidationCheck(name="restriction_site_conflicts", status="FAIL", message="conflict")],
            "FAIL",
        )
    )
    severities = {check.check_id: check.severity for check in report.checks}
    assert severities["restriction_site_conflicts"] == Severity.FAIL
    assert severities["codon_usage"] == Severity.UNKNOWN
    assert severities["repeat_and_instability"] == Severity.UNKNOWN
    assert severities["regulatory_compatibility"] == Severity.UNKNOWN
    assert report.overall == Severity.FAIL


def test_evaluated_at_can_be_pinned_so_a_report_is_reproducible() -> None:
    pinned = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _, design = CURATED_DESIGNS[0]
    assert PlasmidValidator(evaluated_at=pinned).validate(design).evaluated_at == pinned


@pytest.mark.parametrize("engine_status", sorted(SEVERITY_BY_ENGINE_STATUS))
def test_every_engine_status_maps_to_a_severity(engine_status: str) -> None:
    report = PlasmidValidator().adapt(
        _engine_report(
            [ValidationCheck(name="codon_usage", status=engine_status, message="x")],
            engine_status,
        )
    )
    codon = next(check for check in report.checks if check.check_id == "codon_usage")
    assert codon.severity.value == SEVERITY_BY_ENGINE_STATUS[engine_status]
