# Construct Web

Next.js 16 frontend for the Phase 4 design workspace. It provides a chat-style interface, plasmid map rendering, outcome reporting, and export actions against the FastAPI backend.

## Runtime

- Node.js `20.9.0` or newer is required by Next.js 16.
- React 19 is used with the App Router.
- Next.js 16 uses Turbopack by default for `next dev` and `next build`.

## Development

Install dependencies from this directory:

```powershell
npm ci
```

Run the web dev server:

```powershell
npm run dev
```

From the repository root, the same command is available through:

```powershell
make serve-web
```

The web server defaults to `http://127.0.0.1:3000`.

## Environment

`NEXT_PUBLIC_API_URL` points the browser at the FastAPI backend.

```powershell
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:8000"
```

If unset, the app uses `http://127.0.0.1:8000`.

No environment-variable changes were introduced by the Next.js 16 migration.

## Tests

Run the production build:

```powershell
npm run build
```

Run browser integration tests:

```powershell
npx playwright install chromium
npm run test:e2e
```

The default Playwright test mocks the API routes in-browser, so it does not require Docker, Redis, a running FastAPI process, or model inference.

Run lint checks:

```powershell
npm run lint
```

`npm run lint` uses ESLint directly. Next.js 16 removed `next lint`.
