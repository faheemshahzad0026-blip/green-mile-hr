from datetime import datetime
from pathlib import Path

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required

from app.decorators import employee_required
from app.employee import bp
from app.employee.services import (
    acknowledge_announcement,
    announcement_acks,
    current_shift,
    employee_agency,
    employee_match_ids,
    employee_notifications,
    leave_overlap_exists,
    leave_quotas,
    mark_notification_read,
    published_announcements,
    records_for_employee,
)
from app.extensions import db
from app.models import HrRecord
from app.utils import save_employee_document_file, write_audit

LEAVE_TYPES = [
    "Annual",
    "Sick",
    "Casual",
    "Maternity",
    "Parental",
    "Bereavement",
    "Study",
    "Unpaid",
    "Other",
]
DOC_TYPES = [
    "Passport",
    "Visa",
    "Emirates ID",
    "Labour card",
    "Work permit",
    "Insurance",
    "Driving licence",
    "Contract",
]


@bp.route("/")
@login_required
@employee_required
def home():
    agency = employee_agency(current_user)
    quotas = leave_quotas(current_user)
    all_announcements = published_announcements(current_user)
    shift = current_shift(current_user)
    docs = records_for_employee(current_user, "documents")[:3]
    unread = sum(1 for n in employee_notifications(current_user, limit=50) if not n.get("read"))
    return render_template(
        "employee/home.html",
        agency=agency,
        employee=current_user,
        quotas=quotas,
        announcements=all_announcements[:5],
        acks=announcement_acks(current_user),
        shift=shift,
        shifts=[shift] if shift else [],
        docs=docs,
        unread_notifications=unread,
    )


@bp.route("/leave", methods=["GET", "POST"])
@login_required
@employee_required
def leave():
    agency = employee_agency(current_user)
    quotas = leave_quotas(current_user)

    if request.method == "POST":
        leave_type = (request.form.get("type") or "Annual").strip()
        if leave_type not in LEAVE_TYPES:
            leave_type = "Annual"
        frm = (request.form.get("from") or "").strip()
        to = (request.form.get("to") or "").strip()
        reason = (request.form.get("reason") or "").strip()
        if not frm or not to:
            flash("Start and end dates are required.", "danger")
        elif not reason or len(reason) > 2000:
            flash("Please enter a reason (max 2000 characters).", "danger")
        else:
            date_error = None
            try:
                d0 = datetime.strptime(frm, "%Y-%m-%d")
                d1 = datetime.strptime(to, "%Y-%m-%d")
                if d1 < d0:
                    date_error = "End date must be on or after start date."
                elif (d1 - d0).days + 1 > 366:
                    date_error = "Leave cannot exceed 366 days."
            except ValueError:
                date_error = "Use valid dates (YYYY-MM-DD)."
            if date_error:
                flash(date_error, "danger")
            elif leave_overlap_exists(current_user, frm, to):
                flash("This overlaps an existing pending or approved leave request.", "danger")
            else:
                row = {
                    "employee": str(current_user.id),
                    "type": leave_type,
                    "from": frm,
                    "to": to,
                    "status": "Pending",
                    "reason": reason,
                    "source": "Employee app",
                }
                db.session.add(HrRecord(agency_id=current_user.agency_id, kind="leave", data=row))
                write_audit(
                    "leave_apply",
                    f"{current_user.employee_code} {leave_type} {frm}→{to}",
                    agency_id=current_user.agency_id,
                )
                db.session.commit()
                flash("Leave request submitted. HR will review it.", "success")
                return redirect(url_for("employee.leave"))

    return render_template(
        "employee/leave.html",
        agency=agency,
        employee=current_user,
        quotas=quotas,
        leave_types=LEAVE_TYPES,
        leaves=quotas.get("leaves") or [],
    )


@bp.route("/announcements", methods=["GET", "POST"])
@login_required
@employee_required
def announcements():
    agency = employee_agency(current_user)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "acknowledge":
            try:
                acknowledge_announcement(
                    current_user,
                    int(request.form.get("id") or 0),
                    (request.form.get("revision") or "").strip(),
                )
                write_audit(
                    "announcement_ack",
                    f"{current_user.employee_code} #{request.form.get('id')}",
                    agency_id=current_user.agency_id,
                )
                db.session.commit()
                flash("Announcement acknowledged.", "success")
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
            return redirect(url_for("employee.announcements"))

    rows = published_announcements(current_user)
    return render_template(
        "employee/announcements.html",
        agency=agency,
        employee=current_user,
        announcements=rows,
        acks=announcement_acks(current_user),
    )


