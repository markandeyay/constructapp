from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from io import StringIO
from pathlib import Path
from typing import Any, Iterable, Protocol
from urllib.error import HTTPError, URLError

import boto3
import psycopg
from Bio import Entrez, SeqIO
from Bio.SeqFeature import SeqFeature
from Bio.SeqRecord import SeqRecord
from botocore.exceptions import ClientError
from psycopg.types.json import Jsonb

from packages.core.schemas import Plasmid
from packages.data_pipeline.marker_terms import contains_marker_term
from packages.data_pipeline.parse.text_signals import contains_signal


SOURCE = "genbank"
DEFAULT_DEV_LIMIT = 10
DEFAULT_STALE_DAYS = 60
# The dev/bulk query is deliberately engineered-vector biased. The earlier
# broad query for plasmid complete sequences mostly returned natural bacterial
# plasmids from environmental/clinical isolates, which are valid GenBank
# records but sparse for expression-cassette parser calibration. This query
# uses NCBI title and sequence-length fields plus nucleotide properties/filters:
# - [Title] narrows to definition-line words such as vector/expression/reporter.
# - [SLEN] constrains sequence length.
# - [PROP] and [FILTER] exclude assembly/master records where possible.
# Docs:
# https://www.ncbi.nlm.nih.gov/books/NBK49540/
# https://www.ncbi.nlm.nih.gov/entrez/query/static/help/Summary_Matrices.html
# Trade-off: high precision for engineered backbones, lower recall for records
# whose title omits "vector" even when the sequence is a synthetic construct.
DEFAULT_QUERY = (
    '("cloning vector"[Title] OR "expression vector"[Title] OR "reporter vector"[Title] '
    'OR "shuttle vector"[Title] OR "lentiviral vector"[Title] OR "retroviral vector"[Title] '
    'OR "plasmid vector"[Title] OR vector[Title]) '
    'AND ("complete sequence"[Title] OR "complete genome"[Title]) '
    "AND 1000:50000[SLEN] AND biomol_genomic[PROP] AND genbank[FILTER] "
    "NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER]"
)
EXPANSION_QUERY = (
    '("expression vector"[Title] OR "T7 expression"[Title] OR "bacterial expression"[Title] '
    'OR "cloning vector"[Title]) '
    "AND (T7[All Fields] OR lac[All Fields] OR tac[All Fields] OR trc[All Fields]) "
    'AND (bla[All Fields] OR "beta-lactamase"[All Fields] OR kan[All Fields] '
    "OR kanamycin[All Fields] OR cat[All Fields] OR chloramphenicol[All Fields]) "
    'AND ("complete sequence"[Title] OR "complete genome"[Title]) '
    "AND 1000:50000[SLEN] AND biomol_genomic[PROP] AND srcdb_genbank[PROP] "
    "NOT gbdiv_con[PROP] NOT wgs[FILTER] NOT tsa[FILTER] "
    "NOT scaffold[Title] NOT contig[Title] NOT chromosome[Title]"
)
REFSEQ_PLASMID_BROAD_QUERY = (
    'plasmid[Title] AND srcdb_refseq[PROP] AND ("complete sequence"[Title] OR "complete genome"[Title]) '
    "AND 1000:50000[SLEN] NOT chromosome[Title] NOT scaffold[Title] NOT contig[Title]"
)
VALID_MODES = ("dev", "bulk", "refresh", "expansion", "refseq_plasmid_broad")
IUPAC_DNA_ALPHABET = frozenset("ACGTRYSWKMBDHVN")
CANONICAL_DNA_ALPHABET = frozenset("ACGT")
PLACEHOLDER_EMAILS = {"", "researcher@example.com", "user@example.com", "your.email@example.com"}
RETRYABLE_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}


class GenbankIngestionError(Exception):
    code = "genbank_ingestion_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}

    def to_error_record(self, accession: str | None = None) -> dict[str, Any]:
        record: dict[str, Any] = {"code": self.code, "message": str(self)}
        if accession is not None:
            record["accession"] = accession
        if self.details:
            record["details"] = self.details
        return record


