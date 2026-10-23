# -*- coding: utf-8 -*-
"""查账户余额（只读）。用法：python _balance.py"""
import json
import os
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> None:
    load_dotenv(HERE / ".env")
    key = os.environ.get("DGTF_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        print("没找到 key（试过 DGTF_API_KEY / OPENAI_API_KEY）")
        return
    base = "https://api.deepseek.com"
    for line in (HERE / "dgtf_config.yaml").read_text(
            encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("base_url"):
            base = s.split(":", 1)[1].strip().strip('"').strip("'")
            break
    print("base_url:", base)
    req = urllib.request.Request(
        base.rstrip("/") + "/user/balance",
        headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(json.dumps(json.loads(r.read().decode("utf-8")),
                             ensure_ascii=False, indent=2)[:800])
    except Exception as e:
        print("查询失败:", type(e).__name__, e)


if __name__ == "__main__":
    main()
