from app.services.geofence import point_in_polygon

from .conftest import make_user

INSIDE = (10.9027, 76.9006)  # campus centre
OUTSIDE = (11.0168, 76.9558)  # Coimbatore city


def test_register_rejects_other_domains(client):
    r = client.post("/api/auth/register", json={"email": "someone@gmail.com", "name": "X Y", "password": "password123"})
    assert r.status_code == 400
    r = client.post("/api/auth/register", json={"email": "x@am.amrita.edu", "name": "X Y", "password": "password123"})
    assert r.status_code == 400


def test_login_requires_verification(client):
    client.post("/api/auth/register", json={"email": "new@cb.amrita.edu", "name": "New", "password": "password123"})
    r = client.post("/api/auth/login", json={"email": "new@cb.amrita.edu", "password": "password123"})
    assert r.status_code == 403


def test_roles(client, admin, student):
    assert client.get("/api/auth/me", headers=admin).json()["role"] == "admin"
    assert client.get("/api/auth/me", headers=student).json()["role"] == "user"
    assert client.get("/api/users", headers=student).status_code == 403
    assert client.get("/api/alerts", headers=student).status_code == 403
    assert client.get("/api/users", headers=admin).status_code == 200


def test_point_in_polygon():
    square = [[0, 0], [0, 1], [1, 1], [1, 0]]
    assert point_in_polygon(0.5, 0.5, square)
    assert not point_in_polygon(1.5, 0.5, square)
    assert not point_in_polygon(0.5, 0.5, [[0, 0], [1, 1]])


def test_report_geofence(client, student, admin):
    form = {"category": "report_safety", "title": "Broken railing", "description": "Near block A"}
    r = client.post("/api/reports", headers=student, data={**form, "lat": OUTSIDE[0], "lon": OUTSIDE[1], "accuracy": 10})
    assert r.status_code == 403
    r = client.post("/api/reports", headers=student, data={**form, "lat": INSIDE[0], "lon": INSIDE[1], "accuracy": 5000})
    assert r.status_code == 400
    r = client.post(
        "/api/reports", headers=student,
        data={**form, "lat": INSIDE[0], "lon": INSIDE[1], "accuracy": 15, "priority": "high"},
        files={"photo": ("p.jpg", b"\xff\xd8\xff fake", "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    alert = r.json()
    assert alert["priority"] == "high" and alert["source"] == "report"
    # student can see their own report and photo, staff can override priority
    assert any(a["id"] == alert["id"] for a in client.get("/api/reports/mine", headers=student).json())
    token = student["Authorization"].split()[1]
    assert client.get(alert["image_url"] + f"?token={token}").status_code == 200
    r = client.patch(f"/api/alerts/{alert['id']}", headers=admin, json={"priority": "critical", "status": "acknowledged"})
    assert r.json()["priority"] == "critical"


def test_admin_can_edit_geofence(client, admin, student):
    poly = [[10.89, 76.89], [10.91, 76.89], [10.91, 76.91], [10.89, 76.91]]
    assert client.put("/api/geofence", headers=student, json={"polygon": poly}).status_code == 403
    assert client.put("/api/geofence", headers=admin, json={"polygon": poly}).status_code == 200
    assert client.get("/api/config").json()["geofence"] == poly


def test_event_type_priority(client, admin):
    r = client.patch("/api/event-types/littering", headers=admin, json={"default_priority": "medium"})
    assert r.json()["default_priority"] == "medium"
    assert client.patch("/api/event-types/littering", headers=admin, json={"default_priority": "urgent"}).status_code == 400


def test_moderation_rules(client, student, admin):
    r = client.post("/api/news", headers=student, json={"title": "Cheap liquor", "body": "Selling liquor at hostel tonight"})
    assert r.json()["post"]["status"] == "removed"
    r = client.post("/api/news", headers=student, json={"title": "Strike", "body": "Students plan a strike tomorrow"})
    flagged = r.json()["post"]
    assert flagged["status"] == "flagged"
    r = client.post("/api/news", headers=student, json={"title": "Library hours", "body": "Library open till 10pm this week"})
    ok = r.json()["post"]
    assert ok["status"] == "published"

    other = make_user(client, "other@cb.amrita.edu", name="Other")
    titles = [p["title"] for p in client.get("/api/news", headers=other).json()]
    assert "Library hours" in titles and "Strike" not in titles and "Cheap liquor" not in titles

    r = client.post(f"/api/news/{ok['id']}/comments", headers=other, json={"body": "betting pool here"})
    assert r.json()["comment"]["status"] == "removed"

    queue = client.get("/api/moderation/queue", headers=admin).json()
    assert any(p["id"] == flagged["id"] for p in queue["posts"])
    client.post(f"/api/moderation/post/{flagged['id']}", headers=admin, json={"decision": "published"})
    titles = [p["title"] for p in client.get("/api/news", headers=other).json()]
    assert "Strike" in titles

    assert client.post("/api/news", headers=student, json={"title": "Exam", "body": "date moved", "is_important": True}).status_code == 403


def test_camera_ingest_and_review(client, admin):
    cam = client.post("/api/cameras", headers=admin, json={"name": "Main gate", "source": "0", "lat": 10.9, "lon": 76.9}).json()
    zone = client.post(f"/api/cameras/{cam['id']}/zones", headers=admin, json={
        "name": "Server room", "kind": "restricted", "polygon": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]],
    }).json()
    assert client.get("/api/ingest/config").status_code == 401
    cfg = client.get("/api/ingest/config", headers={"X-Service-Key": "svc-key"}).json()
    assert cfg["speed_limit_kmh"] == 20 and cfg["cameras"][0]["zones"][0]["id"] == zone["id"]

    svc = {"X-Service-Key": "svc-key"}
    r = client.post("/api/ingest/alerts", headers=svc, data={"camera_id": cam["id"], "event_type": "intrusion", "zone_id": zone["id"], "confidence": 0.9},
                    files={"image": ("s.jpg", b"\xff\xd8\xff", "image/jpeg")})
    assert r.json()["status"] == "created"
    assert r.json()["alert"]["status"] == "open"
    # same zone again within cooldown is ignored
    r = client.post("/api/ingest/alerts", headers=svc, data={"camera_id": cam["id"], "event_type": "intrusion", "zone_id": zone["id"]})
    assert r.json()["status"] == "ignored"
    # low-reliability detections wait for review
    r = client.post("/api/ingest/alerts", headers=svc, data={"camera_id": cam["id"], "event_type": "fight"})
    fight = r.json()["alert"]
    assert fight["status"] == "pending_review"
    r = client.post(f"/api/alerts/{fight['id']}/broadcast", headers=admin)
    assert r.json()["broadcast"] is True and r.json()["status"] == "open"

    stats = client.get("/api/alerts/stats", headers=admin).json()
    assert stats["by_type"]["intrusion"] >= 1
    client.post("/api/ingest/stats", headers=svc, json=[{"camera_id": cam["id"], "fps": 4, "people": 12}])
    assert client.get(f"/api/cameras/{cam['id']}", headers=admin).json()["status"]["people"] == 12


def test_websocket_rejects_bad_token(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws?token=bad") as ws:
            ws.receive_text()
