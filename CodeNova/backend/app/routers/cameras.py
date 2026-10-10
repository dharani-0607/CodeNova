from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ZONE_KINDS, Camera, User, Zone
from ..security import require_admin, require_staff
from ..serializers import camera_out, zone_out
from ..services.camera_status import camera_status

router = APIRouter(prefix="/api/cameras", tags=["cameras"])

DETECTORS = [
    "crowd", "intrusion", "loitering", "unattended_object", "animal", "vehicle_zone",
    "wrong_parking", "triple_riding", "speeding", "fire_smoke", "fall", "fight", "smoking", "littering",
]


class CameraIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=500)
    location_name: str = ""
    lat: float | None = None
    lon: float | None = None
    enabled: bool = True
    detectors: dict = Field(default_factory=lambda: {d: True for d in DETECTORS})
    calibration: dict = Field(default_factory=dict)
    params: dict = Field(default_factory=dict)


class ZoneIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str
    polygon: list[list[float]]
    params: dict = Field(default_factory=dict)
    enabled: bool = True


def _check_polygon(poly: list[list[float]]) -> None:
    if len(poly) < 3:
        raise HTTPException(400, "A zone needs at least 3 points")
    for pt in poly:
        if len(pt) != 2 or not all(0 <= v <= 1 for v in pt):
            raise HTTPException(400, "Zone points must be normalised [x, y] values between 0 and 1")


@router.get("/detectors")
def list_detectors(_: User = Depends(require_staff)):
    return {"detectors": DETECTORS, "zone_kinds": ZONE_KINDS}


@router.get("")
def list_cameras(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    cams = db.query(Camera).order_by(Camera.id).all()
    return [{**camera_out(c), "status": camera_status.get(c.id)} for c in cams]


@router.post("")
def create_camera(body: CameraIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    cam = Camera(**body.model_dump())
    db.add(cam)
    db.commit()
    return camera_out(cam)


@router.get("/{camera_id}")
def get_camera(camera_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    return {**camera_out(cam), "status": camera_status.get(cam.id)}


@router.put("/{camera_id}")
def update_camera(camera_id: int, body: CameraIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    for k, v in body.model_dump().items():
        setattr(cam, k, v)
    db.commit()
    return camera_out(cam)


@router.delete("/{camera_id}")
def delete_camera(camera_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    db.delete(cam)
    db.commit()
    return {"ok": True}


@router.post("/{camera_id}/zones")
def create_zone(camera_id: int, body: ZoneIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if not db.get(Camera, camera_id):
        raise HTTPException(404, "Camera not found")
    if body.kind not in ZONE_KINDS:
        raise HTTPException(400, f"kind must be one of {ZONE_KINDS}")
    _check_polygon(body.polygon)
    zone = Zone(camera_id=camera_id, **body.model_dump())
    db.add(zone)
    db.commit()
    return zone_out(zone)


@router.put("/zones/{zone_id}")
def update_zone(zone_id: int, body: ZoneIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    zone = db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(404, "Zone not found")
    if body.kind not in ZONE_KINDS:
        raise HTTPException(400, f"kind must be one of {ZONE_KINDS}")
    _check_polygon(body.polygon)
    for k, v in body.model_dump().items():
        setattr(zone, k, v)
    db.commit()
    return zone_out(zone)


@router.delete("/zones/{zone_id}")
def delete_zone(zone_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    zone = db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(404, "Zone not found")
    db.delete(zone)
    db.commit()
    return {"ok": True}
