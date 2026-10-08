> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Observability Audit

Date: 2026-06-17
Branch: `observability-and-corpus`

Scope: current frontend to FastAPI to queue/worker to retrieval/generation/model inference and back to frontend. This audit intentionally avoids `packages/validation/`, dependency configuration, and existing dependency/security audit documents.

## Executive Summary

The application has a useful lightweight observability start: FastAPI request middleware creates or accepts `X-Correlation-ID`, emits structured-ish request/job-queued logs, returns the correlation ID response header, and exposes in-process request latency/error metrics at `/v1/metrics`. The worker/queue/generation side is much thinner. The API passes the correlation ID into the queued payload, but worker execution does not restore it into the logging context, job/model timings are not wired to metrics, queue depth is not exposed, and model registry health is available only through offline CLI/file access.

The highest-value production-readiness work is not heavy tracing infrastructure. Add a small shared observation contract around the existing primitives: carry `correlation_id` through every frontend request and job result, restore it inside fake/Celery workers, emit per-stage timings and counters, expose queue/job status summaries in `/v1/metrics`, and add a small model status endpoint backed by the existing registry.

## Request Path Walkthrough

### Frontend Submit And Poll

Files: `apps/web/lib/api.ts`, `apps/web/app/page.tsx`, `apps/web/lib/types.ts`

- `handleSubmit()` creates a session when needed, submits `/v1/sessions/{session_id}/design` or `/v1/sessions/{session_id}/refine`, stores `job_id`, and calls `pollJob()`.
- `request()` adds `Content-Type` and `X-User-ID`, but does not create or send `X-Correlation-ID`.
- `exportDesign()` uses raw `fetch()` and does not include `X-User-ID`, `X-Correlation-ID`, or the shared JSON error parsing headers except for response parsing.
- `pollJob()` repeatedly calls `/v1/jobs/{job_id}` until a terminal status or timeout. The frontend state tracks `activeJobId`, elapsed wall time, and user-facing status, but does not retain API correlation IDs or show one in error messages.
- `JobAcceptedResponse` and `JobStatusResponse` types include `job_id` and status/result details, but not `correlation_id`.

### FastAPI API

Files: `services/api/app.py`, `packages/application/observability.py`

- Middleware reads `X-Correlation-ID` or generates a UUID, stores it in a `ContextVar`, measures request duration with `time.perf_counter()`, returns the ID in the response header, records aggregate request metrics, and logs `api_request_completed`/`api_request_failed`.
- `/v1/metrics` returns an in-memory snapshot with aggregate request count, aggregate 5xx error rate, request p50/p95/p99, job duration summary, and model inference summary.
- Design/refine endpoints enqueue a job and pass `correlation_id=get_correlation_id()` into the job payload.
- API logs `api_job_queued` with `session_id`, `job_id`, and action, but does not record enqueue latency, queue depth, or job accepted counters by action.
- Error responses are structured, but correlation ID is present only as an HTTP header, not in the JSON error body that the frontend stores.

### Queue And Worker

Files: `packages/application/sessions.py`, `packages/application/jobs.py`, `services/worker/celery_app.py`, `services/api/e2e_app.py`

- Default `create_app()` uses `InMemoryJobQueue` from `packages/application/sessions.py`, which queues jobs but does not execute them. This is a known live-demo gap.
- E2E uses `FakeJobQueue` from `packages/application/jobs.py`, which synchronously marks queued/running/succeeded or failed around a handler call.
- `CeleryJobQueue` creates a persistent job record and sends a Celery task with `job_id`, `session_id`, `action`, and payload.
- `create_job_task()` marks running, invokes the handler, and marks succeeded/failed.
- Neither fake nor Celery worker restores `payload["correlation_id"]` into `packages.application.observability.set_correlation_id()`, so worker logs cannot automatically share the request correlation context.
- Neither queue implementation exposes queue depth, counts by status, oldest queued age, running job age, worker heartbeat, or failures by stage.

### Generation And Model Inference

