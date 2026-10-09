from __future__ import annotations

from typing import Any

import pytest

from packages.application.jobs import InMemoryJobStore, PostgresJobStore
from services.worker import run as worker_run
from services.worker.celery_app import register_job_task


def test_registered_celery_task_returns_none_so_the_result_backend_never_sees_a_jobrecord() -> None:
    store = InMemoryJobStore()
    seen: dict[str, Any] = {}

    class App:
        def task(self, *, name: str) -> Any:
            def decorator(fn: Any) -> Any:
                seen["fn"] = fn
                return fn

            return decorator

    register_job_task(App(), store=store, handler=lambda *, job_id, session_id, action, payload: {"ok": True})
    record = store.create(session_id="s", action="design", payload={"text": "x"})

    returned = seen["fn"](job_id=record.job_id, session_id="s", action="design", payload={"text": "x"})

    assert returned is None
    assert store.get(record.job_id).status == "succeeded"


def test_build_worker_app_registers_task_on_postgres_store(monkeypatch: pytest.MonkeyPatch) -> None:
    from services.api import local_app

    handler = object()
    stores = {"job_store": PostgresJobStore("postgresql://example")}
    monkeypatch.setattr(local_app, "build_job_runtime", lambda **kw: (None, stores, handler))
    registered: dict[str, Any] = {}

    class App:
        pass

    monkeypatch.setattr(worker_run, "build_celery_app", lambda: App())
    monkeypatch.setattr(
        worker_run, "register_job_task", lambda app, *, store, handler: registered.update(store=store, handler=handler)
    )

    app = worker_run.build_worker_app()

    assert isinstance(app, App)
    assert registered == {"store": stores["job_store"], "handler": handler}


def test_build_worker_app_refuses_in_memory_store(monkeypatch: pytest.MonkeyPatch) -> None:
    from services.api import local_app

    monkeypatch.setattr(local_app, "build_job_runtime", lambda **kw: (None, {"job_store": InMemoryJobStore()}, object()))
    with pytest.raises(RuntimeError, match="Postgres job store"):
        worker_run.build_worker_app()


def test_main_uses_solo_pool_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[list[str]] = []

    class App:
        def worker_main(self, argv: list[str]) -> None:
            started.append(argv)

    monkeypatch.setattr(worker_run, "build_worker_app", lambda: App())
    monkeypatch.setattr(worker_run.sys, "platform", "win32")
    worker_run.main([])
    assert "--pool=solo" in started[0]
    worker_run.main(["--pool=threads"])
    assert "--pool=solo" not in started[1]
