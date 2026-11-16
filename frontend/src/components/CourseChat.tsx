import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ExternalLink, Loader2, Send } from "lucide-react";
import { ApiError, postChat } from "../api/client.ts";
import type {
  ChatCourse,
  ChatResponse,
  ChatSource,
  ChatSourceLink,
  ChatTurn,
  CourseRow,
  RecommendationReport,
} from "../api/types.ts";
import { useTranslation } from "../i18n/index.tsx";
import { loadChatHistory, saveChatHistory } from "../state/sessionStore.ts";

interface CourseChatProps {
  course: CourseRow;
  report: RecommendationReport;
  llmAvailable: boolean;
  onCareerJobStarted?: () => void;
}

interface StoredTurn extends ChatTurn {
  sources?: ChatSource[];
  notes?: string[];
  status?: ChatResponse["status"];
}

function renderAnswerWithCitations(text: string): ReactNode[] {
  const parts = text.split(/(\[[A-Za-z]+\d*\])/g);
  return parts.map((part, idx) => {
    if (/^\[[A-Za-z]+\d*\]$/.test(part)) {
      return (
        <span
          key={idx}
          className="mx-0.5 inline-flex items-center rounded border border-[#BFDBFE] bg-[#EFF6FF] px-1.5 py-0.2 text-[11px] font-semibold text-[#1D4ED8]"
        >
          {part}
        </span>
      );
    }
    return <span key={idx}>{part}</span>;
  });
}

function buildChatCourse(
  course: CourseRow,
  report: RecommendationReport,
): ChatCourse {
  const dist = report.rankings?.distance;
  const distMatch = dist?.suggestions?.find(
    (s) => s.uni_code === course.uni_code,
  );
  const order3Note = dist?.feedback?.course_notes?.[course.uni_code]?.note;

  return {
    ...course,
    ...(distMatch
      ? {
          order3_position: distMatch.position,
          ...(distMatch.parts ? { parts: distMatch.parts } : {}),
        }
      : {}),
    ...(order3Note ? { order3_note: order3Note } : {}),
  };
}

function buildStudentContext(report: RecommendationReport): Record<string, unknown> {
  const { profile, origin, preferences } = report;
  const home =
    origin?.ds_division && origin?.district
      ? `${origin.ds_division} (${origin.district})`
      : profile.home || "";

  return {
    stream: profile.stream,
    al_results: profile.al_results,
    z_score: profile.z_score ?? null,
    admission_district: profile.admission_district,
    home,
    interests: preferences?.text ?? "",
  };
}

