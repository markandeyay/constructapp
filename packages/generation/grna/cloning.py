"""Cloning-ready oligos for the chosen scaffold and vector (section 8.7).

Section 8.7 requires "cloning-ready oligos for the chosen scaffold and vector,
including any required 5' overhangs for the cloning strategy". Every overhang
and every scaffold sequence used here comes from
`packages.validation.grna.vectors`, which records the repository accession of
each vector and the reference implementation the sequence was read from.
Nothing in this module invents or recalls a sequence; it only concatenates
published parts around the user's own spacer, which is also why the resulting
provenance is complete (section 11.1).

Two published protocol rules are applied and reported rather than applied
silently:

* Efficient transcription from the human U6 promoter needs the transcript to
  start with G. When the spacer does not, the published protocols prepend a G
  to the sense oligo and append a matching C to the antisense oligo, giving a
  guide one nucleotide longer than the spacer. Recorded in the vector record as
  `requires_five_prime_g`.
* T7 transcription initiates most efficiently when the first transcribed
  nucleotide is G, so the in-vitro-transcription template oligo carries a
  single prepended G when the spacer does not begin with one.

Both additions are reported in the oligo's `notes` so nobody orders a sequence
whose extra base is invisible.
"""

from __future__ import annotations

from packages.core.schemas.grna import CloningOligo, CloningPlan, GuideRNARequest
from packages.core.sequence import clean_sequence, reverse_complement
from packages.validation.grna.vectors import IVT_TEMPLATES, get_vector

U6_G_NOTE = (
    "Efficient transcription from the human U6 promoter needs the transcript to begin with G, and "
    "this spacer does not, so a G is prepended here and a matching C is appended to the antisense "
    "oligo. The expressed guide is therefore one nucleotide longer than the spacer."
)

T7_G_NOTE = (
    "T7 transcription initiates most efficiently when the first transcribed nucleotide is G, and "
    "this spacer does not begin with one, so a single G is prepended to the template oligo."
)


def _oligo(
    name: str,
    overhang: str,
    core: str,
    tail: str,
    role: str,
    notes: list[str],
) -> CloningOligo:
    sequence = f"{overhang}{core}{tail}"
    return CloningOligo(
        name=name,
        sequence=sequence,
        role=role,
        five_prime_overhang=overhang,
        three_prime_addition=tail,
        length_nt=len(sequence),
        notes=notes,
    )


def annealed_oligo_pair(
    request: GuideRNARequest,
    spacer: str,
    guide_name: str,
) -> CloningPlan:
    """The sense and antisense oligos that anneal into the digested vector.

    This is the primary cloning route for a guide expressed from a plasmid. The
    pair is written 5' to 3', each with the vector's published 5' overhang.
    """
    vector = get_vector(request.cloning_vector, request.nuclease)
    sequence = clean_sequence(spacer)
    notes: list[str] = []
    sense_core = sequence
    antisense_tail = vector.suffix
    antisense_core = reverse_complement(sequence)

    if vector.requires_five_prime_g and not sequence.startswith("G"):
        sense_core = "G" + sequence
        antisense_core = reverse_complement(sequence) + "C"
        notes.append(U6_G_NOTE)

    oligos = [
        _oligo(
            name=f"{guide_name}_sense",
            overhang=vector.forward_overhang,
            core=sense_core,
            tail=vector.suffix,
            role="sense oligo, anneal with the antisense oligo and ligate into the digested vector",
            notes=list(notes),
        ),
        _oligo(
            name=f"{guide_name}_antisense",
            overhang=vector.reverse_overhang,
            core=antisense_core,
            tail=antisense_tail,
            role="antisense oligo, anneal with the sense oligo",
            notes=list(notes),
        ),
    ]
    plan_notes = [
        f"Digest {vector.name} ({vector.accession}) with "
        + (vector.digest_enzyme or "the enzyme named in its own protocol")
        + ", then anneal and ligate the oligo pair above.",
        f"Overhang source: {vector.source}.",
    ]
    if vector.protocol_reference:
        plan_notes.append(f"Vector cloning protocol: {vector.protocol_reference}")
    return CloningPlan(
        vector_id=vector.vector_id,
        vector_name=f"{vector.name} ({vector.accession})",
        vector_source=vector.source,
        digest_enzyme=vector.digest_enzyme,
        protocol_reference=vector.protocol_reference,
        oligos=oligos,
        notes=plan_notes,
    )


def ivt_oligo_pair(request: GuideRNARequest, spacer: str, guide_name: str) -> CloningPlan:
    """Overlapping oligos for making the guide by T7 in-vitro transcription.

    No Cas12a template exists in the reference implementation, because both
    oligos depend on the nuclease's own scaffold. A Cas12a request therefore
    returns a plan with no oligos and the reason, rather than a Cas9 scaffold
    under a Cas12a label.
    """
    template = IVT_TEMPLATES.get(request.nuclease)
    sequence = clean_sequence(spacer)
    if template is None:
        return CloningPlan(
            vector_id="t7_in_vitro",
            vector_name="T7 in-vitro transcription from overlapping oligos",
            vector_source="no published template available in this build",
            digest_enzyme=None,
            oligos=[],
            notes=[
                f"No in-vitro transcription oligo pair is produced for {request.nuclease}. Both "
                "oligos depend on the scaffold, the scaffold is specific to the nuclease, and the "
                "reference implementation this build reads its templates from states that its T7 "
                "template information applies only to SpCas9 and SaCas9. Supplying a Cas9 "
                "scaffold here would be wrong. Use a published vector route instead, or supply "
                f"the {request.nuclease} scaffold explicitly.",
            ],
        )
    notes: list[str] = []
    core = sequence
    if not sequence.startswith("G"):
        core = "G" + sequence
        notes.append(T7_G_NOTE)
    oligos = [
        _oligo(
            name=f"{guide_name}_t7_template",
            overhang=template.target_prefix,
            core=core,
            tail=template.target_suffix,
            role="guide-specific template oligo, carries the T7 promoter and the scaffold start",
            notes=list(notes),
        ),
        CloningOligo(
            name=f"{request.nuclease}_t7_scaffold_common",
            sequence=template.constant_oligo,
            role="constant scaffold oligo, the same for every guide with this nuclease",
            length_nt=len(template.constant_oligo),
            notes=[
                "Order once and reuse. It carries no guide-specific sequence.",
            ],
        ),
    ]
    return CloningPlan(
        vector_id="t7_in_vitro",
        vector_name=f"T7 in-vitro transcription, {request.nuclease} scaffold",
        vector_source=template.source,
        digest_enzyme=None,
        protocol_reference=None,
        oligos=oligos,
        notes=[
            "Anneal and extend the two oligos to make the transcription template, then transcribe "
            "with T7 RNA polymerase.",
            f"Scaffold source: {template.source}.",
            "An in-vitro-transcribed guide is outside the validity domain of the published "
            "on-target model used here, so that score is withheld for this expression system.",
        ],
    )


def cloning_plan(request: GuideRNARequest, spacer: str, guide_name: str) -> CloningPlan:
    """Pick the route the request's expression system implies."""
    if request.expression_system == "t7_in_vitro":
        return ivt_oligo_pair(request, spacer, guide_name)
    return annealed_oligo_pair(request, spacer, guide_name)
