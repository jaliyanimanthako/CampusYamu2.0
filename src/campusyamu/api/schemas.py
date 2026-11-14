"""Request and response models for the public API (they become the OpenAPI spec at /docs)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SubjectGrade(BaseModel):
    subject: str = Field(examples=["Combined Mathematics"])
    grade: str = Field("", description="A, B, C, S or F; an empty grade is ignored", examples=["A"])


class RecommendationRequest(BaseModel):
    stream: str = Field(min_length=1, description="One of GET /v1/options `streams`", examples=["Physical Science"])
    al: list[SubjectGrade] = Field(description="Exactly three different A/L subjects (from `al_subjects`)")
    ol: list[SubjectGrade] = Field(default_factory=list, description="O/L Science, English, Mathematics")
    cgt: int = Field(ge=0, le=100, description="Common General Test mark (below the pass mark, no course is "
                                               "eligible)", examples=[40])
    z_score: float | None = Field(None, examples=[1.56])
    admission_district: str = Field(min_length=1, description="One of `districts`", examples=["Kandy"])
    ds_division: str = Field(min_length=1, description="Home DS division, from `ds_divisions[district]`",
                             examples=["Gangawata Korale"])
    preferences: str = Field("", max_length=2000, description="Free-text interests",
                             examples=["engineering, design"])
    use_llm: bool = Field(False, description="Use AI to read the preferences (engine: `preference_engine`; "
                                             "needs `llm_available` or `preference_ai_available`)")
    suggestions: int = Field(20, ge=5, le=50, description="Entries per suggestion list")


class RecommendationResponse(BaseModel):
    report: dict[str, Any] = Field(description="Full report: profile, origin, bands, rankings, preferences, ...")
    used_llm: bool


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatCourse(BaseModel):
    """One course row from the recommendations report (send the whole row; extra fields help the answer)."""

    model_config = ConfigDict(extra="allow")
    course_code: str = Field(min_length=1)
    course_name: str = ""


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000, examples=["What are the career prospects?"])
    course: ChatCourse | None = Field(None, description="The course row from the report. Signed in, `uni_code` "
                                                        "is enough: the server takes the row from the saved results")
    uni_code: str | None = Field(None, description="Signed in: the course's UNI code from the saved results",
                                 examples=["008G"])
    student: dict[str, Any] = Field(default_factory=dict,
                                    description="stream, al_results, z_score, admission_district, home, interests")
    history: list[ChatTurn] = Field(default_factory=list, max_length=40,
                                    description="Earlier turns of this course's chat (at most 40)")


class CareerOutlookSummary(BaseModel):
    generated_at: str | None = None
    status: str | None = None
    sources: int = 0
    overall: Any = None


class CareerJob(BaseModel):
    model_config = ConfigDict(extra="allow")
    course: str
    state: Literal["running", "done", "failed"]
    message: str = ""
    started: float | None = None
    finished: float | None = None


class CareerStatus(BaseModel):
    course: str
    available: bool = Field(description="False when the research keys are missing on the server")
    missing_keys: list[str]
    outlook: CareerOutlookSummary | None = Field(None, description="Cached outlook, if research has run")
    job: CareerJob | None = Field(None, description="Background research job; poll until state != running")


class CareerResearchRequest(BaseModel):
    course: str = Field(min_length=1, description="Exact course name", examples=["Quantity Surveying"])


class CareerResearchResponse(CareerStatus):
    message: str


class ChatSource(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    kind: str
    title: str | None = None
    citation: str | None = None
    links: list[Any] | None = None


class Usage(BaseModel):
    used: int = Field(description="Calls today (Sri Lanka time)")
    limit: int = Field(description="Daily limit; 0 = no limit")


class ChatResponse(BaseModel):
    answer: str
    status: Literal["answered", "partly_answered", "not_in_sources", "out_of_scope"] = Field(
        description="out_of_scope: the question was outside the course / selection-process domain and was refused")
    sources: list[ChatSource]
    career_research: bool = Field(description="True when a cached career outlook was used")
    notes: list[str]
    model: str
    career: CareerStatus | None = Field(None, description="Career research status for this course")
    usage: Usage | None = Field(None, description="Chat questions used today (signed in only)")


class Me(BaseModel):
    user_id: str
    usage: dict[str, Usage] = Field(description="Today's use of the paid calls: chat, ai_recommendations, research")


class ChatSummary(BaseModel):
    uni_code: str
    course_code: str
    course_name: str
    university: str
    messages: int
    created_at: str
    updated_at: str = Field(description="Last message")


class StoredMessage(BaseModel):
    seq: int = Field(description="1, 2, 3 ... within the chat; pass the smallest as `before` to page back")
    role: Literal["user", "assistant"]
    content: str
    sources: list[Any] = Field(description="For answers: the sources shown with it")
    created_at: str


class ChatHistory(BaseModel):
    uni_code: str
    course_code: str
    course_name: str
    university: str
    messages: list[StoredMessage] = Field(description="Oldest first")
    has_more: bool = Field(description="Older messages exist: ask again with before=<first seq>")


class SavedResults(BaseModel):
    form: dict[str, Any] = Field(description="The body sent to POST /v1/recommendations (to fill the form again)")
    report: dict[str, Any] = Field(description="The report it returned (show it again)")
    used_llm: bool
    saved_at: str


class Deleted(BaseModel):
    deleted: str


class StreamHint(BaseModel):
    model_config = ConfigDict(extra="allow")
    defaults: list[str]
    source: str


class Options(BaseModel):
    streams: list[str]
    stream_hints: dict[str, StreamHint]
    al_subjects: list[str]
    al_grades: list[str]
    ol_subjects: list[str]
    ol_grades: list[str]
    districts: list[str]
    ds_divisions: dict[str, list[str]]
    llm_available: bool = Field(description="OpenAI configured: course chat and AI feedback work")
    preference_engine: str = Field("openai", description="AI that reads interests: openai | gemini_decision")
    preference_ai_available: bool = Field(False, description="That engine has its key: `use_llm` works")


class Health(BaseModel):
    ok: bool
    version: str
    llm_available: bool


class ErrorResponse(BaseModel):
    errors: list[str]
