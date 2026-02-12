from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Deep Research"
    api_prefix: str = "/api/v1"
    db_path: str = "backend/.data/deep_research.db"
    log_level: str = "INFO"
    use_mock_sources: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_prefix="DR_")


settings = Settings()
