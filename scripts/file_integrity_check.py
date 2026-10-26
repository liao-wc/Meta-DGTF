# -*- coding: utf-8 -*-
"""关键文件完整性检查：防截断/防语法损坏/防关键功能回退。"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from safe_file_ops import verify  # noqa: E402

MARKERS = {
    "dgtf_app/server.py": [
        ("App 全方位检查", "App 全方位检查"),
        ("本轮真跑轮换", "真跑轮换"),
        ("guard_receipt.py", "完成回执"),
        ("/api/status/sidebar", "侧边栏接口"),
        ("_dsh_clean_title", "DSH 标题"),
    ],
    "dgtf_app/static/app.js": [
        ("renderEnvInfo", "北斗状态"),
        ("agentRenderDsh", "DSH 会话"),
        ("newDshCurrentConversation", "DSH 新对话"),
    ],
    "dgtf_app/static/style.css": [(".env-beidou", "北斗星链")],
    "dgtf_app/static/index.html": [("app.js", "应用脚本")],
    "dgtf_app/engine_runner.py": [("def ", "引擎运行器")],
    "dgtf_app/v2_online.py": [("def choose", "在线策略")],
}
MIN_SIZE = {"dgtf_app/server.py": 350000, "dgtf_app/static/app.js": 250000,
            "dgtf_app/static/style.css": 60000, "dgtf_app/static/index.html": 20000,
            "dgtf_app/engine_runner.py": 30000, "dgtf_app/v2_online.py": 3000}


def main():
    out = []
    bad = 0
    for x in verify():
        p = Path(x["file"])
        rec = dict(x)
        if p.is_file():
            if p.stat().st_size < MIN_SIZE.get(x["file"], 1):
                rec.update(ok=False, error="file too small (%d)" % p.stat().st_size)
            else:
                text = p.read_text(encoding="utf-8", errors="replace")
                for needle, label in MARKERS.get(x["file"], []):
                    if needle not in text:
                        rec.update(ok=False, error="missing marker: " + label)
                        break
        if not rec["ok"]:
            bad += 1
        out.append(rec)
    doc = {"ok": bad == 0, "files": out, "bad": bad}
    dst = ROOT / "docs" / "file_integrity_latest.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
