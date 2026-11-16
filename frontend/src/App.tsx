import { useMemo, useState } from "react";
import { QueryClient, QueryClientProvider, useMutation, useQuery } from "@tanstack/react-query";
import { GitCompareArrows, Share2 } from "lucide-react";
import { getHealth, postRecommendations, setDemoMode } from "./api/client.ts";
import {
  BAND_ORDER,
  type CourseRow,
  type RecommendationReport,
  type RecommendationRequest,
} from "./api/types.ts";
import { BandsExplorer } from "./components/BandsExplorer.tsx";
import { CompareModal } from "./components/CompareModal.tsx";
import { CourseDrawer } from "./components/CourseDrawer.tsx";
import { Header } from "./components/Header.tsx";
import { HeroHome } from "./components/HeroHome.tsx";
import { ProfileForm } from "./components/ProfileForm.tsx";
import { RankingsView } from "./components/RankingsView.tsx";
import { ShareMatchModal } from "./components/ShareMatchModal.tsx";
import { ShortlistDrawer } from "./components/ShortlistDrawer.tsx";
import { SummaryStrip } from "./components/SummaryStrip.tsx";
import { useTranslation } from "./i18n/index.tsx";
import {
  loadReport,
  loadShortlist,
  loadUsedLlm,
  resetAllSessionData,
  saveReport,
  saveShortlist,
} from "./state/sessionStore.ts";

type WorkspaceTab = "rankings" | "bands";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 60_000,
    },
  },
});

function buildCourseMap(report: RecommendationReport | null): Map<string, CourseRow> {
  const map = new Map<string, CourseRow>();
  if (!report) return map;
  for (const band of BAND_ORDER) {
    for (const row of report.bands?.[band] ?? []) {
      map.set(row.uni_code, row);
    }
  }
  return map;
}

