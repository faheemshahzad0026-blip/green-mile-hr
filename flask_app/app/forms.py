from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, Regexp


class AdminLoginForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=3, max=40)],
        render_kw={"placeholder": "e.g. ahmed.khan"},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(max=128)],
        render_kw={"placeholder": "e.g. ••••••••"},
    )
    remember_me = BooleanField("Remember me", default=False)
    submit = SubmitField("Sign in")


class EmployeeLoginForm(FlaskForm):
    employee_code = StringField(
        "Employee ID",
        validators=[DataRequired(), Length(max=40)],
        render_kw={"placeholder": "e.g. EMP-1042"},
    )
    pin = PasswordField(
        "6-digit PIN",
        validators=[DataRequired(), Regexp(r"^\d{6}$", message="PIN must be 6 digits")],
        render_kw={"placeholder": "e.g. 123456"},
    )
    remember_me = BooleanField("Remember me", default=False)
    submit = SubmitField("Sign in")


class AgencyForm(FlaskForm):
    name = StringField(
        "Agency name",
        validators=[DataRequired(), Length(max=160)],
        render_kw={"placeholder": "e.g. Green Mile Dubai"},
    )
    company_name = StringField(
        "Company name",
        validators=[DataRequired(), Length(max=200)],
        render_kw={"placeholder": "e.g. Green Mile Recycling LLC"},
    )
    company_email = StringField(
        "Company email",
        validators=[Optional(), Email(), Length(max=160)],
        render_kw={"placeholder": "e.g. hr@company.ae"},
    )
    company_phone = StringField(
        "Company phone",
        validators=[Optional(), Length(max=60)],
        render_kw={"placeholder": "e.g. +971 4 123 4567"},
    )
    company_address = TextAreaField(
        "Company address",
        validators=[Optional(), Length(max=1000)],
        render_kw={"placeholder": "e.g. Dubai Industrial City"},
    )
    logo = FileField("Logo", validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "webp", "gif"])])
    admin_username = StringField(
        "Agency admin username",
        validators=[Optional(), Length(max=80)],
        render_kw={"placeholder": "e.g. agency.admin"},
    )
    admin_password = PasswordField(
        "Agency admin password",
        validators=[Optional(), Length(min=6, max=128)],
        render_kw={"placeholder": "e.g. ••••••••"},
    )
    admin_full_name = StringField(
        "Agency admin full name",
        validators=[Optional(), Length(max=160)],
        render_kw={"placeholder": "e.g. Sara Ali"},
    )
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save agency")


class AgencyUserForm(FlaskForm):
    agency_id = SelectField("Agency", coerce=int, validators=[DataRequired()])
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(max=80)],
        render_kw={"placeholder": "e.g. ahmed.khan"},
    )
    full_name = StringField(
        "Full name",
        validators=[Optional(), Length(max=160)],
        render_kw={"placeholder": "e.g. Ahmed Khan"},
    )
    role = SelectField(
        "Role",
        choices=[("agency_admin", "Agency Admin"), ("staff", "Staff")],
        validators=[DataRequired()],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=6, max=128)],
        render_kw={"placeholder": "e.g. ••••••••"},
    )
    password_confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password")],
        render_kw={"placeholder": "e.g. ••••••••"},
    )
    submit = SubmitField("Create user")


class StaffForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(max=80)],
        render_kw={"placeholder": "e.g. ahmed.khan"},
    )
    full_name = StringField(
        "Full name",
        validators=[Optional(), Length(max=160)],
        render_kw={"placeholder": "e.g. Ahmed Khan"},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=6, max=128)],
        render_kw={"placeholder": "e.g. ••••••••"},
    )
    password_confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password")],
        render_kw={"placeholder": "e.g. ••••••••"},
    )
    submit = SubmitField("Create staff")


class EmployeeForm(FlaskForm):
    employee_code = StringField(
        "Employee ID",
        validators=[Optional(), Length(max=40)],
        render_kw={"placeholder": "e.g. EMP-1042"},
    )
    full_name = StringField(
        "Full name",
        validators=[DataRequired(), Length(max=160)],
        render_kw={"placeholder": "e.g. Ahmed Khan"},
    )
    phone = StringField(
        "Phone",
        validators=[Optional(), Length(max=60)],
        render_kw={"placeholder": "e.g. +971 50 123 4567"},
    )
    email = StringField(
        "Email",
        validators=[Optional(), Email(), Length(max=160)],
        render_kw={"placeholder": "e.g. ahmed.khan@email.com"},
    )
    designation = StringField(
        "Designation",
        validators=[Optional(), Length(max=120)],
        render_kw={"placeholder": "e.g. Driver"},
    )
    department = StringField(
        "Department",
        validators=[Optional(), Length(max=120)],
        render_kw={"placeholder": "e.g. Operations"},
    )
    pin = PasswordField(
        "6-digit PIN",
        validators=[DataRequired(), Regexp(r"^\d{6}$", message="PIN must be 6 digits")],
        render_kw={"placeholder": "e.g. 123456"},
    )
    submit = SubmitField("Register employee")
