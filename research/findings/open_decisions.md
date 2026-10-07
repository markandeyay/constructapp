# Open Decisions Register

Scope: consolidated pending decisions for AUDIT-1 on `demo-readiness`, drawn from `PROGRESS.md` and recent `research/findings/` documents. This file intentionally records decisions still requiring human approval; it does not change policy by itself.

## Phase 2 Spend And Model Training

### P2-1. Authorize the first paid Carbon-3B fine-tuning run

- Decision needed: Whether to proceed with the first paid managed-GPU Carbon-3B LoRA run, and under what exact budget/provider controls.
- Why it matters: Phase 2 remains incomplete without a real fine-tuned generation baseline, but a paid run creates spend, artifact-retention, license, and model-promotion obligations.
- Current evidence/context: `phase2_finetune_run_v1.md` found the training path and the authorized public NCBI-derived `117/15/8` triplet snapshot ready, but stopped before paid provisioning because provider automation was absent. `phase2_provider_selection.md` selects RunPod Pods, preferring A100 80 GB, under the existing USD 300 cap.
- Practical options: Proceed once RunPod or Lambda access is configured and balance/availability can be verified; run only a bounded smoke test first; defer all GPU spend until corpus/provenance policy is stricter; cancel the current snapshot and require a larger corpus before any paid run.

### P2-2. Choose the first trainable model route and exact revision policy

- Decision needed: Confirm Carbon-3B as the first practical target, whether Carbon FNS/base-pair loss is required, and whether the base model/tokenizer revision must be pinned before any run.
- Why it matters: Model revision, tokenizer behavior, loss masking, and adapter method affect reproducibility, sequence validity, cost, and whether later evaluation can be attributed to a stable artifact.
- Current evidence/context: `finetune_config.md` recommends `HuggingFaceBio/Carbon-3B` with LoRA/QLoRA, target-DNA loss masking, exact revision pinning, and Carbon-500M only for smoke tests. Evo 2 7B and Carbon-8B remain deferred.
- Practical options: Use Carbon-3B LoRA/QLoRA with standard 6-mer token loss; require Carbon FNS loss before any serious run; run Carbon-500M smoke only; add Evo 2 7B as a later benchmark after Carbon results; require legal review before pinning any route as commercially usable.

### P2-3. Define what a small Phase 2 run is allowed to claim

- Decision needed: Whether the current small fine-tuning snapshot may support a quality claim, or only a research/plumbing dry run.
- Why it matters: Overstating model quality would corrupt phase-gate accounting and product readiness; understating it may still allow useful infrastructure validation.
- Current evidence/context: `phase2_readiness.md` warned the earlier 82-record corpus was not enough for credible fine-tuning. Current `PROGRESS.md` says Phase 2 has a public NCBI-derived `117/15/8` snapshot authorized for one run, but Phase 2 gate is still not met and there is no biologically validated fine-tuned generator.
- Practical options: Label the run strictly as a research dry run; allow it to establish an offline baseline but not gate eligibility; require a minimum profile-balanced corpus before training; require the formal Phase 0 scale gate before any Phase 2 quality claim.

### P2-4. Set hard abort and artifact-retention requirements for training

- Decision needed: Which abort criteria, checkpoint retention, artifact storage, and dependency gates are mandatory before launch.
- Why it matters: The training run must be reproducible and stoppable before budget or data-policy issues become expensive.
- Current evidence/context: `finetune_config.md` lists abort criteria for unresolved training rights, split leakage, NaN loss, overfit signals, memorization, GPU headroom, budget overrun, and policy flags. `phase2_finetune_run_v1.md` notes GPU-host dependencies such as `peft`, `accelerate`, and `bitsandbytes` must be installed and verified on the provider host.
- Practical options: Require every listed abort criterion before launch; use a reduced smoke-only checklist; require object-storage setup before training; allow local-only artifact download for the first run and register the model only after evaluation.

### P2-5. Decide whether upstream open-weight licenses are sufficient for internal or commercial use

