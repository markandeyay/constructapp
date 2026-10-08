> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Validation Repeat Detector Audit

Audit date: 2026-06-15

Scope audited: `packages/validation/repeats.py`, related repeat tests in `tests/validation/test_repeats.py`, and validation gold/curated data under `data/eval/validation/`.

## Executive Summary

The current `repeat_and_instability` implementation is a deterministic first-hit synthesis-risk screen, not a context-aware repeat validator. It detects homopolymers, local GC extremes, exact non-overlapping direct repeats, and exact non-overlapping inverted repeats. It uses hard-coded global thresholds and ignores `DesignSpec`, annotated features, topology, provider, sequence role, and biological intent.

This means it can block required biology such as annotated lentiviral LTRs or AAV ITRs if they contain a long exact repeat, and it can miss provider-specific manufacturability issues that are below its current hard-coded fail thresholds. The existing repo spec in `research/findings/validation_repeats.md` already calls for provider profiles and vector-context exceptions, but `packages/validation/repeats.py` has not implemented those requirements yet.

## Current Behavior

Implementation entry point: `packages/validation/repeats.py:20`.

Current check order is short-circuiting. Only the first category found is reported:

| Order | Finding | Status | Threshold | Notes |
| --- | --- | --- | --- | --- |
| 1 | Homopolymer | FAIL | Any single-base run >=12 nt | Base-agnostic; A/T and G/C use the same cutoff. |
| 2 | Local GC extreme | FAIL | 100 bp window with GC <20% or >80%; if sequence is shorter than 100 bp, whole sequence uses same cutoffs | Windows advance by 20 bp, so narrower or offset local extremes can be missed. |
| 3 | Exact direct or inverted repeat | FAIL | First exact non-overlapping repeat k-mer of 40 bp | Reports only the repeated 40 bp seed, not the maximal repeat. |
| 4 | Exact direct or inverted repeat | WARN | First exact non-overlapping repeat k-mer of 25 bp | Suppressed if any earlier FAIL exists. |
| 5 | Homopolymer | WARN | Any single-base run >=8 nt | Base-agnostic. |
| 6 | None | PASS | No detected blocking repeat, homopolymer, or GC-instability pattern | Does not mean provider-ready for Twist, IDT, or GenScript. |

Repeat kinds detected today:

- `direct`: exact same-orientation non-overlapping k-mer repeated at least twice, found by `first_exact_repeat(sequence, k=...)`.
- `inverted`: exact reverse-complement non-overlapping k-mer pair, found after direct-repeat search by reverse-complement indexing.
- Tandem repeats are not classified separately. Adjacent exact duplicate k-mers satisfy the direct-repeat condition because `start - previous >= k` allows adjacent non-overlapping copies.
- Palindromes and local hairpins are not classified separately. A perfect or near-local inverted repeat may be detected only if two non-overlapping reverse-complement arms of length at least `k` exist.
- Repeat density, small repeat clusters, approximate repeats, imperfect repeats, microsatellites, and maximal repeat length are not detected.

Identity assumptions:

- Repeats must be exact string matches at a fixed seed length (`25` for WARN, `40` for FAIL).
- Direct-repeat copies must be non-overlapping. Overlapping repeated words are ignored.
- Inverted-repeat arms must be exact reverse complements and non-overlapping.
- The implementation does not extend hits to maximal repeat length, count all copies, report paired coordinates, or compare repeat locations to annotated features.
- The checker assumes sequence text is already normalized. It does not use `DesignSpec` and explicitly discards it with `del spec`.

## Biological Context Handling

The current checker does not consider biological context.

Ignored context includes:

- Annotated required repeats such as lentiviral or retroviral LTRs.
- Annotated AAV ITRs and other required inverted terminal repeat structures.
- Whether a repeat overlaps promoter, ORI, marker, GOI, MCS, LTR, ITR, or other functional feature.
- Whether `annotation_complete` is false.
- `AnnotatedSequence.topology`, including circular motifs that cross coordinate 0.
- `vector_profile`, `DesignSpec.vector_type`, `DesignSpec.organism`, `DesignSpec.cell_line`, `DesignSpec.cloning_method`, and provider/sequence-role hints.

This is biologically important because required viral repeats can be intentional but still risky for propagation or synthesis. The curated uncertainty log already says required viral LTR/ITR-like repeats were excluded from the blocking known-bad set because they can be biologically necessary even when they create review risk (`data/eval/validation/curated_known_bad_uncertainty.md:7`). The design-rule findings also note that lentiviral plasmids can be unstable in some E. coli hosts and that vector context/host strain matters. Therefore, intentional LTRs should generally produce a visible WARN with stable-propagation guidance, not an unconditional FAIL solely because an exact repeat crosses a hard-coded length threshold.

