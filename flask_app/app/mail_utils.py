"""Simple SMTP helpers for HR outbound mail (stdlib only)."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


def mail_configured() -> bool:
    cfg = current_app.config
    return bool(cfg.get("MAIL_SERVER") and cfg.get("MAIL_USERNAME") and cfg.get("MAIL_PASSWORD"))


def send_email(
    *,
    to_addr: str,
    subject: str,
    body: str,
    from_addr: str | None = None,
    from_name: str | None = None,
) -> tuple[bool, str]:
    """Send a plain-text email. Returns (ok, error_message)."""
    to_addr = (to_addr or "").strip()
    if not to_addr or "@" not in to_addr:
        return False, "Recipient email is missing or invalid."
    if not mail_configured():
        return False, "Email is not configured. Set MAIL_SERVER / MAIL_USERNAME / MAIL_PASSWORD on the server."

    cfg = current_app.config
    sender = (from_addr or cfg.get("MAIL_DEFAULT_SENDER") or cfg.get("MAIL_USERNAME") or "").strip()
    if not sender:
        return False, "No sender email configured."

    msg = EmailMessage()
    display = (from_name or "").strip()
    msg["From"] = f"{display} <{sender}>" if display else sender
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    host = cfg["MAIL_SERVER"]
    port = int(cfg.get("MAIL_PORT") or 465)
    user = cfg["MAIL_USERNAME"]
    password = cfg["MAIL_PASSWORD"]
    use_ssl = bool(cfg.get("MAIL_USE_SSL"))
    use_tls = bool(cfg.get("MAIL_USE_TLS"))

    try:
        if use_ssl and not use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as smtp:
                smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.ehlo()
                if use_tls:
                    context = ssl.create_default_context()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                smtp.login(user, password)
                smtp.send_message(msg)
    except Exception as exc:  # noqa: BLE001 — surface SMTP errors to HR UI
        return False, f"Could not send email: {exc}"
    return True, ""
