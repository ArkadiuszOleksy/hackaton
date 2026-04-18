from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    article_number: str
    text: str


class LegalActListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sejm_id: str
    title: str
    status: str | None
    kadencja: int | None
    published_at: datetime | None
    source_url: str | None


class LegalActDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sejm_id: str
    title: str
    status: str | None
    kadencja: int | None
    published_at: datetime | None
    source_url: str | None
    full_text: str | None
    articles: list[ArticleOut]


class ArticleSearchItemOut(BaseModel):
    id: UUID
    act_id: UUID
    act_title: str
    article_number: str
    text: str
    score: int


class PatentSearchItemOut(BaseModel):
    id: UUID
    uprp_id: str
    title: str
    abstract: str
    source_url: str | None
    filed_at: datetime | None
    score: int


class NewsItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_name: str
    title: str
    link: str
    published_at: datetime | None
    summary: str | None


class EtlRunOut(BaseModel):
    status: str
    inserted: bool | None = None
    message: str
    legal_act_id: str | None = None
    articles_inserted: int | None = None


class EliImportOut(BaseModel):
    status: str
    publisher: str
    year: int
    limit: int
    with_text: bool
    processed: int
    imported: int
    updated: int
    skipped: int
    positions: list[int]
    text_saved: int | None = None


class RssSourceRunOut(BaseModel):
    source_name: str
    source_url: str
    fetched: int
    imported: int
    skipped: int
    error: str | None = None


class RssImportOut(BaseModel):
    status: str
    sources: list[RssSourceRunOut]
    imported: int
    skipped: int
    errors: int


class ArticlesBackfillOut(BaseModel):
    status: str
    processed: int
    updated_acts: int
    inserted_articles: int
    skipped: int
    act_ids: list[str]


class PatentSeedOut(BaseModel):
    status: str
    inserted: int
    skipped: int


class LegalActsListResponse(BaseModel):
    data: list[LegalActListItemOut]


class LegalActDetailResponse(BaseModel):
    data: LegalActDetailOut


class ArticleSearchResponse(BaseModel):
    data: list[ArticleSearchItemOut]


class PatentSearchResponse(BaseModel):
    data: list[PatentSearchItemOut]


class NewsSourcesResponse(BaseModel):
    data: list[NewsItemOut]


class EtlRunResponse(BaseModel):
    data: EtlRunOut


class EliImportResponse(BaseModel):
    data: EliImportOut


class RssImportResponse(BaseModel):
    data: RssImportOut


class ArticlesBackfillResponse(BaseModel):
    data: ArticlesBackfillOut


class PatentSeedResponse(BaseModel):
    data: PatentSeedOut