## Test And Gold Data Coverage

Current repeat tests cover:

- Homopolymer FAIL at 12 nt.
- Local GC FAIL using a 100 bp all-GC insert.
- Direct repeat FAIL for a repeated 40+ bp exact segment.
- Inverted repeat FAIL for a 45 bp arm and its reverse complement.
- Direct repeat detection with ambiguous `N` when helper function is called directly.
- PASS for a stable generated sequence.

Coverage gaps:

- No tests for WARN thresholds: 25 bp repeat or 8-11 nt homopolymer.
- No tests for base-specific homopolymer thresholds required by IDT-style gBlocks screening.
- No tests for direct repeats between 20-39 bp, despite Twist and GenScript guidance flagging repeats >=20 bp.
- No tests for provider profile selection or provider-specific status differences.
- No tests for LTR/ITR/AAV required-repeat downgrade behavior.
- No tests for feature mapping, incomplete annotation caveats, circular wraparound homopolymers/repeats, local GC stride edge cases, repeat density, tandem classification, palindromic/hairpin spacers, or multiple simultaneous findings.

Gold data observations:

- Generated `validation_gold.jsonl` repeat bad cases from `packages/validation/gold.py` only exercise 12 nt homopolymers for the deterministic seed set.
- Curated known-bad data under `curated_known_bad.jsonl` includes repeat-instability cases for homopolymer 12 nt, local GC extreme 100 bp, and direct repeat 40 bp.
- The baseline shows repeat check precision/recall as perfect on the curated dataset, but that dataset mostly confirms current hard-coded behavior and does not validate biology-aware or provider-aware repeat handling.

## Provider Threshold Comparison

The repo already contains provider documentation summaries and citations in `research/findings/validation_repeats.md` and `research/findings/validation_tools.md`. Public provider guidance is not fully equivalent: some providers state hard limits, while others describe risk factors or scoring-model inputs.

| Provider profile | Public/repo-cited guidance | Current implementation alignment |
| --- | --- | --- |
| Twist | Twist Express/Twist Tips guidance says synthesis scoring considers overall GC, maximum homopolymer length, maximum repeat length, sequence length, and repeat density; recommends global GC 25-65%, avoiding repeats >=20 bp or Tm >=60 C, limiting 50 bp GC spread, avoiding homopolymers >13 nt, avoiding clusters of 8-9 bp repeats, and avoiding direct repeats longer than 12-16 bp. Sources: `research/findings/validation_repeats.md:300-301`, `research/findings/validation_tools.md:17-18`. | Partially aligned on homopolymer FAIL if interpreted as >=14 vs current >=12, but current direct-repeat FAIL at 40 bp is too permissive for Twist; local GC uses 100 bp absolute 20-80% instead of global 25-65% and 50 bp spread. No repeat density or Tm. |
| IDT gBlocks | IDT says problematic gBlocks motifs include GC <25% or >75%, homopolymeric runs of >=10 A/T or >=6 G/C, and structural motifs such as repeats or hairpins. Source: `research/findings/validation_repeats.md:302`, `research/findings/validation_tools.md:19`. | Not aligned. Current base-agnostic homopolymer FAIL at 12 misses G/C runs of 6-11 and A/T runs of 10-11; current GC uses local 20-80% and no global GC; repeats/hairpins are only exact >=40 bp FAIL or >=25 bp WARN. |
| GenScript | GenScript says synthesis success is affected by repetitive sequences, GC content, host-cell stability/toxicity; flags global GC <20% or >80%, variable GC content, homopolymers, repeats >=20 bp, small repeat count/length, and palindromic sequence. Source: `research/findings/validation_repeats.md:303`, `research/findings/validation_tools.md:20`. | Partially aligned on 20-80% GC bounds but only as local 100 bp windows, not global or variable local GC. Direct-repeat FAIL at 40 misses GenScript's cited >=20 bp repeat threshold. Palindromic sequence and small-repeat count/length are not implemented. |

Provider conclusion: the current checker should not be described as Twist-ready, IDT gBlocks-ready, or GenScript-ready. It is a coarse conservative local screen in some dimensions and too permissive in others.

## Key Risks

1. False PASS for provider-relevant repeats: exact direct repeats of 20-39 bp currently PASS unless another finding triggers, despite Twist and GenScript guidance around repeats >=20 bp.
2. False PASS for IDT gBlocks homopolymers: G/C runs of 6-11 and A/T runs of 10-11 currently do not FAIL.
3. False FAIL for intentional biology: required LTR/ITR repeats may be blocked without annotation-aware downgrade or stable-propagation guidance.
4. Missed circular motifs: wraparound homopolymers, repeats, and GC windows are not detected.
5. Misleading single-result reporting: only the first finding is returned, hiding additional higher-actionability issues depending on scan order.
6. Provider ambiguity: one hard-coded status is used for all providers, even though Twist, IDT, and GenScript thresholds differ materially.

