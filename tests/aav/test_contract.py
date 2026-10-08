"""The section 5 contract, as the AAV capability implements it.

Covers the five section 5.4 rules, the registry wiring the gold-set runner
depends on, and the schema invariants of `packages/core/schemas/aav.py`.
"""

from __future__ import annotations

import pytest

from packages.core.capability_registry import CAPABILITY_REGISTRY, get_capability
from packages.core.schemas.aav import (
    AAVDesign,
    AAVRequest,
    AAVValidationInput,
    CassetteElement,
    CassetteElementRole,
    coerce_design,
)
from packages.core.schemas.capability import CapabilityKind, Severity, ValidationReport
from packages.generation.aav import AAVDesigner
from packages.validation.aav import AAV_VALIDATOR_VERSION, AAVValidator, build_validator

from tests.aav.support import build_design, cds_of_length, check_of, part_element


class TestRegistryWiring:
    """The gold-set runner reports cases as UNEVALUABLE unless both of these resolve."""

    def test_aav_is_registered(self):
        assert CapabilityKind.AAV in CAPABILITY_REGISTRY
        spec = get_capability(CapabilityKind.AAV)
        assert spec.label == "AAV vector"
        assert spec.api_route == "/v1/aav"

    def test_the_validator_factory_resolves_to_a_capability_validator(self):
        validator = get_capability(CapabilityKind.AAV).validator_factory()
        assert isinstance(validator, AAVValidator)
        assert validator.kind is CapabilityKind.AAV
        assert validator.version == AAV_VALIDATOR_VERSION
        assert callable(validator.validate)

    def test_the_design_model_resolves(self):
        model = get_capability(CapabilityKind.AAV).design_model
        assert model is AAVValidationInput

    def test_the_gold_runner_resolver_finds_the_capability(self):
        from tests.gold.runner import registry_resolver

        runner = registry_resolver("aav")
        report = runner(
            {
                "transgene_name": "gold resolver smoke test",
                "transgene_sequence": cds_of_length(1_200),
                "target_tissue": "ubiquitous",
            }
        )
        assert len(report.checks) == 14

    def test_the_gold_runner_can_also_take_an_explicit_cassette(self):
        from tests.gold.runner import registry_resolver

        runner = registry_resolver("aav")
        report = runner(build_design().model_dump(mode="json"))
        assert report.overall is Severity.PASS

    def test_the_router_is_registered_in_the_wp_03_region(self):
        from services.api.routes import CAPABILITY_ROUTERS, load_router

        entry = next(item for item in CAPABILITY_ROUTERS if item.capability == "aav")
        assert entry.router == "services.api.routes.aav:router"
        assert load_router(entry).prefix == "/v1/aav"


class TestRuleOneOverall:
    def test_overall_is_the_worst_non_unknown_severity(self):
        clean = AAVValidator().validate(build_design())
        assert clean.overall is Severity.PASS
        warned = AAVValidator().validate(build_design(promoter="promoter.cag", target_tissue="ubiquitous"))
        assert warned.overall is Severity.WARN
        failed = AAVValidator().validate(build_design(polya=None))
        assert failed.overall is Severity.FAIL

    def test_unknown_never_improves_a_verdict(self):
        """A missing ITR makes three checks UNKNOWN; the report still fails."""
        report = AAVValidator().validate(build_design(itr_3=None))
        unknown = {check.check_id for check in report.unknown_checks}
        assert "aav.itr_orientation" in unknown
        assert "aav.itr_internal_sites" in unknown
        assert report.overall is Severity.FAIL

    def test_unknown_never_becomes_a_pass(self):
        report = AAVValidator().validate(build_design(serotype="AAV9"))
        unknown = {check.check_id for check in report.unknown_checks}
        assert unknown == {"aav.itr_present_both", "aav.itr_orientation", "aav.itr_internal_sites"}
        assert all(check.severity is not Severity.PASS for check in report.unknown_checks)

    def test_the_contract_helper_is_used_rather_than_a_local_recomputation(self):
        """A report whose overall disagrees with its checks is rejected by the contract."""
        report = AAVValidator().validate(build_design(polya=None))
        with pytest.raises(ValueError, match="build the report with ValidationReport.from_checks"):
            ValidationReport(
                capability=CapabilityKind.AAV,
                overall=Severity.PASS,
                checks=report.checks,
                evaluated_at=report.evaluated_at,
                validator_version=report.validator_version,
            )


