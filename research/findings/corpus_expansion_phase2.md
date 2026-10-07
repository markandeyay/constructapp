# Corpus Expansion Phase 2

## Summary

The highest-yield, lowest-implementation-risk candidate for CORPUS-2 is an NCBI RefSeq plasmid ingestion lane, followed by a stricter GenBank engineered-vector lane. RefSeq is not a vector-specific database, so it should not replace engineered-vector curation, but it gives the largest public, stable, provenance-preserving plasmid sequence expansion available through the same NCBI tooling already used by Construct.

Recommended CORPUS-2 target: ingest NCBI `srcdb_refseq[PROP]` plasmid records first as a broad public plasmid pretraining/evaluation corpus, then run separate GenBank engineered-vector presets for cloning/expression/reporter/shuttle vectors. Keep non-NCBI sources behind explicit license/provenance gates unless their terms clearly allow Construct's intended training use.

Key finding: the current 206-record local corpus is tiny relative to public NCBI plasmid-scale records. Read-only Entrez count probes on 2026-06-02 found about 71k RefSeq plasmid-title records in the 1 kb to 50 kb range, about 38k RefSeq complete plasmid-title records, about 55k broad GenBank plasmid-title records after WGS/TSA/CON exclusions, and about 10k GenBank engineered-vector-title records.

## Current Corpus Baseline

- Current local corpus baseline for this task: 206 records after a single Entrez query expansion.
- Earlier project findings show why this is insufficient for generation: broad `plasmid complete sequence` style queries admit many natural clinical/environmental plasmids, and older quality reports showed high `unknown` profile rates and sparse promoter/terminator annotations.
- Existing Construct notes already recommend moving from broad vector-title matching to component-gated Entrez queries and preserving raw GenBank artifacts before parsing.
- Generation prep needs two different public data lanes: broad sequence diversity for plasmid-length sequence modeling, and smaller high-confidence engineered-vector data for component/layout validity.

## Candidate Sources

| Priority | Source | Estimated yield | Quality/risk | Licensing/provenance | Implementation notes |
| --- | ---: | ---: | --- | --- | --- |
| 1 | NCBI RefSeq plasmid collection | About 38k complete plasmid-title hits; about 71k broad plasmid-title hits | Medium-high sequence quality, medium engineered-vector relevance | NCBI/RefSeq public access; GenBank/NCBI data-use caveats still require IP provenance fields | Best CORPUS-2 first implementation lane |
| 2 | NCBI GenBank engineered-vector title/component queries | About 10k vector-title hits; likely hundreds to low thousands high-confidence after parser gates | High relevance when gated; variable submitter annotation | NCBI places no restrictions on GenBank distribution, but submitter IP claims may exist | Best supervised engineered-vector expansion after RefSeq |
| 3 | NCBI publication-linked methods/vector queries | About 958 count-probe hits | Medium-high relevance; journal fields reduce some noise but `Gene` and `Plasmid` are broad | Same GenBank caveats | Good second NCBI preset, not first |
| 4 | NCBI depositor/lab/vendor name queries | About 471 hits for Addgene/Invitrogen/Thermo/Clontech/Takara/Promega/NEB/Novagen plus vector terms | Potentially high-quality but field matching is noisy | Same GenBank caveats; depositor names in NCBI are not a clean license grant | Use only as audit/curated seed lane |
| 5 | SEVA plasmids | About 184 NCBI hits for SEVA/pSEVA; SEVA site has curated canonical plasmids with GenBank/SBOL links | High engineered-vector relevance for modular bacterial vectors | SEVA encourages open access and no MTA for academic/nonprofit distribution, but disclaims commercial/industrial IP responsibility | Good curated bacterial-vector subset, legal review before commercial training |
| 6 | Yeast vector sources via NCBI plus SGD metadata | About 173 yeast-vector query hits; pRS/pYES exact probes much smaller | Useful for yeast shuttle/vector profiles; SGD itself is not primarily a plasmid sequence repository | SGD site footer indicates CC BY 4.0 for site content; NCBI records carry NCBI caveats | Use NCBI for sequences, SGD for yeast gene/context metadata only |
| 7 | iGEM Registry/BioBrick parts | Registry claims 70k+ documented parts; NCBI exact-ish BioBrick backbone probe about 238; iGEM term probe about 1,393 | High synthetic-biology relevance, but many entries are parts rather than complete plasmids | License/terms for training use were not confirmed from accessible pages; legacy registry is archive/read-only | Exclude from implementation until terms are confirmed |
| 8 | DNASU Plasmid Repository | Site reports about 592k available plasmids | Large repository but geared to physical clone distribution, many ORF clones rather than full annotated backbones | MTAs required for all plasmids; sequence/training terms not established | Exclude from default training ingestion |

