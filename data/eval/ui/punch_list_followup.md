# Demo Punch List Follow-Up

Date: 2026-06-20  
Branch/worktree: `demo-punch-list` in the Construct-opencode worktree  
Scope: follow-up on `data/eval/ui/demo_walkthrough.md`, UX/a11y audits, current Next 16 frontend, and frontend E2E coverage.

## Active Items

### 1. Live `make serve-api` plus `npm run dev` still is not a reliable completing demo path

Category: Blocker for demo

Evidence/source: The original walkthrough reports the yeast shuttle prompt remained in `Designing and validating plasmid` for more than a minute under `make serve-api` plus `npm run dev`. Current docs still warn that the default API scaffold can queue jobs without completing them, and `make demo` is the reliable deterministic fixture. The Makefile has `serve-api`, `serve-web`, and `demo: e2e-test`, but no live `serve-demo` or `serve-worker` target.

Why it matters for external demo: The five-minute story depends on job completion, map rendering, export enablement, and outcome reporting. If the live job never completes, the demo stalls before the visual payoff.

Suggested bounded frontend-only fix: Log for human. The real fix requires choosing a demo execution model outside the frontend: worker, fake queue, seeded result, or scripted deterministic API fixture. Frontend-only mitigation is clearer timeout copy, but that does not make the live path demo-safe.

### 2. Poll timeout UX is improved but still undersells the likely worker/offline cause

Category: Polish that would improve demo

Evidence/source: Current frontend has a 30s polling timeout and `Check status` recovery. The copy says the job is still running, but does not mention that a demo worker may be offline or that the presenter should verify the demo fixture/worker path.

Why it matters for external demo: If the job does not complete during rehearsal, the presenter needs the UI to make the failure mode obvious instead of looking like a broken product.

Suggested bounded frontend-only fix: Update `poll_timeout` messages and the bottom job status line to say that the job is still queued or running, and for local demos the worker/demo fixture should be checked before retrying.

### 3. After a polling timeout, the composer can start a refinement while an unresolved job is still active

Category: Polish that would improve demo

Evidence/source: `isBusy` is only `submitting | polling`. On timeout, `activeJobId` is retained and state becomes `poll_timeout`, but the submit handler only blocks on `isBusy`. Because a session exists, the submit button can read `Refine` while an unresolved job remains.

Why it matters for external demo: A presenter trying to recover can accidentally submit a refinement against the same session while the first job is unresolved, making the story harder to explain and increasing the chance of stale right-rail confusion.

Suggested bounded frontend-only fix: Treat `state === "poll_timeout" && activeJobId` as a recovery state. Disable normal submit or change the primary action area to `Check status` plus an explicit `Start over`/`Abandon job` action that clears the unresolved job intentionally.

### 4. Small viewport behavior is plausible but not covered by E2E

Category: Polish that would improve demo

Evidence/source: The layout collapses to one column, the pending outcome toast moves on small screens, and the result includes a `View plasmid map` anchor. Playwright configs currently run desktop Chromium only.

Why it matters for external demo: If the demo is shown on a laptop window, projector, or resized browser, the map/export/outcome payoff may be below the fold and untested.

Suggested bounded frontend-only fix: Add one mocked Playwright small-viewport smoke test that completes a design, taps `View plasmid map`, verifies the map/feature list, verifies export controls are reachable, and opens the outcome modal. No API changes needed.

### 5. Turbopack/SeqViz coverage is still shallow

Category: Polish that would improve demo

Evidence/source: Next 16 uses Turbopack by default. The map has a dynamic `seqviz` import and an error boundary. Current E2E asserts the wrapper `data-testid="seqviz-map"` is visible, but that can pass even if the inner visualization is visually degraded.

Why it matters for external demo: The plasmid map is the main visual proof point. A blank or half-rendered SeqViz area would be highly visible.

Suggested bounded frontend-only fix: Strengthen the E2E smoke to assert the accessible map summary and feature list are present, and assert `Map could not render` is not visible on the happy path. If a stable SeqViz DOM marker exists, assert that too.

### 6. Outcome history refresh failures are still silent

Category: Minor nice-to-have

Evidence/source: `getOutcome(designId)` errors are swallowed as expected for missing current outcomes. Known local outcomes are refreshed in the background, but failures resolve to `null` and no status is shown if all refreshes fail.

