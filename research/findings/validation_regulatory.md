> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Deterministic Regulatory-Element Compatibility Check

## Scope

This finding designs the Phase 3 regulatory compatibility checker required by `SYSTEM_DESIGN.md` Section 8.2 item 4. It is deterministic validation logic, not ML and not a claim that a construct is experimentally optimal. The checker answers four narrow questions:

1. Is each expression promoter compatible with the intended host and transcript class?
2. Does the construct contain the selectable-marker evidence required by its vector profile and target workflow?
3. Does the replication origin evidence support the intended propagation host?
4. Is a host-appropriate terminator or polyadenylation signal downstream of the GOI/expression slot?

The checker should return one `ValidationCheck` per sub-rule, using the existing `PASS | WARN | FAIL` semantics in `packages/core/schemas/models.py`. It should operate on `AnnotatedSequence`, `DesignSpec`, and profile metadata; it should not re-parse raw GenBank or infer hidden biology from sequence alone once Phase 0 annotation has run.

Out of scope: promoter strength optimization, cell-line-specific expression tuning, induction dose, viral titer prediction, packaging capacity, codon optimization, restriction-site conflicts, therapeutic regulatory approval, and provider synthesis acceptance. Those belong to other Phase 3 checks or later advisory layers.

## Inputs

Primary inputs:

- `AnnotatedSequence.sequence`: normalized ACGT sequence.
- `AnnotatedSequence.topology`: `circular` or `linear`; needed for downstream/coordinate logic across base 1.
- `AnnotatedSequence.features`: canonical features with `type`, `start`, `end`, `strand`, `name`, and `confidence`. The regulatory check consumes feature types `ORI`, `promoter`, `GOI`, `marker`, `MCS`, `terminator`, and relevant `other` viral/CRISPR signals.
- `AnnotatedSequence.vector_profile`: profile string produced by `packages/data_pipeline/parse/classify.py`.
- `AnnotatedSequence.annotation_complete`: reported but not by itself a failure if explicit requested evidence is present.
- `DesignSpec.organism`, `cell_line`, `vector_type`, `genes`, `promoter_type`, `inducer`, `markers`, `application`, and `constraints`.
- `packages/data_pipeline/parse/vector_profiles.yaml`: profile-aware required/optional/not-required component policy.
- `packages/data_pipeline/parse/references/component_library.json`: reference component names, aliases, origin host classes, and replication roles.
- Parser support helpers: `marker_support.distinct_marker_classes`, `origin_support.general_shuttle_evidence`, and the expression-cassette evidence patterns in `expression_evidence.py`.

Derived controlled vocabularies should be encoded in a future validation config, not hard-coded into procedural logic. Initial tables:

- Host classes:
  - `bacterial`: `Escherichia coli`, bacterial expression/cloning contexts, and bacterial propagation.
  - `mammalian`: named mammalian cell lines such as HEK293, CHO, HeLa, Jurkat, iPSC-derived cells, and `organism` values containing human, mouse, rat, hamster, or mammalian.
  - `yeast`: `Saccharomyces cerevisiae` and yeast shuttle contexts.
  - `viral_transfer`: lentiviral/retroviral/AAV transfer vector contexts; these still require bacterial propagation elements for plasmid production.
  - `unknown`: missing or unrecognized host.
- Promoter classes:
  - Bacterial RNAP promoters: `lac`, `tac`, `trc`, `araBAD/pBAD`, `T7`, `T3`, `SP6`, `lpp-lac`, plus future RegulonDB-backed E. coli promoters.
  - Mammalian RNA polymerase II promoters: `CMV`, `EF1a`, `CAG`, `PGK`, `SV40`, `TRE`, `RSV`, `CBh`.
  - Mammalian RNA polymerase III small-RNA promoters: `U6`, `H1`, `7SK`.
  - Yeast promoters: `GAL1`, `TEF1`, `ADH1`, `CYC1`, `GPD/TDH3`.
  - Viral terminal/promoter elements: `5' LTR`, `3' LTR`, chimeric/self-inactivating LTR; these are vector-profile signals, not a substitute for a host-matched internal promoter when the transfer vector requires one.
