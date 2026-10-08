"""The plasmid capability's adapter onto the shared capability contract.

`packages.validation.engine.ConstraintEngine` keeps deciding every plasmid
verdict. This package only reshapes its report into the section 5.1
`ValidationReport` of `CheckResult` objects, so the plasmid gold set runs
through the same multi-capability runner, and the same section 9.3 assertions,
as AAV, assembly and guide RNA.
"""

from .constants import CHECK_ID_BY_ENGINE_NAME, CHECK_IDS, VALIDATOR_VERSION
from .validator import PlasmidValidator, build_validator

__all__ = [
    "CHECK_IDS",
    "CHECK_ID_BY_ENGINE_NAME",
    "PlasmidValidator",
    "VALIDATOR_VERSION",
    "build_validator",
]
