import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Info,
  Loader2,
  RefreshCw,
} from "lucide-react";
import {
  ApiError,
  getOptions,
  isDemoMode,
  postRecommendations,
  setDemoMode,
} from "../api/client.ts";
import type {
  Options,
  RecommendationReport,
  RecommendationRequest,
  StreamHint,
  SubjectGrade,
} from "../api/types.ts";
import {
  translateOlSubject,
  translateStream,
  useTranslation,
  type Locale,
  type TranslationKey,
} from "../i18n/index.tsx";
import {
  loadFormState,
  saveFormState,
  type ProfileFormState,
} from "../state/sessionStore.ts";

interface ProfileFormProps {
  onSuccess: (report: RecommendationReport, usedLlm: boolean) => void;
}

const INTEREST_CHIPS = [
  "Software & AI",
  "Engineering",
  "Medicine & Health",
  "Business & Finance",
  "Design & Architecture",
  "Near Home",
];

function buildInitialState(options: Options): ProfileFormState {
  const saved = loadFormState();
  if (saved && options.streams.includes(saved.stream)) {
    return saved;
  }

  const defaultStream =
    options.streams.find((s) => s === "Physical Science") ??
    options.streams[0] ??
    "";
  const hintDefaults = options.stream_hints[defaultStream]?.defaults ?? [];
  const defaultGrades = options.al_grades;
  const al: SubjectGrade[] = [0, 1, 2].map((idx) => ({
    subject: hintDefaults[idx] ?? options.al_subjects[idx] ?? "",
    grade: defaultGrades[0] ?? "A",
  }));

  const defaultDistrict =
    options.districts.find((d) => d === "Kandy") ?? options.districts[0] ?? "";
  const townList = options.towns[defaultDistrict] ?? [];

  return {
    stream: defaultStream,
    al,
    ol: {},
    cgt: "50",
    zScore: "",
    admissionDistrict: defaultDistrict,
    homeDistrict: defaultDistrict,
    homeTown: townList[0] ?? "",
    preferences: "",
    useLlm: false,
  };
}

function getStreamSoftNotice(
  locale: Locale,
  t: (key: TranslationKey, params?: Record<string, string | number>) => string,
  stream: string,
  subjects: string[],
  hint: StreamHint | undefined,
): string | null {
  if (!hint) return null;
  const chosen = subjects.filter(Boolean);
  if (chosen.length === 0) return null;
  const streamLabel = translateStream(locale, stream);

  if (hint.required_all && hint.required_all.length > 0) {
    const missing = hint.required_all.filter((req) => !chosen.includes(req));
    if (missing.length > 0) {
      return t("form.softNotice.requiredAll", {
        stream: streamLabel,
        subjects: missing.join(", "),
      });
    }
  }

  if (hint.required_any && hint.required_any.length > 0) {
    const hasAny = hint.required_any.some((req) => chosen.includes(req));
    if (!hasAny) {
      return t("form.softNotice.requiredAny", {
        stream: streamLabel,
        subjects: hint.required_any.join(", "),
      });
    }
  }

  if (hint.allowed && hint.allowed.length > 0) {
    const outside = chosen.filter((sub) => !hint.allowed!.includes(sub));
    if (outside.length > 0) {
      return t("form.softNotice.allowed", {
        stream: streamLabel,
        subjects: outside.join(", "),
      });
    }
  }

  return null;
}

