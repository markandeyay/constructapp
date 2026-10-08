"use client";

import type { ReactNode } from "react";
import { CAPABILITY_OPTIONS, type AavParts, type CapabilityKind, type GrnaReference } from "@/lib/capabilities";
import {
  EDIT_INTENT_OPTIONS,
  FALLBACK_NUCLEASES,
  TISSUE_OPTIONS,
  newFragment,
  type AavFormState,
  type AssemblyFormState,
  type GrnaFormState
} from "@/lib/use-capabilities";

// Section 10.1: the capability selector and the per-capability request forms.
// Field, input and button classes are the ones the plasmid composer already uses.

const INPUT_CLASS =
  "w-full rounded-md border border-line bg-paper px-sm py-xs text-sm text-ink shadow-rest outline-none focus:border-coral focus:ring-2 focus:ring-coral/40 disabled:cursor-not-allowed disabled:bg-mist";
const PRIMARY_BUTTON =
  "mt-2 h-10 w-full rounded-md border border-coral bg-coral px-sm text-sm font-semibold text-paper shadow-rest hover:shadow-raised focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40 disabled:cursor-not-allowed disabled:border-line disabled:bg-line disabled:text-slate disabled:shadow-none";

export function CapabilitySelector({
  value,
  onChange,
  disabled
}: {
  value: CapabilityKind;
  onChange: (kind: CapabilityKind) => void;
  disabled?: boolean;
}) {
  return (
    <div className="shrink-0 border-b border-line px-md py-sm">
      <div role="radiogroup" aria-label="Capability" className="grid grid-cols-2 gap-xs rounded-md bg-mist p-2xs">
        {CAPABILITY_OPTIONS.map((option) => {
          const checked = option.kind === value;
          return (
            <button
              key={option.kind}
              type="button"
              role="radio"
              aria-checked={checked}
              disabled={disabled}
              onClick={() => onChange(option.kind)}
              title={option.hint}
              data-capability={option.kind}
              className={`rounded-sm px-sm py-2xs text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-coral/40 disabled:cursor-not-allowed ${checked ? "bg-paper text-ink shadow-rest" : "text-slate hover:text-ink"}`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="block text-caption font-semibold uppercase tracking-[0.06em] text-slate">
        {label}
      </label>
      <div className="mt-2xs">{children}</div>
      {hint ? <p className="mt-2xs text-caption text-slate">{hint}</p> : null}
    </div>
  );
}

function Checkbox({ id, label, checked, onChange, disabled }: { id: string; label: string; checked: boolean; onChange: (value: boolean) => void; disabled?: boolean }) {
  return (
    <label htmlFor={id} className="flex items-center gap-xs text-sm text-ink">
      <input id={id} type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} className="h-4 w-4 accent-[#365f43]" />
      {label}
    </label>
  );
}

function FormShell({
  title,
  intro,
  error,
  busy,
  submitLabel,
  busyLabel,
  onSubmit,
  children
}: {
  title: string;
  intro: string;
  error: string | null;
  busy: boolean;
  submitLabel: string;
  busyLabel: string;
  onSubmit: () => void;
  children: ReactNode;
}) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (!busy) {
          onSubmit();
        }
      }}
      className="shrink-0 overflow-y-auto border-t border-line bg-paper px-sm py-sm"
      aria-label={title}
      aria-busy={busy}
    >
      <p className="mb-sm text-small leading-5 text-slate">{intro}</p>
      <div className="space-y-sm">{children}</div>
      {error ? (
        <p className="mt-sm rounded-md border border-clay/40 bg-clay/5 p-sm text-small leading-5 text-clay" role="alert">
          {error}
        </p>
      ) : null}
      <button type="submit" disabled={busy} className={PRIMARY_BUTTON}>
        {busy ? busyLabel : submitLabel}
      </button>
    </form>
  );
}

