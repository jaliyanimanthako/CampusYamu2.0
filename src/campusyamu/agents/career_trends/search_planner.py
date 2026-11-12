"""Build bounded, course-specific searches without using an LLM."""

from __future__ import annotations

from .models import CourseProfile, SearchQuery
from .source_registry import FIELD_SOURCE_DOMAINS


COMMUNITY_SOURCE = "reddit"


def build_search_queries(
    course: CourseProfile,
    region: str,
) -> tuple[SearchQuery, ...]:
    occupation_terms = " OR ".join(
        f'"{term}"' for term in course.focus_areas[:5]
    )
    queries = [
        SearchQuery(
            "local_live_jobs",
            (
                f"({occupation_terms}) "
                f"(jobs OR vacancies OR internships OR \"graduate trainee\" "
                f"OR \"entry level\") {region}"
            ),
            country=region,
        ),
        SearchQuery(
            "local_market",
            f'"{course.name}" employment labour market industry report {region}',
            country=region,
        ),
        SearchQuery(
            "local_challenges",
            (
                f"({occupation_terms}) {region} "
                f"(layoffs OR \"hiring slowdown\" OR \"job losses\" OR "
                f"\"internship shortage\" OR \"entry-level competition\" "
                f"OR unemployment OR \"skills gap\")"
            ),
            ("web", "news"),
            time_range="year",
            country=region,
        ),
        SearchQuery(
            "global_outlook",
            (
                f"({occupation_terms}) employment outlook "
                f"(growth OR decline OR automation OR displacement OR layoffs "
                f"OR \"future demand\" OR skills)"
            ),
            ("web", "news"),
            time_range="year",
        ),
    ]
    queries.append(
        SearchQuery(
            "international_pathways",
            (
                f"({occupation_terms}) from {region} working abroad "
                f"(overseas demand OR migration OR \"skilled visa\" OR licensing "
                f"OR \"remote jobs\" OR \"foreign employers\")"
            ),
        )
    )
    queries.append(
        SearchQuery(
            "further_study",
            (
                f'"{course.name}" graduates {region} (postgraduate OR masters OR PhD '
                f"OR specialisation OR \"higher studies\" OR scholarships) "
                f"career value"
            ),
        )
    )
    # Small, growing specialisations (e.g. carbon assessment for quantity
    # surveying) rarely appear in job or market searches, so ask for them
    # directly. Worldwide: they usually show up abroad first.
    if course.emerging_areas:
        areas = " OR ".join(f'"{area}"' for area in course.emerging_areas[:4])
        emerging_text = (
            f'"{course.name}" ({areas}) (demand OR career OR skills OR training '
            f"OR certification)"
        )
    else:
        emerging_text = (
            f'future of "{course.name}" emerging specialisations niche skills '
            f"(growing demand OR new roles OR certification)"
        )
    queries.append(SearchQuery("emerging_specialisations", emerging_text))
    # Reddit search handles plain keywords better than boolean operators.
    community_terms = (
        f"{course.name} jobs {region}",
        *(f"{term} {region}" for term in course.focus_areas[:2]),
        f"{course.name} masters abroad {region}",
    )
    queries.append(
        SearchQuery(
            "community_signals",
            " | ".join(community_terms),
            (COMMUNITY_SOURCE,),
            community_terms,
        )
    )
    domains = FIELD_SOURCE_DOMAINS.get(course.category, ())
    if domains:
        queries.append(
            SearchQuery(
                "field_sources",
                f'"{course.name}" employment careers {region}',
                include_domains=domains,
            )
        )
    return tuple(queries)
