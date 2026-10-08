"""Guide RNA composition (section 8 of the engine capability system design).

`GuideRNAGenerator` enumerates guides on both strands at the correct PAM
offset, scores them, searches the declared off-target space, validates them and
ranks them with the reasoning attached. `cloning_plan` produces the orderable
oligos for the chosen vector or for in-vitro transcription.
"""

from .cloning import annealed_oligo_pair, cloning_plan, ivt_oligo_pair
from .designer import (
    GuideRNAGenerator,
    build_generator,
    render_guide_table,
    render_oligo_table,
)

__all__ = [
    "GuideRNAGenerator",
    "annealed_oligo_pair",
    "build_generator",
    "cloning_plan",
    "ivt_oligo_pair",
    "render_guide_table",
    "render_oligo_table",
]
