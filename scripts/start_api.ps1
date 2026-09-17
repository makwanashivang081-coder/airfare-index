$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
$env:PYTHONPATH = (Resolve-Path ".\src").Path
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Missing venv at $py — run: python -m venv .venv && .\.venv\Scripts\python -m pip install -e `".[dev]`" tzdata" }

# free 8000
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {
  Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

Write-Host "Starting AirPriceX on http://127.0.0.1:8000 ..."
& $py -m uvicorn apix.api.main:app --host 127.0.0.1 --port 8000
