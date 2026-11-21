import type {
  ChatTurn,
  RecommendationReport,
  SubjectGrade,
} from "../api/types.ts";

export interface ProfileFormState {
  stream: string;
  al: SubjectGrade[];
  ol: Record<string, string>;
  cgt: string;
  zScore: string;
  admissionDistrict: string;
  homeDistrict: string;
  homeTown: string;
  preferences: string;
  useLlm: boolean;
}

const KEYS = {
  form: "campusyamu_form_state_v1",
  report: "campusyamu_report_v1",
  usedLlm: "campusyamu_used_llm_v1",
  shortlist: "campusyamu_shortlist_v1",
  chatPrefix: "campusyamu_chat_v1_",
} as const;

function safeReadJson<T>(key: string): T | null {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function safeWriteJson(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage quota or availability errors
  }
}

export function loadFormState(): ProfileFormState | null {
  // state saved before home towns has dsDivision; many DS divisions are also town names
  const saved = safeReadJson<ProfileFormState & { dsDivision?: string }>(KEYS.form);
  if (!saved) return null;
  const { dsDivision, ...rest } = saved;
  return { ...rest, homeTown: saved.homeTown ?? dsDivision ?? "" };
}

export function saveFormState(state: ProfileFormState): void {
  safeWriteJson(KEYS.form, state);
}

export function loadReport(): RecommendationReport | null {
  return safeReadJson<RecommendationReport>(KEYS.report);
}

export function saveReport(report: RecommendationReport, usedLlm: boolean): void {
  safeWriteJson(KEYS.report, report);
  safeWriteJson(KEYS.usedLlm, usedLlm);
}

export function loadUsedLlm(): boolean {
  return Boolean(safeReadJson<boolean>(KEYS.usedLlm));
}

export function clearReport(): void {
  try {
    window.localStorage.removeItem(KEYS.report);
    window.localStorage.removeItem(KEYS.usedLlm);
  } catch {
    // Ignore storage errors
  }
}

export function resetAllSessionData(): void {
  try {
    window.localStorage.removeItem(KEYS.form);
    window.localStorage.removeItem(KEYS.report);
    window.localStorage.removeItem(KEYS.usedLlm);
    window.localStorage.removeItem(KEYS.shortlist);
  } catch {
    // Ignore storage errors
  }
}

export function loadShortlist(): string[] {
  return safeReadJson<string[]>(KEYS.shortlist) ?? [];
}

export function saveShortlist(uniCodes: string[]): void {
  safeWriteJson(KEYS.shortlist, uniCodes);
}

export function loadChatHistory(uniCode: string): ChatTurn[] {
  return safeReadJson<ChatTurn[]>(`${KEYS.chatPrefix}${uniCode}`) ?? [];
}

export function saveChatHistory(uniCode: string, turns: ChatTurn[]): void {
  safeWriteJson(`${KEYS.chatPrefix}${uniCode}`, turns);
}
