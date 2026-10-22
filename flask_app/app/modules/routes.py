import json
import re
from datetime import datetime

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.decorators import admin_required
from app.extensions import db
from app.hr_modules import EMPLOYEE_SCOPED_KINDS, MODULES, TOOL_PAGES
from app.models import Employee, HrRecord, User
from app.modules import bp
from app.utils import (
    get_active_agency,
    next_employee_code,
    pending_notifications,
    save_agency_logo,
    save_employee_document_file,
    write_audit,
)


def _agency_or_redirect():
    agency = get_active_agency()
    if agency:
        return agency
    if current_user.is_super_admin:
        flash("Select an agency first (All agencies → Open workspace).", "warning")
        return None
    flash("No agency assigned.", "danger")
    return None


def _employees_for_agency(agency_id):
    """People for employee pickers (shifts, leave, payroll, …).

    Built from Active HR employee records — not the app-login ``is_active`` flag,
    so blocked-app staff still appear when assigning shifts.
    Option values prefer ``authEmployeeId`` (same as emp_ref / filters).
    """
    from types import SimpleNamespace

    rows = (
        HrRecord.query.filter_by(agency_id=agency_id, kind="employees")
        .order_by(HrRecord.id.desc())
        .all()
    )
    result = []
    seen = set()
    for r in rows:
        data = r.data or {}
        if _employment_status(data) == "Inactive":
            continue
        code = (data.get("code") or "").strip()
        name = (data.get("name") or "Employee").strip()
        value_id = data.get("authEmployeeId")
        if value_id is None and code:
            auth = Employee.query.filter_by(
                agency_id=agency_id, employee_code=code
            ).first()
            if auth:
                value_id = auth.id
        if value_id is None:
            value_id = r.id
        key = str(value_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            SimpleNamespace(
                id=value_id,
                full_name=name,
                employee_code=code or str(value_id),
            )
        )
    result.sort(key=lambda e: str(e.employee_code))
    return result


def _clip_cell(text, limit=72):
    """Plain text truncated for table cells; full text in native tooltip."""
    from markupsafe import Markup, escape

    raw = str(text or "").strip()
    if not raw:
        return "—"
    short = raw if len(raw) <= limit else raw[: max(0, limit - 1)].rstrip() + "…"
    if short == raw:
        return Markup(f'<span class="cell-clip" title="{escape(raw)}">{escape(short)}</span>')
    return Markup(f'<span class="cell-clip" title="{escape(raw)}">{escape(short)}</span>')


def _display(record, key, employees_map):
    from markupsafe import Markup

    from app.employee.services import format_time_12h

    val = record.get(key)
    if key == "employee":
        emp = employees_map.get(str(val)) or employees_map.get(val)
        if emp:
            return f"{emp.full_name} · {emp.employee_code}"
        # also try hr employee records
        return str(val or "—")
    if key in {"title", "body", "subject", "message", "reason", "notes"}:
        return _clip_cell(val, 56 if key == "title" else 80)
    if key == "audience":
        aud = str(val or "All employees")
        if aud == "Department" and record.get("department"):
            return _clip_cell(f"Department · {record.get('department')}", 48)
        return aud or "—"
    if key in {"timeIn", "timeOut", "start", "end"}:
        return format_time_12h(val)
    if key == "location":
        loc = record.get("checkInLocation") or record.get("checkOutLocation")
        if not isinstance(loc, dict):
            return "—"
        lat, lng = loc.get("latitude"), loc.get("longitude")
        if lat is None or lng is None:
            return "—"
        acc = loc.get("accuracy")
        label = f"{lat}, {lng}"
        if acc is not None:
            label += f" (±{int(acc)}m)"
        maps = f"https://maps.google.com/?q={lat},{lng}"
        kind = "In" if record.get("checkInLocation") else "Out"
        if record.get("checkInLocation") and record.get("checkOutLocation"):
            kind = "In/Out"
        return Markup(
            f'<a class="text-btn" href="{maps}" target="_blank" rel="noopener" title="{label}">{kind} GPS</a>'
        )
    if key == "selfie":
        bits = []
        for label, field in (("In", "checkInSelfie"), ("Out", "checkOutSelfie")):
            path = record.get(field)
            if path:
                bits.append(
                    f'<a class="text-btn" href="{url_for("static", filename=path)}" target="_blank" rel="noopener">{label}</a>'
                )
        return Markup(" · ".join(bits)) if bits else "—"
    if key == "status" and getattr(record, "kind", None) == "employees":
        # Normalize legacy employment statuses for the listing
        raw = str(val or "Active")
        if raw in {"Terminated", "Resigned", "Inactive"}:
            return "Inactive"
        return "Active" if raw in {"Active", "On leave"} else raw
    if key == "net":
        try:
            basic = float(record.get("basic") or 0)
            allowances = float(record.get("allowances") or 0)
            additions = float(record.get("additions") or 0)
            deductions = float(record.get("deductions") or record.get("otherDeductions") or 0)
            return f"{basic + allowances + additions - deductions:,.2f}"
        except Exception:
            return str(val or "—")
    if val in (None, ""):
        return "—"
    return str(val)


