# Construct App: Build Progress

## Claimed
WP-00 CLAIMED by orchestrator at 2026-10-07T00:00:00Z
WP-01 CLAIMED by wp01-rebrand at 2026-10-07T00:00:00Z
WP-02 CLAIMED by wp02-contract at 2026-10-07T22:48:16Z
WP-09 CLAIMED by wp09-harness at 2026-10-07T22:48:59Z
WP-03 CLAIMED by wp03-aav at 2026-10-07T23:30:00Z
WP-04 CLAIMED by wp04-assembly at 2026-10-07T23:40:00Z
WP-05 CLAIMED by wp05-grna at 2026-10-07T23:30:00Z

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

WP-03 DONE by wp03-aav at 2026-10-08T01:05:00Z
  Section 6 complete: all 14 section 6.4 checks, the banded limit, the section 6.6 remediation engine, section 6.7 composition, linear map, length budget, GenBank and FASTA.
  Full suite 924 passed 2 skipped (baseline was 520/2); tests/aav 404 passed; eval-capabilities exit 0. Detail in progress/WP-03.md.

WP-05 DONE by wp05-grna at 2026-10-07T23:59:00Z
  Guide RNA capability complete: both-strand enumeration at the Appendix C PAM offsets, a faithful Rule Set 1 on-target model with domain gating plus a labeled fallback heuristic, a faithful MIT specificity off-target model over a declared non-genome-wide space, all nine section 8.5 checks plus the section 8.6 off-target check, ranked output with per guide reasoning and cloning oligos.
  Full suite 764 passed 2 skipped (WP-02 baseline 520 plus 244 new); tests/grna green; make eval-capabilities exit 0. Detail in progress/WP-05.md.

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

WP-03: section 6.7 step 2 reads "the user's preference if given and compatible", which could mean silently substituting an incompatible promoter. The composer keeps the stated promoter_preference, records why in AAVDesign.notes, and lets aav.promoter_tissue_match report the WARN that section 6.4 check 8 exists to produce; silently discarding a stated choice would hide the mistake the check is for.
WP-03: section 6.4 lists aav.packaging_limit and aav.sc_capacity separately, so check 1 always measures against the single stranded band and check 7 against the halved one. That way the section 9.4 case of an scAAV cassette sized legally for ssAAV reports exactly one FAIL, on the check that names the reason, which the gold harness requires.
WP-03: aav.internal_repeats scopes itself to the region between the ITRs. The two AAV2 reference ITRs share their 125 bp hairpin core verbatim (right equals reverse complement of D plus the same core), so the ITR pair of every correct cassette is an exact 125 bp direct repeat and counting it would WARN on every valid design, which section 3.4 calls worse than no validator. Checks 2, 3 and 14 police the ITR relationship instead.
WP-03: section 9.3 writes must_also_report: ["remediation_suggestion"], but the field WP-02 added is named remediation and CheckResult forbids extra fields, so a gold case must use ["remediation"] or the object form. Noted for WP-06.
WP-03: section 6.3 allows resolving a transgene by name, but this build has no transgene corpus and validators must not need a database, so the composer refuses with a message naming the fix rather than producing a placeholder sequence that would be exported as orderable DNA. AAVComposer(transgene_resolver=...) is the hook.

WP-05: section 8.5 lists nine checks and none is an off-target check, but section 8.6 specifies FAIL, WARN and PASS conditions for off-target hits and ValidationReport is the only place a severity can live. One check added, grna.off_target_hits, documented as section 8.6 mandated. Without it a dangerous off-target could not move the overall verdict. Section 8.5, unlike section 6.4, does not forbid additions.
WP-05: section 8.2's five request fields cannot support checks 4, 7, 8 and 9. Five additive defaulted fields added (expression_system, host_context, delivery_construct_name and delivery_construct_sequence, cloning_vector, and the spans cds_region, final_exon_region, constitutive_regions). With only the section 8.2 fields the request stays valid and the affected checks report UNKNOWN with the field to supply, so nothing silently passes.
WP-05: section 8.6 types OffTargetSpace.label as a required str, but it also requires the label never to overstate, and a user could supply "genome-wide". The field is kept and defaulted to the empty string; the text shown in the UI and in every export is generated by the code from the sequences actually searched and their real total size.
WP-05: the no-personal-names rule and Appendix E's read-not-recalled rule meet in two identifiers, doenchParams and calcDoenchScores. They are the literal names of the coefficient table and function inside the third-party source file the coefficients were read from, not a reference to a person, and the provenance is unverifiable without them. Kept, flagged for WP-10. No author surname appears in any shipped model name, message or payload.

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

