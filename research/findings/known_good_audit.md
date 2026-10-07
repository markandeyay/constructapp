# Known-Good Validation Audit

## Scope

I audited the curated known-good validation set in `data/eval/validation/curated_known_good.jsonl`, the shortfall blocker in `data/eval/validation/curated_known_good_blocker.json`, the curation generator in [`tools_curate_known_good.py`](tools_curate_known_good.py:113), the Phase 3 design spec in [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md:188) and [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md:593), and the current validation engine in [`packages/validation/engine.py`](packages/validation/engine.py:32) plus its check modules.

The task-referenced `scripts/build_curated_known_good_validation.py` does not exist in this checkout. The actual known-good curation path is `tools_curate_known_good.py`.

## Bottom Line

The 31 retained records were the only defensible ones because the generator only keeps records that are both:

1. complete annotated local corpus records with parseable raw provenance, and
2. either `PASS` under the Phase 3 engine or `WARN` only for a small allowed set of non-blocking checks.

The blocker records the full screening result: 141 complete payloads were examined, 110 failed validation, 15 passed, and 16 warned, leaving 31 defensible records total ([`curated_known_good_blocker.json`](data/eval/validation/curated_known_good_blocker.json:2)).

## Why 31 Is Defensible

The generator logic is explicit. It:

- loads only complete corpus payloads,
- parses the cached raw GenBank record,
- skips incomplete or unknown-profile records,
- runs `ConstraintEngine.validate(...)`,
- keeps only `PASS` reports, and keeps `WARN` reports only when the warning names are limited to `repeat_and_instability`, `regulatory_compatibility`, or `codon_usage` ([`tools_curate_known_good.py`](tools_curate_known_good.py:135), [`tools_curate_known_good.py`](tools_curate_known_good.py:158), [`tools_curate_known_good.py`](tools_curate_known_good.py:202)).

That matches the Phase 3 contract in the design doc: deterministic validation, PASS/WARN/FAIL per check, and a known-good/known-bad gate for at least 50 each ([`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md:591), [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md:603)).

The retained entries are not synthetic "hand-picked" positives. Their embedded provenance points to actual local corpus records, with:

- `raw_ref` fields back to cached GenBank sources,
- `citations` pointing to NCBI nuccore, vendor maps, or direct-submission references,
- `known_good_basis` distinguishing curated seed manifest records from complete annotated corpus records,
- `warn_justifications` explaining why a warning was accepted instead of rejected.

Examples:

- `pUC18` carries `raw/curated/pUC18.gb`, NCBI and Addgene citations, and a manifest note that it is a pUC19 sibling with reversed MCS orientation ([`curated_known_good.jsonl`](data/eval/validation/curated_known_good.jsonl:1)).
- `pUC19c` carries `raw/curated/pUC19.gb`, NCBI plus NEB provenance, and a manifest note describing the cloning-vector context ([`curated_known_good.jsonl`](data/eval/validation/curated_known_good.jsonl:2)).
- `pCal-n-ek` and `pMal-X` are complete GenBank-backed records with direct-submission provenance, and their only retained issues are bounded WARNs with explicit justifications ([`curated_known_good.jsonl`](data/eval/validation/curated_known_good.jsonl:30), [`curated_known_good.jsonl`](data/eval/validation/curated_known_good.jsonl:31)).

## Absolute Versus Addressable Disqualifiers

### Absolute disqualifiers

These are hard fails under the current engine and are not defensible for the known-good set:

- Restriction-site conflict when an explicitly requested enzyme cuts outside the annotated MCS ([`packages/validation/restriction.py`](packages/validation/restriction.py:39)).
- Repeat / instability failures: homopolymer runs of 12+ bases, 100 bp windows with GC outside 20-80%, or exact direct/inverted repeats of 40 bp or more ([`packages/validation/repeats.py`](packages/validation/repeats.py:20)).
- Codon usage failures when the GOI's host-specific adaptation score falls below 0.55 ([`packages/validation/codon.py`](packages/validation/codon.py:75)).
- Regulatory incompatibility failures for missing selectable marker, incompatible origin, or incompatible promoter/host pairing ([`packages/validation/regulatory.py`](packages/validation/regulatory.py:18)).
- Any `FAIL` overall report from the deterministic engine is excluded by the generator's defensibility filter ([`packages/validation/engine.py`](packages/validation/engine.py:32), [`tools_curate_known_good.py`](tools_curate_known_good.py:135)).

These are "absolute" in the audit sense: the current source record either violates the rule or it does not. Extra narrative cannot turn a deterministic `FAIL` into a known-good entry without changing the underlying sequence, annotation, or design spec.

### Potentially addressable with more evidence or clarification

These are the cases the generator already treats as defensible when the context is explicit:

- Non-blocking repeat / instability warnings below the hard threshold.
- Marginal codon-usage warnings, including rare-codon clusters, when the record is a source vector and not a de novo optimization target.
- Regulatory warnings about downstream terminator completeness when the parser lacks enough cassette context to prove a stronger `PASS`.

The known-good file itself encodes these justifications in `warn_justifications`, and the generator only accepts the warning classes above ([`tools_curate_known_good.py`](tools_curate_known_good.py:113), [`tools_curate_known_good.py`](tools_curate_known_good.py:135)).

This is the biology question that remains visible in the set, but it is not a blocker for the audit:

- Should a missing downstream terminator be treated as advisory for source vectors and cloning backbones, or as blocking only for expression cassettes?
- Should codon usage be evaluated against the source vector's native coding region when the record is being used as provenance rather than as a de novo optimized expression target?

The current implementation answers both conservatively by allowing WARNs only when the curation note and provenance make the context explicit.

## Conclusion

The 31-record set is the defensible intersection of complete local corpus provenance and Phase 3 outcomes that are either `PASS` or a bounded, explicitly justified `WARN`. The shortfall is not a curation mistake in the narrow sense; it is the result of the current corpus and engine leaving too few complete records that clear that bar while still preserving source truthfulness.

## Policy Decision and Gate Closure

On 2026-06-06, the human owner accepted the 31 known-good / 52 known-bad curated set as the operational Phase 3 baseline. The earlier 50-record known-good threshold in `SYSTEM_DESIGN.md` was treated as a planning placeholder rather than a biology-grounded requirement.

The rationale is quality-based: this audit found that the retained 31 known-good records are profile-diverse, provenance-backed, and defensible under the current deterministic engine, while expanding to 50 with the current corpus would require weakening the admission standard. The gate criterion was refined to require at least 95% accuracy across a curated, profile-diverse known-good/known-bad set whose size is determined by source quality.

The curated baseline generated at `data/eval/validation/2026-06-07-033018-validation-baseline.md` reports:

- Known-good cases: `31`
- Known-bad cases: `52`
- Total curated cases: `83`
- Overall accuracy: `1.000`
- Per-check accuracy: `1.000` for restriction-site conflicts, repeat/instability, codon usage, and regulatory compatibility
- Misclassified cases: `0`

Under the refined policy, this formally closes the Phase 3 validation gate while keeping the curation standard explicit and auditable.
