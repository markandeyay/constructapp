"""The section 11.1 provenance gate on the assembly and guide RNA routes.

The AAV route's gate tests live with that capability in `tests/aav/test_api.py`.
These cover the two table capabilities, whose exports are CSV and TSV rather
than sequence records.

On how the blocked path is reached. The allowed path is driven with ordinary
requests, because an ordinary request is attributable: the designers compose
primers from the fragments in the request and spacers from the target in the
request, so a correctly composed design has nothing unattributable in it. That
is the point of the architecture and it means a route level block cannot be
provoked by a request alone.

So the blocked tests strip the attribution from one span of the real subject and
let the real gate decide. The gate is not mocked and its verdict is not
simulated: the provenance assertion runs over a genuinely uncovered span and
genuinely refuses. What is injected is the condition, which is what a resolver
bug or an unregistered overhang rule would produce in production, and what is
under test is what the route does with a refusal.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from services.api.app import create_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def _entries(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _part_sequence(name):
    with open(f"data/parts/promoter/{name}.json", encoding="utf-8") as handle:
        return json.load(handle)["sequence"]


@pytest.fixture(scope="module")
def assembly_request():
    cbh = _part_sequence("cbh")
    cmv = _part_sequence("cmv")
    return {
        "strategy": "gibson",
        "fragments": [
            {
                "name": "frag_a",
                "sequence": cbh[100:250],
                "role": "insert",
                "source": "GenBank KU341333.1, CBh promoter, plus strand offset 100, 150 bp",
            },
            {
                "name": "frag_b",
                "sequence": cmv[410:590],
                "role": "insert",
                "source": "GenBank AF396260.1, CMV promoter, plus strand offset 410, 180 bp",
            },
        ],
    }


@pytest.fixture(scope="module")
def grna_request():
    with open("docs/demo_assets/grna_target_bla_pUC19.txt", encoding="utf-8") as handle:
        target = handle.read().strip()
    return {
        "target_sequence": target,
        "target_name": "PUC19_BLA",
        "nuclease": "SpCas9",
        "edit_intent": "knockout",
        "off_target_space": {"scope": "construct_only", "label": ""},
        "max_guides_returned": 10,
    }


def _strip_first_segment(module, attribute, subject_builder):
    """Return a replacement subject builder that leaves one span unattributed."""

    def build(*args, **kwargs):
        subject = subject_builder(*args, **kwargs)
        for sequence in subject.sequences:
            if sequence.segments:
                sequence.segments.clear()
                break
        return subject

    return build


class TestAssemblyExportGate:
    def test_an_attributable_design_returns_its_order_table(
        self, client, assembly_request, export_audit_path
    ):
        body = client.post("/v1/assembly/design", json=assembly_request).json()

        assert body["export_blocked"] is False
        assert body["export_block_reason"] is None
        assert body["outputs"]["order_table"]
        assert body["outputs"]["order_table_csv"]

        entries = _entries(export_audit_path)
        assert len(entries) == 1
        assert entries[0]["decision"] == "exported"
        assert entries[0]["capability"] == "assembly"
        # The audit entry has to be able to name a table format. The codecs in
        # packages/application/exports.py still refuse one, which is why the
        # auditable vocabulary is a separate constant.
        assert entries[0]["export_format"] == "csv"
        assert entries[0]["sequences"], "every primer is orderable DNA and belongs in the entry"

    def test_an_unattributable_primer_withholds_the_order_table(
        self, client, assembly_request, export_audit_path, monkeypatch
    ):
        from packages.application.screening.adapters.assembly import assembly_subject

        monkeypatch.setattr(
            "services.api.routes.assembly.assembly_subject",
            _strip_first_segment(None, None, assembly_subject),
        )

        response = client.post("/v1/assembly/design", json=assembly_request)

        # Section 11.1 blocks the export, not the design.
        assert response.status_code == 200
        body = response.json()
        assert body["export_blocked"] is True
        assert "provenance" in body["export_block_reason"]

        # Withheld in both renderings, and no placeholder row substituted:
        # section 4.3 forbids a placeholder because it gets exported as DNA.
        assert body["outputs"]["order_table"] == []
        assert body["outputs"]["order_table_csv"] == ""

        # Everything that is not orderable DNA survives, so the researcher can
        # read the report and act on the reason.
        assert body["outputs"]["report"]["checks"]
        assert body["outputs"]["protocol"]
        assert body["design"]["primers"]

        entries = _entries(export_audit_path)
        assert [entry["decision"] for entry in entries] == ["blocked"]
        assert entries[0]["blocked_reasons"]

    def test_the_csv_endpoint_refuses_rather_than_serving_an_empty_file(
        self, client, assembly_request, monkeypatch
    ):
        """That endpoint exists only to hand over the table, so a 200 would lie."""
        from packages.application.screening.adapters.assembly import assembly_subject

        monkeypatch.setattr(
            "services.api.routes.assembly.assembly_subject",
            _strip_first_segment(None, None, assembly_subject),
        )

        response = client.post("/v1/assembly/order-table.csv", json=assembly_request)

        assert response.status_code == 409
        error = response.json()["error"]
        # A specific code, so a client can tell a refusal from any other 409,
        # and the gate's own text preserved rather than replaced with a generic
        # friendly message: the researcher needs the span to act on it.
        assert error["code"] == "export_blocked"
        assert "provenance" in error["message"]
        assert error["retryable"] is False


class TestGuideRNAExportGate:
    def test_an_attributable_run_returns_both_tables(
        self, client, grna_request, export_audit_path
    ):
        body = client.post("/v1/grna/design", json=grna_request).json()

        assert body["export_blocked"] is False
        assert body["export_block_reason"] is None
        assert body["exports"]["guide_table.tsv"]
        assert body["exports"]["oligo_order_table.tsv"]

        entries = _entries(export_audit_path)
        assert len(entries) == 1
        assert entries[0]["decision"] == "exported"
        assert entries[0]["capability"] == "guide_rna"
        assert entries[0]["export_format"] == "tsv"
        # One sequence per returned spacer plus its cloning oligos, so the entry
        # records every orderable oligo and not just a count of guides.
        assert len(entries[0]["sequences"]) > len(body["result"]["guides_returned"])

    def test_an_unattributable_spacer_withholds_both_tables(
        self, client, grna_request, export_audit_path, monkeypatch
    ):
        from packages.application.screening.adapters.grna import grna_subject

        monkeypatch.setattr(
            "services.api.routes.grna.grna_subject",
            _strip_first_segment(None, None, grna_subject),
        )

        response = client.post("/v1/grna/design", json=grna_request)

        assert response.status_code == 200
        body = response.json()
        assert body["export_blocked"] is True
        assert "provenance" in body["export_block_reason"]
        assert body["exports"] == {}

        # The ranked guides and the report survive the block.
        assert body["result"]["guides_returned"]
        assert body["design_result"]["report"]["checks"]
        assert body["off_target_space_statement"]

        entries = _entries(export_audit_path)
        assert [entry["decision"] for entry in entries] == ["blocked"]
        assert entries[0]["export_format"] == "tsv"
