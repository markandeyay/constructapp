"use client";

import { Card, EmptyPanel, PanelShell, ParametersUsed, SECONDARY_BUTTON } from "@/components/capability-shared";
import { componentColor } from "@/lib/component-colors";
import {
  parseLinearMap,
  type AavDesignResponse,
  type AavLengthBudget,
  type AavLinearMap,
  type AavMapElement,
  type RemediationChange,
  type RemediationPlan
} from "@/lib/capabilities";

// Section 10.2, AAV: a LINEAR cassette map with the elements drawn to scale, and
// the length budget table beneath it. An AAV genome is a linear single-stranded
// cassette between two ITRs, so this panel never uses the circular plasmid
// renderer (section 10.2: doing so would be a visible error to anyone in the field).

const ROLE_FEATURE_TYPE: Record<string, string> = {
  itr_5: "MCS",
  itr_3: "MCS",
  enhancer: "marker",
  promoter: "promoter",
  intron: "ORI",
  kozak: "other",
  cds: "GOI",
  wpre: "marker",
  polya: "terminator"
};

const ROLE_LABEL: Record<string, string> = {
  itr_5: "5' ITR",
  itr_3: "3' ITR",
  enhancer: "Enhancer",
  promoter: "Promoter",
  intron: "Intron",
  kozak: "Kozak",
  cds: "Coding sequence",
  wpre: "WPRE",
  polya: "polyA"
};

function roleColor(role: string): string {
  return componentColor(ROLE_FEATURE_TYPE[role] ?? "other");
}

function shortName(element: { role: string; name: string }): string {
  if (element.role === "itr_5" || element.role === "itr_3") {
    return ROLE_LABEL[element.role];
  }
  return element.name.replace(/\s*\([^)]*\)\s*/g, " ").trim();
}

function mapFromBudget(budget: AavLengthBudget): AavLinearMap {
  let start = 0;
  return {
    elements: budget.rows.map((row) => {
      const element: AavMapElement = {
        index: row.index,
        role: row.role,
        name: row.name,
        part_id: row.part_id,
        length_bp: row.length_bp,
        start,
        end: start + row.length_bp,
        start_1based: start + 1,
        end_1based: start + row.length_bp,
        fraction_of_cassette: budget.total_bp ? row.length_bp / budget.total_bp : 0
      };
      start += row.length_bp;
      return element;
    }),
    total_bp: budget.total_bp,
    target_bp: budget.target_bp,
    soft_limit_bp: budget.soft_limit_bp,
    hard_limit_bp: budget.hard_limit_bp,
    topology: "linear",
    self_complementary: budget.self_complementary
  };
}

function fmt(value: number): string {
  return value.toLocaleString();
}

function niceStep(span: number): number {
  const rough = span / 6;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rough)));
  const normalized = rough / magnitude;
  const factor = normalized >= 5 ? 5 : normalized >= 2 ? 2 : 1;
  return factor * magnitude;
}

