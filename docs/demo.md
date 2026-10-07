# Construct 5-Minute Demo Script

Audience: YC partners, early investors, and scientific collaborators.

Goal: show that the app is not a generic chatbot. It turns a plain-English plasmid request into a retrieval-grounded design session, supports conversational refinement, displays validation evidence, exports handoff files, and later captures wet-lab outcomes for a feedback loop.

This script was checked against the current Next.js workspace, the `Makefile` targets, and the `apps/web` UI on branch `demo-punch-list`.

Use `make serve-local` for the interactive local app. Use `make demo` only for deterministic end-to-end verification against the fixture app.

## Pre-Demo Setup

Install dependencies, make sure `.env` exists, and start Postgres/pgvector before using the live local app:

```powershell
docker compose up -d
```

The current local app expects the Python dependencies from `requirements.txt`, including the official `google-genai` SDK, and reads environment values from `.env`.

Run the deterministic verification demo with `make demo`. This is the canonical, self-contained verification path: it starts the fixture API (`services.api.e2e_app`) and the web app together and drives the full-stack Playwright flow through a design job that completes, a plasmid map that renders, and a GenBank export that downloads.

```powershell
make demo
```

Under the hood, `make demo` runs `make e2e-test`, which invokes the full-stack Playwright config (`apps/web/playwright.fullstack.config.ts`). That config brings up the deterministic fixture API on `127.0.0.1:8000` and the web app on `127.0.0.1:3000`, then exercises the design, retrieval, map, and GenBank export flow against `services.api.e2e_app` rather than the live scaffold.

For the interactive local app, start the API and web separately:

```powershell
make serve-local
make serve-web
```

The API command behind `make serve-local` is `python -m uvicorn --factory services.api.local_app:build_local_app --host 127.0.0.1 --port 8000`, and the web command behind `make serve-web` is `cd apps/web && npm run dev`. Open `http://127.0.0.1:3000` after both are running.

Do NOT use `make serve-api` for the interactive app. It runs the default FastAPI scaffold (`services.api.app`), which can queue design jobs without completing them unless a generation worker is wired in. The production queue path remains future Celery plus a durable Postgres-backed job queue deployment.

Before starting:

- Clear old downloads so the GenBank export is easy to find.
- Keep browser zoom at 100%.
- If you want to show the outcome follow-up toast path, seed a pending outcome prompt for a stable `design_id` so the bottom-right "Outcome follow-up" toast appears; otherwise use the in-session "Report outcome" path in the right rail.
- Do not claim full Phase 4/5 production readiness. Auth, primer output, synthesis-provider handoff, deployed hosting, and automated fine-tune promotion are still open.

## Demo Flow

### 0:00-0:35 - Set The Frame

Screen: `Design workspace` with the left chat column and right-side `Plasmid map`, `Export`, `Lab outcome`, and `My outcomes` panels.

Say:

"Construct is a design workspace for molecular biologists. The first wedge is simple: describe the construct, retrieve a grounded template from real plasmid records, generate an annotated candidate, run deterministic validation checks, and export a file a bench scientist can inspect."

Point out:

- The first screen is the workspace, not a landing page.
- The empty plasmid map says: "Submit a design to render the annotated plasmid."
- The export and outcome panels are disabled until a design exists.

### 0:35-1:30 - Initial Chat Prompt

Click the prompt box labeled `Experimental goal`.

Type exactly:

```text
a yeast shuttle vector with URA3 selection and centromere maintenance
```

Click `Design`.

Expected screen while running:

- The user message appears as `Researcher`.
- A progress card appears with `Starting design job` or `Designing and validating plasmid`.
- The progress steps read `Retrieving templates`, `Generating candidate`, and `Running checks`.
- A job ID may appear below the progress bar.

Say:

"This is intentionally phrased like a scientist would ask, not like an API payload. The system parses host, vector type, selectable marker, and maintenance constraints, then retrieves a template instead of making up a backbone."

When the job completes, expected screen:

- A `Design agent` message appears.
- The message includes either a generated design summary or recommendation text.
- A `Validation report` panel appears in the assistant message when validation is returned.
- A retrieved-template list appears, for example `Retrieved 1: pRS416` or another yeast shuttle template, with a numeric score if available.
- A `View plasmid map` link appears.
- The right rail renders a seqviz plasmid map with sequence length, topology, annotation status, and a feature legend.

