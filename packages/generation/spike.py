from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, Protocol, Sequence

import boto3
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from botocore.exceptions import ClientError

from packages.core.schemas import (
    AnnotatedSequence,
    DesignSpec,
    GeneratedSequence,
    PlasmidRecommendation,
    RetrievedPlasmid,
    ValidationCheck,
    ValidationReport,
)
from packages.core.vocabularies import (
    MARKER_TERMS,
    PROMOTER_TYPE_TERMS,
    TAG_TERMS,
    VECTOR_TYPE_TERMS,
    ControlledTerm,
    contains_term,
    normalize_text,
    normalize_to_controlled,
)
from packages.data_pipeline.ingest.genbank import env, load_dotenv
from packages.data_pipeline.parse.sequence_parser import parse_genbank_text, parse_seqrecord
from packages.generation.generator import FakeGenerator, SequenceGenerator, ensure_generated_sequence_count
from packages.retrieval.embed_corpus import EmbedCorpusConfig, build_embedder, build_vector_store
from packages.retrieval.intent_parser import IntentParser, build_intent_parser
from packages.retrieval.recommender import RecommendationGenerator
from packages.retrieval.retriever import DEFAULT_RETRIEVAL_K, HybridRetriever, PostgresRetrievalRepository, Retriever
from packages.validation.engine import ConstraintEngine as DeterministicConstraintEngine


SPIKE_PIPELINE_VERSION = "phase2-generation-spike-v1"
STUB_CONSTRAINT_ENGINE_VERSION = "stub-constraint-engine-v0"


class ConstraintEngine(Protocol):
    def validate(self, sequence: AnnotatedSequence, spec: DesignSpec) -> ValidationReport: ...


class Reannotator(Protocol):
    def reannotate(self, generated: GeneratedSequence, template: RetrievedPlasmid) -> AnnotatedSequence: ...


@dataclass(frozen=True)
class ComponentCheck:
    kind: str
    requested: str
    matched: bool
    evidence: str | None = None


@dataclass(frozen=True)
class GenerationSpikeResult:
    query: str
    spec: DesignSpec
    template: RetrievedPlasmid
    retrieved_templates: list[RetrievedPlasmid]
    recommendations: list[PlasmidRecommendation]
    generated: GeneratedSequence
    reannotated_sequence: AnnotatedSequence
    validation_report: ValidationReport
    component_checks: list[ComponentCheck]
    pipeline_version: str = SPIKE_PIPELINE_VERSION

    @property
    def passed(self) -> bool:
        return self.validation_report.overall == "PASS" and all(check.matched for check in self.component_checks)


@dataclass(frozen=True)
class StubConstraintEngine:
    version: str = STUB_CONSTRAINT_ENGINE_VERSION

    def validate(self, sequence: AnnotatedSequence, spec: DesignSpec) -> ValidationReport:
        del sequence, spec
        return ValidationReport(
            overall="PASS",
            checks=[
                ValidationCheck(
                    name="phase2_spike_stub",
                    status="PASS",
                    message="Phase 2 plumbing spike stub only; no biological validation performed.",
                )
            ],
            generated_by_model_version=self.version,
        )


@dataclass(frozen=True)
class S3TemplateReannotator:
    object_store: Any

    def reannotate(self, generated: GeneratedSequence, template: RetrievedPlasmid) -> AnnotatedSequence:
        raw = self.object_store.get_text(template.plasmid.raw_ref)
        if raw is not None:
            try:
                annotated = parse_genbank_text(raw)
                if annotated.sequence == generated.annotated_sequence.sequence:
                    return annotated
            except Exception:
                pass
        return parse_generated_sequence(generated.annotated_sequence.sequence)


@dataclass(frozen=True)
class S3TextObjectStore:
    bucket: str
    client: Any

    @classmethod
    def from_env(cls) -> S3TextObjectStore:
        dotenv = load_dotenv(Path(".env"))
        endpoint = env("OBJECT_STORE_ENDPOINT", "http://localhost:9000", dotenv)
        bucket = env("OBJECT_STORE_BUCKET", "plasmid-design-local", dotenv)
        access_key = env("OBJECT_STORE_ACCESS_KEY", "minioadmin", dotenv)
        secret_key = env("OBJECT_STORE_SECRET_KEY", "minioadmin", dotenv)
        return cls(
            bucket=bucket,
            client=boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name="us-east-1",
            ),
        )

    def get_text(self, key: str) -> str | None:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return response["Body"].read().decode("utf-8")


