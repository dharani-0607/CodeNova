from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ADMIN, SECURITY, USER, User
from ..security import require_admin
from ..serializers import user_out

router = APIRouter(prefix="/api/users", tags=["users"])


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None


@router.get("")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [user_out(u) for u in db.query(User).order_by(User.created_at.desc()).all()]


@router.patch("/{user_id}")
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), me: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == me.id and (body.role not in (None, ADMIN) or body.is_active is False):
        raise HTTPException(400, "You cannot demote or disable yourself")
    if body.role is not None:
        if body.role not in (ADMIN, SECURITY, USER):
            raise HTTPException(400, "Invalid role")
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    db.commit()
    return user_out(user)
