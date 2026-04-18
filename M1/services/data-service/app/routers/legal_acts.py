from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import LegalAct
from app.schemas import LegalActDetailResponse, LegalActsListResponse

router = APIRouter(tags=["legal-acts"])


@router.get("/legal-acts", response_model=LegalActsListResponse)
def list_legal_acts(
    kadencja: int | None = Query(default=None),
    status_value: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(LegalAct).order_by(
        LegalAct.published_at.desc().nullslast(),
        LegalAct.created_at.desc(),
    )

    if kadencja is not None:
        stmt = stmt.where(LegalAct.kadencja == kadencja)

    if status_value is not None:
        stmt = stmt.where(LegalAct.status == status_value)

    stmt = stmt.limit(limit)

    acts = db.execute(stmt).scalars().all()
    return {"data": acts}


@router.get("/legal-acts/{act_id}", response_model=LegalActDetailResponse)
def get_legal_act(
    act_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    stmt = (
        select(LegalAct)
        .options(selectinload(LegalAct.articles))
        .where(LegalAct.id == act_id)
    )

    act = db.execute(stmt).scalar_one_or_none()

    if act is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Legal act '{act_id}' not found.",
        )

    return {"data": act}