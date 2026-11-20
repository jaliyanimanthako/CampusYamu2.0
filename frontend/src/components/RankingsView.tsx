import { useEffect, useRef, useState } from "react";
import type { RecommendationReport } from "../api/types.ts";
import { BANDS, fmtMinutes, pad2, RANKING_MODES, type RankingMode } from "../utils/course.ts";

interface RankingsViewProps {
  report: RecommendationReport;
  onOpenCourse: (uniCode: string) => void;
}

export function RankingsView({ report, onOpenCourse }: RankingsViewProps) {
  const [mode, setMode] = useState<RankingMode>("distance");
  const tabsRef = useRef<HTMLDivElement>(null);
  const inkRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const tabsEl = tabsRef.current;
    const inkEl = inkRef.current;
    if (!tabsEl || !inkEl) return;
    const updateInk = () => {
      const activeBtn = tabsEl.querySelector<HTMLButtonElement>("button.active");
      if (!activeBtn) return;
      inkEl.style.width = `${activeBtn.offsetWidth}px`;
      inkEl.style.transform = `translateX(${activeBtn.offsetLeft}px)`;
    };
    const raf = requestAnimationFrame(updateInk);
    window.addEventListener("resize", updateInk);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", updateInk);
    };
  }, [mode]);

  const fb = report.rankings.distance?.feedback;
  const courseNotes = fb?.course_notes ?? {};
  const suggestions = report.rankings[mode]?.suggestions ?? [];

  return (
    <>
      <section>
        <span className="label reveal">Ranked order</span>
        <h1 className="reveal" style={{ ["--i" as string]: 1, marginTop: 12 }}>
          The order to <span className="accent">list them.</span>
        </h1>
        <p
          className="muted reveal"
          style={{ ["--i" as string]: 2, maxWidth: 620, margin: "16px 0 0", fontSize: 17 }}
        >
          Three ways to order the same courses. <b>Balanced</b> weighs your interests, how
          competitive each course is, and how far it is from home.
        </p>
      </section>

      <div className="rank-layout">
        <div>
          <div className="tabs reveal" ref={tabsRef}>
            <span className="ink" ref={inkRef} />
            {RANKING_MODES.map((r) => (
              <button
                key={r.id}
                type="button"
                className={mode === r.id ? "active" : ""}
                onClick={() => setMode(r.id)}
              >
                {r.label}
              </button>
            ))}
          </div>

          <div className="rank-list">
            {suggestions.slice(0, 10).map((sug, i) => {
              const parts = sug.parts;
              const tot = parts
                ? Math.abs(parts.interest) + Math.abs(parts.cutoff) + Math.abs(parts.distance) || 1
                : 0;
              const bandLabel = BANDS.find((b) => b.id === sug.band)?.label;
              const note = mode === "distance" ? courseNotes[sug.uni_code]?.note : undefined;

              return (
                <article
                  key={`${mode}-${sug.uni_code}`}
                  className={`card rank band-${sug.band} reveal`}
                  style={{ ["--i" as string]: i }}
                  onClick={() => onOpenCourse(sug.uni_code)}
                >
                  <div className="pos num">{pad2(sug.position)}</div>
                  <div>
                    <h3 style={{ fontSize: 17 }}>{sug.course_name}</h3>
                    <div className="tags" style={{ marginTop: 3 }}>
                      <span>{sug.university}</span>
                      <span>{fmtMinutes(sug.car_min)}</span>
                      {bandLabel && <span>{bandLabel}</span>}
                    </div>
                    {note && <div className="note">{note}</div>}
                  </div>
                  {parts ? (
                    <div className="parts">
                      <div className="parts-bar">
                        <i
                          style={{
                            width: `${(Math.abs(parts.interest) / tot) * 100}%`,
                            background: "var(--blue)",
                          }}
                          title={`Interest ${parts.interest}`}
                        />
                        <i
                          style={{
                            width: `${(Math.abs(parts.cutoff) / tot) * 100}%`,
                            background: "var(--lav)",
                          }}
                          title={`Demand ${parts.cutoff}`}
                        />
                        <i
                          style={{
                            width: `${(Math.abs(parts.distance) / tot) * 100}%`,
                            background: "var(--mustard)",
                          }}
                          title={`Distance ${parts.distance}`}
                        />
                      </div>
                      <div className="parts-legend">
                        <span>Interest</span>
                        <span>Demand</span>
                        <span>Distance</span>
                      </div>
                    </div>
                  ) : (
                    <div className="parts">
                      <div className="margin-row">
                        <span>Last cut-off</span>
                        <b className="num">{sug.latest_cutoff?.toFixed(4) ?? "—"}</b>
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </div>

        <aside className="card advice reveal" style={{ ["--i" as string]: 2 }}>
          <span className="chip">Advice</span>
          <p>{fb?.summary || "Select a course to explore cut-offs, handbook details, and career outlook."}</p>
          {(fb?.priorities ?? []).map((pr, idx) => (
            <div key={idx} className="prio">
              <b>{pr.label ? pr.label[0].toUpperCase() + pr.label.slice(1) : "Priority"}</b>
              {pr.advice}
            </div>
          ))}
        </aside>
      </div>
    </>
  );
}
