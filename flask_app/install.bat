@echo off
cd /d "%~dp0"
echo.
echo === Green Mile HR — install dependencies ===
echo.

python -c "import sys; print('Python', sys.version); raise SystemExit(0 if sys.version_info>=(3,12) else 1)"
if errorlevel 1 (
  echo ERROR: Need Python 3.12+. Python 3.14 needs this new requirements.txt.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
)

call ".venv\Scripts\activate.bat"

echo Upgrading pip...
python -m pip install --upgrade pip

echo Removing old Pillow if present...
python -m pip uninstall -y Pillow 2>nul

echo Installing Pillow 12.3.0 wheel only (no source build)...
python -m pip install --only-binary=:all: "Pillow==12.3.0"
if errorlevel 1 (
  echo.
  echo Pillow wheel install failed.
  echo Install Python 3.12 or 3.13 from https://www.python.org/downloads/
  echo then delete the .venv folder and run install.bat again.
  pause
  exit /b 1
)

echo Installing remaining packages...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Install failed.
  pause
  exit /b 1
)

echo.
echo Done. Run start.bat to launch the app.
pause
