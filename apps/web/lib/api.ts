import { API_BASE_URL } from "@/lib/config";
import type {
  AavDesignResponse,
  AavParts,
  AavRequestBody,
  AssemblyDesignResponse,
  AssemblyRequestBody,
  GrnaDesignResponse,
  GrnaReference,
  GrnaRequestBody
} from "@/lib/capabilities";
import type {
  ApiErrorEnvelope,
  ApiFieldError,
  JobAcceptedResponse,
  JobStatusResponse,
  OutcomeResponse,
  OutcomeReport,
  PendingOutcomePrompt,
  PendingOutcomePromptsResponse,
  SessionResponse
} from "@/lib/types";

const USER_ID_HEADER = "web-demo-user";

export class ApiError extends Error {
  status?: number;
  code?: string;
  retryable: boolean;
  fieldErrors: ApiFieldError[];
  details: Record<string, unknown>;
  lastJob?: JobStatusResponse;

  constructor(
    message: string,
    options: {
      status?: number;
      code?: string;
      retryable?: boolean;
      fieldErrors?: ApiFieldError[];
      details?: Record<string, unknown>;
      lastJob?: JobStatusResponse;
    } = {}
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.retryable = options.retryable ?? false;
    this.fieldErrors = options.fieldErrors ?? [];
    this.details = options.details ?? {};
    this.lastJob = options.lastJob;
  }
}

export async function createSession(): Promise<SessionResponse> {
  return request<SessionResponse>("/v1/sessions", { method: "POST" });
}

export async function submitDesign(sessionId: string, goal: string): Promise<JobAcceptedResponse> {
  return request<JobAcceptedResponse>(`/v1/sessions/${encodeURIComponent(sessionId)}/design`, {
    method: "POST",
    body: JSON.stringify({ goal })
  });
}

export async function submitRefinement(sessionId: string, instruction: string): Promise<JobAcceptedResponse> {
  return request<JobAcceptedResponse>(`/v1/sessions/${encodeURIComponent(sessionId)}/refine`, {
    method: "POST",
    body: JSON.stringify({ instruction })
  });
}

export async function getJob(jobId: string): Promise<JobStatusResponse> {
  return request<JobStatusResponse>(`/v1/jobs/${encodeURIComponent(jobId)}`, { method: "GET" });
}

export async function pollJob(
  jobId: string,
  options: { intervalMs?: number; timeoutMs?: number; onUpdate?: (job: JobStatusResponse) => void } = {}
) {
  const intervalMs = options.intervalMs ?? 750;
  const timeoutMs = options.timeoutMs ?? 30000;
  const startedAt = Date.now();

  for (;;) {
    const job = await getJob(jobId);
    options.onUpdate?.(job);
    const status = job.status.toLowerCase();
    if (status === "completed" || status === "succeeded" || status === "failed" || job.error) {
      return job;
    }
    if (Date.now() - startedAt > timeoutMs) {
      throw new ApiError(
        `The job is still running. You can try again in a moment with job ID ${jobId}.`,
        { code: "job_poll_timeout", retryable: true, details: { job_id: jobId }, lastJob: job }
      );
    }
    await sleep(job.retry_after_ms ?? intervalMs);
  }
}

export async function exportDesign(designId: string, format: "genbank" | "fasta"): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/v1/designs/${encodeURIComponent(designId)}/export?format=${format}`);
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return response.blob();
}

export async function submitOutcome(designId: string, report: OutcomeReport): Promise<OutcomeReport> {
  const response = await request<OutcomeResponse>(`/v1/designs/${encodeURIComponent(designId)}/outcome`, {
    method: "POST",
    body: JSON.stringify(report)
  });
  return response.report;
}

export async function getOutcome(designId: string): Promise<OutcomeReport> {
  const response = await request<OutcomeResponse>(`/v1/designs/${encodeURIComponent(designId)}/outcome`, { method: "GET" });
  return response.report;
}

export async function getPendingOutcomePrompts(): Promise<PendingOutcomePrompt[]> {
  const response = await request<PendingOutcomePromptsResponse>("/v1/users/me/pending-outcome-prompts", { method: "GET" });
  return response.prompts;
}

export async function getAavParts(): Promise<AavParts> {
  return request<AavParts>("/v1/aav/parts", { method: "GET" });
}

export async function designAav(body: AavRequestBody): Promise<AavDesignResponse> {
  return request<AavDesignResponse>("/v1/aav/design", { method: "POST", body: JSON.stringify(body) });
}

export async function designAssembly(body: AssemblyRequestBody): Promise<AssemblyDesignResponse> {
  return request<AssemblyDesignResponse>("/v1/assembly/design", { method: "POST", body: JSON.stringify(body) });
}

export async function getGrnaReference(): Promise<GrnaReference> {
  return request<GrnaReference>("/v1/grna/reference", { method: "GET" });
}

export async function designGrna(body: GrnaRequestBody): Promise<GrnaDesignResponse> {
  return request<GrnaDesignResponse>("/v1/grna/design", { method: "POST", body: JSON.stringify(body) });
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-User-ID": USER_ID_HEADER,
      ...(init.headers ?? {})
    }
  });
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return response.json() as Promise<T>;
}

async function parseApiError(response: Response): Promise<ApiError> {
  const text = await response.text();
  if (text) {
    try {
      const body = JSON.parse(text) as Partial<ApiErrorEnvelope> & { detail?: unknown };
      const detail = capabilityErrorDetail(body.detail);
      if (!body.error?.message && detail) {
        return new ApiError(detail, { status: response.status });
      }
      if (body.error?.message) {
        return new ApiError(body.error.message, {
          status: response.status,
          code: body.error.code,
          retryable: body.error.retryable,
          fieldErrors: body.error.field_errors,
          details: body.error.details
        });
      }
    } catch {
      return new ApiError(text, { status: response.status });
    }
  }
  return new ApiError(`API request failed with ${response.status}`, { status: response.status });
}

// The capability routes report a rejected request as `{ "detail": ... }`, either a
// message string or a list of field errors, rather than the workspace envelope.
function capabilityErrorDetail(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (item && typeof item === "object") {
          const record = item as { loc?: unknown[]; msg?: unknown };
          const where = Array.isArray(record.loc) ? record.loc.filter((part) => part !== "body").join(".") : "";
          return typeof record.msg === "string" ? (where ? `${where}: ${record.msg}` : record.msg) : null;
        }
        return null;
      })
      .filter((part): part is string => Boolean(part));
    return parts.length ? parts.join("; ") : null;
  }
  return null;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
