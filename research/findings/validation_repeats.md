> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Repeat / instability validation spec

## Scope

This spec defines the deterministic `RepeatInstabilityCheck` for SYSTEM_DESIGN Section 8.2 item 2. The check identifies sequence patterns that can make a generated plasmid difficult to synthesize or unstable during bacterial propagation:

- exact direct repeats, including tandem repeats, above a conservative length threshold;
- exact inverted repeats and palindromic segments above a conservative arm-length threshold;
- global and local GC-content extremes;
- homopolymer runs likely to cause synthesis or sequencing errors.

The check is advisory about molecular mechanism and blocking about synthesis readiness. It must not rewrite the sequence. It emits PASS, WARN, or FAIL entries with coordinates and actionable messages. It should be implemented as a pure local function with deterministic output ordering and no runtime web dependency.

The first implementation should distinguish two risk classes:

- `synthesis_complexity`: provider-facing manufacturability risk caused by repeats, homopolymers, and GC extremes.
- `propagation_instability`: bacterial propagation/recombination risk, especially for repeated, palindromic, lentiviral LTR, and AAV ITR contexts.

## Inputs

Primary inputs:

- `AnnotatedSequence.sequence`: normalized uppercase A/C/G/T sequence. The schema already rejects empty and non-ACGT sequences.
- `AnnotatedSequence.topology`: `linear` or `circular`.
- `AnnotatedSequence.features`: feature intervals used to map findings to GOI, promoter, ORI, marker, MCS, terminator, or other annotated regions.
- `AnnotatedSequence.vector_profile`: coarse vector context when present.
- `AnnotatedSequence.annotation_complete`: if false, findings still run but messages should state that feature attribution may be incomplete.
- `DesignSpec.vector_type`, `DesignSpec.organism`, `DesignSpec.cell_line`, `DesignSpec.cloning_method`, and `DesignSpec.constraints`: used to choose vector-context exceptions and provider profile hints.

Profile inputs:

- `provider_profile`: one of `conservative_default`, `twist_default`, `idt_gblocks`, or `genscript_default`. If absent, use `conservative_default`.
- `sequence_role`: optional `full_plasmid`, `gene_insert`, `gene_fragment`, `oligo_pool_fragment`, or `unknown`. If absent, use `unknown` but still run all checks.

Recommended internal result model, even before the public schema expands:

```text
RepeatFinding(
  check_id,
  status,
  risk_class,
  motif_type,
  motif,
  length_or_arm_length,
  copy_count,
  regions,
  affected_feature_ids,
  provider_profile,
  threshold,
  message,
  remediation
)
```

Current public output must fit `ValidationCheck {name, status, message, region}` from `packages/core/schemas/models.py`. Until the schema supports multiple regions, emit one `ValidationCheck` per finding or per finding family, put the worst/first offending interval in `region`, and include paired coordinates in the message.

## Thresholds

Use conservative defaults because this validator is meant to decide whether generated output can be returned as synthesis-ready. Provider-specific profiles may relax or tighten individual thresholds, but the default should err toward early warning.

### Global GC content

For sequences at least 50 bp:

| Profile | PASS | WARN | FAIL |
| --- | --- | --- | --- |
| `conservative_default` | 30-60% | 25-29.99% or 60.01-65% | <25% or >65% |
| `twist_default` | 25-65% | 65.01-70% only if not Express-bound | <25% or >65% for Express-ready output |
| `idt_gblocks` | 30-70% | 25-29.99% or 70.01-75% | <25% or >75% |
| `genscript_default` | 30-70% | 20-29.99% or 70.01-80% | <20% or >80% |

Rationale: Twist Express guidance says global GC must be 25-65%; IDT flags less than 25% and greater than 75% for gBlocks; GenScript lists less than 20% or higher than 80% as a main sequence-analysis factor.

### Local GC windows

Use 50 bp windows with stride 1. For circular sequences with length at least 50 bp, windows must wrap across the origin. For sequences shorter than 50 bp, use the full sequence as one window and downgrade local-GC FAIL to WARN unless the selected provider has a hard short-fragment rule.

`conservative_default`:

- PASS: all 50 bp windows are 25-75% GC and `max_window_gc - min_window_gc <= 45 percentage points`.
- WARN: any 50 bp window is 15-24.99% or 75.01-85% GC, or the GC spread is 45.01-52 percentage points.
- FAIL: any 50 bp window is <15% or >85% GC, or the GC spread is >52 percentage points.

Provider notes:

- `twist_default`: FAIL if the highest-minus-lowest 50 bp GC spread is greater than 52 percentage points for Express-ready output.
- `idt_gblocks`: WARN local extremes because the public FAQ gives global GC limits but says structural motifs are reviewed multifactorially.
- `genscript_default`: WARN variable local GC by default; FAIL only at the conservative extreme threshold unless product-specific ordering rules are later added.

### Homopolymer runs

| Profile | WARN | FAIL |
| --- | --- | --- |
| `conservative_default` | A/T run 8-9; G/C run 5 | A/T run >=10; G/C run >=6 |
| `twist_default` | any base run 10-13 | any base run >=14 |
| `idt_gblocks` | A/T run 8-9; G/C run 5 | A/T run >=10; G/C run >=6 |
| `genscript_default` | any base run >=8 | any base run >=14 until product-specific hard limits are curated |

Rationale: IDT publishes the strictest explicit base-specific limits for gBlocks: 10 or more A/T bases and 6 or more G/C bases. Twist recommends avoiding homopolymers greater than 13 nt in its design PDF and says homopolymer length is part of its scoring model. GenScript lists homopolymers as a main sequence-analysis factor without a public base-specific cutoff.

### Exact direct repeats

Direct repeats are exact repeated substrings in the same orientation. Tandem repeats are adjacent or near-adjacent direct repeats and should be reported as `motif_type=tandem_repeat` when repeat copies are separated by no more than one repeat unit.

`conservative_default`:

- PASS: no exact direct repeat >=16 bp outside known required vector elements, and no high-density short-repeat cluster.
- WARN: exact direct repeat 16-19 bp, or any 8-15 bp motif appearing at least 4 times in a 200 bp span.
- FAIL: exact direct repeat >=20 bp, except required vector-context repeats that are downgraded to WARN with an explicit propagation/synthesis caveat.

Provider notes:

- `twist_default`: FAIL direct repeat >=20 bp for Express-ready output; WARN 12-19 bp if repeat density is high, because Twist design guidance recommends avoiding direct repeats longer than 12-16 bp and repeats >=20 bp.
- `idt_gblocks`: WARN repeats >=16 bp and FAIL repeats >=20 bp when coupled with another complexity finding; IDT states repeats and hairpins may affect acceptance but does not publish a repeat-length hard limit in the reviewed FAQ.
- `genscript_default`: FAIL repeats >=20 bp; WARN high counts of small repeats.

Propagation-instability escalation:

- WARN any exact direct repeat >=20 bp in promoter, viral regulatory, LTR, ITR, or non-coding backbone regions even when synthesis profile does not fail it.
- FAIL direct repeats >=50 bp when not annotated as required vector elements, because longer homology materially increases deletion/recombination risk in bacterial propagation.

### Inverted repeats and palindromes

An inverted repeat is a pair of reverse-complement arms separated by a spacer. A perfect palindrome is an inverted repeat with spacer length 0. Do not flag routine restriction-enzyme palindromes below the arm-length threshold.

Use these parameters:

- `min_arm_warn = 16 bp`
- `min_arm_fail = 20 bp`
- `max_spacer_for_hairpin = 100 bp`
- `long_spacer_warn_limit = 1000 bp`

`conservative_default`:

- PASS: no perfect or near-local exact inverted repeat with arm length >=16 bp.
- WARN: arm length 16-19 bp with spacer <=100 bp; arm length >=20 bp with spacer 101-1000 bp; annotated required viral ITR/LTR-like inverted repeat.
- FAIL: arm length >=20 bp with spacer <=100 bp when not annotated as a required vector element.

Provider notes:

- `twist_default`: FAIL if the inverted repeat also satisfies repeat length >=20 bp or estimated Tm >=60 C when Tm support is added.
- `idt_gblocks`: WARN inverted repeats/hairpins by default; FAIL when arm length >=20 bp and spacer <=100 bp or combined with a homopolymer/GC FAIL.
- `genscript_default`: WARN palindromic sequence; FAIL when the conservative default FAIL threshold is met.

Vector-context exceptions:

- AAV ITRs and lentiviral/retroviral LTRs may be required functional elements. Do not auto-fail solely because such annotated elements are present. Emit WARN with remediation such as "verify ITR/LTR integrity by sequence-confirmed stock and use a stable propagation workflow."
- If required ITR/LTR annotations are absent but the sequence has long inverted repeats consistent with those elements, report WARN or FAIL based on thresholds and state that incomplete annotation may affect interpretation.

## Rule Logic

Normalize:

