"""The designer, the registry entry, the contract obligations and the endpoints.

Source: sections 4.1, 5.1, 5.2, 5.4, 7.1, 7.2, 13.3 and Appendix D of the engine
capability system design.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from packages.core.capability_registry import CAPABILITY_REGISTRY, get_capability
from packages.core.schemas.assembly import (
    AssemblyDesign,
    AssemblyRequest,
    AssemblyThresholds,
    Fragment,
    HostCodonUsageSpec,
    OverhangStandardSpec,
)
from packages.core.schemas.capability import (
    CapabilityKind,
    CapabilityValidator,
    DesignResult,
)
from packages.core.sequence import reverse_complement
from packages.generation.assembly.designer import (
    AssemblyGenerator,
    choose_binding_region,
    compose,
    host_codon_usage_from_request,
)
from packages.generation.assembly.outputs import build_outputs
from packages.validation.assembly.enzymes import find_recognition_sites, get_enzyme
from packages.validation.assembly.settings import settings_for
from packages.validation.assembly.validator import AssemblyValidator, parameters_used
from services.api.routes import CAPABILITY_ROUTERS, include_capability_routers
from tests.assembly.fixtures import (
    FRAGMENT_A,
    GOLDEN_GATE_A,
    GOLDEN_GATE_A_SOURCE,
    GOLDEN_GATE_B,
    GOLDEN_GATE_B_SOURCE,
    clean_golden_gate_request,
    clean_request,
    design_from,
)

VALIDATOR = AssemblyValidator()


# ---------------------------------------------------------------------------
# Section 7.2, the request schema
# ---------------------------------------------------------------------------


def test_the_request_schema_has_the_section_7_2_fields_and_defaults() -> None:
    """Section 7.2, field for field."""
    request = AssemblyRequest(
        strategy="gibson", fragments=[Fragment(name="f", sequence=FRAGMENT_A, source="fixture")]
    )
    assert request.target_tm_c == 60.0
    assert request.primer_conc_nm == 500.0
    assert request.monovalent_salt_mm == 50.0
    assert request.divalent_salt_mm == 1.5
    assert request.dntp_mm == 0.2
    assert request.vector_backbone is None
    assert request.enzyme is None


def test_golden_gate_requires_an_enzyme() -> None:
    """Section 7.2: "required for golden_gate"."""
    with pytest.raises(ValueError, match="requires `enzyme`"):
        AssemblyRequest(
            strategy="golden_gate", fragments=[Fragment(name="f", sequence=FRAGMENT_A, source="fixture")]
        )


def test_an_ambiguity_code_in_a_fragment_is_rejected() -> None:
    """An N has no Tm and no recognition-site semantics, so it cannot be ordered."""
    with pytest.raises(ValueError):
        Fragment(name="f", sequence="ACGTNACGT", source="fixture")


def test_a_coding_region_must_be_a_whole_number_of_codons() -> None:
    """Section 7.6 needs a reading frame, so a partial codon is refused."""
    with pytest.raises(ValueError, match="whole number of codons"):
        Fragment(name="f", sequence=FRAGMENT_A, source="fixture", coding_regions=[(0, 100)])


def test_duplicate_fragment_names_are_rejected() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        AssemblyRequest(
            strategy="gibson",
            fragments=[
                Fragment(name="f", sequence=FRAGMENT_A, source="a"),
                Fragment(name="f", sequence=GOLDEN_GATE_A, source="b"),
            ],
        )


def test_zero_salt_is_rejected_because_the_salt_correction_needs_a_logarithm() -> None:
    with pytest.raises(ValueError, match="ln"):
        AssemblyRequest(
            strategy="gibson",
            fragments=[Fragment(name="f", sequence=FRAGMENT_A, source="a")],
            monovalent_salt_mm=0.0,
        )


# ---------------------------------------------------------------------------
# The designer, section 7.1
# ---------------------------------------------------------------------------


def test_the_binding_region_length_is_chosen_to_hit_the_target_tm() -> None:
    """Deterministic exhaustive scan over the configured length window."""
    request = clean_request()
    settings = settings_for(request)
    binding, start, end = choose_binding_region(
        FRAGMENT_A, direction="forward", request=request, settings=settings
    )
    assert start == 0 and end == len(binding)
    assert settings.primer_min_length_nt <= len(binding) <= settings.primer_max_length_nt
    assert FRAGMENT_A.startswith(binding)


def test_a_reverse_primer_is_the_reverse_complement_of_the_template_three_prime_end() -> None:
    request = clean_request()
    settings = settings_for(request)
    binding, start, end = choose_binding_region(
        FRAGMENT_A, direction="reverse", request=request, settings=settings
    )
    assert end == len(FRAGMENT_A)
    assert binding == reverse_complement(FRAGMENT_A[start:end])


def test_a_template_shorter_than_the_minimum_primer_fails_loudly() -> None:
    """Section 3.3 constraint 4: never return a primer that was not designed."""
    request = clean_request()
    with pytest.raises(ValueError, match="shorter than the minimum primer length"):
        choose_binding_region("ACGTACGT", direction="forward", request=request, settings=settings_for(request))


@pytest.mark.parametrize("strategy", ["gibson", "golden_gate", "pcr_cloning"])
def test_all_three_section_7_1_strategies_compose(strategy: str) -> None:
    request = clean_golden_gate_request() if strategy == "golden_gate" else clean_request(strategy=strategy)
    design = compose(request)
    assert design.composed is True
    assert len(design.primers) == 2 * len(request.fragments)
    assert len(design.amplicons) == len(request.fragments)
    for primer in design.primers:
        assert primer.sequence == primer.tail + primer.binding


def test_a_gibson_primer_carries_the_upstream_fragment_as_a_five_prime_tail() -> None:
    design = compose(clean_request())
    for junction in design.junctions:
        downstream_forward = next(
            primer
            for primer in design.primers
            if primer.fragment == junction.right_fragment and primer.direction == "forward"
        )
        assert downstream_forward.tail == junction.sequence
        upstream = design.fragment(junction.left_fragment)
        assert upstream.sequence.endswith(junction.sequence)


def test_a_golden_gate_primer_places_the_site_spacer_and_overhang_per_appendix_d() -> None:
    """Appendix D's cut geometry: `top_cut_offset` filler nucleotides, then the overhang."""
    enzyme = get_enzyme("BsaI")
    design = compose(clean_golden_gate_request())
    for primer in design.primers:
        assert enzyme.recognition in primer.tail
        index = primer.tail.index(enzyme.recognition) + len(enzyme.recognition)
        filler = primer.tail[index : index + enzyme.top_cut_offset]
        assert len(filler) == enzyme.top_cut_offset
        if primer.direction == "forward":
            # The overhang is the fragment's own first bases, so the tail stops
            # after the filler and the join is scarless.
            assert len(primer.tail) == 1 + len(enzyme.recognition) + enzyme.top_cut_offset
        else:
            assert len(primer.tail) == 1 + len(enzyme.recognition) + enzyme.top_cut_offset + enzyme.overhang_nt


