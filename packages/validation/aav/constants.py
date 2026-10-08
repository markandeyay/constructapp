"""Configurable constants for the AAV vector designer.

Source of record: section 6.5 of the engine capability system design, plus the
primary literature named per constant. Section 3.3 constraint 1 forbids an
invented biological constant, and constraint 2 forbids hard coding a threshold
inline, so every number a check measures against lives here, carries its source
in a docstring, and is overridable through `AAVThresholds`.

Two things are worth stating plainly, because they are the questions section
15.4 says to expect:

* The packaging ceiling is a **band, not a number.** Labs genuinely disagree
  about the practical ceiling for recombinant AAV. Published figures for the
  point at which titer and genome integrity start to suffer range from about
  the wild-type size upward, and the point at which packaging effectively
  stops is reported differently again depending on serotype, production
  system and how truncated species are measured. Asserting one value would be
  overclaiming. Section 6.5 therefore defines three boundaries per modality,
  all configurable, and the validator reports which band a design lands in.
* The engine is deterministic. The biology it encodes is not settled. See the
  determinism row of section 16.

Every value below is also exposed through `AAVThresholds`, a frozen dataclass,
so a caller can override any single one without editing this module, and
`AAVThresholds.as_mapping()` is what lands in `DesignResult.parameters_used`
(section 5.4 rule 3).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

# ---------------------------------------------------------------------------
# Packaging capacity, single stranded (section 6.5)
# ---------------------------------------------------------------------------

AAV_SS_TARGET_BP = 4_700
"""Total recombinant genome length, 5' ITR start through 3' ITR end, inclusive.

At or under this value the packaging check passes (section 6.5 banding table).
The wild-type AAV2 genome is approximately 4,700 bp: the reference record this
registry draws its ITRs from, NC_001401.2, is 4,679 bp end to end, and the two
ITR features in it sit at 1..145 and 4535..4679. The capsid imposes a physical
ceiling near that size. Oversized genomes package with reduced efficiency and
produce truncated species, which means wasted production runs.

Source: section 6.5 of the system design, which fixes this value; corroborated
in repository by the length of NC_001401.2 recorded in data/parts/PROVENANCE.md.
Configurable through `AAVThresholds.ss_target_bp`.
"""

AAV_SS_SOFT_LIMIT_BP = 4_900
"""Over target, at or under this value: WARN (section 6.5 banding table).

In this band the cassette is expected to package, with reduced titer. The
message must state the overage in bp and that titer may be reduced.

Source: section 6.5 of the system design. Configurable through
`AAVThresholds.ss_soft_limit_bp`.
"""

AAV_SS_HARD_LIMIT_BP = 5_200
"""Over this value: FAIL (section 6.5 banding table).

Above this the design is treated as not packageable, and the message must carry
at least one specific element substitution computed from the part registry
(section 6.5, section 6.6).

Source: section 6.5 of the system design. Configurable through
`AAVThresholds.ss_hard_limit_bp`.
"""

# ---------------------------------------------------------------------------
# Packaging capacity, self complementary (section 6.5)
# ---------------------------------------------------------------------------

AAV_SC_TARGET_BP = 2_400
"""Self complementary target.

Self complementary AAV packages an inverted repeat genome that self anneals
into double stranded DNA, bypassing the rate limiting second strand synthesis
step. It expresses faster and at lower dose, but the genome is effectively
duplicated, which halves usable capacity (section 6.2).

Source: section 6.5 of the system design. Configurable through
`AAVThresholds.sc_target_bp`.
"""

AAV_SC_SOFT_LIMIT_BP = 2_500
"""Self complementary soft limit: over target and at or under this is a WARN.

Source: section 6.5 of the system design. Configurable through
`AAVThresholds.sc_soft_limit_bp`.
"""

AAV_SC_HARD_LIMIT_BP = 2_600
"""Self complementary hard limit: over this is a FAIL.

Source: section 6.5 of the system design. Configurable through
`AAVThresholds.sc_hard_limit_bp`.
"""

AAV_MIN_GENOME_BP = 2_000
"""Below this, packaging efficiency degrades and the empty capsid fraction rises.

Under-length genomes are reported as a WARN by `aav.minimum_genome_size`, never
as a failure: a short cassette still packages, it just packages less well, and
the fix (adding filler or a larger regulatory element) is a design choice the
user makes.

