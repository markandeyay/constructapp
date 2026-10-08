> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Phase 2 Fine-Tuning Configuration Spec

- Prepared: 2026-06-06
- Scope: configuration design for a future explicitly authorized GPU run only.
- Session constraint: no GPU use, no model download, no fine-tuning, no training dry run, no paid compute, and no model promotion were performed in this session.
- Related repo-local records: `research/findings/phase2_readiness.md`, `research/findings/sequence_models.md`, `research/findings/training_data_format.md`, `research/findings/phase2_spike_spec.md`.

## Recommendation

Use `HuggingFaceBio/Carbon-3B` as the Phase 2 practical fine-tuning target, after retaining `HuggingFaceBio/Carbon-500M` for optional loading and training-pipeline smoke tests.

This recommendation remains consistent with the repository readiness docs and current public Carbon documentation. Carbon-3B is Apache-2.0, decoder-only/autoregressive, 3B parameters, compatible with standard Hugging Face causal-LM loading, supports DNA generation through the Carbon hybrid tokenizer, has native 32,768-token context and YaRN extension to 65,536 tokens, and is documented by the provider as competitive with Evo2-7B while being substantially faster to run. The main caveats remain unchanged: Carbon is not plasmid-specific, its pretraining is primarily eukaryotic with a smaller prokaryotic component, and task-specific quality must be established by future authorized evaluation rather than assumed from the model card.

Do not switch the first practical fine-tuning target to Carbon-8B or Evo 2 7B yet. Carbon-8B increases compute before Carbon-3B has been tested on this project. Evo 2 7B remains a useful higher-cost benchmark, but current repo decisions explicitly defer it until the Carbon path and compute inventory are proven.

## Base Model

Recommended base:

```yaml
base_model: HuggingFaceBio/Carbon-3B
base_model_revision: pin exact commit before any authorized run
tokenizer: HuggingFaceBio/Carbon-3B
tokenizer_revision: same pinned commit as base_model unless intentionally separated
model_class: AutoModelForCausalLM
tokenizer_loader: AutoTokenizer.from_pretrained(..., trust_remote_code=True)
model_loader: AutoModelForCausalLM.from_pretrained(..., torch_dtype=torch.bfloat16)
training_script_start_point: carbon/finetuning/finetune_sft.py or a project-local equivalent using FNSTrainer semantics
```

Input formatting requirements:

- Wrap every DNA span in `<dna>...</dna>` so the Carbon tokenizer uses 6-mer DNA mode.
- Normalize sequences to uppercase `A`, `C`, `G`, `T` only before tokenization.
- Prefer target lengths divisible by 6 for standard 6-mer-token loss; if exact base-pair lengths are required, evaluate the Carbon `fns` revision/FNS trainer path.
- Keep structured triplet JSONL as the canonical data source and derive model text just-in-time.

## Training Data Input And Snapshot Assumptions

Future authorized training must consume only a frozen formatter snapshot produced from the Phase 2 triplet formatter contract:

```text
data/training/phase2/<snapshot_id>/triplets.train.jsonl
data/training/phase2/<snapshot_id>/triplets.validation.jsonl
data/training/phase2/<snapshot_id>/triplets.test.jsonl
data/training/phase2/<snapshot_id>/manifest.json
data/training/phase2/<snapshot_id>/stats.md
data/training/phase2/<snapshot_id>/stats.json
```

Snapshot prerequisites before a real run:

- Exact Phase 0 corpus snapshot ID recorded.
- Formatter version recorded.
- Source/license policy recorded; unresolved Addgene or other non-training-cleared sources excluded.
- Split assignment completed before template retrieval, grouped by depositing lab/publication/accession/exact-sequence/near-duplicate component where available.
- Cross-split exact duplicate count is zero.
- Validation and test splits are frozen and not used for training-time template retrieval.
- Training examples contain full normalized target sequence plus context/template structure, but model input may mask loss outside the target DNA span.
- Current repo-local readiness docs say the earlier 82-record corpus, and later noted spike-scale corpus, are not sufficient for credible product fine-tuning or a Phase 2 gate. If the future snapshot remains small, the run must be labeled a research dry-run or plumbing run, not a quality claim.

Recommended model text rendering for first SFT pass:

```text
<context>
{context.text}
</context>
<template id="{template.plasmid_id}">
<dna>{template.sequence}</dna>
</template>
<target>
<dna>{target.sequence}</dna>
</target>
```

Recommended loss mask:

- Compute supervised causal-LM loss only on the target DNA block for first-pass adapter training.
- Keep context and template tokens as conditioning prefix with labels set to `-100`.
- Record whether FNS base-pair-level loss or standard token-level causal loss was used.

## Recommended Hyperparameters

First authorized Carbon-3B training should be parameter-efficient, not a full fine-tune. Use LoRA or QLoRA depending on confirmed GPU memory. Full fine-tuning should remain out of scope until adapter runs demonstrate value and the managed-GPU budget is approved.

