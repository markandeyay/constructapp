# AI Construct Design Platform: System Design Document

> ## HISTORICAL DESIGN NOTE. READ THIS FIRST.
>
> This document is the **earlier** design record for the plasmid engine, kept as a
> historical record of how the system was reasoned about. It is **no longer the
> single source of truth**, and parts of it describe intent rather than anything
> that exists.
>
> **What actually exists today is four capabilities:** plasmid design, AAV vector
> design, assembly and primer design, and guide RNA design. Anything else named or
> implied anywhere below, including specific vectors, inducible systems or
> modalities not in that list, is on the roadmap and is not built. Treat no
> sequence or capability claim below as current.
>
> For current truth, in order of authority:
>
> | For | Read |
> |---|---|
> | What the four capabilities do and how they are measured | `README.md` |
> | How to run and demo the system | `docs/demo.md` |
> | What is actually implemented, decided and still open | `PROGRESS.md` and `progress/` |
> | What may and may not be claimed about the product | the claim safety register in the engine capability specification |
> | What the provenance and export gate really enforces | `progress/WP-08.md` |
>
> The body below is left unedited on purpose. Correcting a historical record in
> place would destroy the record.

> **Document type:** Build specification for an autonomous coding agent.
> **Status:** Historical. Superseded for all current claims; see the note above.
> **Audience:** A coding agent executing the build across many sessions, plus the human supervising it.

---

## MISSION STATEMENT

**The goal of this program is to generate complete, valid, synthesis-ready plasmid designs from natural-language prompts.**

A researcher describes their experimental goal in plain English — for example, *"I need a lentiviral vector expressing GFP-tagged BRCA1 under a doxycycline-inducible promoter in HEK293 cells for live imaging of DNA repair foci"* — and the system returns a complete, annotated, biologically valid plasmid: the full DNA sequence, a labeled map of its functional components, a validation report, primer designs, and one-click handoff to a synthesis provider. What currently takes a skilled molecular biologist two to four weeks of manual design, literature review, and iteration — and fails 30–50% of the time on the first attempt — should take minutes and succeed far more often.

Everything in this document serves that single sentence: **plain-English goal in, validated plasmid out.** Every component, phase, and gate exists because it moves the system closer to producing a plasmid a researcher can order and trust. When a design decision is ambiguous, resolve it in favor of whichever option best serves correct, trustworthy generation of plasmids from natural language.

---

## 0. How to use this document (READ THIS FIRST, EVERY SESSION)

You are a coding agent building a large system that **cannot be finished in one session**. Your context window will be compacted (summarized and truncated) repeatedly. This document and its companion state file are how you stay oriented across that.

### 0.1 The two-file contract

There are two files you must care about:

1. **`SYSTEM_DESIGN.md`** (this file) — the *immutable* specification. It describes *what* to build and *how* the pieces fit. You read from it. You do **not** rewrite it unless the human explicitly asks you to revise the design.
2. **`PROGRESS.md`** — the *mutable* state file. It records *what has actually been done so far*, *what is in progress*, and *what is next*. You **update this file at the end of every working session and before any compaction** you can anticipate.

If `PROGRESS.md` does not exist yet, your **very first action** is to create it by copying the template in Section 1 of this document.

### 0.2 Session startup ritual (do this at the start of EVERY session)

Run this sequence before writing any code:

1. Open and read `PROGRESS.md` in full. This tells you where you are.
2. Read the "Current Phase" and "Next Concrete Task" fields at the top of `PROGRESS.md`.
3. Re-read **only** the section(s) of `SYSTEM_DESIGN.md` relevant to the current phase (the document is large; do not re-read all of it every time — use the table of contents in Section 2).
4. Run the test suite for whatever already exists (`make test` or the documented equivalent) to confirm the codebase is in a known-good state before you change anything.
5. Pick up the "Next Concrete Task."

### 0.3 Session shutdown ritual (do this at the end of EVERY session, and whenever you sense compaction coming)

1. Update the "Build Log" in `PROGRESS.md` with what you did this session (one bullet per meaningful change, with file paths).
2. Tick any newly completed items in the Master Checklist (Section 3) — record the tick in `PROGRESS.md`, not in this file.
3. Update "Current Phase," "Next Concrete Task," and "Known Issues / Blockers" at the top of `PROGRESS.md`.
4. If you left anything half-done, write an explicit "RESUME HERE" note in `PROGRESS.md` describing the exact file, function, and line you were editing and what the intended end-state is.
5. Commit all work to git with a descriptive message. Never end a session with uncommitted changes.

### 0.4 Guardrails (rules you never break)

- **Never** mark a checklist item complete unless its acceptance criteria (defined in the relevant section) are met *and* tests pass.
- **Never** delete or fabricate training data, scientific results, or validation outcomes. This is a scientific tool; correctness is paramount.
- **Never** hard-code secrets. All credentials come from environment variables / a secrets manager (Section 11).
- **Prefer** finishing and testing one vertical slice over starting many horizontal layers. A working retrieval-only product beats three half-built ML layers.
- When biology is involved and you are unsure, **stop and flag it in `PROGRESS.md` under "Questions for the human"** rather than guessing. Wrong biology is worse than no biology.
- Keep every component behind an interface (Section 4.3) so layers can be swapped without rewrites.

---

## 1. `PROGRESS.md` template (create this file on first run)

When `PROGRESS.md` does not exist, create it with exactly this content, then begin work.

```markdown
# PROGRESS — Build State (mutable)

## AT-A-GLANCE (update every session)
- **Current Phase:** Phase R — Research & knowledge acquisition
- **Next Concrete Task:** Create the research workspace per SYSTEM_DESIGN Section 4.5 and dispatch the first research subagents
- **Overall completion estimate:** 0%
- **Last session date:** <fill in>
- **Codebase known-good?** (tests passing) Yes / No

## RESUME HERE (only if mid-task)
<exact file, function, line, and intended end-state — clear this when the task is done>

## KNOWN ISSUES / BLOCKERS
- <none yet>

## QUESTIONS FOR THE HUMAN
- <none yet>

## PHASE GATE STATUS
- [ ] Phase R gate met (see SYSTEM_DESIGN 3.05)
- [ ] Phase 0 gate met (see SYSTEM_DESIGN 3.1)
- [ ] Phase 1 gate met
- [ ] Phase 2 gate met
- [ ] Phase 3 gate met
- [ ] Phase 4 gate met
- [ ] Phase 5 gate met

## MASTER CHECKLIST MIRROR
<Copy the checklist from SYSTEM_DESIGN Section 3 here on first run, then tick items here as you go. This is the authoritative record of completion.>

## BUILD LOG (append-only, newest at top)
- <date> — Created PROGRESS.md, read system design, scaffolding repo.
```

