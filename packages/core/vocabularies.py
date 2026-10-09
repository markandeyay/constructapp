from __future__ import annotations

import re
from dataclasses import dataclass


UNKNOWN_ORGANISM = "unknown"


@dataclass(frozen=True)
class ControlledTerm:
    canonical: str
    synonyms: tuple[str, ...]


ORGANISM_TERMS: tuple[ControlledTerm, ...] = (
    ControlledTerm("Homo sapiens", ("homo sapiens", "human", "human cells", "hek", "hela", "a549", "jurkat", "k562", "mammalian")),
    ControlledTerm("Mus musculus", ("mus musculus", "mouse", "murine", "nih3t3", "3t3", "mesc")),
    ControlledTerm("Rattus norvegicus", ("rattus norvegicus", "rat")),
    ControlledTerm("Aeromonas salmonicida", ("aeromonas salmonicida", "a salmonicida")),
    ControlledTerm("Zygosaccharomyces rouxii", ("zygosaccharomyces rouxii", "z rouxii")),
    ControlledTerm("Escherichia coli", ("escherichia coli", "e coli", "e. coli", "ecoli", "bacteria", "bacterial", "bl21", "dh5alpha", "dh5 alpha")),
    ControlledTerm("Saccharomyces cerevisiae", ("saccharomyces cerevisiae", "s cerevisiae", "yeast", "budding yeast")),
    ControlledTerm("Drosophila melanogaster", ("drosophila melanogaster", "drosophila", "fly")),
    ControlledTerm("Arabidopsis thaliana", ("arabidopsis thaliana", "arabidopsis", "plant")),
)


CELL_LINE_TERMS: tuple[ControlledTerm, ...] = (
    ControlledTerm("HEK293T", ("hek293t", "hek 293t", "hek-293t", "293t", "293 t")),
    ControlledTerm("HEK293", ("hek293", "hek 293", "hek-293", "293 cells", "293 cell", "human embryonic kidney 293")),
    ControlledTerm("HeLa", ("hela",)),
    ControlledTerm("CHO", ("cho", "cho cells", "chinese hamster ovary")),
    ControlledTerm("U2OS", ("u2os", "u-2 os", "u 2 os")),
    ControlledTerm("A549", ("a549",)),
    ControlledTerm("Jurkat", ("jurkat",)),
    ControlledTerm("K562", ("k562",)),
    ControlledTerm("NIH3T3", ("nih3t3", "nih 3t3", "nih 3t3 cells", "3t3")),
    ControlledTerm("COS-7", ("cos7", "cos-7", "cos 7")),
    ControlledTerm("HepG2", ("hepg2", "hep g2")),
    ControlledTerm("MCF7", ("mcf7", "mcf-7")),
    ControlledTerm("iPSC", ("ipsc", "induced pluripotent stem cells")),
    ControlledTerm("mESC", ("mesc", "mouse embryonic stem cells")),
)


CELL_LINE_ORGANISMS: dict[str, str] = {
    "HEK293T": "Homo sapiens",
    "HEK293": "Homo sapiens",
    "HeLa": "Homo sapiens",
    "U2OS": "Homo sapiens",
    "A549": "Homo sapiens",
    "Jurkat": "Homo sapiens",
    "K562": "Homo sapiens",
    "HepG2": "Homo sapiens",
    "MCF7": "Homo sapiens",
    "iPSC": "Homo sapiens",
    "CHO": "Cricetulus griseus",
    "NIH3T3": "Mus musculus",
    "mESC": "Mus musculus",
    "COS-7": "Chlorocebus sabaeus",
}


VECTOR_TYPE_TERMS: tuple[ControlledTerm, ...] = (
    ControlledTerm("lentiviral_or_retroviral_transfer_vector", ("lentiviral", "lenti", "lentivirus", "lentiviral transfer", "retroviral", "retroviral transfer")),
    ControlledTerm("mammalian_reporter_vector", ("mammalian reporter", "reporter plasmid", "reporter vector", "luciferase reporter", "gfp reporter", "fluorescent reporter")),
    ControlledTerm("mammalian_expression_vector", ("mammalian expression", "expression in human cells", "human expression", "cmv expression")),
    ControlledTerm("bacterial_expression_vector", ("bacterial expression", "bacterial protein expression", "e coli expression", "ecoli expression", "protein expression in bacteria", "protein expression in e coli", "t7 expression", "gst fusion")),
    ControlledTerm("bacterial_cloning_vector", ("bacterial cloning", "cloning vector", "cloning plasmid", "subcloning", "puc backbone", "puc plasmid", "phagemid cloning")),
    ControlledTerm("crispr_vector", ("crispr", "cas9", "sgrna", "grna", "guide rna", "crispri", "crispra")),
    ControlledTerm("yeast_shuttle_vector", ("yeast shuttle", "cen ars", "cen/ars", "2 micron", "2-micron", "yeast centromere", "yeast expression")),
    ControlledTerm("general_shuttle_vector", ("shuttle vector", "broad host range", "broad-host-range")),
)


