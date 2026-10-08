> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Corpus Expansion Strategy

## Executive Summary

The next GenBank expansion should move from broad vector-title matching to component-gated Entrez queries. The current query has enough recall but weak precision: the latest quality report shows 82 total records, 70 from GenBank, and 55 records classified as `unknown`. The dominant noise pattern is natural strain plasmids with `plasmid ... complete sequence` titles and sparse engineered-vector annotations.

Recommended first implementation query: the bacterial expression/component query below. It targets common engineered bacterial backbones, has a manageable hit set for an `N=200` run, and does not depend on unreliable depositor metadata.

Second implementation pass: run the publication-linked/methods-journal query and the mammalian expression/reporter query as separate batches, dedupe by accession/version and sequence hash, and evaluate profile/null-rate impact before broadening.

Do not rely on depositor/institution strings as primary filters. NCBI documents that Direct Submission institution/address text is only searchable through broad text fields and can produce false hits.

## Current Corpus Limitation

Current state from `data/eval/quality/2026-06-01-214652-quality-report.json`:

| Metric | Value |
| --- | ---: |
| Total records | 82 |
| Curated records | 12 |
| GenBank records | 70 |
| Unknown profiles | 55 |
| Annotation-complete records | 24 |
| Annotation-complete rate | 29.27% |
| Marker null rate | 63.41% |
| Promoter null rate | 90.24% |

The current refined query returns true engineered vectors near the top of the result set, but later pages still admit natural clinical/environmental plasmids. Adding title-negative filters such as `NOT strain[Title]` is not enough because many noisy records still satisfy broad plasmid/vector wording.

## Entrez Syntax Notes

Official references used:

- NCBI Entrez Help, Cooper and Romiti, updated 2024-06-27: https://www.ncbi.nlm.nih.gov/books/NBK3837/
- NCBI Search Field Descriptions for Sequence Databases, Romiti and Cooper, updated 2024-07-05: https://www.ncbi.nlm.nih.gov/books/NBK49540/
- NCBI E-utilities In-Depth, Sayers, updated 2026-03-04: https://www.ncbi.nlm.nih.gov/books/NBK25499/
- NCBI Sample GenBank Record: https://www.ncbi.nlm.nih.gov/genbank/samplerecord/
- NCBI INSDC/Feature Table overview: https://www.ncbi.nlm.nih.gov/genbank/collab/

Implementation-relevant behavior:

- Boolean operators should be uppercase; parentheses should be used for grouping.
- `[Title]` in Nucleotide searches the GenBank `DEFINITION` line, not publication/reference titles.
- Reference-title text is better searched with `[WORD]` or broader fields than `[Title]`.
- `[FKEY]` searches biological feature keys such as `promoter`, `CDS`, `rep_origin`, and `primer_bind`.
- `[SLEN]`, `[PDAT]`, and `[MDAT]` accept range syntax with `:`.
- `[PROP]` is appropriate for sequence properties such as `biomol_genomic[PROP]`, `srcdb_genbank[PROP]`, and GenBank divisions such as `gbdiv_syn[PROP]`.
- `[GENE]` and `[PROT]` are submitter-provided for GenBank records and can be inconsistent.
- `[KYWD]` is not reliable for broad expansion because keywords are not well controlled and are often absent.
- ESearch supports `retmax`, `retstart`, `sort`, `idtype=acc`, and `rettype=count`.
- NCBI E-utilities policy asks API clients to include `tool` and `email`, and to use an API key above 3 requests per second.

## Depositor And Institution Queries

Conservative conclusion: do not use depositor/institution-style queries as primary implementation filters.

NCBI's sample GenBank record explains that the last `REFERENCE` is usually the Direct Submission block and contains submitter contact information. It also says institution/address elements are searchable with `All Fields`, but warns that results can be false hits because the institution string may appear elsewhere, such as comments.

Practical implication:

- Queries such as `"Invitrogen"[All Fields]`, `"Promega"[All Fields]`, `"Clontech"[All Fields]`, `"New England Biolabs"[All Fields]`, or `"Addgene"[All Fields]` are useful only as exploratory audits.
- They should not be the first expansion path because GenBank does not expose a clean depositor/institution field equivalent to Addgene source metadata in the sequence Entrez field list.
- If used later, require a second-stage validator that inspects fetched GenBank flat files for engineered-vector features, title, source organism, and marker/promoter signals.

