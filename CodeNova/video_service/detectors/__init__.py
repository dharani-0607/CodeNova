from .base import Detector, Event, ExtraDetection, FrameContext, Sustain, ZoneCfg, build_zones
from .crowd import CrowdDetector
from .objects import AnimalDetector, LitteringDetector, UnattendedObjectDetector
from .safety import FallDetector, FightDetector, FireSmokeDetector, SmokingDetector
from .traffic import SpeedDetector, TripleRidingDetector
from .zones import IntrusionDetector, LoiteringDetector, VehicleZoneDetector, WrongParkingDetector

# camera detector toggle -> event types it can produce (for skipping disabled event types)
EVENT_TYPES = {
    "crowd": ["crowd_density", "congestion"],
    "intrusion": ["intrusion"],
    "loitering": ["loitering"],
    "unattended_object": ["unattended_object"],
    "animal": ["animal", "dangerous_animal"],
    "vehicle_zone": ["vehicle_pedestrian_zone"],
    "wrong_parking": ["wrong_parking"],
    "triple_riding": ["triple_riding"],
    "speeding": ["speeding"],
    "fire_smoke": ["fire_smoke"],
    "fall": ["fall"],
    "fight": ["fight"],
    "smoking": ["smoking"],
    "littering": ["littering"],
}


def build_detectors(fire_heuristic_fallback: bool = False) -> list[Detector]:
    return [
        CrowdDetector(), IntrusionDetector(), LoiteringDetector(), UnattendedObjectDetector(),
        AnimalDetector(), VehicleZoneDetector(), WrongParkingDetector(), TripleRidingDetector(),
        SpeedDetector(), FireSmokeDetector(fire_heuristic_fallback), FallDetector(), FightDetector(),
        SmokingDetector(), LitteringDetector(),
    ]


__all__ = [
    "Detector", "Event", "ExtraDetection", "FrameContext", "Sustain", "ZoneCfg", "build_zones",
    "build_detectors", "EVENT_TYPES",
]
