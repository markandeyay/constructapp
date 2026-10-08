"""Provenance and pre-export screening (section 11).

What this package implements, and only this:

1. The sequence provenance assertion (section 11.1 item 1). Every base of every
   exported sequence must be covered by a span naming a curated registry part,
   a retrieved template, the user's own supplied input, or a named rule. A
   design with an unattributable base is BLOCKED from export. A design whose
   attribution cannot be evaluated is UNKNOWN with a reason, and that blocks
   too (section 3.3 constraint 4).
2. The registry-only composition assertion (section 11.1 item 2). Every span
   claiming a curated part resolves in `data/parts` and reproduces that record
   base for base, so no element is synthesized de novo by this system.
3. The screening hook (section 11.1 item 3). A documented interface,
   `ScreeningBackend`, with its result recorded in the design's provenance. The
   backend is configurable. No screening backend ships with this build, which
   is open question Q8's recorded answer, so the default is
   `NoExternalScreeningBackend`: an explicitly named no-op whose result states
   that no external screening ran.
4. The export audit log (section 11.1 item 4). One entry per export, allowed or
   blocked, recording what was exported, when, the validator version, and the
   screening result.

The sentence section 11.2 permits about this package, and the only one that may
be quoted, is in `progress/WP-08.md`. No sequence here is examined by any
external screening service, because no backend is wired, and every record of
that fact says so in words rather than leaving it to be inferred.
"""

from __future__ import annotations

from .attribution import (
    REGISTRY_ORIGINS,
    AttributedSegment,
    AttributedSequence,
    ExportSubject,
    SequenceOrigin,
)
from .audit import (
    AUDIT_LOG_PATH_ENV,
    AUDIT_SCHEMA_VERSION,
    DEFAULT_AUDIT_LOG_PATH,
    ExportAuditEntry,
    ExportAuditLog,
    ExportedArtifact,
    ExportedSequence,
    InMemoryExportAuditLog,
    JsonlExportAuditLog,
    default_audit_log_path,
    sha256_hex,
)
from .backends import (
    NO_BACKEND_ID,
    NOT_SCREENED_OUTCOMES,
    BackendFinding,
    BackendOutcome,
    NoExternalScreeningBackend,
    ScreeningBackend,
    ScreeningBackendUnreachable,
    ScreeningResult,
    run_screening_backend,
)
from .composition import (
    CompositionAssertion,
    CompositionElement,
    assert_registry_only_composition,
)
from .gate import (
    DECISION_BLOCKED,
    DECISION_EXPORTED,
    DEFAULT_POLICY,
    ExportBlocked,
    ScreenedExport,
    ScreeningPolicy,
    ScreeningRecord,
    evaluate_export,
    screen_and_export,
    screen_design,
)
from .provenance import (
    PERMITTING_VERDICTS,
    AssertionVerdict,
    AttributionFinding,
    ProvenanceAssertion,
    assert_provenance,
)

__all__ = [
    "AUDIT_LOG_PATH_ENV",
    "AUDIT_SCHEMA_VERSION",
    "DECISION_BLOCKED",
    "DECISION_EXPORTED",
    "DEFAULT_AUDIT_LOG_PATH",
    "DEFAULT_POLICY",
    "NOT_SCREENED_OUTCOMES",
    "NO_BACKEND_ID",
    "PERMITTING_VERDICTS",
    "REGISTRY_ORIGINS",
    "AssertionVerdict",
    "AttributedSegment",
    "AttributedSequence",
    "AttributionFinding",
    "BackendFinding",
    "BackendOutcome",
    "CompositionAssertion",
    "CompositionElement",
    "ExportAuditEntry",
    "ExportAuditLog",
    "ExportBlocked",
    "ExportSubject",
    "ExportedArtifact",
    "ExportedSequence",
    "InMemoryExportAuditLog",
    "JsonlExportAuditLog",
    "NoExternalScreeningBackend",
    "ProvenanceAssertion",
    "ScreenedExport",
    "ScreeningBackend",
    "ScreeningBackendUnreachable",
    "ScreeningPolicy",
    "ScreeningRecord",
    "ScreeningResult",
    "SequenceOrigin",
    "assert_provenance",
    "assert_registry_only_composition",
    "default_audit_log_path",
    "evaluate_export",
    "run_screening_backend",
    "screen_and_export",
    "screen_design",
    "sha256_hex",
]
