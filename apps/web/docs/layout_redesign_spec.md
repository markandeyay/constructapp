# Plasmid-Centered Layout Redesign Spec

Status: SPEC, for IMPL-2 to implement on branch `visual-redesign`.
Author: LAYOUT-1.
Scope: `apps/web/app/page.tsx` layout, `apps/web/components/plasmid-map-view.tsx` container sizing, and the supporting panel chrome. Does NOT touch `services/api/`, the API client (`apps/web/lib/api`), or any business logic in handlers. IMPL-2 reorganizes WHERE components live; handlers, state, and props are preserved as-is.

## Core principle

The plasmid map is the visual centerpiece. Everything else (chat, exports, outcomes, validation) is supporting chrome that orbits the map. The map should occupy the dominant central canvas; the composer and panel chrome should feel like toolbars and inspectors around it, not peers competing for the top of the page.

Reference mental models: Figma's canvas-centered layout (large central canvas, slim panes at the edges) and Linear's content-centered layout (one dominant content region, sparse chrome). We are not building a Figma clone; we are adopting the size relationship: one large thing, several small things around it.

---

## 1. Where the chat composer lives

**Decision: bottom docked composer, full width, persistent. Not a drawer, not a sidebar, not a modal.**

The composer is a horizontal dock anchored to the bottom edge of the viewport across all breakpoints, spanning the full width of the content area (between the left panel and the right inspector on large desktop; full width on mobile/tablet). It is always visible while designing; it does not expand/collapse.

Rationale, evaluated against the five options:

- (a) Bottom drawer that expands mid-conversation, Rejected in favor of a persistent dock. A drawer that hides the composer until "expanded" fights the conversational nature of the tool: refinement is the primary action, and hiding the entry point reduces the perceived responsiveness that a research tool needs during long polling loops. The "bottom" instinct is correct; the "drawer" framing is not. Keep it bottom, keep it always-present.
- (b) Left sidebar narrower than current, Rejected. A vertical sidebar competes with the map for horizontal space, which is exactly what we are trying to give the map. It also forces a portrait composer that is awkward for multi-line prompts.
- (c) Right sidebar, Rejected for the same horizontal-competition reason, and because the right side must remain available for the inspector panels (export, outcome, validation).
- (d) Floating panel, Rejected. A floating composer overlays the map and forces stacking-order management. It also breaks keyboard flow because a floating element signals "temporary."
- (e) Modal overlay with persistent thread visible elsewhere, Rejected. Modal-on-modal conflicts with the existing `OutcomeReportModal`, and a conversation tool's input is not a one-shot interaction.

The bottom dock matches the human's stated default ("bottom is a strong default"), matches the chat/composer pattern researchers already know from ChatGPT/Claude, and crucially leaves the entire upper viewport free for the map to dominate. The composer is the floor; the map is the stage above it.

The composer retains its current internal structure from `page.tsx`: the clarification banner (when `state === "awaiting_clarification"`), the example-prompt chips (when `idle` and no `sessionId`), the `Experimental goal` textarea (`id="goal"`), the submit button whose label cycles through Design/Refine/Answer/Starting/Designing, and the poll-timeout `Check status` / `Start over` controls. None of this changes; only the container moves.

The "Design workspace" heading (`#design-workspace-title`) currently lives on the left `<section>`. In the new layout it graduates to a slim top app bar (see section 5) so it stays a reachable landmark for the E2E test that asserts `heading "Design workspace"`.

---

## 2. How chat history surfaces

**Decision: chat history is a dismissible, non-modal overlay panel that slides up FROM the composer, covering the lower ~55% of the map area. It is NOT permanently visible. The composer's resting state shows only the input; the thread is on demand.**

This is the load-bearing structural decision and it directly serves the centerpiece directive. Permanent chat history would steal vertical space from the map every turn, shrinking the centerpiece to make room for text that is only interesting when you choose to read it. Instead:

