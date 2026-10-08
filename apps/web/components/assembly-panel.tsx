"use client";

import { Card, CopyButton, EmptyPanel, PanelShell, ParametersUsed, SECONDARY_BUTTON, downloadText } from "@/components/capability-shared";
import type {
  AssemblyDesignResponse,
  JunctionMapEntry,
  OrderTableRow,
  ThermocyclingStep
} from "@/lib/capabilities";

// Section 10.2, assembly: a junction map as the primary visual, then the order
// table (copy-pasteable, CSV export), the protocol and the domestication report.
// Everything shown is read from the design response.

export function orderTableTsv(rows: OrderTableRow[]): string {
  const header = ["Primer name", "Sequence (5' to 3')", "Length (nt)", "Tm (C)", "GC (%)", "Notes"].join("\t");
  const body = rows.map((row) =>
    [row.name, row.sequence_5_to_3, row.length_nt, row.tm_c, row.gc_percent, row.notes.replace(/\s+/g, " ")].join("\t")
  );
  return [header, ...body].join("\n");
}

export function AssemblyResultPanel({ response }: { response: AssemblyDesignResponse | null }) {
  if (!response) {
    return (
      <EmptyPanel
        id="assembly-panel"
        title="Assembly junction map"
        heading="No assembly designed"
        text="Add the fragments to join and design primers to see the junction map and the order table."
      />
    );
  }
  const { outputs, design } = response;
  const strategy = design.request.strategy.replace("_", " ");
  return (
    <PanelShell
      id="assembly-panel"
      title="Assembly junction map"
      subtitle={`${strategy} · ${design.fragment_order.length} fragments · ${outputs.order_table.length} primers`}
    >
      <JunctionMap response={response} />
      <OrderTable response={response} />
      <ProtocolCard response={response} />
      {outputs.domestication ? <DomesticationCard response={response} /> : null}
      <ParametersUsed parameters={response.parameters_used} />
    </PanelShell>
  );
}