Source: section 6.5 of the system design. Configurable through
`AAVThresholds.min_genome_bp`.
"""

# ---------------------------------------------------------------------------
# Structural thresholds (section 6.5)
# ---------------------------------------------------------------------------

ITR_IDENTITY_THRESHOLD = 0.95
"""Fraction match required between an ITR in the design and a serotype reference.

Applied by `aav.itr_present_both` to each ITR separately, against the ITR
references of the requested serotype in the part registry, in both
orientations. The best match is taken, because which reference record an ITR
copy derives from is not a design error; its orientation relative to the other
ITR is, and that is check 3's job.

It is also reused by `aav.itr_orientation` for the short D element window, so
there is one identity threshold in the capability rather than two.

Source: section 6.5 of the system design. Configurable through
`AAVThresholds.itr_identity_threshold`.
"""

MAX_DIRECT_REPEAT_BP = 20
"""Longest direct repeat tolerated inside the cassette.

A direct repeat longer than this is reported by `aav.internal_repeats` as a
WARN: homologous stretches in the same orientation are substrates for
recombination during vector production, which yields deleted species.

This is a WARN and not a FAIL on purpose. Real, widely used elements carry
repeats above it. In this registry the 21 bp sequence ACGGTAAATGGCCCGCCTGGC
occurs twice inside promoter.cmv, twice inside promoter.cag and twice inside
promoter.cbh, because all three contain the repeated CMV enhancer motif. Those
are standard parts, not mistakes, which is exactly the section 3.4 Tier B case:
surfaced and explained, not failed.

The check scopes itself to the region between the two ITRs. The two AAV2
reference ITRs share their 125 bp hairpin core verbatim, so every correct
cassette contains that core as an exact direct repeat; see
`check_internal_repeats` for why counting it would make the check useless.

Source: section 6.5 of the system design. Configurable through
`AAVThresholds.max_direct_repeat_bp`.
"""

MAX_HOMOPOLYMER_RUN = 8
"""Longest single base run tolerated inside the cassette.

A longer run is reported by `aav.homopolymer_runs` as a WARN: long
homopolymers destabilise synthesis and replication and are a common cause of
sequencing and assembly artifacts.

Also a WARN and not a FAIL for the same Tier B reason: promoter.cag carries a
14 bp G run and promoter.cbh a 16 bp G run in their GC rich cores, and both are
standard parts.

Source: section 6.5 of the system design. Configurable through
`AAVThresholds.max_homopolymer_run`.
"""

# ---------------------------------------------------------------------------
# ITR orientation, derived from the registry rather than asserted
# ---------------------------------------------------------------------------

ITR_D_ELEMENT_BP = 20
"""Length of the D element window used to decide ITR orientation.

The AAV2 ITR is 145 nt and has the structure A, B, B', C, C', A', D. The A
through A' part is the palindromic hairpin; the D sequence is about 20 nt and
is present at only one end of each ITR, the end that faces the transgene. That
asymmetry is what makes orientation decidable.

This constant is a window length, not a biological assertion, and it is
verified inside the repository rather than taken on trust. For the AAV2 ITR
pair in data/parts, the reverse complement of the last 20 nt of
itr.aav2_itr_left is exactly the first 20 nt of itr.aav2_itr_right
(CTCCATCACTAGGGGTTCCT and AGGAACCCCTAGTGATGGAG). The relation in fact holds
exactly out to at least 25 nt, so the precise value is not load bearing. A test
in tests/aav asserts it, and `serotype_itr_references` refuses to use the D
anchor for a serotype where it does not hold.

Literature on the ITR terminal repeat structure: Srivastava and colleagues,
Journal of Virology 1983, 45:555-564 (doi:10.1128/JVI.45.2.555-564.1983), the
record cited by both ITR parts in data/parts/PROVENANCE.md.

Configurable through `AAVThresholds.itr_d_element_bp`.
"""

ITR_ORIENTATION_MARGIN = 0.05
"""Separation required before the fallback orientation test will call a verdict.

`aav.itr_orientation` prefers the D element anchor above, which is exact. When
the D element cannot be located in one of the ITRs (a truncated ITR, for
example), the fallback compares two identities: the 5' ITR against the reverse
complement of the 3' ITR (the inverted arrangement) and against the 3' ITR as
written (the tandem arrangement). The larger wins, but only if it wins by at
least this margin; otherwise the check returns UNKNOWN with a reason rather
than guessing (section 3.3 constraint 4).

