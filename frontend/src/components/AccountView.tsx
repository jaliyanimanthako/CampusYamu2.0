import { useEffect, useState } from "react";
import { getMyChats } from "../api/client.ts";
import type { ChatSummary, Me } from "../api/types.ts";
import { hasLocalAccountToken, isAuthEnabled } from "../auth/supabase.ts";
import { ENABLED_LANGS, useMockupI18n, type LangId } from "../i18n/mockupI18n.tsx";
import { useAppTheme } from "../theme/appTheme.tsx";
import { pad2 } from "../utils/course.ts";
import { AnimalAvatar, type AvatarId } from "./AnimalAvatar.tsx";
import { FigureImg } from "./BrandMark.tsx";

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
      <div className="theme-opts">
        <button
          type="button"
          aria-pressed={theme === "system"}
          onClick={() => setTheme("system")}
        >
          <span className="theme-ic theme-ic-system" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <rect x="3" y="4" width="18" height="13" rx="3" stroke="#4F6FE8" strokeWidth="2" />
              <path d="M8 20h8M12 17v3" stroke="#4F6FE8" strokeWidth="2" strokeLinecap="round" />
              <path d="M12 7.5a3 3 0 1 0 0 6v-6z" fill="#F2B84B" />
              <path d="M12 7.5a3 3 0 0 1 0 6v-6z" fill="#C9B8F5" />
            </svg>
          </span>
          <span>System</span>
        </button>
        <button
          type="button"
          aria-pressed={theme === "light"}
          onClick={() => setTheme("light")}
        >
          <span className="theme-ic theme-ic-light" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="4.5" fill="#F2B84B" />
              <path
                d="M12 2.5v2.2M12 19.3v2.2M4.93 4.93l1.55 1.55M17.52 17.52l1.55 1.55M2.5 12h2.2M19.3 12h2.2M4.93 19.07l1.55-1.55M17.52 6.48l1.55-1.55"
                stroke="#4F6FE8"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </span>
          <span>Light</span>
        </button>
        <button
          type="button"
          aria-pressed={theme === "dark"}
          onClick={() => setTheme("dark")}
        >
          <span className="theme-ic theme-ic-dark" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path
                d="M20.2 14.5A8.2 8.2 0 0 1 9.5 3.8a8.2 8.2 0 1 0 10.7 10.7z"
                fill="#C9B8F5"
              />
              <path
                d="M17.5 4l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"
                fill="#F2B84B"
              />
            </svg>
          </span>
          <span>Dark</span>
        </button>
      </div>

      {ENABLED_LANGS.length > 1 && (
        <>
          <h3 style={{ marginTop: 40 }}>{t("language")}</h3>
          <div className="lang-opts">
            {ENABLED_LANGS.map((l) => (
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
        </>
      )}

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
          <FigureImg name="empty-chats" />
          <p style={{ margin: 0 }}>No chats yet. Open a course and ask a question.</p>
        </div>
      )}
    </>
  );
}
