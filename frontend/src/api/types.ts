import type { components } from "./schema.d.ts";

export type SubjectGrade = components["schemas"]["SubjectGrade"];
export type RecommendationRequest = components["schemas"]["RecommendationRequest"];
export type ChatTurn = components["schemas"]["ChatTurn"];
export type ChatCourse = components["schemas"]["ChatCourse"];
export type ChatRequest = components["schemas"]["ChatRequest"];
export type CareerOutlookSummary = components["schemas"]["CareerOutlookSummary"];
export type CareerJob = components["schemas"]["CareerJob"];
export type CareerStatus = components["schemas"]["CareerStatus"];
export type CareerResearchRequest = components["schemas"]["CareerResearchRequest"];
export type CareerResearchResponse = components["schemas"]["CareerResearchResponse"];
export type ChatSource = components["schemas"]["ChatSource"];
export type ChatResponse = components["schemas"]["ChatResponse"];
export type StreamHint = components["schemas"]["StreamHint"];
export type Options = components["schemas"]["Options"];
export type Health = components["schemas"]["Health"];
export type ErrorResponse = components["schemas"]["ErrorResponse"];

export type BandKey = "strong" | "competitive" | "reach" | "unlikely" | "no_history";

export const BAND_ORDER: readonly BandKey[] = [
  "strong",
  "competitive",
  "reach",
  "unlikely",
  "no_history",
] as const;

export interface CourseRow {
  uni_code: string;
  course_code: string;
  course_name: string;
  university: string;
  band: BandKey;
  site?: string | null;
  site_district?: string | null;
  group?: "can_apply" | "with_conditions" | string;
  aptitude_test?: boolean;
  ol_met?: string[];
  ol_failed?: string[];
  ol_unknown?: string[];
  proposed_intake?: number | null;
  latest_cutoff?: number | null;
  latest_year?: string | null;
  predicted_cutoff?: number | null;
  uncertainty?: number | null;
  expected_margin?: number | null;
  years_met?: number | null;
  years_compared?: number | null;
  reason?: string | null;
  zscore_note?: string | null;
  car_min?: number | null;
  bus_min_est?: number | null;
  road_km?: number | null;
  same_district?: boolean;
  preference_score?: number | null;
  details_block?: number | null;
  [key: string]: unknown;
}

export interface RankingParts {
  interest: number;
  cutoff: number;
  distance: number;
}

export interface RankingSuggestion {
  position: number;
  uni_code: string;
  course_code: string;
  course_name: string;
  university: string;
  band: BandKey;
  latest_cutoff?: number | null;
  car_min?: number | null;
  bus_min_est?: number | null;
  preference_score?: number | null;
  flags?: string[];
  combined_score?: number | null;
  parts?: RankingParts | null;
  [key: string]: unknown;
}

export interface RankingCloseCall {
  ranks: string | number[];
  note: string;
}

export interface RankingPriority {
  label: string;
  advice: string;
}

export interface DistanceFeedback {
  summary?: string;
  course_notes?: Record<string, { note?: string }>;
  close_calls?: RankingCloseCall[];
  priorities?: RankingPriority[];
}

export interface RankingList {
  title: string;
  total: number;
  suggestions: RankingSuggestion[];
  notes?: string[];
  feedback?: DistanceFeedback;
  analysis?: unknown;
}

export interface CourseDetailsBlock {
  title?: string;
  section?: string;
  pages?: number[];
  citation?: string;
  degree_programmes?: string[];
  duration?: string[];
  medium?: string[];
  notes?: string[];
  specializations?: Record<string, unknown>;
  text?: string;
}

export interface CourseDetailsEntry {
  course_name?: string;
  blocks?: CourseDetailsBlock[];
}

export interface ReportProfile {
  stream: string;
  al_results: [string, string][];
  common_general_test?: number;
  admission_district: string;
  home?: string;
  ol_results?: [string, string][];
  z_score?: number | null;
}

export interface ReportOrigin {
  ds_division: string;
  district: string;
  province?: string;
  origin_id?: string;
}

export interface ReportCounts {
  can_apply?: number;
  with_conditions?: number;
  not_eligible?: number;
  band_strong?: number;
  band_competitive?: number;
  band_reach?: number;
  band_unlikely?: number;
  band_no_history?: number;
  [key: string]: number | undefined;
}

export interface ReportPreferences {
  text?: string;
  best_overall?: unknown[];
  [key: string]: unknown;
}

export interface RecommendationReport {
  profile: ReportProfile;
  origin: ReportOrigin;
  counts: ReportCounts;
  bands: Record<BandKey, CourseRow[]>;
  rankings: {
    zscore?: RankingList;
    preference?: RankingList;
    distance?: RankingList;
  };
  preferences?: ReportPreferences;
  course_details?: Record<string, CourseDetailsEntry>;
  notes?: string[];
}

export interface RecommendationResponse {
  report: RecommendationReport;
  used_llm: boolean;
}

export interface ChatSourceLink {
  id?: string;
  title?: string;
  url: string;
}

export interface CareerOverall {
  label?: string;
  summary?: string;
  confidence?: string;
  evidence_refs?: string[];
}