export function AavResultPanel({
  response,
  onApplyPlan,
  onUseAsFragments
}: {
  response: AavDesignResponse | null;
  onApplyPlan?: (plan: RemediationPlan) => void;
  onUseAsFragments?: () => void;
}) {
  if (!response) {
    return (
      <EmptyPanel
        id="aav-panel"
        title="AAV cassette map"
        heading="No cassette composed"
        text="Enter a transgene and compose a cassette to see the linear map and the length budget."
      />
    );
  }
  const map = parseLinearMap(response) ?? mapFromBudget(response.length_budget);
  const budget = response.length_budget;
  const plans = response.remediation.plans;
  return (
    <PanelShell
      id="aav-panel"
      title="AAV cassette map"
      subtitle={`${fmt(budget.total_bp)} bp · linear cassette${map.serotype ? ` · ${map.serotype}` : ""}${budget.self_complementary ? " · self-complementary" : ""}`}
      badge={
        <span className="rounded-pill border border-line-strong bg-mist px-xs py-2xs text-caption font-semibold uppercase tracking-[0.06em] text-slate" data-testid="topology-badge">
          Linear
        </span>
      }
    >
      <LinearCassetteMap map={map} />
      <LengthBudgetTable budget={budget} axisMax={Math.max(budget.total_bp, budget.hard_limit_bp)} />
      {plans.length ? <RemediationCard response={response} onApplyPlan={onApplyPlan} /> : null}
      {response.notes.length ? (
        <Card title="Composition notes">
          <ul className="space-y-2xs text-small leading-5 text-slate">
            {response.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </Card>
      ) : null}
      {onUseAsFragments ? (
        <div className="mt-md">
          <button type="button" onClick={onUseAsFragments} className={SECONDARY_BUTTON}>
            Use these elements as assembly fragments
          </button>
        </div>
      ) : null}
      <ParametersUsed parameters={response.result.parameters_used} />
    </PanelShell>
  );
}

type PlacedLabel = { element: AavMapElement; center: number; lane: number; text: string; half: number };

function LinearCassetteMap({ map }: { map: AavLinearMap }) {
  const width = 800;
  const padX = 24;
  const plotWidth = width - padX * 2;
  const axisMax = Math.max(map.total_bp, map.hard_limit_bp);
  const x = (bp: number) => padX + (bp / axisMax) * plotWidth;
  const barTop = 74;
  const barHeight = 44;
  const barBottom = barTop + barHeight;
  const tip = 10;

  // Labels sit beneath the bars on lanes so that narrow elements stay legible.
  const labelFont = 7.4;
  const placed: PlacedLabel[] = [];
  const laneEnds: number[] = [];
  for (const element of map.elements) {
    const text = `${shortName(element)}`;
    const half = (Math.max(text.length, `${fmt(element.length_bp)} bp`.length) * labelFont) / 2;
    const center = (x(element.start) + x(element.end)) / 2;
    let lane = laneEnds.findIndex((end) => center - half > end + 8);
    if (lane === -1) {
      lane = laneEnds.length;
      laneEnds.push(0);
    }
    laneEnds[lane] = center + half;
    placed.push({ element, center, lane, text, half });
  }
  const laneHeight = 38;
  const axisY = barBottom + 14;
  const labelsTop = axisY + 34;
  const height = labelsTop + laneEnds.length * laneHeight + 8;

  const step = niceStep(axisMax);
  const ticks: number[] = [];
  for (let bp = 0; bp <= axisMax; bp += step) {
    ticks.push(bp);
  }

  const over = map.total_bp > map.target_bp;
  const limits = [
    { key: "target", bp: map.target_bp, label: `${fmt(map.target_bp)} target`, anchor: "end" as const, row: 0 },
    { key: "soft", bp: map.soft_limit_bp, label: `${fmt(map.soft_limit_bp)} soft limit`, anchor: "middle" as const, row: 1 },
    { key: "hard", bp: map.hard_limit_bp, label: `${fmt(map.hard_limit_bp)} hard limit`, anchor: "end" as const, row: 2 }
  ];

  return (
    <div className="mt-md rounded-md border border-line bg-paper p-sm shadow-rest" data-testid="aav-linear-map" data-topology={map.topology}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Linear AAV cassette map, ${fmt(map.total_bp)} base pairs, ${map.elements.length} elements drawn to scale`}
      >
        <defs>
          <pattern id="aav-over-hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="8" height="8" fill="rgba(123,61,69,0.18)" />
            <line x1="0" y1="0" x2="0" y2="8" stroke="#7b3d45" strokeWidth="2" />
          </pattern>
        </defs>

        {limits.map((limit) => (
          <g key={limit.key} data-limit={limit.key}>
            <line x1={x(limit.bp)} x2={x(limit.bp)} y1={20 + limit.row * 16} y2={barBottom + 6} stroke="#5f665f" strokeWidth="1" strokeDasharray="4 3" />
            <text
              x={limit.anchor === "end" ? x(limit.bp) - 4 : x(limit.bp)}
              y={16 + limit.row * 16}
              textAnchor={limit.anchor}
              fontSize="12"
              fill="#5f665f"
            >
              {limit.label}
            </text>
          </g>
        ))}

        {map.elements.map((element) => {
          const x0 = x(element.start);
          const x1 = x(element.end);
          const forward = element.role !== "itr_3";
          const t = Math.min(tip, (x1 - x0) / 2);
          const points = forward
            ? `${x0},${barTop} ${x1 - t},${barTop} ${x1},${barTop + barHeight / 2} ${x1 - t},${barBottom} ${x0},${barBottom}`
            : `${x0 + t},${barTop} ${x1},${barTop} ${x1},${barBottom} ${x0 + t},${barBottom} ${x0},${barTop + barHeight / 2}`;
          return (
            <polygon
              key={`${element.index}-${element.start}`}
              points={points}
              fill={roleColor(element.role)}
              stroke="#fffffc"
              strokeWidth="1.5"
              data-testid="aav-element"
              data-role={element.role}
              data-start={element.start}
              data-end={element.end}
            >
              <title>{`${element.name}: ${fmt(element.length_bp)} bp (${fmt(element.start_1based)}..${fmt(element.end_1based)})`}</title>
            </polygon>
          );
        })}

        {over ? (
          <rect
            x={x(map.target_bp)}
            y={barTop - 4}
            width={Math.max(0, x(map.total_bp) - x(map.target_bp))}
            height={barHeight + 8}
            fill="url(#aav-over-hatch)"
            stroke="#7b3d45"
            strokeWidth="1"
            pointerEvents="none"
            data-testid="aav-over-target"
          />
        ) : null}

        <line x1={x(0)} x2={x(axisMax)} y1={axisY} y2={axisY} stroke="#c9cbc2" strokeWidth="1" />
        {ticks.map((bp) => (
          <g key={bp}>
            <line x1={x(bp)} x2={x(bp)} y1={axisY} y2={axisY + 4} stroke="#c9cbc2" strokeWidth="1" />
            <text x={x(bp)} y={axisY + 15} textAnchor="middle" fontSize="11" fill="#5f665f">
              {fmt(bp)}
            </text>
          </g>
        ))}

        {placed.map(({ element, center, lane, text, half }) => {
          const y = labelsTop + lane * laneHeight;
          const textX = Math.min(width - padX - half, Math.max(padX + half, center));
          return (
            <g key={`label-${element.index}`}>
              <line x1={center} x2={center} y1={barBottom} y2={y - 11} stroke="#c9cbc2" strokeWidth="1" />
              <text x={textX} y={y} textAnchor="middle" fontSize="13" fontWeight="600" fill="#1f2320">
                {text}
              </text>
              <text x={textX} y={y + 15} textAnchor="middle" fontSize="12" fill="#5f665f">
                {fmt(element.length_bp)} bp
              </text>
            </g>
          );
        })}
      </svg>
      <p className="mt-xs text-caption text-slate">
        Drawn to scale on a {fmt(axisMax)} bp axis. Arrowheads show orientation; the two ITRs point towards each other.
        {over ? " The hatched span is the part of the cassette beyond the packaging target." : ""}
      </p>
    </div>
  );
}

export function LengthBudgetTable({ budget, axisMax }: { budget: AavLengthBudget; axisMax: number }) {
  const over = budget.total_bp > budget.target_bp;
  return (
    <section className="mt-md rounded-md border border-line-strong bg-paper shadow-raised" aria-labelledby="length-budget-title" data-testid="length-budget">
      <div className="flex flex-wrap items-center justify-between gap-sm border-b border-line bg-mist px-md py-sm">
        <h3 id="length-budget-title" className="font-serif text-h3 text-ink">Length budget</h3>
        <div className="flex flex-wrap gap-xs text-caption">
          <LimitChip label="Target" value={budget.target_bp} />
          <LimitChip label="Soft limit" value={budget.soft_limit_bp} />
          <LimitChip label="Hard limit" value={budget.hard_limit_bp} />
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-left text-sm">
          <caption className="sr-only">
            Element lengths with running total and headroom against the {fmt(budget.target_bp)} bp packaging target
          </caption>
          <thead>
            <tr className="border-b border-line text-caption uppercase tracking-[0.06em] text-slate">
              <th scope="col" className="px-md py-sm font-semibold">Element</th>
              <th scope="col" className="px-md py-sm text-right font-semibold">bp</th>
              <th scope="col" className="px-md py-sm font-semibold">Running total</th>
              <th scope="col" className="px-md py-sm text-right font-semibold">Headroom to target</th>
            </tr>
          </thead>
          <tbody>
            {budget.rows.map((row) => {
              const rowOver = row.headroom_bp < 0;
              return (
                <tr key={`${row.index}-${row.part_id ?? row.name}`} className="border-b border-line last:border-b-0" data-testid="budget-row">
                  <th scope="row" className="px-md py-sm font-medium text-ink">
                    <span className="block">{shortName(row)}</span>
                    <span className="block text-caption font-normal text-slate">
                      {ROLE_LABEL[row.role] ?? row.role}
                      {row.part_id ? ` · ${row.part_id}` : " · supplied sequence"}
                    </span>
                  </th>
                  <td className="px-md py-sm text-right tabular-nums text-ink">{fmt(row.length_bp)}</td>
                  <td className="px-md py-sm">
                    <div className="flex items-center gap-sm">
                      <span className="w-16 shrink-0 text-right tabular-nums text-ink">{fmt(row.running_total_bp)}</span>
                      <span className="relative h-2 min-w-[80px] flex-1 rounded-pill bg-mist" aria-hidden="true">
                        <span
                          className={`absolute inset-y-0 left-0 rounded-pill ${rowOver ? "bg-clay/70" : "bg-coral/60"}`}
                          style={{ width: `${Math.min(100, (row.running_total_bp / axisMax) * 100)}%` }}
                        />
                        <span
                          className="absolute -inset-y-0.5 w-px bg-ink/60"
                          style={{ left: `${(budget.target_bp / axisMax) * 100}%` }}
                        />
                      </span>
                    </div>
                  </td>
                  <td className={`px-md py-sm text-right tabular-nums ${rowOver ? "font-semibold text-clay" : "text-ink"}`}>
                    {rowOver ? `${fmt(Math.abs(row.headroom_bp))} over` : fmt(row.headroom_bp)}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-line-strong bg-mist">
              <th scope="row" className="px-md py-sm font-semibold text-ink">Total, 5&apos; ITR through 3&apos; ITR</th>
              <td className="px-md py-sm text-right font-semibold tabular-nums text-ink" data-testid="budget-total">{fmt(budget.total_bp)}</td>
              <td className="px-md py-sm text-small text-slate">of {fmt(budget.target_bp)} bp target</td>
              <td className={`px-md py-sm text-right font-semibold tabular-nums ${over ? "text-clay" : "text-ink"}`} data-testid="budget-headroom">
                {over ? `${fmt(Math.abs(budget.headroom_bp))} over` : fmt(budget.headroom_bp)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="border-t border-line px-md py-sm text-small leading-5 text-slate">{budget.limit_basis}</p>
    </section>
  );
}

function LimitChip({ label, value }: { label: string; value: number }) {
  return (
    <span className="rounded-pill border border-line-strong bg-paper px-xs py-2xs font-semibold text-slate">
      {label} <span className="tabular-nums text-ink">{fmt(value)} bp</span>
    </span>
  );
}

function describeChange(change: RemediationChange): string {
  if (change.kind === "remove") {
    return `Remove ${change.from_name}, saving ${fmt(change.saved_bp)} bp`;
  }
  return `Replace ${change.from_name} with ${change.to_name ?? "a shorter part"}, saving ${fmt(change.saved_bp)} bp`;
}

export function planIsApplicable(plan: RemediationPlan): boolean {
  return plan.changes.every(
    (change) =>
      (change.kind === "substitute" && Boolean(change.to_part_id) && (change.role === "promoter" || change.role === "polya")) ||
      (change.kind === "remove" && change.role === "wpre")
  );
}

function RemediationCard({
  response,
  onApplyPlan
}: {
  response: AavDesignResponse;
  onApplyPlan?: (plan: RemediationPlan) => void;
}) {
  const remediation = response.remediation;
  return (
    <Card title="Changes that close the gap">
      <p className="text-small leading-5 text-slate">
        The cassette is {fmt(remediation.total_bp)} bp against a {fmt(remediation.target_bp)} bp target
        {remediation.overage_bp > 0 ? `, ${fmt(remediation.overage_bp)} bp over.` : "."}{" "}
        Each option below is computed from the part registry.
      </p>
      <ol className="mt-sm space-y-sm">
        {remediation.plans.map((plan, index) => (
          <li key={index} className="rounded-md border border-line bg-mist p-md" data-testid="remediation-plan">
            <ul className="space-y-2xs text-sm text-ink">
              {plan.changes.map((change, changeIndex) => (
                <li key={changeIndex}>{describeChange(change)}</li>
              ))}
            </ul>
            <p className="mt-xs text-small text-slate">
              Result: {fmt(plan.resulting_bp)} bp, {fmt(Math.abs(plan.resulting_headroom_bp))} bp{" "}
              {plan.resulting_headroom_bp >= 0 ? "under" : "over"} the target.
              {plan.preserves_promoter_preference ? " Keeps your stated promoter." : ""}
            </p>
            {plan.changes.map((change, changeIndex) => (
              <p key={changeIndex} className="mt-2xs text-xs leading-5 text-slate">{change.tradeoff}</p>
            ))}
            {onApplyPlan && planIsApplicable(plan) ? (
              <button type="button" onClick={() => onApplyPlan(plan)} className={`mt-sm ${SECONDARY_BUTTON}`}>
                Apply this change and recompose
              </button>
            ) : null}
          </li>
        ))}
      </ol>
      {remediation.remaining_deficit_bp ? (
        <p className="mt-sm text-small leading-5 text-slate">
          No combination of registry substitutions closes the gap. {fmt(remediation.remaining_deficit_bp)} bp remain over the target.
        </p>
      ) : null}
    </Card>
  );
}
