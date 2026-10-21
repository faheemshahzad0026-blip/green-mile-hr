from flask import flash, redirect, render_template, request, session, url_for
from flask_login import login_required

from app.decorators import super_admin_required
from app.extensions import db
from app.forms import AgencyForm, AgencyUserForm
from app.models import Agency, Employee, User
from app.super_admin import bp
from app.utils import save_agency_logo, unique_agency_slug, write_audit


@bp.route("/agencies")
@login_required
@super_admin_required
def agencies():
    items = Agency.query.order_by(Agency.name.asc()).all()
    return render_template("super_admin/agencies.html", agencies=items)


@bp.route("/agencies/new", methods=["GET", "POST"])
@login_required
@super_admin_required
def agency_create():
    form = AgencyForm()
    if request.method == "GET":
        form.is_active.data = True
    if form.validate_on_submit():
        if not form.admin_username.data or not form.admin_password.data:
            flash("Agency admin username and password are required for new agencies.", "danger")
            return render_template("super_admin/agency_form.html", form=form, title="Create agency")
        if User.query.filter_by(username=form.admin_username.data.strip()).first():
            flash("That admin username is already taken.", "danger")
            return render_template("super_admin/agency_form.html", form=form, title="Create agency")

        agency = Agency(
            name=form.name.data.strip(),
            slug=unique_agency_slug(form.name.data),
            company_name=form.company_name.data.strip(),
            company_email=(form.company_email.data or "").strip() or None,
            company_phone=(form.company_phone.data or "").strip() or None,
            company_address=(form.company_address.data or "").strip() or None,
            is_active=bool(form.is_active.data),
        )
        db.session.add(agency)
        db.session.flush()

        try:
            logo_path = save_agency_logo(form.logo.data, agency.id)
            if logo_path:
                agency.logo_path = logo_path
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return render_template("super_admin/agency_form.html", form=form, title="Create agency")

        admin = User(
            agency_id=agency.id,
            username=form.admin_username.data.strip(),
            full_name=(form.admin_full_name.data or "").strip() or form.admin_username.data.strip(),
            role=User.ROLE_AGENCY_ADMIN,
            is_active=True,
        )
        admin.set_password(form.admin_password.data)
        db.session.add(admin)
        write_audit("agency_create", f"Created agency {agency.name}", agency_id=agency.id)
        db.session.commit()
        flash(f"Agency '{agency.name}' created.", "success")
        return redirect(url_for("super_admin.agencies"))
    return render_template("super_admin/agency_form.html", form=form, title="Create agency")


@bp.route("/agencies/<int:agency_id>/edit", methods=["GET", "POST"])
@login_required
@super_admin_required
def agency_edit(agency_id):
    agency = Agency.query.get_or_404(agency_id)
    form = AgencyForm(obj=agency)
    if request.method == "GET":
        form.is_active.data = agency.is_active
    if form.validate_on_submit():
        agency.name = form.name.data.strip()
        agency.company_name = form.company_name.data.strip()
        agency.company_email = (form.company_email.data or "").strip() or None
        agency.company_phone = (form.company_phone.data or "").strip() or None
        agency.company_address = (form.company_address.data or "").strip() or None
        agency.is_active = bool(form.is_active.data)
        try:
            logo_path = save_agency_logo(form.logo.data, agency.id)
            if logo_path:
                agency.logo_path = logo_path
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template(
                "super_admin/agency_form.html",
                form=form,
                title="Edit agency",
                agency=agency,
            )
        write_audit("agency_update", f"Updated agency {agency.name}", agency_id=agency.id)
        db.session.commit()
        flash("Agency updated.", "success")
        return redirect(url_for("super_admin.agencies"))
    return render_template(
        "super_admin/agency_form.html",
        form=form,
        title="Edit agency",
        agency=agency,
    )


@bp.route("/agencies/<int:agency_id>/toggle", methods=["POST"])
@login_required
@super_admin_required
def agency_toggle(agency_id):
    agency = Agency.query.get_or_404(agency_id)
    agency.is_active = not agency.is_active
    write_audit(
        "agency_toggle",
        f"Set {agency.name} active={agency.is_active}",
        agency_id=agency.id,
    )
    db.session.commit()
    flash(
        f"Agency '{agency.name}' is now {'active' if agency.is_active else 'inactive'}.",
        "success",
    )
    return redirect(url_for("super_admin.agencies"))


@bp.route("/agencies/<int:agency_id>/view")
@login_required
@super_admin_required
def agency_view(agency_id):
    agency = Agency.query.get_or_404(agency_id)
    session["view_agency_id"] = agency.id
    flash(f"Viewing as {agency.company_name}.", "info")
    return redirect(url_for("agency.dashboard"))


@bp.route("/users", methods=["GET", "POST"])
@login_required
@super_admin_required
def users():
    form = AgencyUserForm()
    form.agency_id.choices = [
        (a.id, f"{a.name} ({'active' if a.is_active else 'inactive'})")
        for a in Agency.query.order_by(Agency.name).all()
    ]
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data.strip()).first():
            flash("Username already exists.", "danger")
        else:
            user = User(
                agency_id=form.agency_id.data,
                username=form.username.data.strip(),
                full_name=(form.full_name.data or "").strip() or None,
                role=form.role.data,
                is_active=True,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            write_audit(
                "user_create",
                f"Created {user.role} {user.username}",
                agency_id=user.agency_id,
            )
            db.session.commit()
            flash(f"User '{user.username}' created.", "success")
            return redirect(url_for("super_admin.users"))

    users_list = (
        User.query.filter(User.role != User.ROLE_SUPER_ADMIN)
        .order_by(User.created_at.desc())
        .all()
    )
    return render_template("super_admin/users.html", form=form, users=users_list)


@bp.route("/overview")
@login_required
@super_admin_required
def overview():
    agencies = Agency.query.order_by(Agency.name).all()
    stats = []
    for agency in agencies:
        stats.append(
            {
                "agency": agency,
                "admins": User.query.filter_by(
                    agency_id=agency.id, role=User.ROLE_AGENCY_ADMIN
                ).count(),
                "staff": User.query.filter_by(agency_id=agency.id, role=User.ROLE_STAFF).count(),
                "employees": Employee.query.filter_by(agency_id=agency.id).count(),
            }
        )
    return render_template("super_admin/overview.html", stats=stats)
