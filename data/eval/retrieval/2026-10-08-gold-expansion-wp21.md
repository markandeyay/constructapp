# WP-21 Retrieval Gold Expansion

## Why

WP-20 embedded the whole corpus, taking it from 194 to 4,455 embedded records. Top-5
fell from 0.850 to 0.800 and MRR from 0.792 to 0.742. `make eval-check` still passed,
but with no margin at all: the threshold is a top-5 drop of 0.05 and the measured drop
was exactly 0.05, so one further lost query would breach the gate.

The underlying defect was not the corpus. It was the gold set. It had 21 records, of
which 20 were scored, and it was built against a corpus roughly two percent of the
size the corpus had reached. On a 20-query set every query is worth 0.05 top-5, which
is the whole regression budget. The gate could not distinguish a real regression from
one query changing rank.

The fix recorded in PROGRESS.md was to grow the gold set to match the corpus that
actually exists, rather than shrink the corpus back to fit the gold set. This is that
work.

## What Changed

The scored set goes from 20 queries to 55, and clarification cases from 1 to 2.
Total records: 21 to 57.

With 55 scored queries each query is worth 0.0182 top-5 instead of 0.05. A 0.05
threshold now absorbs two lost queries and breaches on the third, instead of
breaching on the first.

The 35 new scored cases and 1 new clarification case are authored and verified by
`scripts/build_retrieval_gold_candidates.py`.

## How Cases Were Chosen

Two rules, both there to stop the expansion from being a way of making the number
look better.

**Selection is outcome blind.** The candidate pool was fixed from corpus strata
before any retrieval was run, and no candidate was dropped because retrieval misses
it. The strata were the indexed `vector_profile`, then organism:

| Stratum | Corpus records | New gold cases |
| --- | --- | --- |
| `bacterial_cloning_vector` | 64 | 11 |
| `mammalian_reporter_vector` | 11 | 4 |
| `crispr_vector` | 7 | 2 |
| `bacterial_expression_vector` | 6 | 1 |
| `lentiviral_or_retroviral_transfer_vector` | 1 | 1 |
| `unknown` | 4,354 | 16 |
| clarification, no target | n/a | 1 |

A case that fails is a finding, not a case to delete. If a later reader finds a
failing case here, that is the intended state: the label is true to the corpus and
the retrieval is what is wrong.

**Every biological claim is checked against the corpus.** Each candidate declares
the exact substrings its rationale depends on, and the script asserts those
substrings appear in that target's own `plasmid_embeddings.composed_document`, read
from Postgres. Nothing was written from memory. No constant, coordinate or citation
is introduced; every claim is a quotation of what the corpus already indexes.

## The `unknown` Stratum Is The Point

4,354 of 4,455 records, 97.7 percent of the corpus, carry the profile `unknown`. The
previous gold set had no case anywhere in that stratum, so it did not measure the
corpus the system actually searches. Sixteen of the new cases are natural-plasmid
lookups drawn from it: a silver resistance determinant, a nickel/cobalt gene cluster,
an arsenic operon, CTX-M-17, an Axe-Txe toxin-antitoxin system, a class 1 integron
with a chloramphenicol efflux gene, and named-plasmid lookups such as pSK41.

These are deliberately not written as vector recommendations. A natural resistance
plasmid is not an engineered backbone, and the queries ask for the record, not for a
design.

## Newly Covered Profiles

The 2026-05-31 expansion recorded two corpus gaps: no indexed lentiviral or
retroviral records and no indexed CRISPR records. Both now exist, so both are now
labeled:

- `genbank:AF010170.1` pAMS, the single record indexed as a retroviral transfer
  vector, named in its own indexed description as a hybrid amphotropic/Moloney
  murine leukemia virus construct. First labeled target for that profile.
- Six natural plasmids indexing CRISPR-associated proteins, plus
  `genbank:CP160042.1`, the only record indexing a Cas9 inhibitor AcrIIA9 family
  protein.

