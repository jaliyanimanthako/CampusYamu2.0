import { useEffect, useMemo, useRef, useState } from "react";
import type { BandKey, CourseRow, RecommendationReport } from "../api/types.ts";
import { abbrevSubject, BANDS, courseArea, fmtMinutes, pad2 } from "../utils/course.ts";
import { ArrowRightIcon } from "./BrandMark.tsx";

interface ResultsViewProps {
  report: RecommendationReport;
  onEditResults: () => void;
  onOpenRankings: () => void;
  onOpenCourse: (uniCode: string) => void;
}

export function ResultsView({
  report,
  onEditResults,
  onOpenRankings,
  onOpenCourse,
}: ResultsViewProps) {
  const firstNonEmptyBand = useMemo(
    () => BANDS.find((b) => (report.bands[b.id]?.length ?? 0) > 0)?.id ?? "strong",
    [report],
  );
  const [band, setBand] = useState<BandKey>(firstNonEmptyBand);
  const [query, setQuery] = useState("");
  const [showAll, setShowAll] = useState(false);

  const tabsRef = useRef<HTMLDivElement>(null);
  const inkRef = useRef<HTMLSpanElement>(null);

  const allRows = useMemo(
    () => BANDS.flatMap((b) => report.bands[b.id] ?? []),
    [report],
  );

  const counts = report.counts ?? {};
  const profile = report.profile;
  const eligible = (counts.can_apply ?? 0) + (counts.with_conditions ?? 0);
  const bandedTotal = BANDS.reduce((sum, b) => sum + (report.bands[b.id]?.length ?? 0), 0) || 1;
  const nearCount = useMemo(
    () => allRows.filter((r) => r.car_min != null && r.car_min <= 45).length,
    [allRows],
  );
  const intakeLabel =
    (report.bands.strong?.[0]?.forecast_year as string | undefined)?.replace("_", "/") ||
    "2025/2026";

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
  }, [band, report]);

  const filteredRows: CourseRow[] = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q) {
      return allRows.filter((r) =>
        `${r.course_name} ${r.university} ${r.uni_code}`.toLowerCase().includes(q),
      );
    }
    return report.bands[band] ?? [];
  }, [allRows, band, query, report]);

  const visibleRows = showAll || query.trim() ? filteredRows : filteredRows.slice(0, 12);
  const activeBandMeta = BANDS.find((b) => b.id === band) ?? BANDS[0];

  return (
    <>
      <section className="hero">
        <div>
          <span className="label reveal">{intakeLabel} intake</span>
          <h1 className="reveal" style={{ ["--i" as string]: 1, marginTop: 12 }}>
            <span className="num">{eligible}</span> courses
            <br />
            <span className="accent">you can apply for.</span>
          </h1>
          <div className="slash reveal" style={{ ["--i" as string]: 2 }}>
            <span>{profile.stream}</span>
            <span>
              {profile.al_results.map(([sub, g]) => `${abbrevSubject(sub)} ${g}`).join(" · ")}
            </span>
            {profile.z_score != null && (
              <span className="accent num">Z {Number(profile.z_score).toFixed(4)}</span>
            )}
            <span>
              {report.origin?.ds_division || profile.home}, {profile.admission_district}
            </span>
          </div>
        </div>
        <div
          className="reveal"
          style={{ ["--i" as string]: 3, display: "flex", gap: 10, flexWrap: "wrap" }}
        >
          <button type="button" className="btn outline" onClick={onEditResults}>
            Edit results
          </button>
          <button type="button" className="btn" onClick={onOpenRankings}>
            Ranked order <ArrowRightIcon />
          </button>
        </div>
      </section>

      <section className="stats">
        <div className="card stat lead reveal" style={{ ["--i" as string]: 1 }}>
          <span className="mono">Strong chance</span>
          <div className="value">
            <span className="num">{counts.band_strong ?? 0}</span>
            <small>of {bandedTotal}</small>
          </div>
        </div>
        <div className="card stat reveal" style={{ ["--i" as string]: 2 }}>
          <span className="mono">Competitive or reach</span>
          <div className="value num">
            {(counts.band_competitive ?? 0) + (counts.band_reach ?? 0)}
          </div>
        </div>
        <div className="card stat reveal" style={{ ["--i" as string]: 3 }}>
          <span className="mono">Within 45 min by car</span>
          <div className="value num">{nearCount}</div>
        </div>
        <div className="card stat warm reveal" style={{ ["--i" as string]: 4 }}>
          <span className="mono">With conditions</span>
          <div className="value num">{counts.with_conditions ?? 0}</div>
        </div>
      </section>

      <section className="card dist reveal">
        <div className="dist-head">
          <h3>Chance of admission</h3>
          <span className="faint">
            From past cut-offs in {profile.admission_district}. Not a guarantee.
          </span>
        </div>
        <div className="dist-bar">
          {BANDS.map((b) => {
            const w = ((report.bands[b.id]?.length ?? 0) / bandedTotal) * 100;
            return (
              <i
                key={b.id}
                style={{ width: `${w}%`, background: b.color }}
                title={b.label}
              />
            );
          })}
        </div>
        <div className="legend">
          {BANDS.map((b) => (
            <span key={b.id}>
              <i style={{ background: b.color }} />
              {b.label} <b className="num">{report.bands[b.id]?.length ?? 0}</b>
            </span>
          ))}
        </div>
      </section>

      <section>
        <div className="section-head reveal">
          <h2>
            All <span className="accent">courses.</span>
          </h2>
          <label className="search">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            <input
              className="input"
              placeholder="Search course or university"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        </div>

        <div className="tabs" ref={tabsRef}>
          <span className="ink" ref={inkRef} />
          {BANDS.map((b) => (
            <button
              key={b.id}
              type="button"
              className={band === b.id ? "active" : ""}
              onClick={() => {
                setBand(b.id);
                setShowAll(false);
                setQuery("");
              }}
            >
              {b.label}
              <span className="n">{report.bands[b.id]?.length ?? 0}</span>
            </button>
          ))}
        </div>

        <p className="faint" style={{ margin: "-8px 0 20px" }}>
          {activeBandMeta.desc}. Nearest first.
        </p>

        {visibleRows.length === 0 ? (
          <div className="card empty">No courses here.</div>
        ) : (
          <div className="courses">
            {visibleRows.map((row, idx) => {
              const m = row.expected_margin;
              const widthScale = m == null ? 0 : Math.min(1, Math.abs(m));
              const bandLabel = BANDS.find((b) => b.id === row.band)?.label;
              const tags = [
                bandLabel,
                row.group === "with_conditions" ? "Conditions" : "Can apply",
                row.aptitude_test ? "Aptitude test" : null,
                row.proposed_intake ? `${row.proposed_intake} places` : null,
              ].filter((t): t is string => Boolean(t));

              return (
                <article
                  key={row.uni_code}
                  className={`card course band-${row.band} reveal`}
                  style={{ ["--i" as string]: idx % 6 }}
                  tabIndex={0}
                  role="link"
                  aria-label={`${row.course_name}, ${row.university}`}
                  onClick={() => onOpenCourse(row.uni_code)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") onOpenCourse(row.uni_code);
                  }}
                >
                  <div className="fig">
                    <img
                      src={`/figures/area-${courseArea(row.course_name)}.webp`}
                      alt=""
                      loading="lazy"
                    />
                  </div>
                  <div className="body">
                    <div className="meta mono">
                      <span>
                        {row.uni_code} · {fmtMinutes(row.car_min)}
                      </span>
                      <span className="idx">{pad2(idx + 1)}</span>
                    </div>
                    <h3>{row.course_name}</h3>
                    <div className="uni">{row.university}</div>
                    {m != null ? (
                      <div className="margin">
                        <div className="margin-track">
                          <span className="zero" />
                          <span
                            className={`fill ${m < 0 ? "neg" : ""}`}
                            style={{
                              ...(m < 0 ? { right: "50%" } : { left: "50%" }),
                              transform: `scaleX(${widthScale})`,
                            }}
                          />
                        </div>
                        <div className="margin-row">
                          <span>Cut-off {row.predicted_cutoff?.toFixed(4) ?? "—"}</span>
                          <span>
                            You <b className="num">{m >= 0 ? "+" : ""}{m.toFixed(3)}</b>
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div className="margin-row">
                        <span>{row.zscore_note || "No cut-off history to compare"}</span>
                      </div>
                    )}
                    <div className="tags">
                      {tags.map((t) => (
                        <span key={t}>{t}</span>
                      ))}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}

        {filteredRows.length > visibleRows.length && (
          <div style={{ textAlign: "center", marginTop: 24 }}>
            <button
              type="button"
              className="btn outline"
              onClick={() => setShowAll(true)}
            >
              Show all {filteredRows.length}
            </button>
          </div>
        )}
      </section>

      {report.notes && report.notes.length > 0 && (
        <footer className="faint" style={{ marginTop: 56, display: "grid", gap: 4 }}>
          {report.notes.map((n, i) => (
            <div key={i}>{n}</div>
          ))}
        </footer>
      )}
    </>
  );
}
