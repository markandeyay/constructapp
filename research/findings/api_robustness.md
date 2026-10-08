> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# API Robustness Audit

Scope: application-layer FastAPI/service code, frontend API client behavior, and existing application/API tests on `phase4-polish`. Excluded: `packages/validation/`, validation gold sets, and performance work.

## Executive Summary

The API has a workable happy path for session creation, design/refine job enqueueing, job polling, and design export, but error handling is not yet robust enough for frontend-renderable heavy-tier behavior. Most failures surface as plain strings, FastAPI's default validation envelope, raw exception messages stored on jobs, or frontend-only timeout errors. Several requested edge cases are either accepted when they should fail early, represented as failed jobs rather than recoverable clarification states, or not represented in the API contract at all.

## Top Findings

### F1. High: Whitespace-only prompts pass request validation and fail later as opaque job errors

Severity: High

Current behavior: `DesignRequest.goal` and `RefineRequest.instruction` use `Field(min_length=1)` with `str_strip_whitespace=True` in `ApiModel` (`services/api/app.py:23-49`). Pydantic validates `min_length` before/after strip behavior in a way that should be confirmed, but the worker handler also strips and raises `ValueError("design job requires non-empty text")` if the queued text is empty (`packages/application/design_jobs.py:22-28`). The frontend blocks empty input client-side (`apps/web/app/page.tsx:45-48`), but direct API callers can still submit whitespace unless API validation definitively rejects it.

Affected requested cases: empty prompt, structured errors.

Recommended top fix: Add explicit non-blank API validation for `goal` and `instruction`, return one consistent structured 422/400 error envelope, and add tests for `""`, whitespace, newline-only, and overlong prompt bodies.

Affected files: `services/api/app.py`, `packages/application/design_jobs.py`, `tests/services/api/test_app.py`, `apps/web/lib/api.ts`.

Test coverage gaps: Existing tests cover missing fields and malformed array fields only (`tests/services/api/test_app.py:264-283`); no tests cover blank strings, whitespace-only strings, or frontend rendering of API validation errors.

### F2. High: API errors are not normalized into a frontend-renderable contract

Severity: High

Current behavior: Not-found responses use `HTTPException(..., detail="session not found")`, `"job not found"`, and `"design not found"` (`services/api/app.py:110-157`). FastAPI validation errors use the default `HTTPValidationError` schema. Job failures expose `error: str | None` on `JobStatusResponse` (`services/api/app.py:58-64`, `packages/application/jobs.py:220-224`, `services/worker/celery_app.py:49-54`). The frontend `request()` reads failures as raw text and throws `ApiError(body || ...)` (`apps/web/lib/api.ts:67-70`), while `exportDesign()` discards the response body and throws only `Export failed with <status>` (`apps/web/lib/api.ts:51-55`).

Affected requested cases: invalid session/job/design IDs, LLM/model inference failures, export failures, structured errors that the frontend can render.

Recommended top fix: Define one API error envelope such as `{ error: { code, message, retryable, field_errors?, details?, correlation_id? } }` for 4xx/5xx and job failure payloads. Add FastAPI exception handlers for validation, not found, export failure, and unhandled application errors. Update frontend `ApiError` to retain `status`, `code`, `retryable`, and field details.

Affected files: `services/api/app.py`, `packages/application/jobs.py`, `services/worker/celery_app.py`, `apps/web/lib/api.ts`, `apps/web/lib/types.ts`, `docs/api/openapi.json`.

Test coverage gaps: Tests assert only status codes for 404/422 (`tests/services/api/test_app.py:286-304`, `tests/application/test_sessions.py:128-135`). There are no contract tests for error body shape, frontend parsing, retryable flags, or OpenAPI error schemas.

### F3. High: Clarification/refinement loop can repeatedly fail or ask again without an explicit state model

Severity: High

Current behavior: The generation spike raises `ValueError("intent clarification required: ...")` when the parsed spec needs clarification (`packages/generation/spike.py:155-158`). Through the job wrapper, that becomes a failed job with a plain error string rather than a successful `awaiting_clarification` result. The frontend can render clarifications only if `job.result` contains `clarification_question` or `design_spec.clarification_needed` (`apps/web/app/page.tsx:70-80`, `apps/web/app/page.tsx:210-215`). Refinement context is the full list of user turns joined with newlines (`services/api/app.py:170-177`, `packages/application/design_jobs.py:22-29`), with no server-side record of whether the previous turn was a clarification request or whether the latest answer resolved it.