The clarification case at line 21 claimed that the corpus had no indexed lentiviral
or CRISPR records. That claim was true when written and is now false, so its
rationale was corrected rather than left standing. The case itself is kept, and is
now a stronger case than before: a guess would land on a specific record instead of
returning nothing.

## Classification Defects Found, Not Papered Over

Writing the cases surfaced parser misclassifications. None of them were used as gold
labels for the profile the parser assigned, because that would be recording a
fabricated claim about biology in a file whose purpose is to be ground truth.

- The seven `crispr_vector` records are natural bacterial and archaeal plasmids
  carrying cas loci. They are not genome-editing delivery vectors. The gold query is
  written as a cas-locus lookup, which is what the records actually support, and the
  rationale says so.
- `genbank:FJ172221.1` pCmGFP is indexed `mammalian_reporter_vector`. It is a
  bacterial GFP plasmid from Neisseria gonorrhoeae with a `cat` marker and a `tac`
  promoter. The gold query asks for a GFP reporter with chloramphenicol selection,
  which is true of the record, and does not repeat the profile.
- `genbank:CP002966.1` pEMTOL05 and `genbank:CP016642.1` are also indexed
  `mammalian_reporter_vector`. They are natural bacterial plasmids whose only
  reporter-like evidence is a protein annotated "Luciferase-like" or "luciferase".
  No gold case was written for either: there is no query they could honestly answer.

Only 101 of 4,455 records carry any profile other than `unknown`. The corpus grew
roughly 23-fold in WP-20 and classification coverage did not grow with it. That is a
separate defect and is not fixed here.

## Verification

`python -m scripts.build_retrieval_gold_candidates verify` passed: all 36 candidates
checked against the live corpus, every declared substring present in its target's own
indexed document. So every biological claim in the new cases is a quotation of the
corpus, not a recollection.

The merged file was also checked structurally: 57 records, every record matching the
exact key shape, no stray quote inside any value, no em dash or en dash, and every
target id matching the accession pattern `tests/test_retrieval_gold.py` enforces.

## First Measured Result

`make eval-retrieval` on the expanded set, report
`data/eval/retrieval/2026-10-09-023638-retrieval-baseline.md`:

| Metric | Old set, 20 scored | New set, 55 scored |
| --- | --- | --- |
| Top-1 | 0.750 | 0.291 |
| Top-5 | 0.800 | 0.418 |
| MRR | 0.742 | 0.333 |
| Clarification pass | 1.000 | 1.000, 2 of 2 |

**These numbers are not comparable to the old ones and must not be read as a
regression.** The system did not change between the two runs; the measuring
instrument did. The old set was 20 queries weighted toward curated records.

23 of 55 scored queries hit in the top 5. The expansion did what it was built to do:
it found a defect the old set could not see.

## What The Expansion Found

**Every one of the 16 natural-plasmid cases missed, and all 16 retrieved nothing at
all.** The pipeline short-circuited into a clarification question instead of
searching. Two distinct parser defects, both in `packages/retrieval/intent_parser.py`:

1.  **A named host that is not a model organism parsed as no host.** "Is there a
    Staphylococcus epidermidis plasmid with an ethidium bromide resistance
    determinant?" returned "Which target organism or cell line should this plasmid
    design use?" with zero results. `ORGANISM_TERMS` covers nine model organisms, so
    any other named species reads as absent, and the clarification branch then
    blocked retrieval outright.
