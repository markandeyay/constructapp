"""Deterministic validation for the primer and assembly capability (section 7).

Source: section 7 of the engine capability system design. `constants` holds every
threshold with its source, `settings` resolves them against a request, `enzymes`
is the Appendix D Type IIS reference, `structure` is the section 7.4 secondary
structure scoring, `codon_usage` records the host codon table decision,
`domestication` is section 7.6, `checks` is the nineteen section 7.5 checks and
`validator` is the `CapabilityValidator` the registry resolves.

The nearest-neighbor melting temperature is not here: section 13.4 requires it to
live in a shared location, so it is `packages.core.sequence.tm`.
"""
