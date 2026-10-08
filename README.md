# Construct

Construct is an AI-assisted construct design system: a researcher describes an experimental goal, the system composes a candidate from real parts and real templates, validates it against deterministic molecular-biology constraints, renders it, and exports files that can move into normal cloning and review workflows.

The architecture is retrieval plus deterministic validation rather than generative sequence modelling, and that is deliberate. Every base in the output traces to the user's own input, a curated part record, a retrieved template, or a published rule.

## Capabilities

Four capabilities exist today. Each shares one contract, one validation report format, and one UI pattern.

| Capability | What it does | Checks |
|---|---|---|
| **Plasmid** | Retrieval-grounded plasmid design with a circular map, conversational refinement, and GenBank and FASTA export | the inherited validation engine |
| **AAV vector** | Composes a cassette from a curated part registry under a banded packaging limit, renders it as a linear map with a length budget table, and when it does not fit, computes which part substitution closes the gap | 14 |
| **Assembly and primers** | Gibson, Golden Gate and simple PCR cloning: primers with nearest-neighbor melting temperatures, an order table, a bench protocol, and a Golden Gate domestication report | 19 |
| **Guide RNA** | Enumerates and ranks guides for SpCas9, SaCas9, LbCas12a and AsCas12a across both strands, with a named published on-target model and an explicitly scoped off-target search | 10 |

Everything else, including cell therapy constructs, antibodies, genetic circuits and pathway design, is on our roadmap and is not built.

Two runnable surfaces matter today: `make serve-local` for the interactive local app, and `make demo` for deterministic end-to-end verification.

## What It Does

For a plasmid request, the workflow is:

1. A researcher describes the construct they want, such as a host, expression goal, selectable marker, reporter, cloning workflow, or template preference.
2. The system parses the request into structured intent and retrieves relevant plasmids from an indexed corpus built from curated records and NCBI GenBank.
3. The local app uses `GOOGLE_API_KEY` with Gemini 2.5 Flash for intent parsing and grounded recommendations when the key is set, then proposes a candidate sequence grounded in the retrieved template rather than inventing an unconstrained backbone.
4. A deterministic validation engine checks restriction-site conflicts, repeat instability, codon-usage fit, and regulatory-element compatibility.
5. The application returns an annotated circular construct with validation evidence, retrieved-template evidence, and export actions for GenBank and FASTA.
6. The outcome system captures wet-lab results so confirmed designs and failures can become future training signal with explicit consent and provenance.

The product surface is a chat-style design workspace with a capability selector. Pick one of the four capabilities, submit a request, inspect the result and its validation report, and export. The plasmid flow additionally supports conversational refinement and recording what happened in the lab afterwards.

### Provenance and export

Designs are composed only from curated parts, and every base is attributable. The three newer capabilities compose exclusively from the curated part registry plus the user's own supplied input, and each design records the provenance of every element it used.

A provenance gate is implemented and tested on top of that. It requires every base of a design to trace to a curated part record, a retrieved template, a user supplied input or a named published rule, verified span by span against the actual part records; it blocks an export outright rather than warning, and a check it cannot evaluate blocks as well rather than passing by default. It also carries a documented interface for a sequence screening backend and an append-only export audit log that records what was exported, when, the validator version and the screening result.

**Stated precisely, because the distinction matters: the gate is wired into one capability's serving route, not all four.** The AAV vector endpoints `POST /v1/aav/design` and `POST /v1/aav/validate` screen every response before returning it. A design whose bases all trace is returned with its GenBank and FASTA artifacts; a design carrying an unattributable span is returned with its validation report intact but with those artifacts withheld and a reason naming the coordinates and the size of the span, because the gate blocks the export rather than the design. One audit entry is appended for each outcome.

The plasmid, assembly and guide RNA export paths do not pass through the gate yet. For assembly and guide RNA the blocker is specific and recorded in `progress/WP-13.md`: the gate's export vocabulary is GenBank and FASTA, and those two capabilities export order tables and guide tables, so gating them means first giving the audit entry a name for a table export. Nothing in this paragraph should be read as a claim about them.

The audit log is append-only JSON Lines at `data/audit/export_audit.jsonl`, overridable with `CONSTRUCT_EXPORT_AUDIT_LOG`. It is runtime state and is not committed.

No external screening backend is configured in this deployment. The default backend is a named no-op whose recorded result says in terms that no external screening examined the design and must not be read as a screening result.

## How It Works

### Retrieval Layer

The retrieval layer embeds natural-language summaries of plasmid records and stores vectors in Postgres with pgvector. Queries combine semantic search with structured filters for biology fields such as host, vector profile, selectable marker, source, and named plasmid lookup. The corpus is drawn from curated seed records and NCBI GenBank records with cached raw blobs so parser improvements can reprocess existing data without refetching.

### Generation Layer

The local app uses a synchronous `FakeJobQueue` and `FakeGenerator` today, with deterministic validation, real export, and real Postgres/pgvector retrieval wired through the app. The production queue path is still future work: Celery plus a durable Postgres-backed job queue.

