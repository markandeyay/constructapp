from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

import psycopg

from packages.core.schemas import DesignSpec, Plasmid, RetrievedPlasmid
from packages.core.vocabularies import (
    MARKER_TERMS,
    ORGANISM_TERMS,
    PROMOTER_TYPE_TERMS,
    VECTOR_TYPE_TERMS,
    contains_term,
    find_controlled_terms,
    normalize_text,
    normalize_to_controlled,
)
from packages.retrieval.document_composer import DOCUMENT_VERSION
from packages.retrieval.embedder import Embedder
from packages.retrieval.vector_store import VectorIndex


DEFAULT_RETRIEVAL_K = 5
DEFAULT_CANDIDATE_MULTIPLIER = 10
MIN_CANDIDATE_LIMIT = 50
GENERIC_NAME_ALIASES = frozenset(
    {
        "synthetic construct",
        "cloning vector",
        "expression vector",
        "reporter vector",
        "shuttle vector",
        "plasmid",
        "vector",
    }
)
NAME_LIKE_TOKEN_PATTERN = re.compile(r"\b(?:p[A-Za-z0-9][A-Za-z0-9_.+-]{1,}|[A-Z]{1,3}\d{4,}(?:\.\d+)?)\b")


@dataclass(frozen=True)
class PlasmidNameRecord:
    plasmid_id: str
    name: str


class PlasmidRepository(Protocol):
    def get_plasmids(self, plasmid_ids: Sequence[str]) -> list[Plasmid]: ...
    def list_name_records(self) -> list[PlasmidNameRecord]: ...


class Retriever(Protocol):
    def retrieve(self, spec: DesignSpec, k: int = DEFAULT_RETRIEVAL_K) -> list[RetrievedPlasmid]: ...


@dataclass(frozen=True)
class PostgresRetrievalRepository:
    database_url: str

    def get_plasmids(self, plasmid_ids: Sequence[str]) -> list[Plasmid]:
        if not plasmid_ids:
            return []
        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute(
                "SELECT id, payload FROM plasmids WHERE id = ANY(%s)",
                (list(plasmid_ids),),
            ).fetchall()
        by_id = {row[0]: Plasmid.model_validate(row[1]) for row in rows}
        return [by_id[plasmid_id] for plasmid_id in plasmid_ids if plasmid_id in by_id]

    def list_name_records(self) -> list[PlasmidNameRecord]:
        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute("SELECT id, payload->>'name' AS name FROM plasmids").fetchall()
        return [PlasmidNameRecord(plasmid_id=row[0], name=row[1]) for row in rows if row[1]]


@dataclass(frozen=True)
class _NameAlias:
    plasmid_id: str
    alias: str
    normalized_alias: str
    priority: int


@dataclass(frozen=True)
class _ExactMatch:
    plasmid_id: str
    alias: str
    priority: int


