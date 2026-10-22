from datetime import timedelta
from pathlib import Path

from flask import Flask, redirect, session, url_for
from flask_login import current_user

from app.extensions import csrf, db, login_manager, migrate
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["APK_FOLDER"]).mkdir(parents=True, exist_ok=True)
    (Path(app.root_path) / "static" / "uploads").mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    @app.before_request
    def _refresh_session_lifetime():
        # Remember me → 30 days · otherwise → 6 hours
        if session.get("long_session"):
            app.permanent_session_lifetime = timedelta(days=30)
        else:
            app.permanent_session_lifetime = timedelta(hours=6)

    from app.models import Employee, User

    @login_manager.user_loader
    def load_user(user_id: str):
        if not user_id or ":" not in user_id:
            return None
        kind, raw = user_id.split(":", 1)
        try:
            pk = int(raw)
        except ValueError:
            return None
        if kind == "u":
            return db.session.get(User, pk)
        if kind == "e":
            return db.session.get(Employee, pk)
        return None

    from app.agency import bp as agency_bp
    from app.auth import bp as auth_bp
    from app.employee import bp as employee_bp
    from app.modules import bp as modules_bp
    from app.super_admin import bp as super_admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(super_admin_bp)
    app.register_blueprint(agency_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(modules_bp)

    @app.context_processor
    def inject_globals():
        from datetime import datetime, timedelta, timezone

        from app.models import Agency
        from app.utils import get_active_agency, pending_notifications

        agency = None
        notify_items = []
        announcement_count = 0
        if current_user.is_authenticated:
            if getattr(current_user, "is_employee_account", False):
                # Employee always uses their agency branding (logo → favicon)
                if getattr(current_user, "agency_id", None):
                    agency = db.session.get(Agency, current_user.agency_id)
                try:
                    from app.employee.services import employee_notifications, published_announcements

                    notify_items = employee_notifications(current_user)
                    announcement_count = len(published_announcements(current_user))
                except Exception:
                    notify_items = []
                    announcement_count = 0
            else:
                # Agency admin / staff: active workspace agency logo as favicon
                agency = get_active_agency()
                if agency is None and getattr(current_user, "agency_id", None):
                    agency = db.session.get(Agency, current_user.agency_id)
                if agency:
                    notify_items = pending_notifications(agency.id)
        from app.period import get_period_state

        now_label = (datetime.now(timezone.utc) + timedelta(hours=4)).strftime("%d/%m/%Y")
        agency_favicon_url = None
        if agency and getattr(agency, "logo_path", None):
            from flask import url_for

            try:
                agency_favicon_url = url_for("static", filename=agency.logo_path)
                if getattr(agency, "updated_at", None):
                    agency_favicon_url += f"?v={int(agency.updated_at.timestamp())}"
            except Exception:
                agency_favicon_url = None
        return {
            "brand_agency": agency,
            "agency_favicon_url": agency_favicon_url,
            "app_name": "Green Mile HR",
            "now_label": now_label,
            "notify_items": notify_items,
            "notify_count": len(notify_items),
            "announcement_count": announcement_count,
            "ui_period": get_period_state(),
        }

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            if getattr(current_user, "is_employee_account", False):
                return redirect(url_for("employee.home"))
            return redirect(url_for("agency.dashboard"))
        return redirect(url_for("auth.login"))

    @app.cli.command("init-db")
    def init_db_command():
        """Create tables and seed super admin."""
        db.create_all()
        _ensure_schema()
        from app.utils import ensure_super_admin

        ensure_super_admin()
        print("Database ready. Super admin seeded if missing.")

    def _ensure_schema():
        try:
            with db.engine.connect() as conn:
                cols = {
                    row[0]
                    for row in conn.exec_driver_sql("SHOW COLUMNS FROM users").fetchall()
                }
                if "email" not in cols:
                    conn.exec_driver_sql(
                        "ALTER TABLE users ADD COLUMN email VARCHAR(160) NULL"
                    )
                    conn.commit()
        except Exception:
            pass

    with app.app_context():
        db.create_all()
        _ensure_schema()
        from app.utils import ensure_super_admin

        ensure_super_admin()

    return app
