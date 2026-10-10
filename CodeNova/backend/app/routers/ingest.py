"""Endpoints the video service calls (authenticated with X-Service-Key)."""
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Camera, EventType
from ..security import require_service
from ..seed import get_setting
from ..serializers import alert_out, camera_out
from ..services.alerts import create_alert, in_cooldown, save_image
from ..services.camera_status import camera_status
from ..services.hub import hub

router = APIRouter(prefix="/api/ingest", tags=["ingest"], dependencies=[Depends(require_service)])


class StatsIn(BaseModel):
    camera_id: int
    online: bool = True
    fps: float = 0
    people: int = 0
    vehicles: int = 0
    error: str | None = None


@router.get("/config")
def ingest_config(db: Session = Depends(get_db)):
    cams = db.query(Camera).filter(Camera.enabled).all()
    enabled_types = [e.key for e in db.query(EventType).filter(EventType.enabled).all()]
    return {
        "cameras": [camera_out(c) for c in cams],
        "enabled_event_types": enabled_types,
        "speed_limit_kmh": get_setting(db, "speed_limit_kmh"),
        "after_hours": get_setting(db, "after_hours"),
    }


@router.post("/alerts")
async def ingest_alert(
    camera_id: int = Form(...),
    event_type: str = Form(...),
    description: str = Form(""),
    confidence: float | None = Form(None),
    zone_id: int | None = Form(None),
    dedupe_key: str | None = Form(None),
    extra: str = Form("{}"),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    et = db.get(EventType, event_type)
    if not et:
        raise HTTPException(400, f"Unknown event type {event_type}")
    if not et.enabled:
        return {"status": "ignored", "reason": "event type disabled"}
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Unknown camera")
    if in_cooldown(et, camera_id, zone_id, dedupe_key):
        return {"status": "ignored", "reason": "cooldown"}
    try:
        extra_data = json.loads(extra) if extra else {}
    except json.JSONDecodeError:
        extra_data = {}
    image_path = save_image(await image.read(), "alerts") if image is not None else None
    zone_name = next((z.name for z in cam.zones if z.id == zone_id), None)
    title = f"{et.label} - {cam.name}" + (f" ({zone_name})" if zone_name else "")
    alert = create_alert(
        db, et, title=title, description=description, source="camera", camera=cam, zone_id=zone_id,
        confidence=confidence, image_path=image_path, extra=extra_data,
    )
    return {"status": "created", "alert": alert_out(alert)}


@router.post("/stats")
def ingest_stats(items: list[StatsIn]):
    for s in items:
        camera_status.update(s.camera_id, s.model_dump())
    hub.publish("camera_stats", {str(k): v for k, v in camera_status.all().items()}, audience="staff")
    return {"ok": True}
