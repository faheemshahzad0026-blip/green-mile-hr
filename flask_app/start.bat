@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
  call ".venv\Scripts\activate.bat"
  pip install -r requirements.txt
) else (
  call ".venv\Scripts\activate.bat"
)

echo.
echo Green Mile HR Flask
echo Open http://127.0.0.1:5000
echo Super Admin: superadmin / Admin@12345
echo Press Ctrl+C to stop.
echo.
python run.py
pause
