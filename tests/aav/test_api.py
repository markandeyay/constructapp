"""The `/v1/aav` endpoints.

The router is mounted on a bare FastAPI app rather than the full application,
because the AAV capability needs no database, no session store and no model
registry: composition and validation are pure functions over sequences.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.routes.aav import router

from tests.aav.support import build_design, cds_of_length


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def transgene():
    return cds_of_length(1_200)


@pytest.fixture(autouse=True)
def audit_path(tmp_path, monkeypatch):
    """Redirect the export audit log for every test in this module.

    Autouse and module wide rather than scoped to the screening tests, because
    every request to `/v1/aav/design` is a screened export and writes an entry.
    Without this the suite appends to the repository's own `data/audit` log,
    which both dirties a real operational record and makes the entry counts in
    the screening tests depend on how many other tests ran first.
    """
    path = tmp_path / "export_audit.jsonl"
    monkeypatch.setenv("CONSTRUCT_EXPORT_AUDIT_LOG", str(path))
    return path


class TestDesignEndpoint:
    def test_a_valid_request_returns_a_full_bundle(self, client, transgene):
        response = client.post(
            "/v1/aav/design",
            json={
                "transgene_name": "api test transgene",
                "transgene_sequence": transgene,
                "target_tissue": "ubiquitous",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["capability"] == "aav"
        assert body["topology"] == "linear"
        assert body["design_id"].startswith("aav-")
        assert len(body["report"]["checks"]) == 14
        assert set(body["result"]["artifacts"]) == {
            "genbank",
            "fasta",
            "length_budget",
            "linear_map_json",
        }
        assert body["result"]["parameters_used"]["applied_target_bp"] == 4_700
        assert body["result"]["provenance"]
        assert body["length_budget_text"].splitlines()[0].strip().startswith("#")

    def test_the_oversized_request_returns_a_failure_with_remediation(self, client):
        response = client.post(
            "/v1/aav/design",
            json={
                "transgene_name": "oversized api transgene",
                "transgene_sequence": cds_of_length(2_895),
                "target_tissue": "ubiquitous",
                "promoter_preference": "promoter.cag",
                "polya_preference": "polya.bgh",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["report"]["overall"] == "fail"
        assert body["remediation"]["overage_bp"] == 349
        assert body["remediation"]["plans"]
        assert body["remediation"]["entries"]
        check = next(
            item for item in body["report"]["checks"] if item["check_id"] == "aav.packaging_limit"
        )
        assert check["severity"] == "fail"
        assert "promoter.efs" in check["message"]
        assert check["remediation"]

    def test_a_missing_transgene_sequence_is_a_422_with_the_reason(self, client):
        response = client.post(
            "/v1/aav/design",
            json={"transgene_name": "no sequence", "target_tissue": "liver"},
        )
        assert response.status_code == 422
        assert "no transgene resolver is configured" in response.json()["detail"]

    def test_an_unknown_serotype_is_a_422(self, client, transgene):
        response = client.post(
            "/v1/aav/design",
            json={
                "transgene_name": "wrong serotype",
                "transgene_sequence": transgene,
                "target_tissue": "liver",
                "serotype": "AAV9",
            },
        )
        assert response.status_code == 422
        assert "no ITR reference pair is registered" in response.json()["detail"]

    def test_an_unknown_part_id_is_a_422(self, client, transgene):
        response = client.post(
            "/v1/aav/design",
            json={
                "transgene_name": "bad part",
                "transgene_sequence": transgene,
                "target_tissue": "liver",
                "promoter_preference": "promoter.not_a_part",
            },
        )
        assert response.status_code == 422

    def test_an_invalid_target_tissue_is_rejected_by_the_schema(self, client, transgene):
        response = client.post(
            "/v1/aav/design",
            json={
                "transgene_name": "bad tissue",
                "transgene_sequence": transgene,
                "target_tissue": "pancreas",
            },
        )
        assert response.status_code == 422

    def test_the_endpoint_is_deterministic(self, client, transgene):
        payload = {
            "transgene_name": "determinism",
            "transgene_sequence": transgene,
            "target_tissue": "ubiquitous",
        }
        first = client.post("/v1/aav/design", json=payload).json()
        second = client.post("/v1/aav/design", json=payload).json()
        assert first["design_id"] == second["design_id"]
        assert first["result"]["artifacts"] == second["result"]["artifacts"]
        assert [check["message"] for check in first["report"]["checks"]] == [
            check["message"] for check in second["report"]["checks"]
        ]


class TestValidateEndpoint:
    def test_a_clean_cassette_validates(self, client):
        response = client.post("/v1/aav/validate", json=build_design().model_dump(mode="json"))
        assert response.status_code == 200
        body = response.json()
        assert body["report"]["overall"] == "pass"
        assert len(body["report"]["checks"]) == 14

    def test_a_cassette_missing_a_polya_fails_on_the_right_check(self, client):
        response = client.post(
            "/v1/aav/validate", json=build_design(polya=None).model_dump(mode="json")
        )
        body = response.json()
        assert body["report"]["overall"] == "fail"
        failing = {
            check["check_id"]
            for check in body["report"]["checks"]
            if check["severity"] == "fail"
        }
        assert failing == {"aav.required_elements", "aav.polya_present_functional"}

    def test_unknown_checks_are_reported_as_unknown_not_pass(self, client):
        response = client.post(
            "/v1/aav/validate", json=build_design(serotype="AAV9").model_dump(mode="json")
        )
        body = response.json()
        unknown = {
            check["check_id"]
            for check in body["report"]["checks"]
            if check["severity"] == "unknown"
        }
        assert unknown == {
            "aav.itr_present_both",
            "aav.itr_orientation",
            "aav.itr_internal_sites",
        }

    def test_a_malformed_cassette_is_a_422(self, client):
        response = client.post("/v1/aav/validate", json={"transgene_name": "x"})
        assert response.status_code == 422


class TestPartsEndpoint:
    def test_every_registry_part_is_listed_by_category(self, client):
        response = client.get("/v1/aav/parts")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 14
        categories = body["categories"]
        assert len(categories["promoter"]) == 8
        assert len(categories["itr"]) == 2
        assert len(categories["polya"]) == 2
        assert len(categories["enhancer"]) == 1
        assert len(categories["intron"]) == 1

    def test_there_is_no_synthetic_short_polya(self, client):
        body = client.get("/v1/aav/parts").json()
        ids = {part["id"] for part in body["categories"]["polya"]}
        assert ids == {"polya.bgh", "polya.sv40"}

    def test_each_part_carries_its_length_source_and_citation(self, client):
        body = client.get("/v1/aav/parts").json()
        for parts in body["categories"].values():
            for part in parts:
                assert part["length_bp"] > 0
                assert part["source"]
                assert part["citation"]

    def test_sequences_are_not_returned(self, client):
        body = client.get("/v1/aav/parts").json()
        for parts in body["categories"].values():
            for part in parts:
                assert "sequence" not in part

    def test_the_lower_confidence_part_is_flagged_in_its_notes(self, client):
        body = client.get("/v1/aav/parts").json()
        mecp2 = next(part for part in body["categories"]["promoter"] if part["id"] == "promoter.mecp2_mini")
        assert "Lowest-confidence source" in mecp2["notes"]


class TestExportScreeningGate:
    """The section 11.1 gate on the served export path.

    The gate is not mocked here. These tests drive the real provenance
    assertion over a real composed cassette, because the thing worth testing is
    that the route releases attributable DNA and withholds unattributable DNA,
    not that a stub was called.

    Every test redirects the audit log into `tmp_path`. The log location is read
    when the log is constructed, which is once per screened export, so setting
    the environment variable is enough and the real `data/audit` log is never
    touched by the suite.
    """

    @staticmethod
    def _audit_entries(path):
        import json

        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_a_fully_attributed_design_exports_with_its_artifacts(
        self, client, transgene, audit_path
    ):
        body = client.post(
            "/v1/aav/design",
            json={
                "transgene_name": "reporter",
                "transgene_sequence": transgene,
                "target_tissue": "ubiquitous",
            },
        ).json()

        assert body["export_blocked"] is False
        assert body["export_block_reason"] is None
        # The orderable artifacts are released, not just present as empty keys.
        artifacts = body["result"]["artifacts"]
        assert artifacts["genbank"]
        assert artifacts["fasta"]

        entries = self._audit_entries(audit_path)
        assert len(entries) == 1
        assert entries[0]["decision"] == "exported"
        assert entries[0]["capability"] == "aav"
        assert entries[0]["blocked_reasons"] == []

    def test_an_unattributable_span_withholds_the_artifacts_and_says_why(
        self, client, transgene, audit_path
    ):
        design = client.post(
            "/v1/aav/design",
            json={
                "transgene_name": "reporter",
                "transgene_sequence": transgene,
                "target_tissue": "ubiquitous",
            },
        ).json()["design"]

        # A transgene resolver that returns an undeclared source token: the
        # element carries a human readable string that claims nothing about
        # where the bases came from. This is the case the adapter docstring
        # names, reached through the route rather than constructed by hand.
        for element in design["elements"]:
            if element.get("source") == "user_input:transgene_sequence":
                element["source"] = "reporter CDS"

        response = client.post("/v1/aav/validate", json=design)

        # Section 11.1 blocks the export, not the design: the researcher still
        # needs the report and the span, so this is a 200 and not an error.
        assert response.status_code == 200
        body = response.json()
        assert body["export_blocked"] is True
        assert body["result"]["artifacts"] == {}

        reason = body["export_block_reason"]
        assert "provenance" in reason
        assert f"{len(transgene):,} bp" in reason

        # The report survives the block, which is the whole point of keeping it.
        assert body["report"]["overall"]
        assert body["report"]["checks"]

        # Two entries, in order: composing the design above is itself a
        # screened export and is recorded as one, then the tampered design is
        # recorded as blocked. Asserting both keeps the setup call visible
        # rather than pretending the gate ran only once.
        entries = self._audit_entries(audit_path)
        assert [entry["decision"] for entry in entries] == ["exported", "blocked"]
        assert entries[-1]["blocked_reasons"]

    def test_a_blocked_export_is_recorded_before_it_is_refused(
        self, client, transgene, audit_path
    ):
        """Item 4 is unconditional: a refusal that leaves no record is a hole."""
        design = client.post(
            "/v1/aav/design",
            json={
                "transgene_name": "reporter",
                "transgene_sequence": transgene,
                "target_tissue": "ubiquitous",
            },
        ).json()["design"]
        for element in design["elements"]:
            if element.get("source") == "user_input:transgene_sequence":
                element["source"] = ""

        client.post("/v1/aav/validate", json=design)

        entries = self._audit_entries(audit_path)
        assert [entry["decision"] for entry in entries] == ["exported", "blocked"]
        assert entries[-1]["validator_version"]
