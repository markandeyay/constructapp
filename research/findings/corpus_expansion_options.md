> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Corpus Expansion Options for Phase 2 Authorization

Date: 2026-06-17

Scope: This note evaluates candidate sources for future Phase 2 corpus expansion. It does not authorize ingestion, redistribution, or dependency changes. Estimates are planning ranges only and should be rechecked immediately before any authorized implementation.

## Executive View

| Option | Estimated useful yield | License posture | Integration cost | Overall recommendation if authorized |
| --- | ---: | --- | --- | --- |
| Continued NCBI GenBank expansion via refined queries | High: tens of thousands to low hundreds of thousands of candidate plasmid/vector records before filtering | NCBI places no restrictions on GenBank data, but submitters may assert patent/copyright/IP claims | Low to medium | Best primary expansion path; use curated query sets, safety filters, provenance, and deduplication |
| iGEM Registry of Standard Biological Parts | Medium: up to 70,000+ documented parts in registry, likely lower after sequence/license/quality filters | Public registry; classic site is archive/read-only. Open-license status needs record-level confirmation before redistribution | Medium | Useful as a synthetic-biology parts metadata source only after license confirmation and quality scoring |
| JCVI plasmid collections | Low to medium: likely small targeted sets rather than bulk corpus source | Unclear for bulk reuse; Addgene public search showed no direct `JCVI` / `J. Craig Venter Institute` plasmid collection match | High | Do not prioritize as a bulk source; treat as targeted literature/accession follow-up only |
| Individual lab repositories on Zenodo/Dryad | Medium: dozens to hundreds of datasets; yield depends on manual discovery | Zenodo record-level license; Dryad datasets are CC0 | High | Use selectively for high-value raw/benchmark data with explicit license/provenance review |
| Synthetic data augmentation | Configurable: hundreds to millions of generated examples | Internally controlled if generated from permitted templates/models; must avoid laundering restricted source data | Medium | Use for validation robustness and parser/model stress tests, not as a substitute for real annotated records |

## 1. Continued NCBI GenBank Expansion via Refined Queries

### Estimated Yield

High. A quick ESearch count for `plasmid[Title] AND complete sequence[Title]` in `nuccore` returned 173,415 candidate records on 2026-06-17. Broader `plasmid[Title]` matched 926,150 records in the same response's translation set. After filters for complete circular molecules, non-human/privacy constraints, length bounds, feature richness, deduplication, and exclusion of low-value fragments, a realistic usable yield is likely tens of thousands to low hundreds of thousands of records.

Refined query families worth evaluating if authorized:

| Query family | Purpose | Expected effect |
| --- | --- | --- |
| `plasmid[Title] AND complete sequence[Title]` | High-precision complete plasmids | Good baseline, manageable false positives |
| `plasmid[Filter]` or plasmid molecule metadata where available | Broader plasmid recall | Higher yield, more cleanup |
| `vector[Title] AND complete sequence[Title]` | Capture cloning/expression vectors not titled as plasmids | Adds useful engineered constructs, higher ambiguity |
| Organism-bounded plasmid searches, e.g. bacterial host filters | Reduce irrelevant eukaryotic or environmental noise | Improves downstream annotation consistency |
| Exclusions for `patent`, `synthetic construct` subclasses, environmental samples, WGS/TSA where inappropriate | Reduce legal/quality/scope risk | Lower yield, higher precision |

### Licensing Terms

NCBI states that it places no restrictions on use or distribution of GenBank data. It also warns that submitters may claim patent, copyright, or other IP rights and that NCBI cannot assess those claims or provide unrestricted permission for submitted information.

Practical implication: public GenBank data is the strongest open-access candidate, but Phase 2 should preserve accession-level provenance and should not imply freedom from patents, MTAs, or other third-party claims.

### Access Mechanism

Use NCBI E-utilities and/or FTP releases. E-utilities provide stable programmatic search and retrieval via `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`. NCBI guidance limits unkeyed E-utilities traffic to 3 requests/second and API-key traffic to 10 requests/second by default, with `tool` and `email` registration expected for production software. For large jobs, use Entrez History and batched `EFetch`, or consume GenBank release files from FTP where practical.

### Expected Annotation Quality

Medium to high. GenBank records are processed for data integrity and quality, but annotation depth is submitter-dependent. Complete plasmid records often include `source`, `CDS`, `gene`, `misc_feature`, `rep_origin`, and antibiotic-resistance annotations, but naming conventions vary and engineered constructs can be underannotated.

### Integration Cost

Low to medium. Existing GenBank-like parsers and provenance conventions should adapt with query configuration, batching, deduplication, and quality gates. The main work is not file parsing; it is query design, filter validation, rate-limit safe harvesting, and accession-level auditability.

