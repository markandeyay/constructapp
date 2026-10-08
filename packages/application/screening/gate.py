"""The pre-export gate: the step section 11.1 requires to run before any export.

One call does all four things section 11.1 asks for, in this order:

1. The sequence provenance assertion (item 1), over every exported sequence.
   `UNATTRIBUTED` and `UNKNOWN` both block. This is a gate, not a warning.
2. The registry-only composition assertion (item 2). `VIOLATED` and `UNKNOWN`
   both block.
3. The screening hook (item 3): the configured backend runs, its result is
   recorded, and the result is appended to the design's provenance.
4. The export audit log (item 4): one entry is written whether the export was
   allowed or blocked.

What is and is not configurable, deliberately. The two assertions are not: a
gate with an off switch is not a gate, and section 11.1 item 1 says blocked
without qualification. `ScreeningPolicy` covers only the backend decisions,
where a deployment genuinely has to choose: whether a backend's findings block,
and whether a configured backend that could not be reached blocks. Both default
to blocking, because section 3.3 constraint 4 says uncertainty is not a pass.

With no backend configured, which open question Q8 records as the state of this
build, the outcome is `no_external_screening_ran`, that never blocks, and the
export is gated entirely on the two assertions. That is exactly the claim
section 11.2 permits and nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Mapping

from pydantic import Field

from packages.core.part_registry import PartRecord
from packages.core.schemas.capability import CapabilityModel, DesignResult, Severity

from .attribution import ExportSubject
from .audit import (
    ExportAuditEntry,
    ExportAuditLog,
    ExportedArtifact,
    ExportedSequence,
    build_entry,
    sha256_hex,
    utc_now,
)
from .backends import (
    NoExternalScreeningBackend,
    ScreeningBackend,
    ScreeningResult,
    run_screening_backend,
)
from .composition import CompositionAssertion, assert_registry_only_composition
from .provenance import AssertionVerdict, ProvenanceAssertion, assert_provenance

DECISION_EXPORTED = "exported"
DECISION_BLOCKED = "blocked"


class ScreeningPolicy(CapabilityModel):
    """The configurable part of the gate, which is the backend decisions only.

    The provenance assertion and the composition assertion are not represented
    here on purpose. Section 11.1 item 1 blocks an unattributable design from
    export without qualification, so there is no flag that lets one through.
    """

    block_on_backend_findings: bool = True
    block_when_configured_backend_fails: bool = True


DEFAULT_POLICY = ScreeningPolicy()


class ScreeningRecord(CapabilityModel):
    """Everything the gate decided about one design, before the export happens.

    `provenance_entries` are the entries to append to the design's
    `DesignResult.provenance` (section 11.1 item 3). `record_in_design` does
    that, returning a copy.
    """

    design_id: str = Field(min_length=1)
    allowed: bool
    blocked_reasons: list[str] = Field(default_factory=list)
    provenance: ProvenanceAssertion
    composition: CompositionAssertion
    screening: ScreeningResult

    @property
    def provenance_entries(self) -> list[str]:
        """The provenance entries this screening run adds to the design.

        One entry for each of the three things that ran: the provenance
        assertion verdict, the composition assertion verdict, and the screening
        result. All three are recorded whether the export was allowed or not.

        Every rule the provenance assertion saw is written in too, as
        `rule_applied:<rule>`. That is what keeps a rule derived base named in
        the provenance list a user reads, even though a capability's own
        provenance list records sequence sources rather than composer rules.
        """
        return [
            f"provenance_assertion:{self.provenance.verdict.value}",
            f"composition_assertion:{self.composition.verdict.value}",
            *(f"rule_applied:{rule}" for rule in self.provenance.rules_applied),
            *self.screening.provenance_entries,
        ]

    def record_in_design(self, result: DesignResult) -> DesignResult:
        """Return a copy of `result` with this screening recorded in its provenance.

        Section 11.1 item 3: the screening result is recorded in the design's
        provenance. Entries already present are not duplicated, so recording
        twice is harmless.
        """
        existing = list(result.provenance)
        for entry in self.provenance_entries:
            if entry not in existing:
                existing.append(entry)
        return result.model_copy(update={"provenance": existing})


class ExportBlocked(Exception):
    """Raised when the gate refuses an export. Carries the written audit entry.

    The message is the list of reasons, so a caller that only logs the
    exception still logs why.
    """

    def __init__(self, record: ScreeningRecord, entry: ExportAuditEntry) -> None:
        self.record = record
        self.entry = entry
        reasons = "; ".join(record.blocked_reasons) or "no reason recorded"
        super().__init__(
            f"export of design {record.design_id!r} is blocked by pre-export screening: {reasons}"
        )


@dataclass(frozen=True)
class ScreenedExport:
    """A permitted export: the payloads, and the audit entry that recorded it.

    A frozen dataclass rather than a pydantic model on purpose. `SchemaModel`
    sets `str_strip_whitespace=True`, which would quietly trim the trailing
    newline off a GenBank or FASTA payload, and the SHA-256 in the audit entry
    is computed over the payload as it arrived. The bytes released here are the
    bytes that were audited, unchanged.
    """

    design_id: str
    export_format: str
    payloads: dict[str, str]
    record: ScreeningRecord
    entry: ExportAuditEntry


def screen_design(
    subject: ExportSubject,
    *,
    backend: ScreeningBackend | None = None,
    policy: ScreeningPolicy | None = None,
    parts: dict[str, PartRecord] | None = None,
) -> ScreeningRecord:
    """Run the three section 11.1 steps that precede the audit entry.

    `backend` defaults to `NoExternalScreeningBackend`, which screens nothing
    and records that fact. Passing a backend wires a real one; it is run
    through `run_screening_backend`, so no failure of it can produce a
    no-findings result.
    """
    active_policy = policy or DEFAULT_POLICY
    active_backend: ScreeningBackend = backend or NoExternalScreeningBackend()

    provenance = assert_provenance(subject, parts=parts)
    composition = assert_registry_only_composition(subject, parts=parts)
    screening = run_screening_backend(active_backend, subject)

    reasons: list[str] = []
    if not provenance.permits_export:
        reasons.append(
            f"sequence provenance assertion is {provenance.verdict.value} "
            f"(section 11.1 item 1): {provenance.reason}"
        )
    if not composition.permits_export:
        reasons.append(
            f"registry-only composition assertion is {composition.verdict.value} "
            f"(section 11.1 item 2): {composition.reason}"
        )
    if screening.findings and active_policy.block_on_backend_findings:
        reasons.append(
            f"the configured screening backend {screening.backend_id!r} returned "
            f"{len(screening.findings)} finding(s) and this deployment's policy blocks on "
            "backend findings"
        )
    if (
        not screening.external_screening_ran
        and screening.backend_id != NoExternalScreeningBackend.backend_id
        and active_policy.block_when_configured_backend_fails
    ):
        reasons.append(
            f"a screening backend is configured ({screening.backend_id!r}) but did not screen "
            f"this design: {screening.detail}"
        )

    return ScreeningRecord(
        design_id=subject.design_id,
        allowed=not reasons,
        blocked_reasons=reasons,
        provenance=provenance,
        composition=composition,
        screening=screening,
    )


def evaluate_export(
    subject: ExportSubject,
    *,
    export_format: str,
    payloads: Mapping[str, str],
    validation_overall: Severity | None = None,
    backend: ScreeningBackend | None = None,
    policy: ScreeningPolicy | None = None,
    parts: dict[str, PartRecord] | None = None,
    audit_log: ExportAuditLog | None = None,
    now: Callable[[], datetime] = utc_now,
) -> tuple[ScreeningRecord, ExportAuditEntry]:
    """Screen a design, write the audit entry, and return both. Never raises on a block.

    The audit entry is written before anything else happens, including before a
    block is reported, so there is no path that produces an export decision
    without a record of it (section 11.1 item 4).
    """
    record = screen_design(subject, backend=backend, policy=policy, parts=parts)
    entry = build_entry(
        capability=subject.capability,
        design_id=subject.design_id,
        export_format=export_format,
        decision=DECISION_EXPORTED if record.allowed else DECISION_BLOCKED,
        blocked_reasons=record.blocked_reasons,
        artifacts=[
            ExportedArtifact(
                name=name,
                format=export_format,
                bytes_written=len(payload.encode("utf-8")),
                sha256=sha256_hex(payload),
            )
            for name, payload in sorted(payloads.items())
        ],
        sequences=[
            ExportedSequence(
                name=item.name,
                length_bp=item.length_bp,
                sha256=sha256_hex(item.sequence),
            )
            for item in subject.sequences
        ],
        validator_version=subject.validator_version,
        validation_overall=validation_overall,
        screening=record.screening,
        provenance_assertion=record.provenance,
        composition_assertion=record.composition,
        declared_provenance=list(subject.declared_provenance),
        adapter=subject.adapter,
        now=now,
    )
    if audit_log is not None:
        audit_log.record(entry)
    return record, entry


def screen_and_export(
    subject: ExportSubject,
    *,
    export_format: str,
    payloads: Mapping[str, str],
    validation_overall: Severity | None = None,
    backend: ScreeningBackend | None = None,
    policy: ScreeningPolicy | None = None,
    parts: dict[str, PartRecord] | None = None,
    audit_log: ExportAuditLog | None = None,
    now: Callable[[], datetime] = utc_now,
) -> ScreenedExport:
    """The gate. Returns the payloads when the export is permitted, raises otherwise.

    Raises `ExportBlocked` when the gate refuses. The audit entry is written in
    both cases and is attached to the exception, so a blocked export is as well
    recorded as a permitted one.
    """
    record, entry = evaluate_export(
        subject,
        export_format=export_format,
        payloads=payloads,
        validation_overall=validation_overall,
        backend=backend,
        policy=policy,
        parts=parts,
        audit_log=audit_log,
        now=now,
    )
    if not record.allowed:
        raise ExportBlocked(record, entry)
    return ScreenedExport(
        design_id=subject.design_id,
        export_format=export_format,
        payloads=dict(payloads),
        record=record,
        entry=entry,
    )


__all__ = [
    "DECISION_BLOCKED",
    "DECISION_EXPORTED",
    "DEFAULT_POLICY",
    "AssertionVerdict",
    "ExportBlocked",
    "ScreenedExport",
    "ScreeningPolicy",
    "ScreeningRecord",
    "evaluate_export",
    "screen_and_export",
    "screen_design",
]