- The map owns the canvas when the user is designing/looking. The composer's resting state is a single-line (expanding to 3-line) input at the bottom with a small "Show conversation" affordance (a chevron button or a "N messages" pill) sitting at the top-left edge of the composer dock.
- Opening chat history lifts a panel up from the composer. The panel is a card with a translucent scrim behind it (so the map is faintly visible and clearly still present), anchored to the bottom dock, occupying roughly 55% of viewport height and the content width between the left rail and right inspector. It contains the full message thread: user prompts, clarification answers, design-agent result messages, system status, errors, the inline validation-report sub-panels, retrieved-templates sub-panels, partial-result notices, and the "View plasmid map" link per result message.
- The thread panel is dismissed by clicking the same affordance, pressing Escape, or clicking the scrim. The composer input remains usable while the thread is open (the thread sits above the input row).
- While a job is busy (`submitting` / `polling`), the thread auto-opens to surface the `JobProgressCard` and any status messages, because that is the moment the user wants to read what is happening. When the job completes or errors, the thread stays open for 1.5s then auto-collapses unless the user has interacted with it, so the map reclaims focus for the new result. (The 1.5s is a soft target; IMPL-2 may tune.)
- The poll-timeout state (`poll_timeout` with an active job) keeps the thread open, because the user needs to see the `Check status` / `Start over` controls and the explaining system message.

Why a slide-up overlay rather than a separate page or a persistent column: a separate page breaks the "map stays in view while I read the thread" need; a persistent column re-introduces the horizontal competition we rejected for the composer. The overlay is the only option that both (a) gives the thread real estate when wanted and (b) yields that real estate back to the map the instant it is not wanted.

**Question for the human (Q1):** The auto-open-on-busy / auto-collapse-on-complete behavior is a recommended default, not a hard cascade risk. If you prefer the thread to ONLY open on explicit user action (no auto-open during polling), say so, the structure above works either way; only the timing rules change. Context to decide: researchers running long jobs may prefer passive progress in the thread, but others may find auto-open intrusive when they want to watch the map. Decide based on whether this tool is used "watch the job run" style or "fire and come back later" style.

---

## 3. How the plasmid map breathes

The map is the single largest element on screen at every breakpoint at or above tablet. Surrounding chrome (top app bar, left rail, right inspector, bottom composer) is intentionally thin so the map's container is the dominant rectangle.

**Adjacent layout (large desktop):** a three-column grid inside the viewport minus the top bar and bottom composer:
- Left rail (collapsed-ready): 56px collapsed / 240px expanded. Holds session list + thread toggle + map navigation. See section 5.
- Center canvas: flexible, hosts the `PlasmidMapView` container and nothing else competing.
- Right inspector: 320px fixed. Holds export, outcome, my-outcomes, validation-summary, job-notice. Scrollable independently.

**What lives directly adjacent to the map:**
- Validation report: NOT inline in the message thread only. A compact `ValidationReportPanel` summary (overall badge + check count) renders in the right inspector under the map context, so the map and its validation verdict are co-visible without scrolling the thread. The full per-check list remains inline in the message thread (when opened) for the existing E2E assertion on `"Assembly completeness"` text.
- Feature list (the `FeatureLegend` inside `PlasmidMapView`): stays inside the map component, directly below the SeqViz canvas, as today. It scrolls independently within the center canvas. This keeps the map and its annotation table co-located and keeps the E2E `region "Feature list"` + `"CMV promoter"` assertions working without selector changes.
- Export actions: right inspector, directly under the validation summary, so "Download GenBank / FASTA" is one glance away from the map. The E2E `region "Export actions"` + `button "GenBank"` assertions apply unchanged.

**Map container heights (SeqViz reads height from its container):**

