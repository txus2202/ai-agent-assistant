from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.application.services.learn_from_session import LearnFromSession
from src.infrastructure.persistence.sqlite_agent_config_repository import SqliteAgentConfigRepository
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository
from src.infrastructure.rag.chroma_document_store import ChromaDBDocumentStore
from src.infrastructure.llm.registry import get_llm_provider


from src.presentation.api.config import get_settings, Settings

router = APIRouter(prefix="/learning", tags=["learning"])


class LearnSessionRequest(BaseModel):
    session_id: str
    content: str | None = None


def get_debate_repo(settings: Settings = Depends(get_settings)) -> SqliteDebateRepository:
    return SqliteDebateRepository(str(settings.sqlite_db_path))


def get_agent_config_repo(settings: Settings = Depends(get_settings)) -> SqliteAgentConfigRepository:
    return SqliteAgentConfigRepository(str(settings.sqlite_db_path))


def _extract_chat_history(repo: SqliteDebateRepository, session_id: str) -> list[dict[str, Any]]:
    record = repo.find_by_id(session_id)
    if not record or not record.events:
        return []
    history: list[dict[str, Any]] = []
    for ev in record.events:
        ev_type = ev.get("type")
        if ev_type in ("user_message", "message", "agent_completed"):
            history.append({
                "role": "user" if ev_type == "user_message" else "assistant",
                "agent": ev.get("role") or ev.get("metadata", {}).get("agent_name"),
                "content": ev.get("content", ""),
            })
    return history


def _resolve_learning_config(
    agent_config_repo: SqliteAgentConfigRepository,
    settings: Settings,
) -> tuple[str, str]:
    config = agent_config_repo.find_by_role("learning")
    prov_name = config.provider if config else settings.default_provider
    mod_name = config.model_name if config else settings.default_model
    return prov_name, mod_name


@router.post(
    "/session",
    responses={
        400: {"description": "Learning session failed or invalid content"}
    },
)
async def learn_session(
    payload: LearnSessionRequest,
    settings: Settings = Depends(get_settings),
    repo: SqliteDebateRepository = Depends(get_debate_repo),
    agent_config_repo: SqliteAgentConfigRepository = Depends(get_agent_config_repo),
) -> Dict[str, Any]:
    chat_history = _extract_chat_history(repo, payload.session_id)
    prov_name, mod_name = _resolve_learning_config(agent_config_repo, settings)

    llm = get_llm_provider(prov_name)
    vault_root = Path(settings.vault_root)
    store_kwargs: dict[str, Any] = {}
    if settings.chroma_host:
        store_kwargs["host"] = settings.chroma_host
        store_kwargs["port"] = settings.chroma_port
    doc_store = ChromaDBDocumentStore(
        persist_directory=str(settings.chroma_persist_dir),
        **store_kwargs,
    )

    result = LearnFromSession.run(
        session_id=payload.session_id,
        chat_history=chat_history,
        llm_provider=llm,
        document_store=doc_store,
        vault_root=vault_root,
        solution_content=payload.content,
        model_name=mod_name,
    )

    if result.errors:
        raise HTTPException(status_code=400, detail="; ".join(result.errors))

    return {
        "ok": True,
        "file": str(result.generated_file.name) if result.generated_file else "",
        "chunks_ingested": result.ingest_result.chunks_upserted,
    }
