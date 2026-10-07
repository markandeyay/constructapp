# AAV part registry: provenance

Every sequence in this directory is a verbatim slice of a GenBank flat file retrieved from NCBI,
cut at the coordinates of an annotated feature. Nothing was typed from memory, invented, trimmed
or padded. `build_parts.py` in this directory repeats the retrieval: `--write` regenerates the
JSON files, `--verify` re-fetches and compares them with what is on disk.

## Method

- Records were found by NCBI E-utilities `esearch` queries on db=nuccore (vector names, element
  names, "AAV" restricted by sequence length), not by remembered accession numbers.
- Each record was fetched with `efetch` (rettype=gb), its FEATURES table was read, and the part was
  sliced from the annotated coordinates. `build_parts.py` fails if the feature type or note at those
  coordinates is not what was expected.
- Query string carried `tool=construct-build`. No email parameter, no API key, requests throttled
  to under 3 per second.
- Retrieval date for every part below: **2026-10-07**.
- Coordinates are 1-based inclusive, as in the GenBank FEATURES table. All parts are plus strand
  slices of the source record.
- Lengths are the real retrieved lengths. Appendix B figures are planning figures and were not used
  to adjust anything. Differences are listed in the last section.
- Each part was also compared against at least one independent record by local alignment (see
  Corroboration). Only AAV2 ITRs are shipped (open question Q5).

## Parts shipped (14)

| Part id | Accession.version | Feature (type, note) | Coordinates | Length (bp) | Retrieved |
|---|---|---|---|---|---|
| itr.aav2_itr_left | NC_001401.2 | repeat_region, inverted terminal repeat | 1..145 | 145 | 2026-10-07 |
| itr.aav2_itr_right | NC_001401.2 | repeat_region, inverted terminal repeat | 4535..4679 | 145 | 2026-10-07 |
| promoter.cmv | AF396260.1 | regulatory (promoter), CMV | 150..812 | 663 | 2026-10-07 |
| promoter.cag | ON785708.1 | regulatory (promoter), no note | 221..1859 | 1639 | 2026-10-07 |
| promoter.ef1a | MT586119.1 | regulatory (promoter), promoter EF-1alpha | 593..1776 | 1184 | 2026-10-07 |
| promoter.efs | MT891328.1 | regulatory (promoter), EF-1alpha core promoter | 529..740 | 212 | 2026-10-07 |
| promoter.hsyn1 | MH282432.1 | regulatory (promoter), hSyn promoter | 216..687 | 472 | 2026-10-07 |
| promoter.cbh | KU341333.1 | regulatory (promoter), CBh promoter | 442..1240 | 799 | 2026-10-07 |
| promoter.gfap | PZ285974.1 | regulatory (promoter), gfaABC1D promoter | 1214..1904 | 691 | 2026-10-07 |
| promoter.mecp2_mini | PY026695.1 | misc_feature, meP229 Promoter | 1..225 | 225 | 2026-10-07 |
| polya.bgh | ON785708.1 | regulatory (polyA_signal_sequence), bovine growth hormone polyadenylation signal | 3786..4010 | 225 | 2026-10-07 |
| polya.sv40 | KX449554.1 | regulatory (polyA_signal_sequence), SV40 polyadenylation signal | 4852..4986 | 135 | 2026-10-07 |
| enhancer.wpre | MH282432.1 | regulatory (enhancer), WPRE | 2868..3456 | 589 | 2026-10-07 |
| intron.chimeric | KT345943.1 | intron, beta-globin-IgG-chimeric intron | 17..157 | 141 | 2026-10-07 |

Source record titles: NC_001401.2 adeno-associated virus 2 complete genome (RefSeq); AF396260.1
cloning vector pAAV-MCS; ON785708.1 cloning vector AAV-CAG-TPP1; MT586119.1 pAAV-EF1A-mScarlet
vector; MT891328.1 cloning vector (181)_P_EFS-mRuby3; MH282432.1 vector pAAV-hSyn1-GCaMP6s-P2A-mRuby3;
KU341333.1 synthetic plasmid pCas9n-sgPdx1; PZ285974.1 clone pZac2.1-GfaABC1D-mCherry; PY026695.1
patent sequence 24 from US 12359219 B2; KX449554.1 cloning vector pAAV2neo-1.3HBV; KT345943.1
cloning vector pAAV-hSyn-mCherry-hSyn-9(5).

Literature DOIs recorded in the JSON `notes` were looked up in PubMed by title and describe the
element, they are not the source of the sequence: AAV2 genome 10.1128/JVI.45.2.555-564.1983,
CAG 10.1016/0378-1119(91)90434-d, EF-1 alpha 10.1016/0378-1119(90)90091-5, hSyn 10.1038/sj.gt.3301905,
CBh 10.1089/hum.2010.245, GfaABC1D 10.1002/glia.20622, WPRE 10.1128/JVI.73.4.2886-2892.1999.

## Corroboration against independent records

Local alignment (match +1, mismatch -1, gap -1) of each shipped part against a second, independently
deposited record. Identity is matches over alignment columns.