def test_a_golden_gate_primer_tail_carries_exactly_one_recognition_site() -> None:
    """The spacer and filler bases must not complete a second site."""
    enzyme = get_enzyme("BsaI")
    design = compose(clean_golden_gate_request())
    for primer in design.primers:
        assert len(find_recognition_sites(primer.tail, enzyme)) == 1, primer.name


def test_a_scarless_overhang_comes_from_the_fragment_junction() -> None:
    design = compose(clean_golden_gate_request())
    for junction in design.junctions:
        assert junction.overhang_source == "fragment_junction"
        assert junction.overhang_standard_name is None
        downstream = design.fragment(junction.right_fragment)
        assert downstream.sequence.startswith(junction.sequence)


def test_a_supplied_overhang_standard_is_used_verbatim_and_cited() -> None:
    """Appendix D: use the standard's defined overhang set and cite the standard."""
    standard = OverhangStandardSpec(
        name="test fixture standard, not a published one",
        citation="tests/assembly/test_designer_and_api.py, illustrative values only",
        overhangs=["AATG", "GCTT"],
    )
    design = compose(clean_golden_gate_request(overhang_standard=standard))
    assert [junction.sequence for junction in design.junctions] == ["AATG", "GCTT"]
    for junction in design.junctions:
        assert junction.overhang_source == "overhang_standard"
        assert junction.overhang_standard_name == standard.name
    assert any(standard.citation in entry for entry in design.provenance)


def test_a_standard_with_too_few_overhangs_fails_loudly() -> None:
    standard = OverhangStandardSpec(name="tiny", citation="a paper", overhangs=["AATG"])
    with pytest.raises(ValueError, match="defines 1 overhangs"):
        compose(clean_golden_gate_request(overhang_standard=standard))


def test_composition_is_deterministic() -> None:
    """Section 3.3 constraint 3: no randomness, no model call."""
    first = compose(clean_golden_gate_request())
    second = compose(clean_golden_gate_request())
    assert first.primers == second.primers
    assert first.junctions == second.junctions
    assert first.provenance == second.provenance


def test_the_generator_satisfies_the_section_5_2_protocol() -> None:
    generator = AssemblyGenerator()
    assert generator.kind == CapabilityKind.ASSEMBLY
    design = generator.compose(clean_request())
    assert isinstance(design, AssemblyDesign)


