import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'green_mile_hr.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
    WTF_CSRF_ENABLED = True
    # Docs stay small; APK uploads need headroom (override with MAX_UPLOAD_MB)
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "80")) * 1024 * 1024
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        str(BASE_DIR / "app" / "static" / "uploads"),
    )
    APK_FOLDER = str(BASE_DIR / "app" / "static" / "apk")
    SUPER_ADMIN_USERNAME = os.getenv("SUPER_ADMIN_USERNAME", "superadmin")
    SUPER_ADMIN_PASSWORD = os.getenv("SUPER_ADMIN_PASSWORD", "Admin@12345")
    # Default session: 6 hours · Remember me: 30 days (see auth login)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=6)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_REFRESH_EACH_REQUEST = True