Files: `packages/application/design_jobs.py`, `packages/generation/spike.py`, `packages/generation/generator.py`, `packages/retrieval/pipeline.py`, `packages/retrieval/retriever.py`, `packages/generation/registry.py`

- `GenerationDesignJobHandler` converts job payload context into free text, runs `pipeline.run()`, converts clarification errors to a structured success-like result, and serializes successful generation output.
- `GenerationSpikePipeline.run()` performs parse, retrieval, generation, reannotation, validation, and component checks as one uninstrumented block.
- `HybridRetriever.retrieve()` performs exact-name matching, embedding, vector query, repository lookup, structured filtering, and ranking without timing or result-count logs.
- `FakeGenerator.generate()` and `CarbonGenerator.generate()` expose `model_version`, but no inference timing, load timing, token/output sizes, model load failures, or provider/model status are recorded.
- `ModelRegistry` stores model metadata in `data/models/registry.jsonl` and supports CLI/list access, but the running API does not expose active model status, registry freshness, selected model, rollout state, or license/eval status.

## Current Observability Surface

- Request correlation: API middleware supports inbound/outbound `X-Correlation-ID`; API enqueue payload includes the current ID.
- API logs: request completion/failure and job queued events use `log_event()` and include correlation ID when the context is set.
- API metrics: `/v1/metrics` exposes in-process aggregate request latency/error rate plus currently-unused job/model timing summaries.
- Job status: `/v1/jobs/{job_id}` exposes job status, result/error, timestamps when present, and retry hints for queued/running jobs.
- Frontend user visibility: page state shows submitting/polling/timeout/error and the active job ID.
- Evaluation observability: continuous evaluation dashboards aggregate offline retrieval/generation/validation/quality metrics, but they are not runtime service observability.

## Blind Spots

### 1. Correlation IDs Stop At The Async Boundary

Priority: P0

Evidence:
- API inserts `correlation_id` into job payload in `_enqueue()`.
- `FakeJobQueue.enqueue()` and `create_job_task()` call handlers without setting the `ContextVar`.
- Frontend never creates or stores a correlation ID, and API responses do not include it in JSON envelopes.

Impact: A failed or slow design request can be followed through API request logs to `api_job_queued`, but not reliably through worker logs, generation stage logs, model inference, job polling, export, or frontend error reports.

Recommendation:
- Generate a browser-side `correlationId` per design/refine attempt and send it on create-session, design/refine, poll, outcome, and export calls.
- Add `correlation_id` to `JobAcceptedResponse`, `JobStatusResponse`, and structured API error details or top-level response metadata.
- In `FakeJobQueue.enqueue()` and Celery `run_job()`, read `payload.get("correlation_id")`, call `set_correlation_id()` before handler execution, and reset it in `finally`.
- Include `correlation_id`, `job_id`, `session_id`, `action`, and `stage` in worker/generation logs.

### 2. Latency Metrics Are Too Coarse For The Design Path

Priority: P0

Evidence:
- `MetricsCollector` can store request, job, and model inference timings, but only `record_request()` is called.
- Generation path has no per-stage timing around parse, retrieval, vector query, generator/model load, model generation, reannotation, or validation.
- API request latency measures enqueue and polling endpoints, not end-to-end job completion latency.

Impact: Operators can see that API requests are slow, but cannot tell whether users are waiting on queue backlog, retrieval DB/vector lookup, model load, model inference, object store reannotation, or validation. The current `/v1/metrics` job/model sections will remain zero in normal API operation.

Recommendation:
- Add a minimal timer helper used in `GenerationDesignJobHandler` or `GenerationSpikePipeline.run()` to emit `job_stage_completed` logs and update counters/timers by `stage`.
- Record job duration in both fake and Celery workers from `mark_running` to terminal status.
- Record model inference timing inside `SequenceGenerator.generate()`, with labels for `model_version` and generator class.
- Keep metrics in-process for now, but structure snapshots as `latency_ms.by_stage.{parse,retrieval,generation,reannotation,validation}` instead of one global list.