class HybridRetriever:
    def __init__(
        self,
        *,
        vector_index: VectorIndex,
        embedder: Embedder,
        repository: PlasmidRepository,
        candidate_multiplier: int = DEFAULT_CANDIDATE_MULTIPLIER,
        min_candidate_limit: int = MIN_CANDIDATE_LIMIT,
    ) -> None:
        if candidate_multiplier <= 0:
            raise ValueError("candidate_multiplier must be positive")
        if min_candidate_limit <= 0:
            raise ValueError("min_candidate_limit must be positive")
        self.vector_index = vector_index
        self.embedder = embedder
        self.repository = repository
        self.candidate_multiplier = candidate_multiplier
        self.min_candidate_limit = min_candidate_limit
        self._name_aliases: list[_NameAlias] | None = None

    def retrieve(self, spec: DesignSpec, k: int = DEFAULT_RETRIEVAL_K) -> list[RetrievedPlasmid]:
        if k <= 0:
            raise ValueError("k must be positive")
        if spec.clarification_needed:
            return []
        query_document = compose_design_query_document(spec)
        exact_matches = self._find_exact_name_matches(query_document)
        query_vector = self.embedder.embed([query_document])[0]
        candidate_limit = max(k * self.candidate_multiplier, self.min_candidate_limit)
        matches = self.vector_index.query(
            query_vector,
            limit=candidate_limit,
            metadata_filter={"document_version": DOCUMENT_VERSION},
        )
        lookup_ids = _dedupe_ids([item.plasmid_id for item in exact_matches] + [match.plasmid_id for match in matches])
        plasmids = self.repository.get_plasmids(lookup_ids)
        plasmids_by_id = {plasmid.id: plasmid for plasmid in plasmids}
        metadata_by_id = {match.plasmid_id: match.metadata for match in matches}

        retrieved: list[RetrievedPlasmid] = []
        seen_ids: set[str] = set()
        top_semantic_score = max((max(0.0, match.score) for match in matches), default=0.0)
        lexical_score = max(1.0, top_semantic_score)
        for exact in exact_matches:
            plasmid = plasmids_by_id.get(exact.plasmid_id)
            if plasmid is None or plasmid.id in seen_ids:
                continue
            metadata = metadata_by_id.get(exact.plasmid_id, {})
            if not passes_structured_filters(spec, plasmid, metadata):
                continue
            retrieved.append(
                RetrievedPlasmid(
                    plasmid=plasmid,
                    score=lexical_score,
                    matched_fields=_matched_fields_for_exact_name(spec, plasmid, metadata),
                )
            )
            seen_ids.add(plasmid.id)
            if len(retrieved) >= k:
                return retrieved
        for match in matches:
            if match.plasmid_id in seen_ids:
                continue
            plasmid = plasmids_by_id.get(match.plasmid_id)
            if plasmid is None:
                continue
            metadata = metadata_by_id.get(match.plasmid_id, {})
            if not passes_structured_filters(spec, plasmid, metadata):
                continue
            retrieved.append(
                RetrievedPlasmid(
                    plasmid=plasmid,
                    score=max(0.0, match.score),
                    matched_fields=matched_fields(spec, plasmid, metadata),
                )
            )
            seen_ids.add(plasmid.id)
            if len(retrieved) >= k:
                break
        return retrieved

    def _find_exact_name_matches(self, query_text: str) -> list[_ExactMatch]:
        matches_by_id: dict[str, _ExactMatch] = {}
        for alias in self._load_name_aliases():
            if not contains_term(query_text, alias.alias):
                continue
            current = matches_by_id.get(alias.plasmid_id)
            candidate = _ExactMatch(plasmid_id=alias.plasmid_id, alias=alias.alias, priority=alias.priority)
            if current is None or _exact_match_sort_key(candidate) > _exact_match_sort_key(current):
                matches_by_id[alias.plasmid_id] = candidate
        return sorted(matches_by_id.values(), key=_exact_match_sort_key, reverse=True)

    def _load_name_aliases(self) -> list[_NameAlias]:
        if self._name_aliases is None:
            aliases: list[_NameAlias] = []
            for record in self.repository.list_name_records():
                aliases.extend(_build_name_aliases(record))
            self._name_aliases = aliases
        return self._name_aliases


def compose_design_query_document(spec: DesignSpec) -> str:
    clauses: list[str] = ["Plasmid design retrieval request."]
    if spec.organism and spec.organism != "unknown":
        clauses.append(f"Target organism: {spec.organism}.")
    if spec.cell_line:
        clauses.append(f"Cell line: {spec.cell_line}.")
    if spec.vector_type:
        clauses.append(f"Vector type: {_humanize(spec.vector_type)}.")
    if spec.genes:
        clauses.append(f"Genes or payloads: {_join(spec.genes)}.")
    if spec.tags:
        clauses.append(f"Tags: {_join(spec.tags)}.")
    if spec.promoter_type:
        clauses.append(f"Promoter preference: {spec.promoter_type}.")
    if spec.inducer:
        clauses.append(f"Inducer: {spec.inducer}.")
    if spec.markers:
        clauses.append(f"Selectable markers: {_join(spec.markers)}.")
    if spec.source:
        clauses.append(f"Requested source provenance: {spec.source}.")
    if spec.publication_doi:
        clauses.append(f"Requested publication DOI: {spec.publication_doi}.")
    if spec.application:
        clauses.append(f"Application: {spec.application}.")
    if spec.cloning_method:
        clauses.append(f"Cloning method: {spec.cloning_method}.")
    if spec.constraints:
        clauses.append(f"Specific constraints and identity cues: {_join(spec.constraints)}.")
    return " ".join(clauses)


