> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Phase 1 Retrieval Gate Findings

## Gate Result

Phase 1 retrieval passed its MVP gate on 2026-05-31 using
`data/eval/retrieval_gold.jsonl`.

| Metric | Result |
| --- | ---: |
| Total gold cases | `21` |
| Scored retrieval queries | `20` |
| Clarification-only queries | `1` |
| Top-1 hit rate | `0.700` |
| Top-5 hit rate | `1.000` |
| MRR | `0.825` |
| Clarification pass rate | `1.000` |

The gate requires at least 20 realistic natural-language queries and top-5 hit
rate at or above 80 percent. The final report is
`data/eval/retrieval/2026-05-31-221057-retrieval-baseline.{md,json}`.

## Gold Set Composition

The expanded set deliberately tests more than the 12-record curated seed. It
includes verified GenBank rows for bacterial expression, bacterial cloning,
general shuttle, mammalian expression, mammalian reporter, yeast shuttle, and
an unknown-profile natural resistance plasmid. One underspecified viral-vector
request has no retrieval label and is scored separately as a clarification
behavior case.

The current 82-record index has no classified lentiviral or CRISPR vectors.
Those profiles were not fabricated in the gate set. They remain corpus-growth
requirements.

## Tuning Decisions

The bounded tuning pass made three retrieval-specific changes:

1. General shuttle records with sparse host metadata may remain retrieval
   candidates when no conflicting host evidence is present. This allows
   inspection retrieval without asserting validated host compatibility.
2. The deterministic intent parser preserves a conservative set of
   differentiating retrieval keywords as constraints, including exact plasmid
   names, origins, ARS terms, and calibrated resistance markers.
3. Composed query documents emit those preserved identity cues so semantic
   ranking retains important user wording.

These changes moved pDL278 and pRAS1_2402_89 from misses to rank 1 and moved the
pBluescript phagemid query from rank 5 to rank 2.

## Residual Work

Semantic retrieval is not a substitute for exact named-record lookup. Queries
such as `pFR-Luc` remain valid top-5 hits but should eventually use a lexical
or exact-name retrieval lane before semantic ranking. Provenance-constrained
queries, such as explicitly requesting only curated records, also need a
structured source filter rather than ranking tweaks.

The current gate demonstrates the Phase 1 retrieval MVP. It does not close the
Phase 0 corpus-scale gate or resolve Addgene partner-program access.

## Phase 1 Cleanup Closeout

The retrieval cleanup work is now limited to documentation closure. The lexical
exact-name lane is implemented with safe names and IDs, and the structured
filters remain preserved. Provenance source and DOI intent handling is also
implemented. `depositing_lab` is not available in the current schema or corpus,
so it cannot be used as a retrieval or filtering field here.

The corpus gap diagnosis in
`data/eval/corpus/2026-06-01-174026-lentiviral-crispr-gap.md` found no parser
bug. It leaves lentiviral and CRISPR seed addition blocked until an approved
exact source and intended-use policy is in place.

Phase 2 readiness is tracked in
`research/findings/phase2_readiness.md`. No Phase 2 implementation has started.
