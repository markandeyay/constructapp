"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, createSession, exportDesign, getOutcome, getPendingOutcomePrompts, pollJob, submitDesign, submitRefinement } from "@/lib/api";
import { AavForm, AssemblyForm, CapabilitySelector, GrnaForm } from "@/components/capability-forms";
import { CapabilityExportActions } from "@/components/capability-exports";
import { CapabilityResultPane } from "@/components/capability-result-pane";
import { ExportActions, type ExportFormat, type ExportStatus } from "@/components/export-actions";
import { OutcomeReportModal } from "@/components/outcome-report-modal";
import { PlasmidMapView } from "@/components/plasmid-map-view";
import { ValidationReportPanel, normalizeStatus } from "@/components/validation-report";
import {
  CAPABILITY_OPTIONS,
  adaptReport,
  outcomeDesignId,
  outcomeReport,
  outcomeSummary,
  type CapabilityKind,
  type CapabilityOutcome
} from "@/lib/capabilities";
import { useCapabilityWorkspace } from "@/lib/use-capabilities";
import type { AnnotatedSequence, JobResultPayload, JobStatusResponse, OutcomeReport, PendingOutcomePrompt, ValidationReport } from "@/lib/types";

type UiState = "idle" | "submitting" | "polling" | "poll_timeout" | "ready" | "awaiting_clarification" | "error";
type PendingPromptStatus = "loading" | "ready" | "error";

type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  kind: "prompt" | "clarification_answer" | "result" | "clarification" | "status" | "error";
  text: string;
  result?: JobResultPayload;
};

type OutcomeModalTarget = {
  designId: string;
  modelVersion: string;
  initialReport?: OutcomeReport;
  promptKey?: string;
  provenanceContext?: Record<string, unknown>;
};

const DEFAULT_PROMPT =
  "a bacterial expression vector for E. coli with ampicillin selection and GFP reporter readout";

const EXAMPLE_PROMPTS = [
  DEFAULT_PROMPT,
  "a mammalian GFP reporter plasmid for expression analysis in cultured cells",
  "a yeast shuttle vector with URA3 selection and centromere maintenance"
];

const DISMISSED_OUTCOME_PROMPTS_KEY = "construct:dismissed-outcome-prompts";
const REPORTED_OUTCOMES_KEY = "construct:reported-outcomes";
const INITIAL_EXPORT_STATUS: Record<ExportFormat, ExportStatus> = { genbank: "idle", fasta: "idle" };
const INITIAL_EXPORT_ERRORS: Record<ExportFormat, string | null> = { genbank: null, fasta: null };

