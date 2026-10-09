# Retrieval Evaluation Report

- Generated at: `2026-10-09T02:36:38.057033+00:00`
- Gold file: `data/eval/retrieval_gold.jsonl`
- Queries: `57`
- Retrieval queries scored: `55`
- Clarification queries: `2`
- Top K: `5`
- Top-1 hit rate: `0.291`
- Top-5 hit rate: `0.418`
- Clarification pass rate: `1.000`
- MRR: `0.333`

## Per-Query Results

### 1. I need a simple high-copy cloning vector for routine plasmid cloning in E. coli.

- Acceptable IDs: `pUC19, pUC18, pBluescript-II-SK-plus, pBluescript-II-SK-minus, pBR322, pACYC184, genbank:AF310245.1`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `curated:pUC18` pUC18 score=`0.7532` fields=`semantic, vector_type, organism, application`
- 2. `curated:pUC19` pUC19c score=`0.7488` fields=`semantic, vector_type, organism, application`
- 3. `genbank:AY428809.1` Cloning vector pSUP202, complete sequence score=`0.7283` fields=`semantic, vector_type, organism, application`
- 4. `genbank:U14120.1` Cloning vector pSG927, HIS4-based plasmid, complete sequence score=`0.7119` fields=`semantic, vector_type, organism, application`
- 5. `genbank:U14122.1` Cloning vector pSG935, HIS4-based plasmid, complete sequence score=`0.7117` fields=`semantic, vector_type, organism, application`

Rationale: These are bacterial cloning backbones with standard cloning-friendly features such as pUC/pMB1-family origins, MCSs, and antibiotic selection. The expanded corpus also retrieves GenBank AF310245.1 pGEM58ZNf(-), annotated as an E. coli cloning vector with a multicloning site, lacZ, bla/AmpR, T7/SP6 promoters, and pUC/pGEM-derived backbone evidence.
Source: Curated seed manifest entries in packages/data_pipeline/ingest/curated_seed_manifest.yaml; GenBank AF310245.1 indexed metadata and GOLD-1 review on 2026-06-02

### 2. Which curated plasmid would you use for GST-tagged bacterial protein expression in E. coli?

- Acceptable IDs: `pGEX-4T-1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- <none>

Rationale: pGEX-4T-1 is explicitly annotated as a GST fusion bacterial expression backbone with tac/lac regulation.
Source: Curated seed manifest entry for pGEX-4T-1

### 3. I need a mammalian reporter plasmid for GFP-based expression analysis in cultured cells.

- Acceptable IDs: `pEGFP-N1`
- Result: `hit at rank 2`
- Reciprocal rank: `0.500`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:AF416989.1` Synthetic construct plasmid pTRE_hTF_Luc, complete sequence score=`0.6670` fields=`semantic, vector_type, organism`
- 2. `curated:pEGFP-N1` pEGFP-N1 score=`0.6616` fields=`semantic, vector_type, organism, genes, application`
- 3. `curated:pGL3-Basic` pGL3-Basic score=`0.6222` fields=`semantic, vector_type, organism`
- 4. `genbank:AF416988.1` Synthetic construct plasmid pTRE_PSKH1_Luc, complete sequence score=`0.6198` fields=`semantic, vector_type, organism`
- 5. `curated:pGL4-10-luc2` pGL4.10[luc2] score=`0.6158` fields=`semantic, vector_type, organism`

Rationale: pEGFP-N1 is curated as a CMV-driven mammalian C-terminal EGFP fusion reporter with a neomycin selectable marker.
Source: Curated seed manifest entry for pEGFP-N1

### 4. Which vector should I use for a luciferase reporter assay in mammalian cells?

- Acceptable IDs: `pGL3-Basic, pGL4-10-luc2, genbank:AF058756.1`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `curated:pGL4-10-luc2` pGL4.10[luc2] score=`0.7167` fields=`semantic, vector_type, organism, genes`
- 2. `genbank:AF416989.1` Synthetic construct plasmid pTRE_hTF_Luc, complete sequence score=`0.7152` fields=`semantic, vector_type, organism, genes`
- 3. `curated:pGL3-Basic` pGL3-Basic score=`0.7037` fields=`semantic, vector_type, organism, genes`
- 4. `genbank:AF416988.1` Synthetic construct plasmid pTRE_PSKH1_Luc, complete sequence score=`0.6816` fields=`semantic, vector_type, organism, genes`
- 5. `genbank:AF416990.1` Synthetic construct plasmid pcDNA3-Rluc, complete sequence score=`0.6750` fields=`semantic, vector_type, organism, genes`

Rationale: The curated pGL3-Basic and pGL4.10[luc2] records are promoterless luciferase reporter vectors intended for reporter assays. The expanded corpus also includes GenBank AF058756.1 pFR-Luc, indexed as a mammalian firefly-luciferase reporter backbone with ampicillin selection and an upstream cloning site.
Source: Curated seed manifest entries for pGL3-Basic and pGL4.10[luc2]; GenBank AF058756.1 indexed metadata and retrieval report entry for pFR-Luc

### 5. I need a yeast shuttle vector with a selectable marker for yeast transformation and maintenance.

- Acceptable IDs: `pRS415, pRS416, genbank:AF041805.1, genbank:AF041806.1, genbank:AF041807.1`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `curated:pRS415` pRS415 score=`0.8300` fields=`semantic, vector_type, organism`
- 2. `curated:pRS416` pRS416 score=`0.8283` fields=`semantic, vector_type, organism`
- 3. `genbank:AF041807.1` Cloning vector yGALset985, complete sequence score=`0.7775` fields=`semantic, vector_type, organism`
- 4. `genbank:AF041805.1` Cloning vector yGALset983, complete sequence score=`0.7775` fields=`semantic, vector_type, organism`
- 5. `genbank:AF041806.1` Cloning vector yGALset984, complete sequence score=`0.7764` fields=`semantic, vector_type, organism`

