from fastapi import APIRouter, Depends
from pydantic import BaseModel
import logging

from src.domain.entities.user import User
from src.infrastructure.llm.registry import get_llm_provider
from src.presentation.api.dependencies.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["Models"])

class ModelResponse(BaseModel):
    id: str
    name: str

class ProviderResponse(BaseModel):
    id: str
    name: str
    models: list[ModelResponse]

@router.get("", response_model=list[ProviderResponse])
def get_available_models(
    current_user: User = Depends(get_current_user),
):
    """
    Returns all available models grouped by provider.
    Queries the actual APIs to get real data.
    """
    providers = ["gemini", "openai", "anthropic"]
    result = []
    
    for provider_name in providers:
        try:
            provider = get_llm_provider(provider_name)
            models = provider.list_models()
            if models:
                result.append({
                    "id": provider_name,
                    "name": provider_name.upper(),
                    "models": models
                })
        except Exception as e:
            # Log the error but continue with other providers.
            # This handles cases where a provider is not configured (e.g. missing API key)
            # or if the API key is invalid.
            logger.warning(f"Failed to fetch models for {provider_name}: {e}")
            
    return result
