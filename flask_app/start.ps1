Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  Write-Host "Creating virtual environment..."
  python -m venv .venv
  & .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
} else {
  & .\.venv\Scripts\Activate.ps1
}

Write-Host ""
Write-Host "Green Mile HR Flask"
Write-Host "Open http://127.0.0.1:5000"
Write-Host "Super Admin: superadmin / Admin@12345"
Write-Host "Press Ctrl+C to stop."
Write-Host ""
python run.py
