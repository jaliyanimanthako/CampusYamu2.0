import { getAccessToken, getRuntimeConfig } from "../auth/supabase.ts";
import {
  buildMockCareerStatus,
  buildMockChatResponse,
  buildMockRecommendationResponse,
  MOCK_OPTIONS,
  startMockCareerResearch,
} from "./mockData.ts";
import type {
  AuthResponse,
  AuthUser,
  CareerResearchRequest,
  CareerResearchResponse,
  CareerStatus,
  ChatHistory,
  ChatRequest,
  ChatResponse,
  ChatSummary,
  Deleted,
  Health,
  Me,
  Options,
  ProgressEvent,
  RecommendationRequest,
  RecommendationResponse,
  SavedResults,
} from "./types.ts";

export function getApiBaseUrl(): string {
  const configured = getRuntimeConfig().apiBaseUrl;
  if (configured) return configured.replace(/\/+$/, "");
  if (import.meta.env.DEV && typeof window !== "undefined" && window.location.port === "5173") {
    return "";
  }
  return "http://127.0.0.1:8780";
}

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
  return `${getApiBaseUrl()}${normalizedPath}`;
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
  if (includeApiKey && !headers.has("Authorization")) {
    const token = await getAccessToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
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

/** The server has no /v1/recommendations/stream (an older backend): use postRecommendations instead. */
export class StreamUnsupportedError extends Error {}

async function simulateProgress(onProgress: (event: ProgressEvent) => void): Promise<void> {
  const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));
  onProgress({ step: "eligibility", status: "done", courses_checked: 126, eligible: 55 });
  onProgress({ step: "travel", status: "done", offerings: 89 });
  onProgress({ step: "interests", status: "running" });
  for (let i = 0; i <= 55; i += 11) {
    onProgress({ step: "zscore", status: "running", done: i, total: 55 });
    await wait(90);
  }
  onProgress({ step: "interests", status: "done" });
  onProgress({ step: "zscore", status: "done", done: 55, total: 55 });
  onProgress({ step: "ranking", status: "running" });
  await wait(250);
  onProgress({ step: "ranking", status: "done" });
}

/**
 * POST /v1/recommendations/stream: the same request, with each pipeline step reported as it finishes
 * (server-sent events). Resolves with the report; rejects with ApiError like apiRequest, or with
 * StreamUnsupportedError when the backend predates the endpoint (nothing has run on the server then).
 */
export async function postRecommendationsStream(
  payload: RecommendationRequest,
  onProgress: (event: ProgressEvent) => void,
): Promise<RecommendationResponse> {
  if (isDemoMode()) {
    await simulateProgress(onProgress);
    return buildMockRecommendationResponse(payload);
  }
  const controller = new AbortController();
  let timedOut = false;
  const timerId = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, HEAVY_TIMEOUT_MS);
  const headers = new Headers({ "Content-Type": "application/json", Accept: "text/event-stream" });
  const token = await getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(buildUrl("/v1/recommendations/stream"), {
      method: "POST",
      body: JSON.stringify(payload),
      headers,
      signal: controller.signal,
    });
  } catch {
    window.clearTimeout(timerId);
    if (timedOut) {
      throw new ApiError(0, [`Request timed out after ${Math.round(HEAVY_TIMEOUT_MS / 1000)}s. Please try again.`],
        { isTimeout: true });
    }
    throw new ApiError(0, ["Unable to reach the CampusYamu API. Check that the backend server is running."],
      { isNetwork: true });
  }
  if (response.status === 404 || response.status === 405) {
    window.clearTimeout(timerId);
    throw new StreamUnsupportedError("No /v1/recommendations/stream on this server");
  }
  if (!response.ok || !response.body) {
    window.clearTimeout(timerId);
    throw new ApiError(response.status, await parseErrorBody(response));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (value) buffer += decoder.decode(value, { stream: true });
      let cut: number;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        let kind = "message";
        let data = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) kind = line.slice(6).trim();
          else if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (!data) continue;
        const parsed = JSON.parse(data) as Record<string, unknown>;
        if (kind === "progress") {
          onProgress(parsed as unknown as ProgressEvent);
        } else if (kind === "result") {
          const status = Number(parsed.status ?? 500);
          if (status >= 400) {
            const errors = Array.isArray(parsed.errors) ? parsed.errors.map(String) : [];
            throw new ApiError(status, errors.length ? errors : [`Request failed (${status})`]);
          }
          return parsed as unknown as RecommendationResponse;
        }
      }
      if (done) break;
    }
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (timedOut) {
      throw new ApiError(0, [`Request timed out after ${Math.round(HEAVY_TIMEOUT_MS / 1000)}s. Please try again.`],
        { isTimeout: true });
    }
    throw new ApiError(0, ["The connection dropped before the results arrived. Please try again."]);
  } finally {
    window.clearTimeout(timerId);
  }
  throw new ApiError(0, ["The connection closed before the results arrived. Please try again."]);
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

export function getMe(): Promise<Me> {
  return apiRequest<Me>("/v1/me", { method: "GET", timeoutMs: DEFAULT_TIMEOUT_MS });
}

export function getMyResults(): Promise<SavedResults> {
  return apiRequest<SavedResults>("/v1/me/results", { method: "GET", timeoutMs: DEFAULT_TIMEOUT_MS });
}

export function getMyChats(): Promise<ChatSummary[]> {
  return apiRequest<ChatSummary[]>("/v1/me/chats", { method: "GET", timeoutMs: DEFAULT_TIMEOUT_MS });
}

export function getMyChatHistory(
  uniCode: string,
  before?: number,
  limit = 100,
): Promise<ChatHistory> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (before != null) params.set("before", String(before));
  return apiRequest<ChatHistory>(
    `/v1/me/chats/${encodeURIComponent(uniCode)}?${params.toString()}`,
    { method: "GET", timeoutMs: DEFAULT_TIMEOUT_MS },
  );
}

export function deleteMyChat(uniCode: string): Promise<Deleted> {
  return apiRequest<Deleted>(`/v1/me/chats/${encodeURIComponent(uniCode)}`, {
    method: "DELETE",
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function postSignUp(payload: {
  email: string;
  password: string;
  name?: string;
  avatar?: string;
}): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/v1/auth/signup", {
    method: "POST",
    includeApiKey: false,
    body: JSON.stringify(payload),
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function postSignIn(payload: {
  email: string;
  password: string;
}): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/v1/auth/signin", {
    method: "POST",
    includeApiKey: false,
    body: JSON.stringify(payload),
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}

export function postSetAvatar(avatar: string): Promise<AuthUser> {
  return apiRequest<AuthUser>("/v1/auth/avatar", {
    method: "POST",
    body: JSON.stringify({ avatar }),
    timeoutMs: DEFAULT_TIMEOUT_MS,
  });
}
