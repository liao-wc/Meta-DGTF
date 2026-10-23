# -*- coding: utf-8 -*-
"""v1.23.44：同步 yaml（头 + 升级段 + memory.eml_adaptive）+ params.py 标签。"""
import yaml
from pathlib import Path

p = Path("dgtf_config.yaml")
raw = p.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
i = next(k for k, l in enumerate(lines)
         if l.startswith("# 元 DGTF · v1.23.43 配置文件"))
lines[i] = "# 元 DGTF · v1.23.44 配置文件"
j = next(k for k, l in enumerate(lines) if l.startswith("# 【v1.23.42 → v1.23.43】"))
NEW = [
    "# 【v1.23.43 → v1.23.44】P-3 学习闭环 —— 新增配置键 memory.eml_adaptive",
    "#   ① 实测：playbook 3 条 shadow 卡在 n_evidence=1 < _EML_PROMOTE_N(3) 永不升级；",
    "#      遗忘需 age>60 天（年轻库永不触发）。两者都是 SOTA 点名的失败模式",
    "#      （cold start / static thresholds，见 ReasoningBank、MemRL 综述）。",
    "#   ② 修法：eml_promote / eml_sweep_forget 加 adaptive 形参 —— 库 < _EML_COLD_LIB(20)",
    "#      时晋升门槛降到 1（冷启期先让学到的条目生效）；遗忘门槛随库规模放大。",
    "#   ③ 新键 memory.eml_adaptive：**默认 false = 关 ⇒ 逐字零行为差**。",
    "",
]
lines[j:j] = NEW
k = next(x for x, l in enumerate(lines) if l == "memory:")
ins = [
    "  # 【用途】EML 阈值冷启自适应：库小时降晋升门槛，让学习闭环能启动。",
    "  # 【建议】false（出厂=关=逐字不变）；想让早期学习生效可设 true。",
    "  # 【依据】ReasoningBank / MemRL：cold start + static thresholds 是失败模式。",
    "  eml_adaptive: false",
    "",
]
lines[k + 1:k + 1] = ins
p.write_bytes("\n".join(lines).replace("\n", "\r\n").encode("utf-8"))
chk = p.read_bytes()
assert chk.count(b"\n") == chk.count(b"\r\n") and chk.count(b"\r\r\n") == 0
assert "`" not in "\n".join(NEW)
d = yaml.safe_load(chk.decode("utf-8"))
print("[ok] yaml -> v1.23.44 | memory.eml_adaptive =", d["memory"]["eml_adaptive"])

q = Path("dgtf_app/params.py")
t = q.read_bytes().decode("utf-8")
anchor = '    "stop.gain_floor": "单标量早停阈值（增益<它连续N圈⇒停；0=关）",\n'
assert t.count(anchor) == 1
t = t.replace(anchor, anchor
              + '    "memory.eml_adaptive": "EML 阈值冷启自适应（库小时降晋升门槛；默认关）",\n', 1)
q.write_bytes(t.encode("utf-8"))
print("[ok] params.py 加了 memory.eml_adaptive 标签")
