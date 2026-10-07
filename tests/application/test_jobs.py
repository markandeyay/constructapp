from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from packages.application.jobs import (
    JOB_STATUS_FAILED,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SUCCEEDED,
    FakeJobQueue,
    InMemoryJobStore,
    PostgresJobStore,
)
from packages.application.observability import MetricsCollector, get_correlation_id
from services.worker import CeleryJobQueue, build_celery_app, create_job_task, register_job_task


def test_in_memory_store_tracks_job_state_transitions() -> None:
    store = InMemoryJobStore()

    created = store.create(session_id="session-1", action="design", payload={"goal": "build a vector"})
    running = store.mark_running(created.job_id)
    finished = store.mark_succeeded(created.job_id, result={"design_id": "design-1"})

    assert created.status == JOB_STATUS_QUEUED
    assert running.status == JOB_STATUS_RUNNING
    assert finished.status == JOB_STATUS_SUCCEEDED
    assert finished.result == {"design_id": "design-1"}
    assert store.get(created.job_id) == finished
    snapshot = store.snapshot()
    assert snapshot["counts_by_status"][JOB_STATUS_SUCCEEDED] == 1
    assert snapshot["counts_by_status"][JOB_STATUS_QUEUED] == 0


def test_fake_job_queue_runs_handler_synchronously_and_stores_success() -> None:
    store = InMemoryJobStore()
    metrics = MetricsCollector()

    queue = FakeJobQueue(
        store=store,
        metrics=metrics,
        handler=lambda *, job_id, session_id, action, payload: {
            "job_id": job_id,
            "session_id": session_id,
            "action": action,
            "goal": payload["goal"],
            "correlation_id": get_correlation_id(),
        },
    )

    record = queue.enqueue(
        session_id="session-2",
        action="design",
        payload={"goal": "strong bacterial promoter", "correlation_id": "trace-job-1"},
    )

    assert record.status == JOB_STATUS_SUCCEEDED
    assert record.result == {
        "job_id": record.job_id,
        "session_id": "session-2",
        "action": "design",
        "goal": "strong bacterial promoter",
        "correlation_id": "trace-job-1",
    }
    assert store.get(record.job_id) == record
    assert get_correlation_id() is None
    assert metrics.snapshot()["jobs"]["terminal"]["action:design:status:succeeded"] == 1


def test_fake_job_queue_captures_handler_failure() -> None:
    store = InMemoryJobStore()

    def fail_handler(*, job_id: str, session_id: str, action: str, payload: dict[str, Any]) -> Any:
        del job_id, session_id, action, payload
        raise ValueError("pipeline unavailable")

    queue = FakeJobQueue(store=store, handler=fail_handler)

    record = queue.enqueue(session_id="session-3", action="refine", payload={"instruction": "swap marker"})

    assert record.status == JOB_STATUS_FAILED
    assert record.error == "pipeline unavailable"
    assert store.get(record.job_id) == record


def test_postgres_job_store_persists_and_reads_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, tuple[Any, ...] | None]] = []
    created_at = datetime(2026, 6, 2, tzinfo=UTC)
    updated_at = datetime(2026, 6, 2, 0, 1, tzinfo=UTC)
    select_rows = [
        ("job-123", "session-9", "design", JOB_STATUS_QUEUED, {"goal": "alpha"}, None, None, created_at, created_at),
        ("job-123", "session-9", "design", JOB_STATUS_RUNNING, {"goal": "alpha"}, None, None, created_at, updated_at),
        ("job-123", "session-9", "design", JOB_STATUS_SUCCEEDED, {"goal": "alpha"}, {"design_id": "done"}, None, created_at, updated_at),
    ]

    class FakeCursor:
        def __init__(self, row: Any) -> None:
            self.row = row

        def fetchone(self) -> Any:
            return self.row

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb

        def execute(self, query: str, params: tuple[Any, ...] | None = None) -> FakeCursor:
            calls.append((" ".join(query.split()), params))
            if "SELECT id, session_id, kind AS action, status, payload, result, error, created_at, updated_at" in query:
                return FakeCursor(select_rows.pop(0))
            return FakeCursor(None)

    monkeypatch.setattr("packages.application.jobs.psycopg.connect", lambda _: FakeConnection())
    monkeypatch.setattr("packages.application.jobs.utc_now", lambda: updated_at)

    store = PostgresJobStore("postgresql://example")
    store.ensure_schema()
    created = store.create(session_id="session-9", action="design", payload={"goal": "alpha"}, job_id="job-123")
    running = store.mark_running("job-123")
    finished = store.mark_succeeded("job-123", result={"design_id": "done"})

    assert created.job_id == "job-123"
    assert running.status == JOB_STATUS_RUNNING
    assert finished.status == JOB_STATUS_SUCCEEDED
    assert finished.result == {"design_id": "done"}
    assert any("CREATE TABLE IF NOT EXISTS jobs" in query for query, _ in calls)
    assert any("INSERT INTO jobs" in query for query, _ in calls)
    assert any("UPDATE jobs SET status = %s," in query for query, _ in calls)