### NCBI RefSeq Plasmid Collection

NCBI describes RefSeq as a comprehensive, integrated, non-redundant, well-annotated set of reference sequences, with FTP and NCBI Datasets access. This makes RefSeq a credible quality-improvement source relative to raw GenBank submissions, although RefSeq plasmids are mostly natural plasmids and reference replicons rather than engineered cloning vectors.

Read-only Entrez count probes on 2026-06-02:

```text
plasmid[Title] AND srcdb_refseq[PROP] AND 1000:50000[SLEN] NOT chromosome[Title] NOT scaffold[Title] NOT contig[Title]
Count: 71,256

plasmid[Title] AND srcdb_refseq[PROP] AND ("complete sequence"[Title] OR "complete genome"[Title]) AND 1000:50000[SLEN] NOT chromosome[Title] NOT scaffold[Title] NOT contig[Title]
Count: 37,896
```

Recommendation: use this as CORPUS-2's first broad public sequence expansion, but label it `refseq_plasmid_broad` and do not treat it as an engineered-vector corpus. Apply post-fetch guards for concrete sequence, topology where present, length bounds, duplicate sequence hashes, source taxonomy, and feature density.

Sources:

- NCBI RefSeq overview: https://www.ncbi.nlm.nih.gov/refseq/
- NCBI RefSeq FTP: https://ftp.ncbi.nlm.nih.gov/refseq/
- NCBI GenBank overview and data usage: https://www.ncbi.nlm.nih.gov/genbank/

### NCBI GenBank Engineered-Vector Queries

GenBank remains the best public, same-tooling route for engineered-vector expansion. NCBI describes GenBank as an annotated collection of all publicly available DNA sequences and part of INSDC daily exchange. It also states that NCBI places no restrictions on GenBank data use or distribution, while warning that submitters may claim patent, copyright, or other IP rights.

Count probes on 2026-06-02:

```text
plasmid[Title] AND srcdb_genbank[PROP] AND 1000:50000[SLEN] NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER] NOT chromosome[Title] NOT scaffold[Title] NOT contig[Title]
Count: 54,779

("cloning vector"[Title] OR "expression vector"[Title] OR "reporter vector"[Title] OR "shuttle vector"[Title]) AND srcdb_genbank[PROP] AND 1000:50000[SLEN] NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER]
Count: 10,092
```

Recommendation: implement separate named query presets and measure yield independently. Do not merge broad natural plasmid records and engineered-vector records without a `source_lane` or `corpus_intent` field.

Sources:

- NCBI GenBank overview/data usage: https://www.ncbi.nlm.nih.gov/genbank/
- NCBI E-utilities in depth: https://www.ncbi.nlm.nih.gov/books/NBK25499/
- NCBI sequence search field descriptions: https://www.ncbi.nlm.nih.gov/books/NBK49540/

### High-Quality Depositor/Lab Queries In NCBI

Depositor or lab names are useful for discovery but are weak primary filters. NCBI sample-record/search notes already observed in Construct research indicate direct-submission institution/address text is not a clean structured field in ordinary sequence search and may appear in comments or references.

Count probe on 2026-06-02:

```text
("Addgene"[All Fields] OR "Invitrogen"[All Fields] OR "Thermo Fisher"[All Fields] OR "Clontech"[All Fields] OR "Takara"[All Fields] OR "Promega"[All Fields] OR "New England Biolabs"[All Fields] OR "Novagen"[All Fields]) AND ("cloning vector"[Title] OR "expression vector"[Title] OR "reporter vector"[Title] OR "vector"[Title]) AND srcdb_genbank[PROP] AND 1000:50000[SLEN] NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER]
Count: 471
```

Recommendation: use this as a review queue, not an automatic training source. Records should pass post-fetch checks for full concrete sequence, engineered-vector features, source organism, and accession-level provenance.

### Publication-Linked Molecular Cloning Queries

Publication-linked queries are useful because many engineered vectors are deposited with methods papers or vector-resource papers. The prior Construct strategy proposed `Nucleic Acids Res`, `Methods Mol Biol`, `Gene`, `BioTechniques`, and `Plasmid` as candidate journals.

Count probe on 2026-06-02:

```text
("cloning vector"[Title] OR "expression vector"[Title] OR "reporter vector"[Title] OR "shuttle vector"[Title] OR "vector system"[All Fields]) AND ("Nucleic Acids Res"[Journal] OR "Methods Mol Biol"[Journal] OR "Gene"[Journal] OR "BioTechniques"[Journal] OR "Plasmid"[Journal]) AND srcdb_genbank[PROP] AND 1000:50000[SLEN] NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER]
Count: 958
```

Recommendation: implement after the main engineered-vector query. Store PMID/DOI/reference metadata when available, but do not ingest PubMed abstract text as sequence-training text unless copyright terms are separately handled.

### SEVA Plasmids

SEVA is a strong open scientific vector source for standardized bacterial plasmids. The SEVA site describes SEVA-DB as a web-based resource and material clone repository, with canonical vectors curated by database managers and available GenBank/SBOL files. SEVA format explicitly standardizes origin of replication, selection marker, and cargo modules.

Count probe on 2026-06-02:

```text
(SEVA[All Fields] OR pSEVA[All Fields]) AND srcdb_genbank[PROP] AND 1000:50000[SLEN] NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER]
Count: 184
```

Risk: SEVA is excellent for a curated bacterial-vector subset, but its site also states that commercial/industrial users should be aware that some DNA sequences could be subject to IP restrictions. Therefore, it should be included only with explicit provenance and legal-review fields for commercial training.

Sources:

- SEVA home: https://seva-plasmids.com/
- SEVA description: https://seva-plasmids.com/description/
- SEVA plasmid finder: https://seva-plasmids.com/find-your-plasmid/

### Yeast Genome Database / Yeast Vector Sources

The Saccharomyces Genome Database is useful for yeast gene and literature context, and its site footer shows a Creative Commons Attribution 4.0 badge. However, SGD is not primarily a plasmid/vector sequence corpus. For yeast shuttle vectors, the lower-risk implementation path is still NCBI accession retrieval for pRS, pYES, and yeast marker/vector records, with SGD used only as contextual yeast metadata if needed.

Count probes on 2026-06-02:

```text
(yeast[Title] OR Saccharomyces[Title] OR pRS[All Fields] OR pYES[All Fields]) AND (URA3[All Fields] OR LEU2[All Fields] OR HIS3[All Fields] OR TRP1[All Fields]) AND srcdb_genbank[PROP] AND 1000:50000[SLEN] NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER]
Count: 173

pYES[All Fields] AND srcdb_genbank[PROP] AND 1000:50000[SLEN] NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER]
Count: 6
```

Recommendation: implement as a targeted profile-balancing lane after CORPUS-2, not as the highest-yield source.

Sources:

- SGD home and data/download navigation: https://www.yeastgenome.org/
- SGD archive/download root: http://sgd-archive.yeastgenome.org/

### iGEM Registry / BioBrick Parts

The legacy iGEM Registry states that it is now read-only/archive mode and that most core part data has been copied to the newer Registry. The legacy site says the Registry has over 70,000 documented parts and describes biological parts, composite parts, plasmid backbones, and BioBrick assembly standards.

Count probes on 2026-06-02:

```text
(BioBrick[All Fields] OR pSB1C3[All Fields] OR pSB1A2[All Fields] OR pSB1K3[All Fields]) AND srcdb_genbank[PROP] AND 100:50000[SLEN] NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER]
Count: 238

iGEM[All Fields] AND srcdb_genbank[PROP] AND 100:50000[SLEN] NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER]
Count: 1,393
```

Risk: many iGEM records are parts, not complete plasmids, and accessible pages did not establish a clear training/commercial-use license for bulk sequence use. Treat iGEM as excluded from implementation until terms are reviewed and an ingestion policy separates complete plasmids from parts.

Sources:

- iGEM legacy Registry home: https://parts.igem.org/Main_Page
- iGEM parts help: https://parts.igem.org/Help:Parts
- BioBricks introduction: https://parts.igem.org/Help:An_Introduction_to_BioBricks

### DNASU Plasmid Repository

DNASU is large and relevant as a plasmid repository, reporting more than 300,000 stored/distributed plasmids and about 592k total available plasmids on the home page. It supports search by gene, species, vector name, accession, clone type, pathway, and vector feature.

Risk: DNASU is primarily a physical clone repository with purchase and MTA workflows. Its FAQ states all plasmids require an MTA. This is not a clearly open public sequence-training source without a separate agreement.

Source:

- DNASU home/FAQ: https://dnasu.org/DNASU/Home.do

## Recommended Phase 2 Ingestion Path

