> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Gemini Intent Parsing and Recommendation Design

- Date: 2026-06-29
- Scope: Gemini-backed retrieval intent parsing and grounded recommendation generation.
- Status: implementation-ready design; no implementation changes are part of this task.
- Target model: `gemini-2.5-flash`.

## Decision

Add Gemini as an explicit, opt-in provider behind the existing `LLMIntentParser` and
`LLMRecommendationGenerator` abstractions. Keep `FakeIntentParser` and
`TemplateRecommendationGenerator` as the defaults. Use the current Google Gen AI
Python SDK, distributed as `google-genai` and imported with
`from google import genai`; do not add the legacy `google-generativeai` package.

Use the GA Interactions API through `client.interactions.create`, with stateless
requests (`store=False`) and structured output:

```python
interaction = client.interactions.create(
    model="gemini-2.5-flash",
    system_instruction=system_instruction,
    input=turns,
    response_format={
        "type": "text",
        "mime_type": "application/json",
        "schema": dict(schema),
    },
    generation_config={"temperature": 0},
    store=False,
)
raw_json = interaction.output_text
```

This preserves the repository's current split of responsibilities:

- Provider clients produce a JSON string constrained by the supplied schema.
- `LLMIntentParser` continues to decode, validate, normalize, and return
  `DesignSpec`.
- `LLMRecommendationGenerator` continues to decode and validate
  `PlasmidRecommendation` objects, then enforce record order, rank, score, and
  basic text grounding.
- No provider silently falls back to a fake/template implementation after an
  explicitly selected provider fails.

## SDK and API Finding

The requested `google-generativeai` package is no longer the supported choice for
new work. Google's library documentation marks it as a legacy Python library that
is not actively maintained. Google recommends the GA `google-genai` SDK and its
central `genai.Client`.

Compatibility implications:

- Add `google-genai>=2.3,<3` to `requirements.txt` during implementation.
  Interactions API support requires at least `2.3.0`; the upper bound follows this
  repository's existing major-version constraint style.
- Do not install both packages or import `google.generativeai`. Their public APIs
  differ: legacy `genai.configure` and `GenerativeModel` examples do not apply to
  `google-genai`.
- Use `from google import genai` and `from google.genai import errors, types`.
- The SDK automatically accepts either `GEMINI_API_KEY` or `GOOGLE_API_KEY`, with
  `GOOGLE_API_KEY` taking precedence. This integration should nevertheless read
  and pass `GOOGLE_API_KEY` explicitly because that is the application contract
  requested here. It must not accept an unrelated Google credential implicitly.
- The SDK uses Pydantic models internally and supports JSON Schema dictionaries.
  The repository already requires Pydantic 2, so no schema-model migration is
  needed.
- `gemini-2.5-flash` is a stable model ID and supports structured output. Do not
  substitute a `-latest` alias or a preview ID, because alias movement would make
  tests and production behavior less reproducible.

  **SUPERSEDED on the model ID, upheld on the reasoning.** `gemini-2.5-flash` now
  returns 404 for a newly issued API key, with the message that it is "no longer
  available to new users", which made the Gemini path unusable for a fresh setup.
  The pinned default is now `gemini-3.8-flash`, the replacement the API names in
  that error, verified end to end through `LLMIntentParser` against the real
  `STRICT_DESIGN_SPEC_SCHEMA`.

  The advice against a `-latest` alias stands and was followed: the new value is
  an exact version, not `gemini-flash-latest`. The lesson is narrower than "pin
  exact versions", which was right. It is that a model ID is not a constant, so a
  note asserting one is stable needs a date and a way to notice when it stops
  being true. Note also that listing the models a key may use still shows
  `gemini-2.5-flash`; appearing in that listing is not permission to call it.
- The Interactions API is GA and Google's recommended interface for new projects
  as of June 2026. The older `generateContent` API remains supported, but it is
  not the proposed integration surface.
- Interactions are stored by default. `store=False` is required here because
  parsing and recommendation are independent requests and should not create
  server-side conversation state or retention merely to perform one inference.

## Existing Contracts

`packages/retrieval/intent_parser.py` already has the correct provider-neutral
boundary:

```python
LLMCall = Callable[[list[dict[str, str]], Mapping[str, Any]], str]
```

`LLMIntentParser` owns prompt construction and the final
`DesignSpec.model_validate` plus controlled-vocabulary normalization. A Gemini
client therefore must implement `__call__(messages, schema) -> str`; it must not
return a `DesignSpec` or bypass existing normalization.

`packages/retrieval/recommender.py` similarly defines:

```python
class RecommendationLLMClient(Protocol):
    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Mapping[str, Any],
    ) -> str: ...
```

