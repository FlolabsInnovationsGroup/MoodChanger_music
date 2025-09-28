# Run the app in MOCK_MODE (PowerShell)
# Usage: Open PowerShell in repository root and run: .\run_mock.ps1

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

$env:MOCK_MODE = '1'
Write-Host "Starting app in MOCK_MODE using: $python"
& $python -m uvicorn app:app --reload --port 8001