### Risks

| Risk | Mitigation |
| --- | --- |
| False positives from broad title searches | Maintain versioned query manifests and sample-review each query family |
| Patent/IP claims despite NCBI's no-restriction posture | Keep accession provenance, exclude patent-heavy subsets unless legal review approves |
| Duplicate or near-duplicate plasmids | Normalize sequence hashes and accession/version lineage |
| Safety/scope concerns for hazardous genes or pathogens | Apply organism, feature, and keyword exclusion filters before inclusion |
| Annotation inconsistency | Score records for feature completeness and normalize feature vocabularies |

### Recommended Use if Authorized

Prioritize as Phase 2's primary real-data expansion source. Start with high-precision complete plasmid/vector query sets, run a 500- to 1,000-record pilot, review yield and annotation quality, then scale using rate-limit compliant batch retrieval. Store query string, retrieval date, accession.version, source URL, and sequence hash for every record.

## 2. iGEM Registry of Standard Biological Parts

### Estimated Yield

Medium. The legacy `parts.igem.org` registry states that the catalog has over 70,000 documented parts and that core part data, including sequences, descriptions, and metadata, has been copied to the modern registry. The useful corpus yield will be lower after removing parts without sequence, weak documentation, duplicate team submissions, deprecated parts, or ambiguous licensing.

Planning range: 10,000 to 50,000 potentially useful parts after basic filtering; lower if requiring strong experimental characterization.

### Licensing Terms

Open-license status is promising but not sufficiently confirmed for automated corpus ingestion from the public pages reviewed here. The classic registry is publicly viewable and searchable but now archive/read-only. Before using iGEM data, Phase 2 authorization should require confirmation from iGEM's current terms/API documentation or written permission covering sequence, descriptions, metadata, redistribution, transformations, and attribution requirements.

If iGEM content is under a Creative Commons share-alike license for some pages, share-alike and attribution obligations could affect corpus redistribution. Record-level or site-wide license confirmation is therefore a blocker, not an implementation detail.

### Access Mechanism

Possible mechanisms:

| Mechanism | Notes |
| --- | --- |
| Modern registry at `registry.igem.org` | JavaScript app; may require API discovery or direct export from iGEM |
| Legacy `parts.igem.org` | Public archive; pages remain viewable/searchable, but submission/editing disabled |
| Registry API/help pages | Legacy help references a Registry API, but endpoint details need confirmation |
| Direct iGEM contact | Best path for license clarity and bulk export format |

### Expected Annotation Quality

Variable. Strengths include standardized part identifiers, categories, sequence fields, descriptions, team provenance, and sometimes experience/characterization pages. Weaknesses include student/team-authored descriptions, inconsistent experimental validation, obsolete parts, partial records, and mixed assembly standards.

### Integration Cost

Medium. iGEM part schema will not map cleanly to GenBank features. Integration would require a separate source adapter, part-type normalization, sequence validation, provenance fields for team/year/part ID, and a quality scoring model that separates sequence availability from characterization evidence.

### Risks

| Risk | Mitigation |
| --- | --- |
| License ambiguity for sequences and descriptions | Do not ingest until license or permission is explicit |
| Inconsistent annotation and characterization | Add quality tiers: sequence-only, described, characterized, distribution-verified |
| API instability during registry migration | Prefer official export/API or written bulk-access guidance |
| Duplicate/subpart/composite part relationships | Preserve hierarchy and avoid treating composites as independent novel parts without lineage |
| Biosecurity and misuse concerns for some parts | Apply the same safety filters used for GenBank |

### Recommended Use if Authorized

Use only after explicit license/access confirmation. If approved, ingest as a parts-specific corpus with quality tiers rather than mixing directly into GenBank-derived records. Prioritize parts with sequence, clear type, source team/year, and evidence of characterization or distribution-kit QC.

## 3. JCVI Plasmid Collections

### Estimated Yield

Low to medium. Publicly discoverable bulk plasmid collection material appears limited. Addgene public catalog searches for `JCVI` and `J. Craig Venter Institute` returned zero plasmid matches during this review. JCVI-related synthetic-biology publications do expose valuable supplemental datasets, such as the minimal-genome `JCV-syn3.0` work with a 531 kbp genome and 473 genes, but that is not the same as a reusable plasmid collection.

Planning range: targeted handfuls to hundreds of records if accessions, supplemental files, or collaborator repositories are identified; not a bulk expansion source without direct JCVI or repository support.

### Licensing Terms

