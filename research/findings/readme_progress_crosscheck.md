> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# README / PROGRESS Cross-Check

Date: 2026-06-16

Result: pass.

Checked `README.md` against the cleaned active sections of `PROGRESS.md` after the loose-ends cleanup.

Agreement points:

- Verification baseline matches: `make test` reports 342 passed, 1 skipped, 8 warnings; frontend build passes; `npm run test:e2e` reports 3 passed; `make e2e-test` reports 1 passed.
- Phase status matches: Phase R, Phase 1, and Phase 3 gates are met; Phase 0, Phase 2, Phase 4, and Phase 5 gates remain open for the reasons stated in `PROGRESS.md`.
- Current capabilities match: API/frontend foundations, retrieval, validation, outcome capture, shadow/canary scaffolding, and deterministic API-backed E2E fixture are described consistently.
- Deferred work matches: Phase 0 scale-up, Addgene/source licensing, Phase 2 fine-tuning, production auth/deployment, primer design, synthesis handoff, full Phase 5 automation, dependency upgrades, and `SYSTEM_DESIGN.md` drift edits are not claimed as complete.
- Demo wording matches: `make demo` is documented as the deterministic fixture path, while live queued demo jobs still need a worker/fake queue/seeded-result decision.

No README changes were required after this cross-check. If a future conflict appears, `PROGRESS.md` remains authoritative.
