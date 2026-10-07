# README Audit

Scope: root `README.md` at `b8df563`, checked against `PROGRESS.md`, `SYSTEM_DESIGN.md`, and current repository structure.

## Executive Summary

The README is directionally useful but stale in several important ways. It understates the current test baseline, says Phase 5 feedback work is in progress on another branch even though the foundation is merged, omits the new API-backed demo fixture command, and still reads partly like a phase-history report instead of a concise contributor entry point. It should be rewritten as a short current-state overview with `PROGRESS.md` as the authoritative mutable state file.

## Accurate Content

- Product description correctly frames Construct as plain-English plasmid design with annotated map, validation, and export ambitions.
- Phase R, Phase 1, and Phase 3 gate status are broadly correct.
- Phase 0 scale limitation and Addgene/legal dependency are honestly represented.
- Phase 2 is correctly described as scaffolding/plumbing without fine-tuned generation gate closure.
- Phase 4 is correctly described as implemented foundation with gate still open for production/auth/deployment/primer/synthesis work.
- The two-file contract (`SYSTEM_DESIGN.md` plus `PROGRESS.md`) is correctly introduced.
- Worktree guidance for the Construct and Construct-opencode worktrees is useful.
- Sequential frontend verification note is correct because `.next` can collide.

## Stale Or Incorrect Content

1. Test baseline is stale.
   - Current README: `328 passing tests plus 1 skipped test`.
   - Current reality: `342 passed, 1 skipped, 8 warnings`; frontend E2E has `3 passed`; `make e2e-test` has `1 passed`.

2. Phase 5 package note is incorrect.
   - Current README says feedback-flywheel implementation is in progress on a separate Codex branch and not part of master.
   - Current reality: outcome capture, training-signal derivation, pending prompts, local outcome UI, and E2E coverage are merged; full scheduled retraining/promote loop remains open.

3. Demo instructions are incomplete.
   - Current README mentions `docs/demo.md` and demo caveat but does not include `make demo` or `make e2e-test` in the quick path.
   - Current reality: `make e2e-test` runs deterministic API-backed Playwright fixture; `make demo` exists as a local demo entry point.

4. Dependency/security status is under-specified.
   - Current README links dependency audit but does not summarize that vulnerabilities are documented and intentionally not upgraded in the latest branch.

5. Architecture/package summary is stale around Phase 5 and demo/readiness artifacts.
   - Current README implies Phase 5 is separate and does not mention rollout-policy/shadow/canary scaffolding accurately enough.

6. Current capabilities are scattered.
   - The README repeats phase status, repository orientation, architecture, and current flow, but a new contributor still has to infer what they can run today.

## Missing Content

1. A concise current-capabilities list.
   - Should include local API, Next.js workspace, retrieval pipeline, deterministic validation, GenBank/FASTA export, outcome capture, shadow/canary scaffolding, and deterministic demo fixture.

2. Explicit deferred items list.
   - Should name Phase 0 scale, Phase 2 real fine-tuning, auth/deployment, primer design, synthesis handoff, full Phase 5 automation, dependency upgrades, and SYSTEM_DESIGN drift edits.

3. `make demo` and `make e2e-test` commands.
   - The requested contributor README should include clone/configure/setup/test/demo commands.

4. Fresh-clone expectations.
   - README should say `.env.example` must be copied and `NCBI_EMAIL` set for Entrez. It should not imply Addgene credentials are available.

5. Clear authority model.
   - README should state `PROGRESS.md` is authoritative for live state, while `SYSTEM_DESIGN.md` is the original build spec and may lag unless explicitly updated.

6. Known limitations with honest wording.
   - Current README has caveats but should avoid implying synthesis-ready output is complete.

## Rewrite Recommendation

Keep the README under 250 lines and structure it as:

1. One-paragraph product description.
2. Current status and capabilities.
3. Phase status table.
4. Getting started commands:
   - clone
   - copy `.env.example`
   - set `NCBI_EMAIL`
   - `make setup`
   - `make test`
   - `make demo`
   - `make e2e-test`
5. Web/frontend commands:
   - `cd apps/web`
   - `npm ci`
   - `npm run build`
   - `npm run test:e2e`
6. Architecture summary with links to `SYSTEM_DESIGN.md`.
7. Contributor/worktree notes.
8. Known limitations/deferred items.
9. Link to `PROGRESS.md` as real-time state.

## Cross-Check Targets For README-2

- Test baseline: `342 passed, 1 skipped, 8 warnings`.
- E2E baseline: `npm run test:e2e` -> `3 passed`; `make e2e-test` -> `1 passed`.
- Current master top state: demo readiness, visual polish, and Phase 4 salvage merged.
- Phase 5 foundation is merged, but full Phase 5 gate remains open.
- Phase 2 fine-tuning execution remains spend-gated.
- Demo runner caveat: API-backed E2E fixture exists; real live demo jobs still need worker/fake queue/demo-runner decision.
- `SYSTEM_DESIGN.md` drift audit exists; direct design-doc edits require explicit human authorization.