def _employment_status(data):
    raw = str((data or {}).get("status") or "Active")
    if raw in {"Terminated", "Resigned", "Inactive"}:
        return "Inactive"
    return "Active"


def _sync_auth_employee(agency_id, data, record_id=None):
    """Keep Employee login row in sync when saving employees module."""
    import secrets

    code = (data.get("code") or "").strip()
    if not code:
        code = next_employee_code(agency_id)
        data["code"] = code
    pin = (data.get("pin") or "").strip()
    generated_pin = None
    emp = Employee.query.filter_by(agency_id=agency_id, employee_code=code).first()
    if not emp:
        if not re.fullmatch(r"\d{6}", pin or ""):
            generated_pin = f"{secrets.randbelow(1000000):06d}"
            pin = generated_pin
        emp = Employee(
            agency_id=agency_id,
            employee_code=code,
            full_name=data.get("name") or code,
            phone=data.get("phone"),
            email=data.get("email"),
            designation=data.get("designation"),
            department=data.get("department"),
            # App login default: Not allowed until HR selects Allow in App Login modal
            is_active=False,
        )
        emp.set_pin(pin)
        db.session.add(emp)
    else:
        emp.full_name = data.get("name") or emp.full_name
        emp.phone = data.get("phone")
        emp.email = data.get("email")
        emp.designation = data.get("designation")
        emp.department = data.get("department")
        # Employment Active/Inactive is separate from app allow/block (emp.is_active).
        if pin and re.fullmatch(r"\d{6}", pin):
            emp.set_pin(pin)
            generated_pin = pin
    data.pop("pin", None)
    data["_generated_pin"] = generated_pin
    return data


@bp.route("/attendance", methods=["GET", "POST"])
@login_required
@admin_required
def attendance_hub():
    """Daily punches (view-only) + correction requests (HR approve / reject)."""
    from app.employee.services import review_attendance_correction

    agency = _agency_or_redirect()
    if not agency:
        return redirect(
            url_for("super_admin.overview")
            if current_user.is_super_admin
            else url_for("agency.dashboard")
        )

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        tab = request.form.get("tab") or "corrections"
        if action in {"Approved", "Rejected"}:
            try:
                cid = int(request.form.get("id") or 0)
                review_attendance_correction(
                    agency.id,
                    cid,
                    action,
                    (request.form.get("reviewNote") or "").strip(),
                )
                write_audit(
                    f"att_correction_{action.lower()}",
                    f"#{cid}",
                    agency_id=agency.id,
                )
                db.session.commit()
                flash(
                    "Attendance marked Present."
                    if action == "Approved"
                    else "Request rejected — day stays Absent.",
                    "success",
                )
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
            return redirect(url_for("modules.attendance_hub", tab="corrections"))
        flash("Daily attendance punches are view-only.", "warning")
        return redirect(url_for("modules.attendance_hub", tab=tab or "daily"))

    tab = request.args.get("tab") or "daily"
    if tab not in {"daily", "corrections"}:
        tab = "daily"
    kind = "corrections" if tab == "corrections" else "attendance"
    return _module_crud(
        agency,
        kind,
        template="modules/attendance.html",
        tab=tab,
        read_only=True,
    )


