# Demo transgene: beta-galactosidase (lacZ)

This is the payload the section 15.3 demo pastes into the AAV transgene field.
It is a real coding sequence, retrieved from NCBI, not a constructed or
length-calibrated artifact.

| Field | Value |
|---|---|
| File | `transgene_lacZ_JF300162.1.txt` |
| Accession | GenBank JF300162.1 |
| Record | Escherichia coli str. K-12 substr. MG1655 beta-galactosidase (lacZ) gene, complete cds |
| Feature | CDS, plus strand, coordinates 1..3075 of that record |
| Length | 3,075 bp |
| Retrieved | 2026-10-08, NCBI E-utilities |

## Why this gene

Beta-galactosidase has been the standard oversized reporter cargo in AAV work
for decades, so it is both a real sequence and the honest illustration of the
constraint the demo is about: at 3,075 bp it does not fit alongside a large
ubiquitous promoter.

## Verified properties

Checked at the time it was added, and re-checked by the validator on every run:

* ACGT only, no ambiguity codes
* length divisible by three
* ATG start
* exactly one in-frame stop, and it is the final codon

## What the demo does with it

With the AAV2 ITR pair, the CAG promoter and the bGH polyA, all from the curated
part registry, the cassette totals 5,229 bp. That is 529 bp over the 4,700 bp
single stranded packaging target and 29 bp past the 5,200 bp hard ceiling, so it
fails. Replacing CAG with EFS saves 1,427 bp and brings it to 3,802 bp, which
clears the limit.

One advisory remains after the substitution, and it is worth saying out loud
rather than hiding: lacZ begins ATGACC, so the base after the start codon is A
where a G is preferred, and the Kozak context is weak. That is a property of the
real gene, not of this tool, and the validator says how to fix it. Section 3.4 is
exactly the argument that a warning with an explanation is the product.

# Demo guide RNA target: beta-lactamase region of pUC19

`grna_target_bla_pUC19.txt` is the 950 bp target sequence of gold case
`grna.good.a1.spcas9_forward_bla_guide` in `tests/gold/grna/tier_a.json`, a real
beta-lactamase region. Pasted into the Guide RNA tab with SpCas9, Knockout and
the target-and-construct-only search space, it returns 10 of 216 enumerated
guides with overall PASS, and the off-target statement names 950 bp and says it
is not genome-wide.

# Demo assembly pair

The two Gibson fragments in `docs/demo.md` are the fragments of gold case
`assembly.good.a1.gibson_two_fragments` in `tests/gold/assembly/tier_a.json`,
plus strand slices of the CBh and CMV promoter records. Overall PASS, 15 checks.