Rationale: The curated pRS vectors are yeast centromere shuttle plasmids with LEU2 or URA3 selection and CEN/ARS maintenance features. The expanded corpus also retrieves yGALset983/984/985 records, which are S. cerevisiae shuttle/expression vectors with yeast maintenance regions and LEU2 selection plus bacterial AmpR maintenance.
Source: Curated seed manifest entries for pRS415 and pRS416; GenBank AF041805.1/AF041806.1/AF041807.1 indexed metadata and GOLD-1 review on 2026-06-02

### 6. Recommend a low-copy bacterial cloning plasmid with chloramphenicol resistance.

- Acceptable IDs: `pACYC184`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:AY428809.1` Cloning vector pSUP202, complete sequence score=`0.7657` fields=`semantic, vector_type, organism, markers, application`
- 2. `genbank:U35133.1` Plasmid pBSL175 cloning vector, complete sequence score=`0.7573` fields=`semantic, vector_type, organism, markers, application`
- 3. `genbank:U35235.1` Plasmid pBSL167 cloning vector, complete sequence score=`0.7476` fields=`semantic, vector_type, organism, markers, application`
- 4. `genbank:U35131.1` Plasmid pBSL159 cloning vector, complete sequence score=`0.7402` fields=`semantic, vector_type, organism, markers, application`
- 5. `genbank:U35132.1` Plasmid pBSL168 cloning vector, complete sequence score=`0.7398` fields=`semantic, vector_type, organism, markers, application`

Rationale: pACYC184 is curated as a low-copy p15A-origin cloning vector with chloramphenicol and tetracycline resistance.
Source: Curated seed manifest entry for pACYC184

### 7. I want a bacterial cloning plasmid with lacZ alpha selection and a standard pUC backbone.

- Acceptable IDs: `pUC19, pUC18, pBluescript-II-SK-plus, pBluescript-II-SK-minus, genbank:L09130.1`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `curated:pUC19` pUC19c score=`0.7972` fields=`semantic, vector_type, organism, application`
- 2. `curated:pUC18` pUC18 score=`0.7967` fields=`semantic, vector_type, organism, application`
- 3. `genbank:L09130.1` Cloning vector pUC13, complete sequence score=`0.7614` fields=`semantic, vector_type, organism, application`
- 4. `genbank:AY428809.1` Cloning vector pSUP202, complete sequence score=`0.7489` fields=`semantic, vector_type, organism, application`
- 5. `genbank:AF310245.1` Cloning vector pGEM58ZNf(-), complete sequence score=`0.7413` fields=`semantic, vector_type, organism, application`

Rationale: These curated records include pUC-family or lacZ alpha/MCS cloning backbones suitable for blue-white screening workflows. The expanded corpus also retrieves GenBank L09130.1 pUC13, a pUC-family cloning vector with beta-galactosidase indicator evidence, M13mp11 polylinker/MCS, and ampicillin selection.
Source: Curated seed manifest entries for the pUC and pBluescript vectors; GenBank L09130.1 indexed metadata and GOLD-1 review on 2026-06-02

### 8. Which curated source cloning vector carries both ampicillin and tetracycline resistance with a pMB1-derived replication region? Exclude GenBank-only matches like pSUP202.

- Acceptable IDs: `pBR322`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- <none>

Rationale: pBR322 is the curated corpus match for the classic pMB1-derived AmpR/TetR cloning backbone. The provenance constraint excludes GenBank candidates such as pSUP202 even though they share overlapping bacterial-cloning and marker evidence.
Source: Curated seed manifest entry for pBR322 plus live local Postgres corpus verification on 2026-05-31 for the contrasting GenBank pSUP202 record

### 9. I need a phagemid cloning vector with an f1 origin, lacZ alpha MCS, and T7/T3 promoter sites.

- Acceptable IDs: `pBluescript-II-SK-plus, pBluescript-II-SK-minus`
- Result: `hit at rank 3`
- Reciprocal rank: `0.333`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `curated:pUC18` pUC18 score=`0.7964` fields=`semantic, vector_type, organism, application`
- 2. `curated:pUC19` pUC19c score=`0.7929` fields=`semantic, vector_type, organism, application`
- 3. `curated:pBluescript-II-SK-minus` pBluescript II SK(-) score=`0.7849` fields=`semantic, vector_type, organism, application`
- 4. `genbank:AF087042.1` Cloning vector pCALnFLAG, complete sequence score=`0.7802` fields=`semantic, vector_type, organism, promoters, application`
- 5. `genbank:L09130.1` Cloning vector pUC13, complete sequence score=`0.7679` fields=`semantic, vector_type, organism, application`

Rationale: The pBluescript II SK records are curated phagemid cloning vectors; SK(+) explicitly includes f1 plus orientation, lacZ alpha/MCS, T7/T3 promoters, pUC origin, and bla, while SK(-) is the corresponding minus-orientation variant.
Source: Curated seed manifest entries for pBluescript-II-SK-plus and pBluescript-II-SK-minus

### 10. Recommend a high-copy ampicillin-resistant pUC plasmid when either MCS orientation is acceptable.

- Acceptable IDs: `pUC19, pUC18, genbank:L09130.1`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `curated:pUC19` pUC19c score=`0.8149` fields=`semantic, vector_type, organism, markers, application`
- 2. `curated:pUC18` pUC18 score=`0.8020` fields=`semantic, vector_type, organism, markers, application`
- 3. `genbank:AY428809.1` Cloning vector pSUP202, complete sequence score=`0.7910` fields=`semantic, vector_type, organism, markers, application`
- 4. `genbank:L09130.1` Cloning vector pUC13, complete sequence score=`0.7649` fields=`semantic, vector_type, organism, markers, application`
- 5. `genbank:U14122.1` Cloning vector pSG935, HIS4-based plasmid, complete sequence score=`0.7570` fields=`semantic, vector_type, organism, markers, application`

Rationale: pUC19 and pUC18 are curated high-copy pUC/pMB1-derived AmpR cloning vectors with opposite MCS orientations. The expanded corpus also includes GenBank L09130.1 pUC13, a pUC-family ampicillin-resistant cloning plasmid with polylinker/MCS and beta-galactosidase indicator evidence.
Source: Curated seed manifest entries for pUC19 and pUC18; GenBank L09130.1 indexed metadata and GOLD-1 review on 2026-06-02

### 11. Which mammalian EGFP fusion vector also provides G418 selection in cells and kanamycin selection in bacteria?

- Acceptable IDs: `pEGFP-N1`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `curated:pEGFP-N1` pEGFP-N1 score=`0.5918` fields=`semantic, organism, markers, genes`

Rationale: pEGFP-N1 is curated as a CMV-driven C-terminal EGFP fusion vector with neomycin/G418 mammalian selection and a kanamycin bacterial marker.
Source: Curated seed manifest entry for pEGFP-N1

### 12. I need a yeast centromere shuttle plasmid specifically selected by URA3 rather than LEU2.

- Acceptable IDs: `pRS416`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `curated:pRS416` pRS416 score=`0.8498` fields=`semantic, vector_type, organism, markers`

Rationale: pRS416 is curated as a yeast centromere vector with a URA3 marker, whereas pRS415 carries LEU2.
Source: Curated seed manifest entries for pRS416 and pRS415

### 13. E. coli T7 expression vector, AmpR, with an MCS. Keep it simple.

- Acceptable IDs: `genbank:AF147463.1, genbank:AF087042.1`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:AF147463.1` T7 Expression vector pNam, complete sequence score=`0.7669` fields=`semantic, vector_type, organism, markers, promoters, application`
- 2. `genbank:AF087042.1` Cloning vector pCALnFLAG, complete sequence score=`0.7455` fields=`semantic, vector_type, organism, markers, promoters`
- 3. `curated:pBluescript-II-SK-minus` pBluescript II SK(-) score=`0.7219` fields=`semantic, vector_type, organism, markers, application`
- 4. `curated:pBluescript-II-SK-plus` pBluescript II SK(+) score=`0.7216` fields=`semantic, vector_type, organism, markers, application`

