"""Employee-scoped helpers ported from the old Next.js lib/* logic."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timedelta, timezone

from app.extensions import db
from app.models import Agency, Employee, HrRecord

DAY_MS = 86400000


def dubai_today() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=4)).strftime("%Y-%m-%d")


def dubai_now_iso() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%S")


def dubai_now_time() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=4)).strftime("%H:%M")


def dubai_yesterday() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=4) - timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )


def employee_match_ids(emp: Employee) -> set[str]:
    """IDs/codes that may appear in HrRecord.data.employee for this login."""
    ids = {str(emp.id), str(emp.employee_code)}
    hrs = (
        HrRecord.query.filter_by(agency_id=emp.agency_id, kind="employees")
        .order_by(HrRecord.id.desc())
        .all()
    )
    for h in hrs:
        hd = h.data or {}
        if str(hd.get("authEmployeeId") or "") == str(emp.id) or hd.get("code") == emp.employee_code:
            ids.add(str(h.id))
            if hd.get("code"):
                ids.add(str(hd.get("code")))
            if hd.get("authEmployeeId"):
                ids.add(str(hd.get("authEmployeeId")))
    return ids


def hr_employee_record(emp: Employee) -> HrRecord | None:
    """Linked HR employees row (for joining date / profile fields)."""
    rows = (
        HrRecord.query.filter_by(agency_id=emp.agency_id, kind="employees")
        .order_by(HrRecord.id.desc())
        .all()
    )
    for h in rows:
        hd = h.data or {}
        if str(hd.get("authEmployeeId") or "") == str(emp.id) or hd.get("code") == emp.employee_code:
            return h
    return None


def records_for_employee(emp: Employee, kind: str) -> list[HrRecord]:
    match = employee_match_ids(emp)
    rows = (
        HrRecord.query.filter_by(agency_id=emp.agency_id, kind=kind)
        .order_by(HrRecord.id.desc())
        .all()
    )
    return [r for r in rows if str((r.data or {}).get("employee") or "") in match]


def leave_day_count(data: dict) -> int:
    try:
        frm = datetime.strptime((data or {}).get("from") or "", "%Y-%m-%d")
        to = datetime.strptime((data or {}).get("to") or "", "%Y-%m-%d")
        return max((to - frm).days + 1, 0)
    except Exception:
        return 0


def _parse_ymd(s: str) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _anniversary(joining: str, year: int) -> str:
    m = int(joining[5:7])
    d = int(joining[8:10])
    # Clamp day for Feb 29 etc.
    try:
        return date(year, m, d).isoformat()
    except ValueError:
        # last day of month
        if m == 12:
            return date(year, 12, 31).isoformat()
        return (date(year, m + 1, 1) - timedelta(days=1)).isoformat()


def _leave_pool_split(settings_data: dict | None) -> tuple[int, int, int]:
    """Total leave pool split ~70% annual / ~30% sick.

    ``annualLeave`` in company settings is the total entitlement.
    Example: total 30 → 20 annual + 10 sick; total 100 → 70 + 30.
    """
    total = 30
    sd = settings_data or {}
    try:
        if sd.get("totalLeave") not in (None, ""):
            total = int(sd.get("totalLeave"))
        elif sd.get("annualLeave") not in (None, ""):
            total = int(sd.get("annualLeave"))
    except Exception:
        total = 30
    total = max(1, total)
    # Prefer exact 70/30 on multiples of 10; else nearest ints summing to total
    annual = (total * 70) // 100
    sick = total - annual
    if sick < 1 and total > 1:
        sick = 1
        annual = total - 1
    # Match common HR example 30 → 20 / 10 (still ~67/33 ≈ 70/30)
    if total == 30:
        annual, sick = 20, 10
    return total, annual, sick


def annual_leave_balance(emp: Employee, leaves: list | None = None) -> dict:
    """Anniversary-cycle annual leave + calendar-year sick (70/30 of total pool)."""
    hr = hr_employee_record(emp)
    joining = str((hr.data or {}).get("joining") or "") if hr else ""
    current_day = dubai_today()

    settings = (
        HrRecord.query.filter_by(agency_id=emp.agency_id, kind="settings")
        .order_by(HrRecord.id.desc())
        .first()
    )
    total_quota, allowance, sick_quota = _leave_pool_split(settings.data if settings else None)

    if leaves is None:
        leaves = records_for_employee(emp, "leave")

    # Sick: simple calendar-year Approved count (old app only tracked Annual formally)
    year = current_day[:4]
    sick_used = 0
    for r in leaves:
        d = r.data if hasattr(r, "data") else r
        if isinstance(d, HrRecord):
            d = d.data or {}
        if (d.get("type") or "") != "Sick" or (d.get("status") or "") != "Approved":
            continue
        if str(d.get("from") or "")[:4] == year:
            sick_used += leave_day_count(d)

    joining_d = _parse_ymd(joining)
    if not joining_d or joining > current_day:
        return {
            "available": False,
            "message": "A valid joining date is required before this leave cycle starts. Ask HR to set it on your profile.",
            "total_quota": total_quota,
            "annual_ratio": 70,
            "sick_ratio": 30,
            "annual_quota": allowance,
            "annual_used": 0,
            "annual_booked": 0,
            "annual_pending": 0,
            "annual_remaining": allowance,
            "sick_quota": sick_quota,
            "sick_used": sick_used,
            "sick_remaining": max(sick_quota - sick_used, 0),
            "other_used": 0,
            "total_used": sick_used,
            "total_remaining": allowance + max(sick_quota - sick_used, 0),
            "pending_count": sum(
                1
                for r in leaves
                if ((r.data or {}) if hasattr(r, "data") else (r or {})).get("status") == "Pending"
            ),
            "cycle_start": "",
            "cycle_end": "",
            "leaves": leaves if isinstance(leaves, list) else [],
        }

    y = int(current_day[:4])
    if _anniversary(joining, y) > current_day:
        y -= 1
    start = _anniversary(joining, y)
    next_ann = _anniversary(joining, y + 1)
    end = (datetime.strptime(next_ann, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()

    used: set[str] = set()
    booked: set[str] = set()
    pending: set[str] = set()
    match = employee_match_ids(emp)
    other_used = 0
    pending_count = 0

    for r in leaves:
        d = (r.data or {}) if hasattr(r, "data") else (r or {})
        if str(d.get("employee") or "") not in match and hasattr(r, "data"):
            # already filtered by records_for_employee usually
            pass
        status = d.get("status") or ""
        if status == "Pending":
            pending_count += 1
        ltype = (d.get("type") or "").strip()
        if ltype == "Annual" and status in {"Approved", "Pending"}:
            frm = d.get("from") or ""
            to = d.get("to") or ""
            if not _parse_ymd(frm) or not _parse_ymd(to) or to < frm:
                continue
            from_d = frm if frm > start else start
            to_d = to if to < end else end
            if to_d < from_d:
                continue
            cur = datetime.strptime(from_d, "%Y-%m-%d").date()
            last = datetime.strptime(to_d, "%Y-%m-%d").date()
            while cur <= last:
                day = cur.isoformat()
                if status == "Pending":
                    pending.add(day)
                elif day <= current_day:
                    used.add(day)
                else:
                    booked.add(day)
                cur += timedelta(days=1)
        elif ltype not in {"Annual", "Sick"} and status == "Approved":
            other_used += leave_day_count(d)

    committed = len(used) + len(booked)
    annual_remaining = max(0, allowance - committed)
    sick_remaining = max(sick_quota - sick_used, 0)
    return {
        "available": True,
        "message": "",
        "total_quota": total_quota,
        "annual_ratio": 70,
        "sick_ratio": 30,
        "annual_quota": allowance,
        "annual_used": len(used),
        "annual_booked": len(booked),
        "annual_pending": len(pending),
        "annual_remaining": annual_remaining,
        "overdrawn": max(0, committed - allowance),
        "sick_quota": sick_quota,
        "sick_used": sick_used,
        "sick_remaining": sick_remaining,
        "other_used": other_used,
        "total_used": len(used) + sick_used + other_used,
        "total_remaining": annual_remaining + sick_remaining,
        "pending_count": pending_count,
        "cycle_start": start,
        "cycle_end": end,
        "leaves": leaves,
    }


def leave_quotas(emp: Employee) -> dict:
    """Alias used by routes — anniversary annual + sick."""
    return annual_leave_balance(emp)


def last_punch_summary(emp: Employee) -> dict:
    """Latest check-in and check-out for dashboard KPI."""
    last_in = None
    last_out = None
    for r in records_for_employee(emp, "attendance"):
        d = r.data or {}
        if not last_in and d.get("timeIn"):
            last_in = {
                "date": d.get("date") or "",
                "time": d.get("timeIn") or "",
                "label": f"{d.get('timeIn')} · {d.get('date') or ''}".strip(" ·"),
            }
        if not last_out and d.get("timeOut"):
            out_date = d.get("timeOutDate") or d.get("date") or ""
            last_out = {
                "date": out_date,
                "time": d.get("timeOut") or "",
                "label": f"{d.get('timeOut')} · {out_date}".strip(" ·"),
            }
        if last_in and last_out:
            break
    return {"last_in": last_in, "last_out": last_out}


def build_employee_dashboard(emp: Employee) -> dict:
    """Employee-only KPIs, 14-day line trend, and pie cards (Chart.js)."""
    quotas = leave_quotas(emp)
    punches = last_punch_summary(emp)
    attendance_rows = records_for_employee(emp, "attendance")
    leave_rows = records_for_employee(emp, "leave")

    today = dubai_today()
    today_d = datetime.strptime(today, "%Y-%m-%d").date()
    days = 14
    labels = []
    checkins = []
    checkouts = []
    on_leave = []
    att_by_date = {}
    for r in attendance_rows:
        d = r.data or {}
        day = str(d.get("date") or "")
        if not day:
            continue
        slot = att_by_date.setdefault(day, {"in": 0, "out": 0})
        if d.get("timeIn"):
            slot["in"] = 1
        if d.get("timeOut"):
            slot["out"] = 1

    def on_leave_day(day: str) -> int:
        for r in leave_rows:
            d = r.data or {}
            if (d.get("status") or "") != "Approved":
                continue
            frm, to = d.get("from") or "", d.get("to") or ""
            if frm and to and frm <= day <= to:
                return 1
        return 0

    for i in range(days - 1, -1, -1):
        day = (today_d - timedelta(days=i)).isoformat()
        labels.append(datetime.strptime(day, "%Y-%m-%d").strftime("%d %b"))
        slot = att_by_date.get(day) or {"in": 0, "out": 0}
        checkins.append(slot["in"])
        checkouts.append(slot["out"])
        on_leave.append(on_leave_day(day))

    approved = sum(1 for r in leave_rows if (r.data or {}).get("status") == "Approved")
    pending = sum(1 for r in leave_rows if (r.data or {}).get("status") == "Pending")
    rejected = sum(1 for r in leave_rows if (r.data or {}).get("status") == "Rejected")

    month_prefix = today[:7]
    month_present = 0
    month_incomplete = 0
    for r in attendance_rows:
        d = r.data or {}
        if str(d.get("date") or "")[:7] != month_prefix:
            continue
        if d.get("timeIn") and d.get("timeOut"):
            month_present += 1
        elif d.get("timeIn"):
            month_incomplete += 1

    colors = {
        "green": "#176344",
        "blue": "#1a73e8",
        "orange": "#e8710a",
        "teal": "#12b5cb",
        "gold": "#c9a227",
        "red": "#c44b3c",
        "muted": "#8aa07a",
    }

    def pie(card_id, title, subtitle, headline, headline_sub, rows):
        chart_rows = list(rows)
        series = [r[1] for r in chart_rows]
        if not any(series):
            chart_rows = [("None yet", 1, colors["muted"])]
            series = [1]
            details = [{"label": "None yet", "value": 0, "color": colors["muted"]}]
        else:
            details = [{"label": r[0], "value": r[1], "color": r[2]} for r in chart_rows]
        return {
            "id": card_id,
            "title": title,
            "subtitle": subtitle,
            "headline": headline,
            "headline_sub": headline_sub,
            "details": details,
            "labels": [r[0] for r in chart_rows],
            "series": series,
            "colors": [r[2] for r in chart_rows],
        }

    leave_pool_rows = [
        ("Annual left", quotas.get("annual_remaining") or 0, colors["green"]),
        ("Sick left", quotas.get("sick_remaining") or 0, colors["blue"]),
        ("Used", quotas.get("total_used") or 0, colors["orange"]),
    ]
    leave_type_rows = [
        ("Annual used", quotas.get("annual_used") or 0, colors["green"]),
        ("Sick used", quotas.get("sick_used") or 0, colors["teal"]),
        ("Other used", quotas.get("other_used") or 0, colors["gold"]),
    ]
    month_rows = [
        ("Complete days", month_present, colors["green"]),
        ("Open (no out)", month_incomplete, colors["orange"]),
        ("On leave days (14d)", sum(on_leave), colors["teal"]),
    ]
    request_rows = [
        ("Pending", pending, colors["orange"]),
        ("Approved", approved, colors["green"]),
        ("Rejected", rejected, colors["red"]),
    ]

    pie_cards = [
        pie(
            "empPieLeavePool",
            "Leave balance",
            f"Pool {quotas.get('total_quota') or 0} days · 70% annual / 30% sick",
            quotas.get("total_remaining") or 0,
            "days remaining",
            leave_pool_rows,
        ),
        pie(
            "empPieLeaveTypes",
            "Leave used",
            "Approved days this cycle / year",
            quotas.get("total_used") or 0,
            "days used",
            leave_type_rows,
        ),
        pie(
            "empPieAttendance",
            "Attendance",
            f"This month ({month_prefix})",
            month_present,
            "complete punch days",
            month_rows,
        ),
        pie(
            "empPieRequests",
            "Leave requests",
            "Your leave applications",
            pending,
            "pending with HR",
            request_rows,
        ),
    ]

    return {
        "quotas": quotas,
        "punches": punches,
        "kpis": {
            "total_leave": quotas.get("total_quota") or 0,
            "total_remaining": quotas.get("total_remaining") or 0,
            "annual_quota": quotas.get("annual_quota") or 0,
            "annual_remaining": quotas.get("annual_remaining") or 0,
            "sick_quota": quotas.get("sick_quota") or 0,
            "sick_remaining": quotas.get("sick_remaining") or 0,
            "last_in": (punches.get("last_in") or {}).get("label") or "—",
            "last_out": (punches.get("last_out") or {}).get("label") or "—",
        },
        "trend": {
            "labels": labels,
            "checkins": checkins,
            "checkouts": checkouts,
            "on_leave": on_leave,
            "range_label": f"Last {days} days · Dubai",
        },
        "pie_cards": pie_cards,
    }


def visible_announcement(d: dict, department: str, today: str | None = None) -> bool:
    """Port of lib/announcements.visibleAnnouncement."""
    today = today or dubai_today()
    if (d.get("status") or "") != "Published":
        return False
    pub = (d.get("date") or "").strip()
    if not pub or pub > today:
        return False
    expiry = (d.get("expiry") or "").strip()
    if expiry and expiry < today:
        return False
    audience = (d.get("audience") or "All employees").strip()
    if audience == "All employees":
        return True
    if audience == "Department":
        return (d.get("department") or "").strip().lower() == (department or "").strip().lower()
    return False


def published_announcements(emp: Employee) -> list[HrRecord]:
    today = dubai_today()
    dept = (emp.department or "").strip()
    rows = (
        HrRecord.query.filter_by(agency_id=emp.agency_id, kind="announcements")
        .order_by(HrRecord.id.desc())
        .all()
    )
    return [r for r in rows if visible_announcement(r.data or {}, dept, today)]


def announcement_acks(emp: Employee) -> dict[str, str]:
    """Map announcementId:revision → acknowledgedAt."""
    rows = (
        HrRecord.query.filter_by(agency_id=emp.agency_id, kind="announcementReads")
        .order_by(HrRecord.id.desc())
        .all()
    )
    out = {}
    for r in rows:
        d = r.data or {}
        if str(d.get("employee") or "") != str(emp.id):
            continue
        key = f"{d.get('announcementId')}:{d.get('revision')}"
        out[key] = d.get("date") or ""
    return out


def ensure_announcement_revision(data: dict) -> dict:
    data = dict(data or {})
    if not data.get("revision"):
        data["revision"] = str(uuid.uuid4())
    return data


def acknowledge_announcement(emp: Employee, announcement_id: int, revision: str) -> None:
    today = dubai_today()
    dept = (emp.department or "").strip()
    row = HrRecord.query.filter_by(
        id=announcement_id, agency_id=emp.agency_id, kind="announcements"
    ).first()
    if not row:
        raise ValueError("Notice not found.")
    d = row.data or {}
    if not visible_announcement(d, dept, today):
        raise ValueError("Notice is not available.")
    if (revision or "") != (d.get("revision") or ""):
        raise ValueError("Notice changed. Refresh and read it again.")
    key = f"{emp.id}:{announcement_id}:{d.get('revision')}"
    existing = (
        HrRecord.query.filter_by(agency_id=emp.agency_id, kind="announcementReads")
        .order_by(HrRecord.id.desc())
        .all()
    )
    already = False
    for e in existing:
        ed = e.data or {}
        if (
            str(ed.get("employee")) == str(emp.id)
            and int(ed.get("announcementId") or 0) == announcement_id
            and ed.get("revision") == d.get("revision")
        ):
            already = True
            break
    if not already:
        receipt = {
            "employee": str(emp.id),
            "announcementId": announcement_id,
            "title": d.get("title") or "",
            "revision": d.get("revision") or "",
            "date": dubai_now_iso(),
            "status": "Acknowledged",
            "naturalKey": key,
        }
        db.session.add(HrRecord(agency_id=emp.agency_id, kind="announcementReads", data=receipt))
    # Also clear matching bell notification
    for n in employee_notifications(emp, limit=40):
        if n.get("type") == "announcements" and int(n.get("recordId") or 0) == announcement_id:
            mark_notification_read(emp, n.get("key") or "")
            break


def current_shift(emp: Employee) -> HrRecord | None:
    """Latest shift with effective ≤ today (old mobile currentShift)."""
    today = dubai_today()
    rows = records_for_employee(emp, "shifts")
    best = None
    best_eff = ""
    for r in rows:
        d = r.data or {}
        eff = (d.get("effective") or "").strip()
        if not eff or eff > today:
            continue
        if eff >= best_eff:
            best_eff = eff
            best = r
    return best


def open_attendance_record(emp: Employee) -> HrRecord | None:
    """Open punch (checked in, not out) for yesterday or today — night-shift aware."""
    today = dubai_today()
    yesterday = dubai_yesterday()
    match = employee_match_ids(emp)
    rows = (
        HrRecord.query.filter_by(agency_id=emp.agency_id, kind="attendance")
        .order_by(HrRecord.id.desc())
        .all()
    )
    for r in rows:
        d = r.data or {}
        if str(d.get("employee") or "") not in match:
            continue
        if (d.get("date") or "") not in {today, yesterday}:
            continue
        if (d.get("timeIn") or "") and not (d.get("timeOut") or ""):
            return r
    return None


def today_attendance_record(emp: Employee) -> HrRecord | None:
    """Closed or open attendance keyed to Dubai today (or open night shift)."""
    open_rec = open_attendance_record(emp)
    if open_rec:
        return open_rec
    today = dubai_today()
    match = employee_match_ids(emp)
    rows = records_for_employee(emp, "attendance")
    for r in rows:
        d = r.data or {}
        if (d.get("date") or "") == today and str(d.get("employee") or "") in match:
            return r
    return None


def punch_attendance(emp: Employee, action: str) -> dict:
    """Employee check-in / check-out → HrRecord(kind=attendance) for admin hub."""
    action = (action or "").strip().lower()
    if action not in {"in", "out"}:
        raise ValueError("Unknown punch action.")

    today = dubai_today()
    now_iso = dubai_now_iso()
    time_hm = dubai_now_time()
    current = open_attendance_record(emp)
    old = dict(current.data or {}) if current else None

    # Prefer today's closed/open record when not mid night-shift
    if not current:
        for r in records_for_employee(emp, "attendance"):
            d = r.data or {}
            if (d.get("date") or "") == today:
                current = r
                old = dict(d)
                break

    if action == "in":
        if old and old.get("timeIn") and not old.get("timeOut") and (old.get("date") or "") in {
            today,
            dubai_yesterday(),
        }:
            raise ValueError("Already checked in. Check out first.")
        if old and old.get("timeIn") and (old.get("date") or "") == today:
            raise ValueError("Already checked in today.")
        punch_date = today
        data = {
            "employee": str(emp.id),
            "date": punch_date,
            "timeIn": time_hm,
            "timeOut": "",
            "timeOutDate": "",
            "method": "Mobile (GPS)",
            "status": "Present",
            "notes": "Employee portal check-in.",
            "checkInAt": now_iso,
        }
        if current and (old or {}).get("date") == today and not (old or {}).get("timeIn"):
            current.data = {**(old or {}), **data}
            rec = current
        else:
            rec = HrRecord(agency_id=emp.agency_id, kind="attendance", data=data)
            db.session.add(rec)
        db.session.flush()
        return {"ok": True, "action": "in", "record": rec.data, "id": rec.id}

    # out
    if not old or not old.get("timeIn"):
        raise ValueError("Check in first.")
    if old.get("timeOut"):
        raise ValueError("Already checked out.")
    data = {
        **old,
        "employee": str(emp.id),
        "timeOut": time_hm,
        "timeOutDate": today,
        "method": old.get("method") or "Mobile (GPS)",
        "status": old.get("status") or "Present",
        "checkOutAt": now_iso,
        "notes": old.get("notes") or "Employee portal check-out.",
    }
    if current:
        current.data = data
        rec = current
    else:
        rec = HrRecord(agency_id=emp.agency_id, kind="attendance", data=data)
        db.session.add(rec)
    db.session.flush()
    return {"ok": True, "action": "out", "record": rec.data, "id": rec.id}


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _notification_reads(emp: Employee) -> set[str]:
    rows = HrRecord.query.filter_by(agency_id=emp.agency_id, kind="notificationReads").all()
    keys = set()
    for r in rows:
        d = r.data or {}
        if str(d.get("employee") or "") != str(emp.id):
            continue
        if d.get("naturalKey"):
            keys.add(d["naturalKey"])
        if d.get("notificationKey"):
            keys.add(f"{emp.id}:{d['notificationKey']}")
    return keys


def employee_notifications(emp: Employee, limit: int = 20) -> list[dict]:
    """Port of lib/notifications.ts feed (announcements + HR decisions)."""
    from flask import url_for

    today = dubai_today()
    dept = (emp.department or "").strip()
    match = employee_match_ids(emp)
    read_keys = _notification_reads(emp)
    items: list[dict] = []

    kinds = (
        HrRecord.query.filter(
            HrRecord.agency_id == emp.agency_id,
            HrRecord.kind.in_(
                [
                    "announcements",
                    "shifts",
                    "leave",
                    "certificateRequests",
                    "helpDesk",
                    "resignations",
                    "finalSettlements",
                ]
            ),
        )
        .order_by(HrRecord.id.desc())
        .limit(120)
        .all()
    )

    for r in kinds:
        d = r.data or {}
        title = message = ""
        event = None
        href = url_for("employee.home")

        if r.kind == "announcements":
            if not visible_announcement(d, dept, today):
                continue
            title = d.get("title") or "HR announcement"
            message = "New HR announcement"
            event = {
                "revision": d.get("revision") or "",
                "title": d.get("title") or "",
                "body": d.get("body") or "",
                "date": d.get("date") or "",
                "expiry": d.get("expiry") or "",
            }
            href = url_for("employee.announcements")
        elif r.kind == "shifts":
            if str(d.get("employee") or "") not in match:
                continue
            title = "Shift assigned"
            message = (
                f"{d.get('name') or 'Shift'} · {d.get('start') or '—'} – {d.get('end') or '—'}"
                f" · Rest {d.get('restDay') or '—'}"
            )
            event = {
                "name": d.get("name"),
                "start": d.get("start"),
                "end": d.get("end"),
                "restDay": d.get("restDay"),
                "effective": d.get("effective"),
            }
            href = url_for("employee.shifts")
        elif r.kind == "leave":
            if str(d.get("employee") or "") not in match:
                continue
            if (d.get("status") or "") not in {"Approved", "Rejected"}:
                continue
            title = f"Leave {(d.get('status') or '').lower()}"
            message = f"{d.get('type') or 'Leave'} · {d.get('from') or '—'} – {d.get('to') or '—'}"
            event = {
                "status": d.get("status"),
                "type": d.get("type"),
                "from": d.get("from"),
                "to": d.get("to"),
                "reason": d.get("reason"),
            }
            href = url_for("employee.leave")
        elif r.kind == "certificateRequests":
            if str(d.get("employee") or "") not in match:
                continue
            if (d.get("status") or "") not in {"Issued", "Rejected"}:
                continue
            title = f"{d.get('type') or 'Certificate'} · {d.get('status')}"
            message = d.get("reviewNote") or "HR has reviewed your certificate request."
            event = {"status": d.get("status"), "reviewNote": d.get("reviewNote")}
            href = url_for("employee.home")
        elif r.kind == "resignations":
            if str(d.get("employee") or "") not in match:
                continue
            if not d.get("reviewedAt"):
                continue
            title = f"Resignation · {d.get('status') or ''}"
            message = f"Clearance: {d.get('clearance') or '—'} · Handover: {d.get('handover') or '—'}"
            event = {"status": d.get("status"), "reviewedAt": d.get("reviewedAt")}
        elif r.kind == "finalSettlements":
            if str(d.get("employee") or "") not in match:
                continue
            if (d.get("status") or "") not in {"Approved", "Paid"}:
                continue
            title = f"Final settlement · {d.get('status')}"
            message = f"Final payable: AED {d.get('net') or '—'}"
            event = {"status": d.get("status"), "net": d.get("net")}
        elif r.kind == "helpDesk":
            if str(d.get("employee") or "") not in match:
                continue
            if not d.get("reviewedAt") and not d.get("reply"):
                continue
            title = f"HR help desk · {d.get('status') or ''}"
            message = d.get("subject") or "HR replied to your request."
            event = {"status": d.get("status"), "reply": d.get("reply")}
        else:
            continue

        if not event:
            continue
        key = f"{r.kind}:{r.id}:{_digest(json.dumps(event, sort_keys=True, default=str))}"
        natural_key = f"{emp.id}:{key}"
        items.append(
            {
                "id": key,
                "key": key,
                "type": r.kind,
                "kind": r.kind,
                "recordId": r.id,
                "title": title,
                "meta": message,
                "message": message,
                "body": d.get("body") or d.get("reason") or d.get("reply") or "",
                "href": href,
                "read": natural_key in read_keys or key in read_keys,
                "created_at": d.get("date") or d.get("from") or str(r.id),
            }
        )
        if len(items) >= limit:
            break

    return items


def mark_notification_read(emp: Employee, key: str) -> None:
    natural_key = f"{emp.id}:{key}"
    reads = _notification_reads(emp)
    if natural_key in reads or key in reads:
        return
    db.session.add(
        HrRecord(
            agency_id=emp.agency_id,
            kind="notificationReads",
            data={
                "employee": str(emp.id),
                "notificationKey": key,
                "naturalKey": natural_key,
                "date": dubai_now_iso(),
            },
        )
    )


def employee_agency(emp: Employee) -> Agency | None:
    return Agency.query.get(emp.agency_id)


def leave_overlap_exists(emp: Employee, frm: str, to: str, exclude_id: int | None = None) -> bool:
    """Block overlapping Pending/Approved leave (old requestLeave rule)."""
    for r in records_for_employee(emp, "leave"):
        if exclude_id and r.id == exclude_id:
            continue
        d = r.data or {}
        if (d.get("status") or "") not in {"Pending", "Approved"}:
            continue
        a, b = d.get("from") or "", d.get("to") or ""
        if not a or not b:
            continue
        if frm <= b and to >= a:
            return True
    return False
