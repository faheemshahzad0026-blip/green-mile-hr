"""HR module definitions ported from lib/hr.ts (Next.js app)."""

from __future__ import annotations

# Example hints shown in inputs as "e.g. …"
PLACEHOLDER_EXAMPLES = {
    "name": "Ahmed Khan",
    "department": "Operations",
    "designation": "Driver",
    "email": "ahmed.khan@email.com",
    "phone": "+971 50 123 4567",
    "address": "Al Quoz, Dubai",
    "visaType": "Employment visa — MOHRE",
    "manager": "Sara Ali",
    "labourId": "784-1990-1234567-1",
    "deviceUser": "EMP-1042",
    "remarks": "Night shift preferred",
    "notes": "Additional details…",
    "reason": "Family emergency",
    "reviewNote": "Approved after verification",
    "timeIn": "08:00",
    "timeOut": "17:00",
    "breakMinutes": "60",
    "basic": "3500",
    "allowances": "1500",
    "additions": "200",
    "otherDeductions": "50",
    "deductions": "100",
    "reference": "TRX-2026-001",
    "amount": "500",
    "hours": "4",
    "monthlyInstallment": "250",
    "number": "C12345678",
    "oldNumber": "C12345678",
    "newNumber": "C87654321",
    "reminderDays": "30",
    "cost": "350",
    "recipient": "Bank / Embassy name",
    "purpose": "Bank account opening",
    "body": "To whom it may concern…",
    "signatory": "Fatima Hassan",
    "signatoryTitle": "HR Manager",
    "title": "Office closed on Friday",
    "message": "Please review my attendance…",
    "subject": "Leave balance enquiry",
    "reply": "Your request is under review",
    "clearanceNote": "Laptop and ID card returned",
    "unpaidSalary": "3500",
    "leaveEncashment": "1200",
    "gratuity": "8000",
    "otherPay": "0",
    "deductionsSettle": "200",
    "code": "EMP-1042",
    "username": "ahmed.khan",
    "full_name": "Ahmed Khan",
    "password": "••••••••",
    "confirm": "••••••••",
    "pin": "123456",
    "employee_code": "EMP-1042",
    "agency_slug": "green-mile",
    "company_name": "Green Mile Recycling LLC",
    "company_email": "hr@company.ae",
    "company_phone": "+971 4 123 4567",
    "company_address": "Dubai Industrial City",
    "admin_username": "agency.admin",
    "admin_full_name": "Agency Admin",
    "admin_password": "••••••••",
    "password_confirm": "••••••••",
}


def _example_placeholder(key, label, type_="text", options=None, placeholder=None):
    if placeholder:
        return placeholder
    if type_ in ("select", "employee"):
        sample = (options or [None])[0]
        return f"e.g. {sample}" if sample else f"e.g. choose {label.lower()}"
    if type_ == "date":
        return "e.g. 15/03/2024"
    if type_ == "time":
        return PLACEHOLDER_EXAMPLES.get(key) and f"e.g. {PLACEHOLDER_EXAMPLES[key]}" or "e.g. 08:00"
    if type_ == "month":
        return "e.g. 2026-03"
    if type_ == "number":
        sample = PLACEHOLDER_EXAMPLES.get(key, "100")
        return f"e.g. {sample}"
    if type_ == "email":
        return f"e.g. {PLACEHOLDER_EXAMPLES.get(key, 'name@email.com')}"
    sample = PLACEHOLDER_EXAMPLES.get(key)
    if sample:
        return f"e.g. {sample}"
    return f"e.g. {label.lower()}"


def f(key, label, type_="text", required=False, options=None, applies_to=None, placeholder=None):
    field = {"key": key, "label": label, "type": type_, "required": required}
    if options:
        field["options"] = options
    if applies_to:
        field["appliesTo"] = applies_to
    field["placeholder"] = _example_placeholder(key, label, type_, options, placeholder)
    return field


employee = f("employee", "Employee", "employee", True, placeholder="e.g. Ahmed Khan · EMP-1042")
date = f("date", "Date", "date", True, placeholder="e.g. 15/03/2024")


def status(options):
    return f("status", "Status", "select", True, options)


