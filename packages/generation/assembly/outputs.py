"""The section 7.7 outputs: order table, protocol, junction map.

Source: section 7.7 of the engine capability system design.

Section 7.7 lists five outputs and this module builds four of them (the fifth,
the validation report, comes from the validator). The one with a hard
requirement attached is the protocol: "thermocycling program with the annealing
temperature derived from the computed Tm rather than assumed". The annealing
temperature here is computed from the lowest nearest-neighbor primer Tm in the
set, and `Protocol.annealing_rule` states the rule that produced it so the
number can be rechecked by hand.

Every reaction condition in the protocol is a named constant in
`packages/validation/assembly/constants.py` with its source recorded there, and
`Protocol.sources` repeats the sources in the output. The protocol says which
product's published conditions it is based on, because a protocol that does not
is not usable at a bench.
"""

from __future__ import annotations

import csv
import io
import math

from packages.core.schemas.assembly import (
    AssemblyDesign,
    AssemblyOutputs,
    JunctionMapEntry,
    OrderTableRow,
    Protocol,
    ThermocyclingStep,
)
from packages.core.schemas.capability import ValidationReport
from packages.core.sequence import gc_content, reverse_complement
from packages.core.sequence.tm import melting_temperature
from packages.validation.assembly import constants
from packages.validation.assembly.enzymes import get_enzyme
from packages.validation.assembly.settings import Settings, settings_for

ORDER_TABLE_COLUMNS: tuple[str, ...] = (
    "Primer name",
    "Sequence (5' to 3')",
    "Length (nt)",
    "Tm (C)",
    "GC (%)",
    "Notes",
)


def _tm(sequence: str, design: AssemblyDesign) -> float:
    request = design.request
    return melting_temperature(
        sequence,
        primer_conc_nm=request.primer_conc_nm,
        monovalent_salt_mm=request.monovalent_salt_mm,
        divalent_salt_mm=request.divalent_salt_mm,
        dntp_mm=request.dntp_mm,
    )


def order_table(design: AssemblyDesign) -> list[OrderTableRow]:
    """The section 7.7 order table: name, sequence 5' to 3', length, Tm, GC%, notes.

    Two numbers could reasonably go in the Tm column and the choice matters, so
    it is stated here and in the notes column of every tailed primer: the Tm
    reported is that of the template-binding region, because that is what the
    annealing temperature has to suit. A Gibson homology arm or a Type IIS tail
    does not anneal to the template in the first cycle, so including it would
    report a temperature the reaction never sees. The full oligo length is in
    the length column, because that is what gets ordered and paid for.
    """
    rows: list[OrderTableRow] = []
    for primer in design.primers:
        notes: list[str] = list(primer.notes)
        if primer.tail:
            notes.append(
                f"5' tail of {len(primer.tail)} nt ({primer.tail}) is added sequence and does not "
                "bind the template; the Tm shown is for the "
                f"{len(primer.binding)} nt binding region"
            )
        rows.append(
            OrderTableRow(
                name=primer.name,
                sequence_5_to_3=primer.sequence,
                length_nt=primer.length_nt,
                tm_c=round(_tm(primer.binding, design), 1),
                gc_percent=round(gc_content(primer.binding) * 100, 1),
                notes="; ".join(notes),
            )
        )
    return rows


