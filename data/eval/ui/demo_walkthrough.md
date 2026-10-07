# Demo Walkthrough Punch List

- Date: 2026-06-13
- Branch: `demo-readiness`
- Scope: manual walkthrough of `docs/demo.md` against local `make serve-api` and `npm run dev`.
- Action taken: observation only. No UI/API fixes were implemented.

## Environment

- API launched with `make serve-api` from the repo root.
- Web app launched with `npm run dev` from `apps/web`.
- Browser URL: `http://127.0.0.1:3000`.
- API log: `C:\tmp\construct-serve-api.log`.

## What Worked

- The web workspace loads and visually matches the current demo script:
  - left chat/workspace column;
  - right `Plasmid map` panel;
  - disabled `Export` panel;
  - disabled `Lab outcome` panel;
  - `My outcomes` local-history panel.
- The initial prompt box and suggestion chips are visible.
- Submitting the yeast-shuttle demo prompt creates a researcher message and a progress card.
- The progress card shows the expected stages: retrieving templates, generating candidate, and running checks.
- The frontend creates a session and queues a design job through the API.
- The frontend polls `GET /v1/jobs/{job_id}` repeatedly without crashing.
- Pending outcome prompt API calls return successfully.

## Blocking Demo Rough Edge

### Design job does not complete under `make serve-api`

Prompt used:

```text
a yeast shuttle vector with URA3 selection and centromere maintenance
```

Observed:

- The API accepted `POST /v1/sessions/{id}/design` with `202 Accepted`.
- The UI stayed in `Designing and validating plasmid` state for more than a minute.
- The API log showed repeated successful polling of the job endpoint, but no completion event.
- The plasmid map remained in the empty state.
- Export and outcome panels remained disabled.

Impact:

- The 5-minute demo cannot currently be run from only `make serve-api` + `npm run dev` unless a synchronous fake job queue or seeded completed design fixture is used.
- `docs/demo.md` correctly warns to confirm that the design job returns before a meeting, but the demo-readiness path should make that explicit and easy.

Recommended follow-up:

- Add a demo mode that uses the existing fake pipeline synchronously from the API process, or
- Add a `make serve-worker` / `make serve-demo` target that starts the required worker alongside the API, or
- Seed a deterministic completed design and pending outcome prompt for demo purposes.

## Non-Blocking UX Rough Edges

- The progress card timer keeps increasing but does not offer a timeout, retry, or "worker may be offline" explanation.
- The bottom status line says the job is running, but does not explain that a background worker is required.
- The empty plasmid map message is clear, but it does not link to a sample/demo design when no job completes.
- `Lab outcome` and `Export` disabled states are understandable but do not explain how to enable them beyond "Complete a design job."
- `My outcomes` is explicitly browser-local, which is honest but demo viewers may ask why outcomes do not sync from the backend list endpoint.

## Demo Script Adjustment Recommendation

Before showing the product externally, either:

1. Run the demo against a seeded fixture with a known completed `design_id`, or
2. Add a one-command demo runner that starts API, worker/fake queue, and web app together.

Until then, the safe demo script should present the current app as a functional UI shell with API-backed sessions/jobs/outcomes, but not promise a live full design completion unless the backend job path has been verified immediately before the meeting.
