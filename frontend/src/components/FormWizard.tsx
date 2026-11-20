import { useState, type FormEvent } from "react";
import type { Options, RecommendationRequest } from "../api/types.ts";
import { FORM_STEPS, pad2 } from "../utils/course.ts";
import { ArrowRightIcon, BackIcon } from "./BrandMark.tsx";

export interface FormState {
  stream: string;
  al: [string, string][];
  ol: Record<string, string>;
  cgt: string;
  z_score: string;
  admission_district: string;
  home_district: string;
  ds_division: string;
  preferences: string;
  use_llm: boolean;
}

export const DEFAULT_FORM_STATE: FormState = {
  stream: "Physical Science",
  al: [
    ["Combined Mathematics", "A"],
    ["Physics", "B"],
    ["Chemistry", "C"],
  ],
  ol: { Science: "B", English: "B", Mathematics: "A" },
  cgt: "40",
  z_score: "1.5600",
  admission_district: "Gampaha",
  home_district: "Gampaha",
  ds_division: "Minuwangoda",
  preferences: "engineering, design",
  use_llm: false,
};

interface FormWizardProps {
  options: Options;
  form: FormState;
  hasSavedReport: boolean;
  onChangeForm: (next: FormState) => void;
  onSubmit: (req: RecommendationRequest) => void;
  onViewSaved: () => void;
  onToast: (msg: string) => void;
}

const INTEREST_CHIPS = ["medicine", "computing", "law", "management", "architecture", "teaching"];

