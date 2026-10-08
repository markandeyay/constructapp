> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Phase 2 Fine-Tune Run V1 Preflight

- Date: 2026-06-10
- Branch: `phase2-finetune-run`
- Intended run: standard `HuggingFaceBio/Carbon-3B`, LoRA adapter, existing `2026-06-04-010952-phase2-triplets` snapshot, budget cap USD 300.
- Outcome: stopped before paid provisioning; no GPU spend occurred.

## Preflight Findings

The local repo has a real Hugging Face training path in `packages/generation/finetune.py`, not only a smoke test. The CLI supports `--snapshot-path`, `--base-model`, `--base-model-revision`, `--method`, learning rate, batch sizes, gradient accumulation, epochs, eval/save steps, max length, seeds, and example limits.

The training snapshot exists and matches the authorized policy:

- Train: 117 triplets.
- Validation: 15 triplets.
- Test: 8 triplets.
- Source policy: public NCBI-derived snapshot, no Addgene-gated data.

The runbook had two pre-spend gaps that were corrected in this session:

- It listed `train.jsonl`, `validation.jsonl`, and `test.jsonl`, but the actual files are `triplets.train.jsonl`, `triplets.validation.jsonl`, and `triplets.test.jsonl`.
- It used a non-existent `--training-snapshot` flag and placeholders for length/steps. The corrected command uses `--snapshot-path` and the approved LoRA defaults from `research/findings/finetune_config.md`.

## Stop Reason

Execution is blocked before spending for two operational reasons:

1. Provider automation is not configured in this worktree. `runpodctl`, a Lambda CLI, and `huggingface-cli` were not available on PATH. The session therefore could not provision a provider instance, verify account balance, or check live GPU availability programmatically.
2. The GPU-host training environment must install and verify PEFT dependencies before training. The local CI `requirements.txt` includes `torch` and `transformers`, but not `peft`, `accelerate`, or `bitsandbytes`. That is acceptable for CI, but a real Carbon-3B LoRA run must pass the GPU-host dependency gate before launch.

No paid resource was provisioned.

## Provider Selection

The selected target is RunPod Pods, preferring A100 80 GB if available. The pricing rationale is documented in `research/findings/phase2_provider_selection.md`.

## Next Attempt Checklist

1. Configure provider access in a way the agent can use non-interactively.
2. Confirm account balance and live A100/H100 availability.
3. Launch the cheapest suitable RunPod A100 80 GB pod if available.
4. Install GPU-host dependencies:

   ```bash
   python -m pip install "peft>=0.18,<1" "accelerate>=1.10,<2" "bitsandbytes>=0.48,<1"
   ```

5. Verify:

   ```bash
   python -c "import torch, transformers, peft, accelerate; print(torch.__version__)"
   nvidia-smi
   ```

6. Pin and record the Carbon-3B revision.
7. Run the corrected command from `docs/runbooks/phase2_finetune.md`.
8. Download checkpoints/logs, destroy the GPU instance, evaluate, and register in shadow mode.
