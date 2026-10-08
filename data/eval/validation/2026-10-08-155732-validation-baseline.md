# Phase 3 Validation Baseline

- Engine version: `phase3-validation-v1`
- Gold policy: `curated_profile_diverse_tiered_quality_over_arbitrary_count`
- Known-good cases: `36`
- Known-bad cases: `52`
- Gold cases: `88`
- Accuracy: `1.000`
- Tier A accuracy: `1.000`
- Tier B accuracy: `1.000`
- Phase 3 gate met: `True`
- Misclassified cases: `0`

## Known-Good Tier Accuracy

| Tier | Correct | Total | Accuracy |
| --- | ---: | ---: | ---: |
| `A` | 25 | 25 | 1.000 |
| `B` | 11 | 11 | 1.000 |

## Per-Check Accuracy

| Check | Correct | Total | Accuracy |
| --- | ---: | ---: | ---: |
| `codon_usage` | 49 | 49 | 1.000 |
| `regulatory_compatibility` | 49 | 49 | 1.000 |
| `repeat_and_instability` | 49 | 49 | 1.000 |
| `restriction_site_conflicts` | 49 | 49 | 1.000 |

## Misclassifications

