import logging
import time
from typing import Annotated, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Response
from pydantic import BaseModel

from src.domain.entities.user import User
from src.domain.ports.model_cache_port import CachedModelCatalog, IModelCacheRepository
from src.infrastructure.llm.registry import (
    LLMProviderConfig,
    get_llm_provider,
    is_provider_configured,
)
from src.presentation.api.config import get_settings
from src.presentation.api.dependencies.auth import get_current_user
from src.presentation.api.dependencies.llm import get_llm_config
from src.presentation.api.dependencies.model_cache import get_model_cache_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["Models"])

CACHE_TTL_SECONDS: float = 86400.0  # 24 hours


class ModelResponse(BaseModel):
    id: str
    name: str


class ProviderResponse(BaseModel):
    id: str
    name: str
    models: list[ModelResponse]


def _probe_provider_in_background(
    provider_name: str,
    cache_repo: IModelCacheRepository,
    llm_config: LLMProviderConfig | None = None,
) -> None:
    """
    Background worker for a single provider that runs healthcheck probes,
    saves the verified catalog to the shared database, and releases the probe lock.
    """
    if not is_provider_configured(provider_name, config=llm_config):
        cache_repo.release_probe_lock(provider_name)
        return

    try:
        provider = get_llm_provider(provider_name, config=llm_config)
        verified_models = provider.list_models(probe=True)
        if verified_models:
            settings = get_settings()
            cache_repo.save(
                CachedModelCatalog(
                    provider=provider_name,
                    models=verified_models,
                    is_verified=True,
                    updated_at=time.time(),
                    app_version=getattr(settings, "api_version", "0.4.0"),
                )
            )
    except Exception as exc:
        logger.warning(f"Background probe failed for {provider_name}: {exc}")
    finally:
        cache_repo.release_probe_lock(provider_name)


def _resolve_provider_catalog(
    provider_name: str,
    now: float,
    refresh: bool,
    app_version: str,
    cache_repo: IModelCacheRepository,
    background_tasks: BackgroundTasks,
    llm_config: LLMProviderConfig | None = None,
) -> tuple[Optional[dict], bool]:
    """
    Resolves models for one provider using SWR from the shared database.
    Returns (provider_dict_or_None, is_probing_triggered).
    """
    if not is_provider_configured(provider_name, config=llm_config):
        return (None, False)

    cached = cache_repo.get(provider_name)
    if cached and cached.is_verified and (now - cached.updated_at) < CACHE_TTL_SECONDS and not refresh:
        return ({"id": provider_name, "name": provider_name.upper(), "models": cached.models}, False)

    # Stale cache: return immediately without blocking (Stale-While-Revalidate)
    if cached and cached.models and not refresh:
        probing = False
        if cache_repo.acquire_probe_lock(provider_name):
            background_tasks.add_task(_probe_provider_in_background, provider_name, cache_repo, llm_config)
            probing = True
        return ({"id": provider_name, "name": provider_name.upper(), "models": cached.models}, probing)

    # Cold start: fetch fast preliminary list (probe=False) so UI is never blocked
    provider = get_llm_provider(provider_name, config=llm_config)
    preliminary = provider.list_models(probe=False)
    if not preliminary:
        return (None, False)

    cache_repo.save(
        CachedModelCatalog(
            provider=provider_name,
            models=preliminary,
            is_verified=False,
            updated_at=now,
            app_version=app_version,
        )
    )

    probing = False
    if cache_repo.acquire_probe_lock(provider_name):
        background_tasks.add_task(_probe_provider_in_background, provider_name, cache_repo, llm_config)
        probing = True

    return ({"id": provider_name, "name": provider_name.upper(), "models": preliminary}, probing)


@router.get("", response_model=list[ProviderResponse])
def get_available_models(
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
    response: Response,
    cache_repo: Annotated[IModelCacheRepository, Depends(get_model_cache_repository)],
    llm_config: Annotated[LLMProviderConfig, Depends(get_llm_config)],
    refresh: bool = False,
):
    """
    Returns available models grouped by provider using a shared database cache with SWR.
    Across all cluster pods:
    1. Fresh cache (<24h & verified): served instantly from shared DB (<1ms).
    2. Stale cache or cold start: returns existing/preliminary models immediately without blocking.
    3. Concurrency guard: only one pod in the cluster acquires the probe lock to run OpenAI/provider probes.
    """
    if refresh:
        cache_repo.invalidate_all()

    now = time.time()
    settings = get_settings()
    app_version = getattr(settings, "api_version", "0.4.0")
    providers = ["gemini", "openai", "anthropic"]
    result = []
    any_probing = False

    for provider_name in providers:
        if not is_provider_configured(provider_name, config=llm_config):
            continue
        try:
            catalog, probing = _resolve_provider_catalog(
                provider_name,
                now,
                refresh,
                app_version,
                cache_repo,
                background_tasks,
                llm_config=llm_config,
            )
            if catalog:
                result.append(catalog)
            if probing:
                any_probing = True
        except Exception as exc:
            logger.warning(f"Failed to fetch models for {provider_name}: {exc}")

    response.headers["X-Models-Probing"] = "1" if any_probing else "0"
    return result
