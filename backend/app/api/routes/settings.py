"""Settings API routes."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import LLMOption, LLMProvider, LLMSettingsResponse

router = APIRouter(prefix="/api/v1/settings")


@router.get("/llm", response_model=LLMSettingsResponse)
def get_llm_settings() -> LLMSettingsResponse:
    """Get available LLM configurations."""
    options: list[LLMOption] = [
        LLMOption(
            provider=LLMProvider.OPENROUTER,
            label="OpenRouter",
            model=settings.openrouter_model,
            configured=bool(settings.openrouter_api_key),
        ),
        LLMOption(
            provider=LLMProvider.DEEPSEEK,
            label="DeepSeek",
            model=settings.deepseek_model,
            configured=bool(settings.deepseek_api_key),
        ),
        LLMOption(
            provider=LLMProvider.OPENAI,
            label="OpenAI",
            model=settings.openai_model,
            configured=bool(settings.openai_api_key),
        ),
    ]

    # Determine default provider
    default_provider = LLMProvider.OPENROUTER
    provider_value = settings.default_llm_provider.lower().strip()
    if provider_value == "deepseek":
        default_provider = LLMProvider.DEEPSEEK
    elif provider_value == "openai":
        default_provider = LLMProvider.OPENAI

    return LLMSettingsResponse(defaultProvider=default_provider, options=options)


@router.patch("/llm", response_model=LLMSettingsResponse)
def update_llm_settings(payload: dict) -> LLMSettingsResponse:
    """Update LLM settings (persisted to session/env)."""
    # For now, this just returns current settings
    # In a full implementation, this would persist the default provider
    return get_llm_settings()