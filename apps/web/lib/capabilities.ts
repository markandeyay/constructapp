import type { ValidationCheck, ValidationReport } from "@/lib/types";

// Payload types for the three capability endpoints (AAV, assembly, guide RNA).
// They mirror the JSON the API returns and carry no constants of their own:
// every number the UI shows comes from these payloads.

export type CapabilityKind = "plasmid" | "aav" | "assembly" | "guide_rna";

export const CAPABILITY_OPTIONS: { kind: CapabilityKind; label: string; hint: string }[] = [
  { kind: "plasmid", label: "Plasmid", hint: "Describe a construct in plain language" },
  { kind: "aav", label: "AAV vector", hint: "Linear cassette checked against the packaging limit" },
  { kind: "assembly", label: "Assembly and primers", hint: "Primers, junctions and an order table" },
  { kind: "guide_rna", label: "Guide RNA", hint: "Ranked guides with the searched space stated" }
];

export type Severity = "pass" | "warn" | "fail" | "unknown";

export type CapabilityCheck = {
  check_id: string;
  label: string;
  severity: Severity;
  message: string;
  coordinates?: [number, number] | null;
  observed?: string | null;
  threshold?: string | null;
  citation?: string | null;
  tier?: "A" | "B" | null;
  remediation?: string[] | null;
};

export type CapabilityReport = {
  capability: string;
  overall: Severity;
  checks: CapabilityCheck[];
  evaluated_at?: string;
  validator_version?: string;
};

/**
 * Adapts a capability `ValidationReport` to the report shape the shared
 * validation component and the workspace chrome already consume. Severity is
 * upper-cased into `status`; `unknown` stays `UNKNOWN` and is never mapped to
 * a pass.
 */
export function adaptReport(report: CapabilityReport): ValidationReport {
  const checks: ValidationCheck[] = report.checks.map((check) => ({
    name: check.label,
    check: check.check_id,
    check_id: check.check_id,
    status: check.severity.toUpperCase(),
    message: check.message,
    observed: check.observed ?? undefined,
    threshold: check.threshold ?? undefined,
    citation: check.citation ?? undefined,
    tier: check.tier ?? undefined,
    start: check.coordinates ? check.coordinates[0] : undefined,
    end: check.coordinates ? check.coordinates[1] : undefined
  }));
  return {
    overall: report.overall.toUpperCase(),
    checks,
    generated_by_model_version: null,
    validator_version: report.validator_version,
    capability: report.capability
  };
}

// ---- AAV ----------------------------------------------------------------

export type AavRequestBody = {
  transgene_name: string;
  transgene_sequence: string;
  target_tissue: string;
  self_complementary: boolean;
  include_wpre: boolean;
  promoter_preference?: string;
  polya_preference?: string;
  packaging_limit_bp?: number;
};

export type AavBudgetRow = {
  index: number;
  role: string;
  name: string;
  part_id: string | null;
  length_bp: number;
  running_total_bp: number;
  headroom_bp: number;
};

export type AavLengthBudget = {
  rows: AavBudgetRow[];
  total_bp: number;
  target_bp: number;
  soft_limit_bp: number;
  hard_limit_bp: number;
  headroom_bp: number;
  self_complementary: boolean;
  limit_basis: string;
};

export type AavMapElement = {
  index: number;
  role: string;
  name: string;
  part_id: string | null;
  length_bp: number;
  start: number;
  end: number;
  start_1based: number;
  end_1based: number;
  fraction_of_cassette: number;
};

export type AavLinearMap = {
  elements: AavMapElement[];
  total_bp: number;
  target_bp: number;
  soft_limit_bp: number;
  hard_limit_bp: number;
  topology: string;
  self_complementary: boolean;
  serotype?: string;
  target_tissue?: string;
  transgene_name?: string;
};

export type RemediationChange = {
  kind: "substitute" | "remove" | string;
  role: string;
  from_part_id: string | null;
  from_name: string;
  from_bp: number;
  to_part_id?: string | null;
  to_name?: string | null;
  to_bp?: number | null;
  saved_bp: number;
  tradeoff: string;
};

export type RemediationPlan = {
  changes: RemediationChange[];
  saved_bp: number;
  resulting_bp: number;
  resulting_headroom_bp: number;
  preserves_promoter_preference: boolean;
};

export type AavRemediation = {
  total_bp: number;
  target_bp: number;
  overage_bp: number;
  plans: RemediationPlan[];
  remaining_deficit_bp?: number;
  max_transgene_bp?: number | null;
  promoter_preference?: string | null;
};

