from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, Sequence

import requests
from pydantic import ValidationError

from packages.core.schemas import DesignSpec
from packages.retrieval.gemini_client import GeminiIntentClient, GeminiJsonClient
from packages.core.vocabularies import (
    CELL_LINE_TERMS,
    INDUCER_TERMS,
    MARKER_TERMS,
    ORGANISM_TERMS,
    PROMOTER_TYPE_TERMS,
    TAG_TERMS,
    UNKNOWN_ORGANISM,
    VECTOR_TYPE_TERMS,
    dedupe_preserve_order,
    find_controlled_terms,
    infer_organism_from_cell_line,
    normalize_many_to_controlled,
    normalize_text,
    normalize_to_controlled,
)


STRICT_DESIGN_SPEC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "organism",
        "cell_line",
        "vector_type",
        "genes",
        "tags",
        "promoter_type",
        "inducer",
        "markers",
        "source",
        "publication_doi",
        "application",
        "cloning_method",
        "constraints",
        "clarification_needed",
        "clarification_question",
    ],
    "properties": {
        "organism": {"type": "string"},
        "cell_line": {"type": ["string", "null"]},
        "vector_type": {"type": ["string", "null"]},
        "genes": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "promoter_type": {"type": ["string", "null"]},
        "inducer": {"type": ["string", "null"]},
        "markers": {"type": "array", "items": {"type": "string"}},
        "source": {"type": ["string", "null"]},
        "publication_doi": {"type": ["string", "null"]},
        "application": {"type": ["string", "null"]},
        "cloning_method": {"type": ["string", "null"]},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "clarification_needed": {"type": "boolean"},
        "clarification_question": {"type": ["string", "null"]},
    },
}


SYSTEM_PROMPT = """You extract plasmid design intent from natural language into strict JSON matching DesignSpec.
Return JSON only. Do not include markdown.
Normalize colloquial biology terms to the provided controlled vocabulary.
Ask one clarifying question instead of guessing when a critical field is missing or ambiguous.
Critical field: organism must be known unless clarification_needed is true.
Do not invent genes, cell lines, promoters, markers, or vector types not implied by the text."""


CONTROLLED_VOCABULARY_PROMPT = """
Controlled vocabulary examples:
- 293 cells -> HEK293; 293T -> HEK293T.
- lenti/lentivirus -> lentiviral_or_retroviral_transfer_vector.
- dox/Tet-On/TRE -> promoter_type doxycycline-inducible and inducer doxycycline.
- E. coli -> Escherichia coli.
- AmpR/bla -> ampicillin; KanR -> kanamycin; G418/NeoR in mammalian context -> neomycin/G418.
- reporter/luciferase/GFP reporter -> mammalian_reporter_vector when the host context is mammalian.
"""


