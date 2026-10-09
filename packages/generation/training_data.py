from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Protocol

import boto3
import psycopg
from botocore.exceptions import ClientError

from packages.core.schemas import AnnotatedSequence, DesignSpec, Plasmid
from packages.core.schemas.models import normalize_dna
from packages.data_pipeline.ingest.genbank import env, load_dotenv
from packages.data_pipeline.parse.sequence_parser import parse_genbank_text
from packages.retrieval.document_composer import DOCUMENT_VERSION, ComposedDocument, compose_plasmid_document


FORMATTER_VERSION = "phase2-triplet-v1"
DEFAULT_OUTPUT_ROOT = Path("data/training/phase2")
SPLITS = ("train", "validation", "test")


class TrainingDataRepository(Protocol):
    def list_plasmids(self) -> list[Plasmid]: ...


class TextObjectStore(Protocol):
    def get_text(self, key: str) -> str: ...


@dataclass(frozen=True)
class TrainingDataConfig:
    database_url: str = "postgresql://plasmid:plasmid@localhost:5432/plasmid_design"
    object_store_endpoint: str = "http://localhost:9000"
    object_store_bucket: str = "plasmid-design-local"
    object_store_access_key: str = "minioadmin"
    object_store_secret_key: str = "minioadmin"
    output_root: Path = DEFAULT_OUTPUT_ROOT
    snapshot_id: str | None = None

    @classmethod
    def from_env(cls, *, output_root: Path, snapshot_id: str | None) -> TrainingDataConfig:
        dotenv = load_dotenv(Path(".env"))
        return cls(
            database_url=env("DATABASE_URL", cls.database_url, dotenv),
            object_store_endpoint=env("OBJECT_STORE_ENDPOINT", cls.object_store_endpoint, dotenv),
            object_store_bucket=env("OBJECT_STORE_BUCKET", cls.object_store_bucket, dotenv),
            object_store_access_key=env("OBJECT_STORE_ACCESS_KEY", cls.object_store_access_key, dotenv),
            object_store_secret_key=env("OBJECT_STORE_SECRET_KEY", cls.object_store_secret_key, dotenv),
            output_root=output_root,
            snapshot_id=snapshot_id,
        )


@dataclass(frozen=True)
class CandidateRecord:
    plasmid: Plasmid
    annotated_sequence: AnnotatedSequence
    document: ComposedDocument
    sequence_sha256: str
    source_accession_cluster: str
    leakage_key: str

    @property
    def profile(self) -> str:
        return self.annotated_sequence.vector_profile


@dataclass(frozen=True)
class TrainingDataset:
    snapshot_id: str
    generated_at: datetime
    examples_by_split: dict[str, list[dict[str, Any]]]
    stats: dict[str, Any]

    @property
    def triplet_count(self) -> int:
        return sum(len(examples) for examples in self.examples_by_split.values())


@dataclass(frozen=True)
class PostgresTrainingDataRepository:
    database_url: str

    def list_plasmids(self) -> list[Plasmid]:
        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute("SELECT payload FROM plasmids ORDER BY id").fetchall()
        return [Plasmid.model_validate(row[0]) for row in rows]


@dataclass(frozen=True)
class S3TextObjectStore:
    bucket: str
    client: Any

    @classmethod
    def from_config(cls, config: TrainingDataConfig) -> S3TextObjectStore:
        return cls(
            bucket=config.object_store_bucket,
            client=boto3.client(
                "s3",
                endpoint_url=config.object_store_endpoint,
                aws_access_key_id=config.object_store_access_key,
                aws_secret_access_key=config.object_store_secret_key,
                region_name="us-east-1",
            ),
        )

    def get_text(self, key: str) -> str:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(key) from exc
            raise
        return response["Body"].read().decode("utf-8")


def build_training_dataset_from_sources(
    repository: TrainingDataRepository,
    object_store: TextObjectStore,
    *,
    snapshot_id: str,
    generated_at: datetime | None = None,
) -> TrainingDataset:
    candidates, skipped = load_candidate_records(repository.list_plasmids(), object_store)
    return build_training_dataset(
        candidates,
        snapshot_id=snapshot_id,
        generated_at=generated_at,
        initial_skipped_counts=skipped,
    )


def load_candidate_records(plasmids: list[Plasmid], object_store: TextObjectStore) -> tuple[list[CandidateRecord], Counter[str]]:
    candidates: list[CandidateRecord] = []
    skipped: Counter[str] = Counter()
    for plasmid in plasmids:
        if not plasmid.annotation_complete:
            skipped["plasmid_annotation_incomplete"] += 1
            continue
        try:
            annotated = parse_genbank_text(object_store.get_text(plasmid.raw_ref))
        except Exception:
            skipped["parse_error"] += 1
            continue
        candidate, reason = candidate_from_records(plasmid, annotated)
        if candidate is None:
            skipped[reason or "not_eligible"] += 1
            continue
        candidates.append(candidate)
    return candidates, skipped