### 3. Error-Rate Aggregation Is API-Only And 5xx-Only

Priority: P1

Evidence:
- `MetricsCollector.record_request()` increments errors only for status codes `>=500`.
- Job failures are returned as `200` from `/v1/jobs/{job_id}` with `status="failed"`, so user-visible job failures do not affect API error rate.
- Worker failures store only `str(exc)` unless a handler pre-formats structured JSON.

Impact: The system can look healthy at the HTTP layer while design jobs fail, clarification loops spike, model provider failures occur, or validation produces unusable outputs.

Recommendation:
- Add counters for `job_terminal_total{status,action}`, `job_failure_total{stage,error_code,retryable}`, and `api_error_total{status_code,path,error_code}`.
- Treat known non-5xx user-impacting outcomes separately: validation errors, rate limits, poll timeouts, failed jobs, and clarification-required rates.
- Store structured worker errors by default: `code`, `message`, `retryable`, `stage`, `error_type`, and optionally `model_version`, while keeping raw exception details out of user-facing responses.

### 4. Queue Depth And Worker Health Are Not Visible

Priority: P1

Evidence:
- `InMemoryJobQueue` and `InMemoryJobStore` hold job maps, and `PostgresJobStore` stores status timestamps, but there is no summary query or metrics hook.
- Celery enqueue sends a task but does not expose broker queue size, oldest queued job, running count, or task dispatch failures.
- README/PROGRESS note live jobs can remain running without a worker, and the frontend timeout only tells the user to check later.

Impact: A missing worker, stuck worker, Redis outage, or growing queue is visible only as user polling timeouts and manual database/broker inspection.

Recommendation:
- Add a lightweight `queue.snapshot()` protocol returning counts by status, oldest queued age, oldest running age, and recent enqueue failures for in-memory/Postgres stores.
- Include this under `/v1/metrics.jobs.queue` and emit `queue_depth_observed` logs periodically or on `/v1/metrics` reads.
- For Celery, start with app-level persisted job counts from `PostgresJobStore`; broker-native queue depth can be optional later.
- Add a simple worker heartbeat record/log with process start time and last job completion time.

### 5. Model Registry Status Is Offline-Only

Priority: P1

Evidence:
- `ModelRegistry` can list records from `data/models/registry.jsonl`, but API/generation code does not expose active rollout state or selected model metadata.
- `FakeGenerator` and `CarbonGenerator` provide `model_version`, but runtime does not verify that version against the registry.

Impact: A response may show a generated model version in validation details, but operators cannot quickly answer which model is active, whether the registry is readable, whether the selected model is blocked/retired, or whether model metadata/eval/license state is missing.

Recommendation:
- Add `/v1/model-status` or a `model_registry` section in `/v1/metrics` with selected generator version, registry path/read status, active `full`/`canary`/`shadow` versions, rollout state, artifact URI presence, license status, and latest registry timestamp.
- On worker startup or first generation, log `model_selected` with `model_version`, `registry_state`, and `code_revision` when available.
- Add a non-fatal warning counter when the running model version is absent from the registry.

### 6. Frontend/API Traceability Is Incomplete

Priority: P1

Evidence:
- Frontend stores `job_id` and elapsed time but not request/correlation IDs.
- Error messages do not include a support token or correlation ID.
- `exportDesign()` is outside the shared request helper and omits the same tracing/user headers.
- Polling creates many API requests, each with server-generated IDs unless the browser supplies one.

Impact: A user report like "export failed" or "job timed out" cannot be connected to a specific API request or worker execution without server-side guessing by time/job ID.

Recommendation:
- Centralize all frontend fetches through one helper that attaches `X-Correlation-ID`, `X-User-ID`, and `Content-Type` when appropriate.
- Return and persist `correlation_id` alongside `job_id`; show it in detailed error text or a copyable diagnostics block.
- Use one correlation ID for the design/refine operation and propagate it across create-session, enqueue, polls, result display, and export for the resulting design.