export default function Page() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      kind: "result",
      text: "Describe the construct you want. I will retrieve a grounding vector, run the design pipeline, and render the annotated plasmid when the job completes."
    }
  ]);
  const [input, setInput] = useState("");
  const [state, setState] = useState<UiState>("idle");
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobStartedAt, setJobStartedAt] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const [exportStatus, setExportStatus] = useState<Record<ExportFormat, ExportStatus>>(INITIAL_EXPORT_STATUS);
  const [exportError, setExportError] = useState<Record<ExportFormat, string | null>>(INITIAL_EXPORT_ERRORS);
  const [outcomeModalOpen, setOutcomeModalOpen] = useState(false);
  const [outcomeModalTarget, setOutcomeModalTarget] = useState<OutcomeModalTarget | null>(null);
  const [latestOutcome, setLatestOutcome] = useState<OutcomeReport | null>(null);
  const [reportedOutcomes, setReportedOutcomes] = useState<OutcomeReport[]>([]);
  const [pendingOutcomePrompts, setPendingOutcomePrompts] = useState<PendingOutcomePrompt[]>([]);
  const [pendingPromptStatus, setPendingPromptStatus] = useState<PendingPromptStatus>("loading");
  const [dismissedPromptKeys, setDismissedPromptKeys] = useState<string[]>([]);
  const [appStatus, setAppStatus] = useState("");
  const [outcomeRefreshStatus, setOutcomeRefreshStatus] = useState<"idle" | "refreshing" | "error">("idle");
  const [isDesktop, setIsDesktop] = useState(true);
  const [chatOpen, setChatOpen] = useState(true);
  const [mobileTab, setMobileTab] = useState<"chat" | "map">("chat");
  const [selectedDesignId, setSelectedDesignId] = useState<string | null>(null);
  const [sidebarSheetOpen, setSidebarSheetOpen] = useState(false);
  const [outcomesCollapsed, setOutcomesCollapsed] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [retryableError, setRetryableError] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(min-width: 768px)");
    const onChange = (event: MediaQueryListEvent) => setIsDesktop(event.matches);
    setIsDesktop(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    const query = window.matchMedia("(min-width: 880px)");
    const onChange = (event: MediaQueryListEvent) => setChatOpen(event.matches);
    setChatOpen(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  const designHistory = useMemo(() => {
    const seen = new Set<string>();
    const rows: { designId: string; recommendation: string; overall: string; bp: number; features: number }[] = [];
    for (const message of [...messages].reverse()) {
      const result = message.result;
      if (!result?.annotated_sequence) {
        continue;
      }
      const id = result.design_id ?? result.design?.design_id;
      if (!id || seen.has(id)) {
        continue;
      }
      seen.add(id);
      const seq = result.annotated_sequence;
      const checks = result.validation_report?.checks ?? [];
      const overall =
        result.validation_report?.overall ??
        (checks.some((check) => normalizeStatus(check.status) === "FAIL")
          ? "FAIL"
          : checks.some((check) => normalizeStatus(check.status) === "WARN")
            ? "WARN"
            : "PASS");
      rows.push({
        designId: id,
        recommendation: (result.recommendation_text ?? result.design?.recommendation_text ?? "").trim(),
        overall,
        bp: seq.sequence.length,
        features: seq.features.length
      });
    }
    return rows;
  }, [messages]);

  const handleCapabilitySubmitted = useCallback((kind: CapabilityKind, summary: string) => {
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", kind: "prompt", text: summary }]);
    setAppStatus(`Running the ${capabilityLabel(kind)} design.`);
  }, []);
  const handleCapabilityCompleted = useCallback((outcome: CapabilityOutcome) => {
    const text = outcomeSummary(outcome);
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        kind: "result",
        text,
        result: {
          design_id: outcomeDesignId(outcome),
          capability: outcome.kind,
          recommendation_text: text,
          validation_report: adaptReport(outcomeReport(outcome))
        }
      }
    ]);
    setAppStatus(`${capabilityLabel(outcome.kind)} design complete.`);
  }, []);
  const handleCapabilityFailed = useCallback((kind: CapabilityKind, message: string) => {
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "system", kind: "error", text: message }]);
    setAppStatus(`${capabilityLabel(kind)} design failed. ${message}`);
  }, []);
  const workspace = useCapabilityWorkspace({
    onSubmitted: handleCapabilitySubmitted,
    onCompleted: handleCapabilityCompleted,
    onFailed: handleCapabilityFailed
  });
  const isPlasmid = workspace.capability === "plasmid";
  const capabilityOutcome = isPlasmid ? null : (workspace.outcomes[workspace.capability] ?? null);

  function handleNewDesign() {
    workspace.clearOutcomes();
    setSessionId(null);
    setMessages([
      {
        id: "welcome",
        role: "assistant",
        kind: "result",
        text: "Describe the construct you want. I will retrieve a grounding vector, run the design pipeline, and render the annotated plasmid when the job completes."
      }
    ]);
    setInput("");
    setState("idle");
    setActiveJobId(null);
    setJobStartedAt(null);
    setSelectedDesignId(null);
    setAppStatus("");
    setRetryableError(false);
    if (!isDesktop) {
      setMobileTab("chat");
    }
  }

  const latestResult = useMemo(
    () => [...messages].reverse().find((message) => message.result?.annotated_sequence)?.result,
    [messages]
  );
  const selectedResult = useMemo(() => {
    if (selectedDesignId) {
      const found = [...messages]
        .reverse()
        .find((message) => (message.result?.design_id ?? message.result?.design?.design_id) === selectedDesignId);
      if (found?.result) {
        return found.result;
      }
    }
    return latestResult;
  }, [selectedDesignId, messages, latestResult]);
  const selectedResultMessageId = useMemo(() => {
    let found;
    if (selectedDesignId) {
      found = [...messages]
        .reverse()
        .find((message) => (message.result?.design_id ?? message.result?.design?.design_id) === selectedDesignId);
    }
    if (!found) {
      found = [...messages].reverse().find((message) => message.result?.annotated_sequence);
    }
    return found?.id ?? null;
  }, [selectedDesignId, messages]);
  const reportedOutcomeDesignIds = useMemo(
    () => Array.from(new Set(reportedOutcomes.map((outcome) => outcome.design_id))).sort().join("|"),
    [reportedOutcomes]
  );
  const annotatedSequence = selectedResult?.annotated_sequence ?? null;
  const designId = selectedResult?.design_id ?? selectedResult?.design?.design_id ?? null;
  const modelVersion = selectedResult?.validation_report?.generated_by_model_version ?? selectedResult?.design?.validation_report?.generated_by_model_version ?? null;
  const capabilityReport = useMemo(
    () => (capabilityOutcome ? adaptReport(outcomeReport(capabilityOutcome)) : null),
    [capabilityOutcome]
  );
  const shownValidationReport = isPlasmid ? (selectedResult?.validation_report ?? null) : capabilityReport;
  const displayDesignId = isPlasmid ? designId : capabilityOutcome ? outcomeDesignId(capabilityOutcome) : null;
  const capabilityMessageId = useMemo(
    () => (isPlasmid ? null : ([...messages].reverse().find((message) => message.result?.capability === workspace.capability)?.id ?? null)),
    [isPlasmid, messages, workspace.capability]
  );
  const isBusy = state === "submitting" || state === "polling";
  const isPollTimeoutRecovery = state === "poll_timeout" && Boolean(activeJobId);
  const activeClarification = useMemo(
    () => [...messages].reverse().find((message) => message.kind === "clarification")?.text ?? null,
    [messages]
  );

  useEffect(() => {
    if (!isBusy || jobStartedAt === null) {
      return;
    }
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, [isBusy, jobStartedAt]);

  useEffect(() => {
    let cancelled = false;
    setDismissedPromptKeys(readDismissedPromptKeys());
    setReportedOutcomes(readReportedOutcomes());
    setPendingPromptStatus("loading");
    getPendingOutcomePrompts()
      .then((prompts) => {
        if (!cancelled) {
          setPendingOutcomePrompts(prompts);
          setPendingPromptStatus("ready");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPendingOutcomePrompts([]);
          setPendingPromptStatus("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!designId) {
      setLatestOutcome(null);
      return;
    }
    setLatestOutcome(reportedOutcomes.find((outcome) => outcome.design_id === designId) ?? null);
  }, [designId, reportedOutcomes]);

  useEffect(() => {
    if (!designId) {
      return;
    }
    let cancelled = false;
    getOutcome(designId)
      .then((outcome) => {
        if (!cancelled) {
          setReportedOutcomes((current) => persistReportedOutcomes(upsertReportedOutcome(current, outcome)));
        }
      })
      .catch(() => {
        // A missing outcome is expected for designs that have not been reported yet.
      });
    return () => {
      cancelled = true;
    };
  }, [designId]);

  useEffect(() => {
    let cancelled = false;
    const designIds = reportedOutcomeDesignIds ? reportedOutcomeDesignIds.split("|") : [];
    if (!designIds.length) {
      setOutcomeRefreshStatus("idle");
      return;
    }
    setOutcomeRefreshStatus("refreshing");
    Promise.all(
      designIds.map((knownDesignId) =>
        getOutcome(knownDesignId)
          .then((outcome) => outcome)
          .catch(() => null)
      )
    ).then((refreshed) => {
      if (cancelled) {
        return;
      }
      const outcomes = refreshed.filter((outcome): outcome is OutcomeReport => Boolean(outcome));
      if (outcomes.length) {
        setReportedOutcomes((current) => persistReportedOutcomes(mergeReportedOutcomes(current, outcomes)));
        setOutcomeRefreshStatus("idle");
      } else {
        setOutcomeRefreshStatus("error");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [reportedOutcomeDesignIds]);

  useEffect(() => {
    setExportStatus({ ...INITIAL_EXPORT_STATUS });
    setExportError({ ...INITIAL_EXPORT_ERRORS });
  }, [designId]);

  const visiblePendingPrompt = pendingOutcomePrompts.find((prompt) => !dismissedPromptKeys.includes(promptKey(prompt))) ?? null;
  const visiblePendingPromptKey = visiblePendingPrompt ? promptKey(visiblePendingPrompt) : null;

  useEffect(() => {
    if (visiblePendingPrompt) {
      setAppStatus(`Outcome follow-up available for design ${visiblePendingPrompt.design_id}.`);
    }
  }, [visiblePendingPromptKey, visiblePendingPrompt]);

  useEffect(() => {
    if (!isDesktop && annotatedSequence) {
      setMobileTab("map");
    }
  }, [annotatedSequence, isDesktop]);

  const capabilityDesignId = capabilityOutcome ? outcomeDesignId(capabilityOutcome) : null;
  useEffect(() => {
    if (!isDesktop && capabilityDesignId) {
      setMobileTab("map");
    }
  }, [capabilityDesignId, isDesktop]);

  useEffect(() => {
    if (!isDesktop && state === "awaiting_clarification") {
      setMobileTab("chat");
    }
  }, [state, isDesktop]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setSidebarSheetOpen(false);
        setSettingsOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || isBusy || isPollTimeoutRecovery) {
      return;
    }

    setInput("");
    setExportStatus({ ...INITIAL_EXPORT_STATUS });
    setExportError({ ...INITIAL_EXPORT_ERRORS });
    const submittedKind = state === "awaiting_clarification" ? "clarification_answer" : "prompt";
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", kind: submittedKind, text }
    ]);

    let keepActiveJob = false;
    try {
      setRetryableError(false);
      setState("submitting");
      setAppStatus("Starting design job.");
      setJobStartedAt(Date.now());
      const currentSessionId = sessionId ?? (await createSession()).session_id;
      const hasExistingSession = Boolean(sessionId);
      setSessionId(currentSessionId);
      const response = hasExistingSession
        ? await submitRefinement(currentSessionId, text)
        : await submitDesign(currentSessionId, text);

      setActiveJobId(response.job_id);
      await pollAndApplyJob(response.job_id);
    } catch (error) {
      if (isPollingTimeout(error)) {
        keepActiveJob = true;
        const jobId = String(error.details.job_id ?? activeJobId ?? "unknown");
        setActiveJobId(jobId);
        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: "system",
            kind: "status",
            text: `Job ${jobId} is still queued or running. Keep this page open, confirm the local worker or demo fixture is running, then use Check status to resume polling.`
          }
        ]);
        setState("poll_timeout");
        setAppStatus(`Job ${jobId} is still queued or running. Check the local worker or demo fixture before retrying.`);
        return;
      }
      const errorText = friendlyErrorMessage(error);
      const canRetry = error instanceof ApiError && error.retryable;
      setRetryableError(canRetry);
      if (canRetry) {
        setInput(text);
      }
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "system", kind: "error", text: errorText }
      ]);
      setState("error");
      setAppStatus(`Design failed. ${errorText}`);
    } finally {
      if (!keepActiveJob) {
        setActiveJobId(null);
        setJobStartedAt(null);
      }
    }
  }

  async function handleCheckJob() {
    if (!activeJobId || isBusy) {
      return;
    }
    let keepActiveJob = false;
    try {
      setJobStartedAt(Date.now());
      await pollAndApplyJob(activeJobId);
    } catch (error) {
      if (isPollingTimeout(error)) {
        keepActiveJob = true;
        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: "system",
            kind: "status",
            text: `Job ${activeJobId} is still queued or running. Confirm the local worker or demo fixture is running, then try again.`
          }
        ]);
        setState("poll_timeout");
        setAppStatus(`Job ${activeJobId} is still queued or running. Check the local worker or demo fixture before retrying.`);
        return;
      }
      const text = friendlyErrorMessage(error);
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "system", kind: "error", text }
      ]);
      setState("error");
      setAppStatus(`Status check failed. ${text}`);
    } finally {
      if (!keepActiveJob) {
        setActiveJobId(null);
        setJobStartedAt(null);
      }
    }
  }

  async function pollAndApplyJob(jobId: string) {
    setState("polling");
    setAppStatus("Designing and validating plasmid.");
    const job = await pollJob(jobId, { onUpdate: () => setNow(Date.now()) });
    const result = normalizeJobResult(job.result);
    const clarification = clarificationQuestion(result);
    if (job.error || job.status.toLowerCase() === "failed") {
      throw jobError(job);
    }
    if (clarification) {
      setRetryableError(false);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          kind: "clarification",
          text: `To design this for you, I need to know: ${clarification}`,
          result
        }
      ]);
      setState("awaiting_clarification");
      setAppStatus("Waiting for your clarification answer.");
    } else {
      setRetryableError(false);
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "assistant", kind: "result", text: resultSummary(result), result }
      ]);
      setState("ready");
      setAppStatus("Design complete.");
    }
  }

  async function handleExport(format: ExportFormat) {
    if (!designId || isBusy) {
      return;
    }
    setExportError((current) => ({ ...current, [format]: null }));
    setExportStatus((current) => ({ ...current, [format]: "loading" }));
    try {
      const blob = await exportDesign(designId, format);
      const suffix = format === "genbank" ? "gb" : "fasta";
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${designId}.${suffix}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setExportStatus((current) => ({ ...current, [format]: "success" }));
    } catch (error) {
      setExportStatus((current) => ({ ...current, [format]: "error" }));
      setExportError((current) => ({ ...current, [format]: `${formatLabel(format)} export failed. ${friendlyErrorMessage(error)}` }));
    }
  }

  function openCurrentOutcomeModal() {
    if (!designId) {
      return;
    }
    setOutcomeModalTarget({ designId, modelVersion: modelVersion ?? latestOutcome?.model_version ?? "unknown-model", initialReport: latestOutcome ?? undefined });
    setOutcomeModalOpen(true);
  }

  function handleOpenFullReport() {
    const targetId = isPlasmid ? selectedResultMessageId : capabilityMessageId;
    const scrollToResult = () => {
      if (!targetId) {
        return;
      }
      const el = document.getElementById(`message-${targetId}`);
      if (el instanceof HTMLElement) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    };
    if (!isDesktop) {
      setMobileTab("chat");
      setSidebarSheetOpen(false);
    } else {
      setChatOpen(true);
    }
    requestAnimationFrame(() => requestAnimationFrame(scrollToResult));
  }

  function openPromptOutcomeModal(prompt: PendingOutcomePrompt) {
    setOutcomeModalTarget({
      designId: prompt.design_id,
      modelVersion: "unknown-model",
      promptKey: promptKey(prompt),
      provenanceContext: {
        reported_via: "web_pending_outcome_prompt",
        prompt_session_id: prompt.session_id,
        prompt_created_at: prompt.created_at,
        prompt_days_since_created: prompt.days_since_created,
        model_version_fallback: "unknown-model"
      }
    });
    setOutcomeModalOpen(true);
  }

  function openReportedOutcomeModal(outcome: OutcomeReport) {
    setOutcomeModalTarget({
      designId: outcome.design_id,
      modelVersion: outcome.model_version,
      initialReport: outcome,
      provenanceContext: { reported_via: "web_my_outcomes_panel" }
    });
    setOutcomeModalOpen(true);
  }

  function dismissPrompt(prompt: PendingOutcomePrompt) {
    const key = promptKey(prompt);
    setDismissedPromptKeys((current) => persistDismissedPromptKey(current, key));
  }

  function handleStartOverAfterTimeout() {
    const abandonedJobId = activeJobId;
    setActiveJobId(null);
    setJobStartedAt(null);
    setSessionId(null);
    setState("idle");
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        role: "system",
        kind: "status",
        text: abandonedJobId
          ? `Stopped waiting for job ${abandonedJobId}. Start a new design when the demo fixture or worker is ready.`
          : "Stopped waiting for the previous job. Start a new design when the demo fixture or worker is ready."
      }
    ]);
    setAppStatus("Timed-out job abandoned. Start a new design when the demo fixture or worker is ready.");
  }

  function handleOutcomeSubmitted(report: OutcomeReport) {
    setReportedOutcomes((current) => persistReportedOutcomes(upsertReportedOutcome(current, report)));
    if (report.design_id === designId) {
      setLatestOutcome(report);
    }
    const submittedPromptKey = outcomeModalTarget?.promptKey;
    if (submittedPromptKey) {
      setDismissedPromptKeys((current) => persistDismissedPromptKey(current, submittedPromptKey));
      setPendingOutcomePrompts((current) => current.filter((prompt) => promptKey(prompt) !== submittedPromptKey));
    }
  }

  const mapPane = isPlasmid ? (
    <PlasmidMapView
      annotatedSequence={annotatedSequence as AnnotatedSequence | null}
      waitingForClarification={state === "awaiting_clarification"}
    />
  ) : (
    <CapabilityResultPane
      capability={workspace.capability as Exclude<CapabilityKind, "plasmid">}
      outcome={capabilityOutcome}
      onApplyPlan={workspace.applyPlan}
      onUseAsFragments={workspace.aavAsFragments}
    />
  );
  const capabilityForm: ReactNode =
    workspace.capability === "aav" ? (
      <AavForm
        form={workspace.aavForm}
        setForm={workspace.setAavForm}
        parts={workspace.aavParts}
        partsFailed={workspace.aavPartsFailed}
        busy={workspace.busy}
        error={workspace.formError}
        onSubmit={workspace.submit}
      />
    ) : workspace.capability === "assembly" ? (
      <AssemblyForm form={workspace.assemblyForm} setForm={workspace.setAssemblyForm} busy={workspace.busy} error={workspace.formError} onSubmit={workspace.submit} />
    ) : workspace.capability === "guide_rna" ? (
      <GrnaForm
        form={workspace.grnaForm}
        setForm={workspace.setGrnaForm}
        reference={workspace.grnaReference}
        busy={workspace.busy}
        error={workspace.formError}
        onSubmit={workspace.submit}
      />
    ) : null;

  return (
    <main className="flex h-screen flex-col bg-cream font-sans text-ink">
      <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">{appStatus}</p>
      {visiblePendingPrompt ? (
        <PendingOutcomeToast prompt={visiblePendingPrompt} onOpen={openPromptOutcomeModal} onDismiss={dismissPrompt} />
      ) : null}

      {isDesktop ? (
        <>
          <header className="hidden h-12 items-center gap-sm border-b border-line bg-paper px-md md:flex" role="banner">
            <span className="font-serif text-h2 tracking-tight text-ink">Construct</span>
            <span className="mx-2xs hidden h-6 w-px bg-line-strong md:block" aria-hidden />
            <h1 id="design-workspace-title" className="font-serif text-h3 text-ink">Design workspace</h1>
            <div className="mx-auto flex items-center gap-xs" aria-live="polite">
              {displayDesignId ? (
                <>
                  <span className="text-small text-slate">{displayDesignId.length > 12 ? `${displayDesignId.slice(0, 12)}\u2026` : displayDesignId}</span>
                  {shownValidationReport ? (
                    <span className={`rounded-pill border px-xs py-2xs text-caption font-semibold uppercase tracking-[0.06em] ${overallBadgeClass(shownValidationReport)}`}>{overallLabel(shownValidationReport)}</span>
                  ) : null}
                </>
              ) : (
                <span className="text-small italic text-slate">no active design</span>
              )}
            </div>
            <div className="ml-auto flex items-center gap-xs">
              <button
                type="button"
                aria-label="Settings"
                onClick={() => setSettingsOpen((open) => !open)}
                className="flex h-8 w-8 items-center justify-center rounded-md border border-line bg-paper text-ink hover:border-line-strong focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40"
              >
                <svg viewBox="0 0 16 16" className="h-4 w-4" aria-hidden="true">
                  <path fill="currentColor" d="M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zm5.5 2.5a5.5 5.5 0 0 1-.07.87l1.43 1.12-1.5 2.6-1.74-.7a5.5 5.5 0 0 1-1.5.87l-.26 1.87H6.14l-.26-1.87a5.5 5.5 0 0 1-1.5-.87l-1.74.7-1.5-2.6 1.43-1.12A5.5 5.5 0 0 1 2.5 8c0-.3.03-.58.07-.87L1.14 6.01l1.5-2.6 1.74.7a5.5 5.5 0 0 1 1.5-.87l.26-1.87h3.72l.26 1.87a5.5 5.5 0 0 1 1.5.87l1.74-.7 1.5 2.6-1.43 1.12c.04.29.07.57.07.87z" />
                </svg>
              </button>
              <button
                type="button"
                onClick={() => setChatOpen((open) => !open)}
                aria-expanded={chatOpen}
                aria-controls="design-thread"
                className="inline-flex items-center gap-xs rounded-md border border-line bg-paper px-sm py-2xs text-xs font-semibold text-ink hover:border-line-strong focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40 md:inline-flex lg:hidden"
              >
                Chat
              </button>
            </div>
          </header>

          <div className={`hidden min-h-0 flex-1 md:grid ${chatOpen ? "md:grid-cols-[56px_minmax(0,1fr)_360px]" : "md:grid-cols-[56px_minmax(0,1fr)]"} lg:grid-cols-[256px_minmax(0,1fr)_400px]`}>
            <SidebarContent
              variant="desktop"
              designHistory={designHistory}
              selectedDesignId={selectedDesignId ?? designHistory[0]?.designId ?? null}
              onSelect={setSelectedDesignId}
              onNewDesign={handleNewDesign}
              reportedOutcomes={reportedOutcomes}
              onOpenReportedOutcome={openReportedOutcomeModal}
              outcomeRefreshStatus={outcomeRefreshStatus}
              pendingPromptStatus={pendingPromptStatus}
              outcomesCollapsed={outcomesCollapsed}
              onToggleOutcomes={() => setOutcomesCollapsed((open) => !open)}
              hasDesign={Boolean(designId)}
              onOpenSheet={() => setSidebarSheetOpen(true)}
            />

            <div className="flex min-h-0 min-w-0 flex-col bg-cream">
              <div className="min-h-0 flex-1 overflow-y-auto p-sm md:p-md">
                {mapPane}
              </div>
              <ToolsStrip
                layout="row"
                capability={workspace.capability}
                capabilityOutcome={capabilityOutcome}
                designId={designId}
                isBusy={isBusy}
                validationReport={shownValidationReport}
                exportStatus={exportStatus}
                exportError={exportError}
                onExport={handleExport}
                latestOutcome={latestOutcome}
                onOpenOutcome={openCurrentOutcomeModal}
                onOpenFullReport={handleOpenFullReport}
              />
            </div>

            <aside
              id="design-thread"
              aria-label="Conversation history"
              className={`hidden min-h-0 flex-col border-l border-line bg-paper md:flex lg:flex ${chatOpen ? "md:flex" : "md:hidden"}`}
            >
              <ChatPanel
                messages={messages}
                isBusy={isBusy}
                state={state}
                activeJobId={activeJobId}
                jobStartedAt={jobStartedAt}
                now={now}
                sessionId={sessionId}
                input={input}
                setInput={setInput}
                onSubmit={handleSubmit}
                activeClarification={activeClarification}
                isPollTimeoutRecovery={isPollTimeoutRecovery}
                onCheckJob={() => void handleCheckJob()}
                onStartOver={handleStartOverAfterTimeout}
                onViewMap={() => undefined}
                retryableError={retryableError}
                capability={workspace.capability}
                onCapabilityChange={workspace.setCapability}
                capabilityForm={capabilityForm}
                capabilityBusy={workspace.busy}
              />
            </aside>
          </div>

          {settingsOpen ? (
            <div className="fixed inset-0 z-40">
              <button type="button" tabIndex={-1} aria-label="Close settings" onClick={() => setSettingsOpen(false)} className="absolute inset-0 bg-ink/30" />
              <div className="absolute right-md top-14 w-64 rounded-md border border-line bg-paper p-md shadow-floating" role="dialog" aria-label="Settings">
                <p className="mt-sm text-caption text-slate">Connection: <span className="text-sage">Connected</span></p>
                <p className="mt-2xs text-caption text-slate">Model: {modelVersion ?? "unknown"}</p>
              </div>
            </div>
          ) : null}
        </>
      ) : (
        <>
          <header className="relative flex h-[52px] items-center gap-sm border-b border-line bg-paper px-md md:hidden" role="banner">
            <span className="font-serif text-h2 tracking-tight text-ink">Construct</span>
            <h1 id="design-workspace-title" className="sr-only">Design workspace</h1>
            <button
              type="button"
              onClick={() => setSidebarSheetOpen(true)}
              aria-label="Open menu"
              className="ml-auto flex h-8 w-8 items-center justify-center rounded-md border border-line bg-paper text-ink hover:border-line-strong focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40"
            >
              <svg viewBox="0 0 16 16" className="h-4 w-4" aria-hidden="true">
                <path fill="currentColor" d="M2 3h12v2H2V3zm0 4h12v2H2V7zm0 4h12v2H2v-2z" />
              </svg>
            </button>
            <div role="tablist" aria-label="Workspace tabs" className="absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center gap-xs rounded-md bg-mist p-2xs">
              <button
                type="button"
                role="tab"
                aria-selected={mobileTab === "map"}
                onClick={() => setMobileTab("map")}
                className={`rounded-sm px-sm py-2xs text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-coral/40 ${mobileTab === "map" ? "bg-paper text-ink shadow-rest" : "text-slate"}`}
              >
                Map
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mobileTab === "chat"}
                onClick={() => setMobileTab("chat")}
                className={`rounded-sm px-sm py-2xs text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-coral/40 ${mobileTab === "chat" ? "bg-paper text-ink shadow-rest" : "text-slate"}`}
              >
                Chat
              </button>
            </div>
          </header>

          <div className="min-h-0 flex-1 md:hidden">
            {mobileTab === "map" ? (
              <div className="flex h-full min-h-0 flex-col bg-cream">
                <div className="min-h-0 flex-1 overflow-y-auto p-sm">
                  {mapPane}
                </div>
                <ToolsStrip
                  layout="stack"
                  capability={workspace.capability}
                  capabilityOutcome={capabilityOutcome}
                  designId={designId}
                  isBusy={isBusy}
                  validationReport={shownValidationReport}
                  exportStatus={exportStatus}
                  exportError={exportError}
                  onExport={handleExport}
                  latestOutcome={latestOutcome}
                  onOpenOutcome={openCurrentOutcomeModal}
                  onOpenFullReport={handleOpenFullReport}
                />
              </div>
            ) : (
              <div className="flex h-full min-h-0 flex-col bg-paper">
                <ChatPanel
                  messages={messages}
                  isBusy={isBusy}
                  state={state}
                  activeJobId={activeJobId}
                  jobStartedAt={jobStartedAt}
                  now={now}
                  sessionId={sessionId}
                  input={input}
                  setInput={setInput}
                  onSubmit={handleSubmit}
                  activeClarification={activeClarification}
                  isPollTimeoutRecovery={isPollTimeoutRecovery}
                  onCheckJob={() => void handleCheckJob()}
                  onStartOver={handleStartOverAfterTimeout}
                  onViewMap={() => setMobileTab("map")}
                  retryableError={retryableError}
                  capability={workspace.capability}
                  onCapabilityChange={workspace.setCapability}
                  capabilityForm={capabilityForm}
                  capabilityBusy={workspace.busy}
                />
              </div>
            )}
          </div>
        </>
      )}

      {sidebarSheetOpen ? (
        <div className="fixed inset-0 z-40">
          <button type="button" tabIndex={-1} aria-label="Close menu" onClick={() => setSidebarSheetOpen(false)} className="absolute inset-0 bg-ink/30" />
          <aside className="absolute left-0 top-0 flex h-full w-72 max-w-[85vw] flex-col border-r border-line bg-paper shadow-floating" aria-label="Workspace navigation">
            <div className="flex shrink-0 items-center justify-between border-b border-line px-md py-sm">
              <span className="font-serif text-h3 text-ink">Menu</span>
              <button
                type="button"
                aria-label="Close menu"
                onClick={() => setSidebarSheetOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-md border border-line bg-paper text-ink hover:border-line-strong focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40"
              >
                <svg viewBox="0 0 16 16" className="h-4 w-4" aria-hidden="true">
                  <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-sm py-md">
              <SidebarContent
                variant="sheet"
                designHistory={designHistory}
                selectedDesignId={selectedDesignId ?? designHistory[0]?.designId ?? null}
                onSelect={(id) => { setSelectedDesignId(id); setSidebarSheetOpen(false); if (designHistory.some((row) => row.designId === id)) { setMobileTab("map"); } }}
                onNewDesign={() => { handleNewDesign(); setSidebarSheetOpen(false); }}
                reportedOutcomes={reportedOutcomes}
                onOpenReportedOutcome={openReportedOutcomeModal}
                outcomeRefreshStatus={outcomeRefreshStatus}
                pendingPromptStatus={pendingPromptStatus}
                outcomesCollapsed={false}
                onToggleOutcomes={() => undefined}
                hasDesign={Boolean(designId)}
                onOpenSheet={() => setSidebarSheetOpen(true)}
              />
            </div>
          </aside>
        </div>
      ) : null}

      <footer className="flex h-6 items-center justify-between border-t border-line bg-paper px-md text-caption text-slate">
        <span className="flex min-w-0 items-center gap-xs">
          {isBusy ? (
            <>
              <span className="h-2 w-2 shrink-0 animate-pulse rounded-pill bg-coral" aria-hidden="true" />
              <span className="truncate">Design running{activeJobId ? ` · ${activeJobId.length > 10 ? `${activeJobId.slice(0, 10)}\u2026` : activeJobId}` : ""}</span>
            </>
          ) : state === "poll_timeout" ? (
            <>
              <span className="h-2 w-2 shrink-0 rounded-pill bg-honey" aria-hidden="true" />
              <span className="truncate">Polling timed out</span>
            </>
          ) : displayDesignId ? (
            <span className="truncate">Design ready · {displayDesignId}</span>
          ) : (
            <span>Idle</span>
          )}
        </span>
        <span className="hidden items-center gap-xs sm:flex">
          <span className={`h-2 w-2 rounded-pill ${appStatus ? "bg-clay" : "bg-sage"}`} aria-hidden="true" />
          {appStatus ? "Offline" : "Connected"}
        </span>
        <span className="hidden sm:inline">
          {isPlasmid ? `Model: ${modelVersion ?? "unknown"}` : `Validator: ${shownValidationReport?.validator_version ?? "unknown"}`}
        </span>
      </footer>

      <OutcomeReportModal
        open={outcomeModalOpen}
        designId={outcomeModalTarget?.designId ?? null}
        modelVersion={outcomeModalTarget?.modelVersion ?? null}
        onClose={() => setOutcomeModalOpen(false)}
        onSubmitted={handleOutcomeSubmitted}
        initialReport={outcomeModalTarget?.initialReport}
        provenanceContext={outcomeModalTarget?.provenanceContext}
      />
    </main>
  );
}