- Origin classes:
  - Bacterial autonomous origins: pMB1/pUC/pBR322/ColE1, p15A, pSC101, R6K, broad-host-range bacterial origins.
  - Yeast autonomous origins/maintenance: ARS/ARSH4, CEN/ARS, 2-micron.
  - Conditional/helper-dependent origins: SV40 origin, f1 origin, oriT. These do not independently satisfy autonomous host replication.
  - Viral ITR/LTR elements are not plasmid ORIs for bacterial propagation.
- Marker classes:
  - Bacterial selection: ampicillin/carbenicillin, kanamycin, chloramphenicol, tetracycline, spectinomycin, streptomycin, gentamicin, zeocin where used in bacteria.
  - Mammalian stable selection: G418/neomycin, hygromycin, puromycin, blasticidin, zeocin.
  - Yeast auxotrophic/drug selection: URA3, LEU2, HIS3, TRP1, ADE2, kanMX/G418, hygMX, natMX.
  - Reporter-only genes such as GFP/luciferase are not selectable markers unless a profile explicitly treats reporter enrichment as optional, not selectable, evidence.

## Rule Logic

The checker should compute a normalized `HostContext` from `DesignSpec` and vector profile before evaluating sub-rules:

- `expression_host_class`: where the GOI or guide/reporter should function.
- `propagation_host_classes`: hosts in which the plasmid must be maintained before use. Default includes `bacterial` for all ordinary engineered plasmids because bacterial propagation is expected unless `DesignSpec.constraints` explicitly says otherwise.
- `profile`: `DesignSpec.vector_type` if supplied, otherwise `AnnotatedSequence.vector_profile`.
- `payload_kind`: `protein_coding`, `small_rna`, `reporter`, `cloning_slot_only`, or `unknown`, inferred from `genes`, `tags`, `application`, `promoter_type`, GOI/MCS features, and CRISPR/sgRNA signals.

### Promoter-Host Compatibility

Evaluate only expression-relevant promoters. Sequencing/primer promoters in cloning vectors should not fail a bacterial cloning profile merely because they do not drive the requested payload.

Rules:

- PASS when a promoter class matches the expression host and payload kind:
  - bacterial host plus bacterial expression promoter and an oriented downstream `GOI` or `MCS`;
  - mammalian host plus RNAP II promoter and protein-coding/reporter `GOI` or `MCS`;
  - mammalian CRISPR guide/small-RNA payload plus RNAP III `U6` or `H1` promoter upstream of guide/scaffold evidence;
  - yeast host plus yeast promoter upstream of `GOI` or `MCS`.
- FAIL when the only payload-driving promoter is clearly incompatible:
  - bacterial-only promoter driving a mammalian protein-coding payload;
  - mammalian/yeast promoter as the only promoter in an in-vivo bacterial expression vector;
  - mammalian RNAP III promoter as the only promoter for a protein-coding GOI;
  - mammalian RNAP II promoter as the only promoter for an sgRNA/shRNA cassette when no RNAP III small-RNA promoter is present;
  - yeast promoter as the only promoter for bacterial or mammalian expression, unless the vector is explicitly yeast-targeted.
- WARN when compatibility is plausible but incomplete:
  - no recognized promoter class, but the profile is cloning-only or the construct has only MCS/no GOI;
  - multiple promoters from different host classes exist and the oriented payload-driving promoter cannot be selected deterministically;
  - a T7/T3/SP6 promoter is present for bacterial expression but no T7/SP6/T3 polymerase host system or expression corroboration is present;
  - CMV is used in a mammalian expression vector where context-dependent silencing may matter; this is a warning, not a hard failure;
  - inducible promoter requested in `DesignSpec.promoter_type` or `inducer`, but no matching operator/inducer evidence is annotated.

Deterministic promoter-to-payload selection:

- A promoter drives a slot if, on strand `+1`, a `GOI` or `MCS` starts after the promoter end; on strand `-1`, a slot ends before the promoter start. Use the nearest same-strand slot within a configurable maximum window, initially 10 kb.
- If no oriented slot exists, the promoter can still satisfy a profile-level marker or reporter rule only when the profile metadata says a complete expression cassette is not required.
- For circular sequences, downstream order must be evaluated with circular distance when topology is `circular`.

### Selectable-Marker Presence

Rules:

- FAIL when no `marker` feature exists and the vector profile requires a selectable marker. All current profiles in `vector_profiles.yaml` require at least one marker for training-eligible completeness.
- PASS when at least one marker class matches the required propagation host:
  - bacterial propagation requires a bacterial selectable marker;
  - yeast shuttle vectors require at least one bacterial marker and at least one yeast marker;
  - mammalian expression vectors require a bacterial marker; a mammalian stable-selection marker is required only when `DesignSpec.markers` requests it, `application` includes stable selection, or `constraints` mention stable cell-line selection.
- FAIL when `DesignSpec.markers` names a specific marker class and no marker feature matches it via controlled aliases.
- WARN when the marker is present but host use is ambiguous:
  - `NeoR/KanR` appears in a mammalian vector; it may support bacterial kanamycin and/or mammalian G418 depending on promoter/context, so require explicit feature-name or promoter context before counting both;
  - resistance-like genes appear in natural plasmid records without engineered-vector metadata;
  - reporter genes are present but no true selectable marker is present;
  - marker feature confidence is below the parser's trusted/reference threshold.
- PASS for CRISPR/lentiviral/reporter profiles when bacterial marker evidence exists and optional fluorescent/drug selection evidence is absent, unless the spec requested selection.

Implementation detail: use `distinct_marker_classes(features)` for antibiotic-family matching, but extend validation config with host usability for each marker class. Avoid treating clinical/natural AMR payloads as vector-selection evidence unless the record is already classified as an engineered vector or has trusted vector metadata.

### ORI-Host Compatibility

Rules:

- FAIL when no autonomous origin supports every required propagation host:
  - any ordinary plasmid vector with no bacterial autonomous ORI fails, because bacterial propagation is expected;
  - yeast shuttle vectors require bacterial autonomous ORI plus yeast ARS/CEN/2-micron evidence;
  - general shuttle vectors require autonomous origin evidence for at least two host classes or trusted exact shuttle-vector metadata plus a recognized origin/replicon signal.
- PASS when recognized autonomous origin evidence matches the propagation host class:
  - pMB1/pUC/pBR322/ColE1/p15A/pSC101/R6K style origins for bacterial propagation;
  - ARS/CEN/2-micron for yeast maintenance;
  - profile-specific broad-host-range origins when the host table explicitly includes the requested bacterial genus/species.
- WARN rather than PASS when origin evidence is only conditional/helper-dependent:
  - f1 origin supports ssDNA rescue/phagemid behavior but not normal autonomous plasmid maintenance;
  - oriT supports transfer/mobilization, not replication;
  - SV40 origin is conditional on large T antigen and does not replace bacterial ORI for plasmid production;
  - viral ITR/LTR elements support packaging/integration biology, not bacterial plasmid replication.
- WARN when `DesignSpec.organism` is outside calibrated host tables but the profile is `general_shuttle_vector`; do not infer broad-host-range behavior from a generic `rep` feature.
- FAIL when the only origin is from a mismatched host class and the profile requires autonomous maintenance in the requested host.

Implementation detail: re-use `origin_support._origin_references()` or expose a public equivalent so the validation engine reads the same origin metadata as the classifier. The validation rule should distinguish `replication_role == autonomous` from `ssdna_rescue`, `transfer`, and `conditional_replication`.

### Terminator Downstream of GOI

Rules:

- PASS when a terminator/polyA signal is downstream of each expression `GOI` on the same strand:
  - bacterial expression: Rho-independent terminator such as T7, rrnB, T0, or annotated terminator downstream of the coding slot;
  - mammalian protein/reporter expression: polyadenylation signal such as BGH, SV40, rabbit beta-globin, or annotated polyA/terminator downstream;
  - yeast expression: yeast terminator/polyA such as CYC1, ADH1, TEF1, or annotated yeast terminator downstream.
- FAIL when an expression profile has a recognized GOI and promoter but no downstream terminator/polyA evidence.
- FAIL when the nearest terminator is upstream of the GOI on the same strand, or downstream only on the opposite strand, and no other valid terminator exists.
- WARN when the profile is cloning-only and contains no expression cassette; terminator is not required for `bacterial_cloning_vector`.
- WARN when the payload is CRISPR guide/small RNA and no explicit RNAP III termination signal is annotated, because current parser support may not detect short pol III termination tracts reliably.
- WARN when multiple GOIs exist and at least one lacks a downstream terminator, unless the design is a known polycistronic cassette with a shared downstream terminator and deterministic coordinate order confirms all ORFs are before that terminator.

Coordinate logic:

- For strand `+1`, terminator is downstream if `terminator.start >= goi.end`.
- For strand `-1`, terminator is downstream if `terminator.end <= goi.start`.
- For circular sequences, use circular distance from GOI end to terminator start on `+1`, and from GOI start backward to terminator end on `-1`.
- Initial maximum allowed GOI-to-terminator distance should be advisory, not a FAIL threshold. Start with WARN if the nearest downstream terminator is more than 5 kb away from the GOI end unless the profile has known long 3-prime elements.

## PASS/WARN/FAIL Semantics

Overall regulatory check status:

- `FAIL` if any required sub-rule fails.
- `WARN` if no sub-rule fails but at least one sub-rule warns.
- `PASS` only when all required sub-rules pass and optional warnings are absent.

Sub-rule status policy:

- `PASS`: deterministic evidence supports the requested host/profile/payload.
- `WARN`: evidence is missing, ambiguous, profile-exempt, conditional, or biologically plausible but risky; the design may be returned but the report must state what is uncertain.
- `FAIL`: deterministic evidence contradicts a required biological dependency or a requested explicit component is missing.

Recommended check names:

- `regulatory.promoter_host`
- `regulatory.selectable_marker`
- `regulatory.ori_host`
- `regulatory.terminator_downstream`
- `regulatory.profile_consistency`

Messages should include: normalized host class, profile, matched features, missing requirement, and an actionable fix. Example: `FAIL: mammalian_expression_vector for HEK293 has CMV promoter and EGFP GOI but no downstream mammalian polyA/terminator feature; add BGH, SV40, or another mammalian polyA signal downstream of the GOI.`

Regions:

- For missing features, `region = null`.
- For incompatible existing features, use the offending promoter/ORI/marker/GOI region.
- For terminator-placement failures, use the GOI region if the terminator is absent; use the mismatched terminator region when a terminator exists but is upstream/opposite-strand.

## Profile-Specific Rules

### `bacterial_cloning_vector`

- Promoter-host: PASS or WARN-only; expression promoter not required. T3/T7/SP6/lac sequencing promoters should not fail cloning-only vectors.
- Marker: require bacterial marker. FAIL if absent.
- ORI: require bacterial autonomous ORI. FAIL if only f1/oriT/conditional origin is present.
- Terminator: not required. WARN only if a GOI and expression promoter are present but terminator is absent, because the construct may be more than cloning-only.

### `bacterial_expression_vector`

- Promoter-host: require bacterial expression promoter with oriented `GOI` or `MCS`. T7 requires expression-cassette corroboration or host/system evidence; T3/SP6 alone should warn or fail depending on requested in-vivo expression.
- Marker: require bacterial marker; specific marker request must match.
- ORI: require bacterial autonomous ORI.
- Terminator: require downstream bacterial terminator when a GOI is present; warn when only MCS exists.

### `mammalian_expression_vector`

