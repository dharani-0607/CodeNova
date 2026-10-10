"""Loads the YOLO models. All run on CPU.

- Detection + tracking (yolov8n.pt, COCO): one instance per camera, because the tracker
  keeps per-stream state inside the model's predictor.
- Pose (yolov8n-pose.pt): shared, used for falls and fights.
- Fire/smoke and smoking: optional public fine-tuned YOLO weights; skipped if missing.
"""
import logging
import threading
from pathlib import Path

from config import get_settings
from detectors import ExtraDetection
from tracking import TRACKED_CLASSES

log = logging.getLogger(__name__)
settings = get_settings()


def _yolo(path: str):
    from ultralytics import YOLO

    return YOLO(settings.resolve(path))


class SharedModel:
    """A model used by several camera threads, guarded by a lock."""

    def __init__(self, name: str, path: str, optional: bool):
        self.name = name
        self.model = None
        self.error = None
        self.lock = threading.Lock()
        resolved = settings.resolve(path)
        if optional and not Path(resolved).exists():
            self.error = f"weights not found at {resolved}"
            log.warning("%s model disabled: %s (see video_service/weights/README.md)", name, self.error)
            return
        try:
            self.model = _yolo(path)
            log.info("Loaded %s model from %s (classes: %s)", name, resolved, getattr(self.model, "names", {}))
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
            log.error("Could not load %s model: %s", name, exc)

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def detect(self, frame, conf: float = 0.35) -> list[ExtraDetection]:
        if self.model is None:
            return []
        with self.lock:
            res = self.model.predict(frame, conf=conf, imgsz=settings.imgsz, verbose=False)[0]
        names = res.names
        out = []
        for box, c, k in zip(res.boxes.xyxy.tolist(), res.boxes.conf.tolist(), res.boxes.cls.tolist()):
            out.append(ExtraDetection(str(names[int(k)]).lower(), float(c), tuple(box)))
        return out

    def pose(self, frame, conf: float = 0.35):
        """Returns list of (box, keypoints[17,3])."""
        if self.model is None:
            return []
        with self.lock:
            res = self.model.predict(frame, conf=conf, imgsz=settings.imgsz, verbose=False)[0]
        if res.keypoints is None:
            return []
        kps = res.keypoints.data.cpu().numpy()
        return list(zip([tuple(b) for b in res.boxes.xyxy.tolist()], kps))


class Models:
    def __init__(self) -> None:
        self.pose = SharedModel("pose", settings.pose_model, optional=False)
        self.fire = SharedModel("fire/smoke", settings.fire_model, optional=True)
        self.smoking = SharedModel("smoking", settings.smoking_model, optional=True)

    def new_tracker(self) -> "Tracker":
        return Tracker()

    def status(self) -> dict:
        return {
            m.name: {"loaded": m.loaded, "error": m.error}
            for m in (self.pose, self.fire, self.smoking)
        }


class Tracker:
    """Per-camera detection + ByteTrack tracking."""

    def __init__(self) -> None:
        self.model = _yolo(settings.detect_model)
        names = self.model.names
        self.class_ids = [i for i, n in names.items() if n in TRACKED_CLASSES]
        self.names = names

    def track(self, frame):
        """Returns list of (track_id, class_name, conf, box)."""
        res = self.model.track(
            frame, persist=True, classes=self.class_ids, conf=settings.det_conf,
            imgsz=settings.imgsz, tracker="bytetrack.yaml", verbose=False,
        )[0]
        if res.boxes is None or res.boxes.id is None:
            return []
        out = []
        for tid, k, c, box in zip(res.boxes.id.int().tolist(), res.boxes.cls.int().tolist(),
                                  res.boxes.conf.tolist(), res.boxes.xyxy.tolist()):
            out.append((tid, self.names[k], float(c), tuple(box)))
        return out
