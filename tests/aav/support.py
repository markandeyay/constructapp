"""Shared fixtures for the AAV tests.

The coding sequences here are deterministic synthetic test payloads. They
stand in for the transgene, which is user input in the section 6.3 sense, and
they carry no biological claim: they are not registry parts, they are never
exported as a curated part, and nothing in the validator treats them as a
reference. Everything in the cassette that *is* a biological claim comes from
`data/parts`, which carries real GenBank sourced sequence with provenance.

`synthetic_cds` is written rather than imported from `random` so the sequences
are byte identical on every Python version and every platform, which the
determinism requirement of section 3.3 constraint 3 makes a property of the
tests too.
"""

from __future__ import annotations

from packages.core.part_registry import get_part
from packages.core.schemas.aav import AAVDesign, CassetteElement, CassetteElementRole
from packages.core.sequence import direct_repeats, homopolymer_runs

STOP_CODONS = ("TAA", "TAG", "TGA")

# A linear congruential generator, so the codon walk is reproducible without
# depending on the standard library's generator implementation. The multiplier
# and increment are the widely published ANSI C values; they carry no
# biological meaning and are a test fixture detail only.
_LCG_MULTIPLIER = 1_103_515_245
_LCG_INCREMENT = 12_345
_LCG_MODULUS = 2**31


def synthetic_cds(
    codon_count: int,
    *,
    seed: int = 20_260_107,
    max_homopolymer: int = 8,
    max_repeat: int = 20,
) -> str:
    """A clean open reading frame of `codon_count` codons.

    Guarantees, so that a test can isolate the check it is about:

    * starts with ATG and the base at +4 is G, which is a strong Kozak context
      once a purine sits at -3;
    * length is divisible by 3;
    * a single in-frame stop, at the 3' end;
    * no homopolymer run longer than `max_homopolymer`;
    * no direct repeat longer than `max_repeat`.

    The last two matter because `aav.internal_repeats` and
    `aav.homopolymer_runs` would otherwise fire on the payload rather than on
    whatever the test is actually exercising.
    """
    if codon_count < 3:
        raise ValueError("codon_count must be at least 3 (ATG, one coding codon, stop)")
    pool = [
        first + second + third
        for first in "ACGT"
        for second in "ACGT"
        for third in "ACGT"
        if first + second + third not in STOP_CODONS
    ]
    codons = ["ATG", "GCT"]
    state = seed
    attempts = 0
    while len(codons) < codon_count - 1:
        attempts += 1
        if attempts > 200 * codon_count:
            raise RuntimeError("could not build a clean coding sequence; relax the constraints")
        state = (_LCG_MULTIPLIER * state + _LCG_INCREMENT) % _LCG_MODULUS
        candidate = pool[state % len(pool)]
        trial = "".join(codons[-12:]) + candidate
        if homopolymer_runs(trial, min_length=max_homopolymer + 1):
            continue
        window = "".join(codons[-max(40, max_repeat * 2) :]) + candidate
        if direct_repeats(window, min_length=max_repeat + 1):
            continue
        codons.append(candidate)
    codons.append("TAA")
    sequence = "".join(codons)
    assert len(sequence) == codon_count * 3
    return sequence


def cds_of_length(length_bp: int, **kwargs: object) -> str:
    """A clean coding sequence of exactly `length_bp` bases, which must be a multiple of 3."""
    if length_bp % 3:
        raise ValueError("length_bp must be divisible by 3")
    return synthetic_cds(length_bp // 3, **kwargs)  # type: ignore[arg-type]


def part_element(role: CassetteElementRole, part_id: str) -> CassetteElement:
    """A cassette element built from a registry part."""
    part = get_part(part_id)
    return CassetteElement(role=role, name=part.name, sequence=part.sequence, part_id=part.id)


def cds_element(sequence: str, name: str = "test transgene coding sequence") -> CassetteElement:
    return CassetteElement(
        role=CassetteElementRole.CDS,
        name=name,
        sequence=sequence,
        part_id=None,
        source="user_input:transgene_sequence",
    )


def build_design(
    *,
    cds: str | None = None,
    promoter: str | None = "promoter.mecp2_mini",
    polya: str | None = "polya.bgh",
    itr_5: str | None = "itr.aav2_itr_left",
    itr_3: str | None = "itr.aav2_itr_right",
    wpre: str | None = None,
    enhancer: str | None = None,
    intron: str | None = None,
    elements: list[CassetteElement] | None = None,
    target_tissue: str = "cns_neuron",
    **kwargs: object,
) -> AAVDesign:
    """A cassette in the section 6.2 functional order, with each slot optional.

    The default is a clean Tier A design: MeCP2 mini promoter (its last three
    bases end A, so position -3 of the Kozak context is a purine), a clean
    coding sequence long enough to clear the 2,000 bp minimum genome size, and
    the bGH polyA. Pass `elements` to supply an arbitrary element list instead,
    which is how the order and duplicate cases are built.
    """
    if elements is None:
        sequence = cds if cds is not None else cds_of_length(1_500)
        elements = []
        if itr_5:
            elements.append(part_element(CassetteElementRole.ITR_5, itr_5))
        if enhancer:
            elements.append(part_element(CassetteElementRole.ENHANCER, enhancer))
        if promoter:
            elements.append(part_element(CassetteElementRole.PROMOTER, promoter))
        if intron:
            elements.append(part_element(CassetteElementRole.INTRON, intron))
        elements.append(cds_element(sequence))
        if wpre:
            elements.append(part_element(CassetteElementRole.WPRE, wpre))
        if polya:
            elements.append(part_element(CassetteElementRole.POLYA, polya))
        if itr_3:
            elements.append(part_element(CassetteElementRole.ITR_3, itr_3))
    payload: dict[str, object] = {
        "transgene_name": "test transgene",
        "target_tissue": target_tissue,
        "elements": elements,
        "provenance": ["user_input:transgene_sequence"]
        + [element.attribution for element in elements if element.part_id],
    }
    payload.update(kwargs)
    return AAVDesign.model_validate(payload)


def severities(report: object) -> dict[str, str]:
    """`{check_id: severity value}` for a report, for compact assertions."""
    return {check.check_id: check.severity.value for check in report.checks}  # type: ignore[attr-defined]


def check_of(report: object, check_id: str) -> object:
    return next(check for check in report.checks if check.check_id == check_id)  # type: ignore[attr-defined]