1. Implement CORPUS-2 as `ncbi_refseq_plasmid_broad` using Entrez/E-utilities with `srcdb_refseq[PROP]`, concrete sequence validation, dedupe by accession/version and sequence hash, and stored raw GenBank/FASTA artifacts.
2. Add `source_lane`, `license_status`, `terms_ref`, `training_use_allowed`, `commercial_use_allowed`, and `review_required` metadata before mixing records from different sources.
3. Keep broad RefSeq plasmids separate from engineered-vector records in evaluation and training manifests.
4. Implement `ncbi_genbank_engineered_vector` as the next lane using vector-title plus component gates from existing Construct strategy notes.
5. Add `ncbi_genbank_methods_publication` and `ncbi_genbank_depositor_audit` as later review queues, not as automatic bulk training lanes.
6. Add small curated profile-balancing lanes for SEVA and yeast vectors only after the NCBI lanes are stable and legal review confirms acceptable use.
7. Exclude iGEM, Addgene direct downloads, and DNASU from implementation until explicit source terms or agreements allow the intended Construct training use.

## Estimated Yield

| Lane | Public count probe | Expected usable additions after dedupe/validation | Notes |
| --- | ---: | ---: | --- |
| NCBI RefSeq complete plasmid broad | 37,896 | 20k to 35k | Highest-yield low-risk public sequence lane; mostly natural/reference plasmids |
| NCBI RefSeq plasmid broad | 71,256 | 30k to 60k | Use only if complete/title filter is too restrictive |
| NCBI GenBank broad plasmid | 54,779 | 10k to 40k | Higher noise than RefSeq; useful for diversity but weaker provenance curation |
| NCBI GenBank vector-title | 10,092 | 1k to 5k | Best public engineered-vector expansion lane after validation |
| Publication-linked vector query | 958 | 300 to 700 | Good precision candidate, moderate journal/title noise |
| Depositor/lab/vendor query | 471 | 100 to 300 | Review queue only |
| SEVA/pSEVA via NCBI | 184 | 100 to 180 | High-value bacterial modular vector subset |
| Yeast vector NCBI query | 173 | 50 to 120 | Useful for yeast shuttle profile balancing |
| iGEM/BioBrick via NCBI | 238 to 1,393 depending query | 0 by default | Exclude until license and complete-plasmid filtering are approved |
| DNASU | 300k+ to 592k repository scale | 0 by default | Exclude until sequence access and MTA/training terms are approved |

These are live metadata estimates, not fetched/parsed corpus counts. NCBI counts drift over time and `[All Fields]` can match submitters, comments, references, and unrelated text.

## Licensing/Provenance Notes

- NCBI GenBank states it places no restrictions on use or distribution of GenBank data, but also states submitters may claim patent, copyright, or other IP rights and NCBI cannot assess those claims or grant unrestricted permissions.
- RefSeq uses NCBI public access and is accessible through RefSeq FTP/NCBI tooling, but it inherits the need to preserve accession, source database, taxonomy, publication, and submitter/provenance metadata.
- Addgene remains excluded from direct implementation unless the approved Developers Portal scope and data access license explicitly allow the intended Construct training use.
- SEVA is scientifically open and explicitly asks contributors to adhere to open access, but it flags possible IP restrictions for commercial/industrial use. Treat as review-required for commercial model training.
- SGD site content appears CC BY 4.0 from the site footer, but SGD should not be treated as a primary plasmid sequence source. Use NCBI accessions for sequences.
- iGEM Registry pages establish public browsing and a large documented-parts corpus, but the accessible pages reviewed here did not confirm bulk sequence training rights. Exclude until terms are confirmed.
- DNASU requires MTAs for plasmids and does not appear to be a default open sequence-training source. Exclude until a data agreement is in place.

## Questions For Human

- Should CORPUS-2 optimize for broad public plasmid sequence pretraining first, or engineered-vector generation only? If engineered-vector-only, use GenBank vector-title/component gates before RefSeq.
- Can Construct treat NCBI GenBank/RefSeq records as training-eligible by default while preserving submitter-IP caveats, or should commercial training require a legal-reviewed allowlist?
- Is commercial model training in scope for Phase 2? This changes whether SEVA, iGEM, Addgene, and DNASU can be used at all.
- Should RefSeq natural plasmids be allowed into generation pretraining if generated outputs are intended to be engineered vectors, or should they be restricted to representation learning/evaluation only?
- Should CORPUS-2 include potentially sensitive natural plasmid classes such as antimicrobial-resistance plasmids, or should those be filtered/downweighted for biosecurity and product-scope reasons?
- Does Construct have or expect an Addgene Developers Portal license that permits bulk sequence use for training? If yes, Addgene likely becomes the best high-context engineered-vector source, but only under that agreement.
