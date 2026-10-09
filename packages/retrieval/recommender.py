from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

import requests
from pydantic import ValidationError

from packages.core.schemas import DesignSpec, PlasmidRecommendation, RetrievedPlasmid
from packages.retrieval.gemini_client import GeminiJsonClient, GeminiRecommendationClient
from packages.core.vocabularies import MARKER_TERMS, PROMOTER_TYPE_TERMS, VECTOR_TYPE_TERMS, find_controlled_terms, normalize_text


TEMPLATE_RECOMMENDER_NAME = "template-grounded-recommender-v1"


class RecommendationGenerator(Protocol):
    @property
    def name(self) -> str: ...

    def recommend(self, retrieved: Sequence[RetrievedPlasmid], spec: DesignSpec) -> list[PlasmidRecommendation]: ...


class RecommendationLLMClient(Protocol):
    def complete_json(self, *, system_prompt: str, user_prompt: str, schema: Mapping[str, Any]) -> str: ...


class TemplateRecommendationGenerator:
    @property
    def name(self) -> str:
        return TEMPLATE_RECOMMENDER_NAME

    def recommend(self, retrieved: Sequence[RetrievedPlasmid], spec: DesignSpec) -> list[PlasmidRecommendation]:
        recommendations = [
            PlasmidRecommendation(
                plasmid_id=item.plasmid.id,
                rank=index + 1,
                score=item.score,
                why_relevant=_why_relevant(item, spec),
                suggested_adaptations=_suggested_adaptations(item, spec),
                caveats=_caveats(item, spec),
            )
            for index, item in enumerate(retrieved)
        ]
        validate_recommendation_grounding(recommendations, retrieved)
        return recommendations


class LLMRecommendationGenerator:
    def __init__(self, client: RecommendationLLMClient, *, name: str = "llm-grounded-recommender-v1") -> None:
        self.client = client
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def recommend(self, retrieved: Sequence[RetrievedPlasmid], spec: DesignSpec) -> list[PlasmidRecommendation]:
        if not retrieved:
            return []
        raw = self.client.complete_json(
            system_prompt=GROUNDING_SYSTEM_PROMPT,
            user_prompt=json.dumps(build_recommendation_context(retrieved, spec), indent=2, sort_keys=True),
            schema=RECOMMENDATION_RESPONSE_SCHEMA,
        )
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("recommendation LLM returned invalid JSON") from exc
        try:
            recommendations = [PlasmidRecommendation.model_validate(item) for item in payload["recommendations"]]
        except (KeyError, TypeError, ValidationError) as exc:
            raise ValueError("recommendation LLM returned invalid recommendation payload") from exc
        validate_recommendation_grounding(recommendations, retrieved)
        return recommendations


@dataclass(frozen=True)
class OpenAIRecommendationClient:
    api_key: str
    model: str = "gpt-4o-mini"
    endpoint: str = "https://api.openai.com/v1/chat/completions"
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> OpenAIRecommendationClient:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAIRecommendationClient")
        return cls(api_key=api_key, model=os.environ.get("OPENAI_RECOMMENDER_MODEL", "gpt-4o-mini"))

    def complete_json(self, *, system_prompt: str, user_prompt: str, schema: Mapping[str, Any]) -> str:
        response = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "RetrievalRecommendations", "strict": True, "schema": schema},
                },
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload["choices"][0]["message"]["content"])


def build_recommendation_generator(*, use_llm: bool | None = None) -> RecommendationGenerator:
    provider = _recommendation_provider()
    if use_llm is True and provider == "template":
        provider = "openai"
    if provider == "template":
        return TemplateRecommendationGenerator()
    if provider == "openai":
        return LLMRecommendationGenerator(OpenAIRecommendationClient.from_env())
    if provider == "gemini":
        return LLMRecommendationGenerator(
            GeminiRecommendationClient(GeminiJsonClient.from_env()),
            name="gemini-grounded-recommender-v1",
        )
    raise ValueError(f"unsupported recommendation provider: {provider}")


def _recommendation_provider() -> str:
    provider = os.environ.get("RECOMMENDER_PROVIDER", "template").strip().casefold()
    if provider not in {"template", "openai", "gemini"}:
        raise ValueError(f"unsupported recommendation provider: {provider}")
    return provider


def validate_recommendation_grounding(
    recommendations: Sequence[PlasmidRecommendation],
    retrieved: Sequence[RetrievedPlasmid],
) -> None:
    expected_ids = [item.plasmid.id for item in retrieved]
    observed_ids = [item.plasmid_id for item in recommendations]
    if observed_ids != expected_ids:
        raise ValueError(f"recommendations must match retrieved plasmids in order: expected {expected_ids}, got {observed_ids}")
    for index, recommendation in enumerate(recommendations):
        retrieved_item = retrieved[index]
        if recommendation.rank != index + 1:
            raise ValueError(f"recommendation rank mismatch for {recommendation.plasmid_id}")
        if recommendation.score != retrieved_item.score:
            raise ValueError(f"recommendation score mismatch for {recommendation.plasmid_id}")
        if not _text_is_grounded(recommendation, retrieved_item):
            raise ValueError(f"recommendation text for {recommendation.plasmid_id} is not grounded in the retrieved record")


def build_recommendation_context(retrieved: Sequence[RetrievedPlasmid], spec: DesignSpec) -> dict[str, Any]:
    return {
        "design_spec": spec.model_dump(mode="json"),
        "retrieved_records": [
            {
                "rank": index + 1,
                "score": item.score,
                "matched_fields": item.matched_fields,
                "plasmid": {
                    "id": item.plasmid.id,
                    "name": item.plasmid.name,
                    "source": item.plasmid.source,
                    "organism": item.plasmid.organism,
                    "vector_type": item.plasmid.vector_type,
                    "markers": item.plasmid.markers,
                    "promoters": item.plasmid.promoters,
                    "use_cases": item.plasmid.use_cases,
                    "publication_doi": item.plasmid.publication_doi,
                    "raw_ref": item.plasmid.raw_ref,
                    "length": item.plasmid.length,
                    "annotation_complete": item.plasmid.annotation_complete,
                },
            }
            for index, item in enumerate(retrieved)
        ],
    }


