import { useEffect, useMemo, useRef, useState } from "react";
import type { ProgressEvent, ProgressStep } from "../api/types.ts";
import { ANALYSING_AGENTS, pad2 } from "../utils/course.ts";
import { FigureImg } from "./BrandMark.tsx";

interface AnalysingViewProps {
  /** The results have arrived. */
  isDone: boolean;
  /** Live steps from POST /v1/recommendations/stream, in arrival order (empty if the server can't stream). */
  progress: ProgressEvent[];
  onCompleteAnimation: () => void;
}

type StepState = "pending" | "running" | "done" | "skipped";

/** Index after the next milestone: runs of Z-score "running" ticks are shown as their latest one. */
function nextMilestone(events: ProgressEvent[], from: number): number {
  let i = from + 1;
  const isTick = (e: ProgressEvent | undefined) => e?.step === "zscore" && e.status === "running";
  if (isTick(events[from])) while (i < events.length && isTick(events[i])) i++;
  return i;
}

export function AnalysingView({ isDone, progress, onCompleteAnimation }: AnalysingViewProps) {
  const reduced = useMemo(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches, []);
  // Show the server's steps one by one (at least STEP_MS apart) so a fast run is still readable.
  const [shown, setShown] = useState(0);
  const STEP_MS = reduced ? 40 : 220;
  useEffect(() => {
    if (shown >= progress.length) return;
    const timer = window.setTimeout(() => setShown((n) => nextMilestone(progress, n)), STEP_MS);
    return () => window.clearTimeout(timer);
  }, [shown, progress, STEP_MS]);

  const visible = progress.slice(0, shown);
  const caughtUp = shown >= progress.length;
  const finished = isDone && caughtUp;

  const states = useMemo(() => {
    const map = new Map<ProgressStep, ProgressEvent>();
    for (const e of visible) map.set(e.step, e);
    return map;
  }, [visible]);
  const stateOf = (id: ProgressStep): StepState => {
    if (finished) return states.get(id)?.status === "skipped" ? "skipped" : "done";
    return (states.get(id)?.status as StepState | undefined) ?? "pending";
  };

  // The first step that is neither done nor skipped is "in progress" until the server says otherwise.
  const firstOpen = ANALYSING_AGENTS.find((a) => !["done", "skipped"].includes(stateOf(a.id)));

  // Counter: courses whose rules were checked (126 once eligibility is done), counting up smoothly.
  const eligibility = states.get("eligibility");
  const target = finished || eligibility ? (eligibility?.courses_checked ?? 126) : 0;
  const [count, setCount] = useState(0);
  const countRef = useRef(0);
  useEffect(() => {
    const start = countRef.current;
    if (start === target) return;
    const t0 = performance.now();
    const ms = reduced ? 1 : 600;
    let frame = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / ms);
      const value = Math.round(start + (target - start) * (1 - Math.pow(1 - p, 3)));
      countRef.current = value;
      setCount(value);
      if (p < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, reduced]);

  useEffect(() => {
    if (!finished) return;
    const timer = window.setTimeout(onCompleteAnimation, 450);
    return () => window.clearTimeout(timer);
  }, [finished, onCompleteAnimation]);

  const zscore = states.get("zscore");
  let message: string = firstOpen?.msg ?? ANALYSING_AGENTS[ANALYSING_AGENTS.length - 1].msg;
  if (finished) {
    message = "Opening your courses…";
  } else if (firstOpen?.id === "zscore" && zscore?.total) {
    message = `Comparing your Z-score with past cut-offs: ${zscore.done ?? 0} of ${zscore.total} courses`;
  }

  return (
    <section className="analysing">
      <div className="card split">
        <div className="side">
          <span className="pill live" style={{ alignSelf: "flex-start" }}>
            <span className="dot" />
            {finished ? "Done" : "Analysing"}
          </span>
          <div className="counter num">{count}</div>
          <div className="muted">
            courses checked
            {eligibility?.eligible != null && <> · {eligibility.eligible} you can apply for</>}
          </div>
          <div className="timeline">
            {ANALYSING_AGENTS.map((agent, i) => {
              const state = stateOf(agent.id);
              const on = state === "running" || (state === "pending" && agent.id === firstOpen?.id);
              const cls = state === "done" ? "tl-item done" : state === "skipped" ? "tl-item skipped"
                : on ? "tl-item on" : "tl-item";
              const detail =
                state === "skipped" ? "skipped"
                  : agent.id === "zscore" && zscore?.total && state === "running"
                    ? `${zscore.done ?? 0} / ${zscore.total}`
                    : agent.d;
              return (
                <div key={agent.id} className={cls}>
                  <b>{agent.k}</b>
                  <span className="mono">
                    {pad2(i + 1)} / {detail}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="status-line" aria-live="polite">
            <span>{message}</span>
          </div>
        </div>
        <div className="side fig-side">
          <FigureImg name="analysing" />
        </div>
      </div>
    </section>
  );
}
