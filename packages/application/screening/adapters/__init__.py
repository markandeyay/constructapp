"""Adapters that turn a capability's own design object into an `ExportSubject`.

Each capability already records a `provenance` list, but a list of source
tokens cannot say which base came from which source, and section 11.1 item 1 is
a claim about bases. An adapter supplies the missing structure by walking the
design and emitting one span per piece of sequence whose origin it can prove
from the design itself.

The rule every adapter follows, and the reason this package can be a gate
rather than a warning:

> An adapter emits a span only when the design proves where those bases came
> from. When it cannot, it emits nothing for that span. The uncovered span then
> blocks the export and is reported with its coordinates and its bases.

So an adapter never guesses, and a gap in an adapter shows up as a blocked
export naming the exact bases, not as a silent pass. Section 3.3 constraint 4.

Adapters live here rather than in the capability packages because section 13.1
gives each file one owning work package, and `packages/application/screening/`
is WP-08's. A capability that later wants to supply its own spans can do so by
building an `ExportSubject` directly.
"""

from __future__ import annotations

from typing import Any

from packages.core.schemas.capability import CapabilityKind

from ..attribution import ExportSubject, SequenceOrigin

#: A source token prefixed with one of these names a sequence the user supplied.
#: `user_input:<field name>` is the form the capability contract already uses
#: (see `packages/core/schemas/capability.py`, rule 5).
USER_INPUT_PREFIXES: tuple[str, ...] = ("user_input:",)

#: A source token prefixed with one of these names a record retrieved from the
#: corpus. A transgene resolver or a template lookup must use this form for its
#: sequence to be attributable; anything else leaves the span uncovered, which
#: blocks the export rather than passing it.
RETRIEVED_TEMPLATE_PREFIXES: tuple[str, ...] = ("retrieved_template:",)

#: A source token prefixed with this names a curated registry part. It is the
#: form `CassetteElement.attribution` already produces.
REGISTRY_PART_PREFIX = "part:"


class NoAttributionAdapter(LookupError):
    """Raised when no adapter can build a subject for a design object.

    Raised rather than returning an empty subject, so a capability that is not
    wired into the gate fails loudly at the call site instead of producing an
    export with no attribution behind it (section 3.3 constraint 4).
    """


def classify_source(source: str) -> SequenceOrigin | None:
    """The origin a source token declares, or None when it declares none.

    None is the honest answer for an unrecognised token, and an adapter that
    gets None emits no span, which blocks the export and names the bases. The
    recognised forms are deliberately few: a token has to say what it is.
    """
    text = (source or "").strip()
    if not text:
        return None
    if text.startswith(REGISTRY_PART_PREFIX) and text[len(REGISTRY_PART_PREFIX) :].strip():
        return SequenceOrigin.REGISTRY_PART
    for prefix in USER_INPUT_PREFIXES:
        if text.startswith(prefix) and text[len(prefix) :].strip():
            return SequenceOrigin.USER_INPUT
    for prefix in RETRIEVED_TEMPLATE_PREFIXES:
        if text.startswith(prefix) and text[len(prefix) :].strip():
            return SequenceOrigin.RETRIEVED_TEMPLATE
    return None


def subject_for_design(design: Any, **kwargs: Any) -> ExportSubject:
    """Build an `ExportSubject` for whichever capability `design` belongs to.

    Dispatch is on the design's own type, so no capability package has to
    register anything. Imports are local to keep this module importable
    without pulling in every capability.
    """
    from packages.core.schemas.aav import AAVDesign
    from packages.core.schemas.assembly import AssemblyDesign
    from packages.core.schemas.grna import GuideRNAResult

    if isinstance(design, AAVDesign):
        from .aav import aav_subject

        return aav_subject(design, **kwargs)
    if isinstance(design, AssemblyDesign):
        from .assembly import assembly_subject

        return assembly_subject(design, **kwargs)
    if isinstance(design, GuideRNAResult):
        from .grna import grna_subject

        return grna_subject(design, **kwargs)
    raise NoAttributionAdapter(
        f"no attribution adapter exists for {type(design).__name__}, so the bases of this design "
        "cannot be traced to a registry part, a retrieved template or the user's own input. "
        "Section 11.1 item 1 blocks an export that cannot be attributed. Write an adapter in "
        "packages/application/screening/adapters/ or build an ExportSubject directly."
    )


#: Capabilities an adapter exists for. A capability absent from this set cannot
#: pass the gate, and `progress/WP-08.md` records why for each one.
ADAPTED_CAPABILITIES = frozenset(
    {CapabilityKind.AAV, CapabilityKind.ASSEMBLY, CapabilityKind.GUIDE_RNA}
)

__all__ = [
    "ADAPTED_CAPABILITIES",
    "REGISTRY_PART_PREFIX",
    "RETRIEVED_TEMPLATE_PREFIXES",
    "USER_INPUT_PREFIXES",
    "NoAttributionAdapter",
    "classify_source",
    "subject_for_design",
]
