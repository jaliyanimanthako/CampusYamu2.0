import { useEffect, useRef, useState } from "react";
import { isAuthEnabled } from "../auth/supabase.ts";
import { LANGS, useMockupI18n } from "../i18n/mockupI18n.tsx";
import { ThemeToggleButton } from "../theme/appTheme.tsx";
import { pad2 } from "../utils/course.ts";
import { ArrowRightIcon, BrandMark } from "./BrandMark.tsx";
import { LangMenu } from "./LangMenu.tsx";

interface HomeViewProps {
  onStart: () => void;
}

const LANDING_STATS = [126, 261, 20, 25, 6, 3] as const;
const AREA_IDS = ["engineering", "medicine", "it", "management", "arts", "science"] as const;
const STEP_FIGS = ["signin", "analysing", "area-engineering", "empty-chats"] as const;

const SparkIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 2.5l2.1 6.4 6.4 2.1-6.4 2.1L12 19.5l-2.1-6.4L3.5 11l6.4-2.1z" />
  </svg>
);

const CheckIcon = () => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </svg>
);

export function HomeView({ onStart }: HomeViewProps) {
  const { t, tRaw } = useMockupI18n();
  const authOn = isAuthEnabled();

  const [activeStep, setActiveStep] = useState(0);
  const [stepProgress, setStepProgress] = useState<number[]>([6, 0, 0, 0]);
  const [activeArea, setActiveArea] = useState<string>(AREA_IDS[0]);
  const [statCounts, setStatCounts] = useState<number[]>(() => LANDING_STATS.map(() => 0));

  const howRef = useRef<HTMLElement>(null);
  const bentoRef = useRef<HTMLDivElement>(null);

  const steps = tRaw<[string, string][]>("l.steps");
  const areas = tRaw<Record<string, [string, string]>>("l.areas");
  const statsLabels = tRaw<string[]>("l.stats");
  const trustItems = tRaw<string[]>("l.trust");
  const promises = tRaw<[string, string][]>("l.promises");
  const faqItems = tRaw<[string, string][]>("l.faq");
  const bands = tRaw<Record<string, [string, string]>>("bands");

  const pairHeadline = (key: string) => {
    const [plain, accent] = tRaw<[string, string]>(key);
    return (
      <>
        {plain} <span className="accent">{accent}</span>
      </>
    );
  };

  useEffect(() => {
    const onScroll = () => {
      const el = howRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const total = Math.max(1, r.height - window.innerHeight);
      const x = Math.min(1, Math.max(0, -r.top / total)) * steps.length;
      const n = Math.min(steps.length - 1, Math.floor(x));
      setActiveStep(n);
      setStepProgress(
        steps.map((_, i) =>
          i < n ? 100 : i === n ? Math.max(6, Math.min(1, x - n) * 100) : 0,
        ),
      );
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    onScroll();
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [steps.length]);

  useEffect(() => {
    const el = bentoRef.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const obs = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        obs.disconnect();
        if (reduced) {
          setStatCounts([...LANDING_STATS]);
          return;
        }
        const t0 = performance.now();
        const dur = 1100;
        const tick = (now: number) => {
          const p = Math.min(1, (now - t0) / dur);
          const eased = 1 - Math.pow(1 - p, 4);
          setStatCounts(LANDING_STATS.map((target) => Math.round(target * eased)));
          if (p < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      },
      { threshold: 0.35 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const scrollToSection = (id: string) => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document
      .getElementById(id)
      ?.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  };

  return (
    <div className="landing view-enter">
      <div className="wrap">
        <header className="topbar">
          <div className="nav-inner">
            <BrandMark href="#/home" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} />
            <nav className="nav">
              <button type="button" onClick={() => scrollToSection("l-how")}>
                {t("l.nav.how")}
              </button>
              <button type="button" onClick={() => scrollToSection("l-areas")}>
                {t("l.nav.areas")}
              </button>
              <button type="button" onClick={() => scrollToSection("l-faq")}>
                {t("l.nav.faq")}
              </button>
            </nav>
            <div className="nav-right">
              <ThemeToggleButton />
              <LangMenu />
              <button type="button" className="btn sm" onClick={onStart}>
                {authOn ? t("signin.btn") : t("l.start")}
              </button>
            </div>
          </div>
        </header>

        <section className="l-hero">
          <div className="l-hero-text">
            <span className="l-kicker reveal">
              <SparkIcon />
              {t("l.kicker")}
            </span>
            <h1 className="reveal" style={{ ["--i" as string]: 1 }}>
              {t("l.h1a")}
              <br />
              <span className="accent">{t("l.h1b")}</span>
            </h1>
            <p className="l-sub reveal" style={{ ["--i" as string]: 2 }}>
              {t("l.sub")}
            </p>
            <div className="l-cta reveal" style={{ ["--i" as string]: 3 }}>
              <button type="button" className="btn" onClick={onStart}>
                {t("l.start")} <ArrowRightIcon />
              </button>
              <button
                type="button"
                className="btn outline"
                onClick={() => scrollToSection("l-how")}
              >
                {t("l.how")}
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M12 5v14M6 13l6 6 6-6" />
                </svg>
              </button>
            </div>
            <ul className="l-trust reveal" style={{ ["--i" as string]: 4 }}>
              {trustItems.map((item) => (
                <li key={item}>
                  <CheckIcon />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="l-hero-art reveal" style={{ ["--i" as string]: 2 }}>
            <div className="fig">
              <img src="/figures/signin.webp" alt="" />
            </div>
            <span className="float f1">
              <span className="chip blue">
                {t("chance", { band: bands.strong?.[0] ?? "Strong" })}
              </span>
            </span>
            <span className="float f2">
              <b className="num">Z 1.5600</b>
            </span>
            <span className="float f3">
              <SparkIcon />
              <span>{t("min", { n: 19 })}</span>
            </span>
          </div>
        </section>
      </div>

      <section
        className="l-how"
        id="l-how"
        ref={howRef}
        style={{ ["--n" as string]: steps.length }}
      >
        <div className="l-how-pin">
          <div className="wrap">
            <span className="label">{t("l.nav.how")}</span>
            <h2>{pairHeadline("l.howH")}</h2>
            <div className="l-how-grid">
              <div className="l-how-visual">
                <div className="card l-stage">
                  <div className="l-stage-figs">
                    {STEP_FIGS.map((figName, i) => (
                      <div key={figName} className={`l-stage-fig ${i === activeStep ? "on" : ""}`}>
                        <div className="fig">
                          <img src={`/figures/${figName}.webp`} alt="" />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="l-progress">
                    {steps.map((_, i) => (
                      <i key={i} className={i < activeStep ? "done" : i === activeStep ? "on" : ""}>
                        <b style={{ width: `${stepProgress[i] ?? 0}%` }} />
                      </i>
                    ))}
                  </div>
                </div>
              </div>
              <div className="l-steps">
                {steps.map(([title, desc], i) => (
                  <article
                    key={title}
                    className={`l-step ${i === activeStep ? "on" : i < activeStep ? "past" : ""}`}
                    aria-hidden={i !== activeStep}
                  >
                    <span className="l-step-n">
                      <span className="rule" />
                      {t("step", { n: pad2(i + 1) })}
                    </span>
                    <h3>{title}</h3>
                    <p>{desc}</p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="l-stats">
        <div className="wrap">
          <h2 className="reveal">{pairHeadline("l.statsH")}</h2>
          <div className="l-bento" ref={bentoRef}>
            {LANDING_STATS.map((_, i) => (
              <div
                key={i}
                className={`card l-tile t${i} reveal`}
                style={{ ["--i" as string]: i }}
              >
                <span className="dash" />
                <b className="num">{statCounts[i]}</b>
                <span>{statsLabels[i]}</span>
                {i === 5 && (
                  <span className="l-langs">
                    {LANGS.map((l) => (
                      <span key={l.id} lang={l.id}>
                        {l.name}
                      </span>
                    ))}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="l-areas" id="l-areas">
        <div className="wrap">
          <span className="label reveal">{t("l.nav.areas")}</span>
          <h2 className="reveal" style={{ ["--i" as string]: 1 }}>
            {pairHeadline("l.areasH")}
          </h2>
          <div className="l-area-row reveal" style={{ ["--i" as string]: 2 }}>
            {AREA_IDS.map((id) => (
              <button
                key={id}
                type="button"
                className={`l-area ${activeArea === id ? "on" : ""}`}
                onMouseEnter={() => setActiveArea(id)}
                onFocus={() => setActiveArea(id)}
                onClick={() => setActiveArea(id)}
              >
                <div className="fig">
                  <img src={`/figures/area-${id}.webp`} alt="" loading="lazy" />
                </div>
                <span className="l-area-text">
                  <b>{areas[id]?.[0]}</b>
                  <span>{areas[id]?.[1]}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="l-chat">
        <div className="wrap l-chat-grid">
          <div>
            <span className="label reveal">{t("l.chatLabel")}</span>
            <h2 className="reveal" style={{ ["--i" as string]: 1 }}>
              {pairHeadline("l.chatH")}
            </h2>
            <p className="l-sub reveal" style={{ ["--i" as string]: 2 }}>
              {t("l.chatP")}
            </p>
            <ul className="l-promises">
              {promises.map(([title, desc], i) => (
                <li key={title} className="reveal" style={{ ["--i" as string]: i + 3 }}>
                  <span className={`glyph g-${["si", "ta", "en"][i]}`}>
                    {i === 0 ? (
                      <CheckIcon />
                    ) : i === 1 ? (
                      <SparkIcon />
                    ) : (
                      <svg
                        width="18"
                        height="18"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.7"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.4A8 8 0 1 1 21 12z" />
                      </svg>
                    )}
                  </span>
                  <div>
                    <b>{title}</b>
                    <span>{desc}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <div className="card l-chat-demo reveal" style={{ ["--i" as string]: 2 }}>
            <div className="chat-head">
              <span className="bot-av">
                <SparkIcon />
              </span>
              <div>
                <b style={{ fontWeight: 600 }}>{t("chat.title")}</b>
                <div className="faint">{t("chat.sub")}</div>
              </div>
            </div>
            <div className="l-chat-body">
              <div className="msg user">{t("l.demoQ")}</div>
              <div className="msg bot">
                <span className="who mono" lang="en">
                  CampusYamu
                </span>
                <div className="text" lang="en">
                  Yes. Architecture needs a practical aptitude test before selection{" "}
                  <span className="cite">S1</span>. Your Z-score is 0.08 above this year&apos;s
                  estimated cut-off for your district <span className="cite">S2</span>.
                </div>
                <div className="sources" lang="en">
                  <span className="chip plain">
                    <b className="mono">S1</b> Handbook · Architecture
                  </span>
                  <span className="chip">
                    <b className="mono">S2</b> Your saved search
                  </span>
                </div>
                {t("enOnly") && (
                  <div className="faint" style={{ marginTop: 8 }}>
                    {t("enOnly")}
                  </div>
                )}
              </div>
            </div>
            <div className="composer">
              <textarea
                rows={1}
                disabled
                placeholder={t("ask.ph")}
                aria-label={t("ask.aria")}
              />
              <span className="btn" aria-hidden="true">
                <ArrowRightIcon />
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="l-faq" id="l-faq">
        <div className="wrap">
          <h2 className="reveal">{pairHeadline("l.faqH")}</h2>
          <div className="l-faq-list">
            {faqItems.map(([q, a], i) => (
              <details
                key={q}
                className="reveal"
                style={{ ["--i" as string]: i }}
                open={i === 0}
              >
                <summary>
                  {q}
                  <span className="pm" aria-hidden="true" />
                </summary>
                <p>{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <div className="wrap">
        <section className="l-final reveal">
          <div>
            <h2>{t("l.ctaH")}</h2>
            <p>{t("l.ctaP")}</p>
          </div>
          <button type="button" className="btn mustard" onClick={onStart}>
            {t("l.start")} <ArrowRightIcon />
          </button>
        </section>
        <footer className="l-foot">
          <BrandMark href="#/home" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} />
          <span className="faint">{t("l.foot")}</span>
        </footer>
      </div>
    </div>
  );
}
