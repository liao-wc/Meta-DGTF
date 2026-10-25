# -*- coding: utf-8 -*-
"""给 engine / app / 其它脚本用的本地模型 HTTP 客户端（零依赖，stdlib）。

用法（服务需先由 scripts/local_model/start_local_llm.ps1 启动）：

    from dgtf_local_llm.client import LocalLLMClient
    cli = LocalLLMClient()                      # 默认 127.0.0.1:8772
    r = cli.generate("self_check_min", text=view_json_text, timeout=60)
    if r["ok"]:
        print(r["json"], r["confidence"], r["ms"])
    else:
        print("本地不可用，回退云端：", r["error"])

设计：任何失败（连接不上 / 503 / 超时）都返回结构化 dict 而不是抛异常，
调用方可以直接拿 `ok` 决定是否回退云 API（级联/QC 门控）。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8772"


class LocalLLMClient:
    def __init__(self, base_url: str = DEFAULT_URL, timeout: float = 90.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ---------- 健康检查 ----------
    def health(self) -> dict:
        try:
            with urllib.request.urlopen(self.base_url + "/health",
                                        timeout=3) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            return {"ok": False, "status": "unreachable",
                    "error": f"{type(e).__name__}: {e}"}

    def is_ready(self) -> bool:
        h = self.health()
        return bool(h.get("ok")) and h.get("status") == "ready"

    # ---------- 生成 ----------
    def generate(self, stage: str, text: str | None = None,
                 messages: list | None = None,
                 max_new_tokens: int | None = None,
                 temperature: float = 0.0,
                 timeout: float | None = None,
                 entry: str | None = None,
                 variant: str | None = None) -> dict:
        payload: dict = {"stage": stage,
                         "timeout": timeout if timeout is not None
                         else self.timeout}
        if text is not None:
            payload["text"] = text
        if messages is not None:
            payload["messages"] = messages
        if max_new_tokens is not None:
            payload["max_new_tokens"] = int(max_new_tokens)
        payload["temperature"] = float(temperature)
        if entry is not None:
            payload["entry"] = str(entry)
        if variant is not None:
            payload["variant"] = str(variant)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/generate", data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST")
        try:
            with urllib.request.urlopen(
                    req, timeout=(timeout or self.timeout) + 5) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                return {"ok": False, "error": {"code": "HTTP",
                                               "message": f"HTTP {e.code}"}}
        except Exception as e:
            return {"ok": False, "error": {"code": "UNREACHABLE",
                                           "message": f"{type(e).__name__}: {e}"}}


if __name__ == "__main__":
    import sys
    cli = LocalLLMClient()
    h = cli.health()
    print(json.dumps(h, ensure_ascii=False, indent=1))
    stage = sys.argv[1] if len(sys.argv) > 1 else "self_check_min"
    r = cli.generate(stage, text="【锚点】\n测试", max_new_tokens=32)
    print(json.dumps({k: r.get(k) for k in ("ok", "stage", "text", "json",
                                            "ms", "confidence", "error")},
                     ensure_ascii=False, indent=1))
