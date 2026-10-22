from datetime import timedelta
import re

from flask import current_app, jsonify, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import bp
from app.forms import UnifiedLoginForm
from app.models import Agency, Employee, User

SESSION_SHORT = timedelta(hours=6)
SESSION_LONG = timedelta(days=30)
REMEMBER_LOGIN_COOKIE = "gm_remember_login"


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


def _set_remember_id_cookie(resp, value: str | None, remember: bool):
    """Store login ID only (never password/PIN) when Remember me is checked."""
    if remember and value:
        resp.set_cookie(
            REMEMBER_LOGIN_COOKIE,
            value,
            max_age=int(SESSION_LONG.total_seconds()),
            httponly=True,
            samesite="Lax",
            secure=bool(request.is_secure),
        )
    else:
        resp.delete_cookie(REMEMBER_LOGIN_COOKIE)
        # Clear legacy cookies
        resp.delete_cookie("gm_remember_user")
        resp.delete_cookie("gm_remember_emp")


def _try_admin_login(login_id: str, secret: str):
    user = User.query.filter_by(username=login_id).first()
    if not user or not user.check_password(secret):
        return None, None
    if not user.is_active:
        return None, "This account is disabled."
    if user.agency_id:
        agency = Agency.query.get(user.agency_id)
        if not agency or not agency.is_active:
            return None, "This agency is inactive. Contact Super Admin."
    return user, None


def _try_employee_login(login_id: str, secret: str):
    candidates = Employee.query.filter_by(employee_code=login_id).all()
    employee = None
    disabled_match = False
    for cand in candidates:
        if not cand.check_pin(secret):
            continue
        agency = Agency.query.get(cand.agency_id)
        if not agency or not agency.is_active:
            continue
        if not cand.is_active:
            disabled_match = True
            continue
        employee = cand
        break
    if disabled_match and not employee:
        return None, "ID disabled. Please contact HR department."
    if not employee:
        return None, None
    return employee, None


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Single login for HR (username + password) and employees (ID + PIN)."""
    if current_user.is_authenticated:
        return _post_login_redirect(current_user)

    form = UnifiedLoginForm()
    if request.method == "GET" and not form.login_id.data:
        saved = (
            request.cookies.get(REMEMBER_LOGIN_COOKIE)
            or request.cookies.get("gm_remember_user")
            or request.cookies.get("gm_remember_emp")
        )
        if saved:
            form.login_id.data = saved
            form.remember_me.data = True

    error = None
    if form.validate_on_submit():
        login_id = form.login_id.data.strip()
        secret = form.secret.data.strip()
        account = None

        # Prefer HR/admin username match; otherwise try employee ID + PIN
        user, user_err = _try_admin_login(login_id, secret)
        if user_err:
            error = user_err
        elif user:
            account = user
        else:
            emp, emp_err = _try_employee_login(login_id, secret)
            if emp_err:
                error = emp_err
            elif emp:
                account = emp
            else:
                error = "Invalid user/ID or password/PIN."

        if account and not error:
            remember = bool(form.remember_me.data)
            _apply_session_duration(remember)
            login_user(
                account,
                remember=remember,
                duration=SESSION_LONG if remember else SESSION_SHORT,
            )
            session.pop("view_agency_id", None)
            if getattr(account, "agency_id", None):
                session["view_agency_id"] = account.agency_id
            remember_value = (
                account.employee_code
                if getattr(account, "is_employee_account", False)
                else account.username
            )
            resp = make_response(_post_login_redirect(account))
            _set_remember_id_cookie(resp, remember_value if remember else None, remember)
            return resp

    return render_template("auth/login.html", form=form, error=error)


@bp.route("/employee-login", methods=["GET", "POST"])
def employee_login():
    """Legacy URL — same unified login page."""
    return redirect(url_for("auth.login"), code=301)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("view_agency_id", None)
    session.pop("long_session", None)
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

    if field in {"username", "admin_username", "login_id"}:
        if len(value) < 2:
            return jsonify(ok=False, message="Enter a user name or employee ID.")
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

    if field in {"password", "admin_password", "new_password", "secret"} and len(value) < 4:
        return jsonify(ok=False, message="Enter your password or PIN.")

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
