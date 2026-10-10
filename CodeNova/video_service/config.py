from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVICE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT_DIR / ".env", ".env"), extra="ignore")

    backend_url: str = "http://localhost:8000"
    service_api_key: str = "change-me-service-key"
    secret_key: str = "change-me-in-.env"  # same as backend, used to check stream tokens
    frontend_origin: str = "http://localhost:5173"

    process_fps: float = 4.0
    imgsz: int = 640
    config_refresh_seconds: int = 15

    # Weights. Ultralytics downloads yolov8n.pt / yolov8n-pose.pt automatically on first run.
    detect_model: str = "yolov8n.pt"
    pose_model: str = "yolov8n-pose.pt"
    fire_model: str = "weights/fire_smoke.pt"
    smoking_model: str = "weights/smoking.pt"
    # Crude colour/flicker fire check used only when no fire model is present. Off by default
    # because sunsets, orange clothes and lights trigger it.
    fire_heuristic_fallback: bool = False

    det_conf: float = 0.35
    jpeg_quality: int = 75

    def resolve(self, path: str) -> str:
        p = Path(path)
        if not p.is_absolute() and (SERVICE_DIR / p).exists():
            return str(SERVICE_DIR / p)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
