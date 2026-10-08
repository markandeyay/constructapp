"""Primer and junction composition for the three section 7.1 strategies.

Source: sections 7.1, 7.2, 7.3 and 7.6 of the engine capability system design,
with Appendix D for the Type IIS cut geometry.

Section 4.2 is the architectural point this module implements: "A primer is a
subsequence of a known template plus an optional tail. The design problem is
choosing coordinates and checking thermodynamics. Nothing is invented." Every
base of every primer produced here is either a base of a supplied fragment, a
base of a supplied vector backbone, an enzyme recognition sequence from
Appendix D, a fusion overhang taken from a fragment junction or from a
caller-supplied published standard, or a spacer nucleotide chosen by the
documented rule in `_filler`. `AssemblyDesign.provenance` lists which.

Determinism (section 3.3 constraint 3): there is no randomness here and no
model call. Binding region length is chosen by an exhaustive scan over the
configured length window, scored by distance from the request's `target_tm_c`
and tie-broken towards the shorter primer. Spacer nucleotides are chosen by an
exhaustive scan in A, C, G, T order. Same request, same primers, always.
"""

from __future__ import annotations

from packages.core.schemas.assembly import (
    Amplicon,
    AssemblyDesign,
    AssemblyRequest,
    Junction,
    Primer,
)
from packages.core.schemas.capability import CapabilityKind
from packages.core.sequence import clean_sequence, reverse_complement
from packages.core.sequence.tm import melting_temperature
from packages.validation.assembly.codon_usage import HostCodonUsage
from packages.validation.assembly.domestication import build_report
from packages.validation.assembly.enzymes import (
    OverhangStandard,
    TypeIISEnzyme,
    find_recognition_sites,
    get_enzyme,
)
from packages.validation.assembly.settings import Settings, settings_for

_BASES: tuple[str, ...] = ("A", "C", "G", "T")

# Name given to the vector backbone when it participates in the assembly as a
# fragment. It is the key `AssemblyRequest.template_set` uses, so the two
# cannot drift apart.
VECTOR_BACKBONE_NAME = "vector_backbone"


def _tm(sequence: str, request: AssemblyRequest) -> float:
    """Nearest-neighbor Tm at the request's own salt and strand concentration.

    Section 7.3 and Appendix A. The request's `divalent_salt_mm` and `dntp_mm`
    are passed through, so the von Ahsen monovalent equivalent documented in
    `packages.core.sequence.tm` is applied when they are non-zero.
    """
    return melting_temperature(
        sequence,
        primer_conc_nm=request.primer_conc_nm,
        monovalent_salt_mm=request.monovalent_salt_mm,
        divalent_salt_mm=request.divalent_salt_mm,
        dntp_mm=request.dntp_mm,
    )


def choose_binding_region(
    template: str,
    *,
    direction: str,
    request: AssemblyRequest,
    settings: Settings,
) -> tuple[str, int, int]:
    """Pick the binding region at one end of a template.

    Returns the primer's binding sequence written 5' to 3', and the interval it
    occupies on the forward strand of the template, zero-based and end
    exclusive. A forward primer anneals to the bottom strand at the template's
    5' end, so its binding sequence is the template's own first bases. A
    reverse primer anneals to the top strand at the 3' end, so its binding
    sequence is the reverse complement of the template's last bases.

    Length is chosen by scanning the configured window and taking the length
    whose Tm is closest to `target_tm_c`, with the shorter length winning a tie.
    Scanning rather than solving keeps the choice exact and keeps it
    deterministic.
    """
    sequence = clean_sequence(template)
    low = settings.primer_min_length_nt
    high = min(settings.primer_max_length_nt, len(sequence))
    if high < low:
        raise ValueError(
            f"template of {len(sequence)} bp is shorter than the minimum primer length "
            f"{low} nt; nothing can be designed against it"
        )
    best: tuple[float, int] | None = None
    for length in range(low, high + 1):
        candidate = sequence[:length] if direction == "forward" else reverse_complement(sequence[-length:])
        distance = abs(_tm(candidate, request) - request.target_tm_c)
        if best is None or (distance, length) < best:
            best = (distance, length)
    assert best is not None  # the window is non-empty, checked above
    length = best[1]
    if direction == "forward":
        return sequence[:length], 0, length
    return reverse_complement(sequence[-length:]), len(sequence) - length, len(sequence)