- Decision needed: Whether Apache-2.0 Carbon weights are acceptable for the project now, and whether legal review must approve exact checkpoint and serving route before canary or production.
- Why it matters: Model license and training-data clearance are separate gates; open weights do not automatically clear local data or downstream commercial usage risk.
- Current evidence/context: `phase2_readiness.md` treats Carbon/Evo licenses as provisionally eligible for internal technical evaluation, not final commercial clearance. `finetune_config.md` requires recording model, tokenizer, code, and data revisions.
- Practical options: Approve Carbon for internal evaluation only; approve Carbon for canary after legal review; require legal approval before any paid fine-tune; block all commercial-serving claims until model and data-source policies are signed off.

## Canary Rollout Thresholds

### C-1. Set the offline promotion rule from shadow to canary

- Decision needed: Whether a candidate must be strictly better on every gate metric, or non-inferior on core metrics with improvement on at least one metric.
- Why it matters: The rule controls how conservative model exposure is and whether small, noisy datasets can ever promote a useful candidate.
- Current evidence/context: `model_rollout.md` requires no material regression in strict generation success, component completeness, Phase 3 pass rate, novelty, latency, timeout rate, or error rate. It explicitly leaves the minimum delta unresolved.
- Practical options: Require strict improvement on every metric; allow non-inferiority on core safety/validity metrics plus one meaningful improvement; require statistical confidence intervals; use human review for early low-sample candidates.

### C-2. Approve initial canary traffic, sample size, and expansion schedule

- Decision needed: Initial traffic percentage, minimum eligible requests, business-cycle duration, and expansion steps.
- Why it matters: Canary size sets blast radius and determines whether observed metrics are actionable.
- Current evidence/context: `model_rollout.md` proposes `1%` of eligible generation requests for at least one business cycle or `100` eligible requests, then `1% -> 5% -> 25% -> 50% -> 100%`. `canary_design.md` says production thresholds still require human approval.
- Practical options: Adopt the proposed schedule; start below 1% for internal tenants only; require larger samples before expansion; stop at shadow-only until outcome feedback exists.

### C-3. Define metric rollback thresholds

- Decision needed: Exact rollback thresholds for strict success, Phase 3 pass rate, component completeness, copy rate, latency, timeout rate, error rate, fallback rate, and support/escalation signals.
- Why it matters: Without predeclared thresholds, rollback becomes subjective after the candidate is already user-visible.
- Current evidence/context: `model_rollout.md` proposes holding if strict generation success is more than 5% relative below incumbent or Phase 3 pass rate is more than 2% absolute below incumbent, but marks these as conservative defaults needing approval.
- Practical options: Use the proposed 5%/2% thresholds; require zero tolerance for any safety or blocking validation miss; set profile-specific thresholds; use one threshold set for canary and stricter thresholds for full promotion.

### C-4. Decide whether warning-class Phase 3 findings may be served during canary

- Decision needed: Which WARN findings, if any, are acceptable in user-visible canary output.
- Why it matters: WARN semantics determine whether canary can measure realistic outputs or only perfectly clean designs; they also affect synthesis-readiness claims.
- Current evidence/context: `generation_eval.md` treats `ValidationReport.overall == PASS` as the conservative Phase 2 gate interpretation. `model_rollout.md` says severe validation failures must not be served and warning tolerance needs human approval.
- Practical options: Serve PASS only; allow selected WARN classes with clear UI labeling; allow WARN internally but block export/synthesis; require human review before serving any WARN during first canary.

### C-5. Choose canary assignment identity and consent policy

- Decision needed: Whether first canary assignment is sticky by design session, user, tenant, or request, and whether explicit user/tenant consent is required.
- Why it matters: Assignment affects user experience, outcome attribution, fairness, and whether users knowingly receive candidate model output.
- Current evidence/context: `canary_design.md` recommends sticky-by-session assignment, falling back to pseudonymous user, tenant, then request id. It leaves explicit consent and eligible tenant/request classes open.
- Practical options: Sticky by design session with internal approval only; sticky by tenant with tenant opt-in; user-level explicit consent for all first canaries; internal-only canaries until the model is promoted.

