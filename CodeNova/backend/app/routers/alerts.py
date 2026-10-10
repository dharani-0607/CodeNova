from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    ACKNOWLEDGED, ALERT_STATUSES, DISMISSED, OPEN, PENDING_REVIEW, PRIORITIES, RESOLVED,
    STAFF_ROLES, Alert, EventType, User,
)
from ..security import get_current_user, require_staff
from ..serializers import alert_out
from ..services.alerts import create_alert
from ..services.notify import broadcast_alert, notify_alert_created, notify_alert_updated

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    notes: str | None = None


class ManualAlertIn(BaseModel):
    event_type: str
    title: str
    description: str = ""
    priority: str | None = None
    location_name: str = ""
    lat: float | None = None
    lon: float | None = None
    broadcast: bool = False


@router.get("")
def list_alerts(
    status: str | None = None,
    priority: str | None = None,
    event_type: str | None = None,
    source: str | None = None,
    camera_id: int | None = None,
    active: bool = False,
    hours: int | None = Query(default=None, ge=1, le=24 * 365),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    q = db.query(Alert)
    if status:
        q = q.filter(Alert.status.in_(status.split(",")))
    if active:
        q = q.filter(Alert.status.in_([PENDING_REVIEW, OPEN, ACKNOWLEDGED]))
    if priority:
        q = q.filter(Alert.priority.in_(priority.split(",")))
    if event_type:
        q = q.filter(Alert.event_type.in_(event_type.split(",")))
    if source:
        q = q.filter(Alert.source == source)
    if camera_id:
        q = q.filter(Alert.camera_id == camera_id)
    if hours:
        q = q.filter(Alert.created_at >= datetime.now(timezone.utc) - timedelta(hours=hours))
    return [alert_out(a) for a in q.order_by(Alert.created_at.desc()).limit(limit).all()]


@router.get("/public")
def public_alerts(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Campus-wide alerts every logged-in user can see."""
    rows = (
        db.query(Alert)
        .filter(Alert.broadcast.is_(True), Alert.status.in_([OPEN, ACKNOWLEDGED, RESOLVED]))
        .order_by(Alert.created_at.desc()).limit(limit).all()
    )
    return [alert_out(a, include_reporter=False) for a in rows]


@router.get("/stats")
def alert_stats(hours: int = Query(default=24, ge=1, le=24 * 90), db: Session = Depends(get_db), _: User = Depends(require_staff)):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    base = db.query(Alert).filter(Alert.created_at >= since)
    by_type = dict(base.with_entities(Alert.event_type, func.count()).group_by(Alert.event_type).all())
    by_priority = dict(base.with_entities(Alert.priority, func.count()).group_by(Alert.priority).all())
    by_status = dict(base.with_entities(Alert.status, func.count()).group_by(Alert.status).all())
    active = db.query(func.count(Alert.id)).filter(Alert.status.in_([PENDING_REVIEW, OPEN, ACKNOWLEDGED])).scalar()
    pending = db.query(func.count(Alert.id)).filter(Alert.status == PENDING_REVIEW).scalar()
    return {
        "hours": hours, "total": sum(by_type.values()), "active": active, "pending_review": pending,
        "by_type": by_type, "by_priority": by_priority, "by_status": by_status,
    }


@router.get("/{alert_id}")
def get_alert(alert_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    if user.role not in STAFF_ROLES and not alert.broadcast and alert.reporter_id != user.id:
        raise HTTPException(403, "Not allowed")
    return alert_out(alert, include_reporter=user.role in STAFF_ROLES)


@router.patch("/{alert_id}")
def update_alert(alert_id: int, body: AlertUpdate, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    was_pending = alert.status == PENDING_REVIEW
    if body.priority is not None:
        if body.priority not in PRIORITIES:
            raise HTTPException(400, "Invalid priority")
        alert.priority = body.priority
    if body.status is not None:
        if body.status not in ALERT_STATUSES:
            raise HTTPException(400, "Invalid status")
        alert.status = body.status
        alert.handled_by = user.id
    if body.notes is not None:
        alert.notes = body.notes
    db.commit()
    # A reviewed alert that security confirms now goes out on the normal channels.
    if was_pending and alert.status in (OPEN, ACKNOWLEDGED):
        et = db.get(EventType, alert.event_type)
        if et:
            notify_alert_created(db, alert, et)
    notify_alert_updated(alert)
    return alert_out(alert)


@router.post("/{alert_id}/broadcast")
def broadcast(alert_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    if alert.status in (PENDING_REVIEW, DISMISSED):
        alert.status = OPEN
        db.commit()
    broadcast_alert(db, alert)
    notify_alert_updated(alert)
    return alert_out(alert)


@router.post("")
def manual_alert(body: ManualAlertIn, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    et = db.get(EventType, body.event_type)
    if not et:
        raise HTTPException(400, "Unknown event type")
    alert = create_alert(
        db, et, title=body.title, description=body.description, source="manual",
        priority=body.priority, reporter_id=user.id, lat=body.lat, lon=body.lon,
        location_name=body.location_name, force_open=True,
    )
    if body.broadcast:
        broadcast_alert(db, alert)
    return alert_out(alert)
