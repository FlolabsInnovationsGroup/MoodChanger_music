# Install test deps (into venv if present) and run pytest
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

# Run tests in mock mode by default so tests that rely on MOCK_MODE work locally
$env:MOCK_MODE = '1'

Write-Host "Installing test deps and running pytest with: $python"
& $python -m pip install pytest httpx -q
Push-Location $PSScriptRoot
try {
	& $python -m pytest -q
} finally {
	Pop-Location
}
