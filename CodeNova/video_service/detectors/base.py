from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from geometry import Box, Point, denorm, foot, point_in_polygon
from tracking import Track, TrackStore


@dataclass
class ZoneCfg:
    id: int
    name: str
    kind: str
    polygon: list[Point]  # pixels
    params: dict

    def contains(self, pt: Point) -> bool:
        return point_in_polygon(pt, self.polygon)

    def contains_box_foot(self, box: Box) -> bool:
        return self.contains(foot(box))


@dataclass
class ExtraDetection:
    cls: str
    conf: float
    box: Box


@dataclass
class FrameContext:
    t: float  # monotonic-ish seconds (time.time())
    now: datetime  # local wall-clock time, for after-hours windows
    frame: np.ndarray | None
    width: int
    height: int
    tracks: list[Track]
    store: TrackStore
    zones: list[ZoneCfg]
    camera: dict
    global_cfg: dict
    fire: list[ExtraDetection] = field(default_factory=list)
    smoking: list[ExtraDetection] = field(default_factory=list)
    fire_model_loaded: bool = False
    smoking_model_loaded: bool = False

    def of(self, classes) -> list[Track]:
        if isinstance(classes, str):
            classes = {classes}
        return [t for t in self.tracks if t.cls in classes]

    def zones_of(self, kind: str) -> list[ZoneCfg]:
        return [z for z in self.zones if z.kind == kind]

    def cam_param(self, key: str, default):
        return (self.camera.get("params") or {}).get(key, default)


@dataclass
class Event:
    event_type: str
    description: str
    confidence: float | None = None
    zone_id: int | None = None
    dedupe_key: str | None = None
    boxes: list[Box] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


class Sustain:
    """Tracks how long a keyed condition has been continuously true."""

    def __init__(self, grace: float = 1.0) -> None:
        self.since: dict = {}
        self.last_true: dict = {}
        self.grace = grace  # tolerate short dropouts (missed detections)

    def update(self, key, active: bool, t: float) -> float:
        if active:
            if key not in self.since or t - self.last_true.get(key, t) > self.grace:
                self.since[key] = t
            self.last_true[key] = t
            return t - self.since[key]
        if key in self.last_true and t - self.last_true[key] > self.grace:
            self.since.pop(key, None)
            self.last_true.pop(key, None)
        return 0.0

    def reset(self, key) -> None:
        self.since.pop(key, None)
        self.last_true.pop(key, None)


class Detector:
    """Base class. `key` is the camera detector toggle name."""

    key: str = ""

    def __init__(self) -> None:
        self.sustain = Sustain()
        self._fired: dict = {}

    def once_per(self, key, t: float, seconds: float) -> bool:
        """Local rate limit so one situation does not produce an event every frame."""
        last = self._fired.get(key)
        if last is not None and t - last < seconds:
            return False
        self._fired[key] = t
        return True

    def process(self, ctx: FrameContext) -> list[Event]:
        raise NotImplementedError


def build_zones(camera: dict, w: int, h: int) -> list[ZoneCfg]:
    out = []
    for z in camera.get("zones", []):
        if not z.get("enabled", True) or len(z.get("polygon", [])) < 3:
            continue
        out.append(ZoneCfg(z["id"], z["name"], z["kind"], denorm(z["polygon"], w, h), z.get("params") or {}))
    return out
