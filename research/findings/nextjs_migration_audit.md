> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Next.js 14 To 16 Migration Audit

## Scope

Audited `apps/web/` and frontend-adjacent configuration for migrating from Next.js 14.2.35 to Next.js 16. Validation-engine paths were intentionally not inspected or changed.

Official references reviewed:

- Next.js 15 upgrade guide: `https://nextjs.org/docs/app/guides/upgrading/version-15`
- Next.js 16 upgrade guide: `https://nextjs.org/docs/app/guides/upgrading/version-16`

## Current Versions

Current resolved frontend package state:

| Package | Current |
| --- | ---: |
| `next` | `14.2.35` |
| `react` | `18.3.1` |
| `react-dom` | `18.3.1` |
| `eslint-config-next` | `14.2.35` |
| `@next/eslint-plugin-next` | transitive `14.2.35` |
| `eslint` | `8.57.x` |
| `@types/react` | `18.3.x` |
| `@types/react-dom` | `18.3.x` |
| `typescript` | `5.9.x` |
| `tailwindcss` | `3.4.x` |
| `postcss` | `8.5.x` |
| `seqviz` | `3.10.x` |

Next 16 requirements relevant to this repo:

| Requirement | Status |
| --- | --- |
| Node.js `20.9.0+` | Local runtime satisfies this; CI/deployment still need confirmation. |
| TypeScript `5.1+` | Satisfied. Do not need TypeScript 6 for this migration. |
| React 19-compatible app/deps | Requires upgrading `react`, `react-dom`, and React type packages. |

## Next.js API Surface

The current app uses very little Next-specific API surface.

| API | Location | Migration Impact |
| --- | --- | --- |
| `Metadata` from `next` | `apps/web/app/layout.tsx` | Still valid. Static metadata only. |
| `dynamic` from `next/dynamic` | `apps/web/components/plasmid-map-view.tsx` | Still valid. Used correctly with `ssr: false` for `seqviz`; highest runtime-risk surface under React 19/Turbopack. |
| Generated `next-env.d.ts` refs | `apps/web/next-env.d.ts` | Normal generated file. |

Not present:

- `next/link`
- `next/image`
- `next/navigation` or legacy `next/router`
- `next/headers`, `cookies()`, `headers()`, `draftMode()`
- route handlers under `app/**/route.ts`
- middleware/proxy files
- server actions
- dynamic route `params` or `searchParams`
- `next/font`, `next/cache`, `unstable_*` cache APIs, or runtime config

## Component Boundaries

| File | Boundary | Notes |
| --- | --- | --- |
| `apps/web/app/layout.tsx` | Server Component | Imports global CSS and exports static metadata. |
| `apps/web/app/page.tsx` | Client Component | Main interactive design workspace, browser storage, polling, downloads. |
| `apps/web/components/plasmid-map-view.tsx` | Client Component | Dynamically imports `seqviz`; includes an error boundary. |
| `apps/web/components/outcome-report-modal.tsx` | Client Component | Focus management and keyboard handling. |
| `apps/web/components/export-actions.tsx` | Client bundle through parent | UI-only export buttons. |
| `apps/web/lib/api.ts` | Client bundle through parent | Browser `fetch`, `window.setTimeout`; no server fetch caching impact. |

The app has no meaningful async request API migration burden because there are no request-time server APIs in use.

## Build Pipeline Surface

Configuration is intentionally small:

- `next.config.mjs` only sets `reactStrictMode: true`.
- `tailwind.config.ts` scans `app`, `components`, and `lib`.
- `postcss.config.js` uses Tailwind 3 plus Autoprefixer.
- `tsconfig.json` already uses the Next TypeScript plugin and `moduleResolution: bundler`.

Tailwind/PostCSS risk is low. The main build-pipeline change is that Next 16 defaults `next dev` and `next build` to Turbopack. That must be validated with production build and Playwright, especially for the `seqviz` dynamic client import.

## Lint Surface

`apps/web/package.json` currently has:

```json
"lint": "next lint"
```

Next 16 removes `next lint`. No `.eslintrc*` or `eslint.config.*` currently exists under `apps/web`, so this migration must add an explicit ESLint CLI setup and align `eslint-config-next` / `@next/eslint-plugin-next` with Next 16.

## E2E And Runtime Risk Surface

Existing Playwright coverage is useful for this migration:

- Chat design/refine flow.
- Seqviz map rendering via `data-testid="seqviz-map"`.
- Export downloads.
- Outcome prompt and modal submission.
- Full-stack API-backed flow through `make e2e-test` and `make demo`.

Highest-risk component: `PlasmidMapView` and `seqviz`. `seqviz@3.10.x` declares React 19-compatible peer ranges, but the actual visualization must still be tested under React 19 and Next 16's default Turbopack build/dev pipeline.

## Official Breaking Changes Relevant Here

Next 15:

- React 19 upgrade path is required for current Next releases.
- Async request APIs changed, but this app does not use them.
- Server `fetch` caching changed, but API calls here are browser-side.
- Route handler caching changed, but no route handlers exist.

Next 16:

- Node.js `20.9+` minimum.
- Turbopack default for `next dev` and `next build`.
- `next lint` removed.
- Async request API sync fallbacks removed, but no affected APIs exist here.
- Middleware renamed toward proxy, but no middleware exists here.

## Applicable Codemods

Likely useful:

```powershell
npx @next/codemod@canary upgrade latest
npx @next/codemod@canary next-lint-to-eslint-cli .
```

Likely no-op for this codebase:

- async request API codemods
- middleware-to-proxy codemod
- Turbopack config codemod
- unstable cache API codemods

## Manual Changes Expected

- Upgrade `next`, `react`, `react-dom`, `eslint-config-next`, `@types/react`, and `@types/react-dom` together.
- Replace `next lint` with direct ESLint CLI.
- Add an explicit ESLint config under `apps/web`.
- Confirm Node `20.9+` in CI/deployment/runtime documentation.
- Verify `seqviz` under React 19 and Turbopack with E2E tests.

## Risk Register

| Risk | Severity | Mitigation |
| --- | --- | --- |
| `next lint` removal | High | Migrate to ESLint CLI and explicit config before final verification. |
| Node runtime below `20.9` outside local shell | High | Document and confirm runtime requirement. |
| `seqviz` runtime under React 19 | Medium | Keep `ssr: false`; run E2E map assertions after each major step. |
| Turbopack bundling of `seqviz` | Medium | Run `npm run build` and Playwright; isolate with webpack only if needed. |
| Tailwind/PostCSS under Turbopack | Low/Medium | Verify production build and UI smoke through Playwright. |
| Async request API changes | Low | No current usage. |

## Audit Conclusion

This is not an App Router rewrite. The migration should be treated as a dependency/tooling upgrade with focused runtime checks around `seqviz`, React 19, Turbopack, and lint command removal.