---

## 2. Table of contents

- Section 0 — How to use this document
- Section 1 — PROGRESS.md template
- Section 2 — Table of contents (you are here)
- Section 3 — Master checklist & phase gates
- Section 4 — System overview & repository structure
- Section 4.5 — Phase R: Research & knowledge acquisition (subagent-driven)
- Section 5 — Phase 0: Data pipeline
- Section 6 — Phase 1: Retrieval (RAG) layer — the MVP
- Section 7 — Phase 2: Sequence generation model
- Section 8 — Phase 3: Constraint & validation engine
- Section 9 — Phase 4: Application layer (API + frontend)
- Section 10 — Phase 5: Feedback flywheel & continuous learning
- Section 11 — Cross-cutting concerns (infra, security, secrets, observability)
- Section 12 — Data schemas (canonical reference)
- Section 13 — API contract (canonical reference)
- Section 14 — Testing strategy
- Section 15 — Glossary of biology terms for the agent

---

## 3. Master checklist & phase gates

This is the spine of the build. Each phase ends with a **gate**: a small set of objective criteria that must be true before the next phase begins. Do not skip gates. Tick items in `PROGRESS.md`, not here.

### 3.0 Phase ordering rationale

Phases are ordered so that a *usable, demoable product exists as early as possible* and each phase de-risks the next:

- **Phase R** acquires the domain knowledge the whole build depends on, via subagents reading the literature, before any code is written. Skipping this means building on guesses about biology.
- **Phase 0** builds the data foundation everything depends on.
- **Phase 1** ships a retrieval-only product (no generation). This is already useful and demoable — it is the MVP.
- **Phase 2** adds novel sequence generation on top of the retrieval foundation.
- **Phase 3** adds the safety/correctness layer that makes generated output trustworthy.
- **Phase 4** wraps everything in a real API and UI.
- **Phase 5** closes the data loop that creates the long-term moat.

You can begin Phase 4 (application scaffolding) partly in parallel once Phase 1 is gated, because the API can serve retrieval results before generation exists. Phase R is partly revisited throughout: when a later phase hits a domain question (a new model, an unfamiliar biological constraint), dispatch a focused research subagent rather than guessing.

### 3.05 Phase R — Research & knowledge acquisition

- [ ] Research workspace created at `research/` with the structure in Section 4.5
- [ ] Subagents dispatched across all research tracks (Section 4.5.3) and their findings written to `research/findings/`
- [ ] Plasmid biology synthesized into `research/findings/plasmid_biology.md` (structure, components, design rules)
- [ ] Sequence-generation landscape synthesized into `research/findings/sequence_models.md` (DNABERT-2, Nucleotide Transformer, Evo, GenSLM, etc., with licenses)
- [ ] Existing tools & prior art synthesized into `research/findings/prior_art.md` (OriGen, PlasmidGPT, Benchling, SnapGene, VectorBuilder, etc.)
- [ ] Data sources synthesized into `research/findings/data_sources.md` (Addgene, NCBI, access methods, licensing, formats)
- [ ] Validation/constraint rules synthesized into `research/findings/design_rules.md` (restriction sites, codon optimization, regulatory compatibility)
- [ ] Visualization approaches synthesized into `research/findings/visualization.md` (seqviz, circular/linear map rendering)
- [ ] An annotated bibliography (`research/bibliography.md`) lists every paper/source read, with a one-line takeaway and citation
- [ ] A consolidated `research/SYNTHESIS.md` distills everything into the decisions that affect the build, with open questions flagged for the human
- [ ] **GATE:** Every research track has a findings file with cited sources; `research/SYNTHESIS.md` exists and explicitly answers the "questions the build needs answered" list (Section 4.5.2); any unresolved biological questions are logged under "Questions for the human" in `PROGRESS.md`.

### 3.1 Phase 0 — Foundations & data pipeline

- [ ] Monorepo scaffolded with the structure in Section 4.2
- [ ] Local dev environment reproducible (`make setup` brings up Postgres + object store + vector DB locally via Docker Compose)
- [ ] CI runs lint + tests on every commit
- [ ] Addgene ingestion job pulls plasmid metadata + sequences into the canonical `plasmids` table (Section 12.1)
- [ ] NCBI GenBank ingestion job pulls plasmid-annotated sequences
- [ ] Literature/context extraction job populates the `experimental_contexts` table (Section 12.2)
- [ ] Sequence parser normalizes every sequence into canonical annotated form (Section 12.3) with component detection (ORI, promoter, GOI, marker, MCS, terminator)
- [ ] Data quality report job produces counts, null-rates, and dedup stats
- [ ] **GATE:** ≥ 50,000 fully-parsed, component-annotated plasmid records exist in the database and pass schema validation; a single CLI command reproduces the whole pipeline from empty DB.

### 3.2 Phase 1 — Retrieval layer (MVP)

- [ ] Embedding service wraps a biomedical encoder (Section 6.2) behind the `Embedder` interface
- [ ] Every plasmid record embedded and indexed in the vector DB
- [ ] NLU parser converts free-text experimental goals into the structured `DesignSpec` (Section 12.4) via an LLM behind the `IntentParser` interface
- [ ] Retrieval service returns top-K relevant plasmids for a `DesignSpec`, with hybrid (semantic + structured-filter) search
- [ ] Recommendation generator produces a plain-English, ranked explanation of how to adapt each retrieved plasmid
- [ ] Evaluation harness measures retrieval quality against a hand-labeled gold set (Section 6.6)
- [ ] **GATE:** Given 20 realistic natural-language queries, the system returns relevant plasmids with a top-5 hit rate ≥ 80% on the gold set, end-to-end, via a single function call.

### 3.3 Phase 2 — Sequence generation

- [ ] Base DNA language model selected and loaded behind the `SequenceGenerator` interface (Section 7.2)
- [ ] Training data formatter produces (context, template, target) examples from Phase 0 data (Section 7.3)
- [ ] Fine-tuning pipeline runs on managed GPUs and checkpoints to object storage
- [ ] Inference service generates a candidate full-length plasmid sequence from a `DesignSpec` + retrieved templates
- [ ] Generated sequences are re-annotated by the Phase 0 parser to confirm component structure
- [ ] Generation evaluation: % of generations that are syntactically valid DNA, contain the requested components, and pass basic feasibility (Section 7.6)
- [ ] **GATE:** ≥ 70% of generations for the gold-set queries are syntactically valid, contain all requested components, and pass the Phase 3 constraint engine.