SeqViz currently keys off `h-[360px] sm:h-[440px] lg:h-[520px]` on the inner `data-testid="seqviz-map"` div. The redesign replaces these fixed pixels with a flex-filled container so the map expands to fill the center canvas. IMPL-2 must change the `seqviz-map` div to use `h-full` and ensure its parent chain provides the resolved height. Recommended resolved container heights (the actual computed pixel height the SeqViz div should receive, target, not exact):

- Large desktop (1440+), 900px tall viewport: map container ~620px tall, ~960px+ wide. The SeqViz `both` viewer (circular + linear) needs width >= ~640px to render both panes comfortably; at 1440 the center canvas is ~960px after 56px rail + 320px inspector + gutters, which fits.
- Medium desktop (1024-1440), 800px tall viewport: map container ~520px tall, ~600-720px wide. Still enough for the `both` viewer; if width drops below 640px the viewer gracefully falls back to a single pane (SeqViz handles this).
- Tablet (768-1024): see breakpoint section. Map container ~420px tall.
- Mobile (<768): map container ~50-55% of viewport height when map is primary.

The empty-state ("No construct loaded") placeholder replaces its fixed `h-64 sm:h-80 lg:h-96` with `h-full` so the placeholder canvas matches the populated map's footprint.

Width treatment: the center canvas is `min-w-0` (the current code already uses `minmax(0,1fr)`, preserve that flexbox correctness) so the map cannot push the inspector off-screen.

---

## 4. Breakpoint layouts

### Large desktop (1440+)
Grid: `[left rail 56-240px] [center canvas 1fr] [right inspector 320px]`, with a 48px top app bar and a 96px bottom composer dock.

- Left rail: 56px collapsed by default (icons only: thread toggle, session list toggle, brand mark). Expands to 240px on demand to show session list and plasmid-map nav. Collapsed-by-default is deliberate: it maximizes the map on the screens that can most afford a big map.
- Center canvas: map container target 620px tall, ~960px wide. Single focus.
- Right inspector: 320px, vertically scrollable, holds job-notice, validation summary, export, outcome, my-outcomes in that top-to-bottom order.
- Bottom composer: full-width-of-content-area dock, ~96px tall (textarea 3 rows + button row). Thread overlay rises from here.

### Medium desktop (1024-1440)
Same three-column grid, but:
- Left rail: 48px collapsed, 220px expanded.
- Right inspector: 296px.
- Map container target 520px tall, ~600-720px wide.
- Bottom composer unchanged.
- Thread overlay occupies the middle 70% of content width (rail and inspector stay visible) to avoid clobbering the inspector on narrower widths.

### Tablet (768-1024)
Two-region layout: the left rail collapses into a hamburger in the top app bar; the right inspector collapses into a slide-over from the right edge, opened by an "Inspect" button in the top bar.

- Map container target ~420px tall, full content width.
- Bottom composer: full width, ~88px.
- Inspector as slide-over: 320px wide, pushes from right, with a scrim. Exports / outcome / validation / my-outcomes all live here so they remain reachable (E2E depends on `region "Export actions"` and `button "GenBank"` being reachable; in tablet they are reachable via the Inspect button).
- Thread overlay rises from the composer and spans full content width.

### Mobile (under 768), map and chat alternate as primary views
This is the second structural decision (flagged for human review, see Q2).

Mobile uses a single primary surface with a segmented control in the top app bar offering two views: **Map** (default after a result lands) and **Chat**. A bottom composer dock is always pinned to the bottom regardless of which view is active, because the composer is the action surface for refinement and must never be hidden behind a tab switch.