Primary path, QLoRA/LoRA SFT:

```yaml
method: qlora_if_memory_constrained_else_lora
precision: bf16_compute
quantization: 4bit_nf4_for_qlora_only
load_in_4bit: true_for_qlora_only
lora_task_type: CAUSAL_LM
lora_target_modules: all-linear
lora_r: 16
lora_alpha: 32
lora_dropout: 0.05
lora_bias: none
learning_rate: 2.0e-4
lr_sweep_if_authorized: [1.0e-4, 2.0e-4, 3.0e-4]
optimizer: paged_adamw_8bit_for_qlora_else_adamw_torch
weight_decay: 0.01
max_grad_norm: 1.0
scheduler: cosine
warmup_ratio: 0.03
per_device_train_batch_size: 1
per_device_eval_batch_size: 1
gradient_accumulation_steps: 16
effective_batch_size_formula: per_device_train_batch_size * gradient_accumulation_steps * data_parallel_world_size
num_train_epochs: 3
max_steps: null_unless_dataset_is_large_or_budget_limited
max_length: start_with_8192_tokens_then_raise_after_memory_benchmark
gradient_checkpointing: true
use_cache_during_training: false
packing: false_for_first_pass_to_preserve_example_boundaries
seed: 20260606
data_seed: 20260607
```

Conservative alternative if using official Carbon FNS SFT directly without PEFT:

```yaml
method: carbon_fns_sft_smoke_only_until_memory_verified
model: HuggingFaceBio/Carbon-3B
add_dna_tag: true
dna_loss_only: true
precision: bf16
learning_rate: 2.0e-5
optimizer: adamw_torch
weight_decay: 0.01
scheduler: cosine
warmup_ratio: 0.03
per_device_train_batch_size: 1
gradient_accumulation_steps: 16
max_steps_for_smoke: 10
full_run_status: blocked_pending_gpu_memory_and_budget_review
```

Do not use full fine-tuning as the first practical Phase 2 run. Carbon's own long-context/pretraining recipe used large H100-scale resources; this project has no approved provider, budget, or GPU inventory. PEFT adapters reduce trainable parameters and artifact size while preserving the base model for reproducible comparison.

## Eval Cadence

For a future authorized adapter run:

```yaml
evaluation_strategy: steps
eval_steps: 100_or_0.1_epoch_whichever_is_smaller
logging_steps: 10
save_steps: same_as_eval_steps
do_eval_before_training: true
eval_splits: [validation]
final_eval_splits: [validation, test]
metric_for_best_model: eval_loss
greater_is_better: false
load_best_model_at_end: true
```

Evaluation outputs must include:

- Validation loss/perplexity or FNS loss.
- DNA alphabet validity on generated samples.
- Requested-component recovery after parser re-annotation.
- Exact-copy and nearest-neighbor similarity against training records and retrieved templates.
- Circular-rotation-aware duplicate checks.
- Phase 3 constraint-engine result only when the approved Phase 3 implementation and gate data are available; do not use provisional validation as a production gate.
- Unsupported-profile counts and skip reasons.

Use a tiny fixed generation sample at each eval point only if it can run inside the authorized training budget. Cap sample generation aggressively because training eval should not become an unbounded inference benchmark.

## Checkpoint Strategy

```yaml
save_strategy: steps
save_steps: same_as_eval_steps
save_total_limit: 3
checkpoint_contents:
  - adapter weights only for LoRA/QLoRA
  - tokenizer files or tokenizer revision reference
  - training args
  - trainer state
  - rng state
  - manifest pointers
  - git commit and dirty-status record
best_checkpoint: lowest validation loss subject to no abort criteria
final_checkpoint: save final adapter separately from best adapter
retention: keep best, final, and latest resumable checkpoint
```

Do not merge LoRA adapters into the base model during training. If a later deployment experiment needs merged weights, create a separate derived artifact with provenance pointing to the immutable adapter and base revision.

## Reproducibility Seeds

Use fixed seeds and record all of them in the run manifest:

```yaml
python_seed: 20260606
numpy_seed: 20260606
torch_seed: 20260606
torch_cuda_seed: 20260606
transformers_seed: 20260606
data_seed: 20260607
split_seed: snapshot_id_derived_in_formatter_manifest
generation_eval_seed: 20260608
```

Also record:

- Base model commit SHA.
- Tokenizer commit SHA.
- Carbon code or script commit SHA if using official scripts.
- Project git commit and dirty status.
- Python, PyTorch, Transformers, PEFT, bitsandbytes, accelerate, CUDA, driver, and GPU model versions.
- Exact command line and environment variables excluding secrets.

## Artifact Layout

Recommended future artifact root:

```text
artifacts/phase2/finetune/<run_id>/
  config/finetune_config.yaml
  config/accelerate_config.yaml
  manifests/run_manifest.json
  manifests/data_manifest.json
  manifests/source_license_audit.json
  logs/train.log
  logs/trainer_state.json
  metrics/eval_history.jsonl
  metrics/final_validation.json
  metrics/final_test.json
  samples/eval_generations.jsonl
  checkpoints/checkpoint-<step>/
  adapters/best/
  adapters/final/
  reports/run_report.md
```

