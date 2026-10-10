"""Object rules: unattended bags, animals, littering."""
from geometry import dist
from tracking import ANIMALS, BAGS, DANGEROUS_ANIMALS, LITTER, PERSON

from .base import Detector, Event, FrameContext


def _nearest_person(ctx: FrameContext, pt, max_d: float):
    best, best_d = None, max_d
    for p in ctx.of(PERSON):
        d = dist(pt, p.center)
        if d <= best_d:
            best, best_d = p, d
    return best


class UnattendedObjectDetector(Detector):
    """Backpack, handbag or suitcase that has not moved and has had nobody near it
    for `unattended_seconds` (camera param, default 60)."""

    key = "unattended_object"

    def process(self, ctx):
        limit = float(ctx.cam_param("unattended_seconds", 60))
        events = []
        for bag in ctx.of(BAGS):
            near_d = max(150.0, 3 * max(bag.width, bag.height))
            alone = bag.is_stationary(min(5.0, limit), 0.5) and _nearest_person(ctx, bag.center, near_d) is None
            held = self.sustain.update(bag.id, alone, ctx.t)
            if held >= limit and self.once_per(bag.id, ctx.t, 1800):
                events.append(Event(
                    "unattended_object", f"{bag.cls.title()} left unattended for {held:.0f}s",
                    confidence=bag.conf, dedupe_key=f"t{bag.id}", boxes=[bag.box], extra={"object": bag.cls},
                ))
        return events


class AnimalDetector(Detector):
    """Dogs, cattle, horses, sheep, cats; elephants and bears are raised as dangerous."""

    key = "animal"
    MIN_CONF = 0.45

    def process(self, ctx):
        events = []
        for a in ctx.of(ANIMALS):
            if a.conf < self.MIN_CONF or a.age < 1.0:
                continue
            dangerous = a.cls in DANGEROUS_ANIMALS
            if not self.once_per(a.id, ctx.t, 900):
                continue
            events.append(Event(
                "dangerous_animal" if dangerous else "animal",
                f"{a.cls.title()} spotted" + (" - keep away and alert forest/security team" if dangerous else ""),
                confidence=a.conf, dedupe_key=a.cls, boxes=[a.box], extra={"animal": a.cls},
            ))
        return events


class LitteringDetector(Detector):
    """A bottle/cup that appeared next to a person, stayed put for 10s after that person
    walked away. If the camera has 'littering' zones the rule only applies inside them."""

    key = "littering"

    def __init__(self) -> None:
        super().__init__()
        self.owner: dict[int, int] = {}  # object track -> person track nearby when it appeared

    def process(self, ctx):
        zones = ctx.zones_of("littering")
        events = []
        for obj in ctx.of(LITTER):
            if zones and not any(z.contains(obj.center) for z in zones):
                continue
            if obj.id not in self.owner:
                p = _nearest_person(ctx, obj.center, max(120.0, 4 * max(obj.width, obj.height)))
                self.owner[obj.id] = p.id if p else -1
            owner_id = self.owner[obj.id]
            if owner_id < 0:
                continue
            owner = ctx.store.get(owner_id)
            owner_gone = owner is None or ctx.t - owner.last_seen > 1.0 or dist(owner.center, obj.center) > 3 * owner.height
            left = obj.is_stationary(5.0, 0.5) and owner_gone
            held = self.sustain.update(obj.id, left, ctx.t)
            if held >= 10.0 and self.once_per(obj.id, ctx.t, 3600):
                events.append(Event(
                    "littering", f"{obj.cls.title()} left behind by a person who walked away",
                    confidence=min(obj.conf, 0.6), dedupe_key=f"t{obj.id}", boxes=[obj.box],
                    extra={"object": obj.cls, "person_track": owner_id},
                ))
        live = {t.id for t in ctx.tracks}
        for k in [k for k in self.owner if k not in live and k not in ctx.store.tracks]:
            del self.owner[k]
        return events
