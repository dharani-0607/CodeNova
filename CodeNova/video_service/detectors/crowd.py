"""Crowd density and congestion.

Density: number of people inside a crowd zone (or the whole frame if the camera has none)
reaches the zone's `max_people` (default: camera param `crowd_warn`, else 30) for 5 seconds.
If the zone has `area_m2`, people per square metre is also checked against `max_density`
(default 2.0 p/m², where movement starts to get restricted).

Congestion: at least `congestion_people` (default 12) people in the zone and their median
movement is below 0.15 body-heights per second for 20 seconds, i.e. people are stuck.
"""
import statistics

from geometry import polygon_area
from tracking import PERSON

from .base import Detector, Event, FrameContext, ZoneCfg


class CrowdDetector(Detector):
    key = "crowd"
    SUSTAIN_DENSITY = 5.0
    SUSTAIN_CONGESTION = 20.0
    SLOW = 0.15

    def process(self, ctx: FrameContext) -> list[Event]:
        people = ctx.of(PERSON)
        zones = ctx.zones_of("crowd")
        if not zones:
            full = [(0, 0), (ctx.width, 0), (ctx.width, ctx.height), (0, ctx.height)]
            zones = [ZoneCfg(0, "full view", "crowd", full, {})]
        events = []
        for z in zones:
            inside = [p for p in people if z.contains(p.foot)]
            n = len(inside)
            max_people = int(z.params.get("max_people", ctx.cam_param("crowd_warn", 30)))
            density = None
            if z.params.get("area_m2"):
                density = n / float(z.params["area_m2"])
            max_density = float(z.params.get("max_density", 2.0))
            over = n >= max_people or (density is not None and density >= max_density)
            zid = z.id or None
            held = self.sustain.update(("density", z.id), over, ctx.t)
            if over and held >= self.SUSTAIN_DENSITY and self.once_per(("density", z.id), ctx.t, 60):
                desc = f"{n} people in {z.name} (limit {max_people})"
                if density is not None:
                    desc += f", {density:.1f} people/m²"
                events.append(Event(
                    "crowd_density", desc, confidence=min(1.0, n / max(1, max_people)), zone_id=zid,
                    boxes=[p.box for p in inside], extra={"people": n, "limit": max_people, "density": density},
                ))

            min_people = int(z.params.get("congestion_people", ctx.cam_param("congestion_people", 12)))
            speeds = [s for s in (p.speed_bodylengths(1.0) for p in inside) if s is not None]
            stuck = n >= min_people and len(speeds) >= min_people // 2 and statistics.median(speeds) < self.SLOW
            held = self.sustain.update(("congestion", z.id), stuck, ctx.t)
            if stuck and held >= self.SUSTAIN_CONGESTION and self.once_per(("congestion", z.id), ctx.t, 120):
                events.append(Event(
                    "congestion",
                    f"{n} people barely moving in {z.name} for {held:.0f}s",
                    confidence=0.7, zone_id=zid, boxes=[p.box for p in inside],
                    extra={"people": n, "median_speed": round(statistics.median(speeds), 3)},
                ))
        return events


def zone_area_px(z: ZoneCfg) -> float:
    return polygon_area(z.polygon)
