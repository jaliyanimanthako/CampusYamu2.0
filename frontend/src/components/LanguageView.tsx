import { LANGS, useMockupI18n, type LangId } from "../i18n/mockupI18n.tsx";
import { ArrowRightIcon, BrandMark } from "./BrandMark.tsx";

interface LanguageViewProps {
  onSelect: (id: LangId) => void;
}

export function LanguageView({ onSelect }: LanguageViewProps) {
  const { lang, langChosen, setLanguage } = useMockupI18n();

  return (
    <div className="wrap">
      <section className="lang-page view-enter">
        <BrandMark />
        <h1 className="lang-title">
          {LANGS.map((l) => (
            <span key={l.id} lang={l.id}>
              {l.choose}
            </span>
          ))}
        </h1>
        <div className="lang-cards">
          {LANGS.map((l, i) => (
            <button
              key={l.id}
              type="button"
              className={`card lang-card reveal ${l.id === lang && langChosen ? "current" : ""}`}
              style={{ ["--i" as string]: i }}
              lang={l.id}
              onClick={() => {
                setLanguage(l.id as LangId);
                onSelect(l.id as LangId);
              }}
            >
              <span className={`glyph g-${l.id}`}>{l.short}</span>
              <span className="txt">
                <b>{l.name}</b>
                <span>
                  {l.hello} {l.line}
                </span>
              </span>
              <ArrowRightIcon />
            </button>
          ))}
        </div>
        <p className="faint lang-later">
          {LANGS.map((l) => (
            <span key={l.id} lang={l.id}>
              {l.later}
            </span>
          ))}
        </p>
      </section>
    </div>
  );
}