### 3.4 Phase 3 — Constraint & validation engine

- [ ] Restriction-site conflict checker
- [ ] Repeat / instability checker
- [ ] Codon optimization scorer for the target organism
- [ ] Regulatory-element compatibility checker (promoter/host, marker presence, ORI/host)
- [ ] Optional therapeutic-compliance checks (flagged, not blocking, for gene-therapy contexts)
- [ ] Validation report object (Section 12.5) with PASS / WARN / FAIL per check and actionable messages
- [ ] Engine runs deterministically and is unit-tested against known-good and known-bad constructs
- [ ] **GATE:** Engine correctly classifies a curated, profile-diverse set of known-good and known-bad constructs with ≥ 95% accuracy. Gold-set size is determined by source quality and defensibility rather than an arbitrary record count; the original ≥50/≥50 target was a planning placeholder revised after the known-good audit in `research/findings/known_good_audit.md`.

### 3.5 Phase 4 — Application layer

- [ ] FastAPI backend exposes the API contract in Section 13
- [ ] Session + conversation persistence (refinement loop) works end-to-end
- [ ] Plasmid map visualizer renders circular + linear maps in the frontend (Section 9.4)
- [ ] Chat-style iterative design UI (describe → design → refine → validate)
- [ ] Export to GenBank / FASTA and primer-design output
- [ ] Synthesis-order handoff (file generation + provider redirect/stub) (Section 9.6)
- [ ] AuthN/AuthZ, rate limiting, usage metering
- [ ] **GATE:** A new user can sign up, type a goal in plain English, receive a validated design with a rendered map, refine it conversationally, and export synthesis-ready files — all through the deployed UI.

### 3.6 Phase 5 — Feedback flywheel

- [ ] Outcome-capture flow (did the construct validate? sequencing + expression data) (Section 10.2)
- [ ] Outcome data stored as labeled training signal
- [ ] Scheduled re-training / fine-tuning pipeline consumes new outcomes
- [ ] Model registry + versioning + safe rollout (shadow → canary → full) (Section 10.4)
- [ ] Offline eval gate prevents regressions before any model promotion
- [ ] **GATE:** A full loop runs automatically — a captured outcome flows into the next scheduled fine-tune, the new model is evaluated offline, and is promoted only if it beats the incumbent on the eval set.

---

## 4. System overview & repository structure

### 4.1 The pipeline in one picture (text form)

```
User free-text goal
      │
      ▼
[IntentParser]  ── LLM ──▶  DesignSpec (structured JSON)
      │
      ▼
[Retriever]  ── Embedder + VectorDB + structured filters ──▶  Top-K template plasmids
      │
      ▼
[SequenceGenerator]  ── fine-tuned DNA LM ──▶  candidate plasmid sequence(s)
      │
      ▼
[ConstraintEngine]  ── deterministic checks ──▶  ValidationReport (PASS/WARN/FAIL)
      │
      ▼
[Assembler]  ──▶  annotated map + GenBank/FASTA + primers + validation protocol
      │
      ▼
[SynthesisHandoff]  ──▶  order-ready files → provider
      │
      ▼ (weeks later)
[OutcomeCapture]  ──▶  labeled outcome ──▶ back into training data (Phase 5)
```

The retrieval-only MVP (Phase 1) is the path: IntentParser → Retriever → recommendation text. Everything after Retriever is added in later phases. Design every stage so the pipeline can short-circuit: if generation is disabled, return retrieval results; if the constraint engine is disabled, return generated sequences with a "validation unavailable" flag.

### 4.2 Repository structure (monorepo)

Use a single repository. Suggested layout — adapt names but keep the separation of concerns:

```
/
├── SYSTEM_DESIGN.md          # this file (read-only reference)
├── PROGRESS.md               # mutable state file
├── research/                 # Phase R: cited findings + synthesis (see Section 4.5)
│   ├── SYNTHESIS.md
│   ├── bibliography.md
│   └── findings/             # one file per research track
├── Makefile                  # setup, test, lint, run, ingest targets
├── docker-compose.yml        # local Postgres + object store (MinIO) + vector DB
├── .env.example              # documents every required env var (no secrets)
├── packages/
│   ├── core/                 # shared domain types: DesignSpec, ValidationReport, Plasmid, etc.
│   │   └── schemas/          # pydantic models = canonical schemas (Section 12)
│   ├── data_pipeline/        # Phase 0: ingestion, parsing, annotation jobs
│   │   ├── ingest/           # addgene.py, genbank.py, literature.py
│   │   ├── parse/            # sequence_parser.py, component_detector.py
│   │   └── dags/             # orchestration (Airflow or Prefect) definitions
│   ├── retrieval/            # Phase 1: embedder, indexer, retriever, intent_parser
│   ├── generation/           # Phase 2: model loading, training, inference
│   ├── validation/           # Phase 3: constraint engine + individual checks
│   ├── assembly/             # map building, file export, primer design
│   └── feedback/             # Phase 5: outcome capture, retraining orchestration
├── services/
│   ├── api/                  # FastAPI app (Phase 4) — thin layer over packages/*
│   └── worker/               # async job runner (Celery/RQ) for long-running design jobs
├── apps/
│   └── web/                  # Next.js frontend (Phase 4)
├── infra/                    # IaC (Terraform), deployment manifests
├── data/                     # gitignored; local data, gold sets live under data/eval/
└── tests/                    # mirror of packages/ with unit + integration tests
```

**Rule:** business logic lives in `packages/`. `services/` and `apps/` are thin. This keeps the ML/biology logic testable without spinning up the web stack, and lets the agent build and test packages in isolation before wiring the API.

### 4.3 The interface contracts (swap-ability is mandatory)

Every external-model-dependent or infrastructure-dependent component sits behind a small interface so it can be swapped (e.g. change embedding model, change LLM provider, change vector DB) without touching callers. Define these in `packages/core` early. Pseudocode (Python; adapt types as needed):

```python
class IntentParser(Protocol):
    def parse(self, free_text: str, clarifications: list[str] | None = None) -> DesignSpec: ...

class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[Vector]: ...
    @property
    def dim(self) -> int: ...

class VectorIndex(Protocol):
    def upsert(self, ids: list[str], vectors: list[Vector], metadata: list[dict]) -> None: ...
    def query(self, vector: Vector, k: int, filters: dict | None = None) -> list[Match]: ...

class Retriever(Protocol):
    def retrieve(self, spec: DesignSpec, k: int = 5) -> list[RetrievedPlasmid]: ...

class SequenceGenerator(Protocol):
    def generate(self, spec: DesignSpec, templates: list[RetrievedPlasmid], n: int = 1) -> list[GeneratedSequence]: ...

class ConstraintEngine(Protocol):
    def validate(self, sequence: AnnotatedSequence, spec: DesignSpec) -> ValidationReport: ...
```

