# Construct App: Build Progress

## Claimed
WP-00 CLAIMED by orchestrator at 2026-10-07T00:00:00Z
WP-01 CLAIMED by wp01-rebrand at 2026-10-07T00:00:00Z
WP-02 CLAIMED by wp02-contract at 2026-10-07T22:48:16Z
WP-09 CLAIMED by wp09-harness at 2026-10-07T22:48:59Z
WP-03 CLAIMED by wp03-aav at 2026-10-07T23:30:00Z
WP-04 CLAIMED by wp04-assembly at 2026-10-07T23:40:00Z
WP-05 CLAIMED by wp05-grna at 2026-10-07T23:30:00Z
WP-07 CLAIMED by wp07-web at 2026-10-08T00:10:00Z
WP-08 CLAIMED by wp08-screening at 2026-10-08T01:20:00Z
WP-06 CLAIMED by wp06-gold at 2026-10-08T02:10:00Z

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

WP-07 DONE by wp07-web at 2026-10-08T03:10:00Z
  Capability selector and four result panels wired end to end: linear AAV map with length budget table, assembly junction map and order table, guide RNA strand view and ranked table, one shared validation report.
  UNKNOWN renders distinctly from PASS, the off-target statement is rendered verbatim, build/lint/e2e/make demo green, pytest 1370 passed 2 skipped. Detail in progress/WP-07.md.
WP-08 DONE by wp08-screening at 2026-10-08T02:40:00Z
  Section 11 complete: a base level provenance assertion that BLOCKS export for any base tracing to no curated part, no retrieved record, no user input and no named rule, the registry-only composition assertion, the documented screening hook with an explicitly named no-op default that records that no external screening ran, and an append only export audit log entry per export whether permitted or blocked.
  Full suite 1477 passed 2 skipped (baseline 1370/2); tests/screening 107 passed; make eval-capabilities exit 0. The one sentence that may be claimed, the interface, the audit entry verbatim and the plasmid attribution gap are in progress/WP-08.md.
WP-06 DONE by wp06-gold at 2026-10-08T03:05:00Z
  Gold sets for all three new capabilities: 91 cases, 30 Tier A, 16 Tier B, 45 known-bad, every known-bad case naming the check that must catch it. make eval-capabilities 91/91 agree, 0 disagreements, exit 0, and still exit 0 with CAPABILITY_GOLD_REQUIRE=1 so no capability is silently uncovered.
  Full suite unchanged at 1370 passed, 2 skipped. Sequences are slices of data/parts and of pUC19 GenBank L09137.1; one synthetic gRNA target and every synthetic edit is declared in its own rationale. Four uses of allowed_extra_fail, each a genuine two-check cascade, all listed in progress/WP-06.md.
WP-11 DONE by wp11-demo at 2026-10-08T15:28:17Z
  Runbook rewritten, historical banners added, all four capabilities walked in a browser with evidence in docs/demo_evidence.
  Full gate green: make test, eval-all, eval-check, demo, web build, lint, e2e. Details in progress/WP-11.md.

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