This is a method parameter, not a biological constant, and the default is set
from measurements on the registry itself:

* AAV2 left ITR against the reverse complement of the right ITR: 0.878
  identity. Against the right ITR as written: 0.758. Separation 0.121. The
  first figure is not 1.000 because the left ITR reads core plus D and the
  right reads reverse complement of D plus the same core, and the 125 bp
  hairpin core is only 85.9 percent identical to its own reverse complement
  (the flip and flop arrangements of the B and C arms).
* The commoner plasmid layout, where both ITRs are the same 145 bp sequence
  with one reverse complemented, gives 1.000 against 0.655. Separation 0.345.

0.05 sits well below both separations while still refusing to call a coin flip.
Configurable through `AAVThresholds.itr_orientation_margin`.
"""

ITR_INTERNAL_MOTIF_BP = 20
"""Window length for `aav.itr_internal_sites`.

The check asks whether any stretch of this length taken from a serotype ITR
reference also occurs inside the cassette, between the two ITRs, on either
strand. An internal ITR copy is a substrate for aberrant resolution and
truncated genomes during production.

This is a method parameter, not a biological constant: it sets how long a
shared stretch has to be before it counts, and the motif set itself is taken
from the ITR reference sequences in the part registry, so no ITR motif is
written into this module and nothing is invented. The window is set equal to
`MAX_DIRECT_REPEAT_BP` so that the two homology based checks in this capability
use one homology length rather than two unrelated ones.

Configurable through `AAVThresholds.itr_internal_motif_bp`.
"""

# ---------------------------------------------------------------------------
# Translation initiation context (section 6.4 check 11)
# ---------------------------------------------------------------------------

KOZAK_CONSENSUS_MOTIF = "GCCRCCATGG"
"""The vertebrate translation initiation consensus, written in IUPAC codes.

Positions, numbering the A of the initiator ATG as +1: G C C R C C A T G G
covers -6 through +4. `R` is a purine, A or G.

The two positions that matter most are a purine at -3 and a G at +4; a context
with both is strong, a context with one is adequate, and a context with
neither initiates poorly and allows leaky scanning past the start codon.
`aav.kozak_context` scores those two positions and reports the full consensus
match separately.

Source: Kozak, "An analysis of 5'-noncoding sequences from 699 vertebrate
messenger RNAs", Nucleic Acids Research 1987, 15:8125-8148
(doi:10.1093/nar/15.20.8125), the paper that defined this consensus and the
-3 and +4 hierarchy.

Configurable through `AAVThresholds.kozak_consensus_motif`.
"""

KOZAK_MINUS3_PURINES = ("A", "G")
"""The bases accepted at position -3 of the initiation context.

A purine, per the Kozak 1987 consensus cited on `KOZAK_CONSENSUS_MOTIF`.
Configurable through `AAVThresholds.kozak_minus3_purines`.
"""

KOZAK_PLUS4_BASE = "G"
"""The base accepted at position +4, the first base after the initiator ATG.

Per the Kozak 1987 consensus cited on `KOZAK_CONSENSUS_MOTIF`. Configurable
through `AAVThresholds.kozak_plus4_base`.
"""

# The three constants below describe the element the composer WRITES when it
# designs an initiation context from scratch. They are a generation choice, not
# a validation bound, so they are deliberately NOT mirrored as `AAVThresholds`
# fields and are NOT in `AAVThresholds.as_mapping`: the check's accept/reject
# bars above are unchanged by them.

KOZAK_PREFERRED_MINUS3 = "A"
"""The purine written at -3 when an initiation context is designed from scratch.

The analysis cited on `KOZAK_CONSENSUS_MOTIF` (Kozak 1987) finds A the commoner
of the two purines at -3. `aav.kozak_context` accepts either purine, so this
constant only chooses which one to WRITE and moves no threshold; the check's own
PASS message already says so: "A and G both satisfy it, so this check accepts
either and the threshold is the same for both, but A is the commoner of the two
in the cited analysis."
"""

KOZAK_UPSTREAM_ELEMENT = KOZAK_CONSENSUS_MOTIF[:6].replace("R", KOZAK_PREFERRED_MINUS3)
"""Positions -6 through -1 of the cited consensus, with R set to the preferred purine.