def passes_structured_filters(spec: DesignSpec, plasmid: Plasmid, metadata: Mapping[str, Any]) -> bool:
    if spec.vector_type and not _vector_matches(spec.vector_type, plasmid, metadata):
        return False
    if spec.organism and spec.organism != "unknown" and not _organism_matches(spec.organism, plasmid, metadata):
        return False
    if spec.markers and not _markers_match(spec.markers, plasmid, metadata):
        return False
    if spec.source and not _source_matches(spec.source, plasmid, metadata):
        return False
    if spec.publication_doi and not _publication_doi_matches(spec.publication_doi, plasmid, metadata):
        return False
    return True


def matched_fields(spec: DesignSpec, plasmid: Plasmid, metadata: Mapping[str, Any]) -> list[str]:
    fields = ["semantic"]
    if spec.vector_type and _vector_matches(spec.vector_type, plasmid, metadata):
        fields.append("vector_type")
    if spec.organism and spec.organism != "unknown" and _organism_matches(spec.organism, plasmid, metadata):
        fields.append("organism")
    if spec.markers and _markers_match(spec.markers, plasmid, metadata):
        fields.append("markers")
    if spec.source and _source_matches(spec.source, plasmid, metadata):
        fields.append("source")
    if spec.publication_doi and _publication_doi_matches(spec.publication_doi, plasmid, metadata):
        fields.append("publication_doi")
    if spec.promoter_type and _contains_controlled(_candidate_text(plasmid, metadata, keys=("promoters",)), spec.promoter_type, PROMOTER_TYPE_TERMS):
        fields.append("promoters")
    if spec.genes and _any_text_overlap(spec.genes, _candidate_text(plasmid, metadata, keys=("payloads", "use_cases"))):
        fields.append("genes")
    if spec.tags and _any_text_overlap(spec.tags, _candidate_text(plasmid, metadata, keys=("payloads", "use_cases", "promoters"))):
        fields.append("tags")
    if spec.application and _any_text_overlap([spec.application], _candidate_text(plasmid, metadata, keys=("use_cases",))):
        fields.append("application")
    return fields


def _matched_fields_for_exact_name(spec: DesignSpec, plasmid: Plasmid, metadata: Mapping[str, Any]) -> list[str]:
    fields = ["lexical_name"]
    if spec.vector_type and _vector_matches(spec.vector_type, plasmid, metadata):
        fields.append("vector_type")
    if spec.organism and spec.organism != "unknown" and _organism_matches(spec.organism, plasmid, metadata):
        fields.append("organism")
    if spec.markers and _markers_match(spec.markers, plasmid, metadata):
        fields.append("markers")
    return fields


def _vector_matches(requested: str, plasmid: Plasmid, metadata: Mapping[str, Any]) -> bool:
    requested_family = _vector_family(requested)
    if requested_family is None:
        return True
    candidate_families = _candidate_vector_families(plasmid, metadata)
    if not candidate_families:
        return False
    if requested_family in candidate_families:
        return True
    if requested_family == "mammalian_expression" and "mammalian_reporter" in candidate_families:
        return True
    if requested_family == "mammalian_reporter" and "mammalian_expression" in candidate_families:
        return True
    return False


def _organism_matches(requested: str, plasmid: Plasmid, metadata: Mapping[str, Any]) -> bool:
    requested_bucket = _organism_bucket(requested)
    if requested_bucket is None:
        return _any_text_overlap([requested], _candidate_text(plasmid, metadata))
    candidate_text = _candidate_text(plasmid, metadata)
    candidate_bucket = _organism_bucket(candidate_text)
    vector_families = _candidate_vector_families(plasmid, metadata)
    if candidate_bucket == requested_bucket:
        return True
    if requested_bucket == "bacterial" and any(family.startswith("bacterial") for family in vector_families):
        return True
    if requested_bucket == "mammalian" and any(family.startswith("mammalian") or family == "lentiviral" for family in vector_families):
        return True
    if requested_bucket == "yeast" and "yeast" in vector_families:
        return True
    if candidate_bucket is None and vector_families:
        if (
            "shuttle" in vector_families
            and requested_bucket in {"bacterial", "yeast"}
            and not _has_conflicting_host_evidence(requested_bucket, candidate_text, vector_families)
        ):
            return True
        return requested_bucket in vector_families
    return candidate_bucket is None and not _has_conflicting_host_evidence(requested_bucket, candidate_text, vector_families)