class GenbankConfigError(GenbankIngestionError):
    code = "config_error"


class GenbankHttpError(GenbankIngestionError):
    code = "http_error"


class GenbankMappingError(GenbankIngestionError):
    code = "mapping_error"


class ObjectStore(Protocol):
    def exists(self, key: str) -> bool: ...

    def is_fresh(self, key: str, max_age: timedelta) -> bool: ...

    def put_text(self, key: str, payload: str) -> None: ...

    def get_text(self, key: str) -> str: ...


class NcbiClient(Protocol):
    def iter_accessions(self, *, limit: int | None = None) -> Iterable[str]: ...

    def fetch_genbank(self, accession: str) -> str: ...


class PlasmidRepository(Protocol):
    def ensure_schema(self) -> None: ...

    def start_run(self, *, source: str, mode: str, started_at: datetime) -> int: ...

    def finish_run(
        self,
        run_id: int,
        *,
        finished_at: datetime,
        records_seen: int,
        records_upserted: int,
        errors: list[dict[str, Any]],
    ) -> None: ...

    def upsert_plasmid(self, plasmid: Plasmid) -> None: ...


@dataclass(frozen=True)
class GenbankIngestionConfig:
    mode: str = "dev"
    limit: int | None = DEFAULT_DEV_LIMIT
    stale_after: timedelta = timedelta(days=DEFAULT_STALE_DAYS)
    query: str = DEFAULT_QUERY
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
    page_size: int = 100
    fetch_rettype: str = "gb"

    @classmethod
    def from_env(cls, *, mode: str, limit: int | None, stale_days: int) -> GenbankIngestionConfig:
        dotenv = load_dotenv(Path(".env"))
        configured_limit = limit
        if mode == "dev" and configured_limit is None:
            configured_limit = int(env("N", str(DEFAULT_DEV_LIMIT), dotenv))
        api_key = env("NCBI_API_KEY", "", dotenv) or None
        default_rps = "10.0" if api_key else "3.0"
        return cls(
            mode=mode,
            limit=configured_limit,
            stale_after=timedelta(days=stale_days),
            query=genbank_query_for_mode(mode, dotenv),
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
            page_size=int(env("NCBI_PAGE_SIZE", "100", dotenv)),
            fetch_rettype=fetch_rettype_for_mode(mode),
        )

    def validate_for_real_network(self) -> None:
        if self.mode not in VALID_MODES:
            raise GenbankConfigError(f"unsupported GenBank ingestion mode: {self.mode}")
        if self.email.strip().lower() in PLACEHOLDER_EMAILS:
            raise GenbankConfigError(
                "NCBI_EMAIL must be set to a real contact email before using Entrez",
                details={"current_value": self.email or "<empty>"},
            )
        if self.requests_per_second <= 0:
            raise GenbankConfigError("NCBI_REQUESTS_PER_SECOND must be positive")
        max_allowed = 10.0 if self.api_key else 3.0
        if self.requests_per_second > max_allowed:
            raise GenbankConfigError(
                "configured NCBI rate limit exceeds published guidance",
                details={"configured": self.requests_per_second, "max_allowed": max_allowed},
            )


@dataclass
class IngestionResult:
    run_id: int
    records_seen: int = 0
    records_upserted: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    filtered: list[dict[str, Any]] = field(default_factory=list)


ENGINEERED_VECTOR_TITLE_TERMS = (
    "cloning vector",
    "expression vector",
    "reporter vector",
    "shuttle vector",
    "lentiviral vector",
    "retroviral vector",
    "plasmid vector",
    "phagemid",
)
NATURAL_CONTEXT_TITLE_TERMS = (
    " strain ",
    " isolate ",
    " unnamed ",
    "chromosomal",
    "chromosome",
)