Affected requested cases: repeated clarification on refinement turns, non-English prompt if parser cannot confidently infer intent, structured errors.

Recommended top fix: Treat clarification as a first-class non-error job outcome, e.g. `status=succeeded` with `result.clarification_question` and no design, or a distinct `needs_clarification` job status if the API contract allows it. Persist enough turn metadata to distinguish initial design, clarification question, clarification answer, and normal refinement. Add a loop guard or explicit max clarification policy.

Affected files: `packages/generation/spike.py`, `packages/application/design_jobs.py`, `services/api/app.py`, `packages/application/sessions.py`, `apps/web/app/page.tsx`, `tests/application/test_design_jobs.py`, `tests/services/api/test_app.py`.

Test coverage gaps: Existing refinement tests only verify a second turn is appended (`tests/services/api/test_app.py:241-261`, `tests/application/test_sessions.py:93-126`). No tests cover a clarification-needed parser result, answering that clarification, repeated clarification, or non-English/low-confidence prompt handling.

### F4. Medium: Long-running jobs time out only in the frontend, leaving the API without stale/running semantics

Severity: Medium

Current behavior: `pollJob()` times out after 30 seconds and throws `ApiError("Timed out waiting for job ...")` (`apps/web/lib/api.ts:33-47`). The API continues to expose only `queued`, `running`, `succeeded`, or `failed` status with no timestamps in `JobStatusResponse` (`services/api/app.py:58-64`). Application job records do have timestamps in storage (`packages/application/jobs.py:24-35`, `packages/application/sessions.py:80-90`), but they are not returned to the frontend. There is no `stale`, `timeout`, cancellation, retry-after, progress, or resumable polling guidance.

Affected requested cases: job longer than frontend polling timeout, LLM/model inference failures if they take too long to surface.

Recommended top fix: Add `created_at`, `updated_at`, optional `expires_at`, optional `retry_after_ms`, and a documented terminal timeout/stale policy to job status responses. Frontend should render a resumable "still running" state instead of treating 30 seconds as a hard job failure.

Affected files: `services/api/app.py`, `packages/application/jobs.py`, `packages/application/sessions.py`, `apps/web/lib/api.ts`, `apps/web/app/page.tsx`, `apps/web/lib/types.ts`.

Test coverage gaps: No tests cover queued/running polling over time, frontend timeout behavior, stale jobs, retry-after, or polling resumption after timeout.

### F5. Medium: Validation FAIL designs are returned as normal successful jobs with no API-level guidance

Severity: Medium

Current behavior: `GenerationSpikePipeline.run()` always returns a `GenerationSpikeResult` after validation, even when `validation_report.overall` is `FAIL` (`packages/generation/spike.py:165-177`). The serialized result includes `passed` and `validation_report` (`packages/generation/spike.py:293-308`), but `GenerationDesignJobHandler` wraps it as a successful job result (`packages/application/design_jobs.py:29-35`). The frontend summary ignores validation status and can show a generic success message (`apps/web/app/page.tsx:217-226`). There is no API policy for the requested case where all four validation checks fail.

Affected requested cases: design with all four validation checks failing, structured errors.

Recommended top fix: Decide whether validation failure is a successful generated artifact with warnings, a blocked design, or a failed job. Then expose an explicit frontend-facing state such as `result.safety_status`, `result.validation_blocking`, or `job.status="failed"` with structured `validation_report` details. Render validation failure prominently in the UI.

Affected files: `packages/generation/spike.py`, `packages/application/design_jobs.py`, `services/api/app.py`, `apps/web/app/page.tsx`, `apps/web/lib/types.ts`, `tests/application/test_design_jobs.py`.

Test coverage gaps: Application/API tests cover only a PASS example (`tests/application/test_sessions.py:51-55`, `tests/application/test_sessions.py:120-125`). No tests cover WARN/FAIL validation reports, all-checks-failing behavior, or frontend rendering of failed validation.

## Additional Findings

### F6. Medium: Export failures can become 500s or bodyless frontend errors

Severity: Medium

Current behavior: Invalid export format is constrained by FastAPI's `Literal["genbank", "fasta"]` and returns default 422. Missing designs return a string-detail 404 (`services/api/app.py:150-158`). Exceptions from `export_annotated_sequence()` are not caught (`services/api/app.py:158`), so malformed persisted designs or Biopython write failures become generic 500 responses. The frontend drops response bodies on export failures (`apps/web/lib/api.ts:51-55`), and `handleExport()` has no local `try/catch` (`apps/web/app/page.tsx:100-114`).

