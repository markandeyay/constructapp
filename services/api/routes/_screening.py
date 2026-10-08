"""Route level glue for the section 11 pre-export provenance gate.

Specification section 11.1 asks for a screening step that runs on every design
before any export action, blocks a design whose sequence cannot be attributed,
and records the result. The gate itself lives in
`packages.application.screening` and is called through
`packages.application.export_screened_design`. This module is the thin layer that
lets a capability route call it without each route repeating the same handling.

Two deliberate choices, both of which follow from section 11.1 rather than from
convenience.

**A blocked export does not fail the request.** Section 11.1 blocks the EXPORT,
not the design. A researcher whose cassette carries an unattributable span needs
to see the validation report and the span, not an opaque server error, and a
provenance problem presented as a 500 looks like a fault in the tool rather than
a fact about the design. So the route still returns the design, the report and
everything else, and withholds only the exportable artifacts, with the gate's own
finding text saying why.

**Only sequence bearing artifacts are gated.** The gate exists to stop
unattributable DNA being handed to someone who will order it. Artifacts that are
views of a design rather than orderable sequence, for example a length budget
table or a map rendering, are released or withheld with the rest but are not
themselves what the gate is reasoning about.
"""

from __future__ import annotations

from typing import Any, Mapping

from packages.application import export_screened_design
from packages.application.exports import SUPPORTED_EXPORT_FORMATS
from packages.application.screening import ExportBlocked, JsonlExportAuditLog

# The artifact keys that carry orderable DNA and that the gate can describe.
# `SUPPORTED_EXPORT_FORMATS` is the gate's own vocabulary, so an artifact is
# gated exactly when the gate has a name for what it is.
GATED_ARTIFACT_KEYS = frozenset(SUPPORTED_EXPORT_FORMATS)

# Preferred format to record in the audit entry when a design offers several.
_FORMAT_PREFERENCE = ("genbank", "fasta")


def audit_log() -> JsonlExportAuditLog:
    """The append-only log every served export decision is recorded in.

    Constructed per call rather than held as a module level singleton, because
    the log resolves `CONSTRUCT_EXPORT_AUDIT_LOG` when it is constructed. A
    singleton would freeze whatever the environment said at import time, which
    would silently ignore an operator pointing the log somewhere else and would
    make a test that redirects the log write into the real one.
    """
    return JsonlExportAuditLog()


def screen_export(
    subject: Any,
    artifacts: Mapping[str, str],
    *,
    validation_overall: Any = None,
) -> tuple[bool, str | None]:
    """Run the gate over a design's sequence bearing artifacts.

    Returns `(allowed, reason)`. `reason` is None when the export is allowed and
    otherwise carries the gate's own text, which names the sequence, the
    coordinates and the offending bases.

    An audit entry is written by the gate for both outcomes, which is section
    11.1 item 4. This function adds nothing to that record and interprets
    nothing: if the gate refuses, the refusal is reported as the gate phrased it.
    """
    sequence_artifacts = {
        name: payload
        for name, payload in artifacts.items()
        if name in GATED_ARTIFACT_KEYS and isinstance(payload, str) and payload
    }
    if not sequence_artifacts:
        # Nothing orderable to screen. Not an approval, just nothing in scope.
        return True, None

    export_format = next(
        (name for name in _FORMAT_PREFERENCE if name in sequence_artifacts),
        sorted(sequence_artifacts)[0],
    )
    try:
        export_screened_design(
            subject,
            format=export_format,
            payloads=sequence_artifacts,
            validation_overall=validation_overall,
            audit_log=audit_log(),
        )
    except ExportBlocked as blocked:
        record = getattr(blocked, "record", None)
        reasons = list(getattr(record, "blocked_reasons", None) or [])
        return False, " ".join(reasons) if reasons else str(blocked)
    return True, None


def withhold_artifacts(payload: dict[str, Any], reason: str) -> dict[str, Any]:
    """Strip the exportable artifacts from a response and say why.

    Everything else in the response is left untouched, so the caller still sees
    the design, the validation report and any capability specific views.
    """
    result = payload.get("result")
    if isinstance(result, dict):
        result["artifacts"] = {}
    payload["export_blocked"] = True
    payload["export_block_reason"] = reason
    return payload
