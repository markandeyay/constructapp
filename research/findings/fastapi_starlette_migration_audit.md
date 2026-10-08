> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# FastAPI / Starlette Migration Audit

Date: 2026-06-20

## Purpose

The dependency audit identified the Starlette 0.51.0 malformed `Host` header URL reconstruction issue as a medium-risk API-stack vulnerability for public deployment. Starlette 1.0.1 fixed malformed `Host` header handling when constructing `request.url`, and later 1.x releases include additional request/URL and parser fixes. This audit scopes the project-specific risk before changing dependencies.

Primary references:

- Starlette release notes: 1.0.1 fixes malformed `Host` header handling for `request.url`; 1.3.0 builds `request.url` from structured components; 1.3.1 adds form parser limit enforcement.
- FastAPI release notes: 0.137.0 changes router internals; 0.138.0 is the latest stable release and adds `app.frontend()` support.

## Current Dependency State

Installed package metadata in the active environment:

- `fastapi==0.136.3`
- `starlette==0.51.0`
- `pydantic==2.12.5`
- `uvicorn==0.40.0`
- `httpx==0.28.1`
- `anyio==4.12.1`

`requirements.txt` currently declares `fastapi>=0.115,<1` and does not declare Starlette directly, so Starlette is resolved transitively. FastAPI 0.136.3 declares `starlette>=0.46.0` with no upper bound in installed metadata.

PyPI resolver dry-run accepts:

- `fastapi==0.138.0`
- `starlette==1.3.1`

## API Stack Usage Catalog

Direct FastAPI imports are limited to `services/api/app.py`:

- `FastAPI`
- `Header`
- `HTTPException`
- `Request`
- `Response`
- `status`
- `RequestValidationError`
- `CORSMiddleware`
- `JSONResponse`
- `PlainTextResponse`

Test imports:

- `fastapi.testclient.TestClient` in `tests/services/api/test_app.py`
- `fastapi.testclient.TestClient` in `tests/application/test_sessions.py`

No direct Starlette imports were found outside FastAPI wrappers.

## API Feature Surface

`services/api/app.py` uses:

- `create_app()` factory with injectable stores, queue, registry, rate limiter, and rate-limit config.
- Pydantic v2 request/response models with `ConfigDict`, `Field`, and `field_validator`.
- Exception handlers for `HTTPException`, `RequestValidationError`, and unhandled `Exception`.
- `CORSMiddleware` via `app.add_middleware`.
- One request middleware via `@app.middleware("http")` for correlation IDs, request timing, structured metrics, and error recording.
- Synchronous path handlers for:
  - `POST /v1/sessions`
  - `GET /v1/health`
  - `GET /v1/metrics`
  - `POST /v1/sessions/{id}/design`
  - `POST /v1/sessions/{id}/refine`
  - `GET /v1/jobs/{job_id}`
  - `GET /v1/designs/{design_id}/export`
  - `POST /v1/designs/{design_id}/outcome`
  - `GET /v1/designs/{design_id}/outcome`
  - `GET /v1/users/me/pending-outcome-prompts`
- Response models on JSON endpoints and explicit `Response` / `PlainTextResponse` for exports and Prometheus-style metrics.

The app does not use:

- WebSockets.
- `BackgroundTasks`.
- FastAPI `Depends`.
- Lifespan/startup/shutdown hooks.
- Mounted sub-apps.
- `APIRouter`.
- Direct iteration or mutation of `app.router.routes` / `router.routes`.
- Custom `APIRoute` or `APIRouter` subclasses.
- Direct `request.url_for()` calls or generated absolute URLs.

## Migration-Risk Assessment

### Low Risk

- The Starlette 1.0.1 Host-header fix is directly relevant and should not require code changes because the app uses `Request.url.path` only for metrics/error paths, not full absolute URL reconstruction.
- FastAPI 0.137.0 route-tree internals should not affect the app because it does not use `APIRouter`, nested routers, custom route classes, or direct route-tree introspection.
- TestClient compatibility is likely stable because current `httpx==0.28.1` satisfies Starlette 1.x `full`-extra compatibility notes and tests only use ordinary HTTP methods.
- Pydantic v2 is already in use; no Pydantic migration is bundled here.

### Medium Risk

- Exception handling and middleware ordering need explicit verification. The API depends on custom JSON error envelopes, correlation ID propagation, metrics recording, and sanitized job errors.
- Rate limiting sits in endpoint helpers and returns structured `429` responses. It must be tested after the middleware stack changes.
- Health and metrics endpoints expose non-standard response behavior (`response_model=None`, content negotiation for `text/plain`) and should be smoke-tested.
- Outcome endpoints rely on header-based user identity via `Header(alias="X-User-ID")`; FastAPI 0.136.3 changed underscore-header handling, so header behavior should remain covered.

### Out of Scope

- Starlette 1.x may contain behavior changes for features not used here, including static files, templates, forms, WebSockets, session middleware, and mounted apps. Those are not part of this API surface.
- Uvicorn does not need a coordinated bump for the FastAPI/Starlette compatibility target. Current `uvicorn==0.40.0` remains within `requirements.txt`.
- Pydantic is already v2.12.5 and should not be changed in this session.

## Audit Conclusion

The project can take a direct compatibility upgrade to FastAPI 0.138.0 and Starlette 1.3.1. This removes the vulnerable Starlette 0.51.0 transitive resolution while staying on current FastAPI and current Starlette stable releases. The migration should require dependency metadata changes only, with verification focused on middleware, exception envelopes, rate limiting, health, metrics, outcome endpoints, API-backed E2E, and continuous evaluation.
