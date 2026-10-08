> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# WIRING-1: Local live application composition

## Decision

Add a dedicated `build_local_app()` composition root, separate from the test-friendly
`create_app()` defaults:

```text
services.api.local_app.build_local_app() -> FastAPI
```

`create_app()` remains the HTTP assembly function with injectable collaborators.
`build_local_app()` owns environment loading, backend selection, schema setup, model
provider selection, retrieval/generation construction, and health metadata.

The local composition must:

1. Prefer one reachable and migrated Postgres backend for sessions, jobs, designs,
   and outcomes.
2. Fall back atomically to the corresponding in-memory stores if Postgres cannot be
   reached or initialized.
3. Execute jobs synchronously through `packages.application.jobs.FakeJobQueue`.
4. Run a real `GenerationDesignJobHandler` backed by the real retrieval, generation,
   reannotation, and deterministic validation components.
5. Select Gemini parsing and recommendation only when `GOOGLE_API_KEY` is non-empty;
   otherwise select `FakeIntentParser` and `TemplateRecommendationGenerator`.
6. Always use `FakeGenerator` for this local target.

The factory should return an application even when optional local infrastructure is
down. A working in-memory retrieval corpus is therefore part of this design, not an
optional test double.

## Current findings

### The default API is intentionally inert

`services/api/app.py` exports `app = create_app()`. Its defaults are
`InMemorySessionStore`, the queue-only `packages.application.sessions.InMemoryJobQueue`,
`InMemoryDesignStore`, and `InMemoryOutcomeStore`. That queue leaves jobs in `queued`,
which is why `docs/demo.md` correctly warns that `make serve-api` can stall.

The synchronous executor required here is the different
`packages.application.jobs.FakeJobQueue`. It creates a job, marks it running, invokes a
`JobHandler`, and stores success or failure before `enqueue()` returns.

### There are two job contract families

`packages/application/sessions.py` contains an older `JobQueue`/`JobRecord` contract
with `enqueue_design()` and `enqueue_refinement()`. `packages/application/jobs.py`
contains the store-backed contract used by `FakeJobQueue` and the Celery adapter:

```python
enqueue(*, session_id, action, payload) -> JobRecord
```

The API's `_enqueue()` compatibility logic currently supports both. The local
composition should use the store-backed family. New live-path tests should stop
expanding the compatibility surface.

### A job ID cannot currently reach the design handler

This is the blocking signature mismatch for persistence. `FakeJobQueue` creates the
job ID before calling:

```python
handler(session_id=session_id, action=action, payload=payload)
```

`GenerationDesignJobHandler` therefore cannot call `DesignStore.create()`, whose
required arguments include `job_id`. The E2E fixture works around this by using a
correlation ID as the design's job ID; the live composition must not copy that.

Change the store-backed `JobHandler` contract to:

```python
def __call__(
    self,
    *,
    job_id: str,
    session_id: str,
    action: str,
    payload: Mapping[str, Any],
) -> Mapping[str, Any]: ...
```

Pass `job_id` from both `FakeJobQueue.enqueue()` and
`services.worker.create_job_task()`. Update Celery handler tests and all handler
implementations at the same time. Keeping the ID in `payload` would blur trusted job
metadata with user-derived data and is not recommended.

### `GenerationSpikePipeline` skips the recommender

`packages/generation/spike.py` currently accepts `parser` and `retriever` directly,
retrieves one template, and never accepts or invokes a `RecommendationGenerator`.
Its result has one `template`, but no `recommendations` or recommendation text.
Meanwhile, `packages/retrieval/pipeline.py` already defines the complete real
retrieval flow:

```text
IntentParser -> HybridRetriever -> RecommendationGenerator -> RetrievalResult
```

Prefer changing `GenerationSpikePipeline` to depend on `RetrievalPipeline`:

```python
@dataclass(frozen=True)
class GenerationSpikePipeline:
    retrieval_pipeline: RetrievalPipeline
    generator: SequenceGenerator
    reannotator: Reannotator
    constraint_engine: ConstraintEngine

    def run(self, free_text: str) -> GenerationSpikeResult:
        retrieval = self.retrieval_pipeline.design_retrieval(free_text, k=1)
        ...
```

This removes duplicated clarification/retrieval orchestration and guarantees that the
same configured recommender used by retrieval is represented in generation results.
`GenerationSpikeResult` should carry `retrieved_templates` and `recommendations`, even
though generation still consumes only the first template.