2.  **`tetM` false-matched the Tet-On/Tet-Off expression system.** "Which
    Lactiplantibacillus plantarum plasmid carries tetM?" returned "Should the
    Tet-regulated design be Tet-On or Tet-Off?" The test was `"tet" in
    normalized_text`, a raw substring check, and `tetM` normalizes to `tetm`. A
    tetracycline resistance gene is not an inducible promoter. Every tet resistance
    gene name hit this, as did the word "tetracycline" itself.

Together these made roughly 98 percent of the corpus unreachable through the
natural-language path. The old 20-query set could not have caught either, because it
contained no query naming a non-model organism and none naming a tet resistance gene.

## Fixes Applied And Verified

Three changes were made in response:

- `packages/core/vocabularies.py`: the tetracycline marker term gained the efflux and
  ribosomal-protection gene names (tetA through tetX). These are the standard names
  for the class, not entries added to satisfy particular gold cases, and they are
  needed because `contains_term` matches whole words.
- `packages/retrieval/intent_parser.py`: the Tet-system test is now a whole-word
  match against `TET_SYSTEM_PHRASES` rather than a substring, so a resistance gene
  cannot trigger it.
- `packages/retrieval/intent_parser.py`: the organism clarification no longer blocks
  a corpus lookup that names something concrete to search for. The alternative,
  enumerating species in `ORGANISM_TERMS` one gold case at a time, is what produced
  the two ad-hoc entries already in that tuple and does not generalize.

All three are verified. Both defects are now pinned by 11 tests in
`tests/retrieval/test_intent_parser.py`, and both pins were proven non-vacuous by
tamper: restoring the `"tet" in normalized_text` substring check and removing the tet
gene synonyms fails 4 tests, and neutering the lookup bypass fails 9. The suite goes
from 1648 to 1659 passing with 2 skipped, and `ruff check .` is clean.

One of the three fixes was wrong on its first attempt, which is worth recording
because the mistake is easy to repeat. The lookup phrases were originally written as
contiguous strings matched with `in`: "which plasmid", "is there a plasmid". That
failed on exactly the queries it was written for, because in "Which
Lactiplantibacillus plantarum plasmid carries tetM?" the species name sits between
the two words. The eval returned byte-identical metrics, which is what a no-op looks
like. Lookup detection now matches sentence-opening forms instead.

A non-vacuity guard is included deliberately: both fixes widen the path to retrieval,
so both could be satisfied by never clarifying at all. Two requests that name no
host, no application and no feature to search for are asserted to still be questioned
rather than guessed at.

## Second Measured Result, And What It Shows

`make eval-retrieval` after the fixes, report
`data/eval/retrieval/2026-10-09-025502-retrieval-baseline.md`:

| Metric | Before fixes | After fixes |
| --- | --- | --- |
| Top-1 | 0.291 | 0.309 |
| Top-5 | 0.418 | 0.436 |
| MRR | 0.333 | 0.351 |

**The fixes moved one query.** All 16 natural-plasmid queries now search instead of
returning nothing, which is the behaviour the fixes were for, but 15 of them still
miss. The parser defects were masking a second, larger problem rather than being the
cause of the misses.

What the misses look like now is the useful part. "Is there a Staphylococcus
epidermidis plasmid with an ethidium bromide resistance determinant?" returns
Streptococcus hyointestinalis, Streptococcus sp. KHUD_016, Streptomyces sp. HK1,
Streptococcus thermophilus and Sulfolobus islandicus. The ranking is matching on
surface similarity between genus names and ignoring the discriminating feature
entirely, even though "ethidium bromide resistance determinant" appears verbatim in
exactly one indexed document in the corpus. "Which plasmid carries the CTX-M-17
extended-spectrum beta-lactamase?" returns only two results, both pTRE luciferase
plasmids, which suggests the structured filters are also over-restricting the
candidate set before ranking.

So the open defect is retrieval quality, not intent parsing: a dense-only ranker over
these composed documents does not discriminate rare exact identifiers such as gene
names and accession-like tokens. A lexical or hybrid component would be the obvious
thing to evaluate, since every one of these queries names a token that is literally
present in its target document. That is a substantially larger piece of work than
these three fixes and has NOT been attempted here.

## The Gate Baseline Is Now Invalid

`make eval-check` compares the latest dashboard against the previous one. Because the
gold set changed underneath it, it will read a top-5 drop of roughly 0.38 and breach.
That is the gate working correctly on an invalid comparison.

**No threshold was moved and no gold case was altered to make it pass.** Resolving
this needs a deliberate decision: either fix retrieval until the new set scores well,
or record a new baseline explicitly labeled as an instrument change rather than a
quality change. The second resets a safety net and should not be done silently.
