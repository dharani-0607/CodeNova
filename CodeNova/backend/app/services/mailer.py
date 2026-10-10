"""Email sending over SMTP. Without SMTP settings, emails are printed to the console."""
import logging
import smtplib
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage

from ..config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mailer")


def _send(to: list[str], subject: str, body: str) -> None:
    if not to:
        return
    if not settings.smtp_enabled:
        log.warning("SMTP not configured. Email to %s\nSubject: %s\n%s", to, subject, body)
        print(f"\n=== EMAIL (console mode) to {to} ===\nSubject: {subject}\n{body}\n===\n", flush=True)
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = settings.smtp_from or settings.smtp_user
    msg["Bcc"] = ", ".join(to)
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except Exception:  # noqa: BLE001
        log.exception("Failed to send email '%s'", subject)


def send_email(to: list[str], subject: str, body: str, background: bool = True) -> None:
    if background:
        _pool.submit(_send, to, subject, body)
    else:
        _send(to, subject, body)
