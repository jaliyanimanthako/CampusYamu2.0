import { useState } from "react";
import { Bookmark, ChevronDown, ChevronUp, GitCompareArrows } from "lucide-react";
import type {
  RankingParts,
  RecommendationReport,
} from "../api/types.ts";
import { useTranslation, type TranslationKey } from "../i18n/index.tsx";
import { formatTravelSummary, formatZScore } from "../utils/format.ts";
import { BandBadge } from "./BandBadge.tsx";

type RankingKey = "distance" | "preference" | "zscore";

interface RankingsViewProps {
  report: RecommendationReport;
  selectedUniCode: string | null;
  shortlist: string[];
  compareList: string[];
  onSelectCourse: (uniCode: string) => void;
  onToggleShortlist: (uniCode: string) => void;
  onToggleCompare: (uniCode: string) => void;
}

const RANKING_TABS: Array<{ key: RankingKey; labelKey: TranslationKey }> = [
  { key: "distance", labelKey: "rankings.tab.distance" },
  { key: "preference", labelKey: "rankings.tab.preference" },
  { key: "zscore", labelKey: "rankings.tab.zscore" },
];

function PartsBar({ parts }: { parts: RankingParts }) {
  const { t } = useTranslation();
  const interest = Math.max(0, parts.interest || 0);
  const cutoff = Math.max(0, parts.cutoff || 0);
  const distance = Math.max(0, parts.distance || 0);
  const total = interest + cutoff + distance;
  if (total <= 0) return null;

  const pctInterest = Math.round((interest / total) * 100);
  const pctCutoff = Math.round((cutoff / total) * 100);
  const pctDistance = Math.max(0, 100 - pctInterest - pctCutoff);

  return (
    <div className="mt-2">
      <div className="flex h-1.5 w-40 overflow-hidden rounded-full bg-[#E2E8F0]">
        <div
          style={{ width: `${pctInterest}%` }}
          className="h-full bg-[#1D4ED8]"
        />
        <div
          style={{ width: `${pctCutoff}%` }}
          className="h-full bg-[#60A5FA]"
        />
        <div
          style={{ width: `${pctDistance}%` }}
          className="h-full bg-[#94A3B8]"
        />
      </div>
      <div className="tabular-nums mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-[#64748B]">
        <span className="inline-flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-[#1D4ED8]" />
          {pctInterest}% {t("rankings.part.interest")}
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-[#60A5FA]" />
          {pctCutoff}% {t("rankings.part.cutoff")}
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-[#94A3B8]" />
          {pctDistance}% {t("rankings.part.distance")}
        </span>
      </div>
    </div>
  );
}

export function RankingsView({
  report,
  selectedUniCode,
  shortlist,
  compareList,
  onSelectCourse,
  onToggleShortlist,
  onToggleCompare,
}: RankingsViewProps) {
  const { t } = useTranslation();
  const [activeRanking, setActiveRanking] = useState<RankingKey>("distance");
  const [adviceOpen, setAdviceOpen] = useState(false);

  const current = report.rankings?.[activeRanking];
  const suggestions = current?.suggestions ?? [];
  const feedback = current?.feedback;
  const hasCloseCalls = Boolean(feedback?.close_calls && feedback.close_calls.length > 0);
  const hasPriorities = Boolean(feedback?.priorities && feedback.priorities.length > 0);

  return (
    <div className="space-y-4">
      {/* Sub-pills for ranking mode */}
      <div
        role="tablist"
        aria-label="Ranking order mode"
        className="flex flex-wrap items-center gap-2"
      >
        {RANKING_TABS.map((tab) => {
          const available = Boolean(report.rankings?.[tab.key]);
          if (!available) return null;
          const isSelected = activeRanking === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={isSelected}
              onClick={() => setActiveRanking(tab.key)}
              className={
                isSelected
                  ? "rounded-full border border-[#1D4ED8] bg-[#1D4ED8] px-3.5 py-1.5 text-[13px] font-medium text-[#FFFFFF]"
                  : "rounded-full border border-[#E2E8F0] bg-[#FFFFFF] px-3.5 py-1.5 text-[13px] font-medium text-[#475569] hover:border-[#CBD5E1] hover:bg-[#F8FAFC]"
              }
            >
              {t(tab.labelKey)}
            </button>
          );
        })}
      </div>

      {/* Title & Feedback Callout */}
      {current ? (
        <div className="rounded-[8px] border border-[#BFDBFE] bg-[#EFF6FF] p-4 sm:p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-[18px] font-semibold tracking-[-0.015em] text-[#0F172A]">
              {current.title}
            </h2>
            <span className="tabular-nums text-[12px] font-medium text-[#475569]">
              {t("rankings.showing", {
                shown: suggestions.length,
                total: current.total,
              })}
            </span>
          </div>
          {feedback?.summary ? (
            <p className="mt-2 text-[14px] leading-relaxed text-[#0F172A]">
              {feedback.summary}
            </p>
          ) : null}

          {hasCloseCalls || hasPriorities ? (
            <div className="mt-3 border-t border-[#BFDBFE] pt-3">
              <button
                type="button"
                aria-expanded={adviceOpen}
                onClick={() => setAdviceOpen((prev) => !prev)}
                className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#1D4ED8] hover:text-[#1E40AF]"
              >
                <span>{t("rankings.closeCallsToggle")}</span>
                {adviceOpen ? (
                  <ChevronUp className="h-4 w-4" strokeWidth={1.5} />
                ) : (
                  <ChevronDown className="h-4 w-4" strokeWidth={1.5} />
                )}
              </button>

              {adviceOpen ? (
                <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {hasCloseCalls ? (
                    <div className="rounded-[6px] border border-[#BFDBFE] bg-[#FFFFFF] p-3">
                      <h3 className="text-[13px] font-semibold text-[#0F172A]">
                        {t("rankings.closeCallsTitle")}
                      </h3>
                      <ul className="mt-2 space-y-2 text-[13px] text-[#475569]">
                        {feedback!.close_calls!.map((cc, idx) => (
                          <li key={idx}>
                            <strong className="font-medium text-[#0F172A]">
                              {Array.isArray(cc.ranks) ? cc.ranks.join(", ") : cc.ranks}:
                            </strong>{" "}
                            {cc.note}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {hasPriorities ? (
                    <div className="rounded-[6px] border border-[#BFDBFE] bg-[#FFFFFF] p-3">
                      <h3 className="text-[13px] font-semibold text-[#0F172A]">
                        {t("rankings.prioritiesTitle")}
                      </h3>
                      <ul className="mt-2 space-y-2 text-[13px] text-[#475569]">
                        {feedback!.priorities!.map((p, idx) => (
                          <li key={idx}>
                            <strong className="font-medium text-[#0F172A]">
                              {p.label}:
                            </strong>{" "}
                            {p.advice}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {/* Ranked Course Rows */}
      {suggestions.length === 0 ? (
        <div className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-6 text-center text-[14px] text-[#475569]">
          {t("rankings.empty")}
        </div>
      ) : (
        <div className="divide-y divide-[#E2E8F0] overflow-hidden rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF]">
          {suggestions.map((item) => {
            const isSelected = selectedUniCode === item.uni_code;
            const isSaved = shortlist.includes(item.uni_code);
            const isComparing = compareList.includes(item.uni_code);
            const courseNote = feedback?.course_notes?.[item.uni_code]?.note;

            return (
              <div
                key={item.uni_code}
                className={
                  isSelected
                    ? "flex flex-col gap-3 bg-[#EFF6FF] p-4 transition-colors sm:flex-row sm:items-center sm:justify-between"
                    : "flex flex-col gap-3 bg-[#FFFFFF] p-4 transition-colors hover:bg-[#F1F5F9] sm:flex-row sm:items-center sm:justify-between"
                }
              >
                <button
                  type="button"
                  onClick={() => onSelectCourse(item.uni_code)}
                  className="flex min-w-0 flex-1 items-start gap-3.5 text-left"
                >
                  <span className="tabular-nums flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px] border border-[#E2E8F0] bg-[#F8FAFC] text-[13px] font-semibold text-[#0F172A]">
                    {item.position}
                  </span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-[15px] font-semibold text-[#0F172A]">
                        {item.course_name}
                      </h3>
                      <BandBadge band={item.band} />
                      {item.flags?.map((flag) => (
                        <span
                          key={flag}
                          className="rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-2 py-0.5 text-[11px] font-medium text-[#475569]"
                        >
                          {flag}
                        </span>
                      ))}
                    </div>
                    <p className="mt-0.5 text-[13px] text-[#475569]">
                      {item.university}{" "}
                      <span className="text-[#64748B]">· {item.uni_code}</span>
                    </p>
                    {courseNote ? (
                      <p className="mt-1 text-[12px] text-[#64748B]">
                        {courseNote}
                      </p>
                    ) : null}
                    {item.parts ? <PartsBar parts={item.parts} /> : null}
                  </div>
                </button>

                <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 pl-10 text-[13px] sm:justify-end sm:pl-0 sm:text-right">
                  <div className="flex items-center gap-4">
                    <div>
                      <span className="block text-[11px] font-medium text-[#64748B]">
                        {t("rankings.latestCutoff")}
                      </span>
                      <span className="tabular-nums font-medium text-[#0F172A]">
                        {formatZScore(item.latest_cutoff)}
                      </span>
                    </div>
                    <div className="min-w-[105px]">
                      <span className="block text-[11px] font-medium text-[#64748B]">
                        {t("rankings.travel")}
                      </span>
                      <span className="tabular-nums text-[#475569]">
                        {formatTravelSummary(item.car_min, item.bus_min_est, t)}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      aria-pressed={isSaved}
                      onClick={() => onToggleShortlist(item.uni_code)}
                      className={
                        isSaved
                          ? "inline-flex items-center gap-1 rounded-[6px] border border-[#BFDBFE] bg-[#EFF6FF] px-2.5 py-1 text-[12px] font-semibold text-[#1D4ED8]"
                          : "inline-flex items-center gap-1 rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-2.5 py-1 text-[12px] font-medium text-[#475569] hover:bg-[#F1F5F9]"
                      }
                    >
                      <Bookmark className="h-3 w-3" strokeWidth={1.5} />
                      <span>{isSaved ? t("shortlist.saved") : t("shortlist.save")}</span>
                    </button>
                    <button
                      type="button"
                      aria-pressed={isComparing}
                      onClick={() => onToggleCompare(item.uni_code)}
                      className={
                        isComparing
                          ? "inline-flex items-center gap-1 rounded-[6px] border border-[#1D4ED8] bg-[#1D4ED8] px-2.5 py-1 text-[12px] font-medium text-[#FFFFFF]"
                          : "inline-flex items-center gap-1 rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-2.5 py-1 text-[12px] font-medium text-[#475569] hover:bg-[#F1F5F9]"
                      }
                    >
                      <GitCompareArrows className="h-3 w-3" strokeWidth={1.5} />
                      <span>{isComparing ? t("compare.added") : t("compare.add")}</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