function AppShell() {
  const { t } = useTranslation();
  const [report, setReport] = useState<RecommendationReport | null>(() =>
    loadReport(),
  );
  const [usedLlm, setUsedLlm] = useState<boolean>(() => loadUsedLlm());
  const [editing, setEditing] = useState<boolean>(() => !loadReport());
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("rankings");
  const [selectedUniCode, setSelectedUniCode] = useState<string | null>(null);
  const [shortlist, setShortlist] = useState<string[]>(() => loadShortlist());
  const [shortlistOpen, setShortlistOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [compareList, setCompareList] = useState<string[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
    retry: 1,
  });

  const courseByCode = useMemo(() => buildCourseMap(report), [report]);
  const selectedCourse = selectedUniCode
    ? (courseByCode.get(selectedUniCode) ?? null)
    : null;
  const compareCourses = useMemo(
    () =>
      compareList
        .map((code) => courseByCode.get(code))
        .filter((c): c is CourseRow => Boolean(c)),
    [compareList, courseByCode],
  );

  const handleReportSuccess = (
    nextReport: RecommendationReport,
    nextUsedLlm: boolean,
  ) => {
    saveReport(nextReport, nextUsedLlm);
    setReport(nextReport);
    setUsedLlm(nextUsedLlm);
    setSelectedUniCode(null);
    setCompareList([]);
    setActiveTab("rankings");
    setEditing(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const quickExploreMutation = useMutation({
    mutationFn: async (preset: RecommendationRequest) => {
      try {
        return await postRecommendations(preset);
      } catch {
        setDemoMode(true);
        void queryClient.invalidateQueries({ queryKey: ["health"] });
        return await postRecommendations(preset);
      }
    },
    onSuccess: (data) => {
      handleReportSuccess(data.report, data.used_llm);
    },
  });

  const toggleShortlist = (uniCode: string) => {
    setShortlist((prev) => {
      const next = prev.includes(uniCode)
        ? prev.filter((c) => c !== uniCode)
        : [...prev, uniCode];
      saveShortlist(next);
      return next;
    });
  };

  const moveShortlist = (index: number, direction: -1 | 1) => {
    setShortlist((prev) => {
      const target = index + direction;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      const [item] = next.splice(index, 1);
      next.splice(target, 0, item);
      saveShortlist(next);
      return next;
    });
  };

  const toggleCompare = (uniCode: string) => {
    setCompareList((prev) => {
      if (prev.includes(uniCode)) {
        return prev.filter((c) => c !== uniCode);
      }
      if (prev.length >= 3) {
        return [...prev.slice(1), uniCode];
      }
      return [...prev, uniCode];
    });
  };

  const handleResetAll = () => {
    resetAllSessionData();
    setReport(null);
    setUsedLlm(false);
    setShortlist([]);
    setCompareList([]);
    setSelectedUniCode(null);
    setEditing(true);
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-[#0F172A]">
      <Header
        hasReport={Boolean(report)}
        shortlistCount={shortlist.length}
        onEditResults={() => setEditing((prev) => !prev)}
        onResetAll={handleResetAll}
        onOpenShortlist={() => setShortlistOpen(true)}
      />
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        {editing || !report ? (
          <div className="space-y-10">
            <HeroHome
              onQuickExplore={(preset) => quickExploreMutation.mutate(preset)}
              isExploring={quickExploreMutation.isPending}
            />

            <div
              id="intake-form"
              className="scroll-mt-6 space-y-5 border-t border-[#E2E8F0] pt-8"
            >
              <div>
                <h2 className="text-[20px] font-bold tracking-[-0.02em] text-[#0F172A] sm:text-[22px]">
                  {t("app.intakeTitle")}
                </h2>
                <p className="mt-1 text-[14px] text-[#475569]">
                  {t("app.intakeSubtitle")}
                </p>
              </div>
              <ProfileForm onSuccess={handleReportSuccess} />
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            <SummaryStrip report={report} usedLlm={usedLlm} />

            {/* Primary Workspace Tabs & Actions */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E2E8F0]">
              <div
                role="tablist"
                aria-label="Recommendations workspace views"
                className="-mb-px flex gap-6"
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "rankings"}
                  onClick={() => setActiveTab("rankings")}
                  className={
                    activeTab === "rankings"
                      ? "border-b-2 border-[#1D4ED8] pb-3 text-[14px] font-semibold text-[#1D4ED8]"
                      : "border-b-2 border-transparent pb-3 text-[14px] font-medium text-[#64748B] hover:text-[#0F172A]"
                  }
                >
                  {t("app.tab.recommended")}
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "bands"}
                  onClick={() => setActiveTab("bands")}
                  className={
                    activeTab === "bands"
                      ? "border-b-2 border-[#1D4ED8] pb-3 text-[14px] font-semibold text-[#1D4ED8]"
                      : "border-b-2 border-transparent pb-3 text-[14px] font-medium text-[#64748B] hover:text-[#0F172A]"
                  }
                >
                  {t("app.tab.bands")}
                </button>
              </div>

              <div className="flex flex-wrap items-center gap-2 pb-2">
                {compareList.length > 0 ? (
                  <button
                    type="button"
                    onClick={() => setCompareOpen(true)}
                    className="inline-flex items-center gap-1.5 rounded-[6px] border border-[#1D4ED8] bg-[#1D4ED8] px-3 py-1.5 text-[12px] font-medium text-[#FFFFFF] hover:bg-[#1E40AF]"
                  >
                    <GitCompareArrows className="h-3.5 w-3.5" strokeWidth={1.5} />
                    <span className="tabular-nums">
                      {t("compare.button", { count: compareList.length })}
                    </span>
                  </button>
                ) : null}

                <button
                  type="button"
                  onClick={() => setShareOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-1.5 text-[12px] font-medium text-[#0F172A] hover:bg-[#F1F5F9]"
                >
                  <Share2 className="h-3.5 w-3.5 text-[#1D4ED8]" strokeWidth={1.5} />
                  <span>{t("share.button")}</span>
                </button>
              </div>
            </div>

            {activeTab === "rankings" ? (
              <RankingsView
                report={report}
                selectedUniCode={selectedUniCode}
                shortlist={shortlist}
                compareList={compareList}
                onSelectCourse={setSelectedUniCode}
                onToggleShortlist={toggleShortlist}
                onToggleCompare={toggleCompare}
              />
            ) : (
              <BandsExplorer
                report={report}
                selectedUniCode={selectedUniCode}
                shortlist={shortlist}
                compareList={compareList}
                onSelectCourse={setSelectedUniCode}
                onToggleShortlist={toggleShortlist}
                onToggleCompare={toggleCompare}
              />
            )}

            <CourseDrawer
              course={selectedCourse}
              report={report}
              llmAvailable={Boolean(health?.llm_available)}
              onClose={() => setSelectedUniCode(null)}
            />

            <ShortlistDrawer
              open={shortlistOpen}
              shortlist={shortlist}
              courseByCode={courseByCode}
              report={report}
              onMove={moveShortlist}
              onRemove={(code) => toggleShortlist(code)}
              onSelectCourse={setSelectedUniCode}
              onClose={() => setShortlistOpen(false)}
            />

            <ShareMatchModal
              open={shareOpen}
              report={report}
              onClose={() => setShareOpen(false)}
            />

            <CompareModal
              open={compareOpen}
              courses={compareCourses}
              onRemove={(code) => toggleCompare(code)}
              onClose={() => setCompareOpen(false)}
            />
          </div>
        )}
      </main>
      <footer className="border-t border-[#E2E8F0] bg-[#FFFFFF] py-5">
        <div className="mx-auto max-w-6xl px-4 text-[12px] text-[#64748B] sm:px-6">
          {t("footer.note")}
        </div>
      </footer>
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppShell />
    </QueryClientProvider>
  );
}

export default App;