- Promoter-host: require mammalian RNAP II promoter for protein-coding/reporter GOI. RNAP III promoters count only for small RNA cassettes.
- Marker: require bacterial marker for plasmid propagation. Require mammalian marker only when requested or stable selection is in scope.
- ORI: require bacterial autonomous ORI. SV40 origin is optional/conditional and cannot substitute for bacterial ORI.
- Terminator: require downstream mammalian polyA/terminator for each GOI or shared cassette.

### `mammalian_reporter_vector`

- Promoter-host: if the profile is promoterless reporter, absence of mammalian promoter is WARN/PASS depending on `DesignSpec.application`; do not fail pGL3-Basic-like promoter-testing vectors for lacking a built-in promoter. If `DesignSpec` requests direct expression in mammalian cells, require a compatible promoter or explicit promoter-cloning-site expectation.
- Marker: require bacterial marker; mammalian selection only if requested.
- ORI: require bacterial autonomous ORI; f1 is optional phagemid support only.
- Terminator: require reporter downstream polyA/terminator unless the vector is explicitly a promoterless assay backbone with existing reporter termination evidence.

### `lentiviral_or_retroviral_transfer_vector`

- Promoter-host: require either a valid LTR-driven transfer design or a host-compatible internal promoter for the payload. For 3rd-generation/self-inactivating transfer designs, an internal mammalian promoter is normally expected for GOI expression.
- Marker: require bacterial marker for plasmid propagation. Drug/fluorescent selection marker is optional unless requested.
- ORI: require bacterial autonomous ORI. LTRs are not ORIs.
- Terminator: require downstream polyA/3-prime LTR termination evidence for the transcript. Warn if viral terminal elements are missing, but the detailed viral-transfer-element check should live in a viral-specific validator.
- Safety note: absence of `gag`, `pol`, and `env` in transfer plasmids is expected and should not fail regulatory compatibility.

### `crispr_vector`

- Promoter-host: apply cassette-level rules. sgRNA/shRNA requires RNAP III `U6`/`H1`-class promoter unless the design explicitly uses an alternative validated guide-expression system. Cas protein GOI requires host-compatible RNAP II promoter in mammalian contexts or bacterial promoter in bacterial CRISPR contexts.
- Marker: require bacterial marker. Require selectable/enrichment marker only when requested.
- ORI: require bacterial autonomous ORI. Add yeast/other host origin only for shuttle CRISPR vectors.
- Terminator: require downstream polyA for Cas/protein GOI. For guide RNA cassettes, warn if no pol III terminator is annotated until the parser gains short-terminator support.

### `yeast_shuttle_vector`

- Promoter-host: yeast promoter required only for yeast expression requests; base pRS-style shuttle/maintenance vectors can pass without an expression cassette.
- Marker: require bacterial marker and yeast marker evidence such as URA3/LEU2/HIS3/TRP1 or validated drug marker.
- ORI: require bacterial autonomous ORI plus yeast ARS/CEN or 2-micron maintenance.
- Terminator: require yeast terminator only when a yeast expression GOI is present.

### `general_shuttle_vector`

- Promoter-host: require promoter matching the requested expression host when expression is requested; otherwise warn if host is ambiguous.
- Marker: require bacterial marker and, if the second host is explicit and selectable maintenance is requested, second-host marker evidence.
- ORI: require autonomous origins for each declared host class, or trusted shuttle metadata plus recognized host-specific origin evidence. Do not count f1 or oriT as autonomous host support.
- Terminator: require host-compatible terminator/polyA only for expression cassettes.

### `unknown`

- Promoter-host: WARN if evidence is insufficient; FAIL only on explicit contradiction with `DesignSpec`.
- Marker: FAIL if `DesignSpec.markers` requests a marker and none matches; otherwise WARN if no marker exists.
- ORI: WARN if no recognized autonomous ORI exists; FAIL only when the spec requires a host-specific replicating plasmid.
- Terminator: WARN if GOI/promoter exists without terminator; FAIL only for explicit expression-vector requests.

