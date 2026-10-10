# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 端到端自检（需先启动 server.py）。

用法：
    python dgtf_app/server.py            # 另开一个终端
    python dgtf_app/selftest.py [--base http://127.0.0.1:8765]

走完「提交 → 实时日志 → 完成 → 取产物 → 历史检索」全链路（mock，零花费），
并在结束时删掉它自己产生的 mock 产物 —— 自检无副作用。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import outputs_index as oi  # noqa: E402

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(("  \u2713 " if cond else "  \u2717 ") + name + (("  \u2014 " + detail) if detail else ""))


def _get(base: str, path: str):
    with urllib.request.urlopen(base + path, timeout=15) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def _post(base: str, path: str, obj: dict):
    req = urllib.request.Request(
        base + path, data=json.dumps(obj).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    base = ap.parse_args().base

    try:
        with urllib.request.urlopen(base + "/", timeout=10) as r:
            html = r.read().decode("utf-8")
        check("首页可访问且含标题", r.status == 200 and "元DGTF" in html)
        check("首页引用静态资源", "/static/app.js" in html and "/static/style.css" in html)
    except Exception as e:  # noqa: BLE001
        print("服务不可达：", e)
        return 2

    s, cfg = _get(base, "/api/config")
    check("config 返回引擎名", s == 200 and str(cfg.get("engine", "")).endswith(".py"),
          str(cfg.get("engine")))
    check("config 不泄露密钥值", "DGTF_API_KEY" not in json.dumps(cfg))

    s, ol = _get(base, "/api/outputs")
    check("产物列表非空", s == 200 and ol.get("count", 0) > 0, f"共 {ol.get('count')} 份")
    s, sl = _get(base, "/api/outputs?q=" + urllib.parse.quote("数字IC"))
    check("关键词检索命中", s == 200 and sl.get("count", 0) >= 1, f"命中 {sl.get('count')}")
    s, fc = _get(base, "/api/outputs?facets=1")
    check("facets 含四个维度",
          set(fc.keys()) == {"decidability", "orientation", "parallel", "stop"})

    s, t = _post(base, "/api/tasks", {"question": "应用端到端自检 mock", "opts": {"mock": True}})
    check("创建任务返回 id", s == 201 and bool(t.get("id")), str(t.get("id")))
    tid = t["id"]

    off, text, st, folded = 0, "", None, 0
    deadline = time.time() + 60
    while time.time() < deadline:
        _, st = _get(base, f"/api/tasks/{tid}")
        running = st["status"] in ("running", "queued")
        mode = "raw" if running else "filtered"
        if not running and off != 0:        # 跑完 → 重拉整段折叠版
            off = 0
        _, lg = _get(base, f"/api/tasks/{tid}/log?offset={off}&mode={mode}")
        off = lg["offset"]
        if running:
            text += lg["text"]              # 运行中：原始（含留痕）
        else:
            text, folded = lg["text"], lg.get("hidden", 0)
            break
        time.sleep(0.4)

    check("任务跑完", bool(st) and st["status"] == "done",
          (st or {}).get("error") or str((st or {}).get("status")))
    check("实时日志有分层输出", "修行层" in text and "元层" in text, f"{len(text)} 字节")
    check("跑完后日志已折叠留痕/全文框",
          folded > 0 and "留痕" not in text and "【ing 全文】" not in text
          and "【view 全文】" not in text and "不应出现在后台" not in text,
          f"折叠 {folded} 行")
    _, lgr = _get(base, f"/api/tasks/{tid}/log?offset=0&mode=raw")
    check("原始模式保留完整内容（运行中用它）",
          "全量留痕" in lgr["text"], f"{len(lgr['text'])} 字节")
    check("任务定位到产物", bool(st and st.get("output_name")), str((st or {}).get("output_name")))

    if st and st.get("output_name"):
        s, res = _get(base, "/api/tasks/" + tid + "/result")
        check("取回产物正文", s == 200 and len(res["body"]) > 0, f"{len(res['body'])} 字节")
        check("运行归档已生成（log + json）",
              bool(st.get("archive_log")) and bool(st.get("archive_json")),
              f"{st.get('archive_log')} / {st.get('archive_json')}")
        if st.get("archive_log"):
            s, a = _get(base, "/api/archive/" + urllib.parse.quote(st["archive_log"]))
            check("归档 log 可读且保留留痕原文",
                  s == 200 and "全量留痕" in a["body"], f"{len(a['body'])} 字节")
        s, d = _get(base, "/api/outputs/" + urllib.parse.quote(st["output_name"]))
        check("产物详情接口可用", s == 200 and d["name"] == st["output_name"])
        for _n in (st["output_name"], st.get("archive_log"), st.get("archive_json")):
            if not _n:
                continue
            try:
                (oi.OUTPUTS_DIR / _n).unlink()
            except OSError:
                pass
        print("  \u00b7 已清理自检产物与归档：" + st["output_name"])

    print(f"\n结果：PASS {len(PASS)} / FAIL {len(FAIL)}")
    if FAIL:
        print("失败项：" + ", ".join(FAIL))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