1. Read `AnnotatedSequence.sequence` as already uppercase A/C/G/T.
2. Let `n = len(sequence)`.
3. For circular topology, create a virtual sequence `sequence + sequence[:max_pattern_len - 1]` for window and motif scanning, but report all coordinates modulo `n` and never report a motif whose primary span exceeds `n`.
4. Sort all findings deterministically by status severity (`FAIL`, `WARN`, `PASS` is not stored as a finding), then motif type, then start coordinate, then descending length, then motif string.

GC:

1. Compute global GC as `(G + C) / n * 100`.
2. Emit a global GC finding if outside PASS range for the selected profile.
3. For local GC, scan all 50 bp windows with stride 1. For linear sequences, scan starts `0..n-50`; for circular sequences, scan starts `0..n-1`.
4. Record the lowest-GC and highest-GC windows and the spread.
5. Emit at most two local-GC findings per sequence: one for the worst absolute local extreme and one for excessive spread. This keeps reports readable while preserving deterministic behavior.

Homopolymers:

1. Run-length encode the sequence.
2. For circular sequences, merge first and last runs if they contain the same base and report the wraparound run as a split or wrapping coordinate.
3. Compare each run with the selected profile's base-specific thresholds.
4. Emit one finding per failing run and one aggregate WARN per base for warn-only runs, capped at the top 10 longest runs in detailed output.

Direct repeats:

1. Find maximal exact repeats using a suffix-array/suffix-automaton implementation or a deterministic rolling-hash index over candidate k-mers. Avoid naive all-pairs substring comparison for full plasmids.
2. Seed candidate pairs at `k = 16` for the conservative profile and extend each candidate left/right to maximal exact-match length.
3. Treat overlapping copies as tandem-repeat candidates when the offset is less than or equal to the repeat length; otherwise report as direct repeats.
4. For each repeat family, retain the maximal repeat length and all copy starts. Collapse duplicate sub-repeats contained within a longer repeat family.
5. Emit FAIL/WARN according to length, repeat density, provider profile, and vector-context exception rules.
6. Report paired coordinates in the message. Put the first copy in `ValidationCheck.region` until the schema supports multiple regions.

Inverted repeats:

1. Search for exact reverse-complement arm pairs with arm length at least 16 bp.
2. Use a k-mer index over reverse complements: for each k-mer, find downstream positions where its reverse complement occurs.
3. Extend candidate arms to the maximal reverse-complement match.
4. Compute spacer as the number of bases between the first arm end and second arm start for same-molecule local hairpins. For circular topology, evaluate the shorter circular spacer and report wraparound coordinates if needed.
5. Classify spacer 0 as palindrome, 1-100 as local hairpin/cruciform risk, and 101-1000 as long-spacer inverted-repeat risk.
6. Collapse nested arm pairs and emit the longest/highest-severity finding per locus.

Feature mapping:

1. For every finding region, intersect with `AnnotatedSequence.features`.
2. Include feature names/types in messages where available, especially if the region overlaps GOI, promoter, LTR, ITR, ori, or marker.
3. If `annotation_complete=false`, append "annotation incomplete; affected feature may be unknown" to WARN/FAIL messages.

Remediation messages:

- Coding sequence direct repeat: "consider synonymous recoding if protein sequence must be preserved."
- Non-coding repeat: "consider alternate regulatory/backbone element or provider review."
- GC window: "rebalance local sequence if biologically editable; otherwise route to provider complex-gene workflow."
- Required viral repeat: "do not remove blindly; verify with sequence-confirmed source and stable propagation workflow."
- Homopolymer: "break run with synonymous or non-functional spacer edits where biologically allowed."

## PASS/WARN/FAIL Semantics

`PASS`:

- No finding exceeds the selected profile's WARN threshold.
- A single `ValidationCheck` named `repeat_instability` may be emitted with PASS and message "No repeat, homopolymer, or GC-window instability findings above configured thresholds."

`WARN`:

- The sequence has a motif known to reduce synthesis acceptance, sequencing robustness, or bacterial propagation stability, but the public evidence or profile does not justify blocking final output.
- Required vector elements such as AAV ITRs or lentiviral LTRs are WARN unless their context suggests an avoidable duplicate or malformed arrangement.
- WARN does not block returning the design, but it must be visible in the validation report.

`FAIL`:

- The sequence violates a selected provider hard threshold or the conservative default threshold for synthesis-ready output.
- Any FAIL from this check blocks returning the design as final under SYSTEM_DESIGN Section 8.1.
- FAIL must include coordinates and a remediation path unless the motif is required and non-editable, in which case the remediation is provider/stable-strain review.

Overall check status:

- If any finding is FAIL, the aggregate repeat-instability status is FAIL.
- Else if any finding is WARN, the aggregate status is WARN.
- Else PASS.

