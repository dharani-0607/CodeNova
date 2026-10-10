import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .config import get_settings
from .db import Base, SessionLocal, engine, get_db
from .models import STAFF_ROLES, Alert
from .routers import admin_settings, alerts, auth, cameras, ingest, news, notifications, reports, users
from .security import user_from_token
from .seed import seed_defaults
from .services.hub import hub

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        seed_defaults(db)
    hub.bind_loop(asyncio.get_running_loop())
    if settings.secret_key == "change-me-in-.env":
        logging.warning("SECRET_KEY is the default value. Set it in .env before real use.")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.frontend_origin.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, users, cameras, alerts, reports, news, notifications, admin_settings, ingest):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "ws_clients": hub.online}


@app.get("/media/{path:path}")
def media(path: str, token: str = Query(...), db: Session = Depends(get_db)):
    """Evidence images. Staff see all; other users only broadcast alerts or their own reports."""
    user = user_from_token(db, token)
    if user is None:
        raise HTTPException(401, "Not authenticated")
    root = Path(settings.media_dir).resolve()
    full = (root / path).resolve()
    if root not in full.parents or not full.is_file():
        raise HTTPException(404, "Not found")
    if user.role not in STAFF_ROLES:
        alert = db.query(Alert).filter(Alert.image_path == path).first()
        if not alert or not (alert.broadcast or alert.reporter_id == user.id):
            raise HTTPException(403, "Not allowed")
    return FileResponse(full)


@app.websocket("/ws")
async def websocket(ws: WebSocket, token: str = Query(...)):
    with SessionLocal() as db:
        user = user_from_token(db, token)
    if user is None:
        await ws.close(code=4401)
        return
    await hub.connect(ws, user.role)
    try:
        while True:
            # Clients only send keep-alive pings.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(ws)