class RateLimiter:
    def __init__(self, requests_per_second: float) -> None:
        self.min_interval_seconds = 1.0 / requests_per_second
        self._last_request_at: float | None = None

    def wait(self) -> None:
        if self._last_request_at is None:
            self._last_request_at = time.monotonic()
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        self._last_request_at = time.monotonic()


class EntrezNcbiClient:
    def __init__(self, config: GenbankIngestionConfig) -> None:
        Entrez.email = config.email
        Entrez.tool = config.tool
        Entrez.api_key = config.api_key
        self.query = config.query
        self.page_size = config.page_size
        self.max_retries = config.max_retries
        self.backoff_seconds = config.backoff_seconds
        self.rate_limiter = RateLimiter(config.requests_per_second)
        self.fetch_rettype = config.fetch_rettype

    def iter_accessions(self, *, limit: int | None = None) -> Iterable[str]:
        yielded = 0
        retstart = 0
        while True:
            retmax = min(self.page_size, limit - yielded) if limit is not None else self.page_size
            if retmax <= 0:
                return
            search = self._entrez_read(
                lambda: Entrez.esearch(
                    db="nuccore",
                    term=self.query,
                    retstart=retstart,
                    retmax=retmax,
                    sort="relevance",
                )
            )
            ids = [str(item) for item in search.get("IdList", [])]
            if not ids:
                return
            for accession in self._summaries_to_accessions(ids):
                yield accession
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            retstart += len(ids)

    def fetch_genbank(self, accession: str) -> str:
        return self._entrez_text(
            lambda: Entrez.efetch(db="nuccore", id=accession, rettype=self.fetch_rettype, retmode="text")
        )

    def _summaries_to_accessions(self, ids: list[str]) -> Iterable[str]:
        summaries = self._entrez_read(lambda: Entrez.esummary(db="nuccore", id=",".join(ids), retmode="xml"))
        for item in summaries:
            accession = item.get("AccessionVersion") or item.get("Caption")
            if accession:
                yield str(accession)

    def _entrez_read(self, operation: Any) -> Any:
        return self._with_retries(lambda handle: Entrez.read(handle), operation)

    def _entrez_text(self, operation: Any) -> str:
        return self._with_retries(lambda handle: handle.read(), operation)

    def _with_retries(self, reader: Any, operation: Any) -> Any:
        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            self.rate_limiter.wait()
            try:
                with operation() as handle:
                    return reader(handle)
            except HTTPError as exc:
                last_error = str(exc)
                if attempt >= self.max_retries:
                    break
                if exc.code not in RETRYABLE_HTTP_STATUS_CODES:
                    break
                time.sleep(retry_delay_seconds(exc, fallback=self.backoff_seconds * (2**attempt)))
            except (URLError, RuntimeError, OSError) as exc:
                last_error = str(exc)
                if attempt >= self.max_retries:
                    break
                time.sleep(self.backoff_seconds * (2**attempt))
        raise GenbankHttpError("NCBI Entrez request failed", details={"last_error": last_error})


class S3TextObjectStore:
    def __init__(self, config: GenbankIngestionConfig) -> None:
        self.bucket = config.object_store_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=config.object_store_endpoint,
            aws_access_key_id=config.object_store_access_key,
            aws_secret_access_key=config.object_store_secret_key,
            region_name="us-east-1",
        )
        self._ensure_bucket()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def is_fresh(self, key: str, max_age: timedelta) -> bool:
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        last_modified = response["LastModified"]
        if last_modified.tzinfo is None:
            last_modified = last_modified.replace(tzinfo=UTC)
        return datetime.now(UTC) - last_modified <= max_age

    def put_text(self, key: str, payload: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=payload.encode("utf-8"),
            ContentType="chemical/seq-na-genbank",
        )

    def get_text(self, key: str) -> str:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read().decode("utf-8")

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)


class PostgresPlasmidRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def ensure_schema(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS plasmids (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    name TEXT NOT NULL,
                    sequence TEXT NOT NULL,
                    length INTEGER NOT NULL,
                    organism TEXT,
                    vector_type TEXT,
                    markers JSONB NOT NULL DEFAULT '[]'::jsonb,
                    promoters JSONB NOT NULL DEFAULT '[]'::jsonb,
                    publication_doi TEXT,
                    use_cases JSONB NOT NULL DEFAULT '[]'::jsonb,
                    annotation_complete BOOLEAN NOT NULL,
                    raw_ref TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    payload JSONB NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL,
                    finished_at TIMESTAMPTZ,
                    records_seen INTEGER NOT NULL DEFAULT 0,
                    records_upserted INTEGER NOT NULL DEFAULT 0,
                    errors JSONB NOT NULL DEFAULT '[]'::jsonb
                )
                """
            )

    def start_run(self, *, source: str, mode: str, started_at: datetime) -> int:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                """
                INSERT INTO ingestion_runs (source, mode, started_at)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (source, mode, started_at),
            ).fetchone()
            if row is None:
                raise GenbankIngestionError("failed to create ingestion run")
            return int(row[0])

    def finish_run(
        self,
        run_id: int,
        *,
        finished_at: datetime,
        records_seen: int,
        records_upserted: int,
        errors: list[dict[str, Any]],
    ) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                UPDATE ingestion_runs
                SET finished_at = %s,
                    records_seen = %s,
                    records_upserted = %s,
                    errors = %s
                WHERE id = %s
                """,
                (finished_at, records_seen, records_upserted, Jsonb(errors), run_id),
            )

    def upsert_plasmid(self, plasmid: Plasmid) -> None:
        payload = plasmid.model_dump(mode="json")
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                INSERT INTO plasmids (
                    id, source, name, sequence, length, organism, vector_type,
                    markers, promoters, publication_doi, use_cases,
                    annotation_complete, raw_ref, created_at, updated_at, payload
                )
                VALUES (
                    %(id)s, %(source)s, %(name)s, %(sequence)s, %(length)s,
                    %(organism)s, %(vector_type)s, %(markers)s, %(promoters)s,
                    %(publication_doi)s, %(use_cases)s, %(annotation_complete)s,
                    %(raw_ref)s, %(created_at)s, %(updated_at)s, %(payload)s
                )
                ON CONFLICT (id) DO UPDATE
                SET source = EXCLUDED.source,
                    name = EXCLUDED.name,
                    sequence = EXCLUDED.sequence,
                    length = EXCLUDED.length,
                    organism = EXCLUDED.organism,
                    vector_type = EXCLUDED.vector_type,
                    markers = EXCLUDED.markers,
                    promoters = EXCLUDED.promoters,
                    publication_doi = EXCLUDED.publication_doi,
                    use_cases = EXCLUDED.use_cases,
                    annotation_complete = EXCLUDED.annotation_complete,
                    raw_ref = EXCLUDED.raw_ref,
                    updated_at = EXCLUDED.updated_at,
                    payload = EXCLUDED.payload
                """,
                {
                    **payload,
                    "markers": Jsonb(payload["markers"]),
                    "promoters": Jsonb(payload["promoters"]),
                    "use_cases": Jsonb(payload["use_cases"]),
                    "payload": Jsonb(payload),
                },
            )


