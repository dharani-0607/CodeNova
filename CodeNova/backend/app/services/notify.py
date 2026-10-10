"""Decides who hears about an alert or news post, and over which channels.

Channels: live dashboard (WebSocket), browser push, email.
- Alerts awaiting review go to security/admin only (dashboard + push).
- Confirmed alerts go to security/admin on every channel enabled for the event type
  (email only for critical/high).
- Alerts marked for campus-wide broadcast also go to every user.
"""
from sqlalchemy.orm import Session

from ..models import (
    PENDING_REVIEW, PRIORITY_RANK, STAFF_ROLES, Alert, EventType, NewsPost, Notification, User,
)
from ..serializers import alert_out, notification_out, post_out
from .hub import hub
from .mailer import send_email
from .webpush import send_push


def _staff(db: Session) -> list[User]:
    return db.query(User).filter(User.role.in_(STAFF_ROLES), User.is_active, User.is_verified).all()


def _everyone(db: Session) -> list[User]:
    return db.query(User).filter(User.is_active, User.is_verified).all()


def _record(db: Session, kind: str, ref_id: int, title: str, body: str, priority: str, audience: str) -> Notification:
    n = Notification(kind=kind, ref_id=ref_id, title=title, body=body, priority=priority, audience=audience)
    db.add(n)
    db.commit()
    hub.publish("notification", notification_out(n), audience=audience)
    return n


def _alert_text(alert: Alert) -> tuple[str, str]:
    where = alert.location_name or (alert.camera.name if alert.camera else "campus")
    title = f"[{alert.priority.upper()}] {alert.title}"
    body = f"{alert.description or alert.title}\nLocation: {where}\nTime: {alert.created_at:%d %b %Y %H:%M} UTC"
    return title, body


def notify_alert_created(db: Session, alert: Alert, et: EventType) -> None:
    hub.publish("alert", alert_out(alert), audience="staff")
    title, body = _alert_text(alert)
    staff = _staff(db)
    urgent = PRIORITY_RANK.get(alert.priority, 9) <= PRIORITY_RANK["high"]

    if alert.status == PENDING_REVIEW:
        _record(db, "alert", alert.id, "Needs review: " + title, body, alert.priority, "staff")
        if et.notify_push and urgent:
            send_push([u.id for u in staff], "Needs review: " + title, body, f"/alerts/{alert.id}", alert.priority)
        return

    _record(db, "alert", alert.id, title, body, alert.priority, "staff")
    if et.notify_push:
        send_push([u.id for u in staff], title, body, f"/alerts/{alert.id}", alert.priority)
    if et.notify_email and urgent:
        send_email([u.email for u in staff], title, body + "\n\nOpen the dashboard to respond.")
    if et.public_broadcast:
        broadcast_alert(db, alert)


def broadcast_alert(db: Session, alert: Alert) -> None:
    """Announce an alert to every campus user (dashboard + push, email when critical)."""
    alert.broadcast = True
    db.commit()
    title, body = _alert_text(alert)
    hub.publish("campus_alert", alert_out(alert, include_reporter=False), audience="all")
    _record(db, "alert", alert.id, "Campus alert: " + title, body, alert.priority, "all")
    send_push(None, "Campus alert: " + title, body, "/", alert.priority)
    if alert.priority == "critical":
        send_email([u.email for u in _everyone(db)], "Campus alert: " + title, body)


def notify_alert_updated(alert: Alert) -> None:
    hub.publish("alert_update", alert_out(alert), audience="staff")


def notify_news(db: Session, post: NewsPost) -> None:
    hub.publish("news", post_out(post), audience="all")
    if post.is_important:
        snippet = post.body[:280]
        _record(db, "news", post.id, "Important: " + post.title, snippet, "high", "all")
        send_push(None, "Campus news: " + post.title, snippet, "/news", "high")
        send_email([u.email for u in _everyone(db)], "Important campus news: " + post.title, post.body)