## Edge Cases

- Promoterless reporter vectors: pGL3-Basic-like vectors are valid promoter-testing backbones. Do not fail for missing promoter unless the spec asks for direct reporter expression without promoter insertion.
- Cloning vectors with T7/T3/SP6 promoters: these are often sequencing or in-vitro transcription sites around an MCS. Do not classify or validate them as bacterial expression cassettes unless there is oriented payload and expression corroboration.
- `NeoR/KanR`: one CDS may support bacterial kanamycin and mammalian G418 depending on regulatory context. Count it conservatively; do not satisfy both hosts unless feature name/metadata or promoter context supports both.
- Natural AMR plasmids: resistance genes in natural plasmids are not automatically engineered selectable markers. Require engineered-vector profile or trusted vector metadata before allowing them to satisfy marker checks.
- f1 origin/phagemids: f1 supports ssDNA rescue, not normal bacterial plasmid replication. It is optional support, not a substitute for pMB1/ColE1/p15A/etc.
- SV40 origin: conditional on large T antigen and host cell context. Warn when used as mammalian replication evidence and still require bacterial ORI for plasmid propagation.
- oriT: transfer origin, not replication origin. Never count as autonomous ORI.
- Circular origin wrap: GOI and downstream terminator may cross coordinate zero. Use circular-aware downstream distance.
- Multiple expression cassettes: evaluate each promoter-GOI-terminator cassette independently; overall FAIL if any required cassette fails.
- Polycistronic/2A/IRES designs: a single downstream terminator may serve multiple ORFs if coordinate order places all ORFs upstream of the terminator on the same transcript.
- Bidirectional promoters: current `AnnotatedFeature` has one strand. Warn until the parser can represent bidirectional promoter behavior explicitly.
- Low-confidence parser features: warn when a required component is detected only below a configurable confidence threshold; fail only if no acceptable evidence remains.
- Missing `DesignSpec.vector_type`: use `AnnotatedSequence.vector_profile`, but warn that validation is profile-inferred.
- Conflicting `DesignSpec.vector_type` and `AnnotatedSequence.vector_profile`: add `regulatory.profile_consistency = WARN` or FAIL when the conflict changes required components, e.g. spec says mammalian expression but annotation classifies bacterial cloning.
- Inducible systems: require both promoter/operator class and `DesignSpec.inducer` match when inducible expression was requested. Missing inducer/operator is WARN unless the promoter-host itself is incompatible.
- Lentiviral transfer plasmids: absence of packaging genes is expected. Presence of gag/pol/env in a generated transfer plasmid should be handled by viral/biosecurity checks, but regulatory compatibility should not require them.

## Test Fixtures

Use small synthetic annotated constructs for unit tests and curated real-vector fixtures for integration tests. Each test should assert both status and message content.

Minimal PASS fixtures:

- `pass_bacterial_cloning_puc`: bacterial profile, pMB1/pUC ORI, AmpR, MCS; no promoter/terminator required.
- `pass_bacterial_expression_tac_gst`: bacterial expression profile, pMB1 ORI, AmpR/KanR, tac promoter upstream of GST/GOI, T7 or rrnB terminator downstream.
- `pass_mammalian_expression_cmv_egfp`: mammalian expression profile, bacterial ORI, bacterial marker, CMV promoter upstream of EGFP, SV40/BGH polyA downstream.
- `pass_promoterless_reporter_pgl3_basic`: mammalian reporter profile, bacterial ORI, AmpR, luciferase GOI, SV40 polyA, no built-in mammalian promoter, `application = promoter assay`.
- `pass_yeast_shuttle_prs416`: bacterial ORI, bacterial marker, ARSH4/CEN, URA3 marker; no expression cassette required.
- `pass_crispr_dual_cassette`: U6 promoter upstream of sgRNA scaffold, mammalian RNAP II promoter upstream of Cas9 GOI, polyA downstream of Cas9, bacterial ORI and marker.

Minimal FAIL fixtures:

- `fail_mammalian_with_lac_only`: HEK293/mammalian expression spec, lac promoter only upstream of GOI.
- `fail_bacterial_with_cmv_only`: E. coli expression spec, CMV promoter only upstream of GOI.
- `fail_rnap3_for_protein`: mammalian protein-coding GOI driven only by U6/H1.
- `fail_missing_marker`: profile requiring marker, no marker features.
- `fail_requested_marker_mismatch`: spec requests puromycin, construct has only ampicillin.
- `fail_missing_bacterial_ori`: ordinary plasmid profile with marker/promoter/GOI but no autonomous bacterial ORI.
- `fail_f1_only_origin`: phagemid f1 origin but no bacterial autonomous ORI.
- `fail_mammalian_no_polyA`: CMV promoter and GOI but no downstream terminator/polyA.
- `fail_wrong_strand_terminator`: terminator exists upstream or opposite-strand relative to GOI.
- `fail_yeast_shuttle_no_yeast_origin`: yeast shuttle profile with bacterial ORI/marker and URA3 but no ARS/CEN/2-micron evidence.

Minimal WARN fixtures:

- `warn_unknown_profile_components_present`: unknown profile with ORI/marker/GOI but unclear promoter class.
- `warn_t7_no_expression_corroboration`: T7 promoter upstream of GOI but no RBS/lacO/tag/host-system evidence.
- `warn_sin_lenti_internal_promoter_missing`: lentiviral transfer profile with LTRs but no internal promoter for GOI expression.
- `warn_sgRNA_no_pol3_terminator_annotation`: U6-sgRNA cassette with no annotated short terminator.
- `warn_s40_conditional_origin_only_for_mammalian`: SV40 origin present, but bacterial ORI still required or present separately.
- `warn_multiple_promoters_ambiguous_driver`: bacterial and mammalian promoters both near a GOI with no deterministic nearest same-strand driver.

Integration fixtures should reuse current local/corpus-backed examples where available: pUC19, pGEX-4T-1, pEGFP-N1, pGL3-Basic, pGL4.10[luc2], pRS416, and pACYC184 once its second-marker policy is resolved. The current corpus has no classified lentiviral or CRISPR seed, so viral/CRISPR tests should start as synthetic annotated fixtures until provenance-approved seeds exist.

## Citations