def test_celery_job_queue_enqueues_without_executing() -> None:
    store = InMemoryJobStore()

    @dataclass
    class FakeCeleryApp:
        sent: list[tuple[str, dict[str, Any]]]

        def send_task(self, task_name: str, kwargs: dict[str, Any]) -> None:
            self.sent.append((task_name, kwargs))

    app = FakeCeleryApp(sent=[])
    queue = CeleryJobQueue(store=store, celery_app=app)

    record = queue.enqueue(session_id="session-10", action="design", payload={"goal": "reporter plasmid"})

    assert record.status == JOB_STATUS_QUEUED
    assert app.sent == [
        (
            "construct.jobs.run",
            {
                "job_id": record.job_id,
                "session_id": "session-10",
                "action": "design",
                "payload": {"goal": "reporter plasmid"},
            },
        )
    ]


def test_create_job_task_updates_store_for_success_and_failure() -> None:
    store = InMemoryJobStore()
    success_record = store.create(session_id="session-11", action="design", payload={"goal": "vector"})

    success_task = create_job_task(
        store=store,
        handler=lambda *, job_id, session_id, action, payload: f"{job_id}:{session_id}:{action}:{payload['goal']}",
    )
    finished = success_task(
        job_id=success_record.job_id,
        session_id="session-11",
        action="design",
        payload={"goal": "vector", "correlation_id": "trace-celery-1"},
    )

    failed_record = store.create(session_id="session-12", action="refine", payload={"instruction": "trim payload"})

    def fail_handler(*, job_id: str, session_id: str, action: str, payload: dict[str, Any]) -> Any:
        del job_id, session_id, action, payload
        raise RuntimeError("worker failed")

    failed = create_job_task(store=store, handler=fail_handler)(
        job_id=failed_record.job_id,
        session_id="session-12",
        action="refine",
        payload={"instruction": "trim payload"},
    )

    assert finished.status == JOB_STATUS_SUCCEEDED
    assert finished.result == f"{success_record.job_id}:session-11:design:vector"
    assert failed.status == JOB_STATUS_FAILED
    assert failed.error == "worker failed"
    assert get_correlation_id() is None


def test_create_job_task_restores_correlation_id_and_records_metrics() -> None:
    store = InMemoryJobStore()
    metrics = MetricsCollector()
    record = store.create(session_id="session-13", action="design", payload={"goal": "vector"})

    task = create_job_task(
        store=store,
        metrics=metrics,
        handler=lambda *, job_id, session_id, action, payload: {
            "job_id": job_id,
            "session_id": session_id,
            "action": action,
            "correlation_id": get_correlation_id(),
        },
    )

    finished = task(
        job_id=record.job_id,
        session_id="session-13",
        action="design",
        payload={"goal": "vector", "correlation_id": "trace-worker-1"},
    )

    assert finished.status == JOB_STATUS_SUCCEEDED
    assert finished.result["job_id"] == record.job_id
    assert finished.result["correlation_id"] == "trace-worker-1"
    assert get_correlation_id() is None
    assert metrics.snapshot()["jobs"]["terminal"]["action:design:status:succeeded"] == 1


def test_register_job_task_uses_celery_decorator_and_build_app_reads_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryJobStore()

    @dataclass
    class FakeCeleryApp:
        name: str | None = None
        wrapped: Any | None = None

        def task(self, *, name: str) -> Any:
            self.name = name

            def decorator(fn: Any) -> Any:
                self.wrapped = fn
                return fn

            return decorator

    registered_app = FakeCeleryApp()
    task = register_job_task(
        registered_app,
        store=store,
        handler=lambda *, job_id, session_id, action, payload: {
            "job_id": job_id,
            "session_id": session_id,
            "action": action,
            **payload,
        },
    )

    assert registered_app.name == "construct.jobs.run"
    assert task is registered_app.wrapped

    built = build_celery_app(
        redis_url="redis://redis.internal:6379/5",
        celery_factory=lambda *args, **kwargs: {"args": args, "kwargs": kwargs},
    )

    assert built["args"] == ("construct-worker",)
    assert built["kwargs"]["broker"] == "redis://redis.internal:6379/5"
    assert built["kwargs"]["backend"] == "redis://redis.internal:6379/5"
