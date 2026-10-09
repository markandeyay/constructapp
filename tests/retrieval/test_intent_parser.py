from __future__ import annotations

import json
import os

import pytest

from packages.core.schemas import DesignSpec
from packages.retrieval.gemini_client import GeminiIntentClient
from packages.retrieval.intent_parser import (
    FakeIntentParser,
    LLMIntentParser,
    OpenAIIntentClient,
    build_intent_parser,
    parse_design_spec_heuristic,
)


def test_fake_intent_parser_normalizes_lentiviral_dox_hek293_and_tagged_gene() -> None:
    spec = FakeIntentParser().parse(
        "I need a lenti vector expressing GFP-tagged BRCA1 under a dox inducible promoter in 293 cells for live imaging."
    )

    assert spec.organism == "Homo sapiens"
    assert spec.cell_line == "HEK293"
    assert spec.vector_type == "lentiviral_or_retroviral_transfer_vector"
    assert spec.genes == ["BRCA1"]
    assert spec.tags == ["GFP"]
    assert spec.promoter_type == "doxycycline-inducible"
    assert spec.inducer == "doxycycline"
    assert spec.application == "live imaging"
    assert spec.clarification_needed is False


def test_fake_intent_parser_normalizes_hek293t_and_bacterial_expression_query() -> None:
    hek = FakeIntentParser().parse("Need a CMV GFP reporter in 293T cells with G418 selection.")
    bacterial = FakeIntentParser().parse("Need E coli T7 expression of His-tagged GFP with kan resistance.")

    assert hek.cell_line == "HEK293T"
    assert hek.organism == "Homo sapiens"
    assert hek.promoter_type == "CMV"
    assert hek.markers == ["neomycin/G418"]

    assert bacterial.organism == "Escherichia coli"
    assert bacterial.vector_type == "bacterial_expression_vector"
    assert bacterial.promoter_type == "T7"
    assert bacterial.genes == ["GFP"]
    assert bacterial.tags == ["His6"]
    assert bacterial.markers == ["kanamycin"]


def test_fake_intent_parser_extracts_retrieval_gold_style_queries() -> None:
    cloning = FakeIntentParser().parse("Recommend a low-copy bacterial cloning plasmid with chloramphenicol resistance.")
    yeast = FakeIntentParser().parse("I need a yeast centromere shuttle plasmid specifically selected by URA3 rather than LEU2.")
    puc = FakeIntentParser().parse("Recommend a high-copy ampicillin-resistant pUC plasmid when either MCS orientation is acceptable.")
    pbr = FakeIntentParser().parse(
        "Which curated cloning vector carries both ampicillin and tetracycline resistance with a pMB1-derived replication region?"
    )
    genbank = FakeIntentParser().parse("Find a GenBank source bacterial expression vector with DOI 10.1000/RICH and ampicillin resistance.")

    assert cloning.organism == "Escherichia coli"
    assert cloning.vector_type == "bacterial_cloning_vector"
    assert cloning.markers == ["chloramphenicol"]
    assert "low-copy" in cloning.constraints

    assert yeast.organism == "Saccharomyces cerevisiae"
    assert yeast.vector_type == "yeast_shuttle_vector"
    assert yeast.markers == ["URA3"]
    assert "exclude LEU2" in yeast.constraints
    assert yeast.application == "yeast transformation"
    assert puc.organism == "Escherichia coli"
    assert puc.markers == ["ampicillin"]
    assert pbr.clarification_needed is False
    assert pbr.source == "curated"
    assert pbr.markers == ["ampicillin", "tetracycline"]
    assert genbank.source == "genbank"
    assert genbank.publication_doi == "10.1000/rich"
    assert genbank.markers == ["ampicillin"]


def test_fake_intent_parser_does_not_treat_context_words_as_tagged_genes() -> None:
    spec = FakeIntentParser().parse("Which curated plasmid would you use for GST-tagged bacterial protein expression in E. coli?")

    assert spec.organism == "Escherichia coli"
    assert spec.vector_type == "bacterial_expression_vector"
    assert spec.tags == ["GST"]
    assert spec.genes == []


