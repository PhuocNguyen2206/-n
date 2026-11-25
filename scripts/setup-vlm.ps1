# Cài model VLM (Qwen2.5-VL 3B) cho tầng đọc biển số dự phòng trên Windows.
# Chạy một lần sau khi pull code (PowerShell, tại thư mục gốc dự án):
#   powershell -ExecutionPolicy Bypass -File scripts\setup-vlm.ps1
# Muốn lưu model ở ổ khác (ví dụ D:) đặt trước: setx OLLAMA_MODELS D:\OllamaModels
$ErrorActionPreference = "Stop"
$Model = if ($env:VLM_MODEL) { $env:VLM_MODEL } else { "qwen2.5vl:3b" }
$OllamaHost = if ($env:OLLAMA_HOST) { $env:OLLAMA_HOST } else { "http://127.0.0.1:11434" }
if ($OllamaHost -notmatch "^https?://") { $OllamaHost = "http://$OllamaHost" }

$candidates = @(
  (Get-Command ollama -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
  "D:\Tools\Ollama\ollama.exe",
  "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
) | Where-Object { $_ -and (Test-Path $_) }
$Ollama = $candidates | Select-Object -First 1
if (-not $Ollama) {
  Write-Host "Chua co Ollama. Tai bo cai tai https://ollama.com/download roi chay lai script nay."
  exit 1
}

function Test-Ollama { try { Invoke-RestMethod "$OllamaHost/api/tags" -TimeoutSec 3 | Out-Null; $true } catch { $false } }
if (-not (Test-Ollama)) {
  Write-Host "Dang khoi dong Ollama nen..."
  Start-Process -FilePath $Ollama -ArgumentList "serve" -WindowStyle Hidden
  for ($i = 0; $i -lt 30 -and -not (Test-Ollama); $i++) { Start-Sleep -Seconds 1 }
}

Write-Host "Tai model $Model (khoang 3,2 GB, chi tai lan dau)..."
& $Ollama pull $Model
Write-Host "Xong. Kiem tra: http://127.0.0.1:8000/api/v1/model/status -> muc vlm.available = true"
