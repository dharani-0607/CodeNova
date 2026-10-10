"""Admin-editable configuration: event types/priorities, geofence, speed limit, moderation rules."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import PRIORITIES, EventType, User
from ..security import get_current_user, require_admin, require_staff
from ..seed import get_setting, set_setting
from ..serializers import event_type_out
from ..services.geofence import validate_polygon
from ..services.moderation import model_status

router = APIRouter(prefix="/api", tags=["settings"])
settings = get_settings()


class EventTypeUpdate(BaseModel):
    label: str | None = None
    default_priority: str | None = None
    requires_review: bool | None = None
    public_broadcast: bool | None = None
    notify_email: bool | None = None
    notify_push: bool | None = None
    enabled: bool | None = None
    cooldown_seconds: int | None = None


class GeofenceIn(BaseModel):
    polygon: list[list[float]]
    center: list[float] | None = None


class CampusSettingsIn(BaseModel):
    speed_limit_kmh: float | None = None
    after_hours: dict | None = None
    max_gps_accuracy_m: float | None = None


class ModerationSettingsIn(BaseModel):
    flag_threshold: float
    remove_threshold: float
    banned_terms: list[str]
    review_terms: list[str]


@router.get("/config")
def public_config(db: Session = Depends(get_db)):
    """Non-secret settings the frontend needs before and after login."""
    return {
        "app_name": settings.app_name,
        "email_domain": settings.allowed_email_domain,
        "vapid_public_key": settings.vapid_public_key or None,
        "video_service_url": settings.video_service_public_url,
        "geofence": get_setting(db, "geofence"),
        "campus_center": get_setting(db, "campus_center"),
        "priorities": PRIORITIES,
    }


@router.get("/event-types")
def list_event_types(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [event_type_out(e) for e in db.query(EventType).order_by(EventType.category, EventType.key).all()]


@router.patch("/event-types/{key}")
def update_event_type(key: str, body: EventTypeUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    et = db.get(EventType, key)
    if not et:
        raise HTTPException(404, "Event type not found")
    data = body.model_dump(exclude_none=True)
    if "default_priority" in data and data["default_priority"] not in PRIORITIES:
        raise HTTPException(400, "Invalid priority")
    if "cooldown_seconds" in data and not 0 <= data["cooldown_seconds"] <= 86400:
        raise HTTPException(400, "Cooldown must be 0-86400 seconds")
    for k, v in data.items():
        setattr(et, k, v)
    db.commit()
    return event_type_out(et)


@router.put("/geofence")
def update_geofence(body: GeofenceIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    try:
        polygon = validate_polygon(body.polygon)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    set_setting(db, "geofence", polygon)
    if body.center:
        set_setting(db, "campus_center", body.center[:2])
    return {"geofence": polygon}


@router.get("/settings/campus")
def get_campus_settings(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return {
        "speed_limit_kmh": get_setting(db, "speed_limit_kmh"),
        "after_hours": get_setting(db, "after_hours"),
        "max_gps_accuracy_m": get_setting(db, "max_gps_accuracy_m") or 200,
    }


@router.put("/settings/campus")
def update_campus_settings(body: CampusSettingsIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if body.speed_limit_kmh is not None:
        if not 5 <= body.speed_limit_kmh <= 120:
            raise HTTPException(400, "Speed limit must be between 5 and 120 km/h")
        set_setting(db, "speed_limit_kmh", body.speed_limit_kmh)
    if body.after_hours is not None:
        set_setting(db, "after_hours", {"from": body.after_hours.get("from", "22:00"), "to": body.after_hours.get("to", "05:00")})
    if body.max_gps_accuracy_m is not None:
        set_setting(db, "max_gps_accuracy_m", body.max_gps_accuracy_m)
    return get_campus_settings(db)


@router.get("/settings/moderation")
def get_moderation_settings(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return {**(get_setting(db, "moderation") or {}), "model": model_status()}


@router.put("/settings/moderation")
def update_moderation_settings(body: ModerationSettingsIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if not 0 < body.flag_threshold <= body.remove_threshold <= 1:
        raise HTTPException(400, "Need 0 < flag threshold <= remove threshold <= 1")
    data = body.model_dump()
    data["banned_terms"] = sorted({t.strip() for t in data["banned_terms"] if t.strip()})
    data["review_terms"] = sorted({t.strip() for t in data["review_terms"] if t.strip()})
    set_setting(db, "moderation", data)
    return get_moderation_settings(db)
