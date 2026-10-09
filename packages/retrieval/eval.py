from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from packages.core.schemas import RetrievalResult
from packages.retrieval.pipeline import RetrievalPipeline, build_default_pipeline


DEFAULT_GOLD_PATH = Path("data/eval/retrieval_gold.jsonl")
DEFAULT_OUTPUT_DIR = Path("data/eval/retrieval")
DEFAULT_TOP_K = 5


@dataclass(frozen=True)
class GoldRecord:
    query: str
    acceptable_target_ids: list[str]
    rationale: str
    source: str
    expected_clarification: bool = False


@dataclass(frozen=True)
class RetrievedEvalMatch:
    plasmid_id: str
    name: str
    score: float
    matched_fields: list[str]


@dataclass(frozen=True)
class QueryEvalResult:
    query: str
    acceptable_target_ids: list[str]
    retrieved: list[RetrievedEvalMatch]
    rank: int | None
    reciprocal_rank: float
    top1_hit: bool
    top5_hit: bool
    clarification_needed: bool
    clarification_question: str | None
    expected_clarification: bool
    clarification_pass: bool | None
    rationale: str
    source: str


@dataclass(frozen=True)
class RetrievalEvalReport:
    generated_at: str
    gold_path: str
    total_queries: int
    retrieval_queries: int
    clarification_queries: int
    top_k: int
    top1_hit_rate: float
    top5_hit_rate: float
    mrr: float
    clarification_pass_rate: float | None
    results: list[QueryEvalResult]


class RetrievalEvaluatorPipeline(Protocol):
    def design_retrieval(self, free_text: str, *, k: int = DEFAULT_TOP_K) -> RetrievalResult: ...


def load_gold(path: Path) -> list[GoldRecord]:
    records: list[GoldRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"empty line in retrieval gold file at line {line_number}")
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in retrieval gold file at line {line_number}") from exc
        try:
            record = GoldRecord(
                query=_required_string(payload, "query", line_number),
                acceptable_target_ids=_required_string_list(
                    payload,
                    "acceptable_target_ids",
                    line_number,
                    allow_empty=payload.get("expected_clarification") is True,
                ),
                rationale=_required_string(payload, "rationale", line_number),
                source=_required_string(payload, "source", line_number),
                expected_clarification=_optional_bool(payload, "expected_clarification", line_number),
            )
        except TypeError as exc:
            raise ValueError(str(exc)) from exc
        records.append(record)
    if not records:
        raise ValueError("retrieval gold file has no records")
    return records


def evaluate_pipeline(
    records: Sequence[GoldRecord],
    pipeline: RetrievalEvaluatorPipeline,
    *,
    gold_path: Path = DEFAULT_GOLD_PATH,
    top_k: int = DEFAULT_TOP_K,
    generated_at: datetime | None = None,
) -> RetrievalEvalReport:
    results: list[QueryEvalResult] = []
    for record in records:
        result = pipeline.design_retrieval(record.query, k=top_k)
        retrieved = [
            RetrievedEvalMatch(
                plasmid_id=item.plasmid.id,
                name=item.plasmid.name,
                score=item.score,
                matched_fields=item.matched_fields,
            )
            for item in result.retrieved[:top_k]
        ]
        results.append(evaluate_query_result(record, retrieved, result))
    timestamp = generated_at or datetime.now(UTC)
    return summarize_results(
        results,
        generated_at=timestamp,
        gold_path=gold_path,
        top_k=top_k,
    )


def evaluate_query_result(
    record: GoldRecord,
    retrieved: Sequence[RetrievedEvalMatch],
    result: RetrievalResult | None = None,
) -> QueryEvalResult:
    rank = first_acceptable_rank(retrieved, record.acceptable_target_ids)
    reciprocal = 0.0 if rank is None else 1.0 / rank
    return QueryEvalResult(
        query=record.query,
        acceptable_target_ids=list(record.acceptable_target_ids),
        retrieved=list(retrieved),
        rank=rank,
        reciprocal_rank=reciprocal,
        top1_hit=rank == 1,
        top5_hit=rank is not None and rank <= 5,
        clarification_needed=result.clarification_needed if result is not None else False,
        clarification_question=result.clarification_question if result is not None else None,
        expected_clarification=record.expected_clarification,
        clarification_pass=(
            (result.clarification_needed if result is not None else False)
            if record.expected_clarification
            else None
        ),
        rationale=record.rationale,
        source=record.source,
    )


def summarize_results(
    results: Sequence[QueryEvalResult],
    *,
    generated_at: datetime,
    gold_path: Path,
    top_k: int,
) -> RetrievalEvalReport:
    total = len(results)
    if total == 0:
        raise ValueError("cannot summarize an empty retrieval evaluation")
    retrieval_results = [result for result in results if not result.expected_clarification]
    clarification_results = [result for result in results if result.expected_clarification]
    if not retrieval_results:
        raise ValueError("cannot summarize retrieval metrics without retrieval queries")
    return RetrievalEvalReport(
        generated_at=generated_at.astimezone(UTC).isoformat(),
        gold_path=_display_path(gold_path),
        total_queries=total,
        retrieval_queries=len(retrieval_results),
        clarification_queries=len(clarification_results),
        top_k=top_k,
        top1_hit_rate=sum(1 for result in retrieval_results if result.top1_hit) / len(retrieval_results),
        top5_hit_rate=sum(1 for result in retrieval_results if result.top5_hit) / len(retrieval_results),
        mrr=sum(result.reciprocal_rank for result in retrieval_results) / len(retrieval_results),
        clarification_pass_rate=(
            sum(1 for result in clarification_results if result.clarification_pass) / len(clarification_results)
            if clarification_results
            else None
        ),
        results=list(results),
    )


