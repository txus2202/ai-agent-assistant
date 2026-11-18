from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from src.domain.entities.user import User
from src.domain.ports.debate_repository import IDebateRepository
from src.presentation.api.config import get_settings, Settings
from src.presentation.api.dependencies.auth import get_current_user, get_debate_repository

router = APIRouter(prefix="/debates", tags=["history"])


class DebateSummaryDTO(BaseModel):
    id: str
    created_at: str
    user_request: str
    target_agent: str
    status: str
    event_count: int
    total_tokens: int
    has_hitl: bool
    conclusion: str
    agents: List[str] = Field(default_factory=list)


class PaginatedDebatesResponse(BaseModel):
    total: int
    total_all: int
    limit: int
    offset: int
    items: List[DebateSummaryDTO]


def get_debate_repo(settings: Settings = Depends(get_settings)) -> IDebateRepository:
    return get_debate_repository(settings)


@router.get("", response_model=PaginatedDebatesResponse)
def get_all_debates(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(default=None, max_length=200),
    filter: Literal["all", "hitl", "today", "week"] = Query(default="all"),
    repo: IDebateRepository = Depends(get_debate_repo),
    current_user: User = Depends(get_current_user),
) -> PaginatedDebatesResponse:
    """
    Returns paginated lightweight debate summaries for the authenticated user without full event payloads.
    """
    page = repo.find_paginated_summaries(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        search=search,
        filter_by=filter,
    )
    items = [
        DebateSummaryDTO(
            id=s.id,
            created_at=s.created_at.isoformat(),
            user_request=s.user_request,
            target_agent=s.target_agent,
            status=s.status,
            event_count=s.event_count,
            total_tokens=s.total_tokens,
            has_hitl=s.has_hitl,
            conclusion=s.conclusion,
            agents=s.agents,
        )
        for s in page.items
    ]
    return PaginatedDebatesResponse(
        total=page.total,
        total_all=page.total_all,
        limit=page.limit,
        offset=page.offset,
        items=items,
    )

@router.get("/{debate_id}", responses={404: {"description": "Debate not found"}})
def get_debate(
    debate_id: str,
    repo: IDebateRepository = Depends(get_debate_repo),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns a specific debate by ID (strictly restricted to owner user_id).
    """
    r = repo.find_by_id(debate_id, user_id=current_user.id)
    if not r:
        raise HTTPException(status_code=404, detail="Debate not found")
        
    return {
        "id": r.id,
        "created_at": r.created_at.isoformat(),
        "user_request": r.user_request,
        "target_agent": r.target_agent,
        "status": r.status,
        "events": r.events
    }

@router.delete("/{debate_id}", responses={404: {"description": "Debate not found"}})
def delete_debate(
    debate_id: str,
    repo: IDebateRepository = Depends(get_debate_repo),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes a specific debate from history (strictly restricted to owner user_id).
    """
    r = repo.find_by_id(debate_id, user_id=current_user.id)
    if not r:
        raise HTTPException(status_code=404, detail="Debate not found")
    repo.delete(debate_id)
    return {"ok": True}
