#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 F.4] 跑 P3/P4/P5/P6 探针的 before/after，**由本脚本写文件**。

★ 为什么不用 shell 的 `>`：本机沙箱里 `>` 重定向偶发写空 / 写旧内容
  （实测 p3/p4 的 after 文件停在上一版），导致「对照」变成假的。
  这里用 subprocess 抓 stdout，剥掉 jieba 的启动日志（取第一个 `{` 起），
  `json.loads` 校验后再 `write_bytes` —— 文件内容必须能被解析成 dict 才算数。

用法：python _run_probes_p3456.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PAIRS = [
    (3, "_baseline_v1220.py"),
    (4, "_baseline_v12177.py"),
    (5, "元DGTF-V1.22.1-rc2.py"),
    (6, "元DGTF-V1.22.1-rc2.py"),
]
AFTER = "元DGTF-V1.22.1.py"


def _run(probe: str, src: str) -> dict:
    r = subprocess.run([sys.executable, probe, src],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    out = r.stdout or ""
    i = out.find("{")
    if i < 0:
        raise SystemExit(probe + " 没输出 JSON；stdout=" + out[:200]
                         + " stderr=" + (r.stderr or "")[:200])
    return json.loads(out[i:])


def main() -> int:
    for n, before_src in PAIRS:
        probe = "_probe_v1221_p" + str(n) + ".py"
        for tag, src in (("before", before_src), ("after", AFTER)):
            d = _run(probe, src)
            assert isinstance(d, dict) and d, probe + " " + tag + " 读数不是非空 dict"
            tgt = Path("_probe_v1221_p" + str(n) + "_" + tag + ".txt")
            tgt.write_bytes(json.dumps(d, ensure_ascii=False, indent=2)
                            .encode("utf-8"))
            print("  ✓ " + tgt.name + "（" + src + "，键 " + str(len(d)) + " 个）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