def candidate_from_records(plasmid: Plasmid, annotated: AnnotatedSequence) -> tuple[CandidateRecord | None, str | None]:
    try:
        sequence = normalize_dna(plasmid.sequence)
    except Exception:
        return None, "invalid_sequence"
    if annotated.sequence != sequence:
        return None, "sequence_mismatch"
    if not annotated.annotation_complete:
        return None, "annotation_incomplete"
    if annotated.vector_profile == "unknown":
        return None, "unknown_profile"
    document = compose_plasmid_document(plasmid, annotated)
    if not has_context_signal(plasmid, annotated, document):
        return None, "insufficient_context"
    sequence_sha256 = hashlib.sha256(sequence.encode("ascii")).hexdigest()
    source_accession_cluster = accession_cluster(plasmid.id)
    return (
        CandidateRecord(
            plasmid=plasmid,
            annotated_sequence=annotated,
            document=document,
            sequence_sha256=sequence_sha256,
            source_accession_cluster=source_accession_cluster,
            leakage_key=leakage_key(plasmid, source_accession_cluster, sequence_sha256),
        ),
        None,
    )


def build_training_dataset(
    candidates: list[CandidateRecord],
    *,
    snapshot_id: str,
    generated_at: datetime | None = None,
    split_for_group: Callable[[str], str] | None = None,
    initial_skipped_counts: Counter[str] | None = None,
) -> TrainingDataset:
    timestamp = generated_at or datetime.now(UTC)
    split_for_group = split_for_group or (lambda group: assign_split(group, snapshot_id=snapshot_id))
    split_by_key = {candidate.leakage_key: split_for_group(candidate.leakage_key) for candidate in candidates}
    by_split: dict[str, list[CandidateRecord]] = {split: [] for split in SPLITS}
    for candidate in candidates:
        by_split[split_by_key[candidate.leakage_key]].append(candidate)

    examples_by_split: dict[str, list[dict[str, Any]]] = {split: [] for split in SPLITS}
    skipped_counts = Counter(initial_skipped_counts or {})
    for split in SPLITS:
        for target in sorted(by_split[split], key=lambda item: item.plasmid.id):
            template = select_template(target, by_split[split])
            if template is None:
                skipped_counts["no_valid_template"] += 1
                continue
            examples_by_split[split].append(build_example(target, template, split=split))

    stats = build_stats(
        candidates=candidates,
        examples_by_split=examples_by_split,
        skipped_counts=skipped_counts,
        snapshot_id=snapshot_id,
        generated_at=timestamp,
    )
    return TrainingDataset(
        snapshot_id=snapshot_id,
        generated_at=timestamp,
        examples_by_split=examples_by_split,
        stats=stats,
    )


def select_template(target: CandidateRecord, candidates: list[CandidateRecord]) -> CandidateRecord | None:
    eligible = [
        candidate
        for candidate in candidates
        if candidate.plasmid.id != target.plasmid.id and candidate.leakage_key != target.leakage_key
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda candidate: template_score(target, candidate))


def template_score(target: CandidateRecord, candidate: CandidateRecord) -> tuple[float, int, int, str]:
    marker_overlap = len(set(normalize_list(target.plasmid.markers)) & set(normalize_list(candidate.plasmid.markers)))
    promoter_overlap = len(set(normalize_list(target.plasmid.promoters)) & set(normalize_list(candidate.plasmid.promoters)))
    profile_score = 100.0 if candidate.profile == target.profile else 0.0
    length_ratio = min(target.plasmid.length, candidate.plasmid.length) / max(target.plasmid.length, candidate.plasmid.length)
    score = profile_score + (marker_overlap * 10.0) + (promoter_overlap * 5.0) + length_ratio
    return (score, marker_overlap, promoter_overlap, candidate.plasmid.id)


def build_example(target: CandidateRecord, template: CandidateRecord, *, split: str) -> dict[str, Any]:
    context_text = build_context_text(target)
    design_spec = build_design_spec(target).model_dump(mode="json")
    return {
        "example_id": f"{FORMATTER_VERSION}::{safe_id(target.plasmid.id)}::{safe_id(template.plasmid.id)}",
        "formatter_version": FORMATTER_VERSION,
        "split": split,
        "context": {
            "text": context_text,
            "design_spec": design_spec,
            "source": "composed_document",
            "provenance": [
                {"field": "plasmid.payload", "source_id": target.plasmid.id},
                {"field": "parsed_sequence", "source_id": target.plasmid.raw_ref},
                {"field": "document_version", "source_id": DOCUMENT_VERSION},
            ],
        },
        "template": {
            "plasmid_id": template.plasmid.id,
            "sequence": template.plasmid.sequence,
            "annotated_sequence": template.annotated_sequence.model_dump(mode="json"),
            "retrieval_score": template_score(target, template)[0],
            "selection_reason": selection_reasons(target, template),
        },
        "target": {
            "plasmid_id": target.plasmid.id,
            "sequence": target.plasmid.sequence,
            "annotated_sequence": target.annotated_sequence.model_dump(mode="json"),
            "source": str(target.plasmid.source),
            "raw_ref": target.plasmid.raw_ref,
            "publication_doi": target.plasmid.publication_doi,
        },
        "leakage_group": {
            "depositing_lab": None,
            "publication_doi": target.plasmid.publication_doi,
            "source_accession_cluster": target.source_accession_cluster,
            "sequence_similarity_cluster": target.sequence_sha256,
            "assigned_group_key": target.leakage_key,
        },
        "quality_flags": [],
    }


