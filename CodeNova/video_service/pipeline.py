"""Camera capture, detection loop, annotation and the manager that syncs with the backend."""
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import backend_client
from config import get_settings
from detectors import EVENT_TYPES, Event, FrameContext, build_detectors, build_zones
from geometry import denorm, iou
from tracking import PERSON, TrackStore

log = logging.getLogger(__name__)
settings = get_settings()
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

ZONE_COLORS = {
    "restricted": (40, 40, 230), "pedestrian": (230, 160, 40), "no_parking": (0, 200, 255),
    "crowd": (200, 80, 200), "after_hours": (120, 120, 120), "littering": (60, 180, 60),
}
CLASS_COLORS = {"person": (90, 220, 90)}
FIRE_WORDS = ("fire", "smoke", "flame")
SMOKING_WORDS = ("cig", "smok", "vape")


def parse_source(src: str):
    src = src.strip()
    if src.isdigit():
        return int(src)
    p = Path(src)
    if not p.is_absolute():
        local = Path(__file__).resolve().parent / src
        if local.exists():
            return str(local)
    return src


def is_file_source(src) -> bool:
    return isinstance(src, str) and Path(src).exists()


class FrameGrabber(threading.Thread):
    """Reads frames continuously and keeps only the newest (avoids RTSP lag build-up).
    Video files loop at their native frame rate so they behave like a live camera."""

    def __init__(self, source: str):
        super().__init__(daemon=True)
        self.source = parse_source(source)
        self.frame = None
        self.frame_t = 0.0
        self.error = None
        self.running = True
        self.lock = threading.Lock()

    @property
    def online(self) -> bool:
        return self.frame is not None and time.time() - self.frame_t < 10

    def latest(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def stop(self):
        self.running = False

    def run(self):
        backoff = 2.0
        while self.running:
            cap = cv2.VideoCapture(self.source)
            if not cap.isOpened():
                self.error = f"cannot open source {self.source}"
                log.warning(self.error)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            self.error, backoff = None, 2.0
            file_mode = is_file_source(self.source)
            delay = 1.0 / (cap.get(cv2.CAP_PROP_FPS) or 25) if file_mode else 0
            while self.running:
                ok, frame = cap.read()
                if not ok:
                    if file_mode:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    self.error = "stream ended / read failed"
                    break
                with self.lock:
                    self.frame, self.frame_t = frame, time.time()
                if delay:
                    time.sleep(delay)
            cap.release()
            time.sleep(1)


class CameraWorker(threading.Thread):
    def __init__(self, cam: dict, models, sender: backend_client.AlertSender, manager: "CameraManager"):
        super().__init__(daemon=True, name=f"camera-{cam['id']}")
        self.cam = cam
        self.models = models
        self.sender = sender
        self.manager = manager
        self.grabber = FrameGrabber(cam["source"])
        self.tracker = None
        self.store = TrackStore()
        self.detectors = build_detectors(settings.fire_heuristic_fallback)
        self.running = True
        self.jpeg: bytes | None = None
        self.raw_jpeg: bytes | None = None
        self.fps = 0.0
        self.counts = {"people": 0, "vehicles": 0}
        self.banners: list[tuple[float, str]] = []
        self.offline_since: float | None = None
        self._offline_sent = False
        self.error: str | None = None

    def stop(self):
        self.running = False
        self.grabber.stop()

    def detector_on(self, key: str) -> bool:
        return bool((self.cam.get("detectors") or {}).get(key, True))

    def run(self):
        self.grabber.start()
        try:
            self.tracker = self.models.new_tracker()
        except Exception as exc:  # noqa: BLE001
            self.error = f"detection model failed to load: {exc}"
            log.exception(self.error)
        period = 1.0 / max(0.5, settings.process_fps)
        frame_i = 0
        while self.running:
            t0 = time.time()
            frame = self.grabber.latest() if self.grabber.online else None
            if frame is None:
                self._handle_offline(t0)
                time.sleep(0.5)
                continue
            self.offline_since = None
            try:
                self._process(frame, t0, frame_i)
            except Exception:  # noqa: BLE001 - keep the camera loop alive
                log.exception("Processing error on camera %s", self.cam["id"])
            frame_i += 1
            took = time.time() - t0
            self.fps = 0.8 * self.fps + 0.2 * (1.0 / max(took, period))
            time.sleep(max(0.0, period - took))

    def _handle_offline(self, t: float):
        if self.offline_since is None:
            self.offline_since, self._offline_sent = t, False
            return
        if t - self.offline_since > 30 and not self._offline_sent and "camera_offline" in self.manager.enabled_types:
            self._offline_sent = True
            self.sender.send(self.cam["id"], Event(
                "camera_offline", f"No video from '{self.cam['name']}': {self.grabber.error or 'no frames'}",
            ), None)

    def _process(self, frame: np.ndarray, t: float, frame_i: int):
        h, w = frame.shape[:2]
        self.raw_jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, settings.jpeg_quality])[1].tobytes()
        dets = self.tracker.track(frame) if self.tracker else []
        tracks = self.store.update(t, dets)
        people = [tr for tr in tracks if tr.cls == PERSON]

        if people and (self.detector_on("fall") or self.detector_on("fight")) and self.models.pose.loaded:
            self._attach_pose(frame, people, t)

        ctx = FrameContext(
            t=t, now=datetime.now(), frame=frame, width=w, height=h, tracks=tracks, store=self.store,
            zones=build_zones(self.cam, w, h), camera=self.cam, global_cfg=self.manager.global_cfg,
            fire_model_loaded=self.models.fire.loaded, smoking_model_loaded=self.models.smoking.loaded,
        )
        if self.detector_on("fire_smoke") and self.models.fire.loaded and frame_i % 2 == 0:
            ctx.fire = [d for d in self.models.fire.detect(frame, 0.3) if any(k in d.cls for k in FIRE_WORDS)]
        if self.detector_on("smoking") and self.models.smoking.loaded and people and frame_i % 2 == 0:
            ctx.smoking = [d for d in self.models.smoking.detect(frame, 0.3) if any(k in d.cls for k in SMOKING_WORDS)]

        events: list[Event] = []
        for det in self.detectors:
            if not self.detector_on(det.key):
                continue
            allowed = [e for e in EVENT_TYPES.get(det.key, []) if e in self.manager.enabled_types]
            if not allowed:
                continue
            for ev in det.process(ctx):
                if ev.event_type in allowed:
                    events.append(ev)

        self.counts = {"people": len(people), "vehicles": sum(1 for tr in tracks if tr.cls in ("car", "motorcycle", "bus", "truck"))}
        annotated = self._annotate(frame, ctx)
        for ev in events:
            self.banners.append((t, ev.description))
            snap = annotated.copy()
            for b in ev.boxes:
                cv2.rectangle(snap, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), (0, 0, 255), 3)
            cv2.putText(snap, ev.description[:80], (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            jpeg = cv2.imencode(".jpg", snap, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes()
            self.sender.send(self.cam["id"], ev, jpeg)
        self.banners = [(bt, txt) for bt, txt in self.banners if t - bt < 6][-4:]
        for i, (_, txt) in enumerate(self.banners):
            cv2.putText(annotated, "! " + txt[:70], (10, 30 + 24 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        self.jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, settings.jpeg_quality])[1].tobytes()

    def _attach_pose(self, frame, people, t):
        poses = self.models.pose.pose(frame)
        for p in people:
            best, best_iou = None, 0.4
            for box, kps in poses:
                v = iou(p.box, box)
                if v > best_iou:
                    best, best_iou = kps, v
            p.keypoints = best
            if best is not None:
                p.kp_history.append((t, best))

    def _annotate(self, frame, ctx: FrameContext):
        out = frame.copy()
        overlay = out.copy()
        for z in ctx.zones:
            pts = np.array(z.polygon, dtype=np.int32)
            color = ZONE_COLORS.get(z.kind, (200, 200, 200))
            cv2.fillPoly(overlay, [pts], color)
            cv2.polylines(out, [pts], True, color, 2)
            cv2.putText(out, z.name, tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        out = cv2.addWeighted(overlay, 0.15, out, 0.85, 0)
        cal = self.cam.get("calibration") or {}
        for name in ("line_a", "line_b"):
            if cal.get(name):
                (x1, y1), (x2, y2) = denorm(cal[name], ctx.width, ctx.height)
                cv2.line(out, (int(x1), int(y1)), (int(x2), int(y2)), (255, 255, 0), 2)
        speed_det = next((d for d in self.detectors if d.key == "speeding"), None)
        for tr in ctx.tracks:
            x1, y1, x2, y2 = map(int, tr.box)
            color = CLASS_COLORS.get(tr.cls, (255, 200, 0))
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            label = f"{tr.cls} {tr.id}"
            if speed_det and tr.id in speed_det.last_speed:
                label += f" {speed_det.last_speed[tr.id]:.0f}km/h"
            cv2.putText(out, label, (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        for d in ctx.fire + ctx.smoking:
            x1, y1, x2, y2 = map(int, d.box)
            cv2.rectangle(out, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(out, f"{d.cls} {d.conf:.2f}", (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        stamp = f"{self.cam['name']}  {datetime.now():%H:%M:%S}  people:{self.counts['people']}  fps:{self.fps:.1f}"
        cv2.putText(out, stamp, (10, ctx.height - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        return out


class CameraManager:
    def __init__(self, models):
        self.models = models
        self.sender = backend_client.AlertSender()
        self.workers: dict[int, CameraWorker] = {}
        self.global_cfg: dict = {"speed_limit_kmh": 20, "after_hours": {"from": "22:00", "to": "05:00"}}
        self.enabled_types: set[str] = set()
        self.running = True

    def start(self):
        threading.Thread(target=self._sync_loop, daemon=True, name="config-sync").start()
        threading.Thread(target=self._stats_loop, daemon=True, name="stats").start()

    def _sync_loop(self):
        while self.running:
            cfg = backend_client.fetch_config()
            if cfg is not None:
                self.apply(cfg)
            time.sleep(settings.config_refresh_seconds)

    def apply(self, cfg: dict):
        self.global_cfg = {"speed_limit_kmh": cfg.get("speed_limit_kmh", 20), "after_hours": cfg.get("after_hours")}
        self.enabled_types = set(cfg.get("enabled_event_types", []))
        wanted = {c["id"]: c for c in cfg.get("cameras", [])}
        for cid in [c for c in self.workers if c not in wanted]:
            log.info("Stopping camera %s", cid)
            self.workers.pop(cid).stop()
        for cid, cam in wanted.items():
            w = self.workers.get(cid)
            if w and w.cam["source"] != cam["source"]:
                w.stop()
                w = None
            if w is None:
                log.info("Starting camera %s (%s)", cid, cam["name"])
                w = CameraWorker(cam, self.models, self.sender, self)
                self.workers[cid] = w
                w.start()
            else:
                w.cam = cam

    def _stats_loop(self):
        while self.running:
            time.sleep(5)
            items = [
                {
                    "camera_id": cid, "online": w.grabber.online, "fps": round(w.fps, 1),
                    "people": w.counts["people"], "vehicles": w.counts["vehicles"],
                    "error": w.error or w.grabber.error,
                }
                for cid, w in list(self.workers.items())
            ]
            if items:
                backend_client.post_stats(items)