WP-05 to WP-04, optional and not blocking: section 8 needs no melting temperature and nothing in the guide RNA package computes one. The one place the shared nearest-neighbor implementation would help is check 6, grna.self_complementarity, which currently reports a stem length against a documented Construct convention and says explicitly that it is not a free energy calculation. It is isolated in packages/validation/grna/selfcomp.py so a hairpin free energy can replace it after the merge.
WP-05 to WP-07: render off_target_space_statement verbatim wherever guides appear and in every export, and render UNKNOWN check rows visually distinct from PASS rows. Both are already in the payload, and GET /v1/grna/reference serves the Appendix C nuclease table, the thresholds, the cloning vectors, and every score's name, kind, citation, validity domain and allowed wording, which is what section 10.4 needs.
WP-05 to WP-06: the guide RNA design_model is packages.core.schemas.grna:GuideRNADesign, so a gold case input is {"request": {...}, "guide": {"spacer": ..., "pam": ..., "strand": 1}}. guide.spacer_start is optional and is resolved by locating the spacer, so a case can name a guide by sequence; supplying it forces a placement, which is how a deliberately mis-placed guide is expressed. The section 9.4 Cas12a 3' PAM offset case exists as a unit test in tests/grna/test_checks.py and can be lifted directly.

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

## The naming gate, stated precisely

The section 2.4 gate is a case-insensitive grep for the retired product name in
its spellings plus the retired lab acronym. Run literally over a full working
tree it returns matches that are NOT branding violations, because the lab
acronym is only three letters and case-insensitive matching finds them inside
unrelated words and inside legitimate scientific names. There are three distinct
classes, none of them authored by this build:

  1. Installed npm dependencies. Those three letters are a registered ISO 639-3
     language code, so they appear as a data key inside a language subtag
     registry package, and they also occur inside the camel case identifier of a
     global npm registry getter function. Both live under node_modules, which is
     gitignored and never committed.

  2. The Next.js build cache under apps/web/.next. The bundler writes the
     absolute build path into its source maps, and the scratchpad build
     directory on this machine is named after the retired product. The cache is
     gitignored and is regenerated by any build or dev server start. At the
     operator path the embedded path contains no retired token, so this class
     does not arise there at all.

  3. Real GenBank nomenclature in the retrieval corpus. Two ingested records are
     plasmids of Methanocaldococcus sp. 10A whose published names are a
     lowercase p followed by those same three letters and a number. That is
     ordinary plasmid naming, p for plasmid plus a depositor designation, and it
     is the real name in a public database record. Those names reach the
     generated corpus quality report. **They were deliberately left alone.**
     Editing a real accession's name to satisfy a grep would corrupt scientific
     data to improve a cosmetic metric, which is the wrong trade in a tool whose
     entire value proposition is that its output is traceable and real.

The meaningful counts, measured rather than asserted:

  Tracked files, case-insensitive, for the retired tokens            0 hits
  Tracked files, case-sensitive, for the actual brand strings        0 hits
  Files this build authored                                          0 hits
  Worktree excluding .git, node_modules and .next,
    case-sensitive, for the actual brand strings                     0 hits
  Worktree excluding .git, node_modules and .next,
    case-INSENSITIVE                                                 4 hits

Those last 4 are class 3 above: the two real Methanocaldococcus plasmid names,
each appearing twice across the generated corpus quality report in its JSON and
Markdown forms. Nothing else outside the gitignored build artifacts matches at
all, and nothing matches case-sensitively anywhere outside them.

Stated plainly, because the distinction is the whole point: a case-sensitive
search for the retired brand strings returns zero everywhere except inside
gitignored, regenerable build output whose file paths happen to contain the
scratchpad directory name. The case-insensitive residue is three letters
colliding with a language code, an npm identifier, and real plasmid nomenclature.

No committed source file, log line, user-facing string, API response, export or
commit message authored by this build contains a retired brand token.

One violation the grep could never have caught was found by WP-07 and fixed: the
web header rendered the retired product name as a text node followed by a
separate styled span holding the remaining two letters. No grep for the joined
string can see that, yet every user could read it. A follow-up scan over all
tracked source for the same split pattern, and for that two-letter token
standing alone adjacent to the product word, found no other instance.

## Open limitation for the operator: plasmid gold cases and the new runner

The plasmid capability's existing gold set, 36 known-good and 52 known-bad, runs
through its own pre-existing harness via `make validate-sample MODE=gold`, and
currently reports accuracy 1.0 with the phase 3 gate met. That path is green.

It does NOT run through WP-09's new multi-capability runner, so it is not yet
subject to the three assertions in specification 9.3: expected overall severity,
the NAMED check reporting the expected severity, and no unexpected FAIL. The
existing harness predates that requirement.

Two reasons it was left alone. Specification 12 scopes WP-06 to
`tests/gold/aav`, `tests/gold/assembly` and `tests/gold/grna` only, so plasmid
is out of that package's ownership. And `PLASMID_SPEC` in the capability
registry deliberately registers no validator, because the existing plasmid
engine predates the section 5.3 interface and would need an adapter.

