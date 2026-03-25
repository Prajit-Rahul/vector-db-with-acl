"""Application settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    database_url: str = "postgresql://postgres:postgres@localhost:5432/acl_search"
    embedding_dimensions: int = 1536
    max_top_k: int = 100

    db_pool_min_size: int = 2
    db_pool_max_size: int = 20
    db_pool_max_idle_seconds: int = 60
    enable_demo_embeddings: bool = False

    model_config = SettingsConfigDict(
        env_prefix="ACL_SEARCH_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
