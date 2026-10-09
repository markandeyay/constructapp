"""Author and verify the WP-21 retrieval gold expansion.

The retrieval gold set had 20 scored queries and was built against a corpus
roughly two percent of the size the corpus reached in WP-20. One lost query was
worth 0.05 top-5, which is exactly the regression threshold, so the eval gate had
no headroom. This script expands the set.

Two rules govern it, and both exist to stop the expansion from being a way of
making a number look better:

1.  Selection is outcome blind. The candidate pool below was fixed from corpus
    strata (indexed vector profile, then organism) before any retrieval was run,
    and no candidate is removed because retrieval misses it. A case that fails is
    a finding, not a case to delete.
2.  Every biological claim is checked against the corpus. Each candidate names
    the exact substrings its rationale depends on, and `verify` asserts those
    substrings appear in the target's own indexed document, read from Postgres.
    Nothing here is written from memory: if the corpus does not say it, the
    candidate fails and is not emitted.

Run `python -m scripts.build_retrieval_gold_candidates verify` to check the
candidates against the live corpus, and `... emit` to write the JSONL records.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = ROOT / "data" / "eval" / "retrieval_gold.jsonl"

#: The corpus the candidates were drawn from. Recorded so a later reader can tell
#: whether a failing verification means the candidate was wrong or the corpus
#: moved underneath it.
CORPUS_SNAPSHOT = "the 4455-record corpus on 2026-10-08"
PROVENANCE = f"WP-21 expansion against {CORPUS_SNAPSHOT}"


@dataclass(frozen=True)
class Candidate:
    """One gold case, with the evidence its rationale rests on."""

    query: str
    targets: tuple[str, ...]
    rationale: str
    #: Substrings that must appear in the indexed document of EVERY target.
    evidence_all: tuple[str, ...] = ()
    #: Substrings that must appear in the indexed document of AT LEAST ONE
    #: target. Used where a case accepts a family whose members differ, for
    #: example two origins of replication across the same vector series.
    evidence_any: tuple[str, ...] = ()
    expected_clarification: bool = False
    stratum: str = ""
    notes: str = ""

    def source(self) -> str:
        """The `source` field as it appears in the gold file.

        Kept byte-identical to the merged records so this script stays the single
        source of truth: `emit` output should diff clean against the gold file.
        """
        if self.expected_clarification:
            return (
                "No corpus target is claimed. Recorded as expected retrieval behaviour for an "
                f"underspecified request against {CORPUS_SNAPSHOT}."
            )
        evidence = self.evidence_all + self.evidence_any
        if len(evidence) == 1:
            rendered = evidence[0]
        else:
            rendered = ", ".join(evidence[:-1]) + f" and {evidence[-1]}"
        return (
            f"Indexed plasmid_embeddings.composed_document for {self._target_phrase()}, "
            f"verified to contain {rendered}. {PROVENANCE}."
        )

    def _target_phrase(self) -> str:
        if len(self.targets) == 1:
            return self.targets[0]
        return ", ".join(self.targets[:-1]) + f" and {self.targets[-1]}"


# --------------------------------------------------------------------------
# Stratum A: records the parser assigned an engineered vector profile.
# These are the queries the capability exists to answer.
# --------------------------------------------------------------------------

ENGINEERED: list[Candidate] = [
    Candidate(
        query="I am looking for a cloning vector that carries gentamicin resistance rather than the usual ampicillin or kanamycin.",
        targets=("genbank:U35129.1", "genbank:U35130.1"),
        rationale=(
            "pBSL141 and pBSL142 are the only two records in the corpus whose indexed selectable "
            "markers include a gentamicin 3-acetyltransferase, and both are indexed as bacterial "
            "cloning vectors."
        ),
        evidence_all=("Bacterial cloning vector", "gentamicin 3-acetyltransferase"),
        stratum="bacterial_cloning_vector",
    ),
    Candidate(
        query="Which cloning vector in the collection uses a low-copy p15A origin together with chloramphenicol selection?",
        targets=("genbank:U35131.1", "genbank:U35132.1", "genbank:U35235.1"),
        rationale=(
            "pBSL159, pBSL168 and pBSL167 are indexed as bacterial cloning vectors carrying a "
            "chloramphenicol acetyltransferase marker on a p15A origin, which is the copy-number "
            "distinction the query asks about."
        ),
        evidence_all=("Bacterial cloning vector", "chloramphenicol acetyltransferase", "p15A origin"),
        stratum="bacterial_cloning_vector",
    ),
    Candidate(
        query="I need a cloning backbone with streptomycin resistance for selection in E. coli.",
        targets=("genbank:U35128.1", "genbank:U35133.1"),
        rationale=(
            "pBSL130 and pBSL175 both carry an indexed streptomycin 3-adenylyltransferase marker "
            "and are indexed as bacterial cloning vectors."
        ),
        evidence_all=("Bacterial cloning vector", "streptomycin 3-adenylyltransferase"),
        stratum="bacterial_cloning_vector",
    ),
    Candidate(
        query="Recommend a cloning vector with a neomycin or kanamycin phosphotransferase marker and a single-strand f1 origin.",
        targets=("genbank:U35127.1", "genbank:U35136.1", "genbank:U35137.1"),
        rationale=(
            "pBSL128, pBSL97 and pBSL99 are indexed bacterial cloning vectors with a neomycin "
            "phosphotransferase marker and an indexed f1 origin alongside the pUC origin."
        ),
        evidence_all=("Bacterial cloning vector", "neomycin phosphotransferase", "f1 origin"),
        stratum="bacterial_cloning_vector",
    ),
    Candidate(
        query="Is there a plasmid in the collection carrying the yeast HIS4 gene that I could use as a starting backbone?",
        targets=(
            "genbank:U14116.1",
            "genbank:U14117.1",
            "genbank:U14118.1",
            "genbank:U14119.1",
            "genbank:U14120.1",
            "genbank:U14121.1",
            "genbank:U14122.1",
            "genbank:U14123.1",
            "genbank:U14124.1",
            "genbank:U14125.1",
            "genbank:U14127.1",
        ),
        rationale=(
            "The pSG925 through pSG935 series is indexed as HIS4-based cloning vectors; HIS4 is the "
            "indexed payload on each one and appears nowhere else in the corpus. Eleven targets are "
            "acceptable because the series is genuinely interchangeable for this request."
        ),
        evidence_all=("Bacterial cloning vector", "HIS4"),
        stratum="bacterial_cloning_vector",
    ),
    Candidate(
        query="I want a Renilla luciferase reporter driven by a CMV promoter for transfection into mammalian cells.",
        targets=("genbank:AF416990.1",),
        rationale=(
            "pcDNA3-Rluc is the only corpus record with Renilla luciferase as an indexed payload, "
            "and its indexed promoters include a CMV promoter."
        ),
        evidence_all=("Mammalian reporter vector", "Renilla luciferase", "CMV promoter"),
        stratum="mammalian_reporter_vector",
    ),
    Candidate(
        query="Looking for a tetracycline-responsive luciferase fusion reporter plasmid to measure induced promoter activity.",
        targets=("genbank:AF416988.1", "genbank:AF416989.1"),
        rationale=(
            "pTRE_PSKH1_Luc and pTRE_hTF_Luc are indexed as mammalian reporter vectors whose "
            "payload is a luciferase fusion protein, in the tet-responsive pTRE naming series."
        ),
        evidence_all=("Mammalian reporter vector", "pTRE", "luciferase"),
        stratum="mammalian_reporter_vector",
    ),
    Candidate(
        query="Do you have a retroviral transfer vector derived from Moloney murine leukemia virus?",
        targets=("genbank:AF010170.1",),
        rationale=(
            "pAMS is the only corpus record indexed as a lentiviral or retroviral transfer vector, "
            "and its indexed description names a hybrid amphotropic/Moloney murine leukemia virus "
            "with gag, pol and env payloads. This is the first labeled retrieval target for that "
            "profile; the 2026-05-31 expansion recorded it as a corpus gap."
        ),
        evidence_all=("Lentiviral or retroviral transfer vector", "Moloney murine leukemia virus", "gag"),
        stratum="lentiviral_or_retroviral_transfer_vector",
    ),
    Candidate(
        query="I need a GFP reporter plasmid that uses chloramphenicol rather than ampicillin for selection.",
        targets=("genbank:FJ172221.1",),
        rationale=(
            "pCmGFP has gfp as its indexed payload and cat as its only indexed selectable marker, "
            "which is the ampicillin-free selection the query asks for. The indexed profile for this "
            "record is mammalian_reporter_vector, which is wrong: it is a bacterial GFP plasmid from "
            "Neisseria gonorrhoeae. The query is written to the evidence that is actually indexed and "
            "does not repeat the misclassification."
        ),
        evidence_all=("gfp", "cat", "tac promoter"),
        stratum="mammalian_reporter_vector",
    ),
    Candidate(
        query="Which plasmid carries eGFP with ampicillin selection on a pUC-family origin?",
        targets=("genbank:GQ404376.1",),
        rationale=(
            "pPRS3a has eGFP as its indexed payload with bla as the indexed marker and a pMB1/pUC "
            "indexed origin."
        ),
        evidence_all=("eGFP", "bla", "pMB1/pUC origin"),
        stratum="mammalian_reporter_vector",
    ),
    Candidate(
        query="I want an E. coli plasmid that provides sacB counter-selection and a tac promoter.",
        targets=("genbank:OP009361.1",),
        rationale=(
            "pSGKp-Tmcr-500GFP lists sacB among its indexed payloads and a tac promoter among its "
            "indexed promoters, and its indexed organism is Escherichia coli."
        ),
        evidence_all=("sacB", "tac promoter", "Escherichia coli"),
        stratum="bacterial_expression_vector",
    ),
    Candidate(
        query="Recommend a broad-host-range cloning vector with kanamycin selection that does not rely on a pUC origin.",
        targets=("genbank:U23751.1",),
        rationale=(
            "pBBR1MCS-2 is indexed as a bacterial cloning vector with a kanamycin resistance "
            "determinant and a dense MCS, and no pUC origin is indexed for it."
        ),
        evidence_all=("Bacterial cloning vector", "pBBR1MCS-2", "kanamycin resistance determinant"),
        stratum="bacterial_cloning_vector",
    ),
    Candidate(
        query="I need a T7 expression plasmid with a histidine-tag cassette on both sides of the cloning site.",
        targets=("genbank:AF012911.1",),
        rationale=(
            "pETHIS-1 has his6-mcs-his10 as both its indexed payload and its indexed cloning site, "
            "under an indexed T7 RNA polymerase promoter."
        ),
        evidence_all=("his6-mcs-his10", "T7 RNA polymerase promoter"),
        stratum="bacterial_cloning_vector",
    ),
    Candidate(
        query="Is there a transposon-delivered luxAB bioluminescence reporter plasmid in the collection?",
        targets=("genbank:U55385.2", "genbank:U55819.2"),
        rationale=(
            "pRL1063a and pRL765 are the only corpus records with luxA and luxB among their indexed "
            "payloads, and both also index a transposase."
        ),
        evidence_all=("luxA", "luxB", "transposase"),
        stratum="bacterial_cloning_vector",
    ),
    Candidate(
        query="Looking for a cloning vector that carries both chloramphenicol and ampicillin resistance plus an f1 origin.",
        targets=("genbank:U35125.1", "genbank:U35126.1"),
        rationale=(
            "pBSL119 and pBSL121 index a chloramphenicol acetyltransferase and a beta-lactamase "
            "together with an f1 origin, which is the two-marker combination requested."
        ),
        evidence_all=(
            "Bacterial cloning vector",
            "chloramphenicol acetyltransferase",
            "beta-lactamase",
            "f1 origin",
        ),
        stratum="bacterial_cloning_vector",
    ),
    Candidate(
        query="I need a conditional-replication plasmid whose origin requires the pir gene product to be supplied by the host.",
        targets=("genbank:AY608912.1",),
        rationale=(
            "pFL129 indexes pir as a payload and the gamma origin of plasmid R6K as its replication "
            "origin, which is the host-dependent replication the query describes."
        ),
        evidence_all=("pir", "gamma origin of plasmid R6K"),
        stratum="bacterial_cloning_vector",
    ),
    Candidate(
        query="Which plasmid with a pUC19 multiple cloning site also carries kanamycin and bleomycin resistance?",
        targets=("genbank:GQ149343.1", "genbank:GQ149347.1"),
        rationale=(
            "pAm05WL6211 and pAm08CQ6130 both index a kanamycin resistance protein and a bleomycin "
            "resistance protein alongside ampicillin resistance."
        ),
        evidence_all=("kanamycin resistance protein", "bleomycin resistance protein"),
        stratum="bacterial_cloning_vector",
    ),
    Candidate(
        query="Show me natural plasmids that carry a CRISPR cas gene cluster.",
        targets=(
            "genbank:CP000954.1",
            "genbank:CP001724.1",
            "genbank:CP002866.1",
            "genbank:CP046159.1",
            "genbank:CP183374.1",
            "genbank:GQ900399.1",
        ),
        rationale=(
            "Each of these records indexes CRISPR-associated proteins among its payloads on a native "
            "bacterial or archaeal plasmid. The parser labels them crispr_vector, which overstates "
            "them: they are natural plasmids carrying cas genes, not genome-editing delivery vectors. "
            "The query is deliberately a cas-locus lookup so the gold label stays true to the record."
        ),
        evidence_all=("CRISPR",),
        stratum="crispr_vector",
    ),
    Candidate(
        query="Is there a plasmid encoding an anti-CRISPR protein that inhibits Cas9?",
        targets=("genbank:CP160042.1",),
        rationale=(
            "The Enterococcus faecalis ATCC 29212 unnamed2 plasmid is the only corpus record whose "
            "indexed payloads include a Cas9 inhibitor AcrIIA9 family protein."
        ),
        evidence_all=("Cas9 inhibitor AcrIIA9",),
        stratum="crispr_vector",
    ),
]


# --------------------------------------------------------------------------
# Stratum B: records the parser left as `unknown`. This is 4354 of 4455
# records, so a gold set with no cases here does not measure the corpus the
# system actually searches.
# --------------------------------------------------------------------------

NATURAL: list[Candidate] = [
    Candidate(
        query="I am studying heavy-metal resistance. Which plasmid carries a silver resistance determinant?",
        targets=("genbank:AF067954.1",),
        rationale=(
            "pMG101 from Salmonella indexes silE, silR and silS, and is the only corpus record whose "
            "indexed document mentions silver."
        ),
        evidence_all=("silE", "silR", "silver"),
        stratum="unknown",
    ),
    Candidate(
        query="Which plasmid carries a nickel and cobalt resistance gene cluster?",
        targets=("genbank:AF322866.1",),
        rationale=(
            "pNRS148 from Hafnia alvei is the only corpus record indexing a nickel/cobalt resistance "
            "determinant, with ncrA, ncrB and ncrC as indexed markers."
        ),
        evidence_all=("ncrA", "nickel/cobalt", "Hafnia alvei"),
        stratum="unknown",
    ),
    Candidate(
        query="Find a Klebsiella plasmid with a complete arsenic resistance operon.",
        targets=("genbank:AF168737.1",),
        rationale=(
            "pMH12 from Klebsiella oxytoca indexes arsA, arsB, arsC, arsD and arsR as payloads with "
            "an arsenical resistance operon as its indexed marker."
        ),
        evidence_all=("arsA", "arsR", "Klebsiella oxytoca"),
        stratum="unknown",
    ),
    Candidate(
        query="I need a Lactococcus lactis plasmid that confers cadmium resistance.",
        targets=("genbank:AF243383.1",),
        rationale=(
            "pAH82 indexes cadA and cadC as selectable markers and Lactococcus lactis subsp. lactis "
            "as its organism."
        ),
        evidence_all=("cadA", "cadC", "Lactococcus lactis"),
        stratum="unknown",
    ),
    Candidate(
        query="Which plasmid carries the CTX-M-17 extended-spectrum beta-lactamase?",
        targets=("genbank:AY033516.1",),
        rationale=(
            "pIP843 from Klebsiella pneumoniae is the only corpus record indexing blaCTX-M-17 as a "
            "selectable marker."
        ),
        evidence_all=("blaCTX-M-17", "Klebsiella pneumoniae"),
        stratum="unknown",
    ),
    Candidate(
        query="Looking for a Lactobacillus plasmid carrying an ermT erythromycin resistance methylase.",
        targets=("genbank:AF310974.1",),
        rationale="p121BS from Lactobacillus sp. PC121B indexes methylase ermT as its selectable marker.",
        evidence_all=("ermT", "Lactobacillus"),
        stratum="unknown",
    ),
    Candidate(
        query="Which Lactiplantibacillus plantarum plasmid carries tetM?",
        targets=("genbank:AF440277.1",),
        rationale=(
            "pMD5057 indexes tetM as its selectable marker with Lactiplantibacillus plantarum as its "
            "indexed organism."
        ),
        evidence_all=("tetM", "Lactiplantibacillus plantarum"),
        stratum="unknown",
    ),
    Candidate(
        query="Is there a Staphylococcus epidermidis plasmid with an ethidium bromide resistance determinant?",
        targets=("genbank:AY092027.1",),
        rationale=(
            "pSepCH indexes an ethidium bromide resistance determinant as its selectable marker with "
            "Staphylococcus epidermidis as its indexed organism."
        ),
        evidence_all=("ethidium bromide resistance determinant", "Staphylococcus epidermidis"),
        stratum="unknown",
    ),
    Candidate(
        query="Find the Francisella tularensis plasmid that carries a tetracycline resistance gene.",
        targets=("genbank:AF055345.1",),
        rationale=(
            "pOM1 indexes tetC as a selectable marker and Francisella tularensis as its organism, and "
            "is the only corpus record naming pOM1."
        ),
        evidence_all=("pOM1", "tetC", "Francisella tularensis"),
        stratum="unknown",
    ),
    Candidate(
        query="Which Helicobacter pylori plasmid encodes a putative microcin peptide?",
        targets=("genbank:AF275307.1",),
        rationale=(
            "pHPM8 is the only corpus record indexing a putative microcin peptide, with Helicobacter "
            "pylori as its indexed organism."
        ),
        evidence_all=("microcin", "Helicobacter pylori"),
        stratum="unknown",
    ),
    Candidate(
        query="I am looking for the Staphylococcus aureus conjugative multiresistance plasmid pSK41.",
        targets=("genbank:AF051917.1",),
        rationale=(
            "pSK41 is indexed by name with a tra conjugative transfer gene set and Staphylococcus "
            "aureus as its organism. This is an exact named lookup, which is the most common real "
            "retrieval pattern for natural plasmids."
        ),
        evidence_all=("pSK41", "traA", "Staphylococcus aureus"),
        stratum="unknown",
    ),
    Candidate(
        query="Which Enterococcus faecalis plasmid carries tetL?",
        targets=("genbank:AF503772.1",),
        rationale="pAMalpha1 indexes tetL as its selectable marker with Enterococcus faecalis as its organism.",
        evidence_all=("pAMalpha1", "tetL", "Enterococcus faecalis"),
        stratum="unknown",
    ),
    Candidate(
        query="Find an Enterococcus faecium plasmid with an Axe-Txe toxin-antitoxin stability system.",
        targets=("genbank:AF507977.1",),
        rationale=(
            "pRUM indexes both Axe and Txe among its payloads with Enterococcus faecium as its "
            "indexed organism."
        ),
        evidence_all=("Axe", "Txe", "Enterococcus faecium"),
        stratum="unknown",
    ),
    Candidate(
        query="Which Staphylococcus aureus plasmid carries both a cadmium resistance operon and a beta-lactamase?",
        targets=("genbank:AY373761.1",),
        rationale=(
            "pUB101 indexes cadD and cadX together with blaZ, blaI and blaR1, and indexes a cadDX "
            "operon as its promoter."
        ),
        evidence_all=("cadD", "blaZ", "Staphylococcus aureus"),
        stratum="unknown",
    ),
    Candidate(
        query="Looking for a Pseudomonas aeruginosa plasmid with a class 1 integron carrying a chloramphenicol efflux gene.",
        targets=("genbank:AF313472.2",),
        rationale=(
            "RPL11 indexes intI1 as a class 1 integron integrase alongside a CmlA1 leader peptide, "
            "with Pseudomonas aeruginosa as its indexed organism."
        ),
        evidence_all=("CmlA1", "intI1", "Pseudomonas aeruginosa"),
        stratum="unknown",
    ),
    Candidate(
        query="Which Pasteurella multocida plasmid carries sulfonamide, tetracycline and chloramphenicol resistance together?",
        targets=("genbank:AY232670.1",),
        rationale=(
            "pJR1 indexes sulII, tetG and catB2 as its three selectable markers, with Pasteurella "
            "multocida as its indexed organism."
        ),
        evidence_all=("sulII", "tetG", "catB2"),
        stratum="unknown",
    ),
]


CLARIFICATION: list[Candidate] = [
    Candidate(
        query="Can you recommend a plasmid for my experiment?",
        targets=(),
        rationale=(
            "The request names no host, no application and no selection requirement. Retrieval should "
            "ask what the construct is for rather than return a ranked list."
        ),
        expected_clarification=True,
        stratum="clarification",
    ),
]


ALL_CANDIDATES: list[Candidate] = ENGINEERED + NATURAL + CLARIFICATION


def _documents(ids: list[str]) -> dict[str, str]:
    """Read the indexed documents for `ids` straight from the corpus."""
    import psycopg

    url = os.environ.get("VECTOR_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("VECTOR_DB_URL or DATABASE_URL must be set to verify candidates")
    with psycopg.connect(url) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT plasmid_id, composed_document FROM plasmid_embeddings WHERE plasmid_id = ANY(%s)",
            (ids,),
        )
        return {row[0]: row[1] for row in cursor.fetchall()}


def verify() -> list[str]:
    """Check every candidate against the corpus. Returns the failures."""
    target_ids = sorted({target for candidate in ALL_CANDIDATES for target in candidate.targets})
    documents = _documents(target_ids)
    failures: list[str] = []

    for candidate in ALL_CANDIDATES:
        if candidate.expected_clarification:
            if candidate.targets:
                failures.append(f"{candidate.query!r}: clarification case must not claim a target")
            continue
        if not candidate.targets:
            failures.append(f"{candidate.query!r}: retrieval case has no target")
            continue
        for target in candidate.targets:
            document = documents.get(target)
            if document is None:
                failures.append(f"{candidate.query!r}: target {target} is not embedded in the corpus")
                continue
            folded = document.casefold()
            for needle in candidate.evidence_all:
                if needle.casefold() not in folded:
                    failures.append(
                        f"{candidate.query!r}: {target} does not support {needle!r}"
                    )
        if candidate.evidence_any:
            joined = " ".join(documents.get(target, "") for target in candidate.targets).casefold()
            for needle in candidate.evidence_any:
                if needle.casefold() not in joined:
                    failures.append(
                        f"{candidate.query!r}: no target supports {needle!r}"
                    )
    return failures


def records() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for candidate in ALL_CANDIDATES:
        row: dict[str, object] = {
            "query": candidate.query,
            "acceptable_target_ids": list(candidate.targets),
            "rationale": candidate.rationale,
            "source": candidate.source(),
        }
        if candidate.expected_clarification:
            row["expected_clarification"] = True
        rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "emit"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    failures = verify()
    if failures:
        print(f"{len(failures)} candidate verification failure(s):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"all {len(ALL_CANDIDATES)} candidates verified against the corpus")

    if args.command == "emit":
        # Written beside the gold file rather than over it: the gold file also
        # holds the twenty-one pre-WP-21 cases, which this script does not own.
        # Separators match GOLD_PATH exactly so the emitted lines can be diffed
        # against the merged ones.
        destination = args.output or GOLD_PATH.with_name("retrieval_gold_wp21.jsonl")
        lines = [json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in records()]
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} records to {destination}")
        print(f"compare against the merged set in {GOLD_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
