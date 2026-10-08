> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Outcome-To-Training-Signal Pipeline

- Prepared: 2026-06-07
- Scope: design contract for `SYSTEM_DESIGN.md` Section 10.3 and the Phase 5 gate.
- Related artifacts: `SYSTEM_DESIGN.md` Sections 3.6, 10.2, 10.3, 10.4; `research/findings/training_data_format.md`; `research/findings/model_rollout.md`; `research/findings/finetune_config.md`; `packages/generation/training_data.py`; `packages/generation/registry.py`; `data/training/phase2/2026-06-04-010952-phase2-triplets/manifest.json`.

## Summary

Phase 5 should turn wet-lab outcomes into supervised or preference-style training records only after a strict eligibility gate. A submitted outcome is not training data by default. It becomes training signal only when the project has explicit consent, a clear validation result, a linked generator model version already present in the model registry, and retained provenance sufficient to replay the original design context, template, target, validation evidence, and consent state.

This design extends the Phase 2 triplet convention instead of replacing it. Successful outcomes become positive `(context, template, target)` examples compatible with the existing `phase2-triplet-v1` shape. Failed outcomes become negative or preference examples only when the failure is attributable enough to the design/model output to avoid teaching on noisy wet-lab or assay failures. Inconclusive outcomes are retained as product/biology telemetry but excluded from training snapshots.

## Inputs

The outcome pipeline consumes:

- Original design record: `design_id`, request text, normalized `DesignSpec`, selected template plasmid, generated target sequence, validation report, retrieval corpus snapshot, prompt/context template version, generator `model_id`, and generator `model_version`.
- Outcome capture record from Section 10.2: whether the construct validated, sequencing result, expression or functional result, submission timestamp, submitter, tenant, and explicit training-consent response.
- Optional evidence payloads: Sanger/NGS consensus sequence, alignment report, chromatogram or sequencing vendor metadata, expression assay summary, functional assay summary, controls, replicate count, and user notes.
- Model registry record from `packages/generation/registry.py`, currently keyed by immutable `model_version` and carrying `base_model`, `training_data_snapshot_id`, `hyperparameter_config`, `eval_scores`, `training_timestamp`, `license_status`, `rollout_state`, optional `artifact_uri`, `code_revision`, and metadata.
- Existing Phase 2 training data contract from `research/findings/training_data_format.md`, especially structured JSONL examples, snapshot manifests, same-split template logic, leakage grouping, provenance retention, and license exclusions.

## Inclusion Criteria

An outcome can enter a training snapshot only if all criteria pass:

| Criterion | Required decision |
| --- | --- |
| Explicit consent | The outcome record has an affirmative, timestamped consent flag for model training use. Missing, expired, withdrawn, tenant-disabled, or ambiguous consent excludes the record. |
| Clear validation result | The outcome maps to a controlled label: `positive_sequence_validated`, `positive_function_validated`, `negative_sequence_failed`, `negative_assembly_failed`, `negative_function_failed_with_controls`, or `preference_pair`. Free-text-only reports and mixed evidence without a clear label are excluded. |
| Model version exists | `model_version` resolves to exactly one record in `data/models/registry.jsonl` through `ModelRegistry.get`. Unknown, blank, duplicate, or pre-registry model versions are excluded. |
| Provenance retained | The training example retains the original design context, template id and sequence hash, generated target sequence hash, model registry version, validation report id/version, outcome evidence ids, consent record id, source design id, tenant/user pseudonymous ids where needed, and artifact locations for restricted payloads. |
| License and privacy eligibility | The original template/source data and submitted outcome are approved for the intended training use. Restricted user IP can be used only within the consented scope and access boundary. |
| Biosecurity and policy eligibility | The design and outcome are not blocked by the biosecurity or policy screening lane. Blocked records remain audit evidence, not training data. |
| Non-leaky split assignment | Outcome-derived examples are assigned by design lineage, user/tenant where required, source accession cluster, template lineage, and sequence similarity cluster before train/validation/test splitting. |

Records failing any criterion should be written to an exclusion audit with reason codes, not silently dropped.

## Outcome Labels

Use a two-layer label: `training_disposition` controls whether the row is emitted, and `outcome_label` captures the biological/product result.

