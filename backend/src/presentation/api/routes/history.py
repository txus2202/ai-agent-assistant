from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from src.domain.entities.user import User
from src.domain.ports.debate_repository import IDebateRepository
from src.presentation.api.config import get_settings, Settings
from src.presentation.api.dependencies.auth import get_current_user, get_debate_repository

router = APIRouter(prefix="/debates", tags=["history"])

def get_debate_repo(settings: Settings = Depends(get_settings)) -> IDebateRepository:
    return get_debate_repository(settings)

@router.get("")
async def get_all_debates(
    repo: IDebateRepository = Depends(get_debate_repo),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Returns all debate records from history for the authenticated user.
    """
    records = repo.find_all(user_id=current_user.id)
    # Serialize manually because events is a JSON string in DB, we want a list of dicts in API
    result = []
    for r in records:
        result.append({
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "user_request": r.user_request,
            "target_agent": r.target_agent,
            "status": r.status,
            "events": r.events # Already a list of dicts thanks to the setter
        })
    return result

@router.get("/{debate_id}", responses={404: {"description": "Debate not found"}})
async def get_debate(
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
async def delete_debate(
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
