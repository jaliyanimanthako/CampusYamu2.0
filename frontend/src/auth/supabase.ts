import { createClient, type Session, type SupabaseClient, type User } from "@supabase/supabase-js";
import type { RuntimeConfig } from "../api/types.ts";

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

export function isAuthEnabled(): boolean {
  return getSupabase() !== null;
}

export async function getAccessToken(): Promise<string | null> {
  const sb = getSupabase();
  if (!sb) return null;
  const { data } = await sb.auth.getSession();
  return data.session?.access_token ?? null;
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
