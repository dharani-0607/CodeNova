"""Default data written on first start. Admins can change all of it from the dashboard."""
from sqlalchemy.orm import Session

from .models import EventType, Setting

# key, label, category, priority, requires_review, public_broadcast, notify_email, cooldown
DEFAULT_EVENT_TYPES = [
    # Camera detections
    ("crowd_density", "Crowd density exceeded", "camera", "high", False, False, False, 120),
    ("congestion", "Congestion / blocked movement", "camera", "medium", False, False, False, 180),
    ("intrusion", "Restricted-zone intrusion", "camera", "high", False, False, True, 60),
    ("loitering", "After-hours loitering", "camera", "medium", False, False, False, 300),
    ("unattended_object", "Unattended object", "camera", "high", True, False, True, 300),
    ("animal", "Animal on campus", "camera", "medium", False, False, False, 300),
    ("dangerous_animal", "Dangerous animal (elephant / bear)", "camera", "critical", False, True, True, 120),
    ("vehicle_pedestrian_zone", "Vehicle in pedestrian zone", "camera", "medium", False, False, False, 120),
    ("wrong_parking", "No-parking violation", "camera", "low", False, False, False, 600),
    ("triple_riding", "Triple riding on two-wheeler", "camera", "medium", False, False, False, 60),
    ("speeding", "Speeding (over campus limit)", "camera", "medium", False, False, False, 30),
    ("fire_smoke", "Fire / smoke", "camera", "critical", False, False, True, 120),
    ("fight", "Fight / violence", "camera", "high", True, False, True, 120),
    ("fall", "Person fallen", "camera", "high", True, False, False, 120),
    ("smoking", "Smoking on campus", "camera", "low", True, False, False, 300),
    ("littering", "Littering", "camera", "low", True, False, False, 300),
    ("camera_offline", "Camera offline", "camera", "medium", False, False, True, 600),
    # Geofenced user reports
    ("report_medical", "Medical emergency", "report", "critical", False, False, True, 0),
    ("report_fire", "Fire", "report", "critical", False, False, True, 0),
    ("report_safety", "Safety hazard", "report", "high", False, False, False, 0),
    ("report_harassment", "Harassment / ragging", "report", "high", False, False, True, 0),
    ("report_suspicious", "Suspicious activity", "report", "medium", False, False, False, 0),
    ("report_animal", "Animal sighting", "report", "medium", False, False, False, 0),
    ("report_traffic", "Traffic / parking violation", "report", "low", False, False, False, 0),
    ("report_infrastructure", "Infrastructure issue", "report", "low", False, False, False, 0),
    ("report_other", "Other", "report", "low", False, False, False, 0),
]

# Approximate outline of Amrita Vishwa Vidyapeetham, Coimbatore (Ettimadai).
# It is a rough box, so an admin must trace the real boundary in Admin -> Geofence.
DEFAULT_GEOFENCE = [
    [10.9105, 76.8930],
    [10.9105, 76.9085],
    [10.8955, 76.9085],
    [10.8955, 76.8930],
]

DEFAULT_SETTINGS = {
    "geofence": DEFAULT_GEOFENCE,
    "campus_center": [10.9027, 76.9006],
    "speed_limit_kmh": 20,
    # Reports are refused when the phone reports worse GPS accuracy than this.
    "max_gps_accuracy_m": 200,
    "after_hours": {"from": "22:00", "to": "05:00"},
    "moderation": {
        "flag_threshold": 0.5,
        "remove_threshold": 0.85,
        # Words or phrases that break campus rules. Matching posts are removed.
        "banned_terms": [
            "ragging", "alcohol party", "liquor", "drugs", "ganja", "weed", "cigarettes for sale",
            "bet", "betting", "gambling", "exam leak", "question paper leak", "paper leak",
            "fake news", "nude", "porn",
        ],
        # Words that send a post to the admin review queue instead of removing it.
        "review_terms": [
            "protest", "strike", "boycott", "hostel fight", "politics", "election", "fees hike",
        ],
    },
}


def seed_defaults(db: Session) -> None:
    for key, label, category, prio, review, public, email, cooldown in DEFAULT_EVENT_TYPES:
        if db.get(EventType, key) is None:
            db.add(
                EventType(
                    key=key, label=label, category=category, default_priority=prio,
                    requires_review=review, public_broadcast=public, notify_email=email,
                    cooldown_seconds=cooldown,
                )
            )
    for key, value in DEFAULT_SETTINGS.items():
        if db.get(Setting, key) is None:
            db.add(Setting(key=key, value=value))
    db.commit()


def get_setting(db: Session, key: str):
    row = db.get(Setting, key)
    if row is not None:
        return row.value
    return DEFAULT_SETTINGS.get(key)


def set_setting(db: Session, key: str, value) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.commit()
