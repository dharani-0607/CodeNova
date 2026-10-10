import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import ADMIN, User
from ..security import create_token, get_current_user, hash_password, is_campus_email, verify_password
from ..serializers import user_out
from ..services.mailer import send_email

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class VerifyIn(BaseModel):
    email: EmailStr
    code: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class EmailIn(BaseModel):
    email: EmailStr


def _issue_code(db: Session, user: User) -> None:
    user.verify_code = f"{secrets.randbelow(1_000_000):06d}"
    user.verify_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    db.commit()
    send_email(
        [user.email],
        "Your Amrita campus dashboard verification code",
        f"Hello {user.name},\n\nYour verification code is {user.verify_code}. It expires in 15 minutes.",
    )


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if not is_campus_email(email):
        raise HTTPException(400, f"Only @{settings.allowed_email_domain} email addresses can register")
    existing = db.query(User).filter(User.email == email).first()
    if existing and existing.is_verified:
        raise HTTPException(400, "An account with this email already exists")
    user = existing or User(email=email)
    user.name = body.name.strip()
    user.password_hash = hash_password(body.password)
    if email in settings.admin_email_set:
        user.role = ADMIN
    if not existing:
        db.add(user)
    db.commit()
    if settings.require_email_verification:
        _issue_code(db, user)
        return {"status": "verification_required", "email": email}
    user.is_verified = True
    db.commit()
    return {"status": "ok", "token": create_token(user), "user": user_out(user)}


@router.post("/verify")
def verify(body: VerifyIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not user.verify_code:
        raise HTTPException(400, "No pending verification for this email")
    expires = user.verify_expires
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and expires < datetime.now(timezone.utc):
        raise HTTPException(400, "Code expired, request a new one")
    if not secrets.compare_digest(user.verify_code, body.code.strip()):
        raise HTTPException(400, "Incorrect code")
    user.is_verified = True
    user.verify_code = None
    db.commit()
    return {"token": create_token(user), "user": user_out(user)}


@router.post("/resend")
def resend(body: EmailIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user and not user.is_verified:
        _issue_code(db, user)
    return {"status": "sent"}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if not is_campus_email(email):
        raise HTTPException(400, f"Use your @{settings.allowed_email_domain} email")
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(403, "Account disabled by admin")
    if not user.is_verified:
        _issue_code(db, user)
        raise HTTPException(403, "Email not verified. A new code has been sent.")
    return {"token": create_token(user), "user": user_out(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)