There is also a result-shape mismatch. `spike_result_as_dict()` emits `spec`,
`template`, and `reannotated_sequence`; `SessionJobResult` and the web application
expect `design_spec`, `retrieved_templates`, and `annotated_sequence`. The current
handler additionally nests that payload under `design`. The frontend can partially
unwrap `design`, but it does not rename the spike fields, so no plasmid map appears.
The handler must explicitly map the domain result to one canonical, top-level API
result rather than exposing the spike serializer.

### Gemini is not implemented

There is no Gemini adapter or `GOOGLE_API_KEY` handling in the repository. Existing
LLM adapters are OpenAI-specific. Add:

- `GeminiIntentClient`, implementing the existing `LLMCall` callable contract used by
  `LLMIntentParser`.
- `GeminiRecommendationClient`, implementing
  `RecommendationLLMClient.complete_json()`.
- Builder support that selects these clients explicitly from local settings.

Use the existing `requests` dependency or add one official Google SDK deliberately;
do not make SDK installation conditional at runtime. Keep model names configurable
(`GOOGLE_INTENT_MODEL`, `GOOGLE_RECOMMENDER_MODEL`) and keep structured JSON
validation in the existing parser/recommender classes.

Provider selection for `build_local_app()` is exact:

| Condition | Parser | Recommender |
| --- | --- | --- |
| `GOOGLE_API_KEY` is non-empty | `LLMIntentParser(GeminiIntentClient)` | `LLMRecommendationGenerator(GeminiRecommendationClient)` |
| key absent or blank | `FakeIntentParser` | `TemplateRecommendationGenerator` |

An absent key is an expected local mode, not a health failure. Invalid credentials or
provider errors occur during a job and must produce a typed failed-job error without
falling back mid-request. Silent provider fallback would make results irreproducible.

## Proposed composition

### Settings and environment loading

Load `.env` once, at the beginning of `build_local_app()`, relative to the repository
root rather than the caller's current directory. Existing `load_dotenv()` helpers only
return a dictionary; they do not populate `os.environ`, while current provider builders
read `os.environ`.

Add one local settings loader with these rules:

1. Parse `.env` using the repository's simple `KEY=value` semantics.
2. Preserve every already-set process environment variable.
3. Use `.env` only for missing variables.
4. Normalize blank secrets to `None`.
5. Materialize a typed `LocalAppSettings`; pass settings into builders instead of
   repeatedly rereading `.env`.
6. Never log secret values.

At minimum the settings object needs `DATABASE_URL`, Postgres connect timeout,
embedding settings, object-store settings if S3 reannotation remains enabled,
`GOOGLE_API_KEY`, both Gemini model names, and local retrieval seed location.

### Backend selection and schema initialization

Use one probe and one decision for all four application stores:

```text
load settings
  -> connect to DATABASE_URL with a short connect_timeout
  -> SELECT 1
  -> run Alembic upgrade head
  -> success: PostgresSessionStore, PostgresJobStore,
              PostgresDesignStore, PostgresOutcomeStore
  -> any failure: InMemorySessionStore, InMemoryJobStore,
                  InMemoryDesignStore, InMemoryOutcomeStore
```

Do not mix Postgres sessions with memory jobs/designs. Foreign keys and restart
semantics require these stores to move as one unit.

Alembic revisions `0001_app_tables` and `0002_outcomes` are authoritative for
application tables. Do not call `PostgresJobStore.ensure_schema()` from this
composition: its standalone `CREATE TABLE` omits migration-owned foreign keys,
indexes, and constraints. Either retain that method only for isolated tests or make it
delegate to the canonical migration path in later cleanup.

After application migrations, initialize the selected retrieval index:

- Postgres mode: construct `PgVectorStore` and call `ensure_schema()` for pgvector and
  `plasmid_embeddings`. The preexisting `plasmids` table and indexed corpus are data
  prerequisites; startup must inspect, not fabricate, corpus data.
- Memory mode: construct `InMemoryVectorStore`, call `ensure_schema()`, and populate it
  from a small checked-in sequence-bearing local corpus using
  `compose_plasmid_document()` and the selected embedder.

The repository currently lacks a reusable in-memory `PlasmidRepository` and a
sequence-bearing bundled local corpus. `curated_seed_manifest.yaml` contains accession
metadata and requires ingestion/network access; retrieval gold files contain expected
IDs but not plasmid sequences. Implementation must add an immutable local seed
repository/artifact before the no-Postgres path can complete a `FakeGenerator` job.
Using API E2E constants or test fixtures from production code is not acceptable.

The memory retrieval path is still a real retrieval pipeline: `HybridRetriever`,
document composition, embeddings, `InMemoryVectorStore`, structured filtering, and the
configured recommender all run. Only persistence and corpus location differ.

### Pipeline graph

Construct one graph and share its instances:

```text
IntentParser (Gemini or fake)
  -> RetrievalPipeline(
       HybridRetriever(
         selected VectorIndex,
         selected Embedder,
         selected PlasmidRepository),
       RecommendationGenerator (Gemini or template))
  -> GenerationSpikePipeline(
       retrieval_pipeline,
       FakeGenerator,
       local reannotator,
       DeterministicConstraintEngine)
  -> GenerationDesignJobHandler(pipeline, design_store)
  -> FakeJobQueue(job_store, handler)
  -> create_app(session_store, queue, design_store, outcome_store, ...)
```

Use a reannotator that does not make MinIO mandatory for the memory path. Since
`FakeGenerator` preserves the selected template sequence, a local implementation can
parse the generated sequence directly. In Postgres mode, `S3TemplateReannotator` may be
used when the object store is reachable, but it should retain its existing
sequence-parser fallback when an object is absent.

The embedding model is part of retrieval correctness. The memory seed must be embedded
with the same embedder used for queries. If the configured transformer cannot be
loaded, either fail that retrieval backend and report it in health or select
`FakeEmbedder` only when `EMBEDDING_FAKE=true`; do not silently change embedding spaces.

### Canonical job result and design persistence

On a successful non-clarification run, the handler should:

1. Map the spike result to `SessionJobResult`.
2. Create one durable design associated with the real `job_id`.
3. Return the API payload below at the top level.

```json
{
  "design_id": "design_...",
  "design_spec": {},
  "clarification_question": null,
  "annotated_sequence": {},
  "validation_report": {},
  "retrieved_templates": [],
  "recommendations": [],
  "recommendation_text": "..."
}
```

`recommendation_text` can be a deterministic rendering of the structured
recommendations. It must not introduce facts outside those recommendations.

A clarification is a succeeded job with `design_spec`,
`clarification_question`, empty retrieval/recommendation lists, and no `design_id`;
no `DesignRecord` is created.

Design creation should be idempotent by `job_id` because the migration already has
`uq_designs_job_id`. Add a `get_by_job_id()`/`create_for_job()` store operation or
handle the unique conflict by returning the existing record. A retry must not create a
second design.

Current `DesignRecord` persists only `annotated_sequence`. Extend its stored result to
include the canonical design artifact (spec, retrieval provenance, recommendations,
validation, and recommendation text), while retaining typed access to
`annotated_sequence` for export. In-memory and Postgres stores must expose identical
behavior. In-memory outcome prompt indexing must also be updated when a design is
created; currently `InMemoryOutcomeStore.design_index` is independent and is populated
only manually in tests. Prefer deriving pending prompts from `DesignStore` plus
`SessionStore`, matching the Postgres query, rather than maintaining a second index.

## GET design endpoint

Add:

```text
GET /v1/designs/{design_id}
```

It should return the same canonical artifact stored by the handler, plus identifiers
and timestamps:

```json
{
  "design_id": "design_...",
  "session_id": "session_...",
  "job_id": "job_...",
  "design_spec": {},
  "annotated_sequence": {},
  "validation_report": {},
  "retrieved_templates": [],
  "recommendations": [],
  "recommendation_text": "...",
  "created_at": "...",
  "updated_at": "..."
}
```

Return the standard `design_not_found` 404 envelope. Apply the same ownership policy
as outcome access once authentication is enforced; for current local sessions, accept
the optional `X-User-ID` convention consistently. Export should continue to read the
same stored record, so GET and export cannot disagree after a restart.

This endpoint is needed for refresh/reload, stable history selection, export recovery,
and outcome context. A job polling response alone is not a durable design read API.

## Health behavior

Extend the existing always-200 `/v1/health` snapshot. It is a local liveness and
diagnostic endpoint, not a Kubernetes readiness gate.

Include:

- `persistence`: selected backend, `status`, and a sanitized fallback reason/type.
- `queue`: existing snapshot; local backend should identify synchronous execution.
- `retrieval`: backend, embedder/model, corpus record count, and readiness.
- `providers`: parser and recommender names; never expose keys.
- `model_registry`: existing snapshot.

Overall status rules:

- `ok`: selected persistence is ready and retrieval has a usable corpus.
- `degraded`: memory persistence was selected because Postgres failed, retrieval is
  unavailable/empty, schema setup failed, or a required local dependency is down.
- Missing `GOOGLE_API_KEY` does not degrade health because fake/template mode is an
  intentional configuration.

Memory fallback can still serve complete design jobs when its seed corpus is ready,
but health remains `degraded` to disclose non-durable application state. Include a
machine-readable reason such as `postgres_unreachable`; do not include connection
URLs, credentials, raw exceptions, or provider responses.

