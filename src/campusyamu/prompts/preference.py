"""Prompts that read a student's free-text interests (agents.preference)."""

from __future__ import annotations

INTERESTS_SYSTEM = """You help Sri Lankan A/L students choose state-university degree programmes.
Map the student's study interests to the fixed categories given, then mark how close each course is
to each interest.
Rules:
- One entry per distinct interest, in the student's order (first = most preferred).
- For each entry give 1-2 category ids, best fit first. Use only the given ids.
- Add course_codes only when the student names or clearly describes a specific programme from "programmes".
- For each entry, give EVERY course in "courses_to_mark" two marks:
  * mark, 1 to 10, how close it is to that interest: 10 = exactly what the student asked for,
    7-9 = strongly related, 4-6 = partly related, 1-3 = barely related.
  * mismatch, -1 to -10, how far off it is: -1 = on topic, -3 = a near miss (similar subjects and skills),
    -6 = a clear miss, -10 = nothing to do with the interest.
  A course can have a low mark and a mild mismatch (for "engineering", Physical Science: mark 2,
  mismatch -3) or a low mark and a strong mismatch (for "engineering", Design: mark 3, mismatch -7;
  Dance: mark 1, mismatch -10).
  Use each course's category_marks as a guide so marks stay consistent, but judge the specific interest:
  for "fashion", Fashion Design is mark 10, mismatch -1, while Architecture is about mark 3, mismatch -6.
- "anything", "not sure" and similar mean no preference: return no entry for them.
- Put words that are not study interests, or that fit no category, in unmatched (copy the student's words).
- Do not invent interests the student did not express."""


# --- engine gemini_decision (agents.preference.decision) ---------------------------------------
# The shared input, sent once per request: the scale and examples for every question.
DECISION_GUIDE = """A Sri Lankan A/L student is choosing state-university degree programmes.
Each question is about ONE of the student's interests and, where it applies, ONE programme.

Match mark (how close the programme is to the interest), levels 1-10:
  10 = exactly what the student asked for; 7-9 = strongly related; 4-6 = partly related; 1-3 = barely related.
Mismatch (how far off the programme is), levels -10 to -1:
  -1 = on topic; -3 = a near miss (similar subjects and skills); -6 = a clear miss; -10 = nothing to do with it.
The two are separate: a programme can have a low match and a mild mismatch, or a low match and a strong mismatch.
Examples for the interest "engineering": Physical Science = match 2, mismatch -3; Design = match 3, mismatch -7;
Dance = match 1, mismatch -10. For "fashion": Fashion Design = match 10, mismatch -1; Architecture = match 3,
mismatch -6.
Each programme's field marks (field: 1-10) are a guide for consistency, but judge the specific interest.

The student's own words: """

# score levels, lowest -> highest (level index 0..9)
MARK_LEVELS = ["1 barely related", "2", "3", "4 partly related", "5", "6", "7 strongly related", "8", "9",
               "10 exactly what the student asked for"]
MISMATCH_LEVELS = ["-10 nothing to do with the interest", "-9", "-8", "-7", "-6 a clear miss", "-5", "-4",
                   "-3 a near miss", "-2", "-1 on topic"]

INTEREST_TRUE = "a study interest, even if vague or misspelt"
INTEREST_FALSE = "filler words or something unrelated to choosing a degree"
NO_PROGRAMME = "No specific programme: a general field, subject or career"


# The per-question instructions. `phrase` and `course` arrive already quoted ("engineering").
def interest_question(phrase: str) -> str:
    return f"Is {phrase} a study interest: a subject, field, kind of work or degree the student wants to study?"


def category_question(phrase: str) -> str:
    return f"Which field best fits the study interest {phrase}?"


def programme_question(phrase: str) -> str:
    return (f"Does {phrase} name or clearly describe one specific degree programme from the list? "
            "Choose none for a general field (e.g. engineering, medicine, business).")


def mark_question(course: str, phrase: str) -> str:
    return f"Match mark: how close is {course} to the interest {phrase}?"


def mismatch_question(course: str, phrase: str) -> str:
    return f"Mismatch: how far off is {course} from the interest {phrase}?"