@bp.route("/api/notifications")
@login_required
@admin_required
def api_notifications():
    """JSON feed for live admin bell (no page reload)."""
    agency = get_active_agency()
    if not agency:
        return jsonify({"ok": False, "count": 0, "items": []}), 400
    items = pending_notifications(agency.id, limit=20)
    return jsonify({"ok": True, "count": len(items), "items": items})


@bp.route("/search")
@login_required
@admin_required
def global_search():
    agency = _agency_or_redirect()
    if not agency:
        return redirect(
            url_for("super_admin.overview")
            if current_user.is_super_admin
            else url_for("agency.dashboard")
        )
    q = (request.args.get("q") or "").strip()
    results = []
    if q:
        ql = q.lower()
        records = HrRecord.query.filter_by(agency_id=agency.id).all()
        for r in records:
            blob = json.dumps(r.data or {}).lower()
            if ql in blob or ql in r.kind.lower():
                href = url_for("modules.module_list", kind=r.kind, edit=r.id)
                if r.kind in {"attendance", "corrections"}:
                    href = url_for(
                        "modules.attendance_hub",
                        tab="corrections" if r.kind == "corrections" else "daily",
                        edit=r.id,
                    )
                if r.kind == "employees":
                    href = url_for("modules.employee_profile", record_id=r.id)
                if r.kind == "leave":
                    emp = (r.data or {}).get("employee") or ""
                    leave_args = {"kind": "leave", "focus": r.id}
                    if emp:
                        leave_args["employee"] = emp
                    href = url_for("modules.module_list", **leave_args)
                results.append({"record": r, "href": href})
    return render_template(
        "modules/search.html",
        agency=agency,
        meta=TOOL_PAGES["globalSearch"],
        q=q,
        results=results,
    )


@bp.route("/employees/<int:record_id>", methods=["GET", "POST"])
@login_required
@admin_required
def employee_profile(record_id):
    agency = _agency_or_redirect()
    if not agency:
        return redirect(url_for("agency.dashboard"))

    record = HrRecord.query.filter_by(
        id=record_id, agency_id=agency.id, kind="employees"
    ).first_or_404()
    data = record.data or {}
    emp_key = str(data.get("authEmployeeId") or data.get("code") or record.id)
    auth_emp = None
    if data.get("code"):
        auth_emp = Employee.query.filter_by(
            agency_id=agency.id, employee_code=data.get("code")
        ).first()
    emp_ids = {str(record.id)}
    if auth_emp:
        emp_ids.add(str(auth_emp.id))
    if data.get("code"):
        emp_ids.add(str(data.get("code")))

    if request.method == "POST":
        action = request.form.get("action")
        if action in {"upload_document", "update_document"}:
            try:
                path = save_employee_document_file(
                    request.files.get("file"), agency.id, emp_key
                )
                payload = {
                    "type": (request.form.get("type") or "Contract").strip(),
                    "number": (request.form.get("number") or "").strip(),
                    "issued": (request.form.get("issued") or "").strip(),
                    "expiry": (request.form.get("expiry") or "").strip(),
                    "status": (request.form.get("status") or "Valid").strip(),
                    "notes": (request.form.get("notes") or "").strip(),
                }
                if action == "update_document":
                    rid = int(request.form.get("id") or 0)
                    doc_rec = HrRecord.query.filter_by(
                        id=rid, agency_id=agency.id, kind="documents"
                    ).first()
                    if not doc_rec:
                        raise ValueError("Document not found.")
                    data = dict(doc_rec.data or {})
                    data.update(payload)
                    if path:
                        data["filePath"] = path
                    if not data.get("number") and not data.get("filePath"):
                        raise ValueError("Enter a document number/title or upload a file.")
                    data["uploadedBy"] = current_user.username or current_user.display_name
                    doc_rec.data = data
                    write_audit("doc_update", f"employee {emp_key} #{rid}", agency_id=agency.id)
                    db.session.commit()
                else:
                    if not payload["number"] and not path:
                        raise ValueError("Enter a document number/title or upload a file.")
                    doc = {
                        "employee": str(auth_emp.id if auth_emp else record.id),
                        **payload,
                        "filePath": path or "",
                        "source": "HR",
                        "uploadedBy": current_user.username or current_user.display_name,
                    }
                    db.session.add(HrRecord(agency_id=agency.id, kind="documents", data=doc))
                    write_audit("doc_upload", f"employee {emp_key}", agency_id=agency.id)
                    db.session.commit()
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
            return redirect(
                url_for("modules.employee_profile", record_id=record.id, _anchor="documents")
            )

    def related(kind):
        rows = (
            HrRecord.query.filter_by(agency_id=agency.id, kind=kind)
            .order_by(HrRecord.id.desc())
            .all()
        )
        out = []
        for r in rows:
            ref = str((r.data or {}).get("employee") or "")
            if ref in emp_ids:
                # Prefer .data via HrRecord.get for templates
                out.append(r)
        return out

    docs = related("documents")

    return render_template(
        "modules/employee_profile.html",
        agency=agency,
        record=record,
        data=data,
        auth_emp=auth_emp,
        documents=docs,
        emp_key=emp_key,
    )