def run_genbank_ingestion(
    config: GenbankIngestionConfig,
    *,
    client: NcbiClient,
    object_store: ObjectStore,
    repository: PlasmidRepository,
) -> IngestionResult:
    repository.ensure_schema()
    run_id = repository.start_run(source=SOURCE, mode=config.mode, started_at=datetime.now(UTC))
    result = IngestionResult(run_id=run_id)
    try:
        for accession in client.iter_accessions(limit=config.limit):
            result.records_seen += 1
            key = raw_cache_key(accession, mode=config.mode)
            try:
                fetched_cache = False
                if should_fetch_cache(config, object_store, key):
                    raw = client.fetch_genbank(accession)
                    object_store.put_text(key, raw)
                    fetched_cache = True
                cached_raw = object_store.get_text(key)
                try:
                    plasmid = map_genbank_text_to_plasmid(cached_raw, raw_ref=key, expected_accession=accession)
                except GenbankMappingError:
                    if fetched_cache:
                        raise
                    raw = client.fetch_genbank(accession)
                    object_store.put_text(key, raw)
                    plasmid = map_genbank_text_to_plasmid(raw, raw_ref=key, expected_accession=accession)
                filter_reason = engineered_vector_filter_reason(plasmid) if config.mode != "refresh" else None
                if filter_reason is not None:
                    result.filtered.append(
                        {
                            "accession": accession,
                            "id": plasmid.id,
                            "reason": filter_reason,
                            "name": plasmid.name,
                        }
                    )
                    continue
                repository.upsert_plasmid(plasmid)
                result.records_upserted += 1
            except GenbankIngestionError as exc:
                result.errors.append(exc.to_error_record(accession))
            except Exception as exc:
                result.errors.append({"code": "unexpected_error", "accession": accession, "message": str(exc)})
        return result
    finally:
        repository.finish_run(
            run_id,
            finished_at=datetime.now(UTC),
            records_seen=result.records_seen,
            records_upserted=result.records_upserted,
            errors=result.errors,
        )


def should_fetch_cache(config: GenbankIngestionConfig, object_store: ObjectStore, key: str) -> bool:
    if config.mode in {"bulk", "expansion", "refseq_plasmid_broad"}:
        return not object_store.exists(key)
    return not object_store.is_fresh(key, config.stale_after)


def genbank_query_for_mode(mode: str, dotenv: dict[str, str]) -> str:
    configured = env("NCBI_GENBANK_QUERY", "", dotenv)
    if configured:
        return configured
    if mode == "refseq_plasmid_broad":
        return env("NCBI_GENBANK_REFSEQ_PLASMID_BROAD_QUERY", REFSEQ_PLASMID_BROAD_QUERY, dotenv)
    if mode == "expansion":
        return env("NCBI_GENBANK_EXPANSION_QUERY", EXPANSION_QUERY, dotenv)
    return DEFAULT_QUERY


def fetch_rettype_for_mode(mode: str) -> str:
    # RefSeq plasmid hits are often CON records. gbwithparts keeps features and
    # materializes the concrete ORIGIN sequence without changing other modes.
    if mode == "refseq_plasmid_broad":
        return "gbwithparts"
    return "gb"


def raw_cache_key(accession: str, *, mode: str = "dev") -> str:
    safe_accession = accession.replace("/", "_").replace("\\", "_")
    if mode == "refseq_plasmid_broad":
        return f"raw/genbank/refseq_plasmid_broad/{safe_accession}.gb"
    return f"raw/genbank/{safe_accession}.gb"


def engineered_vector_filter_reason(plasmid: Plasmid) -> str | None:
    """Route obvious natural/non-engineered records away from the engineered-vector lane."""

    text = f" {plasmid.name} {' '.join(plasmid.use_cases)} ".lower()
    if has_engineered_vector_title(text):
        return None
    if "unverified" in text:
        return "unverified_record"
    if "partial sequence" in text:
        return "partial_sequence"
    if plasmid.length > 50_000:
        return "outside_engineered_vector_length_window"
    accession = plasmid.id.removeprefix("genbank:")
    if accession.startswith(("NC_", "NZ_")):
        return "broad_refseq_natural_plasmid"
    if any(term in text for term in NATURAL_CONTEXT_TITLE_TERMS):
        return "natural_isolate_or_chromosomal_context"
    return None


def has_engineered_vector_title(text: str) -> bool:
    return any(term in text for term in ENGINEERED_VECTOR_TITLE_TERMS)


