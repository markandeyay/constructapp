"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, designAav, designAssembly, designGrna, getAavParts, getGrnaReference } from "@/lib/api";
import type {
  AavParts,
  AavRequestBody,
  AssemblyFragmentBody,
  AssemblyRequestBody,
  CapabilityKind,
  CapabilityOutcome,
  GrnaReference,
  GrnaRequestBody,
  RemediationPlan
} from "@/lib/capabilities";

// State and requests for the AAV, assembly and guide RNA workspaces. The plasmid
// workspace keeps its own session and job flow in the page. This hook holds the
// three request forms, calls the capability endpoints, and keeps the latest
// outcome per capability so switching the selector does not discard a result.

export type AavFormState = {
  transgeneName: string;
  transgeneSequence: string;
  targetTissue: string;
  selfComplementary: boolean;
  includeWpre: boolean;
  promoter: string;
  polya: string;
  packagingLimit: string;
};

export type AssemblyFragmentForm = { key: string; name: string; role: AssemblyFragmentBody["role"]; sequence: string; source: string };

export type AssemblyFormState = {
  strategy: AssemblyRequestBody["strategy"];
  enzyme: string;
  targetTm: string;
  fragments: AssemblyFragmentForm[];
};

export type GrnaFormState = {
  targetName: string;
  targetSequence: string;
  nuclease: string;
  editIntent: string;
  scope: string;
  fastaPath: string;
  deliveryName: string;
  deliverySequence: string;
  cloningVector: string;
  cdsStart: string;
  cdsEnd: string;
  maxGuides: string;
};

export const TISSUE_OPTIONS: { value: string; label: string }[] = [
  { value: "ubiquitous", label: "Ubiquitous" },
  { value: "cns_neuron", label: "CNS neuron" },
  { value: "cns_astrocyte", label: "CNS astrocyte" },
  { value: "retina", label: "Retina" },
  { value: "liver", label: "Liver" },
  { value: "muscle", label: "Muscle" },
  { value: "cardiac", label: "Cardiac" }
];

export const EDIT_INTENT_OPTIONS: { value: string; label: string }[] = [
  { value: "knockout", label: "Knockout" },
  { value: "knockin", label: "Knock-in" },
  { value: "activation", label: "Activation" },
  { value: "interference", label: "Interference" }
];

// Names of the nucleases the API accepts, used until the reference endpoint answers.
export const FALLBACK_NUCLEASES = ["SpCas9", "SaCas9", "LbCas12a", "AsCas12a"];

let fragmentCounter = 0;
export function newFragment(partial: Partial<AssemblyFragmentForm> = {}): AssemblyFragmentForm {
  fragmentCounter += 1;
  return { key: `fragment-${fragmentCounter}`, name: "", role: "insert", sequence: "", source: "", ...partial };
}

const INITIAL_AAV: AavFormState = {
  transgeneName: "",
  transgeneSequence: "",
  targetTissue: "ubiquitous",
  selfComplementary: false,
  includeWpre: true,
  promoter: "",
  polya: "",
  packagingLimit: ""
};

const INITIAL_GRNA: GrnaFormState = {
  targetName: "",
  targetSequence: "",
  nuclease: "SpCas9",
  editIntent: "knockout",
  scope: "construct_only",
  fastaPath: "",
  deliveryName: "",
  deliverySequence: "",
  cloningVector: "",
  cdsStart: "",
  cdsEnd: "",
  maxGuides: ""
};

/** Strips FASTA header lines and whitespace so a pasted record is accepted as is. */
export function cleanSequenceInput(raw: string): string {
  return raw
    .split(/\r?\n/)
    .filter((line) => !line.trimStart().startsWith(">"))
    .join("")
    .replace(/\s+/g, "");
}

function optionalNumber(raw: string): number | undefined {
  const trimmed = raw.trim();
  if (!trimmed) {
    return undefined;
  }
  const value = Number(trimmed);
  return Number.isFinite(value) ? value : undefined;
}

export type SubmitResult = { outcome: CapabilityOutcome; requestSummary: string } | { error: string };

export function buildAavBody(form: AavFormState): AavRequestBody | string {
  const sequence = cleanSequenceInput(form.transgeneSequence);
  if (!form.transgeneName.trim()) {
    return "Enter a transgene name.";
  }
  if (!sequence) {
    return "Paste the transgene coding sequence. The designer does not substitute a placeholder for DNA you did not supply.";
  }
  const body: AavRequestBody = {
    transgene_name: form.transgeneName.trim(),
    transgene_sequence: sequence,
    target_tissue: form.targetTissue,
    self_complementary: form.selfComplementary,
    include_wpre: form.includeWpre
  };
  if (form.promoter) {
    body.promoter_preference = form.promoter;
  }
  if (form.polya) {
    body.polya_preference = form.polya;
  }
  const limit = optionalNumber(form.packagingLimit);
  if (limit !== undefined) {
    body.packaging_limit_bp = limit;
  }
  return body;
}

