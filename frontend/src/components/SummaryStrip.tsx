import type { RecommendationReport } from "../api/types.ts";
import { translateStream, useTranslation } from "../i18n/index.tsx";

interface SummaryStripProps {
  report: RecommendationReport;
  usedLlm: boolean;
}

export function SummaryStrip({ report, usedLlm }: SummaryStripProps) {
  const { locale, t } = useTranslation();
  const { profile, origin, counts } = report;

  const statItems: Array<{ label: string; value: number; highlight?: boolean }> = [
    { label: t("summary.readyToApply"), value: counts.can_apply ?? 0 },
    { label: t("summary.withConditions"), value: counts.with_conditions ?? 0 },
    { label: t("band.strong"), value: counts.band_strong ?? 0, highlight: true },
    { label: t("band.competitive"), value: counts.band_competitive ?? 0 },
    { label: t("band.reach"), value: counts.band_reach ?? 0 },
    { label: t("band.unlikely"), value: counts.band_unlikely ?? 0 },
    { label: t("band.no_history"), value: counts.band_no_history ?? 0 },
  ];

  return (
    <section
      aria-label="Student profile and eligibility summary"
      className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-4 sm:p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E2E8F0] pb-3.5">
        <div className="flex flex-wrap items-center gap-2 text-[13px]">
          <span className="rounded-full border border-[#BFDBFE] bg-[#EFF6FF] px-3 py-0.5 font-medium text-[#0F172A]">
            {translateStream(locale, profile.stream)}
          </span>
          <span className="tabular-nums rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-0.5 font-medium text-[#0F172A]">
            {profile.z_score != null
              ? t("summary.zscorePrefix", { value: profile.z_score })
              : t("summary.noZscore")}
          </span>
          <span className="rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-0.5 text-[#475569]">
            {t("summary.admissionPrefix")}{" "}
            <strong className="font-medium text-[#0F172A]">
              {profile.admission_district}
            </strong>
          </span>
          {origin?.ds_division ? (
            <span className="rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-0.5 text-[#475569]">
              {t("summary.homePrefix")}{" "}
              <strong className="font-medium text-[#0F172A]">
                {origin.ds_division}
              </strong>
            </span>
          ) : null}
          {usedLlm ? (
            <span className="rounded-full border border-[#BFDBFE] bg-[#EFF6FF] px-2.5 py-0.5 text-[12px] font-medium text-[#1D4ED8]">
              {t("summary.aiInterests")}
            </span>
          ) : null}
        </div>
      </div>

      <div className="mt-3.5 grid grid-cols-2 gap-2.5 sm:grid-cols-4 lg:grid-cols-7">
        {statItems.map((item) => (
          <div
            key={item.label}
            className={
              item.highlight
                ? "rounded-[6px] border border-[#BFDBFE] bg-[#EFF6FF] px-3 py-2"
                : "rounded-[6px] border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-2"
            }
          >
            <span className="block text-[11px] font-medium text-[#64748B]">
              {item.label}
            </span>
            <span
              className={
                item.highlight
                  ? "tabular-nums mt-0.5 block text-[17px] font-semibold text-[#1D4ED8]"
                  : "tabular-nums mt-0.5 block text-[17px] font-semibold text-[#0F172A]"
              }
            >
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