def map_genbank_text_to_plasmid(raw_text: str, *, raw_ref: str, expected_accession: str | None = None) -> Plasmid:
    validated_sequence = validate_raw_genbank_sequence(raw_text)
    try:
        record = SeqIO.read(StringIO(raw_text), "genbank")
    except Exception as exc:
        raise GenbankMappingError("cached GenBank text could not be parsed") from exc

    try:
        sequence = str(record.seq).upper()
    except Exception as exc:
        raise GenbankMappingError("GenBank record sequence content is undefined") from exc
    if not sequence:
        raise GenbankMappingError("GenBank record is missing a sequence")
    if sequence != validated_sequence:
        raise GenbankMappingError(
            "GenBank parser sequence does not match raw ORIGIN sequence",
            details={"parsed_length": len(sequence), "origin_length": len(validated_sequence)},
        )
    invalid_canonical_bases = sorted(set(sequence) - CANONICAL_DNA_ALPHABET)
    if invalid_canonical_bases:
        raise GenbankMappingError(
            "GenBank record contains ambiguous bases outside the canonical schema alphabet",
            details={"invalid_characters": "".join(invalid_canonical_bases)},
        )

    accession = record.id or record.name
    if not accession:
        raise GenbankMappingError("GenBank record is missing accession")
    if expected_accession is not None and accession != expected_accession:
        raise GenbankMappingError(
            "GenBank record accession does not match requested accession",
            details={"expected_accession": expected_accession, "record_accession": accession},
        )

    organism = extract_organism(record)
    vector_type = "plasmid" if has_plasmid_signal(record) else None
    markers = extract_markers(record)
    promoters = extract_promoters(record)
    publication_doi = extract_publication_doi(record)
    use_cases = dedupe_strings([record.description, *as_list(record.annotations.get("keywords"))])

    return Plasmid(
        id=f"genbank:{accession}",
        source=SOURCE,
        name=record.description or accession,
        sequence=sequence,
        length=len(sequence),
        organism=organism,
        vector_type=vector_type,
        markers=markers,
        promoters=promoters,
        publication_doi=publication_doi,
        use_cases=use_cases,
        annotation_complete=False,
        raw_ref=raw_ref,
    )


def validate_raw_genbank_sequence(raw_text: str) -> str:
    locus_length = extract_locus_length(raw_text)
    origin_sequence = extract_origin_sequence(raw_text)
    if origin_sequence is None:
        raise GenbankMappingError("GenBank record has no ORIGIN sequence block")
    if not origin_sequence:
        raise GenbankMappingError("GenBank ORIGIN block has no nucleotide content")
    invalid = sorted(set(origin_sequence) - IUPAC_DNA_ALPHABET)
    if invalid:
        raise GenbankMappingError(
            "GenBank ORIGIN block contains non-IUPAC nucleotide characters",
            details={"invalid_characters": "".join(invalid)},
        )
    if locus_length is not None and len(origin_sequence) != locus_length:
        raise GenbankMappingError(
            "GenBank ORIGIN sequence length does not match LOCUS length",
            details={"locus_length": locus_length, "origin_length": len(origin_sequence)},
        )
    return origin_sequence


def extract_locus_length(raw_text: str) -> int | None:
    for line in raw_text.splitlines():
        if not line.startswith("LOCUS"):
            continue
        match = re.search(r"\s(\d+)\s+bp\s", line)
        return int(match.group(1)) if match else None
    return None


def retry_delay_seconds(error: HTTPError, *, fallback: float) -> float:
    retry_after = error.headers.get("Retry-After") if error.headers else None
    if not retry_after:
        return fallback
    try:
        return max(0.0, float(retry_after))
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(retry_after)
    except (TypeError, ValueError):
        return fallback
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return max(0.0, (parsed - datetime.now(UTC)).total_seconds())


