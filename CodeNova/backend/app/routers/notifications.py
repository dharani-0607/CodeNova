from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import STAFF_ROLES, Notification, PushSubscription, User
from ..security import get_current_user, require_admin
from ..serializers import notification_out
from ..services.webpush import send_push

router = APIRouter(prefix="/api/notifications", tags=["notifications"])
settings = get_settings()


class SubscriptionIn(BaseModel):
    endpoint: str
    keys: dict


class EndpointIn(BaseModel):
    endpoint: str


@router.get("")
def list_notifications(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    q = db.query(Notification)
    if user.role not in STAFF_ROLES:
        q = q.filter(Notification.audience == "all")
    return [notification_out(n) for n in q.order_by(Notification.created_at.desc()).limit(limit).all()]


@router.post("/push/subscribe")
def subscribe(body: SubscriptionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not settings.push_enabled:
        raise HTTPException(400, "Browser push is not configured on the server (VAPID keys missing)")
    p256dh, auth = body.keys.get("p256dh"), body.keys.get("auth")
    if not p256dh or not auth:
        raise HTTPException(400, "Invalid subscription")
    sub = db.query(PushSubscription).filter(PushSubscription.endpoint == body.endpoint).first()
    if sub:
        sub.user_id, sub.p256dh, sub.auth = user.id, p256dh, auth
    else:
        db.add(PushSubscription(user_id=user.id, endpoint=body.endpoint, p256dh=p256dh, auth=auth))
    db.commit()
    return {"ok": True}


@router.post("/push/unsubscribe")
def unsubscribe(body: EndpointIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(PushSubscription).filter(
        PushSubscription.endpoint == body.endpoint, PushSubscription.user_id == user.id
    ).delete()
    db.commit()
    return {"ok": True}


@router.post("/push/test")
def push_test(user: User = Depends(require_admin)):
    send_push([user.id], "Test notification", "Browser push is working.", "/", "low")
    return {"ok": True}
