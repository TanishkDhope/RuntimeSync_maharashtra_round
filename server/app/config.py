"""Application configuration, read once from server/.env.

Every threshold the brief calls out is a config value, not a constant, because
they will be retuned when the trained diagnoser replaces the stub.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVER_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=SERVER_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Diagnoser
    diagnoser: Literal["stub", "model", "ollama"] = "stub"
    model_path: str = "../model/relearn-diagnosis.gguf"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "relearn-diagnosis"
    query_prompt: str = ""
    doc_prompt: str = ""

    # Thresholds
    unknown_threshold: float = 0.5
    probe_gap: float = 0.1  # read by the probe path, which is not built yet

    # Quiz
    session_length: int = 5
    run_timeout_seconds: float = 5.0

    # LLM. Unused this milestone: the intervention and probe paths that would
    # call it are not built yet. Reported by /health so the UI can say so.
    llm_provider: str = ""
    llm_model: str = ""
    llm_api_key: str = ""

    # Paths
    data_dir: str = "../data"
    database_url: str = "sqlite:///./relearn.db"

    # Frontend origin(s), comma separated. Kept as a plain string because
    # pydantic-settings JSON-decodes list-typed fields read from .env.
    # Vite picks the next free port when 5173 is taken, so allow a small range.
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:5175,http://127.0.0.1:5175"
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]

    @property
    def data_path(self) -> Path:
        return (SERVER_DIR / self.data_dir).resolve()

    @property
    def model_dir(self) -> Path:
        return (SERVER_DIR / self.model_path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