def _markers_match(requested_markers: Sequence[str], plasmid: Plasmid, metadata: Mapping[str, Any]) -> bool:
    candidate_groups = set(find_controlled_terms(_candidate_text(plasmid, metadata, keys=("markers", "use_cases")), MARKER_TERMS))
    for marker in requested_markers:
        requested = normalize_to_controlled(marker, MARKER_TERMS) or marker
        if requested not in candidate_groups:
            return False
    return True


def _candidate_vector_families(plasmid: Plasmid, metadata: Mapping[str, Any]) -> set[str]:
    values: list[str] = []
    profile = metadata.get("vector_profile")
    if isinstance(profile, str):
        values.append(profile)
    if plasmid.vector_type:
        values.append(plasmid.vector_type)
    values.extend(plasmid.use_cases)
    source_description = metadata.get("source_description")
    if isinstance(source_description, str):
        values.append(source_description)
    values.extend(_candidate_labels(metadata, "use_cases"))
    text = " ".join(values)
    families = {_vector_family(value) for value in find_controlled_terms(text, VECTOR_TYPE_TERMS)}
    explicit = _vector_family(str(profile)) if profile else None
    if explicit is not None:
        families.add(explicit)
    return {family for family in families if family is not None}


def _source_matches(requested: str, plasmid: Plasmid, metadata: Mapping[str, Any]) -> bool:
    requested_value = normalize_text(requested)
    candidate_values = {
        normalize_text(str(plasmid.source)),
        normalize_text(str(metadata.get("source", ""))),
        normalize_text(str(metadata.get("source_description", ""))),
    }
    return requested_value in candidate_values


def _publication_doi_matches(requested: str, plasmid: Plasmid, metadata: Mapping[str, Any]) -> bool:
    requested_value = normalize_text(requested)
    candidate_values = {
        normalize_text(plasmid.publication_doi or ""),
        normalize_text(str(metadata.get("publication_doi", ""))),
    }
    return requested_value in candidate_values


def _vector_family(value: str) -> str | None:
    canonical = normalize_to_controlled(value, VECTOR_TYPE_TERMS) or value
    normalized = normalize_text(canonical)
    if "lentiviral" in normalized or "retroviral" in normalized:
        return "lentiviral"
    if "mammalian reporter" in normalized:
        return "mammalian_reporter"
    if "mammalian expression" in normalized:
        return "mammalian_expression"
    if "bacterial expression" in normalized:
        return "bacterial_expression"
    if "bacterial cloning" in normalized:
        return "bacterial_cloning"
    if "crispr" in normalized:
        return "crispr"
    if "yeast shuttle" in normalized or normalized == "yeast_shuttle_vector":
        return "yeast"
    if "general shuttle" in normalized or normalized == "general_shuttle_vector" or "shuttle vector" in normalized:
        return "shuttle"
    return None


def _organism_bucket(value: str) -> str | None:
    text = normalize_text(value)
    canonical = find_controlled_terms(value, ORGANISM_TERMS)
    if any(item in {"Homo sapiens", "Mus musculus", "Rattus norvegicus"} for item in canonical):
        return "mammalian"
    if "mammalian" in text or any(token in text for token in ("human", "hek293", "hela", "cho")):
        return "mammalian"
    if "escherichia coli" in text or "e coli" in text or "ecoli" in text or "bacterial" in text:
        return "bacterial"
    if "Saccharomyces cerevisiae" in canonical or "yeast" in text or "saccharomyces" in text:
        return "yeast"
    if "arabidopsis" in text or "plant" in text:
        return "plant"
    return None


def _has_conflicting_host_evidence(requested_bucket: str, candidate_text: str, vector_families: set[str]) -> bool:
    candidate_bucket = _organism_bucket(candidate_text)
    if candidate_bucket is not None and candidate_bucket != requested_bucket:
        return True
    if requested_bucket == "bacterial" and any(family.startswith("mammalian") or family in {"lentiviral", "yeast"} for family in vector_families):
        return True
    if requested_bucket == "mammalian" and any(family.startswith("bacterial") or family == "yeast" for family in vector_families):
        return True
    if requested_bucket == "yeast" and any(family.startswith("bacterial") or family.startswith("mammalian") for family in vector_families):
        return True
    return False