@bp.route("/shifts")
@login_required
@employee_required
def shifts():
    agency = employee_agency(current_user)
    rows = records_for_employee(current_user, "shifts")
    active = current_shift(current_user)
    return render_template(
        "employee/shifts.html",
        agency=agency,
        employee=current_user,
        shifts=rows,
        current=active,
    )


@bp.route("/documents", methods=["GET", "POST"])
@login_required
@employee_required
def documents():
    agency = employee_agency(current_user)
    emp_key = current_user.employee_code or str(current_user.id)

    if request.method == "POST":
        action = request.form.get("action") or "upload"
        if action == "delete":
            rid = int(request.form.get("id") or 0)
            match = employee_match_ids(current_user)
            rec = HrRecord.query.filter_by(
                id=rid, agency_id=current_user.agency_id, kind="documents"
            ).first()
            if not rec or str((rec.data or {}).get("employee") or "") not in match:
                flash("Document not found.", "danger")
            else:
                db.session.delete(rec)
                write_audit(
                    "doc_delete_self",
                    f"{current_user.employee_code} doc#{rid}",
                    agency_id=current_user.agency_id,
                )
                db.session.commit()
                flash("Document removed.", "success")
            return redirect(url_for("employee.documents"))

        try:
            path = save_employee_document_file(
                request.files.get("file"), current_user.agency_id, emp_key
            )
            doc = {
                "employee": str(current_user.id),
                "type": (request.form.get("type") or "Contract").strip(),
                "number": (request.form.get("number") or "").strip(),
                "issued": (request.form.get("issued") or "").strip(),
                "expiry": (request.form.get("expiry") or "").strip(),
                "status": (request.form.get("status") or "Valid").strip(),
                "filePath": path or "",
                "notes": (request.form.get("notes") or "").strip(),
            }
            if doc["type"] not in DOC_TYPES:
                doc["type"] = "Contract"
            if not doc["number"] and not path:
                raise ValueError("Enter a document number or upload a file.")
            db.session.add(HrRecord(agency_id=current_user.agency_id, kind="documents", data=doc))
            write_audit(
                "doc_upload_self",
                f"{current_user.employee_code}",
                agency_id=current_user.agency_id,
            )
            db.session.commit()
            flash("Document saved.", "success")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        return redirect(url_for("employee.documents"))

    rows = records_for_employee(current_user, "documents")
    return render_template(
        "employee/documents.html",
        agency=agency,
        employee=current_user,
        documents=rows,
        doc_types=DOC_TYPES,
    )


@bp.route("/api/notifications")
@login_required
@employee_required
def api_notifications():
    """JSON feed for portal + Android WebView (old employee-bridge notifications)."""
    items = employee_notifications(current_user, limit=20)
    announcements = published_announcements(current_user)
    unread = sum(1 for n in items if not n.get("read"))
    return jsonify(
        {
            "ok": True,
            "count": len(items),
            "unread": unread,
            "announcement_count": len(announcements),
            "items": items,
        }
    )


@bp.route("/api/notifications/read", methods=["POST"])
@login_required
@employee_required
def api_notification_read():
    key = (request.json or {}).get("key") or request.form.get("key") or ""
    if not key:
        return jsonify({"ok": False, "error": "Missing key"}), 400
    mark_notification_read(current_user, key)
    db.session.commit()
    unread = sum(1 for n in employee_notifications(current_user, limit=50) if not n.get("read"))
    return jsonify({"ok": True, "unread": unread})


@bp.route("/download-apk")
def download_apk_page():
    apk_dir = Path(current_app.config["APK_FOLDER"])
    apk_file = apk_dir / "green-mile-attendance.apk"
    if current_user.is_authenticated and getattr(current_user, "is_employee_account", False):
        layout_name = "layout_employee.html"
    elif current_user.is_authenticated:
        layout_name = "layout_admin.html"
    else:
        return render_template(
            "employee/download_apk_public.html",
            apk_ready=apk_file.exists(),
        )
    return render_template(
        "employee/download_apk.html",
        layout_name=layout_name,
        apk_ready=apk_file.exists(),
    )


@bp.route("/apk-file")
def apk_file():
    apk_dir = Path(current_app.config["APK_FOLDER"])
    filename = "green-mile-attendance.apk"
    path = apk_dir / filename
    if not path.exists():
        flash("APK is not available yet. Place the signed APK on the server.", "warning")
        return redirect(url_for("employee.download_apk_page"))
    return send_from_directory(apk_dir, filename, as_attachment=True)
