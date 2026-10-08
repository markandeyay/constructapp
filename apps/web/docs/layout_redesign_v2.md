# Cursor-Style Three-Pane Layout Redesign Spec (v2)

Status: SPEC, for IMPL-LAYOUT-1, IMPL-CHAT-1, IMPL-INSPECTOR-1 to implement on branch `visual-redesign`.
Author: LAYOUT-2.
Supersedes: `apps/web/docs/layout_redesign_spec.md` (v1, map-centric with bottom composer + slide-up thread overlay). v1's slide-up thread overlay and full-width bottom composer are **removed**. The chat thread becomes a **persistent right panel** (Cursor IDE spatial organization), and the composer lives inside that panel.
Scope: `apps/web/app/page.tsx` shell layout and the panel chrome that hosts existing components. Does NOT touch `services/api/`, the API client (`apps/web/lib/api`), handlers, state, or props. IMPL subagents reorganize WHERE components live; business logic is preserved.

## Core principle

Anthropic colors and typography (warm cream, paper, ink, coral, Newsreader/Inter, 4px spacing, 6/10/14 radius, warm shadows, unchanged from `design_system.md`), Cursor's spatial organization:

- **Left sidebar** (narrow, supporting context): navigation + session design history + the user's saved library.
- **Center canvas** (dominant): the plasmid map. The artifact the researcher is here to look at. Nothing competes with it except a thin tools strip directly beneath.
- **Right chat panel** (persistent): the conversational interaction home, message thread above, composer below. Always visible on desktop. Not a popup, not a slide-up overlay.
- **Top bar** spans all three panes: branding, the current design / session indicator, account/settings.
- **Bottom status bar** (Cursor-style) spans all three panes: job status, connection, model.

The design system stays. Only the layout changes.

---

## 1. LEFT SIDEBAR

**Decision: this is a single-view tool, not a multi-session app. The left sidebar hosts the current session's design history + a "New design" action + the user's reported-outcomes library. No multi-session browser is built.**

### Evaluation of the flagged options

- **Multi-session conversation history browser:** REJECTED as a built feature. The current app holds `sessionId` in state but has no session-list UI, no backend list endpoint, and no persistence key for sessions. Building a session browser for a demo tool means fabricating data the API does not return. It would also mis-signal "switch between research projects" when the app supports one active session with refinement turns. A session-list is NOT meaningful enough to build for this tool at this scope.
- **Navigation between core views (Design workspace / My outcomes / Settings):** REJECTED as a multi-view nav. The app has exactly one primary view (Design workspace). `MyOutcomesPanel` is a list panel, not a separate route; `Settings` does not exist. A nav rail with three items where two are sparse/no-ops would be dishonest chrome.
- **Reference panels (corpus statistics, model registry summary):** REJECTED for the left rail. These are curiosity content, not navigation or current-artifact context. If desired later, they belong in a "More"/about sheet, not the rail that anchors the work.

### What GENUINELY belongs here

The sidebar is the **supporting context** for the single artifact on the canvas, mirroring Cursor's file-tree role:

