import { useEffect, useState } from "react";
import { getMyChats } from "../api/client.ts";
import type { ChatSummary, Me } from "../api/types.ts";
import { hasLocalAccountToken, isAuthEnabled } from "../auth/supabase.ts";
import { LANGS, useMockupI18n, type LangId } from "../i18n/mockupI18n.tsx";
import { useAppTheme } from "../theme/appTheme.tsx";
import { pad2 } from "../utils/course.ts";
import { AnimalAvatar, type AvatarId } from "./AnimalAvatar.tsx";

interface AccountViewProps {
  me: Me | null;
  userEmail: string | null;
  avatarId: AvatarId;
  onOpenCourse: (uniCode: string) => void;
  onSignOut: () => void;
}

export function AccountView({
  me,
  userEmail,
  avatarId,
  onOpenCourse,
  onSignOut,
}: AccountViewProps) {
  const { lang, setLanguage, t } = useMockupI18n();
  const { theme, setTheme } = useAppTheme();
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const authOn = isAuthEnabled() || hasLocalAccountToken();

  useEffect(() => {
    if (!authOn) return;
    let active = true;
    getMyChats()
      .then((list) => {
        if (active) setChats(list);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [authOn]);

  const email = userEmail || "student@campusyamu.lk";
  const [localPart, domainPart] = email.split("@");

  const meters = [
    {
      label: "Chat questions",
      used: me?.usage?.chat?.used ?? 0,
      limit: me?.usage?.chat?.limit ?? 0,
    },
    {
      label: "AI-read searches",
      used: me?.usage?.ai_recommendations?.used ?? me?.usage?.recommendations_llm?.used ?? 0,
      limit: me?.usage?.ai_recommendations?.limit ?? me?.usage?.recommendations_llm?.limit ?? 0,
    },
    {
      label: "Career research",
      used: me?.usage?.research?.used ?? 0,
      limit: me?.usage?.research?.limit ?? 0,
    },
  ];

  return (
    <>
      <section style={{ display: "flex", alignItems: "end", gap: 20, flexWrap: "wrap" }}>
        <div className="profile-head">
          <AnimalAvatar id={avatarId} size={72} />
          <div>
            <span className="label reveal">{t("account")}</span>
            <h1
              className="reveal"
              style={{ ["--i" as string]: 1, marginTop: 8, fontSize: "clamp(28px, 4vw, 48px)" }}
            >
              {localPart}
              {domainPart && <span className="accent">@{domainPart}</span>}
            </h1>
          </div>
        </div>
        <button
          type="button"
          className="btn outline reveal"
          style={{ ["--i" as string]: 2, marginLeft: "auto" }}
          onClick={onSignOut}
        >
          {authOn ? "Sign out" : "Back to start"}
        </button>
      </section>

      <h3 style={{ marginTop: 40 }}>Appearance</h3>
      <div className="lang-opts">
        <button
          type="button"
          aria-pressed={theme === "light"}
          onClick={() => setTheme("light")}
        >
          <span className="glyph g-en">☀️</span>
          <span>Light</span>
        </button>
        <button
          type="button"
          aria-pressed={theme === "dark"}
          onClick={() => setTheme("dark")}
        >
          <span className="glyph g-si">🌙</span>
          <span>Dark</span>
        </button>
      </div>

      <h3 style={{ marginTop: 40 }}>{t("language")}</h3>
      <div className="lang-opts">
        {LANGS.map((l) => (
          <button
            key={l.id}
            type="button"
            aria-pressed={l.id === lang}
            lang={l.id}
            onClick={() => setLanguage(l.id as LangId)}
          >
            <span className={`glyph g-${l.id}`}>{l.short}</span>
            <span>{l.name}</span>
          </button>
        ))}
      </div>

      {authOn && (
        <>
          <h3 style={{ marginTop: 48 }}>Today&apos;s use</h3>
          <div className="me-grid">
            {meters.map((m, idx) => {
              const pct = m.limit > 0 ? Math.min(100, (m.used / m.limit) * 100) : 0;
              return (
                <div
                  key={m.label}
                  className="card meter reveal"
                  style={{ ["--i" as string]: idx + 1 }}
                >
                  <span className="mono faint">{m.label}</span>
                  <div className="value num">
                    {m.used}
                    <small> / {m.limit > 0 ? m.limit : "∞"}</small>
                  </div>
                  <div className="track">
                    <i style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      <h2 className="reveal" style={{ marginTop: authOn ? 0 : 40, marginBottom: 20 }}>
        Your course <span className="accent">chats.</span>
      </h2>

      {chats.length > 0 ? (
        <div className="chat-list">
          {chats.map((c, i) => (
            <a
              key={c.uni_code}
              className="chat-item reveal"
              style={{ ["--i" as string]: i }}
              href={`#/course/${c.uni_code}`}
              onClick={(e) => {
                e.preventDefault();
                onOpenCourse(c.uni_code);
              }}
            >
              <span className="mono">{pad2(i + 1)}</span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <b style={{ fontWeight: 550 }}>{c.course_name}</b>{" "}
                <span className="faint">· {c.university}</span>
              </div>
              <span className="chip plain">{c.messages} messages</span>
            </a>
          ))}
        </div>
      ) : (
        <div className="card empty reveal">
          <div className="fig">
            <img src="/figures/empty-chats.webp" alt="" />
          </div>
          <p style={{ margin: 0 }}>No chats yet. Open a course and ask a question.</p>
        </div>
      )}
    </>
  );
}