@dataclass(frozen=True)
class ParserReannotator:
    def reannotate(self, generated: GeneratedSequence, template: RetrievedPlasmid) -> AnnotatedSequence:
        del template
        return parse_generated_sequence(generated.annotated_sequence.sequence)


@dataclass(frozen=True)
class GenerationSpikePipeline:
    parser: IntentParser
    retriever: Retriever
    generator: SequenceGenerator
    reannotator: Reannotator
    constraint_engine: ConstraintEngine
    recommendation_generator: RecommendationGenerator | None = None
    retrieval_k: int = DEFAULT_RETRIEVAL_K
    version: str = SPIKE_PIPELINE_VERSION

    def run(self, free_text: str) -> GenerationSpikeResult:
        spec = self.parser.parse(free_text)
        if spec.clarification_needed:
            raise ValueError(f"intent clarification required: {spec.clarification_question}")
        template_limit = max(1, self.retrieval_k if self.recommendation_generator is not None else 1)
        templates = self.retriever.retrieve(spec, k=template_limit)
        if not templates:
            raise ValueError("retrieval returned no templates for generation spike")
        recommendations = self.recommendation_generator.recommend(templates, spec) if self.recommendation_generator is not None else []
        generated = self.generator.generate(spec, templates, n=1)
        ensure_generated_sequence_count(generated)
        generated_sequence = generated[0]
        reannotated = self.reannotator.reannotate(generated_sequence, templates[0])
        validation = self.constraint_engine.validate(reannotated, spec)
        component_checks = requested_component_checks(spec, reannotated)
        return GenerationSpikeResult(
            query=free_text,
            spec=spec,
            template=templates[0],
            retrieved_templates=templates,
            recommendations=recommendations,
            generated=generated_sequence,
            reannotated_sequence=reannotated,
            validation_report=validation,
            component_checks=component_checks,
            pipeline_version=self.version,
        )


def build_default_spike_pipeline(*, local_files_only: bool = False, fake_embedder: bool = False) -> GenerationSpikePipeline:
    config = EmbedCorpusConfig.from_env(
        batch_size=1,
        limit=None,
        use_fake=fake_embedder,
        local_files_only=local_files_only,
        hf_cache_dir=None,
    )
    embedder = build_embedder(config)
    vector_index = build_vector_store(config, embedder)
    vector_index.ensure_schema()
    return GenerationSpikePipeline(
        parser=build_intent_parser(use_fake=True),
        retriever=HybridRetriever(
            vector_index=vector_index,
            embedder=embedder,
            repository=PostgresRetrievalRepository(config.database_url),
        ),
        generator=FakeGenerator(),
        reannotator=S3TemplateReannotator(S3TextObjectStore.from_env()),
        constraint_engine=DeterministicConstraintEngine(),
    )


def parse_generated_sequence(sequence: str) -> AnnotatedSequence:
    record = SeqRecord(Seq(sequence), id="generated_spike_candidate", name="generated_spike_candidate")
    record.annotations["topology"] = "circular"
    record.annotations["molecule_type"] = "DNA"
    return parse_seqrecord(record)


def requested_component_checks(spec: DesignSpec, annotated: AnnotatedSequence) -> list[ComponentCheck]:
    evidence = _annotation_evidence_text(annotated)
    checks: list[ComponentCheck] = []
    if spec.vector_type:
        checks.append(
            ComponentCheck(
                kind="vector_type",
                requested=spec.vector_type,
                matched=_component_present(spec.vector_type, evidence, VECTOR_TYPE_TERMS)
                or normalize_text(spec.vector_type) == normalize_text(annotated.vector_profile),
                evidence=annotated.vector_profile,
            )
        )
    for marker in spec.markers:
        checks.append(
            ComponentCheck(
                kind="marker",
                requested=marker,
                matched=_component_present(marker, evidence, MARKER_TERMS),
                evidence=_matching_evidence(marker, evidence, MARKER_TERMS),
            )
        )
    if spec.promoter_type:
        checks.append(
            ComponentCheck(
                kind="promoter",
                requested=spec.promoter_type,
                matched=_component_present(spec.promoter_type, evidence, PROMOTER_TYPE_TERMS),
                evidence=_matching_evidence(spec.promoter_type, evidence, PROMOTER_TYPE_TERMS),
            )
        )
    for gene in spec.genes:
        checks.append(
            ComponentCheck(
                kind="gene",
                requested=gene,
                matched=contains_term(evidence, gene),
                evidence=gene if contains_term(evidence, gene) else None,
            )
        )
    for tag in spec.tags:
        checks.append(
            ComponentCheck(
                kind="tag",
                requested=tag,
                matched=_component_present(tag, evidence, TAG_TERMS),
                evidence=_matching_evidence(tag, evidence, TAG_TERMS),
            )
        )
    return checks


