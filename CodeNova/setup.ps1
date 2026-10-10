# One-time setup on Windows (PowerShell):   .\setup.ps1
# Needs: Python 3.10-3.12, Node.js 18+. Docker Desktop is optional (for PostgreSQL).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    # Fill in random secrets so the app is safe by default
    $secret = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | ForEach-Object { [char]$_ })
    $svc = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 40 | ForEach-Object { [char]$_ })
    (Get-Content .env) -replace '^SECRET_KEY=.*', "SECRET_KEY=$secret" -replace '^SERVICE_API_KEY=.*', "SERVICE_API_KEY=$svc" | Set-Content .env
    Write-Host "Created .env - open it and set ADMIN_EMAILS and your SMTP (Gmail) details." -ForegroundColor Yellow
}

# Database: PostgreSQL in Docker if available, otherwise SQLite
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "Starting PostgreSQL in Docker..."
    docker compose up -d db
} else {
    Write-Host "Docker not found - switching .env to SQLite (fine for a single laptop)." -ForegroundColor Yellow
    (Get-Content .env) -replace '^DATABASE_URL=postgresql.*', 'DATABASE_URL=sqlite:///./campus.db' | Set-Content .env
}

Write-Host "Creating Python virtual environment (.venv)..."
if (-not (Test-Path .venv)) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r backend\requirements.txt -r video_service\requirements.txt -r backend\requirements-ml.txt

Write-Host "Generating browser push keys..."
$envText = Get-Content .env -Raw
if ($envText -match 'VAPID_PUBLIC_KEY=\s*\r?\n') {
    $keys = & $py scripts\generate_vapid_keys.py
    $pub = ($keys | Select-String 'VAPID_PUBLIC_KEY=').ToString()
    $priv = ($keys | Select-String 'VAPID_PRIVATE_KEY=').ToString()
    (Get-Content .env) -replace '^VAPID_PUBLIC_KEY=.*', $pub -replace '^VAPID_PRIVATE_KEY=.*', $priv | Set-Content .env
}

Write-Host "Downloading model weights..."
Push-Location video_service
& "..\.venv\Scripts\python.exe" download_weights.py
Pop-Location

Write-Host "Installing frontend packages..."
Push-Location frontend
npm install
Pop-Location

Write-Host "`nSetup finished. Start everything with:  .\start.ps1" -ForegroundColor Green
