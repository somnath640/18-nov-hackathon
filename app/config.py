from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    triage_model: str = "llama-3.1-8b-instant"
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    redis_url: str = "redis://localhost:6379/0"
    rerank_threshold: float = 0.42
    max_loop_steps: int = 5
    step_timeout_ms: int = 120
    loop_budget_ms: int = 450
    mcp_timeout_ms: int = 150

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
