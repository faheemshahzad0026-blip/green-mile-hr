# Green Mile HR (Flask)

Multi-tenant Flask HR app for shared cPanel hosting and local testing.

## Roles

- **Super Admin** — same admin UI as agency admin, plus Create/Manage Agencies and Create Users; can view all agencies
- **Agency Admin / Staff** — manage own agency staff and employees only; branded logo/name
- **Employee** — ID + 6-digit PIN; web or APK download

Inactive agencies cannot log in.

## Local setup (Windows)

Use **Python 3.12 or 3.13** if possible. Python **3.14** works if you install deps from this repo’s `requirements.txt` (needs Pillow 12+ for prebuilt Windows wheels). Do not use Pillow 11 on 3.14 — pip will try to compile it and fail without zlib.

Double-click or run:

```bat
flask_app\start.bat
```

Or PowerShell:

```powershell
cd flask_app
.\start.ps1
```

Open http://127.0.0.1:5000 — press Ctrl+C to stop.

Default Super Admin (from `.env`):

- Username: `superadmin`
- Password: `Admin@12345`

## cPanel

1. Upload `flask_app` contents
2. Create Python app pointing `passenger_wsgi.py`
3. Set env vars from `.env.example`
4. Install requirements into the app virtualenv

## APK

1. Set Android `BASE` URL to your HTTPS domain
2. Build signed APK
3. Copy to `app/static/apk/green-mile-attendance.apk`
