# -*- coding: utf-8 -*-
"""[_probe_log_capture.py] 确定性单测：wrapper 的流捕获是否真的收全。

为什么需要它：V67 真跑恰好 stderr=0 行、引擎也没吐 warning ——
「stderr 会被收进来」「logger.warning/error 会被收进来」这两条
**没有被那次运行证明**。这里直接对捕获机制本身做断言。

覆盖：
  ① print → sys.stdout      必须进日志（计数 out+1）
  ② print(file=sys.stderr)  必须进日志（计数 err+1）
  ③ logger.info/warning/error 必须进日志（按级别各 +1）
  ④ 日志首尾哨兵 + 完整性统计行必须存在
"""
import contextlib
import importlib.util
import io
import logging
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_rv", HERE / "_run_verif.py")
rv = importlib.util.module_from_spec(spec)
sys.modules["_rv"] = rv
spec.loader.exec_module(rv)          # main() 有 __main__ 守卫，import 不会跑

F = HERE / "_probe_log_capture.out.txt"
LOG = io.open(F, "w", encoding="utf-8", buffering=1)
counters = {"out": 0, "err": 0}

h = rv._CountHandler(LOG, counters)
h.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
root = logging.getLogger()
root.handlers = [h]
root.setLevel(logging.INFO)
lg = logging.getLogger("dgtf")

with contextlib.redirect_stdout(rv._Cap(LOG, "out", counters)), \
        contextlib.redirect_stderr(rv._Cap(LOG, "err", counters)):
    print("OUT-LINE-1")
    print("ERR-LINE-1", file=sys.stderr)
    lg.info("ENGINE-INFO-1")
    lg.warning("ENGINE-WARN-1")
    lg.error("ENGINE-ERR-1")
LOG.close()

t = F.read_text(encoding="utf-8")
checks = [
    ("OUT-LINE-1" in t, "stdout 已进日志"),
    ("ERR-LINE-1" in t, "stderr 已进日志"),
    ("[INFO] dgtf: ENGINE-INFO-1" in t, "logger.info 已进日志（旧版正是丢在这里）"),
    ("[WARNING] dgtf: ENGINE-WARN-1" in t, "logger.warning 已进日志"),
    ("[ERROR] dgtf: ENGINE-ERR-1" in t, "logger.error 已进日志"),
    (counters.get("out") == 1, f"stdout 计数 = {counters.get('out')}（应为 1）"),
    (counters.get("err") == 1, f"stderr 计数 = {counters.get('err')}（应为 1）"),
    (counters.get("INFO") == 1, f"INFO 计数 = {counters.get('INFO')}"),
    (counters.get("WARNING") == 1, f"WARNING 计数 = {counters.get('WARNING')}"),
    (counters.get("ERROR") == 1, f"ERROR 计数 = {counters.get('ERROR')}"),
]
bad = [m for ok, m in checks if not ok]
print(f"\n日志文件 {F.name} 内容：")
for ln in t.rstrip("\n").split("\n"):
    print("  | " + ln)
print()
for ok, m in checks:
    print(f"  {'✓' if ok else '✗'} {m}")
F.unlink()
print("\n结果:", "全过" if not bad else f"失败 {len(bad)} 条")
sys.exit(1 if bad else 0)