### Validation Layer

The validation engine is deterministic rather than probabilistic. It evaluates restriction-site conflicts, repeat and synthesis-instability patterns, codon-usage scoring for intended payload coding sequences, and regulatory compatibility across promoters, origins, markers, terminators, and host context. Validation reports include actionable messages, coordinates where available, and context labels that distinguish design-construct failures from source-record uncertainty.

### Application Layer

The backend is a FastAPI service with sessions, turns, async design jobs, export endpoints, outcome endpoints, structured errors, local rate limiting, health checks, and metrics. The frontend is a Next.js 16 workspace with chat-style refinement, validation and retrieval evidence panels, outcome prompts, and a seqviz-based circular plasmid map renderer.

### Feedback Loop

Outcome capture links a design, model version, user-reported lab result, consent flag, timestamps, and provenance. Confirmed outcomes can be transformed into versioned training-signal snapshots, preserving the connection from generated design to wet-lab evidence.

## Validation

Construct uses curated gold sets to check whether the deterministic engine recognizes both good and bad designs. A capability is not considered done because it produces output. It is done when it produces output and correctly rejects bad input.

All four capabilities are measured by one harness, which asserts three things per known-bad case: that the overall severity matches, that the **specifically named** check reports the expected severity, and that no unexpected failure appears anywhere else. The second assertion stops a case passing for the wrong reason. The third catches a validator that happens to be right by accident.

> 179 of 179 on our curated gold set, spanning four capability types, with 82 known-good and 97 known-bad cases.

| Capability | Tier A | Tier B | Known-bad | Total |
|---|---|---|---|---|
| Plasmid | 25 | 11 | 52 | 88 |
| AAV vector | 10 | 5 | 17 | 32 |
| Assembly and primers | 11 | 5 | 14 | 30 |
| Guide RNA | 10 | 5 | 14 | 29 |

Known-bad cases may also declare the incidental warnings they expect, and when they do the warning set is asserted exactly in both directions, so a warning that fires undeclared and a declared warning that stops firing are both failures. That exists because a case description drifting from its own report is otherwise invisible to every gate.

The set was assembled by this team and has no held-out split, so this number describes recognition on a curated set, not generalization to unseen designs. Say "curated" when quoting it.

Known-good records are tiered:

- **Tier A, strict-clean:** designs that validate with no warnings.
- **Tier B, accepted-with-caveats:** real plasmids that validate with documented warnings, such as intentional biological architecture that should be surfaced but not treated as a hard failure.

This tiering reflects real molecular biology: validated plasmids can have caveats, and the validator should explain them rather than flattening everything into a binary pass/fail label. The same validation layer is used by generation evaluation, demo flows, and continuous evaluation dashboards.

## Getting Started

Requirements:

- Python 3.11 or newer
- Node.js 20.9.0 or newer with npm
- Docker and Docker Compose for local Postgres, pgvector, Redis, MinIO, and service checks
- GNU Make
- Python dependencies from `requirements.txt`, including the current `google-genai` SDK

Clone and set up the project:

```bash
git clone https://github.com/markandeyay/constructapp.git
cd constructapp
cp .env.example .env
make setup
```

On PowerShell, use:

```powershell
Copy-Item .env.example .env
```

Run the backend test suite and service checks:

```bash
make test
```

Start the interactive local app:

```bash
docker compose up -d
make serve-local
make serve-web
```

API startup command:

```bash
python -m uvicorn --factory services.api.local_app:build_local_app --host 127.0.0.1 --port 8000
```

Web startup command:

```bash
cd apps/web && npm run dev
```

Run the deterministic verification demo:

```bash
make demo
```

Run continuous evaluation:

```bash
make eval-all
make eval-check
```

Run the web app checks:

```bash
cd apps/web
npm install
npm run build
npm run lint
npm run test:e2e
```

Use these local development targets from the repository root:

```bash
make serve-api
make serve-web
make serve-local
make e2e-test
make quality-report
make validate-sample MODE=gold
```

The API defaults to `http://127.0.0.1:8000`; the web app defaults to `http://127.0.0.1:3000`. Set `NEXT_PUBLIC_API_URL` when the frontend should target a different API URL.

## Repository Map

- `packages/core/`: shared schemas and contracts.
- `packages/data_pipeline/`: ingestion, parsing, annotation, reprocessing, and corpus-quality jobs.
- `packages/retrieval/`: intent parsing, document composition, embeddings, vector storage, retrieval, recommendation, and evaluation.
- `packages/generation/`: sequence-generator interfaces, local generator wiring, training data, registry, shadow/canary support, and generation evaluation.
- `packages/validation/`: deterministic biological validation checks.
- `packages/application/`: application services, stores, jobs, and export codecs.
- `packages/feedback/`: outcome-to-training-signal derivation.
- `services/api/`: FastAPI application and API surface.
- `services/worker/`: async job worker integration.
- `apps/web/`: Next.js design workspace and Playwright tests.
- `docs/`: demo and operational runbooks.
- `research/findings/`: design notes, audits, policy decisions, and implementation findings.
