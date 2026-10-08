> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Phase 2 Training Data Formatter

## Summary

Phase 2 needs deterministic `(context, template, target)` examples from Phase 0 records as specified in `SYSTEM_DESIGN.md` Section 7.3. The existing corpus does not naturally contain many explicit redesign pairs, so the formatter should synthesize supervised examples by treating one real, validated plasmid as the `target`, deriving a natural-language goal-like `context` from the same record, and selecting a closely related but distinct real plasmid as the `template`.

Implementation can proceed with conservative assumptions. No biology blocker prevents building the formatter, provided the first implementation excludes incomplete annotations, performs holdout assignment before template retrieval, and reports leakage diagnostics rather than claiming biological novelty.

The formatter is a data-preparation component only. It must not touch frontend, API, or worker code, and it must not promote a Phase 2 quality claim. The current Phase 2 readiness note states that the corpus is below the formal Phase 0 gate and lacks a real constraint engine; this formatter is therefore a prerequisite artifact, not evidence that fine-tuning or the Phase 2 gate is ready (`research/findings/phase2_readiness.md`).

## Inputs/Outputs

### Inputs

- Canonical `Plasmid` records from `packages/core/schemas/models.py`, matching `SYSTEM_DESIGN.md` Section 12.1: source-stable ID, source, name, sequence, length, organism, vector type, markers, promoters, publication DOI, use cases, annotation completeness, and raw reference.
- Canonical `AnnotatedSequence` records from `packages/core/schemas/models.py`, matching `SYSTEM_DESIGN.md` Section 12.3: normalized DNA sequence, topology, typed feature list, vector profile, and annotation completeness.
- Optional `ExperimentalContext` rows from `SYSTEM_DESIGN.md` Section 12.2 when available: organism, cell line, vector type, genes, tags, promoter type, inducer, application, assay, and provenance.
- Existing Phase 1 retrieval document composer semantics from `packages/retrieval/document_composer.py` and `research/decisions/phase1_document_composer.md`.
- Existing retrieval embeddings/vector metadata where available, because Section 7.3 says template selection should use a closely related plasmid retrieved as in Phase 1.
- Source/provenance metadata for leakage grouping: `source`, `raw_ref`, `publication_doi`, accession-like IDs, source-native submitter/depositing lab fields when later ingestion provides them, and sequence-similarity clusters computed from normalized DNA.

### Outputs

Emit versioned JSONL examples, one example per line. Use JSONL because it is appendable, streamable, easy to shard, and compatible with fine-tuning loaders.

Required fields:

```json
{
  "example_id": "phase2fmt-v1::<target_id>::<template_id>",
  "formatter_version": "phase2-triplet-v1",
  "split": "train|validation|test",
  "context": {
    "text": "Natural-language design goal...",
    "design_spec": { "...": "DesignSpec-compatible fields" },
    "source": "experimental_context|composed_document|derived_summary",
    "provenance": [{ "field": "...", "source_id": "..." }]
  },
  "template": {
    "plasmid_id": "...",
    "sequence": "ACGT...",
    "annotated_sequence": { "...": "AnnotatedSequence JSON" },
    "retrieval_score": 0.0,
    "selection_reason": ["same_vector_profile", "nearest_neighbor"]
  },
  "target": {
    "plasmid_id": "...",
    "sequence": "ACGT...",
    "annotated_sequence": { "...": "AnnotatedSequence JSON" },
    "source": "genbank|addgene|curated|literature",
    "raw_ref": "...",
    "publication_doi": "..."
  },
  "leakage_group": {
    "depositing_lab": null,
    "publication_doi": "...",
    "source_accession_cluster": "...",
    "sequence_similarity_cluster": "...",
    "assigned_group_key": "..."
  },
  "quality_flags": []
}
```

Recommended artifact layout:

- `data/training/phase2/<snapshot_id>/triplets.train.jsonl`
- `data/training/phase2/<snapshot_id>/triplets.validation.jsonl`
- `data/training/phase2/<snapshot_id>/triplets.test.jsonl`
- `data/training/phase2/<snapshot_id>/manifest.json`
- `data/training/phase2/<snapshot_id>/stats.md`

The manifest must include input snapshot IDs, formatter version, composer document version, embedding model/version, split policy, similarity-clustering parameters, and generation timestamp. This follows `SYSTEM_DESIGN.md` Section 11.3 on idempotent, snapshot-parameterized jobs.

## Triplet Generation Algorithm

1. Load all candidate plasmids and their latest parsed `AnnotatedSequence` records for a fixed Phase 0 snapshot.
2. Exclude records with invalid DNA, missing sequence, length mismatch, parse errors, `annotation_complete=false`, or `AnnotatedSequence.annotation_complete=false`.
3. Exclude records whose source license/terms do not allow model training. If a source is usable for retrieval/display but not training, it can appear in non-training diagnostics only, not in emitted examples.
4. Exclude records that are not engineered-vector-like templates when the parser classifies them as unknown natural plasmids, natural mobile resistance plasmids, environmental plasmids, or other non-design backbones. The classifier audit notes that natural mobile resistance plasmids can be useful for comparative retrieval but should not be treated as engineered vector templates (`data/eval/classifier_unknown_audit_2026-06-02-102348.md`).
5. Build or load leakage groups for all remaining records before assigning splits.
6. Assign each leakage group to `train`, `validation`, or `test` with deterministic hashing seeded by the snapshot ID. Suggested ratios: 80/10/10 while enforcing minimum counts per vector profile where possible.
7. For each target plasmid, construct `context` using the hierarchy in the Context Text Construction section.
8. Select the template only from the same split as the target. This prevents a held-out target from using a training template that is nearly identical by provenance or sequence.
9. Retrieve candidate templates using Phase 1 semantics over composed documents plus structured filters. Exclude the target itself and any record in the same leakage group.
10. Apply quality filters to retrieved candidates: same or compatible `vector_profile`, compatible topology, sequence length within a configurable ratio, no near-duplicate above the test-leakage threshold, and no incompatible host/vector evidence.
11. Pick the highest-ranked remaining candidate as the template. If no template passes, skip the target and record a `no_valid_template` statistic.
12. Serialize the target and template as normalized `AnnotatedSequence` JSON plus raw sequence.
13. Validate the example schema, write to the split JSONL, and append audit metadata to the manifest/stats.

The target remains the real plasmid itself. The model learns to produce a public/source-validated plasmid conditioned on a goal-like context and a similar starting backbone. This matches Section 7.3's explicit fallback for scarce direct redesign pairs.

## Context Text Construction

The formatter should produce two synchronized context representations: human-readable `context.text` and a `DesignSpec`-compatible object. This allows fine-tuning formats to use either plain text, structured JSON, or both.

Context source priority:

1. Prefer high-confidence `ExperimentalContext` rows linked to the target plasmid when present. These are the closest match to a real researcher goal because Section 5.4/12.2 describes extracting organism, cell line, vector type, genes, tags, promoter, inducer, application, and assay from literature context.
2. Otherwise derive context from the Phase 1 composed document audit payload, not from raw metadata strings alone. The composer already emits goal-like clauses in deterministic order: profile, source description, organism annotation, promoters, payloads, cloning sites, terminators, selectable markers, origins, use cases, length/topology, and source (`packages/retrieval/document_composer.py`; `research/decisions/phase1_document_composer.md`).
3. If neither source yields enough fields, skip the target rather than hallucinating a goal.

Text style:

