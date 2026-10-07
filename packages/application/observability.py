from __future__ import annotations

import json
import logging
import os
from collections import Counter
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from statistics import median
from typing import Any


_correlation_id: ContextVar[str | None] = ContextVar("construct_correlation_id", default=None)


class JsonFormatter(logging.Formatter):
    """Small JSON log formatter for production-like environments."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = getattr(record, "correlation_id", None) or get_correlation_id()
        if correlation_id:
            payload["correlation_id"] = correlation_id
        fields = getattr(record, "construct_fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        return json.dumps(payload, sort_keys=True, default=str)


def configure_logging(*, production: bool | None = None) -> None:
    """Configure process logging once with dev text or JSON production output."""

    json_mode = production if production is not None else _json_logging_enabled()
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    if json_mode:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    root.setLevel(os.environ.get("CONSTRUCT_LOG_LEVEL", "INFO"))


def set_correlation_id(correlation_id: str) -> Token[str | None]:
    return _correlation_id.set(correlation_id)


def reset_correlation_id(token: Token[str | None]) -> None:
    _correlation_id.reset(token)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    correlation_id = fields.pop("correlation_id", None) or get_correlation_id()
    logger.info(
        event,
        extra={
            "correlation_id": correlation_id,
            "construct_fields": {"event": event, **fields},
        },
    )


@dataclass
class MetricsCollector:
    """In-memory metrics snapshot for local/API observability smoke tests."""

    request_latencies_ms: list[float] = field(default_factory=list)
    request_count: int = 0
    request_error_count: int = 0
    http_error_count: int = 0
    job_durations_ms: list[float] = field(default_factory=list)
    model_inference_times_ms: list[float] = field(default_factory=list)
    request_counts: Counter[str] = field(default_factory=Counter)
    error_counts: Counter[str] = field(default_factory=Counter)
    job_terminal_counts: Counter[str] = field(default_factory=Counter)
    max_samples: int = 1_000

    def record_request(self, *, latency_ms: float, status_code: int, method: str | None = None, path: str | None = None) -> None:
        self.request_count += 1
        _append_sample(self.request_latencies_ms, latency_ms, max_samples=self.max_samples)
        if method and path:
            self.request_counts[f"{method} {path} {status_code}"] += 1
        if status_code >= 400:
            self.http_error_count += 1
        if status_code >= 500:
            self.request_error_count += 1

    def record_job_duration(self, *, duration_ms: float) -> None:
        _append_sample(self.job_durations_ms, duration_ms, max_samples=self.max_samples)

    def record_model_inference(self, *, duration_ms: float) -> None:
        _append_sample(self.model_inference_times_ms, duration_ms, max_samples=self.max_samples)

    def record_error(self, *, code: str, status_code: int, path: str | None = None) -> None:
        status_family = f"{status_code // 100}xx"
        self.error_counts[f"{status_family}:{code}"] += 1
        if path:
            self.error_counts[f"path:{path}:{code}"] += 1

    def record_job_terminal(self, *, status: str, action: str | None = None) -> None:
        self.job_terminal_counts[f"status:{status}"] += 1
        if action:
            self.job_terminal_counts[f"action:{action}:status:{status}"] += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "requests": {
                "count": self.request_count,
                "error_rate": self.request_error_count / self.request_count if self.request_count else 0.0,
                "http_error_rate": self.http_error_count / self.request_count if self.request_count else 0.0,
                "latency_ms": _latency_summary(self.request_latencies_ms),
                "by_route": dict(sorted(self.request_counts.items())),
            },
            "errors": {
                "count": sum(self.error_counts.values()),
                "by_code": dict(sorted(self.error_counts.items())),
            },
            "jobs": {
                "count": len(self.job_durations_ms),
                "duration_ms": _latency_summary(self.job_durations_ms),
                "terminal": dict(sorted(self.job_terminal_counts.items())),
            },
            "model_inference": {
                "count": len(self.model_inference_times_ms),
                "time_ms": _latency_summary(self.model_inference_times_ms),
            },
        }


def _json_logging_enabled() -> bool:
    return os.environ.get("CONSTRUCT_LOG_FORMAT", "").lower() == "json" or os.environ.get("CONSTRUCT_ENV", "").lower() == "production"


def _latency_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    sorted_values = sorted(values)
    return {
        "p50": float(median(sorted_values)),
        "p95": _percentile(sorted_values, 0.95),
        "p99": _percentile(sorted_values, 0.99),
    }


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    index = min(len(sorted_values) - 1, max(0, round((len(sorted_values) - 1) * percentile)))
    return float(sorted_values[index])


def _append_sample(values: list[float], value: float, *, max_samples: int) -> None:
    values.append(value)
    if len(values) > max_samples:
        del values[: len(values) - max_samples]
