# CPU Generation Feasibility

## Summary

Go for GEN-2 with Carbon-500M as the CPU spike model.

Carbon-500M is genuinely CPU-runnable on this machine for a short pretrained inference smoke test. A local CPU-only load plus 4-token greedy generation completed in 40.68 seconds total, under the requested 10-minute threshold. This is not a quality validation, not fine-tuning, and not integration work.

Carbon-500M is the best GEN-2 spike choice because it is an Apache-2.0, 500M-parameter, decoder-only autoregressive DNA model with standard Hugging Face causal-LM loading and direct DNA generation support. It is explicitly described as a small Carbon-family draft/speculative decoding model, not as the flagship quality model, so GEN-2 should treat it as a plumbing and feasibility target rather than a biological-quality generator.

## Candidates Reviewed

### Carbon-500M

- Model: `HuggingFaceBio/Carbon-500M`.
- Parameters: 0.5B / 500M params.
- Architecture: decoder-only autoregressive Llama-style DNA model, released as `LlamaForCausalLM`.
- Tokenizer: Carbon hybrid tokenizer, 6-mer DNA mode plus Qwen3 BPE for English text; DNA prompts must be wrapped with `<dna>` and should use uppercase A/C/G/T with lengths aligned to 6 bp where practical.
- Context: 8,192 6-mer tokens, about 49 kbp.
- Training: 600B 6-mer tokens, about 3.6T DNA base pairs; data mixture includes eukaryotic genes, mature mRNA, splice-enriched mRNA, and GTDB bacterial genomes.
- License: Apache-2.0 on the Hugging Face model card.
- Use constraints: card says it is primarily intended as a draft model for speculative decoding with Carbon-3B/8B and is not designed to be competitive with larger Carbon models on downstream benchmarks.
- Benchmarks: Carbon-500M card points to the Carbon evaluation suite and says it is benchmarked against about 1B-parameter DNA models, but the card does not expose detailed CPU latency benchmarks. Local CPU timing below is therefore the relevant feasibility evidence for this machine.

### Carbon-3B

- Model: `HuggingFaceBio/Carbon-3B`.
- Parameters: 3B.
- Architecture: decoder-only autoregressive genomic foundation model.
- Tokenizer/context: same Carbon hybrid tokenizer; native 32,768 6-mer tokens, about 197 kbp; YaRN extension to 65,536 tokens, about 393 kbp.
- License: Apache-2.0 on the Hugging Face model card.
- Benchmarks: model card reports competitive zero-shot results versus Evo2-7B and GENERator-v2 3B on sequence recovery, variant-effect prediction, perturbation tasks, and Genomic-NIAH long-context retrieval. It also reports very high H100 throughput, but that is GPU-serving evidence, not local CPU evidence.
- Feasibility judgment: not smoke-tested locally because Carbon-500M already met the CPU spike threshold and Carbon-3B would increase download and RAM pressure. Keep Carbon-3B as a future quality/throughput comparison when GPU or larger CPU benchmarking is authorized.

### DNABERT-2 117M

- Model: `zhihan1996/DNABERT-2-117M`.
- Parameters: 117M.
- Architecture: transformer-based genome foundation model, BERT-style encoder rather than autoregressive generator.
- Output shape: model card demonstrates hidden states with 768-dimensional embeddings.
- License: the official GitHub repository is Apache-2.0; the fetched Hugging Face model page did not show an explicit license tag for the hosted weights.
- Benchmarks: DNABERT-2 paper/card position it as an efficient multi-species genome foundation model evaluated on GUE-style tasks. The paper reports comparable performance to larger prior models with much less pretraining compute, but the model card demonstrates embeddings rather than generation.
- Feasibility judgment: useful fallback for CPU embeddings, masked/encoder-style sequence scoring, retrieval, or classifiers, but not a direct whole-sequence generation spike. Local smoke test was blocked before model load by missing `einops`; this is an environment dependency blocker, not CPU infeasibility.

### Nucleotide Transformer Family

- Models: InstaDeep Nucleotide Transformer checkpoints.
- Parameters: includes 500M and 2.5B families in earlier releases.
- Architecture/use: encoder/masked-language modeling and downstream genomic prediction/variant scoring, not a direct autoregressive plasmid generator.
- License: earlier Hugging Face checkpoints reviewed in prior findings use CC-BY-NC-SA-4.0, which blocks commercial production use without separate permission.
- Feasibility judgment: not recommended for GEN-2 spike generation because of non-commercial license constraints and non-autoregressive primary use.

### Evo / Evo 2

- Models: Evo 1 7B and Evo 2 7B+ families.
- Architecture/use: autoregressive biological sequence generation with long context.
- License: open local Hugging Face/GitHub paths reviewed previously are Apache-2.0, with separate NVIDIA terms for hosted NIM paths.
- Feasibility judgment: technically relevant but outside this CPU smoke-test scope. 7B-class local CPU inference is likely much slower and larger than Carbon-500M, and Phase 2 spike notes already defer Evo 2 benchmarking.

