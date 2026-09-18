from fastapi import APIRouter
from src.domain.agents.agent_role import AgentRole
from typing import List, Dict

router = APIRouter(prefix="/config", tags=["config"])

@router.get("/agents")
async def get_agents_config() -> List[Dict[str, str]]:
    """
    Devuelve la lista de agentes disponibles en el sistema y su orden de ejecución aproximado.
    El campo 'role' coincide con el valor devuelto en los eventos del WebSocket.
    """
    # Devolvemos los agentes en un orden lógico de ejecución
    ordered_roles = [
        AgentRole.NL_INTERPRETER,
        AgentRole.INNOVATOR,
        AgentRole.SENIOR_ARCHITECT,
        AgentRole.THE_JUDGE,
        AgentRole.DIAGRAMMER,
        AgentRole.DEVOPS_SECOPS
    ]
    
    return [
        {
            "id": role.value,
            "name": role.name.replace("_", " ").title() # ej: 'Nl Interpreter', 'The Judge'
        }
        for role in ordered_roles
    ]
