> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Fine-Tuning Cost Readiness Estimate

- Date: 2026-06-06
- Scope: readiness estimate only for a credible future Carbon-3B run on the existing 117 training examples.
- Authorization: this document does not authorize GPU spend, fine-tuning, model promotion, performance work, or Phase 2 gate work.
- CPU smoke cost: `$0`; keep any CPU-only smoke test local and free of cloud GPU usage.

## Recommendation

Use a no-spend posture until data/legal readiness is explicitly approved. If a future GPU run is authorized, budget for a LoRA/QLoRA-only Carbon-3B trial, not a full fine-tune.

Recommended budget envelope:

| Run type | Practical target | Estimated GPU-hours | Budget envelope |
| --- | --- | ---: | ---: |
| CPU smoke | Local load/tokenization/tiny dry run only | 0 cloud GPU-hours | `$0` |
| LoRA/QLoRA readiness run | Single 24-48 GB GPU for packaging, tokenizer, training script, checkpoint, and eval smoke | 8-24 GPU-hours | `$10-$75` on low-cost GPU clouds; `$10-$90` on hyperscaler single-GPU equivalents |
| LoRA/QLoRA conservative fallback | Single 40-80 GB A100/H100 if long context, batch shape, or activation memory forces a larger card | 8-24 GPU-hours | `$16-$105` on Lambda/RunPod; about `$88-$527` if forced onto AWS 8xA100 `p4d.24xlarge` |
| Full fine-tune | Full Carbon-3B weight update with optimizer state and activation checkpointing | 12-48 GPU-hours on 80 GB class, or an 8-GPU instance if provider packaging requires it | `$70-$275` on single H100-class public GPU clouds; `$263-$1,054` on AWS `p4d.24xlarge` instance-hours |

For a first authorized run, cap spend at `$100` and require manual approval before any retry. If using AWS `p4d.24xlarge`, treat the minimum credible cap as `$600` because the instance exposes 8 A100 GPUs and is poor fit for a tiny 117-example readiness run.

## Dataset Assumptions

- Existing training set size: 117 examples.
- Format: retrieval-grounded `(context, template, target)` examples, consistent with the Phase 2 formatter notes.
- Token estimate: Carbon uses 6-mer DNA tokenization for DNA segments; assume 0.8k-2.0k model tokens per example after context/template/target wrapping, depending plasmid length and metadata text.
- Effective training tokens: about 94k-234k tokens per epoch; 3-10 epochs gives about 0.3M-2.3M tokens before packing/padding overhead.
- Cost driver: fixed setup, dependency installation, checkpoint save/load, and troubleshooting dominate. Raw training compute is tiny.
- This dataset is not enough to claim biological quality or generalization. The only credible goal is pipeline readiness.

## Memory Class

| Method | Plausible GPU memory class | Notes |
| --- | --- | --- |
| CPU smoke | No cloud GPU | Tokenizer/model-load or dry-run checks only; cost target remains `$0`. |
| LoRA | 24 GB minimum, 48 GB preferred | Carbon-3B BF16 weights are roughly 6 GB before activations and framework overhead; LoRA with gradient checkpointing can plausibly fit on 24-48 GB if sequence lengths and batch size are conservative. |
| QLoRA | 24 GB minimum, 48 GB preferred | Quantized base weights reduce memory pressure; still budget 48 GB when using long plasmid contexts or inefficient kernels. |
| Full fine-tune | 80 GB preferred; 40 GB is risky | Full optimizer state, gradients, activations, and long contexts make A100/H100 80 GB the safer class. Multi-GPU sharding may be needed if preserving long context without aggressive checkpointing. |

## Provider Estimates

Public/on-demand prices vary by region, availability, OS image, storage, network, taxes, and whether the provider bills per GPU or per instance. Prices below are readiness estimates as of 2026-06-06. GCP line items are marked approximate because the public pricing page is region/SKU-dependent and should be rechecked in the calculator before spend.