## Edge Cases

- Circular origin: local GC windows, homopolymer runs, direct repeats, and inverted repeats must detect motifs crossing coordinate 0. Report wraparound intervals explicitly in the message even though `FeatureRegion` currently cannot represent split intervals.
- Short sequences: for `n < 50`, compute global GC and full-sequence GC only; downgrade local-GC-only FAIL to WARN unless a provider profile says otherwise.
- Ambiguous bases: not supported by the current schema; upstream normalization rejects non-ACGT input.
- Nested repeats: report the longest maximal repeat and suppress contained shorter repeats unless they trigger a different threshold class, such as a tandem cluster.
- Repeated standard features: common duplicated promoters, tags, LTRs, ITRs, and polyA elements may be intentional. Intentionality downgrades some findings from FAIL to WARN only when annotation and `DesignSpec` support the vector context.
- Restriction sites: short palindromic restriction sites below 16 bp are out of scope for this check and belong to the restriction-site checker.
- Very long plasmids: cap detailed emitted findings, not scanning. The implementation should scan the full sequence but report the top findings per motif class by severity and length.
- Incomplete annotation: do not suppress findings; add an interpretation caveat.
- Multiple provider profiles: if a user selects a provider, use that profile for status. Optionally include a secondary note when another common provider would classify the same sequence more strictly.
- Required biological repeats: validators must not suggest deleting AAV ITRs, LTRs, origins, or regulatory repeats without context-aware replacement guidance.

## Test Fixtures

Each fixture should assert deterministic status, motif type, coordinates, and message substring. Coordinates below are 0-based, half-open unless a wrapping interval is explicitly noted.

1. `pass_balanced_no_repeat`
   - Build a 240 bp synthetic sequence from a fixed seeded generator with 45-55% GC, no homopolymer above 4 bp, no exact direct repeat >=12 bp, and no inverted repeat arm >=12 bp.
   - Expected: PASS under `conservative_default`.

2. `fail_direct_repeat_20`
   - Sequence contains exact 20 bp motif `ATGTCAGTACGATCGTACGA` at two non-overlapping loci separated by at least 30 bp.
   - Expected: FAIL under `conservative_default`, `twist_default`, and `genscript_default`; WARN or FAIL under `idt_gblocks` depending on whether strict combined-complexity mode is enabled.

3. `warn_direct_repeat_16`
   - Sequence contains exact 16 bp motif `ATGTCAGTACGATCGT` twice and no other complexity motif.
   - Expected: WARN under `conservative_default`.

4. `fail_inverted_repeat_local`
   - Sequence contains arm `ATGTCAGTACGATCGTACGA`, spacer `TACGAT`, and reverse-complement arm `TCGTACGATCGTACTGACAT`.
   - Expected: FAIL under `conservative_default` because arm length is 20 bp and spacer is 6 bp.

5. `warn_required_aav_itr_like`
   - Annotated feature named `AAV ITR` overlaps an inverted repeat arm length >=20 bp.
   - Expected: WARN, not FAIL, with required-element propagation caveat.

6. `fail_gc_global_high`
   - Sequence has global GC 66% and no repeat/homopolymer issue.
   - Expected: FAIL under `conservative_default` and `twist_default`; WARN under `idt_gblocks`; PASS or WARN under `genscript_default` depending on configured PASS band.

7. `fail_local_gc_spread`
   - Sequence has one 50 bp window near 20% GC and one 50 bp window near 80% GC, while global GC remains near 50%.
   - Expected: FAIL under `conservative_default` because spread is >52 percentage points; FAIL under `twist_default` for Express-ready output.

8. `fail_homopolymer_gc6`
   - Sequence contains `GGGGGG` and no other complexity motif.
   - Expected: FAIL under `conservative_default` and `idt_gblocks`; WARN under `twist_default` unless run length reaches 14.

9. `fail_homopolymer_at10`
   - Sequence contains `AAAAAAAAAA` and no other complexity motif.
   - Expected: FAIL under `conservative_default` and `idt_gblocks`; WARN under `twist_default` unless run length reaches 14.

10. `warn_circular_wrap_homopolymer`
    - Circular sequence begins with `AAA` and ends with `AAAAAAA`, creating a 10 bp A run across the origin.
    - Expected: FAIL under `conservative_default` and `idt_gblocks`, with message noting wraparound coordinates.

11. `warn_short_sequence_local_gc`
    - 40 bp sequence with 80% GC and no repeats.
    - Expected: global-GC status by profile; no separate 50 bp local-window FAIL because the sequence is shorter than the window.

