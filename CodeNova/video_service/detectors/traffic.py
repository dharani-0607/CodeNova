"""Traffic rules: triple riding and speeding."""
from geometry import denorm, intersection, box_area, expand, segment_intersection, foot
from tracking import PERSON, VEHICLES

from .base import Detector, Event, FrameContext


class TripleRidingDetector(Detector):
    """Three or more people overlapping one motorcycle for 1 second."""

    key = "triple_riding"

    @staticmethod
    def riders(ctx: FrameContext, bike) -> list:
        # Riders sit above the bike, so extend the bike box upwards and a little sideways.
        region = (bike.box[0] - 0.15 * bike.width, bike.box[1] - 1.2 * bike.height,
                  bike.box[2] + 0.15 * bike.width, bike.box[3] + 0.1 * bike.height)
        out = []
        for p in ctx.of(PERSON):
            overlap = intersection(p.box, region) / max(1.0, box_area(p.box))
            cx = p.center[0]
            if overlap >= 0.5 and bike.box[0] - 0.1 * bike.width <= cx <= bike.box[2] + 0.1 * bike.width \
                    and p.box[3] >= bike.box[1]:
                out.append(p)
        return out

    def process(self, ctx):
        events = []
        for bike in ctx.of("motorcycle"):
            riders = self.riders(ctx, bike)
            held = self.sustain.update(bike.id, len(riders) >= 3, ctx.t)
            if held >= 1.0 and self.once_per(bike.id, ctx.t, 600):
                events.append(Event(
                    "triple_riding", f"{len(riders)} people riding one two-wheeler",
                    confidence=min([bike.conf] + [r.conf for r in riders]), dedupe_key=f"t{bike.id}",
                    boxes=[bike.box] + [r.box for r in riders], extra={"riders": len(riders)},
                ))
        return events


class SpeedDetector(Detector):
    """Average speed between two calibrated lines across the road.

    Camera calibration: {"line_a": [[x,y],[x,y]], "line_b": [[x,y],[x,y]], "distance_m": 12}
    (normalised coordinates, distance measured on the ground between the two lines).
    A vehicle crossing both lines gets speed = distance / time; above the campus limit -> event.
    """

    key = "speeding"
    VEHICLE_CLASSES = VEHICLES | {"bicycle"}

    def __init__(self) -> None:
        super().__init__()
        self.crossings: dict[int, dict[str, float]] = {}
        self.last_speed: dict[int, float] = {}

    def process(self, ctx):
        cal = ctx.camera.get("calibration") or {}
        if not (cal.get("line_a") and cal.get("line_b") and cal.get("distance_m")):
            return []
        lines = {
            "a": denorm(cal["line_a"], ctx.width, ctx.height),
            "b": denorm(cal["line_b"], ctx.width, ctx.height),
        }
        distance = float(cal["distance_m"])
        limit = float(ctx.global_cfg.get("speed_limit_kmh") or 20)
        events = []
        for v in ctx.of(self.VEHICLE_CLASSES):
            if len(v.history) < 2:
                continue
            (t0, b0), (t1, b1) = v.history[-2], v.history[-1]
            p0, p1 = foot(b0), foot(b1)
            seen = self.crossings.setdefault(v.id, {})
            for name, (q1, q2) in lines.items():
                if name in seen:
                    continue
                frac = segment_intersection(p0, p1, q1, q2)
                if frac is not None:
                    seen[name] = t0 + frac * (t1 - t0)
            if "a" in seen and "b" in seen and v.id not in self.last_speed:
                dt = abs(seen["b"] - seen["a"])
                if dt <= 0.05:
                    continue
                kmh = distance / dt * 3.6
                self.last_speed[v.id] = kmh
                if kmh > limit:
                    events.append(Event(
                        "speeding", f"{v.cls.title()} at {kmh:.0f} km/h (limit {limit:.0f} km/h)",
                        confidence=v.conf, dedupe_key=f"t{v.id}", boxes=[v.box],
                        extra={"speed_kmh": round(kmh, 1), "limit_kmh": limit, "vehicle": v.cls},
                    ))
        # forget vehicles that left
        for tid in [k for k in self.crossings if k not in ctx.store.tracks]:
            self.crossings.pop(tid, None)
            self.last_speed.pop(tid, None)
        return events