1. Addgene, "Plasmids 101: The Promoter Region - Let's Go!" Establishes promoter compatibility with RNA type and host organism, including limited crossover among eukaryotic hosts and bacterial versus eukaryotic promoter differences. https://blog.addgene.org/plasmids-101-the-promoter-region
2. Addgene, "Plasmids 101: Terminators and PolyA signals." Establishes that terminators/polyA signals are downstream of the transcribed gene and affect RNA processing and expression. https://blog.addgene.org/plasmids-101-terminators-and-polya-signals
3. Addgene, "Plasmids 101: Mammalian Vectors." Notes mammalian vector compatibility requirements and that bacterial ORIs do not allow plasmid replication in mammalian cells; also discusses mammalian versus bacterial selection behavior of neo/kan. https://blog.addgene.org/plasmids-101-mammalian-vectors
4. Addgene, "Plasmids 101: Shuttle Vectors." Describes shuttle-vector logic and the need for species-compatible expression/selection components. https://blog.addgene.org/plasmids-101-shuttle-vectors
5. Addgene, "Lentiviral Vector Guide." Describes transfer plasmids, LTRs, packaging genes supplied in trans, and separation of required components across plasmids for safety. https://www.addgene.org/lentiviral/packaging/
6. Addgene, "Viral Vectors 101: Viral Vector Elements." Describes transfer plasmids versus helper/packaging plasmids and LTR terminal functions. https://blog.addgene.org/viral-vectors-101-viral-vector-elements
7. Thermo Fisher, pcDNA3.1 vector documentation/catalog page. Documents a mammalian expression architecture with CMV promoter, BGH polyadenylation signal, bacterial origin, and antibiotic resistance marker. https://www.thermofisher.com/order/catalog/product/V79020
8. Thermo Fisher, pcDNA3.1/GS vector map PDF. Public map labels CMV promoter, BGH polyadenylation signal, and pMB1/pUC-derived origin coordinates. https://tools.thermofisher.com/content/sfs/vectors/pcdna3.1gs_horf.pdf
9. GenScript, "pET-28a(+)-TEV" vector page. Documents an E. coli expression vector driven by T7 promoter/lac operator with kanamycin resistance and pUC/pBR322/pMB1 origin. https://www.genscript.com/vector/detail?vector_name=cEVULTI4YSglMkIpLVRFVg%3D%3D
10. Promega, "pGL3 Luciferase Reporter Vectors Technical Manual." Documents pGL3 reporter architecture including luciferase, ampicillin resistance, f1 origin, enhancer/polyA context, and promoter-testing variants. https://www.promega.com/-/media/files/resources/protocols/technical-manuals/0/pgl3-luciferase-reporter-vectors-protocol.pdf
11. Thermo Fisher, pYES2 catalog/documentation. Documents yeast shuttle/expression elements including 2-micron origin, URA3 selection, GAL1 promoter, and bacterial propagation elements. https://www.thermofisher.com/order/catalog/product/V82520
12. Sikorski RS and Hieter P. "A system of shuttle vectors and yeast host strains designed for efficient manipulation of DNA in Saccharomyces cerevisiae." Genetics. 1989;122(1):19-27. Establishes pRS yeast shuttle-vector architecture and yeast selectable-marker/maintenance logic. https://doi.org/10.1093/genetics/122.1.19
13. Studier FW and Moffatt BA. "Use of bacteriophage T7 RNA polymerase to direct selective high-level expression of cloned genes." Journal of Molecular Biology. 1986;189(1):113-130. Establishes T7 RNAP-based bacterial expression system context. https://doi.org/10.1016/0022-2836(86)90385-2
14. Guzman LM, Belin D, Carson MJ, Beckwith J. "Tight regulation, modulation, and high-level expression by vectors containing the arabinose PBAD promoter." Journal of Bacteriology. 1995;177(14):4121-4130. Supports PBAD/araBAD bacterial inducible-promoter classification. https://doi.org/10.1128/jb.177.14.4121-4130.1995
15. Khan KH. "Gene Expression in Mammalian Cells and its Applications." Advanced Pharmaceutical Bulletin. 2013. Lists mammalian expression-vector elements including promoter, terminator/polyA, prokaryotic origin, and markers. https://pmc.ncbi.nlm.nih.gov/articles/PMC7147855/
16. Zhao J, Hyman L, Moore C. "Formation of mRNA 3' Ends in Eukaryotes." Microbiology and Molecular Biology Reviews. 1999. Reviews eukaryotic cleavage/polyadenylation signal architecture. https://pmc.ncbi.nlm.nih.gov/articles/PMC98971/
17. Haellman V and Piras V. "The sound of silence: transgene silencing in mammalian cell engineering." Biotechnology Advances. 2023. Supports warning-level treatment of promoter silencing/context variability. https://pmc.ncbi.nlm.nih.gov/articles/PMC9880859/
18. Cong L et al. "Multiplex genome engineering using CRISPR/Cas systems." Science. 2013. Describes CRISPR vector formats using guide RNA and Cas expression cassettes. https://doi.org/10.1126/science.1231143
19. Sanjana NE, Shalem O, Zhang F. "Improved vectors and genome-wide libraries for CRISPR screening." Nature Methods. 2014. Supports CRISPR vector profile distinctions for Cas/sgRNA modules and lentiviral guide-library vectors. https://doi.org/10.1038/nmeth.3047
20. DDBJ/ENA/GenBank Feature Table Definition. Defines feature types such as `rep_origin`, promoter/regulatory, CDS, and terminator/polyA-related annotations used by the parser. https://www.ddbj.nig.ac.jp/ddbj/feature-table.html