Object storage path, once authorized:

```text
s3://<approved-bucket>/phase2/finetune/<snapshot_id>/<run_id>/
```

Do not write model artifacts into validation gold-set directories or performance-work directories.

## Failure And Abort Criteria

Abort a future authorized run if any of the following occur:

- Training dataset includes a source whose training rights are unresolved.
- Exact sequence or leakage connected component appears in more than one split.
- Validation/test split is regenerated or modified after training starts.
- Tokenization produces `<oov>` for canonical training sequences above a tiny threshold caused by known edge cases; default threshold is zero for first pass.
- More than 1% of emitted examples fail schema validation or DNA normalization.
- Training loss is NaN or infinite at any step.
- Gradient norm is NaN/inf, or repeated clipping indicates instability for more than 20 consecutive optimizer steps.
- Validation loss worsens for three consecutive evals after warmup while training loss continues downward sharply, suggesting overfit on a small corpus.
- Generated eval samples show exact target memorization or near-copy behavior above the predeclared threshold.
- GPU memory exceeds budgeted headroom after batch-size reduction and gradient checkpointing.
- Runtime cost exceeds the approved budget ceiling or provider quota.
- Any biosecurity or policy screening process flags a generated sample or training record for human review.

## Smoke-Test Constraints

Before any real run, require an explicitly authorized smoke test with hard caps:

```yaml
smoke_model_order: [Carbon-500M, Carbon-3B]
smoke_max_steps: 10
smoke_max_train_examples: 16
smoke_max_eval_examples: 8
smoke_checkpointing: local_temp_only_unless_artifact_storage_is_approved
smoke_goal: verify loading_tokenization_loss_checkpoint_resume_only
smoke_non_goal: quality_claim_or_phase2_gate
```

Smoke tests must not use validation gold sets, production services, user-visible generation, or unapproved GPU spend. Any smoke test involving GPU use requires a separate human authorization for that session.

## Human Review Gates

Human review is required before training for:

- Exact model revision and whether the `fns` revision is required.
- Managed-GPU provider, hardware, budget ceiling, and object-storage target.
- Source-by-source training-rights policy.
- Minimum corpus size and vector-profile coverage for a real fine-tune versus a dry run.
- Whether validation/test examples are sufficient to interpret any adapter result.
- Whether any Addgene-derived data can be used for model training.

## Citations

- Repo-local readiness: `research/findings/phase2_readiness.md` records Carbon-500M first for smoke testing, Carbon-3B as the practical target, no GPU authorization, insufficient corpus scale for credible fine-tuning, and unresolved legal/data gates.
- Repo-local model review: `research/findings/sequence_models.md` records Carbon-3B as Apache-2.0, decoder-only/autoregressive, long-context, metadata-conditioned, and a lower-cost practical baseline relative to Evo 2 7B.
- Repo-local data contract: `research/findings/training_data_format.md` defines the Phase 2 `(context, template, target)` JSONL format, leakage grouping, split policy, artifact layout, and no-training-rights exclusions.
- Carbon-3B model card, `https://huggingface.co/HuggingFaceBio/Carbon-3B`, fetched 2026-06-06: Apache-2.0 license; 3B decoder-only autoregressive model; native 32,768 6-mer context; YaRN extension to 65,536 tokens; hybrid tokenizer with required `<dna>` tags; metadata-conditioned generation; BF16; AdamW pretraining details; limitations.
- Carbon repository, `https://github.com/huggingface/carbon`, fetched 2026-06-06: Carbon family, Apache-2.0 repository, standard Transformers loading, evaluation scripts, Carbon-3B described as flagship matching or beating Evo2 7B, and fine-tuning scripts.
- Carbon fine-tuning README, `https://github.com/huggingface/carbon/blob/main/finetuning/README.md`, fetched 2026-06-06: official downstream recipes, `finetune_sft.py`, `FNSTrainer`, FNS loss, `--add_dna_tag`, `--dna_loss_only`, and example `batch_size 4 --grad_accum 4` multi-GPU pattern.
- Hugging Face Transformers Trainer docs, `https://huggingface.co/docs/transformers/en/main_classes/trainer`, fetched 2026-06-06: `Trainer`/`TrainingArguments` provide PyTorch training/evaluation loops, distributed/mixed-precision support, optimizer/scheduler defaults, checkpoint save/resume, evaluation, metrics, and state saving.
- Hugging Face PEFT LoRA docs, `https://huggingface.co/docs/peft/en/package_reference/lora`, fetched 2026-06-06: LoRA reduces trainable parameters; `LoraConfig` fields include `r`, `target_modules`, `lora_alpha`, `lora_dropout`, `bias`, `task_type`; PEFT supports k-bit preparation patterns for quantized adapter training.
