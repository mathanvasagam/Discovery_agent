from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
load_dotenv(PROJECT_DIR / ".env")


class Settings(BaseSettings):
    app_name: str = "Discovery Agent"
    environment: str = "development"
    database_url: str = f"sqlite:///{BASE_DIR / 'discovery_agent.db'}"
    data_dir: Path = BASE_DIR / "data"
    uploads_dir: Path = BASE_DIR / "data" / "uploads"
    generated_dir: Path = BASE_DIR / "data" / "generated"
    reports_dir: Path = BASE_DIR / "data" / "reports"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    demo_mode: bool = False

    groq_api_key: Optional[str] = None
    groq_model: str = "openai/gpt-oss-120b"
    gemini_model: str = "gemini-3.5-flash-lite"
    llm_provider_order: str = "groq,gemini"
    llm_timeout_seconds: float = 30.0

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    allowed_hosts: str = "localhost,127.0.0.1,*.onrender.com"
    session_secret: Optional[str] = None
    workspace_isolation: bool = False
    rate_limit_enabled: bool = True

    max_upload_bytes: int = 20 * 1024 * 1024
    max_persisted_text_chars: int = 100_000
    retain_uploads: bool = True
    validation_mode: str = "docker"

    model_config = SettingsConfigDict(
        env_file=PROJECT_DIR / ".env",
        env_prefix="DISCOVERY_",
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def parsed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def parsed_allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    def validate_runtime(self) -> None:
        if self.is_production and self.database_url.startswith("sqlite"):
            raise RuntimeError("Production requires a persistent database. Configure DISCOVERY_DATABASE_URL with PostgreSQL.")
        if self.workspace_isolation and not self.session_secret:
            raise RuntimeError("Workspace isolation requires DISCOVERY_SESSION_SECRET.")
        if self.is_production and self.validation_mode.strip().lower() in {"local", "docker"}:
            raise RuntimeError("Public production deployments must use DISCOVERY_VALIDATION_MODE=static.")

    def runtime_status(self) -> Dict[str, Any]:
        return {
            "environment": self.environment,
            "validation_mode": self.validation_mode,
            "workspace_isolation": self.workspace_isolation,
            "rate_limits": self.rate_limit_enabled,
            "original_upload_retention": self.retain_uploads,
            "database": "sqlite" if self.database_url.startswith("sqlite") else "postgresql",
            "privacy_mode": "ephemeral-originals" if not self.retain_uploads else "retained-originals",
        }

    def ensure_directories(self) -> None:
        for path in [self.data_dir, self.uploads_dir, self.generated_dir, self.reports_dir]:
            os.makedirs(path, exist_ok=True)


settings = Settings()
