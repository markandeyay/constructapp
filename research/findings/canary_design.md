> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Generation Canary Deployment Design

- Date: 2026-06-10
- Scope: generation-layer canary routing after shadow evaluation, before full production promotion.
- Status: implementation scaffold approved for fake-backed testing only; production thresholds and rollout policy still require human approval.

## Purpose

Shadow mode compares incumbent and candidate outputs without serving the candidate. Canary mode serves a candidate model to a small, controlled slice of eligible traffic. The canary mechanism must make model assignment auditable, preserve fallback to the incumbent, capture metrics, and automatically stop candidate serving when hard rollback conditions occur.

## Routing Model

Canary routing happens inside the generation layer after request normalization and retrieval, and before calling `SequenceGenerator.generate(...)`.

The router receives:

- normalized `DesignSpec`;
- retrieved templates;
- incumbent and candidate generators;
- a `CanaryPolicy`;
- request metadata such as `request_id`, `session_id`, user or tenant bucket, and timestamp when available.

Only one candidate should be actively canaried at a time unless a future human-approved multi-arm experiment explicitly changes that rule.

## Assignment Policy

Default recommendation: sticky-by-session assignment.

Stable assignment keys should be chosen in this order:

1. `design_session_id`;
2. pseudonymous user id;
3. pseudonymous tenant id;
4. request id only when no stable identity exists.

Sticky session assignment avoids a user seeing different generator behavior across regenerate/export steps within the same design workflow and keeps wet-lab outcome attribution clear.

Assignment uses deterministic hashing:

```text
bucket = hash(policy_id, assignment_key, assignment_salt) % 10000
candidate if bucket < traffic_percent * 100
```

This gives 0.01% granularity and makes assignments reproducible without storing precomputed assignments.

## Canary Policy

Minimum policy fields:

- `policy_id`;
- `enabled`;
- `candidate_model_version`;
- `incumbent_model_version`;
- `traffic_percent`;
- `assignment_mode`: `sticky_session` or `per_request`;
- `assignment_salt`;
- `max_assigned_requests`;
- `fallback_to_incumbent_on_candidate_failure`;
- hard rollback switches for candidate exception, timeout, empty output, and blocking validation;
- metric thresholds once approved.

The short-term implementation stores this as an in-process object. The production design should use an append-only rollout policy log so immutable model registry metadata and live traffic-routing policy remain distinct.

## Eligibility

A request is eligible for canary only when:

- policy is enabled;
- candidate registry state is `canary`;
- incumbent registry state is `full`;
- license and biosecurity requirements are satisfied;
- request environment and tenant/user are allowed by policy;
- automatic rollback is not active.

If any eligibility check fails, route to the incumbent and log the reason.

## Serving Behavior

For a candidate-assigned request:

1. Generate with the candidate.
2. Re-annotate and validate the candidate output when parser/validator hooks are available.
3. Serve candidate output only if it passes the configured user-visible serving gate.
4. If candidate generation or validation fails, use the configured fallback behavior.

Recommended fallback:

- Candidate exception, timeout, empty output, invalid output, or blocking validation: suppress candidate output and attempt incumbent fallback.
- If incumbent fallback succeeds: serve incumbent output and log `fallback_served`.
- If both fail: return the normal controlled generation failure.
- Record `assigned_model_version` and `served_model_version` separately.

## Metrics

Every request should produce an assignment record:

- `request_id`;
- timestamp;
- `policy_id`;
- assignment key hash and bucket;
- `assigned_model_version`;
- `served_model_version`;
- incumbent and candidate model versions;
- eligibility result and reason codes;
- fallback status and reason;
- latency and error fields.

Aggregate metrics:

- assigned/served/fallback counts;
- generation success rate;
- empty output rate;
- exception rate by class;
- timeout rate;
- latency p50/p95/p99;
- Phase 0 parse success rate once hooked in;
- Phase 3 pass/warn/fail rate once hooked in;
- exact-copy/template-copy rate once available;
- user-visible failure rate;
- later wet-lab outcome links when available and consented.

## Rollback

Hard rollback disables candidate serving immediately. Hard triggers:

- candidate serves or attempts to serve a blocking Phase 3 failure that should have been suppressed;
- candidate model or output is blocked by safety/biosecurity policy;
- license status becomes unknown, insufficient, or blocked;
- candidate artifact/config differs from approved registry/policy metadata;
- repeated candidate load/generation crashes;
- infrastructure saturation threatens incumbent serving;
- human manual rollback.

Metric-based rollback thresholds remain unresolved and require human approval before production use.

## Implementation For This Session

Implement a deterministic fake-backed canary wrapper with:

- deterministic percentage assignment;
- sticky assignment key support;
- assignment records;
- candidate failure fallback;
- in-memory metrics;
- hard rollback after configurable consecutive candidate failures.

Do not wire canary serving into the live API yet. This branch only validates the generation-layer mechanism against deterministic fakes.

## Open Human Decisions

- Approved initial canary percentage.
- Expansion schedule and minimum sample size per stage.
- Rollback thresholds for strict success, Phase 3 pass rate, component completeness, copy rate, latency, timeout rate, error rate, and fallback rate.
- Whether warning-class Phase 3 findings may ever be served during canary.
- Whether first canary requires explicit tenant/user consent.
- Which tenants or request classes are eligible.
- Whether incumbent shadow generation should continue for candidate-assigned canary requests.
- Named approvers for canary start, expansion, rollback override, and full promotion.
- Retention/access policy for restricted generated sequence payloads.
- Whether multiple simultaneous canaries are ever allowed.
