"""Simple SMTP helpers for HR outbound mail (stdlib only)."""

from __future__ import annotations

import html
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv
from flask import current_app


def _reload_mail_env() -> None:
    """Re-read flask_app/.env so MAIL_* updates apply without a full process restart."""
    env_path = Path(current_app.root_path).resolve().parent / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=True)


def normalize_recipient_email(raw: str | None) -> str:
    """Clean pasted emails like www.name@gmail.com → name@gmail.com."""
    email = (raw or "").strip().lower()
    if not email:
        return ""
    # Accidental URL paste
    for prefix in ("mailto:", "https://", "http://"):
        if email.startswith(prefix):
            email = email[len(prefix) :]
    email = email.strip().strip("/")
    if "@" not in email:
        return email
    local, _, domain = email.partition("@")
    local = local.strip()
    domain = domain.strip()
    # Common mistake: www. pasted onto the local part
    if local.startswith("www."):
        local = local[4:]
    # Trailing junk from copy/paste
    domain = domain.split("/")[0].split("?")[0].strip().rstrip(".,;")
    return f"{local}@{domain}" if local and domain else ""


def _mail_settings() -> dict:
    _reload_mail_env()
    cfg = current_app.config
    password = (os.getenv("MAIL_PASSWORD") or cfg.get("MAIL_PASSWORD") or "").strip()
    # Strip accidental quotes from .env values
    if len(password) >= 2 and password[0] == password[-1] and password[0] in {'"', "'"}:
        password = password[1:-1]
    return {
        "server": (os.getenv("MAIL_SERVER") or cfg.get("MAIL_SERVER") or "").strip(),
        "port": int(os.getenv("MAIL_PORT") or cfg.get("MAIL_PORT") or 465),
        "username": (os.getenv("MAIL_USERNAME") or cfg.get("MAIL_USERNAME") or "").strip(),
        "password": password,
        "use_ssl": (os.getenv("MAIL_USE_SSL") or str(cfg.get("MAIL_USE_SSL") or "1")).strip().lower()
        in {"1", "true", "yes"},
        "use_tls": (os.getenv("MAIL_USE_TLS") or str(cfg.get("MAIL_USE_TLS") or "0")).strip().lower()
        in {"1", "true", "yes"},
        "sender": (
            os.getenv("MAIL_DEFAULT_SENDER")
            or cfg.get("MAIL_DEFAULT_SENDER")
            or os.getenv("MAIL_USERNAME")
            or cfg.get("MAIL_USERNAME")
            or ""
        ).strip(),
    }


def mail_missing() -> str:
    """Return which mail settings are missing (empty string if ready)."""
    s = _mail_settings()
    missing = []
    if not s["server"]:
        missing.append("MAIL_SERVER")
    if not s["username"]:
        missing.append("MAIL_USERNAME")
    if not s["password"] or s["password"] in {
        "PASTE_MAILBOX_PASSWORD_HERE",
        "your-mailbox-password",
        "changeme",
    }:
        missing.append("MAIL_PASSWORD")
    return ", ".join(missing)


def mail_configured() -> bool:
    return not mail_missing()


def _smtp_send(msg: EmailMessage, *, host: str, port: int, user: str, password: str, mode: str) -> None:
    if mode == "ssl":
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
        return
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        if mode == "tls":
            context = ssl.create_default_context()
            smtp.starttls(context=context)
            smtp.ehlo()
        smtp.login(user, password)
        smtp.send_message(msg)


