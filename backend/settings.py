from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    app_name: str = "Discovery Agent"
    database_url: str = f"sqlite:///{BASE_DIR / 'discovery_agent.db'}"
    data_dir: Path = BASE_DIR / "data"
    uploads_dir: Path = BASE_DIR / "data" / "uploads"
    generated_dir: Path = BASE_DIR / "data" / "generated"
    reports_dir: Path = BASE_DIR / "data" / "reports"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    demo_mode: bool = False
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_prefix="DISCOVERY_", extra="ignore")

    def ensure_directories(self) -> None:
        for path in [self.data_dir, self.uploads_dir, self.generated_dir, self.reports_dir]:
            os.makedirs(path, exist_ok=True)


settings = Settings()
