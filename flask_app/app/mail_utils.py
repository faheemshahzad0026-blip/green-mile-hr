"""Simple SMTP helpers for HR outbound mail (stdlib only)."""

from __future__ import annotations

import html
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


def mail_missing() -> str:
    """Return which mail settings are missing (empty string if ready)."""
    cfg = current_app.config
    missing = []
    if not (cfg.get("MAIL_SERVER") or "").strip():
        missing.append("MAIL_SERVER")
    if not (cfg.get("MAIL_USERNAME") or "").strip():
        missing.append("MAIL_USERNAME")
    password = (cfg.get("MAIL_PASSWORD") or "").strip()
    if not password or password in {"PASTE_MAILBOX_PASSWORD_HERE", "your-mailbox-password", "changeme"}:
        missing.append("MAIL_PASSWORD")
    return ", ".join(missing)


def mail_configured() -> bool:
    return not mail_missing()


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

    cfg = current_app.config
    sender = (from_addr or cfg.get("MAIL_DEFAULT_SENDER") or cfg.get("MAIL_USERNAME") or "").strip()
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


def build_app_credentials_email(
    *,
    company: str,
    employee_name: str,
    login_id: str,
    pin: str,
    login_url: str,
    apk_url: str,
    logo_url: str | None = None,
) -> tuple[str, str]:
    """Return (plain_text, html) for the app login credentials email."""
    company_s = (company or "HR").strip()
    name_s = (employee_name or "Employee").strip()
    login_s = str(login_id or "").strip()
    pin_s = str(pin or "").strip()
    login_url_s = (login_url or "").strip()
    apk_url_s = (apk_url or "").strip()
    logo_s = (logo_url or "").strip()

    plain = (
        f"{company_s}\n\n"
        f"Dear {name_s},\n\n"
        f"Welcome to {company_s}. Your mobile app login is ready.\n\n"
        f"Login ID: {login_s}\n"
        f"Access code (PIN): {pin_s}\n\n"
        f"Employee login: {login_url_s}\n"
        f"Android app download: {apk_url_s}\n\n"
        "Important:\n"
        "- Do not share your Login ID or PIN with anyone.\n"
        "- Keep this email private.\n"
        "- If you did not request this, contact HR immediately.\n"
        "- Need a new PIN? Ask HR — do not reuse old codes after a reset.\n\n"
        f"Regards,\n{company_s} HR Team\n"
    )

    c = html.escape(company_s)
    n = html.escape(name_s)
    lid = html.escape(login_s)
    p = html.escape(pin_s)
    lu = html.escape(login_url_s)
    au = html.escape(apk_url_s)
    logo_block = ""
    if logo_s:
        logo_block = (
            f'<img src="{html.escape(logo_s)}" alt="{c}" width="88" height="88" '
            'style="display:block;margin:0 auto 14px;border:0;border-radius:12px;'
            'object-fit:contain;background:#ffffff;">'
        )

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{c} — App login</title>
</head>
<body style="margin:0;padding:0;background:#eef4ea;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#163c22;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef4ea;padding:28px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #d5e4c6;">
          <tr>
            <td style="background:linear-gradient(160deg,#1a4a2c 0%,#2f6b45 100%);padding:28px 28px 22px;text-align:center;">
              {logo_block}
              <div style="font-size:22px;font-weight:700;letter-spacing:.02em;color:#f4f9ef;line-height:1.25;">{c}</div>
              <div style="margin-top:6px;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#c9e0b8;">Mobile app access</div>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 28px 8px;">
              <p style="margin:0 0 12px;font-size:16px;line-height:1.5;">Dear <strong>{n}</strong>,</p>
              <p style="margin:0 0 18px;font-size:15px;line-height:1.6;color:#355a3d;">
                Welcome to <strong>{c}</strong>. Your employee app login has been enabled.
                Use the details below to sign in — and keep them private.
              </p>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f9ef;border:1px solid #d5e4c6;border-radius:12px;margin:0 0 20px;">
                <tr>
                  <td style="padding:18px 20px;">
                    <div style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#5d7a5a;margin-bottom:6px;">Login ID</div>
                    <div style="font-size:22px;font-weight:700;letter-spacing:.08em;color:#163c22;margin-bottom:16px;">{lid}</div>
                    <div style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#5d7a5a;margin-bottom:6px;">Access code (PIN)</div>
                    <div style="font-size:22px;font-weight:700;letter-spacing:.28em;color:#163c22;">{p}</div>
                  </td>
                </tr>
              </table>
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 22px;">
                <tr>
                  <td style="padding:0 8px 8px 0;">
                    <a href="{lu}" style="display:inline-block;background:#163c22;color:#f4f9ef;text-decoration:none;font-size:13px;font-weight:600;padding:11px 16px;border-radius:8px;">Open employee login</a>
                  </td>
                  <td style="padding:0 0 8px 0;">
                    <a href="{au}" style="display:inline-block;background:#e8f1dc;color:#163c22;text-decoration:none;font-size:13px;font-weight:600;padding:11px 16px;border-radius:8px;border:1px solid #b7d09a;">Download Android app</a>
                  </td>
                </tr>
              </table>
              <div style="background:#fff8e8;border:1px solid #efd9a0;border-radius:12px;padding:14px 16px;margin:0 0 18px;">
                <div style="font-size:13px;font-weight:700;color:#7a5a12;margin-bottom:8px;">Please keep this private</div>
                <ul style="margin:0;padding-left:18px;color:#5c4a1e;font-size:13px;line-height:1.55;">
                  <li>Do not share your Login ID or PIN with anyone.</li>
                  <li>Do not forward this email.</li>
                  <li>If you did not expect this message, contact HR right away.</li>
                  <li>If your PIN is reset, only use the newest code from HR.</li>
                </ul>
              </div>
              <p style="margin:0 0 6px;font-size:14px;line-height:1.5;color:#355a3d;">
                Need help? Reply to this email or contact your HR team.
              </p>
              <p style="margin:18px 0 0;font-size:14px;line-height:1.5;color:#163c22;">
                Regards,<br>
                <strong>{c} HR Team</strong>
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:16px 28px 22px;border-top:1px solid #e4eed9;font-size:11px;line-height:1.5;color:#6a8268;text-align:center;">
              This message was sent by {c} HR for your official app access only.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return plain, html_body