def send_email(
    *,
    to_addr: str,
    subject: str,
    body: str,
    html_body: str | None = None,
    from_addr: str | None = None,
    from_name: str | None = None,
) -> tuple[bool, str]:
    """Send email (plain + optional HTML). Returns (ok, error_message)."""
    to_addr = (to_addr or "").strip()
    if not to_addr or "@" not in to_addr:
        return False, "Recipient email is missing or invalid."
    missing = mail_missing()
    if missing:
        return False, f"Email is not configured. Missing in .env: {missing}."

    s = _mail_settings()
    sender = (from_addr or s["sender"] or s["username"]).strip()
    if not sender:
        return False, "No sender email configured."

    msg = EmailMessage()
    display = (from_name or "").strip()
    msg["From"] = f"{display} <{sender}>" if display else sender
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body or " ")
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    host = s["server"]
    user = s["username"]
    password = s["password"]

    # Preferred path from .env, then reliable cPanel fallbacks
    attempts: list[tuple[str, int, str]] = []
    if s["use_ssl"] and not s["use_tls"]:
        attempts.append((host, s["port"] or 465, "ssl"))
    elif s["use_tls"]:
        attempts.append((host, s["port"] or 587, "tls"))
    else:
        attempts.append((host, s["port"] or 465, "ssl"))
    for alt_host, alt_port, alt_mode in (
        (host, 465, "ssl"),
        (host, 587, "tls"),
        ("mail.udottechnologies.com", 465, "ssl"),
        ("mail.udottechnologies.com", 587, "tls"),
        ("udottechnologies.com", 465, "ssl"),
        ("udottechnologies.com", 587, "tls"),
    ):
        key = (alt_host, alt_port, alt_mode)
        if key not in attempts:
            attempts.append(key)

    errors: list[str] = []
    for host_try, port_try, mode in attempts:
        try:
            _smtp_send(
                msg,
                host=host_try,
                port=port_try,
                user=user,
                password=password,
                mode=mode,
            )
            return True, ""
        except smtplib.SMTPAuthenticationError as exc:
            errors.append(f"{host_try}:{port_try}/{mode} → {exc}")
            # Keep trying other transports; auth can differ by port on some hosts
            continue
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{host_try}:{port_try}/{mode} → {exc}")
            continue

    detail = errors[0] if errors else "unknown SMTP error"
    if any("535" in e or "authentication" in e.lower() for e in errors):
        return (
            False,
            "Could not send email: SMTP login failed (535). "
            "Confirm MAIL_PASSWORD in flask_app/.env matches the cPanel mailbox password "
            f"for {user}, then fully stop and restart run.py. Detail: {detail}",
        )
    return False, f"Could not send email: {detail}"


def build_app_credentials_email(
    *,
    company: str,
    employee_name: str,
    login_id: str,
    pin: str,
    logo_url: str | None = None,
    login_url: str | None = None,  # unused — kept for call-site compatibility
    apk_url: str | None = None,  # unused — kept for call-site compatibility
) -> tuple[str, str]:
    """Minimal credentials email: logo, company, greeting, ID/PIN, privacy, regards."""
    del login_url, apk_url
    company_s = (company or "HR").strip()
    name_s = (employee_name or "Employee").strip()
    login_s = str(login_id or "").strip()
    pin_s = str(pin or "").strip()
    logo_s = (logo_url or "").strip()

    plain = (
        f"{company_s}\n"
        f"Mobile app access\n\n"
        f"Dear {name_s},\n\n"
        f"Welcome. Your mobile app login is ready.\n\n"
        f"Login ID: {login_s}\n"
        f"Password (PIN): {pin_s}\n\n"
        "Please keep this private. Do not share your Login ID or PIN with anyone.\n\n"
        f"Regards,\n{company_s} HR\n"
    )

    c = html.escape(company_s)
    n = html.escape(name_s)
    lid = html.escape(login_s)
    p = html.escape(pin_s)
    logo_block = ""
    if logo_s:
        logo_block = (
            f'<img src="{html.escape(logo_s)}" alt="{c}" width="72" height="72" '
            'style="display:block;margin:0 auto 12px;border:0;border-radius:10px;'
            'object-fit:contain;background:#ffffff;">'
        )

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background:#eef4ea;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#163c22;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef4ea;padding:24px 12px;">
    <tr><td align="center">
      <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid #d5e4c6;">
        <tr>
          <td style="background:#1a4a2c;padding:22px 24px;text-align:center;">
            {logo_block}
            <div style="font-size:20px;font-weight:700;color:#f4f9ef;line-height:1.3;">{c}</div>
            <div style="margin-top:6px;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#c9e0b8;">Mobile app access</div>
          </td>
        </tr>
        <tr>
          <td style="padding:24px;">
            <p style="margin:0 0 10px;font-size:15px;line-height:1.5;">Dear <strong>{n}</strong>,</p>
            <p style="margin:0 0 18px;font-size:14px;line-height:1.55;color:#355a3d;">Welcome. Your mobile app login is ready.</p>
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f9ef;border:1px solid #d5e4c6;border-radius:10px;margin:0 0 16px;">
              <tr><td style="padding:16px 18px;">
                <div style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#5d7a5a;margin-bottom:4px;">Login ID</div>
                <div style="font-size:20px;font-weight:700;letter-spacing:.06em;color:#163c22;margin-bottom:14px;">{lid}</div>
                <div style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#5d7a5a;margin-bottom:4px;">Password (PIN)</div>
                <div style="font-size:20px;font-weight:700;letter-spacing:.22em;color:#163c22;">{p}</div>
              </td></tr>
            </table>
            <p style="margin:0 0 18px;font-size:13px;line-height:1.5;color:#5a4030;">Please keep this private. Do not share your Login ID or PIN with anyone.</p>
            <p style="margin:0;font-size:14px;line-height:1.5;color:#163c22;">Regards,<br><strong>{c} HR</strong></p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return plain, html_body