Affected requested cases: export failures, invalid design IDs, structured errors.

Recommended fix: Catch export exceptions and return structured errors with codes like `design_not_found`, `unsupported_export_format`, and `export_failed`. Frontend export flow should parse the same error envelope and render an inline message.

Affected files: `services/api/app.py`, `packages/application/exports.py`, `apps/web/lib/api.ts`, `apps/web/app/page.tsx`, `apps/web/components/export-actions.tsx`, `tests/application/test_exports.py`, `tests/application/test_sessions.py`.

Test coverage gaps: Tests cover successful GenBank export and library-level unknown format (`tests/application/test_sessions.py:138-161`, `tests/application/test_exports.py:30-33`), but not missing design export body shape, invalid format API response shape, Biopython/export exceptions, or frontend export error rendering.

### F7. Medium: LLM/model inference failures are captured as raw exception strings

Severity: Medium

Current behavior: `FakeJobQueue` and Celery task wrappers catch `Exception` and store `str(exc)` as `error` (`packages/application/jobs.py:220-224`, `services/worker/celery_app.py:49-54`). This preserves basic failure visibility, but loses error type, retryability, stage, model name/version, whether partial artifacts exist, and whether the message is safe for end users.

Affected requested cases: LLM or model inference failures, structured errors.

Recommended fix: Introduce typed application exceptions or a `JobError` model with fields like `code`, `message`, `stage`, `retryable`, `safe_to_show`, and `details`. Ensure logs can keep internal exception detail while API responses stay stable and user-safe.

Affected files: `packages/application/jobs.py`, `services/worker/celery_app.py`, `packages/application/design_jobs.py`, `services/api/app.py`, `apps/web/lib/types.ts`.

Test coverage gaps: Tests assert only raw strings for failure (`tests/application/test_jobs.py:58-71`, `tests/application/test_jobs.py:151-182`). No tests cover typed model failure, retryable transient errors, or sanitized user messages.

### F8. Low: Non-English prompts have no explicit handling or user-facing contract

Severity: Low

Current behavior: The API accepts any non-empty string. The heuristic parser relies largely on English terms and controlled vocabulary matching (`packages/retrieval/intent_parser.py:313-442`). If it cannot infer enough information, it may produce clarification or unknown-organism states; in the spike pipeline, clarification is raised as a failed job (`packages/generation/spike.py:155-158`). There is no language detection, translation policy, or structured `unsupported_language`/`needs_translation` outcome.

Affected requested cases: non-English prompt, repeated clarification, structured errors.

Recommended fix: Decide whether the product supports non-English prompts. If not, reject unsupported language early with a clear structured error. If yes, add translation/language metadata and tests for supported languages.

Affected files: `services/api/app.py`, `packages/retrieval/intent_parser.py`, `packages/application/design_jobs.py`, `apps/web/app/page.tsx`.

Test coverage gaps: No application/API tests exercise non-English prompts, mixed-language prompts, or unsupported-language messaging.

## Recommended Top Fixes

1. Define and enforce a shared structured error envelope across immediate HTTP errors and asynchronous job failures.
2. Make clarification a first-class job outcome instead of a raw failed job string, and persist clarification state across turns.
3. Add explicit non-blank prompt validation at the API boundary with tests for blank/whitespace/overlong inputs.
4. Extend job status with timestamps/retry guidance and update frontend polling to support long-running resumable jobs.
5. Decide and document validation-FAIL semantics, then expose validation failure prominently in the API result and frontend UI.

## Questions for the Human

1. Should a design that produces a sequence but has `validation_report.overall == "FAIL"` be considered a successful job with blocking warnings, or a failed job?
2. Should clarification-needed outcomes use `status="succeeded"` with a clarification result, a new terminal status like `needs_clarification`, or an HTTP/job error code?
3. What is the intended support policy for non-English prompts: reject, best-effort parse, or translate before parsing?
4. What frontend polling SLA should the API contract assume for heavy-tier jobs: 30 seconds, minutes, or indefinite resumable polling?
5. Which error details are safe to show to end users for LLM/model/provider failures, and which should be log-only?
6. Should export failures expose precise causes such as malformed persisted design or writer failure, or only a generic user-facing `export_failed` message?
7. Are session/job/design IDs intended to be opaque unguessable strings only, or should the API validate ID format and return `invalid_id` before lookup?

## Safety Note

No model safety refusal occurred during this audit. The review stayed at the application/API contract level and did not require changing validation logic, gold sets, performance code, or concrete biological design instructions.
