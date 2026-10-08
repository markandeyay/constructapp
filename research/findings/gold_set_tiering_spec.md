> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Curated Validation Gold-Set Tiering

## Context

The Phase 3 validation gold set now admits real plasmid records with two biologically distinct validation outcomes. The original curated known-good set contained records that validated cleanly. After the 2026-06-18 validation refinements, five additional reviewed candidates became defensible: one validates cleanly and four validate with an intentional repeat warning. The human policy decision is that real known-good plasmids may carry documented caveats; rejecting WARN-status records after adding WARN semantics would make the gold set less biologically realistic.

## Tiers

The curated known-good file uses a `tier` field with exactly two allowed values.

| Tier | Name | Admission rule | Evaluation expectation |
| --- | --- | --- | --- |
| `A` | strict-clean | The validation report is overall `PASS` and no check returns `WARN` or `FAIL`. | The engine must return overall `PASS` with no WARN checks. |
| `B` | accepted-with-caveats | The validation report is overall `PASS` or `WARN`, no check returns `FAIL`, and every expected WARN is documented in the record metadata. | The engine must return no FAIL checks, and every documented expected WARN must appear. |

Tier B exists for records whose source provenance and biological role are strong enough to treat them as known-good while preserving the caution surfaced by deterministic validation. A tier-B entry must include an `expected_warnings` list. Each item records the validation check name and a concise rationale for why that warning is expected rather than a regression.

## Schema Additions

Each curated known-good JSONL row gains:

```json
{
  "tier": "A",
  "tier_label": "strict-clean",
  "expected_warnings": []
}
```

For tier-B records:

```json
{
  "tier": "B",
  "tier_label": "accepted-with-caveats",
  "expected_warnings": [
    {
      "check": "repeat_and_instability",
      "status": "WARN",
      "rationale": "Intentional reviewed vector architecture; warning should remain visible for synthesis/stability review."
    }
  ]
}
```

The existing `warn_justifications` field remains for compatibility with older reports. For new tier-B entries, `warn_justifications` mirrors the warning rationale in human-readable form.

## Metrics

The curated validation baseline reports three headline accuracy values:

- `tier_a_accuracy`: strict-clean known-good cases classified as clean PASS, plus known-bad cases excluded from this tier metric.
- `tier_b_accuracy`: accepted-with-caveats known-good cases classified as PASS/WARN with the documented WARNs present and no FAIL checks.
- `accuracy`: combined curated-gold accuracy across tier-A known-good, tier-B known-good, and known-bad cases.

The Phase 3 gate threshold remains `accuracy >= 0.95`, where `accuracy` is the combined value. Tier-specific metrics are surfaced so a future regression cannot hide behind the combined score. A fall in tier-A accuracy means clean constructs are being over-warned or failed; a fall in tier-B accuracy means caveated real constructs are no longer producing the expected warning shape or are failing.

## Current Admissions

The human approved admission of all five defensible post-refinement candidates:

- `AF013597.1`: tier A, no caveats.
- `U47121.2`: tier B, expected `repeat_and_instability` WARN for reviewed intentional vector architecture.
- `AF041805.1`: tier B, expected `repeat_and_instability` WARN for reviewed intentional yeast shuttle vector architecture.
- `AF041806.1`: tier B, expected `repeat_and_instability` WARN for reviewed intentional yeast shuttle vector architecture.
- `AF041807.1`: tier B, expected `repeat_and_instability` WARN for reviewed intentional yeast shuttle vector architecture.

After refreshing the prior 31 known-good records against the current validator, 7 pre-existing records also classify as tier B because their current validation reports contain documented WARN checks. The expanded known-good set therefore contains 25 tier-A records and 11 tier-B records. This is intentional: tiering reflects the validator's current report shape, not the historical expectation embedded when a row was first curated.

Future tier-B admissions should be conservative: WARN type matters, and every WARN must be acknowledged by metadata. Multiple WARN entries are allowed only when every warning is expected and explicitly documented; otherwise the record should remain a candidate rather than enter the gold set.
