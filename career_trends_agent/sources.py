"""Curated authoritative sources used instead of unrestricted web crawling."""

from __future__ import annotations

from .models import TrendSource


GLOBAL_SOURCES = (
    TrendSource(
        "wef_jobs_2025",
        "World Economic Forum — Future of Jobs 2025",
        "https://www.weforum.org/publications/the-future-of-jobs-report-2025/2-jobs-outlook",
        "global",
        "job outlook",
    ),
    TrendSource(
        "wef_skills_2025",
        "World Economic Forum — Skills Outlook 2025",
        "https://www.weforum.org/publications/the-future-of-jobs-report-2025/3-skills-outlook",
        "global",
        "skills outlook",
    ),
    TrendSource(
        "ilo_ai_exposure_2025",
        "ILO — Global Index of Occupational Exposure to GenAI",
        "https://www.ilo.org/publications/generative-ai-and-jobs-refined-global-index-occupational-exposure",
        "global",
        "AI task exposure",
    ),
    TrendSource(
        "oecd_skills_2025",
        "OECD Skills Outlook 2025",
        "https://www.oecd.org/en/publications/oecd-skills-outlook-2025_26163cd3-en/full-report/from-skills-to-labour-market-opportunities_c97cd32b.html",
        "OECD countries",
        "skills and labour-market opportunities",
    ),
)

US_SOURCES = (
    TrendSource(
        "bls_projections",
        "U.S. Bureau of Labor Statistics — Occupational Projections",
        "https://www.bls.gov/emp/tables/occupational-projections-and-characteristics.htm",
        "United States",
        "occupation growth, openings, education, and wages",
    ),
)

SRI_LANKA_SOURCES = (
    TrendSource(
        "sl_labor_force",
        "Sri Lanka Department of Census and Statistics — Labour Force",
        "https://www.statistics.gov.lk/LabourForce/StaticalInformation/AnnualReports",
        "Sri Lanka",
        "national employment context",
    ),
    TrendSource(
        "sl_tvec_lmi",
        "Sri Lanka TVEC — Labour Market Information Bulletin",
        "https://www.tvec.gov.lk/wp-content/uploads/2025/04/LMI_2024_volume_1_F.pdf",
        "Sri Lanka",
        "occupation demand and vacancies",
    ),
)


def sources_for_region(region: str) -> tuple[TrendSource, ...]:
    normalized = region.casefold().replace(" ", "_")
    if normalized in {"us", "usa", "united_states"}:
        return GLOBAL_SOURCES + US_SOURCES
    if normalized in {"sri_lanka", "srilanka", "lk"}:
        return GLOBAL_SOURCES + SRI_LANKA_SOURCES
    return GLOBAL_SOURCES