def order_table_csv(rows: list[OrderTableRow]) -> str:
    """The order table as CSV, which section 7.7 requires it to export as.

    Written with the csv module rather than by joining commas, so a note
    containing a comma or a quote does not corrupt the file. Line terminator is
    a plain newline so the string is the same on every platform.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(ORDER_TABLE_COLUMNS)
    for row in rows:
        writer.writerow(
            [
                row.name,
                row.sequence_5_to_3,
                row.length_nt,
                f"{row.tm_c:.1f}",
                f"{row.gc_percent:.1f}",
                row.notes,
            ]
        )
    return buffer.getvalue()


def order_table_text(rows: list[OrderTableRow]) -> str:
    """The order table as aligned plain text, so it can be pasted anywhere."""
    columns = [list(ORDER_TABLE_COLUMNS)] + [
        [
            row.name,
            row.sequence_5_to_3,
            str(row.length_nt),
            f"{row.tm_c:.1f}",
            f"{row.gc_percent:.1f}",
            row.notes,
        ]
        for row in rows
    ]
    widths = [max(len(cell[index]) for cell in columns) for index in range(len(ORDER_TABLE_COLUMNS))]
    lines = ["  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)).rstrip() for row in columns]
    lines.insert(1, "  ".join("-" * width for width in widths))
    return "\n".join(lines) + "\n"


def annealing_temperature(design: AssemblyDesign, settings: Settings) -> tuple[float, str]:
    """The annealing temperature, derived from the computed Tm, and the rule used.

    Section 7.7 requires it to be derived rather than assumed. The rule is the
    lowest binding-region Tm in the set minus the configured offset, clamped to
    the polymerase's documented annealing range so a pathological Tm cannot
    produce an impossible thermocycler step. The returned string states the rule
    with the numbers filled in, so the result can be checked by hand.
    """
    tms = [_tm(primer.binding, design) for primer in design.primers]
    if not tms:
        raise ValueError("a protocol needs at least one primer to derive an annealing temperature from")
    lowest = min(tms)
    raw = lowest - settings.annealing_offset_below_min_tm_c
    clamped = min(max(raw, settings.annealing_min_c), settings.annealing_max_c)
    rule = (
        f"Lowest primer binding-region Tm in the set is {lowest:.1f} C (nearest-neighbor, "
        f"SantaLucia 1998 unified parameters, at {design.request.primer_conc_nm:.0f} nM primer and "
        f"{design.request.monovalent_salt_mm:.0f} mM monovalent salt). Annealing temperature is that "
        f"minus the configured {settings.annealing_offset_below_min_tm_c:.1f} C offset, giving "
        f"{raw:.1f} C"
    )
    if clamped != raw:
        rule += (
            f", clamped to {clamped:.1f} C by the {settings.annealing_min_c:.0f} to "
            f"{settings.annealing_max_c:.0f} C annealing range in the NEB Q5 protocol"
        )
    rule += (
        ". A high-fidelity polymerase often tolerates a higher annealing temperature than this "
        "conservative rule gives; raise it if the vendor's own calculator says so."
    )
    return round(clamped, 1), rule


def pcr_program(design: AssemblyDesign, annealing_c: float) -> list[ThermocyclingStep]:
    """Thermocycling for the fragment amplifications.

    Conditions are the NEB Q5 High-Fidelity DNA Polymerase standard protocol,
    held as named constants in `constants.py`. Extension time is computed from
    the longest expected amplicon at the documented seconds per kilobase, with
    a floor of one second per step because a thermocycler step cannot be zero.
    """
    longest_bp = max((amplicon.length_bp for amplicon in design.amplicons), default=1000)
    extension_s = max(1, math.ceil(longest_bp / 1000 * constants.PCR_EXTENSION_S_PER_KB))
    return [
        ThermocyclingStep(
            label="Initial denaturation",
            temperature_c=constants.PCR_INITIAL_DENATURATION_C,
            seconds=constants.PCR_INITIAL_DENATURATION_S,
        ),
        ThermocyclingStep(
            label="Denature",
            temperature_c=constants.PCR_DENATURATION_C,
            seconds=constants.PCR_DENATURATION_S,
            cycles=constants.PCR_CYCLES,
        ),
        ThermocyclingStep(
            label="Anneal, derived from the computed Tm",
            temperature_c=annealing_c,
            seconds=constants.PCR_ANNEALING_S,
            cycles=constants.PCR_CYCLES,
        ),
        ThermocyclingStep(
            label=f"Extend, {constants.PCR_EXTENSION_S_PER_KB} s per kb for a {longest_bp} bp longest amplicon",
            temperature_c=constants.PCR_EXTENSION_C,
            seconds=extension_s,
            cycles=constants.PCR_CYCLES,
        ),
        ThermocyclingStep(
            label="Final extension",
            temperature_c=constants.PCR_EXTENSION_C,
            seconds=constants.PCR_FINAL_EXTENSION_S,
        ),
    ]


def assembly_program(design: AssemblyDesign) -> list[ThermocyclingStep]:
    """The assembly reaction itself, per strategy.

    Gibson: the NEBuilder HiFi DNA Assembly incubation, whose length depends on
    the number of fragments. Golden Gate: the NEB Golden Gate Assembly cycling,
    alternating digestion and ligation then a final digestion. Simple PCR
    cloning: a restriction digest at the standard condition for most enzymes.
    """
    strategy = design.request.strategy
    fragments = len(design.fragment_order)
    if strategy == "gibson":
        minutes = (
            constants.GIBSON_INCUBATION_MIN_FEW_FRAGMENTS
            if fragments <= constants.GIBSON_FEW_FRAGMENTS_MAX
            else constants.GIBSON_INCUBATION_MIN_MANY_FRAGMENTS
        )
        return [
            ThermocyclingStep(
                label=f"NEBuilder HiFi assembly incubation, {fragments} fragments",
                temperature_c=constants.GIBSON_INCUBATION_C,
                seconds=minutes * 60,
            )
        ]
    if strategy == "golden_gate":
        return [
            ThermocyclingStep(
                label="Digest",
                temperature_c=constants.GOLDEN_GATE_DIGEST_C,
                seconds=constants.GOLDEN_GATE_DIGEST_S,
                cycles=constants.GOLDEN_GATE_CYCLES,
            ),
            ThermocyclingStep(
                label="Ligate",
                temperature_c=constants.GOLDEN_GATE_LIGATE_C,
                seconds=constants.GOLDEN_GATE_LIGATE_S,
                cycles=constants.GOLDEN_GATE_CYCLES,
            ),
            ThermocyclingStep(
                label="Final digest",
                temperature_c=constants.GOLDEN_GATE_FINAL_DIGEST_C,
                seconds=constants.GOLDEN_GATE_FINAL_DIGEST_S,
            ),
        ]
    return [
        ThermocyclingStep(
            label="Restriction digest of insert and vector",
            temperature_c=constants.PCR_CLONING_DIGEST_C,
            seconds=constants.PCR_CLONING_DIGEST_MIN * 60,
        )
    ]


def _composition(design: AssemblyDesign) -> list[str]:
    strategy = design.request.strategy
    common = [
        "PCR, per 25 uL reaction: 12.5 uL 2X high-fidelity master mix, 1.25 uL each primer at "
        "10 uM (500 nM final, matching the primer_conc_nm the Tm values were computed at), 1 to "
        "10 ng template, water to 25 uL.",
        "Confirm the master mix lot insert before use: the conditions below are the vendor's "
        "published defaults, not a measurement from this build.",
    ]
    if strategy == "gibson":
        return common + [
            "Assembly, per 20 uL reaction: 10 uL NEBuilder HiFi 2X master mix, 0.03 to 0.2 pmol "
            "of each purified fragment, water to 20 uL. Use equimolar fragments and keep the "
            "total insert DNA under 1 pmol."
        ]
    if strategy == "golden_gate":
        enzyme = get_enzyme(design.request.enzyme) if design.request.enzyme else None
        name = enzyme.name if enzyme else "the chosen Type IIS enzyme"
        return common + [
            f"Assembly, per 20 uL reaction: 2 uL T4 DNA ligase buffer, 1 uL {name}, 1 uL T4 DNA "
            "ligase, 75 ng of each purified fragment, water to 20 uL. Keep fragments equimolar.",
            f"{name} cuts outside its own recognition site, so the site is consumed at each "
            "junction and the join leaves no scar.",
        ]
    return common + [
        "Digest, per 50 uL reaction: 5 uL 10X restriction buffer, 1 uL of each enzyme, 1 ug DNA, "
        "water to 50 uL. Gel-purify, then ligate insert and vector at a 3 to 1 molar ratio with "
        "T4 DNA ligase."
    ]


def _expected_outcome(design: AssemblyDesign) -> str:
    strategy = design.request.strategy
    total = sum(design.fragment(name).length_bp for name in design.fragment_order if _has(design, name))
    if design.request.vector_backbone:
        total += len(design.request.vector_backbone)
    sizes = ", ".join(f"{amplicon.name} at {amplicon.length_bp} bp" for amplicon in design.amplicons)
    assembled = (
        f"The assembled construct is approximately {total} bp, being the "
        f"{len(design.fragment_order)} fragments joined in the order "
        f"{' to '.join(design.fragment_order)}."
    )
    if strategy == "gibson":
        return (
            f"Each PCR gives one band: {sizes}. {assembled} Transform the assembly reaction "
            "directly and screen colonies by PCR across each junction, then sequence the junctions."
        )
    if strategy == "golden_gate":
        return (
            f"Each PCR gives one band: {sizes}. {assembled} Correct assemblies lose the Type IIS "
            "sites, so a diagnostic digest with the same enzyme leaves a correct clone uncut. "
            "Screen colonies by PCR and sequence the junctions."
        )
    return (
        f"Each PCR gives one band: {sizes}. {assembled} Screen colonies by restriction digest for "
        "the expected insert size, then sequence across both junctions to confirm orientation."
    )


def _has(design: AssemblyDesign, name: str) -> bool:
    try:
        design.fragment(name)
    except KeyError:
        return False
    return True


def protocol(design: AssemblyDesign, settings: Settings | None = None) -> Protocol:
    """The section 7.7 protocol, with the annealing temperature derived from the Tm."""
    resolved = settings or settings_for(design.request)
    annealing_c, rule = annealing_temperature(design, resolved)
    sources = [
        "PCR cycling: NEB Q5 High-Fidelity DNA Polymerase standard protocol.",
        "Annealing temperature: derived from the nearest-neighbor Tm of the primer binding "
        "regions (SantaLucia 1998 unified parameters, Appendix A), not assumed.",
    ]
    if design.request.strategy == "gibson":
        sources.append(
            "Assembly incubation: NEBuilder HiFi DNA Assembly protocol, 50 C for 15 minutes for "
            "two or three fragments and 60 minutes for four to six."
        )
        sources.append("Method: Gibson et al. 2009, Nat Methods 6:343-345.")
    elif design.request.strategy == "golden_gate":
        sources.append(
            "Assembly cycling: NEB Golden Gate Assembly protocol, cycles of 37 C digestion and "
            "16 C ligation followed by a 60 C final digestion."
        )
        sources.append(
            "Method: Engler and colleagues introduced the one-pot Type IIS assembly method "
            "(Appendix E). Enzyme recognition sequence and cut offsets are from Appendix D."
        )
    else:
        sources.append("Digest: the standard 37 C condition for most NEB restriction enzymes.")
    return Protocol(
        strategy=design.request.strategy,
        reaction_composition=_composition(design),
        annealing_temperature_c=annealing_c,
        annealing_rule=rule,
        pcr_program=pcr_program(design, annealing_c),
        assembly_program=assembly_program(design),
        expected_outcome=_expected_outcome(design),
        sources=sources,
    )


def junction_map(design: AssemblyDesign) -> list[JunctionMapEntry]:
    """The section 7.7 junction map: how fragments join, with overhangs or arms labelled."""
    entries: list[JunctionMapEntry] = []
    for junction in design.junctions:
        if junction.kind == "gibson_homology":
            label = f"{junction.length_bp} bp homology arm"
            detail = (
                f"The {junction.right_fragment} forward primer carries the last {junction.length_bp} bp "
                f"of {junction.left_fragment} as a 5' tail ({junction.sequence}), so the two "
                f"amplicons share that sequence and anneal after exonuclease chew-back. Overlap Tm "
                f"{_tm(junction.sequence, design):.1f} C."
            )
        elif junction.kind == "golden_gate_overhang":
            source = (
                f"taken from the {junction.right_fragment} fragment junction, which makes the join scarless"
                if junction.overhang_source == "fragment_junction"
                else f"defined by the {junction.overhang_standard_name} standard"
            )
            detail = (
                f"A {junction.length_bp} nt fusion overhang {junction.sequence}, complementary "
                f"overhang {reverse_complement(junction.sequence)}, {source}. The Type IIS site sits "
                f"in the primer tail outside the overhang, so it is cut away and does not end up in "
                "the construct."
            )
            label = f"{junction.length_bp} nt overhang {junction.sequence}"
        else:
            label = f"restriction site {junction.sequence}"
            detail = (
                f"Both amplicon ends carry the {junction.sequence} site in the primer tail. Digest "
                "and ligate. The same site at both ends means the insert can go in either "
                "orientation, so screen for it."
            )
        entries.append(
            JunctionMapEntry(
                index=junction.index,
                left_fragment=junction.left_fragment,
                right_fragment=junction.right_fragment,
                label=label,
                sequence=junction.sequence,
                length_bp=junction.length_bp,
                detail=detail,
            )
        )
    return entries


def junction_map_text(design: AssemblyDesign, entries: list[JunctionMapEntry]) -> str:
    """The junction map as plain text, for the terminal and for an export."""
    if not entries:
        return (
            f"No junctions: the {design.request.strategy} design amplifies "
            f"{len(design.fragment_order)} fragment(s) without joining them.\n"
        )
    lines = [f"Assembly order: {' to '.join(design.fragment_order)} (circular)"]
    for entry in entries:
        lines.append("")
        lines.append(f"  [{entry.left_fragment}] --{entry.label}-- [{entry.right_fragment}]")
        lines.append(f"      {entry.detail}")
    return "\n".join(lines) + "\n"


def build_outputs(design: AssemblyDesign, report: ValidationReport) -> AssemblyOutputs:
    """Every section 7.7 output in one payload."""
    settings = settings_for(design.request)
    rows = order_table(design)
    entries = junction_map(design)
    return AssemblyOutputs(
        order_table=rows,
        order_table_csv=order_table_csv(rows),
        protocol=protocol(design, settings),
        junction_map=entries,
        junction_map_text=junction_map_text(design, entries),
        domestication=design.domestication,
        report=report,
    )


__all__ = [
    "ORDER_TABLE_COLUMNS",
    "annealing_temperature",
    "assembly_program",
    "build_outputs",
    "junction_map",
    "junction_map_text",
    "order_table",
    "order_table_csv",
    "order_table_text",
    "pcr_program",
    "protocol",
]