- Default view before any result: Chat (so the welcome message + example prompt chips are the initial surface; matches current first-paint behavior and the E2E flow where the user fills the goal and clicks Design on first load).
- When a job completes and an `annotated_sequence` lands, auto-switch to Map view so the centerpiece shows immediately. The composer remains pinned. The "View plasmid map" result link (E2E-asserted) becomes the manual way to hop to Map view from Chat view.
- Reverse hop: a "View conversation" chip at the top of the Map view (and the same segmented control) switches back to Chat.
- Inspector panels (export, outcome, validation, my-outcomes, job-notice): collapse into a bottom-up sheet opened by a "More" pill in the top bar. The E2E small-viewport test clicks `link "View plasmid map"` then asserts map heading, accessible summary, feature list, `region "Export actions"`, `button "GenBank"`, then `button "Report outcome"` and the dialog heading. Under the new mobile layout:
  - "View plasmid map" link switches to Map view (preserved as a link with that exact text).
  - "Plasmid map" heading remains the `#plasmid-map-title` (or `#plasmid-map-title-empty`) heading inside `PlasmidMapView`; unchanged.
  - "Accessible map summary" and "Feature list" remain inside `PlasmidMapView`; unchanged.
  - "Export actions" region and "GenBank" button: reach them by opening the "More" sheet. The E2E test currently scrolls/clicks directly; VERIFY-1 should add a step to open the "More" sheet before asserting export buttons, OR IMPL-2 should pin a compact export row directly under the map on mobile (see below decision).
- Decision (mobile export row): to avoid forcing the E2E test through an extra sheet-open step, pin a compact, always-visible Export row directly below the map on mobile (GenBank + FASTA buttons only, no headers). The full `ExportActions` region moves into the "More" sheet for tablet/desktop parity, but a slim mirror of the two buttons stays pinned on mobile under the map. This keeps `button "GenBank"` reachable without any new interaction. IMPL-2 must ensure the buttons are not duplicated-on-screen (the slim row replaces the full region on mobile).

**Question for the human (Q2):** The mobile Map/Chat segmented toggle is a recommended default but is a genuine cascade risk: the current E2E test (`design-workspace.spec.ts`, "small viewport..." test) assumes a linear scroll where the map link and the export region are on the same page without a view switch. Two options:
  (i) Keep the Map/Chat segmented control as described, and have VERIFY-1 update the small-viewport E2E to add `More` sheet open + the segmented control hops as needed.
  (ii) On mobile, instead of a toggle, stack Map-then-Chat in a single scroll (map first, composer pinned at bottom, inspector as bottom sheet), preserving a linear page so the existing E2E selectors keep working with minimal changes.
Both are defensible. (i) is more app-like and matches the "map is centerpiece" spirit on mobile; (ii) is lower-risk for tests and closer to the current behavior. Please pick. Default if you do not answer: (ii) the single-scroll stack, because it preserves E2E reachability and the composer is already pinned at the bottom so the map still reads as the top-of-page centerpiece.

---

## 5. Auxiliary panels placement

- **Top app bar (new):** 48px tall on desktop/tablet, 56px on mobile. Holds, left-to-right: brand mark ("Construct"), the `Design workspace` heading (relocated from the left `<section>` so the landmark E2E assertion `heading "Design workspace"` still passes), the mobile Map/Chat segmented control (mobile only), the Inspect button (tablet only) / More pill (mobile only), and a thread-toggle button mirroring the composer's "Show conversation" affordance. This is the only fixed top chrome.
- **Left rail (desktop):** collapsed icon rail (56px) by default expanding to 240px. Hosts the session list when it exists. NOTE: the current app has no session-list UI, `sessionId` is held in state but there is no session browser. The left rail's session list is therefore a forward-looking slot: IMPL-2 should render the rail with the thread-toggle and map-nav icons now, and leave a clearly-marked placeholder region for a future session list. Do NOT build a session list; just allocate the space. The current scope has no multi-session UI to place.
- **Right inspector (desktop/tablet-as-slide-over/mobile-as-bottom-sheet):** top-to-bottom order inside the inspector:
  1. `RightRailJobNotice` (only while busy), keep its `role="status"` semantics.
  2. Validation summary (compact: overall badge + check count + link to open thread at the full report). The full `ValidationReportPanel` per-check rendering remains inline in the thread as today.
  3. `ExportActions` (full region; on mobile the slim mirror row is pinned under the map, and the full region is omitted from the More sheet to avoid duplicate-on-screen buttons).
  4. `OutcomePanel` (the "Report outcome" / "Review or edit outcome" button, E2E-asserted; must remain a `button` with that exact label).
  5. `MyOutcomesPanel` (`region "My reported outcomes"`, E2E-asserted; preserve the `aria-label`).
  - `PendingPromptFetchMessage` (the error case for fetching pending prompts) renders at the top of the inspector when present.
