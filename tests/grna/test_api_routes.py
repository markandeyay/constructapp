"""The three guide RNA endpoints.

The router is mounted on a bare application so these tests exercise the route
code without the rest of the API, and without a database (the operator
constraint, and section 3.3 constraint 3).
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from starlette.testclient import TestClient

from .conftest import TARGET, load_grna_route_module
from .test_checks import CLEAN_SPACER


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(load_grna_route_module().router)
    return TestClient(app)


def design_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "target_sequence": TARGET,
        "target_name": "API_TARGET",
        "nuclease": "SpCas9",
        "edit_intent": "knockout",
        "off_target_space": {"scope": "construct_only"},
        "max_guides_returned": 3,
    }
    payload.update(overrides)
    return payload


class TestDesignEndpoint:
    def test_a_valid_request_returns_a_ranked_table(self, client: TestClient) -> None:
        response = client.post("/v1/grna/design", json=design_payload())
        assert response.status_code == 200
        body = response.json()
        assert body["capability"] == "guide_rna"
        assert body["off_target_space_statement"].endswith(
            "This is not a genome-wide search."
        )
        guides = body["result"]["guides_returned"]
        assert 0 < len(guides) <= 3
        assert [guide["rank"] for guide in guides] == list(range(1, len(guides) + 1))

    def test_the_statement_is_a_top_level_field_not_buried(self, client: TestClient) -> None:
        body = client.post("/v1/grna/design", json=design_payload()).json()
        statement = body["off_target_space_statement"]
        assert body["result"]["off_target_space_statement"] == statement
        for guide in body["result"]["guides_returned"]:
            assert guide["off_target"]["space_statement"] == statement
        assert body["exports"]["guide_table.tsv"].startswith(statement)
        assert body["exports"]["oligo_order_table.tsv"].startswith(statement)

    def test_scope_none_says_so_in_the_payload_and_the_exports(self, client: TestClient) -> None:
        body = client.post(
            "/v1/grna/design", json=design_payload(off_target_space={"scope": "none"})
        ).json()
        assert body["off_target_space_statement"].startswith(
            "No off-target search was performed."
        )
        assert body["exports"]["guide_table.tsv"].startswith(
            "No off-target search was performed."
        )

    def test_every_score_carries_its_model_and_disclaimer(self, client: TestClient) -> None:
        body = client.post("/v1/grna/design", json=design_payload()).json()
        for guide in body["result"]["guides_returned"]:
            on_target = guide["on_target"]
            assert on_target["model_name"]
            assert on_target["model_kind"] in {"published_model", "labeled_heuristic"}
            assert on_target["citation"]
            assert on_target["validity_domain"]
            assert on_target["disclaimer"]
            off_target = guide["off_target"]
            assert off_target["specificity_model_name"]
            assert off_target["specificity_citation"]
            assert off_target["disclaimer"]

    def test_the_design_result_contract_fields_are_present(self, client: TestClient) -> None:
        body = client.post("/v1/grna/design", json=design_payload()).json()
        design_result = body["design_result"]
        assert design_result["capability"] == "guide_rna"
        assert design_result["parameters_used"]
        assert design_result["provenance"]
        assert design_result["report"]["validator_version"]

    def test_an_unknown_nuclease_is_rejected_by_the_schema(self, client: TestClient) -> None:
        response = client.post("/v1/grna/design", json=design_payload(nuclease="Cas13"))
        assert response.status_code == 422

    def test_a_non_dna_target_is_rejected_loudly(self, client: TestClient) -> None:
        response = client.post(
            "/v1/grna/design", json=design_payload(target_sequence="ACGTXYZ")
        )
        assert response.status_code == 422
        assert "DNA" in response.text or "detail" in response.text

    def test_a_missing_fasta_path_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/v1/grna/design",
            json=design_payload(off_target_space={"scope": "supplied_fasta"}),
        )
        assert response.status_code == 422


class TestValidateEndpoint:
    def test_a_valid_guide_validates(self, client: TestClient) -> None:
        target = "CCAACCAACCA" + CLEAN_SPACER + "AGG" + "ACCAACCAACCAACCAACCAACCAACCAACC"
        response = client.post(
            "/v1/grna/validate",
            json={
                "request": design_payload(target_sequence=target, cds_region=[0, 65]),
                "guide": {"spacer": CLEAN_SPACER, "pam": "AGG", "strand": 1},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["report"]["checks"]) == 10
        assert body["parameters_used"]["seed_region_nt"] == 12
        assert "grna.self_targeting" in body["unknown_checks"]

    def test_a_cas12a_guide_with_a_three_prime_pam_fails_the_pam_check(
        self, client: TestClient
    ) -> None:
        spacer = "GCACGTCAGTCAGGATCCAGTCC"
        target = "CCAGGCACCAGGCACC" + "TTTA" + spacer + "TTTC" + "AGGCACCAGGCACC"
        response = client.post(
            "/v1/grna/validate",
            json={
                "request": design_payload(
                    target_sequence=target,
                    nuclease="LbCas12a",
                    cloning_vector="pu6_lb_crrna",
                ),
                "guide": {"spacer": spacer, "pam": "TTTC", "strand": 1},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["report"]["overall"] == "fail"
        pam_check = next(
            check
            for check in body["report"]["checks"]
            if check["check_id"] == "grna.pam_valid"
        )
        assert pam_check["severity"] == "fail"
        assert "5' of the spacer" in pam_check["message"]


class TestReferenceEndpoint:
    def test_the_appendix_c_table_is_served(self, client: TestClient) -> None:
        body = client.get("/v1/grna/reference").json()
        rows = {row["nuclease"]: row for row in body["nucleases"]}
        assert rows["SpCas9"]["pam_motif"] == "NGG"
        assert rows["SpCas9"]["pam_position"] == "3' of spacer"
        assert rows["SpCas9"]["spacer_length_nt"] == 20
        assert rows["SpCas9"]["alternative_pams"] == ["NAG"]
        assert rows["SaCas9"]["pam_motif"] == "NNGRRT"
        assert rows["SaCas9"]["spacer_length_nt"] == 21
        assert rows["LbCas12a"]["pam_position"] == "5' of spacer"
        assert rows["LbCas12a"]["spacer_length_nt"] == 23
        assert rows["AsCas12a"]["pam_position"] == "5' of spacer"

    def test_the_thresholds_are_served_with_the_appendix_c_defaults(
        self, client: TestClient
    ) -> None:
        thresholds = client.get("/v1/grna/reference").json()["thresholds"]
        assert thresholds["spacer_gc_min"] == 0.40
        assert thresholds["spacer_gc_max"] == 0.70
        assert thresholds["max_homopolymer_run"] == 4
        assert thresholds["u6_terminator_motif"] == "TTTT"
        assert thresholds["seed_region_nt"] == 12

    def test_each_score_states_its_kind_domain_and_allowed_wording(
        self, client: TestClient
    ) -> None:
        scores = client.get("/v1/grna/reference").json()["scores"]
        kinds = {score["name"]: score["kind"] for score in scores}
        assert any(kind == "published_model" for kind in kinds.values())
        assert any(kind == "labeled_heuristic" for kind in kinds.values())
        for score in scores:
            assert score["citation"]
            assert score["validity_domain"]
            assert score["wording"]
            for banned in ("validated", "guaranteed"):
                assert banned not in score["wording"].lower()

    def test_the_off_target_scopes_are_described(self, client: TestClient) -> None:
        scopes = client.get("/v1/grna/reference").json()["off_target_scopes"]
        assert {item["scope"] for item in scopes} == {
            "construct_only",
            "supplied_fasta",
            "none",
        }
        none_scope = next(item for item in scopes if item["scope"] == "none")
        assert "unknown" in none_scope["covers"]

    def test_every_vector_is_served_with_its_accession(self, client: TestClient) -> None:
        vectors = client.get("/v1/grna/reference").json()["cloning_vectors"]
        assert len(vectors) >= 8
        for vector in vectors:
            assert vector["accession"].startswith("Addgene ")
            assert vector["forward_overhang"]
            assert vector["source"]


class TestThresholdDisclosures:
    """Section 10.4: the scope disclosure must say what was actually done.

    These two came out of the WP-10 scientific review as disclosure items rather
    than defects, meaning the implementation is correct and an operator reading
    only the numbers would still draw the wrong conclusion. The point of pinning
    them here is that a disclosure which drifts away from the threshold it
    describes is worse than none, because it is confidently wrong.
    """

    def test_both_disclosures_are_exposed(self, client):
        body = client.get("/v1/grna/reference").json()
        subjects = {item["threshold"] for item in body["threshold_disclosures"]}
        assert subjects == {"seed_region_nt", "on_target_model"}

    def test_the_seed_disclosure_carries_the_live_value(self, client):
        """So the text and the number cannot disagree after a threshold change."""
        body = client.get("/v1/grna/reference").json()
        seed = next(
            item
            for item in body["threshold_disclosures"]
            if item["threshold"] == "seed_region_nt"
        )
        assert seed["value"] == body["thresholds"]["seed_region_nt"]

    def test_the_premise_of_the_seed_disclosure_still_holds(self, client):
        """The disclosure says a longer seed makes the FAIL rule HARDER to satisfy.

        That is only true because the rule demands a perfectly matched seed. If
        that ever stops being so, the explanation inverts and this test is the
        thing that catches it.
        """
        body = client.get("/v1/grna/reference").json()
        assert body["thresholds"]["off_target_fail_max_seed_mismatches"] == 0

    def test_the_seed_disclosure_says_permissive_not_conservative(self, client):
        body = client.get("/v1/grna/reference").json()
        seed = next(
            item
            for item in body["threshold_disclosures"]
            if item["threshold"] == "seed_region_nt"
        )
        text = seed["disclosure"].lower()
        assert "permissive" in text
        assert "not the conservative end" in text

    def test_the_on_target_disclosure_names_the_implemented_model(self, client):
        body = client.get("/v1/grna/reference").json()
        disclosure = next(
            item
            for item in body["threshold_disclosures"]
            if item["threshold"] == "on_target_model"
        )
        published = next(
            score for score in body["scores"] if score["kind"] == "published_model"
        )
        assert disclosure["value"] == published["name"]
        assert "2016" in disclosure["disclosure"]
