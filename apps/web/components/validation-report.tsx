import type { ValidationCheck, ValidationReport } from "@/lib/types";

// The one validation report component, shared by all four capabilities.
//
// It accepts the plasmid pipeline's report (`name`, `status`, `message`) and the
// capability `ValidationReport` (`label`, `severity`, `observed`, `threshold`,
// `citation`, `tier`) through the same `ValidationReport` type, so a plasmid and an
// AAV vector are read in the same way.
//
// Section 10.3: an UNKNOWN row must never be read as a PASS. UNKNOWN is therefore
// distinguished by label ("Not evaluated"), by glyph, by a dashed border and a
// hatched background, and by a count in the panel header, so colour is never the
// only signal.

export function normalizeStatus(status: string | undefined): string {
  return (status ?? "UNKNOWN").toUpperCase();
}

export function checkTitle(check: ValidationCheck): string {
  return check.name ?? check.check ?? check.category ?? "Validation check";
}

export function regionLabel(check: ValidationCheck): string | null {
  const explicitRegions = check.regions
    ?.map((region) => {
      if (typeof region.start !== "number" || typeof region.end !== "number") {
        return region.label ?? region.feature ?? null;
      }
      return `${region.label ?? region.feature ?? "region"} ${region.start + 1}..${region.end}`;
    })
    .filter(Boolean);
  if (explicitRegions?.length) {
    return explicitRegions.join(", ");
  }
  if (typeof check.start === "number" && typeof check.end === "number") {
    return `${check.start + 1}..${check.end}`;
  }
  return null;
}

const BADGE_BASE = "rounded-pill border px-xs py-2xs text-caption font-semibold uppercase tracking-[0.06em]";

export function StatusBadge({ status }: { status: string }) {
  const normalized = normalizeStatus(status);
  if (normalized === "UNKNOWN") {
    return (
      <span
        className={`${BADGE_BASE} border-dashed border-ink/50 bg-paper text-ink`}
        data-status="UNKNOWN"
        title="This check could not be evaluated. It is not a pass."
      >
        <span aria-hidden="true">? </span>Not evaluated
      </span>
    );
  }
  const className =
    normalized === "PASS"
      ? "border-sage/40 bg-sage/10 text-sage"
      : normalized === "WARN"
        ? "border-honey/40 bg-honey/10 text-honey"
        : normalized === "FAIL"
          ? "border-clay/40 bg-clay/10 text-clay"
          : "border-line-strong bg-mist text-slate";
  const glyph = normalized === "PASS" ? "✓ " : normalized === "WARN" ? "! " : normalized === "FAIL" ? "× " : "";
  return (
    <span className={`${BADGE_BASE} ${className}`} data-status={normalized}>
      <span aria-hidden="true">{glyph}</span>
      {normalized}
    </span>
  );
}

// A diagonal hatch marks a row that was not evaluated. Inline style because the
// gradient is not part of the Tailwind token set.
const UNKNOWN_ROW_STYLE = {
  backgroundImage:
    "repeating-linear-gradient(135deg, rgba(95,102,95,0.10) 0, rgba(95,102,95,0.10) 6px, transparent 6px, transparent 12px)"
} as const;

function reportOverall(report: ValidationReport): string {
  const checks = report.checks ?? [];
  return (
    report.overall ??
    (checks.some((check) => normalizeStatus(check.status) === "FAIL")
      ? "FAIL"
      : checks.some((check) => normalizeStatus(check.status) === "WARN")
        ? "WARN"
        : "PASS")
  );
}

export function ValidationReportPanel({ report }: { report: ValidationReport }) {
  const checks = report.checks ?? [];
  const overall = reportOverall(report);
  const unknownCount = checks.filter((check) => normalizeStatus(check.status) === "UNKNOWN").length;
  return (
    <section className="mt-md rounded-md border border-line bg-mist p-md" aria-label="Validation report">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-caption font-semibold uppercase tracking-[0.06em] text-slate">Validation report</h3>
        <div className="flex flex-wrap items-center gap-xs">
          <StatusBadge status={overall} />
          {unknownCount ? (
            <span
              className="rounded-pill border border-dashed border-ink/50 bg-paper px-xs py-2xs text-caption font-semibold text-ink"
              data-testid="unknown-count"
            >
              {unknownCount} not evaluated
            </span>
          ) : null}
        </div>
      </div>
      {report.generated_by_model_version ? (
        <p className="mt-2xs text-xs text-slate">Model: {report.generated_by_model_version}</p>
      ) : null}
      {report.validator_version ? (
        <p className="mt-2xs text-xs text-slate">Validator version: {report.validator_version}</p>
      ) : null}
      {unknownCount ? (
        <p className="mt-sm rounded-md border border-dashed border-ink/40 bg-paper p-sm text-small leading-5 text-ink" role="note">
          {unknownCount} of {checks.length} checks could not be evaluated. A check that was not evaluated is not a pass, and
          the overall verdict above does not include it.
        </p>
      ) : null}
      {checks.length ? (
        <div className="mt-sm space-y-sm">
          {checks.map((check, index) => (
            <ValidationRow key={`${check.check_id ?? checkTitle(check)}-${index}`} check={check} />
          ))}
        </div>
      ) : (
        <p className="mt-sm text-small text-slate">No individual checks were returned.</p>
      )}
    </section>
  );
}

function ValidationRow({ check }: { check: ValidationCheck }) {
  const status = normalizeStatus(check.status ?? "PASS");
  const unknown = status === "UNKNOWN";
  const region = regionLabel(check);
  const hasComparison = Boolean(check.observed || check.threshold);
  return (
    <div
      className={`rounded-md border p-md ${unknown ? "border-dashed border-ink/50 bg-paper" : "border-line bg-paper"}`}
      style={unknown ? UNKNOWN_ROW_STYLE : undefined}
      data-severity={status}
      data-testid="validation-row"
      title={check.citation ?? undefined}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-ink">
          {checkTitle(check)}
          {check.tier === "B" ? (
            <span className="ml-xs rounded-sm border border-line-strong px-xs py-2xs text-caption font-semibold text-slate" title="Tier B: surfaced and explained, not a failure">
              Tier B
            </span>
          ) : null}
        </p>
        <StatusBadge status={status} />
      </div>
      {check.message ? (
        <p className="mt-2xs text-small leading-5 text-slate">
          {unknown ? <span className="font-semibold text-ink">Not evaluated. </span> : null}
          {check.message}
        </p>
      ) : null}
      {hasComparison ? (
        <dl className="mt-2xs grid gap-2xs text-xs text-slate sm:grid-cols-2">
          {check.observed ? (
            <div>
              <dt className="inline font-semibold text-ink">Observed: </dt>
              <dd className="inline break-words">{check.observed}</dd>
            </div>
          ) : null}
          {check.threshold ? (
            <div>
              <dt className="inline font-semibold text-ink">Threshold: </dt>
              <dd className="inline break-words">{check.threshold}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}
      {region ? <p className="mt-2xs text-xs text-slate">Region: {region}</p> : null}
      {check.citation ? (
        <details className="mt-2xs text-xs text-slate">
          <summary className="cursor-pointer font-semibold text-coral focus:outline-none focus:ring-2 focus:ring-coral/40">
            Citation
          </summary>
          <p className="mt-2xs leading-5">{check.citation}</p>
        </details>
      ) : null}
    </div>
  );
}
