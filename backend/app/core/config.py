from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Deep Research"
    api_prefix: str = "/api/v1"
    db_path: str = "backend/.data/deep_research.db"
    log_level: str = "INFO"
    use_mock_sources: bool = True
    default_llm_provider: str = "openrouter"
    default_llm_model: str = "deepseek/deepseek-chat-v3-0324"

    # LLM providers
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "deepseek/deepseek-chat-v3-0324"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"

    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-3-7-sonnet-latest"

    # Search providers
    serper_api_key: str = ""
    serpapi_api_key: str = ""
    tavily_api_key: str = ""
    brave_api_key: str = ""
    bing_subscription_key: str = ""
    google_cse_api_key: str = ""
    google_cse_cx: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="DR_")


settings = Settings()
