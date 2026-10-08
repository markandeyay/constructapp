"""Resolved thresholds for one request: the cited defaults, with overrides applied.

Source: section 3.3 constraint 2 ("Every threshold is configurable") and
section 5.4 rule 3 ("Every threshold used appears in `parameters_used`").

`constants.py` holds the default for every threshold and the source of each.
`AssemblyThresholds` on the request holds a caller's overrides. This module is
the single place the two are combined, so there is exactly one answer to "what
was this verdict measured against", and `Settings.as_parameters` produces it in
the form `parameters_used` takes.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from packages.core.schemas.assembly import AssemblyRequest, AssemblyThresholds

from . import constants


@dataclass(frozen=True)
class Settings:
    """Every threshold, resolved. Field names match `constants.thresholds()` keys."""

    primer_tm_warn_tolerance_c: float
    primer_tm_fail_tolerance_c: float
    primer_pair_max_tm_delta_c: float
    primer_gc_min_fraction: float
    primer_gc_max_fraction: float
    primer_min_length_nt: int
    primer_max_length_nt: int
    primer_max_total_length_nt: int
    primer_three_prime_window_nt: int
    primer_three_prime_max_gc_in_window: int
    primer_max_homopolymer_run_nt: int
    hairpin_min_loop_nt: int
    hairpin_dg_warn_kcal_per_mol: float
    hairpin_three_prime_dg_fail_kcal_per_mol: float
    hairpin_window_stem_warn_bp: int
    hairpin_window_stem_three_prime_fail_bp: int
    three_prime_involvement_window_nt: int
    max_self_complementarity_any_bp: float
    max_self_complementarity_end_bp: float
    max_pair_complementarity_any_bp: float
    max_pair_complementarity_end_bp: float
    gibson_overlap_min_bp: int
    gibson_overlap_max_bp: int
    gibson_overlap_design_bp: int
    gibson_overlap_min_tm_c: float
    gibson_junction_max_shared_homology_bp: int
    golden_gate_primer_spacer_nt: int
    golden_gate_default_overhang_nt: int
    amplicon_min_bp: int
    amplicon_max_bp: int
    annealing_offset_below_min_tm_c: float
    annealing_min_c: float
    annealing_max_c: float

    def as_parameters(self) -> dict[str, Any]:
        """The thresholds, keyed as `constants.thresholds()` keys them."""
        return {field.name: getattr(self, field.name) for field in fields(self)}

    def overridden(self) -> dict[str, Any]:
        """Only the thresholds that differ from the cited default.

        Shown alongside the full set so a reader can see at a glance whether a
        verdict used the documented defaults or a caller's own numbers.
        """
        defaults = constants.thresholds()
        return {
            name: value
            for name, value in self.as_parameters().items()
            if name in defaults and defaults[name] != value
        }


DEFAULT_SETTINGS = Settings(**constants.thresholds())


def settings_for(request: AssemblyRequest | None = None) -> Settings:
    """Resolve thresholds for one request: defaults, with any overrides applied."""
    resolved = dict(constants.thresholds())
    overrides: AssemblyThresholds | None = request.thresholds if request is not None else None
    if overrides is not None:
        for name, value in overrides.model_dump(exclude_none=True).items():
            if name not in resolved:
                raise ValueError(f"{name!r} is not a known assembly threshold")
            resolved[name] = value
    settings = Settings(**resolved)
    if settings.primer_gc_min_fraction > settings.primer_gc_max_fraction:
        raise ValueError("primer_gc_min_fraction must not exceed primer_gc_max_fraction")
    if settings.primer_min_length_nt > settings.primer_max_length_nt:
        raise ValueError("primer_min_length_nt must not exceed primer_max_length_nt")
    if settings.gibson_overlap_min_bp > settings.gibson_overlap_max_bp:
        raise ValueError("gibson_overlap_min_bp must not exceed gibson_overlap_max_bp")
    if settings.amplicon_min_bp > settings.amplicon_max_bp:
        raise ValueError("amplicon_min_bp must not exceed amplicon_max_bp")
    return settings
