# AI-SDLC run script (随机端口)
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Resolve-Path "$ScriptDir\.."

Write-Host "AI-SDLC starting..."
Write-Host ""

# Find free ports
function Find-FreePort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = $listener.LocalEndpoint.Port
    $listener.Stop()
    return $port
}

$env:BACKEND_PORT = Find-FreePort
$env:FRONTEND_PORT = Find-FreePort

Write-Host "Allocated ports: Backend=$($env:BACKEND_PORT), Frontend=$($env:FRONTEND_PORT)"

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
        "cd `"$BackendDir`"; .\venv\Scripts\Activate.ps1; uvicorn main:app --reload --reload-exclude `"venv/*`" --host 127.0.0.1 --port $($env:BACKEND_PORT)"
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
        "`$env:BACKEND_PORT=$($env:BACKEND_PORT); `$env:FRONTEND_PORT=$($env:FRONTEND_PORT); cd `"$FrontendDir`"; npm run dev"
    ) `
    -PassThru

Write-Host "Frontend PID: $($Frontend.Id)"

Write-Host ""
Write-Host "Started successfully."
Write-Host "Backend: http://localhost:$($env:BACKEND_PORT)"
Write-Host "Frontend: http://localhost:$($env:FRONTEND_PORT)"
Write-Host "API docs: http://localhost:$($env:BACKEND_PORT)/docs"
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