| Part | Compared record and coordinates | Identity | Share of part aligned |
|---|---|---|---|
| promoter.cmv | PV882387.1 14..597 (CMV enhancer plus CMV) | 99.5% | 86% (the 584 bp core; the rest is 5' UTR) |
| promoter.cag | KF926476.1 203..2076 (CBA promoter) | 98.6% | 100% |
| promoter.ef1a | MT612428.1 593..1776 | 100% | 100% |
| promoter.efs | MT891323.1 529..740 | 100% | 100% (also contained in promoter.ef1a) |
| promoter.hsyn1 | AY640628.1 1759..2228 (minus strand), KT345943.1 187..656 | 100% | 99% (472 vs 470 bp) |
| promoter.cbh | KU341332.1 442..1240 | 100% | 100% |
| promoter.gfap | PZ398262.1 3384..4070 | 100% | 99% (691 vs 687 bp) |
| promoter.mecp2_mini | PY026693.1 1..426 (meP426) | 100% | 100% (the part is its 3' end) |
| polya.bgh | MN224158.1 3205..3429 | 100% | 100% |
| polya.sv40 | KX470733.1 61..195 | 100% | 100% |
| enhancer.wpre | JN898959.1 1491..2079; GQ202120.1 411..1008 (minus strand) | 100%; 99.2% | 100% |
| intron.chimeric | HQ416703.1 341..481 (minus strand) | 100% | 100% |
| itr.aav2_itr_left | AF396260.1 1..141 (left AAV-2ITR), MN224159.1 1..141 | 100% | 76% (those records carry a 141 bp ITR without the full D region) |
| itr.aav2_itr_right | AF396260.1 1913..2053, MN224159.1 3882..4022 | 100% | 90% |

promoter.cbh: also matched by patent record QQ167606.1 (annotated CBh promoter), local alignment
score 796 of 799 possible.

## Notes a user of the registry needs

- **ITRs are not exact mirror images.** The reverse complement of itr.aav2_itr_right matches
  itr.aav2_itr_left at 128 of 145 positions (88.3%) because the reference annotates the left ITR as
  flip oriented and the right ITR as flop oriented (misc_feature 42..83 and 4597..4638). Compare each
  ITR with its own reference, not with the other one, or the identity will fall below any 0.95
  threshold.
- **promoter.cmv** (663 bp) is the annotated feature of a commercial AAV plasmid. It extends past the
  roughly 584 bp enhancer plus promoter core through the transcription start and 5' UTR.
- **promoter.cag** source feature has no descriptive note. It was identified by alignment: it begins
  with the CMV enhancer (matched to the annotated CMV enhancer in PV882387.1) and matches the
  annotated chicken beta-actin promoter record KF926476.1 at 98.6%.
- **promoter.mecp2_mini** is the weakest source: a patent sequence record (US 12359219 B2), not a
  vector deposit, labelled meP229 though the record is 225 bp. It is shipped because its sequence
  is real, annotated, and consistent with the same patent's meP426 and a 1682 bp cassette record
  (PY026698.1 contains PY026693.1 exactly). Treat it as lower confidence than the others.
- Each promoter record states the count of ATG trinucleotides on its sense strand, for the Kozak
  context check.
- Source annotations were not independently curated beyond the corroboration above.
- The parenthetical author citation inside the hSyn feature note was replaced with the text
  "author citation omitted", because this repository carries no personal names.

## Parts attempted and not shipped (1)

| Part id | Why it is not shipped |
|---|---|
| polya.synthetic_short | The only synthetic polyadenylation annotation found was a 154 bp "synthetic poly(A) signal/transcriptional pause site" in a luciferase reporter vector (MZ090950.1, 4631..4784). That is a polyA plus pause cassette, not the roughly 50 bp minimal signal Appendix B describes, and it is longer than the 135 bp SV40 signal, so it would not serve as the smallest option. No record annotating a minimal synthetic polyA was found in several search rounds. Omitted rather than substituted. |

Other candidates examined and rejected: ON785707.1 (CAG-GFP, promoter annotation spans the whole
record), JN898959.1 CAG feature (935 bp, lacks the intron), MN224160.1 GFAP promoter (1679 bp, a
different, longer GFAP fragment than the Appendix B element), LT740684.1 (the EFS gene ORF, not the
promoter).

## Difference from Appendix B planning figures

| Part | Appendix B (approx.) | Retrieved |
|---|---|---|
| AAV2 ITR | 130 to 145 | 145 |
| CMV promoter | ~600 | 663 |
| CAG | ~1,700 | 1,639 |
| EF1 alpha full | ~1,200 | 1,184 |
| EFS | ~212 | 212 |
| hSyn1 | ~470 | 472 |
| GFAP | ~680 | 691 |
| CBh | ~800 | 799 |
| MeCP2 mini | ~230 | 225 |
| WPRE | ~600 | 589 |
| Chimeric intron | ~130 | 141 |
| bGH polyA | ~225 | 225 |
| SV40 polyA | ~135 | 135 |

The registry lengths are authoritative. The validator measures the actual sequence.
