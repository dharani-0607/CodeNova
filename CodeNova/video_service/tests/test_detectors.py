"""Detector rules on synthetic tracks (no models or video needed)."""
from datetime import datetime

import numpy as np

from detectors import FrameContext, build_zones
from detectors.crowd import CrowdDetector
from detectors.objects import AnimalDetector, LitteringDetector, UnattendedObjectDetector
from detectors.safety import FallDetector, FightDetector, FireSmokeDetector, SmokingDetector
from detectors.base import ExtraDetection
from detectors.traffic import SpeedDetector, TripleRidingDetector
from detectors.zones import IntrusionDetector, LoiteringDetector, VehicleZoneDetector, WrongParkingDetector
from geometry import in_time_window, segment_intersection
from tracking import TrackStore

W, H = 1000, 1000
DAY = datetime(2026, 10, 10, 14, 0)
NIGHT = datetime(2026, 10, 10, 23, 30)


def cam(zones=(), calibration=None, params=None):
    return {"id": 1, "name": "cam", "zones": list(zones), "calibration": calibration or {}, "params": params or {}}


def zone(zid, kind, poly, **params):
    return {"id": zid, "name": f"z{zid}", "kind": kind, "polygon": poly, "params": params, "enabled": True}


LEFT_HALF = [[0, 0], [0.5, 0], [0.5, 1], [0, 1]]


class Sim:
    def __init__(self, camera, now=DAY, fps=4.0):
        self.camera, self.now, self.store, self.t, self.dt = camera, now, TrackStore(), 1000.0, 1 / fps

    def step(self, dets, detector, **extra):
        """dets: (id, cls, box) or (id, cls, box, conf)."""
        self.t += self.dt
        norm = [(d[0], d[1], d[3] if len(d) > 3 else 0.9, d[2]) for d in dets]
        tracks = self.store.update(self.t, norm)
        kps = extra.pop("keypoints", {})
        for tr in tracks:
            if tr.id in kps:
                tr.keypoints = kps[tr.id]
                tr.kp_history.append((self.t, kps[tr.id]))
        ctx = FrameContext(
            t=self.t, now=self.now, frame=None, width=W, height=H, tracks=tracks, store=self.store,
            zones=build_zones(self.camera, W, H), camera=self.camera,
            global_cfg={"speed_limit_kmh": 20, "after_hours": {"from": "22:00", "to": "05:00"}}, **extra,
        )
        return detector.process(ctx)

    def run(self, seconds, dets_fn, detector, **extra):
        events = []
        for i in range(int(seconds / self.dt)):
            events += self.step(dets_fn(i), detector, **extra)
        return events


def person(i, x, y, w=40, h=100):
    return (i, "person", (x, y, x + w, y + h))


def test_geometry_helpers():
    assert segment_intersection((0, 0), (10, 0), (5, -5), (5, 5)) == 0.5
    assert segment_intersection((0, 0), (4, 0), (5, -5), (5, 5)) is None
    assert in_time_window(NIGHT, "22:00", "05:00")
    assert not in_time_window(DAY, "22:00", "05:00")
    assert in_time_window(DAY, "09:00", "17:00")


def test_crowd_density_needs_sustained_count():
    sim = Sim(cam(params={"crowd_warn": 10}))
    det = CrowdDetector()
    crowd = [person(i, 50 * i, 300) for i in range(12)]
    assert not sim.run(3, lambda i: [person(i, 50 * i, 300) for i in range(5)], det)  # below limit
    assert not sim.run(4, lambda i: crowd, det)  # over limit, but not yet 5 seconds
    events = sim.run(3, lambda i: crowd, det)
    assert [e.event_type for e in events].count("crowd_density") == 1


def test_congestion_when_crowd_stops_moving():
    sim = Sim(cam(params={"crowd_warn": 100, "congestion_people": 12}))
    det = CrowdDetector()
    crowd = [person(i, 50 * i, 300) for i in range(15)]
    events = sim.run(25, lambda i: crowd, det)
    assert any(e.event_type == "congestion" for e in events)
    # moving crowd: no congestion
    sim2, det2 = Sim(cam(params={"crowd_warn": 100})), CrowdDetector()
    moving = lambda i: [person(j, 50 * j, (300 + 60 * i) % 800) for j in range(15)]  # noqa: E731
    assert not any(e.event_type == "congestion" for e in sim2.run(25, moving, det2))


def test_intrusion_only_inside_restricted_zone():
    sim = Sim(cam([zone(5, "restricted", LEFT_HALF)]))
    det = IntrusionDetector()
    assert not sim.run(3, lambda i: [person(1, 700, 300)], det)
    events = sim.run(3, lambda i: [person(1, 100, 300)], det)
    assert len(events) == 1 and events[0].zone_id == 5


def test_intrusion_respects_active_hours():
    sim = Sim(cam([zone(5, "restricted", LEFT_HALF, active_from="22:00", active_to="06:00")]), now=DAY)
    assert not sim.run(3, lambda i: [person(1, 100, 300)], IntrusionDetector())


def test_loitering_only_after_hours():
    det = LoiteringDetector()
    day = Sim(cam(params={"loiter_seconds": 10}), now=DAY)
    assert not day.run(15, lambda i: [person(1, 100, 300)], det)
    night = Sim(cam(params={"loiter_seconds": 10}), now=NIGHT)
    events = night.run(15, lambda i: [person(1, 100, 300)], LoiteringDetector())
    assert len(events) == 1


