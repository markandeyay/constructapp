from __future__ import annotations

"""FastAPI application scaffold for session-driven design workflows."""

import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from packages.application import (
    InMemoryJobQueue,
    InMemoryOutcomeStore,
    InMemorySessionStore,
    JobQueue,
    OutcomeStore,
    SessionJobResult,
    SessionStore,
)
from packages.application.designs import DesignStore, InMemoryDesignStore
from packages.application.exports import export_annotated_sequence
from packages.application.observability import (
    MetricsCollector,
    configure_logging,
    get_correlation_id,
    log_event,
    reset_correlation_id,
    set_correlation_id,
)
from packages.core.schemas import AnnotatedSequence, OutcomeReport
from packages.generation.registry import ModelRegistry
from services.api.routes import include_capability_routers


MAX_PROMPT_LENGTH = 2_000
JOB_RETRY_AFTER_MS = 750


class ApiModel(BaseModel):
    """Base model for API-layer envelopes."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
    )


class CreateSessionResponse(ApiModel):
    """Response returned when a session is created."""

    session_id: str = Field(min_length=1)


class DesignRequest(ApiModel):
    """Initial free-text design request."""

    goal: str = Field(min_length=1, max_length=MAX_PROMPT_LENGTH)

    @field_validator("goal")
    @classmethod
    def require_non_blank_goal(cls, value: str) -> str:
        return _require_non_blank(value)


class RefineRequest(ApiModel):
    """Follow-up refinement instruction."""

    instruction: str = Field(min_length=1, max_length=MAX_PROMPT_LENGTH)

    @field_validator("instruction")
    @classmethod
    def require_non_blank_instruction(cls, value: str) -> str:
        return _require_non_blank(value)


class ApiFieldError(ApiModel):
    """One frontend-renderable request validation issue."""

    field: str
    message: str
    type: str


class ApiErrorDetail(ApiModel):
    """Stable frontend-renderable error detail."""

    code: str
    message: str
    retryable: bool = False
    field_errors: list[ApiFieldError] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ApiErrorResponse(ApiModel):
    """Standard API error envelope."""

    error: ApiErrorDetail


class JobAcceptedResponse(ApiModel):
    """Async job handle returned from design/refinement requests."""

    job_id: str = Field(min_length=1)


class JobStatusResponse(ApiModel):
    """Status payload returned when polling an async job."""

    job_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    result: SessionJobResult | dict[str, Any] | None = None
    error: str | None = None
    error_detail: ApiErrorDetail | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    retry_after_ms: int | None = None


class OutcomeResponse(ApiModel):
    outcome_id: str = Field(min_length=1)
    report: OutcomeReport
    created_at: datetime


class DesignResponse(ApiModel):
    design_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    annotated_sequence: AnnotatedSequence
    created_at: datetime
    updated_at: datetime


class PendingOutcomePromptResponse(ApiModel):
    design_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    created_at: datetime
    days_since_created: int


class PendingOutcomePromptsResponse(ApiModel):
    prompts: list[PendingOutcomePromptResponse] = Field(default_factory=list)


@dataclass(frozen=True)
class RateLimitRule:
    limit: int
    window_seconds: int


@dataclass(frozen=True)
class RateLimitConfig:
    session_create: RateLimitRule = RateLimitRule(limit=60, window_seconds=60)
    job_enqueue: RateLimitRule = RateLimitRule(limit=30, window_seconds=60)
    job_poll: RateLimitRule = RateLimitRule(limit=600, window_seconds=60)
    export: RateLimitRule = RateLimitRule(limit=120, window_seconds=60)
    enabled: bool = True


@dataclass
class InMemoryRateLimiter:
    buckets: dict[str, list[float]] = field(default_factory=dict)

    def check(self, key: str, *, limit: int, window_seconds: int, now: float | None = None) -> float | None:
        if limit <= 0 or window_seconds <= 0:
            return 0.0
        current = time.monotonic() if now is None else now
        cutoff = current - window_seconds
        timestamps = [timestamp for timestamp in self.buckets.get(key, []) if timestamp > cutoff]
        if len(timestamps) >= limit:
            self.buckets[key] = timestamps
            return max(0.0, window_seconds - (current - timestamps[0]))
        timestamps.append(current)
        self.buckets[key] = timestamps
        return None


def create_app(
    *,
    session_store: SessionStore | None = None,
    job_queue: Any | None = None,
    design_store: DesignStore | None = None,
    outcome_store: OutcomeStore | None = None,
    model_registry: Any | None = None,
    rate_limiter: InMemoryRateLimiter | None = None,
    rate_limit_config: RateLimitConfig | None = None,
) -> FastAPI:
    """Build the FastAPI app with injectable collaborators for tests."""

    configure_logging()
    logger = logging.getLogger("construct.api")
    store = session_store or InMemorySessionStore()
    queue = job_queue or InMemoryJobQueue()
    designs = design_store or InMemoryDesignStore()
    outcomes = outcome_store or InMemoryOutcomeStore()
    registry = model_registry or ModelRegistry()
    metrics = MetricsCollector()
    limiter = rate_limiter or InMemoryRateLimiter()
    limits = rate_limit_config or RateLimitConfig()

    app = FastAPI(title="Construct API", version="0.1.0")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            code = str(detail.get("code") or _default_error_code(exc.status_code))
            message = str(detail.get("message") or detail.get("detail") or "Request failed.")
            retryable = bool(detail.get("retryable", False))
            details = {key: value for key, value in detail.items() if key not in {"code", "message", "detail", "retryable"}}
        else:
            code = _code_from_message(str(detail), exc.status_code)
            message = _friendly_message(str(detail), exc.status_code)
            retryable = False
            details = {}
        _record_api_error(
            logger=logger,
            metrics=metrics,
            request=request,
            status_code=exc.status_code,
            code=code,
            retryable=retryable,
        )
        return _error_response(
            status_code=exc.status_code,
            code=code,
            message=message,
            retryable=retryable,
            details=details,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        field_errors = [
            ApiFieldError(
                field=".".join(str(part) for part in error.get("loc", []) if part != "body"),
                message=str(error.get("msg", "Invalid value.")),
                type=str(error.get("type", "value_error")),
            )
            for error in exc.errors()
        ]
        _record_api_error(
            logger=logger,
            metrics=metrics,
            request=request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            retryable=False,
            field_count=len(field_errors),
        )
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="Please fix the highlighted fields and try again.",
            field_errors=field_errors,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        _record_api_error(
            logger=logger,
            metrics=metrics,
            request=request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            retryable=True,
            error_type=type(exc).__name__,
        )
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="The server hit an unexpected error while handling the request.",
            retryable=True,
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.session_store = store
    app.state.job_queue = queue
    app.state.design_store = designs
    app.state.outcome_store = outcomes
    app.state.model_registry = registry
    app.state.metrics = metrics
    app.state.rate_limiter = limiter

    @app.middleware("http")
    async def correlation_and_metrics_middleware(request: Request, call_next: Any) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
        token = set_correlation_id(correlation_id)
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started_at) * 1000
            metrics.record_request(
                latency_ms=duration_ms,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                method=request.method,
                path=request.url.path,
            )
            metrics.record_error(code="internal_error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, path=request.url.path)
            log_event(
                logger,
                "api_request_failed",
                method=request.method,
                path=request.url.path,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                duration_ms=round(duration_ms, 3),
            )
            reset_correlation_id(token)
            raise
        duration_ms = (time.perf_counter() - started_at) * 1000
        response.headers["X-Correlation-ID"] = correlation_id
        metrics.record_request(
            latency_ms=duration_ms,
            status_code=response.status_code,
            method=request.method,
            path=request.url.path,
        )
        log_event(
            logger,
            "api_request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 3),
        )
        reset_correlation_id(token)
        return response

    @app.post(
        "/v1/sessions",
        response_model=CreateSessionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_session(request: Request, x_user_id: str | None = Header(default=None, alias="X-User-ID")) -> CreateSessionResponse:
        # TODO: enforce bearer auth, durable account-aware rate limits, and usage metering.
        _enforce_rate_limit(request, limiter=limiter, config=limits, bucket="session_create", rule=limits.session_create)
        session = _create_session(store, user_id=x_user_id)
        return CreateSessionResponse(session_id=session.session_id)

    @app.get("/v1/health")
    def health_snapshot() -> dict[str, Any]:
        """Return lightweight process, queue, and model-registry health."""

        queue_status = _queue_snapshot(queue)
        registry_status = _model_registry_snapshot(registry)
        unhealthy = queue_status.get("status") == "error" or registry_status.get("status") == "error"
        return {
            "status": "degraded" if unhealthy else "ok",
            "queue": queue_status,
            "model_registry": registry_status,
        }

    @app.get("/v1/metrics", response_model=None)
    def metrics_snapshot(request: Request) -> Any:
        """Return lightweight in-process metrics for local observability."""

        snapshot = metrics.snapshot()
        snapshot["queue"] = _queue_snapshot(queue)
        snapshot["model_registry"] = _model_registry_snapshot(registry)
        if "text/plain" in request.headers.get("accept", ""):
            return PlainTextResponse(_metrics_to_text(snapshot))
        return snapshot

    @app.post(
        "/v1/sessions/{session_id}/design",
        response_model=JobAcceptedResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def design_session(session_id: str, request: Request, payload: DesignRequest) -> JobAcceptedResponse:
        """Queue a design job for the session without blocking on model work."""

        # TODO: enforce bearer auth, durable account-aware rate limits, and usage metering.
        _enforce_rate_limit(request, limiter=limiter, config=limits, bucket="job_enqueue", rule=limits.job_enqueue, subject=session_id)
        session = _get_session(store, session_id)
        if session is None:
            raise _http_error(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found.")
        turn = _add_turn(store, session_id=session_id, action="design", text=payload.goal)
        try:
            job_id = _enqueue(
                queue,
                session=store.get_session(session_id) or session,
                action="design",
                text=payload.goal,
                correlation_id=get_correlation_id(),
            )
        except Exception as exc:
            log_event(logger, "api_job_queue_unavailable", session_id=session_id, action="design", error_type=type(exc).__name__)
            raise _http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "job_queue_unavailable",
                "The design job queue is temporarily unavailable.",
                retryable=True,
            ) from exc
        _attach_job_id(store, session_id=session_id, turn=turn, job_id=job_id)
        log_event(logger, "api_job_queued", session_id=session_id, job_id=job_id, action="design")
        return JobAcceptedResponse(job_id=job_id)

    @app.post(
        "/v1/sessions/{session_id}/refine",
        response_model=JobAcceptedResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def refine_session(session_id: str, request: Request, payload: RefineRequest) -> JobAcceptedResponse:
        """Queue a refinement job for the session without blocking on model work."""

        # TODO: enforce bearer auth, durable account-aware rate limits, and usage metering.
        _enforce_rate_limit(request, limiter=limiter, config=limits, bucket="job_enqueue", rule=limits.job_enqueue, subject=session_id)
        session = _get_session(store, session_id)
        if session is None:
            raise _http_error(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found.")
        turn = _add_turn(store, session_id=session_id, action="refine", text=payload.instruction)
        try:
            job_id = _enqueue(
                queue,
                session=store.get_session(session_id) or session,
                action="refine",
                text=payload.instruction,
                correlation_id=get_correlation_id(),
            )
        except Exception as exc:
            log_event(logger, "api_job_queue_unavailable", session_id=session_id, action="refine", error_type=type(exc).__name__)
            raise _http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "job_queue_unavailable",
                "The design job queue is temporarily unavailable.",
                retryable=True,
            ) from exc
        _attach_job_id(store, session_id=session_id, turn=turn, job_id=job_id)
        log_event(logger, "api_job_queued", session_id=session_id, job_id=job_id, action="refine")
        return JobAcceptedResponse(job_id=job_id)

    @app.get("/v1/jobs/{job_id}", response_model=JobStatusResponse)
    def get_job(job_id: str, request: Request) -> JobStatusResponse:
        """Poll async job state and any available result payload."""

        # TODO: enforce bearer auth, durable account-aware rate limits, and usage metering.
        _enforce_rate_limit(request, limiter=limiter, config=limits, bucket="job_poll", rule=limits.job_poll)
        job = _get_job(queue, job_id)
        if job is None:
            raise _http_error(status.HTTP_404_NOT_FOUND, "job_not_found", "Job not found.")
        job_status = str(job.status)
        error_text = getattr(job, "error", None)
        return JobStatusResponse(
            job_id=job.job_id,
            status=job_status,
            result=job.result,
            error=error_text,
            error_detail=_job_error_detail(error_text),
            created_at=getattr(job, "created_at", None),
            updated_at=getattr(job, "updated_at", None),
            retry_after_ms=JOB_RETRY_AFTER_MS if job_status.lower() in {"queued", "running"} else None,
        )

    @app.get("/v1/designs/{design_id}", response_model=DesignResponse)
    def get_design(design_id: str) -> DesignResponse:
        design = designs.get(design_id)
        if design is None:
            raise _http_error(status.HTTP_404_NOT_FOUND, "design_not_found", "Design not found.")
        return DesignResponse(
            design_id=design.design_id,
            session_id=design.session_id,
            job_id=design.job_id,
            annotated_sequence=design.annotated_sequence,
            created_at=design.created_at,
            updated_at=design.updated_at,
        )

    @app.get("/v1/designs/{design_id}/export")
    def export_design(design_id: str, format: Literal["genbank", "fasta"], request: Request) -> Response:
        """Export a persisted annotated design as GenBank or FASTA."""

        # TODO: enforce bearer auth, durable account-aware rate limits, and usage metering.
        _enforce_rate_limit(request, limiter=limiter, config=limits, bucket="export", rule=limits.export, subject=design_id)
        design = designs.get(design_id)
        if design is None:
            raise _http_error(status.HTTP_404_NOT_FOUND, "design_not_found", "Design not found.")
        try:
            payload = export_annotated_sequence(design.annotated_sequence, format=format)
        except Exception as exc:
            raise _http_error(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "export_failed",
                "The design export could not be prepared.",
                retryable=True,
            ) from exc
        media_type = "text/plain" if format == "fasta" else "application/genbank"
        suffix = "fasta" if format == "fasta" else "gb"
        return Response(
            content=payload,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{design_id}.{suffix}"'},
        )

    @app.post("/v1/designs/{design_id}/outcome", response_model=OutcomeResponse, status_code=status.HTTP_201_CREATED)
    def submit_outcome(
        design_id: str,
        report: OutcomeReport,
        x_user_id: str | None = Header(default=None, alias="X-User-ID"),
    ) -> OutcomeResponse:
        """Capture a user-reported wet-lab outcome for a generated design."""

        user_id = _require_user_id(x_user_id)
        design = designs.get(design_id)
        if design is None:
            raise _http_error(status.HTTP_404_NOT_FOUND, "design_not_found", "Design not found.")
        _require_design_owner(store, design.session_id, user_id)
        if report.design_id != design_id:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "design_id_mismatch", "Outcome design_id must match the URL.")
        outcome = outcomes.create(report=report, user_id=user_id)
        return OutcomeResponse(outcome_id=outcome.outcome_id, report=outcome.report, created_at=outcome.created_at)

    @app.get("/v1/designs/{design_id}/outcome", response_model=OutcomeResponse)
    def get_outcome(
        design_id: str,
        x_user_id: str | None = Header(default=None, alias="X-User-ID"),
    ) -> OutcomeResponse:
        """Return the most recent captured outcome for a design."""

        user_id = _require_user_id(x_user_id)
        design = designs.get(design_id)
        if design is None:
            raise _http_error(status.HTTP_404_NOT_FOUND, "design_not_found", "Design not found.")
        _require_design_owner(store, design.session_id, user_id)
        outcome = outcomes.latest_for_design(design_id)
        if outcome is None:
            raise _http_error(status.HTTP_404_NOT_FOUND, "outcome_not_found", "Outcome not found.")
        return OutcomeResponse(outcome_id=outcome.outcome_id, report=outcome.report, created_at=outcome.created_at)

    @app.get("/v1/users/me/pending-outcome-prompts", response_model=PendingOutcomePromptsResponse)
    def pending_outcome_prompts(
        x_user_id: str | None = Header(default=None, alias="X-User-ID"),
        min_age_days: int = 14,
    ) -> PendingOutcomePromptsResponse:
        """Return aged designs that should prompt the user for wet-lab outcomes."""

        user_id = _require_user_id(x_user_id)
        prompts = outcomes.list_pending_prompts(user_id=user_id, min_age_days=min_age_days)
        return PendingOutcomePromptsResponse(
            prompts=[
                PendingOutcomePromptResponse(
                    design_id=prompt.design_id,
                    session_id=prompt.session_id,
                    created_at=prompt.created_at,
                    days_since_created=prompt.days_since_created,
                )
                for prompt in prompts
            ]
        )

    # Mount the capability routers declared in the section 13.3 router block.
    # Each capability package registers itself there; without this call the
    # routers are declared but never served. Done here, after the plasmid routes
    # are defined, so a capability router cannot shadow an existing path.
    included = include_capability_routers(app)
    logger.info("api_capability_routers_included", extra={"capabilities": included})

    return app


def _create_session(store: Any, *, user_id: str | None) -> Any:
    try:
        return store.create_session(user_id=user_id)
    except TypeError:
        return store.create_session()


def _enqueue(queue: Any, *, session: Any, action: str, text: str, correlation_id: str | None = None) -> str:
    if _has_explicit_callable(queue, "enqueue"):
        context = [turn.user_text if hasattr(turn, "user_text") else turn.get("content", "") for turn in session.turns]
        record = queue.enqueue(
            session_id=session.session_id,
            action=action,
            payload={action: text, "text": text, "context": context, "correlation_id": correlation_id},
        )
        return getattr(record, "job_id", str(record))
    if _has_explicit_callable(queue, "submit"):
        return queue.submit(session_id=session.session_id, action=action, text=text, correlation_id=correlation_id)
    if action == "design" and _has_explicit_callable(queue, "enqueue_design"):
        return queue.enqueue_design(session=session, goal=text)
    if action == "refine" and _has_explicit_callable(queue, "enqueue_refinement"):
        return queue.enqueue_refinement(session=session, instruction=text)
    raise TypeError("job queue does not expose a supported enqueue method")


def _has_explicit_callable(instance: Any, name: str) -> bool:
    if name in getattr(instance, "__dict__", {}):
        return callable(getattr(instance, name))
    return any(name in cls.__dict__ and callable(getattr(instance, name)) for cls in type(instance).__mro__)


def _get_job(queue: Any, job_id: str) -> Any | None:
    try:
        if hasattr(queue, "get_job"):
            return queue.get_job(job_id)
        return queue.store.get(job_id)
    except KeyError:
        return None


def _get_session(store: Any, session_id: str) -> Any | None:
    try:
        return store.get_session(session_id)
    except KeyError:
        return None


def _require_user_id(user_id: str | None) -> str:
    if user_id is None or not user_id.strip():
        raise _http_error(status.HTTP_401_UNAUTHORIZED, "authentication_required", "Authentication is required.")
    return user_id.strip()


def _require_design_owner(store: Any, session_id: str, user_id: str) -> None:
    session = _get_session(store, session_id)
    if session is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found.")
    owner = getattr(session, "user_id", None)
    if owner is not None and owner != user_id:
        raise _http_error(status.HTTP_403_FORBIDDEN, "forbidden", "You do not own this design.")


def _add_turn(store: Any, *, session_id: str, action: str, text: str) -> Any:
    turn = store.add_turn(session_id, turn_type=action, user_text=text)
    if isinstance(turn, dict):
        turn.setdefault("role", "user")
        turn.setdefault("content", text)
    return turn


def _attach_job_id(store: Any, *, session_id: str, turn: Any, job_id: str) -> None:
    if isinstance(turn, dict):
        turn["job_id"] = job_id
        return
    setter = getattr(store, "set_turn_job_id", None)
    if callable(setter):
        setter(session_id, turn_id=turn.turn_id, job_id=job_id)


def _require_non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("Input must contain at least one non-whitespace character.")
    return value


def _http_error(
    status_code: int,
    code: str,
    message: str,
    *,
    retryable: bool = False,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "retryable": retryable},
        headers=headers,
    )


def _enforce_rate_limit(
    request: Request,
    *,
    limiter: InMemoryRateLimiter,
    config: RateLimitConfig,
    bucket: str,
    rule: RateLimitRule,
    subject: str | None = None,
) -> None:
    if not config.enabled:
        return
    client = request.client.host if request.client is not None else "unknown"
    key = ":".join(part for part in (bucket, client, subject) if part)
    retry_after = limiter.check(key, limit=rule.limit, window_seconds=rule.window_seconds)
    if retry_after is None:
        return
    retry_seconds = max(1, math.ceil(retry_after))
    raise _http_error(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "rate_limited",
        "Too many requests. Please wait before trying again.",
        retryable=True,
        headers={"Retry-After": str(retry_seconds)},
    )


def _record_api_error(
    *,
    logger: logging.Logger,
    metrics: MetricsCollector,
    request: Request,
    status_code: int,
    code: str,
    retryable: bool,
    **fields: Any,
) -> None:
    metrics.record_error(code=code, status_code=status_code, path=request.url.path)
    log_event(
        logger,
        "api_error_response",
        method=request.method,
        path=request.url.path,
        status_code=status_code,
        error_code=code,
        retryable=retryable,
        **fields,
    )


def _queue_snapshot(queue: Any) -> dict[str, Any]:
    snapshot = getattr(queue, "snapshot", None)
    if not callable(snapshot):
        return {"status": "unknown", "reason": "queue snapshot is not implemented"}
    try:
        payload = snapshot()
    except Exception as exc:
        return {"status": "error", "error_type": type(exc).__name__}
    if not isinstance(payload, dict):
        return {"status": "unknown", "reason": "queue snapshot returned a non-object payload"}
    return {"status": "ok", **payload}


def _model_registry_snapshot(registry: Any) -> dict[str, Any]:
    list_records = getattr(registry, "list", None)
    if not callable(list_records):
        return {"status": "unknown", "reason": "model registry listing is not implemented"}
    try:
        records = list_records()
    except Exception as exc:
        return {"status": "error", "error_type": type(exc).__name__}
    states: dict[str, int] = {}
    active_versions: list[str] = []
    for record in records:
        state = str(getattr(record, "rollout_state", "unknown"))
        states[state] = states.get(state, 0) + 1
        if state in {"shadow", "canary", "full"}:
            active_versions.append(str(getattr(record, "model_version", "unknown")))
    return {
        "status": "ok",
        "count": len(records),
        "states": dict(sorted(states.items())),
        "active_versions": sorted(active_versions),
    }


def _metrics_to_text(snapshot: dict[str, Any]) -> str:
    lines = ["# TYPE construct_info gauge", "construct_info 1"]
    for name, value in _flatten_metric_values("construct", snapshot):
        lines.append(f"{name} {value}")
    return "\n".join(lines) + "\n"


def _flatten_metric_values(prefix: str, value: Any) -> list[tuple[str, float]]:
    if isinstance(value, bool):
        return [(prefix, 1.0 if value else 0.0)]
    if isinstance(value, int | float):
        return [(prefix, float(value))]
    if not isinstance(value, dict):
        return []
    flattened: list[tuple[str, float]] = []
    for key, nested in value.items():
        safe_key = _metric_name_part(str(key))
        flattened.extend(_flatten_metric_values(f"{prefix}_{safe_key}", nested))
    return flattened


def _metric_name_part(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in value).strip("_") or "unknown"


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    field_errors: list[ApiFieldError] | None = None,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ApiErrorResponse(
        error=ApiErrorDetail(
            code=code,
            message=message,
            retryable=retryable,
            field_errors=field_errors or [],
            details=details or {},
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"), headers=headers)


def _default_error_code(status_code: int) -> str:
    if status_code == status.HTTP_404_NOT_FOUND:
        return "not_found"
    if status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
        return "validation_error"
    return "request_failed"


def _code_from_message(message: str, status_code: int) -> str:
    normalized = message.lower().replace(" ", "_")
    if normalized in {"session_not_found", "job_not_found", "design_not_found"}:
        return normalized
    return _default_error_code(status_code)


def _friendly_message(message: str, status_code: int) -> str:
    normalized = message.lower()
    if normalized == "session not found":
        return "Session not found."
    if normalized == "job not found":
        return "Job not found."
    if normalized == "design not found":
        return "Design not found."
    if status_code >= 500:
        return "The server hit an unexpected error while handling the request."
    return message or "Request failed."


def _job_error_detail(error_text: str | None) -> ApiErrorDetail | None:
    if not error_text:
        return None
    parsed = _parse_job_error(error_text)
    if parsed is not None:
        return parsed
    return ApiErrorDetail(
        code="job_failed",
        message="The design job failed before producing a result.",
        retryable=True,
    )


def _parse_job_error(error_text: str) -> ApiErrorDetail | None:
    if not error_text.startswith("{"):
        return None
    try:
        payload = json.loads(error_text)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    code = payload.get("code")
    message = payload.get("message")
    if not code or not message:
        return None
    return ApiErrorDetail(
        code=str(code),
        message=str(message),
        retryable=bool(payload.get("retryable", False)),
        details={key: value for key, value in payload.items() if key not in {"code", "message", "retryable"}},
    )


app = create_app()