Rationale: The GenBank pNam record is indexed as a bacterial expression vector with a T7 promoter, bla/AmpR selection, and a multiple cloning site. The expanded corpus also retrieves GenBank AF087042.1 pCALnFLAG, an E. coli-maintained AmpR vector with T7 lac promoter control and a cloning/tag region suitable for bacterial expression workflows.
Source: Live local Postgres corpus verification on 2026-05-31; GenBank AF147463.1 indexed metadata; GenBank AF087042.1 indexed metadata and GOLD-1 review on 2026-06-02

### 14. For an E. coli cloning workflow, retrieve a backbone carrying ampicillin, tetracycline, and chloramphenicol resistance.

- Acceptable IDs: `genbank:AY428809.1`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:AY428809.1` Cloning vector pSUP202, complete sequence score=`0.7263` fields=`semantic, organism, markers, application`

Rationale: The GenBank pSUP202 record is indexed as a bacterial cloning vector with bla/ampicillin, tet, and cat markers. Requiring all three markers distinguishes it from two-marker cloning backbones.
Source: Live local Postgres corpus verification on 2026-05-31; GenBank AY428809.1 indexed metadata

### 15. Need an E. coli-Pseudomonas broad-host-range shuttle vector with tetracycline resistance and lacZ alpha for blue/white screening.

- Acceptable IDs: `genbank:U07168.1`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:U07168.1` Cloning vector pUCP26, Escherichia-Pseudomonas shuttle vector with tetracycline efflux protein (tet) and LacZ alpha peptide (lacZ alpha) genes, complete sequence score=`0.7797` fields=`semantic, vector_type, organism, markers`

Rationale: The GenBank pUCP26 record is indexed as a general shuttle vector with broad-host-range use, tet selection, lacZ alpha, and an MCS. The query tests shuttle-host intent and a hard tetracycline marker filter.
Source: Live local Postgres corpus verification on 2026-05-31; GenBank U07168.1 indexed metadata

### 16. E. coli SpecR shuttle vector.

- Acceptable IDs: `genbank:AF216802.1`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:AF216802.1` Shuttle vector pDL278, complete sequence score=`0.7460` fields=`semantic, vector_type, organism, markers`

Rationale: The GenBank pDL278 record is indexed as a general shuttle vector with spectinomycin adenyltransferase. The intentionally terse query tests controlled-marker normalization and shuttle-vector filtering.
Source: Live local Postgres corpus verification on 2026-05-31; GenBank AF216802.1 indexed metadata

### 17. For transient mammalian expression, I need an ampicillin-selected pSI-style plasmid with an SV40 enhancer and early promoter.

- Acceptable IDs: `genbank:U47121.2`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:U47121.2` Cloning vector pSI, mammalian expression vector, complete sequence score=`1.0000` fields=`lexical_name, vector_type, organism, markers`
- 2. `genbank:AF416990.1` Synthetic construct plasmid pcDNA3-Rluc, complete sequence score=`0.6521` fields=`semantic, vector_type, organism, markers`
- 3. `genbank:AF416989.1` Synthetic construct plasmid pTRE_hTF_Luc, complete sequence score=`0.6469` fields=`semantic, vector_type, organism, markers`
- 4. `genbank:AF416988.1` Synthetic construct plasmid pTRE_PSKH1_Luc, complete sequence score=`0.6463` fields=`semantic, vector_type, organism, markers`
- 5. `curated:pGL3-Basic` pGL3-Basic score=`0.6377` fields=`semantic, vector_type, organism, markers`

