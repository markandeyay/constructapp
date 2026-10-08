"""AAV cassette composition and outputs (sections 6.7 and 6.8).

Composition, not generation: an AAV vector is a known set of parts in a known
order assembled under a length budget, so every base traces to a curated
registry record or to the user's own input (section 4.2).
"""

from .composer import AAVComposer, TransgeneResolver, TransgeneUnavailable, stable_design_id
from .designer import (
    ARTIFACT_FASTA,
    ARTIFACT_GENBANK,
    ARTIFACT_LENGTH_BUDGET,
    ARTIFACT_LINEAR_MAP,
    AAVDesignBundle,
    AAVDesigner,
)
from .export import to_fasta, to_genbank
from .layout import length_budget, linear_layout, linear_map_json, linear_map_payload

__all__ = [
    "AAVComposer",
    "AAVDesignBundle",
    "AAVDesigner",
    "ARTIFACT_FASTA",
    "ARTIFACT_GENBANK",
    "ARTIFACT_LENGTH_BUDGET",
    "ARTIFACT_LINEAR_MAP",
    "TransgeneResolver",
    "TransgeneUnavailable",
    "length_budget",
    "linear_layout",
    "linear_map_json",
    "linear_map_payload",
    "stable_design_id",
    "to_fasta",
    "to_genbank",
]
