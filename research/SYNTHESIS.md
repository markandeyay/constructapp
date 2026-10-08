> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Phase R Synthesis

Status: Phase R research complete pending human review.

This synthesis distills Tracks A-J into build decisions. It is grounded in the cited findings files under `research/findings/`; those files remain the detailed source of record.

## Required Answers From SYSTEM_DESIGN Section 4.5.2

### 1. Plasmid structure

A valid generic expression plasmid needs at least a propagation module and, when expression is requested, an expression cassette. The propagation module usually includes a compatible origin of replication and bacterial selectable marker. The expression cassette normally has a host-compatible promoter upstream of the GOI/MCS, correct GOI orientation and reading frame, and a downstream terminator or polyA element. Mammalian constructs often combine an E. coli propagation backbone with a mammalian expression cassette and sometimes a separate experimental marker. Circular topology and strand-aware coordinates must be first-class data, not display-only metadata. [Source: Track A, `research/findings/plasmid_biology.md`; Track B, `research/findings/design_rules.md`; Track F, `research/findings/representation.md`]

Vector-specific rules are mandatory. Lentiviral, AAV, shRNA, bacterial-expression, mammalian-expression, plant, yeast, CRISPR, and other designs have different required parts and failure modes, so the validator should use per-vector profiles rather than a single global "valid plasmid" rule. [Source: Track A, `research/findings/plasmid_biology.md`; Track B, `research/findings/design_rules.md`]

### 2. Design rules

Constructs fail when biological compatibility, sequence syntax, assembly strategy, propagation, or synthesis constraints are violated. Core codifiable rules include promoter/host/transcript compatibility, host-appropriate translation initiation context, correct cassette order and strand, in-frame tags/linkers/GOI joins, downstream terminator/polyA, compatible ORI and marker, cloning-method-specific restriction-site rules, codon-usage scoring against the target host, repeat/instability screening, and synthesis-provider GC/homopolymer/repeat thresholds. [Source: Track B, `research/findings/design_rules.md`; Track G, `research/findings/validation_tools.md`]

Provider thresholds conflict enough that synthesis readiness must be profile-driven. Twist, IDT, and GenScript publish overlapping but non-identical limits for GC content, repeats, homopolymers, and sequence-complexity review. The default should be conservative until the user selects a provider. [Source: Track B, `research/findings/design_rules.md`; Track G, `research/findings/validation_tools.md`]

### 3. Sequence generation

The generator should start from an autoregressive DNA model, not an encoder-only genomic model. Evo 2 7B is the strongest initial candidate for whole-plasmid experiments because it is autoregressive, single-nucleotide resolution, long-context, all-domain, and appears Apache-2.0 in the open local repository/model-card path. Carbon-3B is a credible lower-cost Apache-2.0 baseline with metadata-conditioned generation. DNABERT, DNABERT-2, Nucleotide Transformer, HyenaDNA, Caduceus, and GenSLM are better fits for embeddings, scoring, or validation unless a specific generative use is proven. [Source: Track C, `research/findings/sequence_models.md`]

No reviewed base model should be assumed to produce synthesis-ready plasmids directly. Whole-plasmid generation must be retrieval-grounded, component-aware, re-annotated, and passed through deterministic validation before user export. Model and data licenses are hard gates; non-commercial or unclear checkpoint licenses cannot be used in commercial production without legal clearance. [Source: Track C, `research/findings/sequence_models.md`; Track I, `research/findings/architecture_patterns.md`]

### 4. Prior art

OriGen demonstrates learned generation of functional plasmid origins/replicons, including E. coli validation, but does not solve whole annotated expression-plasmid design. PlasmidGPT is relevant for plasmid-like sequence generation and embeddings, but its public validation and license status are insufficient for direct production reliance. Benchling, SnapGene, PlasMapper, pLannotate, VectorBuilder, Asimov Kernel, and Addgene cover parts of the workflow: manual CAD, annotation, maps, cloning simulation, component libraries, order handoff, or limited compiler-style design. [Source: Track D, `research/findings/prior_art.md`]

