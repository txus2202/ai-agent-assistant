from typing import Annotated, List, Dict

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
async def get_agents_config(repo: Annotated[SqliteAgentConfigRepository, Depends(get_config_repo)]) -> List[Dict[str, str]]:
    """
    Devuelve la lista de agentes disponibles en el sistema con su nombre, descripción, proveedor y modelo configurados.
    """
    settings = get_settings()
    
    result = []
    for profile in get_all_profiles():
        role_value = profile.id
        config = repo.find_by_role(role_value)
        if not config:
            config = repo.find_by_role(profile.display_name)
        result.append({
            "id": role_value,
            "name": profile.display_name,
            "description": profile.description,
            "color_hex": profile.color_hex,
            "provider": config.provider if config else settings.default_provider,
            "model_name": config.model_name if config else settings.default_model
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
