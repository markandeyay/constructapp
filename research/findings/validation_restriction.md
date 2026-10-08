> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Restriction-Site Conflict Validation Spec

## Scope

Design the Phase 3 deterministic `RestrictionSiteConflictCheck` described in `SYSTEM_DESIGN.md` Section 8.2 item 1. The check answers one narrow question: would the restriction-enzyme cut pattern of the generated `AnnotatedSequence` break the cloning strategy implied by `DesignSpec.cloning_method` and explicit user constraints?

This check is not a general synthesis-complexity checker, not primer design, not diagnostic digest design, and not an automatic sequence-domestication step. It may recommend remediation text, but it must not rewrite sequence.

## Inputs

Required runtime inputs:

- `AnnotatedSequence.sequence`: normalized ACGT sequence.
- `AnnotatedSequence.topology`: `circular` or `linear`; circular designs must be searched as circular molecules.
- `AnnotatedSequence.features`: feature coordinates using the current schema's 0-based, half-open intervals. At minimum, the check needs `GOI`, `MCS`, and relevant `other` cloning-slot or insert-part annotations when present.
- `DesignSpec.cloning_method`: currently free text, normalized by the checker into a cloning strategy profile.
- `DesignSpec.constraints`: free-text constraints that may name enzymes, required uniqueness, forbidden internal sites, provider/system standards, or diagnostic digest requirements.
- Optional future structured fields should be added when implementation reaches Phase 3: `cloning_strategy`, `intended_enzymes`, `assembly_standard`, `insert_feature_ids`, `cloning_slot_feature_id`, `expected_cut_regions`, `allowed_cut_regions`, `forbidden_feature_types`, `diagnostic_digest_enzymes`, and `enzyme_policy`.

Minimum normalization behavior:

- Parse enzyme names and common aliases case-insensitively from `cloning_method` and `constraints`.
- Normalize strategy names into: `restriction_ligation`, `golden_gate_type_iis`, `gateway_topo`, `gibson_hifi_lic`, `synthesis_only`, or `unknown`.
- Treat phrases such as "EcoRI/HindIII cloning", "restriction cloning", and "digest and ligate" as `restriction_ligation`.
- Treat "Golden Gate", "MoClo", "GoldenBraid", and explicit type IIS enzyme workflows such as `BsaI`, `BsmBI/Esp3I`, `BbsI`, `SapI/BspQI`, or `PaqCI/AarI` as `golden_gate_type_iis`.
- Treat "Gibson", "NEBuilder", "HiFi", "In-Fusion", "LIC", and "SLIC" as homology/overlap workflows where incidental restriction sites are not conflicts unless the user also specified restriction enzymes or no-site constraints.

## Reference data

Use Biopython `Bio.Restriction` for deterministic local restriction analysis. The project currently has Biopython 1.87 installed; pin the supported Biopython version in Phase 3 and record it in check metadata. Biopython's restriction package is REBASE-derived and supports `RestrictionBatch`, `AllEnzymes`, `CommOnly`, and `Analysis(batch, sequence, linear=False)` for circular searches.

Use a local version-pinned enzyme catalog for policy metadata, seeded from Biopython and refreshed from REBASE/NEB review data. The catalog should contain:

- canonical enzyme name;
- aliases/isoschizomers, e.g. BsmBI/Esp3I and SapI/BspQI;
- recognition sequence;
- cut offsets and overhang class;
- enzyme type, especially type IIS;
- commercial availability;
- methylation sensitivity and warnings;
- whether the enzyme is allowed for default design, hidden unless explicitly requested, or unsupported.

Runtime validation must not call web tools. REBASE/NEB may be used during reference-data refresh and source review, not during user-request validation.

Default enzyme set:

- For explicit named-enzyme strategies, analyze exactly the named enzymes after alias normalization.
- For Golden Gate-style workflows where no enzyme is named, default to a reviewed type IIS profile of `BsaI`, `BsmBI`/`Esp3I`, `BbsI`, `SapI`/`BspQI`, and `PaqCI`/`AarI`, but report `WARN` that the method needs an explicit enzyme/standard before final wet-lab handoff.
- For "unique MCS" backbone validation without a named strategy, analyze MCS enzymes detected inside the annotated `MCS` feature, limited to commercially available type II enzymes in `CommOnly`, and warn rather than fail on extra non-required sites.

## Rule logic

1. Build a normalized `RestrictionRuleProfile` from `DesignSpec`.

   Fields: `strategy`, `enzymes`, `required_cut_regions`, `allowed_cut_regions`, `forbidden_regions`, `require_unique_sites`, `require_no_internal_insert_sites`, `require_cut_in_mcs`, `diagnostic_only`, and `strictness`.

