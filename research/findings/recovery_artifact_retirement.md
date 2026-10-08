> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Recovery Artifact Retirement Proposal

## Scope

Audit local recovery artifacts on `demo-readiness`:

- `backup/phase3-hardening-before-recovery`
- `backup/phase4-polish-contaminated`
- `stash@{0}` (`On phase4-polish: pre-recovery mixed phase3-phase4 worktree`)

No branch, stash, or remote state was modified during this audit.

## Commands Inspected

- `git status --short --branch`
- `git log --oneline --decorate -n 20`
- `git stash list`
- `git branch --list "backup/phase3-hardening-before-recovery" "backup/phase4-polish-contaminated" --verbose --no-abbrev`
- `git log --oneline --decorate --graph --boundary demo-readiness backup/phase3-hardening-before-recovery backup/phase4-polish-contaminated -n 80`
- `git rev-parse demo-readiness backup/phase3-hardening-before-recovery backup/phase4-polish-contaminated "stash@{0}" "stash@{0}^1"`
- `git stash show --stat "stash@{0}"`
- `git log --oneline demo-readiness..backup/phase3-hardening-before-recovery`
- `git log --oneline demo-readiness..backup/phase4-polish-contaminated`
- `git diff --stat demo-readiness..backup/phase4-polish-contaminated`
- `git branch --contains backup/phase3-hardening-before-recovery`
- `git branch --contains backup/phase4-polish-contaminated`
- `git show --stat --oneline --decorate af034bb`
- `git show --stat --oneline --decorate efa473c`
- `git show --stat --oneline --decorate 2603d64`
- `git show --stat --oneline --decorate 7485c6e`
- `git stash show --patch --stat "stash@{0}"`
- `git show --stat --oneline --decorate "stash@{0}"`
- `git show --name-status --oneline --decorate "stash@{0}"`
- `git log --oneline --decorate --all --grep="Polish API error handling"`
- `git show --stat --oneline --decorate 74bea19`
- `rg -n "MetricsCollector|correlation|X-Correlation-ID|api_request_completed|/v1/metrics|api_job_queued" services/api/app.py packages tests research/findings PROGRESS.md`

## Current State

`demo-readiness` is clean and currently points at:

- `1ac230d` `Record consolidated shadow and outcome UI state`

The audited refs point at:

- `backup/phase3-hardening-before-recovery`: `acae025cdf030d7384ee64ba47af6de4656114aa`
- `backup/phase4-polish-contaminated`: `2603d6455840af421acb46781ac623449e82ebc2`
- `stash@{0}`: `b7308be4f24fd62c7ac1168d02f2d7febb12b445`
- `stash@{0}^1`: `2603d6455840af421acb46781ac623449e82ebc2`

## Artifact Findings

### `backup/phase3-hardening-before-recovery`

Recommendation: safe to retire after this proposal is accepted.

Evidence:

- `git branch --contains backup/phase3-hardening-before-recovery` lists `demo-readiness`, `master`, `phase4-iteration`, and both backup branches.
- `git log --oneline demo-readiness..backup/phase3-hardening-before-recovery` returns no commits.
- The branch tip `acae025` is already reachable from `demo-readiness`.

What would be lost if retired:

- Only the convenience branch name for the pre-recovery checkpoint.
- No unique commit content would be lost, because the branch tip is contained by `demo-readiness`.

### `backup/phase4-polish-contaminated`

Recommendation: safe to retire after this proposal is accepted, with optional final tag/manifest if a named contamination checkpoint is still useful.

Evidence:

- `git branch --contains backup/phase4-polish-contaminated` lists only `backup/phase4-polish-contaminated`, so the exact commit is not reachable from `demo-readiness`.
- `git log --oneline demo-readiness..backup/phase4-polish-contaminated` shows two commits:
  - `2603d64` `Polish frontend design workflow`
  - `af034bb` `Add curated known-bad validation set`
