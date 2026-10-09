from __future__ import annotations

import json

import pytest

from packages.core.schemas import DesignSpec, Plasmid, RetrievedPlasmid
from packages.retrieval.gemini_client import GeminiRecommendationClient
from packages.retrieval.recommender import (
    LLMRecommendationGenerator,
    TemplateRecommendationGenerator,
    build_recommendation_context,
    build_recommendation_generator,
    validate_recommendation_grounding,
)


class FakeRecommendationClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def complete_json(self, *, system_prompt: str, user_prompt: str, schema: dict) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt, "schema": schema})
        return json.dumps(self.payload)


def plasmid(
    plasmid_id: str = "curated:pEGFP-N1",
    *,
    name: str = "pEGFP-N1",
    markers: list[str] | None = None,
    promoters: list[str] | None = None,
    use_cases: list[str] | None = None,
    vector_type: str | None = "mammalian reporter vector",
    annotation_complete: bool = True,
) -> Plasmid:
    return Plasmid(
        id=plasmid_id,
        source="curated",
        name=name,
        sequence="ACGT" * 100,
        length=400,
        organism="Cloning vector pEGFP-N1",
        vector_type=vector_type,
        markers=["neomycin phosphotransferase"] if markers is None else markers,
        promoters=["CMV immediate-early enhancer/promoter"] if promoters is None else promoters,
        use_cases=["fluorescent reporting"] if use_cases is None else use_cases,
        annotation_complete=annotation_complete,
        raw_ref=f"raw/curated/{name}.gb",
    )


def retrieved(plasmid_id: str = "curated:pEGFP-N1", **kwargs) -> RetrievedPlasmid:
    return RetrievedPlasmid(
        plasmid=plasmid(plasmid_id, **kwargs),
        score=0.91,
        matched_fields=["semantic", "vector_type", "markers", "promoters", "application"],
    )


def test_template_recommender_returns_one_recommendation_per_match() -> None:
    items = [retrieved(), retrieved("curated:pGL3-Basic", name="pGL3-Basic", markers=["AmpR"], promoters=[], use_cases=["reporter"])]
    spec = DesignSpec(organism="Homo sapiens", vector_type="mammalian_reporter_vector", application="reporter assay")

    recommendations = TemplateRecommendationGenerator().recommend(items, spec)

    assert [item.plasmid_id for item in recommendations] == ["curated:pEGFP-N1", "curated:pGL3-Basic"]
    assert [item.rank for item in recommendations] == [1, 2]
    assert [item.score for item in recommendations] == [0.91, 0.91]


def test_template_recommender_explains_relevance_and_validates_grounding() -> None:
    item = retrieved()
    spec = DesignSpec(
        organism="Homo sapiens",
        vector_type="mammalian_reporter_vector",
        markers=["neomycin/G418"],
        promoter_type="CMV",
        application="fluorescent reporting",
    )

    recommendations = TemplateRecommendationGenerator().recommend([item], spec)

    assert "pEGFP-N1 is relevant" in recommendations[0].why_relevant
    assert "marker" in recommendations[0].why_relevant
    assert "promoter" in recommendations[0].why_relevant
    validate_recommendation_grounding(recommendations, [item])


def test_template_recommender_suggests_promoter_marker_gene_and_backbone_changes() -> None:
    item = RetrievedPlasmid(
        plasmid=plasmid(markers=["AmpR"], promoters=["CMV"], vector_type="bacterial cloning vector"),
        score=0.75,
        matched_fields=["semantic"],
    )
    spec = DesignSpec(
        organism="Homo sapiens",
        vector_type="lentiviral_or_retroviral_transfer_vector",
        genes=["BRCA1"],
        promoter_type="doxycycline-inducible",
        markers=["puromycin"],
    )

    recommendation = TemplateRecommendationGenerator().recommend([item], spec)[0]

    assert any("BRCA1" in change for change in recommendation.suggested_adaptations)
    assert any("doxycycline-inducible" in change for change in recommendation.suggested_adaptations)
    assert any("puromycin" in change for change in recommendation.suggested_adaptations)
    assert any("lentiviral" in change for change in recommendation.suggested_adaptations)