2. Run Biopython analysis.

   Use `RestrictionBatch(profile.enzymes)` and `Analysis(..., linear=(topology == "linear"))`. Convert Biopython's biological 1-based cut positions into canonical 0-based coordinates for reporting. Also compute recognition-site spans separately from cut positions, because type IIS enzymes cut outside the recognition sequence.

3. Classify each site by feature overlap.

   A site is in the intended cloning region when its recognition span or cut position overlaps the selected `MCS`/cloning-slot feature or an explicitly allowed region. A site is internal to an insert/GOI/part when its recognition span overlaps a `GOI` or explicitly selected insert feature and is not one of the intended flanking sites. For circular sequences, handle recognition sites and cut positions that wrap across coordinate 0 and report them as wraparound regions.

4. Apply strategy-specific rules.

   For `restriction_ligation`:

   - `FAIL` if any intended enzyme has no expected site in the cloning slot/MCS.
   - `FAIL` if an intended enzyme has a recognition site or cut position internal to the GOI/insert fragment being cloned.
   - `FAIL` if a supposedly unique cloning enzyme has additional sites outside allowed cut regions.
   - `WARN` if a single-enzyme strategy is detected for directional GOI insertion, because insert orientation may need independent verification unless the design includes an orientation-specific validation plan.
   - `WARN` for compatible but non-identical overhang choices unless explicitly requested.

   For `golden_gate_type_iis`:

   - `FAIL` if any assembly enzyme has an internal recognition site in a part/GOI/vector backbone region that should survive into the assembled construct.
   - `FAIL` if expected flanking type IIS sites are absent from source/part designs before assembly, when the check is run on pre-assembly parts.
   - `PASS` when the final assembled product lacks the assembly enzyme recognition sites, if the strategy profile says final product is post-assembly and scarless.
   - `WARN` when the method is Golden Gate-like but enzyme or assembly standard is ambiguous.

   For `gateway_topo`:

   - Do not fail incidental restriction sites.
   - `WARN` if user constraints also request "no internal restriction sites" but do not name enzymes.

   For `gibson_hifi_lic`:

   - Do not fail incidental restriction sites.
   - `FAIL` only for explicitly named forbidden enzymes/sites, explicitly required linearization enzymes with extra cuts, or explicit "no internal <enzyme>" constraints.
   - `WARN` if the workflow text names a restriction enzyme only as a vector-linearization step and the enzyme cuts more than once in the designed vector.

   For `synthesis_only`:

   - Do not fail incidental restriction sites unless constraints explicitly forbid them.
   - `WARN` on broad "remove common restriction sites" requests that do not name enzymes, and request a concrete forbidden list.

   For `unknown`:

   - If enzymes are explicitly named, apply the relevant named-enzyme uniqueness/internal-site rules.
   - If no enzymes are named, emit `WARN` that restriction-site conflict validation is under-specified; do not scan all enzymes and fail the design just because common sites exist.

## PASS/WARN/FAIL semantics

- `PASS`: Every enzyme named or implied by the resolved strategy has the expected cut pattern: required sites exist in allowed cloning regions, forbidden internal sites are absent, and final-product expectations match the strategy.
- `WARN`: The sequence is not proven to break cloning, but the strategy is ambiguous, enzyme choice is missing, extra benign sites may complicate optional diagnostics, a single-enzyme restriction strategy may be non-directional, methylation sensitivity may affect wet-lab digestion, or the user requested broad site avoidance without naming enzymes.
- `FAIL`: The conflict is blocking for the intended cloning method: missing required cloning-site cut, extra cut by an intended enzyme outside allowed regions, internal cut in GOI/insert/assembly part for the enzyme used to clone it, or an explicitly forbidden site is present.

Benign cut sites:

- Sites for enzymes not named, implied, or forbidden by the strategy.
- Sites in intentionally discarded stuffer/counterselection/dropout regions when those regions are explicitly annotated as allowed to be cut out.
- Type IIS assembly recognition sites in pre-assembly flanks when the check is evaluating source parts and the profile expects them there.
- Extra sites used only for optional diagnostic digests, unless the user requested a unique diagnostic pattern.
- Incidental restriction sites in Gibson/HiFi/LIC/Gateway/TOPO/synthesis-only designs with no named restriction constraint.

## Edge cases

