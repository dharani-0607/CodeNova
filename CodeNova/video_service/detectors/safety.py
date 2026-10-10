"""Safety rules: fire/smoke, falls, fights, smoking.

Fire/smoke and smoking use extra YOLO models (public weights, see weights/README.md).
Falls and fights use the YOLOv8 pose model's keypoints with hand-written rules; these are
heuristics, so the backend sends their alerts to security for review by default.
"""
import math
from collections import deque

import cv2
import numpy as np

from geometry import center, dist
from tracking import PERSON

from .base import Detector, Event, FrameContext

# COCO keypoint indices
L_SHO, R_SHO, L_WRI, R_WRI, L_HIP, R_HIP = 5, 6, 9, 10, 11, 12
KP_CONF = 0.3


class FireSmokeDetector(Detector):
    """Fire/smoke model detections in at least 3 of the last 5 analysed frames.
    Without a model, an optional colour + flicker heuristic (off by default)."""

    key = "fire_smoke"

    def __init__(self, heuristic_fallback: bool = False) -> None:
        super().__init__()
        self.recent: deque = deque(maxlen=5)
        self.heuristic_fallback = heuristic_fallback
        self.prev_mask = None

    def _heuristic(self, frame: np.ndarray):
        small = cv2.resize(frame, (320, int(320 * frame.shape[0] / frame.shape[1])))
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (0, 120, 200), (35, 255, 255))
        ratio = float(np.count_nonzero(mask)) / mask.size
        flicker = 0.0
        if self.prev_mask is not None and self.prev_mask.shape == mask.shape:
            changed = cv2.bitwise_xor(mask, self.prev_mask)
            flicker = float(np.count_nonzero(changed)) / max(1, np.count_nonzero(mask))
        self.prev_mask = mask
        return ratio > 0.005 and flicker > 0.2, ratio

    def process(self, ctx):
        if ctx.fire_model_loaded:
            hits = [d for d in ctx.fire if d.conf >= 0.4]
            self.recent.append(hits)
            if sum(1 for h in self.recent if h) >= 3 and hits and self.once_per("fire", ctx.t, 60):
                kinds = sorted({d.cls for d in hits})
                return [Event(
                    "fire_smoke", f"{' and '.join(k.title() for k in kinds)} detected",
                    confidence=max(d.conf for d in hits), boxes=[d.box for d in hits],
                    extra={"classes": kinds, "method": "model"},
                )]
            return []
        if self.heuristic_fallback and ctx.frame is not None:
            hit, ratio = self._heuristic(ctx.frame)
            held = self.sustain.update("heur", hit, ctx.t)
            if held >= 3.0 and self.once_per("fire", ctx.t, 120):
                return [Event(
                    "fire_smoke", "Possible fire (colour/flicker check, no fire model installed) - verify",
                    confidence=0.3, extra={"method": "colour_heuristic", "area_ratio": round(ratio, 4)},
                )]
        return []


def _kp(kps, i):
    if kps is None or kps[i][2] < KP_CONF:
        return None
    return float(kps[i][0]), float(kps[i][1])


def torso_angle(kps) -> float | None:
    """Angle of the shoulder-midpoint -> hip-midpoint line from vertical, in degrees."""
    ls, rs, lh, rh = (_kp(kps, i) for i in (L_SHO, R_SHO, L_HIP, R_HIP))
    sho = [p for p in (ls, rs) if p]
    hip = [p for p in (lh, rh) if p]
    if not sho or not hip:
        return None
    sx, sy = sum(p[0] for p in sho) / len(sho), sum(p[1] for p in sho) / len(sho)
    hx, hy = sum(p[0] for p in hip) / len(hip), sum(p[1] for p in hip) / len(hip)
    return math.degrees(math.atan2(abs(hx - sx), abs(hy - sy) + 1e-6))


def is_lying(track) -> bool:
    ang = torso_angle(track.keypoints)
    if ang is not None:
        return ang > 60
    return track.width / track.height > 1.4


def was_upright(track, within: float) -> bool:
    for t, b in reversed(track.history):
        if track.last_seen - t > within:
            break
        w, h = b[2] - b[0], b[3] - b[1]
        if h > 1.2 * w:
            return True
    return False


