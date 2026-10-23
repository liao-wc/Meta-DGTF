# -*- coding: utf-8 -*-
"""v1.23.46：yaml 头 + 升级段 + duty.span_tolerant；params.py 标签。"""
import yaml
from pathlib import Path

p = Path("dgtf_config.yaml")
raw = p.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
i = next(k for k, l in enumerate(lines)
         if l.startswith("# 元 DGTF · v1.23.45 配置文件"))
lines[i] = "# 元 DGTF · v1.23.46 配置文件"
j = next(k for k, l in enumerate(lines) if l.startswith("# 【v1.23.44 → v1.23.45】"))
NEW = [
    "# 【v1.23.45 → v1.23.46】P-5 职责 S 口径对称化 —— 新增配置键 duty.span_tolerant",
    "#   ① 实测：真产物 duty_trace = {S:0.0, C:0.25, R:0.0} ⇒ S=0 是被 R=0 拖的。",
    "#      根因：C 用 _hit(问项, 全文) 计覆盖；R 用 _hit(问项, 单句) 计「直接段」。",
    "#      _hit 的 gram 覆盖率按**问项长度**归一 ⇒ 问项**跨句**时 C 记、R 不记。",
    "#   ② 修法：duty_of_layer / duty_components 加 span_tolerant 形参 —— True 时 R 的",
    "#      「直接命中」用**跨句窗口**（本句 + 下一句）。",
    "#   ③ 新键 duty.span_tolerant：**默认 false = 关 ⇒ 逐字零行为差**（R 与改前相同）。",
    "",
]
lines[j:j] = NEW
k = next(x for x, l in enumerate(lines) if l == "duty:")
ins = [
    "  # 【用途】职责 S 口径对称化：R 的「直接命中」用跨句窗口（修 C 全文/R 逐句 的不对称）。",
    "  # 【建议】false（出厂=关=逐字不变）；想让跨句问项在 R 里也算命中可设 true。",
    "  # 【依据】真产物实测：C=0.25 而 R=0.0 ⇒ S 被和均值拖到 0。",
    "  span_tolerant: false",
    "",
]
lines[k + 1:k + 1] = ins
p.write_bytes("\n".join(lines).replace("\n", "\r\n").encode("utf-8"))
chk = p.read_bytes()
assert chk.count(b"\n") == chk.count(b"\r\n") and chk.count(b"\r\r\n") == 0
assert "`" not in "\n".join(NEW)
d = yaml.safe_load(chk.decode("utf-8"))
print("[ok] yaml -> v1.23.46 | duty.span_tolerant =", d["duty"]["span_tolerant"])

q = Path("dgtf_app/params.py")
t = q.read_bytes().decode("utf-8")
anchor = '    "memory.eml_adaptive": "EML 阈值冷启自适应（库小时降晋升门槛；默认关）",\n'
assert t.count(anchor) == 1
t = t.replace(anchor, anchor
              + '    "duty.span_tolerant": "职责 S 口径对称化（R 用跨句窗口；默认关）",\n', 1)
q.write_bytes(t.encode("utf-8"))
print("[ok] params.py 加了 duty.span_tolerant 标签")
