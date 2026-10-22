import re
import secrets
from pathlib import Path

from flask import current_app, session
from flask_login import current_user
from PIL import Image
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Agency, AuditLog, Employee, HrRecord, User


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or secrets.token_hex(4)


def unique_agency_slug(name: str) -> str:
    base = slugify(name)
    slug = base
    n = 1
    while Agency.query.filter_by(slug=slug).first():
        n += 1
        slug = f"{base}-{n}"
    return slug


def write_audit(action: str, details: str = "", agency_id=None, actor=None):
    actor = actor or (current_user if current_user.is_authenticated else None)
    entry = AuditLog(
        actor_user_id=getattr(actor, "id", None) if actor and not getattr(actor, "is_employee_account", False) else None,
        actor_label=getattr(actor, "display_name", None) or getattr(actor, "username", "system"),
        agency_id=agency_id,
        action=action,
        details=details,
    )
    db.session.add(entry)


def save_agency_logo(file_storage, agency_id: int) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    ext = Path(filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        raise ValueError("Logo must be PNG, JPG, WEBP, or GIF.")
    upload_root = Path(current_app.config["UPLOAD_FOLDER"])
    agency_dir = upload_root / str(agency_id)
    agency_dir.mkdir(parents=True, exist_ok=True)
    dest_name = f"logo{ext}"
    dest = agency_dir / dest_name
    image = Image.open(file_storage)
    image.thumbnail((400, 400))
    image.save(dest)
    return f"uploads/{agency_id}/{dest_name}"


def get_active_agency_id():
    """Agency context for lists: super admin may switch; others use own agency."""
    if not current_user.is_authenticated:
        return None
    if getattr(current_user, "is_employee_account", False):
        return current_user.agency_id
    if current_user.is_super_admin:
        return session.get("view_agency_id")
    return current_user.agency_id


def get_active_agency():
    agency_id = get_active_agency_id()
    if not agency_id:
        return None
    return Agency.query.get(agency_id)


def agency_scope_or_403(agency_id: int) -> Agency:
    agency = Agency.query.get_or_404(agency_id)
    if current_user.is_super_admin:
        return agency
    if current_user.agency_id != agency.id:
        from flask import abort

        abort(403)
    return agency


def next_employee_code(agency_id: int) -> str:
    count = Employee.query.filter_by(agency_id=agency_id).count() + 1
    return f"{count:05d}"


def ensure_super_admin():
    from flask import current_app

    existing = User.query.filter_by(role=User.ROLE_SUPER_ADMIN).first()
    if existing:
        if not getattr(existing, "email", None):
            existing.email = "superadmin@greenmile.local"
            db.session.commit()
        return existing
    user = User(
        username=current_app.config["SUPER_ADMIN_USERNAME"],
        full_name="Super Admin",
        email="superadmin@greenmile.local",
        role=User.ROLE_SUPER_ADMIN,
        agency_id=None,
        is_active=True,
    )
    user.set_password(current_app.config["SUPER_ADMIN_PASSWORD"])
    db.session.add(user)
    write_audit("seed_super_admin", f"Created {user.username}", actor=user)
    db.session.commit()
    return user


def pending_notifications(agency_id: int, limit: int = 12):
    """Open employee queries / alerts for the header notification panel."""
    from flask import url_for

    kinds = {
        "helpDesk": ("Help desk", "Pending"),
        "corrections": ("Attendance correction", "Pending"),
        "leave": ("Leave request", "Pending"),
        "certificateRequests": ("Certificate request", "Pending"),
        "resignations": ("Resignation", "Pending"),
    }
    items = []
    records = (
        HrRecord.query.filter(
            HrRecord.agency_id == agency_id,
            HrRecord.kind.in_(list(kinds.keys())),
        )
        .order_by(HrRecord.id.desc())
        .limit(80)
        .all()
    )
    for rec in records:
        label, pending_status = kinds.get(rec.kind, ("Request", "Pending"))
        status = (rec.data or {}).get("status") or ""
        if status != pending_status and status not in {"Pending", "In progress"}:
            continue
        if rec.kind == "helpDesk" and status not in {"Pending", "In progress"}:
            continue
        subject = (
            (rec.data or {}).get("subject")
            or (rec.data or {}).get("reason")
            or (rec.data or {}).get("purpose")
            or (rec.data or {}).get("type")
            or label
        )
        emp_ref = (rec.data or {}).get("employee") or ""
        if rec.kind == "corrections":
            href = url_for("modules.attendance_hub", tab="corrections")
        elif rec.kind == "leave":
            href = url_for("modules.module_list", kind="employees")
        elif emp_ref:
            href = url_for(
                "modules.module_list", kind=rec.kind, employee=emp_ref, edit=rec.id
            )
        else:
            href = url_for("modules.module_list", kind=rec.kind, edit=rec.id)
        items.append(
            {
                "title": f"{label}: {subject}",
                "meta": f"Status · {status or 'Open'}",
                "href": href,
            }
        )
        if len(items) >= limit:
            break
    return items


def save_employee_document_file(file_storage, agency_id: int, employee_key: str) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    if not filename:
        raise ValueError("Invalid file name.")
    ext = Path(filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf"}:
        raise ValueError("Document must be PDF or image (PNG/JPG/WEBP/GIF).")
    upload_root = Path(current_app.config["UPLOAD_FOLDER"])
    dest_dir = upload_root / str(agency_id) / "docs" / str(employee_key)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_name = f"{secrets.token_hex(6)}_{filename}"
    dest = dest_dir / dest_name
    file_storage.save(dest)
    return f"uploads/{agency_id}/docs/{employee_key}/{dest_name}"


def save_attendance_selfie(file_storage, agency_id: int, employee_id, action: str) -> str:
    """Store punch selfie under uploads/{agency}/selfies/{employee}/…"""
    from datetime import datetime, timedelta, timezone

    if not file_storage or not getattr(file_storage, "filename", None):
        raise ValueError("Selfie image is required.")
    filename = secure_filename(file_storage.filename) or "selfie.jpg"
    ext = Path(filename).suffix.lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("Selfie must be JPG, PNG or WEBP.")
    day = (datetime.now(timezone.utc) + timedelta(hours=4)).strftime("%Y-%m-%d")
    upload_root = Path(current_app.config["UPLOAD_FOLDER"])
    dest_dir = upload_root / str(agency_id) / "selfies" / str(employee_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_name = f"{day}-{action}-{secrets.token_hex(4)}{ext}"
    dest = dest_dir / dest_name
    file_storage.save(dest)
    # Soft size check after save
    if dest.stat().st_size > 900_000:
        dest.unlink(missing_ok=True)
        raise ValueError("Selfie is too large. Retake a clearer, smaller photo.")
    if dest.stat().st_size < 800:
        dest.unlink(missing_ok=True)
        raise ValueError("Selfie looks empty. Retake the photo.")
    return f"uploads/{agency_id}/selfies/{employee_id}/{dest_name}"
