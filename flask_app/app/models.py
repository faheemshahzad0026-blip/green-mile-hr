from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class Agency(db.Model):
    __tablename__ = "agencies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    company_name = db.Column(db.String(200), nullable=False)
    company_email = db.Column(db.String(160))
    company_phone = db.Column(db.String(60))
    company_address = db.Column(db.Text)
    logo_path = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    users = db.relationship("User", back_populates="agency", lazy="dynamic")
    employees = db.relationship("Employee", back_populates="agency", lazy="dynamic")

    def __repr__(self):
        return f"<Agency {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    ROLE_SUPER_ADMIN = "super_admin"
    ROLE_AGENCY_ADMIN = "agency_admin"
    ROLE_STAFF = "staff"

    id = db.Column(db.Integer, primary_key=True)
    agency_id = db.Column(db.Integer, db.ForeignKey("agencies.id"), nullable=True, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(160))
    email = db.Column(db.String(160))
    role = db.Column(db.String(40), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    agency = db.relationship("Agency", back_populates="users")

    def get_id(self):
        return f"u:{self.id}"

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_super_admin(self) -> bool:
        return self.role == self.ROLE_SUPER_ADMIN

    @property
    def is_agency_admin(self) -> bool:
        return self.role == self.ROLE_AGENCY_ADMIN

    @property
    def is_staff(self) -> bool:
        return self.role == self.ROLE_STAFF

    @property
    def is_employee_account(self) -> bool:
        return False

    @property
    def display_name(self) -> str:
        """Login username first, then full name — never role titles."""
        username = (self.username or "").strip()
        if username:
            return username
        name = (self.full_name or "").strip()
        if name:
            return name
        email = (self.email or "").strip()
        if email and "@" in email:
            return email.split("@", 1)[0].strip() or "User"
        return "User"

    @property
    def initials(self) -> str:
        text = (self.username or self.display_name or "U").strip() or "U"
        parts = [p for p in text.replace(".", " ").replace("_", " ").split() if p]
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return (parts[0][:2] if parts else "U").upper()


class Employee(UserMixin, db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    agency_id = db.Column(db.Integer, db.ForeignKey("agencies.id"), nullable=False, index=True)
    employee_code = db.Column(db.String(40), nullable=False, index=True)
    full_name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(60))
    email = db.Column(db.String(160))
    designation = db.Column(db.String(120))
    department = db.Column(db.String(120))
    pin_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    agency = db.relationship("Agency", back_populates="employees")

    __table_args__ = (
        db.UniqueConstraint("agency_id", "employee_code", name="uq_agency_employee_code"),
    )

    def get_id(self):
        return f"e:{self.id}"

    def set_pin(self, pin: str):
        self.pin_hash = generate_password_hash(pin)

    def check_pin(self, pin: str) -> bool:
        return check_password_hash(self.pin_hash, pin)

    @property
    def is_super_admin(self) -> bool:
        return False

    @property
    def is_agency_admin(self) -> bool:
        return False

    @property
    def is_staff(self) -> bool:
        return False

    @property
    def is_employee_account(self) -> bool:
        return True

    @property
    def role(self) -> str:
        return "employee"

    @property
    def display_name(self) -> str:
        return self.full_name

    @property
    def username(self) -> str:
        return self.employee_code


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, nullable=True)
    actor_label = db.Column(db.String(120))
    agency_id = db.Column(db.Integer, nullable=True, index=True)
    action = db.Column(db.String(80), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class HrRecord(db.Model):
    """Agency-scoped HR records (attendance, leave, payroll, etc.)."""

    __tablename__ = "hr_records"

    id = db.Column(db.Integer, primary_key=True)
    agency_id = db.Column(db.Integer, db.ForeignKey("agencies.id"), nullable=False, index=True)
    kind = db.Column(db.String(60), nullable=False, index=True)
    data = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    agency = db.relationship("Agency")

    def get(self, key, default=""):
        return (self.data or {}).get(key, default)
