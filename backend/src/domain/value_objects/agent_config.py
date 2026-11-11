from dataclasses import dataclass
from typing import Optional

@dataclass
class AgentConfig:
    """
    Configuration for an agent's LLM model, provider, and per-agent RAG retrieval parameters.
    """
    role: str
    provider: str
    model_name: str
    user_id: Optional[str] = None
    rag_top_k: Optional[int] = None
    rag_min_score: Optional[float] = None