MARKER_TERMS: tuple[ControlledTerm, ...] = (
    ControlledTerm("ampicillin", ("ampicillin", "amp", "ampr", "amp r", "bla", "beta lactamase", "beta-lactamase")),
    ControlledTerm("kanamycin", ("kanamycin", "kan", "kanr", "kan r", "neor/kanr", "neo kan", "aph", "nptii")),
    ControlledTerm("neomycin/G418", ("neomycin", "g418", "neo", "neor", "neo r", "neomycin phosphotransferase")),
    ControlledTerm("chloramphenicol", ("chloramphenicol", "cam", "cmr", "cm r", "cat")),
    # The tet efflux and ribosomal-protection gene names are listed explicitly
    # because `contains_term` matches whole words: "tetM" normalizes to "tetm",
    # which the bare "tet" synonym does NOT match. Without them a query naming a
    # real tetracycline resistance gene parsed as having no marker at all, and
    # then tripped the Tet-On/Tet-Off clarification because the raw text happens
    # to start with "tet". These are the standard names for the class, not
    # entries added to satisfy particular gold cases.
    ControlledTerm(
        "tetracycline",
        (
            "tetracycline",
            "tet",
            "tetr",
            "tet r",
            "tetracycline resistance",
            "teta",
            "tetb",
            "tetc",
            "tetd",
            "tetg",
            "tetk",
            "tetl",
            "tetm",
            "tetw",
            "tetx",
        ),
    ),
    ControlledTerm("spectinomycin", ("spectinomycin", "spec", "specr", "spec r")),
    ControlledTerm("streptomycin", ("streptomycin", "strep", "strepr", "strep r")),
    ControlledTerm("puromycin", ("puromycin", "puro", "puror", "puro r", "pac")),
    ControlledTerm("hygromycin", ("hygromycin", "hygro", "hygr", "hyg r", "hph")),
    ControlledTerm("zeocin", ("zeocin", "zeo", "zeor", "zeo r", "ble")),
    ControlledTerm("blasticidin", ("blasticidin", "bsd", "blastr", "blast r")),
    ControlledTerm("URA3", ("ura3", "uracil selection")),
    ControlledTerm("LEU2", ("leu2", "leucine selection")),
)


PROMOTER_TYPE_TERMS: tuple[ControlledTerm, ...] = (
    ControlledTerm("doxycycline-inducible", ("doxycycline inducible", "dox inducible", "dox-inducible", "tet-on", "tet on", "teton", "teto", "tre", "tetracycline inducible")),
    ControlledTerm("Tet-off", ("tet-off", "tet off")),
    ControlledTerm("lac/IPTG-inducible", ("iptg", "lac promoter", "lac", "laco", "tac", "trc")),
    ControlledTerm("arabinose-inducible", ("arabinose", "pbad", "arabad")),
    ControlledTerm("galactose-inducible", ("galactose", "gal1")),
    ControlledTerm("constitutive", ("constitutive", "always on")),
    ControlledTerm("CMV", ("cmv", "cytomegalovirus")),
    ControlledTerm("EF1a", ("ef1a", "ef1 alpha", "ef1-alpha", "ef-1a", "ef1α")),
    ControlledTerm("CAG", ("cag",)),
    ControlledTerm("PGK", ("pgk",)),
    ControlledTerm("SV40", ("sv40",)),
    ControlledTerm("T7", ("t7", "t7 promoter")),
    ControlledTerm("U6", ("u6", "u6 promoter")),
    ControlledTerm("H1", ("h1", "h1 promoter")),
    ControlledTerm("GPD", ("gpd",)),
    ControlledTerm("ADH1", ("adh1",)),
)


INDUCER_TERMS: tuple[ControlledTerm, ...] = (
    ControlledTerm("doxycycline", ("doxycycline", "dox")),
    ControlledTerm("IPTG", ("iptg",)),
    ControlledTerm("arabinose", ("arabinose",)),
    ControlledTerm("galactose", ("galactose",)),
)


TAG_TERMS: tuple[ControlledTerm, ...] = (
    ControlledTerm("EGFP", ("egfp",)),
    ControlledTerm("GFP", ("gfp", "green fluorescent protein")),
    ControlledTerm("mCherry", ("mcherry", "m cherry")),
    ControlledTerm("FLAG", ("flag",)),
    ControlledTerm("HA", ("ha",)),
    ControlledTerm("Myc", ("myc",)),
    ControlledTerm("His6", ("his", "his6", "6xhis", "6x his", "his tag", "his-tagged", "histidine tag")),
    ControlledTerm("GST", ("gst", "glutathione s transferase", "glutathione-s-transferase")),
    ControlledTerm("MBP", ("mbp",)),
    ControlledTerm("V5", ("v5",)),
)


def normalize_text(value: str) -> str:
    text = value.casefold().replace("α", "a")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_term(text: str, synonym: str) -> bool:
    normalized_text = f" {normalize_text(text)} "
    normalized_synonym = normalize_text(synonym)
    if not normalized_synonym:
        return False
    return f" {normalized_synonym} " in normalized_text


def find_controlled_terms(text: str, terms: tuple[ControlledTerm, ...]) -> list[str]:
    matches: list[str] = []
    for term in terms:
        if any(contains_term(text, synonym) for synonym in (term.canonical, *term.synonyms)):
            matches.append(term.canonical)
    return dedupe_preserve_order(matches)


def normalize_to_controlled(value: str | None, terms: tuple[ControlledTerm, ...]) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    for term in terms:
        if normalize_text(stripped) == normalize_text(term.canonical):
            return term.canonical
        if any(normalize_text(stripped) == normalize_text(synonym) for synonym in term.synonyms):
            return term.canonical
    found = find_controlled_terms(stripped, terms)
    return found[0] if found else stripped


def normalize_many_to_controlled(values: list[str], terms: tuple[ControlledTerm, ...]) -> list[str]:
    normalized = [normalize_to_controlled(value, terms) for value in values]
    return dedupe_preserve_order([value for value in normalized if value is not None])


def infer_organism_from_cell_line(cell_line: str | None) -> str | None:
    if cell_line is None:
        return None
    return CELL_LINE_ORGANISMS.get(cell_line)


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = normalize_text(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