- Those two commits match recovered commits already present in the current history by title, files, and line stats:
  - `af034bb` matches `efa473c` (`Add curated known-bad validation set`): 3 files, 457 insertions.
  - `2603d64` matches `7485c6e` (`Polish frontend design workflow`): 5 files, 377 insertions, 71 deletions.
- The current branch history includes the recovery commits:
  - `dbea59a` `Recover Phase 3 hardening artifacts from retained stash`
  - `e0e73b6` `Recover Phase 4 polish artifacts from retained stash`

What would be lost if retired:

- The exact contaminated branch topology and commit IDs `af034bb` and `2603d64`.
- No currently identified unique file content, because the same substantive changes were recovered into current history under replacement commit IDs.
- The large `git diff --stat demo-readiness..backup/phase4-polish-contaminated` is mostly a snapshot-age comparison against a much newer `demo-readiness`; it should not be interpreted as evidence of unique work on the backup branch.

### `stash@{0}`

Recommendation: safe to retire after this proposal is accepted, but retire it last.

Evidence:

- `git stash list` identifies it as `On phase4-polish: pre-recovery mixed phase3-phase4 worktree`.
- The stash base is `stash@{0}^1 = 2603d64`, the contaminated phase 4 branch tip.
- `git stash show --stat "stash@{0}"` shows only:
  - `PROGRESS.md`: 8 changed lines
  - `services/api/app.py`: 76 insertions, 8 deletions
- The `PROGRESS.md` hunk rewinds the mutable progress note to an older `phase3-hardening` resume state and is stale relative to the consolidated `demo-readiness` history.
- The `services/api/app.py` hunk adds API observability behavior: logging setup, `MetricsCollector`, correlation ID middleware, `X-Correlation-ID`, `/v1/metrics`, queue payload correlation IDs, and `api_job_queued` logging.
- Current `services/api/app.py` already contains those observability features. `rg` found the relevant symbols and endpoints in the current tree, including `MetricsCollector`, `correlation_and_metrics_middleware`, `X-Correlation-ID`, `api_request_completed`, `/v1/metrics`, and `api_job_queued`.
- Current history also contains `74bea19` `Polish API error handling`, which touches `services/api/app.py`, `packages/application/design_jobs.py`, and tests, with broader coverage than the stash-only API hunk.

What would be lost if retired:

- The exact pre-recovery mixed worktree snapshot and stash label.
- The stale `PROGRESS.md` rollback hunk.
- No currently identified unique API behavior, because the material `services/api/app.py` changes are already present on `demo-readiness` and backed by current-history tests.

## Retirement Plan

1. Keep this proposal committed first so the audit trail survives artifact deletion.
2. Optionally create immutable labels before deleting the backup names, if exact recovery labels are still desired:
   - `git tag archive/phase3-hardening-before-recovery acae025cdf030d7384ee64ba47af6de4656114aa`
   - `git tag archive/phase4-polish-contaminated 2603d6455840af421acb46781ac623449e82ebc2`
   - For the stash, record `b7308be4f24fd62c7ac1168d02f2d7febb12b445` in this proposal; a stash object is not a normal long-term archival mechanism.
3. Delete only the fully contained backup branch first:
   - `git branch -d backup/phase3-hardening-before-recovery`
4. Delete the contaminated backup branch only after confirming the replacement commits remain present:
   - `git show --stat --oneline efa473c`
   - `git show --stat --oneline 7485c6e`
   - `git branch -D backup/phase4-polish-contaminated`
5. Drop the stash last, after confirming current API observability is still present:
   - `rg -n "MetricsCollector|X-Correlation-ID|/v1/metrics|api_job_queued" services/api/app.py`
   - `git stash drop stash@{0}`
6. Re-check state:
   - `git status --short --branch`
   - `git branch --list "backup/phase3-hardening-before-recovery" "backup/phase4-polish-contaminated"`
   - `git stash list`

This plan intentionally uses `git branch -D` only for `backup/phase4-polish-contaminated` because Git will not consider that exact contaminated tip merged, even though its substantive patches were recovered into current history under different commit IDs.
