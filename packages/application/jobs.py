from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
import logging
import time
from typing import Any, Mapping, Protocol
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

from packages.application.observability import MetricsCollector, log_event, reset_correlation_id, set_correlation_id


JOB_STATUS_QUEUED = "queued"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_SUCCEEDED = "succeeded"
JOB_STATUS_FAILED = "failed"
JOB_STATUSES = {
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SUCCEEDED,
    JOB_STATUS_FAILED,
}
LOGGER = logging.getLogger("construct.worker")


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    session_id: str
    action: str
    status: str
    payload: Mapping[str, Any]
    result: Any | None = None
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.status not in JOB_STATUSES:
            raise ValueError(f"unsupported job status: {self.status}")


class JobStore(Protocol):
    def create(self, *, session_id: str, action: str, payload: Mapping[str, Any], job_id: str | None = None) -> JobRecord: ...

    def get(self, job_id: str) -> JobRecord | None: ...

    def mark_running(self, job_id: str) -> JobRecord: ...

    def mark_succeeded(self, job_id: str, *, result: Any) -> JobRecord: ...

    def mark_failed(self, job_id: str, *, error: str) -> JobRecord: ...

    def snapshot(self) -> dict[str, Any]: ...


class JobQueue(Protocol):
    def enqueue(self, *, session_id: str, action: str, payload: Mapping[str, Any]) -> JobRecord: ...

    def get_job(self, job_id: str) -> JobRecord | None: ...

    def snapshot(self) -> dict[str, Any]: ...


class JobHandler(Protocol):
    def __call__(self, *, job_id: str, session_id: str, action: str, payload: Mapping[str, Any]) -> Any: ...


class PostgresJobStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def ensure_schema(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    result JSONB,
                    error TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )

    def create(self, *, session_id: str, action: str, payload: Mapping[str, Any], job_id: str | None = None) -> JobRecord:
        now = utc_now()
        record = JobRecord(
            job_id=job_id or new_job_id(),
            session_id=session_id,
            action=action,
            status=JOB_STATUS_QUEUED,
            payload=dict(payload),
            created_at=now,
            updated_at=now,
        )
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                INSERT INTO jobs (id, session_id, kind, status, payload, result, error, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record.job_id,
                    record.session_id,
                    record.action,
                    record.status,
                    Jsonb(dict(record.payload)),
                    None,
                    None,
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def get(self, job_id: str) -> JobRecord | None:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                """
                SELECT id, session_id, kind AS action, status, payload, result, error, created_at, updated_at
                FROM jobs
                WHERE id = %s
                """,
                (job_id,),
            ).fetchone()
        return None if row is None else _job_record_from_row(row)

    def mark_running(self, job_id: str) -> JobRecord:
        record = self.get(job_id)
        if record is None:
            raise KeyError(f"unknown job: {job_id}")
        updated = replace(record, status=JOB_STATUS_RUNNING, updated_at=utc_now())
        self._persist(updated)
        return updated

    def mark_succeeded(self, job_id: str, *, result: Any) -> JobRecord:
        record = self.get(job_id)
        if record is None:
            raise KeyError(f"unknown job: {job_id}")
        updated = replace(record, status=JOB_STATUS_SUCCEEDED, result=result, error=None, updated_at=utc_now())
        self._persist(updated)
        return updated

    def mark_failed(self, job_id: str, *, error: str) -> JobRecord:
        record = self.get(job_id)
        if record is None:
            raise KeyError(f"unknown job: {job_id}")
        updated = replace(record, status=JOB_STATUS_FAILED, result=None, error=error, updated_at=utc_now())
        self._persist(updated)
        return updated

    def snapshot(self) -> dict[str, Any]:
        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*), MIN(created_at), MIN(updated_at)
                FROM jobs
                GROUP BY status
                """
            ).fetchall()
        now = utc_now()
        counts: dict[str, int] = {status: 0 for status in sorted(JOB_STATUSES)}
        oldest_created_age_ms: dict[str, float | None] = {status: None for status in sorted(JOB_STATUSES)}
        oldest_updated_age_ms: dict[str, float | None] = {status: None for status in sorted(JOB_STATUSES)}
        for status, count, oldest_created, oldest_updated in rows:
            counts[str(status)] = int(count)
            if oldest_created is not None:
                oldest_created_age_ms[str(status)] = _age_ms(now, oldest_created)
            if oldest_updated is not None:
                oldest_updated_age_ms[str(status)] = _age_ms(now, oldest_updated)
        return {
            "backend": "postgres",
            "counts_by_status": counts,
            "oldest_created_age_ms": oldest_created_age_ms,
            "oldest_updated_age_ms": oldest_updated_age_ms,
        }

    def _persist(self, record: JobRecord) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = %s,
                    result = %s,
                    error = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    record.status,
                    Jsonb(record.result) if record.result is not None else None,
                    record.error,
                    record.updated_at,
                    record.job_id,
                ),
            )


class InMemoryJobStore:
    def __init__(self) -> None:
        self.records: dict[str, JobRecord] = {}

    def create(self, *, session_id: str, action: str, payload: Mapping[str, Any], job_id: str | None = None) -> JobRecord:
        now = utc_now()
        record = JobRecord(
            job_id=job_id or new_job_id(),
            session_id=session_id,
            action=action,
            status=JOB_STATUS_QUEUED,
            payload=dict(payload),
            created_at=now,
            updated_at=now,
        )
        self.records[record.job_id] = record
        return record

    def get(self, job_id: str) -> JobRecord | None:
        return self.records.get(job_id)

    def mark_running(self, job_id: str) -> JobRecord:
        return self._replace(job_id, status=JOB_STATUS_RUNNING, updated_at=utc_now())

    def mark_succeeded(self, job_id: str, *, result: Any) -> JobRecord:
        return self._replace(job_id, status=JOB_STATUS_SUCCEEDED, result=result, error=None, updated_at=utc_now())

    def mark_failed(self, job_id: str, *, error: str) -> JobRecord:
        return self._replace(job_id, status=JOB_STATUS_FAILED, result=None, error=error, updated_at=utc_now())

    def snapshot(self) -> dict[str, Any]:
        now = utc_now()
        counts: dict[str, int] = {status: 0 for status in sorted(JOB_STATUSES)}
        oldest_created_age_ms: dict[str, float | None] = {status: None for status in sorted(JOB_STATUSES)}
        oldest_updated_age_ms: dict[str, float | None] = {status: None for status in sorted(JOB_STATUSES)}
        for record in self.records.values():
            counts[record.status] += 1
            if record.created_at is not None:
                age = _age_ms(now, record.created_at)
                current = oldest_created_age_ms[record.status]
                oldest_created_age_ms[record.status] = age if current is None else max(current, age)
            if record.updated_at is not None:
                age = _age_ms(now, record.updated_at)
                current = oldest_updated_age_ms[record.status]
                oldest_updated_age_ms[record.status] = age if current is None else max(current, age)
        return {
            "backend": "memory",
            "counts_by_status": counts,
            "oldest_created_age_ms": oldest_created_age_ms,
            "oldest_updated_age_ms": oldest_updated_age_ms,
        }

    def _replace(self, job_id: str, **changes: Any) -> JobRecord:
        record = self.records.get(job_id)
        if record is None:
            raise KeyError(f"unknown job: {job_id}")
        updated = replace(record, **changes)
        self.records[job_id] = updated
        return updated


class FakeJobQueue:
    def __init__(self, *, store: JobStore, handler: JobHandler, metrics: MetricsCollector | None = None) -> None:
        self.store = store
        self.handler = handler
        self.metrics = metrics

    def enqueue(self, *, session_id: str, action: str, payload: Mapping[str, Any]) -> JobRecord:
        record = self.store.create(session_id=session_id, action=action, payload=payload)
        self.store.mark_running(record.job_id)
        started_at = time.perf_counter()
        token = None
        correlation_id = payload.get("correlation_id")
        if isinstance(correlation_id, str) and correlation_id:
            token = set_correlation_id(correlation_id)
        log_event(LOGGER, "worker_job_started", job_id=record.job_id, session_id=session_id, action=action)
        try:
            result = self.handler(job_id=record.job_id, session_id=session_id, action=action, payload=payload)
        except Exception as exc:
            duration_ms = (time.perf_counter() - started_at) * 1000
            if self.metrics is not None:
                self.metrics.record_job_duration(duration_ms=duration_ms)
                self.metrics.record_job_terminal(status=JOB_STATUS_FAILED, action=action)
            log_event(
                LOGGER,
                "worker_job_failed",
                job_id=record.job_id,
                session_id=session_id,
                action=action,
                duration_ms=round(duration_ms, 3),
                error_type=type(exc).__name__,
            )
            if token is not None:
                reset_correlation_id(token)
            return self.store.mark_failed(record.job_id, error=str(exc))
        duration_ms = (time.perf_counter() - started_at) * 1000
        if self.metrics is not None:
            self.metrics.record_job_duration(duration_ms=duration_ms)
            self.metrics.record_job_terminal(status=JOB_STATUS_SUCCEEDED, action=action)
        log_event(
            LOGGER,
            "worker_job_completed",
            job_id=record.job_id,
            session_id=session_id,
            action=action,
            duration_ms=round(duration_ms, 3),
        )
        if token is not None:
            reset_correlation_id(token)
        return self.store.mark_succeeded(record.job_id, result=result)

    def get_job(self, job_id: str) -> JobRecord | None:
        return self.store.get(job_id)

    def snapshot(self) -> dict[str, Any]:
        return self.store.snapshot()


def new_job_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


def _age_ms(now: datetime, then: datetime) -> float:
    if then.tzinfo is None:
        then = then.replace(tzinfo=UTC)
    return max(0.0, (now - then).total_seconds() * 1000)


def _job_record_from_row(row: Any) -> JobRecord:
    return JobRecord(
        job_id=row[0],
        session_id=row[1],
        action=row[2],
        status=row[3],
        payload=row[4],
        result=row[5],
        error=row[6],
        created_at=row[7],
        updated_at=row[8],
    )
