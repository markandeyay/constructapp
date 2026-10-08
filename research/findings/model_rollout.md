> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Fine-Tuned Sequence Generator Rollout

## Summary

This document specifies a safe rollout path for fine-tuned sequence generators under `SYSTEM_DESIGN.md` Section 10.4: model registry versioning plus promotion through `shadow -> canary -> full`, with a terminal `retired` state for displaced models. The rollout keeps candidate output away from users until offline generation evaluation and Phase 3 validation evidence justify controlled exposure.

Current baseline context:

| Generator | Strict generation success | Novelty | Gate status |
| --- | ---: | ---: | --- |
| FakeGenerator | 0.000 | 0.000 | Not gate-eligible; template-copy baseline |
| Carbon-500M CPU spike | 0.462 | 1.000 | Not gate-eligible; pretrained plumbing spike |

These baselines are useful regression context only. They are not production promotion thresholds because the fake baseline copies templates and the Carbon-500M spike was not fine-tuned or Phase 3 gate-eligible.

## Model Registry

Every sequence-generator artifact must be registered before any online execution, including shadow execution.

Required registry fields:

- `model_id`: stable logical name, for example `sequence-generator-carbon-lora`.
- `model_version`: immutable semantic or timestamped version.
- `artifact_uri`: object-storage URI for weights, tokenizer/config, adapter files, and generation wrapper code reference.
- `code_revision`: git commit or build digest used to train and package the artifact.
- `base_model`: upstream checkpoint name, revision, license, and access route.
- `training_data_snapshot_id`: immutable snapshot id for training examples.
- `holdout_snapshot_id`: immutable held-out set id not used in training or tuning.
- `gold_set_version`: generation gold set used for offline eval.
- `phase3_validator_version`: validation engine version used in gate reports.
- `eval_report_uri`: Markdown and JSON report URIs for offline generation eval.
- `license_status`: one of `unknown`, `internal_eval_only`, `approved_for_canary`, `approved_for_production`.
- `biosecurity_review_status`: one of `not_reviewed`, `approved_for_shadow`, `approved_for_canary`, `approved_for_full`, `blocked`.
- `rollout_state`: one of `registered`, `shadow`, `canary`, `full`, `retired`, `blocked`.
- `incumbent_model_version`: model version used as comparator for the promotion decision.
- `approval_records`: human approvals with approver, timestamp, scope, and notes.

State changes must be append-only audit events. Do not mutate prior eval results or approvals in place.

## Rollout States

| State | Serves user-visible output | Purpose | Entry requirement | Exit |
| --- | --- | --- | --- | --- |
| `registered` | No | Artifact inventory and reproducibility | Complete registry record, artifact checksum, license and biosecurity status recorded | Move to `shadow` after offline eval passes minimum eligibility |
| `shadow` | No | Compare candidate against incumbent on real traffic distribution without user exposure | Human approval for shadow, offline eval at least as good as incumbent on gate metrics, no blocking license/biosecurity issue | Promote to `canary`, keep shadowing, or mark `blocked` |
| `canary` | Yes, for a small approved traffic slice | Measure real operational and validation behavior under controlled exposure | Human approval for canary, shadow metrics pass, rollback automation ready | Promote to `full`, reduce to `shadow`, or mark `blocked` |
| `full` | Yes | Default serving model | Human approval for full, canary metrics pass, no unresolved safety regressions | Stay full until superseded or rolled back |
| `retired` | No new traffic | Preserve reproducibility for old designs and audits | Superseded by a full model or removed after rollback | May be used only for historical replay/audit, not new generation |
| `blocked` | No | Quarantine unsafe, noncompliant, or regressed artifact | Automatic or human block | Requires new version and fresh approvals; do not unblock in place |

## Shadow Operation

In shadow mode, the incumbent remains the only model whose output can be returned to a user or downstream synthesis/design workflow. The candidate receives the same normalized request context as the incumbent and runs asynchronously or in a bounded side path.

