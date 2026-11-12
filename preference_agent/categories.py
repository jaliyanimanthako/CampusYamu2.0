"""Interest categories and the owner-reviewed course -> category tags."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAGS = PROJECT_ROOT / "data" / "course_categories.json"


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    description: str
    synonyms: tuple[str, ...] = field(default_factory=tuple)


CATEGORIES: tuple[Category, ...] = (
    Category("engineering", "Engineering & Technology",
             "Designing and building machines, structures, electronics and industrial systems.",
             ("engineering", "engineer", "civil", "mechanical", "electrical", "electronic", "electronics",
              "chemical engineering", "mechatronics", "robotics", "technology", "technical", "machines",
              "manufacturing", "industrial")),
    Category("computing", "Computing & IT",
             "Software, programming, computer science, data, AI and information systems.",
             ("computing", "computer", "computers", "computer science", "it", "ict", "software", "programming",
              "coding", "ai", "artificial intelligence", "data", "data science", "cyber security", "networking",
              "information technology", "information systems", "web", "apps")),
    Category("mathematics", "Mathematics, Statistics & Quantitative Finance",
             "Mathematics, statistics, operations research and mathematical / actuarial finance.",
             ("mathematics", "maths", "math", "statistics", "stats", "actuarial", "numbers", "quantitative",
              "operations research", "applied mathematics", "combined maths")),
    Category("physical_sciences", "Physical & Applied Sciences",
             "Physics, chemistry, earth sciences and applied physical science degrees.",
             ("physics", "chemistry", "science", "physical science", "applied science", "geology",
              "earth science", "materials", "polymer")),
    Category("biological_sciences", "Biological Sciences",
             "Biology, biochemistry, molecular biology and life sciences.",
             ("biology", "bio", "biological science", "life science", "biochemistry", "molecular biology",
              "zoology", "botany", "microbiology", "genetics", "biotechnology")),
    Category("health", "Medicine & Health Sciences",
             "Medicine, dentistry, veterinary science, nursing, pharmacy and allied health professions.",
             ("medicine", "medical", "doctor", "health", "healthcare", "nursing", "nurse", "pharmacy",
              "dental", "dentist", "dentistry", "physiotherapy", "hospital", "veterinary", "vet",
              "radiography", "lab technology", "optometry", "mbbs")),
    Category("indigenous_medicine", "Indigenous Medicine",
             "Ayurveda, Siddha, Unani and other traditional medicine and medicinal resources.",
             ("ayurveda", "indigenous medicine", "traditional medicine", "siddha", "unani", "herbal",
              "native medicine", "yoga")),
    Category("agriculture_environment", "Agriculture, Food, Fisheries & Environment",
             "Agriculture, plantations, food science, animal science, fisheries, marine and environment.",
             ("agriculture", "farming", "agri", "food", "food science", "fisheries", "fish", "marine",
              "ocean", "environment", "environmental", "nature", "animals", "animal science", "plantation",
              "aquatic", "forestry", "nutrition")),
    Category("built_environment", "Architecture, Planning & Built Environment",
             "Architecture, town and urban planning, surveying, quantity surveying, real estate and facilities.",
             ("architecture", "architect", "planning", "town planning", "urban planning", "urban", "city",
              "surveying", "quantity surveying", "construction", "real estate", "buildings", "building",
              "landscape", "property", "gis")),
    Category("design", "Design & Visual Arts",
             "Design, fashion and product design, art and visual arts.",
             ("design", "designing", "art", "arts and design", "drawing", "painting", "fashion", "creative",
              "graphic design", "graphics", "visual arts", "interior design", "product design", "sculpture")),
    Category("performing_arts_media", "Performing Arts, Media & Communication",
             "Music, dance, drama and theatre, film and television, mass media and communication.",
             ("music", "dance", "dancing", "drama", "theatre", "acting", "film", "cinema", "television",
              "media", "mass media", "journalism", "communication", "performing arts", "singing")),
    Category("business", "Business, Management & Finance",
             "Commerce, management, accounting, finance, banking, marketing, HR and entrepreneurship.",
             ("business", "management", "commerce", "accounting", "accountancy", "finance", "banking",
              "marketing", "economics", "entrepreneurship", "hr", "human resource", "insurance",
              "administration", "project management", "logistics")),
    Category("tourism", "Tourism & Hospitality",
             "Tourism, hotel and hospitality, travel and events management.",
             ("tourism", "hospitality", "hotel", "hotels", "travel", "events", "event management")),
    Category("law", "Law", "Legal studies leading to the legal profession.",
             ("law", "lawyer", "legal", "attorney", "llb")),
    Category("languages", "Languages & Translation",
             "Languages, linguistics, translation and English language teaching.",
             ("language", "languages", "english", "linguistics", "translation", "arabic", "literature",
              "sinhala", "tamil", "tesl")),
    Category("humanities", "Humanities & Social Sciences",
             "Arts degrees, social sciences, social work, peace studies, religion and public policy.",
             ("arts", "humanities", "social science", "social sciences", "history", "sociology", "politics",
              "political science", "social work", "philosophy", "religion", "psychology", "geography",
              "peace", "public policy", "archaeology")),
    Category("education_sport", "Education & Sport",
             "Teaching, primary education, physical education and sports science.",
             ("education", "teaching", "teacher", "sport", "sports", "physical education", "coaching",
              "fitness", "sports science")),
)
CATEGORY_BY_ID = {c.id: c for c in CATEGORIES}

# How related two categories are (0 = unrelated, 1 = the same); pairs not listed are 0.
# Used for the offline mismatch mark: Physical Science is a near miss for "engineering",
# Design a clear miss, Dance a complete miss.
CATEGORY_RELATEDNESS: dict[tuple[str, str], float] = {
    ("engineering", "computing"): 0.75, ("engineering", "physical_sciences"): 0.75,
    ("engineering", "mathematics"): 0.7, ("engineering", "built_environment"): 0.6,
    ("engineering", "design"): 0.35, ("engineering", "agriculture_environment"): 0.3,
    ("engineering", "business"): 0.2, ("engineering", "health"): 0.2,
    ("computing", "mathematics"): 0.8, ("computing", "physical_sciences"): 0.5, ("computing", "business"): 0.4,
    ("computing", "design"): 0.3, ("computing", "built_environment"): 0.25,
    ("computing", "performing_arts_media"): 0.15,
    ("mathematics", "physical_sciences"): 0.7, ("mathematics", "business"): 0.45,
    ("physical_sciences", "biological_sciences"): 0.5, ("physical_sciences", "agriculture_environment"): 0.4,
    ("physical_sciences", "health"): 0.3,
    ("biological_sciences", "health"): 0.7, ("biological_sciences", "agriculture_environment"): 0.75,
    ("biological_sciences", "indigenous_medicine"): 0.5,
    ("health", "indigenous_medicine"): 0.7, ("health", "education_sport"): 0.35,
    ("health", "agriculture_environment"): 0.3, ("indigenous_medicine", "agriculture_environment"): 0.35,
    ("agriculture_environment", "business"): 0.3, ("agriculture_environment", "built_environment"): 0.25,
    ("built_environment", "design"): 0.7, ("built_environment", "business"): 0.4,
    ("design", "performing_arts_media"): 0.6, ("design", "business"): 0.25,
    ("performing_arts_media", "languages"): 0.5, ("performing_arts_media", "humanities"): 0.5,
    ("performing_arts_media", "education_sport"): 0.25,
    ("business", "tourism"): 0.7, ("business", "law"): 0.4, ("business", "humanities"): 0.35,
    ("tourism", "languages"): 0.4, ("tourism", "humanities"): 0.3,
    ("law", "humanities"): 0.6, ("law", "languages"): 0.35,
    ("languages", "humanities"): 0.75, ("languages", "education_sport"): 0.45,
    ("humanities", "education_sport"): 0.5, ("humanities", "indigenous_medicine"): 0.2,
}


def relatedness(a: str, b: str) -> float:
    if a == b:
        return 1.0
    return CATEGORY_RELATEDNESS.get((a, b), CATEGORY_RELATEDNESS.get((b, a), 0.0))


@dataclass(frozen=True)
class CourseTags:
    """How close one course is to each category, 1-10 (unlisted categories count as 1)."""

    code: str
    name: str
    marks: dict[str, int]

    @property
    def primary(self) -> str:
        return max(self.marks, key=lambda c: self.marks[c])

    @property
    def secondary(self) -> tuple[str, ...]:
        return tuple(c for c in sorted(self.marks, key=lambda c: -self.marks[c]) if c != self.primary)

    def mark(self, category: str) -> int:
        return self.marks.get(category, 1)


def load_course_tags(path: Path = DEFAULT_TAGS) -> dict[str, CourseTags]:
    """Course code -> category marks, validated against the category list."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tags = {}
    for code, entry in data["courses"].items():
        marks = {c: int(m) for c, m in entry["marks"].items()}
        unknown = [c for c in marks if c not in CATEGORY_BY_ID]
        if unknown:
            raise ValueError(f"{path}: course {code} uses unknown categories {unknown}")
        bad = {c: m for c, m in marks.items() if not 1 <= m <= 10}
        if bad or not marks:
            raise ValueError(f"{path}: course {code} needs marks between 1 and 10, got {entry['marks']}")
        tags[code] = CourseTags(code, entry["name"], marks)
    return tags
