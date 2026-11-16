import ReactMarkdown from "react-markdown";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  HelpCircle,
  MapPin,
  XCircle,
} from "lucide-react";
import type { CourseRow, RecommendationReport } from "../api/types.ts";
import { translateOlSubject, useTranslation } from "../i18n/index.tsx";
import { formatMinutes, formatZScore } from "../utils/format.ts";
import { BandBadge } from "./BandBadge.tsx";

interface CourseOverviewProps {
  course: CourseRow;
  report: RecommendationReport;
}

function ZScoreGauge({
  studentZ,
  predicted,
  uncertainty,
  latest,
  label,
}: {
  studentZ: number;
  predicted: number;
  uncertainty: number;
  latest?: number | null;
  label: string;
}) {
  const low = predicted - uncertainty;
  const high = predicted + uncertainty;
  const minBound = Math.min(low, studentZ, latest ?? predicted) - 0.15;
  const maxBound = Math.max(high, studentZ, latest ?? predicted) + 0.15;
  const span = Math.max(0.2, maxBound - minBound);
  const toPct = (val: number) =>
    Math.min(98, Math.max(2, ((val - minBound) / span) * 100));

  const bandLeft = toPct(low);
  const bandRight = toPct(high);
  const studentPct = toPct(studentZ);

  return (
    <div className="mt-3 rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] p-3">
      <div className="flex items-center justify-between text-[11px] font-medium text-[#64748B]">
        <span>{label}</span>
        <span className="tabular-nums font-semibold text-[#1D4ED8]">
          {studentZ.toFixed(4)}
        </span>
      </div>
      <div className="relative mt-2.5 h-2.5 w-full rounded-full bg-[#E2E8F0]">
        <div
          style={{
            left: `${bandLeft}%`,
            width: `${Math.max(4, bandRight - bandLeft)}%`,
          }}
          className="absolute top-0 h-full rounded-full bg-[#BFDBFE]"
        />
        <div
          style={{ left: `${studentPct}%` }}
          className="absolute -top-1 h-4 w-4 -translate-x-1/2 rounded-full border-2 border-[#FFFFFF] bg-[#1D4ED8]"
        />
      </div>
      <div className="tabular-nums mt-1.5 flex justify-between text-[10px] text-[#64748B]">
        <span>{low.toFixed(2)}</span>
        <span>{predicted.toFixed(2)}</span>
        <span>{high.toFixed(2)}</span>
      </div>
    </div>
  );
}