MODULES = {
    "employees": {
        "title": "Employees",
        "description": "Active = working with you · Inactive = no longer with you. App login is controlled separately with the lock.",
        "columns": ["code", "name", "department", "designation", "joining", "status"],
        "fields": [
            f("name", "Full name", "text", True),
            f("department", "Department", "text", True),
            f("designation", "Designation / position", "text", True),
            f("nationality", "Nationality", "select", True, ["Pakistan", "India", "Bangladesh", "Nepal", "Philippines", "United Arab Emirates", "Syria", "Sudan", "Sri Lanka", "Other"]),
            f("gender", "Gender", "select", True, ["Male", "Female"]),
            f("marital", "Marital status", "select", False, ["Single", "Married"]),
            f("dob", "Date of birth", "date"),
            f("email", "Email", "email"),
            f("phone", "Mobile number"),
            f("address", "Address"),
            f("visaType", "Visa type / issuing authority"),
            f("contractStart", "Contract start", "date"),
            f("contractEnd", "Contract end", "date"),
            f("joining", "Joining date", "date", True),
            f("location", "Work location", "select", True, ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah", "Umm Al Quwain"]),
            f("contract", "Contract type", "select", True, ["Full-time fixed term", "Part-time", "Temporary", "Flexible"]),
            f("manager", "Reporting manager"),
            f("labourId", "Labour / person ID"),
            f("deviceUser", "Attendance device user ID"),
            f("remarks", "Remarks", "textarea"),
            # Employment status (not app login). Active = still working with you.
            status(["Active", "Inactive"]),
        ],
    },
    "attendance": {
        "title": "Attendance",
        "description": "Daily attendance, manual corrections and device imports.",
        "columns": ["employee", "date", "timeIn", "timeOut", "method", "status"],
        "fields": [
            employee, date,
            f("timeIn", "Time in (Dubai)", "time"),
            f("timeOut", "Time out (Dubai)", "time"),
            f("timeOutDate", "Check-out date", "date"),
            f("method", "Attendance method", "select", True, ["Manual", "Face device", "Fingerprint device", "Card device", "Mobile (GPS)"]),
            status(["Present", "Absent", "Late", "On leave", "Rest day"]),
            f("notes", "Notes"),
        ],
    },
    "corrections": {
        "title": "Attendance corrections",
        "description": "Review employee requests. Approval updates attendance.",
        "columns": ["employee", "date", "timeIn", "timeOut", "reason", "status"],
        "fields": [
            employee, date,
            f("timeIn", "Requested check-in (Dubai)", "time", True),
            f("timeOut", "Requested check-out (Dubai, optional)", "time"),
            f("reason", "Employee reason", "text", True),
            status(["Pending", "Approved", "Rejected"]),
            f("reviewNote", "HR review note"),
        ],
    },
    "shifts": {
        "title": "Shifts & schedules",
        "description": "Select an employee and assign their working shift, hours and weekly rest day. Employees see this on their portal and app.",
        "columns": ["name", "employee", "start", "end", "restDay"],
        "fields": [
            f("name", "Shift name", "text", True),
            employee,
            f("start", "Shift start", "time", True),
            f("end", "Shift end", "time", True),
            f("breakMinutes", "Break (minutes)", "number"),
            f("restDay", "Weekly rest day", "select", True, ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]),
            f("effective", "Effective from", "date", True),
        ],
        "add_label": "+ Assign shift",
    },
    "leave": {
        "title": "Leave requests",
        "description": "Review requests, dates and approval decisions.",
        "columns": ["employee", "type", "from", "to", "status"],
        "fields": [
            employee,
            f("type", "Leave type", "select", True, ["Annual", "Sick", "Casual", "Maternity", "Parental", "Bereavement", "Study", "Unpaid", "Other"]),
            f("from", "Start date", "date", True),
            f("to", "End date", "date", True),
            status(["Pending", "Approved", "Rejected"]),
            f("reason", "Reason"),
        ],
    },
    "payroll": {
        "title": "Payroll",
        "description": "Monthly salary drafts, adjustments and payment tracking in AED.",
        "columns": ["employee", "month", "basic", "allowances", "additions", "deductions", "net", "status"],
        "fields": [
            employee,
            f("month", "Payroll month", "month", True),
            f("basic", "Basic salary (AED)", "number", True),
            f("allowances", "Allowances (AED)", "number"),
            f("additions", "Total additions including overtime (AED)", "number"),
            f("otherDeductions", "Other deductions (AED)", "number"),
            f("deductions", "Total deductions (AED)", "number"),
            status(["Draft", "Approved", "Paid"]),
            f("paidDate", "Payment date", "date"),
            f("reference", "Payment reference"),
            f("notes", "Notes"),
        ],
    },
    "adjustments": {
        "title": "Loans & adjustments",
        "description": "Record loans, advances, overtime and salary deductions.",
        "columns": ["employee", "date", "type", "amount", "status"],
        "fields": [
            employee, date,
            f("type", "Adjustment type", "select", True, ["Loan", "Advance", "Deduction", "Overtime", "Bonus"]),
            f("amount", "Amount (AED)", "number", True),
            f("hours", "Overtime hours", "number"),
            f("monthlyInstallment", "Monthly recovery installment (AED)", "number"),
            f("recoveryStart", "First recovery month", "month"),
            status(["Pending", "Approved", "Settled"]),
            f("notes", "Notes"),
        ],
    },
    "documents": {
        "title": "Documents & expiry",
        "description": "Separate document records, complete details and live expiry reminders.",
        "columns": ["employee", "type", "number", "issued", "expiry", "status"],
        "fields": [
            employee,
            f("type", "Document type", "select", True, ["Passport", "Visa", "Emirates ID", "Labour card", "Work permit", "Insurance", "Driving licence", "Contract"]),
            f("number", "Document number", "text", True),
            f("issued", "Issue date", "date"),
            f("expiry", "Expiry date", "date", True),
            status(["Valid", "Renewal pending", "Expired"]),
            f("reminderDays", "Reminder before expiry (days)", "number"),
            f("notes", "Notes"),
        ],
    },
    "documentRenewals": {
        "title": "Document Renewal Tracker",
        "description": "Track renewal applications and preserve old document history.",
        "columns": ["employee", "type", "oldExpiry", "applicationDate", "status", "newExpiry"],
        "fields": [
            employee,
            f("type", "Document type"),
            f("oldNumber", "Old document number"),
            f("oldExpiry", "Old expiry", "date"),
            f("applicationDate", "Application date", "date"),
            f("reference", "Application reference"),
            f("cost", "Cost (AED)", "number"),
            status(["Pending", "In progress", "Renewed"]),
            f("newNumber", "New document number"),
            f("newIssued", "New issue date", "date"),
            f("newExpiry", "New expiry date", "date"),
            f("notes", "Notes", "textarea"),
        ],
    },
    "letters": {
        "title": "Letters & certificates",
        "description": "Generate and save employee letters with company branding.",
        "columns": ["employee", "type", "date", "recipient", "purpose"],
        "fields": [
            employee,
            f("type", "Letter type", "select", True, ["Salary certificate", "Employment certificate", "NOC", "Experience certificate"]),
            date,
            f("recipient", "Addressed to", "text"),
            f("purpose", "Purpose", "text"),
            f("body", "Letter text", "textarea"),
            f("signatory", "Signatory name", "text"),
            f("signatoryTitle", "Signatory designation", "text"),
        ],
    },
    "certificateRequests": {
        "title": "Certificate requests",
        "description": "Review employee requests and issue their certificates.",
        "columns": ["employee", "type", "date", "recipient", "purpose", "status"],
        "fields": [
            employee,
            f("type", "Certificate type", "select", True, ["Salary certificate", "Employment certificate", "NOC"]),
            date,
            f("recipient", "Addressed to", "text", True),
            f("purpose", "Employee purpose", "text", True),
            status(["Pending", "Rejected", "Issued"]),
            f("reviewNote", "HR review note", "textarea"),
        ],
    },
    "announcements": {
        "title": "HR announcements",
        "description": "Send a notice to all employees (or one department). Published messages appear as notifications on the employee portal and in the app.",
        "columns": ["title", "date", "expiry", "audience", "status"],
        "fields": [
            f("title", "Notice title", "text", True),
            f("body", "Message", "textarea", True),
            date,
            f("expiry", "Expiry date (optional)", "date"),
            f("audience", "Audience", "select", True, ["All employees", "Department"]),
            f("department", "Selected department (only if audience is Department)"),
            status(["Draft", "Published"]),
        ],
        "add_label": "+ Send announcement",
    },
    "helpDesk": {
        "title": "Employee HR help desk",
        "description": "Review employee complaints and requests. Reply and track resolution.",
        "columns": ["employee", "date", "category", "subject", "status"],
        "fields": [
            employee, date,
            f("category", "Category", "select", True, ["Salary / payroll", "Attendance", "Leave", "Documents", "Accommodation / transport", "Workplace concern", "Other"]),
            f("subject", "Subject", "text", True),
            f("message", "Employee message", "textarea", True),
            status(["Pending", "In progress", "Resolved"]),
            f("reply", "HR reply", "textarea"),
        ],
    },
    "resignations": {
        "title": "Resignations & clearance",
        "description": "Review resignation requests and complete clearance.",
        "columns": ["employee", "date", "lastDay", "status", "handover", "clearance"],
        "fields": [
            employee, date,
            f("lastDay", "Proposed last working date", "date", True),
            f("reason", "Employee reason", "textarea", True),
            status(["Pending", "Approved", "Rejected"]),
            f("approvedLastDay", "Approved last working date", "date"),
            f("handover", "Handover", "select", True, ["Pending", "Completed"]),
            f("clearance", "Clearance", "select", True, ["Pending", "Cleared"]),
            f("clearanceNote", "Clearance note", "textarea"),
        ],
    },
    "finalSettlements": {
        "title": "Final Settlement (F&F)",
        "description": "Review final entitlements and record settlement payment.",
        "columns": ["employee", "lastDay", "unpaidSalary", "leaveAmount", "gratuity", "net", "status"],
        "fields": [
            employee,
            f("lastDay", "Last working date", "date"),
            f("unpaidSalary", "Unpaid salary (AED)", "number"),
            f("leaveAmount", "Leave encashment (AED)", "number"),
            f("gratuity", "Gratuity (AED)", "number"),
            f("loanRecovery", "Loan recovery (AED)", "number"),
            f("net", "Final payable (AED)", "number"),
            status(["Draft", "Approved", "Paid"]),
        ],
    },
    "departments": {
        "title": "Departments",
        "description": "Organise teams and their managers.",
        "columns": ["name", "manager", "location"],
        "fields": [
            f("name", "Department name", "text", True),
            f("manager", "Department manager"),
            f("location", "Location"),
            f("notes", "Notes"),
        ],
    },
    "assets": {
        "title": "Company assets",
        "description": "Follow equipment assignments and returns.",
        "columns": ["name", "serial", "employee", "date", "status"],
        "fields": [
            f("name", "Asset name", "text", True),
            f("serial", "Serial / asset tag", "text", True),
            employee, date,
            status(["Assigned", "Returned", "Damaged", "Lost"]),
            f("notes", "Notes"),
        ],
    },
    "recruitment": {
        "title": "Recruitment",
        "description": "Keep candidates and hiring decisions organised.",
        "columns": ["name", "position", "phone", "date", "status"],
        "fields": [
            f("name", "Candidate name", "text", True),
            f("position", "Position", "text", True),
            f("phone", "Phone"),
            f("email", "Email", "email"),
            date,
            status(["Applied", "Interview", "Offer", "Hired", "Rejected"]),
            f("notes", "Notes"),
        ],
    },
    "performance": {
        "title": "Performance",
        "description": "Employee reviews and follow-up actions.",
        "columns": ["employee", "date", "rating", "reviewer"],
        "fields": [
            employee, date,
            f("rating", "Rating", "select", True, ["1 — Needs improvement", "2 — Developing", "3 — Meets expectations", "4 — Exceeds expectations", "5 — Outstanding"]),
            f("reviewer", "Reviewer", "text", True),
            f("notes", "Review notes"),
        ],
    },
    "disciplinary": {
        "title": "Disciplinary records",
        "description": "Document incidents and formal actions.",
        "columns": ["employee", "date", "type", "status"],
        "fields": [
            employee, date,
            f("type", "Action", "select", True, ["Verbal warning", "Written warning", "Final warning", "Investigation"]),
            status(["Open", "Resolved"]),
            f("notes", "Incident / action details", "text", True),
        ],
    },
    "devices": {
        "title": "Face & fingerprint",
        "description": "Register attendance hardware. No device is connected yet.",
        "columns": ["name", "brand", "model", "method", "status"],
        "fields": [
            f("name", "Device name", "text", True),
            f("brand", "Brand"),
            f("model", "Model"),
            f("method", "Supported attendance", "select", True, ["Face + Fingerprint", "Face", "Fingerprint", "Card"]),
            f("location", "Location"),
            f("serial", "Serial number"),
            status(["Not connected", "Awaiting integration"]),
            f("notes", "Connection notes"),
        ],
    },
    "settings": {
        "title": "Company settings",
        "description": "Company details used on reports and salary slips.",
        "columns": ["name", "location", "establishment"],
        "fields": [
            f("name", "Company name", "text", True),
            f("location", "Address"),
            f("phone", "Phone"),
            f("email", "Email", "email"),
            f("establishment", "MOHRE establishment ID"),
            f("jurisdiction", "Employment jurisdiction", "select", True, ["UAE federal private sector", "DIFC — separate rules", "ADGM — separate rules", "Other — review policy"]),
            f("annualLeave", "Total leave days / year (70% annual · 30% sick)", "number"),
            f("sickLeave", "Sick leave override (optional — leave blank to use 30%)", "number"),
            f("overtimeRate", "Company overtime rate (AED/hour)", "number"),
            f("notes", "Payroll / leave policy notes", "textarea"),
        ],
    },
}