def test_fake_intent_parser_preserves_retrieval_identity_and_feature_constraints() -> None:
    parser = FakeIntentParser()

    prAS1 = parser.parse(
        "For a bacterial resistance-plasmid comparison, retrieve the Aeromonas salmonicida pRAS1_2402_89 plasmid carrying tetracycline resistance, sul1, and dfrA16."
    )
    pbluescript = parser.parse("I need a phagemid cloning vector with an f1 origin, lacZ alpha MCS, and T7/T3 promoter sites.")
    psb3 = parser.parse("For a yeast shuttle comparison, retrieve the Zygosaccharomyces rouxii pSB3 plasmid with an ARS region.")

    assert prAS1.organism == "Aeromonas salmonicida"
    assert prAS1.markers == ["tetracycline"]
    assert prAS1.constraints == ["pRAS1_2402_89", "sul1", "dfrA16"]

    assert pbluescript.organism == "Escherichia coli"
    assert pbluescript.vector_type == "bacterial_cloning_vector"
    assert pbluescript.promoter_type == "T7"
    assert pbluescript.constraints == ["phagemid", "f1 origin", "lacZ alpha MCS", "T3"]

    assert psb3.organism == "Zygosaccharomyces rouxii"
    assert psb3.vector_type == "yeast_shuttle_vector"
    assert psb3.constraints == ["pSB3", "ARS region"]


def test_fake_intent_parser_clarifies_missing_or_ambiguous_critical_fields() -> None:
    generic = FakeIntentParser().parse("Make me a plasmid to express my gene in mammalian cells.")
    viral = FakeIntentParser().parse("I want a viral vector with antibiotic resistance.")

    assert generic.clarification_needed is True
    assert generic.clarification_question is not None
    assert generic.organism == "unknown"

    assert viral.clarification_needed is True
    assert viral.clarification_question is not None
    assert "viral" in viral.clarification_question.casefold()


def test_fake_intent_parser_uses_canned_specs_and_clarification_answers() -> None:
    parser = FakeIntentParser(
        {
            "custom query": DesignSpec(
                organism="E. coli",
                vector_type="cloning vector",
                markers=["AmpR"],
            )
        }
    )

    canned = parser.parse("custom query")
    clarified = FakeIntentParser().parse("Need a reporter plasmid.", clarifications=["Use HEK293 cells and GFP."])

    assert canned.organism == "Escherichia coli"
    assert canned.vector_type == "bacterial_cloning_vector"
    assert canned.markers == ["ampicillin"]

    assert clarified.organism == "Homo sapiens"
    assert clarified.cell_line == "HEK293"
    assert clarified.genes == ["GFP"]


def test_llm_intent_parser_validates_and_post_normalizes_output() -> None:
    def fake_llm(_messages, _schema) -> str:
        return json.dumps(
            {
                "organism": "E. coli",
                "cell_line": None,
                "vector_type": "lenti",
                "genes": ["BRCA1"],
                "tags": ["gfp"],
                "promoter_type": "dox inducible",
                "inducer": "dox",
                "markers": ["puro"],
                "source": "GenBank",
                "publication_doi": "10.1000/XYZ",
                "application": "live imaging",
                "cloning_method": None,
                "constraints": [],
                "clarification_needed": False,
                "clarification_question": None,
            }
        )

    spec = LLMIntentParser(fake_llm).parse("ignored")

    assert spec.organism == "Escherichia coli"
    assert spec.vector_type == "lentiviral_or_retroviral_transfer_vector"
    assert spec.tags == ["GFP"]
    assert spec.promoter_type == "doxycycline-inducible"
    assert spec.inducer == "doxycycline"
    assert spec.markers == ["puromycin"]
    assert spec.source == "genbank"
    assert spec.publication_doi == "10.1000/xyz"


def test_llm_intent_parser_rejects_invalid_json_and_extra_keys() -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        LLMIntentParser(lambda _messages, _schema: "not json").parse("x")

    def extra_key(_messages, _schema) -> str:
        payload = {
            "organism": "Homo sapiens",
            "cell_line": None,
            "vector_type": None,
            "genes": [],
            "tags": [],
            "promoter_type": None,
            "inducer": None,
            "markers": [],
            "source": None,
            "publication_doi": None,
            "application": "expression",
            "cloning_method": None,
            "constraints": [],
            "clarification_needed": False,
            "clarification_question": None,
            "invented": True,
        }
        return json.dumps(payload)

    with pytest.raises(ValueError, match="invalid DesignSpec"):
        LLMIntentParser(extra_key).parse("x")


