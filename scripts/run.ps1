# AI-SDLC run script
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Resolve-Path "$ScriptDir\.."

Write-Host "AI-SDLC starting..."
Write-Host ""

$BackendDir = Join-Path $ProjectDir "backend"
$FrontendDir = Join-Path $ProjectDir "frontend"

Write-Host "Starting backend FastAPI..."
Set-Location $BackendDir

if (-not (Test-Path "venv")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv venv
}

& ".\venv\Scripts\Activate.ps1"

if (-not (Test-Path "venv\.deps_installed")) {
    Write-Host "Installing Python dependencies..."
    pip install -q -r requirements.txt
    New-Item -ItemType File -Path "venv\.deps_installed" -Force | Out-Null
}

$Backend = Start-Process powershell `
    -ArgumentList @(
        "-NoExit",
        "-Command",
        "cd `"$BackendDir`"; .\venv\Scripts\Activate.ps1; uvicorn main:app --reload --reload-exclude `"venv/*`" --host 0.0.0.0 --port 8000"
    ) `
    -PassThru

Write-Host "Backend PID: $($Backend.Id)"

Write-Host "Starting frontend React + Vite..."
Set-Location $FrontendDir

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing Node dependencies..."
    npm install
}

$Frontend = Start-Process powershell `
    -ArgumentList @(
        "-NoExit",
        "-Command",
        "cd `"$FrontendDir`"; npm run dev"
    ) `
    -PassThru

Write-Host "Frontend PID: $($Frontend.Id)"

Write-Host ""
Write-Host "Started successfully."
Write-Host "Backend: http://localhost:8000"
Write-Host "Frontend: http://localhost:5173"
Write-Host "API docs: http://localhost:8000/docs"
Write-Host ""
Write-Host "Press Ctrl+C to stop services."

try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host ""
    Write-Host "Stopping services..."

    if ($Backend -and -not $Backend.HasExited) {
        Stop-Process -Id $Backend.Id -Force
    }

    if ($Frontend -and -not $Frontend.HasExited) {
        Stop-Process -Id $Frontend.Id -Force
    }

    Write-Host "Stopped."
}