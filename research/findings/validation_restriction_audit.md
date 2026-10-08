> Historical design or research note, kept for the record and not current. Current truth lives in `README.md`, `docs/demo.md` and `PROGRESS.md`.

# Validation Restriction-Site Audit

Date: 2026-06-15
Branch: `validation-deepening`
Scope reviewed: `packages/validation/restriction.py`, validation package integration, validation gold data, and related validation tests.

## Executive Summary

`restriction_site_conflicts` currently detects one narrow class of conflict: if `DesignSpec.cloning_method` or `DesignSpec.constraints` explicitly names one of 14 hard-coded common restriction enzymes, the checker scans the full construct and fails when a detected cut/recognition interval does not overlap an annotated `MCS` feature plus 6 bp padding.

This is useful for simple two-enzyme restriction cloning examples, but it is not yet a method-aware cloning validator. It misses many real conflicts and can also pass biologically incomplete restriction-cloning specs because it treats absent requested sites as `PASS`.

Highest-priority gaps:

1. Enzyme extraction is a small hard-coded whitelist, not Biopython/REBASE-backed, so named enzymes outside `COMMON_CLONING_ENZYMES` are ignored.
2. The check has no isoschizomer/equischizomer/neoschizomer policy, even though Biopython exposes these relationships.
3. The check does not interpret cloning method semantics: restriction cloning, Golden Gate/type IIS, Gibson/HiFi/LIC, Gateway, TOPO/TA, and synthesis should not share the same rule.
4. GOI-internal and vector-backbone-internal sites are collapsed into the same "outside MCS" failure, while MCS-internal sites are always accepted.
5. It does not verify required site presence, uniqueness, orientation, overhang compatibility, or whether cuts would excise the intended insert rather than simply existing within an MCS.

## Current Implementation

Relevant code path:

- `packages/validation/restriction.py:39-60`: `run_restriction_site_check()` extracts enzyme names from `DesignSpec`, searches sites, and fails first site outside MCS.
- `packages/validation/restriction.py:63-69`: `enzymes_from_spec()` scans `spec.cloning_method` plus `spec.constraints` with exact word-boundary regex matches against `COMMON_CLONING_ENZYMES`.
- `packages/validation/restriction.py:72-85`: `find_restriction_sites()` selects matching enzyme classes from Biopython `AllEnzymes`, builds a `RestrictionBatch`, searches the sequence, and emits `RestrictionSite(enzyme, start, end)`.
- `packages/validation/common.py:64-68`: `overlaps_any()` determines whether a site overlaps an MCS with padding.
- `packages/validation/engine.py:33-39`: the check runs as one of four deterministic validation checks.

Current algorithm:

1. Build `haystack = spec.cloning_method + constraints`.
2. Detect only enzyme names in `COMMON_CLONING_ENZYMES`: BamHI, EcoRI, HindIII, KpnI, NcoI, NdeI, NotI, PstI, SacI, SalI, SmaI, SpeI, XbaI, XhoI.
3. If no enzyme is found, return `PASS`.
4. Search the complete sequence with Biopython, using circular search when `sequence.topology == "circular"`.
5. If no site is found for requested enzymes, return `PASS`.
6. Find annotated features whose `type` is `MCS`.
7. Fail the first requested-enzyme site that does not overlap any MCS feature with 6 bp padding.
8. Pass if all requested-enzyme sites overlap an MCS.

## What It Detects Today

The check detects:

- Internal sites outside annotated MCS for the 14 hard-coded enzymes when their exact enzyme names appear in `DesignSpec.cloning_method` or `DesignSpec.constraints`.
- Sites in circular constructs, including boundary-spanning sites, because `RestrictionBatch.search(..., linear=False)` is used for circular topology.
- Multiple named enzymes in free text, including strings such as `EcoRI and BamHI cloning` and `EcoRI/BamHI cloning`.
- MCS-overlap allowance: selected enzyme sites inside or near an annotated MCS are accepted.

Evidence:

- `tests/validation/test_restriction.py:7-17` asserts failure when EcoRI is outside MCS under `EcoRI and BamHI cloning`.
- `tests/validation/test_restriction.py:19-26` asserts pass when EcoRI and BamHI are both inside MCS.
- `tests/validation/test_restriction.py:29-32` asserts pass under Gibson assembly with no named enzyme context.
- `data/eval/validation/curated_known_bad.jsonl` lines 1-13 contain curated bad cases for EcoRI, BamHI, HindIII, XhoI, KpnI, PstI, SalI, XbaI, NcoI, NdeI, NotI, SacI, and SpeI internal sites outside MCS.
- `data/eval/validation/curated_known_bad_uncertainty.md:5` states that incidental restriction sites in Gibson/HiFi/LIC, Gateway/TOPO, or synthesis-only designs were excluded unless a named enzyme constraint made the site blocking.

## What It Misses

### Enzyme Coverage

The checker ignores any enzyme not in `COMMON_CLONING_ENZYMES`, even if Biopython supports it and the user names it explicitly. Examples: BsaI, BsmBI, BbsI, SapI, PaqCI, Esp3I, Acc65I, Asp718I, EcoRV, BglII, AgeI, AflII, AvrII, MluI, AscI, SfiI, and hundreds more.

This matters because Golden Gate/type IIS methods commonly use BsaI, BsmBI/Esp3I, BbsI, SapI, PaqCI, or related enzymes. None are in the whitelist, so a DesignSpec such as `Golden Gate with BsaI` currently returns `PASS` even if BsaI appears internally in the GOI or backbone.

Biopython 1.87 in this environment reports `AllEnzymes` with 1088 enzyme classes and accepts enzyme-name strings in `RestrictionBatch(['EcoRI'])`, so broader extraction is implementable without maintaining a local enzyme whitelist.

### Required Site Presence

If a restriction-cloning DesignSpec names an enzyme but the sequence has no corresponding sites, the current checker returns `PASS` at `packages/validation/restriction.py:45-46`. For simple restriction cloning, absent named sites may be a failure or at least a warning because the requested digestion cannot happen from the provided construct.

This is not a pure "conflict" bug, but it makes the check overstate validity for incomplete restriction-cloning designs.

### Site Count and Placement

The checker only asks whether all detected sites overlap an MCS. It does not verify:

- The expected count for single/double digest workflows.
- Whether the named enzymes flank the GOI or insertion point.
- Whether two enzymes produce compatible intended ends.
- Whether duplicate sites within the MCS would fragment the insert or vector.
- Whether enzyme sites are ordered correctly around the MCS/GOI.
- Whether selected enzymes are unique in the vector backbone.

### Cut Coordinates Versus Recognition Coordinates

Biopython restriction search positions follow biological 1-based cut-position semantics; the cookbook states that `search()` returns the first base of the downstream segment produced by restriction, not necessarily the recognition-sequence start. The current code converts each returned position to `start = position - 1` and then uses `site_len` to build a region. For enzymes that cut within or outside recognition sites, this interval can be shifted relative to the recognition motif.

For EcoRI, this is usually close enough for conflict localization. For enzymes that cut outside their recognition site, including type IIS enzymes used in Golden Gate, this will not reliably report the recognition-site interval or the cut-site interval unless the implementation uses enzyme cut metadata intentionally.

### Methylation, Star Activity, and Edge Accessibility

Biopython's restriction cookbook explicitly notes limitations: it treats DNA as non-methylated, has no support for star activity, allows degenerate DNA safely, rejects non-standard bases, and warns that sites at linear DNA edges might not be accessible in real digestion. The current validation check inherits these limitations and does not surface them as uncertainty.

## Isoschizomer And Neoschizomer Handling

Current handling: effectively none.

What happens today:

- If the exact named enzyme is in `COMMON_CLONING_ENZYMES`, Biopython detects that enzyme's recognition site.
- If a user names an isoschizomer/equischizomer/neoschizomer not in `COMMON_CLONING_ENZYMES`, the checker treats the spec as having no restriction-enzyme context and returns `PASS`.
- If a user names KpnI, the sequence motif `GGTACC` is detected. But if the user names Acc65I or Asp718I, the checker ignores the context despite those enzymes sharing the same recognition site family with KpnI.
- The check does not distinguish true/equischizomers that cut the same way from neoschizomers that recognize the same sequence but cut differently.

