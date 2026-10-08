"""Cloning vectors and their guide oligo overhangs (section 8.7).

Section 8.7 requires "cloning-ready oligos for the chosen scaffold and vector,
including any required 5' overhangs for the cloning strategy". A 5' overhang is
a real sequence belonging to a real published vector, so section 3.3 constraint
1 applies to it: nothing here was invented or recalled.

Every overhang below was read 2026-10-07 from the reference implementation of
the CRISPOR guide selection tool, file `crispor.py`, tables `addGenePlasmids`,
`addGenePlasmidsAureus` and `addGenePlasmidInfo` and function
`makeHelperPrimers`, at
https://raw.githubusercontent.com/maximilianh/crisporWebsite/master/crispor.py
CRISPOR is published as Genome Biol 2016;17(1):148,
doi:10.1186/s13059-016-1012-2, PMID 27380939. Each record also carries the
repository accession number of the vector and, where the reference
implementation supplies one, the link to that vector's own cloning protocol,
which is the primary source for the overhang.

The scaffold sequences used for in-vitro transcription come from the same
reference implementation, which cites Cell 2015;163(3):759-771 and
Cell 2015;162(4) for the SaCas9 scaffold context. They are reproduced verbatim
and are not modified here.

Nothing in this module is a threshold, so nothing in it is tunable; it is a
registry of published sequences. A vector that is not listed is a `KeyError`
rather than a guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

CRISPOR_SOURCE = (
    "CRISPOR guide RNA selection tool, Genome Biol 2016;17(1):148, "
    "doi:10.1186/s13059-016-1012-2, PMID 27380939; overhangs read 2026-10-07 from its source "
    "file crispor.py (addGenePlasmidInfo, makeHelperPrimers)"
)


@dataclass(frozen=True)
class CloningVector:
    """One guide expression vector and the oligo overhangs it needs.

    * `forward_overhang` is prepended to the spacer on the sense oligo.
    * `reverse_overhang` is prepended to the reverse complement of the spacer on
      the antisense oligo.
    * `suffix` is appended to both oligos; it is non-empty only for vectors
      whose published protocol calls for it.
    * `requires_five_prime_g` records that efficient transcription from the
      human U6 promoter needs the transcript to begin with G. When the spacer
      does not, the published protocols add a G to the sense oligo and a
      matching C to the antisense oligo, producing a guide one nucleotide
      longer. The reference implementation applies this to the Cas9 vectors and
      not to the Cas12a vectors, and that is reproduced here rather than
      generalised.
    """

    vector_id: str
    name: str
    accession: str
    nucleases: tuple[str, ...]
    digest_enzyme: str | None
    forward_overhang: str
    reverse_overhang: str
    suffix: str = ""
    requires_five_prime_g: bool = True
    protocol_reference: str | None = None
    source: str = CRISPOR_SOURCE


CLONING_VECTORS: Mapping[str, CloningVector] = {
    vector.vector_id: vector
    for vector in (
        CloningVector(
            vector_id="px330",
            name="pX330-U6-Chimeric_BB-CBh-hSpCas9 and derivatives",
            accession="Addgene 42230",
            nucleases=("SpCas9",),
            digest_enzyme="BbsI",
            forward_overhang="CACC",
            reverse_overhang="AAAC",
            protocol_reference=(
                "https://www.addgene.org/static/data/plasmids/52/52961/"
                "52961-attachment_B3xTwla0bkYD.pdf"
            ),
        ),
        CloningVector(
            vector_id="lenticrispr_v2",
            name="lentiCRISPR v2",
            accession="Addgene 52961",
            nucleases=("SpCas9",),
            digest_enzyme="BsmBI",
            forward_overhang="CACC",
            reverse_overhang="AAAC",
            protocol_reference=(
                "https://www.addgene.org/static/data/plasmids/52/52961/"
                "52961-attachment_B3xTwla0bkYD.pdf"
            ),
        ),
        CloningVector(
            vector_id="lentiguide_puro",
            name="lentiGuide-Puro",
            accession="Addgene 52963",
            nucleases=("SpCas9",),
            digest_enzyme="BsmBI",
            forward_overhang="CACC",
            reverse_overhang="AAAC",
            protocol_reference=(
                "https://www.addgene.org/static/data/plasmids/52/52963/"
                "52963-attachment_IPB7ZL_hJcbm.pdf"
            ),
        ),
        CloningVector(
            vector_id="mlm3636",
            name="MLM3636",
            accession="Addgene 43860",
            nucleases=("SpCas9",),
            digest_enzyme="BsmBI",
            forward_overhang="ACACC",
            reverse_overhang="AAAAC",
            suffix="G",
            protocol_reference=(
                "https://www.addgene.org/static/data/plasmids/43/43860/"
                "43860-attachment_T35tt6ebKxov.pdf"
            ),
        ),
        CloningVector(
            vector_id="px601",
            name="pX601-AAV-CMV::NLS-SaCas9-NLS-3xHA-bGHpA;U6::BsaI-sgRNA",
            accession="Addgene 61591",
            nucleases=("SaCas9",),
            digest_enzyme="BsaI",
            forward_overhang="CACC",
            reverse_overhang="AAAC",
            protocol_reference=(
                "https://www.addgene.org/static/data/plasmids/61/61591/"
                "61591-attachment_it03kn5x5O6E.pdf"
            ),
        ),
        CloningVector(
            vector_id="vvt1",
            name="VVT1",
            accession="Addgene 65779",
            nucleases=("SaCas9",),
            digest_enzyme="BsmBI",
            forward_overhang="CACC",
            reverse_overhang="AAAC",
            protocol_reference=(
                "https://www.addgene.org/static/data/plasmids/65/65779/"
                "65779-attachment_G8oNyvV6pA78.pdf"
            ),
        ),
        CloningVector(
            vector_id="pu6_lb_crrna",
            name="pU6-Lb-crRNA",
            accession="Addgene 78957",
            nucleases=("LbCas12a",),
            digest_enzyme=None,
            forward_overhang="AGAT",
            reverse_overhang="AAAA",
            requires_five_prime_g=False,
            protocol_reference="https://www.addgene.org/78957/",
        ),
        CloningVector(
            vector_id="pu6_as_crrna",
            name="pU6-As-crRNA",
            accession="Addgene 78956",
            nucleases=("AsCas12a",),
            digest_enzyme=None,
            forward_overhang="AGAT",
            reverse_overhang="AAAA",
            requires_five_prime_g=False,
            protocol_reference="https://www.addgene.org/78956/",
        ),
    )
}

DEFAULT_VECTOR_BY_NUCLEASE: Mapping[str, str] = {
    "SpCas9": "px330",
    "SaCas9": "px601",
    "LbCas12a": "pu6_lb_crrna",
    "AsCas12a": "pu6_as_crrna",
}
"""Which vector is chosen when the request names none. Each is a vector the
reference implementation lists first for that nuclease, so the default is not a
Construct preference."""


def get_vector(vector_id: str | None, nuclease: str) -> CloningVector:
    """Resolve the vector for a request, failing loudly on an unknown identifier."""
    if vector_id is None:
        vector_id = DEFAULT_VECTOR_BY_NUCLEASE.get(nuclease)
        if vector_id is None:
            raise KeyError(f"no default cloning vector is registered for {nuclease!r}")
    try:
        return CLONING_VECTORS[vector_id]
    except KeyError:
        known = ", ".join(sorted(CLONING_VECTORS))
        raise KeyError(f"unknown cloning vector {vector_id!r} (registered: {known})") from None


# ---------------------------------------------------------------------------
# In-vitro transcription templates
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IvtTemplate:
    """Overlapping oligo pair for making a guide by T7 in-vitro transcription.

    `target_prefix` carries the T7 promoter and `target_suffix` the start of the
    scaffold; `constant_oligo` is the scaffold oligo shared by every guide for
    that nuclease. Both sequences are reproduced verbatim from the reference
    implementation named in the module docstring.

    The reference implementation also records the standard recommendation that
    T7 transcription initiates most efficiently when the first transcribed
    nucleotides are G, and prepends a single G when the spacer does not already
    begin with one. That behaviour is reproduced, and the added base is reported
    as an explicit note on the oligo rather than hidden.
    """

    nuclease: str
    target_prefix: str
    target_suffix: str
    constant_oligo: str
    source: str = CRISPOR_SOURCE


IVT_TEMPLATES: Mapping[str, IvtTemplate] = {
    "SpCas9": IvtTemplate(
        nuclease="SpCas9",
        target_prefix="GAAATTAATACGACTCACTATA",
        target_suffix="GTTTTAGAGCTAGAAATAGCAAG",
        constant_oligo=(
            "AAAAGCACCGACTCGGTGCCACTTTTTCAAGTTGATAACGGACTAGCCTTATTTTAACTTGCTATTTCTAGCTCTAAAAC"
        ),
    ),
    "SaCas9": IvtTemplate(
        nuclease="SaCas9",
        target_prefix="GAAATTAATACGACTCACTATA",
        target_suffix="GTTTTAGTACTCTGGAAACAGAA",
        constant_oligo=(
            "GTTTTAGTACTCTGGAAACAGAATCTACTAAAACAAGGCAAAATGCCGTGTTTATCTCGTCAACTTGTTGGCGAGATTTTTTT"
        ),
    ),
}
"""No Cas12a entry exists on purpose. The reference implementation warns that
its T7 primer information applies only to SpCas9 and SaCas9, because both
oligos depend on the scaffold and the scaffold is specific to the nuclease. A
Cas12a in-vitro transcription request therefore gets no oligos and an explicit
reason, rather than a Cas9 scaffold with the wrong name on it."""
