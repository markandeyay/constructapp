> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Phase 2 Generation Evaluation Harness

## Summary

This document specifies the Phase 2 generation evaluation harness for EVAL-2. The target is an offline, end-to-end harness against `FakeGenerator`, which deterministically returns the top retrieved template verbatim, then reports baseline generation metrics under `data/eval/generation/` as Markdown and JSON.

The harness implements `SYSTEM_DESIGN.md` Section 7.6: syntactic DNA validity, requested-component recovery after Phase 0 re-annotation, Phase 3 constraint pass/fail when available, and novelty against training examples. It must stay behind existing interfaces and must not touch frontend, API, or worker code.

Implementation can proceed with conservative assumptions. There are no blocking biology questions for the fake-backed evaluation harness because it can treat validity as a deliberately narrow offline metric, not a synthesis-ready or wet-lab-validity claim.

Relevant project references:

- `SYSTEM_DESIGN.md` Sections 3.3 and 7.6 define the Phase 2 generation metrics and `>= 70%` gate.
- `SYSTEM_DESIGN.md` Sections 5.3 and 12.3 define Phase 0 parser/re-annotation output as `AnnotatedSequence`.
- `SYSTEM_DESIGN.md` Sections 8.1, 8.2, and 12.5 define the future `ConstraintEngine` and `ValidationReport` contract.
- `SYSTEM_DESIGN.md` Section 14 requires fake-backed pipeline tests and `make eval-generation` reports under `data/eval/`.
- `research/findings/phase2_readiness.md` recommends provisional evaluation fields: DNA validity, requested-component recovery, circular rotation robustness, exact-copy/identity reporting, provenance, unsupported-profile handling, and clear non-gate labeling.
- `research/findings/phase2_spike_spec.md` defines the authorized fake-backed plumbing path and warns that `FakeGenerator` results are not biological-quality evidence.
- `packages/generation/generator.py` provides `SequenceGenerator`, `FakeGenerator`, `MarkerSwap`, and `fake-template-generator-v1`.
- `packages/generation/spike.py` already provides `ConstraintEngine` and `Reannotator` protocols, `StubConstraintEngine`, `GenerationSpikePipeline`, `requested_component_checks`, `spike_result_as_dict`, and Markdown rendering patterns.
- `packages/core/schemas/models.py` defines `DNA_ALPHABET`, `normalize_dna`, `DesignSpec`, `AnnotatedSequence`, `GeneratedSequence`, and `ValidationReport`.
- `data/eval/generation/2026-06-01-181237-generation-spike-report.md` is the existing one-off spike report that the harness should generalize into a repeatable eval.

## Evaluation Inputs

The harness should consume a generation gold set and run one or more candidates per case through the same core path:

1. Parse or load a `DesignSpec`.
2. Retrieve templates, defaulting to `k=1` for the FakeGenerator baseline.
3. Generate `n` candidates with the configured `SequenceGenerator`.
4. Re-annotate every generated candidate with the Phase 0 parser.
5. Run requested-component checks against the re-annotated sequence.
6. Run the configured constraint engine, using the existing stub only when the real Phase 3 engine is unavailable.
7. Run novelty checks against the retrieved templates and the configured training/corpus examples.
8. Write aggregate metrics plus per-case details to Markdown and JSON under `data/eval/generation/`.

Recommended command surface for EVAL-2:

- `make eval-generation` runs the fake-backed offline baseline.
- Optional CLI module name can mirror existing structure, for example `python -m packages.generation.eval`.
- Default output prefix should be timestamped, for example `data/eval/generation/2026-06-03-101500-generation-eval.{md,json}`.

Required input fields per gold case:

- `id`: stable case id.
- `query`: natural-language query for end-to-end mode.
- `spec`: optional explicit `DesignSpec` JSON. If present, use this rather than relying on parser variability.
- `expected_components`: structured requirements that the parser must recover from the generated candidate.
- `acceptable_template_ids`: optional expected retrieval/template set for sanity checks.
- `unsupported`: boolean for cases that should be skipped or marked unsupported because the current corpus/parser lacks the vector profile.
- `notes`: human-readable rationale and provenance.

Use explicit `spec` entries for the initial harness so the evaluation isolates generation/re-annotation rather than re-measuring intent parsing. Query text should still be preserved in reports for auditability.

## Metrics

Report metrics at both candidate level and gold-case level. If each case produces one candidate, these are identical. If `n > 1`, case-level pass should be true when at least one candidate passes all required checks unless EVAL-2 explicitly chooses a stricter all-candidates policy and documents it.

Core metrics:

- `syntactic_valid_rate`: fraction of candidates whose sequence normalizes with `normalize_dna` and contains only `ACGT`.
- `sane_length_rate`: fraction of candidates whose length falls inside the configured length policy.
- `component_complete_rate`: fraction of candidates whose re-annotation satisfies all requested component checks.
- `constraint_pass_rate`: fraction of candidates where `ValidationReport.overall == PASS`.
- `novel_rate`: fraction of candidates that are not verbatim copies of training/corpus examples under circular-aware exact matching.
- `phase2_gate_proxy_rate`: fraction of candidates satisfying syntactic validity, sane length, component completeness, and constraint pass.
- `strict_generation_success_rate`: fraction satisfying syntactic validity, sane length, component completeness, constraint pass, and novelty.

Important distinction: `phase2_gate_proxy_rate` matches `SYSTEM_DESIGN.md` Section 7.6's gate ingredients except novelty is reported separately. `strict_generation_success_rate` includes novelty for operational visibility but should not be used to claim the formal Phase 2 gate unless the human updates the gate definition.

Length policy:

- Default conservative plasmid bounds: `1000 <= length_bp <= 20000`.
- If `expected_components.vector_type` or `spec.vector_type` has a configured profile-specific bound, use it and record the bound in the report.
- Do not make AAV/lentiviral/package-capacity hard failures in this harness unless the Phase 3 engine supplies those checks. Capacity and synthesis constraints belong in Phase 3; this harness only records the length screen.

Report denominator handling:

- Exclude `unsupported=true` gold cases from pass-rate denominators and report them separately.
- Include retrieval/generation failures in denominators as failed cases unless the case is explicitly unsupported.
- If the real Phase 3 engine is unavailable and `StubConstraintEngine` is used, label `constraint_pass_rate` as `stub_constraint_pass_rate` and mark the report as not eligible for a Phase 2 gate claim.

## Gold Set Structure

Initial file target: `data/eval/generation_gold.jsonl`.

EVAL-2 can implement a small fake-baseline gold set first, then expand toward the formal Phase 2 gate set later. The first set should reuse current corpus strengths and avoid profiles known to be absent.

Recommended initial cases:

- Bacterial cloning vector, e.g. pUC-style routine E. coli cloning, expecting vector profile, ORI, marker, and MCS when those components are requested.
- Bacterial expression vector, e.g. GST-tagged E. coli expression, expecting bacterial-expression profile, marker, promoter, GOI/tag evidence, and ORI where parser support exists.
- Yeast shuttle vector, expecting yeast-shuttle profile, bacterial propagation components, yeast-maintenance component evidence when available, and marker if requested.
- Mammalian reporter vector only if the current branch corpus/parser can re-annotate it reliably.

Do not include lentiviral, AAV, CRISPR, or shRNA cases in the first denominator unless parser/corpus support has been explicitly added and approved. `PROGRESS.md` records that lentiviral and CRISPR classified seeds are still absent, and `research/findings/phase2_readiness.md` preserves Addgene/provenance constraints.

Suggested JSONL shape:

```json
{
  "id": "gen-bacterial-cloning-puc19",
  "query": "I need a simple high-copy cloning vector for routine plasmid cloning in E. coli.",
  "spec": {
    "organism": "Escherichia coli",
    "vector_type": "bacterial_cloning_vector",
    "genes": [],
    "tags": [],
    "promoter_type": null,
    "markers": ["ampicillin"],
    "application": "routine plasmid cloning",
    "cloning_method": null,
    "constraints": [],
    "clarification_needed": false,
    "clarification_question": null
  },
  "expected_components": {
    "vector_type": "bacterial_cloning_vector",
    "markers": ["ampicillin"],
    "feature_types": ["ORI", "marker", "MCS"]
  },
  "acceptable_template_ids": ["curated:pUC19"],
  "unsupported": false,
  "notes": "FakeGenerator baseline should retrieve and return pUC19, then parser should recover core cloning-vector components."
}
```

The harness should validate each gold-set row with a local Pydantic model or equivalent strict parser before running evaluation. Invalid gold rows should fail the eval early.

## Component Completeness Checks

Component completeness must be based on the re-annotated `AnnotatedSequence`, not on carried-forward template annotations. This follows `SYSTEM_DESIGN.md` Section 7.5 and `research/findings/phase2_spike_spec.md`.

Minimum checks:

- `DesignSpec.vector_type` must match `AnnotatedSequence.vector_profile` or controlled-vocabulary evidence in feature names, using the existing `requested_component_checks` approach.
- Every requested marker in `DesignSpec.markers` must match re-annotated marker evidence via controlled marker terms.
- `DesignSpec.promoter_type`, when present, must match re-annotated promoter evidence via controlled promoter terms.
- Every requested gene in `DesignSpec.genes` must have GOI or feature-name evidence using conservative token-boundary matching.
- Every requested tag in `DesignSpec.tags` must match re-annotated evidence via controlled tag terms.
- Every explicit `expected_components.feature_types` entry must appear in `AnnotatedSequence.features` by feature type.

