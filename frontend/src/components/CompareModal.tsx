import { X } from "lucide-react";
import type { CourseRow } from "../api/types.ts";
import { useTranslation } from "../i18n/index.tsx";
import { formatMinutes, formatZScore } from "../utils/format.ts";
import { BandBadge } from "./BandBadge.tsx";

interface CompareModalProps {
  open: boolean;
  courses: CourseRow[];
  onRemove: (uniCode: string) => void;
  onClose: () => void;
}

export function CompareModal({
  open,
  courses,
  onRemove,
  onClose,
}: CompareModalProps) {
  const { t } = useTranslation();

  if (!open || courses.length === 0) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label={t("compare.title")}
    >
      <div
        aria-hidden="true"
        onClick={onClose}
        className="fixed inset-0 bg-[#0F172A]/30"
      />
      <div className="relative z-10 max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-5">
        <div className="flex items-center justify-between gap-3 border-b border-[#E2E8F0] pb-3">
          <h2 className="text-[18px] font-semibold text-[#0F172A]">
            {t("compare.title")}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("drawer.closeAria")}
            className="rounded-[6px] border border-[#E2E8F0] p-1.5 text-[#475569] hover:bg-[#F1F5F9]"
          >
            <X className="h-4 w-4" strokeWidth={1.5} />
          </button>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          {courses.map((course) => (
            <div
              key={course.uni_code}
              className="flex flex-col justify-between rounded-[8px] border border-[#E2E8F0] bg-[#F8FAFC] p-4"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-[15px] font-semibold text-[#0F172A]">
                      {course.course_name}
                    </h3>
                    <p className="text-[12px] text-[#475569]">
                      {course.university} · {course.uni_code}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onRemove(course.uni_code)}
                    aria-label={t("shortlist.remove")}
                    className="rounded p-1 text-[#64748B] hover:bg-[#E2E8F0] hover:text-[#0F172A]"
                  >
                    <X className="h-3.5 w-3.5" strokeWidth={1.5} />
                  </button>
                </div>

                <div className="mt-3">
                  <BandBadge band={course.band} />
                </div>

                <dl className="mt-4 space-y-2.5 text-[13px]">
                  <div className="flex justify-between gap-2 border-b border-[#E2E8F0] pb-1.5">
                    <dt className="text-[#64748B]">{t("overview.latestCutoff")}</dt>
                    <dd className="tabular-nums font-semibold text-[#0F172A]">
                      {formatZScore(course.latest_cutoff)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2 border-b border-[#E2E8F0] pb-1.5">
                    <dt className="text-[#64748B]">{t("overview.predictedCutoff")}</dt>
                    <dd className="tabular-nums font-medium text-[#0F172A]">
                      {formatZScore(course.predicted_cutoff)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2 border-b border-[#E2E8F0] pb-1.5">
                    <dt className="text-[#64748B]">{t("overview.proposedIntake")}</dt>
                    <dd className="tabular-nums font-medium text-[#0F172A]">
                      {course.proposed_intake ?? "—"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2 border-b border-[#E2E8F0] pb-1.5">
                    <dt className="text-[#64748B]">{t("overview.byCar")}</dt>
                    <dd className="tabular-nums text-[#0F172A]">
                      {formatMinutes(course.car_min, t)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2 border-b border-[#E2E8F0] pb-1.5">
                    <dt className="text-[#64748B]">{t("overview.estBus")}</dt>
                    <dd className="tabular-nums text-[#0F172A]">
                      {formatMinutes(course.bus_min_est, t)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt className="text-[#64748B]">{t("bands.badge.aptitudeTest")}</dt>
                    <dd className="font-medium text-[#0F172A]">
                      {course.aptitude_test ? "Yes" : "No"}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