| Provider | Example public/on-demand SKU | Price basis used | LoRA/QLoRA 8-24h estimate | Full FT 12-48h estimate |
| --- | --- | ---: | ---: | ---: |
| AWS | `g5.2xlarge`, 1x A10G 24 GB | `$1.212/hr` | `$10-$29` | Not recommended for full Carbon-3B |
| AWS | `p4d.24xlarge`, 8x A100 40 GB | `$21.958/instance-hr` | `$176-$527` if forced onto this instance | `$263-$1,054` |
| GCP | G2/L4 24 GB class | approx `$0.80-$1.20/hr` | `$6-$29` | Not recommended for full Carbon-3B |
| GCP | A2/A100 40-80 GB class | approx `$3.70-$6.00/hr` | `$30-$144` | `$44-$288` |
| Lambda Labs | 1x A6000 48 GB | `$1.09/GPU-hr` | `$9-$26` | Not recommended for full Carbon-3B |
| Lambda Labs | 1x A100 40 GB | `$1.99/GPU-hr` | `$16-$48` | Risky for full Carbon-3B |
| Lambda Labs | 1x H100 80 GB | `$4.29/GPU-hr` | `$34-$103` | `$51-$206` |
| RunPod | L4 24 GB pod | `$0.39/hr` | `$3-$9` | Not recommended for full Carbon-3B |
| RunPod | L40S 48 GB pod | `$0.86/hr` | `$7-$21` | Not recommended for full Carbon-3B |
| RunPod | A100 80 GB pod | `$1.39-$1.49/hr` | `$11-$36` | `$17-$72` |
| RunPod | H100 80 GB pod | `$2.89-$3.29/hr` | `$23-$79` | `$35-$158` |

## Interpretation

LoRA/QLoRA is the only cost-rational future path for the current 117-example set. The dataset is so small that a successful run would prove packaging and integration, not model quality. Full fine-tuning Carbon-3B on 117 examples is technically possible on 80 GB class hardware, but it is likely to overfit and waste the fixed cost of environment setup and debugging.

Avoid AWS `p4d.24xlarge` unless there is an AWS-specific operational requirement. It is a high-quality A100 training instance, but the instance-level 8-GPU footprint makes it an expensive mismatch for a single-GPU readiness exercise.

## No-GPU-Spend Note

No GPU spend is authorized by this estimate. The next safe action remains a `$0` CPU smoke or dry-run workflow that validates dataset serialization, tokenization boundaries, training command construction, checkpoint-path handling, and evaluation wiring without allocating a cloud GPU.

## Risks

- Pricing can change without notice; re-check provider calculators immediately before any approved spend.
- Cloud GPU availability may be lower than listed, especially for A100/H100 capacity.
- Storage, image pull time, egress, persistent volumes, managed notebooks, taxes, and idle time are excluded from the core GPU-hour estimate.
- Carbon-3B fine-tuning memory is not benchmarked in this repository; long context, batch packing, tokenizer behavior, and framework versions may change fit from 24 GB to 48/80 GB.
- 117 examples are insufficient for a quality claim; overfitting is the main technical risk.
- Training-data rights and model/license review remain separate gates.
- Full fine-tuning may require distributed training expertise that is not justified for the current dataset size.

## Sources

1. Carbon-3B model card, `HuggingFaceBio/Carbon-3B`, https://huggingface.co/HuggingFaceBio/Carbon-3B.
2. Carbon fine-tuning instructions, https://github.com/huggingface/carbon/blob/main/finetuning/README.md.
3. AWS EC2 On-Demand pricing page, https://aws.amazon.com/ec2/pricing/on-demand/.
4. AWS P4 instance page, A100/P4d hardware description, https://aws.amazon.com/ec2/instance-types/p4/.
5. Vantage AWS `g5.2xlarge` price/spec snapshot, updated 2026-06-06, https://instances.vantage.sh/aws/ec2/g5.2xlarge.
6. Vantage AWS `p4d.24xlarge` price/spec snapshot, updated 2026-06-06, https://instances.vantage.sh/aws/ec2/p4d.24xlarge.
7. Google Cloud Compute Engine pricing overview and accelerator-optimized pricing entry point, https://cloud.google.com/compute/gpus-pricing and https://cloud.google.com/products/compute/pricing/accelerator-optimized.
8. Lambda AI Cloud pricing page, https://lambda.ai/pricing.
9. RunPod GPU Cloud pricing page, https://www.runpod.io/pricing.
