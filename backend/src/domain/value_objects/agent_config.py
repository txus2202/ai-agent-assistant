from dataclasses import dataclass

@dataclass
class AgentConfig:
    """
    Configuration for an agent's LLM model and provider.
    """
    role: str
    provider: str
    model_name: str