Failed pipeline calls remain job failures returned by `GET /v1/jobs/{job_id}`. Health
must not report `ok` merely because the synchronous queue itself can accept calls.

## Persistence behavior

Postgres mode survives API restarts for sessions, turns, jobs, designs, exports, and
outcomes. A completed synchronous job is visible immediately and remains queryable by
job ID and design ID after restart.

Memory mode is process-local and is lost on restart. All memory collaborators must be
singletons within one built app; constructing stores inside request handlers would
break session/job/design linkage. The health response and startup log must state the
non-durable mode once.

Synchronous execution means the POST request performs pipeline work before returning
the existing `202` response. This preserves the API contract and frontend polling
flow, although the first poll normally observes `succeeded`. It is a local-only
execution policy, not a production queue design.

## Make target and documentation

Add this target without changing the meaning of `serve-api`:

```make
.PHONY: serve-local

serve-local:
	$(PYTHON) -m uvicorn services.api.local_app:build_local_app --factory --host $(API_HOST) --port $(API_PORT)
```

`serve-api` remains useful for the injectable scaffold. Update `docs/demo.md` only in
the implementation change that lands the factory: describe `make serve-local` as the
interactive live path, retain `make demo` as deterministic browser E2E, and state the
Postgres/memory and Gemini/template selection rules.

The target must not start Docker, run ingestion, or download a model implicitly.
Those are explicit setup operations. Startup may run idempotent schema migrations and
build the small bundled memory index.

## Tests

### Composition unit tests

- Existing environment values override `.env`; blank `GOOGLE_API_KEY` selects
  fake/template mode.
- A non-empty key selects both Gemini adapters, with no real network call.
- Successful probe plus migration selects all four Postgres stores and one shared URL.
- Probe, migration, or schema failure selects all four memory stores; no mixed backend
  is possible.
- Memory retrieval startup indexes the bundled corpus with the same embedder used for
  queries.
- Transformer load failure is visible and is not silently replaced by fake embeddings.

Inject probe, migration runner, client factories, and pipeline builders into the
factory's lower-level composition helper so these tests do not require Docker,
provider calls, or model downloads.

### Contract and pipeline tests

- `FakeJobQueue` and Celery task execution pass the created `job_id` to handlers.
- `GenerationSpikePipeline` calls `RetrievalPipeline.design_retrieval(k=1)` and carries
  its structured recommendations into the spike result.
- The handler maps `spec` to `design_spec`, `reannotated_sequence` to
  `annotated_sequence`, and the singular template to `retrieved_templates`.
- A successful handler call creates exactly one design with the actual job ID and
  returns a top-level canonical result.
- Repeating a job does not create a duplicate design.
- Clarification succeeds without creating a design.
- Provider/retrieval/validation failures produce failed jobs with safe typed errors.

### API tests

- POST session -> POST design -> GET job completes synchronously and includes a
  `design_id`, map-ready annotated sequence, retrieval evidence, recommendations, and
  validation.
- Refinement uses accumulated session context and creates a second persisted design.
- `GET /v1/designs/{id}` returns the stored artifact; unknown IDs return the standard
  404.
- Both export formats work for the newly persisted design.
- Outcome creation and pending prompts work without manually editing an in-memory
  index.
- Health covers Postgres, intentional memory fallback, empty corpus, provider mode,
  and queue failure.
- Existing injected `create_app()` tests remain green.

### Integration tests

Add an opt-in Docker/Postgres test that runs migrations against a fresh database,
executes one synchronous fake-generation job, rebuilds the app, and verifies the job,
design GET, export, and outcome records survive. Separately run the no-services memory
smoke path and verify a supported bundled prompt completes.

The browser full-stack suite should gain one configuration using `make serve-local`
with fake embeddings and no Google key. Keep the deterministic `services.api.e2e_app`
suite as the fast, provider-independent regression path.

## Implementation order

1. Normalize job handler `job_id` propagation in fake and Celery execution.
2. Integrate `RetrievalPipeline` and recommendations into `GenerationSpikePipeline`.
3. Define the canonical result mapper and expand `DesignStore` persistence.
4. Add Gemini clients/builders and the typed local settings loader.
5. Add Postgres probe/migration selection and the memory retrieval seed repository.
6. Implement `build_local_app()`, health details, and `GET /v1/designs/{design_id}`.
7. Add `make serve-local`, documentation, unit/integration tests, and a browser smoke
   test.

This order keeps each contract testable before the composition root depends on it and
avoids presenting a live target that can complete jobs but cannot persist or retrieve
the resulting design.