@bp.route("/<kind>", methods=["GET", "POST"])
@login_required
@admin_required
def module_list(kind):
    agency = _agency_or_redirect()
    if not agency:
        return redirect(
            url_for("super_admin.overview")
            if current_user.is_super_admin
            else url_for("agency.dashboard")
        )

    # Merged / removed sidebar modules
    if kind in {"attendance", "corrections", "mobile", "attendanceLedger"}:
        tab = "corrections" if kind == "corrections" else "daily"
        return redirect(
            url_for(
                "modules.attendance_hub",
                tab=tab,
                edit=request.args.get("edit"),
                new=request.args.get("new"),
                q=request.args.get("q"),
            )
        )
    if kind in {
        "adminMobile",
        "dataQuality",
        "employeeFile",
        "leaveBalances",
        "globalSearch",
        "payroll",
        "salaryPayments",
        "adjustments",
        "loanReport",
        "mobileAccess",
        "monthlySummary",
        "staff",
    }:
        if kind == "globalSearch":
            return redirect(url_for("modules.global_search", q=request.args.get("q")))
        if kind in {"employeeFile", "mobileAccess", "staff"}:
            flash("Manage this from the Employees list.", "info")
            return redirect(url_for("modules.module_list", kind="employees"))
        flash("This module is not used in the current workspace menu.", "info")
        return redirect(url_for("agency.dashboard"))

    # Employee-scoped modules: require employee= (or edit=) so they stay under Employees
    if kind in EMPLOYEE_SCOPED_KINDS and kind != "gratuity":
        if not request.args.get("employee") and not request.args.get("edit"):
            flash("Open this from Employees → Actions for a specific person.", "info")
            return redirect(url_for("modules.module_list", kind="employees"))

    # Tool / report pages
    if kind in TOOL_PAGES and kind not in MODULES:
        return _tool_page(kind, agency)

    mod = MODULES.get(kind)
    if not mod:
        flash("Unknown module.", "danger")
        return redirect(url_for("agency.dashboard"))

    return _module_crud(agency, kind)


