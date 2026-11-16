import { useState } from "react";
import { ArrowDown, BookOpen, Check, Compass, Scale, SlidersHorizontal, Sparkles } from "lucide-react";
import type { RecommendationRequest } from "../api/types.ts";
import { useTranslation } from "../i18n/index.tsx";

interface HeroHomeProps {
  onQuickExplore: (preset: RecommendationRequest) => void;
  isExploring: boolean;
}

const SAMPLE_PRESETS: Array<{ labelKey: "hero.preset1" | "hero.preset2" | "hero.preset3"; request: RecommendationRequest }> = [
  {
    labelKey: "hero.preset1",
    request: {
      stream: "Physical Science",
      al: [
        { subject: "Combined Mathematics", grade: "A" },
        { subject: "Physics", grade: "B" },
        { subject: "Chemistry", grade: "C" },
      ],
      ol: [
        { subject: "Mathematics", grade: "A" },
        { subject: "Science", grade: "B" },
        { subject: "English", grade: "B" },
      ],
      cgt: 55,
      z_score: 1.56,
      admission_district: "Kandy",
      ds_division: "Gangawata Korale",
      preferences: "software engineering, data science",
      use_llm: false,
    },
  },
  {
    labelKey: "hero.preset2",
    request: {
      stream: "Biological Science",
      al: [
        { subject: "Biology", grade: "A" },
        { subject: "Chemistry", grade: "B" },
        { subject: "Physics", grade: "B" },
      ],
      ol: [
        { subject: "Mathematics", grade: "A" },
        { subject: "Science", grade: "A" },
        { subject: "English", grade: "B" },
      ],
      cgt: 58,
      z_score: 1.42,
      admission_district: "Gampaha",
      ds_division: "Gampaha",
      preferences: "medicine, biotechnology, health",
      use_llm: false,
    },
  },
  {
    labelKey: "hero.preset3",
    request: {
      stream: "Commerce",
      al: [
        { subject: "Accounting", grade: "A" },
        { subject: "Business Studies", grade: "A" },
        { subject: "Economics", grade: "B" },
      ],
      ol: [
        { subject: "Mathematics", grade: "A" },
        { subject: "English", grade: "A" },
      ],
      cgt: 62,
      z_score: 1.65,
      admission_district: "Colombo",
      ds_division: "Colombo",
      preferences: "finance, management, analytics",
      use_llm: false,
    },
  },
];

