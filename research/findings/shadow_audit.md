> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Shadow Generator Audit

- Date: 2026-06-10
- Branch: `phase2-shadow-eval`
- Scope: `packages/generation/shadow.py`, existing tests in `tests/generation/test_shadow.py`, and rollout requirements in `research/findings/model_rollout.md`.

## Summary

The existing shadow wrapper correctly preserves the most important safety invariant: user-visible output always comes from the incumbent generator, while candidate failures are suppressed and logged. The implementation is intentionally minimal, however. It logs only model versions, output counts, and candidate error text. That is not enough to support the eventual canary decision described in `research/findings/model_rollout.md`.

No `packages/generation/rollout_eval.py` file exists in the current tree, so rollout evaluation is not yet implemented as a reusable module.

## Current Behavior

Established implementation facts:

- `ShadowComparisonGenerator.generate(...)` calls the incumbent first and returns only incumbent output.
- The candidate runs in a `try` block after incumbent generation.
- Candidate exceptions do not fail the request.
- `ShadowComparisonRecord` currently stores `request_id`, incumbent/candidate/served model versions, incumbent/candidate counts, and optional candidate error.
- Registry helper functions identify `shadow`, `canary`, and `full` records.

## Gaps Versus Rollout Design

`research/findings/model_rollout.md` requires the shadow path to capture enough evidence to compare candidate and incumbent behavior before canary exposure. Missing pieces:

- No correlation field beyond request id; individual incumbent/candidate outputs cannot be paired.
- No timestamp or trace metadata.
- No latency measurement for incumbent or candidate.
- No incumbent error path. If incumbent generation fails, nothing is recorded.
- Candidate output is not summarized beyond count.
- No output divergence metrics: sequence identity, sequence hash equality, length delta, parent-template overlap, or feature/component differences.
- No validation report comparison. The design requires both outputs to be re-annotated and validated through Phase 3 before canary decisions.
- No generated sequence hash or restricted payload pointer, which makes later audit hard without storing full sequences in unrestricted logs.
- No explicit retention policy field or payload retention mode.
- No CLI or report writer that can run a dry shadow comparison over the retrieval gold set.

## Recommended Fixes For This Session

Implement a bounded offline shadow-eval path rather than trying to solve production observability in one step:

1. Extend `ShadowComparisonRecord` with timestamp, latency fields, incumbent/candidate error fields, per-output summaries, divergence metrics, validation status comparison fields, and payload retention mode.
2. Add deterministic helper functions in `packages/generation/shadow.py` for sequence hashing, feature-count summaries, pairwise comparison, and latency measurement.
3. Preserve current safety semantics: incumbent output remains the only served output, and candidate failure is logged rather than surfaced.
4. Add a new `packages/generation/rollout_eval.py` CLI that compares two fake-backed generators over `data/eval/retrieval_gold.jsonl`, writes timestamped JSON and Markdown reports under `data/eval/shadow/`, and prints the report path.
5. Wire `make shadow-eval`.
6. Keep full payloads out of unrestricted logs. Store only hashes, lengths, features, model versions, errors, and aggregate metrics for this dry run.

## Deferred Work

- Production trace propagation through FastAPI/jobs.
- Restricted sequence payload storage.
- Phase 3 validation comparison for arbitrary online shadow output.
- Shadow sampling against real traffic.
- Human-approved retention policy for candidate payloads.
- Integration with model registry promotion events.
