"""Worker process entrypoint: `python -m services.worker.run`.

Builds the same stores and design handler the API uses, registers the job task
on a Celery app, and starts consuming from Redis. Everything is built inside
`build_worker_app()` and not at import time, so importing this module (for
tests, or by Celery itself) never opens a database connection or loads the
embedding model.
"""

from __future__ import annotations

import sys
from typing import Any

from packages.application.jobs import PostgresJobStore
from services.worker.celery_app import build_celery_app, register_job_task


def build_worker_app() -> Any:
    # Imported here: local_app pulls in the whole retrieval stack, which the
    # queue adapter in celery_app.py deliberately does not depend on.
    from services.api.local_app import build_job_runtime

    _config, stores, handler = build_job_runtime()
    assert handler is not None
    job_store = stores["job_store"]
    if not isinstance(job_store, PostgresJobStore):
        raise RuntimeError("The worker requires the Postgres job store; app tables were not found.")
    app = build_celery_app()
    register_job_task(app, store=job_store, handler=handler)
    return app


def main(argv: list[str] | None = None) -> None:
    app = build_worker_app()
    args = list(sys.argv[1:] if argv is None else argv)
    # Celery's default prefork pool does not work on Windows, where it dies with
    # a PermissionError in the child. The solo pool runs tasks in the worker's
    # main thread, which is correct on every platform for one job at a time.
    if sys.platform == "win32" and not any(a.startswith("--pool") or a == "-P" for a in args):
        args.append("--pool=solo")
    app.worker_main(["worker", "--loglevel=INFO", *args])


if __name__ == "__main__":
    main()
