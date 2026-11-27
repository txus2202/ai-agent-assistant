from typing import Annotated, List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.application.services.user_topology_service import (
    ResolvedUserTopology,
    UserTopologyService,
)
from src.domain.entities.user import User
from src.domain.ports.agent_catalog_repository import IAgentCatalogRepository
from src.domain.ports.agent_config_repository import IAgentConfigRepository
from src.domain.value_objects.agent_config import AgentConfig
from src.presentation.api.config import get_settings, Settings
from src.presentation.api.dependencies.agents import (
    get_agent_catalog,
    get_user_topology_service,
    resolve_effective_settings,
    resolve_fallback_review_rounds,
)
from src.presentation.api.dependencies.auth import (
    get_agent_config_repository,
    get_current_user,
    get_current_user_optional,
)

router = APIRouter(prefix="/config", tags=["config"])


class AgentConfigUpdate(BaseModel):
    provider: str
    model_name: str
    rag_top_k: Optional[int] = Field(default=None, ge=0, le=50)
    rag_min_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class TopologyUpdatePayload(BaseModel):
    supervisor: Optional[str] = None
    interpreters: List[str] = Field(default_factory=list)
    proposers: List[str] = Field(default_factory=list)
    reviewers: List[str] = Field(default_factory=list)
    evaluators: List[str] = Field(default_factory=list)
    implementers: List[str] = Field(default_factory=list)
    review_rounds: int = Field(default=1, ge=0, le=5)


