> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Phase 2 Rollout Policy Recommendation Memo

Status: recommendation only; not final policy approval.

Scope: rollout promotion thresholds, canary policy, and shadow payload retention for Phase 2 model/service releases. This memo is limited to rollout governance and retention recommendations.

## Executive Recommendation

Use a conservative, staged rollout that starts with shadow traffic, promotes through small canary cohorts, and requires explicit human approval before broad exposure. The default should optimize for early detection, fast rollback, and limited blast radius rather than fastest time to full rollout.

Recommended defaults:

| Area | Default Recommendation |
| --- | --- |
| Promotion thresholds | Require 24 hours of clean shadow observation, zero critical contract/safety violations, no material increase in service errors versus baseline, no new high-severity operational alarms, and human sign-off before first user-facing canary. |
| Canary policy | Use fixed waves: internal/allowlisted users, 1%, 5%, 25%, 50%, then 100%; require a bake window at each wave; automatically pause or roll back on health, error, or safety alarms. |
| Shadow payload retention | Retain raw shadow request/response payloads for 7 days, redacted/debug payloads for 30 days, and aggregate non-payload metrics plus rollout decisions for 90 days. Extend only by explicit incident/legal/privacy approval. |

## Industry Patterns Cited

The recommendations align with common patterns from MLOps, SRE, feature-flag rollout, and production model monitoring:

| Pattern | Relevant Industry Practice |
| --- | --- |
| Continuous ML delivery | Google Cloud describes MLOps as continuous delivery and automation for ML systems, with production pipelines and operational monitoring rather than one-time model shipment. Source: https://cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning |
| Symptom-oriented monitoring | Google SRE recommends focusing monitoring on latency, traffic, errors, and saturation, and keeping paging/rollback rules actionable and user-visible. Source: https://sre.google/sre-book/monitoring-distributed-systems/ |
| Feature-flag canaries | Martin Fowler describes canary release via feature flags, using a small, stable cohort such as 1% before broad release. Source: https://martinfowler.com/articles/feature-toggles.html |
| Staggered safe deployment | AWS Builders' Library recommends one-box deployments, increasing waves, bake time, and automatic rollback based on alarms to limit blast radius. Source: https://aws.amazon.com/builders-library/automating-safe-hands-off-deployments/ |
| Model monitoring | Amazon SageMaker Model Monitor captures inference inputs/outputs and monitors data quality, model quality, bias drift, and feature-attribution drift against baselines with alerts. Source: https://docs.aws.amazon.com/sagemaker/latest/dg/model-monitor.html |

## Promotion Thresholds

### Recommended Defaults

Promote a candidate from shadow to canary only when all of the following are true:

| Threshold | Default |
| --- | --- |
| Shadow observation window | At least 24 consecutive hours, including normal peak and off-peak traffic where available. |
| Critical contract/safety violations | Zero unresolved critical violations. Any critical violation resets the observation window after remediation. |
| Service error delta | Candidate error rate must not exceed baseline by more than 0.25 percentage points or 10% relative, whichever is stricter for the measured service path. |
| Invalid/empty/unparseable output delta | Candidate rate must not exceed baseline by more than 0.25 percentage points. |
| Manual override/retry/escalation delta | Candidate rate must not exceed baseline by more than 0.5 percentage points unless approved as expected behavior. |
| Alert state | No open high-severity service, safety, or data-handling alarms attributable to the candidate. |
| Monitoring coverage | Required rollout dashboards and rollback alarms are live before user-facing exposure. |
| Human approval | Product owner, engineering owner, and safety/privacy owner approve first canary exposure. |

Promote between canary waves only when all of the following are true:

| Threshold | Default |
| --- | --- |
| Bake completion | Wave-specific bake window completed. |
| Error/incident state | No active high-severity incident or unresolved rollback alarm. |
| Cohort comparison | Candidate cohort remains within the shadow-to-canary thresholds above when compared with control/baseline. |
| Complaint/support signal | No credible user-impact report attributable to the rollout. |
| Owner review | Engineering owner approves each step through 25%; broader approval required for 50% and 100%. |

### Trade-Offs

Stricter thresholds reduce user risk and produce clearer rollback decisions, but they slow promotion and may block harmless changes when traffic is sparse or noisy.

Looser thresholds move faster, but increase the chance that weak signals are ignored until the rollout has a larger blast radius.

Relative thresholds adapt across endpoints with different baseline rates, but can be misleading when the baseline is very low. Pairing relative thresholds with absolute percentage-point limits avoids promoting a candidate that doubles rare but important failures.

Human sign-off adds coordination cost, but is appropriate for early Phase 2 because ownership, acceptable risk, and privacy boundaries are still being established.

### Rationale

The defaults follow AWS's staged deployment and bake-time pattern, Fowler's feature-flag canary cohort pattern, and Google SRE's emphasis on actionable operational signals. The goal is not to prove broad model quality in this memo; it is to prevent uncontrolled promotion when operational, safety, or data-handling signals are already negative.

## Canary Policy