Unclear for bulk corpus reuse. Publication abstracts and supplemental metadata may be accessible, but article, supplement, strain, plasmid, and genome sequence rights can differ. Addgene distribution, if relevant for any future identified plasmids, would involve Addgene terms, material transfer constraints, and sequence access terms rather than a simple open-data license.

### Access Mechanism

Possible mechanisms:

| Mechanism | Notes |
| --- | --- |
| Publication supplements | Good for targeted metadata; not necessarily open corpus material |
| GenBank accessions linked from JCVI publications | Best legal/technical route when records are deposited in GenBank |
| Direct JCVI contact | Needed for any named plasmid collection or bulk export not publicly documented |
| Addgene | Public searches did not find direct JCVI collection matches; recheck if specific plasmid names emerge |

### Expected Annotation Quality

High for curated JCVI publications and GenBank submissions, especially minimal-genome and synthetic-cell datasets. Annotation quality for any actual plasmid constructs would depend on whether records include full maps, features, and sequence verification.

### Integration Cost

High relative to yield. Discovery would be manual, publication-driven, and likely heterogeneous. If sequences are already in GenBank, they should enter through the GenBank pipeline rather than a special JCVI source.

### Risks

| Risk | Mitigation |
| --- | --- |
| Confusing publication supplements with reusable sequence corpus rights | Require license review per dataset |
| Low yield after substantial manual search | Treat as targeted enrichment only |
| MTA or biological material constraints | Use only public sequence records with clear reuse terms; do not infer rights from physical material availability |
| Synthetic-cell content may raise scope/safety review needs | Add explicit Phase 2 safety authorization gate |

### Recommended Use if Authorized

Do not prioritize as a standalone corpus expansion path. Use JCVI as a targeted source list for accession discovery, especially where JCVI records already exist in GenBank or where publication supplements have explicit open licenses.

## 4. Individual Lab Repositories Publishing Raw Data on Zenodo/Dryad

### Estimated Yield

Medium but uneven. Likely yield is dozens to hundreds of relevant datasets and thousands to tens of thousands of files or records, depending on search terms and manual curation. High-value examples may include raw plasmid maps, sequencing reads, construct libraries, benchmark annotation sets, or supplementary CSV/FASTA/GenBank files from individual labs.

### Licensing Terms

Zenodo requires users to specify a license for publicly available files; reuse is governed by the license chosen for the deposit. Metadata is CC0 except email addresses. Zenodo supports open, embargoed, restricted, and closed files.

Dryad requires datasets to be published under the CC0 instrument and does not accept files with licensing terms incompatible with CC0. Dryad terms state users are allowed and encouraged to reuse datasets, while citation is expected as scholarly norm.

Practical implication: Dryad is cleaner legally but less domain-specific. Zenodo has broader coverage but requires record-level license filtering.

### Access Mechanism

| Repository | Mechanism |
| --- | --- |
| Zenodo | Search UI, REST API, OAI-PMH, DOI landing pages, downloadable files up to record limits |
| Dryad | Search UI, DOI landing pages, downloadable datasets, curation metadata |

Discovery queries should combine biological terms (`plasmid`, `vector`, `construct`, `genbank`, `snapgene`, `fasta`, `synthetic biology`, `parts library`) with file-type and license filters where APIs support them.

### Expected Annotation Quality

Highly variable. Some lab datasets include rich README files, schemas, Sanger/NGS validation, and publication context. Others are raw archives with inconsistent naming, proprietary map formats, missing feature annotations, or insufficient machine-readable metadata.

### Integration Cost

High. Each dataset may need individual license checks, file-type handling, decompression, README interpretation, schema inference, and provenance review. This is better handled as a curated intake queue than a broad crawler.

### Risks

| Risk | Mitigation |
| --- | --- |
| Record-level license variability on Zenodo | Ingest only allowlisted licenses approved by counsel/project policy |
| Raw data lacks standardized annotations | Require minimum metadata schema and assign lower quality tier when absent |
| Hidden privacy, controlled-access, or embargo constraints | Use only open files; preserve DOI/license/access date |
| Proprietary file formats | Prefer FASTA, GenBank, SBOL, CSV/TSV, JSON, and README; avoid formats that require closed tooling |
| Manual curation burden | Start with a small allowlisted set of high-value datasets |

### Recommended Use if Authorized

Use selectively as a high-value enrichment path, not as the first bulk expansion source. Start with Dryad CC0 datasets and Zenodo records with explicit permissive licenses, clear README files, and machine-readable sequence/annotation formats. Require per-dataset intake notes.

## 5. Synthetic Data Augmentation

### Estimated Yield

