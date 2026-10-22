import json
import re
from datetime import datetime

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.decorators import admin_required
from app.extensions import db
from app.hr_modules import EMPLOYEE_SCOPED_KINDS, MODULES, TOOL_PAGES
from app.models import Employee, HrRecord, User
from app.modules import bp
from app.utils import (
    get_active_agency,
    next_employee_code,
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


def _display(record, key, employees_map):
    val = record.get(key)
    if key == "employee":
        emp = employees_map.get(str(val)) or employees_map.get(val)
        if emp:
            return f"{emp.full_name} · {emp.employee_code}"
        # also try hr employee records
        return str(val or "—")
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
    """View-only attendance: all employee punches + correction requests (HR cannot add)."""
    agency = _agency_or_redirect()
    if not agency:
        return redirect(
            url_for("super_admin.overview")
            if current_user.is_super_admin
            else url_for("agency.dashboard")
        )

    if request.method == "POST":
        flash("Attendance is view-only. Records come from employee punches.", "warning")
        tab = request.form.get("tab") or "daily"
        return redirect(url_for("modules.attendance_hub", tab=tab))

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
        if action == "upload_document":
            try:
                path = save_employee_document_file(
                    request.files.get("file"), agency.id, emp_key
                )
                doc = {
                    "employee": str(auth_emp.id if auth_emp else record.id),
                    "type": (request.form.get("type") or "Contract").strip(),
                    "number": (request.form.get("number") or "").strip(),
                    "issued": (request.form.get("issued") or "").strip(),
                    "expiry": (request.form.get("expiry") or "").strip(),
                    "status": (request.form.get("status") or "Valid").strip(),
                    "filePath": path or "",
                    "notes": (request.form.get("notes") or "").strip(),
                }
                if not doc["number"] and not path:
                    raise ValueError("Enter a document number or upload a file.")
                db.session.add(HrRecord(agency_id=agency.id, kind="documents", data=doc))
                write_audit("doc_upload", f"employee {emp_key}", agency_id=agency.id)
                db.session.commit()
                flash("Document saved for this employee.", "success")
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
            return redirect(url_for("modules.employee_profile", record_id=record.id, _anchor="documents"))

        if action == "add_leave":
            leave = {
                "employee": str(auth_emp.id if auth_emp else record.id),
                "type": (request.form.get("type") or "Annual").strip(),
                "from": (request.form.get("from") or "").strip(),
                "to": (request.form.get("to") or "").strip(),
                "status": (request.form.get("status") or "Pending").strip(),
                "reason": (request.form.get("reason") or "").strip(),
            }
            if not leave["from"] or not leave["to"]:
                flash("Leave start and end dates are required.", "danger")
            else:
                db.session.add(HrRecord(agency_id=agency.id, kind="leave", data=leave))
                write_audit("leave_create", f"employee {emp_key}", agency_id=agency.id)
                db.session.commit()
                flash("Leave request saved.", "success")
            return redirect(url_for("modules.employee_profile", record_id=record.id, _anchor="leave"))

        if action in {"reset_pin", "toggle_app", "set_pin"}:
            if not auth_emp:
                flash("Create/save the employee first so an app login exists.", "danger")
                return redirect(url_for("modules.employee_profile", record_id=record.id))
            if action == "toggle_app":
                auth_emp.is_active = not auth_emp.is_active
                write_audit(
                    "app_access_toggle",
                    f"{auth_emp.employee_code} active={auth_emp.is_active}",
                    agency_id=agency.id,
                )
                db.session.commit()
                flash(
                    "App access allowed." if auth_emp.is_active else "App access blocked.",
                    "success",
                )
            elif action == "reset_pin":
                import secrets

                new_pin = f"{secrets.randbelow(1000000):06d}"
                auth_emp.set_pin(new_pin)
                session[f"reveal_pin_{record.id}"] = new_pin
                write_audit("app_pin_reset", auth_emp.employee_code, agency_id=agency.id)
                db.session.commit()
                flash(f"New app PIN: {new_pin} (copy it now — it won’t be shown again).", "success")
            elif action == "set_pin":
                new_pin = (request.form.get("pin") or "").strip()
                if not re.fullmatch(r"\d{6}", new_pin):
                    flash("PIN must be exactly 6 digits.", "danger")
                else:
                    auth_emp.set_pin(new_pin)
                    session[f"reveal_pin_{record.id}"] = new_pin
                    write_audit("app_pin_set", auth_emp.employee_code, agency_id=agency.id)
                    db.session.commit()
                    flash(f"App PIN updated to {new_pin}.", "success")
            return redirect(url_for("modules.employee_profile", record_id=record.id, _anchor="app-access"))

    def related(kind):
        rows = HrRecord.query.filter_by(agency_id=agency.id, kind=kind).order_by(HrRecord.id.desc()).all()
        out = []
        for r in rows:
            ref = str((r.data or {}).get("employee") or "")
            if ref in emp_ids:
                out.append(r)
        return out

    leave_rows = related("leave")
    help_rows = related("helpDesk")
    docs = related("documents")
    approved_leave_days = 0
    for r in leave_rows:
        if (r.data or {}).get("status") != "Approved":
            continue
        try:
            frm = datetime.strptime((r.data or {}).get("from") or "", "%Y-%m-%d")
            to = datetime.strptime((r.data or {}).get("to") or "", "%Y-%m-%d")
            approved_leave_days += max((to - frm).days + 1, 0)
        except Exception:
            pass
    annual = 30
    settings = (
        HrRecord.query.filter_by(agency_id=agency.id, kind="settings")
        .order_by(HrRecord.id.desc())
        .first()
    )
    if settings and (settings.data or {}).get("annualLeave"):
        try:
            annual = int(settings.data.get("annualLeave"))
        except Exception:
            pass

    open_queries = sum(
        1
        for r in help_rows
        if (r.data or {}).get("status") in {"Pending", "In progress"}
    )

    reveal_pin = session.pop(f"reveal_pin_{record.id}", None)

    return render_template(
        "modules/employee_profile.html",
        agency=agency,
        record=record,
        data=data,
        auth_emp=auth_emp,
        documents=docs,
        leave_rows=leave_rows,
        help_rows=help_rows,
        leave_balance=max(annual - approved_leave_days, 0),
        annual_leave=annual,
        used_leave=approved_leave_days,
        open_queries=open_queries,
        reveal_pin=reveal_pin,
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
        "leave",
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
        if kind in {"employeeFile", "leave", "mobileAccess", "staff"}:
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
            flash("Record deleted.", "success")
            return _redirect_after()

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
                flash(
                    f"Employee saved. ID {data.get('code')} · App PIN {generated_pin} (copy now — shown once).",
                    "success",
                )
                return redirect(url_for("modules.module_list", kind="employees", app=rec.id))
            if kind == "announcements" and (data.get("status") or "") == "Published":
                audience = data.get("audience") or "All employees"
                flash(
                    f"Announcement published for {audience}. Employees will see it on their portal and in the app notifications.",
                    "success",
                )
            elif kind == "shifts":
                flash("Shift assigned. The employee can see it under Shifts & schedules.", "success")
            else:
                flash("Saved successfully.", "success")
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

    rows = []
    reveal_pins = {}
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
        else:
            flash(message, "success")
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
        flash("Account settings updated.", "success")
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
