import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { QueryClient, QueryClientProvider, useMutation, useQuery } from "@tanstack/react-query";
import {
  getMe,
  getMyResults,
  getOptions,
  postRecommendations,
  setDemoMode,
} from "./api/client.ts";
import {
  BAND_ORDER,
  type CourseRow,
  type Me,
  type RecommendationReport,
  type RecommendationRequest,
} from "./api/types.ts";
import { getCurrentUser, getSupabase, isAuthEnabled } from "./auth/supabase.ts";
import { AccountView } from "./components/AccountView.tsx";
import { AnalysingView } from "./components/AnalysingView.tsx";
import { CourseDetailView } from "./components/CourseDetailView.tsx";
import { DEFAULT_FORM_STATE, FormWizard, type FormState } from "./components/FormWizard.tsx";
import { RankingsView } from "./components/RankingsView.tsx";
import { ResultsView } from "./components/ResultsView.tsx";
import { Shell, type AppRoute } from "./components/Shell.tsx";
import { SignInView } from "./components/SignInView.tsx";
import { loadReport, resetAllSessionData, saveReport } from "./state/sessionStore.ts";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 60_000,
    },
  },
});

function parseHash(): { route: AppRoute; arg?: string } {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const [head, arg] = raw.split("/");
  switch (head) {
    case "signin":
    case "form":
    case "analysing":
    case "results":
    case "rankings":
    case "course":
    case "me":
      return { route: head, arg: arg ? decodeURIComponent(arg) : undefined };
    default:
      return { route: "form" };
  }
}

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

function formStateFromSaved(savedForm: RecommendationRequest): FormState {
  const ol: Record<string, string> = { ...DEFAULT_FORM_STATE.ol };
  for (const item of savedForm.ol ?? []) {
    if (item.subject && item.grade) ol[item.subject] = item.grade;
  }
  return {
    stream: savedForm.stream || DEFAULT_FORM_STATE.stream,
    al:
      savedForm.al?.length === 3
        ? (savedForm.al.map((x) => [x.subject, x.grade]) as [string, string][])
        : DEFAULT_FORM_STATE.al,
    ol,
    cgt: String(savedForm.cgt ?? DEFAULT_FORM_STATE.cgt),
    z_score: savedForm.z_score != null ? String(savedForm.z_score) : "",
    admission_district: savedForm.admission_district || DEFAULT_FORM_STATE.admission_district,
    home_district: savedForm.admission_district || DEFAULT_FORM_STATE.home_district,
    ds_division: savedForm.ds_division || DEFAULT_FORM_STATE.ds_division,
    preferences: savedForm.preferences ?? "",
    use_llm: Boolean(savedForm.use_llm),
  };
}