Shadow execution rules:

- The served response must always come from the incumbent.
- Candidate output must be stored only in restricted evaluation logs/artifacts, never in user-visible responses, downloadable design packages, or fulfillment queues.
- Shadow failures must not fail the user request unless shared pre-processing has already failed before either model runs.
- Candidate generation must use the same `DesignSpec`, retrieval results, constraint-engine version, and policy configuration as the incumbent unless the experiment explicitly records a controlled difference.
- The comparison must re-annotate both incumbent and candidate outputs through the Phase 0 parser and validate both through the same Phase 3 engine.
- Shadow sampling should start with a conservative non-user-impacting rate, proposed default `5%` of eligible requests, then expand only after latency/cost are understood.

Required logs and metadata per shadow comparison:

- `request_id`, trace id, timestamp, environment, and rollout state.
- Tenant/user pseudonymous id or privacy-preserving bucket, if needed for debugging; no secrets or unnecessary personal data.
- `design_spec_hash` plus the canonical `DesignSpec` stored in an access-controlled evaluation record.
- Retrieval template ids, retrieval scores, corpus snapshot id, and retrieval model/index version.
- Incumbent and candidate model ids, versions, artifact checksums, decoding parameters, random seeds, prompt/context template version, and timeout settings.
- Generated sequence hashes, lengths, circularity flags, and restricted sequence payload location.
- Re-annotation parser version, recovered component summary, and feature counts.
- Phase 3 validation report id, validator version, overall status, fail/warn counts, and failed check ids.
- Novelty result, exact-copy match ids when present, parent-template identity, and edit locality metrics when available.
- Latency, memory/GPU utilization when available, token counts, retry count, timeout flag, and exception class.
- Final comparison label: `candidate_better`, `candidate_equal`, `candidate_regressed`, `inconclusive`, or `not_evaluable`, with reason codes.

## Promotion Gates

### Registered To Shadow

Minimum gate before candidate executes beside live traffic:

- Registry record is complete, artifact checksums are recorded, and the artifact can be reproduced from `training_data_snapshot_id` plus `code_revision`.
- License status is at least `internal_eval_only`; biosecurity review status is at least `approved_for_shadow`.
- Offline generation eval ran on held-out plus generation gold sets using the same report schema as current generation eval.
- Candidate has no automatic regression versus the incumbent on syntactic validity, sane length, requested-component completeness, Phase 3 constraint pass rate, strict generation success, and novelty.
- Candidate meets the formal Phase 2 gate once applicable: at least `0.700` valid, component-complete, constraint-passing generations on approved gold-set queries.
- Candidate is not worse than the current contextual baselines in a way that indicates broken plumbing; for example, it should not fall to FakeGenerator-like novelty `0.000` unless explicitly intended as a non-novel baseline.
- Human ML owner and safety/biosecurity reviewer approve shadow start.

### Shadow To Canary

Required evidence:

- Offline generation eval and Phase 3 validation metrics beat or match incumbent on the formal gate metrics, with no blocking regression on held-out or gold sets.
- Shadow comparison shows no statistically or operationally material regression in strict generation success, component completeness, Phase 3 pass rate, novelty, latency, timeout rate, or error rate.
- All candidate outputs that would have been user-visible pass the configured deterministic Phase 3 checks, or the canary policy explicitly suppresses failed outputs before serving.
- No new high-severity biosecurity, licensing, privacy, or provenance issue is observed in logs.
- Canary blast radius is configured with automatic rollback and a conservative traffic cap, proposed default `1%` of eligible generation requests for the first canary window.
- Product, ML, platform, and safety/biosecurity humans approve canary start.

### Canary To Full

Required evidence:

- Canary metrics remain at or above incumbent for strict generation success, Phase 3 pass rate, user-visible failure rate, timeout/error rate, and support/escalation signals.
- Candidate maintains novelty above incumbent and does not increase exact training/template copy matches.
- No severe validation failures are served. Any warning-class findings are understood and accepted by the human review group.
- Cost and latency remain within approved serving budgets.
- Rollback has been tested during canary or in a production-equivalent drill.
- Human product owner, ML owner, platform owner, and safety/biosecurity reviewer approve full promotion.

## Canary Metrics

Track canary against the incumbent and against shadow/offline expectations:

- `strict_generation_success_rate`.
- `phase3_constraint_pass_rate` and fail/warn counts by check id.
- `component_complete_rate` after re-annotation.
- `novel_rate` plus exact-copy/template-copy match rate.
- User-visible generation failure rate and fallback rate.
- Latency p50/p95/p99, timeout rate, model-load failures, GPU/CPU memory pressure, and cost per generation.
- Safety/biosecurity block rate and manual-review escalation rate.
- User acceptance proxy if available, for example design downloaded, regenerated, abandoned, or later outcome feedback.

Conservative proposed defaults requiring human approval:

- First canary: `1%` of eligible traffic for at least one full business cycle or `100` eligible requests, whichever is later.
- Expansion steps: `1% -> 5% -> 25% -> 50% -> 100%`, with a human checkpoint at each step.
- Automatic hold if candidate strict generation success is more than `5%` relative below incumbent or if Phase 3 pass rate is more than `2%` absolute below incumbent.

## Rollback Rules

Automatic rollback from canary or full to incumbent must occur when any of the following happens:

- Candidate serves or attempts to serve a sequence with a blocking Phase 3 validation failure that should have been suppressed.
- Safety/biosecurity policy returns a blocking finding for the model version or a served output.
- License status changes to `blocked`, `unknown`, or below the required rollout state.
- Error rate, timeout rate, or infrastructure saturation exceeds approved SLOs for the rollout window.
- Strict generation success, component completeness, or Phase 3 pass rate drops below the incumbent by the approved rollback threshold.
- Exact-copy rate materially increases, or any training/holdout leakage issue is detected.
- The model artifact, tokenizer, prompt template, retrieval index, or validator version is discovered to differ from the approved registry record.
- Human approver triggers manual rollback.

Rollback behavior:

- Route all new eligible requests to the prior full model immediately.
- Move the candidate to `blocked` if the trigger is safety, license, artifact-integrity, or served blocking validation failure; otherwise move it back to `shadow` for diagnosis.
- Preserve all logs, generated sequence artifacts, approval records, and comparison reports.
- Do not retry full/canary with the same model version after rollback. Produce a new registered version and repeat gates.

## Human Approval Checkpoints

Required human checkpoints:

- Approve artifact eligibility after registry completion, license review, and biosecurity review.
- Approve shadow start and eligible traffic scope.
- Review shadow comparison report and approve canary start.
- Approve each canary expansion step.
- Review canary report and approve full promotion.
- Approve retirement of the displaced incumbent after reproducibility requirements are met.
- Approve any threshold changes, warning-tolerance changes, or policy exceptions.

## Questions For The Human

- What exact minimum delta over incumbent is required for offline promotion: strictly greater than incumbent on every gate metric, or non-inferior on core metrics with improvement on at least one metric?
- Should strict generation success include novelty as a hard promotion gate, or should novelty remain a separate blocking metric only for exact copies and leakage?
- What approved rollback thresholds should replace the proposed defaults of `5%` relative strict-success drop and `2%` absolute Phase 3 pass-rate drop?
- What canary traffic percentages and minimum sample sizes are acceptable for this product before full promotion?
- Which warning-class Phase 3 findings, if any, may be served during canary with disclosure or internal review?
- Who are the named approver roles for product, ML, platform, legal/license, and safety/biosecurity checkpoints?
- What retention and access policy should apply to restricted candidate sequence payloads captured during shadow comparison?
- When should a retired model be kept loadable for exact historical replay versus preserved only as artifact metadata and hashes?
