import { useState } from "react";
import { ArrowDown, ArrowUp, Check, Copy, Printer, Trash2, X } from "lucide-react";
import type { CourseRow, RecommendationReport } from "../api/types.ts";
import { useTranslation } from "../i18n/index.tsx";
import { formatTravelSummary, formatZScore } from "../utils/format.ts";
import { BandBadge } from "./BandBadge.tsx";

interface ShortlistDrawerProps {
  open: boolean;
  shortlist: string[];
  courseByCode: Map<string, CourseRow>;
  report: RecommendationReport;
  onMove: (index: number, direction: -1 | 1) => void;
  onRemove: (uniCode: string) => void;
  onSelectCourse: (uniCode: string) => void;
  onClose: () => void;
}

export function ShortlistDrawer({
  open,
  shortlist,
  courseByCode,
  report,
  onMove,
  onRemove,
  onSelectCourse,
  onClose,
}: ShortlistDrawerProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  if (!open) return null;

  const items = shortlist
    .map((code) => courseByCode.get(code))
    .filter((row): row is CourseRow => Boolean(row));

  const handleCopyWhatsapp = async () => {
    const lines = [
      `*My Draft UGC Order — ${report.profile.stream} (${report.profile.admission_district})*`,
      ...items.map(
        (c, i) =>
          `${i + 1}. ${c.course_name} — ${c.university} (${c.uni_code})`,
      ),
      "",
      "Created with CampusYamu",
    ];
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Ignore clipboard failure
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-label={t("shortlist.title")}
    >
      <div
        aria-hidden="true"
        onClick={onClose}
        className="fixed inset-0 bg-[#0F172A]/25"
      />
      <aside
        style={{ boxShadow: "var(--shadow-drawer)" }}
        className="relative z-10 flex h-full w-full flex-col border-l border-[#E2E8F0] bg-[#FFFFFF] md:max-w-[540px]"
      >
        <div className="flex items-start justify-between gap-4 border-b border-[#E2E8F0] px-5 py-4">
          <div>
            <h2 className="text-[18px] font-semibold text-[#0F172A]">
              {t("shortlist.title")}
            </h2>
            <p className="mt-0.5 text-[12px] text-[#64748B]">
              {t("shortlist.subtitle")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("drawer.closeAria")}
            className="rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] p-1.5 text-[#475569] hover:bg-[#F1F5F9]"
          >
            <X className="h-4 w-4" strokeWidth={1.5} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {items.length === 0 ? (
            <div className="rounded-[8px] border border-[#E2E8F0] bg-[#F8FAFC] p-6 text-center text-[13px] text-[#475569]">
              {t("shortlist.empty")}
            </div>
          ) : (
            <div className="divide-y divide-[#E2E8F0] overflow-hidden rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF]">
              {items.map((row, idx) => (
                <div
                  key={row.uni_code}
                  className="flex items-center justify-between gap-3 p-3.5"
                >
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="tabular-nums flex h-6 w-6 shrink-0 items-center justify-center rounded bg-[#EFF6FF] text-[12px] font-bold text-[#1D4ED8]">
                      {idx + 1}
                    </span>
                    <div className="min-w-0">
                      <button
                        type="button"
                        onClick={() => {
                          onClose();
                          onSelectCourse(row.uni_code);
                        }}
                        className="text-left text-[14px] font-semibold text-[#0F172A] hover:text-[#1D4ED8]"
                      >
                        {row.course_name}
                      </button>
                      <p className="text-[12px] text-[#475569]">
                        {row.university} · {row.uni_code}
                      </p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-2">
                        <BandBadge band={row.band} />
                        <span className="tabular-nums text-[11px] text-[#64748B]">
                          {formatZScore(row.latest_cutoff)} ·{" "}
                          {formatTravelSummary(row.car_min, row.bus_min_est, t)}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-1">
                    <button
                      type="button"
                      disabled={idx === 0}
                      onClick={() => onMove(idx, -1)}
                      aria-label={t("shortlist.moveUp")}
                      className="rounded border border-[#E2E8F0] p-1 text-[#475569] hover:bg-[#F1F5F9] disabled:opacity-40"
                    >
                      <ArrowUp className="h-3.5 w-3.5" strokeWidth={1.5} />
                    </button>
                    <button
                      type="button"
                      disabled={idx === items.length - 1}
                      onClick={() => onMove(idx, 1)}
                      aria-label={t("shortlist.moveDown")}
                      className="rounded border border-[#E2E8F0] p-1 text-[#475569] hover:bg-[#F1F5F9] disabled:opacity-40"
                    >
                      <ArrowDown className="h-3.5 w-3.5" strokeWidth={1.5} />
                    </button>
                    <button
                      type="button"
                      onClick={() => onRemove(row.uni_code)}
                      aria-label={t("shortlist.remove")}
                      className="rounded border border-[#E2E8F0] p-1 text-[#B91C1C] hover:bg-[#FEF2F2]"
                    >
                      <Trash2 className="h-3.5 w-3.5" strokeWidth={1.5} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {items.length > 0 ? (
          <div className="flex flex-wrap items-center justify-end gap-2.5 border-t border-[#E2E8F0] px-5 py-4">
            <button
              type="button"
              onClick={() => window.print()}
              className="inline-flex items-center gap-1.5 rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-3.5 py-2 text-[13px] font-medium text-[#0F172A] hover:bg-[#F1F5F9]"
            >
              <Printer className="h-3.5 w-3.5" strokeWidth={1.5} />
              <span>{t("shortlist.printPdf")}</span>
            </button>
            <button
              type="button"
              onClick={() => void handleCopyWhatsapp()}
              className="inline-flex items-center gap-1.5 rounded-[6px] bg-[#1D4ED8] px-4 py-2 text-[13px] font-medium text-[#FFFFFF] hover:bg-[#1E40AF]"
            >
              {copied ? (
                <Check className="h-3.5 w-3.5" strokeWidth={2} />
              ) : (
                <Copy className="h-3.5 w-3.5" strokeWidth={1.5} />
              )}
              <span>{copied ? t("shortlist.copied") : t("shortlist.copyWhatsapp")}</span>
            </button>
          </div>
        ) : null}
      </aside>
    </div>
  );
}
