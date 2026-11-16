import { useState } from "react";
import { Check, Copy, Share2, X } from "lucide-react";
import type { RecommendationReport } from "../api/types.ts";
import { translateStream, useTranslation } from "../i18n/index.tsx";
import { BandBadge } from "./BandBadge.tsx";

interface ShareMatchModalProps {
  open: boolean;
  report: RecommendationReport;
  onClose: () => void;
}

export function ShareMatchModal({
  open,
  report,
  onClose,
}: ShareMatchModalProps) {
  const { locale, t } = useTranslation();
  const [includeZ, setIncludeZ] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!open) return null;

  const top3 = (report.rankings?.distance?.suggestions ?? []).slice(0, 3);
  const streamLabel = translateStream(locale, report.profile.stream);

  const shareTextLines = [
    `My Top State University Matches (${streamLabel} · ${report.profile.admission_district})`,
    ...(includeZ && report.profile.z_score != null
      ? [`Z-Score: ${report.profile.z_score}`]
      : []),
    "",
    ...top3.map(
      (item, idx) => `${idx + 1}. ${item.course_name} — ${item.university}`,
    ),
    "",
    "Found on CampusYamu",
  ];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareTextLines.join("\n"));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Ignore clipboard failure
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label={t("share.title")}
    >
      <div
        aria-hidden="true"
        onClick={onClose}
        className="fixed inset-0 bg-[#0F172A]/30"
      />
      <div className="relative z-10 w-full max-w-md rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <Share2 className="h-4 w-4 text-[#1D4ED8]" strokeWidth={1.5} />
            <h2 className="text-[17px] font-semibold text-[#0F172A]">
              {t("share.title")}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("drawer.closeAria")}
            className="rounded-[6px] border border-[#E2E8F0] p-1 text-[#475569] hover:bg-[#F1F5F9]"
          >
            <X className="h-4 w-4" strokeWidth={1.5} />
          </button>
        </div>

        {/* Shareable Visual Card */}
        <div className="mt-4 rounded-[8px] border border-[#BFDBFE] bg-[#EFF6FF] p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[13px] font-bold text-[#1D4ED8]">
              CampusYamu
            </span>
            <span className="text-[12px] font-medium text-[#475569]">
              {streamLabel} · {report.profile.admission_district}
            </span>
          </div>
          {includeZ && report.profile.z_score != null ? (
            <p className="tabular-nums mt-1 text-[12px] font-semibold text-[#0F172A]">
              Z-Score: {report.profile.z_score}
            </p>
          ) : null}

          <div className="mt-3 space-y-2">
            {top3.map((item, idx) => (
              <div
                key={item.uni_code}
                className="flex items-center justify-between gap-2 rounded-[6px] border border-[#BFDBFE] bg-[#FFFFFF] px-3 py-2"
              >
                <div className="min-w-0">
                  <span className="text-[13px] font-semibold text-[#0F172A]">
                    {idx + 1}. {item.course_name}
                  </span>
                  <span className="block truncate text-[12px] text-[#475569]">
                    {item.university}
                  </span>
                </div>
                <BandBadge band={item.band} />
              </div>
            ))}
          </div>
        </div>

        {report.profile.z_score != null ? (
          <label className="mt-3 flex cursor-pointer items-center gap-2 text-[13px] text-[#475569]">
            <input
              type="checkbox"
              checked={includeZ}
              onChange={(e) => setIncludeZ(e.target.checked)}
              className="h-4 w-4 rounded border-[#CBD5E1] text-[#1D4ED8]"
            />
            <span>{t("share.includeZscore")}</span>
          </label>
        ) : null}

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={() => void handleCopy()}
            className="inline-flex items-center gap-1.5 rounded-[6px] bg-[#1D4ED8] px-4 py-2 text-[13px] font-medium text-[#FFFFFF] hover:bg-[#1E40AF]"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5" strokeWidth={2} />
            ) : (
              <Copy className="h-3.5 w-3.5" strokeWidth={1.5} />
            )}
            <span>{copied ? t("shortlist.copied") : t("share.copyText")}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