Rationale: The GenBank pSI record is indexed as the corpus mammalian-expression profile and carries ampR plus the SV40 enhancer/early promoter. This case exercises mammalian host, profile, and bacterial-selection filters.
Source: Live local Postgres corpus verification on 2026-05-31; GenBank U47121.2 indexed metadata

### 18. Can you pull pFR-Luc? I need an AmpR mammalian firefly-luciferase reporter backbone with an upstream cloning site.

- Acceptable IDs: `genbank:AF058756.1`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:AF058756.1` Cloning vector pFR-Luc, complete sequence score=`1.0000` fields=`lexical_name, vector_type, organism, markers`
- 2. `curated:pGL4-10-luc2` pGL4.10[luc2] score=`0.7642` fields=`semantic, vector_type, organism, markers, genes`
- 3. `genbank:AF416989.1` Synthetic construct plasmid pTRE_hTF_Luc, complete sequence score=`0.7600` fields=`semantic, vector_type, organism, markers, genes`
- 4. `curated:pGL3-Basic` pGL3-Basic score=`0.7370` fields=`semantic, vector_type, organism, markers, genes`
- 5. `genbank:AF416988.1` Synthetic construct plasmid pTRE_PSKH1_Luc, complete sequence score=`0.7208` fields=`semantic, vector_type, organism, markers, genes`

Rationale: The GenBank pFR-Luc record is indexed as a mammalian reporter vector with luciferase, ampicillin selection, an MCS candidate, and SV40 late polyA. This researcher-style lookup broadens reporter coverage beyond curated seeds.
Source: Live local Postgres corpus verification on 2026-05-31; GenBank AF058756.1 indexed metadata

### 19. For a yeast shuttle comparison, retrieve the Zygosaccharomyces rouxii pSB3 plasmid with an ARS region.

- Acceptable IDs: `genbank:PV135004.1`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:PV135004.1` Zygosaccharomyces rouxii culture ATCC:56076 plasmid pSB3, complete sequence score=`1.0000` fields=`lexical_name, vector_type, organism`
- 2. `curated:pRS415` pRS415 score=`0.8257` fields=`semantic, vector_type, organism`
- 3. `curated:pRS416` pRS416 score=`0.8248` fields=`semantic, vector_type, organism`
- 4. `genbank:AF041805.1` Cloning vector yGALset983, complete sequence score=`0.7785` fields=`semantic, vector_type, organism`
- 5. `genbank:AF041807.1` Cloning vector yGALset985, complete sequence score=`0.7782` fields=`semantic, vector_type, organism`

Rationale: The GenBank pSB3 record exists as a Zygosaccharomyces rouxii plasmid and is indexed with the yeast-shuttle profile plus an ARS region. It is labeled as a comparison retrieval, not as a fabricated Saccharomyces engineering backbone.
Source: Live local Postgres corpus verification on 2026-05-31; GenBank PV135004.1 indexed metadata

### 20. For a bacterial resistance-plasmid comparison, retrieve the Aeromonas salmonicida pRAS1_2402_89 plasmid carrying tetracycline resistance, sul1, and dfrA16.

- Acceptable IDs: `genbank:PZ138287.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- <none>

Rationale: The natural GenBank pRAS1_2402_89 record exists in the broader corpus with tetA, tetR, sul1, and dfrA16 annotations. It remains profile unknown and is intentionally labeled for comparative retrieval rather than as an engineered vector template.
Source: Live local Postgres corpus verification on 2026-05-31; GenBank PZ138287.1 indexed metadata

### 21. I need a viral vector with antibiotic resistance.

- Acceptable IDs: ``
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `True`
- Clarification needed: `True`
- Clarification question: Which viral vector type should this use: lentiviral, retroviral, AAV, or another system?

Retrieved:
- <none>

Rationale: The request does not identify the viral system or selectable marker. Retrieval should ask a clarifying question instead of guessing a lentiviral, retroviral, AAV, or marker label. The corpus now does hold one record indexed as a retroviral transfer vector and several indexed as CRISPR, which makes the clarification more necessary rather than less: a guess would now land on a specific record instead of returning nothing.
Source: Human-authored ambiguity case informed by live local Postgres profile audit on 2026-05-31; rationale corrected on 2026-10-08 after the WP-20 full-corpus embedding changed the profile inventory

### 22. I am looking for a cloning vector that carries gentamicin resistance rather than the usual ampicillin or kanamycin.

- Acceptable IDs: `genbank:U35129.1, genbank:U35130.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:GQ149343.1` Escherichia coli plasmid pAm05WL6211, complete sequence score=`0.7272` fields=`semantic, vector_type, organism, markers`
- 2. `genbank:GQ149347.1` Escherichia coli plasmid pAm08CQ6130, complete sequence score=`0.7071` fields=`semantic, vector_type, organism, markers`

Rationale: pBSL141 and pBSL142 are the only two records in the corpus whose indexed selectable markers include a gentamicin 3-acetyltransferase, and both are indexed as bacterial cloning vectors.
Source: Indexed plasmid_embeddings.composed_document for genbank:U35129.1 and genbank:U35130.1, verified to contain Bacterial cloning vector and gentamicin 3-acetyltransferase. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 23. Which cloning vector in the collection uses a low-copy p15A origin together with chloramphenicol selection?

- Acceptable IDs: `genbank:U35131.1, genbank:U35132.1, genbank:U35235.1`
- Result: `hit at rank 3`
- Reciprocal rank: `0.333`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:AY428809.1` Cloning vector pSUP202, complete sequence score=`0.7927` fields=`semantic, vector_type, organism, markers, application`
- 2. `genbank:U35133.1` Plasmid pBSL175 cloning vector, complete sequence score=`0.7797` fields=`semantic, vector_type, organism, markers, application`
- 3. `genbank:U35235.1` Plasmid pBSL167 cloning vector, complete sequence score=`0.7727` fields=`semantic, vector_type, organism, markers, application`
- 4. `curated:pACYC184` pACYC184 score=`0.7710` fields=`semantic, vector_type, organism, markers, application`
- 5. `genbank:U35131.1` Plasmid pBSL159 cloning vector, complete sequence score=`0.7677` fields=`semantic, vector_type, organism, markers, application`

