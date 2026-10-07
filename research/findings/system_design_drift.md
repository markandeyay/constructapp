# SYSTEM_DESIGN Drift Audit

- Date: 2026-06-13
- Branch/worktree: `demo-readiness` in the Construct worktree
- Scope: drift between `SYSTEM_DESIGN.md`, current implementation, `PROGRESS.md`, and relevant `research/findings/` policy docs.
- Constraint: `SYSTEM_DESIGN.md` was not edited.

## Summary

`SYSTEM_DESIGN.md` still describes the long-term product shape, but several sections now lag behind the operational project policy. The largest drift areas are data-source policy, phase ordering, Phase 2 model/fine-tuning policy, Phase 4 demo limitations, outcome-capture shape, and rollout governance.

Some items below are not implementation defects. They are places where the design doc implies a stronger or different current state than the project now permits. Recommended actions are phrased as review actions for a future design refresh.

## Findings

### 1. Section 0 / document authority

**Location:** `SYSTEM_DESIGN.md` lines 3, 33-34, and 70-71.

**Design text/current implication:** The design doc calls itself the "single source of truth" and the immutable specification, while `PROGRESS.md` records mutable state.

**Current reality:** Current project policy is spread across `PROGRESS.md` and later findings docs. Examples include the Addgene/legal gating policy, the 31/52 curated-quality Phase 3 gate, Carbon-first Phase 2 policy, one authorized USD 300 Phase 2 fine-tune, frontend-only outcome history, and canary/shadow restrictions. These are now controlling operational facts even when not fully reflected in `SYSTEM_DESIGN.md`.

**Impact:** A future agent that follows only `SYSTEM_DESIGN.md` can make unsafe or stale decisions, especially around source licensing, phase gates, and model rollout.

**Recommended review action:** Add a short "policy overlays" section or explicit cross-reference list in `SYSTEM_DESIGN.md` naming the findings docs and `PROGRESS.md` fields that currently supersede or refine the original design.

### 2. Section 3.0 / phase ordering rationale

**Location:** `SYSTEM_DESIGN.md` lines 128-140.

**Design text/current implication:** The phase order implies Phase 0 gates the data foundation before downstream build phases, with Phase 4 only partly parallel after Phase 1.

**Current reality:** The repo has intentionally progressed out of strict phase order. `PROGRESS.md` says Phase 1 and Phase 3 gates are met while the Phase 0 scale gate remains unmet. Phase 4 API/frontend foundations and Phase 5 outcome foundations are also merged/scaffolded. This was a practical de-risking path, not the linear path implied by the original rationale.

**Impact:** The design doc under-explains why Phase 1/3/4/5 artifacts exist before Phase 0 scale completion and can lead agents to misclassify valid merged work as out-of-policy.

**Recommended review action:** Clarify that phase gates are formal product readiness gates, but humans may authorize bounded vertical slices out of sequence when the slice does not claim the unmet upstream gate.

### 3. Section 5.2 / data-source priority

**Location:** `SYSTEM_DESIGN.md` lines 457-466.

**Design text/current implication:** Addgene is listed as the primary plasmid repository and the ingestion plan expects `ingest/addgene.py` to pull metadata and sequences.

**Current reality:** Addgene direct ingestion is blocked pending partner/API access, terms, and commercial licensing. The active safe path is NCBI-backed curated seed data, GenBank engineered-vector lanes, and proposed RefSeq/GenBank expansion with source-lane and license metadata. `packages/data_pipeline/ingest/addgene.py` explicitly errors without approved credentials/license, while the curated manifest excludes Addgene-only records pending approval.

**Impact:** Treating Addgene as the default data source can violate current provenance/legal policy and can cause agents to chase a blocked credential path instead of the approved NCBI/curated lanes.

**Recommended review action:** Reframe Addgene as the preferred future high-context source once licensed, and document NCBI/curated/RefSeq lanes as the current default implementation policy.

### 4. Sections 5.6 and 3.1 / Phase 0 scale gate

**Location:** `SYSTEM_DESIGN.md` lines 166 and 497-499.

**Design text/current implication:** Phase 0 acceptance requires at least 50,000 fully parsed, component-annotated plasmids and one CLI command reproducing the whole pipeline from an empty DB.

