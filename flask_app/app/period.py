"""Shared date-range filter for header + dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import session


PERIOD_OPTIONS = [
    ("today", "Today"),
    ("all", "All"),
    ("7d", "7 days"),
    ("1m", "1 month"),
    ("3m", "3 months"),
    ("6m", "6 months"),
    ("12m", "12 months"),
    ("custom", "Custom"),
]


def dubai_today():
    return (datetime.now(timezone.utc) + timedelta(hours=4)).date()


def _parse(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def get_period_state():
    key = session.get("ui_period") or "today"
    if key not in {k for k, _ in PERIOD_OPTIONS}:
        key = "today"
    custom_from = _parse(session.get("ui_period_from"))
    custom_to = _parse(session.get("ui_period_to"))
    today = dubai_today()

    start = today
    end = today
    label = "Today"

    if key == "all":
        start = None
        end = today
        label = "All time"
    elif key == "7d":
        start = today - timedelta(days=6)
        label = "Last 7 days"
    elif key == "1m":
        start = today - timedelta(days=29)
        label = "Last 1 month"
    elif key == "3m":
        start = today - timedelta(days=89)
        label = "Last 3 months"
    elif key == "6m":
        start = today - timedelta(days=179)
        label = "Last 6 months"
    elif key == "12m":
        start = today - timedelta(days=364)
        label = "Last 12 months"
    elif key == "custom":
        start = custom_from or today
        end = custom_to or today
        if start > end:
            start, end = end, start
        label = f"{start.strftime('%d/%m/%Y')} – {end.strftime('%d/%m/%Y')}"
    else:
        key = "today"
        start = today
        end = today
        label = "Today"

    return {
        "key": key,
        "label": label,
        "start": start,
        "end": end,
        "custom_from": (custom_from or today).isoformat(),
        "custom_to": (custom_to or today).isoformat(),
        "options": PERIOD_OPTIONS,
    }


def set_period(key: str, custom_from: str | None = None, custom_to: str | None = None):
    if key not in {k for k, _ in PERIOD_OPTIONS}:
        key = "today"
    session["ui_period"] = key
    if key == "custom":
        if custom_from:
            session["ui_period_from"] = custom_from[:10]
        if custom_to:
            session["ui_period_to"] = custom_to[:10]
    return get_period_state()
