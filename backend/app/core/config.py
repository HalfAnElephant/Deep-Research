from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import default_data_dir, default_frontend_dist_dir, default_reports_dir


class Settings(BaseSettings):
    app_name: str = "Research Flow"
    api_prefix: str = "/api/v1"
    data_dir: str = str(default_data_dir())
    db_path: str = str(default_data_dir() / "research_flow.db")
    reports_dir: str = str(default_reports_dir())
    frontend_dist_dir: str = str(default_frontend_dist_dir())
    log_level: str = "INFO"
    use_mock_sources: bool = False
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

    # LongCat API (用于用户交互，不用于文章生成)
    longcat_api_key: str = ""
    longcat_base_url: str = "https://api.longcat.chat/openai/v1"
    longcat_model: str = "LongCat-Flash-Lite"

    # LLM 超时配置（秒）
    llm_timeout_short: int = 30      # 简单查询
    llm_timeout_medium: int = 60     # 计划生成
    llm_timeout_long: int = 120      # 文章生成

    model_config = SettingsConfigDict(env_file=".env", env_prefix="DR_", extra="ignore")


settings = Settings()