Its length, 6 bp, is the extent of the 5' portion of the motif, not a number
chosen here. Source: Kozak 1987, cited on `KOZAK_CONSENSUS_MOTIF`. It is derived
from `KOZAK_CONSENSUS_MOTIF` by slicing so the value can never drift from the
cited motif.
"""

KOZAK_ELEMENT_SOURCE = "published_rule:kozak_1987"
"""Provenance token of the composed Kozak element.

This is the WP-08 `published_rule` origin (section 11.1 item 1's fourth origin):
the bases come from a published rule, not from a registry part, a retrieved
record or user input. The rule is Kozak 1987, cited on `KOZAK_CONSENSUS_MOTIF`.
"""

KOZAK_ELEMENT_RULE = (
    f"Kozak 1987 vertebrate translation initiation consensus, positions -6 to -1 of "
    f"{KOZAK_CONSENSUS_MOTIF} with the purine at -3 instantiated as {KOZAK_PREFERRED_MINUS3} "
    f"(Nucleic Acids Research 1987, 15:8125-8148, doi:10.1093/nar/15.20.8125)"
)
"""Human readable statement of the rule that produced `KOZAK_UPSTREAM_ELEMENT`.

Built by interpolation from `KOZAK_CONSENSUS_MOTIF` and `KOZAK_PREFERRED_MINUS3`
so it cannot drift from them. Source: Kozak 1987, cited on
`KOZAK_CONSENSUS_MOTIF`.
"""

# ---------------------------------------------------------------------------
# Polyadenylation signal recognition (section 6.4 check 12)
# ---------------------------------------------------------------------------

POLYA_SIGNAL_MOTIFS = ("AATAAA", "ATTAAA")
"""Hexamers accepted as a functional polyadenylation signal.

`aav.polya_present_functional` FAILs when no polyA element is present at all
and WARNs when an element is present but carries none of these hexamers, which
is the section 6.4 distinction between a functional signal and a mere
annotation.

AATAAA is the canonical signal: Proudfoot and Brownlee, "3' non-coding region
sequences in eukaryotic messenger RNA", Nature 1976, 263:211-214. ATTAAA is the
commonest single base variant in human genes: Beaudoing and colleagues,
"Patterns of variant polyadenylation signal usage in human genes", Genome
Research 2000, 10:1001-1010.

Verified in repository rather than taken on trust: AATAAA occurs at position 91
of polya.bgh and at positions 32 and 61 of polya.sv40 (1-based), the two
GenBank sourced polyA records in data/parts. A test in tests/aav asserts this,
so a registry edit that broke recognition would be caught.

Configurable through `AAVThresholds.polya_signal_motifs`.
"""

# ---------------------------------------------------------------------------
# Promoter and tissue compatibility (section 6.4 check 8)
# ---------------------------------------------------------------------------

TISSUE_COMPATIBILITY: dict[str, frozenset[str]] = {
    "cns_neuron": frozenset({"cns_neuron", "ubiquitous"}),
    "cns_astrocyte": frozenset({"cns_astrocyte", "ubiquitous"}),
    "retina": frozenset({"retina", "ubiquitous"}),
    "liver": frozenset({"liver", "ubiquitous"}),
    "muscle": frozenset({"muscle", "ubiquitous"}),
    "cardiac": frozenset({"cardiac", "ubiquitous"}),
    "ubiquitous": frozenset({"ubiquitous"}),
}
"""Which promoter `tissue_specificity` values are accepted for each target tissue.

A rules table, not settled science (see the determinism row of section 16). The
default is deliberately strict: a promoter is compatible with a target only if
it is annotated for exactly that target or is annotated ubiquitous. Anything
else is a WARN from `aav.promoter_tissue_match`, with a message naming both
annotations and what to substitute.

Strictness is cheap here because the severity on violation is WARN, never FAIL
(section 6.4 check 8). Surfacing "hSyn1 is annotated cns_neuron and the target
is retina" is useful even though hSyn1 does drive expression in retinal
neurons: the user is the one who knows whether the intended cell type is a
neuron. Widening the table is a one line override rather than a code change.

Note the `ubiquitous` row: a tissue specific promoter in a vector whose stated
target is ubiquitous is also a WARN, because it restricts expression below
what was asked for.

Keys and values use the section 6.3 `target_tissue` vocabulary, which the part
registry also uses for `tissue_specificity`.

Configurable through `AAVThresholds.tissue_compatibility`.
"""

# ---------------------------------------------------------------------------
# Remediation engine (section 6.6)
# ---------------------------------------------------------------------------

REMEDIATION_MAX_PLANS = 5
"""How many ranked remediation plans to report.

A presentation limit, not a biological one. Section 6.6 asks for the minimum
set of substitutions that closes the overage and the worked example also offers
alternatives, so the engine reports the best plan plus the next few.
Configurable through `AAVThresholds.remediation_max_plans`.
"""

REMEDIATION_MAX_CHANGES = 3
"""Largest number of simultaneous element changes the engine will propose.

A search bound, not a biological one. Beyond three changes the cassette is a
different design and the honest answer is the section 6.6 step 5 one: a shorter
transgene variant or a dual vector approach. Configurable through
`AAVThresholds.remediation_max_changes`.
"""

# ---------------------------------------------------------------------------
# Validator version and the threshold pin table (section 5.4 rule 4)
# ---------------------------------------------------------------------------

AAV_VALIDATOR_VERSION = "aav-1.1.0"
"""Version stamped onto every `ValidationReport` this capability produces.

Section 5.4 rule 4: bump this whenever any threshold above changes, so a stored
report stays interpretable. `PINNED_THRESHOLD_FINGERPRINTS` makes that
mechanical: a threshold edited without a bump changes the fingerprint and the
test in tests/aav/test_constants.py fails.

A severity change is the same kind of event and gets the same treatment, because
a stored report is only interpretable if the verdict it carries can be read back
against the rule that produced it. 1.1.0 is that case: no threshold value moved,
so the fingerprint is unchanged from 1.0.0, but `aav.itr_orientation` now reports
WARN rather than PASS for an inverted ITR pair whose D sequences face the
cassette ends instead of the transgene. A report stamped aav-1.0.0 may carry a
PASS on that check for a design that aav-1.1.0 warns on, and the two entries in
the pin table sharing one fingerprint record exactly that: the measurements did
not change, the verdict did.
"""

PINNED_THRESHOLD_FINGERPRINTS: dict[str, str] = {
    "aav-1.0.0": "26088420ff7718304ff861f7e334bb2d6731f964fbc22d38ca2d0978bd2927b7",
    "aav-1.1.0": "26088420ff7718304ff861f7e334bb2d6731f964fbc22d38ca2d0978bd2927b7",
}
"""Each released `validator_version` mapped to the fingerprint it shipped with.

Maintained with `packages.core.schemas.capability.thresholds_fingerprint` over
`AAVThresholds().as_mapping()`. Adding a threshold, removing one or changing a
value all change the fingerprint, which is the point. Two versions may share a
fingerprint, which says that the thresholds were untouched and something else,
a severity or a message, changed instead.
"""


@dataclass(frozen=True)
class AAVThresholds:
    """Every AAV threshold in one overridable object (section 3.3 constraint 2).

    Defaults are the module constants above, each with its source in its own
    docstring. Construct with keyword overrides to change one value, or call
    `for_request` to apply the section 6.3 `packaging_limit_bp` override.
    """

    ss_target_bp: int = AAV_SS_TARGET_BP
    ss_soft_limit_bp: int = AAV_SS_SOFT_LIMIT_BP
    ss_hard_limit_bp: int = AAV_SS_HARD_LIMIT_BP
    sc_target_bp: int = AAV_SC_TARGET_BP
    sc_soft_limit_bp: int = AAV_SC_SOFT_LIMIT_BP
    sc_hard_limit_bp: int = AAV_SC_HARD_LIMIT_BP
    min_genome_bp: int = AAV_MIN_GENOME_BP
    itr_identity_threshold: float = ITR_IDENTITY_THRESHOLD
    max_direct_repeat_bp: int = MAX_DIRECT_REPEAT_BP
    max_homopolymer_run: int = MAX_HOMOPOLYMER_RUN
    itr_d_element_bp: int = ITR_D_ELEMENT_BP
    itr_orientation_margin: float = ITR_ORIENTATION_MARGIN
    itr_internal_motif_bp: int = ITR_INTERNAL_MOTIF_BP
    kozak_consensus_motif: str = KOZAK_CONSENSUS_MOTIF
    kozak_minus3_purines: tuple[str, ...] = KOZAK_MINUS3_PURINES
    kozak_plus4_base: str = KOZAK_PLUS4_BASE
    # KOZAK_PREFERRED_MINUS3, KOZAK_UPSTREAM_ELEMENT, KOZAK_ELEMENT_SOURCE and
    # KOZAK_ELEMENT_RULE are deliberately not fields here and not in as_mapping:
    # they describe the element the composer writes, a generation choice, not a
    # validation bound, so they move no threshold and no fingerprint.
    polya_signal_motifs: tuple[str, ...] = POLYA_SIGNAL_MOTIFS
    tissue_compatibility: dict[str, frozenset[str]] = None  # type: ignore[assignment]
    remediation_max_plans: int = REMEDIATION_MAX_PLANS
    remediation_max_changes: int = REMEDIATION_MAX_CHANGES

    def __post_init__(self) -> None:
        if self.tissue_compatibility is None:
            object.__setattr__(self, "tissue_compatibility", dict(TISSUE_COMPATIBILITY))
        for name in ("ss_target_bp", "ss_soft_limit_bp", "ss_hard_limit_bp"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not self.ss_target_bp <= self.ss_soft_limit_bp <= self.ss_hard_limit_bp:
            raise ValueError("single stranded band must satisfy target <= soft limit <= hard limit")
        if not self.sc_target_bp <= self.sc_soft_limit_bp <= self.sc_hard_limit_bp:
            raise ValueError("self complementary band must satisfy target <= soft limit <= hard limit")
        if not 0.0 < self.itr_identity_threshold <= 1.0:
            raise ValueError("itr_identity_threshold must be in (0, 1]")

    # -- band selection -----------------------------------------------------

    def band(self, self_complementary: bool) -> tuple[int, int, int]:
        """The (target, soft limit, hard limit) that applies to one modality."""
        if self_complementary:
            return self.sc_target_bp, self.sc_soft_limit_bp, self.sc_hard_limit_bp
        return self.ss_target_bp, self.ss_soft_limit_bp, self.ss_hard_limit_bp

    def with_packaging_limit(self, limit_bp: int | None, self_complementary: bool) -> AAVThresholds:
        """Apply the section 6.3 `packaging_limit_bp` override.

        The override replaces the *target* of the applicable band. The soft and
        hard limits move with it, keeping the default band widths, so a user
        who raises the target to 4,900 bp gets 5,100 bp and 5,400 bp rather
        than a target above its own soft limit. The widths are taken from the
        defaults of this object, which is what makes the behaviour predictable
        and reportable in `parameters_used`.
        """
        if limit_bp is None:
            return self
        if limit_bp <= 0:
            raise ValueError("packaging_limit_bp must be positive")
        if self_complementary:
            soft_width = self.sc_soft_limit_bp - self.sc_target_bp
            hard_width = self.sc_hard_limit_bp - self.sc_target_bp
            return replace(
                self,
                sc_target_bp=limit_bp,
                sc_soft_limit_bp=limit_bp + soft_width,
                sc_hard_limit_bp=limit_bp + hard_width,
            )
        soft_width = self.ss_soft_limit_bp - self.ss_target_bp
        hard_width = self.ss_hard_limit_bp - self.ss_target_bp
        return replace(
            self,
            ss_target_bp=limit_bp,
            ss_soft_limit_bp=limit_bp + soft_width,
            ss_hard_limit_bp=limit_bp + hard_width,
        )

    # -- reporting ----------------------------------------------------------

    def as_mapping(self) -> dict[str, Any]:
        """Every threshold as a plain JSON friendly mapping.

        This is what goes into `DesignResult.parameters_used` (section 5.4 rule
        3) and what `thresholds_fingerprint` hashes (rule 4), so it must cover
        every value a verdict was measured against, with nothing left out.
        """
        return {
            "ss_target_bp": self.ss_target_bp,
            "ss_soft_limit_bp": self.ss_soft_limit_bp,
            "ss_hard_limit_bp": self.ss_hard_limit_bp,
            "sc_target_bp": self.sc_target_bp,
            "sc_soft_limit_bp": self.sc_soft_limit_bp,
            "sc_hard_limit_bp": self.sc_hard_limit_bp,
            "min_genome_bp": self.min_genome_bp,
            "itr_identity_threshold": self.itr_identity_threshold,
            "max_direct_repeat_bp": self.max_direct_repeat_bp,
            "max_homopolymer_run": self.max_homopolymer_run,
            "itr_d_element_bp": self.itr_d_element_bp,
            "itr_orientation_margin": self.itr_orientation_margin,
            "itr_internal_motif_bp": self.itr_internal_motif_bp,
            "kozak_consensus_motif": self.kozak_consensus_motif,
            "kozak_minus3_purines": list(self.kozak_minus3_purines),
            "kozak_plus4_base": self.kozak_plus4_base,
            "polya_signal_motifs": list(self.polya_signal_motifs),
            "tissue_compatibility": {
                key: sorted(value) for key, value in sorted(self.tissue_compatibility.items())
            },
            "remediation_max_plans": self.remediation_max_plans,
            "remediation_max_changes": self.remediation_max_changes,
        }


DEFAULT_THRESHOLDS = AAVThresholds()
"""The default threshold set, built from the module constants above."""


# Citations attached to each check result, so the UI can show why a threshold
# exists (`CheckResult.citation`, section 5.1). Each entry names the section of
# the system design that fixes the rule and, where the rule rests on primary
# literature, that literature.
CHECK_CITATIONS: dict[str, str] = {
    "aav.packaging_limit": (
        "System design section 6.5 (banded packaging limit). Wild-type AAV2 genome "
        "NC_001401.2 is 4,679 bp; the capsid ceiling sits near that size. The band exists "
        "because the practical ceiling is contested in the literature."
    ),
    "aav.itr_present_both": (
        "System design section 6.2 (ITRs are required in cis for replication and packaging) "
        "and section 6.5 (ITR_IDENTITY_THRESHOLD). Reference ITRs: NC_001401.2 positions "
        "1..145 and 4535..4679, see data/parts/PROVENANCE.md."
    ),
    "aav.itr_orientation": (
        "System design section 6.4 check 3. ITR terminal repeat structure including the D "
        "element: Srivastava and colleagues, Journal of Virology 1983, 45:555-564 "
        "(doi:10.1128/JVI.45.2.555-564.1983)."
    ),
    "aav.required_elements": "System design section 6.2 (cassette order) and section 6.4 check 4.",
    "aav.element_order": "System design section 6.2 functional order and section 6.4 check 5.",
    "aav.cds_integrity": (
        "System design section 6.4 check 6. Standard genetic code, NCBI translation table 1, "
        "as implemented in packages/core/sequence/codon.py."
    ),
    "aav.sc_capacity": (
        "System design section 6.2 (self complementary genomes are effectively duplicated, "
        "halving usable capacity) and section 6.5 self complementary band."
    ),
    "aav.promoter_tissue_match": (
        "System design section 6.2 (promoter choice encodes tissue specificity) and section "
        "6.4 check 8. Promoter annotations from data/parts, each with its own citation."
    ),
    "aav.internal_repeats": (
        "System design section 6.4 check 9 and MAX_DIRECT_REPEAT_BP in section 6.5. Direct "
        "repeats are recombination substrates during vector production."
    ),
    "aav.homopolymer_runs": (
        "System design section 6.4 check 10 and MAX_HOMOPOLYMER_RUN in section 6.5. Long "
        "homopolymers destabilise synthesis and replication."
    ),
    "aav.kozak_context": (
        "System design section 6.4 check 11. Initiation consensus and the -3 and +4 "
        "hierarchy: Kozak, Nucleic Acids Research 1987, 15:8125-8148 "
        "(doi:10.1093/nar/15.20.8125)."
    ),
    "aav.polya_present_functional": (
        "System design section 6.4 check 12. AATAAA: Proudfoot and Brownlee, Nature 1976, "
        "263:211-214. ATTAAA variant usage: Beaudoing and colleagues, Genome Research 2000, "
        "10:1001-1010."
    ),
    "aav.minimum_genome_size": (
        "System design section 6.4 check 13 and AAV_MIN_GENOME_BP in section 6.5. Below the "
        "minimum, packaging efficiency degrades and the empty capsid fraction rises."
    ),
    "aav.itr_internal_sites": (
        "System design section 6.4 check 14. Motif set is derived from the serotype ITR "
        "reference records in data/parts, not written into code."
    ),
}