export function AavForm({
  form,
  setForm,
  parts,
  partsFailed,
  busy,
  error,
  onSubmit
}: {
  form: AavFormState;
  setForm: (next: AavFormState) => void;
  parts: AavParts | null;
  partsFailed: boolean;
  busy: boolean;
  error: string | null;
  onSubmit: () => void;
}) {
  const promoters = parts?.categories.promoter ?? [];
  const polyas = parts?.categories.polya ?? [];
  const update = (patch: Partial<AavFormState>) => setForm({ ...form, ...patch });
  return (
    <FormShell
      title="AAV vector request"
      intro="Supply the transgene coding sequence. The cassette is composed from registry parts and checked against the packaging limit."
      error={error}
      busy={busy}
      submitLabel="Compose cassette"
      busyLabel="Composing"
      onSubmit={onSubmit}
    >
      <Field id="aav-name" label="Transgene name">
        <input id="aav-name" value={form.transgeneName} onChange={(event) => update({ transgeneName: event.target.value })} className={INPUT_CLASS} disabled={busy} />
      </Field>
      <Field id="aav-sequence" label="Transgene coding sequence" hint="DNA, ATG through stop. A FASTA header line is ignored.">
        <textarea
          id="aav-sequence"
          value={form.transgeneSequence}
          onChange={(event) => update({ transgeneSequence: event.target.value })}
          rows={4}
          spellCheck={false}
          className={`${INPUT_CLASS} resize-none font-mono text-xs`}
          disabled={busy}
        />
      </Field>
      <Field id="aav-tissue" label="Target tissue">
        <select id="aav-tissue" value={form.targetTissue} onChange={(event) => update({ targetTissue: event.target.value })} className={INPUT_CLASS} disabled={busy}>
          {TISSUE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </Field>
      <Field id="aav-promoter" label="Promoter" hint={partsFailed ? "The part list could not be loaded. Automatic selection will be used." : undefined}>
        <select id="aav-promoter" value={form.promoter} onChange={(event) => update({ promoter: event.target.value })} className={INPUT_CLASS} disabled={busy}>
          <option value="">Automatic, from target tissue</option>
          {promoters.map((part) => (
            <option key={part.id} value={part.id}>
              {part.name.replace(/\s*\([^)]*\)\s*/g, " ").trim()} ({part.length_bp.toLocaleString()} bp)
            </option>
          ))}
        </select>
      </Field>
      <Field id="aav-polya" label="PolyA signal">
        <select id="aav-polya" value={form.polya} onChange={(event) => update({ polya: event.target.value })} className={INPUT_CLASS} disabled={busy}>
          <option value="">Automatic, shortest functional signal</option>
          {polyas.map((part) => (
            <option key={part.id} value={part.id}>
              {part.name} ({part.length_bp.toLocaleString()} bp)
            </option>
          ))}
        </select>
      </Field>
      <div className="space-y-xs">
        <Checkbox id="aav-sc" label="Self-complementary" checked={form.selfComplementary} onChange={(value) => update({ selfComplementary: value })} disabled={busy} />
        <Checkbox id="aav-wpre" label="Include WPRE if it fits" checked={form.includeWpre} onChange={(value) => update({ includeWpre: value })} disabled={busy} />
      </div>
      <Field id="aav-limit" label="Packaging target override (bp)" hint="Leave empty to use the validator default.">
        <input id="aav-limit" inputMode="numeric" value={form.packagingLimit} onChange={(event) => update({ packagingLimit: event.target.value })} className={INPUT_CLASS} disabled={busy} />
      </Field>
    </FormShell>
  );
}

