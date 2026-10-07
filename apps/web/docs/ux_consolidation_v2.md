# UX Consolidation v2, Affordance Audit and Recommendations

Scope: the Construct web frontend on `branch visual-redesign`. This document is a SPEC DOC only. It inventories every interactive affordance currently rendered, audits consistency, surface placement, and empty states, and issues specific consolidation recommendations using the vocabulary in `apps/web/docs/design_system.md` (primary `bg-coral`, secondary `border-line-strong text-ink bg-paper`, tertiary text-only `hover:text-coral`).

All findings reference the actual source. No code is changed by this document. No new buttons are recommended.

Sources read fully:
- `apps/web/app/page.tsx` (lines 1-1199)
- `apps/web/components/export-actions.tsx`
- `apps/web/components/outcome-report-modal.tsx`
- `apps/web/components/plasmid-map-view.tsx`
- `apps/web/docs/design_system.md`

---

## 1. COMPLETE BUTTON / AFFORDANCE INVENTORY

### Header (`apps/web/app/page.tsx:452-474`)

| Affordance | Location | What it does | Placement justified? | Visual hierarchy | Needed? |
| --- | --- | --- | --- | --- | --- |
| `Inspect` button (`page.tsx:457-463`) | Header, right cluster; `md:inline-flex lg:hidden` | Opens `inspectOpen` drawer that re-renders the right-rail panels for medium widths (768-1023px) where the rail is not permanently visible | Ambiguous, only shown in the 768-1023px band; on mobile (`<768`) the rail is stacked and on `lg` it is permanent, so this exists purely for a transitional band | Secondary (border + `bg-paper`), correct recipe | Relocate, see Recommendation R5 |
| `Show conversation` / `Hide conversation` button (`page.tsx:464-472`) | Header, right cluster | Toggles `threadOpen` | Yes, conversation is a secondary surface that should not always occupy space | Secondary (border + `bg-paper`), correct recipe | Yes |

### Left nav (`apps/web/app/page.tsx:479-496`)

| Affordance | Location | What it does | Placement justified? | Visual hierarchy | Needed? |
| --- | --- | --- | --- | --- | --- |
| Conversation-toggle icon button, `aria-label="Toggle conversation"` (`page.tsx:480-491`) | 56px left icon-rail, `lg:flex` | Identical action to the `Show conversation`/`Hide conversation` header button | No, pure duplicate of the header toggle | Secondary (border + `bg-paper`), correct recipe, but redundant | Remove entirely (R1) |
| Two decorative dashed squares (`page.tsx:492-495`) | Bottom of the left rail, `aria-hidden` | Nothing, they are placeholder chrome | No, they read as disabled nav items ("random buttons") the user expects to click | Not interactive, but visually mimics disabled buttons | Remove entirely (R1) |

### Desktop right rail (`apps/web/app/page.tsx:502-513`)

| Affordance | Location | What it does | Placement justified? | Visual hierarchy | Needed? |
| --- | --- | --- | --- | --- | --- |
| `Open full report` (`ValidationSummary`, `page.tsx:874-880`) | Validation panel | Scrolls/opens the conversation drawer where the full `ValidationReportPanel` is rendered | Yes, summary here, detail in thread | Tertiary text `text-coral` + `hover:underline` | Yes |
| `GenBank` and `FASTA` export buttons (`export-actions.tsx:27-28`) | Export panel | Triggers `exportDesign(designId, format)` and downloads the file | Yes, primary product output actions | Secondary (`border-line-strong bg-paper`), correct | Yes, but two buttons could remain since only 2 formats exist (R8 judgment call) |
| `Report outcome` / `Review or edit outcome` (`OutcomePanel`, `page.tsx:902-909`) | Outcome panel for the current design | Opens `OutcomeReportModal` for `designId` | Yes, single primary action of this panel | Primary `bg-coral`, correct per design_system "one primary action per panel" | Yes |
| `Review or edit outcome` per reported outcome (`MyOutcomesPanel`, `page.tsx:772-774`) | One button per outcome card | Opens the modal for that historical outcome | Ambiguous, useful, but a coral primary on every card creates multiple coral primaries in a single rail | Primary `bg-coral`, too loud for an edit/review action on historical items | Demote to secondary (R6) |