## Local CPU Smoke Tests

Environment captured on branch `phase2-real-generation`:

```text
Python 3.14.2
torch 2.12.0+cpu
cuda_available False
transformers 4.57.6
HF_HOME None
TRANSFORMERS_CACHE None
HF_HUB_CACHE None
```

Hugging Face cache root:

```text
~\.cache\huggingface\hub
```

Cached artifacts after tests:

```text
models--HuggingFaceBio--Carbon-500M size_on_disk 1.0G nb_files 5 refs main
models--Qwen--Qwen3-4B-Base size_on_disk 11.5M nb_files 4 refs main
models--zhihan1996--DNABERT-2-117M size_on_disk 210.7K nb_files 5 refs main
```

The Qwen cache entry was pulled by Carbon's hybrid tokenizer dependency.

### Carbon-500M CPU Generation

Command attempted:

```powershell
$env:CUDA_VISIBLE_DEVICES=""; python -c "import time, torch; from huggingface_hub import constants; from transformers import AutoTokenizer, AutoModelForCausalLM; repo='HuggingFaceBio/Carbon-500M'; prompt='<dna>ATGCGCTAGCTACGATCGATCGTAGCTAGCTAGCTAGCTACG'; print('repo', repo); print('cache', constants.HF_HUB_CACHE); print('cuda_available', torch.cuda.is_available()); t0=time.perf_counter(); tok=AutoTokenizer.from_pretrained(repo, trust_remote_code=True); print('tokenizer_load_s', round(time.perf_counter()-t0, 2)); t1=time.perf_counter(); model=AutoModelForCausalLM.from_pretrained(repo, dtype=torch.float32, device_map=None).to('cpu').eval(); print('model_load_s', round(time.perf_counter()-t1, 2)); inputs=tok(prompt, return_tensors='pt', add_special_tokens=False); print('input_tokens', inputs['input_ids'].shape[-1]); t2=time.perf_counter(); import torch as _torch; exec('with _torch.no_grad():\n    out=model.generate(**inputs, max_new_tokens=4, do_sample=False, pad_token_id=tok.eos_token_id)'); print('generate_s', round(time.perf_counter()-t2, 2)); print('new_tokens', out.shape[-1]-inputs['input_ids'].shape[-1]); print('decoded', tok.decode(out[0][inputs['input_ids'].shape[-1]:], skip_special_tokens=True)); print('total_s', round(time.perf_counter()-t0, 2))"
```

Result:

```text
repo HuggingFaceBio/Carbon-500M
cache ~\.cache\huggingface\hub
cuda_available False
tokenizer_load_s 5.67
model_load_s 31.86
input_tokens 8
generate_s 3.12
new_tokens 4
decoded ATCGATCGTAGCTAGCTAGCTAGC
total_s 40.68
```

Interpretation:

- Carbon-500M is CPU-runnable locally for short inference.
- The measured 4-token greedy decode was comfortably below 10 minutes.
- The command used `dtype=torch.float32` on CPU instead of GPU-oriented BF16 loading. This likely increases RAM use versus BF16 but avoids relying on BF16 CPU kernel behavior.
- Hugging Face emitted Windows symlink-cache warnings; caching still worked in degraded non-symlink mode.
- `trust_remote_code=True` was needed for the tokenizer. GEN-2 should pin a revision before any repeatable workflow.

### DNABERT-2 CPU Embedding Fallback

Command attempted:

```powershell
$env:CUDA_VISIBLE_DEVICES=""; python -c "import time, torch; from huggingface_hub import constants; from transformers import AutoTokenizer, AutoModel; repo='zhihan1996/DNABERT-2-117M'; dna='ACGTAGCATCGGATCTATCTATCGACACTTGGTTATCGATCTACGAGCATCTCGTTAGC'; print('repo', repo); print('cache', constants.HF_HUB_CACHE); print('cuda_available', torch.cuda.is_available()); t0=time.perf_counter(); tok=AutoTokenizer.from_pretrained(repo, trust_remote_code=True); print('tokenizer_load_s', round(time.perf_counter()-t0, 2)); t1=time.perf_counter(); model=AutoModel.from_pretrained(repo, trust_remote_code=True, dtype=torch.float32).to('cpu').eval(); print('model_load_s', round(time.perf_counter()-t1, 2)); inputs=tok(dna, return_tensors='pt'); print('input_tokens', inputs['input_ids'].shape[-1]); t2=time.perf_counter(); import torch as _torch; exec('with _torch.no_grad():\n    hidden=model(**inputs)[0]'); print('forward_s', round(time.perf_counter()-t2, 2)); print('hidden_shape', tuple(hidden.shape)); print('embedding_dim', hidden.shape[-1]); print('total_s', round(time.perf_counter()-t0, 2))"
```