FEW_SHOT_MESSAGES: list[dict[str, str]] = [
    {
        "role": "user",
        "content": "I need a lentiviral vector expressing GFP-tagged BRCA1 under a dox inducible promoter in 293 cells for live imaging.",
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "organism": "Homo sapiens",
                "cell_line": "HEK293",
                "vector_type": "lentiviral_or_retroviral_transfer_vector",
                "genes": ["BRCA1"],
                "tags": ["GFP"],
                "promoter_type": "doxycycline-inducible",
                "inducer": "doxycycline",
                "markers": [],
                "source": None,
                "publication_doi": None,
                "application": "live imaging",
                "cloning_method": None,
                "constraints": [],
                "clarification_needed": False,
                "clarification_question": None,
            }
        ),
    },
    {
        "role": "user",
        "content": "Make me a plasmid to express my gene in mammalian cells.",
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "organism": UNKNOWN_ORGANISM,
                "cell_line": None,
                "vector_type": "mammalian_expression_vector",
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
                "clarification_needed": True,
                "clarification_question": "Which organism or cell line should this mammalian expression plasmid target, and what gene should it express?",
            }
        ),
    },
    {
        "role": "user",
        "content": "Need E coli T7 expression of His-tagged GFP with kan resistance.",
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "organism": "Escherichia coli",
                "cell_line": None,
                "vector_type": "bacterial_expression_vector",
                "genes": ["GFP"],
                "tags": ["His6"],
                "promoter_type": "T7",
                "inducer": None,
                "markers": ["kanamycin"],
                "source": None,
                "publication_doi": None,
                "application": "protein expression",
                "cloning_method": None,
                "constraints": [],
                "clarification_needed": False,
                "clarification_question": None,
            }
        ),
    },
    {
        "role": "user",
        "content": "For a bacterial resistance-plasmid comparison, retrieve the Aeromonas salmonicida pRAS1_2402_89 plasmid carrying tetracycline resistance, sul1, and dfrA16.",
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "organism": "Aeromonas salmonicida",
                "cell_line": None,
                "vector_type": None,
                "genes": [],
                "tags": [],
                "promoter_type": None,
                "inducer": None,
                "markers": ["tetracycline"],
                "source": "genbank",
                "publication_doi": None,
                "application": None,
                "cloning_method": None,
                "constraints": ["pRAS1_2402_89", "sul1", "dfrA16"],
                "clarification_needed": False,
                "clarification_question": None,
            }
        ),
    },
    {
        "role": "user",
        "content": "I need a phagemid cloning vector with an f1 origin, lacZ alpha MCS, and T7/T3 promoter sites.",
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "organism": "Escherichia coli",
                "cell_line": None,
                "vector_type": "bacterial_cloning_vector",
                "genes": [],
                "tags": [],
                "promoter_type": "T7",
                "inducer": None,
                "markers": [],
                "source": "curated",
                "publication_doi": None,
                "application": "cloning",
                "cloning_method": None,
                "constraints": ["phagemid", "f1 origin", "lacZ alpha MCS", "T3"],
                "clarification_needed": False,
                "clarification_question": None,
            }
        ),
    },
]


class IntentParser(Protocol):
    def parse(self, free_text: str, clarifications: list[str] | None = None) -> DesignSpec: ...


LLMCall = Callable[[list[dict[str, str]], Mapping[str, Any]], str]


@dataclass(frozen=True)
class FakeIntentParser:
    canned: Mapping[str, DesignSpec | Mapping[str, Any]] = field(default_factory=dict)

    def parse(self, free_text: str, clarifications: list[str] | None = None) -> DesignSpec:
        key = free_text.strip()
        if key in self.canned:
            value = self.canned[key]
            spec = value if isinstance(value, DesignSpec) else DesignSpec.model_validate(value)
            return normalize_design_spec(spec, source_text=_combine_text(free_text, clarifications))
        return parse_design_spec_heuristic(free_text, clarifications=clarifications)


class LLMIntentParser:
    def __init__(self, call_llm: LLMCall) -> None:
        self._call_llm = call_llm

    def parse(self, free_text: str, clarifications: list[str] | None = None) -> DesignSpec:
        prompt = _combine_text(free_text, clarifications)
        messages = [
            {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{CONTROLLED_VOCABULARY_PROMPT}"},
            *FEW_SHOT_MESSAGES,
            {"role": "user", "content": prompt},
        ]
        raw = self._call_llm(messages, STRICT_DESIGN_SPEC_SCHEMA)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("intent parser LLM returned invalid JSON") from exc
        if isinstance(payload, dict):
            payload["source"] = _normalize_source(payload.get("source"))
            payload["publication_doi"] = _normalize_publication_doi(payload.get("publication_doi"))
        try:
            spec = DesignSpec.model_validate(payload)
        except ValidationError as exc:
            raise ValueError("intent parser LLM returned invalid DesignSpec") from exc
        return normalize_design_spec(spec, source_text=prompt)


@dataclass(frozen=True)
class OpenAIIntentClient:
    api_key: str
    model: str = "gpt-4o-mini"
    endpoint: str = "https://api.openai.com/v1/chat/completions"
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> OpenAIIntentClient:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAIIntentClient")
        return cls(api_key=api_key, model=os.environ.get("OPENAI_INTENT_MODEL", cls.model))

    def __call__(self, messages: list[dict[str, str]], schema: Mapping[str, Any]) -> str:
        response = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": messages,
                "temperature": 0,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "DesignSpec", "strict": True, "schema": schema},
                },
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload["choices"][0]["message"]["content"])