def normalize_match_ids(plasmid_id: str) -> set[str]:
    value = plasmid_id.strip().casefold()
    values = {value}
    if ":" in value:
        values.add(value.split(":", 1)[1])
    return values


def is_acceptable_match(retrieved_id: str, acceptable_ids: Sequence[str]) -> bool:
    retrieved = normalize_match_ids(retrieved_id)
    acceptable = set().union(*(normalize_match_ids(value) for value in acceptable_ids))
    return bool(retrieved & acceptable)


def first_acceptable_rank(retrieved: Sequence[RetrievedEvalMatch], acceptable_ids: Sequence[str]) -> int | None:
    for index, match in enumerate(retrieved, start=1):
        if is_acceptable_match(match.plasmid_id, acceptable_ids):
            return index
    return None


def render_markdown_report(report: RetrievalEvalReport) -> str:
    lines = [
        "# Retrieval Evaluation Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Gold file: `{report.gold_path}`",
        f"- Queries: `{report.total_queries}`",
        f"- Retrieval queries scored: `{report.retrieval_queries}`",
        f"- Clarification queries: `{report.clarification_queries}`",
        f"- Top K: `{report.top_k}`",
        f"- Top-1 hit rate: `{report.top1_hit_rate:.3f}`",
        f"- Top-5 hit rate: `{report.top5_hit_rate:.3f}`",
        f"- MRR: `{report.mrr:.3f}`",
        "",
        "## Per-Query Results",
        "",
    ]
    if report.clarification_pass_rate is not None:
        lines.insert(10, f"- Clarification pass rate: `{report.clarification_pass_rate:.3f}`")
    for index, result in enumerate(report.results, start=1):
        rank = "miss" if result.rank is None else f"hit at rank {result.rank}"
        lines.extend(
            [
                f"### {index}. {result.query}",
                "",
                f"- Acceptable IDs: `{', '.join(result.acceptable_target_ids)}`",
                f"- Result: `{rank}`",
                f"- Reciprocal rank: `{result.reciprocal_rank:.3f}`",
                f"- Expected clarification: `{result.expected_clarification}`",
                f"- Clarification needed: `{result.clarification_needed}`",
            ]
        )
        if result.clarification_question:
            lines.append(f"- Clarification question: {result.clarification_question}")
        lines.extend(["", "Retrieved:"])
        if result.retrieved:
            for rank_index, match in enumerate(result.retrieved, start=1):
                fields = ", ".join(match.matched_fields) if match.matched_fields else "<none>"
                lines.append(f"- {rank_index}. `{match.plasmid_id}` {match.name} score=`{match.score:.4f}` fields=`{fields}`")
        else:
            lines.append("- <none>")
        lines.extend(["", f"Rationale: {result.rationale}", f"Source: {result.source}", ""])
    return "\n".join(lines).rstrip() + "\n"


def report_as_dict(report: RetrievalEvalReport) -> dict[str, Any]:
    return asdict(report)


def write_report(
    report: RetrievalEvalReport,
    output_dir: Path,
    *,
    write_json: bool = True,
) -> tuple[Path, Path | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.fromisoformat(report.generated_at).strftime("%Y-%m-%d-%H%M%S")
    markdown_path = output_dir / f"{stamp}-retrieval-baseline.md"
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    json_path = None
    if write_json:
        json_path = output_dir / f"{stamp}-retrieval-baseline.json"
        json_path.write_text(json.dumps(report_as_dict(report), indent=2), encoding="utf-8")
    return markdown_path, json_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Phase 1 retrieval against the retrieval gold set.")
    parser.add_argument("--gold-path", type=Path, default=DEFAULT_GOLD_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--fake-embedder", action="store_true", help="Use fake query embeddings; requires a fake-embedded corpus.")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--hf-cache-dir")
    parser.add_argument("--no-json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = load_gold(args.gold_path)
    pipeline: RetrievalPipeline = build_default_pipeline(
        use_fake_embedder=args.fake_embedder,
        local_files_only=args.local_files_only,
        hf_cache_dir=args.hf_cache_dir,
    )
    report = evaluate_pipeline(records, pipeline, gold_path=args.gold_path, top_k=args.top_k)
    markdown_path, json_path = write_report(report, args.output_dir, write_json=not args.no_json)
    print(render_markdown_report(report))
    print(f"Wrote markdown report: {markdown_path}")
    if json_path is not None:
        print(f"Wrote JSON report: {json_path}")
    return 0


def _required_string(payload: Mapping[str, Any], key: str, line_number: int) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"retrieval gold line {line_number} needs non-empty string field {key!r}")
    return value


def _required_string_list(
    payload: Mapping[str, Any],
    key: str,
    line_number: int,
    *,
    allow_empty: bool = False,
) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or (not value and not allow_empty):
        raise TypeError(f"retrieval gold line {line_number} needs non-empty list field {key!r}")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise TypeError(f"retrieval gold line {line_number} field {key!r} must contain non-empty strings")
    return list(value)


def _optional_bool(payload: Mapping[str, Any], key: str, line_number: int) -> bool:
    value = payload.get(key, False)
    if not isinstance(value, bool):
        raise TypeError(f"retrieval gold line {line_number} field {key!r} must be a boolean")
    return value


def _display_path(path: Path | str) -> str:
    if isinstance(path, Path):
        return path.as_posix()
    return str(path).replace("\\", "/")


if __name__ == "__main__":
    raise SystemExit(main())