export function buildAssemblyBody(form: AssemblyFormState): AssemblyRequestBody | string {
  if (!form.fragments.length) {
    return "Add at least one fragment.";
  }
  const fragments: AssemblyFragmentBody[] = [];
  for (const [index, fragment] of form.fragments.entries()) {
    const sequence = cleanSequenceInput(fragment.sequence);
    if (!fragment.name.trim() || !sequence || !fragment.source.trim()) {
      return `Fragment ${index + 1} needs a name, a sequence and a source.`;
    }
    fragments.push({ name: fragment.name.trim(), sequence, role: fragment.role, source: fragment.source.trim() });
  }
  if (form.strategy === "golden_gate" && !form.enzyme.trim()) {
    return "Golden Gate assembly needs a Type IIS enzyme name.";
  }
  const body: AssemblyRequestBody = { strategy: form.strategy, fragments };
  if (form.strategy === "golden_gate") {
    body.enzyme = form.enzyme.trim();
  }
  const tm = optionalNumber(form.targetTm);
  if (tm !== undefined) {
    body.target_tm_c = tm;
  }
  return body;
}

export function buildGrnaBody(form: GrnaFormState): GrnaRequestBody | string {
  const sequence = cleanSequenceInput(form.targetSequence);
  if (!form.targetName.trim()) {
    return "Enter a target name.";
  }
  if (!sequence) {
    return "Paste the target sequence.";
  }
  if (form.scope === "supplied_fasta" && !form.fastaPath.trim()) {
    return "A supplied sequence set needs the path of its FASTA file.";
  }
  const body: GrnaRequestBody = {
    target_sequence: sequence,
    target_name: form.targetName.trim(),
    nuclease: form.nuclease,
    edit_intent: form.editIntent,
    off_target_space: form.scope === "supplied_fasta" ? { scope: form.scope, fasta_path: form.fastaPath.trim() } : { scope: form.scope }
  };
  const max = optionalNumber(form.maxGuides);
  if (max !== undefined) {
    body.max_guides_returned = max;
  }
  if (form.deliverySequence.trim()) {
    body.delivery_construct_sequence = cleanSequenceInput(form.deliverySequence);
    if (form.deliveryName.trim()) {
      body.delivery_construct_name = form.deliveryName.trim();
    }
  }
  if (form.cloningVector) {
    body.cloning_vector = form.cloningVector;
  }
  const start = optionalNumber(form.cdsStart);
  const end = optionalNumber(form.cdsEnd);
  if (start !== undefined && end !== undefined) {
    body.cds_region = [start, end];
  }
  return body;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof TypeError) {
    return "The design service could not be reached. Check that the API is running, then try again.";
  }
  return error instanceof Error ? error.message : "The request failed.";
}

type Options = {
  onSubmitted: (kind: CapabilityKind, summary: string) => void;
  onCompleted: (outcome: CapabilityOutcome) => void;
  onFailed: (kind: CapabilityKind, message: string) => void;
};