- Use an imperative or request-like sentence: `Design a {vector_profile phrase} for {application} with {promoter} promoter, {genes/tags payload}, {marker} selection, and {origin/topology constraints}.`
- Do not include the target plasmid name, target source accession, raw reference, DOI, or exact sequence in `context.text`. Including the target identity makes the task a lookup problem rather than generation.
- Preserve biological uncertainty explicitly. For example, use `organism annotation: ...` when the source field is not a reliable experimental host, following the composer decision that `Plasmid.organism` should not be rewritten as host use.
- Prefer controlled vocabulary fields already accepted by `DesignSpec`: organism, cell line, vector type, genes, tags, promoter type, inducer, markers, source, publication DOI, application, cloning method, and constraints.
- Put weaker claims in `constraints` rather than core fields. Example: `"constraints": ["source record mentions low-copy behavior"]` if copy number is inferred from text rather than an annotated origin profile.

Minimum context requirements for an emitted example:

- `vector_type` or `vector_profile` must be known.
- At least one design-relevant component must be known: marker, promoter, GOI/payload, origin, MCS/cloning slot, tag, application, or experimental context.
- `clarification_needed` must be `false`; training examples should not encode ambiguous requests as completed designs.

## Template Selection

Template selection should emulate the Phase 1 retrieval path while avoiding leakage.

Candidate retrieval lanes:

- Structured prefilter: same split, not same target, not same leakage group, annotation complete, compatible source license, compatible vector profile if known.
- Semantic ranking: use existing Phase 1 embeddings over composed plasmid documents (`SYSTEM_DESIGN.md` Sections 6.2 and 6.4).
- Optional sequence-neighbor ranking: within the structured candidate set, compute DNA sequence similarity or k-mer MinHash distance and use it as a secondary signal.

Recommended scoring:

```text
template_score = 0.60 * semantic_similarity
               + 0.25 * structured_overlap
               + 0.15 * bounded_sequence_relatedness
```

Structured overlap can count vector profile, marker, promoter family, origin family, host/cell-line context, application, topology, and length bucket. `bounded_sequence_relatedness` should reward similarity enough to make the pair plausible but must reject near-identical leakage.

Hard exclusions:

- Same plasmid ID.
- Same source accession cluster.
- Same publication/depositing-lab group when that group is the assigned split key.
- Pairwise sequence identity above the configured near-duplicate threshold for validation/test examples. A conservative starting value is `>= 0.95` over most of the plasmid length; tune after inspecting duplicate clusters.
- Candidate is a natural resistance/mobilizable plasmid or other non-engineered vector profile unless the target has the same explicit non-engineered profile and humans approve that profile for training.
- Incompatible vector profile, such as using a bacterial cloning vector as the template for a lentiviral transfer-vector target, unless no same-profile templates exist and the example is explicitly flagged for later exclusion from first-pass fine-tuning.

Tie-breakers should be deterministic: higher score, then higher annotation completeness confidence if available, then shorter absolute length difference, then lexicographic plasmid ID.

## Target Serialization

Serialize targets in a model-agnostic way first; tokenizer-specific representations can be derived later by the training job.

Required target content:

- Full normalized ACGT DNA sequence from `Plasmid.sequence` or `AnnotatedSequence.sequence`; these must match exactly after normalization.
- `AnnotatedSequence` JSON with topology, features, vector profile, and `annotation_complete=true`.
- `Plasmid` provenance fields: ID, source, name, raw reference, publication DOI, source license status, and source snapshot ID.

Recommended target text wrapper for instruction fine-tuning:

```text
<context>
{context.text}
</context>
<template id="{template.plasmid_id}">
{template.sequence}
</template>
<target>
{target.sequence}
</target>
```

Do not make this wrapper the only persisted representation. Keep structured JSONL as the source of truth so future model adapters can choose FASTA-like, GenBank-like, tokenized, or edit-script formats.

Optional derived target fields:

- Edit script from template to target for encoder-decoder or edit-model experiments.
- Feature table as compact JSON for models that condition on annotations.
- Chunked sequence windows only if the selected base model cannot fit full plasmids. Chunked examples must preserve plasmid-level split assignment and must not put chunks from one plasmid into different splits.