### C-6. Decide shadow behavior during canary and payload retention

- Decision needed: Whether candidate-assigned canary requests also run incumbent shadow comparison, and what retention/access policy applies to restricted sequence payloads.
- Why it matters: Dual execution improves comparison but raises cost, latency, and sensitive payload-retention risk.
- Current evidence/context: `shadow_audit.md` says current shadow records are improved for offline eval but production restricted payload storage and retention remain deferred. `model_rollout.md` requires restricted candidate payload policy before promotion decisions.
- Practical options: Continue incumbent shadow for all canary-assigned requests; shadow only sampled canary requests; run only served candidate plus fallback; store only hashes/summaries; store restricted payloads with short retention and reviewer-only access.

### C-7. Decide whether simultaneous canaries are allowed

- Decision needed: Whether one-candidate canary remains a hard rule or multi-arm experiments can run.
- Why it matters: Multiple canaries complicate attribution, rollback, and wet-lab outcome linkage.
- Current evidence/context: `canary_design.md` recommends only one active candidate unless a future human-approved multi-arm experiment changes the rule.
- Practical options: One active candidate only; allow multi-arm internal experiments only; allow multi-arm tenant-opt-in experiments with separate assignment salts and independent rollback thresholds.

## Outcome And UX Choices

### O-1. Decide one outcome per design or multiple outcome rows

- Decision needed: Whether user-facing views and storage allow multiple outcomes for multiple clones/samples, or keep only latest outcome per design.
- Why it matters: Multiple clones are biologically realistic, but they complicate UI, training labels, and lineage. Latest-only is simpler but can discard contradictory evidence.
- Current evidence/context: `outcome_capture.md` proposes an append-friendly `outcomes` table and asks whether `(design_id)` should be unique. `PROGRESS.md` notes the current outcome UI uses local browser storage for the "My outcomes" list until a backend list endpoint exists.
- Practical options: One latest outcome per design for MVP; multiple outcomes with clone/sample IDs; append-only revisions with one displayed summary; multiple rows in backend but latest-only in initial frontend.

### O-2. Choose first outcome prompt wording

- Decision needed: Whether the required first question should ask "Was this design built or tested?" rather than "Did your construct validate?"
- Why it matters: Prompt wording can reduce self-reporting bias and distinguish not-built from failed designs, which should not become negative training signal.
- Current evidence/context: `outcome_training_signal.md` excludes `not_built` from training and requires clear labels. `PROGRESS.md` asks whether outcome labels/training eligibility should be hidden to avoid answer-shaping.
- Practical options: Start with built/tested status, then ask validation details; ask validation first but include explicit not-built; hide training labels from users; show only plain-language outcome categories.

### O-3. Define minimum sequencing evidence for a positive label

- Decision needed: What counts as `sequence_validated`: full-plasmid NGS consensus, full Sanger tiling, insert plus junctions, or profile-specific critical regions.
- Why it matters: Positive training examples must be reliable enough to teach the model; too strict a rule reduces usable data, while too loose a rule admits false positives.
- Current evidence/context: `outcome_capture.md` requires sequencing evidence compatible with the intended construct for positives. `outcome_training_signal.md` recommends no positive triplet without sequence confirmation in the first implementation.
- Practical options: Require full-plasmid consensus; require insert plus junctions for simple cloning; define profile-specific critical regions; allow partial matches only after human review.

### O-4. Decide how restriction digest evidence affects training labels

- Decision needed: Whether successful restriction digest without sequencing can create a positive training signal, or only a lower-confidence reviewed signal.
- Why it matters: Digest evidence is common and useful, but it can miss sequence-level defects.
- Current evidence/context: `outcome_capture.md` treats restriction digest as first-class evidence but positive labels still require sequencing-compatible evidence. `PROGRESS.md` asks whether digest alone can ever be positive.
- Practical options: Never positive without sequencing; allow digest-only positives after human review for low-risk profiles; use digest-only as product telemetry; use digest-only only for negative/assembly failure signals.

