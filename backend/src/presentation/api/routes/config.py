from typing import Annotated, List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.domain.agents.sub_agent_profiles import get_all_profiles, get_profile
from src.domain.entities.user import User
from src.domain.ports.agent_config_repository import IAgentConfigRepository
from src.domain.value_objects.agent_config import AgentConfig
from src.presentation.api.config import get_settings, Settings
from src.presentation.api.dependencies.auth import get_agent_config_repository, get_current_user

router = APIRouter(prefix="/config", tags=["config"])

class AgentConfigUpdate(BaseModel):
    provider: str
    model_name: str

def get_config_repo(settings: Annotated[Settings, Depends(get_settings)]) -> IAgentConfigRepository:
    return get_agent_config_repository(settings)

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
    default_provider: str,
    default_model: str,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    role_value = profile.id
    config = repo.find_by_role(role_value, user_id=user_id) or repo.find_by_role(profile.display_name, user_id=user_id)

    return {
        "id": role_value,
        "name": profile.display_name,
        "description": profile.description,
        "color_hex": profile.color_hex,
        "provider": config.provider if config else default_provider,
        "model_name": config.model_name if config else default_model,
        "uses_rag": profile.uses_rag,
        "supports_hitl": profile.supports_hitl,
        "can_ingest_documents": profile.can_ingest_documents,
        "topology_roles": _extract_topology_roles(profile, top),
        "tools": list(getattr(profile, "tools", ())),
    }


@router.get("/agents")
async def get_agents_config(
    repo: Annotated[IAgentConfigRepository, Depends(get_config_repo)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> List[Dict[str, Any]]:
    """
    Devuelve la lista de agentes disponibles en el sistema con su nombre, descripción, proveedor, modelo y capacidades configuradas para el usuario autenticado.
    """
    settings = get_settings()
    from src.domain.agents.debate_topology import load_topology
    top = load_topology()

    return [
        _build_agent_item(profile, top, repo, settings.default_provider, settings.default_model, user_id=current_user.id)
        for profile in get_all_profiles()
    ]

@router.get(
    "/agents/{role}",
    responses={
        404: {"description": "Agent role not found"}
    }
)
async def get_agent_config(
    role: str,
    repo: Annotated[IAgentConfigRepository, Depends(get_config_repo)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Dict[str, str]:
    """
    Obtiene la configuración (nombre, descripción, proveedor y modelo) de un agente específico para el usuario autenticado.
    """
    try:
        profile = get_profile(role)
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent role not found")

    settings = get_settings()
    config = repo.find_by_role(profile.id, user_id=current_user.id)
    if not config:
        config = repo.find_by_role(profile.display_name, user_id=current_user.id)
    
    return {
        "id": profile.id,
        "name": profile.display_name,
        "description": profile.description,
        "color_hex": profile.color_hex,
        "provider": config.provider if config else settings.default_provider,
        "model_name": config.model_name if config else settings.default_model
    }

@router.put(
    "/agents/{role}",
    responses={
        404: {"description": "Agent role not found"}
    }
)
async def update_agent_config(
    role: str, 
    update: AgentConfigUpdate, 
    repo: Annotated[IAgentConfigRepository, Depends(get_config_repo)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Actualiza la configuración (proveedor y modelo) de un agente específico para el usuario autenticado.
    """
    try:
        profile = get_profile(role)
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent role not found")

    config = AgentConfig(
        role=profile.id,
        provider=update.provider,
        model_name=update.model_name,
        user_id=current_user.id,
    )
    repo.save(config)
    return {"ok": True}


@router.get("/topology")
async def get_topology(
    current_user: Annotated[User, Depends(get_current_user)],
) -> Dict[str, Any]:
    """
    Devuelve la topología de roles y asignación de agentes configurada en topology.yaml.
    """
    from src.domain.agents.debate_topology import load_topology
    top = load_topology()
    return {
        "project_name": top.project_name,
        "project_description": top.project_description,
        "supervisor": top.supervisor,
        "interpreters": list(top.interpreters),
        "proposers": list(top.proposers),
        "reviewers": list(top.reviewers),
        "evaluators": list(top.evaluators),
        "implementers": list(top.implementers),
    }