class TestRuleTwoActionableMessages:
    def test_every_message_says_what_to_do(self):
        designs = [
            build_design(),
            build_design(polya=None),
            build_design(itr_3=None),
            build_design(promoter="promoter.hsyn1", target_tissue="liver"),
            build_design(cds=cds_of_length(2_895), promoter="promoter.cag", target_tissue="ubiquitous"),
            build_design(serotype="AAV9"),
        ]
        actionable = (
            "no change is needed",
            "add ",
            "replace",
            "substitut",
            "remove",
            "drop",
            "move the",
            "change the",
            "trim",
            "prepend",
            "append",
            "correct the",
            "choose",
            "set ",
            "confirm",
            "verify",
            "supply",
            "keep",
            "shorten",
            "reverse complement",
            "use a registry",
            "to fix",
            "fix the",
            "break it",
            "annotate",
            "place the",
            "accept it",
            "insert the",
            "check whether",
            "and this check will evaluate",
            "is needed",
        )
        for design in designs:
            for check in AAVValidator().validate(design).checks:
                lowered = check.message.lower()
                assert any(marker in lowered for marker in actionable), (
                    f"{check.check_id} ({check.severity.value}) is not actionable: {check.message}"
                )

    def test_the_packaging_failure_names_a_specific_element_substitution(self):
        """Section 6.5: the FAIL message must carry at least one substitution from the registry."""
        design = build_design(
            cds=cds_of_length(2_895), promoter="promoter.cag", polya="polya.bgh", target_tissue="ubiquitous"
        )
        check = check_of(AAVValidator().validate(design), "aav.packaging_limit")
        assert check.severity is Severity.FAIL
        assert "promoter.efs" in check.message
        assert "bp" in check.message
        assert check.remediation


class TestRuleThreeParametersUsed:
    def test_parameters_used_is_populated(self):
        bundle = AAVDesigner().design(
            AAVRequest(
                transgene_name="parameters test",
                transgene_sequence=cds_of_length(1_200),
                target_tissue="ubiquitous",
            )
        )
        parameters = bundle.result.parameters_used
        assert parameters
        for key in (
            "ss_target_bp",
            "ss_soft_limit_bp",
            "ss_hard_limit_bp",
            "sc_target_bp",
            "min_genome_bp",
            "itr_identity_threshold",
            "max_direct_repeat_bp",
            "max_homopolymer_run",
            "kozak_consensus_motif",
            "polya_signal_motifs",
            "tissue_compatibility",
            "validator_version",
            "applied_target_bp",
            "applied_soft_limit_bp",
            "applied_hard_limit_bp",
        ):
            assert key in parameters, key

    def test_the_applied_band_reflects_the_modality(self):
        validator = AAVValidator()
        ss = validator.parameters_used(build_design())
        sc = validator.parameters_used(build_design(self_complementary=True))
        assert ss["applied_target_bp"] == 4_700
        assert sc["applied_target_bp"] == 2_400

    def test_an_override_is_visible_in_parameters_used(self):
        parameters = AAVValidator().parameters_used(build_design(packaging_limit_bp=5_000))
        assert parameters["packaging_limit_bp_override"] == 5_000
        assert parameters["applied_target_bp"] == 5_000
        assert parameters["applied_hard_limit_bp"] == 5_500

    def test_every_threshold_a_check_quoted_is_in_parameters_used(self):
        validator = AAVValidator()
        design = build_design()
        parameters = validator.parameters_used(design)
        assert parameters["max_homopolymer_run"] == 8
        assert parameters["max_direct_repeat_bp"] == 20
        assert parameters["itr_identity_threshold"] == 0.95