def _filler(prefix: str, count: int, enzyme: TypeIISEnzyme) -> str:
    """Spacer nucleotides for a Type IIS primer tail, chosen deterministically.

    Appendix D's cut notation puts `top_cut_offset` nucleotides between the
    recognition site and the top strand cut, so a Type IIS primer tail needs
    that many filler bases before the fusion overhang. Their identity is free,
    with one constraint that matters: they must not complete a new copy of the
    recognition site, which would make the primer cut itself.

    The rule is an exhaustive scan in A, C, G, T order, taking the first base at
    each position that adds no recognition site beyond the ones `prefix`
    already contains. `prefix` normally ends with the deliberate recognition
    site itself, so the test counts sites rather than looking for any site: the
    deliberate one must survive and only an extra one is rejected. The order
    carries no biological claim; it exists so the same request always produces
    the same primer (section 3.3 constraint 3).
    """
    baseline = len(find_recognition_sites(prefix, enzyme)) if prefix else 0
    filler = ""
    for _ in range(count):
        for base in _BASES:
            if len(find_recognition_sites(prefix + filler + base, enzyme)) <= baseline:
                filler += base
                break
        else:  # pragma: no cover - some base always avoids a 6 or 7 bp site
            raise ValueError(f"no spacer base avoids creating a {enzyme.recognition} site")
    return filler


def _assembly_order(request: AssemblyRequest) -> list[tuple[str, str]]:
    """The fragments in assembly order, as (name, sequence) pairs.

    The order is the order the fragments were supplied, with the vector
    backbone last when one is given. Section 7.5 check 18 then verifies that
    the overhang topology actually admits exactly one order; this function
    states the intended one, it does not prove it.
    """
    order = [(fragment.name, fragment.sequence) for fragment in request.fragments]
    if request.vector_backbone:
        order.append((VECTOR_BACKBONE_NAME, request.vector_backbone))
    return order


def _overhang_for(
    index: int,
    right_sequence: str,
    overhang_nt: int,
    standard: OverhangStandard | None,
) -> tuple[str, str, str | None]:
    """The fusion overhang for one junction, and where it came from.

    Appendix D: a published modular standard's defined overhang set is used
    verbatim when one applies, rather than generating overhangs. Otherwise the
    overhang is the first `overhang_nt` bases of the downstream fragment, which
    is the scarless choice: those bases are already in the construct, so the
    join leaves no added sequence behind.
    """
    if standard is not None:
        if index >= len(standard.overhangs):
            raise ValueError(
                f"overhang standard {standard.name!r} defines {len(standard.overhangs)} overhangs "
                f"but the assembly has at least {index + 1} junctions"
            )
        return standard.overhangs[index], "overhang_standard", standard.name
    return right_sequence[:overhang_nt], "fragment_junction", None


