"""Creating alerts from camera detections, user reports, or staff."""
import time
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import OPEN, PENDING_REVIEW, PRIORITIES, Alert, EventType
from .notify import notify_alert_created

settings = get_settings()
_last_seen: dict[tuple, float] = {}


def save_image(data: bytes, folder: str, ext: str = "jpg") -> str:
    """Store an uploaded image under media/<folder>/ and return its relative path."""
    ext = ext.lower().lstrip(".")
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    rel = Path(folder) / f"{uuid.uuid4().hex}.{ext}"
    full = Path(settings.media_dir) / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(data)
    return rel.as_posix()


def in_cooldown(et: EventType, camera_id: int | None, zone_id: int | None, key: str | None = None) -> bool:
    if not et.cooldown_seconds:
        return False
    k = (et.key, camera_id, zone_id, key)
    now = time.monotonic()
    last = _last_seen.get(k)
    if last is not None and now - last < et.cooldown_seconds:
        return True
    _last_seen[k] = now
    return False


def create_alert(
    db: Session,
    et: EventType,
    *,
    title: str | None = None,
    description: str = "",
    source: str = "camera",
    priority: str | None = None,
    camera=None,
    zone_id: int | None = None,
    reporter_id: int | None = None,
    confidence: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    location_name: str = "",
    image_path: str | None = None,
    extra: dict | None = None,
    force_open: bool = False,
) -> Alert:
    prio = priority if priority in PRIORITIES else et.default_priority
    status = PENDING_REVIEW if (et.requires_review and not force_open) else OPEN
    alert = Alert(
        event_type=et.key, source=source, camera_id=camera.id if camera else None, zone_id=zone_id,
        reporter_id=reporter_id, title=title or et.label, description=description, priority=prio,
        status=status, confidence=confidence,
        lat=lat if lat is not None else (camera.lat if camera else None),
        lon=lon if lon is not None else (camera.lon if camera else None),
        location_name=location_name or (camera.location_name if camera else ""),
        image_path=image_path, extra=extra or {},
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    notify_alert_created(db, alert, et)
    return alert