class TestRuleFourVersion:
    def test_the_version_is_stamped_on_every_report(self):
        assert AAVValidator().validate(build_design()).validator_version == AAV_VALIDATOR_VERSION

    def test_the_version_is_also_in_parameters_used(self):
        assert AAVValidator().parameters_used(build_design())["validator_version"] == AAV_VALIDATOR_VERSION


class TestRuleFiveProvenance:
    def test_provenance_lists_every_part(self):
        bundle = AAVDesigner().design(
            AAVRequest(
                transgene_name="provenance test",
                transgene_sequence=cds_of_length(1_200),
                target_tissue="ubiquitous",
                include_wpre=True,
            )
        )
        provenance = bundle.result.provenance
        for part_id in ("itr.aav2_itr_left", "promoter.efs", "enhancer.wpre", "polya.sv40", "itr.aav2_itr_right"):
            assert f"part:{part_id}" in provenance

    def test_the_transgene_source_is_recorded(self):
        bundle = AAVDesigner().design(
            AAVRequest(
                transgene_name="provenance test",
                transgene_sequence=cds_of_length(1_200),
                target_tissue="ubiquitous",
            )
        )
        assert "user_input:transgene_sequence" in bundle.result.provenance

    def test_a_design_that_arrives_without_provenance_gets_one_from_its_elements(self):
        design = build_design().model_copy(update={"provenance": []})
        bundle = AAVDesigner().evaluate(design)
        assert bundle.result.provenance
        assert "part:itr.aav2_itr_left" in bundle.result.provenance

    def test_an_unattributed_element_is_visible_rather_than_hidden(self):
        element = CassetteElement(
            role=CassetteElementRole.CDS, name="orphan sequence", sequence=cds_of_length(900)
        )
        design = build_design(
            elements=[
                part_element(CassetteElementRole.ITR_5, "itr.aav2_itr_left"),
                part_element(CassetteElementRole.PROMOTER, "promoter.mecp2_mini"),
                element,
                part_element(CassetteElementRole.POLYA, "polya.bgh"),
                part_element(CassetteElementRole.ITR_3, "itr.aav2_itr_right"),
            ]
        ).model_copy(update={"provenance": []})
        assert "unattributed" in AAVDesigner().evaluate(design).result.provenance

    def test_an_empty_provenance_is_rejected_by_the_contract(self):
        from packages.core.schemas.capability import DesignResult

        report = AAVValidator().validate(build_design())
        with pytest.raises(ValueError):
            DesignResult(
                capability=CapabilityKind.AAV,
                design_id="x",
                report=report,
                artifacts={},
                provenance=[],
                parameters_used={"a": 1},
            )