export function CourseChat({
  course,
  report,
  llmAvailable,
  onCareerJobStarted,
}: CourseChatProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [turns, setTurns] = useState<StoredTurn[]>(() =>
    loadChatHistory(course.uni_code),
  );
  const [question, setQuestion] = useState("");

  useEffect(() => {
    setTurns(loadChatHistory(course.uni_code));
    setQuestion("");
  }, [course.uni_code]);

  const chatCourse = useMemo(
    () => buildChatCourse(course, report),
    [course, report],
  );
  const studentContext = useMemo(() => buildStudentContext(report), [report]);

  const starterChips = [
    t("chat.starter.1"),
    t("chat.starter.2"),
    t("chat.starter.3"),
  ];

  const mutation = useMutation({
    mutationFn: async (userQuestion: string) => {
      const historyPayload: ChatTurn[] = turns
        .slice(-8)
        .map((turn) => ({ role: turn.role, content: turn.content }));

      return postChat({
        question: userQuestion,
        course: chatCourse,
        student: studentContext,
        history: historyPayload,
      });
    },
    onSuccess: (response, userQuestion) => {
      const nextTurns: StoredTurn[] = [
        ...turns,
        { role: "user", content: userQuestion },
        {
          role: "assistant",
          content: response.answer,
          sources: response.sources,
          notes: response.notes,
          status: response.status,
        },
      ];
      setTurns(nextTurns);
      saveChatHistory(
        course.uni_code,
        nextTurns.map(({ role, content }) => ({ role, content })),
      );
      setQuestion("");

      if (response.career) {
        queryClient.setQueryData(
          ["career-outlook", course.course_name],
          response.career,
        );
        if (response.career.job?.state === "running") {
          onCareerJobStarted?.();
        }
      }
    },
  });

  if (!llmAvailable) {
    return (
      <div className="rounded-[8px] border border-[#E2E8F0] bg-[#F8FAFC] p-5 text-[13px] text-[#64748B]">
        {t("chat.unavailable")}
      </div>
    );
  }

  const handleSend = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || mutation.isPending) return;
    mutation.mutate(trimmed);
  };

  const errorMessage =
    mutation.error instanceof ApiError
      ? mutation.error.errors[0]
      : mutation.error
        ? t("chat.failed")
        : null;

  return (
    <div className="flex flex-col gap-4">
      {/* Starter Chips */}
      <div className="flex flex-wrap gap-2">
        {starterChips.map((chip) => (
          <button
            key={chip}
            type="button"
            disabled={mutation.isPending}
            onClick={() => handleSend(chip)}
            className="rounded-full border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-1 text-[12px] font-medium text-[#0F172A] hover:border-[#BFDBFE] hover:bg-[#EFF6FF] hover:text-[#1D4ED8] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {chip}
          </button>
        ))}
      </div>

      {/* Conversation Turns */}
      <div className="space-y-3">
        {turns.length === 0 ? (
          <div className="rounded-[8px] border border-[#E2E8F0] bg-[#F8FAFC] p-4 text-[13px] text-[#64748B]">
            {t("chat.emptyPrompt", {
              course: course.course_name,
              university: course.university,
            })}
          </div>
        ) : (
          turns.map((turn, idx) => (
            <div
              key={idx}
              className={
                turn.role === "user"
                  ? "ml-6 rounded-[8px] border border-[#BFDBFE] bg-[#EFF6FF] p-3.5 text-[14px] text-[#0F172A]"
                  : "mr-4 rounded-[8px] border border-[#E2E8F0] bg-[#FFFFFF] p-3.5 text-[14px] text-[#0F172A]"
              }
            >
              <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
                {turn.role === "user"
                  ? t("chat.role.user")
                  : t("chat.role.assistant")}
              </span>
              <div className="whitespace-pre-line leading-relaxed text-[#0F172A]">
                {turn.role === "assistant"
                  ? renderAnswerWithCitations(turn.content)
                  : turn.content}
              </div>

              {turn.sources && turn.sources.length > 0 ? (
                <div className="mt-3 space-y-1.5 border-t border-[#E2E8F0] pt-2.5">
                  <span className="block text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">
                    {t("chat.sources")}
                  </span>
                  {turn.sources.map((src) => {
                    const links = (src.links ?? []) as ChatSourceLink[];
                    return (
                      <div
                        key={src.id}
                        className="rounded-[6px] border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-2 text-[12px]"
                      >
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="font-semibold text-[#1D4ED8]">
                            [{src.id}]
                          </span>
                          {src.title ? (
                            <span className="font-medium text-[#0F172A]">
                              {src.title}
                            </span>
                          ) : null}
                          {src.citation ? (
                            <span className="text-[#64748B]">
                              — {src.citation}
                            </span>
                          ) : null}
                        </div>
                        {links.length > 0 ? (
                          <div className="mt-1.5 flex flex-wrap gap-2">
                            {links.map((link, lIdx) =>
                              link?.url ? (
                                <a
                                  key={lIdx}
                                  href={link.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 text-[11px] font-medium text-[#1D4ED8] hover:underline"
                                >
                                  <span>{link.title || link.url}</span>
                                  <ExternalLink className="h-3 w-3" strokeWidth={1.5} />
                                </a>
                              ) : null,
                            )}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              ) : null}
            </div>
          ))
        )}
      </div>

      {errorMessage ? (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-[8px] border border-[#FECACA] bg-[#FEF2F2] p-3 text-[13px] text-[#B91C1C]"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.5} />
          <span>{errorMessage}</span>
        </div>
      ) : null}

      {/* Input Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend(question);
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          maxLength={1000}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={mutation.isPending}
          placeholder={t("chat.inputPlaceholder")}
          aria-label={t("chat.inputAria")}
          className="flex-1 rounded-[6px] border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-[14px] text-[#0F172A] placeholder:text-[#64748B] focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20 disabled:bg-[#F8FAFC]"
        />
        <button
          type="submit"
          disabled={mutation.isPending || !question.trim()}
          className="inline-flex items-center gap-1.5 rounded-[6px] bg-[#1D4ED8] px-4 py-2 text-[13px] font-medium text-[#FFFFFF] hover:bg-[#1E40AF] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
          ) : (
            <Send className="h-4 w-4" strokeWidth={1.5} />
          )}
          <span>{mutation.isPending ? t("chat.sending") : t("chat.send")}</span>
        </button>
      </form>
    </div>
  );
}