The Gemini recommender client must implement this protocol and leave all
post-response grounding checks in `LLMRecommendationGenerator`.

## Proposed Classes

Add the following internal shared adapter and two public provider adapters. They
may live in the existing retrieval modules to keep this change scoped; if shared
code is extracted, use `packages/retrieval/gemini_client.py` and keep only the two
protocol adapters in their current modules.

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass
class GeminiStructuredJSONClient:
    """Small injectable wrapper over the Google Interactions API."""

    client: Any
    model: str = "gemini-2.5-flash"

    @classmethod
    def from_env(cls, *, model_env: str) -> GeminiStructuredJSONClient:
        import os
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is required for Gemini structured output"
            )
        model = os.environ.get(model_env, "gemini-2.5-flash")
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=60_000),
        )
        return cls(client=client, model=model)

    def complete(
        self,
        *,
        system_instruction: str,
        turns: Sequence[Mapping[str, Any]],
        schema: Mapping[str, Any],
    ) -> str:
        from google.genai import errors

        try:
            interaction = self.client.interactions.create(
                model=self.model,
                system_instruction=system_instruction,
                input=list(turns),
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": dict(schema),
                },
                generation_config={"temperature": 0},
                store=False,
            )
        except errors.APIError as exc:
            raise RuntimeError(
                f"Gemini request failed with API status {exc.code}"
            ) from exc

        raw = interaction.output_text
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("Gemini returned an empty structured response")
        return raw
```

The timeout value is in milliseconds. The `client` field is constructor-injected
so unit tests can pass an in-memory fake without credentials or network access.
The Google import in `from_env` also ensures that importing and using the default
fake/template path does not initialize a provider client.

The intent adapter is:

```python
@dataclass
class GeminiIntentClient:
    backend: GeminiStructuredJSONClient

    @classmethod
    def from_env(cls) -> GeminiIntentClient:
        return cls(
            GeminiStructuredJSONClient.from_env(
                model_env="GEMINI_INTENT_MODEL",
            )
        )

    def __call__(
        self,
        messages: list[dict[str, str]],
        schema: Mapping[str, Any],
    ) -> str:
        system_parts = [
            message["content"] for message in messages
            if message["role"] == "system"
        ]
        turns = [
            {
                "role": "model" if message["role"] == "assistant"
                else message["role"],
                "content": message["content"],
            }
            for message in messages
            if message["role"] != "system"
        ]
        return self.backend.complete(
            system_instruction="\n\n".join(system_parts),
            turns=turns,
            schema=schema,
        )
```

Gemini uses `model`, not OpenAI's `assistant`, for model-authored few-shot turns.
The existing `FEW_SHOT_MESSAGES` therefore remain provider-neutral at the parser
layer and are translated only at this adapter boundary. Input turns use the
Interactions shape `{"role": "user"|"model", "content": <string>}`.

The recommendation adapter is:

```python
@dataclass
class GeminiRecommendationClient:
    backend: GeminiStructuredJSONClient

    @classmethod
    def from_env(cls) -> GeminiRecommendationClient:
        return cls(
            GeminiStructuredJSONClient.from_env(
                model_env="GEMINI_RECOMMENDER_MODEL",
            )
        )

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Mapping[str, Any],
    ) -> str:
        return self.backend.complete(
            system_instruction=system_prompt,
            turns=[{"role": "user", "content": user_prompt}],
            schema=schema,
        )
```

Both model override variables default to the required `gemini-2.5-flash`. Separate
variables allow independent rollback or evaluation without coupling intent and
recommendation behavior.

## Provider Selection

Provider names are explicit, case-insensitive values:

| Component | Environment variable | Default | Supported values |
| --- | --- | --- | --- |
| Intent parser | `INTENT_PARSER_PROVIDER` | `fake` | `fake`, `openai`, `gemini` |
| Recommender | `RECOMMENDER_PROVIDER` | `template` | `template`, `openai`, `gemini` |

Implement `build_intent_parser` with this precedence:

```python
def build_intent_parser(*, use_fake: bool | None = None) -> IntentParser:
    if use_fake is True:
        return FakeIntentParser()

    provider = os.environ.get("INTENT_PARSER_PROVIDER", "fake").casefold()
    if provider == "gemini":
        return LLMIntentParser(GeminiIntentClient.from_env())
    if use_fake is False or provider == "openai":
        return LLMIntentParser(OpenAIIntentClient.from_env())
    if provider == "fake":
        return FakeIntentParser()
    raise ValueError(f"unsupported INTENT_PARSER_PROVIDER: {provider}")
