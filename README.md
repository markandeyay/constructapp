# Construct

Construct is an AI-assisted plasmid design system: a researcher describes an experimental goal in natural language, the system grounds the request in real plasmid records, proposes an annotated candidate design, validates it against deterministic molecular-biology constraints, renders the plasmid map, and exports files that can move into normal cloning and review workflows.

Two runnable surfaces matter today: `make serve-local` for the interactive local app, and `make demo` for deterministic end-to-end verification.

## What It Does

Construct turns any design request into a validated plasmid artifact through a single workflow:

1. A researcher describes the construct they want, such as a host, expression goal, selectable marker, reporter, cloning workflow, or template preference.
2. The system parses the request into structured intent and retrieves relevant plasmids from an indexed corpus built from curated records and NCBI GenBank.
3. The local app uses `GOOGLE_API_KEY` with Gemini 2.5 Flash for intent parsing and grounded recommendations when the key is set, then proposes a candidate sequence grounded in the retrieved template rather than inventing an unconstrained backbone.
4. A deterministic validation engine checks restriction-site conflicts, repeat instability, codon-usage fit, and regulatory-element compatibility.
5. The application returns an annotated circular construct with validation evidence, retrieved-template evidence, and export actions for GenBank and FASTA.
6. The outcome system captures wet-lab results so confirmed designs and failures can become future training signal with explicit consent and provenance.

The product surface is a chat-style design workspace: ask for a plasmid, refine it conversationally, inspect the map and validation report, export the sequence, and later record what happened in the lab.

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

Construct uses a curated validation gold set to check whether the deterministic engine recognizes both good and bad constructs. The current curated set contains 36 known-good constructs and 52 known-bad constructs with 100% combined accuracy.

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
