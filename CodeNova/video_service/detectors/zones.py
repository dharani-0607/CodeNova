"""Zone rules: restricted-area intrusion, after-hours loitering, vehicles in pedestrian
zones and no-parking violations."""
from geometry import in_time_window
from tracking import PERSON, VEHICLES

from .base import Detector, Event, FrameContext, ZoneCfg


def zone_active(z: ZoneCfg, ctx: FrameContext) -> bool:
    start, end = z.params.get("active_from"), z.params.get("active_to")
    if start and end:
        return in_time_window(ctx.now, start, end)
    return True


class IntrusionDetector(Detector):
    """Person inside a restricted zone for `min_seconds` (default 1s).
    Optional zone params active_from/active_to limit the rule to certain hours."""

    key = "intrusion"

    def process(self, ctx):
        events = []
        for z in ctx.zones_of("restricted"):
            if not zone_active(z, ctx):
                continue
            min_s = float(z.params.get("min_seconds", 1.0))
            inside = [p for p in ctx.of(PERSON) if z.contains(p.foot)]
            inside_ids = {p.id for p in inside}
            for p in ctx.of(PERSON):
                self.sustain.update((z.id, p.id), p.id in inside_ids, ctx.t)
            offenders = [p for p in inside if ctx.t - self.sustain.since.get((z.id, p.id), ctx.t) >= min_s]
            if offenders and self.once_per(z.id, ctx.t, 30):
                events.append(Event(
                    "intrusion", f"{len(offenders)} person(s) entered restricted zone '{z.name}'",
                    confidence=max(p.conf for p in offenders), zone_id=z.id,
                    boxes=[p.box for p in offenders], extra={"people": len(offenders)},
                ))
        return events


class LoiteringDetector(Detector):
    """Person staying `dwell_seconds` (default 60) in an after-hours zone during its window.
    Window: zone params active_from/active_to, else the campus after-hours setting.
    Cameras with no after_hours zones apply the rule to the whole frame."""

    key = "loitering"

    def process(self, ctx):
        zones = ctx.zones_of("after_hours")
        if not zones:
            full = [(0, 0), (ctx.width, 0), (ctx.width, ctx.height), (0, ctx.height)]
            zones = [ZoneCfg(0, "camera view", "after_hours", full, {})]
        after = ctx.global_cfg.get("after_hours") or {"from": "22:00", "to": "05:00"}
        events = []
        for z in zones:
            start = z.params.get("active_from", after.get("from", "22:00"))
            end = z.params.get("active_to", after.get("to", "05:00"))
            active = in_time_window(ctx.now, start, end)
            dwell = float(z.params.get("dwell_seconds", ctx.cam_param("loiter_seconds", 60)))
            for p in ctx.of(PERSON):
                held = self.sustain.update((z.id, p.id), active and z.contains(p.foot), ctx.t)
                if held >= dwell and self.once_per((z.id, p.id), ctx.t, 600):
                    events.append(Event(
                        "loitering", f"Person loitering in {z.name} for {held/60:.1f} min after hours ({start}-{end})",
                        confidence=p.conf, zone_id=z.id or None, dedupe_key=f"t{p.id}", boxes=[p.box],
                        extra={"dwell_seconds": round(held)},
                    ))
        return events


class VehicleZoneDetector(Detector):
    """Car, motorcycle, bus or truck inside a pedestrian-only zone for 2 seconds."""

    key = "vehicle_zone"

    def process(self, ctx):
        events = []
        for z in ctx.zones_of("pedestrian"):
            if not zone_active(z, ctx):
                continue
            for v in ctx.of(VEHICLES):
                held = self.sustain.update((z.id, v.id), z.contains(v.foot), ctx.t)
                if held >= 2.0 and self.once_per((z.id, v.id), ctx.t, 300):
                    events.append(Event(
                        "vehicle_pedestrian_zone", f"{v.cls.title()} in pedestrian zone '{z.name}'",
                        confidence=v.conf, zone_id=z.id, dedupe_key=f"t{v.id}", boxes=[v.box],
                        extra={"vehicle": v.cls},
                    ))
        return events


class WrongParkingDetector(Detector):
    """Vehicle stationary inside a no-parking zone for `max_seconds` (default 120)."""

    key = "wrong_parking"

    def process(self, ctx):
        events = []
        for z in ctx.zones_of("no_parking"):
            if not zone_active(z, ctx):
                continue
            limit = float(z.params.get("max_seconds", 120))
            for v in ctx.of(VEHICLES):
                parked = z.contains(v.foot) and v.is_stationary(min(10.0, limit), 0.2)
                held = self.sustain.update((z.id, v.id), parked, ctx.t)
                # held counts from when it became stationary; add the initial 10 s window
                if parked and held + min(10.0, limit) >= limit and self.once_per((z.id, v.id), ctx.t, 1800):
                    events.append(Event(
                        "wrong_parking", f"{v.cls.title()} parked in no-parking zone '{z.name}'",
                        confidence=v.conf, zone_id=z.id, dedupe_key=f"t{v.id}", boxes=[v.box],
                        extra={"vehicle": v.cls},
                    ))
        return events