### 7. Metrics Storage Is Process-Local And Unbounded

Priority: P2

Evidence:
- `MetricsCollector` stores latencies in lists without max length and lives only inside the FastAPI process.

Impact: Long-running local processes can grow memory usage, and multi-process or restarted deployments lose history. This is acceptable for local smoke observability but weak for production-like operation.

Recommendation:
- Keep the lightweight approach, but cap latency arrays with a ring buffer or fixed-size deque.
- Add cumulative counters separate from rolling latency samples.
- Document `/v1/metrics` as local/process-scoped until a real metrics backend is introduced.

## Prioritized Implementation Plan

### P0: Make A Single Design Attempt Traceable End-To-End

- Add browser-generated correlation IDs and shared frontend fetch plumbing.
- Add `correlation_id` to accepted job/status/error response payloads.
- Restore correlation context in fake and Celery worker execution.
- Emit `job_started`, `job_completed`, and `job_failed` logs with `job_id`, `session_id`, `action`, `correlation_id`, `duration_ms`, and `stage` when known.

### P0: Wire Existing Metrics To Real Job And Model Work

- Record job duration in fake and Celery workers.
- Add stage timers around parser, retrieval, generation, reannotation, and validation.
- Record model inference timing and model version in generator implementations.
- Expand `/v1/metrics` to expose stage-level latency summaries and job terminal counters.

### P1: Add Queue And Worker Visibility Without New Infra

- Add `JobStore.snapshot()` or `JobQueue.snapshot()` for counts by status and age summaries.
- Include queue snapshot under `/v1/metrics`.
- Add a minimal worker heartbeat timestamp and last error summary.
- Surface frontend timeout copy that distinguishes "job still running" from "worker may be offline" when oldest queued/running age suggests a stuck system.

### P1: Expose Runtime Model Status

- Add a small API-accessible model status summary backed by `ModelRegistry` and selected generator metadata.
- Warn/count when selected model version is missing, blocked, retired, or registry is unreadable.
- Include model version and registry state in generation logs and job results.

### P2: Harden Metrics Shape

- Bound in-memory latency samples.
- Split request metrics by route template/method/status family, not raw path with IDs.
- Count 4xx and domain failures separately from 5xx infrastructure failures.
- Add tests that assert a correlation ID appears in API responses, job payloads, worker logs/context, and frontend-visible errors.

## Suggested Lightweight Event Names

- `api_request_completed`
- `api_job_queued`
- `worker_job_started`
- `worker_job_completed`
- `worker_job_failed`
- `generation_stage_completed`
- `model_inference_completed`
- `queue_snapshot_observed`
- `model_registry_status_observed`

Recommended common fields: `correlation_id`, `job_id`, `session_id`, `action`, `stage`, `duration_ms`, `status`, `error_code`, `error_type`, `retryable`, `model_version`, `queue_status_counts`.

## Acceptance Checks

- A design submitted from the browser has one correlation ID visible in frontend diagnostics, API logs, queued payload, worker logs, generation logs, job status response, and final export request.
- `/v1/metrics` shows non-zero job duration and model inference counts after an E2E fake-worker run.
- `/v1/metrics` or `/v1/model-status` reports registry readability and active/selected model state.
- A simulated worker failure increments job failure counters and returns a structured, retryable-safe error detail without leaking raw exception internals.
- A missing worker or stuck queue is visible from metrics without inspecting Redis/Postgres manually.

## Blockers And Open Questions

- The default `services.api.app:app` currently uses a non-executing in-memory queue, so live end-to-end runtime observability cannot be fully exercised without choosing the demo/worker execution model.
- There is no single production composition that wires FastAPI, `PostgresJobStore`, `CeleryJobQueue`, and `GenerationDesignJobHandler` together; observability hooks should be designed around the abstractions but verified once that composition exists.
- The existing metrics collector is process-local; that is acceptable for the recommended lightweight phase but should be documented as non-durable and per-process.