The product gap is the integrated workflow: plain-English experimental goal, structured intent, retrieval of grounded real plasmids, complete annotated design, deterministic validation, primers, synthesis-ready export, biosecurity screening, and provenance. No surveyed public source establishes that complete end-to-end capability. [Source: Track D, `research/findings/prior_art.md`]

### 5. Data

Addgene is the best contextual plasmid source because its approved API/bulk routes expose genes, species, experimental use, vector type, expression, promoters, resistance markers, cloning metadata, article fields, depositor comments, sequence files, and terms. It is approval-gated and license-scoped; ingestion must require an API token plus explicit accepted-license configuration, and records must preserve source terms and sequence provenance. Addgene sequence completeness varies across NGS full sequences, depositor full sequences, depositor partial sequences, and Sanger insert-verification records. [Source: Track E, `research/findings/data_sources.md`]

NCBI GenBank is the broad annotated sequence source. Use Entrez ESearch/EPost/EFetch with registered `tool` and `email`, conservative throttling, optional API key, and `rettype=gb` for feature-bearing ingestion. GenBank places no broad NCBI restrictions on use, but submitter IP claims remain possible, so commercial training clearance is still a review item. [Source: Track E, `research/findings/data_sources.md`]

### 6. Representation

Use a canonical internal sequence model with raw DNA, topology, feature intervals, strand, feature type, label, qualifiers, evidence, and provenance. Internally use zero-based half-open coordinates with explicit import/export conversions for GenBank and GFF3. Preserve original source locations because GenBank/INSDC annotations can include joins, complements, fuzzy bounds, and origin-wrapping features. [Source: Track F, `research/findings/representation.md`]

Retrieval should store composed text documents, structured metadata, sequence windows, and component-level chunks. Validation must run on exact bases and coordinates, not token IDs, because restriction sites, frames, primers, overlaps, and circular wraparound are base-level properties. Circular plasmids need rotation, origin-aware slicing, and cross-origin utilities. [Source: Track F, `research/findings/representation.md`]

### 7. Validation

The deterministic validation engine should be built as independent checks with PASS/WARN/FAIL results, coordinates, affected features, rule IDs, and remediation text. Start with:

- Restriction-site conflicts via Biopython `Bio.Restriction` plus version-pinned REBASE-derived metadata.
- Codon usage scoring via local HIVE-CUTs/Kazusa-style tables and Biopython CAI, without automatic rewrite in validation.
- Repeat/instability checks for homopolymers, direct/tandem/inverted repeats, palindromes, repeat density, and local GC windows.
- Regulatory compatibility via local curated rule tables seeded from Addgene guidance, EPD/JASPAR/RegulonDB where relevant, and plasmid-specific promoter catalogs.
- Provider-profile synthesis readiness for Twist, IDT, and GenScript-style constraints.
- Optional therapeutic/gene-therapy compliance flags coordinated with the biosecurity layer. [Source: Track G, `research/findings/validation_tools.md`; Track B, `research/findings/design_rules.md`; Track J, `research/findings/biosecurity.md`]

### 8. Visualization

Use `seqviz` as the Phase 4 default renderer because it supports circular, linear, and combined views and maps naturally from `AnnotatedSequence` to `{ name, seq, annotations, viewer }`. Keep visualization behind a frontend adapter, e.g. `PlasmidMapView`, so backend/API contracts remain based on the canonical `AnnotatedSequence` rather than viewer-specific props. Use deterministic colors by feature type. Test origin-spanning annotations before implementation because this pass did not verify `seqviz` behavior for features crossing base 1. [Source: Track H, `research/findings/visualization.md`]

Open Vector Editor is the likely future choice for browser editing, CGView.js for dense circular genome/plot export, and JBrowse/igv.js for genome-browser workflows. They are not the simplest MVP map renderer. [Source: Track H, `research/findings/visualization.md`]

### 9. Building a system of this scope