Why it matters for external demo: The `My outcomes` panel is honest that it is browser-local, but a stale or unrefreshed outcome list can still prompt questions about sync reliability.

Suggested bounded frontend-only fix: Add a small `Refreshing outcomes...` state and a non-blocking `Could not refresh saved outcomes` message only when there are known local outcomes and every refresh attempt fails.

### 7. Outcome modal accessibility is improved, but field-level validation association remains incomplete

Category: Minor nice-to-have

Evidence/source: Modal focus, Escape handling, restoration, and `aria-labelledby` are now present. Validation issues still render as a general list, and select/textarea controls do not use `aria-invalid`, `aria-describedby`, or explicit required/review relationships.

Why it matters for external demo: Accessibility-minded reviewers may inspect the outcome workflow because it is the feedback-loop differentiator.

Suggested bounded frontend-only fix: Add stable IDs for validation/help text, mark the consent review area and minimum evidence fields with `aria-describedby`, and set `role="alert"` or `aria-live="polite"` on validation changes after submit attempts.

### 8. Focus styling is still inconsistent in modal form fields

Category: Minor nice-to-have

Evidence/source: Many page controls now use `focus:ring-2 focus:ring-action/20`, but modal `textarea` and `select` still rely mainly on `focus:border-action`.

Why it matters for external demo: Keyboard navigation through the outcome modal can look less polished than the main workspace.

Suggested bounded frontend-only fix: Add the same `focus:ring-2 focus:ring-action/20` treatment to modal selects and textareas.

### 9. Major regions are better than before but still not fully named

Category: Minor nice-to-have

Evidence/source: Individual right-rail panels have labels or labelled headings, but the main conversation section and right rail container are not explicitly named. The a11y audit called this out as a landmark/region improvement.

Why it matters for external demo: It is unlikely to block a visual demo, but it improves screen-reader navigation and polish.

Suggested bounded frontend-only fix: Add IDs to the `Design workspace` heading and a right-rail heading or sr-only label, then use `aria-labelledby` on the conversation section and aside.

### 10. First impression remains visually flat before the map loads

Category: Minor nice-to-have

Evidence/source: The visual audit noted the sparse scientific-tool aesthetic can read as wireframe-like before SeqViz loads. Current panels still share similar borders, panel backgrounds, and subtle shadows.

Why it matters for external demo: The first screen is the first credibility moment, and the visual payoff only arrives after completion.

Suggested bounded frontend-only fix: Add slightly stronger emphasis to the plasmid map panel or welcome card only, such as a stronger heading/metadata row or more intentional empty-state well. Avoid broad restyling.

## Superseded Or Fixed

- Original live-job blocker is partially mitigated, not fixed: frontend now times out and offers `Check status`, but the live `serve-api` completion path still needs a human demo-runner decision.
- Right rail stale-design risk during a new job is fixed: the UI labels that a new design is running and export/outcome actions are disabled while busy.
- Zero retrieved-template and missing-validation states are fixed: completed result cards render explicit placeholder panels.
- Partial result without annotated sequence is fixed: supporting evidence can render while map/export remain unavailable.
- Export stale state and global error ambiguity are fixed: export status/errors reset on `designId` change and per-format errors are shown.
- Export status announcement and visual feedback are fixed: export section uses busy state, status text, alert/error panels, and success panels.
- Pending outcome prompt error collapse is mostly fixed: prompt fetch tracks loading, ready, and error states and surfaces a right-rail error message on failure.
- Pending outcome toast mobile overlap is fixed: the toast is top-fixed on small screens and bottom-right only from `sm` upward.
- Modal programmatic name, focus entry, focus trap, Escape close, and focus restore are fixed.
- Dynamic chat/job status announcement is improved: the app has a screen-reader live status region and the progress card uses `role="status"`.
- Plasmid map non-visual accommodation is fixed enough for demo: accessible summary, feature list, complete coordinates/strand/confidence text, and render fallback are present.
- Button hierarchy and status badges are improved: main panel actions are mostly filled primary buttons, secondary/export actions are outlined, and badges share a more consistent recipe.
- `make demo` supersedes the original manual live walkthrough for verification: it runs the deterministic full-stack Playwright fixture through `make e2e-test`.
