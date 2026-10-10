"""Browser push notifications via the Web Push protocol (VAPID)."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from ..config import get_settings
from ..db import SessionLocal
from ..models import PushSubscription, User

log = logging.getLogger(__name__)
settings = get_settings()
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="webpush")


def _send(user_ids: list[int] | None, payload: dict) -> None:
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        log.warning("pywebpush not installed; skipping browser push")
        return
    db = SessionLocal()
    try:
        q = db.query(PushSubscription).join(User, User.id == PushSubscription.user_id).filter(User.is_active)
        if user_ids is not None:
            q = q.filter(PushSubscription.user_id.in_(user_ids))
        for sub in q.all():
            try:
                webpush(
                    subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                    data=json.dumps(payload),
                    vapid_private_key=settings.vapid_private_key,
                    vapid_claims={"sub": settings.vapid_subject},
                    ttl=3600,
                )
            except WebPushException as exc:
                status = getattr(exc.response, "status_code", None)
                if status in (404, 410):  # subscription expired
                    db.delete(sub)
                    db.commit()
                else:
                    log.warning("Push failed: %s", exc)
    finally:
        db.close()


def send_push(user_ids: list[int] | None, title: str, body: str, url: str = "/", priority: str = "medium") -> None:
    """user_ids=None sends to every subscribed user."""
    if not settings.push_enabled:
        return
    _pool.submit(_send, user_ids, {"title": title, "body": body, "url": url, "priority": priority})
