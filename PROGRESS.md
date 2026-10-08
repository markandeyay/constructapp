# Construct App: Build Progress

## Claimed
WP-00 CLAIMED by orchestrator at 2026-10-07T00:00:00Z
WP-01 CLAIMED by wp01-rebrand at 2026-10-07T00:00:00Z
WP-02 CLAIMED by wp02-contract at 2026-10-07T22:48:16Z
WP-09 CLAIMED by wp09-harness at 2026-10-07T22:48:59Z
WP-03 CLAIMED by wp03-aav at 2026-10-07T23:30:00Z

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

WP-03 DONE by wp03-aav at 2026-10-08T01:05:00Z
  Section 6 complete: all 14 section 6.4 checks, the banded limit, the section 6.6 remediation engine, section 6.7 composition, linear map, length budget, GenBank and FASTA.
  Full suite 924 passed 2 skipped (baseline was 520/2); tests/aav 404 passed; eval-capabilities exit 0. Detail in progress/WP-03.md.

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

WP-03: section 6.7 step 2 reads "the user's preference if given and compatible", which could mean silently substituting an incompatible promoter. The composer keeps the stated promoter_preference, records why in AAVDesign.notes, and lets aav.promoter_tissue_match report the WARN that section 6.4 check 8 exists to produce; silently discarding a stated choice would hide the mistake the check is for.
WP-03: section 6.4 lists aav.packaging_limit and aav.sc_capacity separately, so check 1 always measures against the single stranded band and check 7 against the halved one. That way the section 9.4 case of an scAAV cassette sized legally for ssAAV reports exactly one FAIL, on the check that names the reason, which the gold harness requires.
WP-03: aav.internal_repeats scopes itself to the region between the ITRs. The two AAV2 reference ITRs share their 125 bp hairpin core verbatim (right equals reverse complement of D plus the same core), so the ITR pair of every correct cassette is an exact 125 bp direct repeat and counting it would WARN on every valid design, which section 3.4 calls worse than no validator. Checks 2, 3 and 14 police the ITR relationship instead.
WP-03: section 9.3 writes must_also_report: ["remediation_suggestion"], but the field WP-02 added is named remediation and CheckResult forbids extra fields, so a gold case must use ["remediation"] or the object form. Noted for WP-06.
WP-03: section 6.3 allows resolving a transgene by name, but this build has no transgene corpus and validators must not need a database, so the composer refuses with a message naming the fix rather than producing a placeholder sequence that would be exported as orderable DNA. AAVComposer(transgene_resolver=...) is the hook.

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
WP-03 to WP-06: AAV gold cases go in tests/gold/aav/. The registry design_model is AAVValidationInput, which accepts either a full AAVDesign cassette (needed for the order, missing ITR, tandem ITR and CDS cases) or an AAVRequest (more readable for the packaging limit cases). Assert remediation with must_also_report: ["remediation"], not "remediation_suggestion"; the field is named remediation. Remediation is carried on aav.packaging_limit and aav.sc_capacity only.
WP-03 to WP-07: the AAV result panel needs the linear_map_json artifact (topology is always "linear", every element has start, end and fraction_of_cassette) and the length_budget artifact. Do not reuse the circular seqviz renderer, per sections 6.8 and 10.2. GET /v1/aav/parts populates the promoter and polyA selectors.
WP-03 to the owner of services/api/app.py: the AAV router is registered in the WP-03 region of services/api/routes/__init__.py but is still not served, because include_capability_routers(app) is not called from create_app. Same request WP-02 filed.
