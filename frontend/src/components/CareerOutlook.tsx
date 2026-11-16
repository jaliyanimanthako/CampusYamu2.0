import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Briefcase, Loader2, Search } from "lucide-react";
import {
  ApiError,
  getCareerOutlook,
  postCareerResearch,
} from "../api/client.ts";
import type { CareerOverall } from "../api/types.ts";
import { useTranslation } from "../i18n/index.tsx";

interface CareerOutlookProps {
  courseName: string;
}

export function CareerOutlook({ courseName }: CareerOutlookProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [conflictNotice, setConflictNotice] = useState<string | null>(null);

  const queryKey = ["career-outlook", courseName] as const;

  const { data, isLoading, isError, error } = useQuery({
    queryKey,
    queryFn: () => getCareerOutlook(courseName),
    refetchInterval: (query) =>
      query.state.data?.job?.state === "running" ? 5_000 : false,
  });

  const researchMutation = useMutation({
    mutationFn: () => postCareerResearch({ course: courseName }),
    onSuccess: (response) => {
      setConflictNotice(null);
      queryClient.setQueryData(queryKey, response);
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        setConflictNotice(t("career.conflict"));
      }
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2.5 rounded-[8px] border border-[#E2E8F0] bg-[#F8FAFC] p-4 text-[13px] text-[#475569]">
        <Loader2 className="h-4 w-4 animate-spin text-[#1D4ED8]" strokeWidth={1.5} />
        <span>{t("career.checking", { course: courseName })}</span>
      </div>
    );
  }

  if (isError) {
    const msg =
      error instanceof ApiError ? error.errors[0] : t("career.loadError");
    return (
      <div className="rounded-[8px] border border-[#FECACA] bg-[#FEF2F2] p-4 text-[13px] text-[#B91C1C]">
        {msg}
      </div>
    );
  }

  if (!data) return null;

  const overall = (data.outlook?.overall ?? null) as CareerOverall | null;
  const job = data.job;
  const isRunning = job?.state === "running";

  return (
    <div className="space-y-4">
      {conflictNotice ? (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-[8px] border border-[#FECACA] bg-[#FEF2F2] p-3.5 text-[13px] text-[#B91C1C]"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.5} />
          <span>{conflictNotice}</span>
        </div>
      ) : null}

      {researchMutation.error &&
      !(
        researchMutation.error instanceof ApiError &&
        researchMutation.error.status === 409
      ) ? (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-[8px] border border-[#FECACA] bg-[#FEF2F2] p-3.5 text-[13px] text-[#B91C1C]"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.5} />
          <span>
            {researchMutation.error instanceof ApiError
              ? researchMutation.error.errors[0]
              : t("career.startError")}
          </span>
        </div>
      ) : null}

      {/* Running Job Progress */}
      {isRunning ? (
        <div
          role="status"
          aria-live="polite"
          className="rounded-[8px] border border-[#BFDBFE] bg-[#EFF6FF] p-4"
        >
          <div className="flex items-center gap-2.5 text-[14px] font-medium text-[#0F172A]">
            <Loader2 className="h-4 w-4 animate-spin text-[#1D4ED8]" strokeWidth={1.5} />
            <span>{t("career.running")}</span>
          </div>
          {job?.message ? (
            <p className="mt-1.5 text-[13px] text-[#475569]">{job.message}</p>
          ) : null}
          <p className="mt-1 text-[12px] text-[#64748B]">
            {t("career.pollingNote")}
          </p>
        </div>
      ) : null}

      {/* Failed Job Notice */}
      {job?.state === "failed" ? (
        <div className="rounded-[8px] border border-[#FECACA] bg-[#FEF2F2] p-4 text-[13px] text-[#B91C1C]">
          {t("career.failed")}
          {job.message ? `: ${job.message}` : "."}
        </div>
      ) : null}

      {/* Cached Outlook */}
      {data.outlook ? (
        <section className="rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-3">
            <div className="flex items-center gap-2">
              <Briefcase className="h-4 w-4 text-[#1D4ED8]" strokeWidth={1.5} />
              <h3 className="text-[15px] font-semibold text-[#0F172A]">
                {t("career.title", { course: courseName })}
              </h3>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {overall?.label ? (
                <span className="rounded-full border border-[#BFDBFE] bg-[#EFF6FF] px-2.5 py-0.5 text-[12px] font-medium capitalize text-[#1D4ED8]">
                  {overall.label}
                </span>
              ) : null}
              {overall?.confidence ? (
                <span className="rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-0.5 text-[12px] font-medium capitalize text-[#475569]">
                  {t("career.confidence", { value: overall.confidence })}
                </span>
              ) : null}
            </div>
          </div>

          {overall?.summary ? (
            <p className="mt-3 text-[14px] leading-relaxed text-[#475569]">
              {overall.summary}
            </p>
          ) : null}

          <div className="mt-3 flex flex-wrap items-center gap-4 text-[12px] text-[#64748B]">
            <span className="tabular-nums">
              {t("career.sourcesCount", { count: data.outlook.sources ?? 0 })}
            </span>
            {data.outlook.generated_at ? (
              <span>
                {t("career.updated", {
                  date: new Date(data.outlook.generated_at).toLocaleDateString(),
                })}
              </span>
            ) : null}
          </div>
        </section>
      ) : !isRunning ? (
        <section className="rounded-[8px] border border-[#E2E8F0] bg-[#F8FAFC] p-5">
          <h3 className="text-[15px] font-semibold text-[#0F172A]">
            {t("career.noneTitle")}
          </h3>
          {data.available ? (
            <>
              <p className="mt-1.5 text-[13px] text-[#475569]">
                {t("career.availableHint", { course: courseName })}
              </p>
              <button
                type="button"
                disabled={researchMutation.isPending}
                onClick={() => researchMutation.mutate()}
                className="mt-4 inline-flex items-center gap-2 rounded-[6px] bg-[#1D4ED8] px-4 py-2 text-[13px] font-medium text-[#FFFFFF] hover:bg-[#1E40AF] disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Search className="h-3.5 w-3.5" strokeWidth={1.5} />
                <span>
                  {researchMutation.isPending
                    ? t("career.startingBtn")
                    : t("career.researchBtn")}
                </span>
              </button>
            </>
          ) : (
            <p className="mt-1.5 text-[13px] text-[#64748B]">
              {t("career.unavailableHint")}
            </p>
          )}
        </section>
      ) : null}
    </div>
  );
}
