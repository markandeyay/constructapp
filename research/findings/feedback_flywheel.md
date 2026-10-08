> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Phase 5 Feedback Flywheel Integration

## Summary

Phase 5 now has the first auditable loop foundation:

1. A generated design is persisted in the application `designs` store.
2. A user submits a wet-lab `OutcomeReport` for that design through the API.
3. The outcome is stored with the design ID, user ID, model version, explicit training consent, outcome label, timestamps, and provenance.
4. `make derive-training-signal` scans underived outcomes, applies the training inclusion policy from `research/findings/outcome_training_signal.md`, and writes a versioned Phase 5 training snapshot under `data/training/phase5/`.
5. A later fine-tuned model is registered through `packages/generation/registry.py` with `training_data_snapshot_id` set to the Phase 5 snapshot ID, and optional metadata linking the model record to the contributing outcome IDs.

This is intentionally append-oriented. Raw outcomes remain the audit source. Derived training snapshots are immutable artifacts.

## Registry Linkage

The model registry already requires `training_data_snapshot_id`. For outcome-derived fine-tunes, that field should be the Phase 5 snapshot ID, for example:

```text
outcomes_2026-06-07-120000
```

The registry `metadata` field should include:

- `phase5_manifest_path`
- `derived_outcome_ids`
- `positive_count`
- `negative_count`
- `exclusion_count`
- `consent_policy_version`
- `outcome_schema_version`

This creates the chain:

```text
model registry record
  -> training_data_snapshot_id
  -> data/training/phase5/<snapshot>_manifest.json
  -> derived_outcome_ids
  -> outcomes table rows
  -> designs table rows
  -> original session/job/model provenance
```

## Current Implementation

Implemented pieces:

- `OutcomeReport` schema in `packages/core/schemas`.
- `outcomes` table migration in `infra/migrations/versions/0002_create_outcomes.py`.
- `InMemoryOutcomeStore` and `PostgresOutcomeStore` in `packages/application/outcomes.py`.
- Outcome API endpoints:
  - `POST /v1/designs/{design_id}/outcome`
  - `GET /v1/designs/{design_id}/outcome`
  - `GET /v1/users/me/pending-outcome-prompts`
- Phase 5 signal derivation job:
  - `packages/feedback/training_signal.py`
  - `make derive-training-signal`

## Deliberate Limits

The first implementation does not send email, schedule background jobs, or run fine-tuning automatically. It also does not promote models. Those later steps depend on the unresolved rollout decisions documented in `research/findings/model_rollout.md` and the OpenCode recommendation memo `research/findings/phase2_rollout_policy.md`.

Training inclusion is conservative:

- No consent, no training.
- Unknown model version, no training.
- Ambiguous outcome, no training.
- Positive examples require a clear positive outcome.
- Negative examples require a clear negative outcome.

## Next Steps

- Add a real auth/session ownership layer instead of the temporary `X-User-ID` scaffold.
- Add append-only consent revision/audit events.
- Connect pending outcome prompts to the frontend.
- Add scheduled execution for `derive-training-signal`.
- Register the first outcome-derived model with `training_data_snapshot_id` pointing to a Phase 5 snapshot once such a model is trained.
