from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Protocol
from urllib.error import HTTPError, URLError

from Bio import Entrez

from packages.core.schemas import Plasmid
from packages.data_pipeline.ingest.genbank import (
    GenbankConfigError,
    GenbankHttpError,
    GenbankIngestionError,
    IngestionResult,
    ObjectStore,
    PlasmidRepository,
    PostgresPlasmidRepository,
    S3TextObjectStore,
    env,
    load_dotenv,
    map_genbank_text_to_plasmid,
)


SOURCE = "curated_seed"
PLASMID_SOURCE = "genbank"
DEFAULT_MANIFEST = Path(__file__).with_name("curated_seed_manifest.yaml")
PLACEHOLDER_EMAILS = {"", "researcher@example.com", "user@example.com", "your.email@example.com"}


class CuratedSeedClient(Protocol):
    def fetch_genbank(self, accession: str) -> str: ...


@dataclass(frozen=True)
class CuratedSeedRecord:
    id: str
    name: str
    category: str
    source: str
    accession: str
    expected_length_bp: int | None = None
    expected_topology: str | None = None
    curation_notes: str = ""
    citations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CuratedSeedConfig:
    manifest_path: Path = DEFAULT_MANIFEST
    email: str = ""
    api_key: str | None = None
    tool: str = "construct-plasmid-design"
    database_url: str = "postgresql://plasmid:plasmid@localhost:5432/plasmid_design"
    object_store_endpoint: str = "http://localhost:9000"
    object_store_bucket: str = "plasmid-design-local"
    object_store_access_key: str = "minioadmin"
    object_store_secret_key: str = "minioadmin"
    requests_per_second: float = 3.0
    max_retries: int = 3
    backoff_seconds: float = 2.0

    @classmethod
    def from_env(cls, *, manifest_path: Path | None = None) -> CuratedSeedConfig:
        dotenv = load_dotenv(Path(".env"))
        api_key = env("NCBI_API_KEY", "", dotenv) or None
        default_rps = "10.0" if api_key else "3.0"
        return cls(
            manifest_path=manifest_path or Path(env("CURATED_SEED_MANIFEST", str(DEFAULT_MANIFEST), dotenv)),
            email=env("NCBI_EMAIL", "", dotenv),
            api_key=api_key,
            tool=env("NCBI_TOOL", "construct-plasmid-design", dotenv),
            database_url=env("DATABASE_URL", "postgresql://plasmid:plasmid@localhost:5432/plasmid_design", dotenv),
            object_store_endpoint=env("OBJECT_STORE_ENDPOINT", "http://localhost:9000", dotenv),
            object_store_bucket=env("OBJECT_STORE_BUCKET", "plasmid-design-local", dotenv),
            object_store_access_key=env("OBJECT_STORE_ACCESS_KEY", "minioadmin", dotenv),
            object_store_secret_key=env("OBJECT_STORE_SECRET_KEY", "minioadmin", dotenv),
            requests_per_second=float(env("NCBI_REQUESTS_PER_SECOND", default_rps, dotenv)),
            max_retries=int(env("NCBI_MAX_RETRIES", "3", dotenv)),
            backoff_seconds=float(env("NCBI_BACKOFF_SECONDS", "2.0", dotenv)),
        )

    def validate_for_real_network(self) -> None:
        if self.email.strip().lower() in PLACEHOLDER_EMAILS:
            raise GenbankConfigError(
                "NCBI_EMAIL must be set to a real contact email before using Entrez",
                details={"current_value": self.email or "<empty>"},
            )
        max_allowed = 10.0 if self.api_key else 3.0
        if self.requests_per_second <= 0 or self.requests_per_second > max_allowed:
            raise GenbankConfigError(
                "configured NCBI rate limit exceeds published guidance",
                details={"configured": self.requests_per_second, "max_allowed": max_allowed},
            )


class EntrezCuratedSeedClient:
    def __init__(self, config: CuratedSeedConfig) -> None:
        Entrez.email = config.email
        Entrez.tool = config.tool
        Entrez.api_key = config.api_key
        self.min_interval_seconds = 1.0 / config.requests_per_second
        self.max_retries = config.max_retries
        self.backoff_seconds = config.backoff_seconds
        self._last_request_at: float | None = None

    def fetch_genbank(self, accession: str) -> str:
        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            self._wait()
            try:
                with Entrez.efetch(db="nuccore", id=accession, rettype="gb", retmode="text") as handle:
                    return handle.read()
            except (HTTPError, URLError, RuntimeError, OSError) as exc:
                last_error = str(exc)
                if attempt >= self.max_retries:
                    break
                time.sleep(self.backoff_seconds * (2**attempt))
        raise GenbankHttpError("NCBI Entrez curated seed fetch failed", details={"last_error": last_error})

    def _wait(self) -> None:
        if self._last_request_at is None:
            self._last_request_at = time.monotonic()
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        self._last_request_at = time.monotonic()


