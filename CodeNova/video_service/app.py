"""Video service: runs detection on every camera and serves annotated live streams.

Run:  uvicorn app:app --port 8001   (from the video_service folder)

Streams require a dashboard login token (?token=...) from a security or admin user.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

import jwt
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from config import get_settings
from models import Models
from pipeline import CameraManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()
manager: CameraManager | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global manager
    manager = CameraManager(Models())
    manager.start()
    yield
    manager.running = False
    for w in manager.workers.values():
        w.stop()


app = FastAPI(title="Campus video analytics", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.frontend_origin.split(",")],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def check_token(token: str) -> None:
    try:
        data = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Invalid token") from exc
    if data.get("role") not in ("admin", "security"):
        raise HTTPException(403, "Security or admin role required")


def worker(camera_id: int):
    w = manager.workers.get(camera_id) if manager else None
    if w is None:
        raise HTTPException(404, "Camera not running")
    return w


@app.get("/health")
def health():
    return {
        "status": "ok",
        "cameras": {
            cid: {"online": w.grabber.online, "fps": round(w.fps, 1), "error": w.error or w.grabber.error}
            for cid, w in (manager.workers.items() if manager else [])
        },
        "models": manager.models.status() if manager else {},
    }


@app.get("/stream/{camera_id}")
async def stream(camera_id: int, token: str = Query(...)):
    check_token(token)
    w = worker(camera_id)

    async def gen():
        last = None
        while True:
            frame = w.jpeg or w.raw_jpeg
            if frame is not None and frame is not last:
                last = frame
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(0.05)
            if not w.running:
                break

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/snapshot/{camera_id}")
def snapshot(camera_id: int, token: str = Query(...), annotated: bool = False):
    """Latest frame (raw by default) - used by the zone editor."""
    check_token(token)
    w = worker(camera_id)
    data = w.jpeg if annotated else w.raw_jpeg
    if data is None:
        raise HTTPException(503, "No frame yet")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
