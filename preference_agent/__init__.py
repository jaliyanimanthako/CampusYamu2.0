"""Preference categorizer: group a student's eligible courses by what they like to study."""

from .categories import CATEGORIES, CATEGORY_BY_ID, DEFAULT_TAGS, load_course_tags
from .categorizer import categorize
from .interpreter import (Interpretation, KeywordInterpreter, LLMInterpreter, Preference,
                          PreferenceInterpreter)

__all__ = ["CATEGORIES", "CATEGORY_BY_ID", "DEFAULT_TAGS", "load_course_tags", "categorize", "Interpretation",
           "KeywordInterpreter", "LLMInterpreter", "Preference", "PreferenceInterpreter"]