export function ProfileForm({ onSuccess }: ProfileFormProps) {
  const { locale, t } = useTranslation();
  const queryClient = useQueryClient();
  const [demoActive, setDemoActive] = useState<boolean>(() => isDemoMode());
  const [step, setStep] = useState<1 | 2 | 3>(1);

  const {
    data: options,
    isLoading: isLoadingOptions,
    isError: isOptionsError,
    refetch: refetchOptions,
  } = useQuery({
    queryKey: ["options", demoActive],
    queryFn: getOptions,
    staleTime: Infinity,
    retry: 1,
  });

  const [form, setForm] = useState<ProfileFormState | null>(null);
  const [olOpen, setOlOpen] = useState(false);
  const [districtFilter, setDistrictFilter] = useState("");
  const [townFilter, setTownFilter] = useState("");
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (options && !form) {
      const initial = buildInitialState(options);
      setForm(initial);
      const hasSavedOl = Object.values(initial.ol).some((g) => Boolean(g));
      if (hasSavedOl) {
        setOlOpen(true);
      }
    }
  }, [options, form]);

  useEffect(() => {
    if (form) {
      saveFormState(form);
    }
  }, [form]);

  const mutation = useMutation({
    mutationFn: postRecommendations,
    onSuccess: (data) => {
      setValidationErrors([]);
      onSuccess(data.report, data.used_llm);
    },
  });

  useEffect(() => {
    if (!mutation.isPending) {
      setElapsedSeconds(0);
      return;
    }
    const start = Date.now();
    const id = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => window.clearInterval(id);
  }, [mutation.isPending]);

  const softNotice = useMemo(() => {
    if (!options || !form) return null;
    return getStreamSoftNotice(
      locale,
      t,
      form.stream,
      form.al.map((item) => item.subject),
      options.stream_hints[form.stream],
    );
  }, [locale, t, options, form]);

  const handleEnableDemo = () => {
    setDemoMode(true);
    setDemoActive(true);
    void queryClient.invalidateQueries({ queryKey: ["health"] });
  };

  const handleStreamChange = (newStream: string) => {
    if (!options || !form) return;
    const defaults = options.stream_hints[newStream]?.defaults ?? [];
    setForm({
      ...form,
      stream: newStream,
      al: [0, 1, 2].map((idx) => ({
        subject: defaults[idx] ?? form.al[idx]?.subject ?? "",
        grade: form.al[idx]?.grade || options.al_grades[0] || "A",
      })),
    });
  };

  const handleAlChange = (
    index: number,
    field: "subject" | "grade",
    value: string,
  ) => {
    if (!form) return;
    const nextAl = form.al.map((entry, idx) =>
      idx === index ? { ...entry, [field]: value } : entry,
    );
    setForm({ ...form, al: nextAl });
  };

  const handleHomeDistrictChange = (district: string) => {
    if (!options || !form) return;
    const towns = options.towns[district] ?? [];
    setTownFilter("");
    setForm({
      ...form,
      homeDistrict: district,
      homeTown: towns[0] ?? "",
    });
  };

  const toggleInterestChip = (chip: string) => {
    if (!form) return;
    const current = form.preferences.trim();
    const lower = current.toLowerCase();
    if (lower.includes(chip.toLowerCase())) {
      const cleaned = current
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s && s.toLowerCase() !== chip.toLowerCase())
        .join(", ");
      setForm({ ...form, preferences: cleaned });
    } else {
      const next = current ? `${current}, ${chip}` : chip;
      setForm({ ...form, preferences: next.slice(0, 2000) });
    }
  };

  const validateStep1 = (): string[] => {
    if (!form) return [];
    const errs: string[] = [];
    if (!form.stream) errs.push(t("form.err.stream"));
    const chosenSubjects = form.al.map((item) => item.subject.trim());
    if (chosenSubjects.some((s) => !s)) {
      errs.push(t("form.err.alAll"));
    } else if (new Set(chosenSubjects).size !== 3) {
      errs.push(t("form.err.alDistinct"));
    }
    if (form.al.some((item) => !item.grade)) {
      errs.push(t("form.err.alGrades"));
    }
    return errs;
  };

  const validateStep2 = (): string[] => {
    if (!form) return [];
    const errs: string[] = [];
    const cgtTrimmed = form.cgt.trim();
    const cgtNum = Number(cgtTrimmed);
    if (!cgtTrimmed || !Number.isInteger(cgtNum) || cgtNum < 0 || cgtNum > 100) {
      errs.push(t("form.err.cgt"));
    }
    const zTrimmed = form.zScore.trim();
    if (zTrimmed !== "") {
      const zNum = Number(zTrimmed);
      if (Number.isNaN(zNum) || !Number.isFinite(zNum)) {
        errs.push(t("form.err.zscore"));
      }
    }
    if (!form.admissionDistrict) errs.push(t("form.err.admissionDistrict"));
    if (!(options?.towns[form.homeDistrict] ?? []).includes(form.homeTown))
      errs.push(t("form.err.homeTown"));
    return errs;
  };

  const handleNextStep = () => {
    const errs = step === 1 ? validateStep1() : step === 2 ? validateStep2() : [];
    if (errs.length > 0) {
      setValidationErrors(errs);
      return;
    }
    setValidationErrors([]);
    setStep((prev) => (prev === 1 ? 2 : 3));
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!options || !form || mutation.isPending) return;

    const errors: string[] = [...validateStep1(), ...validateStep2()];
    if (form.preferences.length > 2000) {
      errors.push(t("form.err.preferencesMax"));
    }

    if (errors.length > 0) {
      setValidationErrors(errors);
      if (validateStep1().length > 0) setStep(1);
      else if (validateStep2().length > 0) setStep(2);
      return;
    }

    setValidationErrors([]);

    const zTrimmed = form.zScore.trim();
    const parsedZScore = zTrimmed !== "" ? Number(zTrimmed) : null;

    const olEntries: SubjectGrade[] = options.ol_subjects
      .map((subject) => ({
        subject,
        grade: (form.ol[subject] ?? "").trim(),
      }))
      .filter((entry) => entry.grade !== "");

    const payload: RecommendationRequest = {
      stream: form.stream,
      al: form.al.map((entry) => ({
        subject: entry.subject,
        grade: entry.grade || "A",
      })),
      ol: olEntries,
      cgt: Number(form.cgt.trim()),
      z_score: parsedZScore,
      admission_district: form.admissionDistrict,
      home_district: form.homeDistrict,
      home_town: form.homeTown,
      preferences: form.preferences.trim(),
      use_llm: options.llm_available ? form.useLlm : false,
    };

    mutation.mutate(payload);
  };

  if (isLoadingOptions) {
    return (
      <div className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-6">
        <div className="flex items-center gap-3 text-[14px] text-[#475569]">
          <Loader2 className="h-4 w-4 animate-spin text-[#1D4ED8]" strokeWidth={1.5} />
          <span>{t("form.loadingOptions")}</span>
        </div>
      </div>
    );
  }

  if (isOptionsError || !options || !form) {
    return (
      <div className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-6">
        <h2 className="text-[18px] font-semibold tracking-[-0.015em] text-[#0F172A]">
          {t("form.offlineTitle")}
        </h2>
        <p className="mt-1.5 text-[14px] text-[#475569]">{t("form.offlineHint")}</p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => void refetchOptions()}
            className="inline-flex items-center gap-2 rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-3.5 py-2 text-[13px] font-medium text-[#0F172A] hover:border-[#CBD5E1] hover:bg-[#F1F5F9]"
          >
            <RefreshCw className="h-3.5 w-3.5 text-[#475569]" strokeWidth={1.5} />
            <span>{t("form.retryConnection")}</span>
          </button>
          <button
            type="button"
            onClick={handleEnableDemo}
            className="inline-flex items-center rounded-[6px] bg-[#1D4ED8] px-4 py-2 text-[13px] font-medium text-[#FFFFFF] hover:bg-[#1E40AF]"
          >
            {t("form.useDemoData")}
          </button>
        </div>
      </div>
    );
  }

  const apiErrors =
    mutation.error instanceof ApiError
      ? mutation.error.errors
      : mutation.error
        ? [t("form.err.unexpected")]
        : [];
  const allErrors = [...validationErrors, ...apiErrors];

  const filteredDistricts = districtFilter.trim()
    ? options.districts.filter((d) =>
        d.toLowerCase().includes(districtFilter.trim().toLowerCase()),
      )
    : options.districts;

  const allHomeTowns = options.towns[form.homeDistrict] ?? [];
  const filteredTowns = townFilter.trim()
    ? allHomeTowns.filter((d) =>
        d.toLowerCase().includes(townFilter.trim().toLowerCase()),
      )
    : allHomeTowns;
  const homeTownValid = allHomeTowns.includes(form.homeTown);

  const aiMilestone =
    elapsedSeconds < 4
      ? t("form.aiMilestone1")
      : elapsedSeconds < 10
        ? t("form.aiMilestone2")
        : elapsedSeconds < 18
          ? t("form.aiMilestone3")
          : t("form.aiMilestone4");

  const wizardSteps: Array<{ num: 1 | 2 | 3; label: string }> = [
    { num: 1, label: t("form.wizard.step1") },
    { num: 2, label: t("form.wizard.step2") },
    { num: 3, label: t("form.wizard.step3") },
  ];

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      {demoActive ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[8px] border border-[#BFDBFE] bg-[#EFF6FF] px-4 py-3 text-[13px] text-[#0F172A]">
          <span>{t("form.demoBanner")}</span>
          <button
            type="button"
            onClick={() => {
              setDemoMode(false);
              setDemoActive(false);
              setForm(null);
              void queryClient.invalidateQueries({ queryKey: ["health"] });
            }}
            className="rounded-[6px] border border-[#BFDBFE] bg-[#FFFFFF] px-3 py-1 text-[12px] font-medium text-[#1D4ED8] hover:bg-[#F8FAFC]"
          >
            {t("form.switchLiveApi")}
          </button>
        </div>
      ) : null}

      {/* 3-Step Wizard Progress Bar */}
      <nav aria-label="Form steps" className="grid grid-cols-3 gap-2">
        {wizardSteps.map((ws) => {
          const active = step === ws.num;
          const completed = step > ws.num;
          return (
            <button
              key={ws.num}
              type="button"
              onClick={() => {
                setValidationErrors([]);
                setStep(ws.num);
              }}
              className={
                active
                  ? "flex items-center gap-2 rounded-[8px] border border-[#1D4ED8] bg-[#EFF6FF] px-3 py-2.5 text-left text-[12px] font-semibold text-[#1D4ED8] sm:text-[13px]"
                  : completed
                    ? "flex items-center gap-2 rounded-[8px] border border-[#BFDBFE] bg-[#FFFFFF] px-3 py-2.5 text-left text-[12px] font-medium text-[#0F172A] sm:text-[13px]"
                    : "flex items-center gap-2 rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2.5 text-left text-[12px] font-medium text-[#64748B] hover:bg-[#F1F5F9] sm:text-[13px]"
              }
            >
              <span
                className={
                  active
                    ? "tabular-nums flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#1D4ED8] text-[11px] font-bold text-[#FFFFFF]"
                    : "tabular-nums flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-[#CBD5E1] text-[11px] font-semibold"
                }
              >
                {ws.num}
              </span>
              <span className="truncate">{ws.label}</span>
            </button>
          );
        })}
      </nav>

      {/* STEP 1: Stream & A/L Subjects with Tap-Friendly Grade Pills */}
      {step === 1 ? (
        <section className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-5 sm:p-6">
          <h2 className="text-[18px] font-semibold tracking-[-0.015em] text-[#0F172A]">
            {t("form.sec1.title")}
          </h2>
          <p className="mt-1 text-[13px] text-[#64748B]">
            {t("form.sec1.subtitle")}
          </p>

          <div className="mt-4">
            <label
              htmlFor="stream-select"
              className="block text-[13px] font-medium text-[#475569]"
            >
              {t("form.streamLabel")}
            </label>
            <select
              id="stream-select"
              value={form.stream}
              onChange={(e) => handleStreamChange(e.target.value)}
              className="mt-1.5 w-full rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-[14px] text-[#0F172A] focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20 sm:max-w-md"
            >
              {options.streams.map((stream) => (
                <option key={stream} value={stream}>
                  {translateStream(locale, stream)}
                </option>
              ))}
            </select>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
            {form.al.map((entry, idx) => (
              <div
                key={idx}
                className="rounded-[6px] border border-[#E2E8F0] bg-[#F8FAFC] p-3.5"
              >
                <span className="block text-[12px] font-medium text-[#64748B]">
                  {t("form.subjectSlot", { n: idx + 1 })}
                </span>
                <select
                  aria-label={t("form.subjectSlot", { n: idx + 1 })}
                  value={entry.subject}
                  onChange={(e) => handleAlChange(idx, "subject", e.target.value)}
                  className="mt-1.5 w-full rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-2.5 py-1.5 text-[13px] text-[#0F172A] focus:border-[#1D4ED8] focus:outline-none"
                >
                  <option value="">{t("form.selectSubject")}</option>
                  {options.al_subjects.map((sub) => (
                    <option key={sub} value={sub}>
                      {sub}
                    </option>
                  ))}
                </select>

                {/* Tap-friendly A/L Grade Pills */}
                <div
                  role="group"
                  aria-label={`${t("form.subjectSlot", { n: idx + 1 })} grade`}
                  className="mt-2.5 grid grid-cols-5 gap-1"
                >
                  {options.al_grades.map((g) => {
                    const selected = entry.grade === g;
                    return (
                      <button
                        key={g}
                        type="button"
                        aria-pressed={selected}
                        onClick={() => handleAlChange(idx, "grade", g)}
                        className={
                          selected
                            ? "rounded-[6px] border border-[#1D4ED8] bg-[#1D4ED8] py-1.5 text-[12px] font-semibold text-[#FFFFFF]"
                            : "rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] py-1.5 text-[12px] font-medium text-[#475569] hover:bg-[#F1F5F9]"
                        }
                      >
                        {g}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {softNotice ? (
            <div className="mt-4 flex items-start gap-2.5 rounded-[6px] border border-[#BFDBFE] bg-[#EFF6FF] px-3.5 py-2.5 text-[13px] text-[#0F172A]">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-[#1D4ED8]" strokeWidth={1.5} />
              <span>{softNotice}</span>
            </div>
          ) : null}
        </section>
      ) : null}

      {/* STEP 2: CGT, Z-Score, O/L Grades & Searchable Location */}
      {step === 2 ? (
        <div className="space-y-5">
          <section className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-5 sm:p-6">
            <h2 className="text-[18px] font-semibold tracking-[-0.015em] text-[#0F172A]">
              {t("form.sec2.title")}
            </h2>

            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="cgt-input"
                  className="block text-[13px] font-medium text-[#475569]"
                >
                  {t("form.cgtLabel")} <span className="text-[#1D4ED8]">*</span>
                </label>
                <input
                  id="cgt-input"
                  type="number"
                  inputMode="numeric"
                  min={0}
                  max={100}
                  step={1}
                  required
                  value={form.cgt}
                  onChange={(e) => setForm({ ...form, cgt: e.target.value })}
                  placeholder={t("form.cgtPlaceholder")}
                  className="tabular-nums mt-1.5 w-full rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-[14px] text-[#0F172A] focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20"
                />
                <p className="mt-1 text-[12px] text-[#64748B]">
                  {t("form.cgtHelp")}
                </p>
              </div>

              <div>
                <label
                  htmlFor="zscore-input"
                  className="block text-[13px] font-medium text-[#475569]"
                >
                  {t("form.zscoreLabel")}{" "}
                  <span className="text-[#64748B]">{t("form.optional")}</span>
                </label>
                <input
                  id="zscore-input"
                  type="number"
                  inputMode="decimal"
                  step="0.0001"
                  value={form.zScore}
                  onChange={(e) => setForm({ ...form, zScore: e.target.value })}
                  placeholder={t("form.zscorePlaceholder")}
                  className="tabular-nums mt-1.5 w-full rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-[14px] text-[#0F172A] focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20"
                />
                <p className="mt-1 text-[12px] text-[#64748B]">
                  {t("form.zscoreHelp")}
                </p>
              </div>
            </div>

            {/* Collapsible O/L Grades with Tap Pills */}
            <div className="mt-5 border-t border-[#E2E8F0] pt-4">
              <button
                type="button"
                onClick={() => setOlOpen((prev) => !prev)}
                aria-expanded={olOpen}
                className="flex w-full items-center justify-between rounded-[6px] bg-[#F8FAFC] px-3.5 py-2.5 text-left text-[13px] font-medium text-[#0F172A] hover:bg-[#F1F5F9]"
              >
                <span>{t("form.olToggle")}</span>
                {olOpen ? (
                  <ChevronUp className="h-4 w-4 shrink-0 text-[#64748B]" strokeWidth={1.5} />
                ) : (
                  <ChevronDown className="h-4 w-4 shrink-0 text-[#64748B]" strokeWidth={1.5} />
                )}
              </button>

              {olOpen ? (
                <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
                  {options.ol_subjects.map((subject) => (
                    <div
                      key={subject}
                      className="rounded-[6px] border border-[#E2E8F0] bg-[#F8FAFC] p-3"
                    >
                      <span className="block text-[12px] font-medium text-[#475569]">
                        {t("form.olSubjectLabel", {
                          subject: translateOlSubject(locale, subject),
                        })}
                      </span>
                      <div className="mt-2 grid grid-cols-5 gap-1">
                        {options.ol_grades.map((grade) => {
                          const selected = (form.ol[subject] ?? "") === grade;
                          return (
                            <button
                              key={grade}
                              type="button"
                              aria-pressed={selected}
                              onClick={() =>
                                setForm({
                                  ...form,
                                  ol: {
                                    ...form.ol,
                                    [subject]: selected ? "" : grade,
                                  },
                                })
                              }
                              className={
                                selected
                                  ? "rounded-[6px] border border-[#1D4ED8] bg-[#1D4ED8] py-1 text-[12px] font-semibold text-[#FFFFFF]"
                                  : "rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] py-1 text-[12px] font-medium text-[#475569] hover:bg-[#F1F5F9]"
                              }
                            >
                              {grade}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </section>

          <section className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-5 sm:p-6">
            <h2 className="text-[18px] font-semibold tracking-[-0.015em] text-[#0F172A]">
              {t("form.sec3.title")}
            </h2>
            <p className="mt-1 text-[13px] text-[#64748B]">
              {t("form.sec3.subtitle")}
            </p>

            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div>
                <label
                  htmlFor="admission-district"
                  className="block text-[13px] font-medium text-[#475569]"
                >
                  {t("form.admissionDistrict")}
                </label>
                <input
                  type="search"
                  value={districtFilter}
                  onChange={(e) => setDistrictFilter(e.target.value)}
                  placeholder={t("form.searchDistrict")}
                  aria-label={t("form.searchDistrict")}
                  className="mt-1.5 w-full rounded-[6px] border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-1.5 text-[12px] text-[#0F172A] placeholder:text-[#64748B] focus:border-[#1D4ED8] focus:outline-none"
                />
                <select
                  id="admission-district"
                  value={form.admissionDistrict}
                  onChange={(e) =>
                    setForm({ ...form, admissionDistrict: e.target.value })
                  }
                  className="mt-1.5 w-full rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-[14px] text-[#0F172A] focus:border-[#1D4ED8] focus:outline-none"
                >
                  {filteredDistricts.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="home-district"
                  className="block text-[13px] font-medium text-[#475569]"
                >
                  {t("form.homeDistrict")}
                </label>
                <select
                  id="home-district"
                  value={form.homeDistrict}
                  onChange={(e) => handleHomeDistrictChange(e.target.value)}
                  className="mt-9 w-full rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-[14px] text-[#0F172A] focus:border-[#1D4ED8] focus:outline-none"
                >
                  {options.districts.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="home-town"
                  className="block text-[13px] font-medium text-[#475569]"
                >
                  {t("form.homeTown")}
                </label>
                <input
                  type="search"
                  value={townFilter}
                  onChange={(e) => setTownFilter(e.target.value)}
                  placeholder={t("form.searchTown")}
                  aria-label={t("form.searchTown")}
                  className="mt-1.5 w-full rounded-[6px] border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-1.5 text-[12px] text-[#0F172A] placeholder:text-[#64748B] focus:border-[#1D4ED8] focus:outline-none"
                />
                <select
                  id="home-town"
                  value={homeTownValid ? form.homeTown : ""}
                  onChange={(e) => setForm({ ...form, homeTown: e.target.value })}
                  className="mt-1.5 w-full rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-[14px] text-[#0F172A] focus:border-[#1D4ED8] focus:outline-none"
                >
                  {!homeTownValid && (
                    <option value="" disabled>
                      {t("form.homeTown")}
                    </option>
                  )}
                  {filteredTowns.map((town) => (
                    <option key={town} value={town}>
                      {town}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </section>
        </div>
      ) : null}

      {/* STEP 3: Interests, Quick Chips & AI Toggle */}
      {step === 3 ? (
        <section className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-5 sm:p-6">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-[18px] font-semibold tracking-[-0.015em] text-[#0F172A]">
              {t("form.sec4.title")}
            </h2>
            <span className="tabular-nums text-[12px] text-[#64748B]">
              {form.preferences.length} / 2000
            </span>
          </div>

          <p className="mt-2 text-[12px] font-medium text-[#64748B]">
            {t("form.interestChipsLabel")}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {INTEREST_CHIPS.map((chip) => {
              const active = form.preferences
                .toLowerCase()
                .includes(chip.toLowerCase());
              return (
                <button
                  key={chip}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleInterestChip(chip)}
                  className={
                    active
                      ? "rounded-full border border-[#1D4ED8] bg-[#EFF6FF] px-3 py-1 text-[12px] font-semibold text-[#1D4ED8]"
                      : "rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-1 text-[12px] font-medium text-[#475569] hover:bg-[#F1F5F9]"
                  }
                >
                  {chip}
                </button>
              );
            })}
          </div>

          <textarea
            id="preferences-input"
            rows={3}
            maxLength={2000}
            value={form.preferences}
            onChange={(e) => setForm({ ...form, preferences: e.target.value })}
            placeholder={t("form.preferencesPlaceholder")}
            className="mt-3 w-full rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-[14px] text-[#0F172A] placeholder:text-[#64748B] focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20"
          />

          {options.llm_available ? (
            <label className="mt-4 flex cursor-pointer items-start gap-2.5 rounded-[6px] border border-[#E2E8F0] bg-[#F8FAFC] p-3">
              <input
                type="checkbox"
                checked={form.useLlm}
                onChange={(e) => setForm({ ...form, useLlm: e.target.checked })}
                className="mt-0.5 h-4 w-4 rounded border-[#CBD5E1] text-[#1D4ED8] focus:ring-[#1D4ED8]"
              />
              <span className="text-[13px] text-[#0F172A]">
                <span className="font-medium">{t("form.useLlmTitle")}</span>
                <span className="block text-[12px] text-[#64748B]">
                  {t("form.useLlmHint")}
                </span>
              </span>
            </label>
          ) : null}
        </section>
      ) : null}

      {/* Inline Errors */}
      {allErrors.length > 0 ? (
        <div
          role="alert"
          className="rounded-[8px] border border-[#FECACA] bg-[#FEF2F2] px-4 py-3 text-[13px] text-[#B91C1C]"
        >
          <div className="flex items-start gap-2.5">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.5} />
            <ul className="list-disc space-y-1 pl-4">
              {allErrors.map((err, idx) => (
                <li key={idx}>{err}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}

      {/* Navigation & Submit Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        {mutation.isPending ? (
          <div
            role="status"
            aria-live="polite"
            className="inline-flex items-center gap-2 text-[13px] text-[#475569]"
          >
            <Loader2 className="h-4 w-4 animate-spin text-[#1D4ED8]" strokeWidth={1.5} />
            <span className="tabular-nums">
              {form.useLlm
                ? `${aiMilestone} (${elapsedSeconds}s)`
                : t("form.analyzing", { seconds: elapsedSeconds })}
            </span>
          </div>
        ) : step > 1 ? (
          <button
            type="button"
            onClick={() => {
              setValidationErrors([]);
              setStep((prev) => (prev === 3 ? 2 : 1));
            }}
            className="inline-flex items-center gap-1.5 rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-4 py-2 text-[13px] font-medium text-[#0F172A] hover:bg-[#F1F5F9]"
          >
            <ArrowLeft className="h-3.5 w-3.5" strokeWidth={1.5} />
            <span>{t("form.wizard.back")}</span>
          </button>
        ) : (
          <span className="text-[12px] text-[#64748B]">
            {t("form.sessionNote")}
          </span>
        )}

        {step < 3 ? (
          <button
            type="button"
            onClick={handleNextStep}
            className="inline-flex items-center gap-1.5 rounded-[6px] bg-[#1D4ED8] px-5 py-2.5 text-[14px] font-medium text-[#FFFFFF] transition-colors hover:bg-[#1E40AF]"
          >
            <span>{t("form.wizard.next")}</span>
            <ArrowRight className="h-4 w-4" strokeWidth={1.5} />
          </button>
        ) : (
          <button
            type="submit"
            disabled={mutation.isPending}
            className="inline-flex items-center justify-center rounded-[6px] bg-[#1D4ED8] px-5 py-2.5 text-[14px] font-medium text-[#FFFFFF] transition-colors hover:bg-[#1E40AF] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {mutation.isPending ? t("form.submitting") : t("form.submit")}
          </button>
        )}
      </div>
    </form>
  );
}
