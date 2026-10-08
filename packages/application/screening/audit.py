"""The export audit log (section 11.1 item 4).

"Every export records what was exported, when, the validator version, and the
screening result."

One entry is written for every call of the export gate, whether the export was
allowed or blocked. A blocked export is the entry most worth having, so there
is no path through the gate that writes nothing.

The four required fields, and where each lives on `ExportAuditEntry`:

* what was exported: `capability`, `design_id`, `export_format`, `artifacts`
  (one row per artifact with its byte length and SHA-256), and `sequences` (one
  row per exported sequence with its length and SHA-256). The digests are what
  make the entry evidential: they tie the entry to the exact bases that left
  the system without storing the sequence itself.
* when: `recorded_at`, UTC, written by an injected clock so a test can pin it.
* the validator version: `validator_version`, copied from the design's
  `ValidationReport.validator_version`, with `validation_overall` beside it.
* the screening result: `screening`, the whole `ScreeningResult`, plus
  `external_screening_ran` as a plain boolean so that nobody has to interpret
  an outcome string to find out whether anything was screened.

`provenance_assertion` and `composition_assertion` are recorded too, since
those are the two assertions the export was actually gated on.

Section 16, the row that governs what may be claimed about section 11: an
entry describes what ran. When no external
screening backend is configured, `external_screening_ran` is false, the outcome
is `no_external_screening_ran`, and `screening.detail` says so in a sentence. No
field in this entry asserts anything about the sequence itself.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

from pydantic import Field

from packages.core.schemas.capability import CapabilityKind, CapabilityModel, Severity

from .backends import ScreeningResult
from .composition import CompositionAssertion
from .provenance import ProvenanceAssertion

#: Bumped when the entry shape changes, so a stored log stays interpretable.
AUDIT_SCHEMA_VERSION = "1"

#: Environment variable naming the audit log file. Section 3.3 constraint 2:
#: configurable, with a documented default.
AUDIT_LOG_PATH_ENV = "CONSTRUCT_EXPORT_AUDIT_LOG"

#: Default audit log location, relative to the repository root.
DEFAULT_AUDIT_LOG_PATH = Path("data") / "audit" / "export_audit.jsonl"


def utc_now() -> datetime:
    """The clock the log uses by default. Injected everywhere, so tests can pin it."""
    return datetime.now(timezone.utc)


def sha256_hex(payload: str) -> str:
    """SHA-256 of a payload, UTF-8 encoded. Deterministic and collision resistant enough to tie an entry to its bytes."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ExportedArtifact(CapabilityModel):
    """One artifact that left the system, identified without being stored."""

    name: str = Field(min_length=1)
    format: str = Field(min_length=1)
    bytes_written: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)


class ExportedSequence(CapabilityModel):
    """One exported sequence, identified without being stored."""

    name: str = Field(min_length=1)
    length_bp: int = Field(gt=0)
    sha256: str = Field(min_length=64, max_length=64)


class ExportAuditEntry(CapabilityModel):
    """One line of the export audit log.

    `decision` is `exported` or `blocked`, and `blocked_reasons` carries one
    sentence per reason when it is `blocked`. An entry is written in both
    cases.
    """

    schema_version: str = Field(default=AUDIT_SCHEMA_VERSION, min_length=1)
    recorded_at: datetime
    capability: CapabilityKind
    design_id: str = Field(min_length=1)
    export_format: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    blocked_reasons: list[str] = Field(default_factory=list)
    artifacts: list[ExportedArtifact] = Field(default_factory=list)
    sequences: list[ExportedSequence] = Field(default_factory=list)
    validator_version: str = Field(min_length=1)
    validation_overall: Severity | None = None
    screening: ScreeningResult
    external_screening_ran: bool
    provenance_assertion: ProvenanceAssertion
    composition_assertion: CompositionAssertion
    declared_provenance: list[str] = Field(default_factory=list)
    adapter: str = Field(min_length=1)

    def to_json_line(self) -> str:
        """One line of JSON, keys sorted, no newline. The on-disk form."""
        payload = self.model_dump(mode="json")
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


@runtime_checkable
class ExportAuditLog(Protocol):
    """A sink for audit entries. Append only: an entry is never rewritten."""

    def record(self, entry: ExportAuditEntry) -> None: ...

    def entries(self) -> list[ExportAuditEntry]: ...


class InMemoryExportAuditLog:
    """An audit log held in memory. Used by tests and by the synchronous local path."""

    def __init__(self) -> None:
        self._entries: list[ExportAuditEntry] = []

    def record(self, entry: ExportAuditEntry) -> None:
        self._entries.append(entry)

    def entries(self) -> list[ExportAuditEntry]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


class JsonlExportAuditLog:
    """An append-only JSON Lines audit log on disk.

    One JSON object per line, keys sorted so a diff of the file is readable.
    The file and its parent directory are created on first write. Appending
    rather than rewriting is the point: an audit log that can be edited in
    place is not an audit log.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_audit_log_path()

    def record(self, entry: ExportAuditEntry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(entry.to_json_line())
            handle.write("\n")

    def entries(self) -> list[ExportAuditEntry]:
        if not self.path.exists():
            return []
        out: list[ExportAuditEntry] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if text:
                    out.append(ExportAuditEntry.model_validate_json(text))
        return out


def default_audit_log_path() -> Path:
    """The configured audit log path, or the documented default."""
    configured = os.environ.get(AUDIT_LOG_PATH_ENV)
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / DEFAULT_AUDIT_LOG_PATH


def build_entry(
    *,
    capability: CapabilityKind,
    design_id: str,
    export_format: str,
    decision: str,
    blocked_reasons: list[str],
    artifacts: list[ExportedArtifact],
    sequences: list[ExportedSequence],
    validator_version: str,
    validation_overall: Severity | None,
    screening: ScreeningResult,
    provenance_assertion: ProvenanceAssertion,
    composition_assertion: CompositionAssertion,
    declared_provenance: list[str],
    adapter: str,
    now: Callable[[], datetime] = utc_now,
) -> ExportAuditEntry:
    """Assemble one entry. `external_screening_ran` is derived, never passed in."""
    return ExportAuditEntry(
        recorded_at=now(),
        capability=capability,
        design_id=design_id,
        export_format=export_format,
        decision=decision,
        blocked_reasons=blocked_reasons,
        artifacts=artifacts,
        sequences=sequences,
        validator_version=validator_version,
        validation_overall=validation_overall,
        screening=screening,
        external_screening_ran=screening.external_screening_ran,
        provenance_assertion=provenance_assertion,
        composition_assertion=composition_assertion,
        declared_provenance=declared_provenance,
        adapter=adapter,
    )