def _module_crud(agency, kind, template="modules/list.html", tab=None, read_only=False):
    mod = MODULES.get(kind)
    if not mod:
        flash("Unknown module.", "danger")
        return redirect(url_for("agency.dashboard"))

    employees = _employees_for_agency(agency.id)
    employees_map = {str(e.id): e for e in employees}
    for e in employees:
        employees_map[e.employee_code] = e

    def _redirect_after():
        if template == "modules/attendance.html":
            return redirect(url_for("modules.attendance_hub", tab=tab or "daily"))
        emp = (request.args.get("employee") or request.form.get("employee") or "").strip()
        if emp and kind != "employees":
            return redirect(url_for("modules.module_list", kind=kind, employee=emp))
        return redirect(url_for("modules.module_list", kind=kind))

    if request.method == "POST":
        if read_only:
            flash("This module is view-only.", "warning")
            return _redirect_after()
        action = request.form.get("action")
        if action == "delete":
            rid = int(request.form.get("id", 0))
            rec = HrRecord.query.filter_by(id=rid, agency_id=agency.id, kind=kind).first_or_404()
            db.session.delete(rec)
            write_audit("hr_delete", f"{kind}#{rid}", agency_id=agency.id)
            db.session.commit()
            return _redirect_after()

        # Leave is employee-applied only — HR may approve / reject, not create
        if kind == "leave" and action not in {"Approved", "Rejected", "delete"}:
            flash("Leave can only be applied by the employee from their portal.", "warning")
            return _redirect_after()

        # Leave: quick approve / reject (✓ / ✕) — notifies employee via portal bell
        if kind == "leave" and action in {"Approved", "Rejected"}:
            from app.employee.services import review_leave_request

            try:
                lid = int(request.form.get("id") or 0)
                review_leave_request(
                    agency.id,
                    lid,
                    action,
                    (request.form.get("reviewNote") or "").strip(),
                )
                write_audit(
                    f"leave_{action.lower()}",
                    f"#{lid}",
                    agency_id=agency.id,
                )
                db.session.commit()
                flash(
                    "Leave approved. Employee will get a notification."
                    if action == "Approved"
                    else "Leave rejected. Employee will get a notification.",
                    "success",
                )
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
            emp = (request.args.get("employee") or request.form.get("employee") or "").strip()
            focus = (request.form.get("id") or "").strip()
            if emp:
                return redirect(
                    url_for("modules.module_list", kind="leave", employee=emp, focus=focus)
                )
            return redirect(url_for("modules.module_list", kind="leave", focus=focus))

        # App access modal actions from Employees listing
        if kind == "employees" and action in {
            "toggle_app",
            "reset_pin",
            "set_pin",
            "allow_app",
            "block_app",
            "set_app_status",
        }:
            return _employee_app_access_action(agency, action)

        data = {}
        for field in mod["fields"]:
            key = field["key"]
            data[key] = (request.form.get(key) or "").strip()
        record_id = request.form.get("id")
        try:
            generated_pin = None
            if kind == "employees":
                data = _sync_auth_employee(agency.id, data, record_id)
                generated_pin = data.pop("_generated_pin", None)
                auth = Employee.query.filter_by(
                    agency_id=agency.id, employee_code=data.get("code")
                ).first()
                if auth:
                    data["authEmployeeId"] = auth.id
            if kind == "payroll" and not data.get("deductions"):
                data["deductions"] = data.get("otherDeductions") or "0"
            if kind == "announcements":
                # Port of old lib/announcements: new revision on every save → re-ack
                import uuid as _uuid

                if data.get("audience") != "Department":
                    data["department"] = ""
                if data.get("expiry") and data.get("date") and data["expiry"] < data["date"]:
                    raise ValueError("Expiry must follow publish date.")
                data["revision"] = str(_uuid.uuid4())
            if record_id:
                rec = HrRecord.query.filter_by(
                    id=int(record_id), agency_id=agency.id, kind=kind
                ).first_or_404()
                # Preserve code / auth id when editing
                if kind == "employees":
                    prev = rec.data or {}
                    if prev.get("code") and not data.get("code"):
                        data["code"] = prev.get("code")
                    if prev.get("authEmployeeId") and not data.get("authEmployeeId"):
                        data["authEmployeeId"] = prev.get("authEmployeeId")
                if kind == "leave":
                    from app.employee.services import dubai_now_iso

                    prev = rec.data or {}
                    # Keep dayPart / days / source from employee app when HR edits status
                    for keep in ("dayPart", "days", "source", "reason"):
                        if not data.get(keep) and prev.get(keep):
                            data[keep] = prev.get(keep)
                    if (data.get("status") or "") in {"Approved", "Rejected"} and (
                        prev.get("status") or ""
                    ) == "Pending":
                        data["reviewedAt"] = dubai_now_iso()
                        if prev.get("reviewNote") and not data.get("reviewNote"):
                            data["reviewNote"] = prev.get("reviewNote")
                rec.data = data
                write_audit("hr_update", f"{kind}#{rec.id}", agency_id=agency.id)
            else:
                rec = HrRecord(agency_id=agency.id, kind=kind, data=data)
                db.session.add(rec)
                db.session.flush()
                write_audit("hr_create", f"{kind}", agency_id=agency.id)
            db.session.commit()
            if kind == "employees" and generated_pin:
                session[f"reveal_pin_{rec.id}"] = generated_pin
                return redirect(url_for("modules.module_list", kind="employees", app=rec.id))
            if kind == "employees" and not record_id:
                return redirect(url_for("modules.module_list", kind="employees", app=rec.id))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        return _redirect_after()

    q = (request.args.get("q") or "").strip().lower()
    employee_filter = (request.args.get("employee") or "").strip()
    records = (
        HrRecord.query.filter_by(agency_id=agency.id, kind=kind)
        .order_by(HrRecord.id.desc())
        .all()
    )
    if q:
        records = [r for r in records if q in json.dumps(r.data or {}).lower()]
    if employee_filter and kind != "employees":
        # Match auth employee id, HR record id, or employee code aliases
        match_ids = {employee_filter}
        try:
            auth = Employee.query.get(int(employee_filter))
            if auth and auth.agency_id == agency.id:
                match_ids.add(str(auth.id))
                match_ids.add(auth.employee_code)
                hr = (
                    HrRecord.query.filter_by(agency_id=agency.id, kind="employees")
                    .order_by(HrRecord.id.desc())
                    .all()
                )
                for h in hr:
                    hd = h.data or {}
                    if str(hd.get("authEmployeeId") or "") == str(auth.id) or hd.get(
                        "code"
                    ) == auth.employee_code:
                        match_ids.add(str(h.id))
        except (TypeError, ValueError):
            pass
        records = [
            r
            for r in records
            if str((r.data or {}).get("employee") or "") in match_ids
        ]

    edit_id = request.args.get("edit")
    edit_record = None
    if edit_id:
        edit_record = HrRecord.query.filter_by(
            id=int(edit_id), agency_id=agency.id, kind=kind
        ).first()

    # Prefill employee when opening "add" from employee actions
    form_defaults = {}
    if employee_filter and not edit_record:
        form_defaults["employee"] = employee_filter
    # Announcements: default to publish for all employees
    if kind == "announcements" and not edit_record and request.args.get("new") == "1":
        from datetime import datetime, timedelta, timezone

        dubai = (datetime.now(timezone.utc) + timedelta(hours=4)).strftime("%Y-%m-%d")
        form_defaults.setdefault("date", dubai)
        form_defaults.setdefault("audience", "All employees")
        form_defaults.setdefault("status", "Published")

    # Leave: pending first so HR can act quickly
    if kind == "leave":
        def _leave_sort_key(r):
            st = ((r.data or {}).get("status") or "").lower()
            pending = 0 if st == "pending" else 1
            return (pending, -(r.id or 0))

        records = sorted(records, key=_leave_sort_key)

    rows = []
    reveal_pins = {}
    focus_id = (request.args.get("focus") or "").strip()
    for r in records:
        data = r.data or {}
        auth = None
        emp_ref = ""
        employment = "Active"
        if kind == "employees":
            employment = _employment_status(data)
            if data.get("authEmployeeId"):
                emp_ref = str(data.get("authEmployeeId"))
            if data.get("code"):
                auth = Employee.query.filter_by(
                    agency_id=agency.id, employee_code=data.get("code")
                ).first()
                if auth and not emp_ref:
                    emp_ref = str(auth.id)
            pin = session.get(f"reveal_pin_{r.id}")
            if pin:
                reveal_pins[str(r.id)] = pin
        rows.append(
            {
                "id": r.id,
                "cells": [_display(r, col, employees_map) for col in mod["columns"]],
                "data": data,
                "name": data.get("name") or "Employee",
                "app_allowed": bool(auth and auth.is_active),
                "has_login": bool(auth),
                "employee_code": data.get("code") or "—",
                "emp_ref": emp_ref or str(r.id),
                "employment_status": employment,
                "reveal_pin": reveal_pins.get(str(r.id), ""),
                "is_focus": focus_id and str(r.id) == focus_id,
            }
        )

    open_app_id = (request.args.get("app") or "").strip()
    if open_app_id and open_app_id in reveal_pins:
        # Keep pin in session until user closes / navigates away after copy
        pass

    return render_template(
        template,
        kind=kind,
        mod=mod,
        agency=agency,
        rows=rows,
        fields=mod["fields"],
        employees=employees,
        edit_record=None if read_only else edit_record,
        form_defaults=form_defaults,
        employee_filter=employee_filter,
        q=q,
        tab=tab,
        read_only=read_only,
        focus_id=focus_id,
        # Modals open only on button click (not on page load / ?new / ?edit)
        show_form=False,
        open_employee_form=False,
        open_app_id=open_app_id,
    )


