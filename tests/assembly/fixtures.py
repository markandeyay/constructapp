"""Shared fixtures for the assembly tests.

Every sequence below is a slice of a real GenBank record already in this
repository's part registry, taken at an offset recorded beside it. Nothing is
invented, per section 3.3 constraint 1, and the slice offsets are chosen rather
than the sequence: a bench scientist picks where to cut a fragment, and where to
cut is the only freedom a Gibson or Golden Gate primer design has, because the
primer has to start exactly at the junction or bases are lost from the construct.

`clean_request` is the Tier A case: a two-fragment Gibson assembly that passes
every applicable section 7.5 check with no warning. The known-bad builders each
break exactly one thing, so a test can assert that the named check fires and
that nothing else fails (section 9.3).
"""

from __future__ import annotations

from packages.core.schemas.assembly import (
    AssemblyDesign,
    AssemblyRequest,
    Fragment,
    Junction,
    Primer,
)

# Slice of GenBank KU341333.1, the CBh promoter (regulatory feature 442..1240 in
# the record, which is part `promoter.cbh`), offset 532, 180 bp.
FRAGMENT_A = (
    "CGGCCCTATAAAAAGCGAAGCGCGCGGCGGGCGGGAGTCGCTGCGACGCTGCCTTCGCCCCGTGCCCCGCTCCGCCGCCGCCTCGCGCC"
    "GCCCGCCCCGGCTCTGACTGACCGCGTTACTCCCACAGGTGAGCGGGCGGGACGGCCCTTCTCCTCCGGGCTGTAATTAGCTGAGCAAGAG"
)
FRAGMENT_A_SOURCE = "GenBank KU341333.1, CBh promoter feature 442..1240, offset 532, 180 bp"

# Slice of GenBank AF396260.1, the CMV promoter (regulatory feature 150..812 in
# the record, which is part `promoter.cmv`), offset 462, 180 bp.
FRAGMENT_B = (
    "GGGAGTTTGTTTTGCACCAAAATCAACGGGACTTTCCAAAATGTCGTAACAACTCCGCCCCATTGACGCAAATGGGCGGTAGGCGTGTAC"
    "GGTGGGAGGTCTATATAAGCAGAGCTCGTTTAGTGAACCGTCAGATCGCCTGGAGACGCCATCCACGCTGTTTTGACCTCCATAGAAGAC"
)
FRAGMENT_B_SOURCE = "GenBank AF396260.1, CMV promoter feature 150..812, offset 462, 180 bp"

# A second pair, from the same two records at different offsets, whose terminal
# four bases give Golden Gate fusion overhangs that pass checks 15 to 17.
GOLDEN_GATE_A = (
    "AGTGTATCATATGCCAAGTACGCCCCCTATTGACGTCAATGACGGTAAATGGCCCGCCTGGCATTGTGCCCAGTACATGACCTTATGGGA"
    "CTTTCCTACTTGGCAGTACATCTACGTATTAGTCATCGCTATTACCATGGTCGAGGTGAGCCCCACGTTCTGCTTCACTCTCCCCATCTC"
)
GOLDEN_GATE_A_SOURCE = "GenBank KU341333.1, CBh promoter feature 442..1240, offset 147, 180 bp"

GOLDEN_GATE_B = (
    "TTTGACTCACGGGGATTTCCAAGTCTCCACCCCATTGACGTCAATGGGAGTTTGTTTTGCACCAAAATCAACGGGACTTTCCAAAATGTC"
    "GTAACAACTCCGCCCCATTGACGCAAATGGGCGGTAGGCGTGTACGGTGGGAGGTCTATATAAGCAGAGCTCGTTTAGTGAACCGTCAGA"
)
GOLDEN_GATE_B_SOURCE = "GenBank AF396260.1, CMV promoter feature 150..812, offset 417, 180 bp"


def fragment_a(**overrides: object) -> Fragment:
    return Fragment(name="frag_a", sequence=FRAGMENT_A, source=FRAGMENT_A_SOURCE, **overrides)  # type: ignore[arg-type]


def fragment_b(**overrides: object) -> Fragment:
    return Fragment(name="frag_b", sequence=FRAGMENT_B, source=FRAGMENT_B_SOURCE, **overrides)  # type: ignore[arg-type]


def clean_request(**overrides: object) -> AssemblyRequest:
    """A two-fragment Gibson assembly that passes every applicable check cleanly."""
    base: dict[str, object] = {
        "strategy": "gibson",
        "fragments": [fragment_a(), fragment_b()],
    }
    base.update(overrides)
    return AssemblyRequest(**base)  # type: ignore[arg-type]


def clean_golden_gate_request(**overrides: object) -> AssemblyRequest:
    """A two-fragment BsaI Golden Gate assembly that passes every check cleanly."""
    base: dict[str, object] = {
        "strategy": "golden_gate",
        "enzyme": "BsaI",
        "fragments": [
            Fragment(name="frag_a", sequence=GOLDEN_GATE_A, source=GOLDEN_GATE_A_SOURCE),
            Fragment(name="frag_b", sequence=GOLDEN_GATE_B, source=GOLDEN_GATE_B_SOURCE),
        ],
    }
    base.update(overrides)
    return AssemblyRequest(**base)  # type: ignore[arg-type]


def design_from(request: AssemblyRequest) -> AssemblyDesign:
    """A design with primers left empty, so the validator composes them."""
    return AssemblyDesign(request=request)


def pinned_design(
    request: AssemblyRequest,
    primers: list[Primer],
    junctions: list[Junction] | None = None,
) -> AssemblyDesign:
    """A design with exact primers, for a case that targets one primer-level check."""
    return AssemblyDesign(
        request=request,
        primers=primers,
        junctions=junctions or [],
        fragment_order=[fragment.name for fragment in request.fragments],
    )


def primer(
    name: str,
    fragment: str,
    direction: str,
    binding: str,
    *,
    tail: str = "",
    start: int = 0,
) -> Primer:
    return Primer(
        name=name,
        fragment=fragment,
        direction=direction,  # type: ignore[arg-type]
        tail=tail,
        binding=binding,
        binding_start=start,
        binding_end=start + len(binding),
    )


def severity_of(report: object, check_id: str) -> str:
    """The severity of one check in a report, as a plain string."""
    for check in report.checks:  # type: ignore[attr-defined]
        if check.check_id == check_id:
            return check.severity.value
    raise AssertionError(
        f"check {check_id!r} is absent from the report; present: "
        + ", ".join(check.check_id for check in report.checks)  # type: ignore[attr-defined]
    )


def unexpected_failures(report: object, allowed: set[str]) -> list[str]:
    """Check ids reporting FAIL that the case did not expect (section 9.3 rule 3)."""
    return [
        check.check_id
        for check in report.checks  # type: ignore[attr-defined]
        if check.severity.value == "fail" and check.check_id not in allowed
    ]
