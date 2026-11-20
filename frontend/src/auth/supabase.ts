import { createClient, type Session, type SupabaseClient, type User } from "@supabase/supabase-js";
import type { AuthUser, RuntimeConfig } from "../api/types.ts";

const LOCAL_TOKEN_KEY = "cy.auth_token";
const LOCAL_USER_KEY = "cy.auth_user";

export function getRuntimeConfig(): RuntimeConfig {
  const winCfg = typeof window !== "undefined" ? window.CAMPUSYAMU_CONFIG : undefined;
  const supabaseUrl =
    winCfg?.supabaseUrl?.trim() ||
    (import.meta.env.VITE_SUPABASE_URL as string | undefined)?.trim() ||
    null;
  const supabaseKey =
    winCfg?.supabaseKey?.trim() ||
    (import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined)?.trim() ||
    (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined)?.trim() ||
    null;
  const apiBaseUrl =
    winCfg?.apiBaseUrl?.trim() ||
    (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ||
    null;
  return { supabaseUrl, supabaseKey, apiBaseUrl };
}

let cachedClient: SupabaseClient | null | undefined;

export function getSupabase(): SupabaseClient | null {
  if (cachedClient !== undefined) return cachedClient;
  const { supabaseUrl, supabaseKey } = getRuntimeConfig();
  if (supabaseUrl && supabaseKey) {
    cachedClient = createClient(supabaseUrl, supabaseKey);
  } else {
    cachedClient = null;
  }
  return cachedClient;
}

export function isSupabaseEnabled(): boolean {
  return getSupabase() !== null;
}

/** Backwards-compatible alias: true when Supabase Auth is configured. */
export function isAuthEnabled(): boolean {
  return isSupabaseEnabled();
}

export function getLocalAuthToken(): string | null {
  try {
    return window.localStorage.getItem(LOCAL_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getLocalAuthUser(): AuthUser | null {
  try {
    const raw = window.localStorage.getItem(LOCAL_USER_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export function setLocalAuthSession(token: string, user: AuthUser): void {
  try {
    window.localStorage.setItem(LOCAL_TOKEN_KEY, token);
    window.localStorage.setItem(LOCAL_USER_KEY, JSON.stringify(user));
  } catch {
    // Ignore storage errors
  }
}

export function clearLocalAuthSession(): void {
  try {
    window.localStorage.removeItem(LOCAL_TOKEN_KEY);
    window.localStorage.removeItem(LOCAL_USER_KEY);
  } catch {
    // Ignore storage errors
  }
}

/** True if the user has a Supabase session OR a local backend account token. */
export function hasLocalAccountToken(): boolean {
  return Boolean(getLocalAuthToken());
}

export async function getAccessToken(): Promise<string | null> {
  const sb = getSupabase();
  if (sb) {
    const { data } = await sb.auth.getSession();
    return data.session?.access_token ?? null;
  }
  return getLocalAuthToken();
}

export async function getCurrentSession(): Promise<Session | null> {
  const sb = getSupabase();
  if (!sb) return null;
  const { data } = await sb.auth.getSession();
  return data.session ?? null;
}

export async function getCurrentUser(): Promise<User | null> {
  const session = await getCurrentSession();
  return session?.user ?? null;
}
