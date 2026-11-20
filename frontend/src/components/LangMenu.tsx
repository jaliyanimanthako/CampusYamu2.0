import { useEffect, useRef, useState } from "react";
import { LANGS, useMockupI18n, type LangId } from "../i18n/mockupI18n.tsx";

export function LangMenu() {
  const { lang, setLanguage, t } = useMockupI18n();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("click", onDocClick);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("click", onDocClick);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  const current = LANGS.find((l) => l.id === lang) ?? LANGS[2];

  return (
    <div ref={rootRef} className={`lang-menu ${open ? "open" : ""}`}>
      <button
        type="button"
        className="lang-btn"
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={t("language")}
        onClick={() => setOpen((prev) => !prev)}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="9" />
          <path d="M3.6 9h16.8M3.6 15h16.8M12 3a13 13 0 0 1 0 18M12 3a13 13 0 0 0 0 18" />
        </svg>
        <span lang={current.id}>{current.short}</span>
      </button>
      <div className="lang-pop" role="menu">
        {LANGS.map((l) => (
          <button
            key={l.id}
            type="button"
            role="menuitemradio"
            aria-checked={l.id === current.id}
            lang={l.id}
            onClick={() => {
              setLanguage(l.id as LangId);
              setOpen(false);
            }}
          >
            <span>{l.name}</span>
            {l.id === current.id && (
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M5 12.5l4.5 4.5L19 7.5" />
              </svg>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