Biopython capabilities:

- The Biopython restriction cookbook defines isoschizomers as enzymes sharing a recognition site and neoschizomers as enzymes recognizing the same site but cutting differently.
- Enzyme classes expose `isoschizomers()`, `neoschizomers()`, `equischizomers()`, `is_isoschizomer()`, `is_neoschizomer()`, and `is_equischizomer()`.
- In the installed Biopython 1.87 probe, `Acc65I.isoschizomers()` returns `Asp718I` and `KpnI`; `Acc65I.neoschizomers()` returns `KpnI`; `Acc65I.equischizomers()` returns `Asp718I`; and `KpnI.is_neoschizomer(Acc65I)` is true.

Recommendation:

- Treat exact named enzymes as primary constraints.
- For "avoid internal recognition site" policy, expand to isoschizomers only when the design constraint is phrased as a recognition-site/domestication constraint or when the cloning method is type IIS site removal.
- For cut/ligation compatibility, distinguish equischizomers from neoschizomers; do not silently substitute neoschizomers in workflows where overhang or cut position matters.

## Cloning-Method Context From DesignSpec

`DesignSpec` currently has only free-text `cloning_method` and `constraints` fields (`packages/core/schemas/models.py:172-185`). `restriction.py` does not parse method classes beyond named enzyme detection.

Observed method handling:

- `Gibson assembly` with no named enzyme returns `PASS` and ignores incidental restriction sites.
- `EcoRI restriction cloning` triggers exact EcoRI scanning.
- `Golden Gate with BsaI` would not trigger because BsaI is not whitelisted.
- `Gateway cloning` or `TOPO cloning` would not trigger unless a whitelisted enzyme is also mentioned in constraints.
- `avoid EcoRI` in constraints triggers the same rule as `EcoRI restriction cloning`, with no distinction between advisory avoidance and required cloning enzyme.

Method-specific constraints from references:

- Restriction enzyme cloning depends on cutting DNA with selected restriction enzymes and ligating compatible fragments; internal sites for selected enzymes in vector/insert can fragment the intended product and are blocking when those enzymes are used.
- NEB describes Gibson Assembly as exonuclease/polymerase/ligase joining of overlapping DNA fragments under isothermal conditions. Restriction sites are not inherently required unless the workflow includes a digestion step or an explicit no-site constraint.
- NEB describes Golden Gate as using type IIS restriction enzymes and ligase; the type IIS recognition site is designed distal to the cut site and eliminated from the product. NEB explicitly says inserts and cloning vectors should be verified so the type IIS sites used are not present in fragments for the expected product.
- Thermo Fisher describes Gateway as recombination cloning that circumvents traditional restriction-enzyme cloning limitations and does not require ligase/subcloning steps. Internal restriction sites are not generally blocking unless separately constrained.
- TOPO/TA topoisomerase cloning is not a restriction-digest method; internal restriction sites are not generally blocking unless a named enzyme constraint is present.

Recommended method classes:

- `restriction_digest`: named enzymes are required; sites should be present in expected MCS/flanking positions and absent from backbone/GOI unless intentionally used.
- `golden_gate_type_iis`: named type IIS enzyme sites should be present only in designed assembly-flank context and absent from assembled fragments/GOI/backbone unless intended to be removed.
- `gibson_hifi_lic`: ignore incidental restriction sites by default; enforce only explicit `avoid <enzyme>` or workflow-specific digestion constraints.
- `gateway_topo_ta`: ignore incidental restriction sites by default; enforce att/topoisomerase/overhang-specific constraints separately, not with the MCS-only restriction rule.
- `synthesis_only`: no restriction conflict by default; enforce provider synthesis constraints elsewhere.

## MCS-Internal Versus GOI-Internal Sites

Current handling:

- Any requested-enzyme site overlapping an annotated `MCS` plus 6 bp padding passes.
- Any requested-enzyme site outside an annotated `MCS` fails.
- GOI-internal, promoter-internal, marker-internal, ORI-internal, terminator-internal, and unannotated-backbone sites are not distinguished in status or message.
- If no MCS is annotated, any detected requested-enzyme site fails because `cloning_regions` is empty.