## Prioritized Recommendations

### P0: Separate synthesis complexity from biological/vector-context interpretation

Implement internal finding objects with at least `risk_class`, `motif_type`, `status`, `regions`, `threshold`, `provider_profile`, and `message`, then aggregate into the existing `ValidationCheck` schema. Keep provider manufacturability findings separate from propagation-instability findings. Do not auto-fail annotated required LTR/ITR/AAV ITR elements solely because they are repeats; emit WARN with explicit propagation/synthesis caveats unless evidence indicates an avoidable duplicate or malformed arrangement.

### P0: Add provider profiles before changing hard-coded thresholds

Add profiles named `conservative_default`, `twist_default`, `idt_gblocks`, and `genscript_default`. Use `conservative_default` only when provider is absent. Provider hints can initially come from `DesignSpec.constraints`, `DesignSpec.source`, or an explicit future field; until then, make default behavior explicit in messages.

### P0: Fix threshold mismatches most likely to affect ordering readiness

Implement base-specific homopolymer thresholds:

- IDT/conservative: WARN A/T 8-9, FAIL A/T >=10; WARN G/C 5, FAIL G/C >=6.
- Twist: WARN any base 10-13, FAIL any base >=14.
- GenScript: WARN any base >=8, FAIL any base >=14 until product-specific hard limits are curated.

Implement direct repeat thresholds:

- Conservative/Twist/GenScript: FAIL exact direct repeat >=20 bp unless required vector-context downgrade applies.
- Conservative WARN exact direct repeat 16-19 bp.
- IDT: WARN repeats/hairpins by default; FAIL repeat >=20 bp when combined with another complexity finding or if strict gBlocks mode is selected.

### P1: Replace fixed-k first-hit repeat detection with maximal repeat families

Seed at the lowest configured repeat threshold, extend candidate matches to maximal exact repeats, classify tandem vs non-tandem direct repeats, count copies, and report paired coordinates. Suppress contained sub-repeats unless they cross a different threshold class.

### P1: Implement inverted-repeat and palindrome semantics

Use arm length and spacer thresholds rather than the same fixed-k direct-repeat logic. Classify local hairpin/cruciform risk separately from long-spacer inverted repeats. Do not report routine short restriction-site palindromes in this check.

### P1: Add global GC and 50 bp local-GC spread checks

Current GC screening only scans 100 bp windows every 20 bp. Add global GC thresholds by provider and 50 bp local windows with stride 1. For Twist-style Express readiness, include 50 bp highest-minus-lowest GC spread. For circular sequences, scan windows across coordinate 0.

### P1: Make topology and annotation part of detection/reporting

For circular sequences, detect homopolymers and repeats crossing the origin. Map findings to features and include feature names/types in messages where available. If `annotation_complete=false`, add an interpretation caveat rather than suppressing findings.

### P2: Expand tests and gold data to cover biology and providers

Add deterministic tests for 20 bp direct repeats, 16 bp WARN repeats, IDT G/C 6 and A/T 10 homopolymers, Twist >=14 homopolymers, GenScript >=20 bp repeats, circular wraparound runs, annotated LTR/ITR WARN downgrades, and multi-finding aggregation. Add curated or synthetic gold cases for direct repeat 20 bp, local GC spread, and required viral-repeat context.

### P2: Improve messages and remediation

Messages should say whether the issue is synthesis complexity, bacterial propagation instability, or both. Suggested remediation should be context-sensitive: synonymous recoding for CDS repeats, provider complex-gene review for non-editable constructs, and stable propagation workflow/sequence-confirmed stock for required viral repeats.

## Human Review Questions

Human biology/product review is needed for these decisions:

- Which provider profile should be the default for "synthesis-ready" output when the user does not select Twist, IDT, or GenScript?
- Should annotated lentiviral LTRs and AAV ITRs always downgrade from FAIL to WARN, or are there product contexts where they must block final output pending manual review?
- How should provider profile be represented in current schemas: new `DesignSpec` field, `constraints` convention, or separate synthesis-ordering configuration?
- For IDT gBlocks, should repeats >=20 bp be WARN-only unless combined with another issue, or should product-facing synthesis readiness treat them as FAIL by default?

## Verification Performed

- `python -m pytest tests/validation/test_repeats.py` passed: 6 tests.
- Bare `pytest` was not available on PATH in this environment.