class TestSchemaInvariants:
    def test_the_request_reproduces_section_six_three(self):
        assert set(AAVRequest.model_fields) == {
            "transgene_name",
            "transgene_sequence",
            "target_tissue",
            "serotype",
            "self_complementary",
            "promoter_preference",
            "include_wpre",
            "polya_preference",
            "packaging_limit_bp",
        }

    def test_request_defaults_match_section_six_three(self):
        request = AAVRequest(transgene_name="x", target_tissue="liver")
        assert request.serotype == "AAV2"
        assert request.self_complementary is False
        assert request.include_wpre is True
        assert request.promoter_preference is None
        assert request.polya_preference is None
        assert request.packaging_limit_bp is None

    def test_an_unknown_target_tissue_is_rejected(self):
        with pytest.raises(ValueError):
            AAVRequest(transgene_name="x", target_tissue="pancreas")

    def test_a_non_acgt_sequence_is_rejected(self):
        with pytest.raises(ValueError, match="non-ACGT"):
            AAVRequest(transgene_name="x", target_tissue="liver", transgene_sequence="ACGTN")

    def test_an_unknown_field_is_rejected(self):
        with pytest.raises(ValueError):
            AAVRequest(transgene_name="x", target_tissue="liver", include_intron=True)

    def test_the_design_is_permissive_enough_to_hold_a_wrong_cassette(self):
        """Section 6.4 rejects a bad cassette, the schema does not."""
        design = build_design(
            elements=[
                part_element(CassetteElementRole.POLYA, "polya.bgh"),
                part_element(CassetteElementRole.PROMOTER, "promoter.efs"),
            ]
        )
        assert len(design.elements) == 2
        report = AAVValidator().validate(design)
        assert report.overall is Severity.FAIL

    def test_an_empty_element_list_is_rejected(self):
        with pytest.raises(ValueError):
            AAVDesign(transgene_name="x", target_tissue="liver", elements=[])

    def test_coordinates_are_derived_so_they_cannot_disagree(self):
        design = build_design()
        layout = design.layout()
        assert [item.length_bp for item in layout] == [element.length_bp for element in design.elements]
        assert layout[-1].end == len(design.cassette_sequence)

    def test_the_interior_span_excludes_the_itrs(self):
        design = build_design()
        start, end = design.interior_span()
        assert start == 145
        assert end == design.total_bp - 145

    def test_there_is_no_interior_without_two_itrs(self):
        assert build_design(itr_3=None).interior_span() is None


class TestCoerceDesign:
    def test_a_design_passes_through(self):
        design = build_design()
        assert coerce_design(design) is design

    def test_a_request_is_composed(self):
        request = AAVRequest(
            transgene_name="coerce test",
            transgene_sequence=cds_of_length(900),
            target_tissue="ubiquitous",
        )
        design = coerce_design(request)
        assert isinstance(design, AAVDesign)
        assert design.first_with_role(CassetteElementRole.PROMOTER) is not None

    def test_a_mapping_of_a_design_is_recognised(self):
        design = build_design()
        assert coerce_design(design.model_dump(mode="json")).total_bp == design.total_bp

    def test_a_mapping_of_a_request_is_recognised(self):
        payload = {
            "transgene_name": "coerce test",
            "transgene_sequence": cds_of_length(900),
            "target_tissue": "ubiquitous",
        }
        assert isinstance(coerce_design(payload), AAVDesign)

    def test_the_validation_input_wrapper_unwraps(self):
        design = build_design()
        wrapped = AAVValidationInput.model_validate(design.model_dump(mode="json"))
        assert wrapped.as_design().total_bp == design.total_bp

    def test_anything_else_is_a_loud_type_error(self):
        with pytest.raises(TypeError, match="must be an AAVDesign"):
            coerce_design(42)

    def test_the_validator_accepts_every_accepted_form(self):
        design = build_design()
        validator = AAVValidator()
        for candidate in (
            design,
            design.model_dump(mode="json"),
            AAVValidationInput.model_validate(design.model_dump(mode="json")),
        ):
            assert len(validator.validate(candidate).checks) == 14


class TestValidatorIsPure:
    def test_the_validator_needs_no_database(self):
        """The environment note: validators are pure functions over sequences."""
        import packages.validation.aav.checks as checks_module
        import packages.validation.aav.itr as itr_module
        import packages.validation.aav.remediation as remediation_module
        import packages.validation.aav.validator as validator_module

        source = "".join(
            open(module.__file__, encoding="utf-8").read()
            for module in (checks_module, itr_module, remediation_module, validator_module)
        )
        for forbidden in ("psycopg", "sqlalchemy", "requests", "httpx", "random.", "datetime.now"):
            assert forbidden not in source, forbidden

    def test_the_factory_takes_no_arguments(self):
        assert isinstance(build_validator(), AAVValidator)

    def test_the_validator_does_not_mutate_the_design(self):
        design = build_design()
        before = design.model_dump_json()
        AAVValidator().validate(design)
        assert design.model_dump_json() == before