**Current reality:** The latest recorded corpus is 256 records with 141 complete annotations, and `Makefile` still marks `ingest-all` as TODO. Current policy explicitly says the formal Phase 0 scale gate remains unmet, while later phases use the verified local corpus for bounded retrieval, validation, and generation plumbing.

**Impact:** The formal gate remains correct as a final data-foundation goal, but the design lacks an approved interim dataset milestone for demo-readiness and Phase 2 research-only work.

**Recommended review action:** Preserve the 50,000-record gate as the formal Phase 0 gate, but add an interim "bounded local corpus / research-only" milestone with allowed and disallowed downstream claims.

### 5. Section 7.2 / base model selection

**Location:** `SYSTEM_DESIGN.md` lines 554-557.

**Design text/current implication:** DNABERT-2, Nucleotide Transformer, and Evo are named as reasonable starting points, with license checks.

**Current reality:** Later research moved the practical policy to Carbon-first. Carbon-500M is the CPU plumbing spike, Carbon-3B is the approved practical fine-tune target, Evo 2 is deferred as a higher-cost benchmark, and NTv3 is excluded from unqualified commercial-product use because of noncommercial licensing. DNABERT-2 fallback smoke is parked pending dependency approval.

**Impact:** The design points future agents toward an outdated model shortlist and can waste effort on models that current policy has deprioritized or excluded.

**Recommended review action:** Update the model-selection section to record Carbon-500M/Carbon-3B as the current implementation path, Evo 2 as deferred benchmark, and NTv3/DNABERT-2 as gated alternatives.

### 6. Sections 3.3, 7.4, and 7.6 / Phase 2 training and gate policy

**Location:** `SYSTEM_DESIGN.md` lines 181-186 and 568-581.

**Design text/current implication:** Fine-tuning runs on managed GPUs with checkpoints to object storage; the Phase 2 gate is at least 70% valid/component-complete/constraint-passing generations.

**Current reality:** Fine-tuning prep exists, but no actual fine-tune has run. Current policy authorizes one bounded Carbon-3B run up to USD 300 on Lambda Labs or RunPod using the existing public NCBI-derived triplets. Carbon-500M CPU output is explicitly a plumbing spike, not Phase 2 evidence. The model registry exists but `data/models/registry.jsonl` is currently empty.

**Impact:** The design does not distinguish production Phase 2 from the approved narrow fine-tune attempt and may invite unsupported gate claims from smoke or spike artifacts.

**Recommended review action:** Add a Phase 2 "authorized experiment" subsection that names the Carbon-3B budgeted run, required artifacts, and the rule that smoke/spike outputs are not gate-eligible.

### 7. Section 9.5 and API contract / primers and synthesis handoff

**Location:** `SYSTEM_DESIGN.md` lines 205-206, 630-634, and 741-742.

**Design text/current implication:** Phase 4 includes primer-design output and synthesis-order handoff endpoints.

**Current reality:** GenBank/FASTA export codecs and `/v1/designs/{design_id}/export` exist. Primer output and `/v1/designs/{design_id}/order` are intentionally absent. `PROGRESS.md` records primer design, synthesis handoff, and deployed hosting as open Phase 4 gaps.

**Impact:** The API contract reads as if endpoints should already exist once Phase 4 scaffolding is present, but the implementation has deliberately scoped them out of the demo foundation.

**Recommended review action:** Mark primers and synthesis handoff as not implemented in the current Phase 4 foundation and add an explicit acceptance checklist for a future handoff slice.

### 8. Sections 9.7 and 13 / auth, metering, and rate limits

**Location:** `SYSTEM_DESIGN.md` lines 207, 636-638, and 744.

**Design text/current implication:** Standard auth, bearer tokens, per-account usage metering, and tiered rate limits should exist from day one.

**Current reality:** The API has `X-User-ID` demo ownership checks for outcome endpoints and TODOs on core design/export endpoints for bearer auth, rate limits, and usage metering. `PROGRESS.md` confirms these are intentionally omitted from Phase 4.

**Impact:** The design overstates the security/commercial readiness of the current API and frontend.