- Coordinate systems: Biopython returns 1-based biological cut positions; report 0-based `FeatureRegion` coordinates consistent with `AnnotatedSequence`.
- Recognition span vs cut position: always store both internally. For type IIS enzymes, the recognition sequence and cleavage point are separated.
- Circular origin: detect and report wraparound sites that cross base 0. A circular plasmid may have a restriction motif spanning the artificial sequence boundary.
- Reverse-complement/non-palindromic sites: rely on Biopython/REBASE-derived enzyme definitions; do not hand-roll strand matching.
- Ambiguous or unsupported enzymes: `WARN` for unrecognized names; `FAIL` only if the explicit cloning method cannot be evaluated without them and no supported equivalent is known.
- Methylation sensitivity: default to `WARN` if the chosen enzyme may be blocked by common propagation-strain methylation and host strain is unknown. Escalate to `FAIL` only when the spec explicitly requires a methylation-sensitive digest from a known incompatible methylation context.
- Duplicate aliases/isoschizomers: collapse aliases before counting conflicts so BsmBI/Esp3I are not double-counted as independent conflicts.
- Annotated-feature gaps: if no GOI/MCS/cloning-slot features exist, run sequence-level enzyme detection but return `WARN` for insufficient annotation rather than claiming absence of internal conflicts.
- Linear PCR products: for linear topology, do not check circular wraparound motifs and preserve end-cut warnings for restriction sites too close to molecule ends only when primer/digest validation is in scope.
- Degenerate enzyme motifs: only use enzymes supported by Biopython/REBASE definitions; do not approximate degenerate recognition sequences with ad hoc regexes.

## Test fixtures

Unit fixtures should be short synthetic sequences with exact expected enzyme coordinates plus at least one real-vector regression set later under `data/eval/validation/`.

- `restriction_ligation_pass_directional`: circular vector with one EcoRI and one HindIII site inside MCS, GOI has no EcoRI/HindIII.
- `restriction_ligation_fail_internal_goi`: same as above, but GOI contains EcoRI.
- `restriction_ligation_fail_extra_vector_site`: intended EcoRI/HindIII cloning, EcoRI appears once in MCS and once in marker/backbone.
- `restriction_ligation_warn_single_enzyme`: one BamHI cloning site flanking insert strategy, no internal BamHI, orientation ambiguous.
- `golden_gate_pass_final_product`: final assembled product has no BsaI/BsmBI/BbsI recognition sites.
- `golden_gate_fail_internal_bsaI`: GOI/part contains BsaI recognition sequence under a BsaI Golden Gate profile.
- `golden_gate_warn_ambiguous_enzyme`: `cloning_method="Golden Gate"` with no enzyme or standard.
- `gibson_pass_incidental_ecori`: Gibson/HiFi design contains EcoRI in GOI but no restriction constraint.
- `explicit_forbidden_fail`: any strategy with constraint "no internal NotI" and NotI in GOI.
- `circular_wraparound_fail`: circular sequence has an intended-enzyme recognition site split across the sequence end/start outside MCS.
- `annotation_missing_warn`: named EcoRI cloning method but no MCS/GOI features; reports found sites and insufficient feature context.

## Citations

1. `SYSTEM_DESIGN.md`, Sections 8.1, 8.2, 8.3, 12.3, 12.4, and 12.5. Local source-of-truth repository specification.
2. Biopython contributors. 2026. "Bio.Restriction package - Biopython 1.87 documentation." https://biopython.org/docs/latest/api/Bio.Restriction.html
3. Biopython contributors. "Restriction cookbook." https://biopython.org/DIST/docs/cookbook/Restriction.html
4. Roberts RJ, Vincze T, Posfai J, Macelis D. 2023. "REBASE: a database for DNA restriction and modification: enzymes, genes and genomes." Nucleic Acids Research 51(D1):D629-D630. https://pubmed.ncbi.nlm.nih.gov/36318248/. DOI: 10.1093/nar/gkac975.
5. New England Biolabs. "Restriction Enzyme Digestion." https://www.neb.com/en/applications/cloning-and-synthetic-biology/dna-preparation/restriction-enzyme-digestion
6. New England Biolabs. "Golden Gate Assembly." https://www.neb.com/en-us/golden-gate/golden-gate
7. New England Biolabs. "Alphabetized List of Recognition Sequences." https://www.neb.com/en-us/tools-and-resources/selection-charts/alphabetized-list-of-recognition-specificities
8. New England Biolabs. "What if there are internal BsaI and BsmBI sites in my insert sequences?" https://www.neb.com/faqs/what-if-there-are-internal-bsai-and-bsmbi-sites-in-my-insert-sequences
9. Addgene. "Molecular Biology Reference." https://www.addgene.org/mol-bio-reference/
10. Addgene. "Molecular Cloning Techniques." https://www.addgene.org/mol-bio-reference/cloning/
11. Addgene. "Plasmids 101: Restriction Cloning." https://blog.addgene.org/plasmids-101-restriction-cloning
