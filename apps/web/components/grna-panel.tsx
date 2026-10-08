"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { Card, EmptyPanel, PanelShell, ParametersUsed } from "@/components/capability-shared";
import { StatusBadge, ValidationReportPanel } from "@/components/validation-report";
import { getGrnaReference } from "@/lib/api";
import { adaptReport, type GrnaDesignResponse, type GrnaGuide, type GrnaOnTarget, type GrnaReference } from "@/lib/capabilities";

// Section 10.2, guide RNA: the target sequence with guide positions marked on both
// strands, then the ranked guide table with per-guide reasoning.
//
// Section 10.4 and section 16 govern the wording here:
//   1. The off-target space statement is rendered exactly as the API returns it, as
//      one unmodified string, at the top of the panel, on every guide's expanded
//      row, and in every export (the exports are the API's own text).
//   2. Every score names its model and says it is a prediction, not a measurement.
// Nothing in this file describes the off-target search or a score with an
// adjective of its own.

export function OffTargetStatement({ statement, compact = false }: { statement: string; compact?: boolean }) {
  return (
    <div
      className={`rounded-md border-l-4 border-coral bg-mist ${compact ? "p-sm" : "p-md"}`}
      role="note"
      aria-label="Off-target search space"
    >
      <p className="text-caption font-semibold uppercase tracking-[0.06em] text-slate">Off-target search space</p>
      <p className="mt-2xs text-sm leading-6 text-ink" data-testid="off-target-statement">{statement}</p>
    </div>
  );
}

const COMPLEMENT: Record<string, string> = { A: "T", T: "A", C: "G", G: "C", a: "t", t: "a", c: "g", g: "c" };

function complement(sequence: string): string {
  return Array.from(sequence, (base) => COMPLEMENT[base] ?? "N").join("");
}

function scoreCaption(onTarget: GrnaOnTarget): string {
  return onTarget.model_kind === "published_model"
    ? "Prediction from a published model, not a measurement"
    : "Labeled heuristic, not a published score and not a measurement";
}

function kindLabel(kind: GrnaOnTarget["model_kind"]): string {
  return kind === "published_model" ? "published model" : "labeled heuristic";
}

export function GrnaResultPanel({
  response,
  targetSequence,
  nuclease
}: {
  response: GrnaDesignResponse | null;
  targetSequence: string;
  nuclease?: string;
}) {
  if (!response) {
    return (
      <EmptyPanel
        id="grna-panel"
        title="Guide RNA targets"
        heading="No guides ranked"
        text="Paste a target sequence and rank guides to see their positions on both strands."
      />
    );
  }
  // Keyed by design so selection and expansion reset when a new result arrives.
  return <GrnaResultBody key={response.result.design_id} response={response} targetSequence={targetSequence} nuclease={nuclease} />;
}