### O-5. Define assay-specific functional success thresholds

- Decision needed: Thresholds for `meets_expected_function` across fluorescence, luminescence, western blot, qPCR, growth selection, phenotype assays, and other readouts.
- Why it matters: Functional labels determine whether a sequence-correct construct is considered successful and whether failure is attributable to design.
- Current evidence/context: `outcome_capture.md` lists structured assay fields but leaves thresholds open. `outcome_training_signal.md` warns that expression/function failures without controls should not become first-pass negatives.
- Practical options: Require user-stated threshold plus controls; define assay-specific numeric defaults; require human review for functional labels; separate `sequence_validated` from `function_validated` and train initially only on sequence positives.

### O-6. Set controls required for negative labels

- Decision needed: When expression fails with a sequence-correct construct, what controls are required before treating the design as a negative instead of assay/protocol failure.
- Why it matters: Wet-lab failures are noisy; weak controls can teach the model to avoid good designs for the wrong reason.
- Current evidence/context: `outcome_training_signal.md` excludes expression failures with absent or weak controls from first-pass negative training. `outcome_capture.md` includes control fields and known protocol deviation fields.
- Practical options: Require positive and negative controls plus replicate count; require human review for all functional negatives; accept user-reported controls for internal metrics only; exclude sequence-correct functional failures from training until more evidence accumulates.

### O-7. Decide uploaded evidence retention and training-derived feature extraction

- Decision needed: Whether chromatograms, gel images, plate-reader files, blot images, and other artifacts may be retained for training-derived feature extraction, or only for human audit.
- Why it matters: Evidence files may contain sensitive data; retaining them expands privacy, security, and consent obligations.
- Current evidence/context: `outcome_capture.md` stores artifacts as restricted URIs and requires consent scope. `outcome_training_signal.md` requires provenance and restricted payload policy before training snapshots.
- Practical options: Human-audit retention only; training feature extraction only with explicit artifact consent; retain hashes/metadata but delete raw files after review; tenant-configurable retention.

### O-8. Define consent text and withdrawal behavior

- Decision needed: Exact consent copy, consent versioning, and what happens when consent is withdrawn after an outcome has entered a released training snapshot.
- Why it matters: Phase 5 training depends on explicit consent, and withdrawal policy affects future snapshots, model retirement, and possible unlearning obligations.
- Current evidence/context: `outcome_capture.md` requires `consent_for_training`, consent version, consent timestamps, and withdrawal fields. `outcome_training_signal.md` asks whether withdrawal means future exclusion only, model retirement, or best-effort unlearning.
- Practical options: Future exclusion only; exclude from future snapshots and mark affected model versions; retire models trained on withdrawn records above a threshold; define best-effort unlearning for enterprise/private data only.

## Corpus And Data Provenance

### D-1. Decide whether broad natural plasmids can enter generation training

- Decision needed: Whether broad natural RefSeq/GenBank plasmids may be used for generation pretraining, restricted to retrieval/evaluation, or excluded from training artifacts.
- Why it matters: Broad plasmid data can increase scale but may reduce engineered-vector relevance and include sensitive classes such as antimicrobial-resistance plasmids.
- Current evidence/context: `corpus_expansion_phase2.md` estimates about 38k complete RefSeq plasmid-title records and about 55k broad GenBank plasmid-title records. It recommends keeping broad RefSeq separate from engineered-vector lanes.
- Practical options: Use broad RefSeq/GenBank for pretraining only; use only engineered-vector lanes for supervised generation; allow broad records for representation/evaluation but not generation targets; filter/downweight sensitive natural plasmid classes.

### D-2. Decide whether NCBI records are training-eligible by default