## Candidate Query 1: Bacterial Expression And Cloning Components

Exact query string:

```text
("expression vector"[Title] OR "T7 expression"[Title] OR "bacterial expression"[Title] OR "cloning vector"[Title]) AND (T7[All Fields] OR lac[All Fields] OR tac[All Fields] OR trc[All Fields]) AND (bla[All Fields] OR "beta-lactamase"[All Fields] OR kan[All Fields] OR kanamycin[All Fields] OR cat[All Fields] OR chloramphenicol[All Fields]) AND ("complete sequence"[Title] OR "complete genome"[Title]) AND 1000:50000[SLEN] AND biomol_genomic[PROP] AND srcdb_genbank[PROP] NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER] NOT scaffold[Title] NOT contig[Title] NOT chromosome[Title]
```

Rationale: this targets bacterial engineered backbones by requiring a vector title, regulatory signal, and selectable-marker signal. `T7`, `lac`, `tac`, or `trc` plus `bla`, `kan`, or `cat` is a stronger engineered-vector signature than title alone.

Risk/noise assessment: medium-low. It may include older cloning vectors that contain `lac` and `bla` but are not expression vectors. `cat[All Fields]` is ambiguous, but the vector/title and marker gates reduce broad natural-plasmid noise.

Estimated expansion for `N=200`: up to roughly 135 Entrez hits before dedupe/fetch failures, with an expected 70-110 high-quality additions after parser classification.

Recommendation: use this as the first implementation query.

## Candidate Query 2: Publication-Linked Methods/Vector Resource Records

Exact query string:

```text
("cloning vector"[Title] OR "expression vector"[Title] OR "reporter vector"[Title] OR "shuttle vector"[Title] OR "vector system"[All Fields]) AND ("Nucleic Acids Res"[Journal] OR "Methods Mol Biol"[Journal] OR "Gene"[Journal] OR "BioTechniques"[Journal] OR "Plasmid"[Journal]) AND ("complete sequence"[Title] OR "complete genome"[Title]) AND 1000:50000[SLEN] AND biomol_genomic[PROP] AND srcdb_genbank[PROP] NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER] NOT scaffold[Title] NOT contig[Title] NOT chromosome[Title]
```

Rationale: this uses journal/reference metadata where records are linked to cloning/vector methods literature. It avoids depositor guessing while still leveraging publication context.

Risk/noise assessment: medium. `Gene` and `Plasmid` are broad journals and can include natural plasmid biology. Run this after Candidate 1 and dedupe.

Estimated expansion for `N=200`: approximately 180-200 unique records before dedupe, with 80-140 likely high-quality additions if post-fetch component scoring is applied.

## Candidate Query 3: Mammalian Expression And Reporter Components

Exact query string:

```text
("expression vector"[Title] OR "reporter vector"[Title] OR "mammalian expression vector"[Title] OR "luciferase reporter vector"[Title] OR "fluorescent protein vector"[Title]) AND (CMV[All Fields] OR "cytomegalovirus"[All Fields] OR SV40[All Fields]) AND (polyA[All Fields] OR "polyadenylation"[All Fields] OR "polyadenylation signal"[All Fields]) AND (neo[All Fields] OR neomycin[All Fields] OR hygromycin[All Fields] OR puromycin[All Fields] OR luciferase[All Fields] OR GFP[All Fields] OR EGFP[All Fields]) AND 1000:50000[SLEN] AND biomol_genomic[PROP] AND srcdb_genbank[PROP] NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER] NOT scaffold[Title] NOT contig[Title] NOT chromosome[Title]
```

Rationale: this targets a high-confidence mammalian expression/reporter signature: CMV/SV40, polyA, selectable marker or reporter. It directly addresses current corpus sparsity: only one mammalian expression vector and four mammalian reporter vectors.

Risk/noise assessment: low noise, low recall. Some real mammalian vectors omit `polyA` or use nonstandard wording, so this query is intentionally conservative.

Estimated expansion for `N=200`: roughly 13 records before dedupe, with 8-13 likely high-quality additions.

## Candidate Query 4: Feature-Key Component Gate

