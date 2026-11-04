from typing import Annotated, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.domain.agents.sub_agent_profiles import get_all_profiles, get_profile
from src.domain.value_objects.agent_config import AgentConfig
from src.infrastructure.persistence.sqlite_agent_config_repository import SqliteAgentConfigRepository
from src.presentation.api.config import get_settings, Settings

router = APIRouter(prefix="/config", tags=["config"])

class AgentConfigUpdate(BaseModel):
    provider: str
    model_name: str

def get_config_repo(settings: Annotated[Settings, Depends(get_settings)]) -> SqliteAgentConfigRepository:
    return SqliteAgentConfigRepository(str(settings.sqlite_db_path))

@router.get("/agents")
async def get_agents_config(repo: Annotated[SqliteAgentConfigRepository, Depends(get_config_repo)]) -> List[Dict[str, Any]]:
    """
    Devuelve la lista de agentes disponibles en el sistema con su nombre, descripción, proveedor, modelo y capacidades configuradas.
    """
    settings = get_settings()
    from src.domain.agents.debate_topology import load_topology
    top = load_topology()
    
    result = []
    for profile in get_all_profiles():
        role_value = profile.id
        config = repo.find_by_role(role_value)
        if not config:
            config = repo.find_by_role(profile.display_name)
        
        top_roles = []
        if profile.display_name == top.supervisor or profile.id == top.supervisor or getattr(profile, "is_supervisor", False) or role_value == "supervisor":
            top_roles.append("supervisor")
        if profile.display_name in top.interpreters or profile.id in top.interpreters:
            top_roles.append("interpreter")
        if profile.display_name in top.proposers or profile.id in top.proposers:
            top_roles.append("proposer")
        if profile.display_name in top.reviewers or profile.id in top.reviewers:
            top_roles.append("reviewer")
        if profile.display_name in top.evaluators or profile.id in top.evaluators:
            top_roles.append("evaluator")
        if profile.display_name in top.implementers or profile.id in top.implementers:
            top_roles.append("implementer")

        result.append({
            "id": role_value,
            "name": profile.display_name,
            "description": profile.description,
            "color_hex": profile.color_hex,
            "provider": config.provider if config else settings.default_provider,
            "model_name": config.model_name if config else settings.default_model,
            "uses_rag": profile.uses_rag,
            "supports_hitl": profile.supports_hitl,
            "can_ingest_documents": profile.can_ingest_documents,
            "topology_roles": top_roles,
        })
    return result

@router.get(
    "/agents/{role}",
    responses={
        404: {"description": "Agent role not found"}
    }
)
async def get_agent_config(
    role: str,
    repo: Annotated[SqliteAgentConfigRepository, Depends(get_config_repo)]
) -> Dict[str, str]:
    """
    Obtiene la configuración (nombre, descripción, proveedor y modelo) de un agente específico.
    """
    try:
        profile = get_profile(role)
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent role not found")

    settings = get_settings()
    config = repo.find_by_role(profile.id)
    if not config:
        config = repo.find_by_role(profile.display_name)
    
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
    repo: Annotated[SqliteAgentConfigRepository, Depends(get_config_repo)]
):
    """
    Actualiza la configuración (proveedor y modelo) de un agente específico.
    """
    try:
        profile = get_profile(role)
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent role not found")

    config = AgentConfig(
        role=profile.id,
        provider=update.provider,
        model_name=update.model_name
    )
    repo.save(config)
    return {"ok": True}


@router.get("/topology")
async def get_topology() -> Dict[str, Any]:
    """
    Devuelve la topología de roles y asignación de agentes configurada en topology.yaml.
    """
    from src.domain.agents.debate_topology import load_topology
    top = load_topology()
    return {
        "supervisor": top.supervisor,
        "interpreters": list(top.interpreters),
        "proposers": list(top.proposers),
        "reviewers": list(top.reviewers),
        "evaluators": list(top.evaluators),
        "implementers": list(top.implementers),
    }

