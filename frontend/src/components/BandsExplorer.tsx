import { useMemo, useState } from "react";
import { Bookmark, GitCompareArrows, Search } from "lucide-react";
import {
  BAND_ORDER,
  type BandKey,
  type CourseRow,
  type RecommendationReport,
} from "../api/types.ts";
import { useTranslation, type TranslationKey } from "../i18n/index.tsx";
import {
  BAND_DESC_KEYS,
  BAND_LABEL_KEYS,
  formatTravelSummary,
  formatZScore,
} from "../utils/format.ts";
import { BandBadge } from "./BandBadge.tsx";

type FilterChip = "all" | "can_apply" | "with_conditions" | "same_district";

interface BandsExplorerProps {
  report: RecommendationReport;
  selectedUniCode: string | null;
  shortlist: string[];
  compareList: string[];
  onSelectCourse: (uniCode: string) => void;
  onToggleShortlist: (uniCode: string) => void;
  onToggleCompare: (uniCode: string) => void;
}

const FILTER_CHIPS: Array<{ key: FilterChip; labelKey: TranslationKey }> = [
  { key: "all", labelKey: "bands.filter.all" },
  { key: "can_apply", labelKey: "bands.filter.canApply" },
  { key: "with_conditions", labelKey: "bands.filter.withConditions" },
  { key: "same_district", labelKey: "bands.filter.sameDistrict" },
];

function matchesFilters(
  row: CourseRow,
  query: string,
  chip: FilterChip,
): boolean {
  if (chip === "can_apply" && row.group !== "can_apply") {
    return false;
  }
  if (chip === "with_conditions" && row.group !== "with_conditions") {
    return false;
  }
  if (chip === "same_district" && !row.same_district) {
    return false;
  }
  if (query) {
    const q = query.toLowerCase();
    const haystack = `${row.course_name} ${row.university} ${row.uni_code}`.toLowerCase();
    if (!haystack.includes(q)) {
      return false;
    }
  }
  return true;
}

