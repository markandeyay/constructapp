> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# FastAPI / Starlette Upgrade Plan

Date: 2026-06-20

## Target

Upgrade the API stack from the current resolved versions:

- `fastapi==0.136.3`
- `starlette==0.51.0`

to:

- `fastapi==0.138.0`
- `starlette==1.3.1`

Rationale:

- Starlette 1.0.1 is the first release line documented as fixing malformed `Host` header handling during `request.url` construction.
- Starlette 1.3.1 is the current stable Starlette release available from PyPI and includes follow-on URL and parser fixes.
- FastAPI 0.138.0 is the current stable FastAPI release available from PyPI.
- FastAPI 0.138.0 resolver metadata accepts Starlette 1.3.1.
- The project does not use the FastAPI router internals affected by FastAPI 0.137.0's breaking route-tree change.

## Upgrade Sequence

### Step 1: Document Audit and Plan

Commit:

- `research/findings/fastapi_starlette_migration_audit.md`
- `research/findings/fastapi_starlette_upgrade_plan.md`

Verification:

- None beyond file review; no runtime code has changed.

### Step 2: Dependency Metadata

Edit `requirements.txt`:

- Change `fastapi>=0.115,<1` to `fastapi>=0.138,<1`.
- Add an explicit Starlette floor and major-version ceiling: `starlette>=1.3.1,<2`.

Then install the targeted runtime dependencies into the local environment:

```powershell
python -m pip install "fastapi>=0.138,<1" "starlette>=1.3.1,<2"
```

Verification checkpoint:

```powershell
python -c "import fastapi, starlette; print(fastapi.__version__, starlette.__version__)"
python -m pytest tests/services/api/test_app.py tests/application/test_sessions.py
make test
```

Expected:

- FastAPI resolves to `0.138.0` or newer `0.x`.
- Starlette resolves to `1.3.1` or newer `1.x`.
- API tests pass.
- Full Python test suite remains at the expected count.

### Step 3: Runtime Verification

Run:

```powershell
make eval-all
make e2e-test
npm run test:e2e
```

Specific API behaviors to confirm through existing tests:

- Structured error envelopes still render for validation, not-found, rate-limit, queue-failure, and job-error paths.
- `429` rate-limit responses include retry metadata.
- `503` queue submission failures remain retryable and sanitized.
- Correlation IDs are preserved through request handling and error responses.
- `/v1/health` reports queue and model-registry status.
- `/v1/metrics` returns JSON and Prometheus-style plaintext.
- Outcome submission, retrieval, and pending-prompt endpoints still respect `X-User-ID`.
- API-backed E2E fixture still runs through the real FastAPI app.

### Step 4: Documentation

Update deployment/runtime documentation only if needed:

- Note that public API deployment requires FastAPI `>=0.138` and Starlette `>=1.3.1,<2`.
- Note that the Starlette 0.51.0 Host-header issue is remediated by the explicit Starlette dependency.
- Do not change frontend documentation or demo walkthroughs in this branch.

### Step 5: Final Project State

Update `PROGRESS.md`:

- Add a build-log entry for the FastAPI/Starlette upgrade.
- Mark the Starlette 0.51.0 vulnerability follow-up as addressed.
- Set `RESUME HERE` to the post-upgrade branch review checkpoint.

Run final verification:

```powershell
make test
make eval-all
make e2e-test
npm run test:e2e
```

Do not push this branch in this session.

## Rollback Plan

If the dependency change causes non-obvious failures in middleware ordering, exception handling, response model serialization, or TestClient behavior:

1. Stop.
2. Leave the audit and plan commits intact.
3. Revert only the dependency metadata change if it has been committed.
4. Document the exact failure in `PROGRESS.md` under Questions for the human / blockers.

Do not attempt a broad API rewrite in this session.