**Recommended review action:** Split "demo identity" from production AuthN/AuthZ/metering in the design and make auth/metering a named Phase 4 gate blocker, not an assumed baseline.

### 9. Section 10.2 / outcome-capture schema

**Location:** `SYSTEM_DESIGN.md` lines 656-658 and API contract line 743.

**Design text/current implication:** Outcome capture is a 3-question form stored in an `outcomes` table linked to design and model version with explicit training consent.

**Current reality:** Outcome capture is implemented as a richer but still demo-scoped `OutcomeReport` with `construct_validated`, sequencing/expression/functional text fields, `outcome_label`, `training_consent`, and provenance. The Postgres migration lacks several fields recommended by `research/findings/outcome_capture.md` such as `session_id`, `job_id`, schema version, structured evidence JSON, derived label fields, and review status. The frontend keeps "My outcomes" in local browser storage until a backend list endpoint exists.

**Impact:** The design understates the evidence needed for training eligibility, while the implementation is not yet the full outcome-capture model proposed by later research.

**Recommended review action:** Replace the "3-question form" wording with a staged outcome model: minimal demo report now, structured evidence/review schema before training use, and browser-local outcome history as temporary UI behavior.

### 10. Section 10.4 / rollout and promotion policy

**Location:** `SYSTEM_DESIGN.md` lines 667-671.

**Design text/current implication:** Promotion follows shadow to canary to full, gated by offline eval beating the incumbent.

**Current reality:** Later rollout docs define much stricter conditions: registry completeness, license status, biosecurity review status, human approval checkpoints, restricted payload logging, shadow comparison metadata, canary assignment policy, fallback behavior, and rollback rules. Implementation has fake-backed shadow/canary scaffolding and an offline shadow report, but canary is not wired into the live API and production thresholds remain unresolved.

**Impact:** The design is too terse for the safety and governance burden of serving generated plasmids and could allow premature canary/full promotion.

**Recommended review action:** Link Section 10.4 to `research/findings/model_rollout.md`, `shadow_audit.md`, and `canary_design.md`, and make their approval/rollback requirements normative before any online rollout.

### 11. Section 11.6 / biosecurity posture

**Location:** `SYSTEM_DESIGN.md` lines 699-702.

**Design text/current implication:** Maintain a screening step for sequences of concern before auto-fulfillment.

**Current reality:** Biosecurity is researched, and `PROGRESS.md` carries unresolved questions about the controlling U.S. screening framework and whether the platform should act as a regulated-like checkpoint before provider handoff. There is no implemented provider handoff or production screening integration in the current app path.

**Impact:** The design states an important requirement but does not reflect current unresolved regulatory policy or the absence of an implemented screening gate.

**Recommended review action:** Mark biosecurity screening as a hard blocker before synthesis handoff or served generated designs, and reference the pending policy questions in `PROGRESS.md`.

### 12. Section 12 / canonical schemas

**Location:** `SYSTEM_DESIGN.md` lines 713-728.

**Design text/current implication:** The schema section is canonical and illustrative, with `Plasmid.source` limited to `addgene|genbank|literature|generated`, and no outcome schema.

**Current reality:** The implemented schemas add `curated` as a plasmid source, add `vector_profile` to `AnnotatedSequence`, add `source` and `publication_doi` to `DesignSpec`, include `PlasmidRecommendation` and `RetrievalResult`, and define `OutcomeReport`. Later corpus policy also calls for source-lane/license/training-use metadata that is not in the design schema.

**Impact:** Agents using Section 12 as the canonical contract can generate incompatible objects or miss important provenance and feedback fields.

**Recommended review action:** Refresh Section 12 from `packages/core/schemas/models.py` and add planned source/license metadata fields as explicit schema TODOs.

## Non-Drift Notes

- Section 3.4 / 8.3 already reflects the approved Phase 3 curated-quality policy: 31 known-good plus 52 known-bad records are acceptable because gold-set size is now governed by provenance and biological defensibility rather than the earlier 50/50 placeholder.
- Section 9.4 is aligned with the implementation: the frontend uses `seqviz` and renders circular/linear maps from `AnnotatedSequence` features.
- The Phase 1 retrieval gate text remains aligned with current reports: top-5 hit rate exceeded the 80% gate.
