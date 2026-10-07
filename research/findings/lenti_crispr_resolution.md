# Lentiviral/CRISPR Resolution Assessment

## Executive Summary

No immediate no-signoff resolution path was found.

The primary CRISPR/lentiviral methods papers establish the biology and vector identities, but they do not provide an unambiguous paper-to-NCBI-accession path for canonical plasmid seed records under the current NCBI-only curated seed policy.

Several NCBI records are reviewable as derivative candidates, especially complete circular `pX330` derivatives and complete lentiviral transfer-vector derivatives. They are not safe canonical substitutions without human biology/provenance approval because the cited papers either do not name them as canonical vectors or the NCBI records are later derivatives, repository submissions, or patent-derived fragments.

## Candidate Accessions

| Accession | Status | Direct Citation Path | Sequence Represents | Caveats |
| --- | --- | --- | --- | --- |
| `KX151730.1` | Review-only CRISPR derivative candidate | NCBI GenBank record `Cloning vector px330_DBH-FLPo, complete sequence` links to Sun and Ray 2016, PMID `27441631`; the record name includes `px330`; Hsu et al. 2013 describes `PX330` as a bicistronic U6-sgRNA and CBh-hSpCas9 vector, DOI `10.1038/nbt.2647`. | Complete circular CRISPR/Cas9 plasmid derivative carrying a DBH-targeting sgRNA module and FLPo-related payload context. | Not canonical `PX330`; accession is a later application-specific derivative. It is suitable only if Construct explicitly allows reviewed derivatives and labels it as a derivative, not as the canonical Zhang `PX330`. |
| `KX151731.1` | Review-only CRISPR derivative candidate | NCBI GenBank record `Cloning vector px330_DBH-p2a-FLPo, complete sequence` links to Sun and Ray 2016, PMID `27441631`; the record name includes `px330`; Hsu et al. 2013 describes `PX330` architecture. | Complete circular CRISPR/Cas9 plasmid derivative carrying a DBH-p2a-FLPo sgRNA context. | Same caveat as `KX151730.1`: it is a later derivative and should not be silently substituted for canonical `PX330`. |
| `MQ170688.1` | Not recommended without legal/provenance review | NCBI summary identifies `Sequence 534 from Patent WO2021171048` with note `pX330-Flag-WT SpCas9 (without sgRNA; with silent mutations)`. | Patent-submitted linear synthetic construct related to `pX330`. | Patent sequence, linear, modified, and not a primary methods-paper plasmid record. Poor seed candidate under current policy. |
| `MP725430.1` | Not recommended without legal/provenance review | NCBI summary identifies `Sequence 50 from Patent EP3684172` with note `pX330-GFP plasmid nucleic acid sequence`. | Patent-submitted `pX330-GFP`-related sequence. | Patent sequence and derivative; not a canonical CRISPR seed. |
| `LT009455.1` to `LT009459.1` | Review-only lentiviral derivative candidates | NCBI summaries identify complete circular lentiviral vectors from the BCCM/LMBP plasmid collection, including `pLenti6-tdTomato-V5-Blast`, `pLenti6-tdTomato-V5-Puro`, `pLenti6-V5-Puro`, `pLenti6-VSV-Blast`, and `pLenti6-VSV-Puro`. | Complete circular lentiviral transfer-vector derivatives. | Not tied to Cong, Shalem, Sanjana, `lentiCRISPR v2`, `lentiGuide-Puro`, `pLKO.1`, or another requested canonical methods-paper vector. May be usable only if human reviewers approve a non-canonical lentiviral derivative lane. |
| `MG840310.1` to `MG840314.1` | Review-only lentiviral CRISPR/dCas9 derivative candidates | NCBI summaries identify complete circular `pLenti-EF1a-dCas9...` vectors. | Lentiviral dCas9 fusion/expression plasmid derivatives. | These are CRISPR-adjacent and lentiviral, but not canonical genome-editing vectors from Cong/Shalem/Sanjana. They are specialized dCas9 derivatives and should not be used as generic CRISPR or lentiviral calibration seeds without review. |

## Primary-Source Rationale

Cong et al. 2013, `Multiplex Genome Engineering Using CRISPR/Cas Systems`, DOI `10.1126/science.1231143`, establishes mammalian CRISPR/Cas genome editing with SpCas9, U6-driven RNA components, and engineered expression constructs. The paper states that reagents would be made available through Addgene and the Zhang lab site, but the article text and supplementary listing do not provide a plasmid GenBank accession for a canonical seed.

