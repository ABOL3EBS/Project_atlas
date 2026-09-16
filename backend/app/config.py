from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = "ollama"
    llm_model: str = "gemma2"
    ollama_base_url: str = "http://localhost:11434"

    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"

    chroma_dir: str = "./data/chroma"
    sqlite_path: str = "./data/atlas.db"
    uploaded_dir: str = "./data/uploads"

    default_knowledge_base_id: str = "default"

    retrieval_top_k: int = 8
    retrieval_min_score: float = 0.20
    grounding_threshold: float = 0.45

    chunk_size: int = 500
    chunk_overlap: int = 50

    max_upload_size: int = 20971520


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    for directory in (settings.uploaded_dir, settings.chroma_dir):
        Path(directory).mkdir(parents=True, exist_ok=True)
    return settings