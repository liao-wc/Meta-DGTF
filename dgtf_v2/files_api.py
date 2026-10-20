# -*- coding: utf-8 -*-
"""DeepSeek Files API：图片上传/引用 file_id（multipart /files）。"""
from __future__ import annotations
import json, os, uuid
from pathlib import Path
import urllib.request

BASE = "https://api.deepseek.com"


def _key() -> str:
    return os.environ.get("DGTF_API_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", "")


def upload(path, purpose: str = "user_data", timeout: float = 120) -> dict:
    p = Path(str(path))
    if not p.is_file():
        return {"error": "not_found"}
    boundary = "----DGTF" + uuid.uuid4().hex
    data = p.read_bytes()
    head = ("--%s\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\n%s\r\n"
            "--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n"
            % (boundary, purpose, boundary, p.name)).encode("utf-8")
    tail = ("\r\n--%s--\r\n" % boundary).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/files", data=head + data + tail,
        headers={"Authorization": "Bearer " + _key(),
                 "Content-Type": "multipart/form-data; boundary=" + boundary})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, e)}


def delete(file_id: str, timeout: float = 30) -> dict:
    req = urllib.request.Request(
        BASE + "/files/" + str(file_id), method="DELETE",
        headers={"Authorization": "Bearer " + _key()})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, e)}


def list_files(limit: int = 20) -> dict:
    req = urllib.request.Request(
        BASE + "/files?limit=%d" % max(1, min(1000, int(limit))),
        headers={"Authorization": "Bearer " + _key()})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, e)}


def file_block(file_id: str) -> dict:
    return {"type": "file", "file_id": str(file_id)}
