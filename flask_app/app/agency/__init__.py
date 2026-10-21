from flask import Blueprint

bp = Blueprint("agency", __name__, url_prefix="/admin")

from app.agency import routes  # noqa: E402,F401
