from datetime import timedelta
import re

from flask import current_app, jsonify, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import bp
from app.forms import AdminLoginForm, EmployeeLoginForm
from app.models import Agency, Employee, User

SESSION_SHORT = timedelta(hours=6)
SESSION_LONG = timedelta(days=30)
REMEMBER_USER_COOKIE = "gm_remember_user"
REMEMBER_EMP_COOKIE = "gm_remember_emp"


def _apply_session_duration(remember: bool):
    """Keep signed-in for 30 days when Remember me is on, else 6 hours."""
    session.permanent = True
    session["long_session"] = bool(remember)
    if remember:
        current_app.permanent_session_lifetime = SESSION_LONG
        current_app.config["REMEMBER_COOKIE_DURATION"] = SESSION_LONG
    else:
        current_app.permanent_session_lifetime = SESSION_SHORT
        current_app.config["REMEMBER_COOKIE_DURATION"] = SESSION_SHORT


def _set_remember_id_cookie(resp, cookie_name: str, value: str | None, remember: bool):
    """Store login ID only (never password/PIN) when Remember me is checked."""
    if remember and value:
        resp.set_cookie(
            cookie_name,
            value,
            max_age=int(SESSION_LONG.total_seconds()),
            httponly=True,
            samesite="Lax",
            secure=bool(request.is_secure),
        )
    else:
        resp.delete_cookie(cookie_name)


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Admin / staff / super-admin login — matches old /login page."""
    if current_user.is_authenticated:
        return _post_login_redirect(current_user)

    form = AdminLoginForm()
    if request.method == "GET" and not form.username.data:
        saved = request.cookies.get(REMEMBER_USER_COOKIE)
        if saved:
            form.username.data = saved
            form.remember_me.data = True

    error = None
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if not user or not user.check_password(form.password.data):
            error = "Invalid username or password."
        elif not user.is_active:
            error = "This account is disabled."
        elif user.agency_id:
            agency = Agency.query.get(user.agency_id)
            if not agency or not agency.is_active:
                error = "This agency is inactive. Contact Super Admin."
        if not error:
            remember = bool(form.remember_me.data)
            _apply_session_duration(remember)
            login_user(
                user,
                remember=remember,
                duration=SESSION_LONG if remember else SESSION_SHORT,
            )
            session.pop("view_agency_id", None)
            if user.agency_id:
                session["view_agency_id"] = user.agency_id
            resp = make_response(_post_login_redirect(user))
            _set_remember_id_cookie(
                resp, REMEMBER_USER_COOKIE, user.username if remember else None, remember
            )
            return resp

    return render_template("auth/login.html", form=form, error=error)


@bp.route("/employee-login", methods=["GET", "POST"])
def employee_login():
    """Employee web login (ID + PIN). No agency code required."""
    if current_user.is_authenticated:
        return _post_login_redirect(current_user)

    form = EmployeeLoginForm()
    if request.method == "GET" and not form.employee_code.data:
        saved = request.cookies.get(REMEMBER_EMP_COOKIE)
        if saved:
            form.employee_code.data = saved
            form.remember_me.data = True

    error = None
    if form.validate_on_submit():
        code = form.employee_code.data.strip()
        pin = form.pin.data.strip()
        matches = Employee.query.filter_by(employee_code=code, is_active=True).all()
        employee = None
        for cand in matches:
            if cand.check_pin(pin):
                agency = Agency.query.get(cand.agency_id)
                if agency and agency.is_active:
                    employee = cand
                    break
        if not employee:
            error = "Invalid employee ID or PIN."
        else:
            remember = bool(form.remember_me.data)
            _apply_session_duration(remember)
            login_user(
                employee,
                remember=remember,
                duration=SESSION_LONG if remember else SESSION_SHORT,
            )
            session["view_agency_id"] = employee.agency_id
            resp = make_response(redirect(url_for("employee.home")))
            _set_remember_id_cookie(
                resp,
                REMEMBER_EMP_COOKIE,
                employee.employee_code if remember else None,
                remember,
            )
            return resp

    return render_template("auth/employee_login.html", form=form, error=error)


@bp.route("/logout")
@login_required
def logout():
    was_employee = getattr(current_user, "is_employee_account", False)
    logout_user()
    session.pop("view_agency_id", None)
    session.pop("long_session", None)
    if was_employee:
        return redirect(url_for("auth.employee_login"))
    return redirect(url_for("auth.login"))


def _post_login_redirect(user):
    if getattr(user, "is_employee_account", False):
        return redirect(url_for("employee.home"))
    return redirect(url_for("agency.dashboard"))


@bp.route("/validate-field", methods=["POST"])
def validate_field():
    """AJAX field validation used by login + workspace forms."""
    data = request.get_json(silent=True) or request.form or {}
    field = (data.get("field") or data.get("name") or "").strip()
    value = (data.get("value") or "").strip()
    required = str(data.get("required") or "").lower() in {"1", "true", "yes"}
    field_type = (data.get("type") or "").strip().lower()

    if required and not value:
        return jsonify(ok=False, message="This field is required.")

    if not value:
        return jsonify(ok=True, message="")

    if field in {"email", "company_email"} or field_type == "email":
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
            return jsonify(ok=False, message="Enter a valid email, e.g. name@email.com.")

    if field in {"username", "admin_username"}:
        if len(value) < 3:
            return jsonify(ok=False, message="Username must be at least 3 characters.")
        if not re.match(r"^[a-zA-Z0-9._-]{3,40}$", value):
            return jsonify(ok=False, message="Use letters, numbers, . _ - only (3–40 chars).")
        q = User.query.filter_by(username=value)
        if current_user.is_authenticated and not getattr(current_user, "is_employee_account", False):
            q = q.filter(User.id != current_user.id)
        if q.first():
            return jsonify(ok=False, message="This username is already taken.")

    if field in {"password", "admin_password", "new_password"} and len(value) < 6:
        return jsonify(ok=False, message="Password must be at least 6 characters.")

    if field in {"confirm", "password_confirm"}:
        other = (data.get("other") or "").strip()
        if other and value != other:
            return jsonify(ok=False, message="Passwords do not match.")

    if field in {"pin"}:
        if not re.match(r"^\d{6}$", value):
            return jsonify(ok=False, message="PIN must be exactly 6 digits.")

    if field in {"employee_code"}:
        if len(value) < 2:
            return jsonify(ok=False, message="Enter a valid employee ID.")

    if field in {"phone", "company_phone"}:
        digits = re.sub(r"\D", "", value)
        if len(digits) < 7:
            return jsonify(ok=False, message="Enter a valid phone number.")

    if field_type == "number" or field in {"basic", "amount", "allowances", "deductions", "cost", "hours"}:
        try:
            float(value)
        except ValueError:
            return jsonify(ok=False, message="Enter a valid number.")

    if field in {"name", "full_name"} and len(value) < 2:
        return jsonify(ok=False, message="Enter a full name.")

    return jsonify(ok=True, message="")