function GrnaResultBody({
  response,
  targetSequence,
  nuclease
}: {
  response: GrnaDesignResponse;
  targetSequence: string;
  nuclease?: string;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const guides = response.result.guides_returned;
  const statement = response.off_target_space_statement;

  function toggle(guideId: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(guideId)) {
        next.delete(guideId);
      } else {
        next.add(guideId);
      }
      return next;
    });
  }

  function focusGuide(guideId: string) {
    setSelected(guideId);
    setExpanded((current) => new Set(current).add(guideId));
    window.requestAnimationFrame(() => {
      document.getElementById(`guide-row-${guideId}`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  }

  return (
    <PanelShell
      id="grna-panel"
      title="Guide RNA targets"
      subtitle={`${response.result.target_name} · ${targetSequence.length.toLocaleString()} nt · ${nuclease ?? response.result.nuclease} · ${guides.length} of ${response.result.guides_enumerated} enumerated guides shown`}
    >
      <div className="mt-md">
        <OffTargetStatement statement={statement} />
      </div>
      <TargetStrandView sequence={targetSequence} guides={guides} selected={selected} onSelect={focusGuide} />
      <ScoreDisclosure />
      <GuideTable guides={guides} selected={selected} expanded={expanded} onToggle={toggle} onSelect={setSelected} />
      {response.result.notes.length || response.result.rejected.length ? (
        <Card title="Not ranked or not searched">
          <ul className="space-y-2xs text-small leading-5 text-slate">
            {response.result.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
          {response.result.rejected.length ? (
            <details className="mt-sm text-small text-slate">
              <summary className="cursor-pointer font-semibold text-coral focus:outline-none focus:ring-2 focus:ring-coral/40">
                {response.result.rejected.length} guide{response.result.rejected.length === 1 ? "" : "s"} listed as not searched
              </summary>
              <ul className="mt-xs space-y-2xs">
                {response.result.rejected.map((item) => (
                  <li key={item.guide_id}>
                    <code className="font-mono text-xs text-ink">{item.spacer}</code>: {item.reason}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </Card>
      ) : null}
      <ParametersUsed parameters={response.result.parameters_used} />
    </PanelShell>
  );
}

// ---- Target sequence with guides on both strands ---------------------------

type Segment = { guide: GrnaGuide; spacerFrom: number; spacerTo: number; pamFrom: number; pamTo: number };

function assignLanes(segments: Segment[]): Segment[][] {
  const lanes: { segments: Segment[]; end: number }[] = [];
  const ordered = [...segments].sort((a, b) => Math.min(a.spacerFrom, a.pamFrom) - Math.min(b.spacerFrom, b.pamFrom));
  for (const segment of ordered) {
    const from = Math.min(segment.spacerFrom, segment.pamFrom);
    const to = Math.max(segment.spacerTo, segment.pamTo);
    let lane = lanes.find((candidate) => candidate.end <= from);
    if (!lane) {
      lane = { segments: [], end: 0 };
      lanes.push(lane);
    }
    lane.segments.push(segment);
    lane.end = to;
  }
  return lanes.map((lane) => lane.segments);
}

function TargetStrandView({
  sequence,
  guides,
  selected,
  onSelect
}: {
  sequence: string;
  guides: GrnaGuide[];
  selected: string | null;
  onSelect: (guideId: string) => void;
}) {
  const lineLength = 60;
  const rows = useMemo(() => {
    const out: { start: number; end: number; forward: Segment[][]; reverse: Segment[][] }[] = [];
    for (let start = 0; start < sequence.length; start += lineLength) {
      const end = Math.min(sequence.length, start + lineLength);
      const forward: Segment[] = [];
      const reverse: Segment[] = [];
      for (const guide of guides) {
        const p = guide.placement;
        const from = Math.min(p.spacer_start, p.pam_start);
        const to = Math.max(p.spacer_end, p.pam_end);
        if (to <= start || from >= end) {
          continue;
        }
        const clip = (a: number, b: number): [number, number] => [Math.max(a, start) - start, Math.min(b, end) - start];
        const [spacerFrom, spacerTo] = clip(p.spacer_start, p.spacer_end);
        const [pamFrom, pamTo] = clip(p.pam_start, p.pam_end);
        const segment: Segment = { guide, spacerFrom, spacerTo, pamFrom, pamTo };
        (guide.strand === 1 ? forward : reverse).push(segment);
      }
      out.push({ start, end, forward: assignLanes(forward), reverse: assignLanes(reverse) });
    }
    return out;
  }, [sequence, guides]);

  return (
    <section className="mt-md rounded-md border border-line bg-paper shadow-rest" aria-labelledby="strand-view-title" data-testid="strand-view">
      <div className="border-b border-line bg-mist px-sm py-sm">
        <h3 id="strand-view-title" className="text-caption font-semibold uppercase tracking-[0.06em] text-slate">
          Target sequence and guide positions
        </h3>
      </div>
      <div className="overflow-x-auto p-md">
        <div className="space-y-md font-mono text-xs leading-5" style={{ width: `${lineLength + 8}ch` }}>
          {rows.map((row) => (
            <div key={row.start} className="flex gap-[1ch]" data-testid="strand-row">
              <div className="w-[7ch] shrink-0 text-right text-slate" aria-hidden="true">{row.start + 1}</div>
              <div className="relative" style={{ width: `${lineLength}ch` }}>
                <Lanes lanes={row.forward} strand={1} selected={selected} onSelect={onSelect} />
                <div className="whitespace-pre text-ink" style={{ letterSpacing: 0 }} aria-label={`Forward strand ${row.start + 1} to ${row.end}`}>
                  {sequence.slice(row.start, row.end)}
                </div>
                <div className="whitespace-pre text-slate" style={{ letterSpacing: 0 }} aria-hidden="true">
                  {complement(sequence.slice(row.start, row.end))}
                </div>
                <Lanes lanes={row.reverse} strand={-1} selected={selected} onSelect={onSelect} />
              </div>
            </div>
          ))}
        </div>
      </div>
      <p className="border-t border-line px-sm py-sm text-caption text-slate">
        Forward-strand guides are drawn above the sequence and reverse-strand guides below the complement. The lighter span
        is the 20 nt protospacer region and the darker span is the PAM. Select a guide to open its row.
      </p>
    </section>
  );
}

function Lanes({
  lanes,
  strand,
  selected,
  onSelect
}: {
  lanes: Segment[][];
  strand: 1 | -1;
  selected: string | null;
  onSelect: (guideId: string) => void;
}) {
  if (!lanes.length) {
    return null;
  }
  return (
    <div className="space-y-px py-px" data-strand={strand === 1 ? "forward" : "reverse"}>
      {lanes.map((lane, index) => (
        <div key={index} className="relative h-5">
          {lane.map(({ guide, spacerFrom, spacerTo, pamFrom, pamTo }) => {
            const isSelected = selected === guide.guide_id;
            const tone = strand === 1 ? "bg-coral/20 border-coral" : "bg-honey/20 border-honey";
            const pamTone = strand === 1 ? "bg-coral" : "bg-honey";
            return (
              <Fragment key={guide.guide_id}>
                {spacerTo > spacerFrom ? (
                  <button
                    type="button"
                    onClick={() => onSelect(guide.guide_id)}
                    aria-label={`Guide ${guide.rank}, ${guide.strand === 1 ? "forward" : "reverse"} strand, positions ${guide.placement.spacer_start + 1} to ${guide.placement.spacer_end}`}
                    aria-pressed={isSelected}
                    data-testid="guide-bar"
                    data-guide-id={guide.guide_id}
                    data-strand={guide.strand === 1 ? "forward" : "reverse"}
                    className={`absolute inset-y-0 flex items-center overflow-hidden border px-[0.5ch] text-[10px] font-semibold leading-none text-ink focus:outline-none focus:ring-2 focus:ring-coral/40 ${tone} ${isSelected ? "ring-2 ring-ink" : ""}`}
                    style={{ left: `${spacerFrom}ch`, width: `${spacerTo - spacerFrom}ch` }}
                  >
                    {guide.rank}
                  </button>
                ) : null}
                {pamTo > pamFrom ? (
                  <span
                    className={`absolute inset-y-0 ${pamTone}`}
                    style={{ left: `${pamFrom}ch`, width: `${pamTo - pamFrom}ch` }}
                    title={`PAM ${guide.pam}`}
                    aria-hidden="true"
                  />
                ) : null}
              </Fragment>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// ---- Score disclosure -----------------------------------------------------

function ScoreDisclosure() {
  const [reference, setReference] = useState<GrnaReference | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    getGrnaReference()
      .then((value) => {
        if (!cancelled) {
          setReference(value);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Card title="Scores and models">
      {reference ? (
        <ul className="space-y-sm" data-testid="score-reference">
          {reference.scores.map((score) => (
            <li key={score.name} className="rounded-md border border-line bg-mist p-sm">
              <p className="text-sm font-semibold text-ink">
                {score.name} <span className="font-normal text-slate">({score.kind === "published_model" ? "published model" : "labeled heuristic"})</span>
              </p>
              <p className="mt-2xs text-small text-slate">{score.role}: {score.wording}.</p>
              <details className="mt-2xs text-xs text-slate">
                <summary className="cursor-pointer font-semibold text-coral focus:outline-none focus:ring-2 focus:ring-coral/40">
                  Validity domain and citation
                </summary>
                <p className="mt-2xs leading-5"><span className="font-semibold text-ink">Validity domain: </span>{score.validity_domain}</p>
                <p className="mt-2xs leading-5"><span className="font-semibold text-ink">Citation: </span>{score.citation}</p>
              </details>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-small leading-5 text-slate">
          {failed
            ? "The score reference could not be loaded. Each guide below still states its own model, its kind and that the score is a prediction."
            : "Loading the score reference..."}
        </p>
      )}
    </Card>
  );
}

// ---- Ranked guide table ---------------------------------------------------

function GuideTable({
  guides,
  selected,
  expanded,
  onToggle,
  onSelect
}: {
  guides: GrnaGuide[];
  selected: string | null;
  expanded: Set<string>;
  onToggle: (guideId: string) => void;
  onSelect: (guideId: string | null) => void;
}) {
  return (
    <section className="mt-md rounded-md border border-line-strong bg-paper shadow-raised" aria-labelledby="guide-table-title" data-testid="guide-table">
      <div className="border-b border-line bg-mist px-sm py-sm">
        <h3 id="guide-table-title" className="font-serif text-h3 text-ink">Ranked guides</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse text-left text-sm">
          <caption className="sr-only">Guides ranked by the on-target model named in each row</caption>
          <thead>
            <tr className="border-b border-line text-caption uppercase tracking-[0.06em] text-slate">
              <th scope="col" className="px-sm py-sm font-semibold">Rank</th>
              <th scope="col" className="px-sm py-sm font-semibold">Spacer (5&apos; to 3&apos;), PAM, strand, position</th>
              <th scope="col" className="px-sm py-sm font-semibold">On-target prediction</th>
              <th scope="col" className="px-sm py-sm font-semibold">Off-target, searched space only</th>
              <th scope="col" className="px-sm py-sm font-semibold">Checks</th>
            </tr>
          </thead>
          <tbody>
            {guides.map((guide) => {
              const open = expanded.has(guide.guide_id);
              const offHits = guide.off_target.hits.filter((hit) => !hit.is_on_target).length;
              const unknown = guide.report.checks.filter((check) => check.severity === "unknown").length;
              return (
                <Fragment key={guide.guide_id}>
                  <tr
                    id={`guide-row-${guide.guide_id}`}
                    className={`border-b border-line align-top ${selected === guide.guide_id ? "bg-mist" : ""}`}
                    data-testid="guide-row"
                    onClick={() => onSelect(guide.guide_id)}
                  >
                    <td className="px-sm py-sm font-semibold tabular-nums text-ink">{guide.rank}</td>
                    <td className="px-sm py-sm">
                      <code className="font-mono text-xs text-ink [user-select:all]">
                        {guide.spacer}
                        <span className="text-coral"> {guide.pam}</span>
                      </code>
                      <span className="mt-2xs block text-caption text-slate">
                        {guide.strand === 1 ? "+ forward" : "- reverse"} strand, {guide.placement.spacer_start + 1}..{guide.placement.spacer_end}, cut after {guide.placement.cut_site}
                      </span>
                      {guide.pam_is_alternative ? (
                        <span className="mt-2xs block text-caption text-slate">Alternative PAM ({guide.pam_motif})</span>
                      ) : null}
                    </td>
                    <td className="px-sm py-sm" data-testid="on-target-cell">
                      {guide.on_target.score !== null ? (
                        <span className="font-semibold tabular-nums text-ink">{guide.on_target.score.toFixed(1)}</span>
                      ) : (
                        <span className="text-slate">No score</span>
                      )}
                      <span className="block text-caption text-ink">{guide.on_target.model_name}</span>
                      <span className="block text-caption text-slate">
                        {kindLabel(guide.on_target.model_kind)}. {scoreCaption(guide.on_target)}.
                      </span>
                      {guide.on_target.status === "out_of_domain" ? (
                        <span className="block text-caption text-honey">Outside the model&apos;s validity domain</span>
                      ) : null}
                    </td>
                    <td className="px-sm py-sm text-small text-ink">
                      {guide.off_target.searched ? (
                        <>
                          {offHits} other site{offHits === 1 ? "" : "s"} in the searched space
                          {guide.off_target.specificity_score !== null ? (
                            <span className="block text-caption text-slate">
                              {guide.off_target.specificity_model_name}: {guide.off_target.specificity_score.toFixed(1)}. Prediction, not a measurement.
                            </span>
                          ) : null}
                        </>
                      ) : (
                        <span className="text-slate">Not searched</span>
                      )}
                    </td>
                    <td className="px-sm py-sm">
                      <StatusBadge status={guide.report.overall} />
                      {unknown ? <span className="mt-2xs block text-caption text-ink">{unknown} not evaluated</span> : null}
                      <button
                        type="button"
                        aria-expanded={open}
                        aria-controls={`guide-detail-${guide.guide_id}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          onToggle(guide.guide_id);
                        }}
                        className="mt-xs rounded-md border border-line-strong bg-paper px-sm py-2xs text-xs font-semibold text-ink hover:bg-mist focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40"
                      >
                        {open ? "Hide reasoning" : "Show reasoning"}
                      </button>
                    </td>
                  </tr>
                  {open ? (
                    <tr className="border-b border-line bg-cream" data-testid="guide-detail">
                      <td colSpan={5} className="px-md py-md" id={`guide-detail-${guide.guide_id}`}>
                        <GuideDetail guide={guide} />
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function GuideDetail({ guide }: { guide: GrnaGuide }) {
  const onTarget = guide.on_target;
  const offTarget = guide.off_target;
  return (
    <div className="space-y-md">
      <OffTargetStatement statement={offTarget.space_statement} compact />

      <div>
        <h4 className="text-caption font-semibold uppercase tracking-[0.06em] text-slate">Reasoning</h4>
        <ul className="mt-xs list-disc space-y-2xs pl-md text-small leading-5 text-slate">
          {guide.reasoning.map((line, index) => (
            <li key={index}>{line}</li>
          ))}
        </ul>
      </div>

      <div className="rounded-md border border-line bg-paper p-sm">
        <h4 className="text-caption font-semibold uppercase tracking-[0.06em] text-slate">On-target score</h4>
        <p className="mt-2xs text-sm text-ink">
          {onTarget.model_name} ({kindLabel(onTarget.model_kind)}):{" "}
          {onTarget.score !== null ? `${onTarget.score.toFixed(1)}, scale ${onTarget.score_scale}` : "no score reported"}
        </p>
        <p className="mt-2xs text-small text-slate">{onTarget.disclaimer}</p>
        {onTarget.caveats.map((caveat) => (
          <p key={caveat} className="mt-2xs text-small text-honey">{caveat}</p>
        ))}
        <details className="mt-2xs text-xs text-slate">
          <summary className="cursor-pointer font-semibold text-coral focus:outline-none focus:ring-2 focus:ring-coral/40">Validity domain and citation</summary>
          <p className="mt-2xs leading-5"><span className="font-semibold text-ink">Validity domain: </span>{onTarget.validity_domain}</p>
          <p className="mt-2xs leading-5"><span className="font-semibold text-ink">Citation: </span>{onTarget.citation}</p>
        </details>
        {onTarget.reasoning.length ? (
          <table className="mt-xs w-full border-collapse text-left text-xs">
            <caption className="sr-only">Features that moved the on-target score</caption>
            <thead>
              <tr className="border-b border-line text-caption uppercase tracking-[0.06em] text-slate">
                <th scope="col" className="py-2xs pr-sm font-semibold">Feature</th>
                <th scope="col" className="py-2xs pr-sm font-semibold">Direction</th>
                <th scope="col" className="py-2xs text-right font-semibold">Weight</th>
              </tr>
            </thead>
            <tbody>
              {onTarget.reasoning.map((item, index) => (
                <tr key={index} className="border-b border-line last:border-b-0">
                  <td className="py-2xs pr-sm text-ink" title={item.detail}>{item.feature}</td>
                  <td className="py-2xs pr-sm text-slate">{item.direction}</td>
                  <td className="py-2xs text-right tabular-nums text-slate">{item.weight.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>

      <div className="rounded-md border border-line bg-paper p-sm">
        <h4 className="text-caption font-semibold uppercase tracking-[0.06em] text-slate">Off-target sites in the searched space</h4>
        <p className="mt-2xs text-small text-slate">
          {offTarget.specificity_model_name}
          {offTarget.specificity_score !== null ? `: ${offTarget.specificity_score.toFixed(1)}. ` : ". "}
          {offTarget.disclaimer}
        </p>
        <p className="mt-2xs text-xs text-slate">
          Up to {offTarget.max_mismatches_searched} mismatches searched; seed region {offTarget.seed_region_nt} nt.
        </p>
        {offTarget.hits.length ? (
          <table className="mt-xs w-full border-collapse text-left text-xs">
            <caption className="sr-only">Sites matching the guide inside the searched space</caption>
            <thead>
              <tr className="border-b border-line text-caption uppercase tracking-[0.06em] text-slate">
                <th scope="col" className="py-2xs pr-sm font-semibold">Site</th>
                <th scope="col" className="py-2xs pr-sm font-semibold">Position</th>
                <th scope="col" className="py-2xs pr-sm font-semibold">Mismatches (seed)</th>
                <th scope="col" className="py-2xs text-right font-semibold">Site score</th>
              </tr>
            </thead>
            <tbody>
              {offTarget.hits.map((hit, index) => (
                <tr key={index} className="border-b border-line last:border-b-0">
                  <td className="py-2xs pr-sm text-ink">{hit.is_on_target ? "On-target site" : hit.source_label}</td>
                  <td className="py-2xs pr-sm tabular-nums text-slate">{hit.start + 1}..{hit.end}</td>
                  <td className="py-2xs pr-sm tabular-nums text-slate">{hit.mismatches} ({hit.seed_mismatches})</td>
                  <td className="py-2xs text-right tabular-nums text-slate">{hit.hit_score === null ? "none" : hit.hit_score.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>

      <ValidationReportPanel report={adaptReport(guide.report)} />

      {guide.cloning ? (
        <div className="rounded-md border border-line bg-paper p-sm">
          <h4 className="text-caption font-semibold uppercase tracking-[0.06em] text-slate">Cloning oligos, {guide.cloning.vector_name}</h4>
          <ul className="mt-xs space-y-xs">
            {guide.cloning.oligos.map((oligo) => (
              <li key={oligo.name} className="text-small">
                <span className="font-medium text-ink">{oligo.name}</span> <span className="text-slate">({oligo.length_nt} nt)</span>
                <code className="block break-all font-mono text-xs text-ink [user-select:all]">{oligo.sequence}</code>
                <span className="block text-xs text-slate">{oligo.role}</span>
              </li>
            ))}
          </ul>
          {guide.cloning.notes.map((note) => (
            <p key={note} className="mt-2xs text-xs leading-5 text-slate">{note}</p>
          ))}
        </div>
      ) : null}
    </div>
  );
}
