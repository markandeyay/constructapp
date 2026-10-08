"""The section 5 contract: fingerprint pin, registry wiring, determinism, provenance.

These are the gate items in section 14.1 that are about the contract rather
than about biology.
"""

from __future__ import annotations

import pytest

from packages.core.capability_registry import CAPABILITY_REGISTRY, get_capability
from packages.core.schemas.capability import (
    CapabilityKind,
    CapabilityValidator,
    Severity,
    assert_version_matches_thresholds,
)
from packages.core.schemas.grna import GuideRNADesign, GuideRNARequest
from packages.validation.grna import (
    DEFAULT_THRESHOLDS,
    THRESHOLD_FINGERPRINTS,
    VALIDATOR_VERSION,
    GuideRNAThresholds,
    build_validator,
    fingerprint_payload,
)

from .conftest import FIXED_TIME, load_grna_route_module, load_routes_module, make_request
from .test_checks import CLEAN_SPACER, clean_design, validate


class TestThresholdFingerprint:
    """Section 5.4 rule 4: a threshold cannot change without a version bump."""

    def test_the_pinned_fingerprint_matches_the_shipped_thresholds(self) -> None:
        assert_version_matches_thresholds(
            VALIDATOR_VERSION, fingerprint_payload(), THRESHOLD_FINGERPRINTS
        )

    def test_changing_a_threshold_changes_the_fingerprint(self) -> None:
        changed = fingerprint_payload(GuideRNAThresholds(spacer_gc_max=0.75))
        with pytest.raises(AssertionError, match="thresholds changed"):
            assert_version_matches_thresholds(
                VALIDATOR_VERSION, changed, THRESHOLD_FINGERPRINTS
            )

    def test_the_nuclease_geometry_is_inside_the_fingerprint(self) -> None:
        """A wrong PAM side would change every verdict, so it is pinned too."""
        payload = fingerprint_payload()
        geometry = payload["nuclease_geometry"]
        assert geometry["LbCas12a"]["pam_side"] == "five_prime"
        assert geometry["SpCas9"]["pam_side"] == "three_prime"
        assert geometry["SaCas9"]["spacer_length"] == 21


class TestThresholdValidation:
    """Section 3.3 constraint 2, with the Appendix C ranges enforced."""

    def test_the_seed_region_must_stay_inside_the_appendix_c_range(self) -> None:
        with pytest.raises(ValueError, match="Appendix C range 8 to 12"):
            GuideRNAThresholds(seed_region_nt=20)
        with pytest.raises(ValueError, match="Appendix C range 8 to 12"):
            GuideRNAThresholds(seed_region_nt=4)

    def test_the_gc_window_must_be_ordered(self) -> None:
        with pytest.raises(ValueError, match="0 <= min < max <= 1"):
            GuideRNAThresholds(spacer_gc_min=0.8, spacer_gc_max=0.4)

    def test_eight_nucleotide_seed_is_accepted(self) -> None:
        assert GuideRNAThresholds(seed_region_nt=8).seed_region_nt == 8