12. `warn_small_repeat_cluster`
    - 200 bp sequence contains an 8 bp motif repeated 4 times without any exact 20 bp direct repeat.
    - Expected: WARN under `conservative_default` and `twist_default`.

## Citations

1. SYSTEM_DESIGN.md, Section 8.2 item 2 and Sections 8.1, 8.3, 12.3, and 12.5.
2. `packages/core/schemas/models.py`, `AnnotatedSequence`, `DesignSpec`, `ValidationCheck`, and `ValidationReport`.
3. Twist Bioscience. "Express Genes." Public guidance states that sequence scoring considers overall GC percent, maximum homopolymer length, maximum repeat length, sequence length, and repeat density; complexity issues are driven mainly by repetitive structures and extreme GC content; design guidance includes avoiding repeats >=20 bp or Tm >=60 C, global GC 25-65%, 50 bp GC-window spread no greater than 52 percentage points, and minimizing homopolymers and small repeats. https://www.twistbioscience.com/products/genes/express-genes
4. Twist Bioscience. 2023. "Twist Tips: How to Design Your Gene." Public design PDF recommends avoiding repeats >=20 bp or Tm >=60 C, keeping global GC 25-65%, limiting local 50 bp GC spread, avoiding homopolymers greater than 13 nt, avoiding clusters of 8-9 bp repeats, and avoiding direct repeats longer than 12-16 bp. https://www.twistbioscience.com/content/dam/twistbioscience/resources/2023-06/DOC-001081_TechNote_TwistTipVectorDesign-REV4-singles.pdf
5. Integrated DNA Technologies. "What types of sequence motifs should be avoided when ordering gBlocks Gene Fragments?" IDT states that problematic gBlocks motifs include GC content less than 25% or greater than 75%, homopolymeric runs of 10 or more A/T bases or 6 or more G/C bases, and structural motifs such as repeats or hairpins. https://www.idtdna.com/pages/support/faqs/what-types-of-sequence-motifs-should-be-avoided-when-ordering-gblocks-gene-fragments-
6. GenScript. "FLASH Gene & Gene Synthesis - 4-Day Gene to Plasmid." GenScript states that synthesis success is mainly determined by repetitive sequences, GC content, host-cell stability, and toxicity, and lists global GC less than 20% or higher than 80%, variable GC content, homopolymers, repeats >=20 bp, small repeat count/length, and palindromic sequence as sequence-analysis factors. https://www.genscript.com/gene_synthesis.html
7. Bzymek M, Lovett ST. 2001. "Instability of repetitive DNA sequences: The role of replication in multiple mechanisms." Proceedings of the National Academy of Sciences 98(15):8319-8325. DOI: 10.1073/pnas.111008398. The review describes direct-repeat-mediated deletion/duplication and RecA-independent rearrangement mechanisms in E. coli. https://pmc.ncbi.nlm.nih.gov/articles/PMC37438/
8. Oliveira PH, Prather KJ, Prazeres DMF, Monteiro GA. 2010. "Analysis of DNA repeats in bacterial plasmids reveals the potential for recurrent instability events." Applied Microbiology and Biotechnology 87:2157-2167. DOI: 10.1007/s00253-010-2671-7. The study analyzed direct, inverted, and tandem repeats in plasmids and reported spontaneous recombination between 21 bp direct repeats in a CMV promoter region. https://doi.org/10.1007/s00253-010-2671-7
9. Al-Allaf FA, Tolmachov OE, Zambetti LP, Tchetchelnitski V, Mehmet H. 2013. "Remarkable stability of an instability-prone lentiviral vector plasmid in Escherichia coli Stbl3." 3 Biotech 3:61-70. DOI: 10.1007/s13205-012-0070-8. The paper reports lentiviral plasmid structural instability in some E. coli propagation contexts and stabilization by host strain choice. https://pubmed.ncbi.nlm.nih.gov/28324350/
10. Ling C, et al. 2024. "Degradation and stable maintenance of adeno-associated virus inverted terminal repeats in E. coli." Molecular Therapy Methods & Clinical Development. The paper reports AAV ITR instability/deletion issues during E. coli plasmid propagation and supports vector-context-specific handling for required ITRs. https://pmc.ncbi.nlm.nih.gov/articles/PMC11754738/
11. EMBOSS. "etandem manual." Reference implementation for tandem-repeat detection parameters and reports. https://emboss.bioinformatics.nl/cgi-bin/emboss/help/etandem
12. EMBOSS. "einverted manual." Reference implementation for inverted-repeat detection parameters and reports. https://emboss.bioinformatics.nl/cgi-bin/emboss/help/einverted