Talking points:

- YC/investor: "The product flow starts with a narrow, high-frequency lab job rather than a broad research assistant."
- Collaborator: "The app exposes the retrieved template so a scientist can audit the starting point."
- Technical: "Recommendation text is constrained to retrieved records; missing requirements are stated as adaptations, not hallucinated as existing features."

### 1:30-2:20 - Retrieval-Template-Grounded Design

Scroll within the assistant message if needed.

Expected screen:

- The assistant result shows the top retrieved templates under the message.
- The plasmid map shows labeled features in the right rail.
- The feature legend includes component names, feature types, coordinates, strand, and confidence percentages.

Say:

"This is the difference between chat and a design system. We are showing the provenance boundary: parsed intent, retrieved template, generated annotated sequence, and validation report are separate artifacts. That gives us something to test, version, and improve."

Point at the right rail:

"The map is not decorative. It is the handoff surface: a scientist can inspect the circular sequence, feature calls, and annotation completeness before downloading anything."

### 2:20-3:05 - Conversational Refinement

Click the same prompt box. The button should now say `Refine`.

Type exactly:

```text
keep URA3 selection, but add a GFP reporter payload for a fluorescence readout
```

Click `Refine`.

Expected screen:

- A second `Researcher` message appears.
- Another progress card appears.
- A second `Design agent` result appears.
- The assistant result should reflect the refinement, either in the recommendation text, generated sequence, retrieved template list, feature legend, or validation report.
- The plasmid map updates if the returned annotated sequence changes.

If a clarification appears instead:

- The UI labels it `Clarification`.
- A yellow `Clarification needed:` box appears above the text area.
- Answer with:

```text
Saccharomyces cerevisiae; use the retrieved yeast shuttle backbone and treat GFP as the payload.
```

Say:

"The session keeps context. The first turn establishes the yeast shuttle backbone and URA3 constraint; the second turn asks for a payload change. For collaborators, this is where we can add lab-specific defaults without forcing people into a form."

Talking points:

- YC/investor: "Refinement is where retention lives: users iterate on real constraints instead of starting over."
- Collaborator: "Ambiguous requests can become explicit clarification turns rather than silent assumptions."
- Technical: "The API stores sessions, turns, jobs, and design artifacts so later export and outcome submission can link back to the exact design."

### 3:05-3:50 - Validation Report And GenBank Export

In the latest assistant message, point to `Validation report`.

Expected screen:

- The validation panel has an overall status badge such as `PASS`, `WARN`, or `FAIL`.
- Individual checks appear as rows with names, statuses, messages, and sometimes regions.
- The model/version line may appear as `Model: ...`.

Say:

"Validation is deterministic and separate from generation. Today it checks synthesis and biology constraints such as restriction-site conflicts, repeat or instability patterns, codon usage, and regulatory compatibility. A failed check is not hidden by a fluent answer."

In the right `Export` panel, click `GenBank`.

Expected screen:

- The button may briefly show `Preparing...`.
- Browser download starts with a filename like `<design_id>.gb`.
- The panel shows `GenBank download started.` and the button becomes `GenBank ready`.

Say:

"Export matters because the user eventually has to leave the app. GenBank preserves sequence, topology, and annotated features, so a collaborator can open it in their normal plasmid tooling. FASTA is available too, but GenBank is the richer demo handoff."

Investor talk track:

"This is the wedge from assistant to workflow: users get an artifact they can inspect, share, and eventually submit for synthesis, not just prose."

Collaborator talk track:

"The exported record includes Construct metadata and feature qualifiers so auditability survives outside the browser."

### 3:50-4:45 - Later Outcome Submission

Use one of two paths.

Preferred path if a current design exists:

1. In the right rail, find `Lab outcome`.
2. Click `Report outcome`.

Fast-forward path if seeded:

1. Point to the bottom-right `Outcome follow-up` toast.
2. It should say `Design <design_id> is ready for lab outcome feedback.`
3. Click `Report outcome`.

Expected modal:

- Header: `Report outcome`.
- Title: `What happened in the lab?`
- Pinned context shows `Design ID:` and `Model version:`.
- Form fields are:
  - `What did you test?`
  - `What sequence evidence do you have?`
  - `What happened in expression testing?`
  - `What happened in functional testing?`
  - `Based on the evidence above, what is your interpretation?`
  - `Notes`
  - Training-consent checkbox.
- The `Evidence category` section updates as choices are made.

Select exactly:

- `What did you test?` -> `Delivered design exactly`
- `What sequence evidence do you have?` -> `Matches expected regions`
- `What happened in expression testing?` -> `Met expected expression`
- `What happened in functional testing?` -> `Met expected function`
- `Based on the evidence above, what is your interpretation?` -> `Accepted for intended use`

In `Notes`, type exactly:

```text
Clone 2 matched expected reporter function after sequence confirmation.
```

Check:

```text
I consent to this outcome report and non-sensitive linked design metadata being used to improve future design models.
```

Click `Submit outcome`.

Expected screen:

- Confirmation title: `Outcome submitted`.
- Summary shows interpretation, sequencing, expression, function, consent, and reported timestamp.
- Text says the report may be reviewed for model improvement if consent was granted.
- Click `Back to design`.
- The right rail `Lab outcome` panel changes to an outcome-reported state.
- `My outcomes` shows the reported design with a positive badge and training-consent status.

Say:

"The long-term advantage is not just generation. It is attribution. Weeks later, the app can ask what happened in the lab and connect the answer to the design ID, model version, evidence, consent, and provenance."

Be precise:

"This is the foundation of the feedback flywheel. The current repo can store outcomes and derive training-signal snapshots, but automated scheduled retraining and promotion are not complete yet."

### 4:45-5:00 - Close

Say:

"In five minutes, we went from a natural-language construct goal to a grounded template, an annotated plasmid map, deterministic validation, GenBank export, and an outcome record that can later improve the model. The next product milestones are production auth, primer and synthesis-provider handoff, and closing the automated training loop."

## Backup Prompts

Use these if the primary prompt does not retrieve cleanly in the current local corpus.

```text
a bacterial expression vector for E. coli with ampicillin selection and GFP reporter readout
```

```text
a mammalian GFP reporter plasmid for expression analysis in cultured cells
```

```text
build a GFP reporter
```

Refinement backup:

```text
switch the backbone to pEGFP-N1 and keep the GFP reporter readout
```

Clarification backup:

```text
Use cultured mammalian cells and keep GFP as the reporter payload.
```

## Claims To Make And Avoid

Make these claims:

- "Retrieval is grounded in indexed plasmid records and templates."
- "The validation engine is deterministic and reports checks separately from generation."
- "The current frontend supports chat, refinement, map rendering, GenBank/FASTA export, and outcome capture."
- "Outcome capture is consent-aware and stores model/design provenance for later training-signal derivation."

Avoid these claims:

- "The system is production deployed."
- "The sequence is guaranteed synthesis-ready."
- "Primer design and synthesis-provider ordering are complete."
- "The model is already learning automatically from every reported outcome."
- "Lentiviral, CRISPR, or Addgene-scale coverage is complete."

## Audience-Specific Notes

YC/investor:

- Lead with workflow compression: prompt -> grounded design -> validation -> export -> outcome.
- Emphasize data flywheel defensibility: the valuable asset is linked design provenance plus later wet-lab outcomes, not chat UX alone.
- Mention current gates honestly: Phase 1 retrieval and Phase 3 validation gates are met; Phase 4/5 productization remains in progress.

Scientific collaborator:

- Lead with auditability: retrieved template names, feature coordinates, validation checks, and export metadata are visible.
- Emphasize conservative behavior: clarification is preferable to guessing, and incomplete annotations are surfaced.
- Ask for help on supported first profiles, default synthesis-provider constraints, and evidence standards for outcomes.

Technical collaborator:

- Lead with architecture: Next.js workspace, FastAPI session/job/export/outcome endpoints, shared Pydantic schemas, retrieval/generation/validation package boundaries.
- Emphasize testable interfaces: parser, retriever, generator, constraint engine, export codec, and outcome store are separate contracts.
- Point to open integration work: job worker wiring, auth/session ownership, primer output, provider handoff, and scheduled outcome-derived training.