def test_the_validator_satisfies_the_section_5_3_protocol() -> None:
    assert isinstance(VALIDATOR, CapabilityValidator)
    assert VALIDATOR.kind == CapabilityKind.ASSEMBLY
    assert VALIDATOR.version


def test_host_codon_usage_is_built_only_when_supplied() -> None:
    assert host_codon_usage_from_request(clean_request()) is None
    spec = HostCodonUsageSpec(host="fixture host", citation="fixture", frequencies={"CTA": 1.0})
    usage = host_codon_usage_from_request(clean_request(host_codon_usage=spec))
    assert usage is not None and usage.host == "fixture host"


# ---------------------------------------------------------------------------
# Section 5.4 rules 3 and 5
# ---------------------------------------------------------------------------


def test_provenance_lists_every_fragment_and_the_tm_model() -> None:
    """Section 5.4 rule 5: no base in the output is unattributable."""
    design = compose(clean_golden_gate_request())
    joined = " ".join(design.provenance)
    for fragment in design.request.fragments:
        assert fragment.name in joined
        assert fragment.source in joined
    assert "enzyme:BsaI" in joined
    assert "Appendix D" in joined
    assert "nearest-neighbor" in joined
    assert all(entry.strip() for entry in design.provenance)


def test_parameters_used_shows_everything_the_verdict_was_measured_against() -> None:
    """Section 5.4 rule 3."""
    request = clean_golden_gate_request()
    report = VALIDATOR.validate(design_from(request))
    parameters = parameters_used(request, settings_for(request), report)
    # The thresholds themselves.
    assert parameters["primer_tm_warn_tolerance_c"] == 3.0
    assert parameters["gibson_overlap_min_tm_c"] == 48.0
    # The reaction conditions that feed every Tm in the report.
    assert parameters["primer_conc_nm"] == 500.0
    assert parameters["monovalent_salt_mm"] == 50.0
    assert parameters["sodium_equivalent_mm"] > 50.0
    assert "von Ahsen" in parameters["divalent_conversion"]
    assert "SantaLucia" in parameters["tm_model"]
    assert "binding region" in parameters["tm_measured_on"]
    # The decisions a reader cannot otherwise see.
    assert "UNKNOWN" in parameters["host_codon_usage"]
    assert "fragment junctions" in parameters["overhang_standard"]
    assert parameters["dimer_score_definition"]
    assert parameters["validator_version"] == VALIDATOR.version
    # What was and was not examined.
    assert set(parameters["checks_evaluated"]) == {check.check_id for check in report.checks}
    assert parameters["checks_not_evaluated_reason"]


def test_parameters_used_records_a_divalent_conversion_that_was_not_applied() -> None:
    """Section 3.3 constraint 4: a degradation is stated, never silent."""
    request = clean_request(divalent_salt_mm=1.5, dntp_mm=2.0)
    parameters = parameters_used(request, settings_for(request))
    assert "not applied" in parameters["divalent_conversion"]
    assert parameters["sodium_equivalent_mm"] == request.monovalent_salt_mm


def test_a_design_result_can_be_built_from_the_outputs() -> None:
    """The shared contract accepts what this capability produces (section 5.1)."""
    request = clean_golden_gate_request()
    design = compose(request)
    report = VALIDATOR.validate(design)
    result = DesignResult(
        capability=CapabilityKind.ASSEMBLY,
        design_id="assembly-test",
        report=report,
        artifacts={"order_table_csv": build_outputs(design, report).order_table_csv},
        provenance=design.provenance,
        parameters_used=parameters_used(request, settings_for(request), report),
    )
    assert result.report.overall.value in {"pass", "warn", "fail"}


# ---------------------------------------------------------------------------
# Section 13.3, the registry and the router block
# ---------------------------------------------------------------------------


def test_the_assembly_capability_is_registered_with_both_hooks() -> None:
    """Section 13.3 and the WP-09 cross-WP request: both or the gold harness is blind."""
    spec = get_capability(CapabilityKind.ASSEMBLY)
    assert spec.label == "Assembly and primers"
    validator = spec.validator_factory()
    assert validator.kind == CapabilityKind.ASSEMBLY
    assert callable(validator.validate)
    assert spec.design_model is AssemblyDesign
    assert spec.api_route == "/v1/assembly"


def test_registering_assembly_left_the_other_regions_alone() -> None:
    """A region entry must not disturb another package's."""
    assert CapabilityKind.PLASMID in CAPABILITY_REGISTRY
    assert CapabilityKind.ASSEMBLY in CAPABILITY_REGISTRY


def test_the_gold_runner_can_resolve_this_capability() -> None:
    """WP-09's runner resolves the validator through the registry; prove it reaches ours."""
    from tests.gold.runner import registry_resolver

    run = registry_resolver("assembly")
    report = run(design_from(clean_request()).model_dump(mode="json"))
    assert report.overall.value == "pass"