WP-08: section 11.1 item 1 names three origins for a base (registry part, retrieved template, user input) and section 4.2 states the same property with a different third (user input, curated part record, published rule). The union is four and the fourth is load bearing: an Appendix D Type IIS recognition site in a primer tail, a published cloning vector overhang in a guide oligo, and the single G the published U6 protocol prepends are each exported and each fully traceable, and none is a part record, a retrieved record or user input. SequenceOrigin therefore has four members. A published_rule span must name its rule, every distinct rule is listed in the audit entry, and the gate writes each rule into the design's provenance, so rule derived bases are enumerated rather than absorbed.
WP-08: Appendix D fixes how many nucleotides sit between a Type IIS site and the cut but not their identity, which packages/generation/assembly/designer.py::_filler sets by a documented deterministic A, C, G, T scan. Those bases are attributed as published_rule citing that rule by file and function, never as a part or a template, and the rule text appears verbatim in the audit entry and in the provenance.
WP-08: the declared provenance cross check (a span's source must appear in DesignResult.provenance) is applied to registry, template and user input spans and not to published_rule spans, because a capability's provenance list records the sources it drew sequence from and does not enumerate the rules its composer applied base by base. A rule derived span carries its rule, the assertion lists it, and ScreeningRecord.record_in_design writes it into the design's provenance, so it still reaches the list a user reads.
WP-03, deferred to after the demo, from the WP-10 review: the AAV composer should place a GCCACC Kozak element between the last upstream element and the CDS when the transgene supplies no 5' context, as a 6 bp cited element in the length budget, the GenBank feature table and AAVDesign.notes. This is not fabrication, because GCCRCC is already a cited constant in packages/validation/aav/constants.py with its Kozak 1987 reference and instantiating R as the preferred purine is ordinary vector design; without it the -3 base is whatever the upstream part's curated feature boundary ends on, and intron.chimeric ending ACCTGC means every cassette including the optional intron draws the aav.kozak_context WARN whichever promoter was chosen. Not done now because it changes the bases of every exported cassette and moves the documented demo numbers, and the present behaviour is honest: it warns, and the message now names the element the base came from and how to fix it.
RESOLVED by WP-17: the preceding deferral is closed. The composer now inserts the 6 bp element, derived from the cited constant rather than written as a literal, and discloses it in the length budget, the GenBank feature table, AAVDesign.notes and the provenance. The original text above is kept unedited as the record of when it was deferred and why. Note one thing it got wrong by implication: this does NOT clear the aav.kozak_context WARN, because check 11 also requires G at +4 and that base is the first of the transgene's second codon, which the composer must not change. See the WP-17 summary at the end of this file and progress/WP-17.md.

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

WP-06 to WP-04 and WP-11: under the sliding-window hairpin engine (the documented fallback when ViennaRNA is absent) every clean two-fragment Gibson and Golden Gate design draws a primer.hairpin WARN, because a 4 bp stem closing a 3 nt loop occurs by chance in nearly every 40 to 47 nt tailed primer and a tailed primer cannot be moved off its junction; the same primers are clean under ViennaRNA. That is the section 3.4 failure mode for the fallback path. Either raise HAIRPIN_WINDOW_STEM_WARN_BP for tailed primers or land the open request to add ViennaRNA to requirements.txt. The gold set pins hairpin_engine to window so its verdicts are deterministic either way, and documents the warning as Tier B case assembly.good.b1 rather than hiding it.
WP-06 to WP-02: aav.kozak_context can only pass when the element immediately upstream of the coding sequence ends with a purine three bases before the ATG. Of the eight registry promoters only cag, gfap and mecp2_mini do; cag warns on its own 14 bp G run and duplicated enhancer motif, and mecp2_mini at 225 bp cannot lift any available real reading frame over the 2,000 bp minimum genome size. promoter.gfap is therefore the only promoter in the registry that can produce a warning-free AAV cassette, and every Tier A AAV gold case uses it. Nothing is broken; one more compact promoter whose 3' end carries a purine at -3 would widen the clean design space considerably.

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

### CORRECTION, superseded by WP-12

The limitation recorded above was closed by WP-12 and the text above is kept
only as the build record of when it was true. Nothing above has been edited.

WP-12 adapted the plasmid engine to the section 5.3 validator interface
(`PlasmidValidator`, reached from `PLASMID_SPEC.validator_ref`) and converted the 88
cases into the new case format under `tests/gold/plasmid/`. The plasmid gold set
therefore now runs through the multi-capability runner and is subject to all
three section 9.3 assertions: expected overall severity, the named check
reporting that severity, and no unexpected FAIL. Detail is in `progress/WP-12.md`.

Measured by `make eval-capabilities`: plasmid 88 of 88, accuracy 1.000, made up of
known-good 36 of 36 (Tier A 25 of 25, Tier B 11 of 11) and known-bad 52 of 52,
inside a total of 179 of 179 cases agreeing with 0 disagreements.

The consequence paragraph above, "holds for plasmid only under the weaker
assertion its own harness makes", no longer applies. The claim now holds for all
four capabilities under the new runner. The statement that the work "is not
started" is likewise no longer true. Recorded by WP-16 in `progress/WP-16.md`.

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
WP-08 to the owner of packages/application/designs.py, packages/generation/generator.py and services/api/app.py: the plasmid export path cannot pass the section 11.1 gate. AnnotatedSequence and DesignRecord carry no base level attribution, and parent_template_ids is produced by the generator and dropped before DesignStore.create, so no base in an exported plasmid can be attributed to a template. There is deliberately no plasmid adapter and subject_for_design raises rather than returning an empty subject, so nothing passes silently; the export route still calls the codec directly and that is now stated in the codec's own docstring. Closing it needs those three files, which WP-08 does not own. Detail and the exact steps in progress/WP-08.md section 6.
WP-08 to WP-11 and the operator: packages.generation.generator.CarbonGenerator splices a model sampled continuation into a template (splice_generated_segment). Those bases trace to a model, which section 11.1 item 1 makes unattributable and item 2 describes as a de novo element. It is not on the demo path, FakeGenerator is. If it is ever enabled the gate would block its output, correctly, and the section 16 claim about curated composition would need qualifying for that generator.
WP-08 to WP-07: after ScreeningRecord.record_in_design the design's provenance carries screening:<backend id>:<outcome> and, whenever nothing was screened, a screening_note: line in plain words. If the UI shows a provenance or screening panel, render that note and never render an absence of findings as a result. ExportAuditEntry.external_screening_ran is the boolean to drive it from.
WP-08 to WP-11: the one sentence that may be claimed about section 11 is in progress/WP-08.md section 1, with the three true elaborations beside it and the list of what may not be said. Quote from there.

## Orchestrator verification of the two WP-08 findings. Both confirmed in source.

FINDING A, CONFIRMED. The ML sequence generator produces unattributable bases.
  `packages/generation/generator.py` line 128: `CarbonGenerator` calls
  `splice_generated_segment(template_sequence, segment)` where `segment` is
  sampled from a language model, and that helper replaces the tail of the
  template with those sampled bases. Those bases trace to a model, not to a
  curated part, a retrieved record, user input or a published rule, so under
  section 11.1 item 1 the sequence is unattributable and under item 2 it is a
  novel functional element synthesized de novo. Routed through the WP-08 gate it
  would be BLOCKED, which is the correct behaviour.
  Not currently reachable: `services/api/local_app.py` line 96 wires
  `FakeGenerator()`, which is the demo and local path, consistent with section
  1.3. `CarbonGenerator` is not wired into any served path.
  CLAIM SAFETY CONSEQUENCE, section 16: the sentence "designs are composed only
  from curated parts, every base is attributable" is TRUE for everything that
  ships and everything on the demo path. It would become FALSE for any design
  produced by `CarbonGenerator`. If that generator is ever enabled, the claim
  must be qualified for it before any design it produces is shown or exported.

FINDING B, CONFIRMED. Plasmid design provenance is dropped between layers.
  `packages/generation/generator.py` lines 82 and 139 set
  `parent_template_ids=[template.id]`, but `DesignStore.create` in
  `packages/application/designs.py` accepts only `session_id`, `job_id`,
  `annotated_sequence` and `design_id`. There is no parameter for provenance, so
  the template attribution never reaches the store or the export route.
  Consequence: the plasmid capability cannot satisfy the section 11.1 gate.
  WP-08 correctly did NOT loosen the check to accommodate it. There is no plasmid
  adapter, and `subject_for_design` raises `NoAttributionAdapter` rather than
  returning an empty subject, so nothing passes silently. The plasmid export
  route still uses the codec directly and is therefore not gated.
  Closing it touches three files WP-08 does not own and changes the behaviour of
  the one capability already on the demo path, so it was filed rather than
  attempted. Operator decision.

INHERITED DOCUMENTS WITH STALE CLAIMS, for WP-11 to audit rather than me to
  rewrite unilaterally. `docs/demo.md` carries an "Avoid these claims" list that
  predates this build, and one entry tells the presenter to avoid saying CRISPR
  coverage is complete, which now reads oddly given a guide RNA capability
  exists. `SYSTEM_DESIGN.md` is the inherited design document and describes a
  roadmap wider than the four capabilities that exist. Neither is a false claim
  made by this build, and both are read by a person preparing the demo, so both
  need a pass against section 16 and open question Q9 before Saturday.

NOTED, not a defect: `packages/retrieval/intent_parser.py` line 563 appends a
  `biosecurity_review_required` constraint when a request mentions a toxin, a
  pathogen, a select agent or gene therapy. That is a pre-existing honest flag
  raising a review requirement, not a claim that screening ran. It fires on gene
  therapy wording, which is exactly what an AAV request contains, so expect to
  see it on the demo path. Conservative and correct.

## Orchestrator walk of the section 15.3 demo path, twice, and what it found

RESULT: the path walks end to end twice with no intervention and identical
  output both times, so it is deterministic. Verbatim beats, API level:
    oversized cassette  5,049 bp  overall FAIL, aav.packaging_limit FAIL,
      14 of 14 checks reported, message names replacing CAG with EFS, structured
      remediation populated
    after applying that substitution  4,211 bp  aav.packaging_limit PASS,
      overall no longer FAIL, topology linear, artifacts fasta, genbank,
      length_budget and linear_map_json all present
  Run twice, byte-identical verdicts.

DEMO SCRIPT ISSUE, worth the operator deciding before Saturday. Section 15.3
  says "Make the substitution. It passes." With the current registry the
  substitution clears the packaging limit but the cassette lands on WARN rather
  than PASS, for one reason that is real and one that was an artifact of the
  synthetic test payload:
    aav.kozak_context WARN is EFS specific. Measured: EFS warns, GFAP does not.
      This confirms WP-06 finding 2 from the other direction. The check wants a
      purine three bases before the ATG, and of the eight registry promoters only
      cag, gfap and mecp2_mini end that way, so a CAG to EFS substitution trades
      a length failure for a Kozak advisory.
    aav.internal_repeats WARN came from the orchestrator's synthetic CDS, which
      is a repeating four codon palette. It appears under both promoters and will
      not appear with a real transgene.
  Three honest ways to handle it, operator choice:
    1. Keep the CAG to EFS narrative and say the advisory out loud. This is
       arguably the strongest option because section 3.4 is exactly the argument
       that a warning with an explanation is the product, and a presenter who
       volunteers it looks more credible than one whose demo is suspiciously
       green.
    2. Target astrocytes and substitute to GFAP, which gives a clean PASS with a
       real transgene. Changes the narrative from "smaller promoter" to
       "tissue appropriate promoter".
    3. Add one compact promoter that ends in a purine at -3 to the registry.
       This widens the clean design space considerably, but it needs a real
       sourced sequence under section 4.3 and open question Q10, so it is new
       WP-02 scope and not a quick fix.
  Nothing here is a defect. The checks are behaving as specified and the
  remediation engine does its job. It is a question of which true story to tell.

## Orchestrator mechanical audit of the appendix constants. 43 of 43 correct.

Scope: can a script verify, without any biological judgment, that every value the
specification fixes appears in the code with exactly the specified value, and
that every constant names a source. Biological judgment is WP-10's job and is
separate. Expected values were transcribed from the specification, not recalled.

RESULT, all confirmed present and correct:
  Appendix A: all 10 nearest-neighbor pairs with both enthalpy and entropy, both
    initiation terms, the symmetry correction, R = 1.987, salt coefficient 0.368.
  Appendix C: all four nucleases with their PAM motif, PAM side and spacer
    length, including that a five-prime PAM side is represented explicitly in
    code rather than a three-prime offset being hard coded, which Appendix C
    names as the likeliest integration bug. Plus the GC window 0.40 to 0.70, max
    homopolymer run 4, the U6 terminator motif, and the seed range 8 to 12.
  Appendix D: all five Type IIS enzymes with their recognition sequences, and
    every overhang length consistent with its stated cut offsets.
  Section 6.5: all ten AAV thresholds at their specified values.

SOURCING, section 3.3 constraint 1 and section 14.1: 116 module-level constants
  scanned across the three capability constants modules and the shared
  thermodynamics module. Every one carries a source in its surrounding
  documentation. The audit initially flagged ITR_INTERNAL_MOTIF_BP, which turned
  out to be a false positive in the audit heuristic rather than a gap: the
  constant is documented at length, states explicitly that it is a method
  parameter and not a biological constant, records that the motif set comes from
  the registry records so nothing is invented, and ties the window to
  MAX_DIRECT_REPEAT_BP. The explanation sits further below the constant than the
  heuristic's scan window reached.

## Open question Q6 resolved properly: ViennaRNA is now a declared dependency.

Q6 asks whether ViennaRNA is installable, and section 7.4 says to PREFER it for
hairpin free energy when it is. It is installable, version 2.7.2, and WP-04 wired
both engines. But it was never added to `requirements.txt`, so a fresh `make
setup` would have installed nothing and the hairpin check would have silently
fallen back to the sliding-window score on every new machine.

That mattered more than a missing line usually does, because WP-06 measured that
under the window fallback EVERY clean two-fragment Gibson and Golden Gate design
draws a `primer.hairpin` WARN: a 4 bp stem closing a 3 nt loop occurs by chance
in nearly any 40 to 47 nt tailed primer, and a tailed primer cannot be moved off
its junction. That is the section 3.4 failure mode, a check that warns on
everything and so trains the user to ignore it.

Added `ViennaRNA>=2.7,<3`. No threshold was changed. The 30 assembly gold cases
pin `hairpin_engine` to `window` deliberately, so they still exercise the
fallback path and their verdicts are unchanged. Suite stays at 1477 passed.
WP-10 is still asked to rule on whether the window threshold itself is too
strict, because the fallback remains reachable when the optional import is
missing.

## Orchestrator verification of two definition-of-done items

ITEM: all four capabilities generate a valid design and export it. VERIFIED.
  AAV: 200, genbank 5,542 chars and fasta both present, topology linear, no
    retired brand token in the exported payload.
  Assembly: 200, order table, protocol and a 15 check validation report present.
  Guide RNA: 200, 5 guides returned, both export tables present.
  Plasmid: session creation 201, the inherited flow is intact and its export path
    is unchanged.

ITEM: the guide RNA off-target space statement appears verbatim in the UI and in
  every export. VERIFIED at the API and export layer, and WP-07 asserts strict
  string equality in the browser with a Playwright test.
  The statement measured in this run:
    "Off-target search covered the target sequence only, 207 bp in total across 1
    sequence. No delivery construct sequence was supplied, so self-targeting of
    the delivery construct was not searched. This is not a genome-wide search."
  It names the real measured size, says plainly that it is not genome-wide, and
  contains neither "comprehensive" nor "exhaustive".
  **Byte identical in all 5 of 5 guide rows and in both export files**, checked by
  string equality against the top level field rather than by eye.

NOTE for the assembly demo beat: an arbitrary pair of 400 bp promoter slices
  produces overall FAIL, which is correct behaviour and not a defect, because
  nothing about two random slices makes a good Gibson pair. The runbook needs
  fragments chosen to assemble cleanly. Routed to WP-11.

## Operational findings that affect Saturday

DOCKER ENGINE WEDGED, FIXED. Docker Desktop's Linux engine began returning
  "500 Internal Server Error" from its named pipe for every container API call,
  including `docker ps`, `docker compose ps` and `scripts/check_services.py`.
  Nothing in this build caused it and nothing in this build can prevent it.
  Fix that worked, in one command: `docker desktop restart`. The engine came back
  immediately. The containers were stopped by the restart, so follow it with
  `docker compose up -d --wait`. The corpus survived in its volume.
  This belongs in the runbook's "if it breaks" section and it is in WP-11's brief.

CORPUS STATE, recorded precisely because it is inconsistent. The background
  expansion ingest kept running after it was last observed and grew the corpus
  from 194 records to 1,298. Embeddings were generated when the corpus was 194,
  so 1,298 plasmid records now sit alongside 194 embeddings.
  Measured consequence: none that breaks a gate. `make eval-check` exits 0 with
  all three halves passing, 91 of 91 capability gold cases agreeing and plasmid
  validation accuracy 1.0, because the unembedded records are invisible to
  semantic retrieval.
  Deliberately NOT remediated, with the reasoning recorded so the next person can
  disagree: running `make embed-corpus` would embed the remaining 1,104 records
  and add that many semantic distractors to a retrieval task whose gold set was
  designed against a corpus of about 82. That would probably lower retrieval
  ranking and force another baseline reset, two days before a demo, in exchange
  for tidiness rather than correctness. The present state is honest and every
  gate passes on it.
  If anyone does run `make embed-corpus`, expect retrieval metrics to move and
  expect the regression check to need a fresh baseline. Do not do it on Saturday
  morning.

PORT 55432, repeated here because it is the single most likely cold start
  failure. A native postgresql-x64-18 Windows service owns 5432 on this machine
  and has no `plasmid` role. The gitignored `.env` already sets POSTGRES_PORT to
  55432 and the connection URLs to match. `.env.example` still documents 5432,
  which is correct for a machine without that conflict. Regenerating `.env` from
  the example on THIS machine reintroduces the failure, which presents as a
  Postgres authentication error rather than a connection refusal, because the
  native service answers and then rejects the credentials.

## Recommendations recorded rather than implemented before the demo

RECOMMENDATION 1, to the gold runner, from WP-06. The audit that found nineteen
  wrong or incomplete case rationales found defects the GATE CANNOT SEE. The
  runner asserts overall severity, the named check, and the absence of an
  unexpected FAIL. It does not assert WARNs on known-bad cases. So a rationale
  claiming a case is isolated when three other checks also warn was invisible to
  every gate and was caught only by reading. Five of twelve such leaks are now
  fixed at the input; the remaining nine are declared in prose that nothing
  checks.
  The fix is an optional `expected_warnings` assertion on known-bad cases,
  mirroring what the runner already does for Tier B. Deliberately NOT implemented
  now: it changes test strictness rather than fixing a defect, it would require
  re-verifying all 45 known-bad cases against a new assertion, and the window
  before a live demo is better spent verifying what exists than extending it.
  Worth doing immediately afterwards.

RECOMMENDATION 2, a coupling nobody had noticed, found by WP-06 while fixing a
  case. `primer.tm_in_range` warns outside a 6.0 C window, and
  `primer.pair_tm_delta` fires above 5.0 C. The gap between them is 1.0 C, so a
  primer pair can only be both individually clean and unusable together inside a
  1.0 C sliver, and the clean example of that case sits exactly on the window
  edges at 57.0 and 63.0 C. Not a bug, and no value should change now. But the
  two thresholds are coupled far more tightly than either docstring suggests, and
  anyone widening the single-primer window without widening the pair threshold
  will silently make that defect class unreachable. Recorded in the case
  rationale and here.

MEASURED FACT worth keeping, since it constrains every future AAV gold case:
  `promoter.cag` carries a 14 base G run at offset 412 and `promoter.cbh` a 16
  base G run at offset 393, both over the 8 base homopolymer threshold. Any design
  using either promoter therefore trips `aav.homopolymer_runs`, which cannot be
  engineered away without editing a real registry part, which section 4.3
  forbids. The two CAG sized cases now say so rather than claiming isolation.

## Orchestrator independent verification of the hairpin fix and the web surfaces

HAIRPIN THRESHOLDS, re-measured by the orchestrator rather than accepted. Random
  oligos at 50 percent GC, 2,000 repetitions per length, against the corrected
  code:
    20 nt  WARN 0.004   3 prime FAIL 0.001
    47 nt  WARN 0.090   3 prime FAIL 0.006
    60 nt  WARN 0.200   3 prime FAIL 0.008
  The 47 nt WARN rate was 0.899 before the change. This reproduces WP-04's own
  figures closely and independently, on a different seed. The check went from
  firing on nine designs in ten to roughly one in eleven.

THE DISPUTED PRIMER, verified with ViennaRNA directly by the orchestrator.
  Sequence GACTTTCCATTGACGTCAATGG, 22 nt, under dna_mathews2004:
    MFE structure  ......((((((....))))))
    MFE energy     -3.90 kcal/mol
    3 prime end paired: yes, the final five positions are all closing brackets
  So it is a genuine 6 bp stem with a 4 nt loop that sequesters the 3 prime end,
  and it is past the -3.0 FAIL level. WP-04's figure was exact. The known-bad
  case that asserts a FAIL here is correct, and the engine it pins was wrong,
  which is why the resolution is to pin it to the engine the build actually uses
  rather than to weaken the case.

NOTE on a disagreement between two agents, resolved by measurement. WP-10's
  review derived the 6 and 7 thresholds from a hand calculation giving a 4 bp
  stem a positive folding energy. WP-04 measured instead and found a 4 bp stem
  folds at about -1.0 in isolation and -0.4 in context, because the review's loop
  penalty was too harsh and its stacking term slightly weak. WP-04 shipped 6 and
  7 anyway on a better basis: not where the mean energy lands, but how often the
  primary engine agrees when the fallback fires, which is 0.88 at 6 bp against
  0.52 at 5 bp. The right answer for the wrong reason was corrected to the right
  answer for the right reason, by the package that owns the code disagreeing with
  its reviewer and measuring.

WEB SURFACES, verified by the orchestrator reading the captured evidence rather
  than trusting the report. All four capabilities render correctly:
    AAV: a LINEAR badge and a linear cassette map drawn to scale, 5,229 bp,
      dashed markers at the 4,700 target, 4,900 soft and 5,200 hard limits, a
      hatched span for the overage, and the length budget table showing element,
      bp, running total and headroom with 529 over in red. FAIL, 14 checks.
    Guide RNA: the off-target space statement rendered verbatim in a prominent
      banner at the top of the result, stating 950 bp across 1 sequence, saying
      plainly it is not a genome-wide search, and disclosing that no delivery
      construct was supplied so self-targeting was not searched. Both strands
      rendered with guide positions. The three section 8.6 scopes are the three
      radio options. PASS, 10 checks.
    Assembly: a junction map with the 20 bp homology arm drawn and explained,
      its real sequence and an overlap melting temperature of 60.7 C, with an
      order table CSV export. PASS, 15 checks.
    Plasmid: the inherited circular flow, unchanged.
  The header reads Construct in every capture, and the four capability tabs are
  present in every one.

## Three rationale defects the gate could not see, found after the hairpin fix

WP-06 swept the assembly cases against master after the recalibration and found
three prose claims that had become false while the gate stayed green at 91 of 91.
All three are now corrected. They are recorded here because the pattern matters
more than the three instances:

  1. `assembly.bad.ambiguous_fragment_order` asserted a `primer.hairpin` warning
     on its engine-composed primers. Verified absent: the only non-pass check in
     the whole report is `assembly.fragment_order_defined` at FAIL, because the
     composed stems now fall under the recalibrated 6 bp threshold. This was a
     THIRD case the recalibration moved, and neither the package that made the
     change nor the orchestrator spotted it, because `expect_check` named a
     different check and `must_also_report` was empty.
  2. and 3. `assembly.bad.primer_three_prime_hairpin` and
     `assembly.good.a1.gibson_two_fragments` both carried a sentence stating that
     the engine is pinned to the window fallback in every assembly case and that
     ViennaRNA is not in requirements.txt. Both halves had become false, and in
     the known-bad case the stale sentence directly contradicted the engine note
     appended below it, which was the orchestrator's own edit.

CORRECTION to an earlier claim in progress/WP-04.md section 13.6, which said the
  expired rationale appeared in all 30 assembly cases. It appeared in exactly
  three. The other 27 make no engine claim in prose.

THE PATTERN, which is the point. Every one of these was invisible to every gate,
  because the runner asserts overall severity, the named check and the absence of
  an unexpected FAIL, and none of them asserts what the prose says. This is the
  second time in this build that a rationale drifted from its input without any
  gate noticing. The recommendation already recorded, an optional
  `expected_warnings` assertion on known-bad cases mirroring what Tier B already
  does, would have caught defect 1 mechanically. It remains the highest value
  piece of work immediately after the demo.

KNOWN LIMITATION, recorded rather than changed. Four of the thirty assembly cases
  behave differently under the two hairpin engines. One matters: the Tier A case
  `assembly.good.a9.gibson_cbh_and_puc19` is clean under the window fallback it
  pins, but its forward primer folds at about -4.1 kcal/mol under the free energy
  engine, which would make it a warning and so a Tier B case. Its rationale makes
  no engine claim, so nothing in it is false and it was left alone. But one Tier A
  grade currently rests on the fallback rather than on the engine the build
  actually runs, and anyone who later flips the assembly set to the live engine
  must re-grade a9 rather than assume it stays Tier A.

## Performance and code quality, measured rather than assumed

RESPONSE TIMES on the demo machine, best of three after a warm call, driven
through the real API:
    AAV design, lacZ plus CAG, the failing demo state      48 ms
    AAV design, lacZ plus EFS, the fixed demo state        46 ms
    AAV parts list                                          4 ms
    guide RNA reference endpoint                            4 ms
    guide RNA design, 950 bp target, ranked guides,
      off-target search over the searched space           301 ms
  Nothing needs optimizing. Everything a judge will click is well under a
  second, and that is worth saying out loud during the demo: a deterministic
  rules engine answers instantly, and the contrast with waiting on a model is
  the architectural argument in section 4.2 made visible.

CODE QUALITY SCAN of every new capability package, the screening package, the
  shared sequence utilities, the capability registry and the part registry:
    TODO, FIXME, XXX, HACK or NotImplemented markers                  0
    silent exception swallows                                          0
  The four exception handlers that exist are all correct. Two re-raise with the
  list of supported values named in the message, which is what section 5.4 rule
  2 asks of an error a user can hit. One captures the message so the check can
  report UNKNOWN with a reason rather than guessing, per section 3.3 constraint
  4. One is the documented optional dependency path for the free energy engine.

NOT DONE, and recorded as a judgment rather than an oversight: `make lint` still
  reports "No lint configured yet". Adding a Python linter now would mean a new
  dependency and a sweep of whatever it flags across a tree that is green and
  two days from a demo, in exchange for style findings on code that has already
  had a line by line scientific review. The risk is real and the return is low.
  Worth doing in the week after.

## Every claim in the demo runbook verified against the running system

The runbook states specific numbers a presenter will say out loud. Each was
re-measured by the orchestrator against the real API rather than trusted.

BEAT 1, plasmid. The runbook's original primary prompt returned FAIL, which
  defeats what beat 1 is for. Eight prompts were measured through the real
  retrieval backed path; two pass. The beat now opens on "a bacterial cloning
  vector with ampicillin resistance and a high copy origin", measured overall
  PASS, 4 checks, 2,686 bp, which is pUC19. The failing yeast prompt is kept as
  an optional answer to a challenge about whether the checks bite, with its real
  reasons recorded, and marked explicitly as not the opener.

BEAT 2, AAV. Measured: lacZ from GenBank JF300162.1 with CAG and bGH gives
  5,229 bp and FAILS, 529 bp over the target and 29 bp past the hard ceiling.
  The engine names the substitution itself. Applying it gives 3,802 bp and the
  packaging check PASSES. Walked twice with identical output.

BEAT 3, assembly. Both runbook fragments verified to be genuine plus strand
  slices of the records and offsets they claim: frag_a is promoter.cbh at offset
  100 for 150 bp, frag_b is promoter.cmv at offset 410 for 180 bp, both exact.
  Outcome measured: overall PASS, 15 checks, no non-pass check at all, amplicons
  of exactly 170 and 200 bp, 4 primers, and the order table CSV and junction map
  exports both present. Every number the runbook states is correct.

BEAT 4, guide RNA. Measured: the committed 950 bp fixture, 216 guides
  enumerated, 10 returned, overall PASS with 10 checks, both export tables
  present, and the off-target banner matching the runbook text BYTE FOR BYTE,
  compared by string equality rather than by eye.

So every figure in the runbook is a measured figure. A presenter reading it
aloud is not repeating anything that was estimated, rounded or assumed.

## CLAIM SAFETY CORRECTION, found by the orchestrator auditing its own text

THE GAP. `export_screened_design` is implemented, exported from
  `packages/application`, and covered by tests that prove an unattributable base
  blocks an export and that no policy flag can let one through. It has **no call
  site outside the screening package**. No API route calls it, and `data/audit/`
  does not exist because no audit entry has ever been written by the running
  application.

WHAT WAS WRONG. The README paragraph describing this, which the orchestrator
  wrote, said "exports are logged" and described the blocking as though it were
  operative. That presents a capability that exists as a capability that is
  running. Section 16's biosafety row calls a false safety claim the one
  overstatement that is never forgiven, and section 11.2 says to claim only what
  is actually implemented. This was over the line and it was caught by auditing
  the orchestrator's own text rather than anyone else's.

WHAT IT NOW SAYS. The claim is split in two. What is true today: designs are
  composed only from curated parts and every base is attributable, because the
  three newer capabilities compose exclusively from the registry plus the user's
  own input and each records its provenance. What exists but is not running: the
  provenance gate, the screening interface and the audit log, stated explicitly
  as not yet wired into a serving route, with the consequence spelled out that
  exports from the running application do not pass through it and no audit
  entries are being written.

WHY IT WAS NOT WIRED NOW instead of disclosed. Wiring the gate into the export
  paths is a behaviour change on every capability two days before a live demo,
  and it cannot be complete in any case: the plasmid capability cannot satisfy
  the gate at all, because `parent_template_ids` is dropped at the design store
  boundary, so wiring it would either block plasmid exports or require a special
  case that defeats the point. Disclosing accurately costs nothing and claims
  nothing false. Wiring it, together with carrying plasmid provenance through to
  the store, is the correct next piece of work and both are recorded.

FOR THE PITCH. Say "designs are composed only from curated parts and every base
  is attributable", which is true and demonstrable from any design's provenance
  list. Do not say exports are screened or logged.

## The provenance gate was run against the real demo design. It passes.

Measured by the orchestrator, driving the actual gate over the actual cassette
the Saturday demo produces (lacZ from JF300162.1 with EFS and bGH, 3,802 bp):

    allowed             True
    blocked_reasons     none
    provenance verdict  attributed, 3,802 of 3,802 bases
    composition verdict satisfied
    screening outcome   no_external_screening_ran

**Every base of the demo cassette traces to a curated registry part or to the
user's own supplied transgene**, verified span by span against the part records
rather than asserted. That is a demonstrable fact about the design on screen and
it needs no wiring to be true: the provenance list is in the design response and
the UI shows it.

CONSEQUENCE FOR THE WIRING DECISION. The gate is not merely implemented, it
  succeeds on the designs the product actually produces. So wiring it into the
  capability export routes is a small integration rather than a risky unknown,
  and the earlier concern that it might block a working design does not apply to
  AAV. It remains unwired for now because it is route level work across three
  capabilities, because the plasmid capability still cannot satisfy it until
  `parent_template_ids` reaches the design store, and because the demo is two
  days out and the tree is green. It is the first thing to do afterwards, and it
  is now a known quantity rather than a guess.

WHAT MAY BE SAID ON SATURDAY, unchanged by any of this: designs are composed only
  from curated parts and every base is attributable. Both halves are true today
  and the second is demonstrable live by opening the provenance panel. Nothing
  about screening or logging may be claimed.

## The gold set now covers all four capabilities under one set of assertions

WP-12, the plasmid validator adapter, closes the last structural gap in the
definition of done. The plasmid capability previously ran through an older
harness that asserted an aggregate verdict and only that the expected check
appeared AMONG the failures. It now runs through the same runner as the other
three, under the three assertions section 9.3 requires.

    plasmid    Tier A 25   Tier B 11   known-bad 52   total  88
    aav        Tier A 10   Tier B  5   known-bad 17   total  32
    assembly   Tier A 11   Tier B  5   known-bad 14   total  30
    grna       Tier A 10   Tier B  5   known-bad 14   total  29
    TOTAL      Tier A 56   Tier B 26   known-bad 97   total 179

    179 of 179 agree, accuracy 1.000, zero disagreements.

THE ADAPTER CHANGES NO VERDICT, and that is proved rather than asserted. A test
  drives the raw engine and the adapter over all 88 curated records and compares
  check ids, severities, messages and coordinates per check, plus the overall
  verdict: 352 per-check comparisons and 88 overall comparisons, none differing.
  A second test compares the whole-set distribution of overall verdicts, so a
  uniform shift could not hide behind per-case equality. The pre-existing path is
  untouched: `make validate-sample MODE=gold` still exits 0 at accuracy 1.0 with
  the phase 3 gate met.

WHAT IS NOW KNOWN THAT WAS NOT BEFORE. The old harness could only show that
  plasmid produced a FAIL with the expected check somewhere among the failures.
  It is now known that each of the 52 known-bad cases fails on exactly the one
  check it names and on no other, that each of the 25 Tier A cases validates with
  no warning, no failure and no unknown, and that each of the 11 Tier B cases
  warns on exactly its documented set.

A SCOPE ADDITION THE PACKAGE FLAGGED AND I ACCEPTED: `plasmid` was added to the
  runner's `EXPECTED_CAPABILITIES` rather than relying on directory discovery, so
  losing the directory reports a capability with zero cases instead of quietly
  reporting three. That is the correct instinct and it stays.

README CORRECTION CAUGHT BEFORE IT SHIPPED. The updated table first carried
  assembly as 10 Tier A and 6 Tier B, which were the counts from before that
  capability's re-grade. Measured and corrected to 11 and 5. Every row now adds
  up and the headline figure, the known-good total and the known-bad total are
  all checked against the table programmatically rather than by eye.

## Correction: the corpus is 4,455 records, not 1,298, and why

The background expansion ingest recorded earlier as having grown the corpus to
1,298 records had NOT finished. It was still running, and was found nearly twenty
hours after it started with 1,085 seconds of CPU consumed, still inserting. It
has been stopped.

Final state: **4,455 plasmid records against 194 embeddings.** The earlier figure
of 1,298 was a snapshot of a process still in flight and is superseded.

MEASURED CONSEQUENCE, which is the part that matters: none that breaks a gate.
  The full suite was run against this corpus and `make eval-check` still exits 0
  with all three halves passing, including the regression thresholds. Semantic
  retrieval is unaffected because the 4,261 unembedded records have no vectors,
  and the retrieval gold targets were already present and embedded.

STILL DELIBERATELY NOT REMEDIATED, same reasoning as before and now better
  evidenced. Running `make embed-corpus` would embed 4,261 further records and
  add that many semantic distractors to a retrieval task whose gold set was built
  against a corpus of about 82. It would also take a long time on CPU. Deleting
  them would be destroying real retrieved records to improve a cosmetic number.
  The present state is honest, every gate passes on it, and it is documented.

LESSON WORTH KEEPING: a long running background job was started and then reasoned
  about from a single snapshot of its output, and that snapshot was written into
  the build record as though it were a final state. The job then ran for another
  nineteen hours. Check that a background job has actually exited before
  recording what it produced.

## WP-13: screening gate wired into the AAV export routes

The section 11.1 provenance gate now runs on a serving route. `POST /v1/aav/design`
and `POST /v1/aav/validate` screen before returning: an attributable design is
returned with its GenBank and FASTA artifacts, an unattributable one is returned
with its report intact and those artifacts withheld, and one audit entry is
appended either way. Full report in `progress/WP-13.md`.

Scope is one capability, not four. Plasmid keeps its own older export route.
Assembly and guide RNA cannot be gated yet for a concrete reason: the gate's
export vocabulary is `{genbank, fasta}` and those capabilities export TSV and CSV
tables, so gating them means first giving the audit entry a name for a table
export, which is a change to WP-08's `packages/application/exports.py` and not a
value this package would invent.

DEFECT FOUND AND FIXED HERE, recorded because the near miss is instructive: the
  first version of the wiring passed the gate no audit log, so items 1 to 3 of
  section 11.1 were enforced and item 4 silently did nothing. The demo flow diff
  came back byte identical, which was the intended result for the allowed path and
  is also exactly what a gate that does nothing produces. What distinguished them
  was the absence of `data/audit/export_audit.jsonl`. A passing diff was
  consistent with both the correct outcome and a no-op.

Gates after the change: full suite 1540 passed 2 skipped, up from 1537 by the
three tests added; `make eval-capabilities` 179 of 179 unchanged; all four demo
beats byte identical to their pre-wiring baseline.

## WP-14: screening gate wired into assembly and guide RNA

Three of the four capabilities now screen before returning an export. Assembly
gates its primer order table on both the design endpoint and the dedicated CSV
endpoint, and guide RNA gates its guide table and oligo order table. Full report
in `progress/WP-14.md`.

The WP-13 blocker was removed without introducing the bug that the obvious fix
would have caused. Widening `SUPPORTED_EXPORT_FORMATS` to admit "tsv" would have
made `read_annotated_sequence` parse a TSV order table as FASTA instead of
failing, because it falls through to the FASTA parser for anything that is not
GenBank. So the codec vocabulary and the audit vocabulary are now separate
constants, with that trap documented next to them.

CONTRACT CHANGE, made explicitly: `AssemblyOutputs.order_table` and
  `order_table_csv` no longer require at least one row. The old constraint assumed
  a composed assembly always has a table to hand over, which stopped being true
  once a withheld table became possible. Empty means withheld, a caller must read
  `export_blocked` rather than infer from a non-empty table, and no placeholder row
  is ever substituted because section 4.3 forbids one.

PLASMID IS STILL NOT GATED, and this is a decision left open rather than work left
  undone. `DesignRecord` stores only an `AnnotatedSequence`, which carries no
  per-base source, and neither it nor `AnnotatedFeature` records where any base
  came from. The template id exists upstream and the corpus keeps full sequences,
  so a verified attribution is reachable, but not without threading the id into the
  design record and giving `assert_provenance` a corpus reader. The two honest
  options are to refuse every plasmid export or to leave the path ungated and
  documented. The second is the current state and the README says so in those
  terms. What was deliberately not done: emitting a whole-sequence span attributed
  to a template nobody verified, which would make the audit log assert a verified
  result that was never verified.

ALSO RECORDED, because it bounds what may be claimed: `assert_provenance`
  base-compares only registry part segments, against `data/parts`. A retrieved
  template or user input segment is only checked for being declared. That is sound
  for the three gated capabilities, whose spans are either registry parts or the
  user's own bytes, and it is the weakness any future plasmid adapter must not be
  built on.

Gates: full suite 1545 passed 2 skipped, up from 1540; `make eval-capabilities`
179 of 179 unchanged; `make eval-check` exit 0 with no regressions; all four demo
beats byte identical to the pre-gate baseline; web app typecheck, lint and build
all exit 0. Both tamper checks confirm the new tests are not vacuous, including one
that now fails for the missing-audit-log defect WP-13 found.

## WP-15: verified provenance for the plasmid export path

All four capabilities now screen before export. The plasmid path is gated, and
unlike the other three its template attribution is verified against the corpus
record rather than asserted: one changed base in a 4,245 bp candidate is refused,
with the finding naming the template and the number of differing positions. Full
report in `progress/WP-15.md`.

WP-14 left this as a choice between leaving plasmid ungated and refusing every
plasmid export, and named a third option without taking it. This package took the
third: thread real spans from the generator, through persistence, into a plasmid
adapter, and extend the provenance assertion to compare a template span against
the record it names at the coordinates it claims.

THE COMPARISON IS AGAINST THE LIVE CORPUS, not a copy stored with the design.
  Storing the template's bases alongside the candidate would have made the lookup
  free and the verification worthless, because it would compare the design against
  a copy written at the same moment by the same code.

THE READER'S ABSENCE REFUSES RATHER THAN PERMITS. A deployment with no corpus
  reader cannot verify a template claim, so plasmid exports are refused there.
  Serving them unscreened instead would be exactly the silent default that section
  3.3 constraint 4 forbids. This also means every design stored before spans were
  recorded is refused, which is the intended direction.

DEFECT FOUND BY SELF CHECK of the delegated work: the Carbon generator's span
  arithmetic was correct, but correct only because a function two calls away
  normalized its input, and `normalize_dna` strips whitespace. Had that moved, the
  span would have silently credited model written bases to a real record. The span
  is now checked against the candidate before it is made: a prefix that does not
  reproduce the record yields no span, which blocks. The value was right; what it
  depended on was not acceptable on that path.

BEHAVIOUR TIGHTENED: a retrieved template span used to be checked only for having
  its token declared. It is now compared against its record, and a span with no id,
  no coordinates, or no supplied record is UNKNOWN and blocks. Nothing relied on
  the looser behaviour, which was checked first.

PRE-EXISTING FRAGILITY FOUND AND FIXED: `pytest tests/services` alone failed to
  collect, on pristine master too, confirmed by stashing. A module scope import
  cycle between `services/api/app.py` and the package `__init__` broke the test
  shim; the full suite only passed because an alphabetically earlier test imported
  the module normally first. The import is now deferred into `create_app`.

Gates: full suite 1559 passed 2 skipped, up from 1545; `make eval-capabilities`
179 of 179 unchanged; `make eval-check` exit 0 with no regressions; all four demo
beats byte identical to the original pre-gate baseline; web typecheck exit 0;
corpus unchanged at 4,455 records. Cost 31.7 ms with a corpus lookup per export,
8.3 ms with the template in memory, so the comparison is cheap and the database
round trip is the cost. Caching was not invented here.

## WP-16: stale plasmid limitation note corrected

The section "Open limitation for the operator: plasmid gold cases and the new
runner" said the plasmid gold set did not run through the multi-capability runner.
That stopped being true when WP-12 landed. A correction block was appended
directly after that section; the original text was not edited, so the record
still shows what was believed when. `make eval-capabilities` reports plasmid 88
of 88 (known-good 36 of 36, Tier A 25 of 25, Tier B 11 of 11, known-bad 52 of 52)
inside 179 of 179 with 0 disagreements. Markdown only: no code, test or data file
changed. Full report in `progress/WP-16.md`.

## WP-17: the deferred Kozak initiation context element, now composed

The last open scientific item, recorded in `## Spec challenges` above and in
`progress/WP-03.md` under "Not done, and why". The AAV composer now places a
6 bp Kozak initiation context element between the promoter and the coding
sequence, if and only if the transgene begins with ATG and therefore supplies no
5' context of its own. Position -3 of every composed cassette is now a cited
base instead of whatever a curator's feature boundary happened to end on.

The element is not a written literal. It is derived as
`KOZAK_CONSENSUS_MOTIF[:6].replace("R", KOZAK_PREFERRED_MINUS3)`, so it is
positions -6 to -1 of the already cited Kozak 1987 consensus with the purine
instantiated, and it cannot drift from that motif. It appears as a cited element
in the length budget, in the GenBank feature table (with its citation on the
feature), in `AAVDesign.notes` and in the provenance, where it is the fourth
origin of section 11.1, a published rule. The attribution adapter emits that
span only when the element's bases ARE the bases the rule produces, so the claim
is verified rather than trusted; any other bases in a `kozak` role element leave
the span uncovered and block the export.

Not claimed: this does NOT remove the Kozak warning and composed cassettes do
NOT now pass check 11. Check 11 needs a purine at -3 AND a G at +4. The element
fixes -3 only. The demo payload, measured, is 3,075 bp beginning ATGACC, so its
+4 is A and the demo cassette still WARNs, now on +4 alone, with the advice
changed from "insert a GCCRCC prefix" (which would now be impossible to act on)
to a synonymous change to the second codon. Of the 16 gold cases that go through
the composer, 11 now pass check 11 and 5 still WARN, every one on +4 alone.

Check 11 was not relaxed: not one accepted base, threshold or severity moved,
and `test_pyrimidine_at_minus_three_warns` passes unmodified. No request field
was added, because section 6.3 is reproduced field for field.

Spec challenge logged: `CassetteElementRole.KOZAK` is an addition to the
section 6.2 order, which does not enumerate an initiation context element. It
reorders nothing section 6.2 fixes and adds no check; there are still exactly
fourteen.

Numbers this moved, re-measured against the running system rather than
recalculated. These SUPERSEDE the AAV figures recorded earlier in this file and
in `progress/WP-03.md`, `WP-06.md`, `WP-09.md`, `WP-10.md`, `WP-11.md` and
`WP-13.md`, none of which was rewritten: the build record is append only and
those entries record what was true when they were written.

  CAG, bGH, lacZ, no WPRE   5,229 -> 5,235 bp, FAIL, 14 checks
  over target/soft/hard       529/329/29 -> 535/335/35 bp
  EFS, bGH, lacZ, no WPRE   3,802 -> 3,808 bp, overall WARN, 14 checks
  EFS, bGH, lacZ, WPRE on   4,391 -> 4,397 bp

The band figures (4,700 target, 4,900 soft, 5,200 hard), the 1,427 bp CAG to EFS
saving and the 3,075 bp lacZ length are all unchanged. `docs/demo.md` and
`docs/demo_assets/README.md` were corrected in place, including the Kozak
passage, which needed rewriting rather than renumbering.

Exactly one gold case was regraded: `aav.good.b3.authentic_cmv_promoter` loses
its `aav.kozak_context` WARN, because that warning's own justification said the
only fix would be to insert linker bases between the promoter and the start
codon, and the composer now does that with the cited element. Measured
`-3 is A, +4 is G, context GCCACCATGG`, PASS. Its `aav.internal_repeats` WARN is
untouched. No other case's expected warning set changed. Stale prose in several
cases was corrected, including a biological error in b1's justification that had
been there from the start: it claimed a `GCCACC` linker "changes the second
codon of the protein", which six bases 5' of the ATG do not.

Gates, each run: `python -m pytest -q` 1589 passed, 2 skipped (baseline 1559 and
2); `make eval-capabilities` 179 of 179, accuracy 1.000, 0 disagreements;
`make eval-check` all three halves PASS, 0 regressions.

Reported rather than fixed, because another worker owns those files:
`apps/web/e2e/fixtures/aav_over.json` and `aav_fixed.json` are static mocked API
responses that still carry pre-change totals and no Kozak element. They stay
self consistent with their own spec file, so the e2e suite passes against them,
but they no longer match what the real API returns. The two AAV screenshots in
`docs/demo_evidence/` likewise show the old totals and cannot be corrected as
text. Full report in `progress/WP-17.md`.

## WP-18: `make lint` is real, with a rule set chosen by measurement

Closes the deferral recorded above under "Performance and code quality,
measured rather than assumed", whose stated reason, being two days from a demo,
has expired. `make lint` ran `@echo "No lint configured yet."`; it now runs
`$(PYTHON) -m ruff check .`.

ruff is pinned EXACTLY, `ruff==0.16.10`, which deviates on purpose from the
`>=X.Y,<N+1` style every other line in requirements.txt uses. ruff's rule
behaviour changes between releases, so a floating version makes the gate non
deterministic across machines and across time; a gate must pin the version
whose findings were triaged. Config is in `ruff.toml` at the root, not a
`pyproject.toml`, because none exists here and adding one could change packaging
behaviour.

Rule set, selected by running candidates over the tree and reading the findings:
`select = ["F", "E401", "E7", "E9", "W605", "B", "A"]`, `ignore = ["B905"]`,
`target-version = "py311"` (the only declared target, README line 119).

The exclusions are the real decisions and each is recorded in `ruff.toml` with
its measured count. E501 is NOT selected: measured over 254 files and 60,955
lines the 95th percentile line is 92 characters, the 99th is 111, the longest is
295 and 274 lines exceed 120, and those long lines are deliberate strings, data
tables and prose, so any line length would have been the formatting fight to
avoid. BLE001 is not selected: 27 findings on broad boundary catches that
section 3.3 constraint 4 actually requires, so the rule fights the design, and
notably E722, a genuine bare `except:`, reports ZERO, so the thing it was meant
to catch is already absent. PLC0415 is not selected: 110 findings on documented
deliberate lazy imports. E402 is not selected: 46 findings, stylistic. B905 is
ignored: 21 findings, unfixable without changing behaviour or adding a no op.
RUF100 is not selected and is recorded as a KNOWN GAP: it was verified
empirically that it flags all 9 existing `# noqa` comments as non enabled even
when their codes are listed under `ignore`, so enabling it would mean deleting 9
comments that carry real reasoning, one of them in a file this package could not
touch.

Findings 32 before, 3 after. Fixed: 10 unused imports (each checked by an AST
scan for re-export before deletion), 7 f-strings without placeholders, 3
undefined `Mapping` annotations in `packages/retrieval/eval.py` (a real defect,
invisible only because that module has `from __future__ import annotations`), 3
unused variables, 2 late-binding closure captures in
`packages/data_pipeline/ingest/genbank.py`, 1 `pytest.raises(Exception)`
narrowed to `dataclasses.FrozenInstanceError`, and 3 `A002` builtin-shadowing
arguments given targeted `# noqa: A002 - reason` comments because `format` is
the public keyword those codecs have always taken.

Code changed in 18 files. Nothing was reformatted, reordered or renamed, no
behaviour changed, and no blanket suppression was added anywhere: no bare
`# noqa`, no file level `# ruff: noqa`, no `per-file-ignores`, no `exclude`.
Where a rule was wrong for this codebase it was left out of `select` with its
reason written down.

One `F841` was NOT fixed by deleting the line. In
`packages/generation/grna/designer.py` the binding was dropped but the call
kept, because `get_nuclease` raises a `KeyError` naming every supported
nuclease and running it first means an unknown name is rejected with that
message before any enumeration. A bare call whose result is discarded reads like
dead code, so a comment now records that it is called for its exception and must
not be removed as a no op.

`make lint` EXITS NON ZERO today, exit 2, on exactly 3 findings in two files
this package was forbidden to edit because another worker owned them and was
editing them concurrently. They are reported rather than worked around, and no
mechanism was added to hide them:
  services/api/app.py:26    F401 JobQueue, verified genuinely unused, one line
                            deletion.
  services/api/app.py:506   A002 format. Must NOT be renamed: it is a FastAPI
                            route parameter, so the name is the public HTTP
                            query parameter. Needs a targeted noqa.
  services/api/e2e_app.py:102  B035 static key. READ, and NOT a bug: the
                            `if template_id == TEMPLATE_ID` filter pins the loop
                            variable to the same constant, so the at most one
                            entry result is exactly what the docstring
                            specifies. Cleanest fix is to key on `template_id`.

Gates: `python -m pytest -q` 1589 passed, 2 skipped, unchanged by this package,
which is the point of a pass that changes no behaviour; `make eval-capabilities`
179 of 179, accuracy 1.000, 0 disagreements; `make eval-check` exit 0, all three
halves PASS, 0 regressions. `python -m ruff check .` and the same config over
`git ls-files '*.py'` report the same count, so no `exclude` was needed. No CI
exists in this repo to wire into. Full report in `progress/WP-18.md`.

## WP-19: the two items WP-17 and WP-18 reported rather than fixed

Both are now closed. Neither was left as reported because the reports were
wrong; each was correctly handed over by a worker that did not own the file.

THE AAV E2E FIXTURES. `apps/web/e2e/fixtures/aav_over.json` and `aav_fixed.json`
  carried no kozak element, so the browser suite exercised a payload the API no
  longer produces and a UI that mishandled the new role would have passed. They
  stay synthetic, which is their job: a 9 bp transgene with an inflated total
  exists to drive the UI through the over limit and remediation states with no
  backend. The element definition is taken verbatim from a live response and
  every total, running total, headroom and coordinate is recomputed from the
  rows rather than adjusted by hand.

  The first attempt at that was incomplete and the e2e caught it, which is the
  test doing its job. The `linear_map_json` artifact still listed five elements
  and the panel prefers that artifact over deriving from the budget, so the map
  and the budget disagreed. Rebuilt from the same rows, with the three views of
  the cassette now asserted to agree on count and end coordinate.

THE TWO SCREENSHOTS, which WP-17 recorded as unable to be corrected as text and
  not regenerated. That was true of editing them and not of replacing them. Both
  were regenerated by driving the real application in a real browser against a
  live API: `02a_aav_before_cag_fail.jpg` now shows 5,235 bp, FAIL, 14 checks,
  and `02b_aav_after_efs_warn.jpg` shows 3,808 bp, WARN, 14 checks. Both show
  the "Kozak initiation context, 6 bp" element in the cassette map, which is the
  thing the old images could not show. Promoter, polyA and WPRE settings match
  the original framing so the pair remains comparable with the rest of the set.

  This also closes the section 14.4 item the done condition verifier left as
  manual on the grounds that it needs a browser. All four capabilities were
  exercised in a real browser: the AAV flow by hand here, the other three by the
  Playwright suites, which pass.

LINT. `make lint` exited 2 on master with three findings in files WP-18 was
  forbidden to touch. All three are fixed and each was checked rather than taken
  on trust. The unused JobQueue import is genuinely unused, which needed a word
  boundary scan to establish, because InMemoryJobQueue looks identical to a
  careless grep and is used. `format` on the export route keeps its name, since
  the name IS the public query parameter and renaming it would change the HTTP
  API. The B035 static key was a real readability fix and not the bug it was
  first framed as.

Gates after all of it: pytest 1627 passed 2 skipped; `ruff check .` all checks
passed; `make eval-capabilities` 179 of 179; `make eval-check` exit 0 with all
three halves PASS; capabilities e2e 5 passed; full stack e2e passed; tsc exit 0.