def test_template_recommender_adds_caveats_for_incomplete_or_sparse_metadata() -> None:
    item = RetrievedPlasmid(
        plasmid=plasmid(markers=[], promoters=[], annotation_complete=False),
        score=0.8,
        matched_fields=["semantic"],
    )
    spec = DesignSpec(organism="Homo sapiens", genes=["BRCA1"], promoter_type="CMV", markers=["puromycin"])

    caveats = TemplateRecommendationGenerator().recommend([item], spec)[0].caveats

    assert any("Annotation is incomplete" in caveat for caveat in caveats)
    assert any("No promoter" in caveat for caveat in caveats)
    assert any("No selectable marker" in caveat for caveat in caveats)


def test_grounding_rejects_unknown_plasmid_or_rank_or_score_mismatch() -> None:
    item = retrieved()
    valid = TemplateRecommendationGenerator().recommend([item], DesignSpec(organism="Homo sapiens"))[0]

    with pytest.raises(ValueError, match="expected"):
        validate_recommendation_grounding([valid.model_copy(update={"plasmid_id": "invented:pFoo"})], [item])
    with pytest.raises(ValueError, match="rank"):
        validate_recommendation_grounding([valid.model_copy(update={"rank": 2})], [item])
    with pytest.raises(ValueError, match="score"):
        validate_recommendation_grounding([valid.model_copy(update={"score": 0.1})], [item])


def test_grounding_rejects_missing_recommendation_for_retrieved_match() -> None:
    items = [retrieved(), retrieved("curated:pGL3-Basic", name="pGL3-Basic")]
    one = TemplateRecommendationGenerator().recommend([items[0]], DesignSpec(organism="Homo sapiens"))

    with pytest.raises(ValueError, match="expected"):
        validate_recommendation_grounding(one, items)


def test_llm_recommender_validates_client_output_and_builds_grounded_context() -> None:
    item = retrieved()
    payload = {
        "recommendations": [
            {
                "plasmid_id": item.plasmid.id,
                "rank": 1,
                "score": item.score,
                "why_relevant": "pEGFP-N1 is relevant because it is one of the retrieved records.",
                "suggested_adaptations": ["Use pEGFP-N1 as the starting template."],
                "caveats": [],
            }
        ]
    }
    client = FakeRecommendationClient(payload)

    recommendations = LLMRecommendationGenerator(client).recommend([item], DesignSpec(organism="Homo sapiens"))
    context = build_recommendation_context([item], DesignSpec(organism="Homo sapiens"))

    assert recommendations[0].plasmid_id == item.plasmid.id
    assert context["retrieved_records"][0]["plasmid"]["id"] == item.plasmid.id
    assert client.calls
    assert "exact plasmid id or exact plasmid name" in client.calls[0]["system_prompt"]


def test_llm_recommender_rejects_ungrounded_client_output() -> None:
    item = retrieved()
    client = FakeRecommendationClient(
        {
            "recommendations": [
                {
                    "plasmid_id": "invented:pFoo",
                    "rank": 1,
                    "score": item.score,
                    "why_relevant": "pFoo is relevant.",
                    "suggested_adaptations": [],
                    "caveats": [],
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="expected"):
        LLMRecommendationGenerator(client).recommend([item], DesignSpec(organism="Homo sapiens"))


def test_llm_recommender_rejects_invalid_json() -> None:
    class BadClient:
        def complete_json(self, *, system_prompt: str, user_prompt: str, schema: dict) -> str:
            return "not json"

    with pytest.raises(ValueError, match="invalid JSON"):
        LLMRecommendationGenerator(BadClient()).recommend([retrieved()], DesignSpec(organism="Homo sapiens"))


def test_build_recommendation_generator_selects_gemini_and_rejects_unknown_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RECOMMENDER_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    generator = build_recommendation_generator()

    assert isinstance(generator, LLMRecommendationGenerator)
    assert isinstance(generator.client, GeminiRecommendationClient)

    monkeypatch.setenv("RECOMMENDER_PROVIDER", "bogus")
    with pytest.raises(ValueError, match="unsupported recommendation provider"):
        build_recommendation_generator()
