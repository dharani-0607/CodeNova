import os
import sys
import tempfile
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp()
# Set TEST_DATABASE_URL to run the suite against PostgreSQL instead of SQLite.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["MEDIA_DIR"] = f"{_tmp}/media"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ["SERVICE_API_KEY"] = "svc-key"
os.environ["ADMIN_EMAILS"] = "admin@cb.amrita.edu"
os.environ["MODERATION_USE_ML"] = "false"
os.environ["REQUIRE_EMAIL_VERIFICATION"] = "true"
os.environ["SMTP_HOST"] = ""

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def make_user(client, email, password="password123", name="Test User"):
    r = client.post("/api/auth/register", json={"email": email, "name": name, "password": password})
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        code = db.query(User).filter(User.email == email).one().verify_code
    r = client.post("/api/auth/verify", json={"email": email, "code": code})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return make_user(client, "admin@cb.amrita.edu", name="Admin")


@pytest.fixture(scope="session")
def student(client):
    return make_user(client, "cb.en.u4cse00001@cb.amrita.edu", name="Student")
