import { useEffect, useState } from "react";
import { X } from "lucide-react";
import type { CourseRow, RecommendationReport } from "../api/types.ts";
import { useTranslation } from "../i18n/index.tsx";
import { CareerOutlook } from "./CareerOutlook.tsx";
import { CourseChat } from "./CourseChat.tsx";
import { CourseOverview } from "./CourseOverview.tsx";

type DrawerTab = "overview" | "chat" | "career";

interface CourseDrawerProps {
  course: CourseRow | null;
  report: RecommendationReport;
  llmAvailable: boolean;
  onClose: () => void;
}

export function CourseDrawer({
  course,
  report,
  llmAvailable,
  onClose,
}: CourseDrawerProps) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<DrawerTab>("overview");

  useEffect(() => {
    setActiveTab("overview");
  }, [course?.uni_code]);

  useEffect(() => {
    if (!course) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [course, onClose]);

  if (!course) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-label={`${course.course_name}`}
    >
      {/* Backdrop */}
      <div
        aria-hidden="true"
        onClick={onClose}
        className="fixed inset-0 bg-[#0F172A]/25"
      />

      {/* Slide-over panel: full-screen on mobile (<768px), max-w-[640px] on desktop */}
      <aside
        style={{ boxShadow: "var(--shadow-drawer)" }}
        className="relative z-10 flex h-full w-full flex-col border-l border-[#E2E8F0] bg-[#FFFFFF] md:max-w-[640px]"
      >
        {/* Drawer Header */}
        <div className="flex items-start justify-between gap-4 border-b border-[#E2E8F0] px-5 py-4">
          <div className="min-w-0">
            <span className="text-[12px] font-medium text-[#64748B]">
              {course.uni_code} · {t("drawer.coursePrefix", { code: course.course_code })}
            </span>
            <h2 className="mt-0.5 text-[18px] font-semibold tracking-[-0.015em] text-[#0F172A]">
              {course.course_name}
            </h2>
            <p className="text-[13px] text-[#475569]">{course.university}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("drawer.closeAria")}
            className="rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] p-1.5 text-[#475569] hover:border-[#CBD5E1] hover:bg-[#F1F5F9] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]"
          >
            <X className="h-4 w-4" strokeWidth={1.5} />
          </button>
        </div>

        {/* Drawer Tabs */}
        <div className="border-b border-[#E2E8F0] px-5">
          <div
            role="tablist"
            aria-label="Course details tabs"
            className="-mb-px flex flex-wrap gap-5"
          >
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "overview"}
              onClick={() => setActiveTab("overview")}
              className={
                activeTab === "overview"
                  ? "border-b-2 border-[#1D4ED8] py-3 text-[13px] font-semibold text-[#1D4ED8]"
                  : "border-b-2 border-transparent py-3 text-[13px] font-medium text-[#64748B] hover:text-[#0F172A]"
              }
            >
              {t("drawer.tab.overview")}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "chat"}
              onClick={() => setActiveTab("chat")}
              className={
                activeTab === "chat"
                  ? "border-b-2 border-[#1D4ED8] py-3 text-[13px] font-semibold text-[#1D4ED8]"
                  : "border-b-2 border-transparent py-3 text-[13px] font-medium text-[#64748B] hover:text-[#0F172A]"
              }
            >
              {t("drawer.tab.chat")}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "career"}
              onClick={() => setActiveTab("career")}
              className={
                activeTab === "career"
                  ? "border-b-2 border-[#1D4ED8] py-3 text-[13px] font-semibold text-[#1D4ED8]"
                  : "border-b-2 border-transparent py-3 text-[13px] font-medium text-[#64748B] hover:text-[#0F172A]"
              }
            >
              {t("drawer.tab.career")}
            </button>
          </div>
        </div>

        {/* Drawer Body */}
        <div className="flex-1 overflow-y-auto p-5">
          {activeTab === "overview" ? (
            <CourseOverview course={course} report={report} />
          ) : null}
          {activeTab === "chat" ? (
            <CourseChat
              course={course}
              report={report}
              llmAvailable={llmAvailable}
              onCareerJobStarted={() => setActiveTab("career")}
            />
          ) : null}
          {activeTab === "career" ? (
            <CareerOutlook courseName={course.course_name} />
          ) : null}
        </div>
      </aside>
    </div>
  );
}