### Mobile layout (`apps/web/app/page.tsx:516-548`)

| Affordance | Location | What it does | Placement justified? | Visual hierarchy | Needed? |
| --- | --- | --- | --- | --- | --- |
| Mobile `GenBank` button (`page.tsx:522-529`) | Mobile-only export strip under the map | Same as the desktop export button | No, hand-rolled duplicate of the `ExportButton` inside `ExportActions`; the component is already a responsive `grid-cols-2` and could be reused directly | Secondary, correct recipe | Remove the duplicate; reuse `ExportActions` (R2) |
| Mobile `FASTA` button (`page.tsx:530-537`) | Mobile-only export strip | Same as above | No, same duplication | Secondary, correct | Remove the duplicate; reuse `ExportActions` (R2) |

(Same right-rail panels `ValidationSummary`, `OutcomePanel`, `MyOutcomesPanel` are also re-rendered in the mobile stack at `page.tsx:539-545`, these are not duplicates of the rail, they are the rail, just stacked.)

### Conversation drawer (`apps/web/app/page.tsx:551-624`)

| Affordance | Location | What it does | Placement justified? | Visual hierarchy | Needed? |
| --- | --- | --- | --- | --- | --- |
| Backdrop dismiss button, `aria-label="Dismiss conversation"` (`page.tsx:553-559`) | Full-viewport scrim, `tabIndex=-1` | Closes the drawer on outside-click | Yes, standard drawer pattern; `tabIndex=-1` keeps it out of tab order | Invisible, acceptable | Keep |
| `Hide` button (`page.tsx:568-574`) | Drawer header | Closes the drawer | No, the header `Hide conversation` button is still visible and active, the backdrop closes, and Escape closes (handled at `page.tsx:209-220`); three ways to close is two too many | Secondary, correct recipe, but redundant | Remove entirely (R3) |
| `View plasmid map` link (`page.tsx:608-615`) | Inline in each result message with an `annotated_sequence` | `href="#plasmid-map"` and closes the drawer so the map is visible | Yes, sensible cross-link from a result message to the persistent map | Tertiary `text-coral`, but **no** `hover:underline`, inconsistent with the ValidationSummary tertiary link | Keep; fix hover treatment (R7) |

### Inspect drawer (`apps/web/app/page.tsx:626-657`)

| Affordance | Location | What it does | Placement justified? | Visual hierarchy | Needed? |
| --- | --- | --- | --- | --- | --- |
| Backdrop dismiss button, `aria-label="Close inspector"` (`page.tsx:628-634`) | Full-viewport scrim, `tabIndex=-1` | Closes the inspect drawer on outside-click | Yes, standard pattern | Invisible, acceptable | Keep (pending R5) |
| `Close` button (`page.tsx:638-644`) | Inspect drawer header | Closes the inspect drawer | Ambiguous, the backdrop and Escape (`page.tsx:209-220`) already close; this is a third affordance for the same action | Secondary, correct | Keep unless R5 removes the whole drawer |

### Composer footer (`apps/web/app/page.tsx:660-723`)

| Affordance | Location | What it does | Placement justified? | Visual hierarchy | Needed? |
| --- | --- | --- | --- | --- | --- |
| Three example-prompt chips (`page.tsx:668-678`) | Above the textarea, only when `!sessionId && state === "idle"` | Prefills `input` with the example | Yes, onboarding for first-time users; disappears after the first job starts | Border chip (`border-line bg-paper hover:bg-mist`), closer to secondary than tertiary; visually heavier than the prompt text inside | Keep; minor weight tweak (R9) |
| Submit button (`page.tsx:698-704`) | Right of the textarea | Submits the design/refinement/clarification answer | Yes, the single primary action of the whole workspace | Primary `bg-coral`, correct | Yes |
| `Check status` button (`page.tsx:713-715`) | Inside the `activeJobId` status strip; only rendered when `state === "poll_timeout"` | Resumes polling for `activeJobId` | Yes, only recovery path for a timed-out job | Tertiary text-only `text-coral`, **no** `hover:*`, wrong: the primary recovery action should not be the lowest hierarchy | Promote to secondary (R4) |
| `Start over` button (`page.tsx:716-718`) | Same status strip | Abandons `activeJobId`, clears session, returns to `idle` | Yes, destructive recovery; correct that it is quieter than `Check status` | Tertiary text-only `text-ink hover:text-coral`, correct recipe, but no padding/click target | Keep; inherit consistent padding (R7) |

