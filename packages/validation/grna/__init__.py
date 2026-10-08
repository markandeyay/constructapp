"""Deterministic guide RNA validation (section 8 of the engine capability system design).

Public surface:

* `GuideRNAValidator` and `build_validator`: the section 5.3 validator.
* `enumerate_guides`: both-strand enumeration at the correct PAM offset (section 8.3).
* `score_on_target`: the published Rule Set 1 model and the labelled fallback
  heuristic, each carrying its own name, citation and validity domain (section 8.4).
* `search_off_targets` and `space_statement`: the declared off-target space, the
  published MIT specificity score, and the sentence that states the searched
  space verbatim (section 8.6).
* `DEFAULT_THRESHOLDS` and `GuideRNAThresholds`: every configurable threshold.
"""

from .checks import ALL_CHECKS, OFF_TARGET_CHECK_ID, SECTION_8_5_CHECK_IDS, build_context
from .constants import (
    DEFAULT_THRESHOLDS,
    THRESHOLD_FINGERPRINTS,
    VALIDATOR_VERSION,
    GuideRNAThresholds,
    HeuristicWeights,
    fingerprint_payload,
)
from .enumeration import EnumeratedGuide, enumerate_guides, resolve_placement, seed_positions
from .nuclease import NUCLEASES, NucleaseSpec, geometry_facts, get_nuclease
from .offtarget import (
    MIT_CITATION,
    MIT_DOMAIN,
    MIT_MODEL_NAME,
    mit_guide_specificity,
    mit_hit_score,
    search_off_targets,
    space_statement,
)
from .ontarget import (
    HEURISTIC_NAME,
    RULE_SET_1_CITATION,
    RULE_SET_1_DOMAIN,
    RULE_SET_1_NAME,
    heuristic_score,
    rule_set_1_logit,
    score_on_target,
)
from .selfcomp import longest_self_complementary_stem
from .validator import GuideRNAValidator, build_validator
from .vectors import CLONING_VECTORS, IVT_TEMPLATES, CloningVector, get_vector

__all__ = [
    "ALL_CHECKS",
    "CLONING_VECTORS",
    "CloningVector",
    "DEFAULT_THRESHOLDS",
    "EnumeratedGuide",
    "GuideRNAThresholds",
    "GuideRNAValidator",
    "HEURISTIC_NAME",
    "HeuristicWeights",
    "IVT_TEMPLATES",
    "MIT_CITATION",
    "MIT_DOMAIN",
    "MIT_MODEL_NAME",
    "NUCLEASES",
    "NucleaseSpec",
    "OFF_TARGET_CHECK_ID",
    "RULE_SET_1_CITATION",
    "RULE_SET_1_DOMAIN",
    "RULE_SET_1_NAME",
    "SECTION_8_5_CHECK_IDS",
    "THRESHOLD_FINGERPRINTS",
    "VALIDATOR_VERSION",
    "build_context",
    "build_validator",
    "enumerate_guides",
    "fingerprint_payload",
    "geometry_facts",
    "get_nuclease",
    "get_vector",
    "heuristic_score",
    "longest_self_complementary_stem",
    "mit_guide_specificity",
    "mit_hit_score",
    "resolve_placement",
    "rule_set_1_logit",
    "score_on_target",
    "search_off_targets",
    "seed_positions",
    "space_statement",
]
