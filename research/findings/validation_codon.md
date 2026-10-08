> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Scope

This note defines the deterministic Phase 3 codon-optimization scoring check from `SYSTEM_DESIGN.md` Section 8.2 item 3. The check scores annotated gene-of-interest coding sequence regions against the target organism's codon-usage table and flags rare-codon clusters. It only reports validation status; it must not rewrite or optimize DNA.

The later implementation should expose one independently unit-tested module used by `ConstraintEngine.validate(sequence: AnnotatedSequence, spec: DesignSpec) -> ValidationReport`. Its output should be a `ValidationCheck` named `codon_optimization` with `status`, `message`, and an optional `FeatureRegion` for the worst offending GOI or rare-codon cluster. If multiple GOIs exist, the check should score each GOI and aggregate deterministically.

# Inputs

Primary inputs:

- `AnnotatedSequence.sequence`: normalized uppercase ACGT DNA. The schema already rejects non-ACGT characters.
- `AnnotatedSequence.features`: half-open feature coordinates `[start, end)` with `type`, `strand`, `name`, and `confidence`.
- `DesignSpec.organism`: target expression organism used to select a codon-usage table.
- Optional future config: `min_goi_confidence`, CAI thresholds, rare-codon thresholds, and organism aliases.

GOI CDS identification:

1. Select features where `feature.type == "GOI"`.
2. Require `feature.confidence >= 0.5` by default. Lower-confidence GOI annotations should not silently drive scoring; if all GOI features are below the threshold, return `WARN`.
3. Extract `sequence[feature.start:feature.end]`. Coordinates remain the original `AnnotatedSequence` coordinates.
4. If `feature.strand == -1`, reverse-complement the extracted region before codon parsing. If `strand == 1`, parse as given. If `strand == 0`, return `WARN` for that feature because coding frame orientation is unknown.
5. Treat the GOI region itself as the CDS frame. Do not infer a shifted frame unless a later schema adds codon phase/qualifiers.
6. Score every GOI that is at least 6 nt and divisible by 3. A 3 nt GOI is usually only an initiation-codon annotation, not a usable CDS, and should be `WARN`.

No implicit CDS discovery should run inside this check. If a generated sequence lacks a GOI feature, that is an annotation/completeness problem and this check should return `WARN`, not scan all ORFs.

# Codon Tables

Implement with a small embedded table for the first supported expression organisms:

- `Escherichia coli` / `E. coli`
- `Saccharomyces cerevisiae` / `S. cerevisiae`
- `Homo sapiens` / `H. sapiens` / `human`
- `Mus musculus` / `M. musculus` / `mouse`

Store tables as source-controlled constants, not runtime downloads, so validation remains deterministic. Each organism table should map every standard sense codon to either:

- codon frequency within synonymous family, preferred for CAI-like scoring, or
- per-thousand codon usage plus raw counts, from which synonymous-family frequencies can be derived.

For implementation simplicity, embed normalized synonymous-family frequencies for all 61 sense codons and include metadata with `source`, `source_url`, `source_date`, `genetic_code`, and `notes`. Stop codons should be present in a separate `stops` set and excluded from CAI calculations except for terminal-stop validation.

The initial source should be Kazusa/Codon Usage Database-style organism codon usage tables, with values copied into the repo and reviewed once. Do not fetch Kazusa during validation. If a target organism is unsupported, return `WARN` with `organism unsupported for codon scoring`.

# Scoring

Use a CAI-like relative-adaptiveness score:

1. Translate each complete codon in the oriented GOI CDS using the standard nuclear genetic code.
2. Permit `ATG` and `TGG` as single-codon amino acid families with weight `1.0`.
3. For every other sense codon `c` encoding amino acid `aa`, compute relative adaptiveness:
   `w[c] = usage_frequency[c] / max(usage_frequency[synonymous_codons_for_aa])`.
4. For codons with zero or missing usage values, use a deterministic floor such as `0.01` and record that the table had a missing/zero value. Complete embedded tables should make this rare.
5. Exclude a single terminal stop codon from the CAI-like geometric mean. Internal stops are `FAIL`.
6. Score the GOI as:
   `score = exp(sum(log(w[c])) / n)`
   where `n` is the number of scored sense codons.
7. Round reported scores to three decimals, but compare using unrounded floats.

Recommended thresholds for first implementation:

- `PASS`: every scorable GOI has score `>= 0.70`, no rare-codon cluster, no internal stop/frame defect.
- `WARN`: any scorable GOI has `0.55 <= score < 0.70`, or any rare-codon cluster is present, or the check cannot confidently score because of missing GOI, unsupported organism, unknown strand, too-short GOI, or incomplete annotation.
- `FAIL`: any GOI has score `< 0.55`, an internal stop codon, a length not divisible by 3, a nonterminal stop codon, or a start/terminal-stop pattern that makes the annotated CDS invalid.

Start/stop handling:

- A valid CDS should start with `ATG` by default. Alternative bacterial starts should not be accepted unless an explicit future config enables them.
- A terminal stop codon is acceptable but not required for scoring because some vectors encode C-terminal fusions.
- If a stop codon appears before the final codon, return `FAIL` with that stop codon's original sequence coordinates.

Aggregation across multiple GOIs:

- Compute per-GOI score and findings.
- Overall check status is the maximum severity: `FAIL` beats `WARN` beats `PASS`.
- Message should include count of GOIs scored, minimum score, target organism key, and number of rare-codon clusters.
- Region should point to the highest-severity region: first internal stop/frame defect, otherwise worst rare-codon cluster, otherwise lowest-scoring GOI.

# Rare-Codon Clusters

Define rare codons from the same selected target-organism table:

