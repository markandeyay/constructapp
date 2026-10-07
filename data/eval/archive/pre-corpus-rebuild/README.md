# Archived evaluation dashboards, pre corpus rebuild

These four dashboards were produced between 2026-06-16 and 2026-06-30 against a
retrieval corpus of 82 records (12 curated plus 70 GenBank, per
`data/eval/retrieval/2026-05-31-gold-expansion-rationale.md`).

## Why they are archived rather than used as a comparison baseline

That corpus did not exist anywhere when this build started. The Postgres
database was empty, zero relations in the public schema, the object store held
an empty bucket, and no cached raw blobs were present in the tree. The corpus
had to be rebuilt from NCBI from scratch.

The rebuilt corpus is 194 records. It is a different corpus: different size and
different composition. The regression thresholds in `packages/eval/continuous.py`
compare the two most recent dashboards in order to catch a CODE regression
between runs. Comparing a run on the rebuilt corpus against a run on a corpus
that no longer exists does not measure a code change, it measures the corpus
swap, so the comparison was not meaningful and these files were moved out of the
comparison path.

Nothing was deleted. These files stay here, and in git history, as the record of
what the earlier corpus produced.

## The numbers, stated plainly

Last pre-rebuild run, 2026-06-30, on the 82 record corpus:

| Area | Metric | Value |
|---|---|---|
| retrieval | top5_hit_rate | 0.9375 |
| retrieval | mrr | 0.9375 |
| quality | complete_annotations | 141 |

First post-rebuild run, 2026-10-07, on the 194 record corpus:

| Area | Metric | Value |
|---|---|---|
| retrieval | top5_hit_rate | lower, see the current dashboard |
| retrieval | mrr | 0.7917 |
| quality | complete_annotations | 23 |

Retrieval ranking is lower on the rebuilt corpus. The rebuild used the broader
`expansion` query, so the corpus carries more records that are not curated
vector deposits, which makes the ranking task harder and leaves fewer records
with complete annotations. This is a property of the corpus, not a change in the
retrieval code.

## Claim safety, per specification section 16

The earlier retrieval figures above describe a corpus that is no longer in the
system. Do not quote them as current. Quote the current dashboard.

The plasmid validation gold set is unaffected by the corpus rebuild, because
those checks are deterministic functions over supplied sequences. It still
reports accuracy 1.0 with the phase 3 gate met on the same curated set of 36
known-good and 52 known-bad constructs.