Configurable. A generator can produce hundreds to millions of examples, but the useful yield is bounded by biological realism and evaluation goals. Synthetic data is best measured by coverage of edge cases, feature combinations, parser formats, and annotation-normalization scenarios rather than raw count.

Candidate augmentation types:

| Type | Useful for | Notes |
| --- | --- | --- |
| Format perturbations | Parser robustness | Vary GenBank formatting, feature ordering, qualifiers, line wrapping |
| Annotation perturbations | Normalization and entity extraction | Synonyms, missing qualifiers, inconsistent capitalization |
| Construct templates | Model training/evaluation | Use simple permitted templates for promoters, CDS, terminators, origins, selectable markers |
| Negative controls | Validation and safety filters | Non-plasmid sequences, fragments, malformed records, duplicate records |
| Synthetic edge cases | Regression tests | Circularity flags, overlapping features, ambiguous bases, unusual topology |

### Licensing Terms

Internally generated data can be project-controlled if it is created from scratch or from sources whose licenses permit derivative generation. It must not be used to launder restricted third-party data, reproduce proprietary plasmid maps, or obscure source attribution. If templates are derived from public records, preserve source/license lineage and ensure derivative rights are compatible.

### Access Mechanism

Internal generator scripts or fixtures, ideally deterministic with seed values and documented templates. No external dependency is required unless using external models or source templates, which would need separate authorization.

### Expected Annotation Quality

High consistency but artificial. Synthetic records can be perfectly annotated against their templates, making them useful for tests and calibration. They will underrepresent real-world naming errors, unexpected biology, and submitter-specific quirks unless those are deliberately modeled.

### Integration Cost

Medium. Requires generator design, schema alignment, seed/provenance tracking, and validation that synthetic examples do not contaminate real-data metrics. Lower integration cost if scoped to tests; higher if used in model training with weighting and provenance controls.

### Risks

| Risk | Mitigation |
| --- | --- |
| Inflated metrics due to template leakage | Keep synthetic data split-aware and report real-data metrics separately |
| Unrealistic biological combinations | Define allowed templates with domain review |
| License laundering from restricted sources | Use only scratch-built or approved-source templates with provenance |
| Confusion with real records | Mark every synthetic record with explicit synthetic provenance and exclude from real corpus counts |

### Recommended Use if Authorized

Authorize for validation fixtures, robustness testing, and controlled augmentation only. Do not count synthetic records as corpus expansion equivalent to real-world records. Keep a separate namespace, deterministic seeds, and explicit synthetic labels.

## Cross-Source Recommendation

If Phase 2 is authorized, use a staged source policy:

1. Begin with refined GenBank expansion because it has the highest yield, clearest access mechanism, and established biological sequence format.
2. Run a parallel license clarification track for iGEM before any ingestion.
3. Treat Zenodo/Dryad as curated enrichment with per-dataset intake records.
4. Use JCVI only as targeted accession discovery unless a documented open plasmid collection is found.
5. Build synthetic augmentation as a separate test/robustness asset with strict labeling.

## Source Notes

| Source | Relevant facts used |
| --- | --- |
| NCBI GenBank overview, `https://www.ncbi.nlm.nih.gov/genbank/` | GenBank is an annotated collection of public DNA sequences; releases every two months; access via Entrez, BLAST, E-utilities, FTP; NCBI places no restrictions but submitter IP claims may exist |
| NCBI E-utilities help, `https://www.ncbi.nlm.nih.gov/books/NBK25497/` | E-utilities URL, request-rate guidance, API-key behavior, batching/history guidance |
| iGEM legacy registry, `https://parts.igem.org/Main_Page` | Classic registry is archive/read-only; core data copied to modern registry; catalog states over 70,000 documented parts |
| iGEM help, `https://parts.igem.org/Help:Contents` | Registry has help pages for search, catalog, distributions, QC, part documentation, sequence/features, and API references |
| Addgene public searches, `https://www.addgene.org/search/catalog/plasmids/?q=JCVI` and `...?q=J.%20Craig%20Venter%20Institute` | No direct public plasmid matches for those searches during review |
| Science article page, `https://science.org/doi/10.1126/science.aad6253` | JCVI-syn3.0 publication describes 531 kbp, 473-gene synthetic minimal genome and downloadable supplementary database |
| Zenodo policies, `https://about.zenodo.org/policies/` | Public files require user-specified licenses; reuse follows record license; metadata CC0 except email addresses; access can be open, embargoed, restricted, or closed |
| Dryad requirements and terms, `https://datadryad.org/stash/requirements`, `https://datadryad.org/stash/terms` | Dryad requires CC0-compatible data; users may reuse datasets; citation expected; file and curation requirements documented |
