> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Phase 5 Outcome Capture Data Model

## Scope

This spec defines the first Phase 5 outcome-capture contract for `SYSTEM_DESIGN.md` Section 10.2. It covers the data that should be captured after a delivered plasmid design, how it links to the design and model version that produced it, which fields are required versus optional, and how captured outcomes become positive or negative training signals under Section 10.3.

The current application persists sessions, jobs, and designs, with generated designs stored in `designs.result` as an `AnnotatedSequence`. There is no outcome store yet. The proposed model should therefore be introduced as a new `outcomes` persistence boundary linked to `designs.id`, not as an overloaded field inside session turns or design result JSON.

## Existing System Fit

- `DesignRecord` has `design_id`, `session_id`, `job_id`, `annotated_sequence`, `created_at`, and `updated_at`.
- `ValidationReport` has `overall`, `checks`, and `generated_by_model_version`.
- Phase 2 training examples already use structured `context`, `template`, `target`, `leakage_group`, and `quality_flags` fields.
- Section 10.2 requires an `outcomes` table linked to design plus model version, with explicit user consent for training use.
- Section 10.3 says confirmed validations become positive `(context, template, target)` examples and failures become negatives for preference-style fine-tuning, while preserving provenance and consent.

## Proposed Storage Shape

Create an append-friendly `outcomes` table with structured JSONB evidence fields. The table should preserve the latest user-submitted form state, while meaningful state transitions such as consent changes can be represented either by append-only audit events or by immutable outcome revisions in a later migration.

Recommended relational columns:

| Column | Required | Type | Notes |
| --- | --- | --- | --- |
| `id` | Yes | `text primary key` | Stable outcome ID, e.g. `outcome_<uuid>`. |
| `design_id` | Yes | `text references designs(id)` | The delivered design being evaluated. |
| `session_id` | Yes | `text references sessions(id)` | Denormalized from design for access control and analytics. |
| `job_id` | Yes | `text references jobs(id)` | Denormalized from design for reproducibility. |
| `model_version` | Yes | `text` | Generation model version that produced the design. Prefer `GeneratedSequence.model_version`; fall back to `ValidationReport.generated_by_model_version` only if generation version is not separately stored. |
| `schema_version` | Yes | `text` | Start with `phase5-outcome-v1`. |
| `user_reported_validation_result` | Yes | `text enum` | User answer to "Did the construct validate?" |
| `sequencing_result` | Yes | `jsonb` | Structured sequencing confirmation status; `status` may be `not_performed` or `not_applicable`. |
| `expression_functional_result` | Yes | `jsonb` | Structured expression or functional readout; `status` may be `not_tested` or `not_applicable`. |
| `consent_for_training` | Yes | `boolean` | Explicit consent gate for any model-training or preference-training use. |
| `provenance` | Yes | `jsonb` | Reporter, channel, design/model snapshot, source of evidence, and audit metadata. |
| `submitted_at` | Yes | `timestamptz` | User submission time. |
| `created_at` | Yes | `timestamptz` | Row creation time. |
| `updated_at` | Yes | `timestamptz` | Row update time. |
| `training_signal_label` | Yes | `text enum` | Derived label: `positive`, `negative`, `inconclusive`, or `not_eligible`. |
| `training_signal_reason_codes` | Yes | `jsonb` | Deterministic reason codes used to derive the label. |
| `review_status` | Yes | `text enum` | `unreviewed`, `auto_labeled`, `needs_human_review`, `approved`, `rejected`. |

Recommended indexes:

- `(design_id)`, unique if only the latest outcome per design is allowed; non-unique if multiple clones/revisions are allowed.
- `(model_version, training_signal_label, consent_for_training, submitted_at)`.
- `(session_id, submitted_at)`.
- GIN on `sequencing_result`, `expression_functional_result`, and `provenance` for evidence queries.

## Required Fields

### Identity and Linkage

Required:

- `id`: stable outcome identifier.
- `design_id`: foreign key to `designs.id`.
- `session_id`: copied from the design.
- `job_id`: copied from the design.
- `model_version`: immutable model version used for the delivered design.
- `schema_version`: outcome schema version.

Optional:

- `account_id` or `tenant_id`: when auth is implemented.
- `project_id` or external notebook/ELN reference.
- `clone_id` or `sample_id`: user's identifier for the tested clone.
- `design_sequence_sha256`: normalized hash of the delivered design sequence.
- `delivered_validation_report_id` or embedded validation report hash.

### User-Reported Validation Result

Required field: `user_reported_validation_result`.

Allowed values:

- `validated`: user reports the construct was made and accepted for intended use.
- `failed`: user reports it did not validate.
- `partially_validated`: some checks passed, but not enough to claim success.
- `inconclusive`: user attempted validation but cannot interpret the result.
- `not_built`: design was not synthesized/cloned/tested.
- `not_reported`: form was submitted without this answer only if the UI permits partial save; final submissions should not use this.

Optional detail fields:

- `validation_summary`: short user text.
- `failure_stage`: `synthesis`, `cloning`, `transformation`, `screening`, `sequencing`, `expression`, `functional_assay`, `unknown`, or `other`.
- `number_of_clones_screened`.
- `selected_clone_strategy`.
- `known_protocol_deviation`: boolean plus note.

### Sequencing Result

Required field: `sequencing_result.status`.

Allowed `status` values:

- `match_expected`: covered bases match the delivered design or explicitly expected edited sequence.
- `mismatch`: sequence differs in a way the user considers relevant.
- `partial_match`: covered regions match, but coverage is incomplete.
- `mixed_or_low_quality`: chromatogram/read data are ambiguous, mixed, or below quality threshold.
- `not_performed`: no sequencing was performed.
- `not_applicable`: sequencing is not relevant to this outcome.
- `inconclusive`: sequencing was attempted but cannot be interpreted.

Optional fields:

- `method`: `sanger`, `amplicon_ngs`, `whole_plasmid_ngs`, `nanopore`, `external_vendor`, `other`, or `unknown`.
- `covered_regions`: array of named regions such as `insert`, `junction_5p`, `junction_3p`, `promoter`, `coding_sequence`, `barcode`, `full_plasmid`.
- `percent_identity`.
- `coverage_fraction`.
- `expected_sequence_sha256`.
- `observed_sequence_sha256`, only if the user supplies sequence data and policy permits retaining it.
- `variant_summary`: structured changes such as substitution, insertion, deletion, inversion, rearrangement, wrong insert, wrong orientation, frameshift, stop codon, or backbone discrepancy.
- `primer_names`: optional user-entered names, not primer sequences unless explicitly approved.
- `external_report_uri`: restricted object-store pointer for uploaded reports.
- `notes`.

Rationale: sequencing confirmation is realistic wet-lab outcome data. Addgene recommends diagnostic digest or sequencing for plasmid verification, and its sequence-analysis guidance emphasizes verifying important features such as inserts, fusion proteins, point mutations, and deletions with primers that flank the target region. Sanger sequencing is grounded in the chain-termination method described by Sanger, Nicklen, and Coulson in 1977.

### Restriction Digest Verification

Restriction digest is optional but should be first-class evidence because many users will screen constructs this way before sequencing.

Optional field: `restriction_digest_result`.

Allowed `status` values:

- `pattern_matches_expected`.
- `pattern_mismatch`.
- `partial_or_unclear`.
- `not_performed`.
- `not_applicable`.

Optional fields:

- `enzymes`: enzyme names only.
- `expected_band_sizes_bp`.
- `observed_band_sizes_bp`.
- `gel_image_uri`: restricted object-store pointer.
- `interpretation`: `insert_present`, `insert_absent`, `wrong_orientation`, `backbone_size_mismatch`, `unclear`, or `other`.
- `notes`.

Rationale: NEB describes analytical restriction digestion of recombinant plasmids as a fast, cost-efficient way to infer insert presence or absence, orientation, plasmid size, and some site-specific sequence information by comparing predicted and observed gel band patterns.

### Expression or Functional Result

Required field: `expression_functional_result.status`.

Allowed `status` values:

- `meets_expected_function`: expression or function was observed at a level the user accepts.
- `below_expected`.
- `absent`.
- `wrong_localization_or_product`.
- `toxic_or_growth_defect`.
- `not_tested`.
- `not_applicable`.
- `inconclusive`.

Optional fields:

- `assay_type`: `fluorescence`, `luminescence`, `western_blot`, `elisa`, `flow_cytometry`, `qpcr`, `activity_assay`, `growth_selection`, `phenotype`, `microscopy`, `other`, or `unknown`.
- `host_or_cell_line`.
- `induction_or_transfection_context`: concise structured metadata, not a protocol.
- `timepoint`.
- `replicate_count`.
- `control_used`: `positive`, `negative`, `both`, `none`, or `unknown`.
- `normalized_value`.
- `units`.
- `fold_change`.
- `threshold_used`.
- `qualitative_observation`.
- `artifact_uri`: restricted pointer for images, plate-reader exports, or blot images.
- `notes`.

Rationale: expression and function are not one measurement type. Realistic outcome data may be a reporter signal, a protein-detection assay, transcript abundance, activity, localization, growth selection, or a phenotype. Luciferase and GFP are established reporter systems for promoter/expression readouts; western blotting and qPCR are common protein and transcript readouts.

### Consent for Training

Required field: `consent_for_training`.