def get_config_repo(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> IAgentConfigRepository:
    effective_settings = resolve_effective_settings(request, settings)
    return get_agent_config_repository(effective_settings)


def resolve_optional_topology_user(
    request: Request,
    optional_user: Annotated[Optional[User], Depends(get_current_user_optional)],
) -> Optional[User]:
    """Resolve authenticated operator when present without rejecting unauthenticated public reads."""
    if optional_user is not None:
        return optional_user
    override = request.app.dependency_overrides.get(get_current_user)
    if callable(override):
        resolved: Optional[User] = override()
        return resolved
    return None


def _extract_topology_roles(profile: Any, top: Any) -> list[str]:
    top_roles: list[str] = []
    identifiers = {profile.display_name, profile.id}

    if (
        identifiers.intersection({top.supervisor, "supervisor"})
        or getattr(profile, "is_supervisor", False)
    ):
        top_roles.append("supervisor")

    slot_mappings = (
        (top.interpreters, "interpreter"),
        (top.proposers, "proposer"),
        (top.reviewers, "reviewer"),
        (top.evaluators, "evaluator"),
        (top.implementers, "implementer"),
    )
    for slot_agents, role_name in slot_mappings:
        if identifiers.intersection(slot_agents):
            top_roles.append(role_name)

    return top_roles


def _build_agent_item(
    profile: Any,
    top: Any,
    repo: IAgentConfigRepository,
    default_rag_top_k: int = 5,
    default_rag_min_score: float = 0.30,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    role_value = profile.id
    config = repo.find_by_role(role_value, user_id=user_id) or repo.find_by_role(profile.display_name, user_id=user_id)

    default_prov = getattr(profile, "default_provider", "") or ""
    default_mod = getattr(profile, "default_model", "") or ""

    return {
        "id": role_value,
        "name": profile.display_name,
        "description": profile.description,
        "color_hex": profile.color_hex,
        "provider": config.provider if (config and config.provider) else default_prov,
        "model_name": config.model_name if (config and config.model_name) else default_mod,
        "rag_top_k": config.rag_top_k if (config and config.rag_top_k is not None) else default_rag_top_k,
        "rag_min_score": config.rag_min_score if (config and config.rag_min_score is not None) else default_rag_min_score,
        "uses_rag": profile.uses_rag,
        "supports_hitl": profile.supports_hitl,
        "can_ingest_documents": profile.can_ingest_documents,
        "topology_roles": _extract_topology_roles(profile, top),
        "tools": list(getattr(profile, "tools", ())),
    }


def _serialize_topology_response(
    resolved: ResolvedUserTopology,
    agent_catalog: IAgentCatalogRepository,
    user_topology_service: UserTopologyService,
) -> dict[str, Any]:
    top = resolved.topology
    supervisor_info: dict[str, Any] | None = None
    try:
        sup_profile = agent_catalog.get_profile(top.supervisor)
        supervisor_info = {
            "id": sup_profile.id,
            "name": sup_profile.display_name,
            "description": sup_profile.description,
            "color_hex": sup_profile.color_hex,
        }
    except KeyError:
        supervisor_info = {
            "id": top.supervisor,
            "name": top.supervisor,
            "description": "",
            "color_hex": "#f59e0b",
        }

    eligible_agents = [
        {
            "id": profile.id,
            "name": profile.display_name,
            "description": profile.description,
            "color_hex": profile.color_hex,
            "uses_rag": profile.uses_rag,
            "supports_hitl": profile.supports_hitl,
        }
        for profile in user_topology_service.get_eligible_profiles()
    ]

    return {
        "project_name": top.project_name,
        "project_description": top.project_description,
        "supervisor": top.supervisor,
        "interpreters": list(top.interpreters),
        "proposers": list(top.proposers),
        "reviewers": list(top.reviewers),
        "evaluators": list(top.evaluators),
        "implementers": list(top.implementers),
        "review_rounds": resolved.review_rounds,
        "is_customized": resolved.is_customized,
        "supervisor_agent": supervisor_info,
        "eligible_agents": eligible_agents,
    }


@router.get("/agents")
def get_agents_config(
    request: Request,
    repo: Annotated[IAgentConfigRepository, Depends(get_config_repo)],
    current_user: Annotated[User, Depends(get_current_user)],
    agent_catalog: Annotated[IAgentCatalogRepository, Depends(get_agent_catalog)],
    user_topology_service: Annotated[UserTopologyService, Depends(get_user_topology_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> List[Dict[str, Any]]:
    """Return all registered agents with effective provider, model, RAG, and topology roles for the authenticated user."""
    effective_settings = resolve_effective_settings(request, settings)
    resolved_topology = user_topology_service.resolve_for_user(
        current_user.id,
        fallback_review_rounds=resolve_fallback_review_rounds(effective_settings),
    )

    return [
        _build_agent_item(
            profile,
            resolved_topology.topology,
            repo,
            default_rag_top_k=effective_settings.rag_top_k,
            default_rag_min_score=effective_settings.rag_min_score,
            user_id=current_user.id,
        )
        for profile in agent_catalog.get_all_profiles()
    ]


@router.get(
    "/agents/{role}",
    responses={
        404: {"description": "Agent role not found"}
    },
)
def get_agent_config(
    role: str,
    request: Request,
    repo: Annotated[IAgentConfigRepository, Depends(get_config_repo)],
    current_user: Annotated[User, Depends(get_current_user)],
    agent_catalog: Annotated[IAgentCatalogRepository, Depends(get_agent_catalog)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Dict[str, Any]:
    """Return effective configuration for a single agent scoped to the authenticated user."""
    try:
        profile = agent_catalog.get_profile(role)
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent role not found")

    effective_settings = resolve_effective_settings(request, settings)
    config = repo.find_by_role(profile.id, user_id=current_user.id)
    if not config:
        config = repo.find_by_role(profile.display_name, user_id=current_user.id)

    default_prov = getattr(profile, "default_provider", "") or ""
    default_mod = getattr(profile, "default_model", "") or ""

    return {
        "id": profile.id,
        "name": profile.display_name,
        "description": profile.description,
        "color_hex": profile.color_hex,
        "provider": config.provider if (config and config.provider) else default_prov,
        "model_name": config.model_name if (config and config.model_name) else default_mod,
        "rag_top_k": config.rag_top_k if (config and config.rag_top_k is not None) else effective_settings.rag_top_k,
        "rag_min_score": config.rag_min_score if (config and config.rag_min_score is not None) else effective_settings.rag_min_score,
    }


@router.put(
    "/agents/{role}",
    responses={
        404: {"description": "Agent role not found"}
    },
)
def update_agent_config(
    role: str,
    update: AgentConfigUpdate,
    repo: Annotated[IAgentConfigRepository, Depends(get_config_repo)],
    current_user: Annotated[User, Depends(get_current_user)],
    agent_catalog: Annotated[IAgentCatalogRepository, Depends(get_agent_catalog)],
) -> Dict[str, bool]:
    """Update provider, model, and RAG retrieval settings for a single agent scoped to the authenticated user."""
    try:
        profile = agent_catalog.get_profile(role)
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent role not found")

    existing = repo.find_by_role(profile.id, user_id=current_user.id)

    rag_top_k = update.rag_top_k
    if rag_top_k is None and existing:
        rag_top_k = existing.rag_top_k

    rag_min_score = update.rag_min_score
    if rag_min_score is None and existing:
        rag_min_score = existing.rag_min_score

    config = AgentConfig(
        role=profile.id,
        provider=update.provider,
        model_name=update.model_name,
        user_id=current_user.id,
        rag_top_k=rag_top_k,
        rag_min_score=rag_min_score,
    )
    repo.save(config)
    return {"ok": True}


@router.get("/topology")
def get_topology(
    request: Request,
    optional_user: Annotated[Optional[User], Depends(resolve_optional_topology_user)],
    agent_catalog: Annotated[IAgentCatalogRepository, Depends(get_agent_catalog)],
    user_topology_service: Annotated[UserTopologyService, Depends(get_user_topology_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Dict[str, Any]:
    """Return effective debate topology (user preference when authenticated, canonical topology.yaml otherwise)."""
    effective_settings = resolve_effective_settings(request, settings)
    user_id = optional_user.id if optional_user is not None else None
    resolved = user_topology_service.resolve_for_user(
        user_id,
        fallback_review_rounds=resolve_fallback_review_rounds(effective_settings),
    )
    return _serialize_topology_response(resolved, agent_catalog, user_topology_service)


@router.put(
    "/topology",
    responses={
        422: {"description": "Invalid debate topology or review_rounds configuration"},
    },
)
def update_topology(
    payload: TopologyUpdatePayload,
    current_user: Annotated[User, Depends(get_current_user)],
    agent_catalog: Annotated[IAgentCatalogRepository, Depends(get_agent_catalog)],
    user_topology_service: Annotated[UserTopologyService, Depends(get_user_topology_service)],
) -> Dict[str, Any]:
    """Validate and persist a custom debate topology and review_rounds for the authenticated user."""
    try:
        resolved = user_topology_service.save_for_user(
            current_user.id,
            interpreters=payload.interpreters,
            proposers=payload.proposers,
            reviewers=payload.reviewers,
            evaluators=payload.evaluators,
            implementers=payload.implementers,
            review_rounds=payload.review_rounds,
            supervisor=payload.supervisor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _serialize_topology_response(resolved, agent_catalog, user_topology_service)


@router.delete("/topology")
def reset_topology(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    agent_catalog: Annotated[IAgentCatalogRepository, Depends(get_agent_catalog)],
    user_topology_service: Annotated[UserTopologyService, Depends(get_user_topology_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Dict[str, Any]:
    """Delete the authenticated user's custom topology so canonical topology.yaml defaults apply."""
    effective_settings = resolve_effective_settings(request, settings)
    resolved = user_topology_service.reset_for_user(
        current_user.id,
        fallback_review_rounds=resolve_fallback_review_rounds(effective_settings),
    )
    return _serialize_topology_response(resolved, agent_catalog, user_topology_service)