function MyOutcomesPanel({ outcomes, onOpen, refreshStatus }: { outcomes: OutcomeReport[]; onOpen: (outcome: OutcomeReport) => void; refreshStatus: "idle" | "refreshing" | "error" }) {
  const sortedOutcomes = [...outcomes].sort((a, b) => new Date(b.reported_at).getTime() - new Date(a.reported_at).getTime());
  return (
    <section className="rounded-md border border-line bg-paper p-md shadow-rest" aria-label="My reported outcomes">
      <div className="flex flex-wrap items-start justify-between gap-sm">
        <div>
          <h2 className="font-serif text-h3 text-ink">My outcomes</h2>
          <p className="mt-2xs text-small leading-5 text-slate">
            Shows outcomes reported from this browser until a backend list endpoint is available. Known designs are refreshed individually when possible.
          </p>
        </div>
        <span className="rounded-sm border border-line bg-mist px-xs py-2xs text-caption font-semibold text-slate">{outcomes.length}</span>
      </div>
      {refreshStatus === "refreshing" ? (
        <p className="mt-sm flex items-center gap-xs text-small text-slate" role="status" aria-busy="true">
          <span className="h-2 w-2 animate-pulse rounded-pill bg-coral" aria-hidden="true" />
          Refreshing outcomes...
        </p>
      ) : null}
      {refreshStatus === "error" && sortedOutcomes.length ? (
        <p className="mt-sm rounded-md border border-line bg-mist p-sm text-small leading-5 text-slate">Could not refresh saved outcomes. The list below shows the most recent reports saved in this browser.</p>
      ) : null}
      {sortedOutcomes.length ? (
        <div className="mt-sm space-y-sm">
          {sortedOutcomes.map((outcome) => (
            <article key={outcome.design_id} className="rounded-md border border-line bg-mist p-md">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="break-all text-sm font-semibold text-ink">{outcome.design_id}</p>
                  <p className="mt-2xs text-xs text-slate">Reported {new Date(outcome.reported_at).toLocaleDateString()}</p>
                </div>
                <OutcomeStatusBadge label={outcome.outcome_label} />
              </div>
              <p className="mt-2 text-small text-slate">Training consent: {outcome.training_consent ? "granted" : "not granted"}</p>
              <button type="button" onClick={() => onOpen(outcome)} className="mt-sm w-full rounded-md border border-line-strong bg-paper px-sm py-xs text-sm font-semibold text-ink hover:bg-mist focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40">
                Review or edit outcome
              </button>
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-sm rounded-md border border-line bg-mist p-sm text-small leading-5 text-slate">No locally known reported outcomes yet. Reports submitted from this browser will appear here.</p>
      )}
    </section>
  );
}

function OutcomeStatusBadge({ label }: { label: OutcomeReport["outcome_label"] }) {
  const className =
    label === "positive"
      ? "border-sage/40 bg-sage/10 text-sage"
      : label === "negative"
        ? "border-clay/40 bg-clay/10 text-clay"
        : "border-honey/40 bg-honey/10 text-honey";
  return <span className={`rounded-pill border px-xs py-2xs text-caption font-semibold capitalize ${className}`}>{label}</span>;
}

function PendingOutcomeToast({ prompt, onOpen, onDismiss }: { prompt: PendingOutcomePrompt; onOpen: (prompt: PendingOutcomePrompt) => void; onDismiss: (prompt: PendingOutcomePrompt) => void }) {
  return (
    <aside className="fixed left-4 right-4 top-4 z-40 rounded-lg border border-line bg-paper p-md shadow-floating sm:left-auto sm:top-auto sm:bottom-4 sm:w-[calc(100%-2rem)] sm:max-w-md" aria-label="Pending outcome prompt">
      <p className="text-caption font-semibold uppercase tracking-[0.06em] text-coral">Outcome follow-up</p>
      <p className="mt-2xs text-sm text-ink">Design {prompt.design_id} is ready for lab outcome feedback.</p>
      <p className="mt-2xs text-xs text-slate">Created {prompt.days_since_created} days ago.</p>
      <div className="mt-sm flex flex-wrap gap-2">
        <button type="button" onClick={() => onOpen(prompt)} className="rounded-md border border-coral bg-coral px-sm py-xs text-sm font-semibold text-paper shadow-rest hover:shadow-raised focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40">
          Report outcome
        </button>
        <button type="button" onClick={() => onDismiss(prompt)} className="rounded-md border border-line-strong bg-paper px-sm py-xs text-sm font-semibold text-ink hover:bg-mist focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40">
          Not now
        </button>
      </div>
    </aside>
  );
}

function PendingPromptFetchMessage() {
  return (
    <section className="rounded-md border border-line bg-paper p-sm text-small leading-5 text-slate shadow-rest" aria-label="Outcome prompt status">
      Outcome follow-ups could not be checked. You can continue designing; prompts will be checked again on reload.
    </section>
  );
}

function JobProgressCard({ jobId, state, elapsedMs }: { jobId: string | null; state: UiState; elapsedMs: number }) {
  const elapsedSeconds = Math.max(0, Math.round(elapsedMs / 1000));
  const label = state === "submitting" ? "Starting design job" : "Designing and validating plasmid";
  return (
    <article className="max-w-3xl rounded-md border border-line bg-mist p-md shadow-rest" role="status" aria-live="polite" aria-atomic="true">
      <div className="mb-2 flex items-center justify-between gap-md text-caption font-semibold uppercase tracking-[0.06em] text-coral">
        <span>{label}</span>
        <span aria-hidden="true">{elapsedSeconds}s</span>
      </div>
      <div className="space-y-sm" aria-hidden>
        <div className="h-2 w-full overflow-hidden rounded-pill bg-paper">
          <div className="h-full w-2/3 origin-left animate-pulse rounded-pill bg-coral/40" />
        </div>
        <div className="grid grid-cols-3 gap-sm text-sm text-slate">
          <span>Retrieving templates</span>
          <span>Generating candidate</span>
          <span>Running checks</span>
        </div>
      </div>
      {jobId ? <p className="mt-sm text-xs text-slate">Job ID: {jobId}</p> : null}
    </article>
  );
}

function RetrievedTemplatesPanel({ result, messageId }: { result: JobResultPayload; messageId: string }) {
  if (!Array.isArray(result.retrieved_templates)) {
    return <ResultNote title="Retrieved templates" text="Template retrieval was not returned for this job." />;
  }

  if (!result.retrieved_templates.length) {
    return <ResultNote title="Retrieved templates" text="No matching templates were retrieved." />;
  }

  return (
    <section className="mt-md rounded-md border border-line bg-mist p-md" aria-label="Retrieved template evidence">
      <h3 className="text-caption font-semibold uppercase tracking-[0.06em] text-slate">Retrieved template evidence</h3>
      <ul className="mt-sm space-y-2xs text-small text-slate">
        {result.retrieved_templates.slice(0, 3).map((template, index) => (
          <li key={`${messageId}-${template.source_id ?? index}`}>
            <span className="font-medium text-ink">Retrieved {index + 1}: {template.name ?? template.source_id ?? "template"}</span>{" "}
            {typeof template.score === "number" ? `(${template.score.toFixed(3)})` : ""}
            <span className="block text-slate">
              {[template.source_id, template.vector_profile, template.source].filter(Boolean).join(" · ") || "No additional source metadata returned."}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function MissingValidationReportPanel() {
  return <ResultNote title="Validation report" text="Validation report was not returned for this job." />;
}

function ResultNote({ title, text }: { title: string; text: string }) {
  return (
    <section className="mt-md rounded-md border border-line bg-mist p-md" aria-label={title}>
      <h3 className="text-caption font-semibold uppercase tracking-[0.06em] text-slate">{title}</h3>
      <p className="mt-2xs text-small leading-5 text-slate">{text}</p>
    </section>
  );
}

function PartialResultNotice({ result }: { result: JobResultPayload }) {
  const hasEvidence = Boolean(result.retrieved_templates?.length || result.validation_report);
  if (!hasEvidence) {
    return null;
  }
  return (
    <section className="mt-md rounded-md border border-honey/40 bg-honey/10 p-md text-small leading-5 text-slate" aria-label="Partial result">
      <p className="font-semibold text-honey">Partial result</p>
      <p className="mt-2xs">
        The job returned supporting evidence but no annotated sequence, so the plasmid map and exports are not available yet. Refine the request or retry the job if a full design was expected.
      </p>
    </section>
  );
}

function overallLabel(report: ValidationReport): string {
  const checks = report.checks ?? [];
  return report.overall ?? (checks.some((check) => normalizeStatus(check.status) === "FAIL")
    ? "FAIL"
    : checks.some((check) => normalizeStatus(check.status) === "WARN")
      ? "WARN"
      : "PASS");
}

function overallBadgeClass(report: ValidationReport): string {
  const overall = overallLabel(report);
  return overall === "PASS"
    ? "border-sage/40 bg-sage/10 text-sage"
    : overall === "WARN"
      ? "border-honey/40 bg-honey/10 text-honey"
      : "border-clay/40 bg-clay/10 text-clay";
}

type DesignHistoryRow = { designId: string; recommendation: string; overall: string; bp: number; features: number };

function SidebarContent({
  variant,
  designHistory,
  selectedDesignId,
  onSelect,
  onNewDesign,
  reportedOutcomes,
  onOpenReportedOutcome,
  outcomeRefreshStatus,
  pendingPromptStatus,
  outcomesCollapsed,
  onToggleOutcomes,
  hasDesign,
  onOpenSheet
}: {
  variant: "desktop" | "sheet";
  designHistory: DesignHistoryRow[];
  selectedDesignId: string | null;
  onSelect: (id: string | null) => void;
  onNewDesign: () => void;
  reportedOutcomes: OutcomeReport[];
  onOpenReportedOutcome: (outcome: OutcomeReport) => void;
  outcomeRefreshStatus: "idle" | "refreshing" | "error";
  pendingPromptStatus: PendingPromptStatus;
  outcomesCollapsed: boolean;
  onToggleOutcomes: () => void;
  hasDesign: boolean;
  onOpenSheet: () => void;
}) {
  if (variant === "desktop") {
    return (
      <nav aria-label="Workspace navigation" className="flex min-h-0 flex-col border-r border-line bg-paper">
        <div className="hidden w-[256px] min-h-0 flex-col overflow-y-auto py-md lg:flex">
          {pendingPromptStatus === "error" ? <div className="px-sm"><PendingPromptFetchMessage /></div> : null}
          <div className="px-sm">
            <button
              type="button"
              onClick={onNewDesign}
              className="w-full rounded-md border border-coral bg-coral px-sm py-xs text-sm font-semibold text-paper shadow-rest hover:shadow-raised focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40"
            >
              New design
            </button>
          </div>
          <div className="mt-md flex-1 overflow-y-auto px-sm">
            <h2 className="sr-only">Design history</h2>
            {designHistory.length ? (
              <ul className="space-y-2xs">
                {designHistory.map((row) => (
                  <li key={row.designId}>
                    <button
                      type="button"
                      onClick={() => onSelect(row.designId)}
                      className={`w-full rounded-sm border border-line bg-paper px-sm py-xs text-left focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40 ${selectedDesignId === row.designId ? "border-l-2 border-l-coral bg-mist" : "hover:bg-mist"}`}
                    >
                      <p className="truncate text-sm font-semibold text-ink">{truncateId(row.designId)}</p>
                      <p className="mt-2xs truncate text-xs text-slate">{truncateSnippet(row.recommendation)}</p>
                      <div className="mt-2xs flex items-center gap-xs">
                        <span className={`rounded-pill border px-xs py-2xs text-caption font-semibold uppercase tracking-[0.06em] ${row.overall === "PASS" ? "border-sage/40 bg-sage/10 text-sage" : row.overall === "WARN" ? "border-honey/40 bg-honey/10 text-honey" : "border-clay/40 bg-clay/10 text-clay"}`}>{row.overall}</span>
                        <span className="text-caption text-slate">{row.bp.toLocaleString()} bp · {row.features} features</span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-small leading-5 text-slate">Designs you complete in this session will list here.</p>
            )}
          </div>
          {reportedOutcomes.length === 0 && !hasDesign ? null : (
            <div className="mt-md px-sm">
              <div className="flex items-center justify-between">
                <button type="button" onClick={onToggleOutcomes} aria-expanded={!outcomesCollapsed} className="text-xs font-semibold text-ink hover:text-coral focus:outline-none focus:ring-2 focus:ring-coral/40">
                  My reported outcomes
                </button>
              </div>
              <div className={outcomesCollapsed ? "hidden" : "mt-2xs"}>
                <MyOutcomesPanel outcomes={reportedOutcomes} onOpen={onOpenReportedOutcome} refreshStatus={outcomeRefreshStatus} />
              </div>
            </div>
          )}
        </div>

        <div className="flex w-[56px] flex-col items-center gap-sm py-md md:flex lg:hidden">
          {pendingPromptStatus === "error" ? (
            <span className="h-2 w-2 rounded-pill bg-clay" aria-label="Outcome prompt status unavailable" role="img" />
          ) : null}
          <button
            type="button"
            onClick={onNewDesign}
            aria-label="New design"
            className="flex h-8 w-8 items-center justify-center rounded-md border border-coral bg-coral text-paper shadow-rest hover:shadow-raised focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40"
          >
            +
          </button>
          <ul className="flex flex-1 flex-col items-center gap-xs overflow-y-auto px-2xs">
            {designHistory.map((row) => (
              <li key={row.designId}>
                <button
                  type="button"
                  onClick={() => onSelect(row.designId)}
                  aria-label={`Select design ${row.designId}, validation ${row.overall}`}
                  className={`flex h-6 w-6 items-center justify-center rounded-pill border ${selectedDesignId === row.designId ? "border-l-2 border-l-coral bg-mist" : row.overall === "PASS" ? "border-sage/40 bg-sage/10" : row.overall === "WARN" ? "border-honey/40 bg-honey/10" : "border-clay/40 bg-clay/10"}`}
                >
                  <span className={`h-2 w-2 rounded-pill ${row.overall === "PASS" ? "bg-sage" : row.overall === "WARN" ? "bg-honey" : "bg-clay"}`} aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={onOpenSheet}
            aria-label="My reported outcomes"
            className="flex h-8 w-8 items-center justify-center rounded-md border border-line bg-paper text-ink hover:border-line-strong focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40"
          >
            <svg viewBox="0 0 16 16" className="h-4 w-4" aria-hidden="true">
              <path fill="currentColor" d="M3 3h10v2H3V3zm0 4h10v2H3V7zm0 4h7v2H3v-2z" />
            </svg>
          </button>
        </div>
      </nav>
    );
  }

  return (
    <div className="flex min-h-0 flex-col">
      {pendingPromptStatus === "error" ? <PendingPromptFetchMessage /> : null}
      <button
        type="button"
        onClick={onNewDesign}
        className="w-full rounded-md border border-coral bg-coral px-sm py-xs text-sm font-semibold text-paper shadow-rest hover:shadow-raised focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40"
      >
        New design
      </button>
      <div className="mt-md flex-1 overflow-y-auto">
        <h2 className="sr-only">Design history</h2>
        {designHistory.length ? (
          <ul className="space-y-2xs">
            {designHistory.map((row) => (
              <li key={row.designId}>
                <button
                  type="button"
                  onClick={() => onSelect(row.designId)}
                  className={`w-full rounded-sm border border-line bg-paper px-sm py-xs text-left focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40 ${selectedDesignId === row.designId ? "border-l-2 border-l-coral bg-mist" : "hover:bg-mist"}`}
                >
                  <p className="truncate text-sm font-semibold text-ink">{truncateId(row.designId)}</p>
                  <p className="mt-2xs truncate text-xs text-slate">{truncateSnippet(row.recommendation)}</p>
                  <div className="mt-2xs flex items-center gap-xs">
                    <span className={`rounded-pill border px-xs py-2xs text-caption font-semibold uppercase tracking-[0.06em] ${row.overall === "PASS" ? "border-sage/40 bg-sage/10 text-sage" : row.overall === "WARN" ? "border-honey/40 bg-honey/10 text-honey" : "border-clay/40 bg-clay/10 text-clay"}`}>{row.overall}</span>
                    <span className="text-caption text-slate">{row.bp.toLocaleString()} bp</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-small leading-5 text-slate">Designs you complete in this session will list here.</p>
        )}
      </div>
      {reportedOutcomes.length === 0 && !hasDesign ? null : (
        <div className="mt-md">
          <h2 className="text-xs font-semibold text-ink">My reported outcomes</h2>
          <div className="mt-2xs">
            <MyOutcomesPanel outcomes={reportedOutcomes} onOpen={onOpenReportedOutcome} refreshStatus={outcomeRefreshStatus} />
          </div>
        </div>
      )}
    </div>
  );
}

function truncateId(id: string): string {
  return id.length > 16 ? `${id.slice(0, 16)}\u2026` : id;
}

function truncateSnippet(text: string): string {
  if (!text) {
    return "No recommendation returned.";
  }
  return text.length > 40 ? `${text.slice(0, 40)}\u2026` : text;
}

function ToolsStrip({
  layout,
  capability,
  capabilityOutcome,
  designId,
  isBusy,
  validationReport,
  exportStatus,
  exportError,
  onExport,
  latestOutcome,
  onOpenOutcome,
  onOpenFullReport
}: {
  layout: "row" | "stack";
  capability: CapabilityKind;
  capabilityOutcome: CapabilityOutcome | null;
  designId: string | null;
  isBusy: boolean;
  validationReport: ValidationReport | null;
  exportStatus: Record<ExportFormat, ExportStatus>;
  exportError: Record<ExportFormat, string | null>;
  onExport: (format: ExportFormat) => Promise<void>;
  latestOutcome: OutcomeReport | null;
  onOpenOutcome: () => void;
  onOpenFullReport: () => void;
}) {
  const candidacy = designId ?? null;
  const isRow = layout === "row";
  const containerClass = "shrink-0 border-t border-line bg-paper";
  const innerClass = isRow ? "grid grid-cols-3 divide-x divide-line" : "flex flex-col divide-y divide-line";
  const cellClass = isRow ? "flex min-h-0 items-center gap-xs overflow-hidden px-sm py-2xs" : "flex flex-col gap-xs px-sm py-2xs";
  const outcomeHint = candidacy
    ? latestOutcome
      ? `Outcome reported ${new Date(latestOutcome.reported_at).toLocaleDateString()}.`
      : "Have lab results? Record them here."
    : "Complete a design job to report lab results.";

  return (
    <section aria-label="Design tools" className={containerClass}>
      <div className={innerClass}>
        <div className={cellClass} aria-label="Validation summary">
          {validationReport ? (
            <>
              <div className="flex min-w-0 items-center gap-xs">
                <span className={`shrink-0 rounded-pill border px-xs py-2xs text-caption font-semibold uppercase tracking-[0.06em] ${overallBadgeClass(validationReport)}`}>{overallLabel(validationReport)}</span>
                <span className="truncate text-caption text-slate">{validationReport.checks?.length ?? 0} check{(validationReport.checks?.length ?? 0) === 1 ? "" : "s"}</span>
              </div>
              <button type="button" onClick={onOpenFullReport} className={`text-xs font-semibold text-coral hover:underline focus:outline-none focus:ring-2 focus:ring-coral/40 ${isRow ? "ml-auto" : ""}`}>
                Open full report
              </button>
            </>
          ) : (
            <span className="text-caption text-slate">No validation report yet.</span>
          )}
        </div>

        <div className={cellClass}>
          {capability === "plasmid" ? (
            <ExportActions designId={candidacy} status={exportStatus} error={exportError} disabledReason={isBusy ? "A new design job is running. Exports stay disabled to avoid downloading the previous design by mistake." : null} onExport={onExport} />
          ) : (
            <CapabilityExportActions outcome={capabilityOutcome} />
          )}
        </div>

        <div className={cellClass} aria-label="Outcome reporting">
          {capability !== "plasmid" ? (
            <span className="truncate text-caption text-slate">Outcome reporting is available for plasmid designs.</span>
          ) : null}
          {capability === "plasmid" && candidacy ? (
            <button
              type="button"
              disabled={isBusy}
              onClick={onOpenOutcome}
              className="shrink-0 rounded-md border border-coral bg-coral px-sm py-2xs text-sm font-semibold text-paper shadow-rest hover:shadow-raised focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40 disabled:cursor-not-allowed disabled:border-line disabled:bg-line disabled:text-slate disabled:shadow-none"
            >
              {latestOutcome ? "Review or edit outcome" : "Report outcome"}
            </button>
          ) : null}
          {capability === "plasmid" ? <span className="truncate text-caption text-slate">{outcomeHint}</span> : null}
        </div>
      </div>
    </section>
  );
}

function ChatPanel({
  messages,
  isBusy,
  state,
  activeJobId,
  jobStartedAt,
  now,
  sessionId,
  input,
  setInput,
  onSubmit,
  activeClarification,
  isPollTimeoutRecovery,
  onCheckJob,
  onStartOver,
  onViewMap,
  retryableError,
  capability,
  onCapabilityChange,
  capabilityForm,
  capabilityBusy
}: {
  messages: ChatMessage[];
  isBusy: boolean;
  state: UiState;
  activeJobId: string | null;
  jobStartedAt: number | null;
  now: number;
  sessionId: string | null;
  input: string;
  setInput: (value: string) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  activeClarification: string | null;
  isPollTimeoutRecovery: boolean;
  onCheckJob: () => void;
  onStartOver: () => void;
  onViewMap: () => void;
  retryableError: boolean;
  capability: CapabilityKind;
  onCapabilityChange: (kind: CapabilityKind) => void;
  capabilityForm: ReactNode;
  capabilityBusy: boolean;
}) {
  return (
    <>
      <div className="flex h-10 shrink-0 items-center border-b border-line px-md">
        <div className="flex items-center gap-xs">
          <h2 className="font-serif text-h3 text-ink">Conversation</h2>
          {isBusy || capabilityBusy ? (
            <span className="flex items-center gap-xs text-caption text-slate" role="status">
              <span className="h-2 w-2 animate-pulse rounded-pill bg-coral" aria-hidden="true" />
              Design running
            </span>
          ) : null}
        </div>
      </div>

      <CapabilitySelector value={capability} onChange={onCapabilityChange} disabled={isBusy || capabilityBusy} />

      <div className="flex-1 space-y-sm overflow-y-auto px-md py-md">
        {messages.map((message) => (
          <article
            key={message.id}
            id={message.result ? `message-${message.id}` : undefined}
            className={`max-w-3xl border p-4 shadow-rest ${
              message.role === "user"
                ? "ml-auto border-coral/30 bg-coral/5"
                : message.kind === "error"
                  ? "border-clay/40 bg-clay/5"
                  : message.kind === "clarification"
                    ? "border-honey/40 bg-honey/5"
                    : "border-line bg-paper"
            }`}
          >
            <div className="mb-2 text-xs font-semibold uppercase text-slate">
              {message.role === "user"
                ? message.kind === "clarification_answer"
                  ? "Clarification answer"
                  : "Researcher"
                : message.kind === "clarification"
                  ? "Clarification"
                  : message.kind === "status"
                    ? "Job status"
                    : "Design agent"}
            </div>
            <p className="whitespace-pre-wrap text-sm leading-6 text-ink">{message.text}</p>
            {message.result ? (
              message.result.validation_report ? <ValidationReportPanel report={message.result.validation_report} /> : <MissingValidationReportPanel />
            ) : null}
            {message.result && !message.result.annotated_sequence && !message.result.capability ? <PartialResultNotice result={message.result} /> : null}
            {message.result && !message.result.capability ? <RetrievedTemplatesPanel result={message.result} messageId={message.id} /> : null}
            {message.result?.capability ? (
              <a
                href={`#${capabilityPanelId(message.result.capability)}`}
                onClick={onViewMap}
                className="mt-3 inline-flex rounded-sm px-xs py-2xs text-xs font-semibold text-coral hover:underline focus:outline-none focus:ring-2 focus:ring-coral/40"
              >
                View {capabilityLabel(message.result.capability).toLowerCase()} result
              </a>
            ) : null}
            {message.result?.annotated_sequence ? (
              <a
                href="#plasmid-map"
                onClick={onViewMap}
                className="mt-3 inline-flex rounded-sm px-xs py-2xs text-xs font-semibold text-coral hover:underline focus:outline-none focus:ring-2 focus:ring-coral/40"
              >
                View plasmid map
              </a>
            ) : null}
          </article>
        ))}
        {isBusy ? (
          <JobProgressCard jobId={activeJobId} state={state} elapsedMs={jobStartedAt ? now - jobStartedAt : 0} />
        ) : null}
      </div>

      {capability !== "plasmid" ? (
        <div className="max-h-[55%] shrink-0 overflow-y-auto">{capabilityForm}</div>
      ) : (
      <form onSubmit={onSubmit} className="shrink-0 border-t border-line bg-paper px-sm py-sm" aria-label="Design composer">
        {state === "awaiting_clarification" && activeClarification ? (
          <div className="mb-3 rounded-md border border-honey/40 bg-honey/10 p-md text-sm text-ink">
            <span className="font-semibold text-honey">Waiting for your answer: </span>
            {activeClarification.replace(/^To design this for you, I need to know:\s*/i, "")}
          </div>
        ) : null}
        {!sessionId && state === "idle" ? (
          <div className="mb-3 flex flex-wrap gap-2">
            {EXAMPLE_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => setInput(prompt)}
                className="rounded-md border border-line bg-paper px-sm py-xs text-left text-xs text-ink hover:text-coral focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40"
              >
                {prompt}
              </button>
            ))}
          </div>
        ) : null}
        <label htmlFor="goal" className="sr-only">
          Experimental goal
        </label>
        <textarea
          id="goal"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          disabled={isBusy || isPollTimeoutRecovery}
          rows={3}
          placeholder={
            state === "awaiting_clarification"
              ? "Answer the clarification question..."
              : "Describe the host, marker, payload, promoter, and any constraints..."
          }
          className="min-h-20 w-full resize-none rounded-md border border-line bg-paper px-sm py-xs text-sm text-ink shadow-rest outline-none focus:border-coral focus:ring-2 focus:ring-coral/40"
        />
        <button
          type="submit"
          disabled={!input.trim() || isBusy || isPollTimeoutRecovery}
          className="mt-2 h-10 w-full rounded-md border border-coral bg-coral px-sm text-sm font-semibold text-paper shadow-rest hover:shadow-raised focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40 disabled:cursor-not-allowed disabled:border-line disabled:bg-line disabled:text-slate disabled:shadow-none"
        >
          {state === "submitting"
            ? "Starting"
            : state === "polling"
              ? "Designing"
              : state === "awaiting_clarification"
                ? "Answer"
                : state === "error" && retryableError
                  ? "Try again"
                  : sessionId
                    ? "Refine"
                    : "Design"}
        </button>
        {activeJobId ? (
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate">
            <span>
              Job {activeJobId} is still queued or running. For a local demo, confirm the worker or deterministic demo fixture is running before retrying.
            </span>
            {state === "poll_timeout" ? (
              <>
                <button type="button" className="rounded-md border border-line-strong bg-paper px-sm py-2xs text-xs font-semibold text-ink hover:bg-mist focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/40" onClick={onCheckJob}>
                  Check status
                </button>
                <button type="button" className="rounded-sm px-xs py-2xs font-semibold text-ink hover:text-coral focus:outline-none focus:ring-2 focus:ring-coral/40" onClick={onStartOver}>
                  Start over
                </button>
              </>
            ) : null}
          </div>
        ) : null}
      </form>
      )}
    </>
  );
}

function capabilityLabel(kind: string): string {
  return CAPABILITY_OPTIONS.find((option) => option.kind === kind)?.label ?? kind;
}

function capabilityPanelId(kind: string): string {
  return kind === "aav" ? "aav-panel" : kind === "assembly" ? "assembly-panel" : "grna-panel";
}

function jobError(job: JobStatusResponse): ApiError {
  const detail = job.error_detail;
  if (detail) {
    return new ApiError(detail.message, {
      code: detail.code,
      retryable: detail.retryable,
      details: detail.details
    });
  }
  return new ApiError(job.error ?? "The design job failed before producing a result.", { code: "job_failed" });
}

function friendlyErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const fieldText = error.fieldErrors.length
      ? ` ${error.fieldErrors.map((field) => `${field.field}: ${field.message}`).join(" ")}`
      : "";
    const retryText = error.retryable && !/try again/i.test(error.message) ? " Try again in a moment." : "";
    return `${error.message}${fieldText}${retryText}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "The design request failed.";
}

function formatLabel(format: ExportFormat): string {
  return format === "genbank" ? "GenBank" : "FASTA";
}

function isPollingTimeout(error: unknown): error is ApiError {
  return error instanceof ApiError && error.code === "job_poll_timeout";
}

function normalizeJobResult(result: unknown): JobResultPayload {
  if (!result || typeof result !== "object") {
    return {};
  }
  const record = result as JobResultPayload;
  if (record.design && typeof record.design === "object") {
    const design = record.design as JobResultPayload;
    return { ...design, ...record, design };
  }
  return record;
}

function clarificationQuestion(result: JobResultPayload): string | null {
  return (
    result.clarification_question ??
    (result.design_spec?.clarification_needed ? result.design_spec.clarification_question ?? null : null)
  );
}

function resultSummary(result: JobResultPayload): string {
  const sequence = result.annotated_sequence;
  const recommendation = result.recommendation_text ?? result.design?.recommendation_text;
  if (recommendation) {
    return recommendation;
  }
  if (sequence) {
    return `Generated annotated ${sequence.topology} sequence with ${sequence.sequence.length.toLocaleString()} bp and ${sequence.features.length} labeled features.`;
  }
  return "Design job completed. Review the returned templates and validation details.";
}

function promptKey(prompt: PendingOutcomePrompt): string {
  return `${prompt.design_id}:${prompt.session_id}`;
}

function readDismissedPromptKeys(): string[] {
  try {
    const raw = window.sessionStorage.getItem(DISMISSED_OUTCOME_PROMPTS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === "string") : [];
  } catch {
    return [];
  }
}

function persistDismissedPromptKey(current: string[], key: string): string[] {
  const next = current.includes(key) ? current : [...current, key];
  try {
    window.sessionStorage.setItem(DISMISSED_OUTCOME_PROMPTS_KEY, JSON.stringify(next));
  } catch {
    return next;
  }
  return next;
}

function readReportedOutcomes(): OutcomeReport[] {
  try {
    const raw = window.localStorage.getItem(REPORTED_OUTCOMES_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(isOutcomeReport);
  } catch {
    return [];
  }
}

function persistReportedOutcomes(outcomes: OutcomeReport[]): OutcomeReport[] {
  try {
    window.localStorage.setItem(REPORTED_OUTCOMES_KEY, JSON.stringify(outcomes));
  } catch {
    return outcomes;
  }
  return outcomes;
}

function upsertReportedOutcome(current: OutcomeReport[], outcome: OutcomeReport): OutcomeReport[] {
  return mergeReportedOutcomes(current, [outcome]);
}

function mergeReportedOutcomes(current: OutcomeReport[], incoming: OutcomeReport[]): OutcomeReport[] {
  const byDesignId = new Map(current.map((outcome) => [outcome.design_id, outcome]));
  for (const outcome of incoming) {
    byDesignId.set(outcome.design_id, outcome);
  }
  return Array.from(byDesignId.values()).sort((a, b) => new Date(b.reported_at).getTime() - new Date(a.reported_at).getTime());
}

function isOutcomeReport(value: unknown): value is OutcomeReport {
  if (!value || typeof value !== "object") {
    return false;
  }
  const record = value as Partial<OutcomeReport>;
  return (
    typeof record.design_id === "string" &&
    typeof record.model_version === "string" &&
    typeof record.training_consent === "boolean" &&
    (record.outcome_label === "positive" || record.outcome_label === "negative" || record.outcome_label === "ambiguous") &&
    typeof record.reported_at === "string"
  );
}
