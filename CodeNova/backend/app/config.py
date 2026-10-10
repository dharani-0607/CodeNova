"""Application settings, read from environment variables or the repo-level .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Amrita Coimbatore Campus Command Center"
    # Postgres in production (see docker-compose.yml); SQLite works for a quick start.
    database_url: str = f"sqlite:///{ROOT_DIR / 'backend' / 'campus.db'}"
    secret_key: str = "change-me-in-.env"
    access_token_minutes: int = 60 * 12

    # Only addresses on this domain can register.
    allowed_email_domain: str = "cb.amrita.edu"
    # Comma-separated emails that become admins on registration.
    admin_emails: str = ""
    # If False (dev only) accounts are verified immediately without an emailed code.
    require_email_verification: bool = True

    # Shared secret the video service uses to push detections.
    service_api_key: str = "change-me-service-key"

    frontend_origin: str = "http://localhost:5173"
    # Where browsers reach the video service. "/video" goes through the frontend proxy.
    video_service_public_url: str = "/video"
    media_dir: str = str(ROOT_DIR / "backend" / "media")

    # Email (SMTP). Leave smtp_host empty to print emails to the console instead.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    # Browser push (VAPID). Generate with scripts/generate_vapid_keys.py
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@cb.amrita.edu"

    # Local moderation model (Hugging Face model id or local path).
    moderation_model: str = "unitary/toxic-bert"
    moderation_use_ml: bool = True

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host)

    @property
    def push_enabled(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
