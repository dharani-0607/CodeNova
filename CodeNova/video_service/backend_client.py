"""HTTP calls from the video service to the backend."""
import json
import logging
import queue
import threading

import requests

from config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()
HEADERS = {"X-Service-Key": settings.service_api_key}


def fetch_config() -> dict | None:
    try:
        r = requests.get(f"{settings.backend_url}/api/ingest/config", headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        log.warning("Cannot reach backend for config: %s", exc)
        return None


def post_stats(items: list[dict]) -> None:
    try:
        requests.post(f"{settings.backend_url}/api/ingest/stats", headers=HEADERS, json=items, timeout=5)
    except requests.RequestException as exc:
        log.debug("Stats post failed: %s", exc)


class AlertSender:
    """Sends alerts from a background thread so camera loops never block on the network."""

    def __init__(self) -> None:
        self.q: queue.Queue = queue.Queue(maxsize=200)
        threading.Thread(target=self._run, daemon=True, name="alert-sender").start()

    def send(self, camera_id: int, event, jpeg: bytes | None) -> None:
        try:
            self.q.put_nowait((camera_id, event, jpeg))
        except queue.Full:
            log.warning("Alert queue full, dropping %s", event.event_type)

    def _run(self) -> None:
        while True:
            camera_id, ev, jpeg = self.q.get()
            data = {
                "camera_id": camera_id, "event_type": ev.event_type, "description": ev.description,
                "extra": json.dumps(ev.extra, default=str),
            }
            if ev.confidence is not None:
                data["confidence"] = f"{ev.confidence:.3f}"
            if ev.zone_id is not None:
                data["zone_id"] = ev.zone_id
            if ev.dedupe_key:
                data["dedupe_key"] = ev.dedupe_key
            files = {"image": ("snapshot.jpg", jpeg, "image/jpeg")} if jpeg else None
            try:
                r = requests.post(f"{settings.backend_url}/api/ingest/alerts", headers=HEADERS,
                                  data=data, files=files, timeout=15)
                if r.status_code >= 400:
                    log.warning("Backend rejected %s: %s %s", ev.event_type, r.status_code, r.text[:200])
                else:
                    log.info("Alert %s on camera %s: %s", ev.event_type, camera_id, r.json().get("status"))
            except requests.RequestException as exc:
                log.warning("Alert post failed: %s", exc)