Rationale: pBSL159, pBSL168 and pBSL167 are indexed as bacterial cloning vectors carrying a chloramphenicol acetyltransferase marker on a p15A origin, which is the copy-number distinction the query asks about.
Source: Indexed plasmid_embeddings.composed_document for genbank:U35131.1, genbank:U35132.1 and genbank:U35235.1, verified to contain Bacterial cloning vector, chloramphenicol acetyltransferase and p15A origin. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 24. I need a cloning backbone with streptomycin resistance for selection in E. coli.

- Acceptable IDs: `genbank:U35128.1, genbank:U35133.1`
- Result: `hit at rank 2`
- Reciprocal rank: `0.500`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:CP000798.1` Escherichia coli E24377A plasmid pETEC_6, complete sequence score=`0.6958` fields=`semantic, organism, markers`
- 2. `genbank:U35133.1` Plasmid pBSL175 cloning vector, complete sequence score=`0.6861` fields=`semantic, organism, markers, application`
- 3. `genbank:U55385.2` Plasmid pRL1063a, complete sequence score=`0.6736` fields=`semantic, organism, markers`
- 4. `genbank:U35128.1` Plasmid pBSL130 cloning vector, complete sequence score=`0.6628` fields=`semantic, organism, markers, application`

Rationale: pBSL130 and pBSL175 both carry an indexed streptomycin 3-adenylyltransferase marker and are indexed as bacterial cloning vectors.
Source: Indexed plasmid_embeddings.composed_document for genbank:U35128.1 and genbank:U35133.1, verified to contain Bacterial cloning vector and streptomycin 3-adenylyltransferase. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 25. Recommend a cloning vector with a neomycin or kanamycin phosphotransferase marker and a single-strand f1 origin.

- Acceptable IDs: `genbank:U35127.1, genbank:U35136.1, genbank:U35137.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `curated:pEGFP-N1` pEGFP-N1 score=`0.6810` fields=`semantic, vector_type, organism, markers, application`

Rationale: pBSL128, pBSL97 and pBSL99 are indexed bacterial cloning vectors with a neomycin phosphotransferase marker and an indexed f1 origin alongside the pUC origin.
Source: Indexed plasmid_embeddings.composed_document for genbank:U35127.1, genbank:U35136.1 and genbank:U35137.1, verified to contain Bacterial cloning vector, neomycin phosphotransferase and f1 origin. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 26. Is there a plasmid in the collection carrying the yeast HIS4 gene that I could use as a starting backbone?

- Acceptable IDs: `genbank:U14116.1, genbank:U14117.1, genbank:U14118.1, genbank:U14119.1, genbank:U14120.1, genbank:U14121.1, genbank:U14122.1, genbank:U14123.1, genbank:U14124.1, genbank:U14125.1, genbank:U14127.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `curated:pRS415` pRS415 score=`0.7502` fields=`semantic, organism`
- 2. `curated:pRS416` pRS416 score=`0.7494` fields=`semantic, organism`
- 3. `genbank:CP004537.1` Saccharomyces cerevisiae YJM1242 plasmid 2 micron, complete sequence score=`0.7128` fields=`semantic, organism`
- 4. `genbank:CP004507.1` Saccharomyces cerevisiae YJM320 plasmid 2 micron, complete sequence score=`0.7124` fields=`semantic, organism`
- 5. `genbank:CP004508.1` Saccharomyces cerevisiae YJM326 plasmid 2 micron, complete sequence score=`0.7111` fields=`semantic, organism`

Rationale: The pSG925 through pSG935 series is indexed as HIS4-based cloning vectors; HIS4 is the indexed payload on each one and appears nowhere else in the corpus. Eleven targets are acceptable because the series is genuinely interchangeable for this request.
Source: Indexed plasmid_embeddings.composed_document for genbank:U14116.1, genbank:U14117.1, genbank:U14118.1, genbank:U14119.1, genbank:U14120.1, genbank:U14121.1, genbank:U14122.1, genbank:U14123.1, genbank:U14124.1, genbank:U14125.1 and genbank:U14127.1, verified to contain Bacterial cloning vector and HIS4. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 27. I want a Renilla luciferase reporter driven by a CMV promoter for transfection into mammalian cells.

- Acceptable IDs: `genbank:AF416990.1`
- Result: `hit at rank 4`
- Reciprocal rank: `0.250`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `curated:pGL3-Basic` pGL3-Basic score=`0.7387` fields=`semantic, vector_type, organism, genes`
- 2. `curated:pGL4-10-luc2` pGL4.10[luc2] score=`0.7344` fields=`semantic, vector_type, organism, genes`
- 3. `genbank:AF416989.1` Synthetic construct plasmid pTRE_hTF_Luc, complete sequence score=`0.7251` fields=`semantic, vector_type, organism, genes`
- 4. `genbank:AF416990.1` Synthetic construct plasmid pcDNA3-Rluc, complete sequence score=`0.7101` fields=`semantic, vector_type, organism, promoters, genes`
- 5. `genbank:AF416988.1` Synthetic construct plasmid pTRE_PSKH1_Luc, complete sequence score=`0.6962` fields=`semantic, vector_type, organism, genes`

Rationale: pcDNA3-Rluc is the only corpus record with Renilla luciferase as an indexed payload, and its indexed promoters include a CMV promoter.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF416990.1, verified to contain Mammalian reporter vector, Renilla luciferase and CMV promoter. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 28. Looking for a tetracycline-responsive luciferase fusion reporter plasmid to measure induced promoter activity.

- Acceptable IDs: `genbank:AF416988.1, genbank:AF416989.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pTRE_PSKH1_Luc and pTRE_hTF_Luc are indexed as mammalian reporter vectors whose payload is a luciferase fusion protein, in the tet-responsive pTRE naming series.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF416988.1 and genbank:AF416989.1, verified to contain Mammalian reporter vector, pTRE and luciferase. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 29. Do you have a retroviral transfer vector derived from Moloney murine leukemia virus?