- Decision needed: Whether NCBI GenBank/RefSeq records can be treated as training-eligible while preserving submitter-IP caveats, or whether commercial training requires a legal-reviewed allowlist.
- Why it matters: This decision controls the largest available public corpus and determines whether Phase 0 scale work can proceed without source-by-source legal review.
- Current evidence/context: `corpus_expansion_phase2.md` notes NCBI places no restrictions on GenBank distribution but warns that submitters may claim IP rights and NCBI cannot grant unrestricted permission.
- Practical options: Train on NCBI records by default with provenance fields; allow internal evaluation only; require legal-reviewed allowlist for commercial model training; separate open-source/internal and commercial training snapshots.

### D-3. Decide non-NCBI source eligibility

- Decision needed: Whether SEVA, iGEM Registry, DNASU, SGD-derived context, and Addgene direct downloads remain excluded until explicit training/commercial-use terms are approved.
- Why it matters: These sources may improve engineered-vector coverage but have distinct access, MTA, commercial-use, or training-rights constraints.
- Current evidence/context: `corpus_expansion_phase2.md` recommends excluding iGEM, Addgene direct downloads, and DNASU until terms are confirmed; treating SEVA as review-required for commercial training; and using SGD mainly as context, not primary sequence source. `PROGRESS.md` says Addgene partner access remains pending.
- Practical options: Keep all non-NCBI sources excluded; admit SEVA/SGD only after legal review; use Addgene only under an approved Developers Portal/license scope; create separate non-trainable retrieval/display lanes.

### D-4. Decide the lentiviral and CRISPR seed strategy

- Decision needed: Whether to wait for Addgene intended-use data license, admit reviewed GenBank derivatives, or remain without lentiviral/CRISPR profiles for now.
- Why it matters: Profile coverage affects retrieval, validation, generation gold sets, and whether product claims can include these vector types.
- Current evidence/context: `PROGRESS.md` records no classified lentiviral or CRISPR vectors in the expanded corpus and says reviewed derivatives need explicit provenance/legal sign-off. `lenti_crispr_resolution.md` is listed among findings for this gap.
- Practical options: Keep profiles unsupported until Addgene terms resolve; admit a tiny reviewed NCBI/manufacturer-only calibration set; use GenBank derivatives only for parser calibration, not training; deprioritize these profiles from MVP.

### D-5. Approve canonical element variants for the reference library

- Decision needed: Which variants to approve for ambiguous elements such as EF1a, SV40 early, U6, tac, trc, araBAD, SV40/BGH/rabbit beta-globin polyA, rrnB T1/T2, lambda T0, ZeoR, BSD, HygR, NeoR/G418, f1 origin, and 2-micron origin.
- Why it matters: Parser completeness, validation, and generation evaluation depend on a trusted reference library; guessing variants can create false evidence.
- Current evidence/context: `PROGRESS.md` records several reference-library expansions and deferrals for ambiguous elements. Earlier decisions kept pACYC184 incomplete rather than importing uncertain CAT sequence.
- Practical options: Approve only exact NCBI/manufacturer-backed variants; create a human-reviewed ambiguous-variant queue; allow low-confidence parser hints separate from training evidence; wait for Addgene/manufacturer rights where needed.

### D-6. Decide source-lane metadata required before more ingestion

- Decision needed: Whether `source_lane`, `license_status`, `terms_ref`, `training_use_allowed`, `commercial_use_allowed`, and `review_required` are mandatory before mixing sources.
- Why it matters: Without lane metadata, broad RefSeq, engineered GenBank, Addgene, SEVA, and user outcomes can be accidentally mixed in training or evaluation.
- Current evidence/context: `corpus_expansion_phase2.md` explicitly recommends these fields before mixing records from different sources. `training_data_format.md` and Phase 5 findings require provenance retention in snapshots.
- Practical options: Make lane metadata mandatory now; add metadata only to new records and backfill later; maintain separate manifests per source without schema changes; block new non-NCBI ingestion until metadata exists.

