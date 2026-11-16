import { Minus } from "lucide-react";
import type { BandKey } from "../api/types.ts";
import { useTranslation } from "../i18n/index.tsx";
import { BAND_LABEL_KEYS } from "../utils/format.ts";

interface BandBadgeProps {
  band: BandKey;
}

const BAND_STYLES: Record<BandKey, { bg: string; text: string; border: string; dot: string }> = {
  strong: {
    bg: "var(--band-strong-bg)",
    text: "var(--band-strong-text)",
    border: "var(--band-strong-border)",
    dot: "var(--band-strong-text)",
  },
  competitive: {
    bg: "var(--band-competitive-bg)",
    text: "var(--band-competitive-text)",
    border: "var(--band-competitive-border)",
    dot: "var(--band-competitive-text)",
  },
  reach: {
    bg: "var(--band-reach-bg)",
    text: "var(--band-reach-text)",
    border: "var(--band-reach-border)",
    dot: "var(--band-reach-text)",
  },
  unlikely: {
    bg: "var(--band-unlikely-bg)",
    text: "var(--band-unlikely-text)",
    border: "var(--band-unlikely-border)",
    dot: "var(--band-unlikely-text)",
  },
  no_history: {
    bg: "var(--band-unlikely-bg)",
    text: "var(--band-unlikely-text)",
    border: "var(--band-unlikely-border)",
    dot: "var(--band-unlikely-text)",
  },
};

export function BandBadge({ band }: BandBadgeProps) {
  const { t } = useTranslation();
  const labelKey = BAND_LABEL_KEYS[band];
  const label = labelKey ? t(labelKey) : band;
  const style = BAND_STYLES[band] ?? BAND_STYLES.no_history;

  return (
    <span
      style={{
        backgroundColor: style.bg,
        color: style.text,
        borderColor: style.border,
      }}
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[12px] font-semibold whitespace-nowrap"
    >
      {band === "no_history" ? (
        <Minus className="h-3 w-3" strokeWidth={2} aria-hidden="true" />
      ) : (
        <span
          aria-hidden="true"
          style={{ backgroundColor: style.dot }}
          className="h-2 w-2 rounded-full"
        />
      )}
      <span>{label}</span>
    </span>
  );
}