export function AssemblyForm({
  form,
  setForm,
  busy,
  error,
  onSubmit
}: {
  form: AssemblyFormState;
  setForm: (next: AssemblyFormState) => void;
  busy: boolean;
  error: string | null;
  onSubmit: () => void;
}) {
  const update = (patch: Partial<AssemblyFormState>) => setForm({ ...form, ...patch });
  const updateFragment = (key: string, patch: Partial<AssemblyFormState["fragments"][number]>) =>
    update({ fragments: form.fragments.map((fragment) => (fragment.key === key ? { ...fragment, ...patch } : fragment)) });
  return (
    <FormShell
      title="Assembly request"
      intro="List the fragments in assembly order. Primers, junctions, an order table and a protocol are generated and checked."
      error={error}
      busy={busy}
      submitLabel="Design primers"
      busyLabel="Designing primers"
      onSubmit={onSubmit}
    >
      <Field id="asm-strategy" label="Strategy">
        <select
          id="asm-strategy"
          value={form.strategy}
          onChange={(event) => update({ strategy: event.target.value as AssemblyFormState["strategy"] })}
          className={INPUT_CLASS}
          disabled={busy}
        >
          <option value="gibson">Gibson</option>
          <option value="golden_gate">Golden Gate</option>
          <option value="pcr_cloning">PCR cloning</option>
        </select>
      </Field>
      {form.strategy === "golden_gate" ? (
        <Field id="asm-enzyme" label="Type IIS enzyme" hint="Enter the enzyme name. The API rejects a name it does not support.">
          <input id="asm-enzyme" value={form.enzyme} onChange={(event) => update({ enzyme: event.target.value })} className={INPUT_CLASS} disabled={busy} />
        </Field>
      ) : null}
      <Field id="asm-tm" label="Target primer Tm (C)" hint="Leave empty to use the designer default.">
        <input id="asm-tm" inputMode="decimal" value={form.targetTm} onChange={(event) => update({ targetTm: event.target.value })} className={INPUT_CLASS} disabled={busy} />
      </Field>
      <ol className="space-y-sm">
        {form.fragments.map((fragment, index) => (
          <li key={fragment.key} className="rounded-md border border-line bg-mist p-sm" aria-label={`Fragment ${index + 1}`}>
            <div className="flex items-center justify-between gap-xs">
              <p className="text-caption font-semibold uppercase tracking-[0.06em] text-slate">Fragment {index + 1}</p>
              <button
                type="button"
                disabled={busy || form.fragments.length < 2}
                onClick={() => update({ fragments: form.fragments.filter((item) => item.key !== fragment.key) })}
                className="rounded-sm px-xs py-2xs text-xs font-semibold text-slate hover:text-clay focus:outline-none focus:ring-2 focus:ring-coral/40 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label={`Remove fragment ${index + 1}`}
              >
                Remove
              </button>
            </div>
            <div className="mt-xs grid grid-cols-2 gap-xs">
              <Field id={`asm-name-${fragment.key}`} label="Name">
                <input id={`asm-name-${fragment.key}`} value={fragment.name} onChange={(event) => updateFragment(fragment.key, { name: event.target.value })} className={INPUT_CLASS} disabled={busy} />
              </Field>
              <Field id={`asm-role-${fragment.key}`} label="Role">
                <select
                  id={`asm-role-${fragment.key}`}
                  value={fragment.role}
                  onChange={(event) => updateFragment(fragment.key, { role: event.target.value as typeof fragment.role })}
                  className={INPUT_CLASS}
                  disabled={busy}
                >
                  <option value="insert">Insert</option>
                  <option value="vector">Vector</option>
                  <option value="linker">Linker</option>
                </select>
              </Field>
            </div>
            <div className="mt-xs">
              <Field id={`asm-source-${fragment.key}`} label="Source" hint="Where this sequence comes from, such as an accession or part id.">
                <input id={`asm-source-${fragment.key}`} value={fragment.source} onChange={(event) => updateFragment(fragment.key, { source: event.target.value })} className={INPUT_CLASS} disabled={busy} />
              </Field>
            </div>
            <div className="mt-xs">
              <Field id={`asm-seq-${fragment.key}`} label="Sequence">
                <textarea
                  id={`asm-seq-${fragment.key}`}
                  value={fragment.sequence}
                  onChange={(event) => updateFragment(fragment.key, { sequence: event.target.value })}
                  rows={3}
                  spellCheck={false}
                  className={`${INPUT_CLASS} resize-none font-mono text-xs`}
                  disabled={busy}
                />
              </Field>
            </div>
          </li>
        ))}
      </ol>
      <button
        type="button"
        disabled={busy}
        onClick={() => update({ fragments: [...form.fragments, newFragment()] })}
        className="rounded-md border border-line-strong bg-paper px-sm py-2xs text-sm font-semibold text-ink hover:bg-mist focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40 disabled:cursor-not-allowed disabled:text-slate"
      >
        Add fragment
      </button>
    </FormShell>
  );
}

const SCOPE_OPTIONS: { value: string; label: string }[] = [
  { value: "construct_only", label: "The target and delivery construct only" },
  { value: "supplied_fasta", label: "The construct plus a sequence set I supply" },
  { value: "none", label: "No off-target search" }
];

