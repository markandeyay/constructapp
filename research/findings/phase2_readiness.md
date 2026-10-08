> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Phase 2 Readiness Assessment

- Assessed: 2026-06-01
- Scope: approved bounded offline spike only. This document does not authorize
  fine-tuning, GPU spend, model promotion, or a Phase 2 gate attempt.
- Repository ownership for this task: this file only.

## Decision Summary

Do not authorize full Phase 2 fine-tuning or a Phase 2 gate attempt yet.

The bounded offline readiness spike is authorized as the Phase 2 entry point.
That spike should prove the `SequenceGenerator` interface, deterministic
retrieval-grounded baselines, open-model loading, and provisional evaluation
wiring. It must not fine-tune a model, produce a promoted model, expose generated
sequences to users, spend GPU budget, or claim that plasmid generation quality
has been demonstrated.

More Phase 0 data work should precede any real fine-tuning attempt. The current
82-record corpus is enough to demonstrate plumbing and template-grounded
candidate flow. It is not enough to train or evaluate a generalizable plasmid
generator.

The approved spike matrix is Carbon-500M first for smoke testing, followed by
Carbon-3B as the practical target. The newly released Carbon family provides
lower-cost Apache-2.0 autoregressive checkpoints with standard Hugging Face
loading. Evo 2 7B remains a credible biological benchmark, but it is deferred
to a later benchmarking session after the plumbing proves out.

Model-card license markings are sufficiently clear to plan an internal
technical evaluation, but they are not a final commercial legal clearance.
Training-data rights remain a separate unresolved gate.

## Established Repository Facts

### Designed Phase 2 Contract

`SYSTEM_DESIGN.md` Section 3.3 and Section 7 require:

1. An open base model loaded behind `SequenceGenerator`.
2. A Phase 0 formatter that produces `(context, template, target)` examples.
3. Managed-GPU fine-tuning with versioned checkpoints in object storage.
4. Inference conditioned on a `DesignSpec` and retrieved templates.
5. Re-annotation of generated sequences by the Phase 0 parser.
6. Evaluation for valid DNA, requested components, feasibility, and novelty.
7. A gate of `>= 70%` valid, component-complete, constraint-passing
   generations for gold-set queries.

The design explicitly says not to train from scratch and to ground generation
in retrieved validated templates. It also requires holdout splitting by
depositing lab or publication to reduce leakage.

### Current Data State

The latest quality report,
`data/eval/quality/2026-05-31-165742-quality-report.md`, reports:

| Measure | Current value |
| --- | ---: |
| Total records | 82 |
| Fully annotated records | 24 |
| Unclassified records | 55 |
| Records missing promoter annotation | 74 |
| Records missing marker annotation | 52 |
| Duplicate clusters | 2 |
| Parse errors | 0 |

`PROGRESS.md` also records no classified lentiviral or CRISPR records in the
current corpus. Phase 0 remains below its formal gate of `>= 50,000`
fully-parsed, component-annotated plasmid records.

The retrieval gate is met:
`data/eval/retrieval/2026-05-31-221057-retrieval-baseline.md` reports `0.700`
top-1 accuracy, `1.000` top-5 accuracy, and `0.825` MRR across the scored cases.
That is enough to preserve retrieval as the grounding path. It does not create
a sequence-generation training set.

### Current Infrastructure State

The repository has local Postgres, Redis, and MinIO services in
`docker-compose.yml`. `.env.example` has placeholders for `DNA_MODEL_NAME`,
`MODEL_ARTIFACT_URI`, and `MLFLOW_TRACKING_URI`.

No generation package, managed-GPU training configuration, registered
sequence-model artifact, or generation gold set is present. `nvidia-smi` was
not available in the current shell, so local GPU capability and VRAM are
unverified. This is an inventory gap, not evidence that no GPU exists.

The Phase 2 quality gate also depends on the Phase 3 constraint engine. Until a
constraint engine or an explicitly provisional substitute exists, the designed
`>= 70%` Phase 2 gate cannot be measured as written.

## Current Primary-Source Update

### Evo 2

Established facts:

- The [official Evo 2 repository](https://github.com/ArcInstitute/evo2) lists
  1B, 7B, 20B, and 40B checkpoints and states that Evo 2 was trained on
  OpenGenome2 across domains of life.
- The official repository is marked Apache-2.0, and the
  [Evo 2 7B model card](https://huggingface.co/arcinstitute/evo2_7b) is marked
  Apache-2.0.
- Evo 2 is now described in a
  [Nature paper](https://www.nature.com/articles/s41586-026-10176-5), rather
  than only a preprint.
- The official repository documents recent NVIDIA GPU requirements for its
  optimized paths. Actual usable hardware and memory for this repository must
  be benchmarked rather than inferred.

Recommendation:

- Keep Evo 2 7B in the comparison matrix as the higher-cost biological
  benchmark for a later session. It is explicitly deferred from the approved
  bounded offline spike.

### Carbon

Established facts:

- Hugging Face released the
  [official Carbon repository](https://github.com/huggingface/carbon) with
  Carbon-500M, Carbon-3B, and Carbon-8B autoregressive DNA/RNA models.
- The repository lists Apache-2.0 for each checkpoint and documents standard
  Hugging Face Transformers and vLLM loading.
- The [Carbon-3B model card](https://huggingface.co/HuggingFaceBio/Carbon-3B)
  and [Carbon-500M model card](https://huggingface.co/HuggingFaceBio/Carbon-500M)
  are marked Apache-2.0.
- Carbon's
  [official fine-tuning instructions](https://github.com/huggingface/carbon/blob/main/finetuning/README.md)
  include a single-GPU Carbon-500M supervised fine-tuning example and LoRA
  examples. They do not establish the memory, latency, or cost profile for this
  repository.
- The provider reports competitive results and substantially faster inference
  relative to Evo 2 7B. Independent plasmid-specific validation is not yet
  established.

Recommendation:

- Use Carbon-500M first to prove loading and bounded offline evaluation.
- Use Carbon-3B as the leading practical model candidate for a retrieval-grounded
  inference spike.
- Treat Carbon-8B as out of scope until Carbon-3B results and compute inventory
  justify expanding the matrix.

### Nucleotide Transformer v3

Established facts:

- The
  [official Nucleotide Transformer repository](https://github.com/instadeepai/nucleotide-transformer)
  now documents NTv3 sequence generation and long-context support.
- Its
  [official license](https://raw.githubusercontent.com/instadeepai/nucleotide-transformer/main/LICENSE.md)
  is CC BY-NC-SA 4.0.

Recommendation:

- Exclude NTv3 from an unqualified commercial-product path. Reconsider only
  after explicit permission or legal approval for the intended use.

### Plasmid-Specific Evidence

Established facts:

- A December 2025 bioRxiv preprint,
  [Generative design and construction of functional plasmids with a DNA language model](https://doi.org/10.64898/2025.12.06.692736),
  reports PlasmidGPT fine-tuning on curated plasmid libraries with
  circular-aware batching. The authors report successful construction and
  replication for 9 of 10 commissioned designs in *E. coli*. This is promising
  but narrow, author-reported preprint evidence.
- A March 2026 bioRxiv preprint,
  [Emergent Biological Realism in RL-Trained DNA Language Models](https://discovery.ucl.ac.uk/id/eprint/10225061/1/2026.03.24.713963v1.full.pdf),
  reports a 150M-parameter plasmid model trained on 15,499 curated plasmid
  sequences with 100 held-out sequences. Its appendix reports material NVIDIA
  L4 GPU usage for supervised training, reinforcement learning, and evaluation.
  This is a useful scale reference, not a minimum requirement for this system.
- A recent preprint,
  [Fundamental limitations of genomic language models on realistic sequence generation tasks](https://pmc.ncbi.nlm.nih.gov/articles/PMC12871140/),
  reports limitations in realistic long-range genomic generation.

Recommendation:

- Preserve retrieval grounding, circular-aware handling, component-plan
  validation, and conservative claims. Do not use free-form full-plasmid
  generation as the MVP definition.

## Licensing Assessment

### Established Facts

- The Evo 2 repository and Evo 2 7B model card are marked Apache-2.0.
- The Carbon repository and Carbon model cards are marked Apache-2.0.
- The [OpenGenome2 dataset card](https://huggingface.co/datasets/arcinstitute/opengenome2)
  and
  [Carbon pretraining corpus card](https://huggingface.co/datasets/HuggingFaceBio/carbon-pretraining-corpus)
  publish license metadata for their released artifacts.
- [NCBI's GenBank page](https://www.ncbi.nlm.nih.gov/genbank/genbank/) says
  there are no NCBI restrictions on GenBank use or distribution, while also
  warning that some submitters may claim patent, copyright, or other
  intellectual-property rights and that NCBI cannot grant unrestricted
  permission.
- Addgene's
  [Developers Portal help page](https://help.addgene.org/hc/en-us/articles/38241923181453-What-is-the-Developers-Portal)
  says API and bulk data access require an intended-use selection and a data
  access license. Addgene's
  [public terms](https://www.addgene.org/terms-of-use/) restrict commercial use
  of site content absent permission.

### Recommendation

Treat Evo 2 and Carbon as provisionally eligible for an internal technical
evaluation after pinning the exact model revision and access route. Do not call
either path commercially cleared until human legal review confirms:

1. The exact checkpoint and serving route.
2. The training-data policy for local GenBank-derived records.
3. The intended Addgene access scope and signed data license before any
   Addgene-derived training use.
4. Whether upstream dataset-card license markings are sufficient for the
   product's commercial risk policy.

Open-weight licensing and training-data clearance are separate decisions.

## Requirements Assessment

### Base Model Choice

| Candidate | Role | Readiness assessment |
| --- | --- | --- |
| Carbon-500M | Smoke test | Best first model-loading and evaluation-wiring target. |
| Carbon-3B | Practical lead | Recommended first retrieval-grounded inference candidate. |
| Evo 2 7B | Higher-cost benchmark | Keep for comparison after hardware inventory. |
| NTv3 | Excluded by default | Technically relevant, but official noncommercial license blocks unqualified commercial use. |

This is a spike ordering recommendation, not a production model selection.
Selection must be revisited after task-specific evaluation.

### Fine-Tuning Data

The 82-record corpus is enough for:

1. A deterministic `FakeGenerator` that returns a retrieved template.
2. A tightly constrained template-edit demonstration with parser
   re-annotation.
3. Open-model loading and inference smoke tests on a small versioned fixture.
4. Building the formatter contract without training a promoted artifact.

The 82-record corpus is not enough for:

1. Leakage-resistant train, validation, and test splits by lab or publication.
2. Fine-tuning with credible claims of generalization.
3. Coverage of supported vector profiles beyond a narrow initial slice.
4. A statistical Phase 2 gate result.

Only 24 records are fully annotated, and annotation gaps are concentrated in
fields that generation evaluation needs. The plasmid-specific preprints above
used curated libraries at materially larger scale. Their dataset sizes are not
direct requirements for this repository, but they reinforce that 82 records
should not be treated as a trainable product corpus.

Recommendation:

- Continue Phase 0 acquisition, provenance, deduplication, and annotation
  before real fine-tuning.
- If a narrow experimental milestone is desired before the formal 50,000-record
  Phase 0 gate, define it explicitly as a research-only dataset milestone. It
  must not bypass the formal Phase 0 gate or support a Phase 2 quality claim.
- Keep initial work limited to bacterial cloning and expression profiles unless
  the expanded corpus justifies a broader profile.

### Compute And Operations

Before a fine-tuning run, record:

1. Available local and managed GPU types, VRAM, compute capability, and quotas.
2. A provider and budget ceiling for smoke tests, inference benchmarks, LoRA,
   and full checkpointing.
3. Checkpoint storage, experiment tracking, artifact naming, and retention.
4. Reproducible model revision, tokenizer revision, training-data snapshot,
   hyperparameters, and evaluation snapshot.
5. Benchmark results for memory, latency, throughput, and approximate cost.

Do not estimate required GPU spend from model size alone. Run a small authorized
benchmark after the provider and budget are approved.

### Evaluation

The final Phase 2 gate must remain the designed `>= 70%` result on gold-set
queries after parser re-annotation and Phase 3 constraint checks.

A pre-Phase-2 spike may use a clearly labeled provisional offline harness:

1. DNA alphabet validity and sane length.
2. Requested-component recovery after parser re-annotation.
3. Circular-origin rotation robustness.
4. Exact-copy, identity, and edit-distance reporting against retrieved templates
   and training records.
5. Provenance and template-edit audit output.
6. Latency, peak memory, and approximate inference cost.
7. Explicit unsupported-profile handling.

The spike fixture proves wiring only. It is not a substitute for a versioned,
profile-balanced generation gold set or the Phase 3 constraint engine.

## Realistic Minimum Viable Deliverable

Under current resources, the minimum viable next deliverable is a separately
authorized offline readiness spike:

1. Implement the `SequenceGenerator` interface and deterministic
   retrieval-template baseline described by the design.
2. Prove the deterministic fake-backed vertical slice end to end.
3. Treat CPU-runnable Carbon-500M loading and inference as a stretch smoke test.
4. Prepare Carbon-3B as the next practical target without spending GPU budget.
5. Defer Evo 2 7B benchmarking to a later explicitly authorized session.
6. Re-annotate all candidates and produce a provisional evaluation report.
7. Prevent model promotion and user-visible sequence delivery.

This would demonstrate that the architecture can carry generated candidates
through validation. It would not demonstrate that fine-tuning is ready or that
generated plasmids are biologically feasible.

## Uncertainties To Preserve

1. The minimum useful fine-tuning corpus size for each supported vector profile
   is unknown. Do not infer it from the cited preprints.
2. Local GPU availability and VRAM are unknown.
3. Managed-GPU provider, quota, and budget are undecided.
4. Carbon's plasmid-specific performance is unknown.
5. Evo 2 7B's task-specific quality and cost relative to Carbon-3B are unknown.
6. Commercial legal clearance for exact model routes and training-data sources
   is pending human review.
7. Addgene access and training rights remain pending the intended-use license.
8. A generation gold set does not yet exist.
9. The Phase 3 constraint-engine dependency is unresolved.

## Human Decisions Recorded On 2026-06-01

1. The bounded offline readiness spike is authorized as the only Phase 2 entry
   point. It is plumbing validation, not credible fine-tuning.
2. The approved spike matrix is Carbon-500M for smoke testing, then Carbon-3B
   as the practical target. Evo 2 7B is deferred to a later benchmark session.
3. No GPU spend is authorized. Any GPU usage requires explicit per-session
   authorization.
4. Phase 3 is not a prerequisite for the spike. Use only an unconditional PASS
   stub during the spike; do not pull Phase 3 implementation forward.
5. Lentiviral and CRISPR seed expansion is deferred while the Addgene
   application is pending. Do not admit reviewed GenBank derivatives without
   explicit human sign-off.
6. The unresolved training-data rights and formal Phase 0 scale-gate questions
   remain open before fine-tuning or a Phase 2 gate attempt.