Each interface gets at least one concrete implementation plus a deterministic **fake** implementation used in tests (e.g. `FakeEmbedder` returning hash-based vectors, `FakeGenerator` returning a template verbatim). The fakes let you test the whole pipeline without GPUs or API keys.

### 4.4 Technology choices (defaults — change only with reason logged in PROGRESS.md)

- **Language:** Python 3.11+ for all backend/ML; TypeScript for the frontend.
- **Bio toolkit:** Biopython for sequence parsing, restriction analysis, and file I/O.
- **Relational store:** PostgreSQL.
- **Object store:** S3 in cloud, MinIO locally (same API).
- **Vector store:** behind `VectorIndex` — local default `pgvector` (so the whole stack runs in Docker Compose with no external account); cloud option Pinecone/Weaviate. Defaulting to pgvector removes a signup dependency for early dev.
- **LLM (intent parsing + recommendations):** behind `IntentParser` — any hosted chat model. Keep prompt + provider in one module.
- **DNA language model:** behind `SequenceGenerator` — start from an open checkpoint (Section 7.2).
- **API:** FastAPI + Pydantic (schemas shared with `packages/core`).
- **Async jobs:** Celery or RQ with Redis broker; long design/generation runs are jobs, not request-blocking.
- **Orchestration:** Prefect or Airflow for data + training DAGs (Prefect is lighter to start).
- **Frontend:** Next.js + `seqviz` for plasmid map rendering.
- **IaC:** Terraform.

---

## 4.5 Phase R — Research & knowledge acquisition (subagent-driven)

**Do this phase first, before writing any production code.** The system designs biological molecules; building on guessed biology produces confidently wrong plasmids. This phase sends out research subagents to read the literature and existing products, and distills what they find into reference files the rest of the build relies on. Treat research as a recurring activity too: whenever a later phase meets a domain question, spin up a focused subagent rather than guessing.

### 4.5.1 The subagent pattern

If your harness supports spawning subagents (Claude Code Task tool, Codex sub-tasks, or equivalent), use them; if not, run each track as a sequential focused research pass. Either way the contract is the same:

- **One subagent per research track.** Each gets a narrow brief, a list of seed sources, and a required output file. Narrow scope keeps each subagent's context focused and its findings high-quality.
- **Every subagent must cite.** No claim lands in a findings file without a source (paper title + authors + year + URL/DOI, or the tool/repo and its docs). Uncited claims are deleted.
- **Subagents read primary sources.** Prefer peer-reviewed papers, preprints (bioRxiv/arXiv), official model cards, and source repositories over blog summaries. Use web search and fetch to retrieve full papers, then extract the parts that affect this build.
- **Subagents distinguish fact from recommendation.** A findings file separates "what the literature establishes" from "what I therefore recommend for this build."
- **Output is structured, not a transcript.** Each findings file follows the template in 4.5.4.
- **Subagents flag uncertainty.** Anything a subagent cannot verify, or where sources conflict, goes into an "Open questions" block that bubbles up to `research/SYNTHESIS.md` and then to `PROGRESS.md`.

The orchestrating agent dispatches the subagents, waits for findings files, reads them, and writes the consolidated `research/SYNTHESIS.md`. It does not start Phase 0 until the Phase R gate (3.05) is met.

### 4.5.2 Questions the build needs answered

`research/SYNTHESIS.md` must explicitly answer each of these. They are the reason Phase R exists:

1. **Plasmid structure** — what are the functional components of a plasmid, in what order/orientation do they typically appear, and what are the rules for a *valid* construct (e.g. promoter must precede GOI; GOI needs a downstream terminator; ORI and marker must match the host)?
2. **Design rules** — what makes a plasmid actually *work* vs. fail? (promoter/host compatibility, codon usage matching the host, element spacing, avoiding internal restriction sites, repeat-induced instability, GC-content windows for synthesis.)
3. **Sequence generation** — which DNA language models exist, what are their architectures, context lengths, training data, capabilities, and **commercial-use licenses**? Which is the best base to fine-tune for *whole-plasmid, component-aware* generation?
4. **Prior art** — what do OriGen, PlasmidGPT, and similar academic models actually do and where do they stop? What do Benchling, SnapGene, VectorBuilder, and Asimov do? What is genuinely unsolved (the gap this build fills)?
5. **Data** — exactly how do you access Addgene and NCBI programmatically, what formats and rate limits apply, what are the licensing terms for training, and how is experimental context represented?
6. **Representation** — how should DNA sequences and their annotations be represented for (a) embedding/retrieval, (b) generation, and (c) validation? (k-mer vs. byte-pair tokenization, feature-coordinate annotation, circular-topology handling.)
7. **Validation** — what are the concrete, codifiable checks for restriction-site conflicts, codon optimization scoring, and regulatory-element compatibility? What tools/databases exist for each (e.g. codon usage tables, restriction enzyme databases)?
8. **Visualization** — how do tools render circular and linear annotated plasmid maps, and what library (e.g. seqviz) and data shape does that require?
9. **Building a system of this scope** — what reference architectures exist for RAG-over-scientific-corpora and for serving fine-tuned generative models in production, and what are the known failure modes?
10. **Biosecurity & compliance** — what sequences/elements of concern must be screened, and what are the obligations for a tool that designs orderable DNA?

### 4.5.3 Research tracks (one subagent each)

Dispatch these subagents. Each line is the brief; the parenthetical is the required output file under `research/findings/`.