### D-7. Decide pACYC184 and chloramphenicol retrieval-gold handling

- Decision needed: Whether the low-copy chloramphenicol retrieval gold case should keep only `pACYC184`, admit newly added GenBank chloramphenicol vectors, or add copy-number/origin-aware retrieval before changing the gold set.
- Why it matters: Retrieval evaluation can be skewed if a gold case admits biologically different chloramphenicol vectors without copy-number/origin distinctions.
- Current evidence/context: `PROGRESS.md` says the expanded-corpus `pACYC184` retrieval regression is fixed and records an earlier human decision that pACYC184 remains incomplete until an exact CAT CDS source is approved.
- Practical options: Keep only `pACYC184` as gold; expand acceptable answers after origin/copy-number filters exist; add separate gold cases for new vectors; treat this as a retrieval policy test rather than parser completeness.

## Validation, Synthesis, And Policy

### V-1. Choose the default synthesis-provider profile

- Decision needed: Which profile is default for "synthesis-ready" when no provider is selected: conservative cross-provider, Twist, IDT, GenScript, or user-selected only.
- Why it matters: Provider profile changes GC, repeat, homopolymer, and synthesis-readiness thresholds, and therefore changes what can be exported as synthesis-ready.
- Current evidence/context: `validation_repeats.md` defines `conservative_default`, `twist_default`, `idt_gblocks`, and `genscript_default`. `PROGRESS.md` asks which default should apply.
- Practical options: Use conservative cross-provider by default; require user/provider selection; default to the cheapest/common provider only after product decision; run all major provider profiles and show the strictest result.

### V-2. Decide codon usage scoring versus automatic rewrite

- Decision needed: Whether MVP only scores codon usage, or may automatically rewrite coding sequences after explicit user consent.
- Why it matters: Automatic rewriting changes biological sequence, IP/provenance, validation burden, and user trust.
- Current evidence/context: `PROGRESS.md` keeps this as an open human decision. Existing validation findings focus on deterministic checks and do not authorize automatic sequence edits.
- Practical options: Score-only MVP; rewrite only after explicit user confirmation; rewrite only coding regions with preserved protein sequence and audit diff; defer rewriting to a later editor workflow.

### V-3. Define WARN/PASS semantics for formal gates and user-visible output

- Decision needed: Whether WARN counts as pass for Phase 2 generation evaluation, API success, canary serving, export, or synthesis handoff.
- Why it matters: The same validation report can be a research metric, a UI warning, or a hard product block depending on policy.
- Current evidence/context: `generation_eval.md` treats WARN as not passing the formal Phase 2 constraint metric unless humans change the gate. `api_robustness.md` says validation FAIL currently returns as a successful job without enough API guidance.
- Practical options: PASS-only for gates and synthesis; PASS/WARN for user-visible draft but block export on FAIL; profile-specific WARN allowances; require human review for WARN in first canary.

### V-4. Decide how expected biological repeats are handled

- Decision needed: Whether repeat/instability validation should ignore, downgrade, or still block biologically expected repeats in natural plasmids, lentiviral LTRs, AAV ITRs, and similar contexts.
- Why it matters: Some functional vectors require repeats that synthesis providers and bacteria may find difficult; blocking them may exclude important profiles, but ignoring them weakens synthesis readiness.
- Current evidence/context: `validation_repeats.md` recommends WARN, not FAIL, for required AAV ITRs or lentiviral/retroviral LTRs when annotation supports the vector context, with propagation/synthesis caveats.
- Practical options: Downgrade required repeats to WARN; block all provider-hard-threshold repeats for synthesis-ready output; show profile-specific caveats and require provider review; exclude repeat-heavy profiles from MVP.

### V-5. Decide biosecurity checkpoint scope and controlling framework