function JunctionMap({ response }: { response: AssemblyDesignResponse }) {
  const { design, outputs } = response;
  const order = design.fragment_order;
  const junctions = outputs.junction_map;
  const lengthByFragment = new Map(design.amplicons.map((amplicon) => [amplicon.fragment, amplicon.length_bp]));
  const sequential = (junction: JunctionMapEntry) => {
    const left = order.indexOf(junction.left_fragment);
    return left >= 0 && order.indexOf(junction.right_fragment) === left + 1;
  };
  const closing = junctions.find(
    (junction) =>
      order.length > 1 &&
      junction.left_fragment === order[order.length - 1] &&
      junction.right_fragment === order[0]
  );
  const between = (index: number) =>
    junctions.find((junction) => sequential(junction) && junction.left_fragment === order[index]);

  const boxWidth = 150;
  const gap = 130;
  const padX = 20;
  const width = padX * 2 + order.length * boxWidth + Math.max(0, order.length - 1) * gap;
  const arcTop = closing ? 34 : 8;
  const boxTop = arcTop + 30;
  const boxHeight = 56;
  const height = boxTop + boxHeight + 28;

  return (
    <div className="mt-md" data-testid="junction-map">
      <div className="overflow-x-auto rounded-md border border-line bg-paper p-sm shadow-rest">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ minWidth: Math.min(width, 720), width: "100%" }}
          role="img"
          aria-label={`Junction map: ${order.join(", then ")}${closing ? ", closing back to the first fragment" : ""}`}
        >
          {order.map((name, index) => {
            const x0 = padX + index * (boxWidth + gap);
            const join = between(index);
            const length = lengthByFragment.get(name);
            return (
              <g key={name}>
                <rect x={x0} y={boxTop} width={boxWidth} height={boxHeight} rx="6" fill="#f0f1ec" stroke="#365f43" strokeWidth="1.5" />
                <text x={x0 + boxWidth / 2} y={boxTop + 24} textAnchor="middle" fontSize="13" fontWeight="600" fill="#1f2320">
                  {name.length > 20 ? `${name.slice(0, 19)}…` : name}
                </text>
                {length ? (
                  <text x={x0 + boxWidth / 2} y={boxTop + 42} textAnchor="middle" fontSize="11" fill="#5f665f">
                    {length.toLocaleString()} bp amplicon
                  </text>
                ) : null}
                {join && index < order.length - 1 ? (
                  <g data-testid="junction-link">
                    <line x1={x0 + boxWidth} x2={x0 + boxWidth + gap} y1={boxTop + boxHeight / 2} y2={boxTop + boxHeight / 2} stroke="#365f43" strokeWidth="2" />
                    <text x={x0 + boxWidth + gap / 2} y={boxTop + boxHeight / 2 - 8} textAnchor="middle" fontSize="11" fontWeight="600" fill="#1f2320">
                      {join.length_bp.toLocaleString()} bp
                    </text>
                    <text x={x0 + boxWidth + gap / 2} y={boxTop + boxHeight / 2 + 16} textAnchor="middle" fontSize="10" fill="#5f665f">
                      {join.label.replace(/^\d[\d,]*\s*bp\s*/i, "")}
                    </text>
                  </g>
                ) : null}
              </g>
            );
          })}
          {closing ? (
            <g data-testid="junction-closing">
              <path
                d={`M ${padX + (order.length - 1) * (boxWidth + gap) + boxWidth / 2} ${boxTop} C ${padX + (order.length - 1) * (boxWidth + gap) + boxWidth / 2} ${arcTop - 8}, ${padX + boxWidth / 2} ${arcTop - 8}, ${padX + boxWidth / 2} ${boxTop}`}
                fill="none"
                stroke="#365f43"
                strokeWidth="2"
                strokeDasharray="5 4"
              />
              <text x={width / 2} y={arcTop + 2} textAnchor="middle" fontSize="11" fontWeight="600" fill="#1f2320">
                {closing.length_bp.toLocaleString()} bp {closing.label.replace(/^\d[\d,]*\s*bp\s*/i, "")}, closing the circle
              </text>
            </g>
          ) : null}
        </svg>
      </div>
      <ul className="mt-sm space-y-xs">
        {junctions.map((junction) => (
          <li key={junction.index} className="rounded-md border border-line bg-mist p-sm" data-testid="junction-detail">
            <p className="text-sm font-medium text-ink">
              {junction.left_fragment} to {junction.right_fragment}: {junction.label}
            </p>
            <p className="mt-2xs break-all font-mono text-xs text-ink">{junction.sequence}</p>
            <p className="mt-2xs text-xs leading-5 text-slate">{junction.detail}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function OrderTable({ response }: { response: AssemblyDesignResponse }) {
  const rows = response.outputs.order_table;
  const tsv = orderTableTsv(rows);
  return (
    <section className="mt-md rounded-md border border-line-strong bg-paper shadow-raised" aria-labelledby="order-table-title" data-testid="order-table">
      <div className="flex flex-wrap items-center justify-between gap-sm border-b border-line bg-mist px-md py-sm">
        <h3 id="order-table-title" className="font-serif text-h3 text-ink">Order table</h3>
        <div className="flex flex-wrap items-center gap-xs">
          <CopyButton text={tsv} label="Copy table" />
          <button
            type="button"
            className={SECONDARY_BUTTON}
            onClick={() => downloadText(`${response.design_id}-order-table.csv`, response.outputs.order_table_csv, "text/csv")}
          >
            Export CSV
          </button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-left text-sm">
          <caption className="sr-only">Primers to order, sequences written 5&apos; to 3&apos;</caption>
          <thead>
            <tr className="border-b border-line text-caption uppercase tracking-[0.06em] text-slate">
              <th scope="col" className="px-md py-sm font-semibold">Primer</th>
              <th scope="col" className="px-md py-sm font-semibold">Sequence (5&apos; to 3&apos;)</th>
              <th scope="col" className="px-md py-sm text-right font-semibold">Length (nt)</th>
              <th scope="col" className="px-md py-sm text-right font-semibold">Tm (C)</th>
              <th scope="col" className="px-md py-sm text-right font-semibold">GC (%)</th>
              <th scope="col" className="px-md py-sm font-semibold">Notes</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.name} className="border-b border-line align-top last:border-b-0" data-testid="order-row">
                <th scope="row" className="px-md py-sm font-medium text-ink">{row.name}</th>
                <td className="px-md py-sm">
                  <code className="break-all font-mono text-xs text-ink [user-select:all]">{row.sequence_5_to_3}</code>
                </td>
                <td className="px-md py-sm text-right tabular-nums text-ink">{row.length_nt}</td>
                <td className="px-md py-sm text-right tabular-nums text-ink">{row.tm_c}</td>
                <td className="px-md py-sm text-right tabular-nums text-ink">{row.gc_percent}</td>
                <td className="px-md py-sm text-xs leading-5 text-slate">{row.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function StepTable({ steps, label }: { steps: ThermocyclingStep[]; label: string }) {
  return (
    <table className="mt-xs w-full border-collapse text-left text-small">
      <caption className="sr-only">{label}</caption>
      <thead>
        <tr className="border-b border-line text-caption uppercase tracking-[0.06em] text-slate">
          <th scope="col" className="py-xs pr-md font-semibold">Step</th>
          <th scope="col" className="py-xs pr-md text-right font-semibold">Temperature (C)</th>
          <th scope="col" className="py-xs pr-md text-right font-semibold">Seconds</th>
          <th scope="col" className="py-xs text-right font-semibold">Cycles</th>
        </tr>
      </thead>
      <tbody>
        {steps.map((step, index) => (
          <tr key={index} className="border-b border-line last:border-b-0">
            <td className="py-xs pr-md text-ink">{step.label}</td>
            <td className="py-xs pr-md text-right tabular-nums text-ink">{step.temperature_c}</td>
            <td className="py-xs pr-md text-right tabular-nums text-ink">{step.seconds}</td>
            <td className="py-xs text-right tabular-nums text-ink">{step.cycles}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ProtocolCard({ response }: { response: AssemblyDesignResponse }) {
  const protocol = response.outputs.protocol;
  return (
    <Card title="Protocol">
      <ul className="space-y-xs text-small leading-5 text-slate">
        {protocol.reaction_composition.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <p className="mt-sm text-sm font-semibold text-ink">Annealing temperature: {protocol.annealing_temperature_c} C</p>
      <p className="mt-2xs text-small leading-5 text-slate">{protocol.annealing_rule}</p>
      <StepTable steps={protocol.pcr_program} label="PCR thermocycling program" />
      {protocol.assembly_program.length ? <StepTable steps={protocol.assembly_program} label="Assembly reaction program" /> : null}
      <p className="mt-sm text-small leading-5 text-slate">
        <span className="font-semibold text-ink">Expected outcome: </span>
        {protocol.expected_outcome}
      </p>
      {protocol.sources.length ? (
        <details className="mt-sm text-xs text-slate">
          <summary className="cursor-pointer font-semibold text-coral focus:outline-none focus:ring-2 focus:ring-coral/40">Sources</summary>
          <ul className="mt-2xs space-y-2xs">
            {protocol.sources.map((source) => (
              <li key={source}>{source}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </Card>
  );
}

function DomesticationCard({ response }: { response: AssemblyDesignResponse }) {
  const report = response.outputs.domestication;
  if (!report) {
    return null;
  }
  return (
    <Card title="Domestication report">
      <p className="text-small leading-5 text-slate">
        {report.enzyme} recognition site {report.recognition_site}: {report.sites_found} site{report.sites_found === 1 ? "" : "s"} found,{" "}
        {report.edits.length} silent edit{report.edits.length === 1 ? "" : "s"} proposed, {report.unresolved.length} unresolved.
      </p>
      {report.edits.length ? (
        <ul className="mt-sm space-y-xs text-small text-slate">
          {report.edits.map((edit, index) => (
            <li key={index} className="rounded-md border border-line bg-mist p-sm">
              <span className="font-medium text-ink">{edit.fragment}</span> position {edit.edit_position + 1}: {edit.original_base} to {edit.proposed_base}
              {edit.in_coding_sequence && edit.original_codon
                ? `, codon ${edit.original_codon} to ${edit.proposed_codon}${edit.amino_acid ? ` (${edit.amino_acid} preserved)` : ""}`
                : ""}
              {edit.host_frequency_status === "unknown" && edit.host_frequency_reason ? (
                <span className="mt-2xs block text-xs">Host codon usage not evaluated. {edit.host_frequency_reason}</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {report.unresolved.map((site, index) => (
        <p key={index} className="mt-xs text-small text-clay">{site.fragment}: {site.reason}</p>
      ))}
      {report.notes.map((note) => (
        <p key={note} className="mt-xs text-xs leading-5 text-slate">{note}</p>
      ))}
    </Card>
  );
}
