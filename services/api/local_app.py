from __future__ import annotations

import logging
import os
from pathlib import Path
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import psycopg
from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from packages.application import (
    FakeJobQueue,
    InMemoryJobStore,
    InMemoryOutcomeStore,
    InMemorySessionStore,
    PostgresJobStore,
    PostgresOutcomeStore,
    PostgresSessionStore,
)
from packages.application.design_jobs import GenerationDesignJobHandler
from packages.application.designs import InMemoryDesignStore, PostgresDesignStore
from packages.data_pipeline.ingest.genbank import load_dotenv
from packages.generation.generator import FakeGenerator
from packages.generation.spike import GenerationSpikePipeline, ParserReannotator
from packages.retrieval.embed_corpus import EmbedCorpusConfig, build_embedder, build_vector_store
from packages.retrieval.anthropic_client import (
    AnthropicIntentClient,
    AnthropicJsonClient,
    AnthropicRecommendationClient,
)
from packages.retrieval.gemini_client import GeminiIntentClient, GeminiJsonClient, GeminiRecommendationClient
from packages.retrieval.intent_parser import FakeIntentParser, LLMIntentParser
from packages.retrieval.recommender import LLMRecommendationGenerator, TemplateRecommendationGenerator
from packages.retrieval.retriever import HybridRetriever, PostgresRetrievalRepository
from packages.validation.engine import ConstraintEngine as DeterministicConstraintEngine
from services.api.app import create_app


REQUIRED_CORPUS_TABLES = ("plasmids", "plasmid_embeddings")
REQUIRED_APP_TABLES = ("sessions", "session_turns", "jobs", "designs", "outcomes")


def build_local_app() -> FastAPI:
    _load_env_defaults(Path(".env"))
    config = EmbedCorpusConfig.from_env(
        batch_size=1,
        limit=None,
        use_fake=False,
        local_files_only=False,
        hf_cache_dir=None,
    )
    if config.use_fake:
        raise RuntimeError("Local app requires a real retrieval embedder configuration; EMBEDDING_FAKE must be false.")
    _assert_corpus_ready(config.database_url)
    _run_app_migrations()
    stores = _build_application_stores(config.database_url)
    pipeline = _build_local_pipeline(config)
    handler = GenerationDesignJobHandler(pipeline=pipeline, design_store=stores["design_store"])
    queue = FakeJobQueue(store=stores["job_store"], handler=handler)
    return create_app(
        session_store=stores["session_store"],
        job_queue=queue,
        design_store=stores["design_store"],
        outcome_store=stores["outcome_store"],
        template_reader=_build_template_reader(config.database_url),
    )


def _build_template_reader(database_url: str) -> Callable[[Sequence[str]], Mapping[str, str]]:
    """Read the full sequence of named corpus templates, for the section 11.1 gate.

    This is what turns a plasmid export from a recorded claim into a verified one.
    The gate holds a span saying which bases of the candidate came from which
    bases of a named template, and it needs the template itself to compare
    against. The corpus keeps the whole sequence of every record it holds, so the
    comparison is against the actual source and not against a copy stored next to
    the design, which would be comparing the design to itself.

    A template this returns nothing for is not a pass: the gate reports UNKNOWN
    for the claim it could not check and the export is blocked.
    """
    repository = PostgresRetrievalRepository(database_url)

    def read(template_ids: Sequence[str]) -> Mapping[str, str]:
        return {
            plasmid.id: plasmid.sequence for plasmid in repository.get_plasmids(list(template_ids))
        }

    return read


def _run_app_migrations() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    command.upgrade(Config(str(repository_root / "alembic.ini")), "head")


def _load_env_defaults(path: Path) -> None:
    for key, value in load_dotenv(path).items():
        os.environ.setdefault(key, value)


def _build_local_pipeline(config: EmbedCorpusConfig) -> GenerationSpikePipeline:
    embedder = build_embedder(config)
    vector_index = build_vector_store(config, embedder)
    retriever = HybridRetriever(
        vector_index=vector_index,
        embedder=embedder,
        repository=PostgresRetrievalRepository(config.database_url),
    )
    # Provider precedence: Claude, then Gemini, then neither.
    #
    # Claude first because it is the configured provider for this deployment and
    # its model is pinned by an allowlist rather than by a default. Gemini stays
    # as the fallback rather than being deleted, because it is the path the
    # existing tests and research notes describe.
    #
    # With no key at all the pipeline uses FakeIntentParser and
    # TemplateRecommendationGenerator. That is a real reduction in capability and
    # not a silent equivalence: intent is parsed by rule instead of by model. It
    # is reported at startup so an operator cannot mistake one for the other.
    anthropic_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    google_key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
    if anthropic_key:
        claude = AnthropicJsonClient.from_env()
        parser = LLMIntentParser(AnthropicIntentClient(claude))
        recommender = LLMRecommendationGenerator(
            AnthropicRecommendationClient(claude),
            name=f"claude-grounded-recommender-v1:{claude.model}",
        )
        logging.getLogger("construct.api").info(
            "intent_provider_selected", extra={"provider": "anthropic", "model": claude.model}
        )
    elif google_key:
        gemini = GeminiJsonClient(api_key=google_key)
        parser = LLMIntentParser(GeminiIntentClient(gemini))
        recommender = LLMRecommendationGenerator(
            GeminiRecommendationClient(gemini),
            name="gemini-grounded-recommender-v1",
        )
        logging.getLogger("construct.api").info(
            "intent_provider_selected", extra={"provider": "google", "model": gemini.model}
        )
    else:
        parser = FakeIntentParser()
        recommender = TemplateRecommendationGenerator()
        logging.getLogger("construct.api").warning(
            "intent_provider_selected",
            extra={"provider": "none", "detail": "rule based intent parsing, no model configured"},
        )
    return GenerationSpikePipeline(
        parser=parser,
        retriever=retriever,
        generator=FakeGenerator(),
        reannotator=ParserReannotator(),
        constraint_engine=DeterministicConstraintEngine(),
        recommendation_generator=recommender,
    )


def _build_application_stores(database_url: str) -> dict[str, Any]:
    if _tables_available(database_url, REQUIRED_APP_TABLES):
        return {
            "session_store": PostgresSessionStore(database_url),
            "job_store": PostgresJobStore(database_url),
            "design_store": PostgresDesignStore(database_url),
            "outcome_store": PostgresOutcomeStore(database_url),
        }
    return {
        "session_store": InMemorySessionStore(),
        "job_store": InMemoryJobStore(),
        "design_store": InMemoryDesignStore(),
        "outcome_store": InMemoryOutcomeStore(),
    }


def _assert_corpus_ready(database_url: str) -> None:
    try:
        if not _tables_available(database_url, REQUIRED_CORPUS_TABLES, require_vector_extension=True):
            missing = ", ".join(REQUIRED_CORPUS_TABLES)
            raise RuntimeError(f"Local app requires corpus tables and pgvector at DATABASE_URL; missing one of: {missing}.")
    except psycopg.Error as exc:
        raise RuntimeError("Local app requires a reachable Postgres corpus at DATABASE_URL.") from exc


def _tables_available(
    database_url: str,
    tables: tuple[str, ...],
    *,
    require_vector_extension: bool = False,
) -> bool:
    with psycopg.connect(database_url) as connection:
        available = {
            row[0]
            for row in connection.execute(
                "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public' AND tablename = ANY(%s)",
                (list(tables),),
            ).fetchall()
        }
        if require_vector_extension:
            vector_ready = connection.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'").fetchone() is not None
            if not vector_ready:
                return False
        return all(table in available for table in tables)