def test_the_router_is_registered_in_the_wp_04_region() -> None:
    entries = [include for include in CAPABILITY_ROUTERS if include.capability == "assembly"]
    assert len(entries) == 1
    assert entries[0].router == "services.api.routes.assembly:router"


# ---------------------------------------------------------------------------
# The endpoints, section 4.1
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    include_capability_routers(app)
    return TestClient(app)


def test_post_design_returns_a_complete_response(client: TestClient) -> None:
    body = clean_golden_gate_request().model_dump(mode="json")
    response = client.post("/v1/assembly/design", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["design_id"].startswith("assembly-")
    assert payload["outputs"]["report"]["overall"] == "pass"
    assert payload["outputs"]["order_table"]
    assert payload["outputs"]["order_table_csv"].startswith("Primer name,")
    assert payload["outputs"]["protocol"]["annealing_temperature_c"] > 0
    assert payload["provenance"]
    assert payload["parameters_used"]["validator_version"]


def test_post_design_is_deterministic(client: TestClient) -> None:
    body = clean_request().model_dump(mode="json")
    first = client.post("/v1/assembly/design", json=body).json()
    second = client.post("/v1/assembly/design", json=body).json()
    assert first["design_id"] == second["design_id"]
    assert first["outputs"]["order_table_csv"] == second["outputs"]["order_table_csv"]


def test_post_validate_accepts_a_design_without_primers(client: TestClient) -> None:
    body = design_from(clean_request()).model_dump(mode="json")
    response = client.post("/v1/assembly/validate", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["capability"] == "assembly"
    assert payload["overall"] == "pass"
    assert len(payload["checks"]) >= 11


def test_post_order_table_csv_returns_csv_and_text(client: TestClient) -> None:
    response = client.post("/v1/assembly/order-table.csv", json=clean_request().model_dump(mode="json"))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["filename"].endswith("-order-table.csv")
    assert payload["csv"].startswith("Primer name,")
    assert "Primer name" in payload["text"]


def test_get_checks_lists_all_nineteen_with_citations(client: TestClient) -> None:
    payload = client.get("/v1/assembly/checks").json()
    assert len(payload["checks"]) == 19
    assert all(entry["citation"] for entry in payload["checks"])
    assert set(payload["applicable_by_strategy"]) == {"gibson", "golden_gate", "pcr_cloning"}


def test_an_unsupported_enzyme_is_a_400_naming_the_alternatives(client: TestClient) -> None:
    body = clean_golden_gate_request(enzyme="EcoRI").model_dump(mode="json")
    response = client.post("/v1/assembly/design", json=body)
    assert response.status_code == 400
    assert "Appendix D" in response.json()["detail"]


def test_a_fragment_shorter_than_a_primer_is_a_400(client: TestClient) -> None:
    body = {
        "strategy": "pcr_cloning",
        "fragments": [{"name": "tiny", "sequence": "ACGTACGT", "source": "fixture", "role": "insert"}],
    }
    response = client.post("/v1/assembly/design", json=body)
    assert response.status_code == 400
    assert "shorter than the minimum primer length" in response.json()["detail"]


def test_golden_gate_without_an_enzyme_is_a_422(client: TestClient) -> None:
    body = clean_request().model_dump(mode="json")
    body["strategy"] = "golden_gate"
    response = client.post("/v1/assembly/design", json=body)
    assert response.status_code == 422


def test_a_threshold_override_reaches_the_endpoint(client: TestClient) -> None:
    """Section 3.3 constraint 2, end to end."""
    body = clean_request(thresholds=AssemblyThresholds(primer_tm_warn_tolerance_c=0.1)).model_dump(mode="json")
    payload = client.post("/v1/assembly/design", json=body).json()
    assert payload["parameters_used"]["primer_tm_warn_tolerance_c"] == 0.1
    assert payload["parameters_used"]["thresholds_overridden"] == {"primer_tm_warn_tolerance_c": 0.1}
    assert payload["outputs"]["report"]["overall"] == "warn"


def test_the_endpoints_need_no_database() -> None:
    """The validators are pure functions, as the environment note requires.

    If anything in the import graph of the route reached a database, importing it
    without one configured would fail. It does not.
    """
    import services.api.routes.assembly as module

    assert module.router is not None
    design = compose(clean_request())
    assert VALIDATOR.validate(design).overall.value == "pass"


def test_the_golden_gate_fixture_sources_are_recorded() -> None:
    """Every fixture sequence traces to a GenBank record, per section 3.3 constraint 1."""
    for source in (GOLDEN_GATE_A_SOURCE, GOLDEN_GATE_B_SOURCE):
        assert "GenBank" in source
        assert "offset" in source
    assert len(GOLDEN_GATE_A) == 180
    assert len(GOLDEN_GATE_B) == 180