- A codon is rare when its synonymous-family frequency is `< 0.10` or its relative adaptiveness `w[c] < 0.20`.
- `ATG` and `TGG` are never rare because they have no synonymous alternative.
- Stop codons are excluded from rare-codon cluster detection.

Cluster rule:

- Scan oriented codons in non-overlapping codon positions.
- Flag a rare-codon cluster when at least 3 rare codons occur in any 8-codon sliding window.
- Merge overlapping flagged windows into one cluster region.
- Report original `AnnotatedSequence` coordinates for each cluster. For reverse-strand GOIs, convert oriented codon offsets back to original coordinates.

Cluster output should include codon list and codon indices in the message for deterministic debugging, but only one `FeatureRegion` can be attached to the current schema. Use the worst cluster by rare count, then earliest original start coordinate as tie-breaker.

# PASS/WARN/FAIL Semantics

`PASS` means the annotated GOI CDS regions are scorable for the requested target organism, have acceptable CAI-like host adaptation, and contain no rare-codon clusters.

`WARN` means the design may be usable but needs review or possible codon optimization. WARN is non-blocking under Section 8.1. Typical WARN cases are moderate score, rare-codon cluster, unsupported target organism, missing confident GOI annotation, unknown strand, or incomplete annotation that prevents confident scoring.

`FAIL` means the annotated CDS is structurally invalid or severely mismatched to the target organism. Typical FAIL cases are frame length not divisible by 3, internal stop, score below the fail threshold, or a CDS so malformed that the score would be misleading.

The check should be deterministic: same sequence, features, spec, and embedded table version always produce the same status, score, cluster list, message, and region.

# Edge Cases

- No GOI features: `WARN`, message `no GOI feature available for codon scoring`.
- Multiple GOIs: score all; aggregate by worst severity.
- GOI shorter than 6 nt: `WARN`, likely an initiation-codon marker rather than a CDS.
- GOI length not divisible by 3: `FAIL`, region is the GOI.
- `strand == 0`: `WARN`, region is that GOI.
- Reverse-strand GOI: reverse-complement before scoring; report coordinates in original orientation.
- Circular feature wraparound: current `AnnotatedFeature` requires `end <= len(sequence)`, so wraparound CDS cannot be represented directly. Until the schema supports split/join features, return `WARN` if a known circular GOI appears split across two adjacent GOI features with the same name.
- Terminal stop present: exclude from score; do not mark rare.
- Internal stop: `FAIL`.
- Unsupported organism alias: `WARN`; do not fall back to E. coli.
- `annotation_complete == false`: still score confident GOI features, but cap status at `WARN` because missing annotations may hide the actual CDS boundaries.
- Codon table missing a sense codon: use the floor for score calculation and return at least `WARN`; embedded tables should be complete enough to avoid this.
- Ambiguous bases: not possible through current schema, but if the scorer is later called directly, reject non-ACGT as `FAIL` or raise a validation error at the schema boundary.

# Test Fixtures

Create focused unit fixtures under the Phase 3 validation tests:

- `ecoli_pass_preferred_codons`: one forward-strand GOI using E. coli-preferred codons, divisible by 3, no internal stop, expected `PASS` and score `>= 0.70`.
- `ecoli_warn_moderate_cai`: synonymous GOI with mixed preferred and low-adaptiveness codons, expected `WARN` with score between `0.55` and `0.70`.
- `ecoli_warn_rare_cluster`: otherwise acceptable GOI with 3 rare codons in an 8-codon window, expected `WARN` and cluster region coordinates.
- `ecoli_fail_low_cai`: GOI dominated by rare synonymous codons, expected `FAIL` with score `< 0.55`.
- `internal_stop_fail`: GOI with an in-frame stop before the final codon, expected `FAIL` and stop-codon region.
- `frame_length_fail`: GOI length not divisible by 3, expected `FAIL`.
- `reverse_strand_pass`: reverse-strand GOI whose reverse complement uses preferred codons, expected `PASS` and original-coordinate region behavior.
- `unsupported_organism_warn`: valid GOI with `DesignSpec.organism = "Danio rerio"`, expected `WARN`.
- `missing_goi_warn`: annotated sequence without GOI features, expected `WARN`.
- `annotation_incomplete_cap_warn`: good GOI with `annotation_complete = false`, expected score computed but overall `WARN`.

Tests should assert exact status, exact reported region, deterministic rounded score, and stable message fields for each fixture. Add separate pure-function tests for codon offset to original-coordinate conversion on forward and reverse strands.

# Citations

- Kazusa/Codon Usage Database: Nakamura, Y., Gojobori, T., and Ikemura, T. 2000. "Codon usage tabulated from international DNA sequence databases: status for the year 2000." `Nucleic Acids Research` 28(1):292. https://doi.org/10.1093/nar/28.1.292. The paper describes compiling codon frequencies from complete CDS entries in GenBank and making organism-level codon usage available through the Kazusa web/FTP database.
- Current Kazusa database landing/readme: Kazusa DNA Research Institute, "Codon Usage Database." https://www.kazusa.or.jp/codon/ and https://www.kazusa.jp/codon/readme_codon.html.
- CAI methodology: Sharp, P. M. and Li, W.-H. 1987. "The codon adaptation index - a measure of directional synonymous codon usage bias, and its potential applications." `Nucleic Acids Research` 15(3):1281-1295. https://doi.org/10.1093/nar/15.3.1281.
- Implementation reference: Biopython `Bio.SeqUtils.CodonAdaptationIndex` documentation states that it implements the Sharp and Li CAI method and computes relative adaptiveness `w_ij` from coding DNA sequences. https://biopython.org/docs/latest/api/Bio.SeqUtils.html.
