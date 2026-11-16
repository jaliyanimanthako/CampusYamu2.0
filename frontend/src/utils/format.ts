import type { BandKey } from "../api/types.ts";
import type { TranslationKey } from "../i18n/index.tsx";

type Translator = (key: TranslationKey, params?: Record<string, string | number>) => string;

export const BAND_LABEL_KEYS: Record<BandKey, TranslationKey> = {
  strong: "band.strong",
  competitive: "band.competitive",
  reach: "band.reach",
  unlikely: "band.unlikely",
  no_history: "band.no_history",
};

export const BAND_DESC_KEYS: Record<BandKey, TranslationKey> = {
  strong: "band.desc.strong",
  competitive: "band.desc.competitive",
  reach: "band.desc.reach",
  unlikely: "band.desc.unlikely",
  no_history: "band.desc.no_history",
};

export function formatZScore(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  return value.toFixed(4);
}

export function formatMinutes(
  minutes: number | null | undefined,
  t?: Translator,
): string {
  if (typeof minutes !== "number" || Number.isNaN(minutes)) {
    return "—";
  }
  const rounded = Math.round(minutes);
  if (rounded < 60) {
    return t ? t("unit.min", { n: rounded }) : `${rounded} min`;
  }
  const hours = Math.floor(rounded / 60);
  const mins = rounded % 60;
  if (mins > 0) {
    return t ? t("unit.hourMin", { h: hours, m: mins }) : `${hours}h ${mins}m`;
  }
  return t ? t("unit.hour", { h: hours }) : `${hours}h`;
}

export function formatTravelSummary(
  carMin: number | null | undefined,
  busMinEst: number | null | undefined,
  t?: Translator,
): string {
  const car = formatMinutes(carMin, t);
  const bus = formatMinutes(busMinEst, t);
  if (car === "—" && bus === "—") return "—";
  const carLabel = t ? t("unit.car", { t: car }) : `${car} car`;
  const busLabel = t ? t("unit.bus", { t: bus }) : `~${bus} bus`;
  if (car !== "—" && bus !== "—") return `${carLabel} · ${busLabel}`;
  if (car !== "—") return carLabel;
  return busLabel;
}
