"use client";

import { downloadText } from "@/components/capability-shared";
import { outcomeDesignId, type CapabilityOutcome } from "@/lib/capabilities";

// Export actions for the AAV, assembly and guide RNA results. Same section, label
// and button styling as the plasmid ExportActions. The content of each file is the
// text the API produced; nothing is rewritten here, so the guide RNA exports keep
// the off-target space statement the API puts at their head.

type ExportFile = { label: string; filename: string; content: string; mime: string };

export function exportFilesFor(outcome: CapabilityOutcome): ExportFile[] {
  const id = outcomeDesignId(outcome);
  if (outcome.kind === "aav") {
    const artifacts = outcome.data.result.artifacts;
    return [
      { label: "GenBank", filename: `${id}.gb`, content: artifacts.genbank ?? "", mime: "application/genbank" },
      { label: "FASTA", filename: `${id}.fasta`, content: artifacts.fasta ?? "", mime: "text/plain" },
      { label: "Length budget", filename: `${id}-length-budget.txt`, content: outcome.data.length_budget_text, mime: "text/plain" }
    ].filter((file) => file.content);
  }
  if (outcome.kind === "assembly") {
    return [
      { label: "Order table CSV", filename: `${id}-order-table.csv`, content: outcome.data.outputs.order_table_csv, mime: "text/csv" },
      { label: "Junction map", filename: `${id}-junction-map.txt`, content: outcome.data.outputs.junction_map_text, mime: "text/plain" }
    ].filter((file) => file.content);
  }
  const exports = outcome.data.exports;
  return Object.entries(exports).map(([name, content]) => ({
    label: name === "guide_table.tsv" ? "Guide table TSV" : name === "oligo_order_table.tsv" ? "Oligo order TSV" : name,
    filename: `${id}-${name}`,
    content,
    mime: "text/tab-separated-values"
  }));
}

// The section 11.1 provenance gate runs on the AAV, assembly and guide RNA design
// routes and withholds the exportable artifacts when a span of the design cannot
// be attributed. The artifacts then arrive empty, which the filter above already
// drops, so no empty file can be downloaded. Without this the buttons would simply
// be absent with nothing said, which is the silent state worth avoiding: the
// researcher needs to know an export was refused and why, not just see no button.
export function exportBlockReasonFor(outcome: CapabilityOutcome | null): string | null {
  if (!outcome || !outcome.data.export_blocked) {
    return null;
  }
  const reason = outcome.data.export_block_reason;
  return reason && reason.trim()
    ? `Export withheld by the provenance gate. ${reason}`
    : "Export withheld by the provenance gate: part of this design could not be attributed to a source record.";
}

export function CapabilityExportActions({ outcome, disabledReason }: { outcome: CapabilityOutcome | null; disabledReason?: string | null }) {
  const files = outcome ? exportFilesFor(outcome) : [];
  const blockReason = exportBlockReasonFor(outcome);
  const reason = disabledReason ?? blockReason;
  return (
    <section aria-label="Export actions" className="flex min-h-0 flex-col justify-center gap-2xs">
      <p className="text-caption text-slate">
        {outcome ? `Design ${outcomeDesignId(outcome)}` : "Complete a design to enable downloads."}
      </p>
      {outcome ? (
        <div className="flex flex-wrap gap-xs">
          {files.map((file) => (
            <button
              key={file.filename}
              type="button"
              disabled={Boolean(reason)}
              onClick={() => downloadText(file.filename, file.content, file.mime)}
              className="rounded-md border border-line-strong bg-paper px-sm py-2xs text-sm font-semibold text-ink hover:bg-mist focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40 disabled:cursor-not-allowed disabled:border-line disabled:bg-paper disabled:text-slate"
            >
              {file.label}
            </button>
          ))}
        </div>
      ) : null}
      {reason ? <p className="text-caption text-slate">{reason}</p> : null}
    </section>
  );
}