- **PendingOutcomeToast:** Confirmed as-is for positioning. The current classes are `fixed left-4 right-4 top-4` on small screens and `sm:bottom-4 sm:w-[calc(100%-2rem)] sm:max-w-md` (so bottom-right from `sm` upward). Keep this exactly. It is viewport-fixed and therefore independent of the new layout grid; it overlays cleanly on top of both the map and the composer. The E2E `getByLabel("Pending outcome prompt")` selector keeps working. No change.
- **OutcomeReportModal:** Unchanged. Rendered at the page root, portal-style, full-screen scrim + dialog. The E2E asserts `dialog heading "What happened in the lab?"`. Keep the dialog semantics and heading. Independent of layout grid.

---

## 6. Component placement table

Mapping each existing component (as named/used in `apps/web/app/page.tsx` and `apps/web/components/*`) to its new home. IMPL-2 follows this table.

| Component (current name / selector) | Large desktop (1440+) | Mobile (<768) |
|---|---|---|
| `Design workspace` heading (`#design-workspace-title`, E2E-asserted) | Top app bar, centered-left after brand | Top app bar, after brand |
| Conversation message thread (the `messages.map` block in `page.tsx`) | Slide-up overlay from bottom composer dock, ~55% viewport height, summoned by thread toggle; auto-opens while busy | Chat view (segmented control), full-screen surface above the pinned composer |
| Composer textarea + submit (`#goal`, submit button, example chips, clarification banner, poll-timeout controls) | Bottom composer dock, full content width, persistent | Bottom composer dock, full width, persistent (always pinned, both Map and Chat views) |
| `RightRailJobNotice` (busy-state notice) | Right inspector, top | "More" bottom sheet, top |
| `PlasmidMapView` (the `#plasmid-map` section) | Center canvas, container ~620px tall, ~960px wide | Map view primary surface, container ~50-55% viewport height, full width |
| `FeatureList` / `FeatureLegend` (inside `PlasmidMapView`, `region "Feature list"`) | Stays inside `PlasmidMapView`, below the SeqViz canvas | Stays inside `PlasmidMapView`, below the SeqViz canvas |
| `ExportActions` (`region "Export actions"`, `button "GenBank"`/`"FASTA"`) | Right inspector, under validation summary | Slim pinned row under the map (GenBank + FASTA buttons only); full region in "More" sheet is omitted to avoid duplicate buttons |
| `OutcomePanel` (`button "Report outcome"`/`"Review or edit outcome"`) | Right inspector | "More" bottom sheet |
| `MyOutcomesPanel` (`region "My reported outcomes"`) | Right inspector, bottom | "More" bottom sheet |
| `PendingOutcomeToast` (`aria-label "Pending outcome prompt"`) | Viewport-fixed bottom-right (from `sm` breakpoint), unchanged | Viewport-fixed top-spanning (small-screen rule), unchanged |
| `OutcomeReportModal` (dialog, heading "What happened in the lab?") | Page-root modal, unchanged | Page-root modal, unchanged |
| `ValidationReportPanel` (full per-check list, inline in thread) | Stays inline in the thread overlay | Stays inline in the Chat view thread |
| Validation summary (NEW compact badge+count, derived from `latestResult.validation_report`) | Right inspector, above export | "More" bottom sheet, above export |
| `RetrievedTemplatesPanel`, `PartialResultNotice`, `MissingValidationReportPanel`, `JobProgressCard` | Stays inline in the thread (they are children of message articles) | Stays inline in the Chat view thread |
| "View plasmid map" link (per-result `<a href="#plasmid-map">`) | Stays inline in each result message in the thread; clicking scrolls/switches focus to the center canvas map | Stays inline in each result message in the Chat view; clicking switches to the Map view (segmented control hops to Map) |
| `PendingPromptFetchMessage` | Right inspector, very top when present | "More" sheet, very top when present |
| Left rail (NEW: thread toggle, map nav, session-list placeholder) | 56px collapsed / 240px expanded | Hamburger in top app bar (rail does not render as a column on mobile) |
| Top app bar (NEW: brand + `Design workspace` heading + view toggles + Inspect/More) | 48px tall | 56px tall |

