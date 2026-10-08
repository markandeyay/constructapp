> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Deprecation Warnings Triage

Date: 2026-06-20

Scope: warning cleanup after the FastAPI/Starlette upgrade and README rewrite.

## Baseline

After the FastAPI/Starlette upgrade, `make test` passed with:

- `369 passed`
- `1 skipped`
- `9 warnings`

Focused API/session tests showed the two backend carryover warnings:

- `StarletteDeprecationWarning`: FastAPI's `TestClient` wrapper imported Starlette's legacy `httpx`-backed client.
- `StarletteDeprecationWarning`: `HTTP_422_UNPROCESSABLE_ENTITY` is deprecated in favor of `HTTP_422_UNPROCESSABLE_CONTENT`.

After the first backend cleanup, `make test` passed with:

- `369 passed`
- `1 skipped`
- `2 warnings`

Remaining warnings:

1. `Bio.pairwise2` deprecation warning from `packages/data_pipeline/parse/sequence_parser.py`.
2. `BiopythonParserWarning` from `tests/retrieval/test_embed_corpus.py`, where the test GenBank fixture declared a 400 bp LOCUS but contained a 240 bp ORIGIN.

## Warning Inventory

### Starlette TestClient `httpx` Deprecation

- **Source:** tests imported `TestClient` from `fastapi.testclient`, which re-exported Starlette's legacy `httpx`-backed client.
- **Category:** own test code; fixable.
- **Resolution:** add `httpx2>=2.4,<3` to `requirements.txt` and import `TestClient` from `starlette.testclient` in API/session tests.
- **Verification:** focused API/session suite passed with no TestClient warning.

### Starlette 422 Status Constant Rename

- **Source:** `services/api/app.py` used `status.HTTP_422_UNPROCESSABLE_ENTITY`.
- **Category:** own API code; fixable.
- **Resolution:** replace with `status.HTTP_422_UNPROCESSABLE_CONTENT`.
- **Behavioral impact:** HTTP status code remains `422`; only the constant name changes.
- **Verification:** focused API/session suite passed with no Starlette 422 warning.

### Biopython `pairwise2` Deprecation

- **Source:** `packages/data_pipeline/parse/sequence_parser.py` used `Bio.pairwise2.align.localms` for seeded reference matching.
- **Category:** own parser code; fixable.
- **Resolution:** replace with `Bio.Align.PairwiseAligner` using equivalent local-alignment scoring parameters.
- **Verification:** parser and embed-corpus tests passed with warnings enabled.

### Biopython GenBank Fixture Length Warning

- **Source:** `tests/retrieval/test_embed_corpus.py` fixture declared `LOCUS ... 400 bp` but contained 240 bp of ORIGIN sequence.
- **Category:** own test fixture; fixable.
- **Resolution:** update the fixture LOCUS length to 240 bp.
- **Verification:** embed-corpus test passed with warnings enabled.

## Suppression Policy

No warning suppression was needed for this pass. All observed warnings were from code or fixtures the project controls and were fixed directly.

Future third-party warnings should be suppressed only at the narrowest test/module scope, with a comment naming the upstream package and reason.
