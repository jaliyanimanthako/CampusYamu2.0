import { useState, type FormEvent } from "react";
import { getSupabase, isAuthEnabled } from "../auth/supabase.ts";
import { ArrowRightIcon, BrandMark } from "./BrandMark.tsx";

interface SignInViewProps {
  onSignedIn: () => void;
  onToast: (msg: string) => void;
}

export function SignInView({ onSignedIn, onToast }: SignInViewProps) {
  const authEnabled = isAuthEnabled();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSignIn = async (e: FormEvent) => {
    e.preventDefault();
    const sb = getSupabase();
    if (!sb) {
      onSignedIn();
      return;
    }
    if (!email.trim() || !password) {
      onToast("Enter your email and password.");
      return;
    }
    setBusy(true);
    try {
      const { error } = await sb.auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      if (error) {
        onToast(error.message);
        return;
      }
      onSignedIn();
    } finally {
      setBusy(false);
    }
  };

  const handleSignUp = async () => {
    const sb = getSupabase();
    if (!sb) {
      onSignedIn();
      return;
    }
    if (!email.trim() || password.length < 6) {
      onToast("Enter a valid email and a password of at least 6 characters.");
      return;
    }
    setBusy(true);
    try {
      const { data, error } = await sb.auth.signUp({
        email: email.trim(),
        password,
      });
      if (error) {
        onToast(error.message);
        return;
      }
      if (data.session) {
        onSignedIn();
      } else {
        onToast("Check your email to confirm your account, then sign in.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="wrap">
      <section className="auth view-enter">
        <BrandMark />
        <div className="card split">
          <div className="side">
            <span className="label">UGC Handbook 2024/25</span>
            <h1 style={{ marginTop: 14 }}>
              Find your
              <br />
              <span className="accent">course.</span>
            </h1>
            <p className="sub">
              Enter your A/L results and see every course you can apply for, how likely you are to
              get in, and how far it is from home.
            </p>
            <form onSubmit={handleSignIn} noValidate>
              {authEnabled ? (
                <>
                  <div className="field">
                    <label htmlFor="email">Email</label>
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
                    <label htmlFor="pw">Password</label>
                    <input
                      className="input"
                      id="pw"
                      type="password"
                      autoComplete="current-password"
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>
                  <button className="btn block" type="submit" disabled={busy}>
                    {busy ? "Signing in…" : "Sign in"} <ArrowRightIcon />
                  </button>
                  <div className="divider">or</div>
                  <button
                    className="btn outline block"
                    type="button"
                    disabled={busy}
                    onClick={handleSignUp}
                  >
                    Create an account
                  </button>
                </>
              ) : (
                <>
                  <button className="btn block" type="submit">
                    Get started <ArrowRightIcon />
                  </button>
                  <span className="faint">
                    Local mode: sign-in is disabled on this server (no SUPABASE_URL configured).
                  </span>
                </>
              )}
            </form>
          </div>
          <div className="side fig-side">
            <div className="fig">
              <img src="/figures/signin.webp" alt="" />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
