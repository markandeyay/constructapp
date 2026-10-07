# Loose Ends Cleanup Plan

Scope: `PROGRESS.md` at `b8df563` on branch `cleanup-loose-ends`. Phase 2 fine-tuning execution items are excluded from actionable cleanup because they remain intentionally spend-gated.

## Summary

| Category | Count | Disposition |
| --- | ---: | --- |
| (a) Still needed and tractable this session | 2 | Documentation cleanup only: consolidate active loose ends in `PROGRESS.md`; rewrite stale README state. |
| (b) Requires human decision or external dependency | 34 | Move into one `Decisions Pending Human Review` section or a concise external-dependency note. |
| (c) Obsolete or superseded by later work | 12 | Remove from active blocker/carryover wording; preserve historical detail in build log. |
| (d) Deferrable to future phase without harm | 15 | Move to `Deferred Follow-Ups` with rationale. |

## Category (a): Tractable This Session

1. Scattered active loose-end notes in `PROGRESS.md`.
   - Reference: `KNOWN ISSUES / BLOCKERS`, `QUESTIONS FOR THE HUMAN`, and top `RESUME HERE`.
   - Rationale: The active state is hard to scan because historical notes, blockers, decisions, and deferred future work share one list.
   - Recommended disposition: Reorganize into current state, external blockers, deferred follow-ups, and decisions pending human review.

2. Root `README.md` stale against current state.
   - Reference: `README.md` still reports 328 passing tests and says Phase 5 implementation is in progress on a separate branch.
   - Rationale: Current `master` baseline is 342 passing tests and Phase 5 foundation is merged.
   - Recommended disposition: Rewrite README under 250 lines as the current contributor-facing overview.

## Category (b): Human Decision Or External Dependency Required

### Data, Corpus, And Licensing

1. Addgene partner access and commercial-use terms.
   - Reference: `KNOWN ISSUES / BLOCKERS` Addgene dev-mode and corpus scale notes; questions on Addgene direct downloads and Vector Database sequences.
   - Decision needed: Whether and under what license Addgene-derived records may be used for retrieval, parser calibration, display, or training.
   - Options: keep excluded; allow retrieval/display only; allow parser calibration; allow training after partner agreement.

2. Non-NCBI public source use in training.
   - Reference: questions on SEVA, iGEM Registry, DNASU, SGD-derived context.
   - Decision needed: Whether these sources are admissible for commercial training artifacts.
   - Options: exclude until explicit terms; use for retrieval/eval only; allow training with source-specific restrictions.

3. Broad natural RefSeq/GenBank use in generation pretraining.
   - Reference: first question under `QUESTIONS FOR THE HUMAN`.
   - Decision needed: Whether broad natural plasmids belong in generation training or only retrieval/evaluation.
   - Options: training allowed; retrieval/eval only; filter out of training artifacts.

4. Lentiviral and CRISPR calibration seed strategy.
   - Reference: current gap note and question on Addgene intended-use license vs GenBank derivatives.
   - Decision needed: Whether to wait for Addgene, admit reviewed GenBank derivatives, or leave these profiles unsupported.

5. Canonical ambiguous element variants.
   - Reference: question listing EF1a, SV40, U6, tac/trc, polyA, markers, origins.
   - Decision needed: Which variants are approved for the reference library.

6. pACYC184 retrieval gold policy.
   - Reference: question about chloramphenicol low-copy gold case.
   - Decision needed: Whether to keep a single canonical answer or broaden with copy-number/origin-aware logic.

### Validation, Synthesis, And Biosecurity

7. Default synthesis provider profile.
   - Reference: synthesis provider question.
   - Decision needed: Conservative cross-provider default vs provider-specific or user-selected defaults.

8. Automatic codon rewriting scope.
   - Reference: question on scoring only vs rewriting after consent.
   - Decision needed: Whether product may rewrite coding sequences and under what user consent.

9. Circular plasmid canonical base 1.
   - Reference: question on source origin, ORI start, MCS, or provider convention.
   - Decision needed: Canonical coordinate convention.

10. Supported validity profile set.
    - Reference: vector types question.
    - Decision needed: First supported profiles for deterministic validation.

11. Repeat/instability treatment for natural plasmids.
    - Reference: question on biologically expected repeats.
    - Decision needed: Whether natural-source repeats should block synthesis readiness.

12. Optional therapeutic-compliance checks.
    - Reference: incomplete Phase 3 checklist item.
    - Decision needed: Whether and when to add gene-therapy/regulated-use checks.