def extract_origin_sequence(raw_text: str) -> str | None:
    in_origin = False
    pieces: list[str] = []
    for line in raw_text.splitlines():
        if line.startswith("ORIGIN"):
            in_origin = True
            continue
        if not in_origin:
            continue
        if line.startswith("//"):
            break
        pieces.append("".join(character for character in line.upper() if character.isalpha()))
    if not in_origin:
        return None
    return "".join(pieces)


def extract_organism(record: SeqRecord) -> str | None:
    for feature in record.features:
        if feature.type != "source":
            continue
        organism = first_qualifier(feature, "organism")
        if organism:
            return organism
    organism = record.annotations.get("organism")
    return str(organism) if organism else None


def has_plasmid_signal(record: SeqRecord) -> bool:
    haystack = " ".join(
        [
            record.description or "",
            record.name or "",
            *as_list(record.annotations.get("keywords")),
            *[
                " ".join(flatten_qualifiers(feature.qualifiers))
                for feature in record.features
                if feature.type == "source"
            ],
        ]
    ).lower()
    return "plasmid" in haystack


def extract_promoters(record: SeqRecord) -> list[str]:
    candidates: list[str] = []
    for feature in record.features:
        text = qualifier_text(feature).lower()
        if feature.type == "promoter":
            candidates.append(best_feature_name(feature, fallback="promoter"))
        elif feature.type == "regulatory" and contains_signal(text, "promoter"):
            candidates.append(best_feature_name(feature, fallback="regulatory promoter"))
        elif feature.type == "misc_feature" and contains_signal(text, "promoter"):
            candidates.append(best_feature_name(feature, fallback="promoter"))
    return dedupe_strings(candidates)


def extract_markers(record: SeqRecord) -> list[str]:
    candidates: list[str] = []
    for feature in record.features:
        if feature.type not in {"CDS", "gene", "misc_feature"}:
            continue
        text = qualifier_text(feature).lower()
        if contains_marker_term(text):
            candidates.append(best_feature_name(feature, fallback="selectable marker"))
    return dedupe_strings(candidates)


def extract_publication_doi(record: SeqRecord) -> str | None:
    fields: list[str] = []
    for reference in record.annotations.get("references", []):
        fields.extend(
            [
                getattr(reference, "title", "") or "",
                getattr(reference, "journal", "") or "",
                getattr(reference, "comment", "") or "",
            ]
        )
    match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", " ".join(fields), flags=re.IGNORECASE)
    return match.group(0) if match else None


def first_qualifier(feature: SeqFeature, key: str) -> str | None:
    values = feature.qualifiers.get(key)
    if not values:
        return None
    value = values[0]
    return str(value) if value else None


def best_feature_name(feature: SeqFeature, *, fallback: str) -> str:
    for key in ("label", "gene", "product", "note", "regulatory_class"):
        value = first_qualifier(feature, key)
        if value:
            return value
    return fallback


def qualifier_text(feature: SeqFeature) -> str:
    return " ".join(flatten_qualifiers(feature.qualifiers))


def flatten_qualifiers(qualifiers: dict[str, list[Any]]) -> list[str]:
    values: list[str] = []
    for key, raw_values in qualifiers.items():
        values.append(str(key))
        values.extend(str(value) for value in raw_values)
    return values


def as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def dedupe_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text.lower() == "none":
            continue
        key = text.lower()
        if key not in seen:
            seen.add(key)
            result.append(text)
    return result


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def env(name: str, default: str, dotenv: dict[str, str]) -> str:
    return os.environ.get(name) or dotenv.get(name) or default


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest NCBI GenBank plasmid-complete sequence records.")
    parser.add_argument("--mode", choices=VALID_MODES, default=os.environ.get("MODE", "dev"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = GenbankIngestionConfig.from_env(mode=args.mode, limit=args.limit, stale_days=args.stale_days)
    try:
        config.validate_for_real_network()
        result = run_genbank_ingestion(
            config,
            client=EntrezNcbiClient(config),
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
                "filtered": result.filtered,
                "errors": result.errors,
            },
            indent=2,
        )
    )
    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
