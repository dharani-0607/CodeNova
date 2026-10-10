"""Per-camera track history built from the tracker's IDs."""
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from geometry import Box, center, foot

PERSON = "person"
VEHICLES = {"car", "motorcycle", "bus", "truck"}
TWO_WHEELERS = {"motorcycle", "bicycle"}
ANIMALS = {"dog", "cat", "cow", "horse", "sheep", "elephant", "bear"}
DANGEROUS_ANIMALS = {"elephant", "bear"}
BAGS = {"backpack", "handbag", "suitcase"}
LITTER = {"bottle", "cup"}
TRACKED_CLASSES = {PERSON, "bicycle"} | VEHICLES | ANIMALS | BAGS | LITTER


@dataclass(eq=False)
class Track:
    id: int
    cls: str
    conf: float
    box: Box
    first_seen: float
    last_seen: float
    history: deque = field(default_factory=lambda: deque(maxlen=400))  # (t, box)
    keypoints: np.ndarray | None = None  # (17, 3) x, y, conf from the pose model
    kp_history: deque = field(default_factory=lambda: deque(maxlen=30))  # (t, keypoints)

    @property
    def foot(self):
        return foot(self.box)

    @property
    def center(self):
        return center(self.box)

    @property
    def height(self) -> float:
        return max(1.0, self.box[3] - self.box[1])

    @property
    def width(self) -> float:
        return max(1.0, self.box[2] - self.box[0])

    @property
    def age(self) -> float:
        return self.last_seen - self.first_seen

    def box_at(self, seconds_ago: float) -> Box | None:
        """Box from roughly `seconds_ago` seconds before the latest observation."""
        target = self.last_seen - seconds_ago
        best = None
        for t, b in self.history:
            if t <= target:
                best = b
            else:
                break
        return best

    def displacement(self, seconds: float) -> float | None:
        """Movement of the box centre over the last `seconds`, in pixels."""
        old = self.box_at(seconds)
        if old is None:
            return None
        c0, c1 = center(old), self.center
        return ((c1[0] - c0[0]) ** 2 + (c1[1] - c0[1]) ** 2) ** 0.5

    def speed_bodylengths(self, seconds: float = 1.0) -> float | None:
        """Movement per second relative to the object's own height (perspective-robust)."""
        d = self.displacement(seconds)
        if d is None:
            return None
        return d / self.height / seconds

    def is_stationary(self, seconds: float, tolerance: float = 0.3) -> bool:
        """No more than `tolerance` x own size of movement during the last `seconds`."""
        if self.age < seconds:
            return False
        d = self.displacement(seconds)
        return d is not None and d <= tolerance * max(self.width, self.height)


class TrackStore:
    def __init__(self, ttl: float = 3.0) -> None:
        self.tracks: dict[int, Track] = {}
        self.ttl = ttl

    def update(self, t: float, detections: list[tuple[int, str, float, Box]]) -> list[Track]:
        """detections: (track_id, class_name, confidence, box). Returns tracks visible now."""
        visible = []
        for tid, cls, conf, box in detections:
            tr = self.tracks.get(tid)
            if tr is None or tr.cls != cls:
                tr = Track(id=tid, cls=cls, conf=conf, box=box, first_seen=t, last_seen=t)
                self.tracks[tid] = tr
            tr.box, tr.conf, tr.last_seen = box, conf, t
            tr.history.append((t, box))
            visible.append(tr)
        for tid in [k for k, v in self.tracks.items() if t - v.last_seen > self.ttl]:
            del self.tracks[tid]
        return visible

    def get(self, tid: int) -> Track | None:
        return self.tracks.get(tid)
