import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { LANGS, STR, type LangId } from "./mockupData.ts";

export { LANGS, type LangId };

export const ENABLED_LANGS = LANGS.filter((l) => l.id === "en");

function readInitialLang(): { lang: LangId; chosen: boolean } {
  return { lang: "en", chosen: true };
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

  const setLanguage = useCallback((_id: LangId) => {
    setLang("en");
    setLangChosen(true);
    document.documentElement.lang = "en";
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
