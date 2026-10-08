"use client";

import { AavResultPanel } from "@/components/aav-panel";
import { AssemblyResultPanel } from "@/components/assembly-panel";
import { GrnaResultPanel } from "@/components/grna-panel";
import type { CapabilityKind, CapabilityOutcome, RemediationPlan } from "@/lib/capabilities";

// The result panel for the selected capability. The plasmid capability keeps the
// existing circular seqviz map, rendered by the page; this pane serves the other three.

export function CapabilityResultPane({
  capability,
  outcome,
  onApplyPlan,
  onUseAsFragments
}: {
  capability: Exclude<CapabilityKind, "plasmid">;
  outcome: CapabilityOutcome | null;
  onApplyPlan: (plan: RemediationPlan) => void;
  onUseAsFragments: () => void;
}) {
  if (capability === "aav") {
    return (
      <AavResultPanel
        response={outcome?.kind === "aav" ? outcome.data : null}
        onApplyPlan={onApplyPlan}
        onUseAsFragments={onUseAsFragments}
      />
    );
  }
  if (capability === "assembly") {
    return <AssemblyResultPanel response={outcome?.kind === "assembly" ? outcome.data : null} />;
  }
  return (
    <GrnaResultPanel
      response={outcome?.kind === "guide_rna" ? outcome.data : null}
      targetSequence={outcome?.kind === "guide_rna" ? outcome.targetSequence : ""}
    />
  );
}