Hsu et al. 2013, `DNA targeting specificity of RNA-guided Cas9 nucleases`, DOI `10.1038/nbt.2647`, explicitly describes `PX330` as a bicistronic expression vector for U6 promoter-driven sgRNA and CBh promoter-driven human codon-optimized `S. pyogenes` Cas9. Its accession statement is for raw sequencing reads at BioProject `SRP023129`, not for a complete plasmid sequence accession. This supports `PX330` as a biologically valid CRISPR vector concept, but not an NCBI-backed canonical plasmid seed.

Shalem et al. 2014, `Genome-Scale CRISPR-Cas9 Knockout Screening in Human Cells`, DOI `10.1126/science.1247005`, describes lentiviral delivery of Cas9, sgRNA, and puromycin selection in `lentiCRISPR`. It does not provide a complete plasmid NCBI accession for `lentiCRISPR`.

Sanjana et al. 2014, `Improved vectors and genome-wide libraries for CRISPR screening`, DOI `10.1038/nmeth.3047`, describes `lentiCRISPR v2`, `lentiCas9-Blast`, and `lentiGuide-Puro`, including lentiviral elements such as psi, RRE, cPPT, EFS/EF1a, P2A, puro/blast, and WPRE. NCBI Nucleotide searches for exact names `lentiCRISPR v2`, `lentiGuide-Puro`, and `lentiCas9-Blast` returned zero records, so this paper does not currently resolve the accession gap under the NCBI-only seed policy.

Mali et al. 2013, `RNA-Guided Human Genome Engineering via Cas9`, DOI `10.1126/science.1232033`, provides an independent CRISPR implementation with Cas9 and U6-driven guide RNAs, but it does not resolve the Zhang-lentiviral or canonical Zhang `PX330` accession question.

NCBI searches for `pLKO.1` and `TRC cloning vector` returned zero Nucleotide records in the checked query form. That leaves `pLKO.1` unresolved under an NCBI-only policy despite its relevance as a canonical lentiviral shRNA vector in Addgene/protocol contexts.

## Assessment

There is a defensible reviewed-derivative path, but not an immediate no-signoff path.

The strongest reviewable CRISPR candidates are `KX151730.1` and `KX151731.1` because they are complete circular GenBank records, explicitly `px330`-named, and linked to a peer-reviewed paper. They still require a human decision because they are DBH/FLPo application derivatives rather than canonical `PX330`, `pX330-U6-Chimeric_BB-CBh-hSpCas9`, `pX458`, or `pX459`.

The strongest reviewable lentiviral candidates are the complete circular `pLenti6` records `LT009455.1` through `LT009459.1`. They still require a human decision because they are BCCM/LMBP repository lentiviral derivatives and not the canonical corpus targets previously named in Construct's representative examples.

No accession-backed candidate found here is strong enough to add unilaterally as a canonical `lentiviral_or_retroviral_transfer_vector` or `crispr_vector` seed under the current policy.

## Caveats

- NCBI records can be public and complete while still being biologically non-canonical for Construct's seed purpose.
- A later derivative can validate parser coverage for some structural features, but it changes the benchmark claim from `canonical vector seed` to `reviewed derivative seed`.
- Patent records may be present in NCBI but remain poor default calibration seeds because they add legal/provenance complexity and may not be complete circular plasmids.
- Addgene remains the clearer source for canonical Zhang lab plasmid identities, but Addgene-only sequence use remains blocked unless licensing/intended-use policy is approved.

## Questions For Human Review

1. Should Construct allow a `reviewed_genbank_derivative` seed lane distinct from canonical curated seeds?
2. If yes, may `KX151730.1` and `KX151731.1` be used as `crispr_vector` derivative seeds with explicit non-canonical labels?
3. If yes, may `LT009455.1` through `LT009459.1` be used as lentiviral transfer-vector derivative seeds even though they are not the requested canonical Zhang/Addgene lentiviral CRISPR vectors?
4. Should patent-derived records such as `MQ170688.1` and `MP725430.1` be categorically excluded from parser-calibration seeds?
5. Should canonical `lentiCRISPR v2`, `lentiGuide-Puro`, `pLKO.1`, `pX330`, `pX458`, and `pX459` remain blocked until Addgene licensing or another exact accession-backed primary source is approved?