### Pending outcome toast (`apps/web/app/page.tsx:795-811`)

| Affordance | Location | What it does | Placement justified? | Visual hierarchy | Needed? |
| --- | --- | --- | --- | --- | --- |
| `Report outcome` button (`page.tsx:802-804`) | Toast | Opens the modal for that prompt | Yes, primary call to action of the toast | Primary `bg-coral`, correct | Yes |
| `Not now` button (`page.tsx:805-807`) | Toast | Dismisses the prompt (session-storage persisted) | Yes, explicit dismiss is clearer than a bare backdrop | Secondary `border-line-strong bg-paper hover:bg-mist`, correct | Yes |

### Outcome report modal (`apps/web/components/outcome-report-modal.tsx`)

| Affordance | Location | What it does | Placement justified? | Visual hierarchy | Needed? |
| --- | --- | --- | --- | --- | --- |
| ModalFrame top-right `Close` (`outcome-report-modal.tsx:366-368`) | Top-right of the modal | Calls `onClose` | No, the footer `Close` and Escape (`onKeyDown` handler at `outcome-report-modal.tsx:317-323`) already close; duplicate | Tertiary `text-slate hover:text-ink`, **different** recipe from the footer Close, inconsistent | Remove entirely (R3) |
| `Back to design` button on the submitted screen (`outcome-report-modal.tsx:208-210`) | Footer of the submitted-state modal | Calls `onClose` | Yes, single primary action of the success screen | Primary `bg-coral`, correct | Yes |
| `Submit without training consent` / `Consent choice reviewed` toggle (`outcome-report-modal.tsx:272-274`) | Inside the consent section | Sets `consentReviewed=true` so the validation issue "Choose whether this report may be used for model improvement." clears even if the checkbox is unchecked | Ambiguous, the checkbox `onChange` already sets `consentReviewed=true` (`outcome-report-modal.tsx:262-266`), so this button only matters when the user wants to submit **without** consent and never touches the checkbox. That is a real but narrow case | Tertiary `text-coral hover:text-coral/80`, inconsistent with other tertiary `text-coral` which use `hover:underline` | Judgment call, see R10 and Question Q2 |
| Footer `Close` button (`outcome-report-modal.tsx:288-290`) | Sticky footer | Calls `onClose`; disabled while submitting | Yes, standard modal footer pair with the primary | Secondary, correct | Yes |
| Footer `Submit outcome` button (`outcome-report-modal.tsx:291-293`) | Sticky footer | Submits the form | Yes, the single primary action of the modal | Primary `bg-coral`, correct | Yes |

### Plasmid map view (`apps/web/components/plasmid-map-view.tsx`)

No interactive buttons or links. The feature list rows expose `title` attributes only (non-affordance tooltips). Map-fallback and empty-state paragraphs are static. Nothing to consolidate here.

---

## 2. INTERACTIVE-AFFORDANCE CONSISTENCY

The canonical recipes from `design_system.md`:

- Primary: `bg-coral text-paper rounded-md shadow-rest hover:shadow-raised` + `focus:ring-2 focus:ring-coral/40 focus:border-coral focus:outline-none`.
- Secondary: `border border-line-strong text-ink bg-paper rounded-md hover:bg-mist` + focus ring.
- Tertiary: `text-coral` (or `text-ink` then `hover:text-coral`) text-only, no border.

Inconsistencies found:

1. **Tertiary `text-coral` hover treatment is split three ways.**
   - `ValidationSummary` "Open full report" (`page.tsx:877`) uses `hover:underline`.
   - `View plasmid map` link (`page.tsx:611`) uses no hover at all.
   - Outcome modal "Consent choice reviewed" (`outcome-report-modal.tsx:272`) uses `hover:text-coral/80`.
   - `Check status` (`page.tsx:713`) uses no hover at all.
   Recommendation: standardize every tertiary `text-coral` affordance to `hover:underline`. See R7.

