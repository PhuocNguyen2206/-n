# Bật bản chạy thật + link công khai trên máy Windows làm máy chủ (Docker Desktop).
#   powershell -ExecutionPolicy Bypass -File scripts\deploy-win.ps1   (hướng dẫn: deploy\HUONG_DAN_WINDOWS.md)
# Chạy lại script này sau mỗi lần cập nhật code (git pull) hoặc sau khi khởi động lại máy để lấy link mới.
# Mỗi lần chạy ghi một dòng vào deploy\LICH_SU_DEPLOY.csv (mở được bằng Excel). Thêm ghi chú: -GhiChu "sua loi camera"
param([string]$GhiChu = "")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# Mã commit đang deploy; SuaChuaCommit = "co" nghĩa là code trên máy còn thay đổi chưa commit.
$Commit = ""; $Dirty = ""
try {
  $Commit = "$(git log -1 --format='%h %s')"
  $Dirty = if (git status --porcelain --untracked-files=normal) { "co" } else { "khong" }
} catch { }

function Add-DeployHistory([string]$Result, [string]$Link = "", [string]$Detail = "") {
  [pscustomobject]@{
    ThoiGian = (Get-Date -Format "yyyy-MM-dd HH:mm:ss"); KetQua = $Result; Commit = $Commit; SuaChuaCommit = $Dirty
    LinkTrycloudflare = $Link; GhiChu = (@($GhiChu, $Detail) | Where-Object { $_ }) -join " | "
  } | Export-Csv -Path (Join-Path $Root "deploy\LICH_SU_DEPLOY.csv") -Append -NoTypeInformation -Encoding UTF8
}

# Lỗi ở bất kỳ bước nào cũng được ghi lại rồi mới dừng.
trap { Add-DeployHistory "LOI" "" $_.Exception.Message; break }

docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop chua chay. Mo Docker Desktop, doi bieu tuong ca voi dung yen roi chay lai." }

foreach ($model in "chars_best.pt") {
  if (-not (Test-Path (Join-Path $Root "backend\models\$model"))) { throw "Thieu backend\models\$model" }
}
if (-not (Test-Path (Join-Path $Root "backend\models\license_plate.pt")) -and -not (Test-Path (Join-Path $Root "backend\models\plate_best.pt"))) {
  throw "Thieu backend\models\license_plate.pt hoac plate_best.pt"
}
try { Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 3 | Out-Null }
catch { Write-Warning "Chua thay Ollama: he thong van chay nhung khong co VLM. Mo app Ollama roi chay: ollama pull qwen2.5vl:3b" }

# .env: dia chi truy cap trong mang noi bo (tao mot lan; sua tay neu doi IP).
$EnvFile = Join-Path $Root ".env"
if (-not (Test-Path $EnvFile)) {
  $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback|vEthernet|WSL|Docker" -and $_.IPAddress -notlike "169.254.*" } | Select-Object -First 1).IPAddress
  $content = "SITE_ADDRESS=localhost, $ip`nDEFAULT_SNI=$ip`n"
  [System.IO.File]::WriteAllText($EnvFile, $content, (New-Object System.Text.UTF8Encoding $false))
  Write-Host "Da tao .env voi IP $ip"
}

$Compose = @("compose", "-f", "docker-compose.prod.yml", "-f", "docker-compose.tunnel.yml")
& docker @Compose up -d --build
if ($LASTEXITCODE -ne 0) { throw "docker compose that bai" }

Write-Host "Dang kiem tra API..."
$healthy = $false
for ($i = 0; $i -lt 30 -and -not $healthy; $i++) {
  Start-Sleep -Seconds 2
  try { $healthy = (Invoke-RestMethod http://127.0.0.1:8080/api/v1/health -TimeoutSec 3).status -eq "ok" } catch { }
}

Write-Host "Dang lay link cong khai..."
$link = $null
for ($i = 0; $i -lt 30 -and -not $link; $i++) {
  Start-Sleep -Seconds 2
  $link = (& docker @Compose logs tunnel 2>&1 | Select-String -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -AllMatches | ForEach-Object { $_.Matches.Value } | Select-Object -Last 1)
}
$ip = (Get-Content $EnvFile | Select-String "DEFAULT_SNI=(.+)").Matches.Groups[1].Value
Write-Host ""
Write-Host "Trong mang noi bo : https://$ip"
if ($link) { Write-Host "Link cong khai    : $link" } else { Write-Host "Chua lay duoc link, xem: docker compose -f docker-compose.prod.yml -f docker-compose.tunnel.yml logs tunnel" }

if ($healthy) { Add-DeployHistory "THANH CONG" "$link" }
else {
  Add-DeployHistory "LOI" "$link" "API khong tra loi sau 60 giay"
  Write-Warning "API khong tra loi. Xem log: docker compose -f docker-compose.prod.yml logs api"
}
Write-Host "Lich su deploy    : deploy\LICH_SU_DEPLOY.csv"