Exact query string:

```text
(promoter[FKEY] OR polyA_signal[FKEY] OR primer_bind[FKEY] OR rep_origin[FKEY]) AND (CDS[FKEY] OR gene[FKEY]) AND ("cloning vector"[Title] OR "expression vector"[Title] OR "reporter vector"[Title] OR "shuttle vector"[Title]) AND 1000:50000[SLEN] AND biomol_genomic[PROP] AND srcdb_genbank[PROP] NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER] NOT scaffold[Title] NOT contig[Title] NOT chromosome[Title] NOT strain[Title]
```

Rationale: this uses official Feature Key indexing rather than free-text title alone. `promoter`, `polyA_signal`, `primer_bind`, and `rep_origin` are stronger indicators of annotated engineered constructs when combined with vector titles.

Risk/noise assessment: medium. Natural plasmids can have `rep_origin`, `CDS`, and `gene` features. This is best as a broad fallback with post-fetch validation.

Estimated expansion for `N=200`: approximately 180-200 records before dedupe, with 80-130 likely high-quality additions if post-fetch feature scoring is applied.

## Candidate Query 5: Yeast Shuttle/Centromere Vectors

Exact query string:

```text
(yeast[Title] OR Saccharomyces[Title] OR pRS*[Title] OR pYES*[Title]) AND (URA3[All Fields] OR LEU2[All Fields] OR HIS3[All Fields] OR TRP1[All Fields]) AND 1000:50000[SLEN] AND biomol_genomic[PROP] AND srcdb_genbank[PROP] NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER]
```

Rationale: yeast engineered vectors often surface by vector family names such as pRS and pYES plus auxotrophic markers rather than a consistent `yeast centromere vector` title phrase.

Risk/noise assessment: medium-high. Wildcards such as `pRS*[Title]` can over-expand and NCBI documents wildcard expansion limits. Use this as a targeted small batch, not the first `N=200` default.

Estimated expansion for `N=200`: up to roughly 112 records before dedupe, with 20-60 likely high-quality additions.

## Date-Range Findings

Recent `PDAT` is not useful for engineered-vector expansion from GenBank; many canonical vector records are older. `MDAT` reflects record updates and can be useful for refresh scheduling, but should not be treated as an annotation-quality proxy. Do not add a recent-date filter to the first expansion query.

## Recommended First Implementation Query

Use Candidate Query 1 first and keep it as a named ingestion mode so expansion quality can be measured independently from the current query.

Implementation notes for `packages/data_pipeline/ingest/genbank.py`:

- Keep `sort="relevance"` for continuity with the current client.
- Use `srcdb_genbank[PROP]` rather than `genbank[FILTER]` in the new query because it is explicitly documented in NCBI sequence-field docs.
- Run query presets as separate ingestion batches so quality reports can attribute profile gains/noise to a query.
- Dedupe by accession/version and existing sequence hash before evaluating corpus growth.
- After fetch, score records by fetched GenBank features and qualifiers, not only Entrez hit membership.
- Prefer records with at least two engineered-vector signals: vector/expression/reporter title, known promoter/regulatory term, selectable marker, replication origin, reporter gene, `primer_bind`, `polyA_signal`, or synthetic/vector organism.
- Reject or down-rank records with natural-strain title patterns unless they also contain strong engineered-vector features.

## Explicit Caveats

- Entrez query counts are live NCBI results and can drift over time.
- Count probes were read-only ESearch checks, not full fetch-and-parse validation.
- `[All Fields]` terms can match authors, references, comments, submitter blocks, and other text, so component queries still require post-fetch feature validation.
- GenBank records are submitter-authored; feature names, gene names, product names, and titles are not fully controlled for engineered-vector semantics.
- Depositor/institution searches are not reliable enough as primary expansion filters.
- Wildcard queries such as `pRS*[Title]` can be incomplete or noisy because Entrez wildcard expansion is limited.
- Older canonical vector records may have better biological relevance but inconsistent modern annotation.
- Recent deposits are not necessarily better for this task, and recent `PDAT` filtering appears actively harmful for canonical engineered-vector retrieval.
- Addgene access should still become the preferred high-quality expansion source once available; these GenBank queries are a conservative bridge.