def load_manifest(path: Path) -> list[CuratedSeedRecord]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GenbankConfigError("curated seed manifest must be JSON-compatible YAML") from exc
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise GenbankConfigError("curated seed manifest has no records")
    return [parse_manifest_record(record) for record in records]


def parse_manifest_record(raw: dict[str, Any]) -> CuratedSeedRecord:
    if raw.get("source") != "ncbi":
        raise GenbankConfigError(
            "curated seed manifest currently allows only NCBI-backed records",
            details={"id": raw.get("id"), "source": raw.get("source")},
        )
    return CuratedSeedRecord(
        id=str(raw["id"]),
        name=str(raw["name"]),
        category=str(raw["category"]),
        source=str(raw["source"]),
        accession=str(raw["accession"]),
        expected_length_bp=raw.get("expected_length_bp"),
        expected_topology=raw.get("expected_topology"),
        curation_notes=str(raw.get("curation_notes") or ""),
        citations=[str(url) for url in raw.get("citations", [])],
    )


def run_curated_seed_ingestion(
    config: CuratedSeedConfig,
    *,
    client: CuratedSeedClient,
    object_store: ObjectStore,
    repository: PlasmidRepository,
) -> IngestionResult:
    records = load_manifest(config.manifest_path)
    repository.ensure_schema()
    run_id = repository.start_run(source=SOURCE, mode="seed", started_at=datetime.now(UTC))
    result = IngestionResult(run_id=run_id)
    try:
        for record in records:
            result.records_seen += 1
            key = raw_cache_key(record)
            try:
                if not object_store.exists(key):
                    object_store.put_text(key, client.fetch_genbank(record.accession))
                raw = object_store.get_text(key)
                plasmid = map_curated_record_to_plasmid(record, raw, raw_ref=key)
                repository.upsert_plasmid(plasmid)
                result.records_upserted += 1
            except GenbankIngestionError as exc:
                result.errors.append(exc.to_error_record(record.id))
            except Exception as exc:
                result.errors.append({"code": "unexpected_error", "accession": record.accession, "message": str(exc)})
        return result
    finally:
        repository.finish_run(
            run_id,
            finished_at=datetime.now(UTC),
            records_seen=result.records_seen,
            records_upserted=result.records_upserted,
            errors=result.errors,
        )


def raw_cache_key(record: CuratedSeedRecord) -> str:
    safe_id = record.id.replace("/", "_").replace("\\", "_")
    return f"raw/curated/{safe_id}.gb"


def map_curated_record_to_plasmid(record: CuratedSeedRecord, raw_text: str, *, raw_ref: str) -> Plasmid:
    plasmid = map_genbank_text_to_plasmid(raw_text, raw_ref=raw_ref)
    use_cases = [record.category]
    if record.curation_notes:
        use_cases.append(record.curation_notes)
    use_cases.extend(plasmid.use_cases)
    return plasmid.model_copy(
        update={
            "id": f"curated:{record.id}",
            "source": PLASMID_SOURCE,
            "name": record.name,
            "raw_ref": raw_ref,
            "use_cases": dedupe(use_cases),
            "annotation_complete": False,
        }
    )


def dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = value.strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest the curated parser-calibration seed manifest.")
    parser.add_argument("--manifest", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = CuratedSeedConfig.from_env(manifest_path=args.manifest)
    try:
        config.validate_for_real_network()
        result = run_curated_seed_ingestion(
            config,
            client=EntrezCuratedSeedClient(config),
            object_store=S3TextObjectStore(config),
            repository=PostgresPlasmidRepository(config.database_url),
        )
    except GenbankIngestionError as exc:
        print(json.dumps({"error": exc.to_error_record()}, indent=2))
        return 2
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "records_seen": result.records_seen,
                "records_upserted": result.records_upserted,
                "errors": result.errors,
            },
            indent=2,
        )
    )
    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