export function BandsExplorer({
  report,
  selectedUniCode,
  shortlist,
  compareList,
  onSelectCourse,
  onToggleShortlist,
  onToggleCompare,
}: BandsExplorerProps) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [chip, setChip] = useState<FilterChip>("all");

  const filteredByBand = useMemo(() => {
    const trimmed = search.trim();
    const out: Record<BandKey, CourseRow[]> = {
      strong: [],
      competitive: [],
      reach: [],
      unlikely: [],
      no_history: [],
    };
    for (const band of BAND_ORDER) {
      const rows = report.bands?.[band] ?? [];
      out[band] = rows.filter((row) => matchesFilters(row, trimmed, chip));
    }
    return out;
  }, [report.bands, search, chip]);

  const totalMatches = BAND_ORDER.reduce(
    (sum, band) => sum + filteredByBand[band].length,
    0,
  );

  return (
    <div className="space-y-5">
      {/* Search & Quick Filter Bar */}
      <div className="flex flex-col gap-3 rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1 sm:max-w-sm">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#64748B]"
            strokeWidth={1.5}
          />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("bands.searchPlaceholder")}
            aria-label={t("bands.searchAria")}
            className="w-full rounded-[6px] border border-[#E2E8F0] bg-[#F8FAFC] py-1.5 pl-9 pr-3 text-[13px] text-[#0F172A] placeholder:text-[#64748B] focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {FILTER_CHIPS.map((item) => {
            const active = chip === item.key;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => setChip(item.key)}
                className={
                  active
                    ? "rounded-full border border-[#1D4ED8] bg-[#1D4ED8] px-3 py-1 text-[12px] font-medium text-[#FFFFFF]"
                    : "rounded-full border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-1 text-[12px] font-medium text-[#475569] hover:border-[#CBD5E1] hover:bg-[#F1F5F9]"
                }
              >
                {t(item.labelKey)}
              </button>
            );
          })}
        </div>
      </div>

      {/* Band Sections in Exact Order */}
      {totalMatches === 0 ? (
        <div className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-6 text-center text-[14px] text-[#475569]">
          {t("bands.empty")}
        </div>
      ) : (
        <div className="space-y-6">
          {BAND_ORDER.map((band) => {
            const rows = filteredByBand[band];
            if (rows.length === 0) return null;

            return (
              <section key={band} className="space-y-2.5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <h2 className="text-[18px] font-semibold tracking-[-0.015em] text-[#0F172A]">
                      {t(BAND_LABEL_KEYS[band])}
                    </h2>
                    <span className="tabular-nums rounded-full border border-[#E2E8F0] bg-[#FFFFFF] px-2.5 py-0.5 text-[12px] font-medium text-[#475569]">
                      {rows.length}
                    </span>
                  </div>
                  <p className="text-[12px] text-[#64748B]">
                    {t(BAND_DESC_KEYS[band])}
                  </p>
                </div>

                <div className="divide-y divide-[#E2E8F0] overflow-hidden rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF]">
                  {rows.map((row) => {
                    const isSelected = selectedUniCode === row.uni_code;
                    const isSaved = shortlist.includes(row.uni_code);
                    const isComparing = compareList.includes(row.uni_code);

                    return (
                      <div
                        key={row.uni_code}
                        className={
                          isSelected
                            ? "flex flex-col gap-3 bg-[#EFF6FF] p-4 transition-colors sm:flex-row sm:items-center sm:justify-between"
                            : "flex flex-col gap-3 bg-[#FFFFFF] p-4 transition-colors hover:bg-[#F1F5F9] sm:flex-row sm:items-center sm:justify-between"
                        }
                      >
                        <button
                          type="button"
                          onClick={() => onSelectCourse(row.uni_code)}
                          className="min-w-0 flex-1 text-left"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-[15px] font-semibold text-[#0F172A]">
                              {row.course_name}
                            </h3>
                            <BandBadge band={row.band} />
                            {row.group === "with_conditions" ? (
                              <span className="rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-2 py-0.5 text-[11px] font-medium text-[#475569]">
                                {t("bands.badge.withConditions")}
                              </span>
                            ) : null}
                            {row.aptitude_test ? (
                              <span className="rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-2 py-0.5 text-[11px] font-medium text-[#475569]">
                                {t("bands.badge.aptitudeTest")}
                              </span>
                            ) : null}
                            {row.same_district ? (
                              <span className="rounded-full border border-[#BFDBFE] bg-[#EFF6FF] px-2 py-0.5 text-[11px] font-medium text-[#1D4ED8]">
                                {t("bands.badge.sameDistrict")}
                              </span>
                            ) : null}
                          </div>
                          <p className="mt-0.5 text-[13px] text-[#475569]">
                            {row.university}{" "}
                            <span className="text-[#64748B]">
                              · {row.uni_code}
                              {row.site_district ? ` · ${row.site_district}` : ""}
                            </span>
                          </p>
                        </button>

                        <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 text-[13px] sm:justify-end sm:text-right">
                          <div className="flex items-center gap-4">
                            <div>
                              <span className="block text-[11px] font-medium text-[#64748B]">
                                {t("rankings.latestCutoff")}
                              </span>
                              <span className="tabular-nums font-medium text-[#0F172A]">
                                {formatZScore(row.latest_cutoff)}
                              </span>
                            </div>
                            <div className="min-w-[105px]">
                              <span className="block text-[11px] font-medium text-[#64748B]">
                                {t("rankings.travel")}
                              </span>
                              <span className="tabular-nums text-[#475569]">
                                {formatTravelSummary(row.car_min, row.bus_min_est, t)}
                              </span>
                            </div>
                          </div>

                          <div className="flex items-center gap-1.5">
                            <button
                              type="button"
                              aria-pressed={isSaved}
                              onClick={() => onToggleShortlist(row.uni_code)}
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
                              onClick={() => onToggleCompare(row.uni_code)}
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
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