- Decision needed: Whether the platform operates as a regulated-like biosecurity checkpoint before provider handoff, and what current U.S. nucleic-acid screening framework controls after the May 5, 2025 Executive Order directive.
- Why it matters: The decision affects product obligations, validation policy, user messaging, audit logging, and whether the platform blocks or merely warns before synthesis handoff.
- Current evidence/context: `PROGRESS.md` flags this as unresolved. `model_rollout.md` and `outcome_training_signal.md` both require biosecurity review status before canary/promotion/training use.
- Practical options: Treat Construct as an internal pre-screening checkpoint with conservative blocks; defer legally mandated screening to synthesis providers but keep audit warnings; require external policy/legal review before synthesis handoff; disable provider handoff until the framework is clarified.

### V-6. Decide canonical base 1 for circular plasmids

- Decision needed: Where canonical base 1 should be placed in generated circular designs: source record origin, ORI start, MCS/cloning site, or synthesis-provider convention.
- Why it matters: Base-1 convention affects sequence diffs, circular novelty checks, exports, user maps, and reproducible training examples.
- Current evidence/context: `generation_eval.md` requires circular-aware exact-copy detection. `PROGRESS.md` lists circular base-1 policy as unresolved.
- Practical options: Preserve source record origin; rotate to primary ORI start; rotate to MCS/design insert boundary; keep internal canonical hash circular-aware and export according to provider/user convention.

### V-7. Choose first supported validity profiles

- Decision needed: Which vector types are in the first supported validity profile set: generic mammalian expression, lentiviral, AAV, bacterial expression, CRISPR/shRNA, or another subset.
- Why it matters: Supported profiles determine validation rules, generation gold sets, UI claims, and corpus acquisition priorities.
- Current evidence/context: `PROGRESS.md` notes no classified lentiviral or CRISPR records, while current parser/eval support is stronger for bacterial cloning/expression, yeast shuttle, and some mammalian reporter/expression cases.
- Practical options: Start with bacterial cloning/expression plus yeast shuttle; include mammalian reporter/expression only; exclude lentiviral/AAV/CRISPR until seeds and validation rules exist; create unsupported-profile clarification flows.

## Product, API, And Frontend Scope

### PF-1. Decide validation failure semantics in API and frontend

- Decision needed: Whether a design with `validation_report.overall == FAIL` is a successful job with blocking warnings, a failed job, or a distinct blocked-design state.
- Why it matters: The frontend currently can imply success for invalid designs; API clients need stable semantics for retry, export, and user messaging.
- Current evidence/context: `api_robustness.md` finds validation FAIL designs are returned as normal successful jobs and frontend summary ignores validation status. `PROGRESS.md` says Phase 4 still omits full production hardening.
- Practical options: Successful job with `validation_blocking=true`; terminal `blocked` job status; failed job with structured validation details; draft-only result that cannot export or submit to synthesis.

### PF-2. Make clarification a first-class state

- Decision needed: Whether clarification-needed outcomes use a successful result, a new terminal status like `needs_clarification`, or an HTTP/job error code.
- Why it matters: Treating clarification as failure breaks refinement loops and makes repeated clarification/non-English prompts hard to handle.
- Current evidence/context: `api_robustness.md` finds clarification currently becomes a raw failed job string in the generation spike, while the frontend can render clarification only if the result shape carries it.
- Practical options: Add `needs_clarification` job status; return succeeded result with `clarification_question`; model clarification as a turn type in session state; reject low-confidence/non-English prompts early with structured errors.

### PF-3. Define structured API error envelope and safe error detail policy

- Decision needed: Error envelope fields, retryability, correlation IDs, field errors, and which provider/model/export failure details are safe to show users.
- Why it matters: Frontend-renderable heavy-tier behavior requires stable errors; raw exception strings risk leaking internals and are hard to act on.
- Current evidence/context: `api_robustness.md` finds API errors are plain strings/default FastAPI envelopes and async job failures store raw exception text.
- Practical options: Implement one envelope for HTTP and job errors; sanitize model/provider messages but log internal details; expose precise export causes only to trusted users; use generic `export_failed` and `model_failed` messages in public UI.

### PF-4. Choose auth and ownership model