- Acceptable IDs: `genbank:AF010170.1`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:AF010170.1` Plasmid pAMS with hybrid amphotropic/Moloney murine leukemia virus, complete sequence score=`0.6715` fields=`semantic, vector_type, organism`

Rationale: pAMS is the only corpus record indexed as a lentiviral or retroviral transfer vector, and its indexed description names a hybrid amphotropic/Moloney murine leukemia virus with gag, pol and env payloads. This is the first labeled retrieval target for that profile; the 2026-05-31 expansion recorded it as a corpus gap.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF010170.1, verified to contain Lentiviral or retroviral transfer vector, Moloney murine leukemia virus and gag. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 30. I need a GFP reporter plasmid that uses chloramphenicol rather than ampicillin for selection.

- Acceptable IDs: `genbank:FJ172221.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pCmGFP has gfp as its indexed payload and cat as its only indexed selectable marker, which is the ampicillin-free selection the query asks for. The indexed profile for this record is mammalian_reporter_vector, which is wrong: it is a bacterial GFP plasmid from Neisseria gonorrhoeae. The query is written to the evidence that is actually indexed and does not repeat the misclassification.
Source: Indexed plasmid_embeddings.composed_document for genbank:FJ172221.1, verified to contain gfp, cat and tac promoter. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 31. Which plasmid carries eGFP with ampicillin selection on a pUC-family origin?

- Acceptable IDs: `genbank:GQ404376.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pPRS3a has eGFP as its indexed payload with bla as the indexed marker and a pMB1/pUC indexed origin.
Source: Indexed plasmid_embeddings.composed_document for genbank:GQ404376.1, verified to contain eGFP, bla and pMB1/pUC origin. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 32. I want an E. coli plasmid that provides sacB counter-selection and a tac promoter.

- Acceptable IDs: `genbank:OP009361.1`
- Result: `hit at rank 5`
- Reciprocal rank: `0.200`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `curated:pUC18` pUC18 score=`0.6026` fields=`semantic, organism, promoters`
- 2. `genbank:AY608912.1` Escherichia coli plasmid pFL129, complete sequence score=`0.5858` fields=`semantic, organism, promoters`
- 3. `genbank:AF147463.1` T7 Expression vector pNam, complete sequence score=`0.5740` fields=`semantic, organism`
- 4. `curated:pUC19` pUC19c score=`0.5708` fields=`semantic, organism, promoters`
- 5. `genbank:OP009361.1` Escherichia coli plasmid pSGKp-Tmcr-500GFP, complete sequence score=`0.5638` fields=`semantic, organism, promoters`

Rationale: pSGKp-Tmcr-500GFP lists sacB among its indexed payloads and a tac promoter among its indexed promoters, and its indexed organism is Escherichia coli.
Source: Indexed plasmid_embeddings.composed_document for genbank:OP009361.1, verified to contain sacB, tac promoter and Escherichia coli. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 33. Recommend a broad-host-range cloning vector with kanamycin selection that does not rely on a pUC origin.

- Acceptable IDs: `genbank:U23751.1`
- Result: `hit at rank 1`
- Reciprocal rank: `1.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:U23751.1` Cloning vector pBBR1MCS-2 plasmid pBBR1MCS-2, complete sequence score=`0.7045` fields=`semantic, vector_type, organism, markers, application`
- 2. `genbank:GQ149343.1` Escherichia coli plasmid pAm05WL6211, complete sequence score=`0.7007` fields=`semantic, vector_type, organism, markers`
- 3. `genbank:GQ149347.1` Escherichia coli plasmid pAm08CQ6130, complete sequence score=`0.6751` fields=`semantic, vector_type, organism, markers`

Rationale: pBBR1MCS-2 is indexed as a bacterial cloning vector with a kanamycin resistance determinant and a dense MCS, and no pUC origin is indexed for it.
Source: Indexed plasmid_embeddings.composed_document for genbank:U23751.1, verified to contain Bacterial cloning vector, pBBR1MCS-2 and kanamycin resistance determinant. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 34. I need a T7 expression plasmid with a histidine-tag cassette on both sides of the cloning site.

- Acceptable IDs: `genbank:AF012911.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:AF087042.1` Cloning vector pCALnFLAG, complete sequence score=`0.7701` fields=`semantic, vector_type, organism, promoters, application`
- 2. `genbank:AF147463.1` T7 Expression vector pNam, complete sequence score=`0.7517` fields=`semantic, vector_type, organism, promoters`
- 3. `curated:pBluescript-II-SK-minus` pBluescript II SK(-) score=`0.7134` fields=`semantic, vector_type, organism, application`
- 4. `curated:pBluescript-II-SK-plus` pBluescript II SK(+) score=`0.7029` fields=`semantic, vector_type, organism, application`
- 5. `curated:pGEX-4T-1` pGEX-4T-1 score=`0.6711` fields=`semantic, vector_type, organism, application`

Rationale: pETHIS-1 has his6-mcs-his10 as both its indexed payload and its indexed cloning site, under an indexed T7 RNA polymerase promoter.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF012911.1, verified to contain his6-mcs-his10 and T7 RNA polymerase promoter. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 35. Is there a transposon-delivered luxAB bioluminescence reporter plasmid in the collection?

- Acceptable IDs: `genbank:U55385.2, genbank:U55819.2`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pRL1063a and pRL765 are the only corpus records with luxA and luxB among their indexed payloads, and both also index a transposase.
Source: Indexed plasmid_embeddings.composed_document for genbank:U55385.2 and genbank:U55819.2, verified to contain luxA, luxB and transposase. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 36. Looking for a cloning vector that carries both chloramphenicol and ampicillin resistance plus an f1 origin.

- Acceptable IDs: `genbank:U35125.1, genbank:U35126.1`
- Result: `hit at rank 5`
- Reciprocal rank: `0.200`
- Expected clarification: `False`
- Clarification needed: `False`

Retrieved:
- 1. `genbank:AY428809.1` Cloning vector pSUP202, complete sequence score=`0.7927` fields=`semantic, vector_type, organism, markers, application`
- 2. `genbank:U35235.1` Plasmid pBSL167 cloning vector, complete sequence score=`0.7663` fields=`semantic, vector_type, organism, markers, application`
- 3. `genbank:U35131.1` Plasmid pBSL159 cloning vector, complete sequence score=`0.7598` fields=`semantic, vector_type, organism, markers, application`
- 4. `genbank:U35132.1` Plasmid pBSL168 cloning vector, complete sequence score=`0.7593` fields=`semantic, vector_type, organism, markers, application`
- 5. `genbank:U35125.1` Plasmid pBSL119 cloning vector, complete sequence score=`0.7522` fields=`semantic, vector_type, organism, markers, application`

Rationale: pBSL119 and pBSL121 index a chloramphenicol acetyltransferase and a beta-lactamase together with an f1 origin, which is the two-marker combination requested.
Source: Indexed plasmid_embeddings.composed_document for genbank:U35125.1 and genbank:U35126.1, verified to contain Bacterial cloning vector, chloramphenicol acetyltransferase, beta-lactamase and f1 origin. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 37. I need a conditional-replication plasmid whose origin requires the pir gene product to be supplied by the host.

- Acceptable IDs: `genbank:AY608912.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pFL129 indexes pir as a payload and the gamma origin of plasmid R6K as its replication origin, which is the host-dependent replication the query describes.
Source: Indexed plasmid_embeddings.composed_document for genbank:AY608912.1, verified to contain pir and gamma origin of plasmid R6K. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 38. Which plasmid with a pUC19 multiple cloning site also carries kanamycin and bleomycin resistance?

