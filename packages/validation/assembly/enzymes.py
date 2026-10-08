"""Type IIS enzyme reference and the published-standard overhang mechanism.

Source: Appendix D of the engine capability system design. Every recognition
sequence and every cut offset below is read from that table and nothing is
added to it, per section 3.3 constraint 1.

Appendix D's notation: `SITE(N1/N2)` means the enzyme cuts N1 nucleotides 3' of
the recognition site on the top strand and N2 on the bottom, leaving an
overhang of `N2 - N1` nucleotides. The `overhang_nt` field below is Appendix
D's stated overhang length and the module asserts at import that it equals
`N2 - N1`, so a typo in either column cannot survive.

Appendix D also states: "Domestication, section 7.6, must check both strands
for the recognition site, since these sequences are not palindromic." That is
`find_recognition_sites`, which searches both strands unconditionally.

And: "If the assembly follows a published modular standard, use that standard's
defined overhang set rather than generating overhangs, and cite the standard."
`OverhangStandard` is that mechanism. `BUNDLED_OVERHANG_STANDARDS` is
deliberately empty: see the note on it.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.core.sequence import clean_sequence, find_both_strands, reverse_complement


@dataclass(frozen=True)
class TypeIISEnzyme:
    """One Type IIS enzyme, exactly as Appendix D records it.

    `top_cut_offset` and `bottom_cut_offset` are Appendix D's N1 and N2: the
    number of nucleotides 3' of the recognition site at which the enzyme cuts
    the top and the bottom strand. `overhang_nt` is Appendix D's overhang
    column, which equals `bottom_cut_offset - top_cut_offset`.
    """

    name: str
    aliases: tuple[str, ...]
    recognition: str
    top_cut_offset: int
    bottom_cut_offset: int
    overhang_nt: int

    @property
    def cut_notation(self) -> str:
        """Appendix D's `SITE(N1/N2)` notation for this enzyme."""
        return f"{self.recognition}({self.top_cut_offset}/{self.bottom_cut_offset})"

    @property
    def is_palindromic(self) -> bool:
        """Whether the recognition sequence equals its own reverse complement.

        Appendix D notes that these sequences are not palindromic, which is why
        both strands must be searched. The property exists so that fact is
        checked rather than assumed.
        """
        return self.recognition == reverse_complement(self.recognition)


# Appendix D: Type IIS enzyme reference. Recognition sequences, cut offsets and
# overhang lengths are the five rows of that table, unmodified.
TYPE_IIS_ENZYMES: dict[str, TypeIISEnzyme] = {
    "BsaI": TypeIISEnzyme("BsaI", (), "GGTCTC", 1, 5, 4),
    "BsmBI": TypeIISEnzyme("BsmBI", ("Esp3I",), "CGTCTC", 1, 5, 4),
    "BbsI": TypeIISEnzyme("BbsI", ("BpiI",), "GAAGAC", 2, 6, 4),
    "SapI": TypeIISEnzyme("SapI", ("LguI",), "GCTCTTC", 1, 4, 3),
    "AarI": TypeIISEnzyme("AarI", (), "CACCTGC", 4, 8, 4),
}

# Appendix D names a second trade name for three of the five enzymes. Either
# name resolves to the same record, because a user who writes Esp3I means BsmBI.
_ALIAS_INDEX: dict[str, str] = {
    alias.upper(): enzyme.name for enzyme in TYPE_IIS_ENZYMES.values() for alias in enzyme.aliases
}
_NAME_INDEX: dict[str, str] = {name.upper(): name for name in TYPE_IIS_ENZYMES}


def _validate_table() -> None:
    """Check the table against Appendix D's own notation at import time."""
    for enzyme in TYPE_IIS_ENZYMES.values():
        expected = enzyme.bottom_cut_offset - enzyme.top_cut_offset
        if expected != enzyme.overhang_nt:
            raise ValueError(
                f"{enzyme.name}: Appendix D gives an overhang of {enzyme.overhang_nt} nt but "
                f"{enzyme.cut_notation} implies {expected} nt"
            )
        clean_sequence(enzyme.recognition)


