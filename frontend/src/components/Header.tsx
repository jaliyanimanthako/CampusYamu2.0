import { useQuery } from "@tanstack/react-query";
import { Bookmark, Moon, PenLine, RotateCcw, Sun } from "lucide-react";
import { getHealth, isDemoMode } from "../api/client.ts";
import { LOCALE_OPTIONS, useTranslation } from "../i18n/index.tsx";
import { useTheme } from "../theme/index.tsx";

interface HeaderProps {
  hasReport: boolean;
  shortlistCount: number;
  onEditResults?: () => void;
  onResetAll?: () => void;
  onOpenShortlist?: () => void;
}

export function Header({
  hasReport,
  shortlistCount,
  onEditResults,
  onResetAll,
  onOpenShortlist,
}: HeaderProps) {
  const { locale, setLocale, t } = useTranslation();
  const { theme, toggleTheme } = useTheme();

  const {
    data: health,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
    retry: 1,
  });

  const demo = isDemoMode();
  const isOnline = !isError && Boolean(health?.ok);

  let statusLabel = t("header.status.checking");
  if (!isLoading) {
    if (demo) {
      statusLabel = t("header.status.demo");
    } else if (!isOnline) {
      statusLabel = t("header.status.offline");
    } else {
      statusLabel = t("header.status.online");
    }
  }

  return (
    <header className="border-b border-[#E2E8F0] bg-[#FFFFFF]">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3.5 sm:px-6">
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="text-[20px] font-bold tracking-[-0.02em] text-[#0F172A] sm:text-[22px]">
              CampusYamu
            </span>
            <span
              role="status"
              aria-live="polite"
              className="inline-flex items-center gap-1.5 rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-2 py-0.5 text-[11px] font-medium text-[#475569]"
            >
              <span
                aria-hidden="true"
                className={
                  isOnline
                    ? "h-1.5 w-1.5 rounded-full bg-[#10B981]"
                    : "h-1.5 w-1.5 rounded-full bg-[#94A3B8]"
                }
              />
              <span>{statusLabel}</span>
            </span>
          </div>
          <span className="text-[12px] font-medium text-[#64748B]">
            {t("brand.subtitle")}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:gap-2.5">
          {/* Trilingual Language Switcher (EN | සිං | தமிழ்) */}
          <div
            role="group"
            aria-label={t("header.languageLabel")}
            className="inline-flex items-center overflow-hidden rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF]"
          >
            {LOCALE_OPTIONS.map((opt, idx) => {
              const active = locale === opt.code;
              return (
                <button
                  key={opt.code}
                  type="button"
                  aria-pressed={active}
                  title={opt.nativeName}
                  onClick={() => setLocale(opt.code)}
                  className={
                    (idx > 0 ? "border-l border-[#E2E8F0] " : "") +
                    (active
                      ? "bg-[#EFF6FF] px-2.5 py-1 text-[12px] font-semibold text-[#1D4ED8]"
                      : "bg-[#FFFFFF] px-2.5 py-1 text-[12px] font-medium text-[#475569] hover:bg-[#F8FAFC] hover:text-[#0F172A]")
                  }
                >
                  {opt.label}
                </button>
              );
            })}
          </div>

          {/* Light / Dark Theme Toggle */}
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={
              theme === "dark"
                ? t("theme.switchToLight")
                : t("theme.switchToDark")
            }
            title={
              theme === "dark"
                ? t("theme.switchToLight")
                : t("theme.switchToDark")
            }
            className="inline-flex items-center gap-1.5 rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-2.5 py-1 text-[12px] font-medium text-[#475569] transition-colors hover:border-[#CBD5E1] hover:bg-[#F1F5F9] hover:text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]"
          >
            {theme === "dark" ? (
              <Sun className="h-3.5 w-3.5 text-[#1D4ED8]" strokeWidth={1.5} />
            ) : (
              <Moon className="h-3.5 w-3.5 text-[#475569]" strokeWidth={1.5} />
            )}
            <span className="hidden sm:inline">
              {theme === "dark" ? t("theme.light") : t("theme.dark")}
            </span>
          </button>

          {hasReport && onOpenShortlist ? (
            <button
              type="button"
              onClick={onOpenShortlist}
              className="inline-flex items-center gap-1.5 rounded-[6px] border border-[#BFDBFE] bg-[#EFF6FF] px-3 py-1.5 text-[12px] font-semibold text-[#1D4ED8] transition-colors hover:bg-[#F1F5F9]"
            >
              <Bookmark className="h-3.5 w-3.5" strokeWidth={1.5} />
              <span className="tabular-nums">
                {t("header.shortlist", { count: shortlistCount })}
              </span>
            </button>
          ) : null}

          {hasReport && onEditResults ? (
            <button
              type="button"
              onClick={onEditResults}
              className="inline-flex items-center gap-1.5 rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-1.5 text-[12px] font-medium text-[#0F172A] transition-colors hover:border-[#CBD5E1] hover:bg-[#F1F5F9]"
            >
              <PenLine className="h-3.5 w-3.5 text-[#475569]" strokeWidth={1.5} />
              <span>{t("header.editResults")}</span>
            </button>
          ) : null}

          {hasReport && onResetAll ? (
            <button
              type="button"
              onClick={onResetAll}
              title={t("header.reset")}
              className="inline-flex items-center gap-1.5 rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-2.5 py-1.5 text-[12px] font-medium text-[#475569] transition-colors hover:border-[#CBD5E1] hover:bg-[#F1F5F9] hover:text-[#0F172A]"
            >
              <RotateCcw className="h-3.5 w-3.5" strokeWidth={1.5} />
              <span className="hidden md:inline">{t("header.reset")}</span>
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
