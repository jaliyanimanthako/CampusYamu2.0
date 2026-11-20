import { useEffect, useState } from "react";
import { ANALYSING_AGENTS, pad2 } from "../utils/course.ts";
import { FigureImg } from "./BrandMark.tsx";

interface AnalysingViewProps {
  isDone: boolean;
  onCompleteAnimation: () => void;
}

export function AnalysingView({ isDone, onCompleteAnimation }: AnalysingViewProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [count, setCount] = useState(0);
  const [finishedSteps, setFinishedSteps] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const totalCourses = 126;
    const stepMs = reduced ? 60 : 750;

    async function runSteps() {
      for (let i = 0; i < ANALYSING_AGENTS.length; i++) {
        if (cancelled) return;
        setStepIndex(i);
        const startCount = Math.round((totalCourses * i) / ANALYSING_AGENTS.length);
        const endCount = Math.round((totalCourses * (i + 1)) / ANALYSING_AGENTS.length);
        const t0 = performance.now();

        await new Promise<void>((resolve) => {
          const tick = (now: number) => {
            if (cancelled) return resolve();
            const p = Math.min(1, (now - t0) / stepMs);
            setCount(Math.round(startCount + (endCount - startCount) * p));
            if (p < 1) {
              requestAnimationFrame(tick);
            } else {
              resolve();
            }
          };
          requestAnimationFrame(tick);
        });
      }
      if (!cancelled) {
        setFinishedSteps(true);
      }
    }

    void runSteps();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (finishedSteps && isDone) {
      const timer = window.setTimeout(onCompleteAnimation, 350);
      return () => window.clearTimeout(timer);
    }
  }, [finishedSteps, isDone, onCompleteAnimation]);

  const currentAgent = ANALYSING_AGENTS[Math.min(stepIndex, ANALYSING_AGENTS.length - 1)];

  return (
    <section className="analysing">
      <div className="card split">
        <div className="side">
          <span className="pill live" style={{ alignSelf: "flex-start" }}>
            <span className="dot" />
            {finishedSteps && isDone ? "Done" : "Analysing"}
          </span>
          <div className="counter num">{count}</div>
          <div className="muted">courses checked</div>
          <div className="timeline">
            {ANALYSING_AGENTS.map((agent, i) => {
              const cls =
                finishedSteps || i < stepIndex
                  ? "tl-item done"
                  : i === stepIndex
                    ? "tl-item on"
                    : "tl-item";
              return (
                <div key={agent.k} className={cls}>
                  <b>{agent.k}</b>
                  <span className="mono">
                    {pad2(i + 1)} / {agent.d}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="status-line">
            <span>
              {finishedSteps && isDone
                ? "Opening your courses…"
                : currentAgent.msg}
            </span>
          </div>
        </div>
        <div className="side fig-side">
          <FigureImg name="analysing" />
        </div>
      </div>
    </section>
  );
}
