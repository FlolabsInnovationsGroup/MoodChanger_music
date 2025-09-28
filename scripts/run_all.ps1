# Helper script to run common tasks locally (PowerShell)
# Usage: .\scripts\run_all.ps1 [run|run-mock|test|lint]
param(
  [string]$cmd = "help"
)

$python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

switch ($cmd) {
  "run" { & $python -m uvicorn app:app --reload --port 8001 }
  "run-mock" { $env:MOCK_MODE = '1'; & $python -m uvicorn app:app --reload --port 8001 }
  "test" { $env:MOCK_MODE = '1'; Push-Location (Join-Path $PSScriptRoot ".."); try { & $python -m pytest } finally { Pop-Location } }
  "lint" { & $python -m pip install black -q; & $python -m black --check . }
  default { Write-Host "Usage: run|run-mock|test|lint" }
}
