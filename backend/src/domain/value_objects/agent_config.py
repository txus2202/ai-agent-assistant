from dataclasses import dataclass
from typing import Optional

@dataclass
class AgentConfig:
    """
    Configuration for an agent's LLM model and provider.
    """
    role: str
    provider: str
    model_name: str
    user_id: Optional[str] = None