## Holdout and Leakage Prevention

Holdout assignment must happen before template selection and before any chunking.

Leakage risk is high because public plasmid corpora often contain renamed derivatives, identical backbone families, duplicate GenBank/Addgene entries, and records tied to the same paper/lab. Section 7.3 explicitly requires holding out by depositing lab/publication to avoid leakage.

Build a hierarchical leakage key for each target:

1. Depositing lab or source submitter, when available from Addgene/source metadata.
2. Publication DOI or PubMed-linked publication cluster.
3. Source accession cluster, including version-stripped GenBank accessions and source-native aliases.
4. Exact sequence hash.
5. Sequence-similarity cluster from an all-vs-all or approximate clustering pass.

Use the strongest available key as `assigned_group_key`, but retain all keys in audit metadata. If a plasmid has multiple keys, the split assignment should merge connected components across keys so related records cannot straddle splits.

Sequence-similarity clustering options:

- Use an exact normalized sequence hash for duplicate detection.
- Use MinHash/k-mer Jaccard or a fast nucleotide clustering tool for approximate grouping at high identity.
- For formal validation/test leakage reports, run pairwise alignment or a stronger sequence-identity check on nearest cross-split neighbors.

External rationale: GenBank is a public archival sequence database with accession-based records and source provenance, so accession/version clustering is appropriate for public GenBank-derived examples. Widely used sequence-clustering approaches such as CD-HIT and MMseqs2 are designed to reduce redundancy and cluster biological sequences at identity thresholds; the formatter can use equivalent local tooling or library implementations for leakage grouping, with exact parameters recorded in the manifest.

Split policy:

- Default: 80% train, 10% validation, 10% test by leakage group.
- Stratify by vector profile where possible.
- If a vector profile has too few independent leakage groups, keep it train-only or validation-only with a warning rather than forcing leaky test examples.
- The test split should be frozen for a Phase 2 data snapshot and never used for template retrieval in training examples.

Required leakage diagnostics:

- Count exact duplicate clusters and their split assignment.
- Count sequence-similarity clusters and largest cluster sizes.
- Report nearest cross-split sequence similarity for validation/test targets.
- Report publication/depositing-lab groups spanning multiple raw sources.
- Report skipped examples by reason.
- Fail the formatter if any exact sequence hash appears in more than one split.
- Fail the formatter if any connected leakage component appears in more than one split.

## Dataset Statistics To Report

The formatter must produce `stats.md` and machine-readable `stats.json` for every snapshot.

Report at minimum:

- Input snapshot ID and formatter version.
- Total plasmid records loaded.
- Records excluded by reason: invalid DNA, incomplete annotation, no sequence, source/license not trainable, unknown/non-engineered profile, no context, no valid template, leakage conflict.
- Emitted triplet count by split.
- Emitted triplet count by source and source license status.
- Emitted triplet count by vector profile.
- Emitted triplet count by organism annotation, marker, promoter, origin, topology, and length bucket.
- Median, min, max, and percentile lengths for target and template sequences.
- Template-target semantic similarity distribution.
- Template-target sequence-similarity distribution.
- Number of unique target plasmids and unique template plasmids.
- Number and size distribution of leakage groups.
- Cross-split exact duplicate count, which must be zero.
- Cross-split high-similarity neighbor count above configured thresholds.
- Number of examples using `ExperimentalContext` versus composed-document-derived context.
- Number of examples with each quality flag.
- Small fixed sample of redacted example headers for audit: example ID, split, vector profile, target ID, template ID, context source, and exclusion-free quality flags. Do not print full sequences in markdown reports unless explicitly requested.

## Edge Cases