Consequence to state honestly rather than paper over: the claim "all four
capabilities correctly reject every known-bad case via the expected check_id"
holds for the three new capabilities under the new runner, and holds for plasmid
only under the weaker assertion its own harness makes. Closing the gap needs a
validator adapter plus a conversion of 88 existing cases to the new case format.
That is real work and it is not started. Recorded for an operator decision
rather than attempted unilaterally late in the build.
WP-03 to WP-06: AAV gold cases go in tests/gold/aav/. The registry design_model is AAVValidationInput, which accepts either a full AAVDesign cassette (needed for the order, missing ITR, tandem ITR and CDS cases) or an AAVRequest (more readable for the packaging limit cases). Assert remediation with must_also_report: ["remediation"], not "remediation_suggestion"; the field is named remediation. Remediation is carried on aav.packaging_limit and aav.sc_capacity only.
WP-03 to WP-07: the AAV result panel needs the linear_map_json artifact (topology is always "linear", every element has start, end and fraction_of_cassette) and the length_budget artifact. Do not reuse the circular seqviz renderer, per sections 6.8 and 10.2. GET /v1/aav/parts populates the promoter and polyA selectors.
WP-03 to the owner of services/api/app.py: the AAV router is registered in the WP-03 region of services/api/routes/__init__.py but is still not served, because include_capability_routers(app) is not called from create_app. Same request WP-02 filed.
Q7 on-target model for gRNA: a faithful published model was achievable, so one shipped. Rule Set 1 (Nat Biotechnol 2014;32(12):1262-1267, doi:10.1038/nbt.3026, PMID 25184501), coefficients read from a reference implementation fetched during the build and verified byte identical, pinned by test against values computed with that implementation. Outside its stated validity domain the score is withheld and a clearly labeled heuristic ranks the guides. Off-target uses the MIT specificity score (Nat Biotechnol 2013;31(9):827-832, doi:10.1038/nbt.2647, PMID 23873081), weights read the same way, withheld for SaCas9 and Cas12a because it was derived from SpCas9 data.

## Orchestrator rulings on Wave 2 spec challenges

RULING 1, WP-05's tenth check `grna.off_target_hits`: ACCEPTED as 8.6-mandated,
  not invented. Section 6.4 says in terms "These are the checks. Do not add an
  invented one", and WP-03 was held to exactly fourteen. Section 8.5 carries no
  such sentence, and section 8.6 specifies FAIL, WARN and PASS conditions for
  off-target findings. `ValidationReport` is the only place a severity can live,
  so without this check a dangerous off-target could not move `overall`, which
  would defeat the purpose of 8.6. The check is documented as deriving from 8.6.

RULING 2, author surnames in citations: ACCEPTED. Section 3.3 constraint 6 and
  section 2.2 forbid personal names, but section 2.2 scopes that to "any personal
  name in code comments, docstrings, or AUTHORS-style files" in the context of
  stripping the previous branding, and Appendix E itself writes "Doench and
  colleagues", "Hsu and colleagues", "Engler and colleagues" and "Gibson and
  colleagues". The specification therefore uses author attribution for scientific
  citation as a matter of course. Appendix E also requires that a coefficient be
  read rather than recalled, and that claim is unauditable unless the code names
  the file and symbol the values were read from. So: scientific citations and
  third-party identifier names stay; no shipped model name, user-facing message
  or payload carries a surname, which WP-05 already ensured and tested.

INTEGRATION REPAIRS by the orchestrator, none of them capability logic:
  1. `pytest.ini` added with importlib import mode. The merge produced duplicate
     test module basenames (tests/aav and tests/assembly each had test_checks,
     test_constants and test_outputs), which broke collection. The alternative,
     adding __init__.py per test directory, would put tests/ on sys.path where
     tests/services/ shadows the real services namespace package.
  2. `tests/grna/test_validator_contract.py` region test rewritten. It asserted
     the WP-03 and WP-04 registry regions were EMPTY, true only while feat/grna
     was the sole capability in the tree. Now asserts the durable section 13.1
     invariant: each region holds its own capability and reaches into no other.
  3. `services/api/app.py` now calls `include_capability_routers(app)`. WP-02 and
     WP-03 both filed this as a cross-WP request and nobody owned it. Without it
     the capability routers were registered and never served. Verified
     behaviourally: /v1/aav/parts, /v1/assembly/checks and /v1/grna/reference all
     return 200.
  4. `.gitattributes` marks PROGRESS.md as union merge, per section 0.4.

In the files above, <retired-brand-token-pattern> stands for the literal alternation the
section 2.4 gate greps for: the retired product name in its four spellings,
plus the former lab name. It is written as a placeholder here so that this
documentation does not match the very gate it describes.