- Decision needed: Whether authenticated resources are user-owned, organization-owned, or project/workspace-owned once auth is in scope.
- Why it matters: Ownership controls session visibility, outcome prompts, canary consent, billing, retention, and training eligibility.
- Current evidence/context: `PROGRESS.md` says Phase 4 intentionally omits AuthN/AuthZ and the outcome UI uses a temporary `web-demo-user` local/demo `X-User-ID`.
- Practical options: User-owned MVP; organization-owned with project membership; workspace/project-owned resources; keep demo-only identity until production scope is approved.

### PF-5. Define retention policy for sessions, turns, jobs, designs, and generated artifacts

- Decision needed: How long to retain sessions, turns, jobs, generated designs, exports, validation reports, outcome records, restricted sequence payloads, and uploaded evidence.
- Why it matters: Retention affects privacy, audit, reproducibility, model training, and user trust.
- Current evidence/context: `outcome_capture.md` and `model_rollout.md` both require provenance and restricted payload policies. `PROGRESS.md` lists general retention policy as unresolved.
- Practical options: Short retention for raw payloads with hash/provenance retention; retain all design artifacts until user deletion; tenant-configurable retention; immutable retention for records included in training snapshots with separate consent-withdrawal handling.

### PF-6. Decide long-running job UX: polling only, SSE, or WebSocket

- Decision needed: Whether MVP remains polling-only or adds server-sent events/WebSocket streaming and progress updates.
- Why it matters: Heavy-tier model jobs can outlast frontend timeouts, and users need resumable status rather than false failure.
- Current evidence/context: `api_robustness.md` finds frontend polling times out after 30 seconds while API lacks stale/running semantics, timestamps, retry-after, or progress.
- Practical options: Keep polling but add timestamps/retry-after/resume; add SSE for job progress; add WebSocket only after product need; use polling MVP and background notifications later.

### PF-7. Choose authoritative persistence shape for job results and designs

- Decision needed: Whether persisted job results stay JSON snapshots, are normalized into design/turn tables, or use both with one authoritative source.
- Why it matters: This affects export, outcome linkage, auditability, migrations, and frontend history.
- Current evidence/context: `outcome_capture.md` notes current generated designs are stored as `designs.result`/`AnnotatedSequence`, and proposes outcomes linked to `designs.id`. `PROGRESS.md` asks whether JSON snapshots or normalized tables should be authoritative.
- Practical options: Keep JSON snapshots authoritative for MVP; normalize designs/features/outcomes now; use normalized core tables plus immutable JSON snapshots for replay; defer schema expansion until auth/ownership is settled.

### PF-8. Decide map and editor scope

- Decision needed: Whether the MVP plasmid map is read-only, or browser-side feature/sequence editing is in scope.
- Why it matters: Editing adds complex validation, provenance, consent, export, and training-lineage rules.
- Current evidence/context: `PROGRESS.md` lists read-only versus browser-side editing as unresolved. Phase 4 currently focuses on outcome submission UI and local outcome history rather than editing.
- Practical options: Read-only map and export only; allow feature annotation edits but not sequence edits; allow sequence edits as a separate derived design with full revalidation; defer editing until canonical base-1 and provenance policies are settled.

### PF-9. Decide backend design ID and outcome-history scope

- Decision needed: Whether the backend must guarantee persisted `design_id` for all real export jobs and provide a backend outcome history/list endpoint before broader demo or MVP use.
- Why it matters: Outcome capture, training signals, and user history require stable backend linkage; local browser storage is insufficient for reproducible Phase 5 data.
- Current evidence/context: `PROGRESS.md` says Phase 4 still omits a backend-persisted `design_id` guarantee for real export jobs, and `phase4-outcome-ui` uses local storage for the "My outcomes" list until a backend list endpoint exists.
- Practical options: Require backend design IDs before any real outcome collection; keep local outcome UI demo-only; add backend list endpoint now; delay outcome UX expansion until auth/ownership exists.
