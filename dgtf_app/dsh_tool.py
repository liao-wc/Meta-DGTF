# -*- coding: utf-8 -*-
"""DSH Agent 的受控工作台工具客户端。

只允许固定动作：fast_gate / acceptance / status。
令牌由工作台在每次 DSH run 启动时通过环境变量下发，不能用于其他接口。
"""
import json
import os
import sys
import urllib.request

ACTIONS = ("fast_gate", "acceptance", "status")
BASE = "http://127.0.0.1:8765/api/dsh/workbench/"


def main():
    action = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if action not in ACTIONS:
        print("用法: python dgtf_app/dsh_tool.py {%s}" % "|".join(ACTIONS))
        return 2
    token = os.environ.get("DGTF_WORKBENCH_TOKEN", "").strip()
    if not token:
        try:
            tf = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "dgtf_memory", "dsh_workbench_token")
            with open(tf, encoding="utf-8") as fh:
                token = fh.read().strip()
        except Exception:
            token = ""
    if not token:
        print("缺少工作台工具令牌（只能由工作台启动的 DSH run 使用）")
        return 2
    req = urllib.request.Request(
        BASE + action, data=b"{}",
        headers={"Content-Type": "application/json",
                 "X-DSH-Workbench": token},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        print("工作台工具调用失败：%s" % exc)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=1))
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