export type AavElementPayload = {
  role: string;
  name: string;
  sequence: string;
  part_id?: string | null;
  source?: string | null;
};

export type AavDesignResponse = {
  design_id: string;
  capability: string;
  topology: string;
  design: { elements: AavElementPayload[]; transgene_name?: string };
  report: CapabilityReport;
  result: {
    artifacts: Record<string, string>;
    parameters_used: Record<string, unknown>;
    provenance: string[];
  };
  length_budget: AavLengthBudget;
  length_budget_text: string;
  remediation: AavRemediation;
  notes: string[];
  export_blocked?: boolean;
  export_block_reason?: string | null;
};

export type AavParts = {
  categories: Record<
    string,
    { id: string; name: string; length_bp: number; tissue_specificity: string | null; notes?: string }[]
  >;
  total: number;
};

export function parseLinearMap(response: AavDesignResponse): AavLinearMap | null {
  const raw = response.result.artifacts.linear_map_json;
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as AavLinearMap;
  } catch {
    return null;
  }
}

// ---- Assembly -----------------------------------------------------------

export type AssemblyFragmentBody = {
  name: string;
  sequence: string;
  role: "insert" | "vector" | "linker";
  source: string;
};

export type AssemblyRequestBody = {
  strategy: "gibson" | "golden_gate" | "pcr_cloning";
  fragments: AssemblyFragmentBody[];
  enzyme?: string;
  target_tm_c?: number;
};

export type OrderTableRow = {
  name: string;
  sequence_5_to_3: string;
  length_nt: number;
  tm_c: number;
  gc_percent: number;
  notes: string;
};

export type ThermocyclingStep = {
  label: string;
  temperature_c: number;
  seconds: number;
  cycles: number;
};

export type AssemblyProtocol = {
  strategy: string;
  reaction_composition: string[];
  annealing_temperature_c: number;
  annealing_rule: string;
  pcr_program: ThermocyclingStep[];
  assembly_program: ThermocyclingStep[];
  expected_outcome: string;
  sources: string[];
};

export type JunctionMapEntry = {
  index: number;
  left_fragment: string;
  right_fragment: string;
  label: string;
  sequence: string;
  length_bp: number;
  detail: string;
};

export type DomesticationEdit = {
  fragment: string;
  recognition_site: string;
  edit_position: number;
  original_base: string;
  proposed_base: string;
  in_coding_sequence: boolean;
  amino_acid?: string | null;
  original_codon?: string | null;
  proposed_codon?: string | null;
  host_frequency_status?: string;
  host_frequency_reason?: string | null;
};

export type DomesticationReport = {
  enzyme: string;
  recognition_site: string;
  sites_found: number;
  edits: DomesticationEdit[];
  unresolved: { fragment: string; recognition_site: string; reason: string }[];
  notes: string[];
};

export type AssemblyDesignResponse = {
  design_id: string;
  design: {
    request: { strategy: string; fragments: { name: string; role: string }[] };
    fragment_order: string[];
    amplicons: { name: string; fragment: string; length_bp: number }[];
    provenance: string[];
  };
  outputs: {
    order_table: OrderTableRow[];
    order_table_csv: string;
    protocol: AssemblyProtocol;
    junction_map: JunctionMapEntry[];
    junction_map_text: string;
    domestication: DomesticationReport | null;
    report: CapabilityReport;
  };
  provenance: string[];
  parameters_used: Record<string, unknown>;
  export_blocked?: boolean;
  export_block_reason?: string | null;
};

// ---- Guide RNA ----------------------------------------------------------

export type GrnaRequestBody = {
  target_sequence: string;
  target_name: string;
  nuclease: string;
  edit_intent: string;
  off_target_space: { scope: string; fasta_path?: string };
  max_guides_returned?: number;
  delivery_construct_name?: string;
  delivery_construct_sequence?: string;
  cloning_vector?: string;
  cds_region?: [number, number];
};

export type GrnaPlacement = {
  strand: 1 | -1;
  spacer_start: number;
  spacer_end: number;
  pam_start: number;
  pam_end: number;
  pam_observed: string;
  pam_side: string;
  cut_site: number;
};

export type GrnaContribution = {
  feature: string;
  detail: string;
  weight: number;
  direction: "up" | "down" | "neutral";
};

export type GrnaOnTarget = {
  model_name: string;
  model_kind: "published_model" | "labeled_heuristic";
  citation: string;
  validity_domain: string;
  status: "in_domain" | "in_domain_with_caveat" | "out_of_domain";
  score: number | null;
  score_scale: string;
  caveats: string[];
  reasoning: GrnaContribution[];
  disclaimer: string;
};

