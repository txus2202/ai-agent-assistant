from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from src.domain.value_objects.debate_record import DebateRecord
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository
from src.presentation.api.config import get_settings, Settings

router = APIRouter(prefix="/debates", tags=["history"])

def get_debate_repo(settings: Settings = Depends(get_settings)) -> SqliteDebateRepository:
    return SqliteDebateRepository(str(settings.sqlite_db_path))

@router.get("")
async def get_all_debates(repo: SqliteDebateRepository = Depends(get_debate_repo)) -> List[Dict[str, Any]]:
    """
    Returns all debate records from history.
    """
    records = repo.find_all()
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

@router.get("/{debate_id}")
async def get_debate(debate_id: str, repo: SqliteDebateRepository = Depends(get_debate_repo)) -> Dict[str, Any]:
    """
    Returns a specific debate by ID.
    """
    r = repo.find_by_id(debate_id)
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

@router.delete("/{debate_id}")
async def delete_debate(debate_id: str, repo: SqliteDebateRepository = Depends(get_debate_repo)):
    """
    Deletes a specific debate from history.
    """
    repo.delete(debate_id)
    return {"ok": True}
