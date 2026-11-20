import { useState, type FormEvent } from "react";
import { postSignIn, postSignUp } from "../api/client.ts";
import {
  getSupabase,
  isSupabaseEnabled,
  setLocalAuthSession,
} from "../auth/supabase.ts";
import { useMockupI18n } from "../i18n/mockupI18n.tsx";
import { ThemeToggleButton } from "../theme/appTheme.tsx";
import { type AvatarId } from "./AnimalAvatar.tsx";
import { ArrowRightIcon, BrandMark, FigureImg } from "./BrandMark.tsx";
import { LangMenu } from "./LangMenu.tsx";

interface SignInViewProps {
  onSignedIn: (email?: string, avatar?: AvatarId, isNewAccount?: boolean) => void;
  onContinueGuest?: () => void;
  onBackHome: () => void;
  onToast: (msg: string) => void;
}

export function SignInView({
  onSignedIn,
  onContinueGuest,
  onBackHome,
  onToast,
}: SignInViewProps) {
  const { t } = useMockupI18n();
  const supabaseOn = isSupabaseEnabled();

  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setNotice(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !trimmedEmail.includes("@")) {
      onToast("Enter a valid email address.");
      return;
    }
    if (mode === "signup") {
      if (password.length < 6) {
        onToast("Password must be at least 6 characters.");
        return;
      }
      if (password !== confirmPassword) {
        onToast("Passwords do not match.");
        return;
      }
    } else if (!password) {
      onToast("Enter your password.");
      return;
    }

    setBusy(true);
    try {
      const sb = getSupabase();
      if (sb) {
        if (mode === "signin") {
          const { data, error } = await sb.auth.signInWithPassword({
            email: trimmedEmail,
            password,
          });
          if (error) {
            onToast(error.message);
            return;
          }
          const metaAvatar = data.user?.user_metadata?.avatar as AvatarId | undefined;
          onSignedIn(data.user?.email ?? trimmedEmail, metaAvatar, false);
        } else {
          const { data, error } = await sb.auth.signUp({
            email: trimmedEmail,
            password,
            options: {
              emailRedirectTo: window.location.origin + window.location.pathname,
              data: name.trim() ? { full_name: name.trim() } : undefined,
            },
          });
          if (error) {
            onToast(error.message);
            return;
          }
          if (data.session) {
            onSignedIn(data.user?.email ?? trimmedEmail, undefined, true);
          } else {
            setNotice(
              `Account created! Check ${trimmedEmail} for a confirmation link, then sign in.`,
            );
            setMode("signin");
            setPassword("");
            setConfirmPassword("");
          }
        }
      } else {
        const res =
          mode === "signin"
            ? await postSignIn({ email: trimmedEmail, password })
            : await postSignUp({
                email: trimmedEmail,
                password,
                name: name.trim(),
              });
        setLocalAuthSession(res.access_token, res.user);
        onSignedIn(res.user.email, res.user.avatar as AvatarId | undefined, mode === "signup");
      }
    } catch (err) {
      onToast(err instanceof Error ? err.message : t("error"));
    } finally {
      setBusy(false);
    }
  };

  const switchMode = (next: "signin" | "signup") => {
    setMode(next);
    setNotice(null);
  };

  const handleGoogleSignIn = async () => {
    const sb = getSupabase();
    if (!sb) return;
    setBusy(true);
    setNotice(null);
    try {
      const { error } = await sb.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: window.location.origin + window.location.pathname,
        },
      });
      if (error) {
        onToast(error.message);
        setBusy(false);
      }
    } catch (err) {
      onToast(err instanceof Error ? err.message : t("error"));
      setBusy(false);
    }
  };

  return (
    <div className="wrap">
      <section className="auth view-enter">
        <div className="auth-top">
          <BrandMark href="#/home" onClick={onBackHome} />
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <ThemeToggleButton />
            <LangMenu />
          </div>
        </div>
        <div className="card split">
          <div className="side">
            <span className="label">{t("signin.kicker")}</span>
            <h1 style={{ marginTop: 14 }}>
              {mode === "signin" ? (
                <>
                  {t("signin.h1a")}
                  <br />
                  <span className="accent">{t("signin.h1b")}</span>
                </>
              ) : (
                <>
                  Create your
                  <br />
                  <span className="accent">account.</span>
                </>
              )}
            </h1>
            <p className="sub">{t("signin.sub")}</p>

            {notice && (
              <div className="notice" style={{ marginTop: 20 }}>
                <span className="chip blue">Info</span>
                <span style={{ fontSize: 13.5 }}>{notice}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} noValidate>
              {mode === "signup" && (
                <div className="field">
                  <label htmlFor="name">Name (optional)</label>
                  <input
                    className="input"
                    id="name"
                    type="text"
                    autoComplete="name"
                    placeholder="Your name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
              )}

              <div className="field">
                <label htmlFor="email">{t("email")}</label>
                <input
                  className="input"
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div className="field">
                <label htmlFor="pw">{t("password")}</label>
                <div className="pw-wrap">
                  <input
                    className="input"
                    id="pw"
                    type={showPassword ? "text" : "password"}
                    autoComplete={mode === "signin" ? "current-password" : "new-password"}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="pw-toggle"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((v) => !v)}
                  >
                    {showPassword ? (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a21.77 21.77 0 0 1 5.06-5.94" />
                        <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a21.8 21.8 0 0 1-2.16 3.19" />
                        <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
                        <path d="M1 1l22 22" />
                      </svg>
                    ) : (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {mode === "signup" && (
                <div className="field">
                  <label htmlFor="pw2">Confirm password</label>
                  <div className="pw-wrap">
                    <input
                      className="input"
                      id="pw2"
                      type={showConfirmPassword ? "text" : "password"}
                      autoComplete="new-password"
                      placeholder="••••••••"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      className="pw-toggle"
                      aria-label={showConfirmPassword ? "Hide confirm password" : "Show confirm password"}
                      aria-pressed={showConfirmPassword}
                      onClick={() => setShowConfirmPassword((v) => !v)}
                    >
                      {showConfirmPassword ? (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                          <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a21.77 21.77 0 0 1 5.06-5.94" />
                          <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a21.8 21.8 0 0 1-2.16 3.19" />
                          <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
                          <path d="M1 1l22 22" />
                        </svg>
                      ) : (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                          <circle cx="12" cy="12" r="3" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
              )}

              <button className="btn block" type="submit" disabled={busy}>
                {busy
                  ? mode === "signin"
                    ? t("signin.busy")
                    : "Creating account…"
                  : mode === "signin"
                    ? t("signin.btn")
                    : t("signin.create")}{" "}
                <ArrowRightIcon />
              </button>

              <div className="divider">{t("or")}</div>

              {supabaseOn && (
                <button
                  className="btn outline block"
                  type="button"
                  disabled={busy}
                  onClick={() => void handleGoogleSignIn()}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                    <path
                      fill="#4285F4"
                      d="M23.52 12.27c0-.85-.08-1.68-.22-2.48H12v4.69h6.46a5.52 5.52 0 0 1-2.39 3.62v3.01h3.87c2.26-2.08 3.58-5.15 3.58-8.84z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 24c3.24 0 5.95-1.07 7.94-2.91l-3.87-3.01c-1.07.72-2.45 1.15-4.07 1.15-3.13 0-5.78-2.11-6.73-4.96H1.27v3.1A12 12 0 0 0 12 24z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.27 14.27A7.2 7.2 0 0 1 4.89 12c0-.79.14-1.56.38-2.27v-3.1H1.27A12 12 0 0 0 0 12c0 1.94.46 3.77 1.27 5.37l4-3.1z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 4.77c1.76 0 3.34.61 4.58 1.8l3.44-3.44C17.95 1.19 15.24 0 12 0A12 12 0 0 0 1.27 6.63l4 3.1C6.22 6.88 8.87 4.77 12 4.77z"
                    />
                  </svg>
                  Continue with Google
                </button>
              )}

              {mode === "signin" ? (
                <button
                  className="btn outline block"
                  type="button"
                  disabled={busy}
                  onClick={() => switchMode("signup")}
                >
                  {t("signin.create")}
                </button>
              ) : (
                <button
                  className="btn outline block"
                  type="button"
                  disabled={busy}
                  onClick={() => switchMode("signin")}
                >
                  Already have an account? {t("signin.btn")}
                </button>
              )}

              {!supabaseOn && onContinueGuest && (
                <button
                  type="button"
                  className="faint"
                  style={{
                    background: "none",
                    border: 0,
                    padding: "6px 0",
                    textAlign: "left",
                    textDecoration: "underline",
                  }}
                  onClick={onContinueGuest}
                >
                  Continue without an account (guest mode)
                </button>
              )}
            </form>
          </div>
          <div className="side fig-side">
            <FigureImg name="signin" />
          </div>
        </div>
      </section>
    </div>
  );
}
