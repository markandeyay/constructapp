> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Phase 2 Bounded Offline Spike Specification

- Approved: 2026-06-01
- Purpose: pipeline plumbing validation only
- Implementation branch: `phase2-spike`
- Related readiness record: `research/findings/phase2_readiness.md`

## Scope

The spike is one narrow vertical slice:

1. Parse one natural-language query into one `DesignSpec`.
2. Retrieve one top template from the existing 82-record corpus.
3. Generate one deterministic candidate sequence from that template.
4. Re-annotate the generated candidate with the Phase 0 parser.
5. Pass the re-annotated candidate through a stub `ConstraintEngine` that
   returns `PASS` unconditionally.
6. Assemble one schema-valid output containing the specification, retrieved
   template provenance, generated candidate, parser annotation, and stub
   validation result.

This proves only that the retrieval-grounded generation path is wired end to
end. It does not demonstrate sequence quality, biological feasibility, or
training readiness.

## Required Interface

Implement and exercise the `SequenceGenerator` contract from
`SYSTEM_DESIGN.md` Section 4.3:

```python
class SequenceGenerator(Protocol):
    def generate(
        self,
        spec: DesignSpec,
        templates: list[RetrievedPlasmid],
        n: int = 1,
    ) -> list[GeneratedSequence]: ...
```

The required spike implementation is a deterministic `FakeGenerator`. It
returns the top retrieved template verbatim by default. An explicitly supplied
marker-sequence swap may be applied for test coverage. A CPU-runnable
Carbon-500M generation path is a stretch goal, not an exit requirement.

Carbon checkpoints are pretrained-only during this spike:

1. `Carbon-500M` is the approved first smoke-test checkpoint.
2. `Carbon-3B` is the approved practical follow-up target.
3. Evo 2 7B is deferred to a later benchmarking session.

## Mechanical Success Criteria

The spike is complete only when:

1. `make spike-generation TEXT="<query>"` runs the vertical slice end to end.
2. The pipeline returns one assembled, schema-valid output.
3. The output includes a valid `GeneratedSequence` and a valid
   `AnnotatedSequence`.
4. The generated candidate is re-annotated by the Phase 0 parser.
5. Parser re-annotation confirms that components requested in the `DesignSpec`
   remain present.
6. The stub `ConstraintEngine` returns `PASS`.
7. Repeating the same command with the same input produces the same candidate
   sequence and the same structured result, aside from explicitly documented
   timestamps if any.

These criteria are mechanical. Passing them must not be reported as evidence
that the generated sequence is biologically valid or synthesis-ready.

## Explicit Non-Goals

Do not add any of the following during the spike:

1. Fine-tuning, LoRA, or training runs.
2. GPU spend or managed-GPU provisioning.
3. Evo 2 7B benchmarking.
4. A Phase 3 constraint checker beyond an unconditional `PASS` stub.
5. Biological-quality claims about generated candidates.
6. A generation gold set or a Phase 2 gate attempt.
7. Model promotion, production serving, or user-visible sequence delivery.
8. Lentiviral or CRISPR seed expansion while Addgene access remains pending.

## Implementation Notes

Keep model-dependent behavior behind `SequenceGenerator`. The deterministic fake
must remain available after any Carbon adapter is added so tests run without
network access, model downloads, API keys, or GPU hardware.

The generated candidate must flow through the existing Phase 0 parser rather
than carrying forward template annotations without verification. The assembled
output must preserve the retrieved template ID and generator model version for
auditability.

If a Carbon smoke test is attempted, it must run on CPU with no paid compute and
must remain optional. Failure to load or run Carbon on local CPU does not block
completion of this fake-backed spike.
