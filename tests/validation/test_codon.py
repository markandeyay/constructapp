from __future__ import annotations

from packages.validation.codon import run_codon_check
from tests.validation.helpers import annotated, feature, spec


def test_codon_optimized_bacterial_goi_passes() -> None:
    cds = "GCCCGCGGCCTG" * 12
    report = run_codon_check(annotated(cds, [feature("GOI", 0, len(cds), "optimized protein")]), spec())

    assert report.status == "PASS"


def test_rare_bacterial_goi_fails() -> None:
    cds = "AGGAGAAGGCTA" * 12
    report = run_codon_check(annotated(cds, [feature("GOI", 0, len(cds), "rare protein")]), spec())

    assert report.status == "FAIL"


def test_codon_check_skips_when_no_goi() -> None:
    report = run_codon_check(annotated("ATGC" * 40), spec())

    assert report.status == "PASS"
    assert "skipped" in report.message


def test_source_vector_maintenance_gois_are_skipped() -> None:
    cds = "AGGAGAAGGCTA" * 12
    seq = annotated(
        cds * 2,
        [
            feature("GOI", 0, len(cds), "rep replication protein"),
            feature("GOI", len(cds), len(cds) * 2, "lacZ alpha screening fragment"),
        ],
    )

    report = run_codon_check(seq, spec(source="genbank"))

    assert report.status == "PASS"
    assert "skipped source-vector context CDS" in report.message


def test_generated_rare_payload_still_fails_without_source_context() -> None:
    cds = "AGGAGAAGGCTA" * 12
    report = run_codon_check(annotated(cds, [feature("GOI", 0, len(cds), "replication payload")]), spec())

    assert report.status == "FAIL"


def test_source_reporter_without_reporter_intent_warns_instead_of_failing() -> None:
    cds = "TTATTATTACTA" * 12
    report = run_codon_check(
        annotated(cds, [feature("GOI", 0, len(cds), "firefly luciferase")], profile="mammalian_expression_vector"),
        spec(organism="human cells", source="genbank", vector_type="mammalian_expression_vector"),
    )

    assert report.status == "WARN"
    assert "not treated as the requested payload" in report.message


def test_source_reporter_with_reporter_intent_is_scored_as_payload() -> None:
    cds = "TTATTATTACTA" * 12
    report = run_codon_check(
        annotated(cds, [feature("GOI", 0, len(cds), "firefly luciferase")], profile="mammalian_reporter_vector"),
        spec(organism="human cells", source="genbank", vector_type="mammalian_reporter_vector", application="reporter assay"),
    )

    assert report.status == "FAIL"
