"""LLM Configuration Repository for persistent API key and task mapping storage."""
from __future__ import annotations

import base64
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.core.config import settings

TaskType = Literal["draft", "chat", "article"]


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for a single LLM provider."""
    provider: str
    api_key: str
    base_url: str
    model: str
    is_default: bool = False

    def mask_api_key(self) -> str:
        """Return masked API key for display (show first 4 and last 4 chars)."""
        if len(self.api_key) <= 12:
            return "****"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"

    @property
    def configured(self) -> bool:
        """Check if provider is configured with an API key."""
        return bool(self.api_key.strip())


@dataclass(frozen=True)
class TaskMapping:
    """Mapping from task type to provider."""
    draft: str
    chat: str
    article: str


class LLMConfigRepository:
    """Repository for managing LLM configurations."""

    _ENCODE_PREFIX = "enc:"

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = Path(db_path or settings.db_path.replace(".db", "_llm_config.db"))
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create tables if they don't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS provider_config (
                    provider TEXT PRIMARY KEY,
                    api_key TEXT NOT NULL DEFAULT '',
                    base_url TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    is_default INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_mapping (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    draft TEXT NOT NULL DEFAULT 'openrouter',
                    chat TEXT NOT NULL DEFAULT 'openrouter',
                    article TEXT NOT NULL DEFAULT 'openrouter'
                )
            """)
            # Ensure default task mapping exists
            conn.execute("""
                INSERT OR IGNORE INTO task_mapping (id, draft, chat, article)
                VALUES (1, 'openrouter', 'openrouter', 'openrouter')
            """)
            conn.commit()

    def _encode_key(self, key: str) -> str:
        """Encode API key for storage."""
        if not key:
            return ""
        encoded = base64.b64encode(key.encode()).decode()
        return f"{self._ENCODE_PREFIX}{encoded}"

    def _decode_key(self, stored: str) -> str:
        """Decode API key from storage."""
        if not stored or not stored.startswith(self._ENCODE_PREFIX):
            return stored
        try:
            decoded = base64.b64decode(stored[len(self._ENCODE_PREFIX):]).decode()
            return decoded
        except Exception:
            return ""

    def _get_env_config(self, provider: str) -> ProviderConfig:
        """Get provider config from environment variables (fallback)."""
        provider_upper = provider.upper()
        api_key = getattr(settings, f"{provider_lower}_api_key" if (provider_lower := provider.lower()) else "", "")
        if not api_key:
            # Try uppercase
            api_key = getattr(settings, f"{provider_upper.lower()}_api_key", "")
        base_url = getattr(settings, f"{provider_lower}_base_url", "")
        model = getattr(settings, f"{provider_lower}_model", "")

        return ProviderConfig(
            provider=provider,
            api_key=api_key or "",
            base_url=base_url or "",
            model=model or "",
            is_default=(provider.lower() == settings.default_llm_provider.lower()),
        )

    def get_provider(self, provider: str) -> ProviderConfig:
        """Get configuration for a specific provider."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM provider_config WHERE provider = ?",
                (provider.lower(),)
            ).fetchone()

            if row:
                return ProviderConfig(
                    provider=row["provider"],
                    api_key=self._decode_key(row["api_key"]),
                    base_url=row["base_url"],
                    model=row["model"],
                    is_default=bool(row["is_default"]),
                )

        # Fallback to environment config
        return self._get_env_config(provider)

    def list_providers(self) -> list[ProviderConfig]:
        """List all provider configurations."""
        providers = ["openrouter", "deepseek", "openai"]
        result = []

        for provider in providers:
            db_config = self._get_from_db(provider)
            if db_config:
                result.append(db_config)
            else:
                # Use environment config as fallback
                result.append(self._get_env_config(provider))

        return result

    def _get_from_db(self, provider: str) -> ProviderConfig | None:
        """Get provider config from database."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM provider_config WHERE provider = ?",
                (provider.lower(),)
            ).fetchone()

            if row:
                return ProviderConfig(
                    provider=row["provider"],
                    api_key=self._decode_key(row["api_key"]),
                    base_url=row["base_url"],
                    model=row["model"],
                    is_default=bool(row["is_default"]),
                )
        return None

    def upsert_provider(self, config: ProviderConfig) -> ProviderConfig:
        """Create or update a provider configuration."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                INSERT INTO provider_config (provider, api_key, base_url, model, is_default)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(provider) DO UPDATE SET
                    api_key = excluded.api_key,
                    base_url = excluded.base_url,
                    model = excluded.model,
                    is_default = excluded.is_default
            """, (
                config.provider.lower(),
                self._encode_key(config.api_key),
                config.base_url,
                config.model,
                1 if config.is_default else 0,
            ))
            conn.commit()

        return self.get_provider(config.provider)

    def set_default_provider(self, provider: str) -> None:
        """Set the default provider."""
        with sqlite3.connect(self._db_path) as conn:
            # Clear all defaults
            conn.execute("UPDATE provider_config SET is_default = 0")
            # Set new default
            conn.execute(
                "UPDATE provider_config SET is_default = 1 WHERE provider = ?",
                (provider.lower(),)
            )
            conn.commit()

    def get_task_mapping(self) -> TaskMapping:
        """Get the task type to provider mapping."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM task_mapping WHERE id = 1").fetchone()

            if row:
                return TaskMapping(
                    draft=row["draft"],
                    chat=row["chat"],
                    article=row["article"],
                )

        # Default mapping
        return TaskMapping(
            draft=settings.default_llm_provider,
            chat=settings.default_llm_provider,
            article=settings.default_llm_provider,
        )

    def update_task_mapping(self, mapping: TaskMapping) -> TaskMapping:
        """Update the task type to provider mapping."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                UPDATE task_mapping
                SET draft = ?, chat = ?, article = ?
                WHERE id = 1
            """, (mapping.draft, mapping.chat, mapping.article))
            conn.commit()

        return self.get_task_mapping()

    def get_provider_for_task(self, task_type: TaskType) -> str:
        """Get the provider configured for a specific task type."""
        mapping = self.get_task_mapping()
        return getattr(mapping, task_type)

    def delete_provider(self, provider: str) -> bool:
        """Delete a provider configuration (reset to environment defaults)."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM provider_config WHERE provider = ?",
                (provider.lower(),)
            )
            conn.commit()
        return True


# Singleton instance
_llm_config_repository: LLMConfigRepository | None = None


def get_llm_config_repository() -> LLMConfigRepository:
    """Get the singleton LLM config repository."""
    global _llm_config_repository
    if _llm_config_repository is None:
        _llm_config_repository = LLMConfigRepository()
    return _llm_config_repository