class TestRegistryWiring:
    """Section 13.3 and the WP-09 cross-WP request: both hooks must resolve."""

    def test_the_capability_is_registered(self) -> None:
        assert CapabilityKind.GUIDE_RNA in CAPABILITY_REGISTRY
        spec = get_capability(CapabilityKind.GUIDE_RNA)
        assert spec.label == "Guide RNA"
        assert spec.api_route == "/v1/grna"

    def test_validator_factory_returns_a_capability_validator(self) -> None:
        spec = get_capability(CapabilityKind.GUIDE_RNA)
        validator = spec.validator_factory()
        assert isinstance(validator, CapabilityValidator)
        assert validator.kind == CapabilityKind.GUIDE_RNA
        assert validator.version == VALIDATOR_VERSION

    def test_design_model_parses_a_gold_case_shaped_input(self) -> None:
        spec = get_capability(CapabilityKind.GUIDE_RNA)
        model = spec.design_model
        assert model is GuideRNADesign
        design = model.model_validate(
            {
                "request": {
                    "target_sequence": "CCAACCAACCA" + CLEAN_SPACER + "AGG" + "ACCAACCAACC",
                    "target_name": "GOLD",
                    "nuclease": "SpCas9",
                    "edit_intent": "knockout",
                    "off_target_space": {"scope": "construct_only"},
                },
                "guide": {"spacer": CLEAN_SPACER, "pam": "AGG", "strand": 1},
            }
        )
        report = spec.validator_factory().validate(design)
        assert report.capability == CapabilityKind.GUIDE_RNA
        assert len(report.checks) == 10

    def test_the_router_is_registered_in_its_own_region(self) -> None:
        routes = load_routes_module()
        entries = [
            item for item in routes.CAPABILITY_ROUTERS if item.capability == "guide_rna"
        ]
        assert len(entries) == 1
        assert entries[0].router == "services.api.routes.grna:router"
        assert entries[0].prefix == ""

    def test_the_registered_router_serves_the_three_endpoints(self) -> None:
        router = load_grna_route_module().router
        paths = {route.path for route in router.routes}
        assert "/v1/grna/design" in paths
        assert "/v1/grna/validate" in paths
        assert "/v1/grna/reference" in paths

    def test_each_region_holds_only_its_own_capability(self) -> None:
        """No package wrote outside its own delimited region (section 13.1).

        Before the Wave 2 merge this asserted that the WP-03 and WP-04 regions
        were empty, which held only while this branch was the sole capability in
        the tree. After the sequenced merge all three regions are populated by
        design, so the durable invariant is containment rather than emptiness:
        each region mentions its own capability and no other package's.
        """
        from pathlib import Path

        text = Path("packages/core/capability_registry.py").read_text(encoding="utf-8")

        def region(start: str, end: str) -> str:
            return text.split(start)[1].split(end)[0].lower()

        aav = region(
            "# ==== WP-03: AAV. Only WP-03 writes here. ====", "# ==== /WP-03 ===="
        )
        assembly = region(
            "# ==== WP-04: assembly. Only WP-04 writes here. ====", "# ==== /WP-04 ===="
        )
        guide_rna = region(
            "# ==== WP-05: guide RNA. Only WP-05 writes here. ====", "# ==== /WP-05 ===="
        )

        # Each region is the only place its own capability is registered, and no
        # region reaches into another package's territory.
        assert "guide_rna" not in aav and "assembly" not in aav
        assert "guide_rna" not in assembly and "aav" not in assembly
        assert "aav" not in guide_rna and "assembly" not in guide_rna
        assert "guide_rna" in guide_rna


class TestDeterminism:
    """Section 3.3 constraint 3."""

    def test_the_same_design_gives_the_same_report(self) -> None:
        design = clean_design()
        first = validate(design)
        second = validate(design)
        assert first.model_dump() == second.model_dump()

    def test_a_fresh_validator_gives_the_same_report(self) -> None:
        design = clean_design()
        from packages.validation.grna import GuideRNAValidator

        first = GuideRNAValidator(evaluated_at=FIXED_TIME).validate(design)
        second = GuideRNAValidator(evaluated_at=FIXED_TIME).validate(design)
        assert first.model_dump() == second.model_dump()

    def test_check_order_is_fixed(self) -> None:
        design = clean_design()
        order = [check.check_id for check in validate(design).checks]
        for _ in range(3):
            assert [check.check_id for check in validate(design).checks] == order