### Recommended Default Rollout Sequence

| Stage | Exposure | Minimum Bake | Promotion Owner |
| --- | --- | --- | --- |
| Shadow | 0% user-visible; production traffic mirrored where permitted | 24 hours | Engineering owner |
| Internal/allowlist | Named internal users or approved testers only | 4 hours or one business session | Engineering + product |
| Canary 1 | 1% stable cohort | 4 hours | Engineering owner |
| Canary 2 | 5% stable cohort | 8 hours | Engineering owner |
| Canary 3 | 25% stable cohort | 24 hours | Engineering + product |
| Canary 4 | 50% stable cohort | 24 hours | Engineering + product + safety/privacy |
| General availability | 100% | Monitor for 72 hours after completion | Engineering + product + safety/privacy |

Use stable cohort assignment, not random reassignment per request. A user or tenant placed in a canary should consistently receive the same candidate behavior during that wave unless rolled back.

### Rollback And Pause Defaults

Automatically pause promotion and roll back the current wave when any of the following occurs:

| Trigger | Default Action |
| --- | --- |
| Critical contract/safety violation | Immediate rollback and incident review before retry. |
| High-severity service alarm | Immediate rollback if attributable or if attribution is unclear during active rollout. |
| Error threshold breach | Pause; rollback unless owner determines breach is unrelated within 30 minutes. |
| Payload handling/privacy alarm | Immediate pause; rollback if candidate touched affected data path. |
| Credible user-impact report | Pause promotion; continue only after triage and owner approval. |

Freeze promotion during active incidents, late-day/weekend windows, or periods without an accountable owner available to respond. Emergency acceleration should require principal-level or equivalent approval and active human monitoring.

### Trade-Offs

Small early canaries limit blast radius but can miss rare issues. The policy compensates by using longer bake windows as exposure grows.

Stable cohorts make comparisons and debugging cleaner, but can concentrate risk if the cohort is not representative. Human owners should reserve the right to shape or exclude sensitive cohorts.

Automatic rollback improves response time, but can roll back on unrelated incidents. The recommendation intentionally favors false rollback over continued exposure during Phase 2.

### Rationale

The sequence mirrors industry patterns: Fowler's canary cohort concept, AWS's one-box and increasing-wave deployment model, and SRE-style rollback on actionable user/service symptoms. The policy keeps early blast radius small while requiring broader human agreement before 50% and 100% exposure.

## Shadow Payload Retention

### Recommended Defaults

| Data Class | Retention Default | Purpose |
| --- | --- | --- |
| Raw shadow request/response payloads | 7 days | Short-window debugging, incident triage, and candidate comparison. |
| Redacted/debug payloads | 30 days | Follow-up analysis after common sensitive fields are removed or tokenized. |
| Aggregated metrics and decision logs | 90 days | Rollout auditability, trend review, and post-incident reconstruction without raw payload exposure. |
| Incident hold | Explicit extension only | Requires named approver, reason, scope, and deletion date. |

Default collection should be opt-in by data path. Shadow capture should exclude payload classes that are not needed for rollout decisions, and should record metadata proving which retention class applies.

### Trade-Offs

Longer retention improves debugging and model-monitoring analysis, especially for slow-burning issues. It also increases privacy, security, and compliance exposure.

Shorter retention limits data risk, but can leave teams unable to reconstruct issues found after a rollout wave has advanced.

Raw payloads are the highest-value debugging artifact and the highest-risk data class. A 7-day default is long enough to cover the recommended shadow window, early canary windows, and immediate incident triage while avoiding open-ended accumulation.

Aggregates and decision logs have lower privacy risk and higher governance value, so 90 days is appropriate for rollout auditability.

### Rationale

Model monitoring systems such as SageMaker Model Monitor commonly capture inference inputs and outputs for comparison against baselines and alerting. For Phase 2, that pattern should be constrained by data minimization: keep raw payloads briefly, retain redacted/debug forms for medium-term analysis, and preserve aggregate rollout evidence longer.

## Open Human Decisions

The following require explicit human decision before this recommendation becomes policy:

| Decision | Required Owner(s) |
| --- | --- |
| Confirm which safety/contract violations are classified as critical and therefore zero-tolerance. | Engineering, safety, product |
| Confirm whether all production traffic classes are eligible for shadow mirroring. | Privacy, security, engineering |
| Approve raw shadow payload retention of 7 days or set a stricter path-specific default. | Privacy, legal/compliance, engineering |
| Decide whether tenants/users can be excluded from canaries by sensitivity, contractual obligation, or operational risk. | Product, legal/compliance, customer owner |
| Define who can approve emergency acceleration and what record must be kept. | Engineering leadership, product leadership |
| Decide whether 100% rollout requires a formal launch review or can proceed with documented owner approval. | Engineering, product, safety/privacy |
| Define the final rollback authority when product goals and safety/operational signals conflict. | Executive/product/engineering leadership |

## Non-Goals

This memo does not approve final policy, select tooling, prescribe package changes, or recommend implementation work outside rollout governance.