Result:

```text
repo zhihan1996/DNABERT-2-117M
cache ~\.cache\huggingface\hub
cuda_available False
tokenizer_load_s 1.77
ImportError: This modeling file requires the following packages that were not found in your environment: einops. Run `pip install einops`
```

Interpretation:

- DNABERT-2 tokenizer download/load started successfully.
- Model load did not run because the local Python environment lacks `einops`.
- This is an environment/package blocker, not a true CPU infeasibility result.
- Even if it loads after installing `einops`, DNABERT-2 is an encoder/embedding model and is not a direct replacement for autoregressive generation.

## Recommendation

GEN-2 go: use Carbon-500M as the optional pretrained CPU spike model behind a narrow, non-default experimental path.

Keep the deterministic fake/template generator as the default path for tests and offline development. Carbon-500M should be used only to prove model-backed generation plumbing and latency feasibility for one short public DNA prompt. Do not claim biological validity, synthesis readiness, or plasmid design quality from Carbon-500M output.

Do not spend GPU, do not fine-tune, and do not benchmark Carbon-3B/Evo 2 locally until explicitly authorized.

## Implementation Notes for GEN-2

- Pin model revisions for repeatability because Carbon tokenizer loading uses remote code.
- Force CPU explicitly with `CUDA_VISIBLE_DEVICES=""`, `torch.cuda.is_available()` logging, and `.to('cpu')`.
- Use `AutoTokenizer.from_pretrained('HuggingFaceBio/Carbon-500M', trust_remote_code=True)`.
- Use `AutoModelForCausalLM.from_pretrained('HuggingFaceBio/Carbon-500M', dtype=torch.float32, device_map=None).to('cpu').eval()` for the proven CPU path.
- Wrap DNA prompts with `<dna>` and use uppercase A/C/G/T only.
- Prefer prompt lengths divisible by 6 bp because Carbon uses non-overlapping 6-mer DNA tokens and pads partial trailing blocks.
- Start with very small `max_new_tokens` values; 4 new 6-mer tokens took 3.12 seconds after load on this machine.
- Treat first-run download/cache time separately from warm inference time.
- Expect about 1.0 GB of Hugging Face cache for Carbon-500M plus about 11.5 MB for the Qwen tokenizer dependency in the current cache layout.
- Enable Windows Developer Mode or tolerate degraded Hugging Face cache storage if symlink warnings matter for disk usage.
- Do not add Carbon to the production path or tests that require network/model downloads.

## Risks

- Carbon-500M is explicitly a draft/speculative model, so output quality may be weak versus Carbon-3B/8B.
- Carbon-family training is primarily eukaryotic/transcript-oriented with only a bacterial component; plasmid/vector-specific behavior is not established.
- Carbon output is unconstrained; without validation and component checks it can easily emit biologically invalid, incomplete, or unsafe-looking sequences.
- `trust_remote_code=True` creates supply-chain risk unless revisions are pinned and reviewed.
- Local CPU timing was measured on one short prompt and 4 generated tokens only; longer sequences may scale poorly.
- Windows Hugging Face cache symlink degradation can increase disk usage.
- DNABERT-2 fallback currently needs at least `einops` installed before model-load feasibility can be measured.
- DNABERT-2 weight licensing remains less clear from the fetched Hugging Face card than Carbon's explicit Apache-2.0 tag.

## Questions For Human

- Should GEN-2 install `einops` to complete a DNABERT-2 CPU embedding smoke test, or is Carbon-500M sufficient for this phase?
- Should GPU authorization be considered later for Carbon-3B or Evo 2 benchmarking, or should GEN-2 remain CPU-only?
- Is Apache-2.0 acceptable for Carbon model weights in the intended Construct deployment context, pending normal legal review?
- Should GEN-2 pin a specific Carbon-500M commit hash now, or wait until the implementation branch begins?

## Sources

1. Hugging Face model card, `HuggingFaceBio/Carbon-500M`, https://huggingface.co/HuggingFaceBio/Carbon-500M.
2. Hugging Face model card, `HuggingFaceBio/Carbon-3B`, https://huggingface.co/HuggingFaceBio/Carbon-3B.
3. Hugging Face model card, `zhihan1996/DNABERT-2-117M`, https://huggingface.co/zhihan1996/DNABERT-2-117M.
4. Zhou et al., "DNABERT-2: Efficient Foundation Model and Benchmark For Multi-Species Genome", https://arxiv.org/abs/2306.15006.
5. MAGICS-LAB DNABERT_2 repository, https://github.com/MAGICS-LAB/DNABERT_2.
6. Prior Construct findings, `research/findings/sequence_models.md`.