13. Biosecurity screening role.
    - Reference: question on regulated-like checkpoint and U.S. screening framework.
    - Decision needed: Product policy and legal interpretation before provider handoff.

### Phase 4 Product And Architecture

14. Auth/session ownership model.
    - Reference: Phase 4 question on user/org/project ownership.
    - Decision needed: Ownership model before AuthN/AuthZ implementation.

15. Retention policy for sessions, turns, jobs, designs.
    - Reference: retention question.
    - Decision needed: Data retention and deletion model.

16. Polling vs SSE/WebSocket streaming.
    - Reference: long-running job question.
    - Decision needed: Keep polling or introduce streaming transport.

17. Persisted job result authority.
    - Reference: JSON snapshot vs normalized tables question.
    - Decision needed: Authoritative persistence model.

18. Demo runner/live worker path.
    - Reference: `RESUME HERE` carryover says real demo jobs still need worker or explicit demo runner beyond E2E fixture.
    - Decision/external dependency: Decide whether demo should use a worker, fake queue, seeded result, or scripted API-backed fixture.

19. Frontend design system primitives and brand treatment.
    - Reference: visual polish questions.
    - Decision needed: Class normalization only vs shared primitives; sparse scientific aesthetic vs stronger brand treatment; semantic status tokens.

20. Pending outcome prompt placement.
    - Reference: visual polish question.
    - Decision needed: Toast vs banner vs right-rail card.

21. Accessibility navigation structure.
    - Reference: visual/a11y questions on skip link, two-region navigation, plasmid map detail route/table, modal vs dedicated outcome route.
    - Decision needed: Whether to make small layout/navigation restructures.

### Feedback And Outcomes

22. Multiple outcome rows per design.
    - Reference: outcome question.
    - Decision needed: One latest outcome vs clone-level multiple outcomes.

23. Outcome evidence standards.
    - Reference: sequencing evidence, restriction digest, assay threshold, expression-control questions.
    - Decision needed: Minimum evidence for positive/negative/ambiguous training signals.

24. Outcome artifact retention.
    - Reference: chromatograms/gels/plate-reader/blot retention question.
    - Decision needed: Whether raw assay files can be retained and used for feature extraction.

25. Outcome consent text and withdrawal policy.
    - Reference: consent-withdrawal question.
    - Decision needed: Legal/policy wording and snapshot retention rule.

26. Outcome form framing and label visibility.
    - Reference: outcome UI questions.
    - Decision needed: Bias-reducing wording and whether training labels should be hidden.

### Rollout And Phase 2 Policy Adjacent

27. Rollout thresholds and canary policy.
    - Reference: questions on offline promotion threshold, canary traffic/sample sizes/rollback thresholds, sticky assignment, consent, incumbent shadowing, simultaneous canaries.
    - Decision needed: Production rollout policy before live canary use.
    - Note: Adjacent to Phase 2 but not GPU execution.

28. Shadow payload retention/access.
    - Reference: restricted candidate sequence payload retention question.
    - Decision needed: Retention/access policy for shadow artifacts.

29. Carbon weights legal/revision policy.
    - Reference: Apache-2.0 Carbon question.
    - Decision needed: Legal approval and revision pinning.

30. DNABERT-2 fallback dependency.
    - Reference: missing `einops` note.
    - External dependency: Decide whether to install dependency or keep fallback parked.

31. Managed GPU provider/hardware/budget.
    - Reference: provider/budget questions and preflight notes.
    - External dependency: Cloud account/API setup and explicit spend authorization.

32. CI setup.
    - Reference: incomplete Phase 0 checklist item `CI runs lint + tests on every commit`.
    - External dependency/human decision: Repository hosting/CI policy not configured in this local-only session.

33. Deployed auth/hosting/rate limiting/usage metering.
    - Reference: Phase 4 gate and known limitations.
    - External dependency: Deployment/product policy and account setup.
    - Note: Local API rate limiting exists, but production auth/metering remains external/product work.

34. Phase 0 scale gate.
    - Reference: corpus size remains 256 records vs 50,000 gate.
    - External dependency: Larger lawful corpus acquisition, likely Addgene/other source decision.

## Category (c): Obsolete Or Superseded

1. `phase4-outcome-ui remains a frontend-only branch` as an active blocker.
   - Superseded by: `phase4-outcome-ui` merged into master on 2026-06-12.
   - Disposition: Keep historical build-log entry only.

