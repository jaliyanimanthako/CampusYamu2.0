import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import {
  deleteMyChat,
  getCareerOutlook,
  getMyChatHistory,
  postChat,
} from "../api/client.ts";
import type {
  CareerStatus,
  ChatSource,
  ChatTurn,
  CourseRow,
  RecommendationReport,
  Usage,
} from "../api/types.ts";
import { isAuthEnabled } from "../auth/supabase.ts";
import { BANDS, courseArea, fmtMinutes, sanitizeDisplayText } from "../utils/course.ts";
import { BackIcon } from "./BrandMark.tsx";

interface CourseDetailViewProps {
  report: RecommendationReport;
  course: CourseRow;
  chatUsage: Usage | null;
  onUpdateChatUsage: (usage: Usage) => void;
  onBack: () => void;
  onToast: (msg: string) => void;
}

interface UiMessage {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  refused?: boolean;
}

const SUGGESTED_QUESTIONS = [
  "What are my chances?",
  "Is there an aptitude test?",
  "How far is it from home?",
  "Research careers for this course",
];

function CutoffChart({ course, z }: { course: CourseRow; z?: number | null }) {
  if (course.predicted_cutoff == null || z == null) {
    return <p className="muted">No cut-off history to chart for this course.</p>;
  }
  const uncertainty = course.uncertainty ?? 0;
  const vals = [
    course.predicted_cutoff - uncertainty,
    course.predicted_cutoff + uncertainty,
    course.latest_cutoff,
    z,
  ].filter((v): v is number => v != null);

  const lo = Math.min(...vals) - 0.25;
  const hi = Math.max(...vals) + 0.25;
  const X = (v: number) => 30 + ((v - lo) / (hi - lo)) * 640;

  const ticks: number[] = [];
  for (let t = Math.ceil(lo * 4) / 4; t <= hi; t += 0.25) {
    ticks.push(t);
  }

  const bandL = X(course.predicted_cutoff - uncertainty);
  const bandR = X(course.predicted_cutoff + uncertainty);
  const youX = X(z);
  const pillX = Math.max(34, Math.min(604, youX - 32));

  return (
    <svg viewBox="0 0 700 150" role="img" aria-label="Your Z-score compared with the estimated cut-off">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={X(t)} x2={X(t)} y1={40} y2={104} stroke="var(--line-soft)" />
          <text
            x={X(t)}
            y={124}
            textAnchor="middle"
            fontSize="10.5"
            fill="var(--faint)"
            fontFamily="inherit"
          >
            {t.toFixed(2)}
          </text>
        </g>
      ))}
      <line x1={30} x2={670} y1={72} y2={72} stroke="var(--line)" />
      <rect x={bandL} width={Math.max(4, bandR - bandL)} y={58} height={28} rx={14} fill="var(--lilac)" />
      <line
        x1={X(course.predicted_cutoff)}
        x2={X(course.predicted_cutoff)}
        y1={56}
        y2={88}
        stroke="var(--lav)"
        strokeWidth={2.5}
        strokeLinecap="round"
      />
      {course.latest_cutoff != null && (
        <>
          <circle
            cx={X(course.latest_cutoff)}
            cy={72}
            r={5.5}
            fill="var(--surface)"
            stroke="var(--ink)"
            strokeWidth={1.5}
          />
          <text x={X(course.latest_cutoff)} y={102} textAnchor="middle" fontSize="11" fill="var(--muted)">
            Last year
          </text>
        </>
      )}
      <text
        x={X(course.predicted_cutoff)}
        y={143}
        textAnchor="middle"
        fontSize="11"
        fontWeight={600}
        fill="var(--blue-ink)"
      >
        Estimate {course.predicted_cutoff.toFixed(3)} ± {uncertainty.toFixed(3)}
      </text>
      <g>
        <line x1={youX} x2={youX} y1={24} y2={100} stroke="var(--blue)" strokeWidth={2} strokeLinecap="round" />
        <rect x={pillX} y={2} width={64} height={24} rx={12} fill="var(--blue)" />
        <text x={pillX + 32} y={18} textAnchor="middle" fontSize="11.5" fill="#fff" fontWeight={700}>
          You {z.toFixed(2)}
        </text>
      </g>
    </svg>
  );
}