GROUNDING_SYSTEM_PROMPT = """Generate plasmid match recommendations using only retrieved_records JSON.
Do not mention plasmids, fields, markers, promoters, organisms, vector types, papers, or use cases unless they appear in retrieved_records.
Return one recommendation per retrieved record, in the same order.
Each why_relevant value must explicitly include that record's exact plasmid id or exact plasmid name.
If the requested design requires something missing from a record, state it as a suggested adaptation, not as an existing feature.
Return JSON only."""


RECOMMENDATION_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["recommendations"],
    "properties": {
        "recommendations": {
            "type": "array",
            "items": PlasmidRecommendation.model_json_schema(),
        }
    },
}


def _why_relevant(item: RetrievedPlasmid, spec: DesignSpec) -> str:
    plasmid = item.plasmid
    reasons: list[str] = []
    if item.matched_fields:
        reasons.append(f"matched {', '.join(item.matched_fields)}")
    if spec.vector_type and _contains_any(plasmid.vector_type or " ".join(plasmid.use_cases), [spec.vector_type], VECTOR_TYPE_TERMS):
        reasons.append(f"has vector evidence for {_humanize(spec.vector_type)}")
    matching_markers = _matching_values(spec.markers, plasmid.markers, MARKER_TERMS)
    if matching_markers:
        reasons.append(f"carries selectable marker(s) {', '.join(matching_markers)}")
    matching_promoters = _matching_values([spec.promoter_type] if spec.promoter_type else [], plasmid.promoters, PROMOTER_TYPE_TERMS)
    if matching_promoters:
        reasons.append(f"includes promoter evidence {', '.join(matching_promoters)}")
    if spec.application and _contains_text(plasmid.use_cases, spec.application):
        reasons.append(f"has use-case evidence for {spec.application}")
    if not reasons:
        reasons.append("was retrieved as a semantic neighbor for the design request")
    return f"{plasmid.name} is relevant because it {reasons[0]}" + (
        f" and {'; '.join(reasons[1:])}." if len(reasons) > 1 else "."
    )


def _suggested_adaptations(item: RetrievedPlasmid, spec: DesignSpec) -> list[str]:
    changes: list[str] = []
    record_text = _record_text(item)
    for gene in spec.genes:
        if normalize_text(gene) not in normalize_text(record_text):
            changes.append(f"Insert or replace the payload with {gene} to match the requested gene.")
    if spec.promoter_type and not _contains_any(record_text, [spec.promoter_type], PROMOTER_TYPE_TERMS):
        changes.append(f"Swap or add a {spec.promoter_type} promoter if that control mode is required.")
    missing_markers = [marker for marker in spec.markers if not _contains_any(record_text, [marker], MARKER_TERMS)]
    if missing_markers:
        changes.append(f"Change selectable marker support to {', '.join(missing_markers)}.")
    if spec.vector_type and "vector_type" not in item.matched_fields:
        changes.append(f"Move the relevant cassette into a {_humanize(spec.vector_type)} backbone before use.")
    if not changes:
        changes.append("Use this plasmid as a starting template with only experiment-specific insert and cloning edits.")
    return changes


def _caveats(item: RetrievedPlasmid, spec: DesignSpec) -> list[str]:
    plasmid = item.plasmid
    caveats: list[str] = []
    if not plasmid.annotation_complete:
        caveats.append("Annotation is incomplete, so verify component boundaries before adapting this record.")
    if spec.promoter_type and not plasmid.promoters:
        caveats.append("No promoter is recorded in the plasmid metadata; confirm promoter compatibility manually.")
    if spec.markers and not plasmid.markers and "markers" not in item.matched_fields:
        caveats.append("No selectable marker is recorded in the plasmid metadata; confirm selection before use.")
    if spec.genes and "genes" not in item.matched_fields:
        caveats.append("The retrieved plasmid may be a backbone/template rather than a record already carrying the requested gene.")
    return caveats


def _text_is_grounded(recommendation: PlasmidRecommendation, item: RetrievedPlasmid) -> bool:
    allowed_names = {item.plasmid.id, item.plasmid.name}
    all_text = " ".join([recommendation.why_relevant, *recommendation.suggested_adaptations, *recommendation.caveats])
    if recommendation.plasmid_id not in allowed_names:
        return False
    return item.plasmid.name in all_text or item.plasmid.id in all_text


def _matching_values(requested: Sequence[str], candidate_values: Sequence[str], terms) -> list[str]:
    text = " ".join(candidate_values)
    return [value for value in requested if _contains_any(text, [value], terms)]


def _contains_any(text: str, values: Sequence[str], terms) -> bool:
    found = set(find_controlled_terms(text, terms))
    for value in values:
        if value in found or normalize_text(value) in normalize_text(text):
            return True
    return False


def _contains_text(values: Sequence[str], requested: str) -> bool:
    text = normalize_text(" ".join(values))
    return normalize_text(requested) in text


def _record_text(item: RetrievedPlasmid) -> str:
    plasmid = item.plasmid
    return " ".join(
        [
            plasmid.id,
            plasmid.name,
            plasmid.organism or "",
            plasmid.vector_type or "",
            *plasmid.markers,
            *plasmid.promoters,
            *plasmid.use_cases,
            *item.matched_fields,
        ]
    )


def _humanize(value: str) -> str:
    return value.replace("_", " ")
