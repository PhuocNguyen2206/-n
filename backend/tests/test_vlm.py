"""Kiểm thử tầng VLM (Ollama) và luật kết hợp OCR + VLM, không cần GPU hay Ollama thật."""

import json

import httpx
import numpy as np
import pytest

from app.services.vlm import VlmPlateReader, is_valid_vn_plate, normalize_plate


def make_reader(handler, **kwargs):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return VlmPlateReader(host="http://ollama.test", model="qwen2.5vl:3b", enabled=True, timeout=5, client=client, **kwargs)


def ollama_handler(response_text="59-F1\n138.60", models=("qwen2.5vl:3b",), fail_generate=False):
    calls = {"generate": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": name} for name in models]})
        if request.url.path == "/api/generate":
            calls["generate"] += 1
            if fail_generate:
                return httpx.Response(500, json={"error": "boom"})
            body = json.loads(request.content)
            assert body["model"] == "qwen2.5vl:3b" and body["images"] and body["options"]["temperature"] == 0
            return httpx.Response(200, json={"response": response_text})
        return httpx.Response(404)

    return handler, calls


IMAGE = np.full((120, 160, 3), 255, np.uint8)


@pytest.mark.parametrize("text,valid", [("59F113860", True), ("51F79512", True), ("50XA5535", True), ("30F5204", True),
                                        ("3T677141", False), ("59FFLMJUGU", False), ("", False), (None, False)])
def test_vn_plate_format(text, valid):
    assert is_valid_vn_plate(text) is valid


def test_normalize_plate():
    assert normalize_plate("59-F1\n138.60") == "59F113860"
    assert normalize_plate("51h-094.88") == "51H09488"


def test_read_plate_ok():
    handler, calls = ollama_handler()
    reading = make_reader(handler).read_plate(IMAGE)
    assert reading.plate == "59F113860" and calls["generate"] == 1


def test_read_plate_rejects_invalid_format():
    handler, _ = ollama_handler(response_text="I cannot read this plate")
    reading = make_reader(handler).read_plate(IMAGE)
    assert reading is not None and reading.plate is None


def test_model_missing_means_unavailable():
    handler, calls = ollama_handler(models=("llama3:8b",))
    reader = make_reader(handler)
    assert reader.status()["available"] is False and "ollama pull" in reader.status()["message"]
    assert reader.read_plate(IMAGE) is None and calls["generate"] == 0


def test_ollama_offline_returns_none():
    def handler(request):
        raise httpx.ConnectError("refused")
    reader = make_reader(handler)
    assert reader.status()["available"] is False
    assert reader.read_plate(IMAGE) is None


def test_generate_error_returns_none():
    handler, _ = ollama_handler(fail_generate=True)
    assert make_reader(handler).read_plate(IMAGE) is None


def test_disabled():
    handler, calls = ollama_handler()
    reader = VlmPlateReader(enabled=False, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert reader.status()["enabled"] is False and reader.read_plate(IMAGE) is None and calls["generate"] == 0


def test_busy_reader_skips_instead_of_queueing():
    handler, calls = ollama_handler()
    reader = make_reader(handler)
    reader._busy.acquire()
    try:
        assert reader.read_plate(IMAGE) is None
    finally:
        reader._busy.release()
    assert calls["generate"] == 0
