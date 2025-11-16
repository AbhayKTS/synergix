# setup_env.ps1
# Creates a virtual environment in .venv and installs requirements.
# Run in PowerShell (Windows):
#   .\setup_env.ps1

$ErrorActionPreference = 'Stop'

$venvPath = Join-Path $PSScriptRoot '.venv'
if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at $venvPath"
    python -m venv $venvPath
} else {
    Write-Host "Virtual environment already exists at $venvPath"
}

$pythonExe = Join-Path $venvPath 'Scripts\python.exe'
$pipExe = Join-Path $venvPath 'Scripts\pip.exe'

if (-not (Test-Path $pythonExe)) {
    Write-Error "Python executable not found in virtualenv. Ensure 'python' is on PATH and venv creation succeeded."
    exit 1
}

Write-Host "Installing dependencies from requirements.txt..."
& $pipExe install --upgrade pip
& $pipExe install -r "$(Join-Path $PSScriptRoot 'requirements.txt')"

Write-Host "Done. To use the venv in PowerShell run:`n  & '$venvPath\Scripts\Activate.ps1'"