export function HeroHome({ onQuickExplore, isExploring }: HeroHomeProps) {
  const { t } = useTranslation();
  const [whatIfZ, setWhatIfZ] = useState(1.55);

  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const stats = [
    {
      value: t("hero.stat.programmes.value"),
      label: t("hero.stat.programmes.label"),
      accent: true,
    },
    {
      value: t("hero.stat.districts.value"),
      label: t("hero.stat.districts.label"),
      accent: false,
    },
    {
      value: t("hero.stat.bands.value"),
      label: t("hero.stat.bands.label"),
      accent: false,
    },
    {
      value: t("hero.stat.languages.value"),
      label: t("hero.stat.languages.label"),
      accent: false,
    },
  ];

  const features = [
    {
      icon: Scale,
      title: t("hero.feat1.title"),
      desc: t("hero.feat1.desc"),
    },
    {
      icon: Compass,
      title: t("hero.feat2.title"),
      desc: t("hero.feat2.desc"),
    },
    {
      icon: BookOpen,
      title: t("hero.feat3.title"),
      desc: t("hero.feat3.desc"),
    },
  ];

  const steps = [
    {
      num: "01",
      title: t("hero.step1.title"),
      desc: t("hero.step1.desc"),
    },
    {
      num: "02",
      title: t("hero.step2.title"),
      desc: t("hero.step2.desc"),
    },
    {
      num: "03",
      title: t("hero.step3.title"),
      desc: t("hero.step3.desc"),
    },
  ];

  return (
    <div className="space-y-8">
      {/* Hero Banner */}
      <section className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-6 sm:p-8">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12 lg:items-center">
          {/* Left: Headline, CTAs & 1-Click Presets */}
          <div className="lg:col-span-7">
            <span className="inline-flex items-center gap-2 rounded-full border border-[#BFDBFE] bg-[#EFF6FF] px-3 py-1 text-[12px] font-medium text-[#1D4ED8]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#1D4ED8]" aria-hidden="true" />
              {t("hero.badge")}
            </span>

            <h1 className="mt-4 text-[26px] font-bold leading-tight tracking-[-0.025em] text-[#0F172A] sm:text-[34px]">
              {t("hero.title")}
            </h1>

            <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-[#475569]">
              {t("hero.subtitle")}
            </p>

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => scrollTo("intake-form")}
                className="inline-flex items-center gap-2 rounded-[6px] bg-[#1D4ED8] px-5 py-2.5 text-[14px] font-medium text-[#FFFFFF] transition-colors hover:bg-[#1E40AF] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8] focus:ring-offset-2"
              >
                <span>{t("hero.ctaPrimary")}</span>
                <ArrowDown className="h-4 w-4" strokeWidth={1.5} />
              </button>

              <button
                type="button"
                onClick={() => scrollTo("how-it-works")}
                className="inline-flex items-center rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-4 py-2.5 text-[14px] font-medium text-[#0F172A] transition-colors hover:border-[#CBD5E1] hover:bg-[#F1F5F9] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8] focus:ring-offset-2"
              >
                {t("hero.ctaSecondary")}
              </button>
            </div>

            {/* 1-Click Sample Student Presets */}
            <div className="mt-6 border-t border-[#E2E8F0] pt-4">
              <span className="flex items-center gap-1.5 text-[12px] font-semibold text-[#475569]">
                <Sparkles className="h-3.5 w-3.5 text-[#1D4ED8]" strokeWidth={1.5} />
                {t("hero.presetsTitle")}
              </span>
              <div className="mt-2.5 flex flex-wrap gap-2">
                {SAMPLE_PRESETS.map((preset) => (
                  <button
                    key={preset.labelKey}
                    type="button"
                    disabled={isExploring}
                    onClick={() => onQuickExplore(preset.request)}
                    className="rounded-full border border-[#BFDBFE] bg-[#EFF6FF] px-3 py-1 text-[12px] font-medium text-[#1D4ED8] transition-colors hover:bg-[#F1F5F9] disabled:opacity-50"
                  >
                    {t(preset.labelKey)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Right: At-a-Glance Metrics & Pre-Results What-If Slider */}
          <div className="space-y-3 lg:col-span-5">
            <div className="grid grid-cols-2 gap-3">
              {stats.map((stat) => (
                <div
                  key={stat.label}
                  className={
                    stat.accent
                      ? "rounded-[8px] border border-[#BFDBFE] bg-[#EFF6FF] p-3.5"
                      : "rounded-[8px] border border-[#E2E8F0] bg-[#F8FAFC] p-3.5"
                  }
                >
                  <span
                    className={
                      stat.accent
                        ? "tabular-nums block text-[20px] font-bold tracking-[-0.02em] text-[#1D4ED8]"
                        : "tabular-nums block text-[18px] font-bold tracking-[-0.02em] text-[#0F172A]"
                    }
                  >
                    {stat.value}
                  </span>
                  <span className="mt-0.5 block text-[12px] text-[#475569]">
                    {stat.label}
                  </span>
                </div>
              ))}
            </div>

            {/* Pre-Results What-If Z-Score Explorer (Ages 16-18) */}
            <div className="rounded-[8px] border border-[#BFDBFE] bg-[#EFF6FF] p-4">
              <div className="flex items-center justify-between gap-2">
                <h2 className="flex items-center gap-1.5 text-[13px] font-semibold text-[#0F172A]">
                  <SlidersHorizontal className="h-3.5 w-3.5 text-[#1D4ED8]" strokeWidth={1.5} />
                  {t("hero.whatIfTitle")}
                </h2>
                <span className="tabular-nums rounded-full border border-[#BFDBFE] bg-[#FFFFFF] px-2.5 py-0.5 text-[12px] font-bold text-[#1D4ED8]">
                  {whatIfZ.toFixed(2)}
                </span>
              </div>
              <p className="mt-1 text-[12px] text-[#475569]">
                {t("hero.whatIfHint")}
              </p>
              <input
                type="range"
                min={0.5}
                max={2.5}
                step={0.05}
                value={whatIfZ}
                aria-label={t("hero.whatIfTitle")}
                onChange={(e) => setWhatIfZ(Number(e.target.value))}
                className="mt-2.5 w-full accent-[#1D4ED8]"
              />
              <button
                type="button"
                disabled={isExploring}
                onClick={() =>
                  onQuickExplore({
                    ...SAMPLE_PRESETS[0].request,
                    z_score: whatIfZ,
                  })
                }
                className="mt-2.5 w-full rounded-[6px] border border-[#BFDBFE] bg-[#FFFFFF] px-3 py-1.5 text-[12px] font-semibold text-[#1D4ED8] hover:bg-[#F8FAFC] disabled:opacity-50"
              >
                {t("hero.whatIfBtn", { z: whatIfZ.toFixed(2) })}
              </button>
            </div>

            <div className="rounded-[8px] border border-[#E2E8F0] bg-[#F8FAFC] p-4">
              <h2 className="text-[13px] font-semibold text-[#0F172A]">
                {t("hero.previewTitle")}
              </h2>
              <ul className="mt-2 space-y-1.5 text-[12px] text-[#475569]">
                {[
                  t("hero.previewItem1"),
                  t("hero.previewItem2"),
                  t("hero.previewItem3"),
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <Check
                      className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#1D4ED8]"
                      strokeWidth={2}
                    />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Highlights */}
      <section aria-labelledby="features-heading" className="space-y-4">
        <h2
          id="features-heading"
          className="text-[18px] font-semibold tracking-[-0.015em] text-[#0F172A]"
        >
          {t("hero.featuresTitle")}
        </h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {features.map((feat) => {
            const Icon = feat.icon;
            return (
              <div
                key={feat.title}
                className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-5"
              >
                <div className="inline-flex h-9 w-9 items-center justify-center rounded-[6px] border border-[#BFDBFE] bg-[#EFF6FF] text-[#1D4ED8]">
                  <Icon className="h-4 w-4" strokeWidth={1.5} />
                </div>
                <h3 className="mt-3.5 text-[15px] font-semibold text-[#0F172A]">
                  {feat.title}
                </h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-[#475569]">
                  {feat.desc}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* How It Works (3-step strip) */}
      <section
        id="how-it-works"
        aria-labelledby="how-heading"
        className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-5 sm:p-6"
      >
        <h2
          id="how-heading"
          className="text-[18px] font-semibold tracking-[-0.015em] text-[#0F172A]"
        >
          {t("hero.howTitle")}
        </h2>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          {steps.map((step) => (
            <div
              key={step.num}
              className="rounded-[6px] border border-[#E2E8F0] bg-[#F8FAFC] p-4"
            >
              <span className="tabular-nums inline-block rounded bg-[#EFF6FF] px-2 py-0.5 text-[12px] font-semibold text-[#1D4ED8]">
                {step.num}
              </span>
              <h3 className="mt-2.5 text-[15px] font-semibold text-[#0F172A]">
                {step.title}
              </h3>
              <p className="mt-1 text-[13px] leading-relaxed text-[#475569]">
                {step.desc}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