export function useCapabilityWorkspace({ onSubmitted, onCompleted, onFailed }: Options) {
  const [capability, setCapability] = useState<CapabilityKind>("plasmid");
  const [aavForm, setAavForm] = useState<AavFormState>(INITIAL_AAV);
  const [assemblyForm, setAssemblyForm] = useState<AssemblyFormState>({
    strategy: "gibson",
    enzyme: "",
    targetTm: "",
    fragments: [newFragment(), newFragment()]
  });
  const [grnaForm, setGrnaForm] = useState<GrnaFormState>(INITIAL_GRNA);
  const [outcomes, setOutcomes] = useState<Partial<Record<CapabilityKind, CapabilityOutcome>>>({});
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [aavParts, setAavParts] = useState<AavParts | null>(null);
  const [aavPartsFailed, setAavPartsFailed] = useState(false);
  const [grnaReference, setGrnaReference] = useState<GrnaReference | null>(null);
  const requested = useRef({ aav: false, guide: false });

  useEffect(() => {
    if (capability === "aav" && !requested.current.aav) {
      requested.current.aav = true;
      getAavParts().then(setAavParts).catch(() => setAavPartsFailed(true));
    }
    if (capability === "guide_rna" && !requested.current.guide) {
      requested.current.guide = true;
      getGrnaReference().then(setGrnaReference).catch(() => undefined);
    }
  }, [capability]);

  const changeCapability = useCallback((kind: CapabilityKind) => {
    setCapability(kind);
    setFormError(null);
  }, []);

  const run = useCallback(
    async (kind: Exclude<CapabilityKind, "plasmid">, aav: AavFormState, assembly: AssemblyFormState, grna: GrnaFormState) => {
      setFormError(null);
      let build: string | AavRequestBody | AssemblyRequestBody | GrnaRequestBody;
      let summary: string;
      if (kind === "aav") {
        build = buildAavBody(aav);
        summary = `AAV vector for ${aav.transgeneName.trim() || "transgene"}, target tissue ${TISSUE_OPTIONS.find((t) => t.value === aav.targetTissue)?.label ?? aav.targetTissue}${aav.selfComplementary ? ", self-complementary" : ""}.`;
      } else if (kind === "assembly") {
        build = buildAssemblyBody(assembly);
        summary = `${assembly.strategy.replace("_", " ")} assembly of ${assembly.fragments.length} fragment${assembly.fragments.length === 1 ? "" : "s"}.`;
      } else {
        build = buildGrnaBody(grna);
        summary = `Guides for ${grna.targetName.trim() || "target"} with ${grna.nuclease}, ${grna.editIntent}.`;
      }
      if (typeof build === "string") {
        setFormError(build);
        return;
      }
      setBusy(true);
      onSubmitted(kind, summary);
      try {
        let outcome: CapabilityOutcome;
        if (kind === "aav") {
          outcome = { kind, data: await designAav(build as AavRequestBody) };
        } else if (kind === "assembly") {
          outcome = { kind, data: await designAssembly(build as AssemblyRequestBody) };
        } else {
          outcome = {
            kind,
            data: await designGrna(build as GrnaRequestBody),
            targetSequence: (build as GrnaRequestBody).target_sequence
          };
        }
        setOutcomes((current) => ({ ...current, [kind]: outcome }));
        onCompleted(outcome);
      } catch (error) {
        const message = errorMessage(error);
        setFormError(message);
        onFailed(kind, message);
      } finally {
        setBusy(false);
      }
    },
    [onCompleted, onFailed, onSubmitted]
  );

  const submit = useCallback(() => {
    if (capability !== "plasmid") {
      void run(capability, aavForm, assemblyForm, grnaForm);
    }
  }, [capability, run, aavForm, assemblyForm, grnaForm]);

  const applyPlan = useCallback(
    (plan: RemediationPlan) => {
      const next: AavFormState = { ...aavForm };
      for (const change of plan.changes) {
        if (change.kind === "substitute" && change.role === "promoter" && change.to_part_id) {
          next.promoter = change.to_part_id;
        } else if (change.kind === "substitute" && change.role === "polya" && change.to_part_id) {
          next.polya = change.to_part_id;
        } else if (change.kind === "remove" && change.role === "wpre") {
          next.includeWpre = false;
        }
      }
      setAavForm(next);
      void run("aav", next, assemblyForm, grnaForm);
    },
    [aavForm, assemblyForm, grnaForm, run]
  );

  const aavAsFragments = useCallback(() => {
    const outcome = outcomes.aav;
    if (!outcome || outcome.kind !== "aav") {
      return;
    }
    const seen = new Map<string, number>();
    const fragments = outcome.data.design.elements.map((element) => {
      const count = (seen.get(element.role) ?? 0) + 1;
      seen.set(element.role, count);
      return newFragment({
        name: count > 1 ? `${element.role}_${count}` : element.role,
        role: "insert",
        sequence: element.sequence,
        source: element.part_id ? `part:${element.part_id}` : element.source ?? "AAV design transgene"
      });
    });
    setAssemblyForm((current) => ({ ...current, fragments }));
    changeCapability("assembly");
  }, [outcomes.aav, changeCapability]);

  const clearOutcomes = useCallback(() => {
    setOutcomes({});
    setFormError(null);
  }, []);

  return {
    capability,
    setCapability: changeCapability,
    aavForm,
    setAavForm,
    assemblyForm,
    setAssemblyForm,
    grnaForm,
    setGrnaForm,
    outcomes,
    clearOutcomes,
    busy,
    formError,
    aavParts,
    aavPartsFailed,
    grnaReference,
    submit,
    applyPlan,
    aavAsFragments
  };
}
