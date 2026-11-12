"""Strict response schema for future-oriented career SWOT analysis."""

FINDING_SCHEMA = {
    "type": "object",
    "properties": {
        # Listed first so the model commits to concrete, course-specific
        # details before writing the finding text.
        "course_specifics": {"type": "array", "items": {"type": "string"}},
        "finding": {"type": "string"},
        "evidence_refs": {"type": "array", "items": {"type": "string"}},
        "reasoning_type": {
            "type": "string",
            "enum": ["direct_evidence", "forward_inference"],
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
    },
    "required": [
        "course_specifics",
        "finding",
        "evidence_refs",
        "reasoning_type",
        "confidence",
    ],
    "additionalProperties": False,
}

THEME_SCHEMA = {
    "type": "object",
    "properties": {
        "theme": {"type": "string"},
        "key_details": {"type": "array", "items": {"type": "string"}},
        "takeaway": {"type": "string"},
        "agreement": {
            "type": "string",
            "enum": ["consistent", "mixed", "single_source"],
        },
        "evidence_refs": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["theme", "key_details", "takeaway", "agreement", "evidence_refs"],
    "additionalProperties": False,
}

FUTURE_SWOT_SCHEMA = {
    "type": "object",
    "properties": {
        # Listed first so the model synthesises across all sources before
        # writing any SWOT finding.
        "evidence_synthesis": {"type": "array", "items": THEME_SCHEMA},
        "course_introduction": {
            "type": "object",
            "properties": {
                "overview": {"type": "string"},
                "career_paths": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string"},
                            "what_you_do": {"type": "string"},
                        },
                        "required": ["role", "what_you_do"],
                        "additionalProperties": False,
                    },
                },
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["overview", "career_paths", "evidence_refs"],
            "additionalProperties": False,
        },
        "future_swot": {
            "type": "object",
            "properties": {
                "strengths": {"type": "array", "items": FINDING_SCHEMA},
                "weaknesses": {"type": "array", "items": FINDING_SCHEMA},
                "opportunities": {"type": "array", "items": FINDING_SCHEMA},
                "threats": {"type": "array", "items": FINDING_SCHEMA},
            },
            "required": ["strengths", "weaknesses", "opportunities", "threats"],
            "additionalProperties": False,
        },
        "local_vs_overseas": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "enum": [
                        "local_stronger",
                        "balanced",
                        "overseas_stronger",
                        "unclear",
                    ],
                },
                "explanation": {"type": "string"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["label", "explanation", "evidence_refs"],
            "additionalProperties": False,
        },
        "further_study": {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "enum": ["essential", "helpful", "optional", "unclear"],
                },
                "explanation": {"type": "string"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["role", "explanation", "evidence_refs"],
            "additionalProperties": False,
        },
        # Small, growing specialisations a student can prepare for early.
        "niche_specialisations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "area": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["area", "why_it_matters", "evidence_refs"],
                "additionalProperties": False,
            },
        },
        "overall_outlook": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "enum": [
                        "very_positive",
                        "positive",
                        "mixed",
                        "cautious",
                        "challenging",
                        "insufficient_evidence",
                    ],
                },
                "summary": {"type": "string"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
                "confidence": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
            },
            "required": ["label", "summary", "evidence_refs", "confidence"],
            "additionalProperties": False,
        },
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "evidence_synthesis",
        "course_introduction",
        "future_swot",
        "local_vs_overseas",
        "further_study",
        "niche_specialisations",
        "overall_outlook",
        "limitations",
    ],
    "additionalProperties": False,
}