Required semantics:

- `true`: this outcome and its non-sensitive linked design metadata may be used to build training or preference-training examples, subject to source/license/biosecurity/privacy policy.
- `false`: this outcome must not be used for model fitting, preference optimization, or training-data snapshots. It may still be used for support, audit, product analytics, or aggregate metrics only if covered by product policy.

Optional fields:

- `consent_version`: exact UI/legal text version shown to the user.
- `consent_collected_at`.
- `consent_collected_by`: `in_app`, `email_link`, `admin_import`, or `api`.
- `consent_withdrawn_at`.
- `consent_scope`: `outcome_only`, `outcome_plus_design_metadata`, `outcome_plus_uploaded_artifacts`, or `custom`.

Training jobs must filter on `consent_for_training=true` and must preserve the consent fields in every downstream training example derived from the outcome.

### Timestamps

Required:

- `submitted_at`: when the user submitted the outcome.
- `created_at`: when the row was first persisted.
- `updated_at`: when the row was last changed.

Optional:

- `prompt_sent_at`.
- `first_opened_at`.
- `experiment_started_at`.
- `experiment_completed_at`.
- `consent_collected_at`.
- `reviewed_at`.

### Provenance

Required field: `provenance`.

Required subfields:

- `reporter_user_ref`: authenticated user ID or pseudonymous local user reference.
- `collection_channel`: `in_app`, `email`, `api`, `admin_import`, or `support_import`.
- `collection_version`: form or API version.
- `source_type`: `user_report`, `uploaded_file`, `instrument_export`, `external_eln`, or `mixed`.
- `design_snapshot`: design ID, design sequence hash, model version, job ID, session ID, and validation report hash where available.
- `captured_by_service_version`: app/API code version or git revision where available.

Optional subfields:

- `evidence_artifacts`: restricted URIs plus artifact type, checksum, and upload timestamp.
- `external_ids`: ELN IDs, LIMS sample IDs, vendor order IDs, or sequencing provider IDs.
- `reviewer_user_ref`.
- `review_notes`.
- `ip_country` or coarse audit metadata if product policy permits it; avoid storing unnecessary personal data.

## Canonical JSON Form

The API body for `POST /v1/designs/{design_id}/outcome` should map closely to this structure:

```json
{
  "schema_version": "phase5-outcome-v1",
  "model_version": "sequence-generator-v2026-06-07",
  "user_reported_validation_result": "validated",
  "sequencing_result": {
    "status": "match_expected",
    "method": "sanger",
    "covered_regions": ["insert", "junction_5p", "junction_3p"]
  },
  "restriction_digest_result": {
    "status": "pattern_matches_expected",
    "enzymes": ["EcoRI", "HindIII"]
  },
  "expression_functional_result": {
    "status": "meets_expected_function",
    "assay_type": "fluorescence",
    "host_or_cell_line": "E. coli"
  },
  "consent_for_training": true,
  "provenance": {
    "collection_channel": "in_app",
    "source_type": "user_report",
    "collection_version": "phase5-outcome-form-v1"
  }
}
```

The service should enrich this body with server-derived `design_id`, `session_id`, `job_id`, timestamps, reporter identity, design hash, model/version provenance, and derived training-signal label.

## Training-Signal Labeling

### Positive Outcome

An outcome is a positive training signal only when all of the following are true:

- `consent_for_training=true`.
- The design, model version, and delivered sequence hash are linked and reproducible.
- `user_reported_validation_result` is `validated` or, with human review, `partially_validated`.
- Sequencing evidence is compatible with the intended construct: `sequencing_result.status=match_expected`, or `partial_match` with reviewed coverage of all regions required for the design goal.
- If expression or function is relevant to the design goal, `expression_functional_result.status=meets_expected_function`.
- If expression or function is not relevant, the expression result is `not_applicable` rather than silently missing.
- Any restriction digest evidence, if supplied, is not contradictory.
- There are no unresolved biosecurity, licensing, privacy, or provenance blockers.

Positive examples should be converted into supervised `(context, template, target)` examples using the original design context/template and the delivered design sequence as target. The downstream example must carry outcome ID, consent fields, model version, design ID, evidence summary, and provenance.

### Negative Outcome

An outcome is a negative training signal only when all of the following are true:

- `consent_for_training=true`.
- The design, model version, and delivered sequence hash are linked and reproducible.
- The construct was built or tested; `not_built` is not a negative training signal.
- The failure has interpretable evidence rather than only abandonment or missing data.
- The failure reason is plausibly attributable to the generated design or its biological specification, not solely to a documented external protocol deviation.

Negative subtype labels should be preserved:

- `sequence_negative`: sequencing reveals a wrong insert, wrong orientation, frameshift, deletion, rearrangement, unexpected mutation in a critical region, or backbone discrepancy.
- `digest_negative`: diagnostic digest pattern conflicts with the expected construct.
- `expression_negative`: sequence is compatible with the intended construct, but expression or function is absent, below expected, toxic, or produces the wrong product/localization.
- `mixed_negative`: multiple failure classes are present.

Negative examples should not overwrite the original target. They should be stored as preference or contrastive records: original context/template, generated target, failure subtype, evidence summary, and reason codes. This lets later training penalize failure modes without pretending there is a known corrected sequence.

### Inconclusive or Not Eligible

Use `inconclusive` when the outcome is biologically or technically ambiguous:

- `partial_match` without enough coverage to confirm critical regions.
- `mixed_or_low_quality` sequencing.
- restriction digest `partial_or_unclear`.
- expression result `inconclusive`.
- user-reported `partially_validated` without review.

Use `not_eligible` when the outcome cannot enter training:

- `consent_for_training=false`.
- `not_built`.
- missing model version or design linkage.
- missing provenance.
- source/license/biosecurity/privacy block.
- failure is explicitly attributed to non-design protocol deviation.

Inconclusive and not-eligible outcomes can still inform product metrics, reminder flows, and human review queues, but not model training snapshots.

## Wet-Lab Evidence References

- Addgene Help Center, "How can I verify the plasmids from my Addgene kit?" states that plasmids should be verified before experiments and recommends diagnostic digest or sequencing. https://help.addgene.org/hc/en-us/articles/205432629-How-can-I-verify-the-plasmids-from-my-Addgene-kit
- Addgene, "Sequence Analysis of a Plasmid," describes sequencing verification of key plasmid features such as inserts, fusion proteins, point mutations, and deletions with suitable primers. https://www.addgene.org/protocols/sequence-analysis/
- Sanger F, Nicklen S, Coulson AR. 1977. "DNA sequencing with chain-terminating inhibitors." PNAS 74(12):5463-5467. DOI: 10.1073/pnas.74.12.5463. https://pubmed.ncbi.nlm.nih.gov/271968/
- New England Biolabs, "Restriction Enzyme Digestion," describes using analytical restriction digests and predicted band patterns to assess insert presence, orientation, plasmid size, and site-specific sequence information. https://www.neb.com/en-gb/applications/cloning-and-synthetic-biology/dna-analysis/restriction-enzyme-digestion
- de Wet JR, Wood KV, DeLuca M, Helinski DR, Subramani S. 1987. "Firefly luciferase gene: structure and expression in mammalian cells." Molecular and Cellular Biology 7(2):725-737. DOI: 10.1128/mcb.7.2.725-737.1987. https://pubmed.ncbi.nlm.nih.gov/3821727/
- Chalfie M, Tu Y, Euskirchen G, Ward W, Prasher DC. 1994. "Green fluorescent protein as a marker for gene expression." Science 263(5148):802-805. DOI: 10.1126/science.8303295. https://www.fpbase.org/reference/225/
- Towbin H, Staehelin T, Gordon J. 1979. "Electrophoretic transfer of proteins from polyacrylamide gels to nitrocellulose sheets." PNAS 76(9):4350-4354. DOI: 10.1073/pnas.76.9.4350. https://pubmed.ncbi.nlm.nih.gov/388439/
- Livak KJ, Schmittgen TD. 2001. "Analysis of relative gene expression data using real-time quantitative PCR and the 2(-Delta Delta C(T)) Method." Methods 25(4):402-408. DOI: 10.1006/meth.2001.1262. https://pubmed.ncbi.nlm.nih.gov/11846609/

## Questions For The Human

1. Should a single design allow multiple outcome rows for multiple clones, or should the first implementation keep one latest outcome per design?
2. What minimum sequencing coverage should count as `match_expected` for a positive label: full plasmid, insert plus junctions, or design-profile-specific critical regions?
3. For `partial_match`, which regions are mandatory for each vector profile before a human can approve a positive signal?
4. Should a successful restriction digest without sequencing ever create a positive training signal, or only a lower-confidence reviewed signal?
5. What assay-specific threshold should define `meets_expected_function` for fluorescence, luminescence, western blot, qPCR, growth selection, and phenotype assays?
6. How should the system treat expression failure when sequencing confirms the designed construct but the user reports weak protocol controls?
7. May uploaded chromatograms, gel images, plate-reader files, or blot images be retained for training-derived feature extraction, or only for human audit?
8. What exact consent text and consent-withdrawal retention policy should govern outcomes already included in a released training snapshot?
9. Should planned user edits after delivery be treated as the expected sequence for matching, or should they create a separate derived design ID?
10. Which biosecurity or sensitive-use outcome categories must be excluded from training even with user consent?
