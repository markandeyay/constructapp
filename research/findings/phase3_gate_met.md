> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Phase 3 Gate Status

## Current Gate Result

Phase 3 remains gate-met under the human-approved curated-quality policy. The latest tiered curated validation baseline is:

- Baseline report: `data/eval/validation/2026-06-18-170718-validation-baseline.md`
- Known-good records: `36`
- Known-bad records: `52`
- Total curated cases: `88`
- Combined accuracy: `1.000`
- Tier A accuracy: `1.000` (`25/25`)
- Tier B accuracy: `1.000` (`11/11`)
- Phase 3 gate met: `True`

## Tiered Known-Good Policy

The known-good set now separates strict-clean records from accepted real-world records with documented caveats:

- Tier A, strict-clean: overall `PASS` and no WARN checks.
- Tier B, accepted-with-caveats: no FAIL checks, with expected WARN checks explicitly documented in the gold-set row.

This policy matches the validation engine's purpose. A real deposited plasmid can be biologically known-good while still carrying an intentional repeat or other cautionable feature that should remain visible to synthesis/stability review. Tiering prevents those records from being flattened into a binary "clean" label while still using them to test the validator's ability to distinguish warnings from blocking failures.

## Candidate Admissions

The human reviewed `data/eval/validation/post_refinement_candidate_evaluation.md` and approved admission of all five defensible candidates:

- `AF013597.1`: strict-clean tier A.
- `U47121.2`: tier B with expected `repeat_and_instability` WARN for reviewed intentional mammalian-expression vector architecture.
- `AF041805.1`: tier B with expected `repeat_and_instability` WARN for reviewed intentional yeast-shuttle vector architecture.
- `AF041806.1`: tier B with expected `repeat_and_instability` WARN for reviewed intentional yeast-shuttle vector architecture.
- `AF041807.1`: tier B with expected `repeat_and_instability` WARN for reviewed intentional yeast-shuttle vector architecture.

Refreshing the pre-existing 31 known-good entries against the current validator moved 7 prior rows into tier B because they now produce documented WARN reports. That is a metadata correction, not a gate regression: the combined baseline remains 100% accurate and the tier metrics make those caveats explicit.

## Future Admissions

Future tier-B rows must document every expected WARN by check name and rationale. If an admitted row develops an unexpected WARN or any FAIL under the current validator, that should count as a baseline regression until the row metadata or validation rule is reviewed.
