# Setup development venv and install requirements (PowerShell)
param()

$venvDir = Join-Path $PSScriptRoot "..\.venv"
if (-not (Test-Path $venvDir)) {
  Write-Host "Creating virtualenv..."
  python -m venv $venvDir
}

$python = Join-Path $venvDir "Scripts\python.exe"
Write-Host "Installing requirements with: $python"
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $PSScriptRoot "..\requirements.txt")
Write-Host "Done. Activate with: & $venvDir\Scripts\Activate.ps1"