Use a layered, interface-first architecture: ingestion/normalization, canonical schemas, retrieval/indexing, intent parsing, recommendation generation, sequence generation, deterministic validation, biosecurity screening, export/assembly, API/jobs, and UI. RAG improves grounding and provenance but does not prove correctness; biological validation and screening are separate gates. [Source: Track I, `research/findings/architecture_patterns.md`]

Retrieval evaluation and generation evaluation must be separate. Track top-k retrieval, source faithfulness, recommendation quality, biological validation pass rate, synthesis readiness, latency, cost, and regression against curated prompts. Use deterministic fakes for every model/infrastructure interface. vLLM is the likely first real serving target for autoregressive DNA models if compatible; Triton is a later option for heterogeneous model serving. Quantized models must pass the same biological evals as full precision. [Source: Track I, `research/findings/architecture_patterns.md`]

### 10. Biosecurity and compliance

Every prompt, generated sequence, export, and synthesis handoff needs biosecurity handling. Prompt screening is triage, not a substitute for sequence screening. Add a mandatory `BiosecurityScreening` interface before export/order handoff, with states such as `CLEAR`, `REVIEW_REQUIRED`, `BLOCKED`, and `SCREENING_UNAVAILABLE`. No synthesis-ready export should proceed unless screening is clear and provider-side screening/attestation is recorded. [Source: Track J, `research/findings/biosecurity.md`]

Production screening must support current U.S. nucleic-acid screening expectations, including sequence-of-concern review, customer legitimacy, translation-aware screening where applicable, audit logging, data minimization, and a human-review path. IBBIS Common Mechanism or provider APIs are plausible implementation candidates, but their limitations for short sequences, proteins, ambiguous codons, and specialized oligo orders need fallback handling. Compliance output should be advisory and not a substitute for institutional biosafety, export-control, select-agent, or synthesis-provider review. [Source: Track J, `research/findings/biosecurity.md`]

## Build Decisions To Carry Forward

- Phase 0 should build schemas and parsers around explicit topology, zero-based half-open coordinates, feature provenance, and source/legal metadata.
- Phase 0 ingestion should implement Addgene and NCBI adapters separately, with Addgene disabled until an approved license/token is configured.
- Phase 1 should be retrieval-first, using composed plasmid documents plus structured filters and provenance-preserving component chunks.
- Phase 2 should benchmark Evo 2 7B and Carbon-3B behind `SequenceGenerator`; do not depend on unclear/non-commercial model weights.
- Phase 3 should implement deterministic checks as pure functions with provider profiles and vector-type-specific rule tables.
- Phase 4 should use `seqviz` through an adapter component, not expose viewer-specific shapes through the backend contract.
- Cross-cutting safety must include a dedicated biosecurity screening interface before export/order handoff.

## Questions For The Human

- Which synthesis provider profile should be the default for "synthesis-ready" when no provider is selected: conservative cross-provider, Twist, IDT, GenScript, or user-selected only?
- Should the first product only score codon usage, or may it automatically rewrite coding sequences after explicit user consent?
- For commercial use, can Addgene-derived records be used for model training under the eventual approved data access license, or only for retrieval/display?
- Should GenBank-derived records be treated as commercially trainable by default, or should submitter-IP caveats require legal review before training?
- Should Evo 2 7B be the first generation candidate, with Carbon-3B as fallback, pending infrastructure and license review?
- Should the platform operate as a regulated-like biosecurity checkpoint before provider handoff, even where direct legal duties attach primarily to synthesis providers or procurement?
- What is the current controlling U.S. nucleic-acid screening framework after the May 5, 2025 Executive Order directive to revise or replace the 2024 framework?
- For circular plasmids, where should canonical base 1 be placed in generated designs: source record origin, ORI start, MCS/cloning site, or synthesis-provider convention?
- Should the MVP map be read-only, or should browser-side feature/sequence editing be in scope?
- Which vector types are in the first supported validity profile set: generic mammalian expression, lentiviral, AAV, bacterial expression, CRISPR/shRNA, or another subset?
