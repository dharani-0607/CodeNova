"""In-memory live stats reported by the video service (people count, fps, online)."""
import threading
import time


class CameraStatus:
    def __init__(self) -> None:
        self._data: dict[int, dict] = {}
        self._lock = threading.Lock()

    def update(self, camera_id: int, stats: dict) -> None:
        with self._lock:
            self._data[camera_id] = {**stats, "updated": time.time()}

    def get(self, camera_id: int) -> dict:
        with self._lock:
            s = self._data.get(camera_id)
        if not s:
            return {"online": False}
        stale = time.time() - s["updated"] > 30
        return {**s, "online": bool(s.get("online", True)) and not stale}

    def all(self) -> dict[int, dict]:
        with self._lock:
            ids = list(self._data)
        return {i: self.get(i) for i in ids}


camera_status = CameraStatus()