- **Track A — Plasmid biology & structure.** Study plasmid anatomy, the role and typical arrangement of ORI / promoter / GOI / marker / MCS / terminator, topology, and what distinguishes a valid from an invalid construct. Seed concepts: molecular cloning fundamentals, vector design reviews. (`plasmid_biology.md`)
- **Track B — Design & validity rules.** Study the rules that make constructs function: promoter/host matching, codon optimization, element spacing, restriction-site avoidance, repeat instability, GC windows for synthesis. (`design_rules.md`)
- **Track C — DNA language models & generation.** Read the model papers and cards: DNABERT / DNABERT-2, Nucleotide Transformer, Evo (Arc Institute), GenSLM, and any newer entrants. Capture architecture, context length, training corpus, tokenization, capabilities, and license terms for commercial use. Recommend a base model for whole-plasmid generation. (`sequence_models.md`)
- **Track D — Prior art & competing/related tools.** Read OriGen and PlasmidGPT (and any successors) in detail; survey Benchling, SnapGene, VectorBuilder, Asimov, and Addgene search. Produce an honest capability matrix and a clear statement of the unsolved gap. (`prior_art.md`)
- **Track E — Data sources & access.** Document programmatic access to Addgene and NCBI (E-utilities/Entrez), formats (GenBank/FASTA), rate limits, bulk-download options, licensing for training use, and how experimental context is represented in each. (`data_sources.md`)
- **Track F — Sequence representation & tokenization.** Study how DNA is tokenized and embedded for ML (k-mer vs. BPE), how annotations/feature coordinates are represented, and how circular topology is handled in linear models. (`representation.md`)
- **Track G — Validation tooling.** Identify concrete tools/databases for each check: Biopython restriction analysis, codon usage tables (e.g. the Codon Usage Database / Kazusa), repeat detection, regulatory-element references. (`validation_tools.md`)
- **Track H — Visualization.** Study seqviz and alternatives for rendering circular/linear annotated maps in the browser; capture the required input data shape. (`visualization.md`)
- **Track I — System architecture & ML-in-production.** Survey reference patterns for RAG over scientific corpora and for serving fine-tuned generative models (inference servers, quantization, eval gating), and known failure modes at this scope. (`architecture_patterns.md`)
- **Track J — Biosecurity & compliance.** Study sequence-of-concern screening obligations and best practices for tools that produce orderable DNA. (`biosecurity.md`)

### 4.5.4 Findings file template

Every file in `research/findings/` follows this shape:

```markdown
# <Track name> — findings

## Scope
<one paragraph: what this track investigated>

## What the literature/sources establish
- <cited fact> [Source: Author et al., Year, title, URL/DOI]
- ...

## What this means for our build
- <recommendation grounded in the facts above>
- ...

## Decisions proposed
- <concrete choice the build should make, e.g. "use DNABERT-2 as the base; license is MIT">

## Open questions / conflicts
- <anything unverified or where sources disagree — these bubble up to SYNTHESIS.md>

## Sources
1. <full citation 1>
2. <full citation 2>
```

### 4.5.5 Research workspace structure

```
research/
├── SYNTHESIS.md            # consolidated decisions; answers all of 4.5.2
├── bibliography.md         # annotated list of every source read, one-line takeaway each
└── findings/
    ├── plasmid_biology.md      # Track A
    ├── design_rules.md         # Track B
    ├── sequence_models.md      # Track C
    ├── prior_art.md            # Track D
    ├── data_sources.md         # Track E
    ├── representation.md       # Track F
    ├── validation_tools.md     # Track G
    ├── visualization.md        # Track H
    ├── architecture_patterns.md# Track I
    └── biosecurity.md          # Track J
```

### 4.5.6 How research feeds the build

The findings files are not write-once. They are referenced by later phases:

- Phase 0 (data) reads `data_sources.md` and `plasmid_biology.md` to build the parser and component detector.
- Phase 1 (retrieval) reads `representation.md` to choose the embedding/document strategy.
- Phase 2 (generation) reads `sequence_models.md` and `representation.md` to choose and configure the base model.
- Phase 3 (validation) reads `design_rules.md` and `validation_tools.md` to implement each check.
- Phase 4 (app) reads `visualization.md` for the map renderer.
- Cross-cutting compliance reads `biosecurity.md`.

When a phase's findings turn out to be incomplete, the agent dispatches a focused follow-up subagent, appends to the relevant findings file (with citations), and notes the update in `PROGRESS.md`. Research never fully "ends"; Phase R is just the up-front bulk of it.

### 4.5.7 Phase R acceptance criteria

All ten findings files exist and are cited; `research/bibliography.md` and `research/SYNTHESIS.md` exist; `SYNTHESIS.md` answers every question in 4.5.2; unresolved biological questions are logged for the human. Only then does Phase 0 begin.

---

## 5. Phase 0 — Data pipeline (detailed)

The whole platform is downstream of data quality. Build this carefully. Everything is idempotent and re-runnable.

### 5.1 Sources

1. **Addgene** — the primary plasmid repository (~130K deposited plasmids), each with metadata, sequence, depositing lab, associated publication, and use-case tags. This is the richest *contextual* source: it links sequences to what they were used for.
2. **NCBI GenBank** (via Entrez/E-utilities) — millions of annotated DNA records; filter to plasmid-complete sequences for a large pretraining/retrieval corpus.
3. **Published literature** (via PubMed/PMC) — papers that reference plasmids. NLP extraction maps free-text experimental descriptions to the plasmids used, producing experimental-context training signal that competitors lack.

### 5.2 Ingestion jobs

Each ingestion job is a function: `fetch → normalize → upsert`, fully idempotent (re-running never duplicates; it upserts by stable source ID).

- `ingest/addgene.py`: pull metadata + sequence per plasmid. Respect rate limits and the source's terms of use; cache raw responses to object storage under `raw/addgene/<id>.json` so re-parsing never re-hits the source. Map into the canonical `plasmids` schema (12.1).
- `ingest/genbank.py`: use Entrez with a query restricted to plasmid-complete records; batch-fetch; cache raw GenBank files under `raw/genbank/`. Parse with Biopython.
- `ingest/literature.py`: query PubMed/PMC for plasmid-referencing papers; store abstracts/full-text where licensing permits; run extraction (5.4).

**Operational rules:** every job records a run row in an `ingestion_runs` table (source, started_at, finished_at, records_seen, records_upserted, errors). Network access is required; if a domain is blocked, surface the proxy deny reason and note it under Blockers in `PROGRESS.md` so the human can update network settings.

### 5.3 Sequence parsing & component annotation

This is the most important Phase 0 component. For each plasmid sequence, detect and label the functional components:

- **Origin of Replication (ORI)** — where copying starts.
- **Promoter** — the expression "on switch."
- **Gene of Interest (GOI)** — the payload.
- **Selectable marker** — usually antibiotic resistance.
- **Multiple Cloning Site (MCS)** — region of restriction sites for inserting DNA.
- **Terminator** — end-of-transcription signal.