export function FormWizard({
  options,
  form,
  hasSavedReport,
  onChangeForm,
  onSubmit,
  onViewSaved,
  onToast,
}: FormWizardProps) {
  const [step, setStep] = useState(0);

  const zVal = Number.parseFloat(form.z_score);
  const hasZ = !Number.isNaN(zVal);
  const zProgress = hasZ ? Math.max(0, Math.min(1, (zVal + 1) / 4)) : 0;
  const zArc = Math.PI * 34;

  const zHint = !hasZ
    ? "No Z-score: every course will show as “no history”."
    : zVal >= 2
      ? "Top of the range: most courses are open to you."
      : zVal >= 1.2
        ? "A strong score for most science and management courses."
        : zVal >= 0.5
          ? "Good for many courses; medicine and engineering will be a reach."
          : "Focus on courses with lower cut-offs and on your interests.";

  const handleStreamSelect = (stream: string) => {
    const defaults = options.stream_hints?.[stream]?.defaults ?? [];
    const nextAl: [string, string][] =
      defaults.length === 3
        ? defaults.map((sub, i) => [sub, form.al[i]?.[1] ?? "A"])
        : form.al;
    onChangeForm({ ...form, stream, al: nextAl });
  };

  const handleAddInterestTag = (tag: string) => {
    const cur = form.preferences.trim();
    const next = cur ? `${cur.replace(/,$/, "")}, ${tag}` : tag;
    onChangeForm({ ...form, preferences: next });
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (step < FORM_STEPS.length - 1) {
      setStep((s) => s + 1);
      return;
    }
    if (new Set(form.al.map(([sub]) => sub)).size !== 3) {
      onToast("Choose three different A/L subjects");
      setStep(0);
      return;
    }
    const cgtNum = Number(form.cgt);
    if (Number.isNaN(cgtNum) || cgtNum < 0 || cgtNum > 100) {
      onToast("Common General Test mark must be between 0 and 100");
      setStep(1);
      return;
    }

    onSubmit({
      stream: form.stream,
      al: form.al.map(([subject, grade]) => ({ subject, grade })),
      ol: Object.entries(form.ol).map(([subject, grade]) => ({ subject, grade })),
      cgt: cgtNum,
      z_score: form.z_score.trim() === "" ? null : Number(form.z_score),
      admission_district: form.admission_district,
      ds_division: form.ds_division,
      preferences: form.preferences,
      use_llm: form.use_llm,
      suggestions: 20,
    });
  };

  const dsList = options.ds_divisions[form.home_district] ?? [];

  return (
    <>
      {hasSavedReport && step === 0 && (
        <div className="notice reveal">
          <span className="chip">Saved</span>
          <span className="muted">You have a saved search from last time.</span>
          <button
            type="button"
            className="btn sm outline"
            style={{ marginLeft: "auto" }}
            onClick={onViewSaved}
          >
            View results <ArrowRightIcon />
          </button>
        </div>
      )}

      <h1 className="reveal" style={{ ["--i" as string]: 1, marginTop: 20 }}>
        Your A/L <span className="accent">results.</span>
      </h1>

      <div className="form-layout">
        <aside>
          <div className="steps">
            {FORM_STEPS.map((label, i) => (
              <button
                key={label}
                type="button"
                className={i === step ? "active" : i < step ? "done" : ""}
                onClick={() => setStep(i)}
              >
                <span className="mono">{pad2(i + 1)}</span>
                <b>{label}</b>
              </button>
            ))}
          </div>
        </aside>

        <form
          className="card form-panel reveal"
          style={{ ["--i" as string]: 2 }}
          onSubmit={handleSubmit}
          noValidate
        >
          {step === 0 && (
            <>
              <header>
                <span className="label">Step 01</span>
                <h2 style={{ marginTop: 10 }}>
                  Stream and <span className="accent">subjects.</span>
                </h2>
                <p className="muted">
                  Pick your stream and we&apos;ll fill in the usual subjects. Change any of them.
                </p>
              </header>
              <div className="field">
                <span className="flabel">Stream</span>
                <div className="streams">
                  {options.streams.map((st) => (
                    <button
                      key={st}
                      type="button"
                      className="stream"
                      aria-pressed={form.stream === st}
                      onClick={() => handleStreamSelect(st)}
                    >
                      {st}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                {form.al.map(([sub, grade], idx) => (
                  <div key={idx} className="subject">
                    <div className="field">
                      <span className="flabel">
                        <span className="mono">{pad2(idx + 1)}</span>&nbsp; A/L subject
                      </span>
                      <select
                        className="select"
                        value={sub}
                        onChange={(e) => {
                          const next = [...form.al] as [string, string][];
                          next[idx] = [e.target.value, grade];
                          onChangeForm({ ...form, al: next });
                        }}
                      >
                        {options.al_subjects.map((opt) => (
                          <option key={opt} value={opt}>
                            {opt}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="grades" role="group" aria-label={`A/L subject ${idx + 1} grade`}>
                      {options.al_grades.map((g) => (
                        <button
                          key={g}
                          type="button"
                          className="grade"
                          aria-pressed={grade === g}
                          onClick={() => {
                            const next = [...form.al] as [string, string][];
                            next[idx] = [sub, g];
                            onChangeForm({ ...form, al: next });
                          }}
                        >
                          {g}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <header>
                <span className="label">Step 02</span>
                <h2 style={{ marginTop: 10 }}>
                  Your <span className="accent">scores.</span>
                </h2>
                <p className="muted">
                  The Z-score sets your chances. Leave it empty if results aren&apos;t out yet.
                </p>
              </header>
              <div className="row two">
                <div className="field">
                  <label htmlFor="cgt">Common General Test mark</label>
                  <input
                    className="input num"
                    id="cgt"
                    type="number"
                    min={0}
                    max={100}
                    value={form.cgt}
                    onChange={(e) => onChangeForm({ ...form, cgt: e.target.value })}
                  />
                  <span className="hint">Required, out of 100.</span>
                </div>
                <div className="field">
                  <label htmlFor="z">Z-score</label>
                  <input
                    className="input num"
                    id="z"
                    type="number"
                    step="0.0001"
                    placeholder="e.g. 1.5623"
                    value={form.z_score}
                    onChange={(e) => onChangeForm({ ...form, z_score: e.target.value })}
                  />
                  <span className="hint">Optional.</span>
                </div>
              </div>
              <div className="zbox">
                <svg width="92" height="56" viewBox="0 0 92 56" style={{ flex: "none" }}>
                  <path
                    d="M12 50 A34 34 0 0 1 80 50"
                    fill="none"
                    stroke="#fff"
                    strokeWidth="8"
                    strokeLinecap="round"
                  />
                  <path
                    d="M12 50 A34 34 0 0 1 80 50"
                    fill="none"
                    stroke="var(--blue)"
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={zArc}
                    strokeDashoffset={zArc * (1 - zProgress)}
                    style={{ transition: "stroke-dashoffset .7s var(--ease-spring)" }}
                  />
                </svg>
                <div>
                  <div className="big num">{hasZ ? zVal.toFixed(4) : "—"}</div>
                  <div className="hint" style={{ marginTop: 6 }}>
                    {zHint}
                  </div>
                </div>
              </div>
              <div className="field">
                <span className="flabel">O/L grades</span>
                <div className="row three">
                  {options.ol_subjects.map((sub) => (
                    <div key={sub} className="field">
                      <span className="hint">{sub}</span>
                      <div className="grades" role="group" aria-label={`${sub} O/L grade`}>
                        {options.ol_grades.map((g) => (
                          <button
                            key={g}
                            type="button"
                            className="grade"
                            aria-pressed={form.ol[sub] === g}
                            onClick={() =>
                              onChangeForm({
                                ...form,
                                ol: { ...form.ol, [sub]: g },
                              })
                            }
                          >
                            {g}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <header>
                <span className="label">Step 03</span>
                <h2 style={{ marginTop: 10 }}>
                  Where you <span className="accent">live.</span>
                </h2>
                <p className="muted">
                  Your admission district sets the cut-offs. Your home sets travel time.
                </p>
              </header>
              <div className="field">
                <label htmlFor="adm">Admission district</label>
                <select
                  className="select"
                  id="adm"
                  value={form.admission_district}
                  onChange={(e) => onChangeForm({ ...form, admission_district: e.target.value })}
                >
                  {options.districts.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>
              <div className="row two">
                <div className="field">
                  <label htmlFor="hd">Home district</label>
                  <select
                    className="select"
                    id="hd"
                    value={form.home_district}
                    onChange={(e) => {
                      const nextDistrict = e.target.value;
                      const firstDs = options.ds_divisions[nextDistrict]?.[0] ?? "";
                      onChangeForm({
                        ...form,
                        home_district: nextDistrict,
                        ds_division: firstDs,
                      });
                    }}
                  >
                    {options.districts.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="ds">DS division</label>
                  <select
                    className="select"
                    id="ds"
                    value={form.ds_division}
                    onChange={(e) => onChangeForm({ ...form, ds_division: e.target.value })}
                  >
                    {dsList.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <header>
                <span className="label">Step 04</span>
                <h2 style={{ marginTop: 10 }}>
                  What you&apos;d like to <span className="accent">study.</span>
                </h2>
                <p className="muted">
                  In your own words. It shapes the ranked order, not your eligibility.
                </p>
              </header>
              <div className="field">
                <label htmlFor="pref">Interests</label>
                <textarea
                  className="input"
                  id="pref"
                  maxLength={2000}
                  placeholder="e.g. engineering, design, working with people"
                  value={form.preferences}
                  onChange={(e) => onChangeForm({ ...form, preferences: e.target.value })}
                />
              </div>
              <div className="interest-tags">
                {INTEREST_CHIPS.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => handleAddInterestTag(tag)}
                  >
                    + {tag}
                  </button>
                ))}
              </div>
              {(options.llm_available || options.preference_ai_available) && (
                <div className="notice">
                  <button
                    type="button"
                    className="toggle"
                    role="switch"
                    aria-checked={form.use_llm}
                    aria-label="Read my interests with AI"
                    onClick={() => onChangeForm({ ...form, use_llm: !form.use_llm })}
                  />
                  <div>
                    <b style={{ fontWeight: 500 }}>Read my interests with AI</b>
                    <div className="hint">
                      Understands phrasing like &ldquo;something with animals&rdquo;. Takes 20–40 seconds.
                    </div>
                  </div>
                  <span className="chip" style={{ marginLeft: "auto" }}>
                    AI
                  </span>
                </div>
              )}
            </>
          )}

          <div className="form-actions">
            <button
              type="button"
              className="btn outline"
              disabled={step === 0}
              onClick={() => setStep((s) => Math.max(0, s - 1))}
            >
              <BackIcon /> Back
            </button>
            {step < FORM_STEPS.length - 1 ? (
              <button type="submit" className="btn">
                Continue
              </button>
            ) : (
              <button type="submit" className="btn">
                Find my courses <ArrowRightIcon />
              </button>
            )}
          </div>
        </form>
      </div>
    </>
  );
}
