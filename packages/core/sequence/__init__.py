"""Shared sequence utilities (section 13.4 of the engine capability system design).

Reverse complement, GC content, genetic codes and ORF finding, sequence search
primitives and pairwise alignment, used by the primer, guide RNA and AAV
capabilities.

The nearest-neighbor Tm implementation (`tm`) is owned by WP-04, the primer and
assembly package, and lives here because section 13.4 requires WP-04 to place
it in a shared location from the start: WP-05 (guide RNA) may need it.
"""

from .align import (
    UNIT_COST_SCORING,
    Alignment,
    AlignmentScoring,
    edit_distance,
    global_align,
    global_identity,
    local_align,
)
from .codon import BACTERIAL_CODE, GENETIC_CODES, STANDARD_CODE, GeneticCode, Orf, find_orfs, translate
from .dna import (
    IUPAC_CODES,
    STRICT_ALPHABET,
    clean_sequence,
    complement,
    gc_content,
    gc_count,
    reverse_complement,
)
from .search import (
    Hit,
    Repeat,
    Run,
    direct_repeats,
    find_both_strands,
    find_exact,
    find_iupac,
    find_with_mismatches,
    hamming_distance,
    homopolymer_runs,
    matches_iupac,
)
from .tm import (
    GAS_CONSTANT_R,
    INITIATION_TERMINAL_AT,
    INITIATION_TERMINAL_GC,
    NEAREST_NEIGHBOR_PARAMETERS,
    SYMMETRY_CORRECTION,
    ThermodynamicResult,
    initiation_terms,
    is_self_complementary,
    melting_temperature,
    melting_temperature_detail,
    nearest_neighbor_stack,
    sodium_equivalent_mm,
)

__all__ = [
    "Alignment",
    "AlignmentScoring",
    "BACTERIAL_CODE",
    "GAS_CONSTANT_R",
    "GENETIC_CODES",
    "GeneticCode",
    "Hit",
    "INITIATION_TERMINAL_AT",
    "INITIATION_TERMINAL_GC",
    "IUPAC_CODES",
    "NEAREST_NEIGHBOR_PARAMETERS",
    "Orf",
    "Repeat",
    "Run",
    "STANDARD_CODE",
    "STRICT_ALPHABET",
    "SYMMETRY_CORRECTION",
    "ThermodynamicResult",
    "UNIT_COST_SCORING",
    "clean_sequence",
    "complement",
    "direct_repeats",
    "edit_distance",
    "find_both_strands",
    "find_exact",
    "find_iupac",
    "find_orfs",
    "find_with_mismatches",
    "gc_content",
    "gc_count",
    "global_align",
    "global_identity",
    "hamming_distance",
    "homopolymer_runs",
    "initiation_terms",
    "is_self_complementary",
    "local_align",
    "matches_iupac",
    "melting_temperature",
    "melting_temperature_detail",
    "nearest_neighbor_stack",
    "reverse_complement",
    "sodium_equivalent_mm",
    "translate",
]