def _candidate_text(plasmid: Plasmid, metadata: Mapping[str, Any], *, keys: Sequence[str] | None = None) -> str:
    values: list[str] = [plasmid.id, plasmid.name, plasmid.organism or "", plasmid.vector_type or ""]
    if keys is None or "markers" in keys:
        values.extend(plasmid.markers)
    if keys is None or "promoters" in keys:
        values.extend(plasmid.promoters)
    if keys is None or "use_cases" in keys:
        values.extend(plasmid.use_cases)
    if keys is None:
        source_description = metadata.get("source_description")
        if isinstance(source_description, str):
            values.append(source_description)
        profile = metadata.get("vector_profile")
        if isinstance(profile, str):
            values.append(profile)
    for key in keys or ("markers", "promoters", "payloads", "use_cases", "origins", "terminators", "cloning_sites"):
        values.extend(_candidate_labels(metadata, key))
    return " ".join(str(value) for value in values if value)


def _candidate_labels(metadata: Mapping[str, Any], key: str) -> list[str]:
    candidates = metadata.get("candidates")
    if not isinstance(candidates, Mapping):
        return []
    values = candidates.get(key)
    if not isinstance(values, list):
        return []
    labels: list[str] = []
    for value in values:
        if isinstance(value, str):
            labels.append(value)
        elif isinstance(value, Mapping) and isinstance(value.get("label"), str):
            labels.append(value["label"])
    return labels


def _contains_controlled(text: str, requested: str, terms: tuple[Any, ...]) -> bool:
    requested_value = normalize_to_controlled(requested, terms) or requested
    return requested_value in find_controlled_terms(text, terms) or normalize_text(requested_value) in normalize_text(text)


def _any_text_overlap(values: Sequence[str], text: str) -> bool:
    normalized_text = normalize_text(text)
    return any(normalize_text(value) in normalized_text for value in values if value)


def _join(values: Sequence[str]) -> str:
    return ", ".join(values)


def _humanize(value: str) -> str:
    return value.replace("_", " ")


def _dedupe_ids(plasmid_ids: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for plasmid_id in plasmid_ids:
        if plasmid_id in seen:
            continue
        seen.add(plasmid_id)
        ordered.append(plasmid_id)
    return ordered


def _build_name_aliases(record: PlasmidNameRecord) -> list[_NameAlias]:
    candidates: list[tuple[str, int]] = [(record.name.strip(), 3)]
    identifier = _plasmid_identifier_alias(record.plasmid_id)
    if identifier:
        candidates.append((identifier, 2))
    aliases: list[_NameAlias] = []
    seen: set[str] = set()
    for value, priority in candidates:
        for alias in _extract_safe_aliases(value):
            normalized_alias = normalize_text(alias)
            if normalized_alias in seen:
                continue
            seen.add(normalized_alias)
            aliases.append(
                _NameAlias(
                    plasmid_id=record.plasmid_id,
                    alias=alias,
                    normalized_alias=normalized_alias,
                    priority=priority,
                )
            )
    return aliases


def _extract_safe_aliases(value: str) -> list[str]:
    normalized = normalize_text(value)
    aliases: list[str] = []
    if normalized and normalized not in GENERIC_NAME_ALIASES and _looks_like_named_record(value):
        aliases.append(value.strip())
    for match in NAME_LIKE_TOKEN_PATTERN.finditer(value):
        token = match.group(0).strip("()[]{}.,;:")
        if token and normalize_text(token) not in GENERIC_NAME_ALIASES:
            aliases.append(token)
    deduped: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        key = normalize_text(alias)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(alias)
    return deduped


def _plasmid_identifier_alias(plasmid_id: str) -> str | None:
    if ":" in plasmid_id:
        tail = plasmid_id.rsplit(":", 1)[1].strip()
        if tail:
            return tail
    stripped = plasmid_id.strip()
    return stripped or None


def _looks_like_named_record(value: str) -> bool:
    return NAME_LIKE_TOKEN_PATTERN.search(value) is not None


def _exact_match_sort_key(match: _ExactMatch) -> tuple[int, int, str]:
    return (match.priority, len(normalize_text(match.alias)), match.plasmid_id)