Biology interpretation:

- For classical restriction cloning, GOI-internal sites for selected enzymes are usually blocking because the GOI would be cut. Backbone-internal sites outside the intended MCS are also blocking because the vector would be cut unexpectedly.
- For Golden Gate/type IIS, GOI-internal sites for the selected type IIS enzyme are usually blocking unless intentionally domesticated/removed or outside the assembled fragment. Vector-backbone internal type IIS sites may also be blocking if present in the digestion substrate.
- For Gibson/HiFi/LIC, GOI-internal EcoRI/BamHI/etc. sites are usually irrelevant unless the workflow explicitly includes digestion or an `avoid` constraint.
- MCS-internal sites are not automatically safe. They are safe only when they are the intended cloning sites and their count/order/overhangs match the cloning plan. Extra MCS-internal sites can still fragment the MCS or produce ambiguous digestion products.

Implementation gap:

- The current MCS-only region rule is too coarse. It should classify conflicts by feature context: `MCS`, `GOI`, `backbone/unannotated`, `ORI`, `marker`, `promoter`, etc., and then apply method-specific policy.

## Tests And Gold Data Gaps

Current tests are minimal and all align to the current implementation:

- One outside-MCS failure for EcoRI/BamHI.
- One inside-MCS pass for EcoRI/BamHI.
- One Gibson no-context pass.

Curated known-bad restriction cases cover internal sites for the common whitelist enzymes, but not:

- Isoschizomer/equischizomer names such as Acc65I/Asp718I.
- Neoschizomer policy such as Acc65I versus KpnI.
- Type IIS Golden Gate enzymes such as BsaI/BsmBI/BbsI/SapI/PaqCI/Esp3I.
- Named enzymes outside the common whitelist, such as EcoRV or BglII.
- Required site absence under restriction cloning.
- Duplicate/extra MCS sites.
- GOI-internal versus backbone-internal conflict messages.
- Gibson/HiFi designs with incidental whitelisted enzyme sites that should remain PASS unless explicitly constrained.
- Explicit `constraints=["avoid BsaI"]` or `constraints=["no internal EcoRI in GOI"]` semantics.

The current baseline reports 1.000 per-check accuracy (`data/eval/validation/2026-06-07-033018-validation-baseline.md:12-19`), but that score reflects a narrow gold policy rather than broad biological coverage.

## Prioritized Recommendations

### P0: Separate Method Classification From Enzyme Extraction

Implement a small parser that derives:

- `method_class`: `restriction_digest`, `golden_gate_type_iis`, `gibson_hifi_lic`, `gateway_topo_ta`, `synthesis_only`, or `unknown`.
- `named_enzymes`: exact Biopython enzyme classes found in `cloning_method` and `constraints`.
- `constraint_intent`: `required_cloning_site`, `avoid_internal_site`, or `incidental_mention` where possible.

Use Biopython `AllEnzymes` names rather than the 14-enzyme whitelist. Keep `COMMON_CLONING_ENZYMES` only as a fallback display/order list if needed.

### P0: Add Type IIS / Golden Gate Coverage

Recognize common type IIS enzymes and their aliases from Biopython, especially BsaI, BsmBI/Esp3I, BbsI, SapI, PaqCI, BspQI, and AarI where available.

For `golden_gate_type_iis`, fail selected type IIS sites inside GOI or non-designed backbone regions. Do not rely on MCS-only overlap; classify whether the recognition sites are intentionally placed to be removed during assembly.

### P0: Fix Absent Required Sites For Restriction Cloning

For `restriction_digest` with required named enzymes, return `FAIL` or `WARN` when none of the named enzymes are found. Recommended behavior:

- `FAIL` if method text says `<enzyme> restriction cloning` or `digest with <enzyme>` and the enzyme site is absent.
- `WARN` if text is ambiguous, e.g. an enzyme name appears only in a free-form note.

### P1: Feature-Context Conflict Classification

Replace the single outside-MCS conflict list with feature-context classification:

- `MCS`: allowed only if method policy expects site in MCS and count/order is acceptable.
- `GOI`: fail for selected restriction/type IIS enzymes in digestion substrates.
- `backbone/unannotated`: fail for selected enzymes in vector substrate.
- `ORI`, `marker`, `promoter`, `terminator`: fail or warn depending on method and substrate.

Include the feature context in messages, e.g. `BsaI has an internal site inside GOI`, `EcoRI has an extra backbone site outside MCS`, or `EcoRI site absent from annotated MCS`.

### P1: Add Isoschizomer Policy

Use Biopython methods to expand and label enzyme relationships:

- Use `equischizomers()` for same recognition and same cut when user intent is substitutability.
- Use `neoschizomers()` only for recognition-site avoidance, not as cut-compatible substitutes.
- Report when a conflict is detected via an isoschizomer relationship, e.g. `Acc65I/KpnI recognition-site family`.

### P1: Improve Coordinates

Store both recognition interval and cut position when possible:

- Recognition interval for "internal site" conflict reports.
- Cut position/overhang metadata for digestion compatibility checks.

Biopython exposes `site`, `elucidate()`, `is_blunt()`, `is_5overhang()`, `is_3overhang()`, and related enzyme metadata. For type IIS enzymes, avoid deriving recognition intervals from cut positions alone.

### P2: Strengthen Gold Data

Add targeted known-good and known-bad cases:

- Gibson construct with internal EcoRI in GOI: expected PASS absent explicit restriction constraint.
- Gibson construct with `constraints=["avoid EcoRI"]` and GOI EcoRI: expected FAIL or WARN by chosen policy.
- Golden Gate BsaI GOI-internal site: expected FAIL.
- Golden Gate BsaI designed flank sites only: expected PASS.
- Acc65I/Asp718I/KpnI isoschizomer and neoschizomer cases.
- Restriction cloning missing EcoRI site: expected FAIL or WARN.
- Duplicate MCS/internal sites for selected enzyme: expected FAIL.
- EcoRV/BglII non-whitelist named-enzyme cases: expected detection.

### P2: Preserve Explicit Uncertainty

When method parsing is ambiguous, prefer `WARN` over silent `PASS` or overbroad `FAIL`. The existing uncertainty policy in `curated_known_bad_uncertainty.md` is sound: incidental sites in Gibson/HiFi/LIC, Gateway/TOPO, or synthesis-only designs should not be treated as known-bad without a named enzyme constraint.

## Human Review Questions

These biology/product-policy choices need human confirmation before implementation:

1. Should missing required enzyme sites in `restriction_digest` be `FAIL` or `WARN`?
2. Should explicit `avoid <enzyme>` constraints fail for GOI-internal sites under all methods, or only when the GOI is part of a digestion substrate?
3. For isoschizomers, should the validator expand by recognition site for all `avoid` constraints, or only for phrases such as `avoid <enzyme> family` / `no <enzyme> site`?
4. For Golden Gate, should any selected type IIS recognition site inside the final assembled product be a hard `FAIL`, or should domestication/intended-removal annotations allow exceptions?
5. Should MCS-internal duplicate sites for selected enzymes be a hard `FAIL` or a method-specific `WARN` until insert boundaries are explicitly modeled?

## References

- Biopython `Bio.Restriction` cookbook, "Working with restriction enzymes": documents `RestrictionBatch`, circular search with `linear=False`, `Analysis`, enzyme comparison operators, isoschizomer/neoschizomer/equischizomer APIs, overhang helpers, REBASE basis, and limitations.
- Biopython 1.87 API, `Bio.Restriction` package: documents package examples using `Analysis(AllEnzymes, seq)` and restriction enzyme reporting.
- NEB, "Gibson Assembly": describes overlap-based exonuclease/polymerase/ligase assembly under isothermal conditions.
- NEB, "NEBridge Golden Gate Assembly": describes type IIS restriction enzyme plus ligase assembly and states that fragments should be verified so the type IIS sites used are not present in the fragments for the expected product.
- Thermo Fisher Scientific, "Gateway Cloning Solutions": describes Gateway recombination cloning as circumventing traditional restriction-enzyme cloning limitations and not requiring ligase/subcloning steps.
