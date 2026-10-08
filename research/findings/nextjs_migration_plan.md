> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Next.js 16 Migration Plan

## Recommendation

Migrate in reviewable stages:

1. Upgrade from Next 14 to Next 15 with React 19.
2. Migrate linting away from `next lint`.
3. Upgrade from Next 15 to Next 16 and validate Turbopack defaults.

This is preferable to a direct 14 to 16 jump because the official docs split the migration across 14 to 15 and 15 to 16, and the risk boundaries are different: React 19 and async request APIs are concentrated in 15, while Node 20.9, Turbopack defaults, and `next lint` removal are concentrated in 16.

## Baseline

Baseline on `nextjs-migration` before package changes:

- `C:\Program Files (x86)\GnuWin32\bin\make.exe test`: `369 passed, 1 skipped, 14 warnings`
- Branch started clean from current consolidated master at `4485927`.

Frontend package state before migration:

- `next@14.2.35`
- `react@18.3.1`
- `react-dom@18.3.1`
- `eslint-config-next@14.2.35`
- `eslint@8.57.x`
- `seqviz@3.10.x`
- `typescript@5.9.x`

## Step 1: Next 14 To 15

Expected effort: small to medium.

Dependency intent:

- Upgrade `next` to the latest 15.x release.
- Upgrade `react` and `react-dom` to React 19.
- Upgrade `@types/react` and `@types/react-dom` to React 19-compatible types.
- Upgrade `eslint-config-next` to 15.x.
- Avoid TypeScript 6 unless required; current TypeScript 5.9 satisfies Next 16.

Suggested command from `apps/web`:

```powershell
npm install next@15 react@19 react-dom@19 eslint-config-next@15
npm install --save-dev @types/react@latest @types/react-dom@latest
```

Then run:

```powershell
npm run build
npm run test:e2e
```

Manual review after this step:

- Confirm no async request API codemod changes are needed. Current code has no `cookies`, `headers`, route handlers, middleware, dynamic route params, or `searchParams` usage.
- Confirm `seqviz` renders under React 19 through Playwright.
- Commit this step only after build and E2E pass.

Rollback boundary: revert the Step 1 dependency/package-lock commit if React 19 introduces a build or runtime regression.

## Step 2: Lint Migration

Expected effort: small, unless ESLint flat config exposes noisy legacy rules.

Reason: Next 16 removes `next lint`, and `apps/web` currently has no explicit ESLint config.

Preferred implementation:

- Replace `"lint": "next lint"` with `"lint": "eslint ."`.
- Add a minimal `eslint.config.mjs` compatible with Next 16 and ESLint 9/10.
- Upgrade `eslint` only as much as required by the final Next 16 config.

Suggested command if useful from `apps/web`:

```powershell
npx @next/codemod@canary next-lint-to-eslint-cli .
```

Then run:

```powershell
npm run lint
npm run build
npm run test:e2e
```

Rollback boundary: keep lint migration separate so lint config can be reverted without rolling back the Next 15 package state.

## Step 3: Next 15 To 16

Expected effort: medium.

Dependency intent:

- Upgrade `next` to 16.x.
- Upgrade `eslint-config-next` and direct `@next/eslint-plugin-next` if used by the flat config.
- Keep React 19 aligned with Next 16.
- Keep TypeScript 5.9 unless the package manager requires a compatible minor update.

Suggested command from `apps/web`:

```powershell
npm install next@16 react@latest react-dom@latest eslint-config-next@16 @next/eslint-plugin-next@16
npm install --save-dev eslint@^9 @types/react@latest @types/react-dom@latest
```

Then run:

```powershell
npm run lint
npm run build
npm run test:e2e
```

Manual review after this step:

- Confirm Next 16 default Turbopack build succeeds.
- Confirm Playwright dev server starts normally with `npm run dev`.
- Confirm `seqviz-map` remains visible.
- If Turbopack fails in `seqviz`, isolate with a one-off webpack build check before choosing any workaround. Do not make webpack fallback permanent unless explicitly justified.

Rollback boundary: revert only the Step 3 commit to return to a passing Next 15 state.

## Step 4: Documentation

Expected effort: small.

Update:

- `apps/web/README.md` with Next 16, Node `20.9+`, commands, and environment variables.
- Root `README.md` if Node runtime requirements changed from prior docs.

Then run:

```powershell
npm run build
npm run test:e2e
```

## Step 5: Full Verification

Required final verification:

```powershell
C:\Program Files (x86)\GnuWin32\bin\make.exe test
npm run build
npm run test:e2e
C:\Program Files (x86)\GnuWin32\bin\make.exe e2e-test
C:\Program Files (x86)\GnuWin32\bin\make.exe demo
C:\Program Files (x86)\GnuWin32\bin\make.exe eval-all
```

Also confirm through E2E evidence:

- chat interface renders
- design/refine flow still works
- `seqviz` plasmid map still renders
- export buttons still download files
- outcome submission UI still works

## Risk Mitigation

| Risk | Mitigation |
| --- | --- |
| React 19 breaks `seqviz` runtime | Stop and surface if Playwright map check fails and the fix is not obvious. |
| Turbopack bundles a transitive `seqviz` dependency incorrectly | Isolate with a one-off webpack build, then decide whether to fix/import-boundary or surface. |
| ESLint flat config churn | Keep lint migration separate and minimal. |
| Node version mismatch in deployment | Document Node `20.9+` requirement and log as human/ops follow-up if CI/deploy runtime is unknown. |
| TypeScript 6 accidental upgrade | Do not upgrade TypeScript beyond current 5.9 line unless required. |

## Questions For PROGRESS.md

- Confirm CI and deployment Node versions are `>=20.9.0`; Next 16 cannot deploy on Node 18.
- Decide whether package ranges should be exact major ranges after migration or broad `latest`-resolved ranges.
- Decide whether ESLint should target the minimum accepted major `^9` or latest available major if the package manager offers newer.
- If Turbopack exposes a `seqviz` issue, decide whether temporary webpack build fallback is acceptable or Next 16 must ship on Turbopack.
