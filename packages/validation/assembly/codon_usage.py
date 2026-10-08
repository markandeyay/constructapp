"""Host codon usage: the mechanism, and the honest absence of a bundled table.

Source: section 7.6 of the engine capability system design, which requires a
domestication report to name "the host codon frequency of both" the original
and the proposed codon, and Appendix E, which says of codon usage: "Host codon
usage tables and the codon adaptation index are the basis for the synonymous
substitution preference in section 7.6. Name the table and the host."

THE DECISION, RECORDED. No host codon usage table ships with this build.
WP-02 could not source one (see `progress/WP-02.md`: "no host codon usage table
is bundled, a caller must source one") and WP-04 did not source one either: a
codon usage table is 64 frequencies per host, and section 3.3 constraint 1
forbids writing numbers down from memory. A fabricated frequency table is worse
than none, because it would make the domestication report look authoritative
while recommending the wrong codon.

What that means for section 7.6, in full:

1. The silent substitution search still runs and still works. It is not
   degraded. Every candidate it returns destroys the recognition site and
   preserves the amino acid, which is the part of section 7.6 that is a
   correctness requirement.
2. Codon choice falls back to the minimal silent edit: among the synonymous
   codons that destroy the site, the one differing from the original in the
   fewest nucleotide positions wins, ties broken by sort order so the result is
   deterministic (section 3.3 constraint 3). Section 7.6 names the minimal edit
   as the correct rule outside a coding sequence; it is used inside one too,
   as the rule that applies when the host preference is unavailable.
3. The host frequency comparison is reported as UNKNOWN with a reason, per
   section 3.3 constraint 4. It is never reported as a number and never
   silently omitted. `CodonFrequencyLookup.unavailable_reason` carries the text
   that reaches the user.

When a caller supplies a real table, through `HostCodonUsage`, the preference
is applied: among the minimal-edit candidates the one with the highest host
frequency wins, and both frequencies are reported with the table named. The
mechanism is implemented and tested, so sourcing a table later is a data
change, not a code change.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.core.sequence import STANDARD_CODE, GeneticCode

# The text a user sees in place of a host codon frequency when no table is
# available. Section 3.3 constraint 4: an unevaluable quantity is reported as
# UNKNOWN with a reason, never as a default value.
NO_TABLE_REASON: str = (
    "No host codon usage table is bundled with this build, so the host frequency of the original "
    "and proposed codons could not be compared. The substitution was chosen as the minimal silent "
    "edit that destroys the recognition site. Supply a host codon usage table, with its source and "
    "host named, to get the frequency comparison."
)


@dataclass(frozen=True)
class HostCodonUsage:
    """A host's codon usage table, supplied by a caller with its source.

    `frequencies` maps each codon to its relative usage within the synonymous
    family for its amino acid, so values for one amino acid sum to 1. That is
    the quantity section 7.6 means by "host codon frequency" and the quantity a
    codon adaptation index is built from.

    `host` and `citation` are both required and both non-empty, because
    Appendix E requires the table and the host to be named. A table that cannot
    say where it came from is refused at construction rather than used.
    """

    host: str
    citation: str
    frequencies: dict[str, float]
    code: GeneticCode = field(default=STANDARD_CODE)

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise ValueError("a host codon usage table must name its host")
        if not self.citation.strip():
            raise ValueError(
                f"host codon usage table for {self.host!r} has no citation; Appendix E requires "
                "the table and the host to be named"
            )
        if not self.frequencies:
            raise ValueError(f"host codon usage table for {self.host!r} is empty")
        normalised = {}
        for codon, value in self.frequencies.items():
            key = codon.strip().upper()
            if len(key) != 3 or any(base not in "ACGT" for base in key):
                raise ValueError(f"{key!r} is not a DNA codon")
            if value < 0:
                raise ValueError(f"codon frequency for {key} is negative")
            normalised[key] = float(value)
        object.__setattr__(self, "frequencies", normalised)

    def frequency(self, codon: str) -> float | None:
        """Relative usage of `codon` in its synonymous family, or None if absent."""
        return self.frequencies.get(codon.strip().upper())


# Host codon usage tables bundled with this build: none. See the module
# docstring for why, and `progress/WP-04.md` for the recorded decision.
BUNDLED_HOST_CODON_USAGE: dict[str, HostCodonUsage] = {}


@dataclass(frozen=True)
class CodonFrequencyLookup:
    """A codon frequency answer that can honestly be "unknown".

    `available` is False exactly when no table could be consulted, in which
    case `value` is None and `unavailable_reason` says why. A caller must not
    treat None as zero: a missing frequency is not a rare codon.
    """

    available: bool
    value: float | None = None
    table: str | None = None
    unavailable_reason: str | None = None


def lookup(usage: HostCodonUsage | None, codon: str) -> CodonFrequencyLookup:
    """Host frequency of one codon, or an explicit unknown with its reason."""
    if usage is None:
        return CodonFrequencyLookup(available=False, unavailable_reason=NO_TABLE_REASON)
    value = usage.frequency(codon)
    if value is None:
        return CodonFrequencyLookup(
            available=False,
            table=f"{usage.host} ({usage.citation})",
            unavailable_reason=(
                f"Codon {codon.upper()} is absent from the {usage.host} codon usage table supplied, "
                "so its host frequency could not be read."
            ),
        )
    return CodonFrequencyLookup(available=True, value=value, table=f"{usage.host} ({usage.citation})")


def get_host_codon_usage(host: str) -> HostCodonUsage:
    """Resolve a bundled host table by name, failing loudly when absent."""
    key = host.strip()
    if key not in BUNDLED_HOST_CODON_USAGE:
        raise KeyError(
            f"no codon usage table for host {host!r} is bundled with this build. None ships: see "
            "the note in codon_usage.py. Supply a HostCodonUsage with its host and citation."
        )
    return BUNDLED_HOST_CODON_USAGE[key]
