"""Campus news feed with comments. Every post and comment passes through AI moderation."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import FLAGGED, PUBLISHED, REMOVED, STAFF_ROLES, Comment, NewsPost, User
from ..security import get_current_user, require_admin, require_staff
from ..serializers import comment_out, post_out
from ..services.hub import hub
from ..services.moderation import moderate
from ..services.notify import notify_news

router = APIRouter(prefix="/api", tags=["news"])

CATEGORIES = ["general", "academics", "events", "sports", "placements", "hostel", "transport", "safety", "lost_found"]


class PostIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=3, max_length=10000)
    category: str = "general"
    is_important: bool = False


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class DecisionIn(BaseModel):
    decision: str  # published | removed


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


def _moderation_message(result: dict) -> str:
    if result["decision"] == REMOVED:
        return "Removed by AI moderation: " + "; ".join(result["reasons"])
    if result["decision"] == FLAGGED:
        return "Held for admin review: " + "; ".join(result["reasons"])
    return "Published"


@router.get("/news/categories")
def news_categories():
    return CATEGORIES


@router.get("/news")
def list_news(
    category: str | None = None,
    important: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    staff = user.role in STAFF_ROLES
    q = db.query(NewsPost).filter(or_(NewsPost.status == PUBLISHED, NewsPost.author_id == user.id))
    if category:
        q = q.filter(NewsPost.category == category)
    if important:
        q = q.filter(NewsPost.is_important.is_(True))
    rows = q.order_by(NewsPost.is_important.desc(), NewsPost.created_at.desc()).limit(limit).all()
    return [post_out(p, staff=staff, viewer_id=user.id) for p in rows]


@router.post("/news")
def create_post(body: PostIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if body.category not in CATEGORIES:
        raise HTTPException(400, "Unknown category")
    staff = user.role in STAFF_ROLES
    if body.is_important and not staff:
        raise HTTPException(403, "Only security or admin can mark news as important")
    result = moderate(db, f"{body.title}\n{body.body}")
    post = NewsPost(
        author_id=user.id, title=body.title.strip(), body=body.body.strip(), category=body.category,
        is_important=body.is_important, is_official=staff, status=result["decision"], moderation=result,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    if post.status == PUBLISHED:
        notify_news(db, post)
    else:
        hub.publish("moderation", {"kind": "post", "id": post.id, "decision": post.status}, audience="staff")
    return {"post": post_out(post, staff=staff, viewer_id=user.id), "message": _moderation_message(result)}


@router.delete("/news/{post_id}")
def delete_post(post_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    post = db.get(NewsPost, post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    if post.author_id != user.id and user.role not in STAFF_ROLES:
        raise HTTPException(403, "Not allowed")
    db.delete(post)
    db.commit()
    hub.publish("news_deleted", {"id": post_id})
    return {"ok": True}


@router.post("/news/{post_id}/comments")
def add_comment(post_id: int, body: CommentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    post = db.get(NewsPost, post_id)
    if not post or post.status != PUBLISHED:
        raise HTTPException(404, "Post not found")
    result = moderate(db, body.body)
    c = Comment(post_id=post_id, author_id=user.id, body=body.body.strip(), status=result["decision"], moderation=result)
    db.add(c)
    db.commit()
    db.refresh(c)
    if c.status == PUBLISHED:
        hub.publish("comment", comment_out(c))
    else:
        hub.publish("moderation", {"kind": "comment", "id": c.id, "decision": c.status}, audience="staff")
    return {"comment": comment_out(c, staff=True), "message": _moderation_message(result)}


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.get(Comment, comment_id)
    if not c:
        raise HTTPException(404, "Comment not found")
    if c.author_id != user.id and user.role not in STAFF_ROLES:
        raise HTTPException(403, "Not allowed")
    db.delete(c)
    db.commit()
    return {"ok": True}


# ---- Moderation review queue -------------------------------------------------

@router.get("/moderation/queue")
def moderation_queue(
    include_removed: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    statuses = [FLAGGED, REMOVED] if include_removed else [FLAGGED]
    posts = db.query(NewsPost).filter(NewsPost.status.in_(statuses)).order_by(NewsPost.created_at.desc()).limit(200).all()
    comments = db.query(Comment).filter(Comment.status.in_(statuses)).order_by(Comment.created_at.desc()).limit(200).all()
    return {
        "posts": [post_out(p, staff=True) for p in posts],
        "comments": [{**comment_out(c, staff=True), "post_title": c.post.title} for c in comments],
    }


@router.post("/moderation/{kind}/{item_id}")
def moderation_decide(kind: str, item_id: int, body: DecisionIn, db: Session = Depends(get_db),
                      user: User = Depends(require_staff)):
    if body.decision not in (PUBLISHED, REMOVED):
        raise HTTPException(400, "decision must be 'published' or 'removed'")
    model = {"post": NewsPost, "comment": Comment}.get(kind)
    if model is None:
        raise HTTPException(400, "kind must be post or comment")
    item = db.get(model, item_id)
    if not item:
        raise HTTPException(404, "Not found")
    item.status = body.decision
    item.moderation = {**(item.moderation or {}), "reviewed_by": user.email, "final": body.decision}
    db.commit()
    if body.decision == PUBLISHED:
        if kind == "post":
            notify_news(db, item)
        else:
            hub.publish("comment", comment_out(item))
    return {"ok": True, "status": item.status}


@router.post("/moderation/test")
def moderation_test(body: TextIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Try the moderation pipeline on any text without posting it."""
    return moderate(db, body.text)
