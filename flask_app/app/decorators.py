from functools import wraps

from flask import abort, flash, redirect, url_for
from flask_login import current_user


def login_roles(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if getattr(current_user, "is_employee_account", False):
                flash("Admin access required.", "warning")
                return redirect(url_for("employee.home"))
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def admin_required(view):
    return login_roles("super_admin", "agency_admin", "staff")(view)


def super_admin_required(view):
    return login_roles("super_admin")(view)


def agency_manager_required(view):
    """Agency admin or staff (not super admin unless viewing via switcher)."""
    return login_roles("super_admin", "agency_admin", "staff")(view)


def employee_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not getattr(current_user, "is_employee_account", False):
            flash("Employee access only.", "warning")
            return redirect(url_for("agency.dashboard"))
        return view(*args, **kwargs)

    return wrapped
