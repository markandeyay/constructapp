from __future__ import annotations

from dataclasses import dataclass

import pytest

from packages.core.schemas import (
    AnnotatedFeature,
    AnnotatedSequence,
    DesignSpec,
    Plasmid,
    PlasmidRecommendation,
    RetrievedPlasmid,
)
from packages.generation import FakeGenerator
from packages.generation.spike import (
    GenerationSpikePipeline,
    StubConstraintEngine,
    render_spike_result,
    requested_component_checks,
    spike_result_as_dict,
)
from packages.retrieval.intent_parser import FakeIntentParser


@dataclass
class FakeRetriever:
    retrieved: list[RetrievedPlasmid]

    def retrieve(self, spec: DesignSpec, k: int = 5) -> list[RetrievedPlasmid]:
        del spec
        return self.retrieved[:k]


@dataclass
class FakeReannotator:
    annotated: AnnotatedSequence

    def reannotate(self, generated, template) -> AnnotatedSequence:
        del generated, template
        return self.annotated


@dataclass
class StaticRecommender:
    recommendations: list[PlasmidRecommendation]
    calls: list[tuple[list[RetrievedPlasmid], DesignSpec]]

    def recommend(self, retrieved: list[RetrievedPlasmid], spec: DesignSpec) -> list[PlasmidRecommendation]:
        self.calls.append((retrieved, spec))
        return self.recommendations


def _template() -> RetrievedPlasmid:
    plasmid = Plasmid(
        id="curated:pUC19",
        source="curated",
        name="pUC19c",
        sequence="ACGT" * 100,
        length=400,
        organism="Cloning vector pUC19c",
        vector_type="bacterial_cloning_vector",
        markers=["AmpR"],
        promoters=["lac promoter region"],
        use_cases=["bacterial_cloning"],
        annotation_complete=True,
        raw_ref="raw/curated/pUC19.gb",
    )
    return RetrievedPlasmid(plasmid=plasmid, score=1.0, matched_fields=["semantic", "exact_name"])


def _annotated() -> AnnotatedSequence:
    return AnnotatedSequence(
        sequence="ACGT" * 100,
        topology="circular",
        vector_profile="bacterial_cloning_vector",
        annotation_complete=True,
        features=[
            AnnotatedFeature(type="marker", start=10, end=60, strand=1, name="AmpR/bla", confidence=0.95),
            AnnotatedFeature(type="promoter", start=70, end=100, strand=1, name="lac promoter region", confidence=0.95),
            AnnotatedFeature(type="MCS", start=110, end=150, strand=0, name="pUC19 MCS", confidence=0.90),
        ],
    )


def test_requested_component_checks_use_reannotated_features_and_profile() -> None:
    spec = DesignSpec(
        organism="Escherichia coli",
        vector_type="bacterial_cloning_vector",
        markers=["ampicillin"],
        promoter_type="lac/IPTG-inducible",
    )

    checks = requested_component_checks(spec, _annotated())

    assert [(check.kind, check.requested, check.matched) for check in checks] == [
        ("vector_type", "bacterial_cloning_vector", True),
        ("marker", "ampicillin", True),
        ("promoter", "lac/IPTG-inducible", True),
    ]


def test_generation_spike_pipeline_runs_end_to_end_with_fakes() -> None:
    spec = DesignSpec(
        organism="Escherichia coli",
        vector_type="bacterial_cloning_vector",
        markers=["ampicillin"],
        promoter_type="lac/IPTG-inducible",
    )
    pipeline = GenerationSpikePipeline(
        parser=FakeIntentParser({"puc request": spec}),
        retriever=FakeRetriever([_template()]),
        generator=FakeGenerator(),
        reannotator=FakeReannotator(_annotated()),
        constraint_engine=StubConstraintEngine(),
    )

    result = pipeline.run("puc request")

    assert result.passed is True
    assert result.template.plasmid.id == "curated:pUC19"
    assert [item.plasmid.id for item in result.retrieved_templates] == ["curated:pUC19"]
    assert result.recommendations == []
    assert result.generated.parent_template_ids == ["curated:pUC19"]
    assert result.reannotated_sequence.features[0].name == "AmpR/bla"
    assert result.validation_report.overall == "PASS"
    assert "full sequence" not in render_spike_result(result).casefold()
    assert spike_result_as_dict(result)["retrieved_templates"] == [
        {
            "source_id": "curated:pUC19",
            "name": "pUC19c",
            "score": 1.0,
            "source": "curated",
            "vector_profile": "bacterial_cloning_vector",
        }
    ]


def test_spike_result_dict_preserves_generated_sequence_spans() -> None:
    # Serialization is where provenance is most easily lost, because the dict form
    # is what crosses into the job queue and the API. Assert the spans arrive.
    spec = DesignSpec(organism="Escherichia coli", vector_type="bacterial_cloning_vector")
    pipeline = GenerationSpikePipeline(
        parser=FakeIntentParser({"span request": spec}),
        retriever=FakeRetriever([_template()]),
        generator=FakeGenerator(),
        reannotator=FakeReannotator(_annotated()),
        constraint_engine=StubConstraintEngine(),
    )

    serialized = spike_result_as_dict(pipeline.run("span request"))

    assert serialized["generated"]["sequence_spans"] == [
        {
            "start": 0,
            "end": 400,
            "source": "retrieved_template:curated:pUC19",
            "source_id": "curated:pUC19",
            "source_start": 0,
            "source_end": 400,
        }
    ]


def test_generation_spike_pipeline_optionally_generates_recommendations() -> None:
    spec = DesignSpec(organism="Escherichia coli", vector_type="bacterial_cloning_vector")
    template = _template()
    recommendations = [
        PlasmidRecommendation(
            plasmid_id=template.plasmid.id,
            rank=1,
            score=template.score,
            why_relevant="pUC19c is relevant because it matched the requested backbone.",
        )
    ]
    recommender = StaticRecommender(recommendations=recommendations, calls=[])
    pipeline = GenerationSpikePipeline(
        parser=FakeIntentParser({"recommended": spec}),
        retriever=FakeRetriever([template]),
        generator=FakeGenerator(),
        reannotator=FakeReannotator(_annotated()),
        constraint_engine=StubConstraintEngine(),
        recommendation_generator=recommender,
    )

    result = pipeline.run("recommended")

    assert result.recommendations == recommendations
    assert recommender.calls == [([template], spec)]


def test_generation_spike_pipeline_fails_on_clarification_or_missing_template() -> None:
    clarification = DesignSpec(
        organism="unknown",
        clarification_needed=True,
        clarification_question="Which organism?",
    )
    pipeline = GenerationSpikePipeline(
        parser=FakeIntentParser({"ambiguous": clarification}),
        retriever=FakeRetriever([]),
        generator=FakeGenerator(),
        reannotator=FakeReannotator(_annotated()),
        constraint_engine=StubConstraintEngine(),
    )

    with pytest.raises(ValueError, match="clarification"):
        pipeline.run("ambiguous")

    no_template = GenerationSpikePipeline(
        parser=FakeIntentParser({"missing": DesignSpec(organism="Escherichia coli", vector_type="bacterial_cloning_vector")}),
        retriever=FakeRetriever([]),
        generator=FakeGenerator(),
        reannotator=FakeReannotator(_annotated()),
        constraint_engine=StubConstraintEngine(),
    )
    with pytest.raises(ValueError, match="no templates"):
        no_template.run("missing")
