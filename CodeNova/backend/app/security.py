"""Password hashing, JWT tokens and role-based dependencies."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import ADMIN, STAFF_ROLES, User

settings = get_settings()
bearer = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "email": user.email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


def is_campus_email(email: str) -> bool:
    email = email.strip().lower()
    return email.endswith("@" + settings.allowed_email_domain.lower())


def user_from_token(db: Session, token: str) -> User | None:
    try:
        data = decode_token(token)
    except jwt.PyJWTError:
        return None
    user = db.get(User, int(data["sub"]))
    if not user or not user.is_active or not user.is_verified:
        return None
    return user


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user = user_from_token(db, creds.credentials)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
    return user


def require_staff(user: User = Depends(get_current_user)) -> User:
    if user.role not in STAFF_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Security or admin role required")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


def require_service(x_service_key: str | None = Header(default=None)) -> None:
    if not x_service_key or x_service_key != settings.service_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid service key")
