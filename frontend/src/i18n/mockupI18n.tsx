import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { LANGS, STR, type LangId } from "./mockupData.ts";

export { LANGS, type LangId };

const STORAGE_KEY = "cy.lang";

function readInitialLang(): { lang: LangId; chosen: boolean } {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "si" || saved === "ta") {
      return { lang: saved, chosen: true };
    }
  } catch {
    // Ignore storage errors
  }
  return { lang: "en", chosen: false };
}

interface I18nContextValue {
  lang: LangId;
  langChosen: boolean;
  setLanguage: (id: LangId) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  tRaw: <T = unknown>(key: string) => T;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function MockupI18nProvider({ children }: { children: ReactNode }) {
  const initial = readInitialLang();
  const [lang, setLang] = useState<LangId>(initial.lang);
  const [langChosen, setLangChosen] = useState<boolean>(initial.chosen);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLanguage = useCallback((id: LangId) => {
    setLang(id);
    setLangChosen(true);
    document.documentElement.lang = id;
    try {
      window.localStorage.setItem(STORAGE_KEY, id);
    } catch {
      // Ignore storage errors
    }
  }, []);

  const tRaw = useCallback(
    <T = unknown>(key: string): T => {
      const dict = STR[lang] as Record<string, unknown>;
      const fallback = STR.en as Record<string, unknown>;
      return (dict[key] ?? fallback[key] ?? key) as T;
    },
    [lang],
  );

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>): string => {
      const raw = tRaw<unknown>(key);
      let s = typeof raw === "string" ? raw : String(raw ?? key);
      if (vars) {
        s = s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m));
      }
      return s;
    },
    [tRaw],
  );

  return (
    <I18nContext.Provider value={{ lang, langChosen, setLanguage, t, tRaw }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useMockupI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useMockupI18n must be used within MockupI18nProvider");
  return ctx;
}