def _employee_app_access_action(agency, action):
    """Allow / block app login and reveal credentials from the listing modal."""
    import secrets

    from flask import jsonify

    wants_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in (request.headers.get("Accept") or "")
    )

    def _json(payload, code=200):
        return jsonify(payload), code

    def _done(message, allowed=None, pin=None, code_val=None, error=None, status=200):
        if wants_json:
            if error:
                return _json({"ok": False, "error": error}, status)
            return _json(
                {
                    "ok": True,
                    "message": message,
                    "allowed": bool(allowed if allowed is not None else (auth.is_active if auth else False)),
                    "pin": pin or session.get(f"reveal_pin_{rec.id}", ""),
                    "code": code_val or (auth.employee_code if auth else ""),
                }
            )
        if error:
            flash(error, "danger")
        return redirect(url_for("modules.module_list", kind="employees", app=rec.id))

    rid = int(request.form.get("id") or 0)
    rec = HrRecord.query.filter_by(
        id=rid, agency_id=agency.id, kind="employees"
    ).first_or_404()
    data = dict(rec.data or {})
    code = (data.get("code") or "").strip()
    auth = None
    if code:
        auth = Employee.query.filter_by(agency_id=agency.id, employee_code=code).first()
    if not auth and data.get("authEmployeeId"):
        auth = Employee.query.filter_by(
            id=int(data["authEmployeeId"]), agency_id=agency.id
        ).first()

    if not auth:
        # Create login row if missing
        if not code:
            code = next_employee_code(agency.id)
            data["code"] = code
            rec.data = data
        new_pin = f"{secrets.randbelow(1000000):06d}"
        auth = Employee(
            agency_id=agency.id,
            employee_code=code,
            full_name=data.get("name") or code,
            phone=data.get("phone"),
            email=data.get("email"),
            designation=data.get("designation"),
            department=data.get("department"),
            is_active=False,
        )
        auth.set_pin(new_pin)
        db.session.add(auth)
        db.session.flush()
        data["authEmployeeId"] = auth.id
        rec.data = data
        session[f"reveal_pin_{rec.id}"] = new_pin

    if action == "set_app_status":
        status = (request.form.get("status") or "not_allowed").strip()
        if status == "allowed":
            auth.is_active = True
            if not session.get(f"reveal_pin_{rec.id}"):
                new_pin = f"{secrets.randbelow(1000000):06d}"
                auth.set_pin(new_pin)
                session[f"reveal_pin_{rec.id}"] = new_pin
            write_audit(
                "app_access_toggle",
                f"{auth.employee_code} active=True",
                agency_id=agency.id,
            )
            db.session.commit()
            return _done(
                "App login allowed. Employee can sign in with Login ID and PIN.",
                allowed=True,
                pin=session.get(f"reveal_pin_{rec.id}", ""),
                code_val=auth.employee_code,
            )
        auth.is_active = False
        write_audit(
            "app_access_toggle",
            f"{auth.employee_code} active=False",
            agency_id=agency.id,
        )
        db.session.commit()
        return _done(
            "App login not allowed. Employee will see: ID disabled. Please contact HR department.",
            allowed=False,
            pin=session.get(f"reveal_pin_{rec.id}", ""),
            code_val=auth.employee_code,
        )
    if action == "block_app" or (action == "toggle_app" and auth.is_active):
        auth.is_active = False
        write_audit("app_access_toggle", f"{auth.employee_code} active=False", agency_id=agency.id)
        db.session.commit()
        return _done("App login not allowed.", allowed=False, code_val=auth.employee_code)
    if action in {"allow_app", "toggle_app"}:
        auth.is_active = True
        if not session.get(f"reveal_pin_{rec.id}"):
            new_pin = f"{secrets.randbelow(1000000):06d}"
            auth.set_pin(new_pin)
            session[f"reveal_pin_{rec.id}"] = new_pin
        write_audit(
            "app_access_toggle",
            f"{auth.employee_code} active=True",
            agency_id=agency.id,
        )
        db.session.commit()
        return _done(
            "App login allowed. Copy Login ID and PIN for the employee.",
            allowed=True,
            pin=session.get(f"reveal_pin_{rec.id}", ""),
            code_val=auth.employee_code,
        )
    if action == "reset_pin":
        new_pin = f"{secrets.randbelow(1000000):06d}"
        auth.set_pin(new_pin)
        session[f"reveal_pin_{rec.id}"] = new_pin
        write_audit("app_pin_reset", auth.employee_code, agency_id=agency.id)
        db.session.commit()
        return _done(
            f"New PIN generated: {new_pin}",
            allowed=auth.is_active,
            pin=new_pin,
            code_val=auth.employee_code,
        )
    if action == "set_pin":
        new_pin = (request.form.get("pin") or "").strip()
        if not re.fullmatch(r"\d{6}", new_pin):
            return _done("", error="PIN must be exactly 6 digits.", status=400)
        auth.set_pin(new_pin)
        session[f"reveal_pin_{rec.id}"] = new_pin
        write_audit("app_pin_set", auth.employee_code, agency_id=agency.id)
        db.session.commit()
        return _done(
            "App PIN saved. Copy it now to send to the user.",
            allowed=auth.is_active,
            pin=new_pin,
            code_val=auth.employee_code,
        )

    return _done("", error="Unknown action.", status=400)


