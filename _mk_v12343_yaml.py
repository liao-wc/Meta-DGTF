# -*- coding: utf-8 -*-
"""v1.23.43：同步 dgtf_config.yaml（头 + 升级段 + 新键 stop.gain_floor）+ params.py 标签。
★ 不用反引号（防被 shell 命令替换吃掉）。"""
import json
import re
from pathlib import Path

# ── yaml ──
p = Path("dgtf_config.yaml")
raw = p.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
s = raw.decode("utf-8").replace("\r\n", "\n")
lines = s.split("\n")
i = next(k for k, l in enumerate(lines)
         if l.startswith("# 元 DGTF · v1.23.42 配置文件"))
lines[i] = "# 元 DGTF · v1.23.43 配置文件"
j = next(k for k, l in enumerate(lines) if l.startswith("# 【v1.23.41 → v1.23.42】"))
NEW = [
    "# 【v1.23.42 → v1.23.43】P-2 早停 —— 新增配置键 stop.gain_floor",
    "#   ① 依据：自反式迭代的最优停止 = **单一、阶段无关阈值**（arXiv:2608.10729），",
    "#      把策略搜索降到一个标量；且自反增益集中在头几轮、之后递减（成本线性涨）。",
    "#   ② 新增纯函数 refinement_gain（各层目标读数的逐圈增量，方向统一成「越大越有进展」）",
    "#      + layer_gain_stop_signal（增益 < 阈值连续 N 圈 ⇒ 停）。",
    "#   ③ 新键 stop.gain_floor：**默认 0 = 关 ⇒ 逐字零行为差**；>0 才启用早停。",
    "",
]
lines[j:j] = NEW
# stop: 段首插新键
k = next(x for x, l in enumerate(lines) if l == "stop:")
ins = [
    "  # 【用途】单标量早停阈值：refinement_gain < 它连续 N 圈 ⇒ 判「迭代饱和」停止。",
    "  # 【建议】0（出厂=关=逐字不变）；想省尾段圈可试 0.01。",
    "  # 【依据】arXiv:2608.10729（自反式迭代的最优停止 = 单一阶段无关阈值）。",
    "  gain_floor: 0.0",
    "",
]
lines[k + 1:k + 1] = ins
p.write_bytes("\n".join(lines).replace("\n", "\r\n").encode("utf-8"))
chk = p.read_bytes()
assert chk.count(b"\n") == chk.count(b"\r\n") and chk.count(b"\r\r\n") == 0
import yaml  # noqa: E402
d = yaml.safe_load(chk.decode("utf-8"))
assert "`" not in "\n".join(NEW), "含反引号"
print("[ok] yaml -> v1.23.43 | stop.gain_floor =", d["stop"]["gain_floor"])

# ── params.py（纯 LF，只插一行）──
q = Path("dgtf_app/params.py")
t = q.read_bytes().decode("utf-8")
assert t.count(b"\r\n".decode()) == 0, "params.py 应为纯 LF"
anchor = '    "runtime.web": "联网检索（auto/on/off）",\n'
assert t.count(anchor) == 1
t = t.replace(anchor, anchor
              + '    "stop.gain_floor": "单标量早停阈值（增益<它连续N圈⇒停；0=关）",\n', 1)
q.write_bytes(t.encode("utf-8"))
print("[ok] params.py 加了 stop.gain_floor 标签")
