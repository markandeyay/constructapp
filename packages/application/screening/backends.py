"""The pre-export screening hook: the interface, and the default no-op backend.

Source: section 11.1 item 3 of the engine capability system design. "A
documented interface where a sequence screening step runs before export, with
its result recorded in the design's provenance. Implement the interface and the
recording. The screening backend itself is configurable."

Open question Q8 is answered in the specification itself: no sequence screening
backend is available to wire in this build. So what ships here is the
interface, the recording, and one explicitly named no-op backend whose result
states that no external screening ran.

The naming in this module exists to make one specific misreading impossible: a
person reading an audit entry months from now must not be able to conclude that
a sequence was examined by an external screening service when it was not. So:

* The default backend is named `NoExternalScreeningBackend` and its id is
  `no_external_screening_backend_configured`. Neither name can be mistaken for
  a service.
* Its outcome is `NO_EXTERNAL_SCREENING_RAN`, not a pass, not a clear, not an
  approval. There is no outcome value in this module that means "examined and
  nothing found" unless an actual backend returned it, and even then the value
  is `BACKEND_REPORTED_NO_FINDINGS`, which names the backend as the author of
  that statement.
* A backend that raises, times out or cannot be reached produces
  `BACKEND_ERROR_NOT_SCREENED` or `BACKEND_UNREACHABLE_NOT_SCREENED`. Those are
  the same category of result as no backend at all: the design was not
  screened. A failure never produces a no-findings outcome.

What may and may not be claimed about this package is in section 11.2 and in
`progress/WP-08.md`. This module makes no claim about any sequence.

Determinism (section 3.3 constraint 3): `NoExternalScreeningBackend` is a pure
function of its inputs, so the same design produces the same screening result
every time. A third party backend is outside this build's determinism promise
by construction, which is itself recorded: the audit entry carries the backend
id and version so a result can be interpreted later.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import Field

from packages.core.schemas.capability import CapabilityModel

from .attribution import ExportSubject

#: The id recorded whenever no external screening backend is configured. It is
#: a statement about configuration, not a service name.
NO_BACKEND_ID = "no_external_screening_backend_configured"


class BackendOutcome(str, Enum):
    """What a screening backend produced, stated so it cannot be over-read.

    Four of the five values mean the design was NOT examined by an external
    service. Only `BACKEND_REPORTED_NO_FINDINGS` and
    `BACKEND_REPORTED_FINDINGS` mean a backend ran and answered, and both name
    the backend as the author of the answer.
    """

    #: No backend is configured. Nothing external examined this design.
    NO_EXTERNAL_SCREENING_RAN = "no_external_screening_ran"
    #: A backend is configured but could not be reached. Nothing examined this design.
    BACKEND_UNREACHABLE_NOT_SCREENED = "backend_unreachable_not_screened"
    #: A backend is configured and raised. Nothing examined this design.
    BACKEND_ERROR_NOT_SCREENED = "backend_error_not_screened"
    #: A configured backend ran and returned findings.
    BACKEND_REPORTED_FINDINGS = "backend_reported_findings"
    #: A configured backend ran and returned no findings. This is the backend's
    #: statement about its own criteria, recorded as such.
    BACKEND_REPORTED_NO_FINDINGS = "backend_reported_no_findings"


#: The outcomes that mean no external screening examined the design. Every one
#: of these must read, in any log or export, as "not screened".
NOT_SCREENED_OUTCOMES = frozenset(
    {
        BackendOutcome.NO_EXTERNAL_SCREENING_RAN,
        BackendOutcome.BACKEND_UNREACHABLE_NOT_SCREENED,
        BackendOutcome.BACKEND_ERROR_NOT_SCREENED,
    }
)


class ScreeningBackendUnreachable(Exception):
    """Raised by a backend that could not reach its service.

    A backend raises this instead of returning any outcome, and
    `run_screening_backend` converts it to
    `BACKEND_UNREACHABLE_NOT_SCREENED`. A hook that cannot reach its configured
    backend never reports that nothing was found (section 3.3 constraint 4).
    """


class BackendFinding(CapabilityModel):
    """One finding a backend returned, carried through verbatim.

    `code` and `detail` are the backend's own words. This build does not
    interpret them, does not rank them and does not translate them into a
    severity of its own, because it has no basis for doing so.
    """

    sequence_name: str = Field(min_length=1)
    code: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    start: int | None = None
    end: int | None = None


class ScreeningResult(CapabilityModel):
    """The recorded result of the pre-export screening hook for one design.

    This is what goes into the audit entry and into the design's provenance.
    `backend_id` and `backend_version` are recorded even when no backend is
    configured, so every entry says what did or did not run.
    """

    backend_id: str = Field(min_length=1)
    backend_version: str = Field(min_length=1)
    outcome: BackendOutcome
    findings: list[BackendFinding] = Field(default_factory=list)
    detail: str = Field(min_length=1)
    sequences_submitted: int = Field(ge=0)
    bases_submitted: int = Field(ge=0)

    @property
    def external_screening_ran(self) -> bool:
        """False whenever nothing external examined the design."""
        return self.outcome not in NOT_SCREENED_OUTCOMES

    @property
    def provenance_entries(self) -> list[str]:
        """The entries appended to `DesignResult.provenance` (section 11.1 item 3).

        One entry per result, always present, always naming the outcome. When
        no external screening ran a second entry says so in words, so a reader
        skimming a provenance list cannot miss it.
        """
        entries = [f"screening:{self.backend_id}:{self.outcome.value}"]
        if not self.external_screening_ran:
            entries.append(
                "screening_note:no external sequence screening backend examined this design"
            )
        return entries


@runtime_checkable
class ScreeningBackend(Protocol):
    """The section 11.1 item 3 interface. Implement this to wire a real backend.

    A backend receives the whole `ExportSubject`, which carries every exported
    sequence with its attribution, the capability, the design id and the
    validator version. It returns a `ScreeningResult` describing what it did.

    Three obligations, which `run_screening_backend` enforces for anything that
    goes wrong and which an implementation must honour for everything else:

    1. Never return a no-findings outcome for a design it did not examine. If
       the service could not be reached, raise `ScreeningBackendUnreachable`.
       Any other failure may be raised as any exception; it is recorded as
       `BACKEND_ERROR_NOT_SCREENED`.
    2. `backend_id` and `backend_version` must identify the service and its
       version precisely enough that a stored audit entry can be interpreted
       later. They are written into every audit entry verbatim.
    3. `detail` is a sentence a person will read in an audit log. It must not
       overstate what was done. Section 16 governs it.

    `screen` must not mutate the subject.
    """

    backend_id: str
    backend_version: str

    def screen(self, subject: ExportSubject) -> ScreeningResult: ...


class NoExternalScreeningBackend:
    """The default backend. It screens nothing and says so.

    This exists because open question Q8 records that no sequence screening
    backend is available to wire in this build, and because the alternative,
    a backend that returns a cheerful default, would put a false statement in
    every audit entry. Its result records the absence of screening as a fact
    about this deployment.

    It is deterministic and has no I/O, so the same design produces the same
    result every time (section 3.3 constraint 3).
    """

    backend_id: str = NO_BACKEND_ID
    backend_version: str = "1"

    DETAIL = (
        "No external sequence screening backend is configured in this deployment, so no "
        "external screening examined this design. This entry records the absence of "
        "screening and must not be read as a screening result. The provenance assertion "
        "and the composition assertion in this same entry did run, and they are what this "
        "export was gated on."
    )

    def screen(self, subject: ExportSubject) -> ScreeningResult:
        return ScreeningResult(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            outcome=BackendOutcome.NO_EXTERNAL_SCREENING_RAN,
            findings=[],
            detail=self.DETAIL,
            sequences_submitted=0,
            bases_submitted=0,
        )


def run_screening_backend(backend: ScreeningBackend, subject: ExportSubject) -> ScreeningResult:
    """Run a backend and return its result, converting every failure honestly.

    A backend that raises `ScreeningBackendUnreachable` gives
    `BACKEND_UNREACHABLE_NOT_SCREENED`. A backend that raises anything else
    gives `BACKEND_ERROR_NOT_SCREENED`. A backend that returns something that
    is not a `ScreeningResult`, or that returns a no-findings outcome while
    also returning findings, is treated as an error: the hook records that the
    design was not screened rather than trusting a malformed answer.

    No path through this function can produce a no-findings outcome for a
    design the backend did not actually answer about (section 3.3
    constraint 3 and constraint 4).
    """
    backend_id = getattr(backend, "backend_id", backend.__class__.__name__) or backend.__class__.__name__
    backend_version = getattr(backend, "backend_version", "unknown") or "unknown"
    try:
        result = backend.screen(subject)
    except ScreeningBackendUnreachable as exc:
        return ScreeningResult(
            backend_id=backend_id,
            backend_version=backend_version,
            outcome=BackendOutcome.BACKEND_UNREACHABLE_NOT_SCREENED,
            findings=[],
            detail=(
                f"The configured screening backend {backend_id!r} version {backend_version} could "
                f"not be reached: {exc or 'no detail given'}. No external screening examined this "
                "design. This is not a no-findings result and must not be read as one."
            ),
            sequences_submitted=len(subject.sequences),
            bases_submitted=subject.total_bp,
        )
    except Exception as exc:  # noqa: BLE001 - every backend failure is recorded, never swallowed
        return ScreeningResult(
            backend_id=backend_id,
            backend_version=backend_version,
            outcome=BackendOutcome.BACKEND_ERROR_NOT_SCREENED,
            findings=[],
            detail=(
                f"The configured screening backend {backend_id!r} version {backend_version} "
                f"raised {type(exc).__name__}: {exc or 'no detail given'}. No external screening "
                "examined this design. This is not a no-findings result and must not be read as "
                "one."
            ),
            sequences_submitted=len(subject.sequences),
            bases_submitted=subject.total_bp,
        )

    if not isinstance(result, ScreeningResult):
        return ScreeningResult(
            backend_id=backend_id,
            backend_version=backend_version,
            outcome=BackendOutcome.BACKEND_ERROR_NOT_SCREENED,
            findings=[],
            detail=(
                f"The configured screening backend {backend_id!r} version {backend_version} "
                f"returned {type(result).__name__}, not a ScreeningResult, so its answer could "
                "not be recorded. No screening result exists for this design."
            ),
            sequences_submitted=len(subject.sequences),
            bases_submitted=subject.total_bp,
        )

    if result.outcome is BackendOutcome.BACKEND_REPORTED_NO_FINDINGS and result.findings:
        return ScreeningResult(
            backend_id=result.backend_id,
            backend_version=result.backend_version,
            outcome=BackendOutcome.BACKEND_ERROR_NOT_SCREENED,
            findings=result.findings,
            detail=(
                f"The configured screening backend {result.backend_id!r} version "
                f"{result.backend_version} reported no findings and then returned "
                f"{len(result.findings)} finding(s), which contradict each other. The answer was "
                "not recorded as a no-findings result. The findings are carried through "
                "unchanged."
            ),
            sequences_submitted=result.sequences_submitted,
            bases_submitted=result.bases_submitted,
        )

    if result.outcome is BackendOutcome.NO_EXTERNAL_SCREENING_RAN and result.backend_id != NO_BACKEND_ID:
        return ScreeningResult(
            backend_id=result.backend_id,
            backend_version=result.backend_version,
            outcome=BackendOutcome.BACKEND_ERROR_NOT_SCREENED,
            findings=result.findings,
            detail=(
                f"The configured screening backend {result.backend_id!r} version "
                f"{result.backend_version} reported that no external screening ran, which only "
                f"the {NO_BACKEND_ID!r} placeholder may report. Recorded as a backend error: this "
                "design was not screened."
            ),
            sequences_submitted=result.sequences_submitted,
            bases_submitted=result.bases_submitted,
        )

    return result