### Notes for VERIFY-1 (test impact)

- The `heading "Design workspace"` assertion still passes (heading relocated to top app bar, same text).
- The `link "View plasmid map"` assertion still passes (link preserved inline in result messages).
- The `heading "Plasmid map"` assertion still passes (heading preserved in `PlasmidMapView`).
- The `text "Accessible map summary"` and `region "Feature list"` + `text "CMV promoter"` assertions still pass (both stay inside `PlasmidMapView`).
- The `region "Export actions"` + `button "GenBank"` assertions: on large desktop the full `ExportActions` region remains in the right inspector and the assertions pass as-is. On the small-viewport test (390x844), the slim pinned export row provides `button "GenBank"`; VERIFY-1 should confirm whether the slim row carries the `aria-label="Export actions"` region wrapper or whether the assertion needs scoping to the pinned row. Recommended: the slim pinned row is wrapped in a `region aria-label="Export actions"` too, so both selectors pass on mobile without test changes.
- The `button "Report outcome"` assertion (small-viewport test, before the dialog): the button lives in the "More" bottom sheet on mobile. The existing test does NOT click "More" first. If Q2 answer is (ii) single-scroll stack, the `OutcomePanel` stays on-page and the assertion passes unchanged. If Q2 answer is (i) segmented toggle, VERIFY-1 must update the small-viewport test to open the More sheet before clicking "Report outcome".
- The `dialog heading "What happened in the lab?"` assertion is unaffected (modal unchanged).
- The `"Pending outcome prompt"` toast assertion is unaffected (toast positioning unchanged).
- The `"My reported outcomes"` region assertion is unaffected (aria-label preserved); on mobile it is inside the More sheet, if Q2 is (i), VERIFY-1 must open More before asserting; if Q2 is (ii), unchanged.
- The `"Submit a design to render the annotated plasmid."` empty-state assertion is unaffected (text preserved inside the empty-state branch of `PlasmidMapView`).

---

## Questions for the human

**Q1, Thread auto-open timing (low cascade risk):** Should the conversation thread auto-open during busy states (`submitting`/`polling`) and auto-collapse ~1.5s after completion, or should it open ONLY on explicit user action with no auto behavior? Recommended default if no answer: auto-open on busy, auto-collapse on complete, EXCEPT in poll_timeout where it stays open. Context: this is a timing/UX rule, not a structural one; either answer works with the layout above.

**Q2, Mobile layout structure (HIGH cascade risk for E2E):** On mobile, should the layout use (i) a Map/Chat segmented control with the inspector in a "More" bottom sheet (more app-like, centerpiece-first, but forces E2E updates for the small-viewport test), or (ii) a single-scroll stack with the map at top, composer pinned at bottom, inspector panels as a bottom sheet opened on demand (lower-risk, keeps existing E2E selectors working with minimal changes)? Recommended default if no answer: (ii) single-scroll stack, because it preserves E2E reachability and the composer-pinned-at-bottom already makes the map the top-of-page centerpiece on mobile.