def build_context_text(target: CandidateRecord) -> str:
    metadata = target.document.metadata
    candidates = metadata.get("candidates", {})
    clauses = [f"Design a {humanize(target.profile)} plasmid."]
    if target.plasmid.organism:
        clauses.append(f"Organism annotation: {target.plasmid.organism}.")
    for label, key in (
        ("Selectable markers", "markers"),
        ("Promoters", "promoters"),
        ("Payloads", "payloads"),
        ("Cloning sites", "cloning_sites"),
        ("Terminators", "terminators"),
        ("Replication origins", "origins"),
        ("Use cases", "use_cases"),
    ):
        values = candidate_names(candidates.get(key, []))
        if values:
            clauses.append(f"{label}: {join_list(values)}.")
    clauses.append(f"Length/topology target: {target.plasmid.length} bp {target.annotated_sequence.topology} plasmid.")
    text = " ".join(clauses)
    return scrub_identity(text, target.plasmid)


def build_design_spec(target: CandidateRecord) -> DesignSpec:
    candidates = target.document.metadata.get("candidates", {})
    promoters = candidate_names(candidates.get("promoters", []))
    use_cases = candidate_names(candidates.get("use_cases", []))
    return DesignSpec(
        organism=target.plasmid.organism or "unknown",
        vector_type=target.profile,
        markers=dedupe(target.plasmid.markers),
        promoter_type=promoters[0] if promoters else None,
        source=target.plasmid.source,
        publication_doi=target.plasmid.publication_doi,
        application=use_cases[0] if use_cases else None,
        constraints=[f"target_length_bp={target.plasmid.length}", f"topology={target.annotated_sequence.topology}"],
        clarification_needed=False,
        clarification_question=None,
    )


def selection_reasons(target: CandidateRecord, template: CandidateRecord) -> list[str]:
    reasons = ["same_split", "not_same_leakage_group"]
    if target.profile == template.profile:
        reasons.append("same_vector_profile")
    if set(normalize_list(target.plasmid.markers)) & set(normalize_list(template.plasmid.markers)):
        reasons.append("marker_overlap")
    if set(normalize_list(target.plasmid.promoters)) & set(normalize_list(template.plasmid.promoters)):
        reasons.append("promoter_overlap")
    reasons.append("length_similarity")
    return reasons


def build_stats(
    *,
    candidates: list[CandidateRecord],
    examples_by_split: dict[str, list[dict[str, Any]]],
    skipped_counts: Counter[str],
    snapshot_id: str,
    generated_at: datetime,
) -> dict[str, Any]:
    candidate_profiles = Counter(candidate.profile for candidate in candidates)
    split_counts = {split: len(examples_by_split[split]) for split in SPLITS}
    profile_by_split: dict[str, dict[str, int]] = {}
    for split in SPLITS:
        counts: Counter[str] = Counter(example["target"]["annotated_sequence"]["vector_profile"] for example in examples_by_split[split])
        profile_by_split[split] = dict(sorted(counts.items()))
    return {
        "formatter_version": FORMATTER_VERSION,
        "snapshot_id": snapshot_id,
        "generated_at": generated_at.astimezone(UTC).isoformat(),
        "candidate_count": len(candidates),
        "triplet_count": sum(split_counts.values()),
        "split_counts": split_counts,
        "candidate_profile_distribution": dict(sorted(candidate_profiles.items())),
        "profile_distribution_by_split": profile_by_split,
        "skipped_counts": dict(sorted(skipped_counts.items())),
        "template_selection": "same-split deterministic structured overlap; no embeddings in v1",
    }