def build_intent_parser(*, use_fake: bool | None = None) -> IntentParser:
    if use_fake is True:
        return FakeIntentParser()
    provider = _intent_parser_provider()
    if use_fake is False and provider == "fake":
        provider = "openai"
    if provider == "fake":
        return FakeIntentParser()
    if provider == "openai":
        return LLMIntentParser(OpenAIIntentClient.from_env())
    if provider == "gemini":
        return LLMIntentParser(GeminiIntentClient(GeminiJsonClient.from_env()))
    raise ValueError(f"unsupported intent parser provider: {provider}")


def _intent_parser_provider() -> str:
    provider = os.environ.get("INTENT_PARSER_PROVIDER", "fake").strip().casefold()
    if provider not in {"fake", "openai", "gemini"}:
        raise ValueError(f"unsupported intent parser provider: {provider}")
    return provider


def parse_design_spec_heuristic(free_text: str, clarifications: list[str] | None = None) -> DesignSpec:
    text = _combine_text(free_text, clarifications)
    normalized = normalize_text(text)

    cell_line = _first(find_controlled_terms(text, CELL_LINE_TERMS))
    organism = _first(find_controlled_terms(text, ORGANISM_TERMS)) or infer_organism_from_cell_line(cell_line)
    vector_type = _first(find_controlled_terms(text, VECTOR_TYPE_TERMS))
    promoter_type = _first(find_controlled_terms(text, PROMOTER_TYPE_TERMS))
    inducer = _first(find_controlled_terms(text, INDUCER_TERMS))
    markers = find_controlled_terms(text, MARKER_TERMS)
    source = _extract_source(text)
    publication_doi = _extract_publication_doi(text)
    tags = find_controlled_terms(text, TAG_TERMS)
    genes, tags = _extract_genes_and_tags(text, tags)
    application = _extract_application(normalized, vector_type)
    cloning_method = _extract_cloning_method(normalized)
    constraints = _extract_constraints(text)
    excluded_markers = _extract_excluded_markers(text)
    if excluded_markers:
        markers = [marker for marker in markers if marker not in excluded_markers]
        constraints.extend(f"exclude {marker}" for marker in excluded_markers)

    if promoter_type == "doxycycline-inducible" and inducer is None:
        inducer = "doxycycline"
    if inducer == "doxycycline" and promoter_type is None:
        promoter_type = "doxycycline-inducible"

    clarification_question = _clarification_question(
        normalized,
        organism=organism,
        cell_line=cell_line,
        vector_type=vector_type,
        genes=genes,
        application=application,
        promoter_type=promoter_type,
        markers=markers,
    )
    clarification_needed = clarification_question is not None
    if organism is None:
        organism = UNKNOWN_ORGANISM if clarification_needed else _infer_organism_from_vector_type(vector_type)
    elif clarification_needed and cell_line is None and "mammalian cells" in normalized:
        organism = UNKNOWN_ORGANISM

    spec = DesignSpec(
        organism=organism,
        cell_line=cell_line,
        vector_type=vector_type,
        genes=genes,
        tags=tags,
        promoter_type=promoter_type,
        inducer=inducer,
        markers=markers,
        source=source,
        publication_doi=publication_doi,
        application=application,
        cloning_method=cloning_method,
        constraints=constraints,
        clarification_needed=clarification_needed,
        clarification_question=clarification_question,
    )
    return normalize_design_spec(spec, source_text=text)


