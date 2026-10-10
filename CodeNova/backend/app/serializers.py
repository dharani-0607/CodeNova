"""Model -> JSON dict helpers."""
from .models import Alert, Camera, Comment, EventType, NewsPost, Notification, User, Zone


def media_url(path: str | None) -> str | None:
    return f"/media/{path}" if path else None


def user_out(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "name": u.name, "role": u.role,
        "is_verified": u.is_verified, "is_active": u.is_active, "created_at": u.created_at,
    }


def zone_out(z: Zone) -> dict:
    return {
        "id": z.id, "camera_id": z.camera_id, "name": z.name, "kind": z.kind,
        "polygon": z.polygon, "params": z.params or {}, "enabled": z.enabled,
    }


def camera_out(c: Camera, with_zones: bool = True) -> dict:
    out = {
        "id": c.id, "name": c.name, "source": c.source, "location_name": c.location_name,
        "lat": c.lat, "lon": c.lon, "enabled": c.enabled, "detectors": c.detectors or {},
        "calibration": c.calibration or {}, "params": c.params or {},
    }
    if with_zones:
        out["zones"] = [zone_out(z) for z in c.zones]
    return out


def event_type_out(e: EventType) -> dict:
    return {
        "key": e.key, "label": e.label, "category": e.category,
        "default_priority": e.default_priority, "requires_review": e.requires_review,
        "public_broadcast": e.public_broadcast, "notify_email": e.notify_email,
        "notify_push": e.notify_push, "enabled": e.enabled, "cooldown_seconds": e.cooldown_seconds,
    }


def alert_out(a: Alert, include_reporter: bool = True) -> dict:
    out = {
        "id": a.id, "event_type": a.event_type, "source": a.source, "camera_id": a.camera_id,
        "camera_name": a.camera.name if a.camera else None, "zone_id": a.zone_id,
        "title": a.title, "description": a.description, "priority": a.priority, "status": a.status,
        "confidence": a.confidence, "lat": a.lat, "lon": a.lon, "location_name": a.location_name,
        "image_url": media_url(a.image_path), "extra": a.extra or {}, "broadcast": a.broadcast,
        "notes": a.notes, "created_at": a.created_at, "updated_at": a.updated_at,
    }
    if include_reporter and a.reporter:
        out["reporter"] = {"id": a.reporter.id, "name": a.reporter.name, "email": a.reporter.email}
    return out


def comment_out(c: Comment, staff: bool = False) -> dict:
    out = {
        "id": c.id, "post_id": c.post_id, "body": c.body, "status": c.status,
        "author": {"id": c.author.id, "name": c.author.name}, "created_at": c.created_at,
    }
    if staff:
        out["moderation"] = c.moderation
    return out


def post_out(p: NewsPost, staff: bool = False, viewer_id: int | None = None) -> dict:
    visible_comments = [
        c for c in p.comments
        if c.status == "published" or staff or c.author_id == viewer_id
    ]
    out = {
        "id": p.id, "title": p.title, "body": p.body, "category": p.category,
        "is_important": p.is_important, "is_official": p.is_official, "status": p.status,
        "author": {"id": p.author.id, "name": p.author.name, "role": p.author.role},
        "created_at": p.created_at,
        "comments": [comment_out(c, staff) for c in sorted(visible_comments, key=lambda c: c.created_at)],
    }
    if staff or p.author_id == viewer_id:
        out["moderation"] = p.moderation
    return out


def notification_out(n: Notification) -> dict:
    return {
        "id": n.id, "kind": n.kind, "ref_id": n.ref_id, "title": n.title, "body": n.body,
        "priority": n.priority, "audience": n.audience, "created_at": n.created_at,
    }
