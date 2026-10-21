from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.agency import bp
from app.dashboard_stats import build_dashboard
from app.decorators import admin_required
from app.period import get_period_state
from app.period import set_period as save_period
from app.utils import get_active_agency


def _require_agency_context():
    agency = get_active_agency()
    if agency:
        return agency
    if current_user.is_super_admin:
        flash("Select an agency first (Agencies → View).", "warning")
        return None
    flash("No agency assigned to your account.", "danger")
    return None


def _safe_next(default_endpoint="agency.dashboard"):
    nxt = (request.values.get("next") or "").strip()
    if nxt.startswith("/") and not nxt.startswith("//"):
        return nxt
    return url_for(default_endpoint)


@bp.route("/")
@bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    agency = get_active_agency()
    if current_user.is_super_admin and not agency:
        return redirect(url_for("super_admin.overview"))

    dash = None
    if agency:
        dash = build_dashboard(agency.id, get_period_state())

    return render_template(
        "agency/dashboard.html",
        agency=agency,
        dash=dash,
    )


@bp.route("/period", methods=["GET", "POST"])
@login_required
@admin_required
def set_period_route():
    if request.method == "POST":
        save_period(
            request.form.get("period") or "custom",
            request.form.get("from"),
            request.form.get("to"),
        )
    else:
        save_period(request.args.get("period") or "today")
    return redirect(_safe_next())


@bp.route("/staff", methods=["GET", "POST"])
@login_required
@admin_required
def staff_list():
    flash("Staff users are not used. Manage people from Employees.", "info")
    return redirect(url_for("modules.module_list", kind="employees"))


@bp.route("/employees", methods=["GET", "POST"])
@login_required
@admin_required
def employees():
    return redirect(url_for("modules.module_list", kind="employees"))


@bp.route("/employees/<int:employee_id>/toggle", methods=["POST"])
@login_required
@admin_required
def employee_toggle(employee_id):
    return redirect(url_for("modules.module_list", kind="employees"))
