> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Phase 2 Provider Selection

- Date: 2026-06-10
- Scope: first authorized Carbon-3B LoRA fine-tuning run, budget capped at USD 300.
- Status: provider target selected, but no paid GPU was provisioned because local provider automation/account access was not available in this session.

## Decision

Use RunPod Pods as the first target, preferring a single A100 80 GB pod if available. Prefer A100 PCIe 80 GB at the published USD 1.39/hr price, then A100 SXM 80 GB at USD 1.49/hr, then H100 PCIe 80 GB at USD 2.89/hr if A100 inventory is unavailable.

Lambda remains the fallback provider. Lambda's published instance pricing lists H100 SXM 80 GB at USD 4.29/GPU/hr for a 1x instance and A100 80 GB pricing only in larger A100 SXM rows at USD 2.79/GPU/hr, making RunPod materially cheaper for this small single-run job.

## Pricing Snapshot

| Provider | Hardware | Published price | Notes |
| --- | ---: | ---: | --- |
| RunPod Pods | A100 PCIe 80 GB | USD 1.39/hr | Cheapest preferred target. |
| RunPod Pods | A100 SXM 80 GB | USD 1.49/hr | Slightly higher price, still preferred over H100 if available. |
| RunPod Pods | H100 PCIe 80 GB | USD 2.89/hr | Fallback if A100 80 GB is unavailable. |
| RunPod Pods | H100 SXM 80 GB | USD 3.29/hr | Fallback if PCIe H100 unavailable. |
| Lambda Instances | H100 SXM 80 GB, 1x | USD 4.29/GPU/hr | More expensive than RunPod H100 PCIe/SXM. |
| Lambda Instances | A100 SXM 80 GB, 8x row | USD 2.79/GPU/hr | Published as an 8x plan; not the cleanest fit for a single small adapter run. |

## Cost Estimate

The dataset is tiny: 117 train, 15 validation, 8 test triplets. A conservative first-run budget model is:

- 1 hour setup/model download/dependency verification.
- 2 hours training and checkpoint export.
- 1 hour evaluation and artifact transfer.

At the preferred RunPod A100 80 GB prices, a 4-hour window costs approximately USD 5.56 to USD 5.96 before storage/network charges. Even a RunPod H100 PCIe fallback costs approximately USD 11.56 for 4 hours. These are far below the USD 300 cap, but the cap remains hard and the instance must be destroyed immediately after artifacts are verified.

## Availability And Access

Published pricing does not guarantee live pod availability. This session found no local `runpodctl`, no local `lambda` CLI, and no `huggingface-cli` on PATH. Because no authenticated provider automation was available, no GPU was provisioned and no spend occurred.

Before retrying execution, configure one of:

- RunPod account/API access plus a scripted pod launch path, or
- Lambda Cloud account/API/SSH launch path.

The execution agent must verify live availability and account balance/limits before provisioning.

## Sources

- RunPod pricing page, fetched 2026-06-10: Pods list A100 PCIe 80 GB at USD 1.39/hr, A100 SXM 80 GB at USD 1.49/hr, H100 PCIe 80 GB at USD 2.89/hr, and H100 SXM 80 GB at USD 3.29/hr.
- Lambda pricing page, fetched 2026-06-10: Instances list H100 SXM 80 GB at USD 4.29/GPU/hr for 1x and A100 SXM 80 GB at USD 2.79/GPU/hr in the 8x row.
- Hugging Face Carbon-3B model card, reviewed in repo-local findings: standard Carbon-3B remains the authorized base model for this run.
