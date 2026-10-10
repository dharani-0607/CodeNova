"""AI moderation for news posts and comments.

Two layers:
1. Campus rule terms (admin-editable): banned terms remove the content, review terms flag it.
2. A local open-source toxicity model (default unitary/toxic-bert via Hugging Face
   transformers) scores toxicity, insults, threats, obscenity and identity hate.
   It runs on CPU on the laptop; nothing is sent to an outside service.

If the model can't be loaded (transformers/torch not installed or no download yet),
moderation falls back to the rule layer plus spam heuristics and says so in the result.
"""
import logging
import re
import threading

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import FLAGGED, PUBLISHED, REMOVED
from ..seed import get_setting

log = logging.getLogger(__name__)
settings = get_settings()

_model = None
_model_error: str | None = None
_lock = threading.Lock()

# Labels from toxic-bert that count as serious enough to remove at a lower score.
SEVERE_LABELS = {"severe_toxic", "threat", "identity_hate"}
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)


def _load_model():
    global _model, _model_error
    if _model is not None or _model_error is not None or not settings.moderation_use_ml:
        return _model
    with _lock:
        if _model is not None or _model_error is not None:
            return _model
        try:
            from transformers import pipeline

            _model = pipeline("text-classification", model=settings.moderation_model, top_k=None, truncation=True)
            log.info("Loaded moderation model %s", settings.moderation_model)
        except Exception as exc:  # noqa: BLE001
            _model_error = f"{type(exc).__name__}: {exc}"
            log.warning("Moderation model unavailable, using rules only: %s", _model_error)
    return _model


def model_status() -> dict:
    return {
        "enabled": settings.moderation_use_ml,
        "model": settings.moderation_model,
        "loaded": _model is not None,
        "error": _model_error,
    }


def _term_hits(text: str, terms: list[str]) -> list[str]:
    low = text.lower()
    hits = []
    for term in terms:
        t = term.strip().lower()
        if t and re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", low):
            hits.append(term)
    return hits


def _spam_reasons(text: str) -> list[str]:
    reasons = []
    if len(URL_RE.findall(text)) >= 3:
        reasons.append("many links (possible spam)")
    letters = [c for c in text if c.isalpha()]
    if len(letters) > 30 and sum(c.isupper() for c in letters) / len(letters) > 0.8:
        reasons.append("mostly capital letters")
    if re.search(r"(.)\1{9,}", text):
        reasons.append("repeated characters")
    return reasons


def _ml_scores(text: str) -> dict[str, float] | None:
    model = _load_model()
    if model is None:
        return None
    try:
        result = model(text[:2000])
        rows = result[0] if result and isinstance(result[0], list) else result
        return {r["label"].lower(): float(r["score"]) for r in rows}
    except Exception:  # noqa: BLE001
        log.exception("Moderation model failed")
        return None


def moderate(db: Session, text: str) -> dict:
    """Return {"decision": published|flagged|removed, "reasons": [...], "scores": {...}}."""
    cfg = get_setting(db, "moderation") or {}
    flag_t = float(cfg.get("flag_threshold", 0.5))
    remove_t = float(cfg.get("remove_threshold", 0.85))
    reasons_remove: list[str] = []
    reasons_flag: list[str] = []

    banned = _term_hits(text, cfg.get("banned_terms", []))
    if banned:
        reasons_remove.append("breaks campus rules: " + ", ".join(banned))
    review = _term_hits(text, cfg.get("review_terms", []))
    if review:
        reasons_flag.append("sensitive topic: " + ", ".join(review))
    reasons_flag += _spam_reasons(text)

    scores = _ml_scores(text)
    if scores:
        for label, score in scores.items():
            if label in ("non-toxic", "neutral", "label_0"):
                continue
            if score >= remove_t or (label in SEVERE_LABELS and score >= flag_t):
                reasons_remove.append(f"{label} ({score:.2f})")
            elif score >= flag_t:
                reasons_flag.append(f"{label} ({score:.2f})")

    if reasons_remove:
        decision = REMOVED
    elif reasons_flag:
        decision = FLAGGED
    else:
        decision = PUBLISHED
    return {
        "decision": decision,
        "reasons": reasons_remove + reasons_flag,
        "scores": scores or {},
        "model_used": scores is not None,
    }
