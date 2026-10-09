from __future__ import annotations

import os
import time
from typing import Any, Callable, Mapping

from packages.application.observability import MetricsCollector, reset_correlation_id, set_correlation_id
from packages.application.jobs import JobHandler, JobRecord, JobStore


DEFAULT_JOB_TASK_NAME = "construct.jobs.run"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def build_celery_app(*, redis_url: str | None = None, celery_factory: Callable[..., Any] | None = None) -> Any:
    factory = celery_factory or _import_celery_factory()
    broker_url = redis_url or os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)
    app = factory(
        "construct-worker",
        broker=broker_url,
        backend=broker_url,
        include=("services.worker.celery_app",),
    )
    conf = getattr(app, "conf", None)
    if conf is not None and hasattr(conf, "update"):
        conf.update(
            # Acknowledge only after the task finishes, and put the message back
            # if the worker process dies mid-task. Without this a worker killed
            # during a run loses the message and the job stays "running" forever.
            # The cost is at-least-once delivery: a redelivered job may run twice.
            task_acks_late=True,
            task_reject_on_worker_lost=True,
            # One message at a time per worker process: design jobs are long, so
            # prefetching would park queued jobs behind a busy worker while an
            # idle one sits empty.
            worker_prefetch_multiplier=1,
        )
    return app


class CeleryJobQueue:
    def __init__(self, *, store: JobStore, celery_app: Any, task_name: str = DEFAULT_JOB_TASK_NAME) -> None:
        self.store = store
        self.celery_app = celery_app
        self.task_name = task_name

    def enqueue(self, *, session_id: str, action: str, payload: Mapping[str, Any]) -> JobRecord:
        record = self.store.create(session_id=session_id, action=action, payload=payload)
        self.celery_app.send_task(
            self.task_name,
            kwargs={
                "job_id": record.job_id,
                "session_id": session_id,
                "action": action,
                "payload": dict(payload),
            },
        )
        return record

    def get_job(self, job_id: str) -> JobRecord | None:
        return self.store.get(job_id)

    def snapshot(self) -> dict[str, Any]:
        return self.store.snapshot()


def create_job_task(*, store: JobStore, handler: JobHandler, metrics: MetricsCollector | None = None) -> Callable[..., JobRecord]:
    def run_job(*, job_id: str, session_id: str, action: str, payload: Mapping[str, Any]) -> JobRecord:
        store.mark_running(job_id)
        started_at = time.perf_counter()
        token = None
        correlation_id = payload.get("correlation_id")
        if isinstance(correlation_id, str) and correlation_id:
            token = set_correlation_id(correlation_id)
        try:
            result = handler(job_id=job_id, session_id=session_id, action=action, payload=payload)
        except Exception as exc:
            if metrics is not None:
                metrics.record_job_duration(duration_ms=(time.perf_counter() - started_at) * 1000)
                metrics.record_job_terminal(status="failed", action=action)
            if token is not None:
                reset_correlation_id(token)
            return store.mark_failed(job_id, error=str(exc))
        if metrics is not None:
            metrics.record_job_duration(duration_ms=(time.perf_counter() - started_at) * 1000)
            metrics.record_job_terminal(status="succeeded", action=action)
        if token is not None:
            reset_correlation_id(token)
        return store.mark_succeeded(job_id, result=result)

    return run_job


def register_job_task(
    celery_app: Any,
    *,
    store: JobStore,
    handler: JobHandler,
    metrics: MetricsCollector | None = None,
    task_name: str = DEFAULT_JOB_TASK_NAME,
) -> Callable[..., JobRecord]:
    task = create_job_task(store=store, handler=handler, metrics=metrics)
    decorator = getattr(celery_app, "task", None)
    if callable(decorator):
        def celery_task(**kwargs: Any) -> None:
            # Return nothing to Celery. The JobRecord is already in Postgres, and
            # a dataclass holding datetimes is not JSON serializable, so handing
            # it back made Celery's result backend raise EncodeError after every
            # successful run (seen against a live worker). Setting
            # task_ignore_result on the app did not prevent it.
            task(**kwargs)

        return decorator(name=task_name)(celery_task)
    return task


def _import_celery_factory() -> Callable[..., Any]:
    try:
        from celery import Celery
    except ImportError as exc:
        raise RuntimeError("Celery is not installed; worker queue adapter cannot build a Celery app") from exc
    return Celery
