"""GenBank and FASTA export for AAV cassettes (section 6.8).

Every element is a GenBank feature carrying its registry part id, so the export
is self describing and nothing in it is unattributable (section 11.1). The
record is written with linear topology: an AAV cassette is not circular, and
the existing circular export path in `packages/application/exports.py` is for
plasmids (sections 6.8 and 10.2).
"""

from __future__ import annotations

from io import StringIO

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from packages.core.schemas.aav import AAVDesign, CassetteElementRole

# GenBank feature type, and regulatory_class where the type is "regulatory",
# for each cassette role. Chosen from the INSDC feature table vocabulary that
# the source records in data/parts themselves use: the ITR parts come from
# `repeat_region` features, the promoters and polyA signals from `regulatory`
# features with those regulatory classes, and the chimeric intron from an
# `intron` feature. See data/parts/PROVENANCE.md.
#
# KOZAK maps to regulatory / ribosome_binding_site. `ribosome_binding_site` is
# the INSDC `regulatory_class` controlled vocabulary term for a region of a
# transcript involved in initiating translation, and a Kozak element is that
# region in a vertebrate transcript. The INSDC vocabulary has no `kozak` class,
# so this is the closest controlled term, not an exact one.
GENBANK_FEATURE: dict[CassetteElementRole, tuple[str, str | None]] = {
    CassetteElementRole.ITR_5: ("repeat_region", None),
    CassetteElementRole.ENHANCER: ("regulatory", "enhancer"),
    CassetteElementRole.PROMOTER: ("regulatory", "promoter"),
    CassetteElementRole.INTRON: ("intron", None),
    CassetteElementRole.KOZAK: ("regulatory", "ribosome_binding_site"),
    CassetteElementRole.CDS: ("CDS", None),
    CassetteElementRole.WPRE: ("regulatory", "enhancer"),
    CassetteElementRole.POLYA: ("regulatory", "polyA_signal_sequence"),
    CassetteElementRole.ITR_3: ("repeat_region", None),
}

ROLE_NOTE: dict[CassetteElementRole, str] = {
    CassetteElementRole.ITR_5: "inverted terminal repeat, 5' end",
    CassetteElementRole.ENHANCER: "enhancer, 5' of the promoter",
    CassetteElementRole.PROMOTER: "promoter",
    CassetteElementRole.INTRON: "intron",
    CassetteElementRole.KOZAK: "translation initiation context element, Kozak consensus GCCRCCATGG, 5' of the start codon",
    CassetteElementRole.CDS: "transgene coding sequence",
    CassetteElementRole.WPRE: "posttranscriptional regulatory element, 3' of the coding sequence",
    CassetteElementRole.POLYA: "polyadenylation signal",
    CassetteElementRole.ITR_3: "inverted terminal repeat, 3' end",
}


def _record(design: AAVDesign) -> SeqRecord:
    record = SeqRecord(
        Seq(design.cassette_sequence),
        id=design.design_id,
        name=design.design_id.replace("-", "_")[:16],
        description=(
            f"Construct AAV cassette: {design.transgene_name}, {design.serotype} ITRs, "
            f"{'self complementary' if design.self_complementary else 'single stranded'}, "
            f"{design.target_tissue} target"
        ),
    )
    record.annotations["molecule_type"] = "ds-DNA"
    record.annotations["topology"] = "linear"  # sections 6.8 and 10.2: never circular
    record.annotations["data_file_division"] = "SYN"
    record.annotations["keywords"] = [
        "CONSTRUCT_AAV_CASSETTE",
        "capability=aav",
        f"serotype={design.serotype}",
        f"self_complementary={str(design.self_complementary).lower()}",
        f"target_tissue={design.target_tissue}",
        f"total_bp={design.total_bp}",
    ]
    record.annotations["comment"] = "\n".join(
        [
            "Composed by Construct from curated registry parts. Linear cassette, 5' ITR to 3' ITR.",
            "Provenance, one entry per source:",
            *(f"  {entry}" for entry in design.provenance),
            *(["Notes:"] + [f"  {note}" for note in design.notes] if design.notes else []),
        ]
    )
    features: list[SeqFeature] = [
        SeqFeature(
            FeatureLocation(0, design.total_bp, strand=1),
            type="source",
            qualifiers={
                "organism": ["synthetic construct"],
                "mol_type": ["other DNA"],
                "note": [f"recombinant {design.serotype} cassette"],
            },
        )
    ]
    for item in design.layout():
        role = CassetteElementRole(item.role)
        feature_type, regulatory_class = GENBANK_FEATURE[role]
        qualifiers: dict[str, list[str]] = {
            "label": [item.name],
            "note": [ROLE_NOTE[role]],
            "construct_role": [role.value],
        }
        if regulatory_class is not None:
            qualifiers["regulatory_class"] = [regulatory_class]
        if item.part_id:
            qualifiers["construct_part_id"] = [item.part_id]
        else:
            element = design.elements[item.index]
            qualifiers["construct_part_id"] = ["none"]
            qualifiers["construct_source"] = [element.source or "unattributed"]
        if role is CassetteElementRole.KOZAK:
            # The citation travels with the feature: the element's notes hold
            # the rule text. Only this role gets a second note, so every other
            # feature's output is unchanged.
            element_notes = design.elements[item.index].notes
            if element_notes:
                qualifiers["note"].append(element_notes)
        if role is CassetteElementRole.CDS:
            qualifiers["codon_start"] = ["1"]
            qualifiers["transl_table"] = ["1"]
            qualifiers["gene"] = [design.transgene_name]
        features.append(
            SeqFeature(FeatureLocation(item.start, item.end, strand=1), type=feature_type, qualifiers=qualifiers)
        )
    record.features = features
    return record


def to_genbank(design: AAVDesign) -> str:
    """The cassette as a GenBank record, every element a feature, topology linear."""
    handle = StringIO()
    SeqIO.write(_record(design), handle, "genbank")
    return handle.getvalue()


def to_fasta(design: AAVDesign) -> str:
    """The cassette as FASTA, with the element order in the description line."""
    layout = design.layout()
    elements = " ".join(
        f"{CassetteElementRole(item.role).value}:{item.start_1based}-{item.end_1based}" for item in layout
    )
    record = SeqRecord(
        Seq(design.cassette_sequence),
        id=design.design_id,
        description=(
            f"Construct AAV cassette | {design.transgene_name} | {design.serotype} | "
            f"{'sc' if design.self_complementary else 'ss'} | {design.total_bp} bp | linear | {elements}"
        ),
    )
    handle = StringIO()
    SeqIO.write(record, handle, "fasta")
    return handle.getvalue()
