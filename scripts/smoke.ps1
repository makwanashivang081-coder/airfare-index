$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONPATH = (Resolve-Path ".\src").Path
$py = ".\.venv\Scripts\python.exe"

Write-Host "== health =="
$h = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/health"
if (-not $h.ready) { throw "API not ready" }
if ($h.live_data) { throw "Expected fixture mode (live_data=false)" }
if ($h.as_of -ne "2026-09-14") { throw "Unexpected as_of $($h.as_of)" }
"mode=$($h.collection_mode) live=$($h.live_data) obs=$($h.observations)"

Write-Host "== proof improvements =="
$imp = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/proof/improvements"
if ($imp.improvements.Count -lt 5) { throw "Expected 5 improvements" }
"improvements=$($imp.improvements.Count)"

Write-Host "== proof DEL-CCU =="
$p = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/proof/routes/DEL-CCU"
if (-not $p.national) { throw "Missing national proof" }
if ($p.cpi_observations.Count -lt 1) { throw "Missing CPI observations" }
"national=$($p.national.value) cpi_obs=$($p.cpi_observations.Count)"

Write-Host "== overview demo =="
$o = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/analytics/overview"
if (-not $o.demo) { throw "overview missing demo lock" }
if (-not $o.callouts) { throw "overview missing callouts" }
"callouts=$($o.callouts.Count) confidence=$($o.index.confidence)"

Write-Host "SMOKE PASS"