class TestParametersUsed:
    """Section 5.4 rule 3."""

    def test_every_threshold_is_exposed_with_the_geometry_applied(self) -> None:
        validator = build_validator()
        payload = validator.parameters_used("LbCas12a")
        for key in (
            "spacer_gc_min",
            "spacer_gc_max",
            "max_homopolymer_run",
            "u6_terminator_motif",
            "seed_region_nt",
            "off_target_max_mismatches",
            "off_target_fail_max_mismatches",
            "off_target_fail_max_seed_mismatches",
            "off_target_warn_max_mismatches",
            "off_target_max_search_bp",
            "max_self_complement_stem_nt",
            "min_hairpin_loop_nt",
            "knockout_cds_max_fraction",
            "heuristic_weights",
            "nuclease_geometry",
            "cloning_enzyme_sites",
            "validator_version",
            "nuclease_applied",
        ):
            assert key in payload, key
        assert payload["nuclease_applied"]["pam_position"] == "5' of spacer"
        assert payload["spacer_gc_min"] == DEFAULT_THRESHOLDS.spacer_gc_min

    def test_appendix_c_defaults_are_the_shipped_defaults(self) -> None:
        payload = build_validator().parameters_used()
        assert payload["spacer_gc_min"] == 0.40
        assert payload["spacer_gc_max"] == 0.70
        assert payload["max_homopolymer_run"] == 4
        assert payload["u6_terminator_motif"] == "TTTT"
        assert payload["seed_region_nt"] == 12

    def test_appendix_d_enzyme_sites_are_the_shipped_values(self) -> None:
        sites = build_validator().parameters_used()["cloning_enzyme_sites"]
        assert sites == {
            "AarI": "CACCTGC",
            "BbsI": "GAAGAC",
            "BsaI": "GGTCTC",
            "BsmBI": "CGTCTC",
            "SapI": "GCTCTTC",
        }


class TestOverallSeverity:
    """Section 5.4 rule 1, enforced by the shared helper rather than locally."""

    def test_overall_is_the_worst_evaluable_severity(self) -> None:
        report = validate(clean_design(cds_region=(0, 30)))
        severities = {
            check.severity for check in report.checks if check.severity != Severity.UNKNOWN
        }
        assert Severity.WARN in severities
        assert report.overall == Severity.WARN

    def test_a_report_always_carries_all_ten_checks(self) -> None:
        for request_kwargs in (
            {},
            {"nuclease": "SaCas9"},
            {"edit_intent": "activation"},
            {"expression_system": "t7_in_vitro"},
        ):
            design = clean_design(**request_kwargs)
            report = validate(design)
            assert len(report.checks) == 10, request_kwargs


class TestNoDatabaseOrNetworkIsNeeded:
    """The operator constraint: validators are pure functions over sequences."""

    def test_validation_runs_with_sockets_blocked(self, monkeypatch) -> None:
        import socket

        def refuse(*args: object, **kwargs: object) -> None:
            raise AssertionError("the validator must not open a socket")

        monkeypatch.setattr(socket, "socket", refuse)
        monkeypatch.setattr(socket, "create_connection", refuse)
        report = validate(clean_design())
        assert report.overall in {Severity.PASS, Severity.WARN, Severity.FAIL}


class TestRequestSchema:
    """Section 8.2, and the additive fields documented in the schema module."""

    def test_the_section_8_2_fields_alone_build_a_valid_request(self) -> None:
        request = GuideRNARequest(
            target_sequence="ACGT" * 20,
            target_name="X",
            nuclease="SpCas9",
            edit_intent="knockout",
            off_target_space={"scope": "construct_only"},  # type: ignore[arg-type]
            max_guides_returned=10,
        )
        assert request.expression_system == "u6_plasmid"
        assert request.delivery_construct_sequence is None

    def test_the_default_nuclease_is_spcas9(self) -> None:
        request = GuideRNARequest(
            target_sequence="ACGT" * 20,
            target_name="X",
            edit_intent="knockout",
            off_target_space={"scope": "none"},  # type: ignore[arg-type]
        )
        assert request.nuclease == "SpCas9"
        assert request.max_guides_returned == 10

    def test_supplied_fasta_requires_a_path(self) -> None:
        with pytest.raises(ValueError, match="requires fasta_path"):
            make_request(off_target_space={"scope": "supplied_fasta"})

    def test_a_fasta_path_on_another_scope_is_refused(self) -> None:
        with pytest.raises(ValueError, match="only meaningful for scope"):
            make_request(off_target_space={"scope": "none", "fasta_path": "x.fa"})
