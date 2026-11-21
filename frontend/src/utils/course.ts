import type { BandKey } from "../api/types.ts";

export interface BandMeta {
  id: BandKey;
  label: string;
  desc: string;
  color: string;
}

export const BANDS: readonly BandMeta[] = [
  {
    id: "strong",
    label: "Strong",
    desc: "Your Z-score has cleared the cut-off in past years",
    color: "var(--blue)",
  },
  {
    id: "competitive",
    label: "Competitive",
    desc: "Close to the cut-off: could go either way",
    color: "var(--lav)",
  },
  {
    id: "reach",
    label: "Reach",
    desc: "Somewhat below recent cut-offs",
    color: "var(--mustard)",
  },
  {
    id: "unlikely",
    label: "Unlikely",
    desc: "Well below recent cut-offs",
    color: "color-mix(in srgb, var(--ink) 22%, var(--bg))",
  },
  {
    id: "no_history",
    label: "No history",
    desc: "No past cut-offs to compare",
    color: "var(--line)",
  },
] as const;

export const FORM_STEPS = [
  "Stream & subjects",
  "Scores",
  "Where you live",
  "Interests",
] as const;

/** The analysing screen's steps, in the order the pipeline runs them (POST /v1/recommendations/stream). */
export const ANALYSING_AGENTS = [
  { id: "eligibility", k: "Eligibility", d: "subject rules", msg: "Checking your subjects against every course's rules" },
  { id: "travel", k: "Travel", d: "from home", msg: "Measuring the road from your home to each campus" },
  { id: "zscore", k: "Z-score", d: "past cut-offs", msg: "Comparing your Z-score with six years of cut-offs" },
  { id: "interests", k: "Interests", d: "what you like", msg: "Matching courses to what you want to study" },
  { id: "ranking", k: "Ranking", d: "best order", msg: "Balancing chances, interests and distance" },
] as const;

export const RANKING_MODES = [
  { id: "distance", label: "Balanced" },
  { id: "zscore", label: "By chance" },
  { id: "preference", label: "By interest" },
] as const;

export type RankingMode = (typeof RANKING_MODES)[number]["id"];

export type CourseArea =
  | "medicine"
  | "it"
  | "engineering"
  | "management"
  | "arts"
  | "science";

/** Map a course name to its illustration area (`public/figures/area-<area>.webp`). */
export function courseArea(name: string): CourseArea {
  const n = name.toLowerCase();
  if (/tourism|hospitality/.test(n)) return "management";
  if (/medicine|dental|nursing|pharm|health|veterinary|medical|physiotherapy|radiograph|laboratory/.test(n)) {
    return "medicine";
  }
  if (/computer|information|software|data science|ict|artificial/.test(n)) return "it";
  if (/engineer|technology|quantity|architect|design|surveying|town/.test(n)) return "engineering";
  if (/management|commerce|account|business|financ|marketing|tourism|estate|hospitality|logistic/.test(n)) {
    return "management";
  }
  if (/arts|law|language|social|music|dance|drama|media|translation|islamic|buddhist/.test(n)) return "arts";
  return "science";
}

export function fmtMinutes(m?: number | null): string {
  if (m == null || Number.isNaN(m)) return "—";
  if (m < 60) return `${Math.round(m)} min`;
  return `${Math.floor(m / 60)}h ${Math.round(m % 60)}m`;
}

export function abbrevSubject(s: string): string {
  return s
    .split(/\s+/)
    .map((w) => w[0] ?? "")
    .join("")
    .slice(0, 4);
}

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/**
 * Clean up PDF-extracted Unicode artifacts, Private Use Area glyphs (e.g. Wingdings bullets),
 * replacement characters (U+FFFD), ligatures, and control chars for clean UI rendering.
 */
export function sanitizeDisplayText(text?: string | null): string {
  if (!text) return "";
  return text
    .replace(/\u00A0/g, " ")
    .replace(/[\u200B-\u200D\uFEFF]/g, "")
    .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, "")
    .replace(/ﬁ/g, "fi")
    .replace(/ﬂ/g, "fl")
    .replace(/ﬀ/g, "ff")
    .replace(/ﬃ/g, "ffi")
    .replace(/ﬄ/g, "ffl")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/?(?:sup|sub)>/gi, "")
    .replace(/^([\t ]*[-*][\t ]+)#{1,6}[\t ]+/gm, "$1")
    .replace(/[\t ]+#(?=[\t ]*$)/gm, "")
    .replace(/^[\t ]*[\uE000-\uF8FF][\t ]*/gm, "- ")
    .replace(/[\uE000-\uF8FF]/g, "•")
    .replace(/\s+—\s+/g, ", ")
    .replace(/—/g, ", ")
    .replace(/\uFFFD+/g, "")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}
