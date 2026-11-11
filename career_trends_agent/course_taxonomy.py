"""Deterministic course-to-occupation search vocabulary."""

from __future__ import annotations

from .models import CourseProfile


OCCUPATIONS = {
    "medicine": (
        "medical officer", "general practitioner", "clinical researcher",
        "public health officer", "health informatics specialist",
    ),
    "allied_health": (
        "medical laboratory scientist", "radiographer", "physiotherapist",
        "occupational therapist", "health promotion officer",
    ),
    "nursing": (
        "registered nurse", "nursing officer", "clinical nurse",
        "community health nurse", "nurse educator",
    ),
    "dentistry": (
        "dental surgeon", "dentist", "dental officer", "oral health researcher",
    ),
    "veterinary": (
        "veterinary surgeon", "veterinary officer", "livestock health officer",
        "animal health researcher",
    ),
    "engineering": (
        "civil engineer", "mechanical engineer", "electrical engineer",
        "electronics engineer", "chemical engineer", "materials engineer",
    ),
    "information_technology": (
        "software engineer", "cybersecurity analyst", "cloud engineer",
        "data engineer", "network engineer", "systems analyst",
    ),
    "applied_science": (
        "environmental scientist", "biotechnologist", "laboratory analyst",
        "industrial chemist", "materials scientist", "quality assurance analyst",
    ),
    "agriculture": (
        "agricultural officer", "agronomist", "agribusiness executive",
        "crop specialist", "agricultural research officer", "extension officer",
    ),
    "food_science": (
        "food technologist", "food scientist", "quality assurance officer",
        "food production officer", "product development technologist",
    ),
    "geography": (
        "GIS analyst", "remote sensing analyst", "spatial data analyst",
        "disaster management officer", "environmental consultant",
    ),
    "management": (
        "management trainee", "business analyst", "human resources executive",
        "operations executive", "supply chain executive", "project coordinator",
    ),
    "finance": (
        "accountant", "auditor", "financial analyst", "banking officer",
        "risk analyst", "investment analyst",
    ),
    "law": (
        "attorney at law", "legal officer", "compliance officer",
        "legal researcher", "corporate legal executive",
    ),
    "built_environment": (
        "architect", "quantity surveyor", "urban planner", "construction manager",
        "facilities manager", "valuation officer",
    ),
    "tourism": (
        "hotel manager", "tourism officer", "travel consultant",
        "events executive", "hospitality operations executive",
    ),
    "education": (
        "teacher", "education officer", "curriculum developer",
        "education researcher", "lecturer",
    ),
    "environment": (
        "environmental officer", "sustainability officer", "forestry officer",
        "conservation officer", "environmental consultant",
    ),
    "social_science": (
        "research officer", "policy analyst", "project officer",
        "development officer", "social worker", "programme coordinator",
    ),
    "arts_communication": (
        "communications officer", "content writer", "translator",
        "media officer", "administrative officer", "teacher",
    ),
}

ALIASES = {
    "it": "information_technology",
    "ict": "information_technology",
    "information technology": "information_technology",
    "applied science": "applied_science",
    "applied sciences": "applied_science",
}

# Order matters: specific regulated and interdisciplinary fields come first.
KEYWORD_RULES = (
    (("dental",), "dentistry"),
    (("veterinary",), "veterinary"),
    (("nursing",), "nursing"),
    (("pharmacy", "physiotherapy", "radiography", "medical laboratory",
      "medical imaging", "occupational therapy", "optometry", "health promotion",
      "speech and hearing", "speech & hearing"), "allied_health"),
    (("medicine", "medical"), "medicine"),
    (("law",), "law"),
    (("architecture", "quantity surveying", "town & country planning",
      "town and country planning", "urban informatics", "facilities management",
      "estate management", "real estate", "surveying science"), "built_environment"),
    (("food science", "food production", "food business"), "food_science"),
    (("agriculture", "agri business", "agribusiness", "animal science",
      "plantation", "export agriculture"), "agriculture"),
    (("geograph", "geographical information", "gis"), "geography"),
    (("environment", "forestry", "natural resources", "green technology"), "environment"),
    (("tourism", "hospitality",), "tourism"),
    (("teaching", "education",), "education"),
    (("accounting", "finance", "banking", "economics", "commerce", "business science"), "finance"),
    (("computer", "software", "information technology", "information system",
      "information communication technology", "data science", "artificial intelligence"),
     "information_technology"),
    (("engineering",), "engineering"),
    (("applied science", "chemistry", "biological science", "physical science",
      "biochemistry", "molecular biology", "science and technology"), "applied_science"),
    (("social work", "peace & conflict", "peace and conflict", "social studies"), "social_science"),
    (("arts", "language", "communication studies", "translation", "media",
      "film & television", "film and television"), "arts_communication"),
    (("management", "entrepreneurship", "project management", "logistics"), "management"),
)


def profile_for(course: str) -> CourseProfile:
    """Map a course to job-title terms, with an explicit fallback."""

    normalized = " ".join(course.casefold().split())
    category = ALIASES.get(normalized)
    if not category:
        category = next(
            (
                candidate
                for keywords, candidate in KEYWORD_RULES
                if any(keyword in normalized for keyword in keywords)
            ),
            None,
        )
    if category:
        return CourseProfile(course, category, OCCUPATIONS[category], True)
    return CourseProfile(course, "unmapped", (course,), False)