Allowed `training_disposition` values:

- `positive_triplet`: emit a supervised `(context, template, target)` record.
- `negative_example`: emit a record identifying a generated design as not preferred for the context.
- `preference_pair`: emit chosen/rejected pair for preference-style fine-tuning.
- `eval_only`: retain for offline metrics and product analytics, but do not train.
- `excluded`: retain only in an exclusion audit.

Recommended `outcome_label` values:

- `sequence_validated`: sequencing confirms the generated construct or accepted corrected target within the approved identity policy.
- `function_validated`: sequencing confirms the construct and expression/functional assay meets the user-stated goal.
- `sequence_failed`: sequencing shows the generated construct was not obtained, has a disruptive mutation, or does not match the generated target beyond the approved tolerance.
- `assembly_failed`: cloning/assembly failed with enough controls to make the generated design a plausible contributor.
- `function_failed_with_controls`: sequence is correct, assay controls pass, but expression/function misses the stated goal.
- `inconclusive`: evidence is incomplete, controls are absent, results conflict, or attribution is unclear.

`inconclusive` outcomes are never used for model fitting in the first implementation.

## Positive Examples

Positive examples are emitted when the user consented and the outcome has sequence-confirmed success. If functional/expression evidence is available and clear, it strengthens metadata but should not be required for every first-pass positive because Section 10.2 asks separately about sequencing and expression outcomes.

Positive triplet construction:

```json
{
  "example_id": "phase5-outcome-v1::<outcome_id>::positive",
  "formatter_version": "phase5-outcome-v1",
  "base_example_format": "phase2-triplet-v1",
  "split": "train|validation|test",
  "training_disposition": "positive_triplet",
  "outcome_label": "sequence_validated|function_validated",
  "context": {
    "text": "Original target-scrubbed design request or normalized request rendering",
    "design_spec": {},
    "source": "original_design_request",
    "provenance": []
  },
  "template": {
    "plasmid_id": "...",
    "sequence_sha256": "...",
    "sequence_ref": "restricted://...",
    "annotated_sequence": {}
  },
  "target": {
    "sequence_sha256": "...",
    "sequence_ref": "restricted://...",
    "target_source": "generated_sequence|sequence_confirmed_observed_construct",
    "annotated_sequence": {}
  },
  "outcome": {
    "outcome_id": "...",
    "design_id": "...",
    "validation_result": "pass",
    "sequencing_result": "confirmed",
    "expression_result": "met_goal|not_measured|not_applicable",
    "evidence_refs": []
  },
  "model": {
    "model_id": "sequence-generator",
    "model_version": "...",
    "registry_path": "data/models/registry.jsonl",
    "training_data_snapshot_id": "..."
  },
  "consent": {
    "consent_record_id": "...",
    "training_use_allowed": true,
    "consented_at": "..."
  },
  "provenance": {
    "design_id": "...",
    "validation_report_id": "...",
    "validator_version": "...",
    "retrieval_snapshot_id": "...",
    "prompt_template_version": "...",
    "created_at": "..."
  },
  "quality_flags": []
}
```

Target selection rules:

- If sequencing confirms the generated sequence exactly under the approved normalization/tolerance policy, use the generated target sequence as `target`.
- If sequencing confirms a user-corrected construct that still satisfies the original design goal, emit it only if the correction is explicitly shared for training and the distinction is stored as `target_source=sequence_confirmed_observed_construct`.
- If only expression is reported but no sequence confirmation exists, do not emit a positive triplet in the first implementation.
- Do not include user, plasmid, accession, or project names in `context.text` when those names would turn the task into lookup or leak private identity. Preserve them in restricted provenance if consent and access policy allow it.

## Negative And Preference Examples

Failed outcomes are useful but high-risk because biology and wet-lab execution can fail for reasons unrelated to the generator. The default is preference-style training over direct negative supervised learning.

Emit `preference_pair` when the pipeline has a rejected generated design and a chosen sequence for the same context:

- `chosen`: a later sequence-confirmed design for the same user request, or a human-approved corrected construct.
- `rejected`: the original generated target linked to a clear failed outcome.
- Required: same or equivalent `DesignSpec`, same intended template lineage unless a human review says the design was intentionally re-scoped, and explicit consent covering both chosen and rejected sequences.