def render_spike_result(result: GenerationSpikeResult) -> str:
    lines = [
        "# Phase 2 Generation Spike Result",
        "",
        f"Query: {result.query}",
        f"Pipeline: `{result.pipeline_version}`",
        f"Template: `{result.template.plasmid.id}` {result.template.plasmid.name}",
        f"Generator: `{result.generated.model_version}`",
        f"Validation: `{result.validation_report.overall}` ({result.validation_report.generated_by_model_version})",
        f"Generated length: `{len(result.generated.annotated_sequence.sequence)}` bp",
        f"Re-annotated profile: `{result.reannotated_sequence.vector_profile}`",
        f"Re-annotated features: `{len(result.reannotated_sequence.features)}`",
        f"Passed: `{result.passed}`",
        "",
        "## Component Checks",
    ]
    if result.component_checks:
        for check in result.component_checks:
            evidence = f" evidence=`{check.evidence}`" if check.evidence else ""
            lines.append(f"- {check.kind}: `{check.requested}` matched=`{check.matched}`{evidence}")
    else:
        lines.append("- No specific marker/promoter/gene/tag/vector component requested by the parsed DesignSpec.")
    lines.extend(["", "## Feature Summary"])
    for feature in result.reannotated_sequence.features[:25]:
        lines.append(f"- {feature.type} `{feature.name}` {feature.start}-{feature.end} confidence=`{feature.confidence:.2f}`")
    if len(result.reannotated_sequence.features) > 25:
        lines.append(f"- ... {len(result.reannotated_sequence.features) - 25} additional features omitted")
    return "\n".join(lines).rstrip() + "\n"


def spike_result_as_dict(result: GenerationSpikeResult) -> dict[str, Any]:
    return {
        "query": result.query,
        "pipeline_version": result.pipeline_version,
        "passed": result.passed,
        "design_spec": result.spec.model_dump(mode="json"),
        "retrieved_templates": [
            {
                "source_id": item.plasmid.id,
                "name": item.plasmid.name,
                "score": item.score,
                "source": item.plasmid.source,
                "vector_profile": item.plasmid.vector_type,
            }
            for item in result.retrieved_templates
        ],
        "recommendations": [item.model_dump(mode="json") for item in result.recommendations],
        # Dumping the whole GeneratedSequence rather than picking fields is what
        # carries sequence_spans through serialization. The spans are only useful
        # downstream if they survive the hop into JSON intact, so this must stay a
        # whole-model dump: naming fields here would silently drop any field added
        # to the model later, and a dropped span reads as unattributed bases.
        "generated": result.generated.model_dump(mode="json"),
        "annotated_sequence": result.reannotated_sequence.model_dump(mode="json"),
        "validation_report": result.validation_report.model_dump(mode="json"),
        "component_checks": [check.__dict__ for check in result.component_checks],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the bounded offline Phase 2 generation plumbing spike.")
    parser.add_argument("--text", required=True)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--fake-embedder", action="store_true", help="Use only with a fake-embedded corpus.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pipeline = build_default_spike_pipeline(local_files_only=args.local_files_only, fake_embedder=args.fake_embedder)
    result = pipeline.run(args.text)
    if args.json:
        print(json.dumps(spike_result_as_dict(result), indent=2))
    else:
        print(render_spike_result(result))
    return 0 if result.passed else 1


def _annotation_evidence_text(annotated: AnnotatedSequence) -> str:
    return " ".join([annotated.vector_profile, *(feature.name for feature in annotated.features)])


def _component_present(value: str, evidence: str, terms: tuple[ControlledTerm, ...]) -> bool:
    canonical = normalize_to_controlled(value, terms) or value
    if contains_term(evidence, canonical):
        return True
    for term in terms:
        if normalize_text(term.canonical) != normalize_text(canonical):
            continue
        return any(contains_term(evidence, synonym) for synonym in term.synonyms)
    return False


def _matching_evidence(value: str, evidence: str, terms: tuple[ControlledTerm, ...]) -> str | None:
    canonical = normalize_to_controlled(value, terms) or value
    if contains_term(evidence, canonical):
        return canonical
    for term in terms:
        if normalize_text(term.canonical) != normalize_text(canonical):
            continue
        for synonym in term.synonyms:
            if contains_term(evidence, synonym):
                return synonym
    return None


if __name__ == "__main__":
    raise SystemExit(main())