2. **Tertiary `text-ink` hover is consistent** (`Start over` at `page.tsx:716` uses `hover:text-coral`, matching design_system's tertiary-text-ink example). Keep.

3. **Two "Close" buttons in the same modal use two different recipes.**
   - ModalFrame top-right Close (`outcome-report-modal.tsx:366`): `text-slate hover:text-ink`, a tertiary `text-slate`.
   - Footer Close (`outcome-report-modal.tsx:288`): `border border-line-strong bg-paper`, secondary.
   Recommendation: keep the footer Close (matches the modal's primary/secondary footer pair) and remove the top-right Close (R3).

4. **Recovery buttons have no click-target padding.**
   - `Check status` and `Start over` (`page.tsx:713-718`) are bare `<button>` elements with only text and focus styles; no `px-/py-`. Their hit area is the text glyph height. Every other interactive button in the app uses `px-sm py-2xs` or `px-md py-sm`. Recommendation: add the standard small-padding recipe (R7).

5. **Focus ring is consistent** across inputs, selects, textareas, and buttons (`focus:ring-2 focus:ring-coral/40 focus:border-coral focus:outline-none`). No deviations found. Good.

6. **Disabled style is consistent** (`disabled:cursor-not-allowed disabled:border-line disabled:bg-paper disabled:text-slate`) across export, outcome, and submit buttons. Good.

7. **Example-prompt chips are heavier than tertiary but used as onboarding hints.** They render as bordered chips (`border-line bg-paper hover:bg-mist`) at `page.tsx:674`, which visually competes with the secondary `Show conversation` button in the header. They are effectively a secondary recipe used for inline suggestions. Minor, see R9.

---

## 3. FEATURE-SURFACE AUDIT

| Surface | Where it lives | When it appears | Buried or in the way? |
| --- | --- | --- | --- |
| Validation report (full) | Inside conversation messages as `ValidationReportPanel` (`page.tsx:978-1008`) | Once a result message with a `validation_report` is rendered | Buried, the right rail's `ValidationSummary` surfaces "Open full report" (`page.tsx:874-880`), which only re-opens the drawer; that trade-off is fine, but it means the full check-by-check detail is only readable while the conversation drawer is open. Acceptable. |
| Validation summary | Right rail `ValidationSummary` (`page.tsx:846-883`) | Always rendered (empty state when no report) | In the way at idle (always-on "No validation report yet" card competes for rail space before any job runs). See R11. |
| Feature list | `FeatureLegend` in `PlasmidMapView` (`plasmid-map-view.tsx:124-159`) | Whenever a design is loaded | Well placed, sits under the map it annotates. |
| Export buttons | `ExportActions` in the rail (`page.tsx:508`) and a hand-rolled duplicate on mobile (`page.tsx:521-538`) | Always rendered (idle when no design) | In the way at idle (genbank/fasta shown disabled before any design exists). See R11. |
| Outcome submission | `OutcomePanel` (rail) → `OutcomeReportModal` | Always rendered (idle when no design) | In the way at idle. The panel text already says "Complete a design job to report lab results." so the disabled primary button is redundant chrome pre-design. See R11. |
| Pending outcome prompts | `PendingOutcomeToast` overlay (`page.tsx:448-450`, `795-811`) | When `visiblePendingPrompt` is set and not dismissed | Correctly in the way, this is a deliberate nudge. |
| My outcomes | `MyOutcomesPanel` (`page.tsx:738-783`) | Always rendered (empty state when no outcomes) | Buried at the bottom of the rail, below Export and Outcome. It is the only surface for historical reports, so its position is defensible, but each card's coral primary is loud. See R6. |
| Refinement composer | Footer form (`page.tsx:660-723`) | Always rendered | Correctly placed, the single composer is the workspace's main input. |
| Job progress | Inline `JobProgressCard` inside the conversation drawer (`page.tsx:618-620`) when busy; `RightRailJobNotice` in the rail when busy (`page.tsx:506`) | While `isBusy` or `poll_timeout` | Job-progress is inside the conversation drawer (which auto-opens when busy, `page.tsx:202-206`). The rail shows a static notice only. Reasonable. |
| Poll-timeout recovery | Inside the composer footer as a text strip with two tertiary buttons (`page.tsx:706-722`) | Only when `state === "poll_timeout" && activeJobId` | Buried, the strip is small text under the textarea and the two recovery actions are low-hierarchy tertiary with no padding. This is a rare but important state. See R4. |

---

## 4. EMPTY-STATE AUDIT

Designed empty states (intentional, with a clear next action or a clear "nothing yet" message):

- `PlasmidMapView` no construct: "No construct loaded" + "Submit a design to render the annotated plasmid." (`plasmid-map-view.tsx:29-32`). Designed.
- `ValidationSummary` no report: "No validation report yet. Run a design job to see assembly checks." (`page.tsx:846-853`). Designed message but **no action**, the next action (run a design) lives in the composer; could be implicit, accept.
- `ExportActions` no design: "Complete a design job to enable downloads." (`export-actions.tsx:22`). Designed message but the buttons still render disabled, taking rail space.
- `OutcomePanel` no design: "Complete a design job to report lab results." (`page.tsx:897`). Same, disabled primary button still rendered.
- `MyOutcomesPanel` no outcomes: "No locally known reported outcomes yet. Reports submitted from this browser will appear here." (`page.tsx:779`). Designed message, no action, no button. Best of the empty states.
- `FeatureLegend` no features: "No annotated features returned." (`plasmid-map-view.tsx:129`). Designed.
- Validation/Partial/Missing-report notices inside messages: all designed ResultNotes.

Accidental / chrome empty states (not designed, fake or noise):

- **The two dashed placeholder squares at the bottom of the left nav** (`page.tsx:492-495`). These render as `aria-hidden` bordered empty boxes that visually read as "disabled nav buttons." There is no future-feature they communicate; they are wireframe residue. See R1.

Wireframe-y always-on rail pre-design:

- At idle (no `sessionId`, no design), the right rail shows four cards, PendingPromptFetchMessage (only on fetch error), ValidationSummary (empty), ExportActions (disabled), OutcomePanel (disabled), MyOutcomesPanel (empty). The rail is dominated by disabled affordances before the user has done anything. See R11.

---

## 5. RECOMMENDED CONSOLIDATIONS

Recommendations are grouped. Each is specific and uses actionable verbs. None removes a capability; only surfaces and placements change.

### R1. Remove the duplicate conversation toggle and the placeholder squares from the left nav.
- Remove the icon button `aria-label="Toggle conversation"` at `apps/web/app/page.tsx:480-491` entirely; its action is reachable via the header `Show conversation` / `Hide conversation` button at `page.tsx:464-472`, which is always visible.
- Remove the two decorative dashed squares at `page.tsx:492-495`; they are fake affordances with no function.
- Cascade: if nothing else is planned for the 56px left nav (see Question Q3), collapse the desktop grid from `lg:grid-cols-[56px_minmax(0,1fr)_320px]` to `lg:grid-cols-[minmax(0,1fr)_320px]` and drop the `<nav>` entirely. This removes a whole column of dead chrome.

### R2. Reuse `ExportActions` on mobile instead of the hand-rolled duplicate.
- Delete the bespoke mobile export strip at `apps/web/app/page.tsx:521-538` (the standalone `GenBank` and `FASTA` buttons).
- Render `<ExportActions designId={designId} status={exportStatus} error={exportError} disabledReason={isBusy ? "..." : null} onExport={handleExport} />` in the mobile stack in its place (it is a responsive `grid-cols-2` already, at `export-actions.tsx:26`).
- Effect: one source of truth for export UI; deletes ~17 lines of duplicate JSX and a duplicate disabled/hover recipe.

### R3. Collapse each "close" cluster to a single affordance.
- Remove the `Hide` button in the conversation drawer header (`apps/web/app/page.tsx:568-574`). The drawer is closeable via the header `Hide conversation` button (still visible while the drawer is open), the scrim at `page.tsx:553-559`, and the Escape handler at `page.tsx:209-220`.
- Remove the ModalFrame top-right `Close` button (`apps/web/components/outcome-report-modal.tsx:366-368`). The footer `Close` at `outcome-report-modal.tsx:288-290` and the Escape handler at `outcome-report-modal.tsx:317-323` already close the modal. One Close per modal.
- Effect: two redundant secondary Close buttons removed.

### R4. Promote `Check status` from tertiary to secondary; keep `Start over` tertiary.
- At `apps/web/app/page.tsx:713-715`, `Check status` is the primary recovery action for a timed-out job, it is the path the user *should* take. Render it as a secondary button (`border border-line-strong text-ink bg-paper rounded-md px-sm py-2xs hover:bg-mist` + focus ring) instead of bare `text-coral`.
- Keep `Start over` (`page.tsx:716-718`) as tertiary text-only `text-ink hover:text-coral`, but add the standard small padding (`px-xs py-2xs`) so its click target matches the rest of the app (see R7).
- Effect: one tertiary recovery pair becomes one secondary + one tertiary, with a clear "do this first" hierarchy.

### R5. Resolve the medium-width "Inspect" path (judgment call).
- The `Inspect` button (`apps/web/app/page.tsx:457-463`) only exists for the 768-1023px band (`md:inline-flex lg:hidden`). Below 768 the rail is stacked inline; above 1023 the rail is permanent. It exists purely to surface the rail at a transitional width.
- Option A: Remove `Inspect` and the `inspectOpen` drawer entirely; at medium widths, render the rail stacked below the map the same way mobile does (`page.tsx:516-548`). One layout for `<lg`, one for `lg+`. Simpler, fewer affordances.
- Option B: Keep `Inspect` at medium widths only, and accept the transitional drawer.
- **Recommendation: Option A.** It removes one header button, the entire `inspectOpen` drawer (`page.tsx:626-657`), its backdrop, and its `Close` button, and eliminates a whole media-query special case. Flagged for the human in Question Q1 because it cascades into the responsive layout decision and may conflict with a design intent to keep the map at full height between 768 and 1023px.

### R6. Demote `Review or edit outcome` in `MyOutcomesPanel` from primary to secondary.
- At `apps/web/app/page.tsx:772-774`, each historical outcome card renders a `bg-coral` primary. With several outcomes, the rail stacks multiple coral primaries, which violates the design_system rule "Reserved for the one primary action in any panel/modal."
- Demote to secondary (`border border-line-strong text-ink bg-paper hover:bg-mist`) so the only coral primary on the rail's outcome surfaces is the current-design `Report outcome` / `Review or edit outcome` button in `OutcomePanel` (`page.tsx:902-909`).
- Effect: coral is reserved for the *current* design's primary action; historical items read as the edit/recovery actions they are.

### R7. Standardize tertiary hover and click-target recipes.
- Every tertiary `text-coral` affordance uses `hover:underline`. Concretely, add `hover:underline` to:
  - `View plasmid map` link (`apps/web/app/page.tsx:611`).
  - `Check status` once promoted (see R4), no longer applies as tertiary.
- Change the consent toggle's `hover:text-coral/80` (`outcome-report-modal.tsx:272`) to `hover:underline` to match the rest of the tertiary `text-coral` family.
- Give the bare-text recovery buttons (`Check status` before R4, `Start over`) the standard `px-xs py-2xs` padding so their hit area matches every other button in the app.

### R8. Keep GenBank and FASTA as two secondary buttons (judgment call).
- With only two export formats, collapsing them into a single `Export` overflow menu would add a click for no compression. Recommendation: **keep**. Flagged because the brief invited overflow menus: here, two buttons is the right floor.

### R9. Tone down the example-prompt chips.
- At `apps/web/app/page.tsx:668-678`, the example prompts are bordered chips with `hover:bg-mist`, which is the secondary recipe. They are onboarding hints, not actions. Recommendation: keep the border but switch the hover to a tertiary `hover:text-coral` on the prompt text so they read as suggestions, not as secondary buttons competing with the header's `Show conversation` secondary.

### R10. Outcome consent confirmation button, judgment call.
- The `Submit without training consent` / `Consent choice reviewed` button at `apps/web/components/outcome-report-modal.tsx:272-274` only matters in the narrow case where a user wants to submit without checking the consent box; the checkbox `onChange` already sets `consentReviewed=true` in every other case.
- Option A: Remove the button; auto-set `consentReviewed=true` on the first submit attempt (when the user has touched the checkbox at all) and surface an inline "Confirm you are submitting without training consent" message instead.
- Option B: Keep the button as the explicit consent-without-training gate, but fix its hover recipe per R7.
- **Recommendation: Option B.** Consent is a legal/ethical gate; an explicit affordance is defensible. Flagged for the human in Question Q2 because it bears on whether the product wants an explicit consent-action or an implicit one.

### R11. Hide disabled primary/secondary affordances until a design exists.
- At idle (no `designId`), the right rail renders `ExportActions` with two disabled GenBank/FASTA buttons (`page.tsx:508`, always rendered) and `OutcomePanel` with a disabled `Report outcome` primary (`page.tsx:509`, always rendered). Both panels keep their explanatory empty-state copy.
- Recommendation: hide the **buttons** themselves until `designId` is set, and keep the panel + its "Complete a design job to..." message. The message already tells the user what to do; a disabled primary button next to it is redundant chrome.
- Concretely:
  - In `ExportActions` (`export-actions.tsx`), render the `grid grid-cols-2` block of `ExportButton`s only when `designId` is truthy; otherwise render only the headline + helper paragraph.
  - In `OutcomePanel` (`page.tsx:885-912`), render the `<button>` only when `designId && !disabledReason`; keep the descriptive `<p>` always.
- Effect: pre-design rail shows two informational cards instead of two informational cards *plus* four disabled buttons. Fewer affordances visible until each is actionable.

### R12. Hide `MyOutcomesPanel` entirely when its list is empty and there is no design yet.
- At `page.tsx:510`, `MyOutcomesPanel` renders even when `outcomes.length === 0`, showing an empty card with "No locally known reported outcomes yet." That card adds rail height before the user has done anything.
- Recommendation: hide the panel when `outcomes.length === 0` and `designId === null`; show it once the user either has reported an outcome *or* has a current design (where they might report one). The `OutcomePanel` already covers the "you can report outcomes" message for the current design.
- Effect: one fewer always-on card in the idle rail.

### R13. Hide `ValidationSummary` entirely until a validation report exists.
- The empty `ValidationSummary` ("No validation report yet. Run a design job...") at `page.tsx:846-853` competes for rail space before any job runs and duplicates what the composer placeholder already implies.
- Recommendation: render `ValidationSummary` only when `latestResult?.validation_report` is non-null. The composer's `Design` button is the next action, not a button in this empty card.
- Effect: the idle rail is reduced from four cards to one (`OutcomePanel` informational only once export/outcome buttons are hidden per R11), making the first-run surface read as "describe a design" rather than a panel of disabled controls.

---

## Summary of changeset shape

- Removed affordances: 5 (left-nav toggle icon, two placeholder squares, conversation-drawer `Hide`, modal top-right `Close`). Plus R5 Option A would remove `Inspect` header button + inspect drawer backdrop + inspect `Close`.
- Relocated / re-hierarchied: 3 (`MyOutcomesPanel` per-card primary demoted to secondary; `Check status` promoted to secondary; mobile export buttons replaced by `ExportActions` component).
- Hidden until relevant: 4 (export buttons, outcome button, `MyOutcomesPanel` empty, `ValidationSummary` empty).
- Hover/padding consistency fixes: 4 tertiary affordances.

Net effect: the right rail at idle goes from four cards + four disabled buttons to informational panels that gain their buttons only when actionable; the left nav either collapses to nothing or holds one real item (Q3); every "close" cluster has exactly one affordance; the outcome modal has one primary and one secondary in its footer and nothing else.

---

## Questions for the human

- **Q1 (cascades into responsive layout):** Follow R5 Option A and remove the `Inspect` header button + `inspectOpen` drawer entirely, stacking the rail below the map at all widths below `lg`? Or keep the medium-width drawer so the map can stay full-height between 768 and 1023px?
- **Q2 (consent semantics):** Keep the explicit `Submit without training consent` confirmation button (R10 Option B), or remove it and auto-confirm consentReviewed on first submit when the checkbox has been touched (R10 Option A)? This is a consent-UX semantics decision, not a styling one.
- **Q3 (left nav future):** Is the 56px left icon-nav intended to gain real surfaces later (history, settings, help), or is it only ever going to hold the conversation toggle? If the latter, remove the entire `<nav>` column at `page.tsx:479-496` and drop the first grid track. If surfaces are planned, keep the column but only after R1 removes the placeholders.

(Recommend flagging Q1, Q2, Q3 in PROGRESS.md for human input before IMPL begins.)