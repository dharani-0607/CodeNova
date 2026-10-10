# CodeNova – Amrita Coimbatore Campus Command Center

A single real-time web dashboard for campus safety and communication at
Amrita Vishwa Vidyapeetham, Coimbatore:

- **Live CCTV analytics**: crowd density, congestion and 12 more campus-rule detectors running on CPU
- **One alert feed** with priority levels (Critical / High / Medium / Low), set per event type and overridable per alert
- **Geofenced incident reports**: only `@cb.amrita.edu` users who are physically inside the campus can file one
- **Notifications** on the live dashboard, as browser push, and by email
- **Campus news and comments** checked by a local AI moderation model plus campus-rule lists, with an admin review queue

```
┌────────────────────┐   WebSocket / REST   ┌────────────────────────┐
│  React dashboard   │◀────────────────────▶│  FastAPI backend :8000 │── PostgreSQL / SQLite
│  (Vite) :5173      │                      │  auth, alerts, news,   │── SMTP (email)
│  /api /ws /video   │   MJPEG via /video   │  moderation, push      │── Web Push (VAPID)
│  proxied           │◀──────────┐          └───────────▲────────────┘
└────────────────────┘           │   alerts + snapshots │ config (cameras, zones)
                       ┌─────────┴────────────────────────┴─┐
                       │  Video service :8001 (YOLOv8, CPU)  │◀── RTSP CCTV / video files / webcam
                       └─────────────────────────────────────┘
```

## Quick start (Windows laptop)

Requirements: **Python 3.10–3.13**, **Node.js 18+**, and optionally **Docker Desktop** for PostgreSQL
(without Docker the setup switches to SQLite automatically).

```powershell
git clone -b shanthanums/genesis https://github.com/dharani-0607/CodeNova.git
cd CodeNova
Set-ExecutionPolicy -Scope Process Bypass   # allow the scripts for this window
.\setup.ps1      # creates .env, .venv, installs everything, downloads models (~1.5 GB, one time)
notepad .env     # set ADMIN_EMAILS and your Gmail SMTP details (see below)
.\start.ps1      # opens 3 windows: backend, video service, dashboard
```

Open **http://localhost:5173** and register with the email you put in `ADMIN_EMAILS`. It becomes the admin.
Linux/macOS: `./setup.sh` then `./start.sh`.

### Phones on campus Wi-Fi

Browsers only give GPS location and push notifications to HTTPS pages. Start with
`.\start.ps1 -Https` and open `https://<laptop-wifi-ip>:5173` on the phone. The certificate is
self-signed, so accept the warning once. Find the laptop IP with `ipconfig`.

## Configuration (`.env`)

