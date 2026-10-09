"""Route level glue for the section 11 pre-export provenance gate.

Specification section 11.1 asks for a screening step that runs on every design
before any export action, blocks a design whose sequence cannot be attributed,
and records the result. The gate itself lives in
`packages.application.screening` and is called through
`packages.application.export_screened_design`. This module is the thin layer that
lets a capability route call it without each route repeating the same handling.

Three deliberate choices, all of which follow from section 11.1 rather than from
convenience.

**A blocked export does not fail the request.** Section 11.1 blocks the EXPORT,
not the design. A researcher whose design carries an unattributable span needs to
see the validation report and the span, not an opaque server error, and a
provenance problem presented as a 500 looks like a fault in the tool rather than
a fact about the design. So the route still returns the design, the report and
everything else, and withholds only the exportable artifacts, with the gate's own
finding text saying why.

**The format is the caller's to state, not this module's to guess.** An AAV
cassette exports as a sequence record and an assembly order table exports as
CSV. Deriving one from an artifact's file extension would work until a capability
named an artifact differently, and would then mislabel an audit entry silently.
The route names its own format.

**Each route clears its own artifacts.** The three capabilities keep their
exports in three different shapes: a dict of rendered artifacts, a response model
field, a dict of named tables. A single clearing function would have to know all
three, so instead this module reports the decision and the route acts on it.
"""

from __future__ import annotations


from typing import Any, Mapping

from packages.application import export_screened_design
from packages.application.exports import SUPPORTED_EXPORT_FORMATS
from packages.application.screening import ExportBlocked, JsonlExportAuditLog

# The artifact keys that carry an orderable sequence record. Used only by the
# capabilities whose exports ARE sequence records, which is AAV today.
SEQUENCE_ARTIFACT_KEYS = frozenset(SUPPORTED_EXPORT_FORMATS)

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
    payloads: Mapping[str, str],
    *,
    export_format: str,
    validation_overall: Any = None,
) -> tuple[bool, str | None]:
    """Run the gate over the payloads a route is about to return.

    Returns `(allowed, reason)`. `reason` is None when the export is allowed and
    otherwise carries the gate's own text, which names the sequence, the
    coordinates and the offending bases.

    An audit entry is written for both outcomes, which is section 11.1 item 4.
    This function adds nothing to that record and interprets nothing: if the gate
    refuses, the refusal is reported as the gate phrased it.
    """
    screened = {
        name: payload
        for name, payload in payloads.items()
        if isinstance(payload, str) and payload
    }
    if not screened:
        # Nothing to screen. Not an approval, just nothing in scope: a design
        # that produced no artifact cannot have one withheld.
        return True, None

    try:
        export_screened_design(
            subject,
            format=export_format,
            payloads=screened,
            validation_overall=validation_overall,
            audit_log=audit_log(),
        )
    except ExportBlocked as blocked:
        record = getattr(blocked, "record", None)
        reasons = list(getattr(record, "blocked_reasons", None) or [])
        return False, " ".join(reasons) if reasons else str(blocked)
    return True, None


def sequence_payloads(artifacts: Mapping[str, Any]) -> tuple[dict[str, str], str | None]:
    """Pick the sequence record artifacts out of a capability's artifact dict.

    Returns the payloads and the format to record, or an empty dict and None when
    the design rendered no sequence record. Only for a capability whose exports
    are GenBank or FASTA records.
    """
    found = {
        name: payload
        for name, payload in artifacts.items()
        if name in SEQUENCE_ARTIFACT_KEYS and isinstance(payload, str) and payload
    }
    if not found:
        return {}, None
    export_format = next(
        (name for name in _FORMAT_PREFERENCE if name in found),
        sorted(found)[0],
    )
    return found, export_format


def mark_blocked(payload: dict[str, Any], reason: str) -> dict[str, Any]:
    """Record on a response that its export was refused, and why.

    Does not touch the artifacts: the caller clears whatever it holds, because
    only the caller knows the shape of its own exports.
    """
    payload["export_blocked"] = True
    payload["export_block_reason"] = reason
    return payload


def withhold_artifacts(payload: dict[str, Any], reason: str) -> dict[str, Any]:
    """Strip a `DesignResult.artifacts` dict from a response and say why.

    The shape this handles is `payload["result"]["artifacts"]`, which is the
    section 5.1 `DesignResult`. Everything else in the response is left
    untouched, so the caller still sees the design, the validation report and any
    capability specific views.
    """
    result = payload.get("result")
    if isinstance(result, dict):
        result["artifacts"] = {}
    return mark_blocked(payload, reason)