function AppShell() {
  const authEnabled = isAuthEnabled();
  const [signedIn, setSignedIn] = useState<boolean>(() => !authEnabled);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [hashState, setHashState] = useState(() => parseHash());
  const [report, setReport] = useState<RecommendationReport | null>(() => loadReport());
  const [restoringResults, setRestoringResults] = useState<boolean>(
    () => authEnabled && !loadReport(),
  );
  const [form, setForm] = useState<FormState>(DEFAULT_FORM_STATE);
  const [me, setMe] = useState<Me | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const toastTimerRef = useRef<number | null>(null);

  const showToast = useCallback((msg: string) => {
    setToastMsg(msg);
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToastMsg(null), 3000);
  }, []);

  const navigate = useCallback((hash: string) => {
    window.location.hash = hash;
    window.scrollTo({ top: 0 });
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      setHashState(parseHash());
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    if (!authEnabled) return;
    const sb = getSupabase();
    if (!sb) return;

    getCurrentUser().then((user) => {
      setSignedIn(Boolean(user));
      setUserEmail(user?.email ?? null);
      if (!user) navigate("#/signin");
    });

    const { data: sub } = sb.auth.onAuthStateChange((_event, session) => {
      setSignedIn(Boolean(session?.user));
      setUserEmail(session?.user?.email ?? null);
    });
    return () => sub.subscription.unsubscribe();
  }, [authEnabled, navigate]);

  const { data: options } = useQuery({
    queryKey: ["options"],
    queryFn: async () => {
      try {
        return await getOptions();
      } catch {
        setDemoMode(true);
        showToast("API offline — running with sample data.");
        return await getOptions();
      }
    },
    enabled: signedIn,
  });

  useEffect(() => {
    if (!signedIn || !authEnabled) return;
    getMe()
      .then(setMe)
      .catch(() => {});
    getMyResults()
      .then((saved) => {
        saveReport(saved.report, saved.used_llm);
        setReport(saved.report);
        if (saved.form) setForm(formStateFromSaved(saved.form));
      })
      .catch(() => {})
      .finally(() => setRestoringResults(false));
  }, [signedIn, authEnabled]);

  const runMutation = useMutation({
    mutationFn: async (req: RecommendationRequest) => {
      try {
        return await postRecommendations(req);
      } catch (err) {
        if (err instanceof Error && err.message.includes("Unable to reach")) {
          setDemoMode(true);
          return await postRecommendations(req);
        }
        throw err;
      }
    },
    onSuccess: (res) => {
      saveReport(res.report, res.used_llm);
      setReport(res.report);
      if (authEnabled) {
        getMe().then(setMe).catch(() => {});
      }
    },
    onError: (err) => {
      showToast(err instanceof Error ? err.message : "Failed to run recommendations");
      navigate("#/form");
    },
  });

  const courseByCode = useMemo(() => buildCourseMap(report), [report]);

  const handleSignOut = async () => {
    const sb = getSupabase();
    if (sb) await sb.auth.signOut();
    resetAllSessionData();
    setReport(null);
    setMe(null);
    if (authEnabled) {
      setSignedIn(false);
      navigate("#/signin");
    } else {
      navigate("#/form");
    }
  };

  const activeRoute: AppRoute = !signedIn ? "signin" : hashState.route;

  if (activeRoute === "signin") {
    return (
      <>
        <SignInView
          onSignedIn={() => {
            setSignedIn(true);
            navigate("#/form");
          }}
          onToast={showToast}
        />
        <div id="toast" className={toastMsg ? "show" : ""} role="status">
          {toastMsg ?? ""}
        </div>
      </>
    );
  }

  let content: React.ReactNode = null;

  if (restoringResults && (activeRoute === "results" || activeRoute === "rankings" || activeRoute === "course")) {
    content = <div className="card empty">Loading your saved results…</div>;
  } else if (activeRoute === "analysing") {
    content = (
      <AnalysingView
        isDone={runMutation.isSuccess}
        onCompleteAnimation={() => navigate("#/results")}
      />
    );
  } else if (activeRoute === "results") {
    if (!report) {
      content = options ? (
        <FormWizard
          options={options}
          form={form}
          hasSavedReport={false}
          onChangeForm={setForm}
          onSubmit={(req) => {
            runMutation.mutate(req);
            navigate("#/analysing");
          }}
          onViewSaved={() => navigate("#/results")}
          onToast={showToast}
        />
      ) : null;
    } else {
      content = (
        <ResultsView
          report={report}
          onEditResults={() => navigate("#/form")}
          onOpenRankings={() => navigate("#/rankings")}
          onOpenCourse={(uni) => navigate(`#/course/${encodeURIComponent(uni)}`)}
        />
      );
    }
  } else if (activeRoute === "rankings") {
    if (!report) {
      navigate("#/form");
    } else {
      content = (
        <RankingsView
          report={report}
          onOpenCourse={(uni) => navigate(`#/course/${encodeURIComponent(uni)}`)}
        />
      );
    }
  } else if (activeRoute === "course") {
    const course = hashState.arg ? courseByCode.get(hashState.arg) : undefined;
    if (!report || !course) {
      navigate("#/results");
    } else {
      content = (
        <CourseDetailView
          report={report}
          course={course}
          chatUsage={me?.usage?.chat ?? null}
          onUpdateChatUsage={(usage) =>
            setMe((prev) =>
              prev ? { ...prev, usage: { ...prev.usage, chat: usage } } : prev,
            )
          }
          onBack={() => window.history.back()}
          onToast={showToast}
        />
      );
    }
  } else if (activeRoute === "me") {
    content = (
      <AccountView
        me={me}
        userEmail={userEmail}
        onOpenCourse={(uni) => navigate(`#/course/${encodeURIComponent(uni)}`)}
        onSignOut={() => void handleSignOut()}
      />
    );
  } else {
    content = options ? (
      <FormWizard
        options={options}
        form={form}
        hasSavedReport={Boolean(report)}
        onChangeForm={setForm}
        onSubmit={(req) => {
          runMutation.mutate(req);
          navigate("#/analysing");
        }}
        onViewSaved={() => navigate("#/results")}
        onToast={showToast}
      />
    ) : (
      <div className="card empty">Loading options…</div>
    );
  }

  return (
    <>
      <Shell active={activeRoute} me={me} userEmail={userEmail} onNavigate={navigate}>
        {content}
      </Shell>
      <div id="toast" className={toastMsg ? "show" : ""} role="status">
        {toastMsg ?? ""}
      </div>
    </>
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