- Acceptable IDs: `genbank:GQ149343.1, genbank:GQ149347.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pAm05WL6211 and pAm08CQ6130 both index a kanamycin resistance protein and a bleomycin resistance protein alongside ampicillin resistance.
Source: Indexed plasmid_embeddings.composed_document for genbank:GQ149343.1 and genbank:GQ149347.1, verified to contain kanamycin resistance protein and bleomycin resistance protein. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 39. Show me natural plasmids that carry a CRISPR cas gene cluster.

- Acceptable IDs: `genbank:CP000954.1, genbank:CP001724.1, genbank:CP002866.1, genbank:CP046159.1, genbank:CP183374.1, genbank:GQ900399.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: Each of these records indexes CRISPR-associated proteins among its payloads on a native bacterial or archaeal plasmid. The parser labels them crispr_vector, which overstates them: they are natural plasmids carrying cas genes, not genome-editing delivery vectors. The query is deliberately a cas-locus lookup so the gold label stays true to the record.
Source: Indexed plasmid_embeddings.composed_document for genbank:CP000954.1, genbank:CP001724.1, genbank:CP002866.1, genbank:CP046159.1, genbank:CP183374.1 and genbank:GQ900399.1, verified to contain CRISPR. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 40. Is there a plasmid encoding an anti-CRISPR protein that inhibits Cas9?

- Acceptable IDs: `genbank:CP160042.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: The Enterococcus faecalis ATCC 29212 unnamed2 plasmid is the only corpus record whose indexed payloads include a Cas9 inhibitor AcrIIA9 family protein.
Source: Indexed plasmid_embeddings.composed_document for genbank:CP160042.1, verified to contain Cas9 inhibitor AcrIIA9. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 41. I am studying heavy-metal resistance. Which plasmid carries a silver resistance determinant?

- Acceptable IDs: `genbank:AF067954.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pMG101 from Salmonella indexes silE, silR and silS, and is the only corpus record whose indexed document mentions silver.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF067954.1, verified to contain silE, silR and silver. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 42. Which plasmid carries a nickel and cobalt resistance gene cluster?

- Acceptable IDs: `genbank:AF322866.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pNRS148 from Hafnia alvei is the only corpus record indexing a nickel/cobalt resistance determinant, with ncrA, ncrB and ncrC as indexed markers.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF322866.1, verified to contain ncrA, nickel/cobalt and Hafnia alvei. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 43. Find a Klebsiella plasmid with a complete arsenic resistance operon.

- Acceptable IDs: `genbank:AF168737.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pMH12 from Klebsiella oxytoca indexes arsA, arsB, arsC, arsD and arsR as payloads with an arsenical resistance operon as its indexed marker.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF168737.1, verified to contain arsA, arsR and Klebsiella oxytoca. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 44. I need a Lactococcus lactis plasmid that confers cadmium resistance.

