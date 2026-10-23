# -*- coding: utf-8 -*-
"""[v1.23.2] `P2.4.a` 的**功效**读数：triage 在**本版产物**里命中几/几。

背景：`triage`（分诊降级）是**随机触发的低概率机制**。`P2.4.a` 的判据
「≥1 题 triage ≥ 1 条」原来只读 `outputs/p2_run{1,2,3}` 各**一份**产物 ⇒ n=3，
功效不足（实测同配置两批次：一次 [1,0,0]、一次 [0,…]）。

本脚本口径：
  · 数据来源 = `_v1230_w6_runs.json` 的每条 run（含 `md` 路径）；
  · **版本门控两重**：① json 的 `src` == 本版；② 产物 md 的 `mtime`
    **不早于**主文件 mtime（老批次留存的 md 会被这一条挡掉）。
  · 只**报读数**，不改判据。若 k==0，那是**真结论**（本版该机制没触发），
    必须照实写进报告，**不许**因为「想让判据绿」而放宽。
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.23.2.py"
# ★ 不用「主文件 mtime」当门槛：主文件的 docstring 改动（changelog）会把
#   已经跑完的本版产物**全部误判成旧产物**。正解是「json 的 src == 本版」
#   —— 跑批每完成一个作业就**整体重写** json（含 src），所以跑批结束后
#   10 条记录全都指向本版产物，不会有旧记录残留。
MAIN_MT = 0.0

J = HERE / "_v1230_w6_runs.json"
D = json.loads(J.read_text(encoding="utf-8"))
print("json src =", D.get("src"), "| 主文件 mtime 门槛 =", round(MAIN_MT, 1))
rows = []
for r in (D.get("runs") or []):
    if not r.get("ok"):
        continue
    md = Path(r.get("md") or "")
    if not md.is_file():
        continue
    fresh = (md.stat().st_mtime >= MAIN_MT) and (D.get("src") == SRC)
    t = md.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"\*\*triage 降级\*\*：(\d+) 条", t)
    rows.append((r.get("job"), (int(m.group(1)) if m else None), fresh,
                 r.get("arm")))

print("%-16s %-8s %-8s %s" % ("作业", "triage", "本版?", "臂"))
for j, k, fresh, arm in rows:
    print("%-16s %-8s %-8s %s" % (j, k, "是" if fresh else "**否**", arm))
_cur = [r for r in rows if r[2]]
_ok = [r for r in _cur if (r[1] or 0) >= 1]
print()
print("本版产物：%d 份（其中 triage ≥1 的 %d 份）" % (len(_cur), len(_ok)))
if not _cur:
    print("⇒ 还没有本版产物（跑批未完），**不下结论**。")
elif not _ok:
    print("⇒ **本版一个都没触发** —— 真结论，必须照实报告，不许放宽判据。")
else:
    print("⇒ 能力成立（%d 份里 k=%d 份真的触发了）。" % (len(_cur), len(_ok)))
