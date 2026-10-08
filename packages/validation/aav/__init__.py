"""Deterministic validation for AAV vector cassettes (section 6 of the system design).

Fourteen checks, the section 6.5 banded packaging limit, and the section 6.6
remediation engine. Every threshold lives in `constants` with its source in a
docstring, and nothing here touches a database, a network or a model.
"""

from .checks import CHECK_IDS, CHECK_LABELS, CHECKS, CheckContext
from .constants import (
    AAV_MIN_GENOME_BP,
    AAV_SC_HARD_LIMIT_BP,
    AAV_SC_SOFT_LIMIT_BP,
    AAV_SC_TARGET_BP,
    AAV_SS_HARD_LIMIT_BP,
    AAV_SS_SOFT_LIMIT_BP,
    AAV_SS_TARGET_BP,
    AAV_VALIDATOR_VERSION,
    CHECK_CITATIONS,
    DEFAULT_THRESHOLDS,
    ITR_IDENTITY_THRESHOLD,
    MAX_DIRECT_REPEAT_BP,
    MAX_HOMOPOLYMER_RUN,
    PINNED_THRESHOLD_FINGERPRINTS,
    AAVThresholds,
)
from .itr import (
    ItrMatch,
    ItrReference,
    UnknownSerotype,
    best_itr_match,
    internal_itr_motif_hits,
    orientation_of_pair,
    serotype_itr_references,
)
from .remediation import build_remediation, remediation_entries, render_remediation_message
from .validator import AAVValidator, build_validator

__all__ = [
    "AAVThresholds",
    "AAVValidator",
    "AAV_MIN_GENOME_BP",
    "AAV_SC_HARD_LIMIT_BP",
    "AAV_SC_SOFT_LIMIT_BP",
    "AAV_SC_TARGET_BP",
    "AAV_SS_HARD_LIMIT_BP",
    "AAV_SS_SOFT_LIMIT_BP",
    "AAV_SS_TARGET_BP",
    "AAV_VALIDATOR_VERSION",
    "CHECKS",
    "CHECK_CITATIONS",
    "CHECK_IDS",
    "CHECK_LABELS",
    "CheckContext",
    "DEFAULT_THRESHOLDS",
    "ITR_IDENTITY_THRESHOLD",
    "ItrMatch",
    "ItrReference",
    "MAX_DIRECT_REPEAT_BP",
    "MAX_HOMOPOLYMER_RUN",
    "PINNED_THRESHOLD_FINGERPRINTS",
    "UnknownSerotype",
    "best_itr_match",
    "build_remediation",
    "build_validator",
    "internal_itr_motif_hits",
    "orientation_of_pair",
    "remediation_entries",
    "render_remediation_message",
    "serotype_itr_references",
]
