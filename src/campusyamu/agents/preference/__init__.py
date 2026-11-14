"""Preference categorizer: group a student's eligible courses by what they like to study."""

from .categories import CATEGORIES, CATEGORY_BY_ID, DEFAULT_TAGS, load_course_tags
from .categorizer import categorize
from .decision import GeminiDecisionInterpreter
from .interpreter import (ENGINES, Interpretation, KeywordInterpreter, LLMInterpreter, Preference,
                          PreferenceInterpreter, engine_available, preference_engine)

__all__ = ["CATEGORIES", "CATEGORY_BY_ID", "DEFAULT_TAGS", "load_course_tags", "categorize", "Interpretation",
           "KeywordInterpreter", "LLMInterpreter", "GeminiDecisionInterpreter", "Preference",
           "PreferenceInterpreter", "ENGINES", "engine_available", "preference_engine"]