export type GrnaOffTargetHit = {
  source_label: string;
  start: number;
  end: number;
  strand: 1 | -1;
  protospacer: string;
  pam: string;
  mismatches: number;
  seed_mismatches: number;
  hit_score: number | null;
  is_on_target: boolean;
};

export type GrnaOffTarget = {
  scope: string;
  space_statement: string;
  hits: GrnaOffTargetHit[];
  specificity_model_name: string;
  specificity_citation: string;
  specificity_validity_domain: string;
  specificity_status: string;
  specificity_score: number | null;
  disclaimer: string;
  searched: boolean;
  seed_region_nt: number;
  max_mismatches_searched: number;
};

export type GrnaOligo = {
  name: string;
  sequence: string;
  role: string;
  length_nt: number;
};

export type GrnaGuide = {
  rank: number;
  guide_id: string;
  spacer: string;
  pam: string;
  pam_motif: string;
  pam_is_alternative: boolean;
  strand: 1 | -1;
  placement: GrnaPlacement;
  on_target: GrnaOnTarget;
  off_target: GrnaOffTarget;
  report: CapabilityReport;
  flags: string[];
  reasoning: string[];
  cloning: { vector_name: string; oligos: GrnaOligo[]; notes: string[] } | null;
};

export type GrnaDesignResponse = {
  capability: string;
  off_target_space_statement: string;
  result: {
    design_id: string;
    target_name: string;
    nuclease: string;
    guides_enumerated: number;
    guides_returned: GrnaGuide[];
    rejected: { guide_id: string; spacer: string; reason: string }[];
    notes: string[];
    parameters_used: Record<string, unknown>;
    provenance: string[];
  };
  design_result: { report: CapabilityReport };
  exports: Record<string, string>;
  export_blocked?: boolean;
  export_block_reason?: string | null;
};

export type GrnaScoreReference = {
  name: string;
  kind: string;
  role: string;
  citation: string;
  validity_domain: string;
  wording: string;
};

export type GrnaReference = {
  validator_version: string;
  nucleases: { nuclease: string; pam_motif: string; pam_position: string; spacer_length_nt: number }[];
  cloning_vectors: { vector_id: string; name: string; nucleases: string[] }[];
  scores: GrnaScoreReference[];
  off_target_scopes: { scope: string; covers: string }[];
};

// ---- Outcome wrapper ----------------------------------------------------

export type CapabilityOutcome =
  | { kind: "aav"; data: AavDesignResponse }
  | { kind: "assembly"; data: AssemblyDesignResponse }
  | { kind: "guide_rna"; data: GrnaDesignResponse; targetSequence: string };

export function outcomeDesignId(outcome: CapabilityOutcome): string {
  return outcome.kind === "guide_rna" ? outcome.data.result.design_id : outcome.data.design_id;
}

export function outcomeReport(outcome: CapabilityOutcome): CapabilityReport {
  if (outcome.kind === "aav") {
    return outcome.data.report;
  }
  if (outcome.kind === "assembly") {
    return outcome.data.outputs.report;
  }
  return outcome.data.design_result.report;
}

export function outcomeSummary(outcome: CapabilityOutcome): string {
  const report = outcomeReport(outcome);
  const unknown = report.checks.filter((check) => check.severity === "unknown").length;
  const verdict = `Overall ${report.overall.toUpperCase()}${unknown ? `, with ${unknown} check${unknown === 1 ? "" : "s"} not evaluated` : ""}.`;
  if (outcome.kind === "aav") {
    const budget = outcome.data.length_budget;
    const headroom = budget.headroom_bp;
    const limitText =
      headroom >= 0
        ? `${headroom.toLocaleString()} bp under the ${budget.target_bp.toLocaleString()} bp packaging target`
        : `${Math.abs(headroom).toLocaleString()} bp over the ${budget.target_bp.toLocaleString()} bp packaging target`;
    return `Composed a linear AAV cassette of ${budget.total_bp.toLocaleString()} bp, ${limitText}. ${verdict}`;
  }
  if (outcome.kind === "assembly") {
    const count = outcome.data.outputs.order_table.length;
    return `Designed ${count} primer${count === 1 ? "" : "s"} for a ${outcome.data.design.request.strategy.replace("_", " ")} assembly of ${outcome.data.design.request.fragments.length} fragments. ${verdict}`;
  }
  const guides = outcome.data.result.guides_returned.length;
  return `Ranked ${guides} guide${guides === 1 ? "" : "s"} for ${outcome.data.result.target_name} from ${outcome.data.result.guides_enumerated} enumerated. ${verdict} ${outcome.data.off_target_space_statement}`;
}
