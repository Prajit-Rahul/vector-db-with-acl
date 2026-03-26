# src/vecgate/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VECGATE_", case_sensitive=False)

    database_url: str = ""
    admin_database_url: str = ""
    embedding_dimensions: int = 1536
    max_top_k: int = 100
    db_pool_min: int = 2
    db_pool_max: int = 20
    enable_rls: bool = False
    enable_audit: bool = False
    hnsw_m: int = 16
    hnsw_ef_construction: int = 200

settings = Settings()
