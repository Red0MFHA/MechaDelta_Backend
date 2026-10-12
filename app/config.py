from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://mechadelta:mechadelta@localhost:5432/mechadelta"
    force_sqlite: bool = True
    # Live perception writes here (runs/latest symlink). Fixtures are demos only.
    mechadelta_runs_root: Path = Path.home() / "mechadelta_ws" / "runs"
    bridge_url: str = "http://127.0.0.1:8765"
    cors_origins: str = "http://localhost:3000"
    public_api_base: str = "http://localhost:8000"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    default_source_id: str = "src-sim-1"
    default_run_id: str = "latest"
    # LiveKit (local --dev keys: devkey / secret)
    livekit_url: str = "ws://127.0.0.1:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "secret"
    livekit_room_prefix: str = "mechadelta"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        if self.force_sqlite:
            data = Path("data")
            data.mkdir(parents=True, exist_ok=True)
            return f"sqlite+pysqlite:///{(data / 'app.db').resolve()}"
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