```

This preserves the existing compatibility behavior that the legacy
`use_fake=False` argument selects OpenAI when no explicit Gemini provider is
configured. `use_fake=True` remains an unconditional test override.

Implement `build_recommendation_generator` with this precedence:

```python
def build_recommendation_generator(
    *,
    use_llm: bool | None = None,
) -> RecommendationGenerator:
    provider = os.environ.get("RECOMMENDER_PROVIDER", "template").casefold()
    if provider == "gemini":
        return LLMRecommendationGenerator(
            GeminiRecommendationClient.from_env(),
            name="gemini-grounded-recommender-v1",
        )
    if use_llm is True or provider == "openai":
        return LLMRecommendationGenerator(OpenAIRecommendationClient.from_env())
    if provider == "template":
        return TemplateRecommendationGenerator()
    raise ValueError(f"unsupported RECOMMENDER_PROVIDER: {provider}")
```

This preserves `use_llm=True` as the legacy OpenAI shortcut while allowing an
explicit Gemini provider to take precedence. `use_llm=False` does not override an
explicit provider today and should continue not to do so.

Production Gemini activation is therefore:

```text
GOOGLE_API_KEY=<secret>
INTENT_PARSER_PROVIDER=gemini
RECOMMENDER_PROVIDER=gemini
```

Tests and local development need no provider variables and remain on
fake/template defaults.

## Structured Schema Behavior

Pass the existing `STRICT_DESIGN_SPEC_SCHEMA` and
`RECOMMENDATION_RESPONSE_SCHEMA` dictionaries unchanged to the Gemini backend.
The schemas use supported structured-output constructs: objects, arrays, strings,
numbers, booleans, null unions, required properties, and
`additionalProperties`.

Do not rely on structured output as application validation. Gemini guarantees the
response shape against its supported JSON Schema subset, but the existing Pydantic
models and deterministic normalization/grounding checks remain authoritative.
In particular:

- `LLMIntentParser` still rejects invalid JSON and invalid/extra `DesignSpec`
  fields and then calls `normalize_design_spec`.
- `LLMRecommendationGenerator` still rejects missing or malformed
  `recommendations`.
- `validate_recommendation_grounding` still rejects invented IDs, changed order,
  rank mismatches, score mismatches, and text that names neither the retrieved ID
  nor name.
- The model receives only `build_recommendation_context` output. No sequence data
  is added, and no tools or search grounding are enabled.

Before release, run one real structured-output smoke request for each schema.
Although both schemas fit Google's documented subset, this catches SDK-side schema
normalization changes, especially nested Pydantic-generated recommendation schema
metadata.

## Error Handling

Failure behavior must be deterministic and provider-specific:

| Failure | Behavior |
| --- | --- |
| Missing `GOOGLE_API_KEY` | Raise `RuntimeError` during explicit Gemini provider construction. |
| Unknown provider value | Raise `ValueError`; do not silently choose fake/template. |
| Google `errors.APIError` | Raise chained `RuntimeError` containing only the numeric API status, never the key, prompt, or response body. |
| Empty/missing `interaction.output_text` | Raise `ValueError("Gemini returned an empty structured response")`. |
| Invalid JSON | Existing parser/generator raises its current `ValueError`. |
| Schema-valid JSON that violates Pydantic/domain rules | Existing parser/generator raises its current validation `ValueError`. |
| Recommendation grounding violation | Existing `validate_recommendation_grounding` raises `ValueError`. |
| Timeout | Let the SDK surface an API/transport failure; do not switch providers. |
| Rate limit or transient 5xx | Surface the failure initially; add bounded retry only with metrics and an idempotency review. |
| Safety refusal/block | Treat missing structured text as a failed request, not as an empty successful result. |

Do not catch broad `Exception`, and do not include full prompts in exception
messages. Application-level fallback would make tests nondeterministic and could
hide production outages or provider-specific quality regressions.

Client lifecycle should follow the application's process lifecycle. A later
dependency-injection container may create one `genai.Client` and close it at
shutdown. Do not create and close a new HTTP client for every request once these
adapters are used in a long-running service.

## Test Plan

All normal tests must use injected fakes and must pass with no Google package
credentials and no network.

Add unit tests in `tests/retrieval/test_intent_parser.py`:

1. `test_gemini_intent_client_maps_system_and_few_shot_roles`
   - Inject a fake Interactions client.
   - Assert `assistant` becomes `model`, user order is preserved, and system text
     is sent via `system_instruction`.
2. `test_gemini_intent_client_requests_stateless_structured_json`
   - Assert model `gemini-2.5-flash`, `store=False`, temperature 0,
     `application/json`, and exact `STRICT_DESIGN_SPEC_SCHEMA`.
3. `test_gemini_intent_client_rejects_empty_output`.
4. `test_gemini_intent_from_env_requires_google_api_key`
   - Clear `GOOGLE_API_KEY`; do not instantiate a real SDK client.
5. `test_build_intent_parser_defaults_to_fake_without_google_credentials`.
6. `test_build_intent_parser_selects_gemini_explicitly`
   - Monkeypatch `GeminiIntentClient.from_env`; assert returned wrapper is
     `LLMIntentParser`.
7. `test_build_intent_parser_rejects_unknown_provider`.
8. Keep all existing fake, normalization, invalid-JSON, and OpenAI tests
   unchanged.

Add unit tests in `tests/retrieval/test_recommender.py`:

1. `test_gemini_recommendation_client_sends_grounding_prompt_and_schema`.
2. `test_gemini_recommendation_generator_preserves_grounding_validation`
   - Return an invented ID and assert the existing grounding failure.
3. `test_build_recommender_defaults_to_template_without_google_credentials`.
4. `test_build_recommender_selects_named_gemini_generator`
   - Assert name `gemini-grounded-recommender-v1`.
5. `test_build_recommender_rejects_unknown_provider`.
6. Keep all existing template and provider-neutral LLM tests unchanged.

Add focused backend tests, either in the two files above or
`tests/retrieval/test_gemini_client.py`:

1. `test_gemini_backend_returns_output_text`.
2. `test_gemini_backend_translates_api_error_without_leaking_payload`.
3. `test_gemini_backend_uses_intent_and_recommender_model_overrides`.
4. `test_default_fake_and_template_paths_never_construct_genai_client`.

Add opt-in live tests marked and skipped unless both conditions are true:

```python
RUN_REAL_GEMINI_TESTS == "1"
GOOGLE_API_KEY is present
```

The intent smoke test parses the existing E. coli/T7/His-GFP/kanamycin prompt and
asserts normalized core fields. The recommendation smoke test uses one synthetic
retrieved record and asserts one recommendation with the exact ID, rank, and
score. Live tests must never run in the default suite and should not assert exact
prose.

Verification commands for the implementation:

```text
python -m pytest tests/retrieval/test_intent_parser.py tests/retrieval/test_recommender.py
python -m pytest tests/retrieval/test_pipeline.py
```

Run live smoke tests separately only after explicitly setting the opt-in flag and
credential.

## Rollout and Acceptance

1. Land dependency, adapters, selection logic, and isolated tests while defaults
   remain fake/template.
2. Run one opt-in live test for each structured schema against
   `gemini-2.5-flash`.
3. Compare Gemini intent output on the existing retrieval-gold prompts against
   fake/OpenAI baselines, emphasizing clarification behavior and controlled
   vocabulary normalization.
4. Compare recommendation failures as well as prose quality; zero tolerance
   remains for ID/order/rank/score grounding violations.
5. Enable Gemini only through environment configuration in a non-production
   deployment first. Roll back by restoring provider variables to `fake`,
   `template`, or `openai`; no code rollback is required.

Acceptance requires:

- no network or credential lookup on default fake/template paths;
- no regression in the existing retrieval test suite;
- both live structured schemas accepted by the API;
- exact downstream Pydantic validation retained;
- exact recommendation grounding checks retained;
- no API key, prompt, or retrieved-record content in error messages.

## Official Sources

Reviewed 2026-06-29:

1. Google, "Interactions API": GA and recommended for new projects, stateless
   `store=false`, supported models including `gemini-2.5-flash`, and Python SDK
   minimum version:
   https://ai.google.dev/gemini-api/docs/interactions-overview
2. Google, "Structured outputs": Interactions API `response_format`, JSON MIME
   type, schema field, Pydantic support, and supported JSON Schema subset:
   https://ai.google.dev/gemini-api/docs/structured-output
3. Google, "Gemini Interactions API reference": `system_instruction`,
   `response_format`, `generation_config`, `store`, input turns, and
   `output_text`:
   https://ai.google.dev/api/interactions-api
4. Google, "Gemini 2.5 Flash": stable model ID and structured-output capability:
   https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash
5. Google, "Gemini API libraries": `google-genai` is the recommended GA Python
   library and `google-generativeai` is not actively maintained:
   https://ai.google.dev/gemini-api/docs/libraries
6. Google, "Migrate to the Google GenAI SDK": package/import/client differences
   between `google-generativeai` and `google-genai`:
   https://ai.google.dev/gemini-api/docs/migrate
7. Google Gen AI Python SDK documentation: environment-variable precedence,
   injectable `Client`, HTTP options, client lifecycle, and `errors.APIError`:
   https://googleapis.github.io/python-genai/
8. Official Google Gen AI Python SDK repository: installation, imports, current
   client API, and release history:
   https://github.com/googleapis/python-genai