| Setting | What it does |
|---|---|
| `ADMIN_EMAILS` | Comma-separated `@cb.amrita.edu` emails that become admins when they register |
| `ALLOWED_EMAIL_DOMAIN` | Only this domain can register (default `cb.amrita.edu`) |
| `SMTP_*` | Email for verification codes and alerts. Gmail: `smtp.gmail.com`, port 587, and an [App Password](https://myaccount.google.com/apppasswords). Leave `SMTP_HOST` empty to print emails (including verification codes) in the backend window |
| `VAPID_*` | Browser push keys. `setup.ps1` generates them (`python scripts/generate_vapid_keys.py`) |
| `DATABASE_URL` | PostgreSQL (default, via `docker compose up -d db`) or `sqlite:///./campus.db` |
| `MODERATION_MODEL` | Local Hugging Face model for toxicity (default `unitary/toxic-bert`) |
| `PROCESS_FPS` | Frames analysed per camera per second (CPU: 2–5) |

Everything else (event priorities, geofence, speed limit, after-hours window, moderation word lists,
cameras and zones) is edited in the dashboard under **Admin**.

## Roles

| Role | Can do |
|---|---|
| **Admin** | Everything: cameras and zones, event priorities, geofence, campus settings, moderation rules, user roles |
| **Security** | Live cameras, alert feed, confirm / acknowledge / resolve / dismiss alerts, change alert priority, broadcast to campus, moderation queue |
| **User** (students and staff) | Campus alerts, news and comments, geofenced incident reports, their own reports |

Promote someone to Security under **Admin → Users**.

## Camera detection

Add cameras in **Admin → Cameras**. The source can be:
- an RTSP URL from campus IT, e.g. `rtsp://user:pass@10.x.x.x:554/Streaming/Channels/101`
- a video file in `video_service/samples/` (e.g. `samples/gate.mp4`, plays on a loop)
- `0` for the laptop webcam

Then click **Zones & lines** to draw zones on a live frame and calibrate speed lines.

| Detector | How it works | Needs |
|---|---|---|
| Crowd density | People inside a *crowd* zone (or whole view) ≥ `max_people` for 5 s; or people/m² ≥ `max_density` if `area_m2` is set | YOLOv8n |
| Congestion | ≥ 12 people barely moving for 20 s | YOLOv8n + tracking |
| Restricted-zone intrusion | Person inside a *restricted* zone (optionally only during set hours) | zone |
| After-hours loitering | Person staying > 60 s during the after-hours window (default 22:00–05:00) | — |
| Unattended object | Backpack/handbag/suitcase stationary with nobody near for 60 s | YOLOv8n |
| Animals | Dog, cat, cow, horse, sheep; **elephant / bear raise a Critical campus-wide alert** | YOLOv8n |
| Vehicle in pedestrian zone | Car, motorcycle, bus or truck inside a *pedestrian* zone | zone |
| No-parking | Vehicle stopped > 120 s in a *no_parking* zone | zone |
| Triple riding | ≥ 3 people on one motorcycle | YOLOv8n |
| Speeding | Time to cross two calibrated lines a known distance apart; over the campus limit (20 km/h) | calibration |
| Fire / smoke | Fire model detections in 3 of 5 frames | `weights/fire_smoke.pt` |
| Fall | Pose keypoints: upright → torso > 60° from vertical and still down 2 s, or lying motionless 30 s | YOLOv8n-pose |
| Fight | Two people close together with fast, repeated arm movement for 1.5 s | YOLOv8n-pose |
| Smoking | Cigarette/smoking model detections | `weights/smoking.pt` |
| Littering | Bottle/cup appears next to a person and stays after they walk away | YOLOv8n + tracking |
| Camera offline | No frames for 30 s | — |

Each alert carries an annotated snapshot. Repeat detections are suppressed by a cooldown per
event type (editable in **Admin → Event priorities**).

### Accuracy – please read

- **Fights, falls, smoking and littering** are heuristics or public community models and *will*
  produce false alarms. They default to **Needs review**: security sees them first and decides,
  and nobody else is notified until it's confirmed.
- **Fire/smoke and smoking weights** come from public Hugging Face models (`download_weights.py`).
  They are not validated on Amrita cameras. Check the licence and test on your own footage.
  For real deployment, fine-tune on campus footage and drop the `.pt` file into `video_service/weights/`.
- **Speeding** is only as good as the calibration. Measure the distance between the two lines on the ground.
- **Capacity**: a CPU-only laptop handles roughly **2–4 cameras** at 3–5 fps. Lower `PROCESS_FPS` or
  disable unused detectors per camera if it struggles.
- **Snakes** are not detected. No reliable public model exists.

## Geofenced reports

**Report incident** reads the device's GPS. The backend accepts the report only if the position
is inside the campus polygon and the GPS accuracy is within 200 m (configurable). The default
polygon is a rough box around the Ettimadai campus, so **trace the real boundary in Admin → Geofence
before going live**. Note: a determined user can fake GPS on their own device; the email-domain
login and audit trail (name, email, position on every report) are the main safeguards.

## Priorities and notifications

Each event type has a default priority, plus switches for *needs review*, *broadcast to all users*,
*email* and *push*. Security can change the priority of any single alert, and can **Broadcast to campus**
any alert to send it to every user.

| Channel | Who | When |
|---|---|---|
| Dashboard pop-up + sound | Security/admin | Every new alert (critical alerts beep) |
| Dashboard pop-up | All users | Broadcast alerts and important news |
| Browser push | Security/admin; all users for broadcasts and important news | Click **Enable push** in the top bar |
| Email | Security/admin for Critical/High alerts (per event type); everyone for critical broadcasts and important news | SMTP configured |

## News moderation

Every news post and comment is checked before it appears:
1. **Campus rules** (Admin → Moderation rules): *banned terms* are removed automatically, *sensitive
   terms* go to the review queue.
2. **Local AI model** (`unitary/toxic-bert`, runs offline on CPU after the first download): scores
   toxicity, insults, threats, obscenity and identity hate. Above the review threshold → held for review;
   above the remove threshold (or any threat/identity hate) → removed.
3. Spam signals (many links, all caps, repeated characters) → held for review.

Authors see why their post was held or removed. Security/admin approve or remove items in **Moderation**,
and admins can test any text there.

## Development

```bash
# backend tests (SQLite by default; set TEST_DATABASE_URL to use PostgreSQL)
cd backend && ../.venv/bin/python -m pytest
# detector rule tests (no models needed)
cd video_service && ../.venv/bin/python -m pytest
# frontend production build
cd frontend && npm run build
```

Project layout:

```
backend/         FastAPI app (app/routers, app/services), tests
video_service/   camera capture, YOLO models, detectors/, MJPEG server, tests
frontend/        React + Vite dashboard (src/pages, src/components, src/lib)
scripts/         helper scripts (VAPID key generator)
setup.ps1 / start.ps1   Windows setup and launch
```

## Security notes

- Change `SECRET_KEY` and `SERVICE_API_KEY` (setup does this for you) and never commit `.env`.
- Camera streams and snapshots require a security/admin login token.
- Evidence images are only served to staff, the reporting user, or everyone once broadcast.
- Keep the laptop on the campus network; don't expose ports 8000/8001 to the internet.