- No valid template: skip target; do not use the target itself as template.
- Only near-duplicate templates exist: skip target for validation/test; optionally keep a train-only example if the duplicate is in the same leakage group and the target/template distinction remains meaningful, but default to skip.
- Circular plasmid rotations: normalize sequence representation or use rotation-aware exact duplicate checks. Two circular sequences can be identical with different starting bases.
- Reverse-complement duplicates: check reverse complements when computing exact/near duplicate clusters.
- Linear records: keep only if topology is known and the vector profile supports linear representation; otherwise skip first-pass training.
- Ambiguous bases: canonical schema accepts only ACGT; records with N/IUPAC ambiguity should be excluded until a tokenizer and validation policy explicitly supports them.
- Missing publication/depositing lab: fall back to accession and sequence-similarity grouping; record null provenance in `leakage_group`.
- Multiple plasmids in one `ExperimentalContext`: emit one target example per plasmid only if context can be linked unambiguously; otherwise skip or flag for human curation.
- Very long plasmids beyond model context length: keep structured examples, but mark `requires_chunking=true` for model-specific preprocessing.
- Target identity in text: remove plasmid name/accession/DOI from `context.text`; these may remain in audit/provenance fields.
- Biosecurity-sensitive records: exclude from training unless the project has a documented screening and approval policy. `SYSTEM_DESIGN.md` Section 11.6 requires screening requests/designs implicating sequences of concern.
- Addgene/commercial-license uncertainty: source records with unresolved training rights must not enter train/validation/test artifacts intended for model fitting.

## Implementation Plan

1. Define a formatter module behind a CLI such as `make format-generation-data SNAPSHOT=<id>` or a direct Python entrypoint. Keep it out of API, worker, and frontend code.
2. Add a Pydantic schema for `TrainingTriplet` and nested `ContextPayload`, `TemplatePayload`, `TargetPayload`, and `LeakageGroup` objects, or implement equivalent validation local to the formatter if avoiding core schema changes in the first pass.
3. Load Phase 0 plasmids and annotations from the same storage path used by quality/reprocess jobs for the selected snapshot.
4. Reuse `compose_plasmid_document(plasmid, annotated_sequence)` for fallback context and semantic retrieval text.
5. Build a candidate index with fields needed for structured filters and vector-profile stratification.
6. Compute leakage connected components from publication DOI, source/depositor fields when available, accession clusters, exact sequence hashes, reverse-complement hashes, circular-rotation-aware hashes, and approximate sequence-similarity clusters.
7. Assign split by leakage component with deterministic hashing and profile-aware balancing.
8. For each target, generate context, retrieve/select an in-split template, validate schema, and write the JSONL line.
9. Emit manifest, stats, skip-reason table, and leakage diagnostics.
10. Add unit tests for deterministic split assignment, target-name redaction from context, no same-ID template, no cross-split exact duplicate, skip behavior for incomplete annotations, and stable JSONL serialization.
11. Add a tiny fixture-based smoke test using public/curated toy records only; do not require network, GPU, model download, API server, worker, or frontend.
12. After implementation, run the formatter on the current corpus and report whether the emitted dataset is sufficient only for a dry-run/spike or for actual fine-tuning. Given current Phase 0 status, expect dry-run scale unless the corpus has grown substantially.

## Questions For Human

No blocking biology question prevents implementation of the conservative formatter.

Non-blocking policy questions to resolve before using the dataset for actual fine-tuning:

1. Which sources are approved for model training, especially Addgene-derived records, versus retrieval/display only?
2. Should unknown but complete natural plasmids ever be included as targets, or should Phase 2 train only on engineered vector profiles?
3. What sequence-identity threshold should define a near-duplicate leakage cluster for plasmids: 95%, 98%, 99%, or a profile-specific rule?
4. Should template-target pairs be required to share vector profile, or may the formatter include cross-profile examples for adaptation tasks after explicit labeling?
5. When depositing lab is unavailable, is publication/accession/sequence-similarity clustering sufficient for the first held-out evaluation set?
6. Should context text include source/publication-derived application claims if they come only from broad GenBank definitions or Addgene descriptions, or only from extracted `ExperimentalContext` rows?
