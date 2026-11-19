import asyncio
import os
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from src.application.services.llm_provider_registry import LLMProviderRegistry
from src.application.services.learn_from_session import LearnFromSession
from src.application.services.vault_domain_service import VaultDomainService
from src.domain.entities.user import User
from src.domain.exceptions import ProviderNotRegisteredError
from src.domain.ports.agent_config_repository import IAgentConfigRepository
from src.domain.ports.debate_repository import IDebateRepository
from src.domain.ports.document_parser import IDocumentParser
from src.domain.ports.document_store import IDocumentStore
from src.presentation.api.config import get_settings, Settings
from src.presentation.api.dependencies.auth import (
    get_agent_config_repository,
    get_current_user,
    get_debate_repository,
)
from src.presentation.api.dependencies.llm import get_llm_registry
from src.presentation.api.dependencies.rag import get_document_parser, get_document_store

router = APIRouter(prefix="/learning", tags=["learning"])


class LearnSessionRequest(BaseModel):
    session_id: str
    content: str | None = None
    target_domain: str | None = None

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("session_id must not be empty")
        return cleaned


class CreateDomainRequest(BaseModel):
    id: str
    name: str
    description: str = ""


def get_debate_repo(settings: Settings = Depends(get_settings)) -> IDebateRepository:
    return get_debate_repository(settings)


def get_agent_config_repo(settings: Settings = Depends(get_settings)) -> IAgentConfigRepository:
    return get_agent_config_repository(settings)


def _extract_chat_history(repo: IDebateRepository, session_id: str, user_id: str) -> list[dict[str, Any]]:
    record = repo.find_by_id(session_id, user_id=user_id)
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
    agent_config_repo: IAgentConfigRepository,
    settings: Settings,
    user_id: str | None = None,
) -> tuple[str, str]:
    config = agent_config_repo.find_by_role("learning", user_id=user_id)
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
    repo: IDebateRepository = Depends(get_debate_repo),
    agent_config_repo: IAgentConfigRepository = Depends(get_agent_config_repo),
    doc_store: IDocumentStore = Depends(get_document_store),
    document_parser: IDocumentParser = Depends(get_document_parser),
    llm_registry: LLMProviderRegistry = Depends(get_llm_registry),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    chat_history = await asyncio.to_thread(_extract_chat_history, repo, payload.session_id, current_user.id)
    prov_name, mod_name = await asyncio.to_thread(
        _resolve_learning_config, agent_config_repo, settings, current_user.id
    )

    try:
        llm = llm_registry.get(prov_name)
    except ProviderNotRegisteredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    vault_root = Path(settings.vault_root)

    result = await asyncio.to_thread(
        LearnFromSession.run,
        session_id=payload.session_id,
        chat_history=chat_history,
        llm_provider=llm,
        document_store=doc_store,
        vault_root=vault_root,
        solution_content=payload.content,
        model_name=mod_name,
        target_domain=payload.target_domain or "deliberations/sessions",
        document_parser=document_parser,
    )

    if result.errors:
        raise HTTPException(status_code=400, detail="; ".join(result.errors))

    generated_name = str(result.generated_file.name) if result.generated_file else ""
    return {
        "ok": True,
        "generated_file": generated_name,
        "file": generated_name,
        "chunks_ingested": result.ingest_result.chunks_upserted,
    }


@router.get("/domains")
async def list_domains(
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    vault_root = Path(settings.vault_root)
    domains = await asyncio.to_thread(VaultDomainService.list_domains, vault_root)
    return [
        {
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "path": d.path,
            "moc_file": d.moc_file,
            "document_count": d.document_count,
            "is_system": d.is_system,
        }
        for d in domains
    ]


@router.post(
    "/domains",
    status_code=201,
    responses={
        400: {"description": "Validation or path error creating domain"},
    },
)
async def create_domain(
    payload: CreateDomainRequest,
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    clean_domain_id = os.path.basename(payload.id.strip())
    if not clean_domain_id or clean_domain_id != payload.id.strip():
        raise HTTPException(status_code=400, detail="Invalid domain ID: path traversal detected.")

    vault_root = Path(settings.vault_root)
    try:
        domain = await asyncio.to_thread(
            VaultDomainService.create_domain,
            vault_root=vault_root,
            domain_id=clean_domain_id,
            name=payload.name,
            description=payload.description,
        )
        return {
            "id": domain.id,
            "name": domain.name,
            "description": domain.description,
            "path": domain.path,
            "moc_file": domain.moc_file,
            "document_count": domain.document_count,
            "is_system": domain.is_system,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