def test_build_intent_parser_selects_gemini_and_rejects_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTENT_PARSER_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    parser = build_intent_parser()

    assert isinstance(parser, LLMIntentParser)
    assert isinstance(parser._call_llm, GeminiIntentClient)

    monkeypatch.setenv("INTENT_PARSER_PROVIDER", "bogus")
    with pytest.raises(ValueError, match="unsupported intent parser provider"):
        build_intent_parser()


@pytest.mark.skipif(
    not (os.environ.get("RUN_REAL_LLM_INTENT_TESTS") == "1" and os.environ.get("OPENAI_API_KEY")),
    reason="real LLM intent parser test requires RUN_REAL_LLM_INTENT_TESTS=1 and OPENAI_API_KEY",
)
def test_openai_intent_client_smoke() -> None:
    parser = LLMIntentParser(OpenAIIntentClient.from_env())

    spec = parser.parse("Need E coli T7 expression of His-tagged GFP with kan resistance.")

    assert spec.organism == "Escherichia coli"
    assert spec.vector_type == "bacterial_expression_vector"


# ---------------------------------------------------------------------------
# WP-21 regressions. The 2026-10-09 retrieval eval on the expanded gold set
# found that all 16 natural-plasmid queries retrieved NOTHING: the parser
# short-circuited into a clarification question instead of searching. Neither
# defect was caught by the 1648-test suite, so both are pinned here.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("gene", ["tetA", "tetG", "tetL", "tetM"])
def test_tet_resistance_gene_is_a_marker_and_not_the_tet_expression_system(gene: str) -> None:
    """A tetracycline resistance gene must not be read as Tet-On/Tet-Off.

    The test was `"tet" in normalized_text`, a raw substring check, and `tetM`
    normalizes to `tetm`. Every tet resistance gene name asked the user to pick
    Tet-On or Tet-Off, and the query returned no results at all.
    """
    spec = parse_design_spec_heuristic(f"Which Lactiplantibacillus plantarum plasmid carries {gene}?")

    assert "tetracycline" in spec.markers
    assert spec.clarification_question != "Should the Tet-regulated design be Tet-On or Tet-Off?"
    assert not spec.clarification_needed


@pytest.mark.parametrize(
    "query",
    [
        "Is there a Staphylococcus epidermidis plasmid with an ethidium bromide resistance determinant?",
        "Which plasmid carries the CTX-M-17 extended-spectrum beta-lactamase?",
        "Find a Klebsiella plasmid with a complete arsenic resistance operon.",
        "I am looking for the Staphylococcus aureus conjugative multiresistance plasmid pSK41.",
        "Which plasmid carries a nickel and cobalt resistance gene cluster?",
    ],
)
def test_corpus_lookup_naming_a_non_model_organism_is_searched_not_questioned(query: str) -> None:
    """A lookup must search, even when its host is outside ORGANISM_TERMS.

    ORGANISM_TERMS covers nine model organisms. Any other named species parsed
    as NO organism, and the clarification branch then blocked retrieval, so a
    query naming both a species and a gene returned nothing. This covers roughly
    98 percent of the corpus.
    """
    spec = parse_design_spec_heuristic(query)

    assert not spec.clarification_needed
    assert spec.clarification_question is None


@pytest.mark.parametrize(
    ("query", "expected_question"),
    [
        (
            "Can you recommend a plasmid for my experiment?",
            "Which target organism or cell line should this plasmid design use?",
        ),
        (
            "I need a viral vector with antibiotic resistance.",
            "Which viral vector type should this use: lentiviral, retroviral, AAV, or another system?",
        ),
    ],
)
def test_genuinely_underspecified_requests_still_clarify(query: str, expected_question: str) -> None:
    """Non-vacuity guard for the two tests above.

    Both fixes widen the path to retrieval, so they could be satisfied by simply
    never clarifying. These two requests name no host, no application and no
    feature to search for, and must still be questioned rather than guessed at.
    """
    spec = parse_design_spec_heuristic(query)

    assert spec.clarification_needed
    assert spec.clarification_question == expected_question
