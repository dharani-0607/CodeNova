from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Roles
ADMIN, SECURITY, USER = "admin", "security", "user"
STAFF_ROLES = {ADMIN, SECURITY}

# Priorities, highest first
PRIORITIES = ["critical", "high", "medium", "low"]
PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITIES)}

# Alert statuses
PENDING_REVIEW, OPEN, ACKNOWLEDGED, RESOLVED, DISMISSED = (
    "pending_review", "open", "acknowledged", "resolved", "dismissed",
)
ALERT_STATUSES = [PENDING_REVIEW, OPEN, ACKNOWLEDGED, RESOLVED, DISMISSED]

# Moderation statuses for news posts and comments
PUBLISHED, FLAGGED, REMOVED = "published", "flagged", "removed"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=USER)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    verify_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    verify_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    # RTSP/HTTP URL, a video file path, or a webcam index such as "0".
    source: Mapped[str] = mapped_column(String(500))
    location_name: Mapped[str] = mapped_column(String(200), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Which detectors run on this camera, e.g. {"crowd": true, "fire_smoke": true}
    detectors: Mapped[dict] = mapped_column(JSON, default=dict)
    # Speed calibration: {"line_a": [[x,y],[x,y]], "line_b": [[x,y],[x,y]], "distance_m": 10}
    # Coordinates are normalised 0..1 relative to the frame.
    calibration: Mapped[dict] = mapped_column(JSON, default=dict)
    # Per-camera thresholds, e.g. {"crowd_warn": 25, "crowd_critical": 50}
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    zones: Mapped[list["Zone"]] = relationship(back_populates="camera", cascade="all, delete-orphan")


ZONE_KINDS = ["restricted", "pedestrian", "no_parking", "crowd", "after_hours", "littering"]


class Zone(Base):
    __tablename__ = "zones"
    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(30))
    # Polygon as [[x, y], ...] normalised 0..1 on the camera frame.
    polygon: Mapped[list] = mapped_column(JSON, default=list)
    # e.g. {"active_from": "22:00", "active_to": "05:00", "dwell_seconds": 60, "max_people": 40}
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    camera: Mapped[Camera] = relationship(back_populates="zones")


class EventType(Base):
    """Configurable behaviour per kind of event (priority, review, notifications)."""

    __tablename__ = "event_types"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    label: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(30), default="camera")  # camera | report
    default_priority: Mapped[str] = mapped_column(String(20), default="medium")
    # When True, alerts wait in a review queue for security before being broadcast.
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False)
    # When True, confirmed alerts are announced to every campus user, not just staff.
    public_broadcast: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_push: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Ignore repeat detections of the same type on the same camera/zone within this window.
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=60)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(ForeignKey("event_types.key"), index=True)
    source: Mapped[str] = mapped_column(String(20), default="camera")  # camera | report | manual
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    zone_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reporter_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    status: Mapped[str] = mapped_column(String(20), default=OPEN, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_name: Mapped[str] = mapped_column(String(200), default="")
    image_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    broadcast: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    handled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    reporter: Mapped[User | None] = relationship(foreign_keys=[reporter_id])
    camera: Mapped[Camera | None] = relationship()


class NewsPost(Base):
    __tablename__ = "news_posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40), default="general")
    is_important: Mapped[bool] = mapped_column(Boolean, default=False)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default=PUBLISHED, index=True)
    moderation: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    author: Mapped[User] = relationship()
    comments: Mapped[list["Comment"]] = relationship(back_populates="post", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("news_posts.id", ondelete="CASCADE"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=PUBLISHED, index=True)
    moderation: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    post: Mapped[NewsPost] = relationship(back_populates="comments")
    author: Mapped[User] = relationship()


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    endpoint: Mapped[str] = mapped_column(String(1000), unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    """History of everything pushed to the dashboard notification centre."""

    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    audience: Mapped[str] = mapped_column(String(20), default="all")  # all | staff
    kind: Mapped[str] = mapped_column(String(20))  # alert | news | system
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Setting(Base):
    """Key/value store for admin-editable settings (geofence, speed limit, moderation rules)."""

    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict | list | str | int | float | None] = mapped_column(JSON)