def compose(
    request: AssemblyRequest,
    *,
    host_codon_usage: HostCodonUsage | None = None,
) -> AssemblyDesign:
    """Compose primers, junctions and amplicons for a request (section 7.1).

    `host_codon_usage` is only used for the Golden Gate domestication report
    and is normally built from `request.host_codon_usage` by the caller. None
    means no table, which `codon_usage.py` handles by reporting the frequency
    comparison as unknown with a reason rather than inventing one.
    """
    settings = settings_for(request)
    order = _assembly_order(request)
    names = [name for name, _ in order]
    provenance: list[str] = [f"strategy:{request.strategy}"]
    for fragment in request.fragments:
        provenance.append(f"fragment:{fragment.name}:{fragment.source}")
    if request.vector_backbone:
        provenance.append("user_input:vector_backbone")

    primers: list[Primer] = []
    junctions: list[Junction] = []
    amplicons: list[Amplicon] = []

    enzyme: TypeIISEnzyme | None = None
    if request.enzyme:
        enzyme = get_enzyme(request.enzyme)
        provenance.append(f"enzyme:{enzyme.name}:Appendix D {enzyme.cut_notation}")

    standard: OverhangStandard | None = None
    if request.overhang_standard is not None:
        standard = OverhangStandard(
            name=request.overhang_standard.name,
            citation=request.overhang_standard.citation,
            overhangs=tuple(request.overhang_standard.overhangs),
        )
        provenance.append(f"overhang_standard:{standard.name}:{standard.citation}")

    # Tails indexed by (fragment name, direction), filled in per strategy and
    # then attached to the primers below.
    tails: dict[tuple[str, str], str] = {}

    if request.strategy == "gibson":
        overlap = settings.gibson_overlap_design_bp
        for index in range(len(order)):
            left_name, left_sequence = order[index - 1]
            right_name, _ = order[index]
            if len(order) == 1:
                break
            arm = left_sequence[-overlap:] if len(left_sequence) >= overlap else left_sequence
            tails[(right_name, "forward")] = arm
            junctions.append(
                Junction(
                    index=index,
                    left_fragment=left_name,
                    right_fragment=right_name,
                    kind="gibson_homology",
                    sequence=arm,
                )
            )
    elif request.strategy == "golden_gate":
        assert enzyme is not None  # AssemblyRequest requires `enzyme` for golden_gate
        overhang_nt = enzyme.overhang_nt
        for index in range(len(order)):
            left_name, left_sequence = order[index - 1] if len(order) > 1 else order[0]
            right_name, right_sequence = order[index]
            overhang, source, standard_name = _overhang_for(index, right_sequence, overhang_nt, standard)
            # Downstream fragment: the overhang is the first bases of its own
            # binding region when it came from the junction, so the tail is
            # only the enzyme machinery. With a standard overhang the bases are
            # added, because they are not the fragment's own.
            forward_prefix = enzyme.recognition
            forward_tail = forward_prefix + _filler(forward_prefix, enzyme.top_cut_offset, enzyme)
            if source == "overhang_standard":
                forward_tail += overhang
            tails[(right_name, "forward")] = (
                _filler("", settings.golden_gate_primer_spacer_nt, enzyme) + forward_tail
            )
            # Upstream fragment: its amplicon has to carry the same overhang at
            # its 3' end, written on the reverse primer as the reverse
            # complement, 5' of the binding region.
            reverse_prefix = enzyme.recognition
            reverse_tail = reverse_prefix + _filler(reverse_prefix, enzyme.top_cut_offset, enzyme)
            reverse_tail += reverse_complement(overhang)
            tails[(left_name, "reverse")] = (
                _filler("", settings.golden_gate_primer_spacer_nt, enzyme) + reverse_tail
            )
            junctions.append(
                Junction(
                    index=index,
                    left_fragment=left_name,
                    right_fragment=right_name,
                    kind="golden_gate_overhang",
                    sequence=overhang,
                    overhang_source=source,  # type: ignore[arg-type]
                    overhang_standard_name=standard_name,
                )
            )
    else:  # pcr_cloning
        if enzyme is not None:
            site = enzyme.recognition
            for name, _ in order:
                tails[(name, "forward")] = _filler("", settings.golden_gate_primer_spacer_nt, enzyme) + site
                tails[(name, "reverse")] = _filler("", settings.golden_gate_primer_spacer_nt, enzyme) + site
            for index in range(len(order)):
                left_name, _ = order[index - 1] if len(order) > 1 else order[0]
                right_name, _ = order[index]
                junctions.append(
                    Junction(
                        index=index,
                        left_fragment=left_name,
                        right_fragment=right_name,
                        kind="restriction_site",
                        sequence=site,
                    )
                )

    for name, sequence in order:
        for direction in ("forward", "reverse"):
            binding, start, end = choose_binding_region(
                sequence, direction=direction, request=request, settings=settings
            )
            primers.append(
                Primer(
                    name=f"{name}_{'F' if direction == 'forward' else 'R'}",
                    fragment=name,
                    direction=direction,  # type: ignore[arg-type]
                    tail=tails.get((name, direction), ""),
                    binding=binding,
                    binding_start=start,
                    binding_end=end,
                )
            )

    by_fragment = {(primer.fragment, primer.direction): primer for primer in primers}
    for name, sequence in order:
        forward = by_fragment[(name, "forward")]
        reverse = by_fragment[(name, "reverse")]
        amplicons.append(
            Amplicon(
                name=f"{name}_amplicon",
                fragment=name,
                forward_primer=forward.name,
                reverse_primer=reverse.name,
                length_bp=len(sequence) + len(forward.tail) + len(reverse.tail),
            )
        )

    domestication = None
    if request.strategy == "golden_gate" and enzyme is not None:
        domestication = build_report(list(request.fragments), enzyme, usage=host_codon_usage)
        if host_codon_usage is not None:
            provenance.append(f"host_codon_usage:{host_codon_usage.host}:{host_codon_usage.citation}")

    provenance.append(
        "tm_model:nearest-neighbor thermodynamics with monovalent salt correction, "
        "SantaLucia 1998 unified parameters (Appendix A)"
    )
    return AssemblyDesign(
        request=request,
        primers=primers,
        junctions=junctions,
        amplicons=amplicons,
        fragment_order=names,
        domestication=domestication,
        provenance=provenance,
        composed=True,
    )


def host_codon_usage_from_request(request: AssemblyRequest) -> HostCodonUsage | None:
    """Build a `HostCodonUsage` from the request, or None when none was supplied.

    None is the normal case: no host codon usage table ships with this build.
    See `packages/validation/assembly/codon_usage.py` for the recorded decision
    and what it means for the section 7.6 report.
    """
    spec = request.host_codon_usage
    if spec is None:
        return None
    return HostCodonUsage(host=spec.host, citation=spec.citation, frequencies=dict(spec.frequencies))


class AssemblyGenerator:
    """`CapabilityGenerator` for the assembly capability (section 5.2)."""

    kind = CapabilityKind.ASSEMBLY

    def compose(self, request: AssemblyRequest) -> AssemblyDesign:  # type: ignore[override]
        return compose(request, host_codon_usage=host_codon_usage_from_request(request))


__all__ = [
    "VECTOR_BACKBONE_NAME",
    "AssemblyGenerator",
    "choose_binding_region",
    "compose",
    "host_codon_usage_from_request",
]
