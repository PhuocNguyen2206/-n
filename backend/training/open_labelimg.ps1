param(
    [ValidateSet("train", "val", "test")]
    [string]$Split = "train"
)

$root = Split-Path -Parent $PSScriptRoot
$images = Join-Path $root "datasets\license_plate_vn\images\$Split"
$labels = Join-Path $root "datasets\license_plate_vn\labels\$Split"
$tool = Join-Path $root ".venv\Scripts\labelImg.exe"

if (-not (Test-Path -LiteralPath $tool)) {
    throw "Không tìm thấy LabelImg. Cài dependency của backend trước."
}

New-Item -ItemType Directory -Force -Path $images, $labels | Out-Null
Start-Process -FilePath $tool -ArgumentList @($images, $labels)