def test_vehicle_in_pedestrian_zone_and_parking():
    sim = Sim(cam([zone(2, "pedestrian", LEFT_HALF), zone(3, "no_parking", [[0.5, 0], [1, 0], [1, 1], [0.5, 1]], max_seconds=20)]))
    car_ped = lambda i: [(7, "car", (100, 300, 300, 420))]  # noqa: E731
    assert len(sim.run(3, car_ped, VehicleZoneDetector())) == 1
    det = WrongParkingDetector()
    parked = lambda i: [(8, "car", (600, 300, 800, 420))]  # noqa: E731
    assert not sim.run(10, parked, det)
    assert len(sim.run(15, parked, det)) == 1


def test_unattended_bag():
    sim = Sim(cam(params={"unattended_seconds": 20}))
    det = UnattendedObjectDetector()
    bag = (3, "backpack", (500, 500, 540, 560))
    # owner next to the bag
    assert not sim.run(25, lambda i: [bag, person(1, 520, 450)], det)
    # owner leaves
    events = sim.run(30, lambda i: [bag], det)
    assert len(events) == 1


def test_animals():
    sim = Sim(cam())
    det = AnimalDetector()
    events = sim.run(2, lambda i: [(4, "dog", (10, 10, 60, 60)), (5, "elephant", (300, 100, 700, 600))], det)
    types = sorted(e.event_type for e in events)
    assert types == ["animal", "dangerous_animal"]


def test_triple_riding():
    sim = Sim(cam())
    bike = (9, "motorcycle", (400, 500, 560, 620))
    riders = [person(11, 400, 420, 50, 140), person(12, 450, 420, 50, 140), person(13, 500, 420, 50, 140)]
    assert len(sim.run(2, lambda i: [bike] + riders, TripleRidingDetector())) == 1
    sim2 = Sim(cam())
    assert not sim2.run(2, lambda i: [bike] + riders[:2], TripleRidingDetector())


def test_speeding():
    calib = {"line_a": [[0, 0.3], [1, 0.3]], "line_b": [[0, 0.7], [1, 0.7]], "distance_m": 10}
    # foot crosses y=300 and y=700. 400 px in 1 s -> 10 m/s = 36 km/h at 4 fps (100 px per frame)
    sim = Sim(cam(calibration=calib))
    fast = lambda i: [(21, "car", (400, 100 * i, 500, 100 * i + 80))]  # noqa: E731
    events = sim.run(3, fast, SpeedDetector())
    assert len(events) == 1 and 30 < events[0].extra["speed_kmh"] < 42
    sim2 = Sim(cam(calibration=calib))
    slow = lambda i: [(22, "car", (400, 20 * i, 500, 20 * i + 80))]  # noqa: E731 - 7.2 km/h
    assert not sim2.run(12, slow, SpeedDetector())


def _kps(angle_lying: bool, wrist_offset=0.0, x=500.0, y=300.0):
    k = np.zeros((17, 3), dtype=float)
    k[:, 2] = 0.9
    if angle_lying:
        k[5], k[6] = (x, y, 0.9), (x, y + 5, 0.9)
        k[11], k[12] = (x + 80, y, 0.9), (x + 80, y + 5, 0.9)
    else:
        k[5], k[6] = (x, y, 0.9), (x + 30, y, 0.9)
        k[11], k[12] = (x, y + 60, 0.9), (x + 30, y + 60, 0.9)
    k[9], k[10] = (x - 10 + wrist_offset, y + 30, 0.9), (x + 40 - wrist_offset, y + 30, 0.9)
    return k


def test_fall_after_upright():
    sim = Sim(cam())
    det = FallDetector()
    sim.run(2, lambda i: [person(1, 500, 300, 40, 120)], det, keypoints={1: _kps(False)})
    events = sim.run(3, lambda i: [(1, "person", (480, 380, 600, 430))], det, keypoints={1: _kps(True)})
    assert len(events) == 1 and events[0].event_type == "fall"


def test_fight_requires_fast_arms():
    det = FightDetector()
    sim = Sim(cam())
    calm = sim.run(4, lambda i: [person(1, 500, 300), person(2, 530, 300)], det,
                   keypoints={1: _kps(False, 0, 500), 2: _kps(False, 0, 530)})
    assert not calm
    sim2, det2 = Sim(cam()), FightDetector()
    events = []
    for i in range(16):
        off = 120.0 if i % 2 else 0.0
        events += sim2.step([person(1, 500, 300), person(2, 530, 300)], det2,
                            keypoints={1: _kps(False, off, 500), 2: _kps(False, -off, 530)})
    assert len(events) == 1


def test_fire_and_smoking_models():
    sim = Sim(cam())
    det = FireSmokeDetector()
    fire = [ExtraDetection("fire", 0.8, (10, 10, 100, 100))]
    events = sim.run(2, lambda i: [], det, fire=fire, fire_model_loaded=True)
    assert len(events) == 1 and events[0].event_type == "fire_smoke"
    assert not Sim(cam()).run(2, lambda i: [], FireSmokeDetector(), fire=[], fire_model_loaded=True)
    cig = [ExtraDetection("cigarette", 0.7, (520, 320, 530, 330))]
    events = Sim(cam()).run(2, lambda i: [person(1, 500, 300)], SmokingDetector(), smoking=cig, smoking_model_loaded=True)
    assert len(events) == 1
    # no smoking model -> detector is silent
    assert not Sim(cam()).run(2, lambda i: [], SmokingDetector(), smoking=cig, smoking_model_loaded=False)


def test_littering():
    sim = Sim(cam())
    det = LitteringDetector()
    bottle = (31, "bottle", (500, 560, 515, 590))
    sim.run(3, lambda i: [bottle, person(1, 490, 480)], det)
    walk_away = lambda i: [bottle, person(1, 490 + 80 * (i + 1), 480)]  # noqa: E731
    events = sim.run(20, walk_away, det)
    assert len(events) == 1 and events[0].event_type == "littering"