def normalize_design_spec(spec: DesignSpec, *, source_text: str = "") -> DesignSpec:
    cell_line = normalize_to_controlled(spec.cell_line, CELL_LINE_TERMS)
    organism = normalize_to_controlled(spec.organism, ORGANISM_TERMS) or spec.organism
    if organism == UNKNOWN_ORGANISM and cell_line is not None:
        organism = infer_organism_from_cell_line(cell_line) or organism
    vector_type = normalize_to_controlled(spec.vector_type, VECTOR_TYPE_TERMS)
    promoter_type = normalize_to_controlled(spec.promoter_type, PROMOTER_TYPE_TERMS)
    inducer = normalize_to_controlled(spec.inducer, INDUCER_TERMS)
    markers = normalize_many_to_controlled(spec.markers, MARKER_TERMS)
    source = _normalize_source(spec.source)
    tags = normalize_many_to_controlled(spec.tags, TAG_TERMS)
    genes = _normalize_genes(spec.genes)
    publication_doi = _normalize_publication_doi(spec.publication_doi)

    if promoter_type == "doxycycline-inducible" and inducer is None:
        inducer = "doxycycline"
    if inducer == "doxycycline" and promoter_type is None:
        promoter_type = "doxycycline-inducible"

    clarification_question = spec.clarification_question
    clarification_needed = spec.clarification_needed
    if not clarification_needed:
        question = _clarification_question(
            normalize_text(source_text),
            organism=None if organism == UNKNOWN_ORGANISM else organism,
            cell_line=cell_line,
            vector_type=vector_type,
            genes=genes,
            application=spec.application,
            promoter_type=promoter_type,
            markers=markers,
        )
        if question is not None:
            clarification_needed = True
            clarification_question = question
            if organism is None:
                organism = UNKNOWN_ORGANISM

    if clarification_needed and not clarification_question:
        clarification_question = "Which target organism or cell line should this plasmid design use?"
    if organism is None:
        organism = UNKNOWN_ORGANISM if clarification_needed else _infer_organism_from_vector_type(vector_type)

    return DesignSpec(
        organism=organism,
        cell_line=cell_line,
        vector_type=vector_type,
        genes=genes,
        tags=tags,
        promoter_type=promoter_type,
        inducer=inducer,
        markers=markers,
        source=source,
        publication_doi=publication_doi,
        application=spec.application,
        cloning_method=spec.cloning_method,
        constraints=dedupe_preserve_order(spec.constraints),
        clarification_needed=clarification_needed,
        clarification_question=clarification_question,
    )


def _combine_text(free_text: str, clarifications: list[str] | None) -> str:
    additions = [item.strip() for item in clarifications or [] if item.strip()]
    if not additions:
        return free_text.strip()
    return f"{free_text.strip()} Clarifications: {' '.join(additions)}"


def _first(values: Sequence[str]) -> str | None:
    return values[0] if values else None


def _extract_genes_and_tags(text: str, seed_tags: list[str]) -> tuple[list[str], list[str]]:
    genes: list[str] = []
    tags = list(seed_tags)
    tagged_patterns = (
        r"\b(?P<tag>gfp|egfp|mcherry|flag|ha|myc|his6?|gst|mbp|v5)[-\s]?tagged\s+(?P<gene>[A-Za-z][A-Za-z0-9-]{1,})\b",
        r"\b(?P<gene>[A-Za-z][A-Za-z0-9-]{1,})[-\s]?tagged\s+with\s+(?P<tag>gfp|egfp|mcherry|flag|ha|myc|his6?|gst|mbp|v5)\b",
    )
    for pattern in tagged_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            genes.append(match.group("gene"))
            tags.append(match.group("tag"))

    for pattern in (
        r"\bexpress(?:ing|ion of)?\s+(?P<gene>[A-Za-z][A-Za-z0-9-]{1,})\b",
        r"\b(?P<gene>luciferase|luc2|gfp|egfp)\s+reporter\b",
    ):
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            gene = match.group("gene")
            if normalize_text(gene) not in {"my", "gene", "protein"}:
                genes.append(gene)

    normalized_tags = normalize_many_to_controlled(tags, TAG_TERMS)
    normalized_genes = _normalize_genes(genes)
    if not normalized_genes and any(tag in {"GFP", "EGFP", "mCherry"} for tag in normalized_tags):
        normalized_genes = [tag for tag in normalized_tags if tag in {"GFP", "EGFP", "mCherry"}]
    gene_keys = {normalize_text(gene) for gene in normalized_genes}
    normalized_tags = [tag for tag in normalized_tags if normalize_text(tag) not in gene_keys]
    return normalized_genes, normalized_tags


