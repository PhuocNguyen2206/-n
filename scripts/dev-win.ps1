# Chạy backend + frontend trên Windows (tương đương scripts/dev-mac.sh).
#   powershell -ExecutionPolicy Bypass -File scripts\dev-win.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Khong tim thay $Python. Tao venv: cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt" }

$api = Start-Process -FilePath $Python -ArgumentList "-m","uvicorn","app.main:app","--reload","--host","127.0.0.1","--port","8000" `
  -WorkingDirectory (Join-Path $Root "backend") -PassThru -NoNewWindow
try {
  Push-Location (Join-Path $Root "frontend")
  npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
} finally {
  Pop-Location
  if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force }
}
