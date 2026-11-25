#!/bin/bash
# Cài model VLM (Qwen2.5-VL 3B) cho tầng đọc biển số dự phòng trên macOS/Linux.
# Chạy một lần sau khi pull code:  bash scripts/setup-vlm.sh
set -euo pipefail
MODEL="${VLM_MODEL:-qwen2.5vl:3b}"
HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Chưa có Ollama. Cài bằng một trong hai cách rồi chạy lại script này:"
  echo "  - Tải ứng dụng: https://ollama.com/download"
  echo "  - Hoặc Homebrew: brew install ollama"
  exit 1
fi

if ! curl -fsS "$HOST/api/tags" >/dev/null 2>&1; then
  echo "Đang khởi động Ollama nền..."
  (ollama serve >/tmp/ollama-serve.log 2>&1 &)
  for _ in $(seq 1 30); do curl -fsS "$HOST/api/tags" >/dev/null 2>&1 && break; sleep 1; done
fi

echo "Tải model $MODEL (khoảng 3,2 GB, chỉ tải lần đầu)..."
ollama pull "$MODEL"
echo "Xong. Kiểm tra: http://127.0.0.1:8000/api/v1/model/status -> mục \"vlm\".\"available\" = true"