- Acceptable IDs: `genbank:AF243383.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pAH82 indexes cadA and cadC as selectable markers and Lactococcus lactis subsp. lactis as its organism.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF243383.1, verified to contain cadA, cadC and Lactococcus lactis. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 45. Which plasmid carries the CTX-M-17 extended-spectrum beta-lactamase?

- Acceptable IDs: `genbank:AY033516.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pIP843 from Klebsiella pneumoniae is the only corpus record indexing blaCTX-M-17 as a selectable marker.
Source: Indexed plasmid_embeddings.composed_document for genbank:AY033516.1, verified to contain blaCTX-M-17 and Klebsiella pneumoniae. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 46. Looking for a Lactobacillus plasmid carrying an ermT erythromycin resistance methylase.

- Acceptable IDs: `genbank:AF310974.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: p121BS from Lactobacillus sp. PC121B indexes methylase ermT as its selectable marker.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF310974.1, verified to contain ermT and Lactobacillus. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 47. Which Lactiplantibacillus plantarum plasmid carries tetM?

- Acceptable IDs: `genbank:AF440277.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Should the Tet-regulated design be Tet-On or Tet-Off?

Retrieved:
- <none>

Rationale: pMD5057 indexes tetM as its selectable marker with Lactiplantibacillus plantarum as its indexed organism.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF440277.1, verified to contain tetM and Lactiplantibacillus plantarum. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 48. Is there a Staphylococcus epidermidis plasmid with an ethidium bromide resistance determinant?

- Acceptable IDs: `genbank:AY092027.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pSepCH indexes an ethidium bromide resistance determinant as its selectable marker with Staphylococcus epidermidis as its indexed organism.
Source: Indexed plasmid_embeddings.composed_document for genbank:AY092027.1, verified to contain ethidium bromide resistance determinant and Staphylococcus epidermidis. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 49. Find the Francisella tularensis plasmid that carries a tetracycline resistance gene.

- Acceptable IDs: `genbank:AF055345.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pOM1 indexes tetC as a selectable marker and Francisella tularensis as its organism, and is the only corpus record naming pOM1.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF055345.1, verified to contain pOM1, tetC and Francisella tularensis. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 50. Which Helicobacter pylori plasmid encodes a putative microcin peptide?

- Acceptable IDs: `genbank:AF275307.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pHPM8 is the only corpus record indexing a putative microcin peptide, with Helicobacter pylori as its indexed organism.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF275307.1, verified to contain microcin and Helicobacter pylori. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 51. I am looking for the Staphylococcus aureus conjugative multiresistance plasmid pSK41.

- Acceptable IDs: `genbank:AF051917.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pSK41 is indexed by name with a tra conjugative transfer gene set and Staphylococcus aureus as its organism. This is an exact named lookup, which is the most common real retrieval pattern for natural plasmids.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF051917.1, verified to contain pSK41, traA and Staphylococcus aureus. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 52. Which Enterococcus faecalis plasmid carries tetL?

- Acceptable IDs: `genbank:AF503772.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Should the Tet-regulated design be Tet-On or Tet-Off?

Retrieved:
- <none>

Rationale: pAMalpha1 indexes tetL as its selectable marker with Enterococcus faecalis as its organism.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF503772.1, verified to contain pAMalpha1, tetL and Enterococcus faecalis. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 53. Find an Enterococcus faecium plasmid with an Axe-Txe toxin-antitoxin stability system.

- Acceptable IDs: `genbank:AF507977.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pRUM indexes both Axe and Txe among its payloads with Enterococcus faecium as its indexed organism.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF507977.1, verified to contain Axe, Txe and Enterococcus faecium. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 54. Which Staphylococcus aureus plasmid carries both a cadmium resistance operon and a beta-lactamase?

- Acceptable IDs: `genbank:AY373761.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pUB101 indexes cadD and cadX together with blaZ, blaI and blaR1, and indexes a cadDX operon as its promoter.
Source: Indexed plasmid_embeddings.composed_document for genbank:AY373761.1, verified to contain cadD, blaZ and Staphylococcus aureus. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 55. Looking for a Pseudomonas aeruginosa plasmid with a class 1 integron carrying a chloramphenicol efflux gene.

- Acceptable IDs: `genbank:AF313472.2`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: RPL11 indexes intI1 as a class 1 integron integrase alongside a CmlA1 leader peptide, with Pseudomonas aeruginosa as its indexed organism.
Source: Indexed plasmid_embeddings.composed_document for genbank:AF313472.2, verified to contain CmlA1, intI1 and Pseudomonas aeruginosa. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 56. Which Pasteurella multocida plasmid carries sulfonamide, tetracycline and chloramphenicol resistance together?

- Acceptable IDs: `genbank:AY232670.1`
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `False`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: pJR1 indexes sulII, tetG and catB2 as its three selectable markers, with Pasteurella multocida as its indexed organism.
Source: Indexed plasmid_embeddings.composed_document for genbank:AY232670.1, verified to contain sulII, tetG and catB2. WP-21 expansion against the 4455-record corpus on 2026-10-08.

### 57. Can you recommend a plasmid for my experiment?

- Acceptable IDs: ``
- Result: `miss`
- Reciprocal rank: `0.000`
- Expected clarification: `True`
- Clarification needed: `True`
- Clarification question: Which target organism or cell line should this plasmid design use?

Retrieved:
- <none>

Rationale: The request names no host, no application and no selection requirement. Retrieval should ask what the construct is for rather than return a ranked list.
Source: No corpus target is claimed. Recorded as expected retrieval behaviour for an underspecified request against the 4455-record corpus on 2026-10-08.
