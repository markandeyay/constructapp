# CONSTRUCT: Engine Capability System Design

> **Status:** SPEC. Immutable. Implement it, do not rewrite it.
> **Scope:** migrate the existing engine into the Construct App repository, rebrand
> it, and add three new generation capabilities to it.
> **Hard deadline:** a live demo on **Saturday, October 10, 2026**. This document
> was written on October 7. You have three working days.
> **Mutable build state** lives in `PROGRESS.md` and `progress/WP-XX.md`. See §0.

---

## REPOSITORIES

| Role | URL | Use |
|---|---|---|
| **Destination. All final code ends up here.** | https://github.com/markandeyay/constructapp.git | The Construct App. Every commit this project produces goes here. |
| **Source engine. Internal reference only.** | https://github.com/markandeyay/PlasmidAI | The working engine being migrated. Read it freely. Its name never appears in any output. See §2.3. |
| Marketing site, separate project | https://github.com/markandeyay/constructsite | Not touched by this document. Mentioned so you do not confuse the two. |

Local working directory on the operator's machine: `~/constructapp`
(Windows: `C:\Users\yalam\constructapp`).

---

## TABLE OF CONTENTS

0. [How agents use this document](#0-how-agents-use-this-document)
1. [What already exists](#1-what-already-exists)
2. [Phase 0: migration and rebrand](#2-phase-0-migration-and-rebrand)
3. [Goals, non-goals, hard constraints](#3-goals-non-goals-hard-constraints)
4. [Architecture: where a capability plugs in](#4-architecture-where-a-capability-plugs-in)
5. [The shared capability contract](#5-the-shared-capability-contract)
6. [Capability A: AAV vector designer](#6-capability-a-aav-vector-designer)
7. [Capability B: primer and assembly designer](#7-capability-b-primer-and-assembly-designer)
8. [Capability C: CRISPR guide RNA designer](#8-capability-c-crispr-guide-rna-designer)
9. [Gold sets and validation methodology](#9-gold-sets-and-validation-methodology)
10. [Web application surfaces](#10-web-application-surfaces)
11. [Biosafety and screening](#11-biosafety-and-screening)
12. [Work packages](#12-work-packages)
13. [File ownership and collision rules](#13-file-ownership-and-collision-rules)
14. [Testing and gates](#14-testing-and-gates)
15. [The Saturday demo path](#15-the-saturday-demo-path)
16. [Claim safety register](#16-claim-safety-register)
17. [Open questions](#17-open-questions)
18. [Appendix A: nearest-neighbor thermodynamic parameters](#appendix-a-nearest-neighbor-thermodynamic-parameters)
19. [Appendix B: AAV element length reference](#appendix-b-aav-element-length-reference)
20. [Appendix C: nuclease and PAM reference](#appendix-c-nuclease-and-pam-reference)
21. [Appendix D: Type IIS enzyme reference](#appendix-d-type-iis-enzyme-reference)
22. [Appendix E: literature the implementations derive from](#appendix-e-literature-the-implementations-derive-from)

---

## 0. HOW AGENTS USE THIS DOCUMENT

### 0.1 The two-file contract

| File | Mutability | Role |
|---|---|---|
| `CONSTRUCT_ENGINE_SYSTEM_DESIGN.md` (this file) | **Immutable** | The spec. |
| `PROGRESS.md` | **Mutable, append-only** | One line per state change. |
| `progress/WP-XX.md` | **Mutable, one writer** | Each agent's own detail file. |

An agent that believes the spec is wrong does not edit the spec. It appends a
line under `## Spec challenges` in `PROGRESS.md` and continues.

### 0.2 Agent startup ritual

Before writing any code:

1. Read this file end to end. The whole thing, not your section. The constraint
   numbers you need are in the appendices, and the reason you must not invent
   them is in §3.3.
2. Read `PROGRESS.md`.
3. Claim one work package by appending one line:
   `WP-XX CLAIMED by <agent-id> at <ISO timestamp>`.
4. Check §13 for the files your package owns. Touch nothing else.
5. Build. Run the §14 gates that apply.
6. Append `WP-XX DONE by <agent-id> at <ISO timestamp>` plus a two-line summary,
   and write your detail into `progress/WP-XX.md`.

### 0.3 The prime directive

> **Every number in this system must be traceable to a published source or to a
> configurable parameter with a documented default. Nothing is invented.**

This is a biology tool. A wrong melting temperature wastes a week of someone's
bench time. A wrong packaging limit produces a vector that does not package at
all. The appendices exist so that no agent ever has to guess, and §3.3 makes
guessing a build failure.

The second directive, equal in weight:

> **A capability is not done when it produces output. It is done when it
> produces output AND correctly rejects bad input.**

The engine's entire value proposition is catching mistakes. A generator with no
gold set of known-bad cases has not demonstrated anything.

### 0.4 PROGRESS.md seed

WP-00 creates this at repo root on its first commit:

```markdown
# Construct App: Build Progress

## Claimed
(none yet)

## Done
(none yet)

## Blocked
(none yet)

## Spec challenges
(none yet)

## Cross-WP requests
(none yet)
```

**Concurrency rule.** `PROGRESS.md` is the only multi-writer file. Append one
single line under the relevant heading, never rewrite an existing line, retry on
conflict. Detail goes in your own `progress/WP-XX.md`.

### 0.5 Model allocation

| Role | Model | Why |
|---|---|---|
| Orchestrator | Sonnet | Its job is mechanical: dispatch work packages in wave order, run the §14 gates, merge on pass, report on fail. **It never judges whether a biological constraint is correct.** Every gate it evaluates is a test exit code. |
| Capability subagents (WP-03, 04, 05) | Opus | These write the constraint logic and the scoring math. This is where correctness matters and where the reasoning is hardest. |
| Gold-set authoring (WP-06) | Opus | Designing known-bad cases that are bad for the *right reason* is subtle work. |
| Migration, rebrand, scaffolding (WP-00, 01, 02) | Sonnet | Mechanical. |
| Web surfaces (WP-07) | Sonnet | Follows existing component patterns. |
| Final scientific review (WP-10) | **Fable** | One pass over every constraint, every threshold, and every citation in the finished code, checking the implementation against the appendices and the literature. This is the single place in the pipeline where a biology-specialized model earns its slot: it is reviewing synthetic biology engineering constraints, not generating them. |

The orchestrator does not decide model assignment on the fly. It is fixed above.

---

## 1. WHAT ALREADY EXISTS

Read the source repository before you build. This section is a map, not a
substitute for reading it.

### 1.1 The pipeline, as built

A researcher describes a construct in natural language. The system:

1. Parses the request into structured intent.
2. Retrieves relevant records from an indexed corpus using hybrid semantic plus
   structured search. Embeddings are PubMedBERT, stored in Postgres with
   pgvector. Structured filters cover host, vector profile, selectable marker,
   source, and named lookup. The corpus draws on curated seed records and NCBI
   GenBank, with cached raw blobs so parser improvements can reprocess without
   refetching.
3. Proposes a candidate sequence **grounded in a retrieved template** rather
   than inventing an unconstrained backbone.
4. Runs the candidate through a **deterministic validation engine**: restriction
   site conflicts, repeat and synthesis instability patterns, codon usage
   scoring, regulatory element compatibility.
5. Returns an annotated circular construct with validation evidence, retrieval
   evidence, and exports to GenBank and FASTA.
6. Captures wet-lab outcomes as future training signal, with explicit consent
   and provenance.

### 1.2 Package layout

| Path | Contains |
|---|---|
| `packages/core/` | Shared schemas and contracts. **Every new capability adds its request and result schemas here.** |
| `packages/data_pipeline/` | Ingestion, parsing, annotation, reprocessing, corpus quality. |
| `packages/retrieval/` | Intent parsing, document composition, embeddings, vector storage, retrieval, recommendation, evaluation. |
| `packages/generation/` | Generator interfaces, local generator wiring, training data, registry, shadow and canary support, generation evaluation. **Each new capability adds a generator here.** |
| `packages/validation/` | Deterministic biological validation checks. **Each new capability adds a constraint module here.** |
| `packages/application/` | Application services, stores, jobs, export codecs. |
| `packages/feedback/` | Outcome to training signal derivation. |
| `services/api/` | FastAPI application and API surface. |
| `services/worker/` | Async job worker integration. |
| `apps/web/` | The Next.js design workspace and Playwright tests. |
| `tests/` | Backend test suite. |
| `docs/` | Demo and operational runbooks. |
| `research/findings/` | Design notes, audits, policy decisions. |

### 1.3 Current runtime state, and what it means for you

Read this carefully, because one item here changes how you build.

- The local app is functional end to end.
- Gemini 2.5 Flash handles intent parsing and grounded recommendation when
  `GOOGLE_API_KEY` is set.
- PubMedBERT handles semantic retrieval against the real corpus.
- **The sequence generator is a `FakeGenerator`.** It returns retrieved
  templates with optional marker swaps. Real fine-tuning is built but not run.
- The validation engine, the export codecs, and the seqviz map renderer are all
  real.
- The job queue in local mode is a synchronous `FakeJobQueue`. Celery plus a
  durable Postgres-backed queue is the production path and is not wired.
- Existing gold set: **36 known-good and 52 known-bad plasmid constructs, 100%
  combined accuracy** on that curated set.

**What this means.** The honest architecture of this system is
*retrieval plus deterministic validation*, not *generative model*. That is a
strength, not a weakness, and all three new capabilities follow the same shape:
compose a candidate from real parts and real templates, then validate it hard.
Do **not** introduce a new ML model for any capability in this build. Every
capability in §6, §7 and §8 is implementable as deterministic composition plus
deterministic checking plus published scoring functions. That is why they are
achievable in three days, and it is why their output is defensible.

### 1.4 Local development commands

```bash
cp .env.example .env          # then set GOOGLE_API_KEY
make setup
docker compose up -d          # Postgres + pgvector, Redis, MinIO
make test                     # backend suite + service checks
make serve-local              # API on 127.0.0.1:8000
make serve-web                # web on 127.0.0.1:3000
make demo                     # deterministic end-to-end verification
make eval-all && make eval-check
make validate-sample MODE=gold
```

API startup, if you need it directly:

```bash
python -m uvicorn --factory services.api.local_app:build_local_app --host 127.0.0.1 --port 8000
```

Requirements: Python 3.11+, Node 20.9+, Docker and Docker Compose, GNU Make.

---

## 2. PHASE 0: MIGRATION AND REBRAND

This is WP-00 and WP-01. **Nothing else starts until `make test` passes on the
migrated tree.** An agent that begins a capability before the migration is
verified is building on sand.

### 2.1 Seeding the destination repository

Preserve the commit history. It is a real record of sustained engineering and it
costs nothing to keep.

```bash
# from the parent of the target directory
git clone https://github.com/markandeyay/PlasmidAI.git constructapp-seed
cd constructapp-seed
git remote set-url origin https://github.com/markandeyay/constructapp.git
git remote add upstream https://github.com/markandeyay/PlasmidAI.git
git push -u origin master
```

The operator already has a local folder at `~/constructapp`. If it is empty,
seed into it directly. If it has content, reconcile rather than overwrite, and
ask before deleting anything.

`upstream` stays attached as a fallback for the duration of this build. Do not
remove it and do not modify the upstream repository.

### 2.2 Rebrand pass

The product is called **Construct**. Nothing else.

Replace across the entire working tree:

| Target | Replacement |
|---|---|
| `PlasmidAI`, `plasmidai`, `plasmid_ai`, `PLASMIDAI` | `Construct`, `construct`, `construct`, `CONSTRUCT` |
| `PMR Labs`, `PMR`, `pmr` | Remove entirely. No replacement. |
| Any personal name in code comments, docstrings, or `AUTHORS`-style files | Remove. |

Specific places that are easy to miss, and that WP-01 must check individually:

- `README.md` and every file under `docs/`
- `package.json` `name` field in `apps/web`
- Python package metadata, `pyproject.toml` or `setup.py` if present
- `docker-compose.yml`: service names, container names, volume names, the
  Postgres database name and user
- `alembic.ini` and any migration that hard-codes a schema or database name
- `.env.example`: environment variable prefixes
- `Makefile` target names and echo strings
- Every user-facing string in `apps/web`
- Page titles, favicons, and metadata in the web app
- Log messages and error strings that name the product
- Test fixture names and snapshot files

**Database rename is a migration hazard.** If you rename the Postgres database
or user, `docker compose down -v` first so the volume is recreated, and verify
`make test` after. If that proves fragile under time pressure, keep the
internal database name and rebrand only what is visible. Record the decision in
`progress/WP-01.md`.

### 2.3 The naming rule, stated precisely

You **may** read the source repository. §1 tells you to.

The name `PlasmidAI` must not appear in: the destination repository's working
tree, any committed file, any log output, any user-facing string, any API
response, any exported file's metadata, any commit message authored by this
build, or any artifact shown to a person.

It **may** appear in: the `upstream` git remote URL, and the pre-existing commit
history inherited from the clone. Those are mechanical and are not output.

`PMR Labs` must not appear anywhere at all, including the inherited history where
you can reach it without rewriting history. Do not rewrite history to chase it.

### 2.4 Verification gate for Phase 0

All of these must pass before WP-02 begins:

```bash
make test                     # green
make demo                     # green
docker compose up -d && make serve-local && make serve-web
# then: load localhost:3000, generate a plasmid, confirm the map renders
grep -ri "plasmidai\|plasmid_ai\|PMR" --exclude-dir=.git .    # zero hits
```

Append the result to `PROGRESS.md`. If `make test` does not pass, **stop and
report**. Do not proceed to capabilities with a broken base.

---

## 3. GOALS, NON-GOALS, HARD CONSTRAINTS

### 3.1 Goals

| # | Goal | Measured by |
|---|---|---|
| G1 | Three new capabilities produce real, orderable designs | Each generates a construct that passes its own validator and exports to GenBank |
| G2 | Each capability correctly **rejects** bad designs | Gold set per capability, known-good and known-bad, documented in §9 |
| G3 | The demo survives an expert question | Every threshold traceable to Appendix A through Appendix E |
| G4 | It looks like one product, not three bolt-ons | All four capabilities share the §5 contract and one UI pattern |
| G5 | Demoable from a laptop on Saturday | §15 |

### 3.2 Non-goals

- No new ML model, no fine-tuning run, no training. §1.3 explains why.
- No production deploy. §15 explains why not before Saturday.
- No Celery or durable queue work. The synchronous local path is fine.
- No authentication, billing, or multi-tenancy.
- No genome-wide off-target search. §8.6 scopes this honestly.
- No protein structure prediction, no affinity modeling, no folding prediction
  beyond the RNA secondary structure noted in §7.4.

### 3.3 Hard constraints

1. **Do not invent a biological constant.** Every length limit, temperature
   threshold, PAM sequence, enzyme recognition site, and scoring coefficient
   either appears in an appendix of this document or is a configurable parameter
   with its default and source recorded in code. An agent that writes a magic
   number with no source has failed its package.
2. **Every threshold is configurable.** Hard-coding the AAV packaging limit as
   `4700` inline is wrong. It belongs in a constants module with the citation in
   a docstring, because labs disagree about the practical ceiling and a judge may
   name a different number.
3. **Deterministic means deterministic.** Same input, same output, every time.
   No randomness in validation. No LLM call inside a validator. If a check needs
   a model, it is not a validator, it is a recommendation, and it goes in the
   generator with its uncertainty surfaced.
4. **Fail loudly on uncertainty.** A validator that cannot evaluate a check
   returns an explicit `UNKNOWN` with a reason. It never returns `PASS` by
   default. The existing engine already distinguishes design-construct failures
   from source-record uncertainty; follow that pattern.
5. **No em dashes in any string, comment, docstring, or document** this build
   produces. Use commas, colons, parentheses, or separate sentences.
6. **No personal names anywhere.** See §2.2 and §2.3.

### 3.4 The tiering principle, inherited

The existing gold set tiers known-good records:

- **Tier A, strict-clean:** validates with no warnings.
- **Tier B, accepted-with-caveats:** real constructs that validate with
  documented warnings, where the warning reflects intentional biological
  architecture that should be surfaced rather than treated as failure.

**Every new capability inherits this tiering.** It matters because real biology
is full of deliberate choices that look like errors to a naive checker. A dual
promoter cassette, an intentional repeat, a deliberately weak Kozak sequence:
these are warnings with explanations, not failures. A validator that flattens
everything to pass or fail is less useful than no validator, because it trains
the user to ignore it.

---

## 4. ARCHITECTURE: WHERE A CAPABILITY PLUGS IN

### 4.1 The five insertion points

Every capability touches exactly these five places. No capability invents a new
architectural layer.

```
packages/core/schemas/<capability>.py        # request + result schemas
packages/generation/<capability>/            # candidate composition
packages/validation/<capability>/            # deterministic checks
services/api/routes/<capability>.py          # endpoint
apps/web/src/<capability>/                   # UI surface
tests/<capability>/                          # unit + gold set
```

Plus one shared registry entry so the UI can enumerate capabilities, and one
gold-set directory.

### 4.2 Why composition rather than generation

All three new capabilities are **composition problems**, not sequence-generation
problems:

- An AAV vector is a known set of parts in a known order, assembled under a
  length budget. The parts come from a curated registry. Nothing is invented.
- A primer is a subsequence of a known template plus an optional tail. The
  design problem is choosing coordinates and checking thermodynamics. Nothing is
  invented.
- A guide RNA is a 20-mer window from a supplied target that sits next to a PAM.
  The design problem is enumeration and scoring. Nothing is invented.

This is the single most important architectural point in this document. It is
why three capabilities fit in three days, and it is why the output is
defensible: every base in the output traces to either the user's input, a
curated part record, or a published rule.

### 4.3 The part registry

Capability A needs a registry of AAV cassette elements: ITRs, promoters,
polyadenylation signals, enhancers, introns. WP-02 builds it.

```
data/parts/
  itr/        aav2_itr_left.json, aav2_itr_right.json
  promoter/   cmv.json, cag.json, ef1a.json, efs.json, hsyn1.json, cbh.json
  polya/      bgh.json, sv40.json, synthetic_short.json
  enhancer/   wpre.json
  intron/     chimeric.json
```

Each part record:

```json
{
  "id": "promoter.cmv",
  "name": "CMV promoter",
  "category": "promoter",
  "length_bp": 603,
  "sequence": "...",
  "host_compatibility": ["mammalian_general"],
  "tissue_specificity": null,
  "source": "Addgene pAAV-CMV backbone, accession <ID>",
  "notes": "Strong ubiquitous expression. Known to silence in some tissues over time.",
  "citation": "<DOI or accession>"
}
```

**Every part record must carry a real `sequence` and a real `source`.** A part
with a placeholder sequence is useless and dangerous: it will be exported as
orderable DNA. If a real sequence for a part is not available at build time, do
not include the part. Ship four real promoters rather than eight with two
invented.

Sequences come from the retrieval corpus already in the system, from NCBI
GenBank records the pipeline already ingests, or from repository backbone
records. WP-02 documents the provenance of every single part in
`data/parts/PROVENANCE.md`.

---

## 5. THE SHARED CAPABILITY CONTRACT

WP-02 defines this. Every capability implements it. This is what makes four
capabilities feel like one product.

### 5.1 Schemas

```python
# packages/core/schemas/capability.py

class CapabilityKind(str, Enum):
    PLASMID   = "plasmid"      # existing
    AAV       = "aav"          # §6
    ASSEMBLY  = "assembly"     # §7
    GUIDE_RNA = "guide_rna"    # §8

class Severity(str, Enum):
    PASS    = "pass"
    WARN    = "warn"      # Tier B: surfaced, explained, not a failure
    FAIL    = "fail"
    UNKNOWN = "unknown"   # could not evaluate; never silently a pass

class CheckResult(BaseModel):
    check_id: str                  # stable, e.g. "aav.packaging_limit"
    label: str                     # human readable, for the UI
    severity: Severity
    message: str                   # actionable. says what to do, not just what is wrong.
    coordinates: tuple[int, int] | None = None
    observed: str | None = None    # "4,912 bp"
    threshold: str | None = None   # "4,700 bp"
    citation: str | None = None    # why this threshold exists
    tier: Literal["A", "B"] | None = None

class ValidationReport(BaseModel):
    capability: CapabilityKind
    overall: Severity              # worst non-UNKNOWN severity present
    checks: list[CheckResult]
    evaluated_at: datetime
    validator_version: str         # bump when any threshold changes

class DesignResult(BaseModel):
    capability: CapabilityKind
    design_id: str
    report: ValidationReport
    artifacts: dict[str, str]      # format -> path or inline payload
    provenance: list[str]          # every part id and template used
    parameters_used: dict[str, Any] # every threshold that was applied
```

### 5.2 The generator interface

```python
class CapabilityGenerator(Protocol):
    kind: CapabilityKind
    def compose(self, request: BaseModel) -> BaseModel: ...
```

### 5.3 The validator interface

```python
class CapabilityValidator(Protocol):
    kind: CapabilityKind
    version: str
    def validate(self, design: BaseModel) -> ValidationReport: ...
```

### 5.4 Rules that bind every implementation

1. `overall` is the worst severity among non-`UNKNOWN` checks. If any check is
   `UNKNOWN`, that fact appears in the UI separately. `UNKNOWN` never improves
   an overall verdict.
2. Every `CheckResult.message` is **actionable**. "Cassette too long" is
   insufficient. "Cassette is 4,912 bp, which is 212 bp over the 4,700 bp
   packaging limit. Consider the 212 bp EFS promoter in place of the 1,702 bp
   CAG promoter, or the 135 bp SV40 polyA in place of the 225 bp bGH polyA." is
   correct.
3. Every threshold used appears in `parameters_used`. A user must be able to see
   what the verdict was measured against.
4. `validator_version` bumps on any threshold change, so a stored report can be
   interpreted later.
5. `provenance` lists every part and template. No base in the output is
   unattributable.

---

## 6. CAPABILITY A: AAV VECTOR DESIGNER

**Owner: WP-03. Branch: `feat/aav`. Model: Opus.**

This is the most important capability in this build. It is the one that makes
the deterministic-validation argument viscerally obvious, because the central
constraint is a hard physical limit that produces an expensive failure when
violated. See §15 for why this is the demo.

### 6.1 What it does

The user describes a gene therapy vector in natural English: a transgene, a
target tissue, a promoter preference, whether self-complementary. The system
composes a complete AAV cassette from real parts, checks it against the
packaging constraint and the structural requirements, and returns either a
validated cassette or a specific, quantified explanation of why it does not fit
and what to change.

### 6.2 Biological background the implementer needs

Adeno-associated virus is a small, non-pathogenic, replication-deficient vector
used in approved gene therapies. For vector design purposes:

- The recombinant genome is a single-stranded DNA cassette flanked by **inverted
  terminal repeats (ITRs)**. The ITRs are the only viral sequence retained; they
  are required in *cis* for replication and packaging.
- The wild-type genome is approximately **4.7 kb**. The capsid imposes a hard
  physical ceiling. Cassettes meaningfully above it package poorly and produce
  truncated genomes, which means wasted production runs and failed experiments.
- **Self-complementary AAV (scAAV)** packages an inverted-repeat genome that
  self-anneals into double-stranded DNA, bypassing the rate-limiting
  second-strand synthesis step. It expresses faster and at lower dose, but it
  **halves the usable capacity** because the genome is effectively duplicated.
- Cassette order is fixed by function:
  `5' ITR → [enhancer] → promoter → [intron] → transgene CDS → [WPRE] → polyA → 3' ITR`
- Promoter choice encodes tissue specificity. A neuron-specific promoter in a
  liver-targeted vector is a design error that no length check will catch, which
  is why §6.4 check 8 exists.

### 6.3 Request schema

```python
class AAVRequest(BaseModel):
    transgene_name: str
    transgene_sequence: str | None = None      # if absent, retrieve by name
    target_tissue: Literal[
        "cns_neuron", "cns_astrocyte", "retina", "liver",
        "muscle", "cardiac", "ubiquitous"
    ]
    serotype: str = "AAV2"                      # ITR source; AAV2 ITRs are standard
    self_complementary: bool = False
    promoter_preference: str | None = None      # part id; else auto-selected
    include_wpre: bool = True
    polya_preference: str | None = None
    packaging_limit_bp: int | None = None       # override; default from constants
```

### 6.4 The validation checks

Every check has a stable `check_id`, a severity, and a citation. **These are the
checks. Implement all of them. Do not add an invented one.**

| # | `check_id` | What it verifies | Severity on violation |
|---|---|---|---|
| 1 | `aav.packaging_limit` | Total length, 5' ITR start through 3' ITR end inclusive, against the limit | See §6.5 banding |
| 2 | `aav.itr_present_both` | Both ITRs present and sequence-matched to the serotype reference above the identity threshold | FAIL |
| 3 | `aav.itr_orientation` | The two ITRs are inverted relative to each other, not tandem | FAIL |
| 4 | `aav.required_elements` | Promoter, transgene CDS, and polyA all present | FAIL |
| 5 | `aav.element_order` | Elements appear in the §6.2 functional order | FAIL |
| 6 | `aav.cds_integrity` | CDS has an ATG start, an in-frame stop, length divisible by 3, no premature in-frame stop | FAIL |
| 7 | `aav.sc_capacity` | If `self_complementary`, the halved limit is applied | See §6.5 banding |
| 8 | `aav.promoter_tissue_match` | Promoter `tissue_specificity` is compatible with `target_tissue` | WARN |
| 9 | `aav.internal_repeats` | No direct repeat above the configured length within the cassette, which risks recombination during production | WARN |
| 10 | `aav.homopolymer_runs` | No homopolymer run above the configured length, which destabilizes synthesis and replication | WARN |
| 11 | `aav.kozak_context` | An ATG with a recognizable Kozak context precedes the CDS | WARN |
| 12 | `aav.polya_present_functional` | PolyA is a recognized functional signal, not merely an annotation | FAIL if absent, WARN if unrecognized |
| 13 | `aav.minimum_genome_size` | Genome is not so small that packaging efficiency degrades | WARN |
| 14 | `aav.itr_internal_sites` | No sequence inside the cassette that duplicates an ITR motif | WARN |

### 6.5 The packaging limit, banded

This is the single most load-bearing number in the capability, and labs genuinely
disagree about the practical ceiling. Band it rather than asserting one value,
and make every boundary configurable.

```python
# packages/validation/aav/constants.py

# Total recombinant genome length, 5' ITR start through 3' ITR end, inclusive.
# Wild-type AAV genome is approximately 4,700 bp and the capsid imposes a
# physical ceiling near that size. Oversized genomes package with reduced
# efficiency and produce truncated species.
AAV_SS_TARGET_BP      = 4_700   # at or under: PASS
AAV_SS_SOFT_LIMIT_BP  = 4_900   # over target, at or under this: WARN
AAV_SS_HARD_LIMIT_BP  = 5_200   # over this: FAIL

# Self-complementary AAV packages an inverted-repeat genome that is
# effectively double the cassette, which halves usable capacity.
AAV_SC_TARGET_BP      = 2_400
AAV_SC_SOFT_LIMIT_BP  = 2_500
AAV_SC_HARD_LIMIT_BP  = 2_600

# Below this, packaging efficiency degrades and empty capsid fraction rises.
AAV_MIN_GENOME_BP     = 2_000

ITR_IDENTITY_THRESHOLD = 0.95   # fraction match to the serotype reference
MAX_DIRECT_REPEAT_BP   = 20
MAX_HOMOPOLYMER_RUN    = 8
```

**Severity banding for check 1:**

| Total length | Severity | Message must include |
|---|---|---|
| ≤ target | PASS | the measured length and the limit |
| > target, ≤ soft limit | WARN | the overage in bp, and that titer may be reduced |
| > soft limit | FAIL | the overage in bp, **and at least one specific element substitution that would fix it**, computed from the part registry |

That last requirement is what turns a validator into a tool. See §6.6.

### 6.6 The remediation engine

When `aav.packaging_limit` fails, the system does not stop at "too long." It
computes the fix.

Algorithm:

1. Compute the overage: `total - target`.
2. For each element in the cassette, enumerate registry parts in the same
   category with the same or compatible `host_compatibility` and
   `tissue_specificity`.
3. For each candidate substitution, compute the bp saved.
4. Report the minimum set of substitutions that closes the overage, preferring
   fewer substitutions, then preferring to preserve the user's stated
   `promoter_preference`.
5. If no combination of registry substitutions closes the gap, say so explicitly
   and report the remaining deficit, suggesting that the transgene itself may
   need a shorter variant or a dual-vector approach.

Worked example, which the demo in §15 uses:

> Cassette is 5,048 bp. The single-stranded packaging target is 4,700 bp, so the
> design is 348 bp over and 152 bp under the hard ceiling of 5,200 bp.
>
> One substitution closes it: replacing the CAG promoter (1,702 bp) with the EFS
> promoter (212 bp) saves 1,490 bp and brings the cassette to 3,558 bp. EFS is
> ubiquitous like CAG, so tissue specificity is preserved, though expression is
> weaker.
>
> A smaller change also works: replacing the bGH polyA (225 bp) with the SV40
> polyA (135 bp) saves 90 bp, and dropping WPRE (approximately 600 bp) saves a
> further 600 bp. Either of those two together closes the overage while keeping
> the CAG promoter.

That output is the product. Build the engine that produces it.

### 6.7 Composition

The generator:

1. Resolves the transgene sequence, from the request or by retrieval.
2. Selects a promoter: the user's preference if given and compatible, otherwise
   the registry part whose `tissue_specificity` matches `target_tissue`,
   preferring the shortest compatible part when `self_complementary` is set.
3. Selects a polyA, defaulting to the shortest functional signal when capacity
   is tight.
4. Includes WPRE only if requested and if it fits.
5. Loads the serotype ITR pair.
6. Assembles in functional order, annotating every element with its registry id
   and coordinates.
7. Returns the candidate with full `provenance`.

### 6.8 Outputs

- Annotated cassette, rendered as a **linear** map in the UI. AAV cassettes are
  linear, not circular. Do not reuse the circular renderer for this.
- A length budget table: every element, its bp, its running total, and the
  remaining headroom against the limit. This single table is the clearest thing
  in the whole product.
- GenBank export with every element as a feature.
- FASTA export.
- The validation report.

---

## 7. CAPABILITY B: PRIMER AND ASSEMBLY DESIGNER

**Owner: WP-04. Branch: `feat/assembly`. Model: Opus.**

This capability turns every design the system produces into something a lab can
order and run. It makes the existing plasmid capability strictly more valuable
rather than adding a parallel silo.

### 7.1 What it does

Given a construct and an assembly strategy, design the primers and produce the
step-by-step plan to build it at the bench: what to order, what to mix, what
temperatures, what to expect.

Three strategies:

- **Gibson assembly:** fragments share terminal homology; an exonuclease plus
  polymerase plus ligase mix joins them in one tube.
- **Golden Gate assembly:** a Type IIS restriction enzyme cuts outside its own
  recognition site, leaving defined 4 bp overhangs, enabling scarless one-pot
  assembly of multiple fragments. Requires that the enzyme's recognition site
  appear nowhere inside the fragments, a process called domestication.
- **Simple PCR cloning:** amplify with primers carrying restriction sites.

### 7.2 Request schema

```python
class AssemblyRequest(BaseModel):
    strategy: Literal["gibson", "golden_gate", "pcr_cloning"]
    fragments: list[Fragment]              # sequence + role + source
    vector_backbone: str | None = None
    enzyme: str | None = None              # required for golden_gate
    target_tm_c: float = 60.0
    primer_conc_nm: float = 500.0
    monovalent_salt_mm: float = 50.0
    divalent_salt_mm: float = 1.5
    dntp_mm: float = 0.2
```

### 7.3 Melting temperature: the real math

**Use nearest-neighbor thermodynamics. Do not use the Wallace rule
(`4*GC + 2*AT`) or any GC-percentage approximation.** Those are wrong by several
degrees on real primers, and several degrees is the difference between a clean
PCR and no product. The parameter tables are in Appendix A.

For a non-self-complementary duplex:

```
ΔH°total = Σ ΔH°(nearest-neighbor pairs) + ΔH°(initiation terms)
ΔS°total = Σ ΔS°(nearest-neighbor pairs) + ΔS°(initiation terms)

Tm (K) = (ΔH°total * 1000) / (ΔS°total + R * ln(C_T / 4))
Tm (C) = Tm(K) - 273.15
```

where `R = 1.987 cal/(mol·K)`, `ΔH°` is in kcal/mol, `ΔS°` is in cal/(mol·K),
and `C_T` is total strand concentration in mol/L. For a self-complementary
duplex, use `C_T` rather than `C_T / 4` and apply the symmetry correction from
Appendix A.

**Salt correction.** The unified parameters are for 1 M Na+. Correct the entropy
for the actual monovalent concentration:

```
ΔS°(salt) = ΔS°(1M) + 0.368 * (N - 1) * ln([Na+])
```

where `N` is the number of phosphates in the duplex, which is the oligo length,
and `[Na+]` is in mol/L. If magnesium and dNTPs are specified, convert to a
monovalent equivalent before applying this; record which conversion was used in
the docstring with its source.

**Validate the implementation against known values.** Appendix A includes test
oligos with expected Tm. If your implementation disagrees by more than 1.0 °C on
those, it is wrong. This is a unit test, not an optional check.

### 7.4 Secondary structure

- **Hairpin:** find the best self-complementary fold and compute its ΔG. Flag
  primers whose hairpin ΔG falls below the configured threshold, especially when
  the stem involves the 3' end.
- **Self-dimer and hetero-dimer:** compute best-scoring alignments between a
  primer and itself, and between the two primers of a pair. **3' end involvement
  is what matters**, because a 3' dimer is extendable and produces primer-dimer
  artifact that consumes the reaction.

A full ΔG minimization is out of scope. A sliding-window complementarity score
with explicit 3' weighting is sufficient and defensible, provided the scoring is
documented. If `ViennaRNA` is installable in the environment, prefer it for
hairpin ΔG and record that choice.

### 7.5 Validation checks

| # | `check_id` | What it verifies | Severity |
|---|---|---|---|
| 1 | `primer.tm_in_range` | Each primer's Tm within the configured window | WARN outside, FAIL far outside |
| 2 | `primer.pair_tm_delta` | ΔTm between a pair at or under the threshold | WARN |
| 3 | `primer.gc_content` | GC fraction within the configured window | WARN |
| 4 | `primer.length` | Length within the configured window | WARN |
| 5 | `primer.three_prime_stability` | 3' terminal base and the last five bases are not excessively GC-rich, and the 3' base is not T | WARN |
| 6 | `primer.hairpin` | Hairpin ΔG at or above threshold, with extra weight on 3' stems | WARN, FAIL if 3' stem below hard threshold |
| 7 | `primer.self_dimer` | No extendable 3' self-complementarity | WARN |
| 8 | `primer.hetero_dimer` | No extendable 3' complementarity between the pair | WARN |
| 9 | `primer.specificity_in_template` | The binding region occurs exactly once in the supplied template set | FAIL on multiple, FAIL on zero |
| 10 | `primer.homopolymer` | No run above the configured length | WARN |
| 11 | `gibson.overlap_length` | Terminal homology within the configured window | FAIL outside |
| 12 | `gibson.overlap_tm` | Overlap Tm at or above the configured floor | WARN |
| 13 | `gibson.overlap_uniqueness` | No two junctions share homology that would allow mis-assembly | FAIL |
| 14 | `gg.enzyme_site_internal` | The chosen Type IIS recognition site appears nowhere inside any fragment | FAIL, with a domestication report |
| 15 | `gg.overhang_uniqueness` | All 4 bp fusion overhangs in the assembly are distinct | FAIL |
| 16 | `gg.overhang_not_palindromic` | No overhang is its own reverse complement, which would allow either orientation | FAIL |
| 17 | `gg.overhang_composition` | No overhang is all-GC or all-AT, which assembles inefficiently | WARN |
| 18 | `assembly.fragment_order_defined` | Overhang topology produces exactly one assembly order | FAIL if ambiguous |
| 19 | `assembly.amplicon_size` | Each expected amplicon is within a PCR-reasonable size | WARN |

### 7.6 Golden Gate domestication

When check 14 fails, produce a domestication report, not just a rejection:

For each internal occurrence of the enzyme recognition site, find a **silent**
substitution that destroys the site. If the site falls inside a coding sequence,
the substitution must preserve the amino acid, which means choosing a synonymous
codon, and should prefer a codon that is common in the target host so expression
is not degraded. Report the position, the original codon, the proposed codon, the
amino acid preserved, and the host codon frequency of both.

If the site falls outside a coding sequence, any substitution that destroys the
site is acceptable; prefer the minimal edit.

This is exactly the kind of output that reads as a real tool rather than a
checker.

### 7.7 Outputs

- An **order table**: primer name, sequence written 5' to 3', length, Tm, GC%,
  and a notes column. This is the artifact a lab actually uses, so it must be
  copy-pasteable and CSV-exportable.
- A **protocol**: reaction composition, thermocycling program with the annealing
  temperature derived from the computed Tm rather than assumed, assembly reaction
  conditions, and expected outcome.
- A **junction map** showing how fragments join, with overhangs or homology arms
  labeled.
- The domestication report, when applicable.
- The validation report.

---

## 8. CAPABILITY C: CRISPR GUIDE RNA DESIGNER

**Owner: WP-05. Branch: `feat/grna`. Model: Opus.**

Highest name recognition of anything in this build. A business judge knows the
word CRISPR and may know nothing else on the slide. It also has the most
competitive landscape, so §8.6 and §8.7 are what differentiate it: honest
scoping and honest uncertainty.

### 8.1 What it does

Given a target sequence and a nuclease, enumerate every valid guide, score each
for predicted on-target activity, search the declared off-target space, and rank
with the reasoning shown.

### 8.2 Request schema

```python
class GuideRNARequest(BaseModel):
    target_sequence: str
    target_name: str
    nuclease: Literal["SpCas9", "SaCas9", "LbCas12a", "AsCas12a"] = "SpCas9"
    edit_intent: Literal["knockout", "knockin", "activation", "interference"]
    off_target_space: OffTargetSpace          # see §8.6
    max_guides_returned: int = 10
```

### 8.3 Enumeration

For the chosen nuclease, scan both strands for every valid PAM and extract the
corresponding protospacer at the correct offset and orientation. Appendix C
carries the PAM motif, spacer length, and PAM position for every supported
nuclease.

Two implementation notes that are easy to get wrong:

- **Cas12a's PAM is 5' of the spacer**, not 3' like Cas9. Hard-coding a 3' offset
  will silently produce garbage guides for Cas12a.
- **Scan both strands.** A guide targeting the reverse strand is equally valid,
  and reporting only forward-strand guides halves the design space for no reason.

### 8.4 On-target scoring

Implement a published position-dependent scoring model. The model used must be
named in the code, in the UI, and in `progress/WP-05.md`, with its citation and
its stated validity domain.

Critical constraint: **a published model is valid only in the context it was
trained on.** A model trained on U6-driven plasmid-expressed SpCas9 in human
cells does not transfer to in-vitro-transcribed guide in zebrafish. If the
request falls outside the model's domain, the score is returned with an explicit
caveat, or returned as `UNKNOWN`. Do not silently extrapolate.

If a faithful implementation of a published model is not achievable in the time
available, the correct fallback is **a transparent heuristic, clearly labeled as
a heuristic, not as a published score.** Composed of the §8.5 sequence features
with stated weights. A labeled heuristic is defensible. A heuristic presented as
a validated published score is not, and it is the kind of thing that ends badly
under questioning.

### 8.5 Sequence feature checks

| # | `check_id` | What it verifies | Severity |
|---|---|---|---|
| 1 | `grna.pam_valid` | A valid PAM for the nuclease at the correct offset and orientation | FAIL |
| 2 | `grna.spacer_length` | Spacer length correct for the nuclease | FAIL |
| 3 | `grna.gc_content` | GC fraction within the configured window | WARN |
| 4 | `grna.u6_terminator` | No `TTTT` in the spacer, which prematurely terminates U6 transcription | FAIL when U6-driven, WARN otherwise |
| 5 | `grna.homopolymer` | No run above the configured length | WARN |
| 6 | `grna.self_complementarity` | No internal self-complementarity that would disrupt the scaffold fold | WARN |
| 7 | `grna.position_in_cds` | For knockout, the cut site falls in an early constitutive region rather than the final exon | WARN |
| 8 | `grna.self_targeting` | The guide does not target the delivery plasmid itself | FAIL |
| 9 | `grna.restriction_in_spacer` | Spacer does not contain a site needed for the cloning strategy | WARN |

### 8.6 Off-target search, scoped honestly

This is where competing tools win, and where overclaiming is most tempting.
**A genome-wide off-target search needs a prebuilt index that this build does
not have.** Pretending otherwise is the fastest way to lose credibility with
anyone who has used a real guide design tool.

The honest architecture:

```python
class OffTargetSpace(BaseModel):
    scope: Literal["construct_only", "supplied_fasta", "none"]
    fasta_path: str | None = None
    label: str          # shown verbatim in the UI and in every export
```

- `construct_only`: search the delivery construct and the target sequence.
  Catches self-targeting and intra-construct repeats. Always available.
- `supplied_fasta`: search a user-provided sequence set. Honest, useful, and
  scales to whatever the user actually cares about.
- `none`: no off-target search. The UI must say so prominently.

**The UI must state the searched space verbatim, in every view and every export.**
Example: "Off-target search covered the delivery construct and the supplied 2.4 Mb
sequence set. This is not a genome-wide search." That sentence is a feature. It
tells a sophisticated user exactly what they are getting, which is more than some
tools do.

Scoring off-target hits: use a published mismatch-position-weighted model, named
and cited. The biologically important principle, which the implementation must
reflect, is that **mismatches in the PAM-proximal seed region are far more
disruptive to binding than distal mismatches.** A model that weights all
positions equally is wrong.

Severity: FAIL on any off-target with very few mismatches concentrated outside
the seed, WARN on moderate hits, PASS when the searched space is clean. The
thresholds are configurable with defaults documented.

### 8.7 Outputs

- A ranked guide table: spacer sequence written 5' to 3', PAM, strand,
  coordinates, on-target score, off-target summary, and flags.
- Per guide, the **reasoning**: which features drove the score up or down. A
  score with no explanation is not usable, and the explanation is the
  differentiator.
- Cloning-ready oligos for the chosen scaffold and vector, including any required
  5' overhangs for the cloning strategy.
- The off-target space statement, verbatim.
- The validation report.

---

## 9. GOLD SETS AND VALIDATION METHODOLOGY

**Owner: WP-06. Model: Opus.** This package is not optional and it is not
decoration. Read §0.3 again.

### 9.1 Why this is the most important work package

The existing claim is "36 known-good and 52 known-bad constructs, 100% combined
accuracy." Adding three capabilities with no gold sets silently converts that
sentence into a claim about one quarter of the product. Anyone who evaluates
models for a living will ask what the number covers, and the answer needs to be
"all four capabilities" rather than a change of subject.

### 9.2 Per-capability requirement

Minimum per capability:

| | Count | Composition |
|---|---|---|
| Known-good Tier A | 6 | Validates clean, no warnings |
| Known-good Tier B | 4 | Validates with documented, intentional warnings |
| Known-bad | 10 | Each fails for exactly one identified reason |

Target: 10 / 5 / 14 if time allows.

### 9.3 Known-bad cases must fail for the right reason

A known-bad case asserts **which check** should catch it. A case that fails for
an unintended reason is a test that proves nothing.

```json
{
  "case_id": "aav.bad.over_hard_limit",
  "capability": "aav",
  "expect_overall": "fail",
  "expect_check": "aav.packaging_limit",
  "expect_severity": "fail",
  "rationale": "Cassette totals 5,340 bp, above the 5,200 bp hard ceiling.",
  "must_also_report": ["remediation_suggestion"],
  "input": { }
}
```

The test harness asserts: the overall severity matches, **the named check
reports the expected severity**, and no unexpected FAIL appears. That third
assertion is what catches a validator that is accidentally right.

### 9.4 Suggested known-bad cases

These are starting points. WP-06 may add, but must cover every one of these.

**AAV:** over the hard limit; between target and soft limit, expecting WARN not
FAIL; scAAV cassette sized legally for ssAAV, expecting FAIL under the halved
capacity; one ITR missing; ITRs in tandem rather than inverted; no polyA; CDS
with a premature in-frame stop; CDS length not divisible by three; elements out
of functional order; neuron-specific promoter with a liver target, expecting WARN;
long internal direct repeat; genome below the minimum size.

**Assembly:** primer pair with a large ΔTm; primer with a strong 3' hairpin;
primer pair with extendable 3' hetero-dimer; primer binding in two places in the
template; Golden Gate fragment containing an internal enzyme site, expecting the
domestication report; two identical overhangs in one assembly; a palindromic
overhang; Gibson overlap far too short; two Gibson junctions sharing homology;
an amplicon far too long.

**gRNA:** no PAM present; spacer length wrong for the nuclease; `TTTT` in the
spacer under U6; guide targeting its own delivery plasmid; guide with a very
close off-target in the searched space; Cas12a request scored with a Cas9 PAM
offset, which is the integration bug most likely to exist; guide in the final
exon for a knockout intent; GC far outside the window.

### 9.5 Reporting

```bash
make eval-all      # every capability, every case
make eval-check    # fails the build on any regression
```

Output per capability: counts, accuracy, and **every disagreement listed
individually** with the case id, expected check, and actual result. An aggregate
percentage with no per-case detail is not a report.

### 9.6 How to describe the number honestly

Once all four capabilities have gold sets, the defensible sentence is:

> N of N on our curated gold set, spanning four capability types, with M
> known-good and K known-bad cases.

Never "100% accurate." Never the figure without the word "curated." The set was
assembled by the team, there is no held-out split, and anyone who evaluates
models will assume selection bias unless told the scope. Saying the scope out
loud is what makes the number credible rather than suspicious. See §16.

---

## 10. WEB APPLICATION SURFACES

**Owner: WP-07. Model: Sonnet.** Follow the existing patterns in `apps/web`.
Do not introduce a new design language. The reason the current app looks good is
consistency.

### 10.1 Capability selector

The existing chat workspace gains a capability selector with four options:
Plasmid, AAV vector, Assembly and primers, Guide RNA. Selecting one changes the
request form and the result panel. The conversational refinement loop, the
evidence panels, and the export actions are shared and unchanged.

### 10.2 Per-capability result panels

| Capability | Primary visual | Secondary |
|---|---|---|
| Plasmid | Existing circular seqviz map | Existing panels |
| AAV | **Linear** cassette map with elements to scale | **The length budget table.** Element, bp, running total, headroom against the limit. This is the clearest artifact in the product; give it room. |
| Assembly | Junction map | The order table, copy-pasteable, with CSV export |
| gRNA | Target sequence with guide positions marked on both strands | The ranked guide table with per-guide reasoning expandable |

AAV cassettes are linear. Do not render them circular. Reusing the circular
renderer because it exists would be a visible error to anyone in the field.

### 10.3 The validation report component

One shared component for all four capabilities, driven by `ValidationReport`.
Per row: the label, the severity, the message, the observed value against the
threshold, and the citation on hover or expand.

`UNKNOWN` rows render distinctly from `PASS`. A user must never read an
unevaluated check as a passed one.

### 10.4 Scope disclosure

Two statements must be visible in the UI, not buried:

1. The gRNA off-target space, per §8.6, stated verbatim wherever guides appear
   and in every export.
2. For any score from a published model, the model name and that it is a
   prediction rather than a measurement.

---

## 11. BIOSAFETY AND SCREENING

**Owner: WP-08. Model: Opus. This package is small and it is required.**

Every capability here designs research reagents: expression plasmids, AAV
research vectors, cloning primers, guide RNAs. This is standard molecular
biology, and the parts registry holds ordinary laboratory elements. The screening
below is good engineering practice for any tool that outputs orderable DNA, and
it is also the honest answer to a question a judge may ask now that the product
has moved from plasmids toward therapeutic modalities.

### 11.1 What to implement

A pre-export screening step that runs on every design before any export action:

1. **Sequence provenance assertion.** Every base in the output traces to a
   registry part, a retrieved template, or the user's own supplied input. A
   design containing unattributable sequence is blocked from export. This is
   mostly a correctness guarantee and it is the strongest safety property in the
   system.
2. **Registry-only composition.** Functional elements come from the curated
   registry. The system does not synthesize novel functional elements de novo.
3. **Screening hook.** A documented interface where a sequence screening step
   runs before export, with its result recorded in the design's provenance.
   Implement the interface and the recording. The screening backend itself is
   configurable.
4. **Export audit log.** Every export records what was exported, when, the
   validator version, and the screening result.

### 11.2 What to claim about it

Only what is implemented. If the screening hook ships with a provenance check
and an audit log but no external screening backend configured, then the claim is
"designs are composed only from curated parts, every base is attributable, and
exports are logged." That is true and it is a real property.

Do not claim "screened against biosecurity constraints" unless a screening
backend is actually wired and running. See §16.

---

## 12. WORK PACKAGES

### Wave 0: migration. Sequential. Nothing is parallel here.

| WP | Title | Model | Owns | Gate |
|---|---|---|---|---|
| **WP-00** | Seed the destination repo | Sonnet | git remotes, initial push, `PROGRESS.md`, `progress/` | Code is on `constructapp`, history intact, `upstream` attached |
| **WP-01** | Rebrand pass | Sonnet | Every file containing the old names | §2.4 gate passes in full, including the grep |

### Wave 1: foundation. Starts only after WP-01's gate passes.

| WP | Title | Model | Deps | Owns |
|---|---|---|---|---|
| **WP-02** | Capability contract and part registry | Opus | 01 | `packages/core/schemas/capability.py`, the capability registry, `data/parts/**`, `data/parts/PROVENANCE.md` |
| **WP-09** | Test harness extension | Sonnet | 01 | `tests/gold/runner.py`, `make eval-all`, `make eval-check` extended for multi-capability |

### Wave 2: capabilities. Fully parallel, one branch each.

| WP | Title | Model | Branch | Deps | Owns |
|---|---|---|---|---|---|
| **WP-03** | AAV vector designer | Opus | `feat/aav` | 02 | `packages/validation/aav/**`, `packages/generation/aav/**`, `packages/core/schemas/aav.py`, `services/api/routes/aav.py`, `tests/aav/**` |
| **WP-04** | Primer and assembly designer | Opus | `feat/assembly` | 02 | `packages/validation/assembly/**`, `packages/generation/assembly/**`, `packages/core/schemas/assembly.py`, `services/api/routes/assembly.py`, `tests/assembly/**` |
| **WP-05** | Guide RNA designer | Opus | `feat/grna` | 02 | `packages/validation/grna/**`, `packages/generation/grna/**`, `packages/core/schemas/grna.py`, `services/api/routes/grna.py`, `tests/grna/**` |

### Wave 3: integration.

| WP | Title | Model | Deps | Owns |
|---|---|---|---|---|
| **WP-06** | Gold sets, all three capabilities | Opus | 03, 04, 05, 09 | `tests/gold/aav/**`, `tests/gold/assembly/**`, `tests/gold/grna/**` |
| **WP-07** | Web surfaces | Sonnet | 03, 04, 05 | `apps/web/src/**` for the four capability views |
| **WP-08** | Provenance and screening | Opus | 02, 03, 04, 05 | `packages/application/screening/**`, export hook, audit log |

### Wave 4: verification.

| WP | Title | Model | Deps | Deliverable |
|---|---|---|---|---|
| **WP-10** | Scientific review | **Fable** | 02 through 08 | One pass over every constant, threshold, formula, and citation in the new code, checked against Appendix A through Appendix E and against the literature. Every disagreement reported with the file, the line, the value found, the value expected, and the source. **This package may not change code.** It reports; the owning package fixes. |
| **WP-11** | Final integration and demo rehearsal | Sonnet | all | §14 gates all green, §15 demo path walked end to end twice, report to the operator |

### 12.1 Parallelism

Wave 2 is the only place with meaningful parallelism, and it is three agents.
Waves 0 and 1 are gating. Do not attempt to parallelize the migration; a
half-rebranded tree with three capability branches on top is unrecoverable in
the time available.

---

## 13. FILE OWNERSHIP AND COLLISION RULES

### 13.1 One writer per file

A file has exactly one owning work package. An agent needing a change elsewhere
appends a line under `## Cross-WP requests` in `PROGRESS.md` and continues.

Two files are exempt, both with protocols: `PROGRESS.md` (§0.4, append one line)
and the capability registry (§13.3).

### 13.2 Why branches

Wave 2's three agents touch three disjoint directory trees, but they all need to
register themselves and they all touch the API router. Branches plus a sequenced
merge is the mechanism. Merge order: `feat/aav`, then `feat/assembly`, then
`feat/grna`, resolving the registry and router each time.

### 13.3 The capability registry

Three packages must add an entry. WP-02 creates the file with three reserved,
delimited regions:

```python
CAPABILITY_REGISTRY: dict[CapabilityKind, CapabilitySpec] = {
    CapabilityKind.PLASMID: PLASMID_SPEC,
    # ==== WP-03: AAV. Only WP-03 writes here. ====
    # ==== /WP-03 ====
    # ==== WP-04: assembly. Only WP-04 writes here. ====
    # ==== /WP-04 ====
    # ==== WP-05: guide RNA. Only WP-05 writes here. ====
    # ==== /WP-05 ====
}
```

Same convention for the API router include block. A merge conflict inside a
delimited region means an agent wrote outside its own, which is a spec violation
to be reported rather than resolved by hand.

### 13.4 Shared code

Anything two capabilities both need belongs in WP-02's scope, requested through a
cross-WP request. The predictable cases:

- Reverse complement, GC content, ORF finding, codon tables: shared utilities.
- **The nearest-neighbor Tm implementation:** WP-04 owns it, but WP-05 may need
  it. WP-04 places it in a shared location from the start.
- Sequence search and alignment primitives: WP-04 and WP-05 both need these.
  WP-02 provides them.

---

## 14. TESTING AND GATES

### 14.1 Per work package

No package is done until all of these pass:

```bash
make test                                  # full backend suite, green
python -m pytest tests/<capability> -v     # the package's own tests, green
make eval-all                              # gold sets, no regression
make eval-check                            # exit 0
```

Plus, for capability packages:

- Every constant has a docstring naming its source.
- Every `CheckResult.message` is actionable per §5.4 rule 2.
- `parameters_used` is populated on every result.
- `provenance` lists every part and template.
- A grep for the old names returns zero hits.
- No em dash in any file the package authored.

### 14.2 Numerical verification

WP-04's Tm implementation is checked against the Appendix A test oligos.
Tolerance: 1.0 °C. This is a unit test and it is a hard gate. A Tm
implementation that is silently wrong is worse than no Tm implementation,
because people will order primers from it.

### 14.3 The orchestrator's gate rule

The orchestrator evaluates **exit codes, not correctness.** It never decides
whether a constraint is biologically right. It runs the commands above, reads
the exit code, and merges on zero. Anything requiring biological judgment
escalates to WP-10 or to the operator.

This is what makes a Sonnet orchestrator safe here.

### 14.4 Definition of done

- [ ] Code is on `constructapp`, history intact.
- [ ] Zero hits for the old names outside `.git`.
- [ ] `make test`, `make demo`, `make eval-all`, `make eval-check` all green.
- [ ] Three new capabilities each generate a valid design and export it.
- [ ] Three new capabilities each correctly reject every known-bad case, with the
      expected check firing.
- [ ] Tm verified against the Appendix A oligos within 1.0 °C.
- [ ] Every new constant traceable to a source.
- [ ] AAV remediation produces a specific substitution suggestion, not just a
      rejection.
- [ ] gRNA off-target space stated verbatim in UI and exports.
- [ ] WP-10's scientific review reports zero unresolved disagreements.
- [ ] All four capabilities selectable and working in the web app.
- [ ] §15 demo walked end to end twice without intervention.
- [ ] Every claim in §16 worded as the allowed column specifies.

---

## 15. THE SATURDAY DEMO PATH

### 15.1 Run it locally

Do not deploy before Saturday. This stack is FastAPI plus Next.js plus Postgres
with pgvector plus Redis plus MinIO plus a worker. A public deploy means managed
Postgres with the pgvector extension, managed Redis, and a hosted service, and
attempting it the night before is the single likeliest way to arrive with nothing
working. Judges watch a demo driven by the presenter. They do not deploy it.

Deploy properly the following week, when it is not competing with the pitch.

### 15.2 Pre-flight, the morning of

```bash
docker compose up -d
make test            # must be green before you leave the house
make serve-local
make serve-web
```

Then, in the browser, run each of the four capabilities once. If the API key is
missing or a container did not come up, you want to know at breakfast.

### 15.3 The demo, in order

The ordering matters. It builds from legible to impressive.

1. **Plasmid, 30 seconds.** The existing flow. Establishes that the thing works
   and that there is a product underneath.
2. **AAV, over the limit. This is the moment.** Request a gene therapy vector
   with a large transgene and the CAG promoter. It fails. The report says the
   cassette is 5,048 bp against a 4,700 bp packaging target, 348 bp over, and
   names the specific substitution that fixes it. Make the substitution. It
   passes.

   That sequence is the entire pitch in twenty seconds: a real, expensive
   mistake, caught before anyone spent money, with the fix computed. It needs no
   biology background to land. A judge who does not know what AAV is still
   understands "it did not fit, and the software said exactly how to make it
   fit."
3. **Assembly, 30 seconds.** Take the passing AAV design and produce the primers
   and the protocol. The point is one sentence: "and here is what to order, and
   what to do at the bench on Monday."
4. **gRNA, 20 seconds, only if time.** Show the ranked table and say the
   off-target scope out loud. Saying the limitation yourself is stronger than
   being asked.

### 15.4 Questions to have answers ready for

- **"Isn't this just ChatGPT with a biology prompt?"** The checking is a rules
  engine, not a model. Same input, same verdict, every time, and every verdict
  cites the threshold it was measured against. Show the `parameters_used` panel.
- **"Where does the packaging limit come from?"** It is banded, configurable, and
  cited. Know the three numbers and know that labs disagree about the practical
  ceiling, which is why it is a band.
- **"What is your off-target search covering?"** The construct plus whatever
  sequence set the user supplies. Not genome-wide. Say it before being pushed.
- **"What does 100% accuracy mean?"** Give the raw counts, say "curated gold
  set," and say who assembled it. Do not say "100% accurate."
- **"Aren't you competing with Benchling?"** Benchling is where designs are
  recorded and managed. This generates and validates them. Know that distinction
  cold.
- **"Can it do CAR-T?"** The honest answer. See §16.

---

## 16. CLAIM SAFETY REGISTER

This governs every statement made about this system, in the UI, in exports, in
the pitch, and on the website.

| Claim | Allowed wording | Banned | Why |
|---|---|---|---|
| Capability breadth | Name the four capabilities that exist: plasmids, AAV vectors, assembly and primers, guide RNAs. For the rest: "on our roadmap." | Listing eleven capability types as shipped | Four real ones is a stronger position than eleven claimed ones, and the eleven-item list cannot survive "show me the CAR-T one." |
| CAR-T, antibodies, circuits, pathways | "Not built yet. Here is what we have." | Any present-tense claim | A cell therapy person will ask about the binder. The breadth claim is the single most probeable thing available. |
| Determinism | "The validation engine follows fixed rules. The same design produces the same verdict, and every verdict cites its threshold." | "Provably correct", "guaranteed valid", determinism extended to imply the biology is settled | Restriction site and length checks are rule scans. Codon fit is a score against a chosen table. Regulatory compatibility is a rules table, not settled science. The engine is deterministic; the biology is not. |
| Gold set | "N of N on our curated gold set across four capability types, M known-good and K known-bad." | "100% accurate", the figure without "curated" | §9.6. |
| On-target scores | Name the model and call it a prediction | "Validated", "measured", "guaranteed" | It is a prediction from a model with a stated validity domain. |
| Off-target | State the searched space verbatim | "Genome-wide", "comprehensive", "exhaustive" | §8.6. The search is scoped and the scope is a feature. |
| Biosafety | Only what §11 actually implements | "Screened against biosecurity constraints" absent a wired backend | §11.2. A false safety claim is the one overstatement that is never forgiven. |
| Clinical | Nothing | "Validated in the clinic", "FDA cleared", "used in an approved therapy" | Designing a vector is not a clinical product. |
| Wet lab | Nothing about lab operations | "Validated at the bench", "our lab results" | The outcome-capture loop is architecture, not evidence. |
| Data source | What §16 of the website spec permits | "Backed by", "investor", "licensed by" absent written confirmation | Naming a real third party's relationship wrongly is checkable in one email. |
| Primer Tm | "Nearest-neighbor thermodynamics with salt correction, verified against reference oligos within 1 °C" | Any accuracy claim beyond what the test shows | The test is the claim. |

---

## 17. OPEN QUESTIONS

Defaults apply if unanswered. Log the choice in `PROGRESS.md`.

| # | Question | Blocks | Default |
|---|---|---|---|
| Q1 | Is `~/constructapp` empty, or does it already contain work to reconcile? | WP-00 | Ask before deleting anything. |
| Q2 | Preserve commit history, or squash to a clean initial commit? | WP-00 | Preserve. It is real evidence of work. |
| Q3 | Rename the Postgres database and user, or keep internal names and rebrand only what is visible? | WP-01 | Keep internal names if the rename risks the test suite. Record it. |
| Q4 | Is `GOOGLE_API_KEY` available to the build agents? | WP-01 gate | Intent parsing degrades without it. Capability validators do not need it. Proceed, note it. |
| Q5 | Which ITR serotypes beyond AAV2 should the registry carry? | WP-02 | AAV2 only. It is the standard for recombinant vector ITRs. |
| Q6 | Is `ViennaRNA` installable in the environment? | WP-04 | If not, use the documented sliding-window complementarity score and label it. |
| Q7 | Which published on-target model for gRNA, and is a faithful implementation achievable in the time? | WP-05 | Implement one and cite it. If not achievable, ship the labeled heuristic per §8.4. Never present a heuristic as a published score. |
| Q8 | Is a sequence screening backend available to wire? | WP-08 | No. Ship the provenance check, the hook, and the audit log, and claim only those. |
| Q9 | Does the pitch deck still list all eleven capability types? | §16 | It should not. Narrow it to four plus a roadmap line. |
| Q10 | Can real part sequences be sourced for every registry element? | WP-02 | Ship only parts with real sequences. Four real promoters beat eight with two invented. |

---

## APPENDIX A: NEAREST-NEIGHBOR THERMODYNAMIC PARAMETERS

Unified nearest-neighbor parameters for Watson-Crick pairs in 1 M NaCl
(SantaLucia, 1998). `ΔH°` in kcal/mol, `ΔS°` in cal/(mol·K). Each entry is
written as the 5'-to-3' dinucleotide over its complement.

| NN pair | ΔH° | ΔS° |
|---|---|---|
| AA/TT | -7.9 | -22.2 |
| AT/TA | -7.2 | -20.4 |
| TA/AT | -7.2 | -21.3 |
| CA/GT | -8.5 | -22.7 |
| GT/CA | -8.4 | -22.4 |
| CT/GA | -7.8 | -21.0 |
| GA/CT | -8.2 | -22.2 |
| CG/GC | -10.6 | -27.2 |
| GC/CG | -9.8 | -24.4 |
| GG/CC | -8.0 | -19.9 |

Initiation terms:

| Term | ΔH° | ΔS° |
|---|---|---|
| Initiation with terminal G·C | 0.1 | -2.8 |
| Initiation with terminal A·T | 2.3 | 4.1 |
| Symmetry correction, self-complementary only | 0.0 | -1.4 |

Apply one initiation term per duplex end, chosen by that end's base pair.

Constants: `R = 1.987 cal/(mol·K)`.

Salt correction, monovalent:

```
ΔS°(salt) = ΔS°(1M) + 0.368 * (N - 1) * ln([Na+])
```

`N` is the oligo length in nucleotides. `[Na+]` in mol/L.

### A.1 Verification oligos

WP-04 must verify its implementation against reference values computed by an
established tool at stated conditions, and record both in
`progress/WP-04.md`. The gate is agreement within 1.0 °C.

Use at minimum these four, at 500 nM primer and 50 mM monovalent salt, spanning
the GC and length range primers actually occupy:

```
GC-balanced, 20 nt:   5'-GTAAAACGACGGCCAGTGAA-3'
GC-rich, 20 nt:       5'-GCGGCCGCGGCCGCGGCCGC-3'
AT-rich, 20 nt:       5'-AATTAATTAATTAATTAATT-3'
Short, 18 nt:         5'-ACGTACGTACGTACGTAC-3'
```

Reference values are **not** written into this spec, because a number copied
from memory is exactly the failure mode §0.3 forbids. WP-04 computes them with a
named, established tool, records the tool and version alongside each value, and
tests against those.

---

## APPENDIX B: AAV ELEMENT LENGTH REFERENCE

Approximate lengths for cassette budgeting. **These are planning figures.** The
authoritative length for any part is the length of the real sequence in that
part's registry record, and the validator measures the actual sequence, never
this table.

| Element | Category | Approx. bp | Notes |
|---|---|---|---|
| AAV2 ITR | itr | 130 to 145 | Required at both ends. The larger figure includes the D sequence. |
| CMV promoter | promoter | ~600 | Strong, ubiquitous. Can silence over time in some tissues. |
| CAG promoter | promoter | ~1,700 | Strong, ubiquitous. Large, so often the first thing cut when over budget. |
| EF1α, full | promoter | ~1,200 | Ubiquitous, durable expression. |
| EFS, short EF1α | promoter | ~212 | The compact ubiquitous option. Weaker than CAG. Valuable when capacity is tight. |
| hSyn1 | promoter | ~470 | Neuron-specific. |
| GFAP | promoter | ~680 | Astrocyte-specific. |
| CBh | promoter | ~800 | Hybrid, ubiquitous. |
| MeCP2, mini | promoter | ~230 | Compact, neuronal. |
| WPRE | enhancer | ~600 | Boosts expression. Optional, and the obvious cut when over budget. |
| Chimeric intron | intron | ~130 | Optional. |
| bGH polyA | polya | ~225 | Common default. |
| SV40 polyA | polya | ~135 | Smaller alternative. |
| Synthetic short polyA | polya | ~50 | Smallest functional option. |

Packaging limits are in §6.5.

---

## APPENDIX C: NUCLEASE AND PAM REFERENCE

| Nuclease | PAM motif | PAM position | Spacer length | Notes |
|---|---|---|---|---|
| SpCas9 | `NGG` | 3' of spacer | 20 nt | The standard. `NAG` is tolerated at substantially reduced efficiency; treat as a WARN-level alternative PAM, not a primary one. |
| SaCas9 | `NNGRRT` | 3' of spacer | 21 nt | Smaller protein, fits AAV more comfortably. `R` is A or G. |
| LbCas12a | `TTTV` | **5' of spacer** | 23 nt | `V` is A, C, or G. Staggered cut, not blunt. |
| AsCas12a | `TTTV` | **5' of spacer** | 23 nt | As above. |

IUPAC codes used: `N` any base, `R` purine (A or G), `V` A or C or G.

**The Cas12a 5' PAM position is the single most likely integration bug in
Capability C.** §9.4 requires a known-bad case for exactly this.

Sequence feature windows, all configurable with these defaults:

| Parameter | Default |
|---|---|
| Spacer GC fraction window | 0.40 to 0.70 |
| Maximum homopolymer run in spacer | 4 |
| U6 terminator motif to reject | `TTTT` |
| Seed region, PAM-proximal, for off-target weighting | 8 to 12 nt |

---

## APPENDIX D: TYPE IIS ENZYME REFERENCE

Type IIS enzymes cut outside their recognition sequence, which is what makes
scarless one-pot assembly possible. Notation `SITE(N1/N2)` means the enzyme cuts
N1 nucleotides 3' of the recognition site on the top strand and N2 on the
bottom, leaving an overhang of `N2 - N1` nucleotides.

| Enzyme | Recognition | Cut offsets | Overhang |
|---|---|---|---|
| BsaI | `GGTCTC` | (1/5) | 4 nt |
| BsmBI, also Esp3I | `CGTCTC` | (1/5) | 4 nt |
| BbsI, also BpiI | `GAAGAC` | (2/6) | 4 nt |
| SapI, also LguI | `GCTCTTC` | (1/4) | 3 nt |
| AarI | `CACCTGC` | (4/8) | 4 nt |

Domestication, §7.6, must check **both strands** for the recognition site, since
these sequences are not palindromic.

Overhang rules for check 15 through 17: all overhangs in one assembly distinct;
no overhang equal to its own reverse complement; avoid all-GC and all-AT
compositions. If the assembly follows a published modular standard, use that
standard's defined overhang set rather than generating overhangs, and cite the
standard.

---

## APPENDIX E: LITERATURE THE IMPLEMENTATIONS DERIVE FROM

Agents must consult primary sources for anything they implement. This list names
what to look up. **It deliberately does not reproduce coefficient tables beyond
Appendix A**, because a coefficient recalled rather than read is the exact
failure §0.3 forbids. Fetch the paper, read the table, cite it in the docstring.

**Nearest-neighbor thermodynamics.** SantaLucia 1998, the unified nearest-neighbor
parameters, is the source for Appendix A. Allawi and SantaLucia 1997 covers
mismatch parameters if ever needed. For salt corrections beyond the monovalent
formula, Owczarzy and colleagues published treatments covering magnesium and
mixed-ion conditions; consult these if the divalent inputs in §7.2 are used for
anything beyond a documented conversion.

**Primer design rules.** Standard guidance on length, GC content, 3' end
composition, and dimer avoidance is well established across primer design
literature and the documentation of established tools. Where the implementation
picks a threshold, cite where it came from.

**Golden Gate and modular assembly.** Engler and colleagues introduced the
one-pot Type IIS method. Subsequent modular cloning standards define overhang
sets and part grammars. If the implementation follows a standard, cite that
standard and use its defined overhangs.

**Gibson assembly.** Gibson and colleagues described the isothermal
exonuclease-polymerase-ligase method. Overlap length and Tm guidance comes from
that work and from the documentation of commercial master mixes.

**CRISPR on-target scoring.** Doench and colleagues published position-dependent
activity models, with the 2016 work being the widely used rule set. Moreno-Mateos
and colleagues addressed in-vitro-transcribed guides, a different validity
domain. §8.4 requires the chosen model be named with its domain.

**CRISPR off-target scoring.** Hsu and colleagues 2013 introduced a widely used
mismatch-position-weighted specificity score. Doench 2016 introduced the cutting
frequency determination approach. Both encode the principle in §8.6 that
PAM-proximal mismatches matter more.

**AAV vector design.** Packaging capacity, ITR requirements, and the
self-complementary capacity reduction are covered extensively in AAV vectorology
reviews. The practical ceiling is genuinely contested in the literature, which is
why §6.5 bands it rather than asserting a single value. Cite what the band is
based on.

**Codon usage.** Host codon usage tables and the codon adaptation index are the
basis for the synonymous substitution preference in §7.6. Name the table and the
host.

---

*End of specification. Build state goes in `PROGRESS.md`.*