# Extra nav pages that are tools / reports (not generic CRUD kinds)
TOOL_PAGES = {
    "adminMobile": {
        "title": "HR admin on mobile",
        "description": "The same private HR data and modules, available on PC and phone.",
    },
    "globalSearch": {
        "title": "HR Global Search",
        "description": "Find employee records across your HR workspace.",
    },
    "dataQuality": {
        "title": "HR Data Quality Check",
        "description": "Review missing, duplicate or inconsistent HR details.",
    },
    "employeeFile": {
        "title": "Employee Complete HR File",
        "description": "Current profile and complete linked HR history.",
    },
    "attendanceLedger": {
        "title": "Attendance Ledger",
        "description": "Monthly attendance codes, weekdays and totals.",
    },
    "mobile": {
        "title": "Mobile attendance",
        "description": "A focused check-in screen for administrators.",
    },
    "mobileAccess": {
        "title": "Employee app access",
        "description": "Provision employee ID/PIN logins and download the Android app.",
    },
    "leaveBalances": {
        "title": "Leave balances",
        "description": "Annual leave balances by employee.",
    },
    "salaryPayments": {
        "title": "Salary Payment Report",
        "description": "Monthly paid salary, approved unpaid salary and payment details.",
    },
    "loanReport": {
        "title": "Loan Recovery Report",
        "description": "Loan and advance balances and salary recovery history.",
    },
    "exitReport": {
        "title": "Employee Exit Report",
        "description": "Resignation, clearance, assets, loan balances and final payment progress.",
    },
    "gratuity": {
        "title": "End of service",
        "description": "Federal private-sector gratuity estimate for eligible expatriate full-time employees.",
    },
    "monthlySummary": {
        "title": "HR Monthly Summary",
        "description": "Monthly attendance, salary, recovery, pending work and exits.",
    },
    "reports": {
        "title": "Reports & insights",
        "description": "Filter your records and export only what you need.",
    },
    "backup": {
        "title": "Backup",
        "description": "Download a complete snapshot of your workspace records.",
    },
    "adminLogin": {
        "title": "Admin Login Settings",
        "description": "Manage your administrator username and password.",
    },
}

# Sidebar order matching Next.js hr-app.tsx (+ Flask multi-tenant extras)
# Sidebar modules only. Employee-scoped tools (documents, help desk, exit, etc.)
# are opened from Employees → Actions, not the main nav.
NAV = [
    ("dashboard", "Dashboard", "workspace"),
    ("employees", "Employees", "workspace"),
    ("attendance", "Attendance", "workspace"),
    ("shifts", "Shifts & schedules", "workspace"),
    ("announcements", "HR announcements", "workspace"),
    ("departments", "Departments", "workspace"),
    ("assets", "Company assets", "workspace"),
    ("recruitment", "Recruitment", "admin"),
    ("reports", "Reports", "admin"),
    ("backup", "Backup", "admin"),
    ("settings", "Company settings", "admin"),
]

# Opened from Employees → Actions (filtered by employee=)
EMPLOYEE_SCOPED_KINDS = {
    "documents",
    "documentRenewals",
    "letters",
    "certificateRequests",
    "helpDesk",
    "resignations",
    "finalSettlements",
    "exitReport",
    "performance",
    "disciplinary",
    "devices",
    "gratuity",
}
