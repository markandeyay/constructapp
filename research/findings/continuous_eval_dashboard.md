> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Continuous Evaluation Dashboard

## Purpose

The project now has separate evaluation commands for retrieval, generation, validation, and corpus quality. Those commands remain the source of truth for their own domains, but routine development needs a single on-demand view that answers: did this change regress the system?

The dashboard should aggregate the latest outputs from the existing suites into one Markdown file under `data/eval/dashboard_<timestamp>.md`. It should not introduce a new evaluation framework, duplicate suite logic, or hide per-suite reports. It should link to the source report files and summarize the headline metrics.

## Cadence

Run on demand at review checkpoints and before merge consolidation:

```powershell
make eval-all
make eval-check
```

Future CI integration can run `make eval-check` nightly or on release branches. It is intentionally heavier than `make test` because it exercises live local services and corpus state.

## Included Suites

| Suite | Command | Source Reports | Dashboard Metrics |
| --- | --- | --- | --- |
| Retrieval | `make eval-retrieval` | `data/eval/retrieval/*-retrieval-baseline.json` | top-1 hit rate, top-5 hit rate, MRR, clarification pass rate, scored query count |
| Generation | `make eval-generation MODE=fake` | `data/eval/generation/*-generation-eval.json` | generator mode/version, strict success rate, phase-2 proxy rate, component-complete rate, scored case count |
| Validation | `make validate-sample MODE=gold` | `data/eval/validation/*-validation-baseline.json` | accuracy, known-good count, known-bad count, Phase 3 gate flag, per-check accuracy |
| Corpus Quality | `make quality-report` | `data/eval/quality/*-quality-report.json` | total records, complete annotations, complete rate, unclassified records, parse errors, duplicate clusters |

## Regression Thresholds

Defaults are conservative and should be tunable at the command line:

| Metric | Default Threshold | Rationale |
| --- | ---: | --- |
| Retrieval top-5 hit rate | drop > 0.05 | The current gold set is small but gate-critical; a 5-point top-5 drop means at least one realistic query likely fell out of the top 5. |
| Retrieval MRR | drop > 0.10 | Rank quality can move more than hit/miss during tuning; larger movement should be reviewed. |
| Validation accuracy | drop > 0.02 | Phase 3 is deterministic safety logic; any drop from the 1.000 curated baseline is concerning, but 2 points avoids noise if the gold set grows. |
| Complete annotations | drop > 10 records | Parser/corpus changes can move a handful of records; losing more than 10 complete records suggests a broad parser or schema regression. |
| Generation strict success | informational only | Fake generation intentionally copies templates, so strict novelty remains 0.000. This becomes gated only after a real fine-tuned model is authorized. |
| Quality parse errors | increase > 0 | Parser errors should not silently grow. Any increase should be flagged. |

`make eval-check` should exit non-zero only for threshold breaches. The dashboard itself should always render if enough source reports exist.

## Dashboard Layout

The Markdown dashboard should use this structure:

```markdown
# Continuous Evaluation Dashboard

- Generated at: `...`
- Commit: `...`
- Compared to: `data/eval/dashboard_...md` or `<none>`
- Overall status: `PASS` / `REGRESSION`

## Headline Metrics

| Area | Metric | Current | Previous | Delta | Threshold | Status |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Retrieval | Top-5 hit rate | 1.000 | 1.000 | +0.000 | -0.050 | PASS |
| Retrieval | MRR | 0.938 | 0.938 | +0.000 | -0.100 | PASS |
| Validation | Accuracy | 1.000 | 1.000 | +0.000 | -0.020 | PASS |
| Corpus | Complete annotations | 141 | 141 | 0 | -10 | PASS |

## Retrieval

- Source: `data/eval/retrieval/...json`
- Queries: `21`, scored retrieval queries: `20`
- Top-1: `0.900`
- Top-5: `1.000`
- MRR: `0.938`
- Clarification pass: `1.000`

## Generation

- Source: `data/eval/generation/...json`
- Generator: `fake-template-generator-v1`
- Scored cases: `13`
- Phase 2 proxy rate: `0.615`
- Strict success: `0.000`
- Note: fake generation strict success is expected to remain zero because template-copy novelty is false.

## Validation

- Source: `data/eval/validation/...json`
- Accuracy: `1.000`
- Known-good / known-bad: `31 / 52`
- Phase 3 gate met: `true`
- Per-check accuracy: restriction, repeats, codon, regulatory

## Corpus Health

- Source: `data/eval/quality/...json`
- Total records: `256`
- Complete annotations: `141`
- Unclassified: `99`
- Parse errors: `0`
- Duplicate clusters: `3`

## Regressions

No threshold breaches.
```

## Implementation Notes

- Keep suite execution in Makefile targets and parsing in a small Python module so tests can exercise aggregation without running external services.
- Store machine-readable sidecar JSON next to each dashboard Markdown file. `eval-check` can compare the two most recent dashboard JSON files instead of parsing Markdown.
- The dashboard should tolerate missing previous dashboards and report `Compared to: <none>`.
- A failed suite command should fail `make eval-all`; a missing report after a successful command should be treated as an implementation error.
- Use newest report by modification time or timestamped filename after each command completes.
