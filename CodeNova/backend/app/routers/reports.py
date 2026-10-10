"""Geofenced incident reports from campus users."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PRIORITIES, Alert, EventType, User
from ..security import get_current_user
from ..seed import get_setting
from ..serializers import alert_out
from ..services.alerts import create_alert, save_image
from ..services.geofence import point_in_polygon

router = APIRouter(prefix="/api/reports", tags=["reports"])
MAX_PHOTO_BYTES = 8 * 1024 * 1024


def check_location(db: Session, lat: float, lon: float, accuracy: float | None) -> dict:
    polygon = get_setting(db, "geofence") or []
    max_acc = float(get_setting(db, "max_gps_accuracy_m") or 200)
    inside = point_in_polygon(lat, lon, polygon)
    accurate = accuracy is None or accuracy <= max_acc
    return {"inside": inside, "accurate_enough": accurate, "max_accuracy_m": max_acc}


@router.get("/check")
def check(lat: float, lon: float, accuracy: float | None = None, db: Session = Depends(get_db),
          _: User = Depends(get_current_user)):
    return check_location(db, lat, lon, accuracy)


@router.get("/categories")
def categories(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(EventType).filter(EventType.category == "report", EventType.enabled).all()
    return [{"key": e.key, "label": e.label, "default_priority": e.default_priority} for e in rows]


@router.post("")
async def create_report(
    category: str = Form(...),
    title: str = Form(..., min_length=3, max_length=200),
    description: str = Form("", max_length=4000),
    priority: str | None = Form(None),
    lat: float = Form(...),
    lon: float = Form(...),
    accuracy: float | None = Form(None),
    location_name: str = Form("", max_length=200),
    photo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    et = db.get(EventType, category)
    if not et or et.category != "report" or not et.enabled:
        raise HTTPException(400, "Unknown report category")
    loc = check_location(db, lat, lon, accuracy)
    if not loc["inside"]:
        raise HTTPException(403, "You must be inside the Amrita Coimbatore campus to file a report")
    if not loc["accurate_enough"]:
        raise HTTPException(400, f"GPS accuracy too low (need {loc['max_accuracy_m']:.0f} m or better). Move outdoors and retry.")
    if priority is not None and priority not in PRIORITIES:
        raise HTTPException(400, "Invalid priority")

    image_path = None
    if photo is not None and photo.filename:
        if not (photo.content_type or "").startswith("image/"):
            raise HTTPException(400, "Photo must be an image")
        data = await photo.read()
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(400, "Photo larger than 8 MB")
        image_path = save_image(data, "reports", photo.filename.rsplit(".", 1)[-1])

    alert = create_alert(
        db, et, title=title, description=description, source="report", priority=priority,
        reporter_id=user.id, lat=lat, lon=lon, location_name=location_name, image_path=image_path,
        extra={"gps_accuracy_m": accuracy},
    )
    return alert_out(alert)


@router.get("/mine")
def my_reports(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Alert).filter(Alert.reporter_id == user.id).order_by(Alert.created_at.desc()).limit(100).all()
    return [alert_out(a) for a in rows]