class FallDetector(Detector):
    """Person goes from upright to lying (torso > 60 degrees from vertical) and stays down 2s,
    or lies motionless for 30s."""

    key = "fall"

    def process(self, ctx):
        events = []
        for p in ctx.of(PERSON):
            lying = is_lying(p)
            held = self.sustain.update(p.id, lying, ctx.t)
            sudden = lying and held >= 2.0 and was_upright(p, held + 4.0)
            motionless = lying and held >= 30.0 and p.is_stationary(10.0, 0.3)
            if (sudden or motionless) and self.once_per(p.id, ctx.t, 600):
                events.append(Event(
                    "fall",
                    "Person fell and is still down" if sudden else "Person lying motionless for 30s+",
                    confidence=0.6 if p.keypoints is not None else 0.4, dedupe_key=f"t{p.id}", boxes=[p.box],
                    extra={"torso_angle": torso_angle(p.keypoints), "seconds_down": round(held)},
                ))
        return events


def wrist_speed(track, window: float = 1.0) -> float | None:
    """Wrist path length over the last `window` seconds, in body-heights per second.
    Path length (not start-to-end distance) so rapid back-and-forth punches count."""
    if len(track.kp_history) < 3:
        return None
    t_end = track.kp_history[-1][0]
    recent = [(t, k) for t, k in track.kp_history if t_end - t <= window]
    if len(recent) < 3 or recent[-1][0] - recent[0][0] < 0.4:
        return None
    best = 0.0
    for i in (L_WRI, R_WRI):
        path = 0.0
        for (_, k0), (_, k1) in zip(recent, recent[1:]):
            a, b = _kp(k0, i), _kp(k1, i)
            if a and b:
                path += dist(a, b)
        best = max(best, path / track.height / (recent[-1][0] - recent[0][0]))
    return best


class FightDetector(Detector):
    """Two people close together, both with fast arm movement, for 1.5 seconds."""

    key = "fight"
    ARM_SPEED = 1.5  # body-heights per second

    def process(self, ctx):
        people = [p for p in ctx.of(PERSON) if p.keypoints is not None]
        events = []
        active_pairs = set()
        for i, a in enumerate(people):
            for b in people[i + 1:]:
                gap = dist(center(a.box), center(b.box))
                if gap > 0.9 * (a.height + b.height) / 2:
                    continue
                sa, sb = wrist_speed(a), wrist_speed(b)
                if sa is None or sb is None:
                    continue
                if max(sa, sb) >= self.ARM_SPEED and min(sa, sb) >= self.ARM_SPEED * 0.5:
                    active_pairs.add((min(a.id, b.id), max(a.id, b.id)))
        for pair in set(self.sustain.since) | active_pairs:
            held = self.sustain.update(pair, pair in active_pairs, ctx.t)
            if pair in active_pairs and held >= 1.5 and self.once_per(pair, ctx.t, 300):
                boxes = [ctx.store.get(i).box for i in pair if ctx.store.get(i)]
                events.append(Event(
                    "fight", "Possible fight: two people with fast aggressive arm movement",
                    confidence=0.5, dedupe_key=f"p{pair[0]}-{pair[1]}", boxes=boxes,
                ))
        return events


class SmokingDetector(Detector):
    """Cigarette/smoking model detections in 2 of the last 4 analysed frames."""

    key = "smoking"

    def __init__(self) -> None:
        super().__init__()
        self.recent: deque = deque(maxlen=4)

    def process(self, ctx):
        if not ctx.smoking_model_loaded:
            return []
        hits = [d for d in ctx.smoking if d.conf >= 0.4]
        self.recent.append(hits)
        if hits and sum(1 for h in self.recent if h) >= 2 and self.once_per("smoking", ctx.t, 120):
            # attach the nearest person for the snapshot
            boxes = [d.box for d in hits]
            for d in hits:
                c = center(d.box)
                near = [p for p in ctx.of(PERSON) if p.box[0] <= c[0] <= p.box[2] and p.box[1] <= c[1] <= p.box[3]]
                boxes += [p.box for p in near]
            return [Event(
                "smoking", "Person smoking on campus", confidence=max(d.conf for d in hits), boxes=boxes,
                extra={"classes": sorted({d.cls for d in hits})},
            )]
        return []