Emit `negative_example` without a chosen target only when the label is clear enough for filtering, reranking, or contrastive objectives:

- Sequencing shows a disruptive generated design defect attributable to the generated target.
- Deterministic Phase 3 validation later identifies a blocking issue in the generated construct that was missed at serving time.
- Assembly failure has controls showing the protocol and materials worked for comparable constructs and the design has a plausible failure mode.

Do not train directly on these first-pass negative cases:

- Expression failed but sequence was correct and controls are absent or weak.
- User changed organism, cell line, assay, induction conditions, copy-number expectation, payload, or success criterion after generation.
- Failure is reported only as free text such as "did not work" without sequencing or controls.
- The failed construct may involve private third-party IP or safety-sensitive material outside the consent scope.

Preference pair sketch:

```json
{
  "example_id": "phase5-outcome-v1::<outcome_id>::preference",
  "formatter_version": "phase5-outcome-v1",
  "training_disposition": "preference_pair",
  "outcome_label": "function_failed_with_controls",
  "context": {},
  "template": {},
  "chosen": {
    "sequence_sha256": "...",
    "sequence_ref": "restricted://...",
    "source": "later_sequence_validated_design|human_corrected_construct"
  },
  "rejected": {
    "sequence_sha256": "...",
    "sequence_ref": "restricted://...",
    "source": "original_generated_design",
    "failure_reason_codes": ["expression_below_goal_with_controls"]
  },
  "model": {},
  "consent": {},
  "provenance": {}
}
```

## Snapshot Layout

Use append-only raw outcome storage, then build immutable training snapshots:

```text
data/training/phase5/<snapshot_id>/positive_triplets.train.jsonl
data/training/phase5/<snapshot_id>/positive_triplets.validation.jsonl
data/training/phase5/<snapshot_id>/positive_triplets.test.jsonl
data/training/phase5/<snapshot_id>/preference_pairs.train.jsonl
data/training/phase5/<snapshot_id>/preference_pairs.validation.jsonl
data/training/phase5/<snapshot_id>/preference_pairs.test.jsonl
data/training/phase5/<snapshot_id>/negative_examples.train.jsonl
data/training/phase5/<snapshot_id>/negative_examples.validation.jsonl
data/training/phase5/<snapshot_id>/negative_examples.test.jsonl
data/training/phase5/<snapshot_id>/manifest.json
data/training/phase5/<snapshot_id>/stats.md
data/training/phase5/<snapshot_id>/exclusions.jsonl
```

The manifest should include:

- `formatter_version=phase5-outcome-v1`.
- Input outcome capture snapshot id.
- Base Phase 2 training snapshot ids, if merged with synthetic/public triplets.
- Model registry path and registry digest.
- Allowed model versions and rollout states included.
- Consent policy version and exclusion counts by consent reason.
- Validation label policy version.
- Leakage grouping policy and split seed.
- Counts by disposition, label, model version, source template profile, validator version, and evidence type.
- Restricted payload storage policy and hash algorithm.

This mirrors the Phase 2 snapshot convention in `data/training/phase2/2026-06-04-010952-phase2-triplets/manifest.json`, while separating positives, negatives, and preference pairs so training jobs can opt into each objective intentionally.

## Pipeline

1. Capture outcome through the Section 10.2 form and store the immutable raw record linked to `design_id` and `model_version`.
2. Resolve `model_version` against `ModelRegistry.get`. Exclude unresolved model versions before label generation.
3. Load original design context, template, generated target, validation report, retrieval metadata, and consent record.
4. Verify consent, license, privacy, and biosecurity eligibility.
5. Normalize sequencing and expression/functional evidence into controlled fields. Preserve raw evidence by reference, not by copying large/private files into public markdown.
6. Assign `training_disposition` and `outcome_label`.
7. Build leakage groups before splitting. Include tenant/user bucket where needed, design lineage, model version, template lineage, source accession cluster, exact sequence hash, and near-duplicate sequence cluster.
8. Render positive triplets, preference pairs, and negative examples into separate JSONL files.
9. Write manifest, stats, and exclusions.
10. Scheduled fine-tuning consumes only approved snapshot files and records the Phase 5 snapshot id in the next model registry record.
11. Candidate models follow the existing rollout path in `research/findings/model_rollout.md`: offline eval, shadow, canary, full, with regressions blocking promotion.