function AnswerWithCitations({ text }: { text: string }) {
  const parts = text.split(/(\[[A-Z]\d*\])/g);
  return (
    <div className="text">
      {parts.map((part, i) => {
        const match = /^\[([A-Z]\d*)\]$/.exec(part);
        if (match) {
          return (
            <span key={i} className="cite">
              {match[1]}
            </span>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </div>
  );
}

export function CourseDetailView({
  report,
  course,
  chatUsage,
  onUpdateChatUsage,
  onBack,
  onToast,
}: CourseDetailViewProps) {
  const authOn = isAuthEnabled();
  const queryClient = useQueryClient();
  const [localMessages, setLocalMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [career, setCareer] = useState<CareerStatus | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);

  const area = courseArea(course.course_name);
  const bandLabel = BANDS.find((b) => b.id === course.band)?.label ?? course.band;
  const block = report.course_details?.[course.course_code]?.blocks?.[course.details_block ?? 0];
  const z = report.profile.z_score;

  const { data: savedHistory, isLoading: isLoadingHistory } = useQuery({
    queryKey: ["chatHistory", course.uni_code],
    queryFn: async () => {
      try {
        const hist = await getMyChatHistory(course.uni_code);
        return hist.messages.map<UiMessage>((m) => ({
          role: m.role,
          content: m.content,
          sources: m.sources,
        }));
      } catch {
        return [] as UiMessage[];
      }
    },
    enabled: authOn,
    staleTime: 30_000,
  });

  const messages = authOn ? (savedHistory ?? []) : localMessages;
  const showHistoryLoading = authOn && isLoadingHistory;

  useEffect(() => {
    let active = true;
    setLocalMessages([]);
    getCareerOutlook(course.course_name)
      .then((res) => {
        if (active) setCareer(res);
      })
      .catch(() => {});

    return () => {
      active = false;
    };
  }, [course.uni_code, course.course_name]);

  useEffect(() => {
    if (career?.job?.state !== "running") return;
    let active = true;
    const interval = window.setInterval(() => {
      getCareerOutlook(course.course_name)
        .then((next) => {
          if (active) setCareer(next);
        })
        .catch(() => {});
    }, 2200);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [career?.job?.state, course.course_name]);

  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, busy]);

  const askQuestion = async (questionText: string) => {
    const q = questionText.trim();
    if (!q || busy) return;
    setBusy(true);
    setInput("");

    const priorHistory: ChatTurn[] = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    const appendMessage = (msg: UiMessage) => {
      if (authOn) {
        queryClient.setQueryData<UiMessage[]>(
          ["chatHistory", course.uni_code],
          (prev = []) => [...prev, msg],
        );
      } else {
        setLocalMessages((prev) => [...prev, msg]);
      }
    };

    appendMessage({ role: "user", content: q });

    try {
      const res = await postChat(
        authOn
          ? { uni_code: course.uni_code, question: q, student: {}, history: [] }
          : {
              question: q,
              course: course as unknown as { course_code: string; course_name: string },
              student: {
                stream: report.profile.stream,
                al_results: report.profile.al_results,
                z_score: report.profile.z_score,
                admission_district: report.profile.admission_district,
                home: report.origin?.ds_division ?? report.profile.home,
              },
              history: priorHistory,
            },
      );
      appendMessage({
        role: "assistant",
        content: res.answer,
        sources: res.sources,
        refused: res.status === "out_of_scope",
      });
      if (res.usage) onUpdateChatUsage(res.usage);
      if (res.career) setCareer(res.career);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong. Try again.";
      appendMessage({ role: "assistant", content: msg, refused: true });
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    void askQuestion(input);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void askQuestion(input);
    }
  };

  const handleClear = async () => {
    if (authOn) {
      await deleteMyChat(course.uni_code).catch(() => {});
      queryClient.setQueryData<UiMessage[]>(["chatHistory", course.uni_code], []);
    } else {
      setLocalMessages([]);
    }
    onToast("Chat cleared");
  };

  const job = career?.job;
  const outlookOverall = career?.outlook?.overall as { label?: string; summary?: string } | undefined;
  const jobStep = typeof job?.step === "number" ? job.step : 0;
  const jobSteps = typeof job?.steps === "number" && job.steps > 0 ? job.steps : 6;
  const ringCirc = 2 * Math.PI * 9;
  const ringProgress = (jobStep + 1) / jobSteps;

  return (
    <>
      <button type="button" className="back" onClick={onBack}>
        <BackIcon /> Back
      </button>

      <section className={`card split detail-hero reveal band-${course.band}`}>
        <div className="side">
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <span className={`chip ${course.band === "strong" ? "blue" : ""}`}>
              {bandLabel} chance
            </span>
            <span className="chip plain">{course.uni_code}</span>
            {course.aptitude_test && <span className="chip ink">Aptitude test</span>}
            {course.same_district && <span className="chip ink">Your district</span>}
          </div>
          <h2>{course.course_name}</h2>
          <div className="muted" style={{ fontSize: 14.5 }}>
            {course.university}
            {course.site ? ` · ${course.site}` : ""}
          </div>
          <div className="facts">
            <div>
              <span className="mono faint">By car</span>
              <b className="num">{fmtMinutes(course.car_min)}</b>
            </div>
            <div>
              <span className="mono faint">By bus</span>
              <b className="num">{fmtMinutes(course.bus_min_est)}</b>
            </div>
            <div>
              <span className="mono faint">Places</span>
              <b className="num">{course.proposed_intake ?? "—"}</b>
            </div>
            <div>
              <span className="mono faint">Years met</span>
              <b className="num">
                {course.years_met ?? "—"}
                <span className="faint"> / {course.years_compared ?? "—"}</span>
              </b>
            </div>
          </div>
        </div>
        <div className="side fig-side">
          <div className="fig">
            <img src={`/figures/area-${area}.webp`} alt="" />
          </div>
        </div>
      </section>

      <div className="detail-grid">
        <div style={{ display: "grid", gap: 18 }}>
          <section className="card panel chart reveal" style={{ ["--i" as string]: 1 }}>
            <div className="panel-head">
              <h3>Your Z-score against the cut-off</h3>
              <span className="mono faint">
                {report.profile.admission_district} ·{" "}
                {((course.forecast_year as string | undefined) || "").replace("_", "/")}
              </span>
            </div>
            <CutoffChart course={course} z={z} />
            {course.reason && (
              <p className="muted" style={{ fontSize: 14, margin: "16px 0 0" }}>
                {sanitizeDisplayText(course.reason)}
              </p>
            )}
          </section>

          {block && (
            <section className="card panel reveal" style={{ ["--i" as string]: 2 }}>
              <div className="panel-head">
                <h3>From the handbook</h3>
                {block.citation && (
                  <span className="chip">{sanitizeDisplayText(block.citation)}</span>
                )}
              </div>
              {block.degree_programmes && block.degree_programmes.length > 0 && (
                <div className="tags" style={{ marginBottom: 14 }}>
                  {block.degree_programmes.map((d) => (
                    <span key={d}>{sanitizeDisplayText(d)}</span>
                  ))}
                </div>
              )}
              {block.text && (
                <div className="md">
                  <ReactMarkdown>{sanitizeDisplayText(block.text)}</ReactMarkdown>
                </div>
              )}
            </section>
          )}
        </div>

        <aside className="card chat reveal" style={{ ["--i" as string]: 1 }}>
          <div className="chat-head">
            <span className="bot-av">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 2.5l2.1 6.4 6.4 2.1-6.4 2.1L12 19.5l-2.1-6.4L3.5 11l6.4-2.1z" />
              </svg>
            </span>
            <div style={{ minWidth: 0 }}>
              <b style={{ fontWeight: 550 }}>Ask about this course</b>
              <div
                className="faint"
                style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
              >
                Answers from the handbook and your results
              </div>
            </div>
            <button
              type="button"
              className="icon-btn"
              title="Clear this chat"
              style={{ marginLeft: "auto" }}
              onClick={handleClear}
            >
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
                <path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />
              </svg>
            </button>
          </div>

          <div className="chat-body" ref={bodyRef}>
            <div className="msg bot">
              <span className="who mono">CampusYamu</span>
              <div className="text">
                Ask me anything about <b>{course.course_name}</b> at {course.university}: entry
                rules, your chances, the journey, or careers.
              </div>
            </div>

            {showHistoryLoading && (
              <div className="chat-loading" aria-live="polite">
                <div className="typing">
                  <i />
                  <i />
                  <i />
                </div>
                <span>Loading previous messages…</span>
              </div>
            )}

            {messages.map((m, idx) =>
              m.role === "user" ? (
                <div key={idx} className="msg user">
                  {m.content}
                </div>
              ) : (
                <div key={idx} className={`msg bot ${m.refused ? "refused" : ""}`}>
                  <span className="who mono">CampusYamu</span>
                  <AnswerWithCitations text={sanitizeDisplayText(m.content)} />
                  {m.sources && m.sources.length > 0 && (
                    <div className="sources">
                      {m.sources.map((src, sIdx) => (
                        <span
                          key={sIdx}
                          className={`chip ${src.kind === "career_outlook" ? "" : "plain"}`}
                        >
                          <b className="mono" style={{ fontSize: 10, letterSpacing: 0 }}>
                            {src.id}
                          </b>{" "}
                          {sanitizeDisplayText(src.citation || src.title || src.kind)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ),
            )}

            {busy && (
              <div className="msg bot">
                <span className="who mono">CampusYamu</span>
                <div className="typing">
                  <i />
                  <i />
                  <i />
                </div>
              </div>
            )}
          </div>

          {job?.state === "running" && (
            <div className="research">
              <svg width="22" height="22" viewBox="0 0 24 24">
                <circle cx={12} cy={12} r={9} fill="none" stroke="var(--lilac)" strokeWidth={2.5} />
                <circle
                  cx={12}
                  cy={12}
                  r={9}
                  fill="none"
                  stroke="var(--blue)"
                  strokeWidth={2.5}
                  strokeLinecap="round"
                  strokeDasharray={ringCirc}
                  strokeDashoffset={ringCirc * (1 - ringProgress)}
                  transform="rotate(-90 12 12)"
                  style={{ transition: "stroke-dashoffset .6s var(--ease)" }}
                />
              </svg>
              <div>
                <b style={{ fontWeight: 550 }}>Researching careers</b>
                <div style={{ fontSize: 12.5 }}>{job.message}…</div>
              </div>
            </div>
          )}

          {job?.state === "done" && outlookOverall && (
            <div className="research">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M5 12.5l4.5 4.5L19 7.5" />
              </svg>
              <div>
                <b style={{ fontWeight: 550 }}>Career research ready</b>{" "}
                {outlookOverall.label && (
                  <span className="chip" style={{ marginLeft: 4 }}>
                    {outlookOverall.label}
                  </span>
                )}
                {outlookOverall.summary && (
                  <div style={{ fontSize: 12.5, marginTop: 4 }}>{outlookOverall.summary}</div>
                )}
              </div>
            </div>
          )}

          {messages.length === 0 && !busy && !showHistoryLoading && (
            <div className="suggest">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button key={q} type="button" onClick={() => void askQuestion(q)}>
                  {q}
                </button>
              ))}
            </div>
          )}

          <form className="composer" onSubmit={handleSubmit}>
            <textarea
              rows={1}
              maxLength={1000}
              placeholder="Ask a question…"
              aria-label="Your question"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <button type="submit" className="btn" aria-label="Send" disabled={busy || !input.trim()}>
              <svg
                width="17"
                height="17"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M5 12h13M13 6l6 6-6 6" />
              </svg>
            </button>
          </form>
          <div className="composer-meta">
            <span>Answers cite their sources</span>
            <span className="num">
              {chatUsage && chatUsage.limit > 0 ? `${chatUsage.used}/${chatUsage.limit} today` : ""}
            </span>
          </div>
        </aside>
      </div>
    </>
  );
}