Detection strategy, in order of preference:
1. **Use existing annotations** when the source GenBank record already labels features — trust and normalize them.
2. **Reference-feature matching** — maintain a curated library of canonical component sequences (common ORIs, promoters like CMV/EF1a/U6, markers like AmpR/PuroR/KanR) and align candidate regions against it (Biopython pairwise / a fast aligner). High-identity matches get labeled.
3. **Motif/heuristic detection** for anything unmatched (e.g. restriction-site density flags an MCS).

Output is the canonical `AnnotatedSequence` (12.3): the raw sequence plus a list of typed features with start/end coordinates and a confidence score. Records where core components cannot be found are flagged `annotation_incomplete = true` (kept, but excluded from training sets that require full structure).

### 5.4 Literature context extraction

Goal: turn "we expressed GFP-tagged BRCA1 from a doxycycline-inducible lentiviral vector in HEK293 cells to image DNA-repair foci" into a structured `experimental_contexts` row linked to the plasmid(s) used. Use an LLM with a strict JSON-output prompt (behind the same `IntentParser`-style boundary) to extract: organism, cell line, vector type, gene(s), tag(s), promoter type/inducer, application, assay. Store provenance (paper DOI, sentence span) for every extraction so claims are traceable.

### 5.5 Data quality

A `data_quality_report` job computes: total records per source, % with complete component annotation, duplicate clusters (by sequence identity), distribution of organisms / vector types / applications, and null-rates per field. The Phase 0 gate reads from this report.

### 5.6 Phase 0 acceptance criteria

≥ 50,000 fully-parsed, component-annotated records; one CLI command (`make ingest-all` or `prefect deployment run ...`) reproduces the pipeline from an empty database; the quality report is generated and committed under `data/eval/quality/`.

---

## 6. Phase 1 — Retrieval layer (the MVP, detailed)

This phase produces a shippable, demoable product **without any sequence generation**: describe a goal in plain English, get the most relevant real plasmids back with a clear recommendation on how to use/adapt each. Ship this first.

### 6.1 Why retrieval first

It is buildable in weeks, it is genuinely useful (it beats keyword search over the repository), and it produces the query/feedback data you need to train generation later. It also de-risks the NLU and embedding stack before you depend on them for generation.

### 6.2 Embedding service

- Wrap a biomedical text encoder (e.g. a PubMed/BioBERT-family sentence encoder) behind `Embedder`. Do not train from scratch.
- Embed a **composed document per plasmid**: a templated natural-language summary built from its structured fields ("Lentiviral vector expressing GFP-tagged BRCA1 under a doxycycline-inducible promoter; selectable with puromycin; used in HEK293 for live imaging"). Embedding a normalized summary rather than raw metadata makes semantic match to user goals far stronger.
- Store vectors in the `VectorIndex` with metadata for structured filtering (organism, vector_type, marker, etc.).

### 6.3 Intent parser (NLU)

- Behind `IntentParser`. Input: user's free text (+ optional clarification answers). Output: `DesignSpec` (12.4).
- Use an LLM with a strict JSON schema and few-shot examples. The parser must (a) extract entities, (b) normalize colloquial terms to controlled vocabulary (e.g. "293 cells" → `HEK293`), and (c) decide whether a **clarifying question** is needed (ambiguous or missing critical field) and return it instead of guessing.
- Maintain controlled vocabularies (organisms, common cell lines, vector types, marker types, promoter types) in `packages/core` and have the parser map onto them.

### 6.4 Retrieval

- Hybrid search: structured pre-filter (must-match fields like organism/vector type when specified) + semantic ranking via vector similarity over the composed-document embeddings.
- Return `RetrievedPlasmid` objects: the plasmid, its similarity score, and the specific fields that matched.

### 6.5 Recommendation generation

For the top-K, generate a plain-English, ranked explanation: why each is relevant, what to change to fit the user's exact goal (swap promoter, change marker, change backbone), and any caveats. This is an LLM call grounded *only* in the retrieved records (RAG) — never let it invent plasmids not in the corpus.

### 6.6 Evaluation harness

- Build a **gold set** under `data/eval/retrieval_gold.jsonl`: ≥ 20 realistic natural-language queries, each with a human-labeled set of acceptable target plasmids/components.
- Metrics: top-1 / top-5 hit rate, MRR. Run via `make eval-retrieval`.
- The Phase 1 gate is top-5 hit rate ≥ 80% on this set.

### 6.7 Phase 1 acceptance criteria

End-to-end function `design_retrieval(free_text) -> recommendations` works; gold-set metrics meet the gate; results are reproducible and logged.

---

## 7. Phase 2 — Sequence generation (detailed)

Adds the ability to generate a *novel* full-length plasmid sequence, grounded in retrieved templates, rather than only returning existing plasmids.

### 7.1 Principle: ground, don't hallucinate

Generation is always conditioned on (a) the `DesignSpec` and (b) the top-K retrieved templates from Phase 1. The model edits/composes from real validated starting points. This dramatically improves correctness over free generation and mirrors how a human designs (start from a known backbone, modify).

### 7.2 Base model selection

- Do **not** train from scratch. Start from an open DNA language model checkpoint. Reasonable starting points include DNABERT-2 (permissive license, light to fine-tune) and larger genomic models (e.g. Nucleotide Transformer; Evo for long-context single-nucleotide generation — check the commercial-use license before relying on it in production).
- Record the chosen model, version, license, and license-clearance status in `PROGRESS.md`. Licensing for commercial use is a real gate — flag any uncertainty to the human.
- Load behind `SequenceGenerator`. Keep a `FakeGenerator` (returns the top template, optionally with a requested-marker swap) so the rest of the pipeline can be built and tested with no GPU.

### 7.3 Training data formatting

From Phase 0 data, build `(context, template, target)` examples:
- **context** = the composed natural-language goal (or its `DesignSpec`).
- **template** = a closely related plasmid (retrieved as in Phase 1).
- **target** = the actual validated plasmid that fits the context.

Where direct (template → target) pairs are scarce, synthesize training pairs by taking a real plasmid as target and a near-neighbor as template. Hold out a test split by depositing-lab/publication to avoid leakage.

### 7.4 Fine-tuning pipeline

- Runs on managed GPUs (e.g. SageMaker / any GPU host); checkpoints to object storage; logs metrics to the experiment tracker (11.5).
- Parameterized config (base model, LR, epochs, data snapshot id) stored alongside each run for reproducibility.
- Output: a versioned model artifact registered in the model registry (10.4).

### 7.5 Inference service

- Input: `DesignSpec` + retrieved templates. Output: one or more candidate sequences.
- Every generated sequence is immediately **re-annotated by the Phase 0 parser** to confirm it contains the requested components, then passed to the Phase 3 engine. Generation is never returned to the user unvalidated.