_validate_table()


def get_enzyme(name: str) -> TypeIISEnzyme:
    """Resolve an enzyme by its Appendix D name or by an Appendix D alias.

    Raises KeyError naming every supported enzyme, because section 3.3
    constraint 4 requires an unsupported request to fail loudly rather than
    fall back to a default enzyme.
    """
    key = name.strip().upper()
    resolved = _NAME_INDEX.get(key) or _ALIAS_INDEX.get(key)
    if resolved is None:
        supported = ", ".join(
            f"{enzyme.name}" + (f" (also {', '.join(enzyme.aliases)})" if enzyme.aliases else "")
            for enzyme in TYPE_IIS_ENZYMES.values()
        )
        raise KeyError(f"enzyme {name!r} is not in the Appendix D reference. Supported: {supported}")
    return TYPE_IIS_ENZYMES[resolved]


def find_recognition_sites(sequence: str, enzyme: TypeIISEnzyme, *, circular: bool = False) -> list:
    """Every occurrence of the recognition site, on both strands.

    Appendix D: the recognition sequences are not palindromic, so a search of
    the forward strand alone misses half the sites. Returns the `Hit` records
    of the shared sequence search utility, whose coordinates are always given
    on the forward strand with `strand` recording which strand matched.
    """
    return find_both_strands(sequence, enzyme.recognition, circular=circular)


@dataclass(frozen=True)
class OverhangStandard:
    """A published modular assembly standard's defined fusion overhang set.

    Appendix D: "If the assembly follows a published modular standard, use that
    standard's defined overhang set rather than generating overhangs, and cite
    the standard." A caller supplies one of these and the designer uses its
    `overhangs` in the given order instead of taking overhangs from the
    fragment junctions. `citation` is carried into the design's `provenance`
    and into `parameters_used`, so the output always says which standard it
    followed.

    `overhangs` are written 5' to 3' on the top strand, in the order the
    standard assigns them to junctions.
    """

    name: str
    citation: str
    overhangs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("an overhang standard must be named")
        if not self.citation.strip():
            raise ValueError(
                f"overhang standard {self.name!r} has no citation; Appendix D requires the "
                "standard to be cited when its overhang set is used"
            )
        if not self.overhangs:
            raise ValueError(f"overhang standard {self.name!r} defines no overhangs")
        cleaned = tuple(clean_sequence(item) for item in self.overhangs)
        if len(set(cleaned)) != len(cleaned):
            raise ValueError(f"overhang standard {self.name!r} repeats an overhang")
        object.__setattr__(self, "overhangs", cleaned)


# Published modular standards bundled with this build: none.
#
# Appendix D requires a published standard's overhang set to be used verbatim
# when the assembly follows that standard, and Appendix E requires the standard
# to be cited. Neither the MoClo fusion site set (Weber et al. 2011) nor any
# other modular cloning standard's overhang strings could be read from a
# primary document while this package was built, and section 3.3 constraint 1
# forbids reciting sequence from memory: a wrong 4 bp overhang set produces an
# assembly that silently does not assemble.
#
# The mechanism is implemented and tested rather than stubbed. A caller that
# supplies an `OverhangStandard`, with its citation, gets that standard's
# overhangs used verbatim, the citation recorded in `provenance` and
# `parameters_used`, and the generated-overhang path bypassed entirely. When no
# standard is supplied, overhangs are taken from the fragment junctions
# themselves (the scarless case) and the design says so, which is honest rather
# than a claim to follow a standard it does not have.
BUNDLED_OVERHANG_STANDARDS: dict[str, OverhangStandard] = {}


def get_overhang_standard(name: str) -> OverhangStandard:
    """Resolve a bundled overhang standard by name, failing loudly when absent."""
    key = name.strip()
    if key not in BUNDLED_OVERHANG_STANDARDS:
        raise KeyError(
            f"overhang standard {name!r} is not bundled with this build. No published modular "
            "standard overhang set ships here (see the note in enzymes.py); supply an "
            "OverhangStandard with its citation instead."
        )
    return BUNDLED_OVERHANG_STANDARDS[key]
