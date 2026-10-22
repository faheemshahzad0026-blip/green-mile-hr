"""Agency dashboard KPIs, chart series, and recent activity lists."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models import Employee, HrRecord


def _dubai_today() -> datetime.date:
    return (datetime.now(timezone.utc) + timedelta(hours=4)).date()


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _emp_label(agency_id: int, emp_ref: str, employees_map: dict) -> dict:
    emp = employees_map.get(str(emp_ref)) or employees_map.get(emp_ref)
    if isinstance(emp, dict):
        return {
            "id": emp.get("code") or emp.get("employee_code") or str(emp_ref or "—"),
            "name": emp.get("name") or emp.get("full_name") or "Employee",
            "ref": str(emp.get("authEmployeeId") or emp.get("record_id") or emp_ref or ""),
        }
    if emp is not None and hasattr(emp, "employee_code"):
        return {
            "id": emp.employee_code,
            "name": emp.full_name,
            "ref": str(emp.id),
        }
    # Fall back to HR employee records
    for e in employees_map.values():
        if isinstance(e, dict) and (
            str(e.get("authEmployeeId")) == str(emp_ref)
            or str(e.get("code")) == str(emp_ref)
            or str(e.get("record_id")) == str(emp_ref)
        ):
            return {
                "id": e.get("code") or "—",
                "name": e.get("name") or "Employee",
                "ref": str(emp_ref),
            }
    return {"id": str(emp_ref or "—"), "name": "Employee", "ref": str(emp_ref or "")}


def _build_employee_maps(agency_id: int):
    auth_emps = Employee.query.filter_by(agency_id=agency_id).all()
    by_key: dict[str, Any] = {}
    for e in auth_emps:
        by_key[str(e.id)] = e
        by_key[e.employee_code] = e

    hr_rows = HrRecord.query.filter_by(agency_id=agency_id, kind="employees").all()
    hr_meta = []
    active = 0
    total = len(hr_rows) or len(auth_emps)
    for r in hr_rows:
        data = r.data or {}
        status = str(data.get("status") or "Active")
        if status not in {"Inactive", "Terminated", "Resigned"}:
            active += 1
        meta = {
            "record_id": r.id,
            "code": data.get("code"),
            "name": data.get("name"),
            "status": status,
            "authEmployeeId": data.get("authEmployeeId"),
            "department": data.get("department") or "Unassigned",
        }
        hr_meta.append(meta)
        by_key[str(r.id)] = meta
        if data.get("code"):
            by_key[str(data.get("code"))] = meta
        if data.get("authEmployeeId"):
            by_key[str(data.get("authEmployeeId"))] = meta

    if not hr_rows:
        active = sum(1 for e in auth_emps if e.is_active)
        total = len(auth_emps)

    return by_key, hr_meta, total, active


def build_dashboard(agency_id: int, period: dict | None = None) -> dict:
    today = _dubai_today()
    period = period or {}
    range_start = period.get("start")
    range_end = period.get("end") or today
    period_key = period.get("key") or "today"
    period_label = period.get("label") or "Today"
    employees_map, hr_meta, all_employees, active_employees = _build_employee_maps(agency_id)

    attendance = (
        HrRecord.query.filter_by(agency_id=agency_id, kind="attendance")
        .order_by(HrRecord.id.desc())
        .all()
    )
    leave_rows = (
        HrRecord.query.filter_by(agency_id=agency_id, kind="leave")
        .order_by(HrRecord.id.desc())
        .all()
    )
    corrections = (
        HrRecord.query.filter_by(agency_id=agency_id, kind="corrections")
        .order_by(HrRecord.id.desc())
        .all()
    )
    help_desk = (
        HrRecord.query.filter_by(agency_id=agency_id, kind="helpDesk")
        .order_by(HrRecord.id.desc())
        .all()
    )

    today_att = []
    for r in attendance:
        d = r.data or {}
        if _parse_date(d.get("date")) == today:
            today_att.append(r)

    checked_in_ids = set()
    for r in today_att:
        d = r.data or {}
        status = (d.get("status") or "").lower()
        if d.get("timeIn") or status in {"present", "late"}:
            checked_in_ids.add(str(d.get("employee") or ""))

    on_leave_today = []
    for r in leave_rows:
        d = r.data or {}
        if (d.get("status") or "") != "Approved":
            continue
        start = _parse_date(d.get("from"))
        end = _parse_date(d.get("to"))
        if start and end and start <= today <= end:
            on_leave_today.append(r)

    on_leave_ids = {str((r.data or {}).get("employee") or "") for r in on_leave_today}
    pending_checkin = max(active_employees - len(checked_in_ids - {""}) - len(on_leave_ids - {""}), 0)

    pending_leave = [
        r
        for r in leave_rows
        if (r.data or {}).get("status") in {"Pending", "In progress"}
    ]

    # Trend window from selected period (cap points for readability)
    if range_start is None:
        chart_start = today - timedelta(days=29)
    else:
        chart_start = range_start
    chart_end = range_end or today
    if chart_start > chart_end:
        chart_start, chart_end = chart_end, chart_start
    span_days = (chart_end - chart_start).days + 1
    if span_days > 60:
        # keep last 60 days of a long range so the line chart stays readable
        chart_start = chart_end - timedelta(days=59)
        span_days = 60

    checkin_by_day = Counter()
    checkout_by_day = Counter()
    for r in attendance:
        d = r.data or {}
        day = _parse_date(d.get("date"))
        if not day or day < chart_start or day > chart_end:
            continue
        if d.get("timeIn") or (d.get("status") or "").lower() in {"present", "late"}:
            checkin_by_day[day.isoformat()] += 1
        if d.get("timeOut"):
            checkout_by_day[day.isoformat()] += 1

    approved_leave_spans = []
    for r in leave_rows:
        d = r.data or {}
        if (d.get("status") or "") != "Approved":
            continue
        start = _parse_date(d.get("from"))
        end = _parse_date(d.get("to"))
        if start and end:
            approved_leave_spans.append((start, end))

    trend_labels = []
    trend_employees = []
    trend_checkins = []
    trend_checkouts = []
    trend_on_leave = []
    for i in range(span_days):
        day = chart_start + timedelta(days=i)
        key = day.isoformat()
        trend_labels.append(day.strftime("%d %b"))
        # No daily workforce history — show current total workforce as baseline
        trend_employees.append(all_employees)
        trend_checkins.append(checkin_by_day.get(key, 0))
        trend_checkouts.append(checkout_by_day.get(key, 0))
        on_leave_n = sum(1 for start, end in approved_leave_spans if start <= day <= end)
        trend_on_leave.append(on_leave_n)

    # Period-aware KPI helpers (attendance in selected range)
    def _in_range(day):
        if day is None:
            return False
        if range_start is None:
            return day <= range_end
        return range_start <= day <= range_end

    period_checkins = sum(
        1
        for r in attendance
        if _in_range(_parse_date((r.data or {}).get("date")))
        and (
            (r.data or {}).get("timeIn")
            or ((r.data or {}).get("status") or "").lower() in {"present", "late"}
        )
    )
    period_checkouts = sum(
        1
        for r in attendance
        if _in_range(_parse_date((r.data or {}).get("date"))) and (r.data or {}).get("timeOut")
    )

    def person_from_att(r, with_time_key):
        d = r.data or {}
        info = _emp_label(agency_id, str(d.get("employee") or ""), employees_map)
        if isinstance(employees_map.get(str(d.get("employee") or "")), dict):
            m = employees_map[str(d.get("employee") or "")]
            info = {
                "id": m.get("code") or info["id"],
                "name": m.get("name") or info["name"],
                "ref": str(d.get("employee") or ""),
            }
        elif hasattr(employees_map.get(str(d.get("employee") or "")), "employee_code"):
            e = employees_map[str(d.get("employee") or "")]
            info = {"id": e.employee_code, "name": e.full_name, "ref": str(e.id)}
        # Prefer HR name by code
        for m in hr_meta:
            if str(m.get("authEmployeeId")) == str(d.get("employee")) or str(
                m.get("code")
            ) == str(d.get("employee")):
                info = {
                    "id": m.get("code") or info["id"],
                    "name": m.get("name") or info["name"],
                    "ref": str(d.get("employee") or ""),
                }
                break
        return {
            **info,
            "time": d.get(with_time_key) or "—",
            "date": d.get("date") or "",
            "status": d.get("status") or "",
            "method": d.get("method") or "Manual",
        }

    last_checkins = []
    for r in attendance:
        d = r.data or {}
        if not d.get("timeIn"):
            continue
        last_checkins.append(person_from_att(r, "timeIn"))
        if len(last_checkins) >= 5:
            break

    last_checkouts = []
    for r in attendance:
        d = r.data or {}
        if not d.get("timeOut"):
            continue
        last_checkouts.append(person_from_att(r, "timeOut"))
        if len(last_checkouts) >= 5:
            break

    leave_list = []
    for r in on_leave_today[:5]:
        d = r.data or {}
        info = _emp_label(agency_id, str(d.get("employee") or ""), employees_map)
        for m in hr_meta:
            if str(m.get("authEmployeeId")) == str(d.get("employee")) or str(
                m.get("code")
            ) == str(d.get("employee")):
                info = {
                    "id": m.get("code") or info["id"],
                    "name": m.get("name") or info["name"],
                    "ref": str(d.get("employee") or ""),
                }
                break
        leave_list.append(
            {
                **info,
                "type": d.get("type") or "Leave",
                "until": d.get("to") or "—",
            }
        )

    pending_requests = []
    for r in pending_leave:
        d = r.data or {}
        info = _emp_label(agency_id, str(d.get("employee") or ""), employees_map)
        for m in hr_meta:
            if str(m.get("authEmployeeId")) == str(d.get("employee")) or str(
                m.get("code")
            ) == str(d.get("employee")):
                info = {
                    "id": m.get("code") or info["id"],
                    "name": m.get("name") or info["name"],
                    "ref": str(d.get("employee") or ""),
                }
                break
        pending_requests.append(
            {
                **info,
                "kind": "Leave",
                "detail": d.get("type") or "Leave request",
                "status": d.get("status") or "Pending",
            }
        )
        if len(pending_requests) >= 5:
            break
    if len(pending_requests) < 5:
        for r in corrections:
            d = r.data or {}
            if (d.get("status") or "") not in {"Pending", "In progress"}:
                continue
            info = _emp_label(agency_id, str(d.get("employee") or ""), employees_map)
            pending_requests.append(
                {
                    **info,
                    "kind": "Correction",
                    "detail": d.get("reason") or "Attendance correction",
                    "status": d.get("status") or "Pending",
                }
            )
            if len(pending_requests) >= 5:
                break
    if len(pending_requests) < 5:
        for r in help_desk:
            d = r.data or {}
            if (d.get("status") or "") not in {"Pending", "In progress"}:
                continue
            info = _emp_label(agency_id, str(d.get("employee") or ""), employees_map)
            pending_requests.append(
                {
                    **info,
                    "kind": "Help desk",
                    "detail": d.get("subject") or "Employee query",
                    "status": d.get("status") or "Pending",
                }
            )
            if len(pending_requests) >= 5:
                break

    checkins_n = len(checked_in_ids - {""})
    on_leave_n = len(on_leave_today)
    inactive_employees = max(all_employees - active_employees, 0)

    pending_corrections = sum(
        1
        for r in corrections
        if (r.data or {}).get("status") in {"Pending", "In progress"}
    )
    pending_help = sum(
        1
        for r in help_desk
        if (r.data or {}).get("status") in {"Pending", "In progress"}
    )
    approved_leave_open = sum(
        1 for r in leave_rows if (r.data or {}).get("status") == "Approved"
    )

    def _pie_card(card_id, title, subtitle, headline, headline_sub, labels, series, colors):
        # Avoid empty pies
        if not series or sum(series) == 0:
            labels, series = ["No data"], [1]
            colors = ["#c9d9b8"]
        details = [
            {"label": lab, "value": val, "color": colors[i % len(colors)]}
            for i, (lab, val) in enumerate(zip(labels, series))
            if lab != "No data"
        ]
        return {
            "id": card_id,
            "title": title,
            "subtitle": subtitle,
            "headline": headline,
            "headline_sub": headline_sub,
            "details": details,
            "labels": labels,
            "series": series,
            "colors": colors,
        }

    pie_cards = [
        _pie_card(
            "pieAttendance",
            "Today's attendance",
            f"Status for {today.strftime('%d/%m/%Y')}",
            checkins_n,
            "checked in",
            ["Checked in", "Pending check-in", "On leave"],
            [checkins_n, pending_checkin, on_leave_n],
            ["#176344", "#c47a3a", "#3d7a8a"],
        ),
        _pie_card(
            "pieWorkforce",
            "Workforce",
            "Employment status",
            active_employees,
            "active employees",
            ["Active", "Inactive"],
            [active_employees, inactive_employees],
            ["#2d8a56", "#a8a8a8"],
        ),
        _pie_card(
            "pieLeave",
            "Leave overview",
            "Leave covering today & approvals",
            on_leave_n,
            "on leave today",
            ["On leave today", "Pending approval", "Approved (open)"],
            [on_leave_n, len(pending_leave), approved_leave_open],
            ["#3d7a8a", "#c47a3a", "#4fa86f"],
        ),
        _pie_card(
            "pieRequests",
            "Pending requests",
            "Items waiting for HR action",
            len(pending_leave) + pending_corrections + pending_help,
            "total pending",
            ["Leave", "Corrections", "Help desk"],
            [len(pending_leave), pending_corrections, pending_help],
            ["#c47a3a", "#8a5a3a", "#5a7a4a"],
        ),
    ]

    # Activity cards: people list (left) + pie (right)
    checkin_methods = Counter()
    for r in attendance:
        d = r.data or {}
        if d.get("timeIn") and _parse_date(d.get("date")) == today:
            checkin_methods[d.get("method") or "Manual"] += 1
    if not checkin_methods and last_checkins:
        for p in last_checkins:
            checkin_methods[p.get("method") or "Manual"] += 1

    checkout_methods = Counter()
    for r in attendance:
        d = r.data or {}
        if d.get("timeOut") and _parse_date(d.get("date")) == today:
            checkout_methods[d.get("method") or "Manual"] += 1
    if not checkout_methods and last_checkouts:
        for p in last_checkouts:
            checkout_methods[p.get("method") or "Manual"] += 1

    palette = ["#176344", "#2d8a56", "#4fa86f", "#c47a3a", "#3d7a8a", "#8a5a3a"]

    def _activity_pie(counter):
        if not counter or sum(counter.values()) == 0:
            return ["No data"], [1], ["#c9d9b8"]
        labels = list(counter.keys())
        series = [counter[k] for k in labels]
        colors = [palette[i % len(palette)] for i in range(len(labels))]
        return labels, series, colors

    cin_l, cin_s, cin_c = _activity_pie(checkin_methods)
    cout_l, cout_s, cout_c = _activity_pie(checkout_methods)

    activity_cards = [
        {
            "id": "pieLastCheckins",
            "title": "Last check-ins",
            "subtitle": "Latest 5 employees who checked in",
            "empty": "No check-ins recorded yet.",
            "people": last_checkins,
            "avatar": "",
            "mode": "checkin",
            "labels": cin_l,
            "series": cin_s,
            "colors": cin_c,
        },
        {
            "id": "pieLastCheckouts",
            "title": "Last check-outs",
            "subtitle": "Latest 5 employees who checked out",
            "empty": "No check-outs recorded yet.",
            "people": last_checkouts,
            "avatar": "",
            "mode": "checkout",
            "labels": cout_l,
            "series": cout_s,
            "colors": cout_c,
        },
    ]

    return {
        "today_label": today.strftime("%d/%m/%Y"),
        "period_key": period_key,
        "period_label": period_label,
        "kpis": {
            "all_employees": all_employees,
            "active_employees": active_employees,
            "checkins_today": checkins_n if period_key == "today" else period_checkins,
            "pending_checkin": pending_checkin,
            "on_leave_today": on_leave_n,
            "pending_leave": len(pending_leave),
            "checkouts_period": period_checkouts,
        },
        "trend": {
            "labels": trend_labels,
            "employees": trend_employees,
            "checkins": trend_checkins,
            "checkouts": trend_checkouts,
            "on_leave": trend_on_leave,
            "range_label": period_label,
        },
        "pie_cards": pie_cards,
        "activity_cards": activity_cards,
        "last_checkins": last_checkins,
        "last_checkouts": last_checkouts,
        "on_leave": leave_list,
        "pending_requests": pending_requests,
    }