### 7.6 Generation evaluation

- Metrics on the gold set: % syntactically valid DNA (only ACGT, sane length), % containing all requested components (per re-annotation), % passing the constraint engine, and novelty (not a verbatim copy of a training plasmid).
- Phase 2 gate: ≥ 70% of gold-set generations are valid, complete, and pass the constraint engine.

---

## 8. Phase 3 — Constraint & validation engine (detailed)

This is deterministic software, **not** ML. It is what makes generated output trustworthy. It must be fast, explainable, and unit-tested exhaustively.

### 8.1 Design

`ConstraintEngine.validate(sequence, spec) -> ValidationReport`. The report contains one entry per check with status `PASS | WARN | FAIL`, a human-readable message, and (where relevant) coordinates of the offending region. `FAIL` on any blocking check means the design is not returned as final; `WARN` is surfaced but not blocking.

### 8.2 Checks (each is an independently unit-tested module)

1. **Restriction-site conflicts** — using Biopython's restriction analysis, detect cut sites that would break intended cloning (e.g. a site inside the GOI that the user's stated cloning strategy depends on cutting only in the MCS). Configurable per the spec's cloning method.
2. **Repeat / instability** — detect direct/inverted repeats above a length threshold and very high/low GC regions that cause synthesis failure or recombination instability.
3. **Codon optimization score** — for the GOI against the target organism's codon usage table; report a score and flag rare-codon clusters. (Scoring/flagging only — actual optimization is a separate assembly step.)
4. **Regulatory compatibility** — promoter ↔ host compatibility (e.g. a mammalian promoter in a bacterial-only context is a FAIL), presence of a selectable marker, ORI ↔ host compatibility, presence of a terminator downstream of the GOI.
5. **Therapeutic-compliance flags** (optional, context-gated) — for gene-/cell-therapy specs, surface advisory flags (e.g. presence of elements discouraged in clinical vectors). Advisory only; never a substitute for regulatory review, and labeled as such.

### 8.3 Acceptance

Curate a profile-diverse known-good and known-bad construct set under `data/eval/validation/`. Gate: engine classifies the curated set with ≥ 95% accuracy. Gold-set size is determined by source quality, provenance, and biological defensibility rather than an arbitrary count. The original ≥50 known-good / ≥50 known-bad planning placeholder was revised on 2026-06-06 after `research/findings/known_good_audit.md` showed that growing known-good from 31 to 50 with the current corpus would require weakening admission standards. Each check has its own targeted unit tests with minimal synthetic sequences.

---

## 9. Phase 4 — Application layer (detailed)

Wraps the pipeline in a real product. Keep `services/` and `apps/` thin over `packages/`.

### 9.1 Backend (FastAPI)

Implements the API contract in Section 13. Long-running design/generation runs are dispatched to the async worker and polled or streamed; the request thread never blocks on a model.

### 9.2 Sessions & the refinement loop

- A **design session** holds the conversation: initial goal, every refinement instruction ("switch the backbone to pLenti-CMV", "add puromycin selection"), and the design state after each turn.
- Each refinement re-runs the pipeline with the accumulated context. Store session + turns in Postgres; cache hot session state in Redis.

### 9.3 Chat-style UI

Describe → design → refine → validate, presented as a conversation where each assistant turn includes the rendered design, its validation report, and the option to refine or export.

### 9.4 Plasmid map visualizer

Use `seqviz` (MIT) to render both circular and linear annotated maps from the `AnnotatedSequence`. Component features are color-coded by type with hover detail. This is the "wow" surface of the product — invest in it.

### 9.5 Exports

GenBank and FASTA export (Biopython writers), plus a primer-design output (forward/reverse primers for the insert with predicted melting temperatures) and a generated validation protocol describing expected sequencing/expression results.

### 9.6 Synthesis handoff

Generate order-ready files and hand off to a synthesis provider (Twist / IDT / GenScript). For MVP this can be a file download plus a deep link / stubbed API call; design the `SynthesisHandoff` interface so a real provider API drops in later. This is also where the referral-commission integration lives commercially.

### 9.7 AuthN/AuthZ, metering, rate limits

Standard auth (email + SSO later), per-account usage metering (designs generated, API calls), tiered rate limits. Meter from day one so billing tiers can attach later.

### 9.8 Acceptance

The Phase 4 gate scenario (Section 3.5) passes on the deployed environment.

---

## 10. Phase 5 — Feedback flywheel & continuous learning (detailed)

The long-term moat: every validated construct makes the model better. No static tool or one-off academic model has this.

### 10.1 Principle

Close the loop from design → real-world wet-lab outcome → training signal → better model. The hard part is not the ML; it is *getting outcomes back* from busy researchers.

### 10.2 Outcome capture

- A few weeks after a design is delivered, prompt the user (in-app + email) with a 3-question outcome form: Did the construct validate? What sequencing result did you get? What expression/functional result did you observe?
- Incentivize completion (e.g. a credit toward the next design unlocks on submission).
- Store outcomes in an `outcomes` table linked to the design + model version that produced it, with explicit user consent for training use.

### 10.3 Turning outcomes into training signal

Confirmed validations become positive `(context, template, target)` examples; failures become negatives (useful for preference-style fine-tuning). Maintain provenance and consent flags on every example.

### 10.4 Model registry, versioning, safe rollout

- Every trained model is registered with version, training-data snapshot id, eval scores, and license status.
- Promotion path: **shadow** (runs alongside, not served) → **canary** (small % of traffic) → **full**. Promotion is gated by an offline eval that must beat the incumbent on the held-out + gold sets. A regression blocks promotion automatically.

### 10.5 Acceptance

The Phase 5 gate (Section 3.6): a captured outcome flows into a scheduled fine-tune, the candidate is evaluated offline, and is promoted only if it beats the incumbent.

---

## 11. Cross-cutting concerns

### 11.1 Local-first development

`make setup` + `docker-compose up` must bring up Postgres (with pgvector), MinIO (S3-compatible), and Redis locally so the entire stack runs on one machine with no cloud accounts. Cloud implementations sit behind the same interfaces.

### 11.2 Configuration & secrets

- All config via environment variables, documented in `.env.example` (committed, no secrets).
- Secrets come from the environment / a secrets manager — never committed, never logged. The agent must never print a secret value.

### 11.3 Idempotency & reproducibility

Every data and training job is idempotent and parameterized by an input snapshot id, so any artifact can be reproduced. Raw source responses are cached to object storage so re-parsing never re-hits external sources.

