# Chạy backend + frontend trên Windows (tương đương scripts/dev-mac.sh).
#   powershell -ExecutionPolicy Bypass -File scripts\dev-win.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Khong tim thay $Python. Tao venv: cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt" }

# API chạy trong cửa sổ riêng (thu nhỏ): khi --reload khởi động lại, Windows gửi Ctrl+C
# cho cả cửa sổ console; nếu dùng chung cửa sổ, lệnh npm của frontend cũng bị tắt theo.
$api = Start-Process -FilePath $Python -ArgumentList "-m","uvicorn","app.main:app","--reload","--host","127.0.0.1","--port","8000" `
  -WorkingDirectory (Join-Path $Root "backend") -PassThru -WindowStyle Minimized
try {
  Push-Location (Join-Path $Root "frontend")
  npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
} finally {
  Pop-Location
  # /T tắt cả tiến trình con của bộ reload.
  if ($api -and -not $api.HasExited) { taskkill /PID $api.Id /T /F | Out-Null }
}