1. **"New design" primary action** (top, full-width button, coral). Clears the current session/message thread and resets to idle. This is the single most-wanted sidebar affordance for a refinement-loop tool (you finish refining one construct, you want to start the next without hunting).
2. **Design history list** (the session's completed designs). Each completed `annotated_sequence` result in `messages` becomes one row: design_id (truncated), one-line recommendation snippet, validation overall badge (PASS/WARN/FAIL pill), and bp count + feature count. Clicking a row sets that result as the `latestResult` shown in the center canvas (this is a pure view-selection, no new API call; the results already live in `messages`). The currently-shown row is highlighted with `mist` fill + `line-strong` left border.
   - This is NOT a session browser across sessions, it is the **current session's result history**. Empty-state: "Designs you complete in this session will list here." Only designs with an `annotated_sequence` render as rows; partial results (no sequence) do not appear as selectable rows but remain in the chat thread.
3. **My reported outcomes** (collapsible, bottom). The existing `MyOutcomesPanel` mounts here in a compact list form, with its `aria-label="My reported outcomes"` region preserved verbatim (E2E-asserted). Collapsible via a `Show / Hide` toggle (default collapsed; expands on demand) so it does not crowd the history list on short viewports.
4. **Brand attribution** as the rail footer, unchanged.

### Sizing

- Large desktop (1440+): **256px** fixed width.
- Narrow desktop (1024-1280): collapses to a **56px icon rail**, the "New design" button becomes a `+` icon button, the history list becomes a vertical stack of small rows showing only the validation badge dot (hover/click reveals a flyout with the row's label), and "My reported outcomes" collapses to a single icon button that opens a flyout drawer. The flyout is a 256px overlay anchored to the rail.
- Tablet (768-1024): collapses entirely into a **hamburger in the top bar**; the rail does not render as a column.
- Mobile (<768): rendered from the same hamburger. See section 6.

### Styling

`bg-paper`, `border-r border-line`, `py-md px-sm`, vertically scrollable internally. The "New design" button uses primary-action tokens (`bg-coral text-paper rounded-md shadow-rest hover:shadow-raised`). History rows use `rounded-sm border border-line bg-paper px-sm py-xs` resting, `bg-mist border-l-2 border-l-coral` selected.

---

## 2. CENTER CANVAS, what is above and below the map

**Decision: the map dominates the canvas. A thin "Design tools" strip sits directly BELOW the map (Option B). Validation report, Export, and Report-outcome live in this strip in compact form; the full per-check validation list and feature detail stay where they already are (feature list inside `PlasmidMapView`; full per-check report inline in the chat thread).**

### Evaluation of the flagged options

- **Tabs above the map (Map | Features | Validation | Export):** REJECTED. Tabs toggle the map away from view for every non-map task. The map is the centerpiece; it must be the resting state, not one of four peers. Tabs also duplicate the feature list that already lives inside `PlasmidMapView`.
- **All in the right panel adjacent to chat:** REJECTED. Outcome/export/validation next to chat turns the right panel into "chat + results", competing for the panel's finite height and forcing the chat thread to scroll constantly under tall validation cards. Chat and results have different rhythms (chat = growing; results = stable per-design); they should not share a column.
- **Inspector strip below the map:** CHOSEN. The map keeps the entire top of the canvas; the strip beneath it is a thin horizontal row (height ~56px desktop / ~48px tablet) that holds the three result-context actions that describe the *current* design. The full `ValidationReportPanel` per-check list remains inline in the chat thread (as today) for both the existing E2E assertion on `"Assembly completeness"` text and because per-check detail is most readable in the conversational context where the agent produced it.

### Above the map

A single thin title row (~32px desktop / 28px mobile): the `#plasmid-map-title` heading ("Plasmid map") left-aligned, plus the topology/bp caption + the Complete/Incomplete pill already rendered by `PlasmidMapView`. This is the existing header inside `PlasmidMapView`; it does not move. No additional chrome is added above the map.

### Below the map, "Design tools" strip

A horizontal strip pinned to the bottom of the center column, above the status bar, separated from the map by `border-t border-line`. Three segments left-to-right, each a cell divided by `border-r border-line`:

1. **Validation cell:** compact `ValidationSummary`, overall pill (PASS/WARN/FAIL) + check-count caption + an "Open full report" link that scrolls the right chat thread to that design's result message (it does NOT open a separate panel; the full report already lives inline in that message). Uses the existing `ValidationSummary` component body but laid out horizontally, no card border (the strip cell provides chrome). `aria-label="Validation summary"` preserved.
2. **Export cell:** the existing `ExportActions` region (`region aria-label="Export actions"`) with the GenBank + FASTA buttons inline (`button "GenBank"`, `button "FASTA"`). E2E-asserted region and buttons preserved verbatim. Laid out as `[GenBank][FASTA]` horizontally.
3. **Outcome cell:** the **Report-outcome button** (`button "Report outcome"` / `button "Review or edit outcome"`, label-cycling per `latestOutcome` as today) plus a tiny outcome status hint (one line: "Outcome reported {date}." / "Have lab results? Record them here." / disabled-message for busy). This is a compact rendering of the `OutcomePanel` action; the descriptive paragraph text from `OutcomePanel` is dropped in favor of the one-line hint to fit the strip height. The button keeps its exact accessible name.

When no design has completed (`designId === null` or `annotatedSequence === null`), all three cells render in their disabled/empty state (validation summary: "No validation report yet."; export: buttons disabled; outcome: button disabled with "Complete a design job to report lab results." caption). The strip is always present so the E2E `region "Export actions"` assertion is satisfied on first paint regardless of state.

### Why this is the focal-artifact-preserving choice

The strip's 56px does not steal meaningful vertical space from a map that targets ~560-620px; the map remains ~85% of the canvas height. Validation/export/outcome describe the *current* design on the canvas, so co-locating them under the map keeps result-vs-artifact glance co-visible without a context switch. The right panel stays purely conversational.

### Map container heights

`PlasmidMapView`'s inner `data-testid="seqviz-map"` div is changed to `h-full` (preserved from v1) and its parent chain resolves a real height. Target resolved heights:

- Large desktop (1440+), 900px viewport: map ~580px tall, ~880-920px wide (256 sidebar + 400 chat + 32px title + 56px tools strip + 48 top bar + 24 status bar at 1440 leaves the canvas ~924px wide and ~772px tall; minus title + strip + map-header + accessible-summary block; the SeqViz `both` viewer needs ≥640px width, comfortably met).
- Narrow desktop (1024-1280): map ~460px tall, ~560-680px wide. At 1024 with 56px rail + 360px chat, the center is ~600px, still renders the `both` viewer; below 640px SeqViz gracefully falls back to a single pane (its existing behavior).
- Tablet (768-1024): map ~400px tall, full column width.
- Mobile (<768): map fills the Map tab area minus a compact tools strip; see section 6.

`center canvas` is `min-w-0` (preserve current flexbox correctness) so the map cannot push the right panel off-screen.

---

## 3. RIGHT CHAT PANEL, persistent, always visible

**Decision: 400px on large desktop, 360px on narrow desktop, persistent (not collapsible on desktop except via an explicit toggle on narrow/tablet widths). Thread above; composer at the bottom of this panel.**

### Width

- Large desktop (1440+): **400px** fixed.
- Narrow desktop (1024-1280): **360px** fixed.

These widths sit in the lower-middle of the 360-440px range that fits a multi-line composer + readable message cards without crowding the map. 400px leaves the center canvas ≥880px at 1440 (the dominant artifact). 440px was rejected as too greedy at 1440 (leaves only ~840px center, still fine but greedier than needed for a thread that is read ≤30% of the time relative to the map). 360px at the low end keeps the chat legible without forcing horizontal scroll on long user prompts.

### Above the thread

A 40px chat header: `Conversation` h2 (Newsreader `h3` size) left + a small "Clear" button (secondary; opens a confirm affordance) right. The header also carries a compact **busy indicator**, when `isBusy`, a coral pulsing dot + "Design running" caption inline in the header (a lightweight mirror of `RightRailJobNotice`, which is REPLACED by this indicator plus the inline `JobProgressCard` in the thread, see component table). No `RightRailJobNotice` card in this panel; the busy indicator in the header + the `JobProgressCard` in the thread cover its function with less panel weight.

### The thread

A scrollable region (flex-1, `overflow-y-auto`, `px-md py-md`, `space-y-sm`) of the same message articles v1 had: user prompts, clarification answers/clarifications, design-agent results, status, errors. Each `message.result` still renders `ValidationReportPanel` / `MissingValidationReportPanel` / `PartialResultNotice` / `RetrievedTemplatesPanel` inline, and a `View plasmid map` link per result message (it scrolls the center map into view on desktop; on mobile it hops to the Map tab).

`JobProgressCard` renders inline at the bottom of the thread when `isBusy` (replaces the separate `RightRailJobNotice` card; the in-thread card already shows job state, elapsed, and job id). `PendingPromptFetchMessage` does NOT render here, it moves to the left sidebar at the top of the rail (it concerns the user's library/follow-ups, which is sidebar context, not chat). See component table.

No auto-open/auto-collapse logic is needed, the thread is always visible. The v1 `threadOpen` state is retired. (If an IMPL subagent prefers to keep a `threadOpen` boolean to drive narrow-desktop/tablet collapse, that is fine, but the desktop default is open and there is no auto-collapse-on-complete behavior.)

### Below the thread, the composer

The composer lives at the bottom of the right chat panel, full width of the panel (NOT full width of the page, this is the v1->v2 change). It is a `<form aria-label="Design composer">` containing, top-to-bottom, in their existing structure (props/handlers unchanged):

1. **The awaiting_clarification banner:** when `state === "awaiting_clarification"` and `activeClarification`, the `border-honey/40 bg-honey/10` card with "Clarification needed: {activeClarification}". Rendering and copy preserved verbatim.
2. **Example prompt chips:** when `!sessionId && state === "idle"`, the `EXAMPLE_PROMPTS` chip row. Rendering preserved.
3. **The textarea + submit row:** `#goal` label (sr-only), the `<textarea id="goal">`, and the submit `<button>` whose label cycles Design / Refine / Answer / Submitting→"Starting" / Polling→"Designing". Internal layout switches to **vertical** at this panel width: textarea above (full panel width, `rows={3}`), submit button full-width below. (The current `sm:flex-row` becomes `flex-col` to fit a ~380px column, a horizontal layout at 380px would leave the textarea ~260px, too narrow for multi-line prompts.)
4. **The poll-timeout controls row:** when `activeJobId && state === "poll_timeout"`, the "Job {id} is still queued…" caption + `Check status` and `Start over` links. Rendering and text preserved.

The composer form is wrapped in `border-t border-line bg-paper px-md py-md` and pinned to the bottom of the right column (sticky/flex-end). The textarea uses `rounded-md border border-line bg-paper px-md py-sm ... focus:ring-2 focus:ring-coral/40` from the design tokens.

### Narrow desktop / tablet collapse

- At **narrow desktop** the chat panel stays persistently visible at 360px (no collapse button shown, 360px is genuinely affordable down to 1024).
- At **tablet (768-1024)** the right chat panel can be toggled by an explicit `Chat` button (icon + label) in the top bar; default open at the wide end of the tablet range, default closed below ~880px where the canvas needs more room. When closed, the center column gains the width; the composer is not reachable until the panel reopens. This is the one breakpoint where the panel is not always-on; flag for UX review (UX-AUDIT-1) whether the toggle should default open or closed below 880px, see flag (c).

---

## 4. TOP BAR

**Decision: 48px tall across all three panes on desktop/tablet, 52px on mobile. Construct wordmark left; current design / session indicator center; settings/account right.**

- Height: **48px** (desktop/tablet), **52px** (mobile). `bg-paper border-b border-line flex items-center px-md`.
- **Left:** the `Construct` brand wordmark (`Construct` with `AI` in coral, Newsreader `h2`, tracking-tight). Immediately after it, a thin `h-6 w-px bg-line-strong` divider, then the relocated **Design workspace** heading `<h1 id="design-workspace-title">Design workspace</h1>` at `font-serif text-h3 text-ink` (preserves the E2E `heading "Design workspace"` assertion, the heading now lives in the top bar, not in the left section). Hidden on `<sm` to make room for the mobile segmented control.
- **Center:** a centered block showing the current design indicator when a design is active: `<span>design-1</span>` (design_id, truncated mono-style, `text-small text-slate`) + the validation overall pill (PASS/WARN/FAIL), small. Before any design: an italic `text-slate` "no active design" hint, or simply empty. On mobile this center slot is occupied by the Map/Chat segmented control (see section 6), and the design indicator moves into the left sidebar header. Aria: the centered indicator is `aria-live="polite"` so the screen-reader announces design changes.
- **Right:** on desktop/tablet, a `Settings` icon button (gear; opens an about/settings sheet, content TBD, currently just a `BrandAttribution`-style info block + connection state); on tablet, the `Chat` toggle button (because the panel is collapsible at 768-1024); on mobile, the hamburger button that opens the left-sidebar contents as a sheet. The `Inspect` button from v1 is REMOVED (there is no separate inspector slide-over anymore, the tools strip + right panel replace it).

---

## 5. STATUS BAR (bottom)

**Decision: YES, keep it. 24px tall, spans all three panes. Justification below.**

A 24px bottom bar `bg-paper border-t border-line flex items-center justify-between px-md text-caption text-slate`:

- **Left:** job status, when `isBusy`: a pulsing coral dot + "Design running" (and job id, truncated); when `state === "poll_timeout"`: a `honey` dot + "Polling timed out"; otherwise: the last terminal state text ("Idle" / "Design ready design-1" / a short error summary).
- **Center:** connection state, "Connected" with a `sage` dot when the app status is empty, "Offline" with a `clay` dot when API calls are failing (wired off the same signals that set `appStatus`). On mobile this segment is hidden.
- **Right:** current model, `Model: {modelVersion ?? "unknown"}` (`modelVersion` already derived in `page.tsx` from `latestResult.validation_report.generated_by_model_version`). On mobile hidden.

### Does it add value or is it pure chrome?

It adds genuine value for a long-job research tool. Three reasons:

1. **Job status is constant-attention content.** A plasmid design job can run 30s-3min. Researchers context-switch during the wait (they read papers, they look back at the map). The alternating v1 chrome (top-bar "Design running" notice that disappeared, plus a `RightRailJobNotice` card that consumed vertical space) required the user to look at two places. A pinned bottom dot is glanceable without leaving the map.
2. **Connection state matters for a tool whose backend may be a local worker.** The demo-fixture environment can silently disconnect; today the only signal is a failed poll. A persistent connection indicator is a research-tool convention (CLIs, IDEs).
3. **Model attribution is a credibility signal for this audience.** PhD-track researchers using NCBI GenBank records care which model verified their construct. A non-obstructive 24px line that shows the model on every screen is cheaper than the current approach of burying it in a validation report only after a design completes.

Not chrome: it replaces the `RightRailJobNotice` card (which consumed ~120px of the old right rail) and removes the need for the top-bar busy mirror. Net panel real estate improves.

Caveat (flag): UX-AUDIT-1 may decide whether the connection-state dot is needed if this tool only ever talks to a known-local backend. Default per this spec: render it; hide if UX-AUDIT rules it out.

---

## 6. BREAKPOINT BEHAVIOR

### Large desktop (1440+)

Full three-pane. Grid rows:

- Row 1 (top bar): 48px, full width.
- Row 2 (main): 1fr, three columns `[left sidebar 256px] [center canvas 1fr] [right chat 400px]`.
- Row 3 (status bar): 24px, full width.

Inside the center column: title row (32px) + map (`h-full` flex-1) + tools strip (56px). The map targets ~580px tall × ~880px wide at 1440×900.

### Narrow desktop (1024-1280)

Three columns `[left sidebar 56px icon rail] [center canvas 1fr] [right chat 360px]`. Top bar 48px. Status bar 24px. Map target ~460px tall × ~560-680px wide. The icon rail expands to a 256px flyout on the New-design / outcome buttons; the history stack shows dot-only rows with a flyout listing on click.

### Tablet (768-1024)

Two columns `[left sidebar 56px icon rail] [center canvas 1fr]`; the right chat panel is **toggleable** via a `Chat` button in the top bar (open by default at ≥880px, closed by default below, see flag). When open, it overlays the right ~360px of the center canvas as a drawer with a scrim (NOT a push layout, pushing would shrink the map below the SeqViz `both`-viewer minimum). When closed, the center canvas is full width. Map target ~400px tall. The tools strip (validation/export/outcome) stays under the map regardless.

The left rail at 56px behaves as in narrow desktop. Below 880px, the rail also collapses into the top-bar hamburger (same as mobile) to free the canvas for the map; the chat toggle remains the only rail-shaped element.

### Mobile (<768)

**TABBED Map/Chat segmented control, NOT the v1 single-scroll stack.** This is the explicit breaking change from v1.

- Top bar (52px): Construct wordmark left, **segmented control** `[ Map | Chat ]` center (full-width-ish, `rounded-pill bg-mist`, the active tab in `bg-paper shadow-rest`), hamburger right.
- Body: the active tab fills the area below the top bar and above the status bar (no v1 bottom composer dock).
  - **Map tab** (default after a result lands; **Chat is the default before any first design** so the welcome message + example chips + composer are the first-paint surface, matching both the E2E desktop flow and the small-viewport test's first action `fill("build a compact GFP reporter") + click("Design")`): PlasmidMapView (map + accessible summary + feature list, full width) followed by the **Design tools strip** (validation/export/outcome, full-width rows scaled for touch, GenBank + FASTA + Report-outcome as full-width buttons, validation summary as a compact card above them). The v1 mobile export row is replaced by this in-tab tools strip.
  - **Chat tab:** chat header + thread + composer. The thread is full height; the composer is pinned to the bottom of the chat tab area.
- The **"View plasmid map"** link (one per result message in the thread) becomes the in-thread affordance that switches to the Map tab (same id, same text, clicking it sets the segmented control to Map; no extra step is introduced for the E2E test).
- **Hamburger** (top-right) opens a left-sheet rendering the sidebar contents: New design button, Design history list (compact), My reported outcomes (expanded; the collapsible is open in the sheet by default on mobile since there is no width pressure once a sheet is open), PendingPromptFetchMessage, BrandAttribution. Closing the sheet returns to the prior tab.
- **Status bar** (24px) is reduced on mobile: only the left segment (job status). Connection-state and model segments are hidden (`hidden max-sm:hidden`). The status bar is visible under whichever tab is active.

### Mobile tab switch rules

- Before any `sessionId`: Chat tab active (first-paint).
- On `submitting`/`polling`: stay on Chat so the user sees `JobProgressCard` and refinement responses; the user is composing/reading, not looking at a not-yet-updated map.
- When an `annotated_sequence` result lands: **auto-switch to Map** so the centerpiece shows. (This is the v1 mobile behavior, preserved.)
- On `awaiting_clarification`: stay on/return to Chat so the user can answer.
- On explicit user tab tap: respect it.
- On `"View plasmid map"` link click: switch to Map (overrides rule above).

---

## 7. COMPONENT PLACEMENT TABLE

Mapping every existing component to its new home. IMPL-LAYOUT-1, IMPL-CHAT-1, IMPL-INSPECTOR-1 follow this table.

| Component (current name / selector) | Large desktop (1440+) | Mobile (<768) |
|---|---|---|
| `Design workspace` heading (`#design-workspace-title`, E2E-asserted) | Top bar, left of center (after brand + divider). Visible at ≥sm. | Top bar (hidden on `<sm`, segmented control occupies the slot; assertion still satisfied because role=heading text "Design workspace" is present in the DOM, just visually clipped if width-constrained, see E2E impact notes). |
| `Construct` wordmark (brand) | Top bar, far left. | Top bar, far left. |
| Current design indicator (design_id + validation pill), NEW chrome from existing state | Top bar, centered. | Left sidebar header (inside hamburger sheet). |
| Settings / account button | Top bar, far right. | Hamburger (top-right). |
| Mobile Map/Chat segmented control | n/a | Top bar, center. |
| Chat toggle button (tablet right-panel open/close) | n/a (panel persistent) | n/a (replaced by segmented control below 768) |
| `RightRailJobNotice` (busy notice card), **REMOVED** | Removed; function absorbed by status bar (job status segment) + chat header busy indicator + inline `JobProgressCard`. | Removed; function absorbed by status bar + chat header + inline `JobProgressCard`. |
| `JobProgressCard` (busy progress card) | Inline in chat thread, bottom (when `isBusy`). | Inline in Chat-tab thread, bottom (when `isBusy`). |
| Conversation message thread (`messages.map` articles) | Right chat panel, between header and composer; persistent (no overlay, no auto-collapse). | Chat tab, between header and composer; full-height scroll. |
| `PendingPromptFetchMessage` | Left sidebar, very top of rail (concerns the user's follow-up library). | Left-sidebar contents in hamburger sheet, very top. |
| Validation summary (compact, existing `ValidationSummary`) | Center canvas tools strip, left cell, under the map. | Map tab tools strip (full-width compact card above export row). |
| Full `ValidationReportPanel` (per-check list, inline in thread) | Stays inline in the result message in the chat thread (unchanged). | Stays inline in the result message in the Chat-tab thread. |
| `MissingValidationReportPanel` / `ResultNote` | Inline in chat thread (unchanged). | Inline in Chat-tab thread (unchanged). |
| `RetrievedTemplatesPanel` | Inline in chat thread (unchanged). | Inline in Chat-tab thread (unchanged). |
| `PartialResultNotice` | Inline in chat thread (unchanged). | Inline in Chat-tab thread (unchanged). |
| `PlasmidMapView` (`#plasmid-map` section incl. `#plasmid-map-title`/empty variant, accessible summary, feature list), the centerpiece | Center canvas, dominant (h-full), above the tools strip. | Map tab, full area, above the mobile tools strip. |
| `FeatureLegend` (`region "Feature list"`, `"CMV promoter"`) | Stays inside `PlasmidMapView`, below the SeqViz canvas (unchanged). | Stays inside `PlasmidMapView`, below the SeqViz canvas (unchanged). |
| `ExportActions` (`region aria-label="Export actions"`, `button "GenBank"` / `"FASTA"`) | Center canvas tools strip, center cell. Region + buttons preserved verbatim. | Map tab tools strip, full-width row. Region + buttons preserved verbatim. |
| `OutcomePanel` action (`button "Report outcome"` / `"Review or edit outcome"`) | Center canvas tools strip, right cell. Compact: button + one-line status hint. `aria-label="Outcome reporting"` region preserved. | Map tab tools strip. Full-width button; status hint above. |
| `OutcomePanel` descriptive paragraph text | Dropped in the strip (the strip shows a one-line hint instead). Full re-introduction is NOT needed for E2E (assertion is only on the button). | n/a (same). |
| `MyOutcomesPanel` (`region aria-label="My reported outcomes"`) | Left sidebar, bottom, collapsible (default collapsed, expands on demand). Region + button + content preserved. | Left-sidebar hamburger sheet, expanded by default. |
| `PendingOutcomeToast` (`aria-label="Pending outcome prompt"`, `button "Report outcome"` / `"Not now"`) | Viewport-fixed, unchanged (`fixed left-4 right-4 top-4 ... sm:bottom-4 sm:w-[calc(100%-2rem)] sm:max-w-md`). Overlays the layout cleanly. | Same: viewport-fixed top-spanning on small screens (the `sm:`-driven bottom-right rule does NOT apply at <640). |
| `OutcomeReportModal` (dialog, heading "What happened in the lab?") | Page-root modal, unchanged. | Page-root modal, unchanged. |
| Composer: awaiting_clarification banner | Right chat panel, top of composer form (unchanged markup). | Chat tab, top of composer form (unchanged markup). |
| Composer: example prompt chips | Right chat panel, inside composer form (shown `!sessionId && state==="idle"`). | Chat tab, inside composer form. |
| Composer: textarea `#goal` + submit button | Right chat panel, composer form, **vertical** layout (textarea above, full-width submit below). Submit label cycles Design/Refine/Answer/Starting/Designing. | Chat tab, composer form, vertical layout. |
| Composer: poll-timeout `Check status` / `Start over` controls row | Right chat panel, composer form, bottom row (shown `state==="poll_timeout"`). | Chat tab, composer form, bottom row. |
| `BrandAttribution` | Left sidebar footer. | Left-sidebar hamburger sheet footer. |
| Top bar (NEW chrome) | 48px tall, spans all three panes. | 52px tall, spans full width. |
| Center canvas tools strip (NEW chrome) | 56px tall, horizontal 3-cell strip under the map. | Full-width tools strip under the map (Map tab). |
| Bottom status bar (NEW chrome) | 24px tall, spans all three panes: job status (left) / connection (center) / model (right). | 24px tall, full width: job status only. |
| Left sidebar (NEW chrome) | 256px column, contents per section 1. | Hamburger sheet, contents per section 1. |
| Right chat panel (NEW chrome) | 400px column, contents per section 3. | Chat tab surface (no column, full width minus nothing). |

---

## 8. E2E IMPACT NOTES (`design-workspace.spec.ts` + `design-workspace.full-stack.spec.ts`)

Going assertion-by-assertion through the flagged list. Stays-put / moves / VERIFY-1.

- **`heading "Design workspace"` (line 78):** MOVES from the left `<section>` to the top bar (left of center). Same text, same `id="design-workspace-title"` (preserve the id), still an `<h1>`. Assertion passes unchanged. On mobile the heading is visually subsumed by the segmented control but the element is still in the DOM with its text, Verify-1 must confirm the heading is `toBeVisible()` at 390px (it may need the top bar to keep it on the left rather than fully hidden). **Recommend IMPL-LAYOUT-1 keep the `Design workspace` heading visible on mobile at small widths by truncating rather than hiding, so the assertion does not need a viewport-conditional change.** If truncation fails the visibility check, VERIFY-1 adds `setViewportSize ≥ 768` for that test, but this is the only assertion at risk.
- **`link "View plasmid map"` (small-viewport test, line 150):** STAYS inline in each result message in the chat thread. On mobile it is in the Chat-tab thread and clicking switches to Map tab. The link's `text`, `role="link"`, and `href="#plasmid-map"` are preserved. Assertion passes, Verify-1 must confirm the click triggers the tab hop (an injected `onClick`). No selector change.
- **`heading "Plasmid map"` (line 151):** STAYS in `PlasmidMapView` (`#plasmid-map-title`). On mobile it is in the Map tab. After the "View plasmid map" link switches to Map, the heading is visible. Assertion passes unchanged.
- **`text "Accessible map summary"` (line 152):** STAYS in `PlasmidMapView`. Assertion passes unchanged.
- **`region "Feature list"` + `text "CMV promoter"` (lines 87-89 small-viewport 153):** STAY in `PlasmidMapView`. Assertion passes unchanged.
- **`region "Export actions"` + `button "GenBank"` (lines 155-156):** MOVES from the right inspector (v1) to the center canvas tools strip. At large desktop the region + button are under the map, visible by default. At small viewport (390px, Map tab active after the View-plasmid-map click) the region + button are in the map-tab tools strip, visible without further navigation. **Assertion passes unchanged on both viewports.** (Confirm the `aria-label="Export actions"` region wrapper is preserved in the strip.)
- **`button "Report outcome"` (small-viewport line 158):** MOVES into the center canvas tools strip (right cell). At small viewport (Map tab), the button is in the tools strip under the map, visible after the same View-plasmid-map hop. Assertion passes **unchanged, no More sheet, no extra step** (this is the key simplification vs v1: the tools strip is on the Map tab, so exporting and reporting are reachable immediately after switching to Map).
- **`dialog heading "What happened in the lab?"` (desktop); `dialog` heading same (mobile):** UNCHANGED. `OutcomeReportModal` is page-root. Assertions pass.
- **`aria-label "Pending outcome prompt"` (line 257):** UNCHANGED, toast is viewport-fixed, layout-independent. Assertion passes.
- **`region "My reported outcomes"` (line 279):** MOVES from the right inspector (v1) to the **left sidebar**. At large desktop this region is in the sidebar (collapsed by default); the test does not collapse it, so VERIFY-1 must confirm the region is present in the DOM and `toContainText`-visible while collapsed, IMPL-INSPECTOR-1 must keep the collapsible's region element in the DOM (CSS-collapsed, not unmounted) so the `region` role and `aria-label` are present. **Verify-1: assert the region renders collapsed; if `toContainText` requires the content visible, IMPL-INSPECTOR-1 should leave the list content in the DOM (hidden via height/overflow) rather than unmounting.** Default-collapsed-or-expanded is a UX-AUDIT-1 call; this spec defaults **expanded** at first paint when `reportedOutcomes.length > 0` so the assertion is satisfied without interaction (and UX-AUDIT-1 may tighten this).
- **`text "Submit a design to render the annotated plasmid."` (line 204):** STAYS the empty-state branch of `PlasmidMapView`. At large desktop visible by default (map canvas). At small viewport, after a *partial* result (no `annotated_sequence`), the Chat tab is active by default (no auto-switch to Map because no sequence landed) and the empty-state map is in the Map tab, Verify-1 must confirm the partial-result test's `toBeVisible()` finds the text without a tab switch. **Flag: the partial-result test (lines 195-205) does not click "View plasmid map" or switch tabs. At small/no-result state the map's empty-state text lives on the Map tab. If the test runs on desktop (default viewport) this is fine, the map canvas is always visible at large desktop. If run at small viewport, VERIFY-1 must keep the empty-state map visible on the Chat tab OR auto-render its text. Recommended: render the empty-state `PlasmidMapView` in BOTH the Map and Chat canvas placeholders on mobile when no result exists, OR keep the test on default viewport. Default: keep test on default viewport (the existing test has no `setViewportSize` on the partial-result test, it is desktop).** No change needed; flagged for awareness.
- **`testid "seqviz-map"` (line 85):** STAYS the inner `data-testid="seqviz-map"`. Assertion passes unchanged.
- **`text "Map could not render"` (hidden check, line 88 / 154):** STAYS the `MapErrorBoundary` fallback inside `PlasmidMapView`. Assertion passes unchanged.
- **`text "Retrieved template evidence"` / `"curated:pEGFP-N1"` (lines 83-84):** STAYS inline in the chat thread (`RetrievedTemplatesPanel`). On desktop the thread is always visible. Assertion passes unchanged.
- **`text "Refined design completed with the lentiviral backbone request captured."` (line 93):** STAYS a message in the chat thread. Assertion passes; the thread is persistent so no toggle is required to read this.
- **`button "Design"` / `"Refine"` (lines 81 / 92):** STAYS in the composer. On desktop the composer is in the always-visible right chat panel. Assertion passes.
- **`button "GenBank"`/`"FASTA"` download asserts (lines 96-101):** the buttons live in the tools strip; the downloads are unchanged (handler preserved). Assertion passes.

### Net E2E changes required (VERIFY-1)

- Confirm `Design workspace` heading is visible at 390×844 (recommend IMPL keep it visible via truncation, not hiding). If not, set the small-viewport test's viewport ≥ 768 OR move the heading to a slot that stays visible on mobile.
- Confirm `region "My reported outcomes"` is in the DOM and content-visible while the left-sidebar collapsible is collapsed (test does not expand it). Recommend IMPL render collapsed content in DOM (hidden via CSS), not by unmount.
- No other selector additions required. The "View plasmid map" link click must perform a tab hop on mobile (injected `onClick`), Verify-1 confirms this.

---

## Questions for the human

**(a) Left sidebar content:** DECIDED (no question). Single-view tool; sidebar hosts New-design action + current-session design-history list + collapsible My-outcomes + PendingPromptFetchMessage + BrandAttribution. No multi-session browser is built.

**(b) Validation report placement:** DECIDED (no question). Compact summary in a 56px tools strip directly below the map (co-visible with the artifact, no context switch); the per-check full list stays inline in the chat thread where the agent produced it. NOT adjacent to chat (would crowd the thread); NOT tabs above the map (would hide the centerpiece).

**(c) Button placement coordination with UX-AUDIT-1:** The following buttons are PLACED by this spec; UX-AUDIT-1 rules on whether each survives:

- `New design` (left sidebar, top), new affordance, no v1 equivalent.
- `Clear conversation` (chat header right), new affordance.
- `Settings` (top bar right, desktop/tablet), new affordance, opens about/settings sheet.
- `Chat` toggle (top bar right, tablet only), new affordance.
- `Export: GenBank` / `FASTA` (center tools strip), existing, preserved.
- `Report outcome` / `Review or edit outcome` (center tools strip), existing, preserved.
- `Open full report` (validation strip cell, links into thread), existing affordance.
- `Show / Hide` (My-outcomes collapsible in left sidebar), new affordance.
- Composer `submit` (Design/Refine/Answer/Starting/Designing), existing, preserved.
- Poll-timeout `Check status` / `Start over`, existing, preserved.
- `View plasmid map` (per-result link), existing, preserved.
- `Report outcome` / `Not now` (PendingOutcomeToast), existing, preserved.
- `Review or edit outcome` (per-outcome in MyOutcomesPanel), existing, preserved.

UX-AUDIT-1 is free to remove `Clear conversation`, `Settings`, and the `Show/Hide` for My-outcomes if those do not justify their cost; their removal does not cascade through this spec (they occupy non-load-bearing chrome slots). Removing `New design`, the composer submit, GenBank/FASTA, or Report-outcome would cascade, those are load-bearing and should be flagged back to LAYOUT-2 if UX-AUDIT-1 proposes removing them.

**One additional question raised by this spec (low cascade risk, flagged for awareness):**

- **Q-L2-1 (tablet chat default, low cascade):** Below 880px (the narrow end of the tablet range), should the right chat panel default open (chat legible, map squeezed to ~2/3 width) or closed (map full-width, user must tap `Chat` to compose)? Recommended default if no answer: **open at ≥880px, closed below 880px**, gives the map the room it needs for the SeqViz `both` viewer at the widths where the panel would squeeze it below the 640px threshold. This is a UX rule, not structural. UX-AUDIT-1 may rule.