def _tool_page(kind, agency):
    meta = TOOL_PAGES[kind]
    if kind == "mobileAccess":
        return redirect(url_for("employee.download_apk_page"))
    if kind == "adminLogin":
        return redirect(url_for("modules.admin_login_settings"))
    if kind == "backup":
        return render_template("modules/backup.html", agency=agency, meta=meta)
    if kind == "globalSearch":
        return redirect(url_for("modules.global_search", q=request.args.get("q")))
    if kind == "gratuity":
        return render_template("modules/gratuity.html", agency=agency, meta=meta)
    return render_template("modules/tool.html", agency=agency, meta=meta, kind=kind)


@bp.route("/admin-login-settings", methods=["GET", "POST"])
@login_required
@admin_required
def admin_login_settings():
    agency = get_active_agency()
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        agency_name = (request.form.get("agency_name") or "").strip()
        company_name = (request.form.get("company_name") or "").strip()
        company_email = (request.form.get("company_email") or "").strip()
        company_phone = (request.form.get("company_phone") or "").strip()
        company_address = (request.form.get("company_address") or "").strip()
        error = None
        if len(username) < 3:
            error = "Username must be at least 3 characters."
        elif password and len(password) < 6:
            error = "Password must be at least 6 characters."
        elif password and password != confirm:
            error = "Passwords do not match."
        elif User.query.filter(User.username == username, User.id != current_user.id).first():
            error = "Username already taken."
        elif agency and (len(agency_name) < 2 or len(company_name) < 2):
            error = "Agency name and company name are required."

        if error:
            flash(error, "danger")
            return render_template(
                "modules/admin_login.html", agency=agency, open_form=True
            )

        current_user.username = username
        current_user.full_name = full_name or None
        current_user.email = email or None
        if password:
            current_user.set_password(password)

        if agency:
            agency.name = agency_name
            agency.company_name = company_name
            agency.company_email = company_email or None
            agency.company_phone = company_phone or None
            agency.company_address = company_address or None
            try:
                logo_path = save_agency_logo(request.files.get("logo"), agency.id)
                if logo_path:
                    agency.logo_path = logo_path
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
                return render_template(
                    "modules/admin_login.html", agency=agency, open_form=True
                )
            write_audit(
                "agency_profile_update",
                f"Updated agency profile {agency.name}",
                agency_id=agency.id,
            )

        db.session.commit()
        return redirect(url_for("modules.admin_login_settings"))
    return render_template("modules/admin_login.html", agency=agency)


@bp.route("/backup.json")
@login_required
@admin_required
def backup_json():
    from flask import Response

    agency = _agency_or_redirect()
    if not agency:
        return redirect(url_for("agency.dashboard"))
    records = HrRecord.query.filter_by(agency_id=agency.id).all()
    payload = {
        "agency": agency.name,
        "company": agency.company_name,
        "exportedAt": datetime.utcnow().isoformat() + "Z",
        "records": [
            {"id": r.id, "kind": r.kind, "data": r.data, "created_at": r.created_at.isoformat()}
            for r in records
        ],
    }
    return Response(
        json.dumps(payload, indent=2),
        mimetype="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=Green-Mile-HR-{agency.slug}-backup.json"
        },
    )
