import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { en, type TranslationKey, type Translations } from "./en.ts";
import { si } from "./si.ts";
import { ta } from "./ta.ts";

export type Locale = "en" | "si" | "ta";

export const LOCALE_OPTIONS: ReadonlyArray<{ code: Locale; label: string; nativeName: string }> = [
  { code: "en", label: "EN", nativeName: "English" },
  { code: "si", label: "සිං", nativeName: "සිංහල" },
  { code: "ta", label: "தமிழ்", nativeName: "தமிழ்" },
] as const;

const DICTIONARIES: Record<Locale, Translations> = { en, si, ta };
const LOCALE_STORAGE_KEY = "campusyamu_locale_v1";

const STREAM_LABELS: Record<Locale, Record<string, string>> = {
  en: {},
  si: {
    Arts: "කලා (Arts)",
    Commerce: "වාණිජ (Commerce)",
    "Biological Science": "ජීව විද්‍යා (Biological Science)",
    "Physical Science": "භෞතික විද්‍යා (Physical Science)",
    "Engineering Technology": "ඉංජිනේරු තාක්ෂණවේදය (Engineering Technology)",
    "Biosystems Technology": "ජෛව පද්ධති තාක්ෂණවේදය (Biosystems Technology)",
    "Information Communication Technology": "තොරතුරු හා සන්නිවේදන තාක්ෂණය (ICT)",
  },
  ta: {
    Arts: "கலை (Arts)",
    Commerce: "வணிகம் (Commerce)",
    "Biological Science": "உயிரியல் விஞ்ஞானம் (Biological Science)",
    "Physical Science": "பௌதிக விஞ்ஞானம் (Physical Science)",
    "Engineering Technology": "பொறியியல் தொழில்நுட்பம் (Engineering Technology)",
    "Biosystems Technology": "உயிர்முறைமைத் தொழில்நுட்பம் (Biosystems Technology)",
    "Information Communication Technology": "தகவல் தொடர்பாடல் தொழில்நுட்பம் (ICT)",
  },
};

const OL_SUBJECT_LABELS: Record<Locale, Record<string, string>> = {
  en: {},
  si: {
    Science: "විද්‍යාව",
    English: "ඉංග්‍රීසි",
    Mathematics: "ගණිතය",
  },
  ta: {
    Science: "விஞ்ஞானம்",
    English: "ஆங்கிலம்",
    Mathematics: "கணிதம்",
  },
};

function loadInitialLocale(): Locale {
  try {
    const saved = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (saved === "en" || saved === "si" || saved === "ta") {
      return saved;
    }
  } catch {
    // Ignore storage errors
  }
  return "en";
}

interface I18nContextValue {
  locale: Locale;
  setLocale: (next: Locale) => void;
  t: (key: TranslationKey, params?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(loadInitialLocale);

  useEffect(() => {
    document.documentElement.lang = locale;
    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    } catch {
      // Ignore storage errors
    }
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
  }, []);

  const t = useCallback(
    (key: TranslationKey, params?: Record<string, string | number>): string => {
      const template = DICTIONARIES[locale][key] ?? en[key] ?? key;
      if (!params) return template;
      return template.replace(/\{(\w+)\}/g, (_, name: string) =>
        params[name] !== undefined ? String(params[name]) : `{${name}}`,
      );
    },
    [locale],
  );

  const value = useMemo(
    () => ({ locale, setLocale, t }),
    [locale, setLocale, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useTranslation must be used within an I18nProvider");
  }
  return ctx;
}

export function translateStream(locale: Locale, stream: string): string {
  return STREAM_LABELS[locale]?.[stream] ?? stream;
}

export function translateOlSubject(locale: Locale, subject: string): string {
  return OL_SUBJECT_LABELS[locale]?.[subject] ?? subject;
}

export type { TranslationKey };