def write_dataset(dataset: TrainingDataset, output_root: Path) -> Path:
    output_dir = output_root / dataset.snapshot_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_files: dict[str, str] = {}
    for split in SPLITS:
        path = output_dir / f"triplets.{split}.jsonl"
        write_jsonl(path, dataset.examples_by_split[split])
        output_files[split] = str(path)
    manifest = {
        "formatter_version": FORMATTER_VERSION,
        "snapshot_id": dataset.snapshot_id,
        "generated_at": dataset.generated_at.astimezone(UTC).isoformat(),
        "document_version": DOCUMENT_VERSION,
        "split_policy": "stable hash by leakage group, 80/10/10",
        "output_files": output_files,
        "stats": dataset.stats,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output_dir / "stats.md").write_text(render_stats_markdown(dataset.stats), encoding="utf-8")
    return output_dir


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def render_stats_markdown(stats: dict[str, Any]) -> str:
    lines = [
        "# Phase 2 Training Data Stats",
        "",
        f"- Snapshot: `{stats['snapshot_id']}`",
        f"- Formatter: `{stats['formatter_version']}`",
        f"- Generated at: `{stats['generated_at']}`",
        f"- Candidate targets: `{stats['candidate_count']}`",
        f"- Triplets: `{stats['triplet_count']}`",
        "",
        "## Splits",
        "",
        "| Split | Triplets |",
        "| --- | ---: |",
    ]
    for split, count in stats["split_counts"].items():
        lines.append(f"| {split} | {count} |")
    lines.extend(["", "## Profile Distribution By Split", ""])
    for split, counts in stats["profile_distribution_by_split"].items():
        lines.append(f"### {split}")
        if not counts:
            lines.append("- No triplets")
            continue
        for profile, count in counts.items():
            lines.append(f"- `{profile}`: `{count}`")
    lines.extend(["", "## Skipped Counts"])
    if not stats["skipped_counts"]:
        lines.append("- None")
    else:
        for reason, count in stats["skipped_counts"].items():
            lines.append(f"- `{reason}`: `{count}`")
    lines.append("")
    return "\n".join(lines)


def assign_split(group_key: str, *, snapshot_id: str) -> str:
    digest = hashlib.sha256(f"{snapshot_id}:{group_key}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    if bucket < 80:
        return "train"
    if bucket < 90:
        return "validation"
    return "test"


def leakage_key(plasmid: Plasmid, source_accession_cluster: str, sequence_sha256: str) -> str:
    if plasmid.publication_doi:
        return f"doi:{plasmid.publication_doi.casefold()}"
    if source_accession_cluster:
        return f"accession:{source_accession_cluster}"
    return f"sequence:{sequence_sha256}"


def accession_cluster(plasmid_id: str) -> str:
    source, _, native = plasmid_id.partition(":")
    if "." in native:
        native = native.rsplit(".", 1)[0]
    return f"{source}:{native}" if native else plasmid_id


def has_context_signal(plasmid: Plasmid, annotated: AnnotatedSequence, document: ComposedDocument) -> bool:
    candidates = document.metadata.get("candidates", {})
    return any(
        [
            plasmid.markers,
            plasmid.promoters,
            plasmid.use_cases,
            annotated.features,
            candidates.get("markers"),
            candidates.get("promoters"),
            candidates.get("origins"),
            candidates.get("payloads"),
            candidates.get("use_cases"),
        ]
    )


def candidate_names(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    names: list[str] = []
    for value in values:
        if isinstance(value, dict):
            candidate = value.get("name") or value.get("value") or value.get("label")
        else:
            candidate = value
        if candidate:
            names.append(str(candidate))
    return dedupe(names)


def scrub_identity(text: str, plasmid: Plasmid) -> str:
    scrubbed = text
    for value in (plasmid.id, plasmid.name, plasmid.raw_ref, plasmid.sequence, accession_cluster(plasmid.id)):
        if value:
            scrubbed = scrubbed.replace(value, "target plasmid")
    return " ".join(scrubbed.split())


def normalize_list(values: list[str]) -> list[str]:
    return [" ".join(value.casefold().split()) for value in values if value]


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = " ".join(str(value).split())
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def humanize(value: str) -> str:
    return value.replace("_", " ")


def join_list(values: list[str]) -> str:
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def safe_id(value: str) -> str:
    return value.replace(":", "_").replace("/", "_").replace("\\", "_")


def default_snapshot_id(now: datetime | None = None) -> str:
    timestamp = now or datetime.now(UTC)
    return timestamp.astimezone(UTC).strftime("%Y-%m-%d-%H%M%S-phase2-triplets")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Phase 2 context-template-target training triplets.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--snapshot-id", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    snapshot_id = args.snapshot_id or default_snapshot_id()
    config = TrainingDataConfig.from_env(output_root=args.output_root, snapshot_id=snapshot_id)
    dataset = build_training_dataset_from_sources(
        PostgresTrainingDataRepository(config.database_url),
        S3TextObjectStore.from_config(config),
        snapshot_id=snapshot_id,
    )
    output_dir = write_dataset(dataset, config.output_root)
    print(json.dumps({"output_dir": str(output_dir), "stats": dataset.stats}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