## Evaluation And Rollout Use

Outcome-derived records should be split into two uses:

- Training inputs: consented train split records only.
- Evaluation inputs: frozen validation/test outcome records used for offline generation evaluation, preference-model evaluation, and regression checks.

Validation/test outcomes must not be used for prompt tuning, threshold tuning, adapter training, retrieval-template selection, or manual cherry-picking. Once a Phase 5 snapshot feeds a model, the model registry record must include that snapshot id in `training_data_snapshot_id` or a metadata field such as `phase5_outcome_snapshot_id`. Promotion remains governed by `SYSTEM_DESIGN.md` Section 10.4 and `research/findings/model_rollout.md`.

## Exclusion Reason Codes

Minimum exclusion codes:

- `missing_training_consent`
- `consent_withdrawn`
- `tenant_training_disabled`
- `ambiguous_validation_result`
- `free_text_only_outcome`
- `missing_sequence_confirmation_for_positive`
- `weak_controls_for_negative`
- `model_version_not_registered`
- `registry_duplicate_or_invalid`
- `missing_original_design`
- `missing_template_or_target`
- `provenance_incomplete`
- `license_not_trainable`
- `privacy_scope_blocked`
- `biosecurity_blocked`
- `leakage_policy_blocked`
- `restricted_payload_unavailable`

## Open Biology And Product Questions

- What is the minimum sequencing evidence for `sequence_validated`: full-plasmid NGS consensus, full Sanger tiling, insert-only Sanger, or provider QC certificate?
- What identity threshold is acceptable for calling a sequence "confirmed" when there are silent mutations, circular rotations, primer-trimmed ends, ambiguous bases, or nonfunctional backbone differences?
- Does "validated" mean sequence-correct only, functionally successful only, or a two-level label that separates sequence validation from expression/function?
- Which expression or functional assay thresholds count as meeting the original goal, especially when the original prompt used qualitative wording like "high expression" or "strong reporter"?
- When expression fails with a sequence-correct construct, what controls are required before treating the generated design as a negative rather than an assay/protocol failure?
- Can user-corrected constructs become `chosen` preference examples, or does that require a separate IP assignment or contributor agreement beyond the training consent checkbox?
- Should tenant/user lineage be part of leakage grouping for all outcome snapshots, or only for enterprise/private deployments?
- Which rollout states are allowed to contribute outcomes: `shadow` outputs should not be user-visible, while `canary` and `full` outputs may have real wet-lab outcomes. Should manually exported `registered` or `blocked` designs ever be eligible?
- Should outcomes from models later marked `blocked` be excluded automatically, or retained as negative/preference evidence with safety review?
- How should the product handle consent withdrawal after a snapshot has already trained a model: future exclusion only, model retirement, or best-effort unlearning policy?

## Source Notes

- `SYSTEM_DESIGN.md` Section 10.3 defines the core requirement: confirmed validations become positive `(context, template, target)` examples, failures become negatives for preference-style fine-tuning, and provenance plus consent flags must be maintained.
- `SYSTEM_DESIGN.md` Section 3.6 defines the Phase 5 gate: a captured outcome flows into scheduled fine-tuning, the new model is evaluated offline, and promotion happens only if it beats the incumbent.
- `packages/generation/training_data.py` and `research/findings/training_data_format.md` establish the existing structured JSONL triplet convention, target identity scrubbing, same-split template selection, leakage grouping, and snapshot manifest pattern.
- `packages/generation/registry.py` implements append-only JSONL model records keyed by `model_version`; unresolved model versions therefore cannot support reproducible outcome attribution.
- `research/findings/model_rollout.md` specifies registry completion, offline evaluation, shadow/canary/full promotion, rollback, and user acceptance/outcome feedback as rollout signals.
- `research/findings/data_sources.md` and `research/findings/corpus_expansion_phase2.md` require source-level training eligibility, license status, and provenance retention before records enter training datasets.
