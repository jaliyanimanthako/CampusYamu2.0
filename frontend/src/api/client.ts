import {
  buildMockCareerStatus,
  buildMockChatResponse,
  buildMockRecommendationResponse,
  MOCK_OPTIONS,
  startMockCareerResearch,
} from "./mockData.ts";
import type {
  CareerResearchRequest,
  CareerResearchResponse,
  CareerStatus,
  ChatRequest,
  ChatResponse,
  Health,
  Options,
  RecommendationRequest,
  RecommendationResponse,
} from "./types.ts";

const RAW_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ||
  "http://127.0.0.1:8780";

export const API_BASE_URL = RAW_BASE_URL.replace(/\/+$/, "");

const API_KEY = (import.meta.env.VITE_API_KEY as string | undefined)?.trim() || "";
const DEMO_MODE_KEY = "campusyamu_demo_mode";

export function isDemoMode(): boolean {
  if ((import.meta.env.VITE_USE_MOCK as string | undefined)?.trim() === "true") {
    return true;
  }
  try {
    return window.sessionStorage.getItem(DEMO_MODE_KEY) === "true";
  } catch {
    return false;
  }
}

export function setDemoMode(enabled: boolean): void {
  try {
    if (enabled) {
      window.sessionStorage.setItem(DEMO_MODE_KEY, "true");
    } else {
      window.sessionStorage.removeItem(DEMO_MODE_KEY);
    }
  } catch {
    // Ignore storage errors
  }
}

export const DEFAULT_TIMEOUT_MS = 15_000;
export const HEAVY_TIMEOUT_MS = 95_000;

export class ApiError extends Error {
  readonly status: number;
  readonly errors: string[];
  readonly isTimeout: boolean;
  readonly isNetwork: boolean;

  constructor(
    status: number,
    errors: string[],
    options?: { isTimeout?: boolean; isNetwork?: boolean },
  ) {
    super(errors[0] || `Request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.errors = errors;
    this.isTimeout = Boolean(options?.isTimeout);
    this.isNetwork = Boolean(options?.isNetwork);
  }
}

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
  includeApiKey?: boolean;
}

function buildUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

async function parseErrorBody(response: Response): Promise<string[]> {
  try {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const data = (await response.json()) as { errors?: unknown; detail?: unknown };
      if (Array.isArray(data.errors) && data.errors.length > 0) {
        return data.errors.map((e) => String(e));
      }
      if (typeof data.detail === "string" && data.detail.trim()) {
        return [data.detail];
      }
    } else {
      const text = (await response.text()).trim();
      if (text) return [text];
    }
  } catch {
    // Fall through to status-based message
  }

  switch (response.status) {
    case 401:
      return ["Unauthorized: missing or invalid X-API-Key."];
    case 409:
      return ["Another career research job is currently running."];
    case 422:
      return ["Request validation failed. Please check your inputs."];
    case 502:
      return ["Upstream AI service failed. Please try again."];
    default:
      return [`Request failed with status ${response.status}.`];
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const {
    timeoutMs = DEFAULT_TIMEOUT_MS,
    includeApiKey = true,
    headers: customHeaders,
    signal: externalSignal,
    ...fetchOptions
  } = options;

  const controller = new AbortController();
  let timedOut = false;

  const onExternalAbort = () => controller.abort();
  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort();
    } else {
      externalSignal.addEventListener("abort", onExternalAbort, { once: true });
    }
  }

  const timerId = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  const headers = new Headers(customHeaders);
  if (fetchOptions.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (includeApiKey && API_KEY && !headers.has("X-API-Key")) {
    headers.set("X-API-Key", API_KEY);
  }

  try {
    const response = await fetch(buildUrl(path), {
      ...fetchOptions,
      headers,
      signal: controller.signal,
    });

    if (!response.ok) {
      const errors = await parseErrorBody(response);
      throw new ApiError(response.status, errors);
    }

    return (await response.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) {
      throw err;
    }
    if (timedOut) {
      throw new ApiError(
        0,
        [`Request timed out after ${Math.round(timeoutMs / 1000)}s. Please try again.`],
        { isTimeout: true },
      );
    }
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(0, ["Request was cancelled."]);
    }
    throw new ApiError(
      0,
      ["Unable to reach the CampusYamu API. Check that the backend server is running."],
      { isNetwork: true },
    );
  } finally {
    window.clearTimeout(timerId);
    if (externalSignal) {
      externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }
}

export async function getHealth(): Promise<Health> {
  if (isDemoMode()) {
    return {
      ok: true,
      version: "demo",
      llm_available: MOCK_OPTIONS.llm_available,
    };
  }
  return apiRequest<Health>("/v1/health", {
    method: "GET",
    includeApiKey: false,
    timeoutMs: 5_000,
  });
}

export async function getOptions(): Promise<Options> {
  if (isDemoMode()) {
    return MOCK_OPTIONS;
  }
  return apiRequest<Options>("/v1/options", {
    method: "GET",
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function getCourses(): Promise<string[]> {
  return apiRequest<string[]>("/v1/courses", {
    method: "GET",
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export async function postRecommendations(
  payload: RecommendationRequest,
): Promise<RecommendationResponse> {
  if (isDemoMode()) {
    await new Promise((resolve) => window.setTimeout(resolve, 650));
    return buildMockRecommendationResponse(payload);
  }
  return apiRequest<RecommendationResponse>("/v1/recommendations", {
    method: "POST",
    body: JSON.stringify(payload),
    timeoutMs: HEAVY_TIMEOUT_MS,
  });
}

export async function postChat(payload: ChatRequest): Promise<ChatResponse> {
  if (isDemoMode()) {
    await new Promise((resolve) => window.setTimeout(resolve, 500));
    return buildMockChatResponse(payload);
  }
  return apiRequest<ChatResponse>("/v1/chat", {
    method: "POST",
    body: JSON.stringify(payload),
    timeoutMs: HEAVY_TIMEOUT_MS,
  });
}

export async function getCareerOutlook(course: string): Promise<CareerStatus> {
  if (isDemoMode()) {
    return buildMockCareerStatus(course);
  }
  const query = encodeURIComponent(course);
  return apiRequest<CareerStatus>(`/v1/career-outlook?course=${query}`, {
    method: "GET",
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export async function postCareerResearch(
  payload: CareerResearchRequest,
): Promise<CareerResearchResponse> {
  if (isDemoMode()) {
    return startMockCareerResearch(payload.course);
  }
  return apiRequest<CareerResearchResponse>("/v1/career-outlook/research", {
    method: "POST",
    body: JSON.stringify(payload),
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}