Do not require universal ORI/promoter/GOI/marker/MCS/terminator for every case. Use vector-profile-aware expectations, consistent with current Phase 0 parser direction in `PROGRESS.md` and parser audit findings. For example, a cloning-vector case may require ORI, marker, and MCS; a simple retrieval query that did not request a promoter should not fail solely because `DesignSpec.promoter_type` is null.

Record component details in JSON:

- `requested_kind`
- `requested_value`
- `matched`
- `evidence`
- `source`: `spec`, `expected_components`, or both

Markdown should show a compact per-case table with failed component checks first.

## Constraint Engine Interface

Use the existing protocol shape from `packages/generation/spike.py` and `SYSTEM_DESIGN.md` Section 8.1:

```python
class ConstraintEngine(Protocol):
    def validate(self, sequence: AnnotatedSequence, spec: DesignSpec) -> ValidationReport: ...
```

Behavior rules:

- If a real Phase 3 engine is importable/configured, use it and report `constraint_engine_version` from `ValidationReport.generated_by_model_version` or a concrete engine version attribute.
- If unavailable, use `StubConstraintEngine` only for the fake-baseline harness, and label every output as provisional.
- A candidate passes constraints only when `ValidationReport.overall == PASS`.
- `WARN` is not a pass for the formal Phase 2 gate unless the human explicitly changes the gate policy. `SYSTEM_DESIGN.md` Section 8.1 says `WARN` is surfaced but not blocking for final return behavior, but Section 7.6 says the Phase 2 gate is pass/fail through the constraint engine. The conservative eval interpretation is PASS-only.
- Preserve all validation checks in JSON and summarize FAIL/WARN/PASS counts in Markdown.

The report must include `constraint_engine_mode` with one of:

- `stub`: unconditional PASS, not gate-eligible.
- `phase3`: real deterministic Phase 3 engine, potentially gate-eligible if all other requirements are met.
- `unavailable`: no engine was run; constraint pass rate must be null and the run is not gate-eligible.

## Novelty Checks

The novelty requirement in `SYSTEM_DESIGN.md` Section 7.6 is narrow: not a verbatim copy of a training plasmid. Because `FakeGenerator` returns templates verbatim, the baseline should deliberately fail novelty when the top template is part of the training/corpus comparison set.

Minimum novelty checks:

- Normalize sequence to uppercase ACGT with whitespace removed.
- Compare against retrieved parent template sequences.
- Compare against the configured training/corpus example sequences.
- Use circular-aware exact matching: two circular plasmids are verbatim copies if one normalized sequence is a rotation of the other or a rotation of the reverse complement, when reverse-complement equivalence is enabled.
- Report exact copy matches by source id, not only true/false.

Recommended optional checks for richer reporting, not pass/fail gating in the first harness:

- `identity_to_parent_template`: percent identity against the top retrieved template for equal-length candidates.
- `length_delta_to_parent`: candidate length minus top-template length.
- `edit_distance_to_parent`: only for short or equal-length sequences where runtime is acceptable.
- `unique_candidate_count`: number of unique generated sequences per case when `n > 1`.

Novelty pass policy:

- `novel=false` if the generated candidate is an exact circular-aware copy of any configured training/corpus example.
- `novel=false` if it is an exact copy of the retrieved parent template and that template is in the training/corpus set.
- `novel=true` only when no exact training/corpus copy is detected.
- Parent-template copying should always be reported, even if the parent template is not in the configured training set.

For the FakeGenerator baseline, expect `novel_rate` to be `0.0` when the comparison set includes retrieved templates.

## FakeGenerator Baseline Expectations

Expected baseline behavior:

- `syntactic_valid_rate`: `1.0` for normal corpus templates, because `Plasmid.sequence` validates via `normalize_dna`.
- `sane_length_rate`: likely `1.0` for curated/common plasmid templates within 1,000-20,000 bp; any outlier should be reported, not hidden.
- `component_complete_rate`: should be high for gold cases chosen from parser-supported profiles, but failures are possible and useful because they reveal parser/gold mismatch.
- `constraint_pass_rate`: `1.0` only when `StubConstraintEngine` is used; the report must label this as stub-only.
- `novel_rate`: `0.0` when retrieved templates are included in the novelty corpus, because `FakeGenerator` returns the top template verbatim.
- `phase2_gate_proxy_rate`: likely high on supported fake cases, but not gate-eligible with the stub engine and not proof of generation quality.
- `strict_generation_success_rate`: expected `0.0` because novelty fails.

