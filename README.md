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

Designs are composed only from curated parts, every base is attributable, and exports are logged. A design containing sequence that cannot be traced to a curated part record, a retrieved template, a user supplied input or a named published rule is blocked from export rather than warned about, and a check that cannot be evaluated blocks as well rather than passing by default. There is a documented interface for a sequence screening backend; no external screening backend is configured in this deployment, and the audit log records that absence explicitly rather than recording a design as clear.

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

**The three newer capabilities** are measured by one harness that asserts three things per known-bad case: that the overall severity matches, that the specifically named check reports the expected severity, and that no unexpected failure appears anywhere else. That third assertion is what catches a validator that happens to be right for the wrong reason.

> 91 of 91 on our curated capability gold set, spanning three capability types, with 46 known-good and 45 known-bad cases.

| Capability | Tier A | Tier B | Known-bad | Total |
|---|---|---|---|---|
| AAV vector | 10 | 5 | 17 | 32 |
| Assembly and primers | 10 | 6 | 14 | 30 |
| Guide RNA | 10 | 5 | 14 | 29 |

**The plasmid capability** has its own older curated set of 36 known-good and 52 known-bad constructs, which it currently passes in full. That set predates the named-check assertion above, so it is measured more weakly and is quoted separately rather than folded into one combined figure.

Both sets were assembled by this team and neither has a held-out split, so these numbers describe recognition on a curated set, not generalization to unseen designs.

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
