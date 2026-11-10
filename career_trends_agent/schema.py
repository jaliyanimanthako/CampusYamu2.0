"""Firecrawl JSON schema for source-grounded career signals."""

SIGNAL_SCHEMA = {
    "type": "object",
    "properties": {
        "signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "occupation": {"type": "string"},
                    "occupation_code": {"type": ["string", "null"]},
                    "direction": {
                        "type": "string",
                        "enum": ["growing", "declining", "mixed", "uncertain"],
                    },
                    "evidence": {"type": "string"},
                    "metric": {"type": ["string", "null"]},
                    "ai_exposure": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "unknown"],
                    },
                    "skills": {"type": "array", "items": {"type": "string"}},
                    "related_studies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "publication_date": {"type": ["string", "null"]},
                },
                "required": ["occupation", "direction", "evidence"],
            },
        }
    },
    "required": ["signals"],
}