export function CourseOverview({ course, report }: CourseOverviewProps) {
  const { locale, t } = useTranslation();
  const detailsEntry = report.course_details?.[course.course_code];
  const blockIndex =
    typeof course.details_block === "number" ? course.details_block : 0;
  const block =
    detailsEntry?.blocks?.[blockIndex] ?? detailsEntry?.blocks?.[0] ?? null;

  const olMet = course.ol_met ?? [];
  const olFailed = course.ol_failed ?? [];
  const olUnknown = course.ol_unknown ?? [];

  const predictedRange =
    course.predicted_cutoff != null
      ? course.uncertainty != null
        ? `${formatZScore(course.predicted_cutoff)} ± ${course.uncertainty.toFixed(4)}`
        : formatZScore(course.predicted_cutoff)
      : "—";

  const yearsCleared =
    course.years_met != null && course.years_compared != null
      ? `${course.years_met} / ${course.years_compared}`
      : "—";

  const studentZ = report.profile.z_score;
  const busMin = course.bus_min_est;

  return (
    <div className="space-y-5">
      {/* Status Summary */}
      <div className="flex flex-wrap items-center gap-2">
        <BandBadge band={course.band} />
        <span className="rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-0.5 text-[12px] font-medium text-[#0F172A]">
          {course.group === "with_conditions"
            ? t("summary.withConditions")
            : t("summary.readyToApply")}
        </span>
        {course.aptitude_test ? (
          <span className="rounded-full border border-[#BFDBFE] bg-[#EFF6FF] px-2.5 py-0.5 text-[12px] font-medium text-[#1D4ED8]">
            {t("overview.aptitudeRequired")}
          </span>
        ) : null}
      </div>

      {/* Prominent Aptitude Test Alert */}
      {course.aptitude_test ? (
        <div className="flex items-start gap-2.5 rounded-[8px] border border-[#FDE68A] bg-[#FFFBEB] p-3.5 text-[13px] text-[#92400E]">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.5} />
          <span>{t("overview.aptitudeAlert")}</span>
        </div>
      ) : null}

      {/* Z-Score Analysis Card */}
      <section className="rounded-[8px] border border-[#E2E8F0] bg-[#F8FAFC] p-4">
        <h3 className="text-[15px] font-semibold text-[#0F172A]">
          {t("overview.zscoreTitle")}
        </h3>

        {studentZ != null && course.predicted_cutoff != null ? (
          <ZScoreGauge
            studentZ={studentZ}
            predicted={course.predicted_cutoff}
            uncertainty={course.uncertainty ?? 0.08}
            latest={course.latest_cutoff}
            label={t("overview.zscoreGaugeTitle")}
          />
        ) : null}

        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div>
            <span className="block text-[11px] font-medium text-[#64748B]">
              {t("overview.latestCutoff")}
              {course.latest_year ? ` (${course.latest_year})` : ""}
            </span>
            <span className="tabular-nums mt-0.5 block text-[15px] font-semibold text-[#0F172A]">
              {formatZScore(course.latest_cutoff)}
            </span>
          </div>
          <div>
            <span className="block text-[11px] font-medium text-[#64748B]">
              {t("overview.predictedCutoff")}
            </span>
            <span className="tabular-nums mt-0.5 block text-[15px] font-semibold text-[#0F172A]">
              {predictedRange}
            </span>
          </div>
          <div>
            <span className="block text-[11px] font-medium text-[#64748B]">
              {t("overview.expectedMargin")}
            </span>
            <span className="tabular-nums mt-0.5 block text-[15px] font-semibold text-[#0F172A]">
              {course.expected_margin != null
                ? `${course.expected_margin >= 0 ? "+" : ""}${course.expected_margin.toFixed(4)}`
                : "—"}
            </span>
          </div>
          <div>
            <span className="block text-[11px] font-medium text-[#64748B]">
              {t("overview.yearsCleared")}
            </span>
            <span className="tabular-nums mt-0.5 block text-[14px] font-medium text-[#0F172A]">
              {yearsCleared}
            </span>
          </div>
          <div>
            <span className="block text-[11px] font-medium text-[#64748B]">
              {t("overview.proposedIntake")}
            </span>
            <span className="tabular-nums mt-0.5 block text-[14px] font-medium text-[#0F172A]">
              {course.proposed_intake ?? "—"}
            </span>
          </div>
        </div>

        {course.reason || course.zscore_note ? (
          <p className="mt-3 border-t border-[#E2E8F0] pt-3 text-[13px] leading-relaxed text-[#475569]">
            {course.reason || course.zscore_note}
          </p>
        ) : null}
      </section>

      {/* Travel & O/L Requirements Card */}
      <section className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-4">
        <h3 className="text-[15px] font-semibold text-[#0F172A]">
          {t("overview.locationTitle")}
        </h3>

        <div className="mt-3 flex flex-wrap items-start gap-2 text-[13px] text-[#475569]">
          <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-[#64748B]" strokeWidth={1.5} />
          <span>
            {course.site || course.university}
            {course.site_district ? ` (${course.site_district})` : ""}
          </span>
        </div>

        {busMin != null ? (
          <div className="mt-2.5 inline-flex items-center rounded-full border border-[#BFDBFE] bg-[#EFF6FF] px-3 py-1 text-[12px] font-medium text-[#1D4ED8]">
            {busMin >= 90
              ? t("overview.boardingLikely", { time: formatMinutes(busMin, t) })
              : t("overview.commuteFeasible", { time: formatMinutes(busMin, t) })}
          </div>
        ) : null}

        <div className="mt-3 grid grid-cols-3 gap-3 rounded-[6px] border border-[#E2E8F0] bg-[#F8FAFC] p-3">
          <div>
            <span className="block text-[11px] font-medium text-[#64748B]">
              {t("overview.byCar")}
            </span>
            <span className="tabular-nums mt-0.5 block text-[14px] font-medium text-[#0F172A]">
              {formatMinutes(course.car_min, t)}
            </span>
          </div>
          <div>
            <span className="block text-[11px] font-medium text-[#64748B]">
              {t("overview.estBus")}
            </span>
            <span className="tabular-nums mt-0.5 block text-[14px] font-medium text-[#0F172A]">
              {formatMinutes(course.bus_min_est, t)}
            </span>
          </div>
          <div>
            <span className="block text-[11px] font-medium text-[#64748B]">
              {t("overview.roadDistance")}
            </span>
            <span className="tabular-nums mt-0.5 block text-[14px] font-medium text-[#0F172A]">
              {course.road_km != null ? `${course.road_km.toFixed(1)} km` : "—"}
            </span>
          </div>
        </div>

        {olMet.length > 0 || olFailed.length > 0 || olUnknown.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {olMet.map((sub) => (
              <span
                key={`met-${sub}`}
                className="inline-flex items-center gap-1 rounded-full border border-[#BFDBFE] bg-[#EFF6FF] px-2.5 py-0.5 text-[12px] font-medium text-[#0F172A]"
              >
                <CheckCircle2 className="h-3.5 w-3.5 text-[#1D4ED8]" strokeWidth={1.5} />
                {t("overview.olMet", { subject: translateOlSubject(locale, sub) })}
              </span>
            ))}
            {olFailed.map((sub) => (
              <span
                key={`fail-${sub}`}
                className="inline-flex items-center gap-1 rounded-full border border-[#FECACA] bg-[#FEF2F2] px-2.5 py-0.5 text-[12px] font-medium text-[#B91C1C]"
              >
                <XCircle className="h-3.5 w-3.5" strokeWidth={1.5} />
                {t("overview.olFailed", { subject: translateOlSubject(locale, sub) })}
              </span>
            ))}
            {olUnknown.map((sub) => (
              <span
                key={`unk-${sub}`}
                className="inline-flex items-center gap-1 rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-0.5 text-[12px] font-medium text-[#64748B]"
              >
                <HelpCircle className="h-3.5 w-3.5" strokeWidth={1.5} />
                {t("overview.olUnknown", { subject: translateOlSubject(locale, sub) })}
              </span>
            ))}
          </div>
        ) : null}
      </section>

      {/* Handbook Section */}
      {block ? (
        <section className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-3">
            <div className="flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-[#1D4ED8]" strokeWidth={1.5} />
              <h3 className="text-[15px] font-semibold text-[#0F172A]">
                {t("overview.handbookTitle")}
              </h3>
            </div>
            {block.citation ? (
              <span className="rounded-full border border-[#BFDBFE] bg-[#EFF6FF] px-2.5 py-0.5 text-[12px] font-medium text-[#1D4ED8]">
                {block.citation}
              </span>
            ) : null}
          </div>

          {block.degree_programmes && block.degree_programmes.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {block.degree_programmes.map((deg) => (
                <span
                  key={deg}
                  className="rounded-[6px] border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-1 text-[12px] font-medium text-[#0F172A]"
                >
                  {deg}
                </span>
              ))}
            </div>
          ) : null}

          {block.text ? (
            <div className="mt-3 space-y-2 text-[14px] leading-relaxed text-[#475569] [&_h1]:text-[16px] [&_h1]:font-semibold [&_h1]:text-[#0F172A] [&_h2]:text-[15px] [&_h2]:font-semibold [&_h2]:text-[#0F172A] [&_h3]:text-[14px] [&_h3]:font-semibold [&_h3]:text-[#0F172A] [&_h5]:text-[14px] [&_h5]:font-semibold [&_h5]:text-[#0F172A] [&_li]:ml-4 [&_li]:list-disc [&_strong]:font-semibold [&_strong]:text-[#0F172A]">
              <ReactMarkdown>{block.text}</ReactMarkdown>
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
