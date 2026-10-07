# Construct App: Build Progress

## Claimed
WP-00 CLAIMED by orchestrator at 2026-10-07T00:00:00Z
WP-01 CLAIMED by wp01-rebrand at 2026-10-07T00:00:00Z
WP-02 CLAIMED by wp02-contract at 2026-10-07T22:48:16Z
WP-09 CLAIMED by wp09-harness at 2026-10-07T22:48:59Z

## Done
WP-00 DONE by orchestrator at 2026-10-07T00:00:00Z
  Destination repo seeded with full inherited history, 399 commits, 410 files.
  Remotes attached: origin to constructapp, upstream to the source engine with push disabled.

WP-01 DONE by wp01-rebrand at 2026-10-07T00:00:00Z, verified by orchestrator
  Rebrand complete across 36 files. pytest 381 passed 1 skipped, grep gate zero hits.
  Internal Postgres names kept per Q3. Compose project name pinned to construct.

ORCHESTRATOR self-check on WP-01 found two gaps the package under-reported, both now fixed:
  1. The package reported the grep gate blocked only by the immutable spec file. It was
     also blocked by 8 occurrences in PROGRESS.md and progress/WP-01.md, which this build
     authored and which section 2.3 covers. Rewritten with token-free phrasing.
  2. Services resolved without the volume copy the package proposed. The old database was
     verified empty, 0 tables in public schema, so there was nothing to migrate. Old
     project stopped with volumes preserved, no -v, and the stack restarted as construct-*.
     check_services.py now exits 0.
  The spec file was untracked from the repository and is now gitignored. It quotes the
  retired brand names verbatim, so section 2.3 forbids it as a committed file. It is read
  from the operator path outside the tree and the copy there is byte identical.

WP-09 DONE by wp09-harness at 2026-10-07T22:56:34Z
  Per-capability gold runner (tests/gold/runner.py) asserts overall, the named check, and no unexpected FAIL; adds eval-capabilities (no DB), eval-plasmid, and eval-all/eval-check running both halves.
  pytest 411 passed 1 skipped; eval-check still fails honestly on the empty corpus. Detail in progress/WP-09.md.
WP-02 DONE by wp02-contract at 2026-10-07T23:17:37Z
  Contract, capability registry (with WP-03/04/05 regions) and router block, 14 real GenBank-sourced AAV parts (1 omitted: polya.synthetic_short), shared sequence utilities.
  Full suite 520 passed 2 skipped. Detail and provenance table in progress/WP-02.md and data/parts/PROVENANCE.md.

## Blocked
BLOCKED worktree checkout in C:\Users\yalam\constructapp denied by the local
  permission classifier. Build proceeds in a scratchpad clone that shares the
  same git history and pushes to origin, so no work is lost. Operator action
  needed to materialize the tree at the canonical path. See progress/WP-00.md.

BLOCKED WP-01 rebrand committed, pytest green (381 passed, 1 skipped), but check_services.py failed because pinning the compose project name meant the containers and volumes created under the previous project name were not adopted. RESOLVED by the orchestrator, see the Done section.

## Spec challenges
(none yet)
LICENSE carries a personal copyright holder (Markandeya Yalamanchi). WP-01 left it untouched on purpose. Operator decision needed.
The immutable spec file itself contains the old names (lines 17, 248, 251, 270, 271, 299, 307, 319), so the literal gate-2 grep cannot reach zero while it is in the tree.
WP-02: CheckResult gained one optional field `remediation: list[str] | None = None` at the coordinator's instruction, because sections 6.5, 6.6 and 9.3 require structured remediation that section 5.1 has no field for.
WP-02: .gitignore edited (not a WP-02 file) to un-ignore data/parts/, because data/* is ignored and the registry could not be committed otherwise.
WP-02: section 4.3 example shows tissue_specificity null for CMV; ubiquitous promoters ship with the explicit value "ubiquitous" to match the AAVRequest target_tissue vocabulary.

## Cross-WP requests
(none yet)
WP-09 to WP-02: the gold runner (tests/gold/runner.py) resolves validators via CAPABILITY_REGISTRY in packages.core.capability_registry (also tries packages.core.schemas.registry, packages.core.registry). Each CapabilitySpec should expose `validator` (or `validator_factory()`) and optionally `design_model` (pydantic model the case `input` is parsed into). If absent, gold cases report UNEVALUABLE, never pass.
WP-02 requests the owner of services/api/app.py (WP-11 or whoever wires routes) call `services.api.routes.include_capability_routers(app)` inside create_app so capability routers registered in the WP-03/04/05 regions are served.

## Defaults taken, per section 17
Q1 local directory was not empty, it held the spec only. Reconciled by git init
  plus fetch plus checkout. Nothing deleted, nothing overwritten.
Q2 commit history preserved, not squashed. It is real evidence of work.
Q3 internal Postgres database and user names kept as they are. Only visible
  strings rebranded. Avoids the volume recreation hazard in section 2.2 under
  deadline pressure.
Q4 GOOGLE_API_KEY availability not yet confirmed. Capability validators do not
  need it. Recorded, build proceeds.
Q5 AAV2 ITRs only in the registry.

## Orchestrator: corpus rebuild and evaluation baseline, 2026-10-07

CORPUS REBUILT FROM SCRATCH. No corpus existed locally: the database had zero
  relations, the object store held an empty bucket, no cached raw blobs were in
  the tree, and the 36 curated known-good records contain no AAV elements.
  Rebuilt from NCBI with operator authorization for a contact email, which lives
  only in the gitignored .env and in no committed file.
  Result: 194 records, all 194 embedded with the locally cached PubMedBERT, zero
  errors. 25 of the 26 retrieval gold targets are present. The missing one,
  genbank:PZ138287.1, was rejected by the pipeline's own quality filter.

EVALUATION BASELINE RESET, with the four pre-rebuild dashboards archived to
  data/eval/archive/pre-corpus-rebuild/ rather than deleted. Reason: the
  regression check compares the two most recent dashboards to catch a code
  regression, and the stored previous dashboard described the 82 record corpus
  that no longer exists. Comparing across a corpus swap measures the swap, not
  the code. Full reasoning and both sets of numbers are in that directory's
  README.

CLAIM SAFETY CONSEQUENCE, per section 16. Retrieval ranking is LOWER on the
  rebuilt corpus: mrr 0.7917 against the previously recorded 0.9375, and
  complete annotations 23 against 141. The earlier figures describe a corpus
  that is not in the system any more and must not be quoted as current. The
  plasmid validation gold set is unaffected, since those checks are
  deterministic functions over supplied sequences, and still reports accuracy
  1.0 with the phase 3 gate met.

MAKEFILE PORTABILITY FIX. The five recursive $(MAKE) invocations are now quoted.
  GNU Make 3.81 here resolves to a path containing spaces and parentheses, so
  the unquoted form was a shell syntax error and eval-all could never run.

POSTGRES HOST PORT MOVED to 55432 in the gitignored .env only. A native
  postgresql-x64-18 Windows service owns 5432 on this machine and has no
  plasmid role, which produced an authentication failure over TCP while
  in-container access worked. The compose file already parameterized the port.
  .env.example still documents the generic 5432 default for other machines.

GATE STATUS at this point: make test 520 passed 2 skipped exit 0, make demo
  1 passed exit 0, make eval-all exit 0, make eval-check exit 0 on two
  consecutive runs.
