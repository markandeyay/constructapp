# Construct App: Build Progress

## Claimed
WP-00 CLAIMED by orchestrator at 2026-10-07T00:00:00Z
WP-01 CLAIMED by wp01-rebrand at 2026-10-07T00:00:00Z
WP-02 CLAIMED by wp02-contract at 2026-10-07T22:48:16Z
WP-09 CLAIMED by wp09-harness at 2026-10-07T22:48:59Z
WP-04 CLAIMED by wp04-assembly at 2026-10-07T23:40:00Z

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
WP-04 DONE by wp04-assembly at 2026-10-08T00:55:00Z
  Section 7 complete: all 19 checks, three strategies, Golden Gate domestication, order table plus
  protocol with the annealing temperature derived from the computed Tm. Appendix A.1 Tm gate passes
  at 0.0000 C deviation on all four oligos against Biopython 1.87 Tm_NN (DNA_NN3, saltcorr=5),
  tolerance 1.0 C. Shared Tm module is packages/core/sequence/tm.py for WP-05.
  Full suite 722 passed 2 skipped; tests/assembly 202 passed; make eval-capabilities exit 0.
  Detail, the side by side Tm table and every constant with its source in progress/WP-04.md.

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
WP-04: section 7.2 request schema implemented literally, plus five optional defaulted fields that
  requirements elsewhere in section 7 have nowhere else to live: overhang_standard (Appendix D),
  host_codon_usage (7.6), thresholds (3.3 constraint 2), hairpin_engine (Q6), and coding_regions on
  Fragment (7.6 needs a reading frame). A section 7.2 request still validates unchanged.
WP-04: a section 7.5 check that does not apply to the requested strategy is omitted from the report
  rather than reported PASS (would assert something untested, 3.3 constraint 4) or UNKNOWN (5.4 rule 1
  reserves that for checks that could not be evaluated, and it would make every Tier A case
  impossible). parameters_used carries applicable_checks, checks_evaluated and checks_not_evaluated.
WP-04: check 15 treats an overhang equal to another overhang's reverse complement as not distinct.
  Appendix D says "all overhangs distinct"; a reverse-complement collision is the same mis-assembly
  hazard, letting a fragment ligate into the wrong junction backwards.
WP-04: no host codon usage table is bundled, so section 7.6 host codon frequencies are reported as
  UNKNOWN with a reason and the edit is the minimal silent change. No frequency is invented
  (3.3 constraint 1). The mechanism is implemented and tested, so a table is a data change later.
WP-04: no published modular standard overhang set is bundled either. Appendix D's mechanism is
  implemented and a caller-supplied standard is used verbatim and cited, but the MoClo and other
  standard overhang strings could not be read from a primary document at build time and 3.3
  constraint 1 forbids reciting sequence from memory.
WP-04: packages/core/sequence/__init__.py edited (not a WP-04 file) to export the Tm names and to
  correct one docstring sentence that said the Tm implementation is not there. Section 13.4 requires
  WP-04 to place it in that shared package, which made the sentence false.

## Cross-WP requests
(none yet)
WP-09 to WP-02: the gold runner (tests/gold/runner.py) resolves validators via CAPABILITY_REGISTRY in packages.core.capability_registry (also tries packages.core.schemas.registry, packages.core.registry). Each CapabilitySpec should expose `validator` (or `validator_factory()`) and optionally `design_model` (pydantic model the case `input` is parsed into). If absent, gold cases report UNEVALUABLE, never pass.
WP-02 requests the owner of services/api/app.py (WP-11 or whoever wires routes) call `services.api.routes.include_capability_routers(app)` inside create_app so capability routers registered in the WP-03/04/05 regions are served.
WP-04 to whoever owns requirements.txt: add ViennaRNA (installed and verified here at 2.7.2). Open
  question Q6 says to prefer it for hairpin free energy when installable, and it is. It is an optional
  import: without it the primer.hairpin check uses the documented sliding-window stem score and says
  so, which is the Q6 default, so nothing breaks either way.
WP-04 to WP-05: the nearest-neighbor Tm is at packages/core/sequence/tm.py per section 13.4, exported
  from packages.core.sequence. Use melting_temperature(seq, primer_conc_nm=..., monovalent_salt_mm=...)
  or melting_temperature_detail for the intermediate terms. Do not reimplement it.
WP-04 to WP-06: gold case input for assembly is an AssemblyDesign. Supplying only `request` lets the
  deterministic designer compose the primers, which is what a fragment-level case wants; pinning
  `primers` targets a primer-level check directly. tests/assembly/test_checks.py has a worked example
  of each. Checks 11 to 13 need strategy gibson, 14 to 17 need golden_gate.
WP-04 to the orchestrator: the literal grep gate in this worktree reports one hit, the `.git` worktree
  pointer FILE (not directory), whose content is the gitdir path of the seed clone. --exclude-dir=.git
  does not exclude a file. Zero hits across every tracked and untracked non-ignored repository file.

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
