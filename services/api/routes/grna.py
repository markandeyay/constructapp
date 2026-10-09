"""Guide RNA capability endpoints (section 4.1).

Three endpoints, and all three are pure functions of their input: no database,
no model call, no network (section 3.3 constraint 3, and the operator
constraint that the validators must not need the database).

* `POST /v1/grna/design`: enumerate, score, search, validate and rank
  (sections 8.3, 8.4, 8.6, 8.7). Returns the ranked table with the per guide
  reasoning, the cloning oligos, the off-target space statement and the
  validation report, plus the section 5.1 `DesignResult`.
* `POST /v1/grna/validate`: validate one supplied guide against the nine
  section 8.5 checks and the section 8.6 off-target check.
* `GET /v1/grna/reference`: the Appendix C nuclease table, the configured
  thresholds, the registered cloning vectors, and the name, citation and
  validity domain of every score the capability reports. This is what the UI
  reads to show the scope disclosure section 10.4 requires.

Section 10.4 and section 16 obligations are met in the payload rather than left
to the UI: the off-target space statement is a top level field on the design
response, every score carries its model name and the word prediction, and the
reference endpoint states each model's validity domain.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from packages.application.screening.adapters.grna import grna_subject
from packages.core.schemas.capability import CapabilityKind
from packages.core.schemas.grna import GuideRNADesign, GuideRNARequest
from packages.generation.grna import GuideRNAGenerator, render_guide_table, render_oligo_table
from packages.validation.grna import (
    CLONING_VECTORS,
    DEFAULT_THRESHOLDS,
    MIT_CITATION,
    MIT_DOMAIN,
    MIT_MODEL_NAME,
    NUCLEASES,
    RULE_SET_1_CITATION,
    RULE_SET_1_DOMAIN,
    RULE_SET_1_NAME,
    VALIDATOR_VERSION,
    GuideRNAValidator,
    geometry_facts,
)
from services.api.routes._screening import mark_blocked, screen_export
from packages.generation.grna.azimuth import (
    RULE_SET_2_CITATION,
    RULE_SET_2_DOMAIN,
    RULE_SET_2_NAME,
)
from packages.validation.grna.ontarget import (
    HEURISTIC_CITATION,
    HEURISTIC_DOMAIN,
    HEURISTIC_NAME,
)

#: HTTP status for a request that parses but cannot be acted on. The numeric
#: literal is used rather than the framework constant, whose name differs
#: between framework versions.
UNPROCESSABLE = 422

router = APIRouter(prefix="/v1/grna", tags=["guide-rna"])


@router.post("/design", summary="Design and rank guide RNAs for a target")
def design_guides(request: GuideRNARequest) -> dict[str, Any]:
    """Run the full section 8 pipeline for one request."""
    generator = GuideRNAGenerator()
    try:
        result, design_result = generator.design_result(request)
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=UNPROCESSABLE, detail=str(error)) from error
    exports = {
        "guide_table.tsv": render_guide_table(result),
        "oligo_order_table.tsv": render_oligo_table(result),
    }
    payload = {
        "capability": CapabilityKind.GUIDE_RNA.value,
        "off_target_space_statement": result.off_target_space_statement,
        "result": result.model_dump(mode="json"),
        "design_result": design_result.model_dump(mode="json"),
        "exports": exports,
        "export_blocked": False,
        "export_block_reason": None,
    }

    # Section 11.1: screen before any export action. Every spacer is attributed
    # by locating it on the target the user supplied, and every cloning oligo by
    # its spacer plus the named vector overhang rule, so the target sequence is
    # required rather than optional: a subject built without it attributes
    # nothing and blocks. The tables are TSV, which the audit vocabulary names
    # but no codec in this build renders.
    subject = grna_subject(
        result,
        validator_version=design_result.report.validator_version,
        target_sequence=request.target_sequence,
        declared_provenance=list(result.provenance or []),
    )
    allowed, reason = screen_export(
        subject,
        exports,
        export_format="tsv",
        validation_overall=design_result.report.overall,
    )
    if not allowed:
        # The guide table and the oligo order table are what a researcher orders
        # from, so those are withheld. The ranked guides stay in `result` because
        # section 11.1 blocks the export and not the design, and the report has
        # to remain readable for the researcher to act on the reason.
        payload["exports"] = {}
        return mark_blocked(payload, reason or "export blocked by the provenance gate")
    return payload


@router.post("/validate", summary="Validate one supplied guide RNA")
def validate_guide(design: GuideRNADesign) -> dict[str, Any]:
    """Run the nine section 8.5 checks and the section 8.6 off-target check."""
    validator = GuideRNAValidator()
    try:
        report = validator.validate(design)
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=UNPROCESSABLE, detail=str(error)) from error
    return {
        "capability": CapabilityKind.GUIDE_RNA.value,
        "report": report.model_dump(mode="json"),
        "parameters_used": validator.parameters_used(design.request.nuclease),
        "unknown_checks": [check.check_id for check in report.unknown_checks],
    }


@router.get("/reference", summary="Nuclease table, thresholds, vectors and score provenance")
def reference() -> dict[str, Any]:
    """Everything the UI needs for the section 10.4 scope disclosure."""
    return {
        "validator_version": VALIDATOR_VERSION,
        "nucleases": [
            {
                "nuclease": facts.nuclease,
                "pam_motif": facts.pam_motif,
                "pam_position": facts.pam_position,
                "spacer_length_nt": facts.spacer_length_nt,
                "alternative_pams": list(facts.alternative_pams),
                "cut_description": facts.cut_description,
                "citation": facts.citation,
            }
            for facts in (geometry_facts(spec) for _, spec in sorted(NUCLEASES.items()))
        ],
        "thresholds": DEFAULT_THRESHOLDS.as_mapping(),
        # Section 10.4 asks the scope disclosure to say what was actually done.
        # A threshold value alone can be read backwards, so the two findings from
        # the WP-10 scientific review that are disclosure items rather than
        # defects are carried here, next to the numbers they are about. Both were
        # reviewed as "nothing is wrong or miscited", and both describe a reading
        # an operator would otherwise plausibly get wrong.
        "threshold_disclosures": [
            {
                "threshold": "seed_region_nt",
                "value": DEFAULT_THRESHOLDS.as_mapping().get("seed_region_nt"),
                "disclosure": (
                    "12 nt is the permissive end of the Appendix C range for the off-target "
                    "FAIL rule, not the conservative end, and the same holds for the near "
                    "match WARN. Both rules require a fully matched seed, so a LONGER seed "
                    "makes the FAIL condition harder to satisfy: with a 20 nt spacer and "
                    "seed 12 the seed covers positions 9 to 20, so a two mismatch site fails "
                    "only when both mismatches fall in positions 1 to 8, whereas seed 8 would "
                    "fail it for mismatches anywhere in positions 1 to 12. Choosing the top of "
                    "the range is defensible on the weight vector evidence, and it should not "
                    "be described as the cautious choice."
                ),
            },
            {
                "threshold": "on_target_model",
                "value": RULE_SET_1_NAME,
                "disclosure": (
                    "Two on-target models are implemented and the request chooses between them "
                    "with on_target_model. Rule Set 1 (Doench 2014) is the default: it is a "
                    "faithful implementation from a readable reference, pinned by tests. Rule "
                    "Set 2 (Doench 2016, run through the authors' Azimuth 2.0 package) is the "
                    "more widely used model today and is opt in, because Azimuth is Python 2 "
                    "with model files that only load on scikit-learn 0.17.1, so it runs in a "
                    "container built from docker/azimuth/Dockerfile. No coefficient is "
                    "transcribed in this repository. It is a generator recommendation, not a "
                    "validator check. If Docker is absent, the image is not built, or the "
                    "container errors, the guide is scored with Rule Set 1 and the score's "
                    "model name says the fallback happened; a Rule Set 1 number is never shown "
                    "as a 2016 score. Rule Set 2 returns a point estimate with no interval, "
                    "on a roughly 0 to 1 scale that is not comparable to Rule Set 1."
                ),
            },
        ],
        "cloning_vectors": [
            {
                "vector_id": vector.vector_id,
                "name": vector.name,
                "accession": vector.accession,
                "nucleases": list(vector.nucleases),
                "digest_enzyme": vector.digest_enzyme,
                "forward_overhang": vector.forward_overhang,
                "reverse_overhang": vector.reverse_overhang,
                "suffix": vector.suffix,
                "protocol_reference": vector.protocol_reference,
                "source": vector.source,
            }
            for _, vector in sorted(CLONING_VECTORS.items())
        ],
        "scores": [
            {
                "name": RULE_SET_1_NAME,
                "kind": "published_model",
                "role": "on-target activity",
                "citation": RULE_SET_1_CITATION,
                "validity_domain": RULE_SET_1_DOMAIN,
                "wording": "a prediction from a published model, not a measurement",
            },
            {
                "name": RULE_SET_2_NAME,
                "kind": "published_model",
                "role": "on-target activity, opt in via on_target_model=rule_set_2, container backed",
                "citation": RULE_SET_2_CITATION,
                "validity_domain": RULE_SET_2_DOMAIN,
                "wording": (
                    "a prediction from a published model, not a measurement; falls back to Rule "
                    "Set 1 with the fallback named in the score when the container is unavailable"
                ),
            },
            {
                "name": HEURISTIC_NAME,
                "kind": "labeled_heuristic",
                "role": "on-target fallback ranking outside the published model's domain",
                "citation": HEURISTIC_CITATION,
                "validity_domain": HEURISTIC_DOMAIN,
                "wording": "a labeled heuristic, not a published score and not a measurement",
            },
            {
                "name": MIT_MODEL_NAME,
                "kind": "published_model",
                "role": "off-target site and guide specificity",
                "citation": MIT_CITATION,
                "validity_domain": MIT_DOMAIN,
                "wording": (
                    "a prediction for sites inside the declared search space only; the search is "
                    "not genome-wide"
                ),
            },
        ],
        "off_target_scopes": [
            {
                "scope": "construct_only",
                "covers": "the delivery construct and the target sequence",
            },
            {
                "scope": "supplied_fasta",
                "covers": (
                    "the delivery construct, the target sequence and a sequence set the user "
                    "supplies"
                ),
            },
            {
                "scope": "none",
                "covers": "nothing; the off-target risk of the guide is reported as unknown",
            },
        ],
    }


__all__ = ["router", "design_guides", "validate_guide", "reference"]
