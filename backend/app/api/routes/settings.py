"""Settings API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    LLMOption,
    LLMProvider,
    LLMSettingsResponse,
    ProviderConfigResponse,
    ProviderConfigUpdate,
    TaskMappingResponse,
    TaskMappingUpdate,
)
from app.repositories.llm_config_repository import get_llm_config_repository

router = APIRouter(prefix="/api/v1/settings")

# Provider labels for display
PROVIDER_LABELS = {
    LLMProvider.OPENROUTER: "OpenRouter",
    LLMProvider.DEEPSEEK: "DeepSeek",
    LLMProvider.OPENAI: "OpenAI",
}


@router.get("/llm", response_model=LLMSettingsResponse)
def get_llm_settings() -> LLMSettingsResponse:
    """Get available LLM configurations (legacy endpoint for compatibility)."""
    repo = get_llm_config_repository()
    providers = repo.list_providers()

    options: list[LLMOption] = []
    default_provider = LLMProvider.OPENROUTER

    for config in providers:
        provider_enum = LLMProvider(config.provider.lower())
        options.append(LLMOption(
            provider=provider_enum,
            label=PROVIDER_LABELS.get(provider_enum, config.provider),
            model=config.model,
            configured=config.configured,
        ))
        if config.is_default:
            default_provider = provider_enum

    return LLMSettingsResponse(defaultProvider=default_provider, options=options)


@router.get("/llm/providers", response_model=list[ProviderConfigResponse])
def list_provider_configs() -> list[ProviderConfigResponse]:
    """List all provider configurations with detailed info."""
    repo = get_llm_config_repository()
    providers = repo.list_providers()

    result: list[ProviderConfigResponse] = []
    for config in providers:
        provider_enum = LLMProvider(config.provider.lower())
        result.append(ProviderConfigResponse(
            provider=provider_enum,
            label=PROVIDER_LABELS.get(provider_enum, config.provider),
            apiKey=config.mask_api_key(),
            baseUrl=config.base_url,
            model=config.model,
            configured=config.configured,
            isDefault=config.is_default,
        ))

    return result


@router.get("/llm/providers/{provider}", response_model=ProviderConfigResponse)
def get_provider_config(provider: LLMProvider) -> ProviderConfigResponse:
    """Get configuration for a specific provider."""
    repo = get_llm_config_repository()
    config = repo.get_provider(provider.value)

    if not config:
        raise HTTPException(status_code=404, detail=f"Provider {provider} not found")

    return ProviderConfigResponse(
        provider=provider,
        label=PROVIDER_LABELS.get(provider, provider.value),
        apiKey=config.mask_api_key(),
        baseUrl=config.base_url,
        model=config.model,
        configured=config.configured,
        isDefault=config.is_default,
    )


@router.put("/llm/providers/{provider}", response_model=ProviderConfigResponse)
def update_provider_config(provider: LLMProvider, update: ProviderConfigUpdate) -> ProviderConfigResponse:
    """Update configuration for a specific provider."""
    repo = get_llm_config_repository()
    existing = repo.get_provider(provider.value)

    # Merge with existing config
    from app.repositories.llm_config_repository import ProviderConfig as RepoConfig
    new_config = RepoConfig(
        provider=provider.value,
        api_key=update.api_key if update.api_key is not None else existing.api_key,
        base_url=update.baseUrl if update.baseUrl is not None else existing.base_url,
        model=update.model if update.model is not None else existing.model,
        is_default=update.isDefault if update.isDefault is not None else existing.is_default,
    )

    updated = repo.upsert_provider(new_config)

    # If setting as default, update others
    if update.isDefault:
        repo.set_default_provider(provider.value)

    return ProviderConfigResponse(
        provider=provider,
        label=PROVIDER_LABELS.get(provider, provider.value),
        apiKey=updated.mask_api_key(),
        baseUrl=updated.base_url,
        model=updated.model,
        configured=updated.configured,
        isDefault=updated.is_default,
    )


@router.delete("/llm/providers/{provider}")
def reset_provider_config(provider: LLMProvider) -> dict:
    """Reset provider configuration to environment defaults."""
    repo = get_llm_config_repository()
    repo.delete_provider(provider.value)
    return {"status": "reset", "provider": provider.value}


@router.get("/llm/task-mapping", response_model=TaskMappingResponse)
def get_task_mapping() -> TaskMappingResponse:
    """Get task type to provider mapping."""
    repo = get_llm_config_repository()
    mapping = repo.get_task_mapping()

    return TaskMappingResponse(
        draft=LLMProvider(mapping.draft.lower()),
        chat=LLMProvider(mapping.chat.lower()),
        article=LLMProvider(mapping.article.lower()),
    )


@router.put("/llm/task-mapping", response_model=TaskMappingResponse)
def update_task_mapping(update: TaskMappingUpdate) -> TaskMappingResponse:
    """Update task type to provider mapping."""
    repo = get_llm_config_repository()
    existing = repo.get_task_mapping()

    from app.repositories.llm_config_repository import TaskMapping
    new_mapping = TaskMapping(
        draft=update.draft.value if update.draft else existing.draft,
        chat=update.chat.value if update.chat else existing.chat,
        article=update.article.value if update.article else existing.article,
    )

    updated = repo.update_task_mapping(new_mapping)

    return TaskMappingResponse(
        draft=LLMProvider(updated.draft.lower()),
        chat=LLMProvider(updated.chat.lower()),
        article=LLMProvider(updated.article.lower()),
    )


@router.patch("/llm", response_model=LLMSettingsResponse)
def update_llm_settings(payload: dict) -> LLMSettingsResponse:
    """Update LLM settings (legacy endpoint for compatibility)."""
    # For now, this just returns current settings
    # In a full implementation, this would persist the default provider
    return get_llm_settings()