def _normalize_genes(genes: list[str]) -> list[str]:
    cleaned: list[str] = []
    for gene in genes:
        value = gene.strip().strip(".,;:()[]{}")
        if not value or normalize_text(value) in {
            "my",
            "gene",
            "protein",
            "vector",
            "plasmid",
            "bacterial",
            "mammalian",
            "yeast",
            "curated",
            "expression",
            "cloning",
        }:
            continue
        if "tagged" in normalize_text(value):
            continue
        normalized = normalize_to_controlled(value, TAG_TERMS) if normalize_text(value) in {"gfp", "egfp"} else None
        if normalized is not None:
            cleaned.append(normalized)
        elif value.isupper() or any(char.isdigit() for char in value):
            cleaned.append(value.upper())
        else:
            cleaned.append(value)
    return dedupe_preserve_order(cleaned)


def _extract_application(normalized_text: str, vector_type: str | None) -> str | None:
    if "live imaging" in normalized_text or "live cell imaging" in normalized_text:
        return "live imaging"
    if "reporter assay" in normalized_text or "luciferase" in normalized_text:
        return "reporter assay"
    if "gfp based expression analysis" in normalized_text or "fluorescent" in normalized_text:
        return "fluorescent reporting"
    if "protein expression" in normalized_text or "gst fusion" in normalized_text:
        return "protein expression"
    if "yeast transformation" in normalized_text or "yeast" in normalized_text:
        return "yeast transformation"
    if "cloning" in normalized_text or vector_type == "bacterial_cloning_vector":
        return "cloning"
    if "expression" in normalized_text:
        return "expression"
    if vector_type == "mammalian_reporter_vector":
        return "reporter assay"
    return None


def _extract_cloning_method(normalized_text: str) -> str | None:
    if "gibson" in normalized_text:
        return "Gibson"
    if "golden gate" in normalized_text:
        return "Golden Gate"
    if "restriction" in normalized_text:
        return "restriction cloning"
    return None


def _extract_constraints(text: str) -> list[str]:
    normalized = normalize_text(text)
    constraints: list[str] = []
    if "high copy" in normalized:
        constraints.append("high-copy")
    if "low copy" in normalized:
        constraints.append("low-copy")
    for match in re.finditer(r"\bavoid\s+([A-Za-z0-9-]+)\b", text, flags=re.IGNORECASE):
        constraints.append(f"avoid {match.group(1)}")
    if any(term in normalized for term in ("toxin", "pathogen", "select agent", "gene therapy")):
        constraints.append("biosecurity_review_required")
    constraints.extend(_extract_retrieval_keywords(text, normalized))
    return dedupe_preserve_order(constraints)


def _extract_retrieval_keywords(text: str, normalized_text: str) -> list[str]:
    constraints: list[str] = []
    for match in re.finditer(r"\bp[A-Za-z0-9][A-Za-z0-9_.+-]{1,}\b", text):
        value = match.group(0)
        if normalize_text(value) not in {"plasmid", "promoter"}:
            constraints.append(value)
    phrase_constraints = [("phagemid", "phagemid"), ("f1 origin", "f1 origin"), ("ars region", "ARS region")]
    if "lacz alpha mcs" in normalized_text:
        phrase_constraints.append(("lacz alpha mcs", "lacZ alpha MCS"))
    elif "lacz alpha" in normalized_text:
        phrase_constraints.append(("lacz alpha", "lacZ alpha"))
    for needle, label in phrase_constraints:
        if needle in normalized_text:
            constraints.append(label)
    if "t7 t3" in normalized_text or "t7/t3" in text.casefold():
        constraints.append("T3")
    elif re.search(r"\bt3\b", text, flags=re.IGNORECASE):
        constraints.append("T3")
    for match in re.finditer(r"\b(?:sul\d+[a-z]?|dfr[a-z]*\d+[a-z]?)\b", text, flags=re.IGNORECASE):
        constraints.append(match.group(0))
    return constraints


