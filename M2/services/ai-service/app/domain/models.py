from pydantic import BaseModel, ConfigDict, field_validator


class Citation(BaseModel):
    model_config = ConfigDict(strict=True)

    article_id: str
    article_number: str
    text_fragment: str


class ResponseMeta(BaseModel):
    model_config = ConfigDict(strict=True)

    request_id: str
    cached: bool
    took_ms: int


class ErrorDetail(BaseModel):
    model_config = ConfigDict(strict=True)

    code: str
    message: str
    details: dict  # type: ignore[type-arg]
    request_id: str


# --- QA ---

class QARequest(BaseModel):
    model_config = ConfigDict(strict=True)

    question: str
    act_id: str | None = None
    top_k: int = 8
    no_cache: bool = False

    @field_validator("top_k")
    @classmethod
    def top_k_max(cls, v: int) -> int:
        if v > 15:
            raise ValueError("top_k cannot exceed 15")
        return v


class QAResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    answer: str
    citations: list[Citation]
    disclaimer: str


# --- Impact ---

class ImpactRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    description: str
    act_id: str | None = None
    top_k: int = 8
    no_cache: bool = False

    @field_validator("top_k")
    @classmethod
    def top_k_max(cls, v: int) -> int:
        if v > 15:
            raise ValueError("top_k cannot exceed 15")
        return v


class ImpactResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    stakeholders_gaining: list[str]
    stakeholders_losing: list[str]
    rationale: str
    citations: list[Citation]
    disclaimer: str


# --- Patent Check ---

class PatentCheckRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    idea_description: str
    top_k: int = 10

    @field_validator("top_k")
    @classmethod
    def top_k_max(cls, v: int) -> int:
        if v > 15:
            raise ValueError("top_k cannot exceed 15")
        return v


class PatentSimilarity(BaseModel):
    model_config = ConfigDict(strict=True)

    patent_id: str
    title: str
    similarity_score: float


class PatentCheckResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    similarity_score: float
    similar_patents: list[PatentSimilarity]
    assessment: str
    disclaimer: str


# --- Trends ---

class TrendsRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    topic: str | None = None
    no_cache: bool = False


class TrendsResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    sentiment: str
    topics: list[str]
    summary: str
    disclaimer: str


# --- Summarize ---

class SummarizeRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    act_id: str
    no_cache: bool = False


class SummarizeResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    summary: str
    disclaimer: str