2. `Phase 4 visual polish is merged... decisions logged as human questions` as an active blocker.
   - Superseded by: Visual polish merged and specific questions can live in decisions section.
   - Disposition: Remove from active blocker list after decision consolidation.

3. `Phase 4 polish is merged locally` as active blocker text.
   - Superseded by: later demo-readiness/visual/salvage consolidation.
   - Disposition: Keep as completed state summary only if needed.

4. OpenCode duplicate API-test coordination note.
   - Superseded by: merge consolidation already handled.
   - Disposition: remove from active blockers; historical log remains enough.

5. pACYC184 retrieval regression as active issue.
   - Superseded by: retrieval robustness rerun ranks `curated:pACYC184` first.
   - Disposition: retain diagnostic reference in archive/build log only.

6. Phase 3 known-good shortfall/formal gate open historical notes.
   - Superseded by: Phase 3 gate met under curated-quality policy.
   - Disposition: remove any active implication that Phase 3 gate is still open.

7. Repeat-detection performance as Phase 3 blocker.
   - Superseded by: profiling showed bottleneck is parser/reference matching, not repeat checker.
   - Disposition: move parser/reference optimization to deferred follow-ups if retained.

8. Frontend `npm build`/E2E `.next` collision as active blocker.
   - Superseded by: documented operational note.
   - Disposition: keep concise verification note, not blocker.

9. Historical branch lists in active blockers.
   - Superseded by: current consolidated master state.
   - Disposition: collapse to a short `recent branches merged` state or remove.

10. `Phase 1 is authorized and active` wording.
    - Superseded by: Phase 1 gate is met.
    - Disposition: remove active phrasing.

11. `Local .env uses POSTGRES_PORT=55432` conflicting with `Construct-opencode` alternate ports note.
    - Superseded by: worktree-specific `.env` note for Construct-opencode.
    - Disposition: replace with a single local-env caveat.

12. `Phase 5 foundation is merged...` as blocker phrasing.
    - Superseded by: Phase 5 foundation is current capability; full Phase 5 gate is deferred.
    - Disposition: represent under status/deferred follow-ups.

## Category (d): Deferrable To Future Phase Without Harm

1. Phase 0 corpus scale to 50,000 annotated plasmids.
   - Rationale: Formal Phase 0 gate remains open, but current retrieval/application work uses the verified smaller corpus.

2. Literature/context extraction into `experimental_contexts`.
   - Rationale: Not needed for current demo path; depends on data-source policy.

3. Addgene ingestion implementation beyond parked dev mode.
   - Rationale: Depends on partner/legal access.

4. Parser/reference-match performance optimization.
   - Rationale: Identified as performance follow-up, not current validation correctness blocker.

5. Depositing-lab retrieval filter.
   - Rationale: Schema/corpus do not carry `depositing_lab`; can wait for schema expansion.

6. Broad lentiviral/CRISPR corpus support.
   - Rationale: Not required for current supported demo profiles.

7. Primer-design output.
   - Rationale: Phase 4 gate item but not needed for current API-backed demo fixture.

8. Synthesis provider handoff.
   - Rationale: Requires provider/default/biosecurity decisions.

9. Production AuthN/AuthZ, rate limiting, usage metering, hosting.
   - Rationale: Productization work; local API has basic safeguards.

10. Streaming job updates.
    - Rationale: Polling is functional and now has timeout UI.

11. Backend list endpoint for My outcomes.
    - Rationale: Local browser-backed list is acceptable for current frontend foundation.

12. Full Phase 5 scheduled retraining/promotion loop.
    - Rationale: Depends on Phase 2 fine-tuning and rollout policy decisions.

13. Model registry/promotion productionization.
    - Rationale: Registry/shadow/canary scaffolding exists; production promotion waits for real model.

14. Dependency upgrades from audit.
    - Rationale: Vulnerabilities documented; upgrades can be scheduled separately to avoid destabilizing cleanup branch.

15. SYSTEM_DESIGN drift edits.
    - Rationale: Drift audit exists; direct SYSTEM_DESIGN edits require explicit human authorization.

## Execution Order

1. Commit this plan.
2. Rewrite `PROGRESS.md` active sections around current state, external blockers, deferred follow-ups, and a consolidated decisions section.
3. Rewrite `README.md` to match current `PROGRESS.md` state.
4. Cross-check README against `PROGRESS.md`.
5. Run `make test`, `npm run build`, and `npm run test:e2e`.
