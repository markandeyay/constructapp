from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient


def _load_create_app() -> Callable[..., Any]:
    try:
        from services.api.app import create_app
    except ImportError as exc:  # pragma: no cover - exercised only when app code is missing locally
        pytest.skip(f"services.api.app is not available in this checkout: {exc}")
    return create_app


class AttrDict(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class SessionHandle(str):
    @property
    def session_id(self) -> str:
        return str(self)

    @property
    def id(self) -> str:
        return str(self)


class JobHandle(str):
    @property
    def job_id(self) -> str:
        return str(self)

    @property
    def id(self) -> str:
        return str(self)


@dataclass
class InMemorySessionStore:
    sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    counter: int = 0

    def create_session(self) -> str:
        self.counter += 1
        session_id = SessionHandle(f"session-{self.counter}")
        self.sessions[str(session_id)] = AttrDict(session_id=str(session_id), turns=[])
        return session_id

    def get_session(self, session_id: str) -> dict[str, Any]:
        if session_id not in self.sessions:
            raise KeyError(session_id)
        return self.sessions[session_id]

    def append_turn(self, session_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        session = self.get_session(session_id)
        turn = self._normalize_turn(*args, **kwargs)
        session["turns"].append(turn)
        return turn

    def _normalize_turn(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        turn: dict[str, Any] = {}
        if args:
            if len(args) == 1 and isinstance(args[0], dict):
                turn.update(args[0])
            elif len(args) >= 2:
                turn["role"] = args[0]
                turn["content"] = args[1]
                if len(args) > 2:
                    turn["extra_args"] = list(args[2:])
        turn.update(kwargs)

        if "content" not in turn:
            for key in ("goal", "instruction", "message", "text", "prompt"):
                if key in turn:
                    turn["content"] = turn[key]
                    break

        if "role" not in turn:
            turn["role"] = turn.get("speaker", "user")

        return turn

    def __getattr__(self, name: str) -> Any:
        aliases = {
            "new_session": self.create_session,
            "start_session": self.create_session,
            "create": self.create_session,
            "create_or_get_session": self.create_session,
            "get": self.get_session,
            "load_session": self.get_session,
            "fetch_session": self.get_session,
            "require_session": self.get_session,
            "append_message": self.append_turn,
            "add_turn": self.append_turn,
            "record_turn": self.append_turn,
            "push_turn": self.append_turn,
            "add_message": self.append_turn,
        }
        if name in aliases:
            return aliases[name]
        raise AttributeError(name)


class SynchronousJobQueue:
    def __init__(self, session_store: InMemorySessionStore) -> None:
        self.session_store = session_store
        self.jobs: dict[str, dict[str, Any]] = {}
        self.counter = 0

    def submit(self, *args: Any, **kwargs: Any) -> str:
        return self._enqueue("submit", *args, **kwargs)

    def get_job(self, job_id: str) -> dict[str, Any]:
        if job_id not in self.jobs:
            raise KeyError(job_id)
        return self.jobs[job_id]

    def snapshot(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for job in self.jobs.values():
            status = str(job["status"])
            counts[status] = counts.get(status, 0) + 1
        return {"backend": "test-memory", "counts_by_status": counts}

    def _enqueue(self, job_type: str, *args: Any, **kwargs: Any) -> str:
        session_id = self._extract_session_id(*args, **kwargs)
        if session_id not in self.session_store.sessions:
            raise KeyError(session_id)

        self.counter += 1
        job_id = JobHandle(f"job-{self.counter}")
        session = self.session_store.sessions[session_id]
        latest_turn = session["turns"][-1] if session["turns"] else None
        payload = self._extract_payload(job_type, *args, **kwargs)
        result = AttrDict(
            job_id=str(job_id),
            job_type=job_type,
            session_id=session_id,
            turn_count=len(session["turns"]),
            latest_turn=latest_turn,
            payload=payload,
            result_text=f"fake result for {job_type}",
        )
        self.jobs[str(job_id)] = AttrDict(job_id=str(job_id), status="completed", result=result)
        return job_id

    def _extract_session_id(self, *args: Any, **kwargs: Any) -> str:
        for key in ("session_id", "session", "id"):
            value = kwargs.get(key)
            if isinstance(value, str):
                return value

        for value in args:
            if isinstance(value, str) and value.startswith("session-"):
                return value
            if isinstance(value, dict):
                nested = value.get("session_id") or value.get("session")
                if isinstance(nested, str):
                    return nested

        raise KeyError("session_id")

    def _extract_payload(self, job_type: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"job_type": job_type}
        payload.update({k: v for k, v in kwargs.items() if k not in {"session_id", "session", "id"}})
        if args:
            for value in args:
                if isinstance(value, dict):
                    payload.update(value)
                elif isinstance(value, str) and value not in payload.values():
                    payload.setdefault("text", value)
        for key in ("goal", "instruction", "message", "text", "prompt"):
            if key in payload:
                payload.setdefault("text", payload[key])
                break
        return payload

    def __getattr__(self, name: str) -> Any:
        aliases = {
            "get": self.get_job,
            "load_job": self.get_job,
            "fetch_job": self.get_job,
            "job": self.get_job,
            "result": self.get_job,
        }
        if name in aliases:
            return aliases[name]

        def _submit(*args: Any, **kwargs: Any) -> str:
            return self._enqueue(name, *args, **kwargs)

        return _submit


@pytest.fixture()
def api_client() -> tuple[TestClient, InMemorySessionStore, SynchronousJobQueue]:
    create_app = _load_create_app()
    session_store = InMemorySessionStore()
    job_queue = SynchronousJobQueue(session_store)
    app = create_app(session_store=session_store, job_queue=job_queue)
    return TestClient(app), session_store, job_queue


def test_create_session_returns_session_id(api_client: tuple[TestClient, InMemorySessionStore, SynchronousJobQueue]) -> None:
    client, _, _ = api_client

    response = client.post("/v1/sessions")

    assert response.status_code in {200, 201}
    body = response.json()
    assert body["session_id"]


def test_health_reports_queue_and_model_registry() -> None:
    create_app = _load_create_app()

    registry_records = [
        AttrDict(model_version="candidate-v1", rollout_state="shadow"),
        AttrDict(model_version="retired-v0", rollout_state="retired"),
    ]

    class FakeRegistry:
        def list(self) -> list[AttrDict]:
            return registry_records

    session_store = InMemorySessionStore()
    job_queue = SynchronousJobQueue(session_store)
    client = TestClient(create_app(session_store=session_store, job_queue=job_queue, model_registry=FakeRegistry()))

    response = client.get("/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["queue"]["status"] == "ok"
    assert body["queue"]["backend"] == "test-memory"
    assert body["model_registry"]["count"] == 2
    assert body["model_registry"]["active_versions"] == ["candidate-v1"]


def test_metrics_support_json_and_plaintext(api_client: tuple[TestClient, InMemorySessionStore, SynchronousJobQueue]) -> None:
    client, _, _ = api_client

    client.post("/v1/sessions")
    json_response = client.get("/v1/metrics")
    text_response = client.get("/v1/metrics", headers={"accept": "text/plain"})

    assert json_response.status_code == 200
    body = json_response.json()
    assert body["requests"]["count"] >= 1
    assert body["queue"]["status"] == "ok"
    assert body["model_registry"]["status"] == "ok"
    assert text_response.status_code == 200
    assert "construct_requests_count" in text_response.text


def test_design_dispatches_job_and_poll_returns_synchronous_result(
    api_client: tuple[TestClient, InMemorySessionStore, SynchronousJobQueue],
) -> None:
    client, _, _ = api_client
    session_id = client.post("/v1/sessions").json()["session_id"]

    design_response = client.post(
        f"/v1/sessions/{session_id}/design",
        json={"goal": "build a GFP reporter"},
        headers={"X-Correlation-ID": "trace-design-1"},
    )

    assert design_response.status_code in {200, 202}
    design_body = design_response.json()
    assert design_body["job_id"]

    job_response = client.get(f"/v1/jobs/{design_body['job_id']}")

    assert job_response.status_code == 200
    job_body = job_response.json()
    assert job_body["status"]
    assert job_body["result"]["session_id"] == session_id
    assert job_body["result"]["turn_count"] == 1
    assert job_body["result"]["latest_turn"]["content"] == "build a GFP reporter"
    assert job_body["result"]["payload"]["correlation_id"] == "trace-design-1"
    assert "fake result" in job_body["result"]["result_text"]


def test_refine_appends_a_turn_and_reruns_with_updated_session_context(
    api_client: tuple[TestClient, InMemorySessionStore, SynchronousJobQueue],
) -> None:
    client, _, _ = api_client
    session_id = client.post("/v1/sessions").json()["session_id"]

    first_job_id = client.post(f"/v1/sessions/{session_id}/design", json={"goal": "build a GFP reporter"}).json()[
        "job_id"
    ]
    first_job = client.get(f"/v1/jobs/{first_job_id}").json()

    second_job_id = client.post(
        f"/v1/sessions/{session_id}/refine",
        json={"instruction": "switch the backbone to pLenti-CMV"},
    ).json()["job_id"]
    second_job = client.get(f"/v1/jobs/{second_job_id}").json()

    assert first_job["result"]["turn_count"] == 1
    assert second_job["result"]["turn_count"] == 2
    assert second_job["result"]["latest_turn"]["content"] == "switch the backbone to pLenti-CMV"
    assert second_job["result"]["turn_count"] > first_job["result"]["turn_count"]


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/v1/sessions/{session_id}/design", {}),
        ("/v1/sessions/{session_id}/design", {"goal": []}),
        ("/v1/sessions/{session_id}/refine", {}),
        ("/v1/sessions/{session_id}/refine", {"instruction": []}),
    ],
)
def test_missing_or_malformed_fields_return_422(
    api_client: tuple[TestClient, InMemorySessionStore, SynchronousJobQueue],
    path: str,
    payload: dict[str, Any],
) -> None:
    client, _, _ = api_client
    session_id = client.post("/v1/sessions").json()["session_id"]

    response = client.post(path.format(session_id=session_id), json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["field_errors"]


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/v1/sessions/{session_id}/design", {"goal": "   \n\t  "}),
        ("/v1/sessions/{session_id}/refine", {"instruction": "   \n\t  "}),
    ],
)
def test_blank_text_fields_return_structured_422(
    api_client: tuple[TestClient, InMemorySessionStore, SynchronousJobQueue],
    path: str,
    payload: dict[str, Any],
) -> None:
    client, _, _ = api_client
    session_id = client.post("/v1/sessions").json()["session_id"]

    response = client.post(path.format(session_id=session_id), json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Please fix the highlighted fields and try again."


@pytest.mark.parametrize("path", ["/v1/sessions/does-not-exist/design", "/v1/sessions/does-not-exist/refine"])
def test_invalid_session_returns_404(
    api_client: tuple[TestClient, InMemorySessionStore, SynchronousJobQueue],
    path: str,
) -> None:
    client, _, _ = api_client

    payload = {"goal": "irrelevant"} if path.endswith("/design") else {"instruction": "irrelevant"}
    response = client.post(path, json=payload)

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "session_not_found"
    assert body["error"]["message"] == "Session not found."


def test_missing_job_returns_404(api_client: tuple[TestClient, InMemorySessionStore, SynchronousJobQueue]) -> None:
    client, _, _ = api_client

    response = client.get("/v1/jobs/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "job_not_found"


def test_metrics_include_structured_error_counts(api_client: tuple[TestClient, InMemorySessionStore, SynchronousJobQueue]) -> None:
    client, _, _ = api_client

    client.get("/v1/jobs/does-not-exist")

    body = client.get("/v1/metrics").json()
    assert body["requests"]["http_error_rate"] > 0
    assert body["errors"]["by_code"]["4xx:job_not_found"] == 1
    assert body["errors"]["by_code"]["path:/v1/jobs/does-not-exist:job_not_found"] == 1


def test_job_polling_response_exposes_retry_hint_and_timestamps() -> None:
    create_app = _load_create_app()
    created_at = datetime(2026, 6, 6, 12, 0, tzinfo=UTC)

    class FixedJobQueue:
        def get_job(self, job_id: str) -> AttrDict:
            return AttrDict(
                job_id=job_id,
                status="running",
                result=None,
                error=None,
                created_at=created_at,
                updated_at=created_at,
            )

    client = TestClient(create_app(job_queue=FixedJobQueue()))

    response = client.get("/v1/jobs/job-running")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["retry_after_ms"] == 750
    assert body["created_at"] == "2026-06-06T12:00:00Z"


def test_failed_job_response_includes_structured_error_detail() -> None:
    create_app = _load_create_app()

    class FixedJobQueue:
        def get_job(self, job_id: str) -> AttrDict:
            return AttrDict(
                job_id=job_id,
                status="failed",
                result=None,
                error="pipeline unavailable",
            )

    client = TestClient(create_app(job_queue=FixedJobQueue()))

    response = client.get("/v1/jobs/job-failed")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_detail"]["code"] == "job_failed"
    assert body["error_detail"]["message"] == "The design job failed before producing a result."
    assert body["error_detail"]["details"] == {}


def test_rate_limited_session_creation_returns_structured_429() -> None:
    from services.api.app import RateLimitConfig, RateLimitRule, create_app

    client = TestClient(
        create_app(
            rate_limit_config=RateLimitConfig(
                session_create=RateLimitRule(limit=1, window_seconds=60),
            )
        )
    )

    assert client.post("/v1/sessions").status_code == 201
    response = client.post("/v1/sessions")

    assert response.status_code == 429
    assert response.headers["Retry-After"]
    body = response.json()
    assert body["error"]["code"] == "rate_limited"
    assert body["error"]["retryable"] is True


def test_rate_limited_job_enqueue_is_scoped_to_session() -> None:
    from services.api.app import RateLimitConfig, RateLimitRule, create_app

    session_store = InMemorySessionStore()
    job_queue = SynchronousJobQueue(session_store)
    client = TestClient(
        create_app(
            session_store=session_store,
            job_queue=job_queue,
            rate_limit_config=RateLimitConfig(job_enqueue=RateLimitRule(limit=1, window_seconds=60)),
        )
    )
    first_session = client.post("/v1/sessions").json()["session_id"]
    second_session = client.post("/v1/sessions").json()["session_id"]

    assert client.post(f"/v1/sessions/{first_session}/design", json={"goal": "build reporter"}).status_code == 202
    limited = client.post(f"/v1/sessions/{first_session}/refine", json={"instruction": "switch marker"})
    other_session = client.post(f"/v1/sessions/{second_session}/design", json={"goal": "build reporter"})

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert other_session.status_code == 202


def test_job_queue_unavailable_returns_retryable_503() -> None:
    create_app = _load_create_app()
    session_store = InMemorySessionStore()

    class BrokenJobQueue:
        def submit(self, *args: Any, **kwargs: Any) -> str:
            del args, kwargs
            raise RuntimeError("redis unavailable")

        def get_job(self, job_id: str) -> dict[str, Any] | None:
            del job_id
            return None

    client = TestClient(create_app(session_store=session_store, job_queue=BrokenJobQueue()))
    session_id = client.post("/v1/sessions").json()["session_id"]

    response = client.post(f"/v1/sessions/{session_id}/design", json={"goal": "build reporter"})

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "job_queue_unavailable"
    assert body["error"]["retryable"] is True
    assert "redis unavailable" not in body["error"]["message"]


def test_typed_job_error_payload_is_rendered_without_raw_internal_details() -> None:
    create_app = _load_create_app()

    class FixedJobQueue:
        def get_job(self, job_id: str) -> AttrDict:
            return AttrDict(
                job_id=job_id,
                status="failed",
                result=None,
                error='{"code":"model_provider_unavailable","message":"The model provider is temporarily unavailable.","retryable":true,"stage":"generation"}',
            )

    client = TestClient(create_app(job_queue=FixedJobQueue()))

    response = client.get("/v1/jobs/job-failed")

    assert response.status_code == 200
    detail = response.json()["error_detail"]
    assert detail["code"] == "model_provider_unavailable"
    assert detail["message"] == "The model provider is temporarily unavailable."
    assert detail["retryable"] is True
    assert detail["details"] == {"stage": "generation"}
