# Starts backend (:8000), video service (:8001) and dashboard (:5173) in separate windows.
#   .\start.ps1            -> http://localhost:5173 (this laptop only)
#   .\start.ps1 -Https     -> https://<laptop-ip>:5173 for phones on the campus Wi-Fi
#                             (GPS reports and push notifications need HTTPS on phones)
param([switch]$Https)
Set-Location $PSScriptRoot
$root = $PSScriptRoot

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 3
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\video_service'; ..\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001"
$httpsEnv = if ($Https) { "`$env:HTTPS='1'; " } else { "" }
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; $httpsEnv npm run dev"

$scheme = if ($Https) { "https" } else { "http" }
Write-Host "Dashboard: ${scheme}://localhost:5173" -ForegroundColor Green
if ($Https) { Write-Host "Phones: ${scheme}://<this laptop's Wi-Fi IP>:5173 (accept the certificate warning once)" }