def _extract_excluded_markers(text: str) -> list[str]:
    excluded: list[str] = []
    for match in re.finditer(r"\b(?:rather than|instead of|not)\s+([A-Za-z0-9/+-]+)\b", text, flags=re.IGNORECASE):
        marker = normalize_to_controlled(match.group(1), MARKER_TERMS)
        if marker is not None:
            excluded.append(marker)
    return dedupe_preserve_order(excluded)


def _extract_source(text: str) -> str | None:
    normalized = normalize_text(text)
    source_patterns = (
        ("curated", ("curated vector", "curated plasmid", "curated source", "which curated", "recommend a curated")),
        ("genbank", ("genbank vector", "genbank plasmid", "genbank source", "from genbank", "genbank backbone")),
        ("addgene", ("addgene vector", "addgene plasmid", "from addgene", "addgene source")),
    )
    for source, phrases in source_patterns:
        if any(phrase in normalized for phrase in phrases):
            return source
    return None


def _extract_publication_doi(text: str) -> str | None:
    match = re.search(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b", text, flags=re.IGNORECASE)
    if match is None:
        return None
    return match.group(1)


def _normalize_source(source: str | None) -> str | None:
    if source is None:
        return None
    value = normalize_text(source)
    if "curated" in value:
        return "curated"
    if "genbank" in value or "ncbi" in value:
        return "genbank"
    if "addgene" in value:
        return "addgene"
    if "literature" in value:
        return "literature"
    if "generated" in value:
        return "generated"
    return source


def _normalize_publication_doi(doi: str | None) -> str | None:
    if doi is None:
        return None
    value = doi.strip()
    return value.lower() or None


#: Whole-word forms that actually denote the tetracycline-controlled expression
#: system. The previous test was `"tet" in normalized_text`, a raw substring
#: check, so every tetracycline resistance gene name (tetA, tetG, tetL, tetM) and
#: the word "tetracycline" itself asked the user to choose Tet-On or Tet-Off. A
#: resistance gene is not an inducible promoter system.
#:
#: OPEN QUESTION, left for a human: with this narrowed, the clarification below
#: may be unreachable. A whole-word "tet" also matches the tetracycline entry in
#: MARKER_TERMS, and "tet on"/"tet off"/"tre" set promoter_type through
#: PROMOTER_TYPE_TERMS; the clarification is guarded against both. In the
#: 2026-10-09 retrieval eval the only two queries that reached it were the tetM
#: and tetL false positives, so the bug may have been its only live path. It is
#: kept rather than deleted because removing a clarification branch is a
#: behaviour change that should be made against a test run, and no test asserts
#: this question is ever produced.
TET_SYSTEM_PHRASES: tuple[str, ...] = ("tet", "tet on", "tet off", "teton", "tetoff", "tre", "tet regulated")


def _mentions_tet_system(normalized_text: str) -> bool:
    """True when the text names the Tet expression system, not a tet marker.

    Matching is whole-word against already-normalized text, so "tetm" and
    "tetracycline" do not match while "tet" and "tet on" do.
    """
    padded = f" {normalized_text} "
    return any(f" {phrase} " in padded for phrase in TET_SYSTEM_PHRASES)


#: Openings that make a request a corpus lookup rather than a design request.
#: A lookup names something to search for and does not need a host organism: a
#: retrieval system asked which plasmid carries a gene should search for it, not
#: ask the user what cell line they had in mind.
#:
#: These are matched as PREFIXES, not as substrings anywhere in the text. An
#: earlier version of this list used phrases like "which plasmid" and matched
#: them with `in`, which failed on exactly the queries it was written for: in
#: "Which Lactiplantibacillus plantarum plasmid carries tetM?" the species name
#: sits between the two words, so the phrase never appears contiguously.
LOOKUP_OPENINGS: tuple[str, ...] = (
    "which",
    "is there",
    "are there",
    "find",
    "show me",
    "do you have",
    "i am looking for",
    "looking for",
    "can you pull",
    "retrieve",
    "list",
)

#: Phrases that mark a lookup wherever they appear, because they refer to the
#: corpus itself rather than to a construct the user wants built.
LOOKUP_PHRASES: tuple[str, ...] = ("in the collection", "in the corpus")


def _is_corpus_lookup(normalized_text: str) -> bool:
    if any(phrase in normalized_text for phrase in LOOKUP_PHRASES):
        return True
    return any(
        normalized_text == opening or normalized_text.startswith(f"{opening} ")
        for opening in LOOKUP_OPENINGS
    )


def _clarification_question(
    normalized_text: str,
    *,
    organism: str | None,
    cell_line: str | None,
    vector_type: str | None,
    genes: list[str],
    application: str | None,
    promoter_type: str | None,
    markers: list[str],
) -> str | None:
    if "viral vector" in normalized_text and vector_type is None:
        return "Which viral vector type should this use: lentiviral, retroviral, AAV, or another system?"
    if "antibiotic resistance" in normalized_text and not markers:
        return "Which selectable marker or antibiotic resistance should the plasmid carry?"
    if "inducible" in normalized_text and promoter_type is None:
        return "Which inducible promoter system should be used, such as doxycycline/Tet-On, IPTG/lac, or arabinose/pBAD?"
    if (
        _mentions_tet_system(normalized_text)
        and "tetracycline resistance" not in normalized_text
        and "tetracycline" not in markers
        and promoter_type not in {"doxycycline-inducible", "Tet-off"}
    ):
        return "Should the Tet-regulated design be Tet-On or Tet-Off?"
    # A corpus lookup is a request to search, not a request to design, so none of
    # the rules below apply to it. Every one of them asks the user to supply
    # something a DESIGN needs: a host organism, a vector type, a payload gene. A
    # lookup has already named what it wants, and most of what it names is
    # outside the controlled vocabularies ("ethidium bromide resistance
    # determinant", "nickel/cobalt resistance gene cluster"), which is exactly
    # what semantic retrieval is for. Answering these with a question returned
    # nothing at all for 16 of 16 natural-plasmid queries in the 2026-10-09 eval.
    #
    # The specific rules above this line still apply, because each one catches a
    # request that names a system without saying which variant of it, and that
    # ambiguity is real whether the user is designing or searching.
    if _is_corpus_lookup(normalized_text):
        return None
    if organism is None and cell_line is None:
        if vector_type in {"bacterial_cloning_vector", "bacterial_expression_vector", "yeast_shuttle_vector"}:
            return None
        if "mammalian" in normalized_text and (vector_type or application or genes):
            return None
        # Reached only by design requests now, since lookups returned above. A
        # design request with no host and no bacterial or yeast vector type
        # genuinely cannot proceed, so this question stands.
        #
        # Enumerating more species in ORGANISM_TERMS is NOT the fix for the
        # natural-plasmid misses: that is what produced the two ad-hoc entries
        # already sitting in that tuple, and it generalizes no further than the
        # one gold case that prompted each.
        return "Which target organism or cell line should this plasmid design use?"
    if not any([vector_type, genes, application, promoter_type, markers, cell_line]):
        return "What plasmid purpose, vector type, payload gene, marker, or application should retrieval target?"
    if "mammalian cells" in normalized_text and not cell_line and not any([genes, application, vector_type]):
        return "Which mammalian cell line should this design target?"
    if "my gene" in normalized_text and not genes:
        return "What gene or payload should the plasmid express?"
    return None


def _infer_organism_from_vector_type(vector_type: str | None) -> str:
    if vector_type in {"bacterial_cloning_vector", "bacterial_expression_vector", "general_shuttle_vector"}:
        return "Escherichia coli"
    if vector_type == "yeast_shuttle_vector":
        return "Saccharomyces cerevisiae"
    return "Homo sapiens"
