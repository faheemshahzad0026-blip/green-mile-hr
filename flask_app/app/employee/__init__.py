from flask import Blueprint

bp = Blueprint("employee", __name__, url_prefix="/employee")

from app.employee import routes  # noqa: E402,F401