export function GrnaForm({
  form,
  setForm,
  reference,
  busy,
  error,
  onSubmit
}: {
  form: GrnaFormState;
  setForm: (next: GrnaFormState) => void;
  reference: GrnaReference | null;
  busy: boolean;
  error: string | null;
  onSubmit: () => void;
}) {
  const update = (patch: Partial<GrnaFormState>) => setForm({ ...form, ...patch });
  const nucleases = reference?.nucleases.map((item) => item.nuclease) ?? FALLBACK_NUCLEASES;
  const vectors = (reference?.cloning_vectors ?? []).filter((vector) => vector.nucleases.includes(form.nuclease));
  return (
    <FormShell
      title="Guide RNA request"
      intro="Paste the target sequence. Guides on both strands are scored, ranked and checked, and the searched off-target space is stated with the result."
      error={error}
      busy={busy}
      submitLabel="Rank guides"
      busyLabel="Ranking guides"
      onSubmit={onSubmit}
    >
      <Field id="grna-name" label="Target name">
        <input id="grna-name" value={form.targetName} onChange={(event) => update({ targetName: event.target.value })} className={INPUT_CLASS} disabled={busy} />
      </Field>
      <Field id="grna-sequence" label="Target sequence" hint="DNA, written 5' to 3'. A FASTA header line is ignored.">
        <textarea
          id="grna-sequence"
          value={form.targetSequence}
          onChange={(event) => update({ targetSequence: event.target.value })}
          rows={4}
          spellCheck={false}
          className={`${INPUT_CLASS} resize-none font-mono text-xs`}
          disabled={busy}
        />
      </Field>
      <div className="grid grid-cols-2 gap-xs">
        <Field id="grna-nuclease" label="Nuclease">
          <select id="grna-nuclease" value={form.nuclease} onChange={(event) => update({ nuclease: event.target.value, cloningVector: "" })} className={INPUT_CLASS} disabled={busy}>
            {nucleases.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </Field>
        <Field id="grna-intent" label="Edit intent">
          <select id="grna-intent" value={form.editIntent} onChange={(event) => update({ editIntent: event.target.value })} className={INPUT_CLASS} disabled={busy}>
            {EDIT_INTENT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </Field>
      </div>
      <fieldset className="rounded-md border border-line p-sm">
        <legend className="px-2xs text-caption font-semibold uppercase tracking-[0.06em] text-slate">Off-target search space</legend>
        <div className="space-y-xs">
          {SCOPE_OPTIONS.map((option) => (
            <label key={option.value} className="flex items-center gap-xs text-sm text-ink">
              <input
                type="radio"
                name="grna-scope"
                value={option.value}
                checked={form.scope === option.value}
                onChange={() => update({ scope: option.value })}
                disabled={busy}
                className="h-4 w-4 accent-[#365f43]"
              />
              {option.label}
            </label>
          ))}
        </div>
        <p className="mt-xs text-caption text-slate">The result states exactly what was searched.</p>
      </fieldset>
      {form.scope === "supplied_fasta" ? (
        <Field id="grna-fasta" label="FASTA path" hint="A path the API can read.">
          <input id="grna-fasta" value={form.fastaPath} onChange={(event) => update({ fastaPath: event.target.value })} className={INPUT_CLASS} disabled={busy} />
        </Field>
      ) : null}
      <details className="rounded-md border border-line p-sm">
        <summary className="cursor-pointer text-caption font-semibold uppercase tracking-[0.06em] text-slate focus:outline-none focus:ring-2 focus:ring-coral/40">
          Optional details
        </summary>
        <div className="mt-sm space-y-sm">
          <Field id="grna-delivery-name" label="Delivery construct name">
            <input id="grna-delivery-name" value={form.deliveryName} onChange={(event) => update({ deliveryName: event.target.value })} className={INPUT_CLASS} disabled={busy} />
          </Field>
          <Field id="grna-delivery-seq" label="Delivery construct sequence" hint="Lets the self-targeting check run.">
            <textarea
              id="grna-delivery-seq"
              value={form.deliverySequence}
              onChange={(event) => update({ deliverySequence: event.target.value })}
              rows={3}
              spellCheck={false}
              className={`${INPUT_CLASS} resize-none font-mono text-xs`}
              disabled={busy}
            />
          </Field>
          <div className="grid grid-cols-2 gap-xs">
            <Field id="grna-cds-start" label="Coding start" hint="Zero-based.">
              <input id="grna-cds-start" inputMode="numeric" value={form.cdsStart} onChange={(event) => update({ cdsStart: event.target.value })} className={INPUT_CLASS} disabled={busy} />
            </Field>
            <Field id="grna-cds-end" label="Coding end" hint="Exclusive.">
              <input id="grna-cds-end" inputMode="numeric" value={form.cdsEnd} onChange={(event) => update({ cdsEnd: event.target.value })} className={INPUT_CLASS} disabled={busy} />
            </Field>
          </div>
          <Field id="grna-vector" label="Cloning vector">
            <select id="grna-vector" value={form.cloningVector} onChange={(event) => update({ cloningVector: event.target.value })} className={INPUT_CLASS} disabled={busy}>
              <option value="">Default for the nuclease</option>
              {vectors.map((vector) => (
                <option key={vector.vector_id} value={vector.vector_id}>{vector.name}</option>
              ))}
            </select>
          </Field>
          <Field id="grna-max" label="Guides to return" hint="Leave empty to use the default.">
            <input id="grna-max" inputMode="numeric" value={form.maxGuides} onChange={(event) => update({ maxGuides: event.target.value })} className={INPUT_CLASS} disabled={busy} />
          </Field>
        </div>
      </details>
    </FormShell>
  );
}