The Markdown summary should explicitly state: the FakeGenerator baseline proves evaluation wiring and creates a lower-bound novelty baseline; it does not demonstrate useful novel plasmid generation.

## Edge Cases

EVAL-2 should cover these with unit tests and report handling:

- Parser returns `clarification_needed=true`: mark case failed unless gold row says `unsupported=true`.
- Retriever returns no templates: mark failed with `failure_reason="no_templates"`.
- Generator returns no candidates: mark failed with `failure_reason="no_candidates"`.
- Generator raises for invalid `n` or marker-swap mismatch: mark failed in per-case output and continue to next case unless `--fail-fast` is set.
- Generated sequence contains non-ACGT or is empty: syntactic validity fails and downstream parser/constraint checks should be skipped for that candidate.
- Generated length outside policy: sane length fails but downstream checks may still run for diagnostics if the sequence is otherwise syntactically valid.
- Phase 0 re-annotation raises: component completeness fails with parser error captured.
- Re-annotated sequence has `annotation_complete=false`: do not automatically fail unless requested components are missing; record the flag separately.
- Circular sequences with different base-1 rotations: novelty exact-copy logic should still detect copies.
- Duplicate generated candidates for `n > 1`: count all candidates for candidate-level metrics and report unique count.
- Unsupported profiles such as lentiviral or CRISPR in the current corpus: mark unsupported only when the gold row explicitly declares it, otherwise fail visibly.
- Constraint engine returns `WARN`: conservative metric treats it as not passing the `constraint_pass_rate`, while still preserving report details.

## Implementation Plan

Recommended smallest implementation path for EVAL-2:

1. Add `data/eval/generation_gold.jsonl` with a small supported-profile baseline set.
2. Add a generation eval module under `packages/generation/` that reuses existing `FakeGenerator`, `S3TemplateReannotator`, `StubConstraintEngine`, `requested_component_checks`, and schema models.
3. Add strict gold-row parsing and a typed result object that can render JSON and Markdown.
4. Implement syntactic validity with `normalize_dna` and length checks with configurable default bounds.
5. Implement component checks by combining `requested_component_checks(spec, reannotated)` with explicit `expected_components.feature_types` checks.
6. Implement novelty with circular-aware exact matching against retrieved templates plus the configured corpus/training sequences.
7. Add a `make eval-generation` target that writes timestamped `.json` and `.md` files under `data/eval/generation/`.
8. Add unit tests for metric math, circular-copy novelty, component-check failures, stub constraint labeling, unsupported-case denominator handling, and fake-baseline expected novelty failure.
9. Run `python -m pytest tests/generation` and the full test target available on the branch.
10. Do not mark the Phase 2 gate complete unless the real Phase 3 engine is used and the configured gold set meets the formal `>= 70%` criteria.

Suggested JSON report top-level fields:

- `generated_at`
- `branch`
- `pipeline_version`
- `generator_version`
- `constraint_engine_mode`
- `constraint_engine_version`
- `gold_set_path`
- `comparison_set_summary`
- `metrics`
- `cases`
- `gate_eligible`
- `gate_exclusion_reasons`

Suggested Markdown report sections:

- Summary
- Configuration
- Metrics
- Gate Eligibility
- Case Results
- Novelty Findings
- Constraint Findings
- Failures And Unsupported Cases

## Questions For Human

No blocking questions for EVAL-2's fake-backed implementation. Implementation can proceed with conservative assumptions.

Non-blocking policy questions to resolve before a real Phase 2 gate claim:

- Should the formal Phase 2 gate treat `ValidationReport.overall == WARN` as pass or fail? This spec uses PASS-only conservatively.
- What exact vector-profile-specific length bounds should replace the default `1000-20000 bp` screen?
- Should novelty compare against all local corpus records, the training split only, or both training and retrieved templates in formal reports?
- Should reverse-complement circular matches count as verbatim copies for plasmid novelty? This spec recommends yes for conservative copy detection.
- Which profiles belong in the first formal generation gold set once parser and corpus support are expanded?
- Which synthesis provider profile should be the default once Phase 3 checks are available?

## Current Generation Baselines

Current reports: `data/eval/generation/2026-06-05-230925-generation-eval.{md,json}` for `FakeGenerator` and `data/eval/generation/2026-06-05-230759-generation-eval.{md,json}` for Carbon-500M.

- `FakeGenerator`: strict generation success `0.000`; novelty `0.000`.
- Carbon-500M pretrained CPU inference: strict generation success `0.462`; novelty `1.000`.

The Carbon result is no-fine-tuning CPU inference only. It is a current-generation plumbing baseline, not a Phase 2 gate claim.
