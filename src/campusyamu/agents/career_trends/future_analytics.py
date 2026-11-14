"""Evidence-grounded, future-oriented SWOT synthesis."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable

from .analysis_guardrails import drop_items, specificity_problems, strip_offending
from .analytics_evidence import (
    build_evidence_packet,
    cap_unverified_confidence,
    validate_evidence_refs,
)
from .analytics_schema import FUTURE_SWOT_SCHEMA
from .openai_client import OpenAIResponsesClient, StructuredAnalyticsModel
from campusyamu.prompts.career import FUTURE_ANALYSIS as DEVELOPER_PROMPT
from campusyamu.prompts.career import FUTURE_REVISION as REVISION_PROMPT


ProgressCallback = Callable[[dict[str, Any]], None]


class FutureCareerAnalyticsAgent:
    """Turn collected evidence into a cited 4–5 year SWOT."""

    def __init__(
        self,
        model_client: StructuredAnalyticsModel | None = None,
        *,
        max_workers: int = 2,
        max_documents_per_course: int = 50,
        max_total_content_chars: int = 80_000,
    ) -> None:
        self.model_client = model_client or OpenAIResponsesClient()
        self.max_workers = max_workers
        self.max_documents_per_course = max_documents_per_course
        self.max_total_content_chars = max_total_content_chars

    def analyze(
        self,
        web_result: dict[str, Any],
        *,
        horizon_years: int = 5,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        if not 4 <= horizon_years <= 5:
            raise ValueError("horizon_years must be 4 or 5")
        courses = web_result.get("course_research")
        if not isinstance(courses, list) or not courses:
            raise ValueError("web_result contains no course_research data")

        analysis_year = datetime.now(timezone.utc).year
        entry_year = analysis_year + horizon_years
        input_value = web_result.get("input")
        input_value = input_value if isinstance(input_value, dict) else {}
        region = str(input_value.get("region") or "Sri Lanka")
        _notify(
            on_progress,
            {"event": "analysis_started", "course_count": len(courses)},
        )
        results: list[dict[str, Any] | None] = [None] * len(courses)
        worker_count = max(1, min(self.max_workers, len(courses)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            pending = {}
            for index, course in enumerate(courses):
                course_name = str(course.get("course") or "").strip()
                _notify(
                    on_progress,
                    {"event": "course_started", "course": course_name},
                )
                future = executor.submit(
                    self._analyze_course,
                    course,
                    web_result.get("generated_at"),
                    region,
                    analysis_year,
                    entry_year,
                    horizon_years,
                )
                pending[future] = (index, course_name)

            for future in as_completed(pending):
                index, course_name = pending[future]
                try:
                    results[index] = future.result()
                    _notify(
                        on_progress,
                        {"event": "course_completed", "course": course_name},
                    )
                except Exception as exc:
                    results[index] = {
                        "course": course_name,
                        "status": "failed",
                        "error": str(exc),
                    }
                    _notify(
                        on_progress,
                        {
                            "event": "course_failed",
                            "course": course_name,
                            "error": str(exc),
                        },
                    )

        completed = [result for result in results if result is not None]
        statuses = {result["status"] for result in completed}
        status = "success" if statuses == {"success"} else (
            "failed" if statuses == {"failed"} else "partial_failure"
        )
        return {
            "status": status,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": self.model_client.model,
            "analysis_type": "evidence_grounded_future_swot",
            "horizon_years": horizon_years,
            "course_analyses": completed,
        }

    def _analyze_course(
        self,
        course: dict[str, Any],
        collected_at: Any,
        region: str,
        analysis_year: int,
        entry_year: int,
        horizon_years: int,
    ) -> dict[str, Any]:
        course_name = str(course.get("course") or "").strip()
        evidence, evidence_index = build_evidence_packet(
            course,
            max_documents=self.max_documents_per_course,
            max_content_chars=self.max_total_content_chars,
        )
        if not evidence:
            raise RuntimeError("No scraped evidence is available for this course")
        payload = {
            "course": course_name,
            "region": region,
            "analysis_year": analysis_year,
            "expected_entry_year": entry_year,
            "horizon_years": horizon_years,
            "evidence_collected_at": collected_at,
            "occupation_search_terms": course.get("occupation_search_terms", []),
            "emerging_areas_searched": course.get("emerging_areas", []),
            "research_agent_leads": (course.get("agent_research") or {}).get("niche_areas", []),
            "evidence": evidence,
        }
        analysis = self.model_client.generate_json(
            DEVELOPER_PROMPT,
            payload,
            FUTURE_SWOT_SCHEMA,
        )
        valid_ids = {item["evidence_id"] for item in evidence}
        validate_evidence_refs(analysis, valid_ids)
        problems = specificity_problems(analysis, evidence, course_name, region)
        first_problems = len(problems)
        if problems:
            # One repair round: the model sees exactly which items failed and why.
            analysis = self.model_client.generate_json(
                f"{DEVELOPER_PROMPT}\n\n{REVISION_PROMPT}",
                {
                    **payload,
                    "previous_answer": analysis,
                    "problems": [problem.message for problem in problems],
                },
                FUTURE_SWOT_SCHEMA,
            )
            validate_evidence_refs(analysis, valid_ids)
        # Last resort: cut advice and job-advert sentences that survived the
        # revision, then drop any finding left generic or empty.
        sentences_removed = strip_offending(analysis)
        problems = specificity_problems(analysis, evidence, course_name, region)
        dropped = drop_items(analysis, problems)
        lowered = cap_unverified_confidence(
            analysis, {item["evidence_id"] for item in evidence if item["trusted"]}
        )
        return {
            "course": course_name,
            "status": "success",
            "analysis_context": {
                "analysis_year": analysis_year,
                "expected_entry_year": entry_year,
                "horizon_years": horizon_years,
                "evidence_collected_at": collected_at,
                "confidence_ratings_lowered": lowered,
                "specificity_problems_found": first_problems,
                "revised": first_problems > 0,
                "generic_items_dropped": dropped,
                "advice_or_advert_sentences_removed": sentences_removed,
                "remaining_problems": [problem.message for problem in problems if not problem.path],
            },
            "evidence_synthesis": analysis["evidence_synthesis"],
            "course_introduction": analysis["course_introduction"],
            "future_swot": analysis["future_swot"],
            "local_vs_overseas": analysis["local_vs_overseas"],
            "further_study": analysis["further_study"],
            "niche_specialisations": analysis["niche_specialisations"],
            "overall_outlook": analysis["overall_outlook"],
            "limitations": analysis["limitations"],
            "evidence_index": evidence_index,
        }

def _notify(callback: ProgressCallback | None, event: dict[str, Any]) -> None:
    if callback:
        callback(event)