### 11.4 Observability

Structured logging everywhere; request tracing in the API; job-run tables for every pipeline; basic metrics (latency, error rate, job durations, model inference time). A failed ingestion or training run is visible without reading raw logs.

### 11.5 Experiment tracking

All fine-tuning runs log hyperparameters, data snapshot, and metrics to an experiment tracker (e.g. MLflow/W&B), and the resulting artifact id links to the model registry.

### 11.6 Compliance & ethics posture

This is a scientific design tool. Biosecurity matters: maintain a screening step that flags requests/designs implicating sequences of concern (e.g. select-agent toxins/pathogen elements) for human review, and never auto-fulfill them. Therapeutic-compliance outputs are advisory and clearly labeled as not constituting regulatory approval. Respect every data source's license and terms of use; record license status per source and per model.

### 11.7 Cost control

Generation and training are the cost centers. Cache aggressively (identical `DesignSpec` → cached design), quantize models for serving where quality permits, and batch embedding/inference jobs. Track spend per environment.

---

## 12. Canonical data schemas (reference)

Define these as Pydantic models in `packages/core/schemas`. They are the contract shared by every layer and by the API. (Fields illustrative; keep names stable once set.)

### 12.1 `Plasmid`
`id` (source-stable), `source` (addgene|genbank|literature|generated), `name`, `sequence` (str, ACGT), `length`, `organism`, `vector_type`, `markers` (list), `promoters` (list), `publication_doi` (nullable), `use_cases` (list), `annotation_complete` (bool), `raw_ref` (object-store key), timestamps.

### 12.2 `ExperimentalContext`
`id`, `plasmid_ids` (list), `organism`, `cell_line`, `vector_type`, `genes` (list), `tags` (list), `promoter_type`, `inducer` (nullable), `application`, `assay`, `provenance` (doi + sentence span), `extraction_confidence`.

### 12.3 `AnnotatedSequence`
`sequence` (str), `topology` (circular|linear), `features` (list of `{type, start, end, strand, name, confidence}` where `type` ∈ ORI|promoter|GOI|marker|MCS|terminator|other), `annotation_complete` (bool).

### 12.4 `DesignSpec`  (output of IntentParser; input to everything downstream)
`organism`, `cell_line` (nullable), `vector_type` (nullable), `genes` (list), `tags` (list), `promoter_type` (nullable), `inducer` (nullable), `markers` (list), `application` (nullable), `cloning_method` (nullable), `constraints` (free list), `clarification_needed` (bool), `clarification_question` (nullable).

### 12.5 `ValidationReport`
`overall` (PASS|WARN|FAIL), `checks` (list of `{name, status, message, region (nullable)}`), `generated_by_model_version`.

### 12.6 Supporting types
`RetrievedPlasmid {plasmid, score, matched_fields}`, `GeneratedSequence {annotated_sequence, model_version, parent_template_ids}`, `Match`, `Vector`.

---

## 13. API contract (reference)

Versioned under `/v1`. All long-running operations return a job handle and are polled or streamed.

- `POST /v1/sessions` → create a design session; returns `session_id`.
- `POST /v1/sessions/{id}/design` — body `{ "goal": "<free text>" }`. Parses intent; if `clarification_needed`, returns the question. Else dispatches a design job; returns `job_id`.
- `POST /v1/sessions/{id}/refine` — body `{ "instruction": "<free text>" }`. Refines current design in session context; returns `job_id`.
- `GET /v1/jobs/{job_id}` → status + result. Result includes the `AnnotatedSequence`, `ValidationReport`, retrieved templates, and recommendation text.
- `GET /v1/designs/{design_id}/export?format=genbank|fasta` → file.
- `GET /v1/designs/{design_id}/primers` → primer design output.
- `POST /v1/designs/{design_id}/order` — body `{ "provider": "twist|idt|genscript" }` → order-ready files + handoff link.
- `POST /v1/designs/{design_id}/outcome` — body = outcome form (Phase 5).
- Auth: bearer token; every endpoint metered; tiered rate limits.

In Phase 1, `/design` returns retrieval recommendations only (no generated sequence). The same contract carries generated designs once Phase 2 lands — clients don't change.

---

## 14. Testing strategy

- **Unit tests** for every check in the constraint engine, every parser, and every schema validator, using small synthetic sequences with known properties.
- **Fakes** (`FakeEmbedder`, `FakeGenerator`, in-memory `VectorIndex`) let the full pipeline run in CI with no GPU and no external API. The end-to-end pipeline test uses fakes and asserts the data flows correctly stage to stage.
- **Golden-set evals** (`make eval-retrieval`, `make eval-generation`, `make eval-validation`) are the phase gates; they run on real implementations and produce committed reports under `data/eval/`.
- **Integration tests** for the API run against the Docker Compose stack.
- **CI** runs lint + unit + fake-backed pipeline tests on every commit. Eval suites run on demand / nightly (they need real models/data).
- A change may not be marked complete if it breaks `make test`.

---

## 15. Glossary (for the agent)

- **Plasmid** — a small, circular, self-replicating DNA molecule, separate from the chromosome, that can be engineered to carry chosen genes into cells.
- **ORI (Origin of Replication)** — sequence telling the host cell where to start copying the plasmid; without it the plasmid is lost on division.
- **Promoter** — the "on switch" controlling when/where/how much a gene is expressed (e.g. CMV, EF1a, U6; inducible ones respond to a chemical like doxycycline).
- **Gene of Interest (GOI)** — the payload gene you want expressed.
- **Selectable marker** — a gene (often antibiotic resistance) letting scientists select cells that took up the plasmid.
- **MCS (Multiple Cloning Site)** — a cluster of restriction-enzyme cut sites for inserting DNA.
- **Terminator** — sequence signaling the end of transcription.
- **Restriction site** — a short sequence a restriction enzyme cuts; central to classic cloning.
- **Codon optimization** — adjusting the DNA so the host organism translates the protein efficiently, without changing the protein.
- **Vector type** — the delivery/format class of the construct (e.g. lentiviral, AAV, standard bacterial expression).
- **Backbone** — the structural part of the plasmid (ORI + marker + regulatory scaffold) into which a GOI is inserted.
- **GenBank / FASTA** — standard file formats for annotated / raw DNA sequences.
- **RAG (Retrieval-Augmented Generation)** — retrieve relevant real examples first, then condition generation on them, to stay grounded.

---

*End of System Design Document. The mutable build state lives in `PROGRESS.md`. Begin every session with the startup ritual in Section 0.2.*
