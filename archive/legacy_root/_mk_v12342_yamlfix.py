# -*- coding: utf-8 -*-
"""修 yaml 升级段：上一轮用 python -c 写，**反引号被 bash 命令替换吃掉** ⇒ 文本残缺。
本脚本走文件（不经过 shell），且**不用反引号**。"""
import yaml
from pathlib import Path

p = Path("dgtf_config.yaml")
raw = p.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
s = raw.decode("utf-8").replace("\r\n", "\n")
lines = s.split("\n")

i = next(k for k, l in enumerate(lines) if l.startswith("# 【v1.23.41 → v1.23.42】"))
j = next(k for k, l in enumerate(lines)
         if l.startswith("# 【v1.23.40 → v1.23.41】"))
NEW = [
    "# 【v1.23.41 → v1.23.42】P-1 上下文裁剪 —— 新增配置键 spiral.shape_limit",
    "#   ① 问题：View.shape_of **无窗口**渲染整个 view（候选/&/线头/悬置…全量），",
    "#      而 _expand_from_views 每圈把它当 views_text 重灌 ⇒ 后段圈单次 prompt",
    "#      随圈数上涨（真跑实测最贵调用 25–32k tok/次；最贵 20% 占 46.5% token）。",
    "#   ② 修法（SOTA observation masking：保留最近 N、更老换结构化占位，成本↓52%）：",
    "#      shape_of 增加 limit 形参（默认 0=不限）；limit>0 只列最近 N 条 + 表头标总数。",
    "#   ③ 新键 spiral.shape_limit：**默认 0 = 不限 ⇒ 逐字零行为差**；>0 才裁剪。",
    "#      实测（48 候选/15 条 & 的真实规模）views_text 段 ↓56%；限 8 时 user prompt ↓50%。",
    "",
]
lines[i:j] = NEW
# 自检：不含反引号、无空残缺行
seg = "\n".join(lines[i:i + len(NEW)])
assert "`" not in seg, "仍有反引号"
assert "shape_of" in seg and "views_text" in seg
p.write_bytes("\n".join(lines).replace("\n", "\r\n").encode("utf-8"))
chk = p.read_bytes()
assert chk.count(b"\n") == chk.count(b"\r\n") and chk.count(b"\r\r\n") == 0
d = yaml.safe_load(chk.decode("utf-8"))
print("[ok] yaml 升级段已修 | spiral.shape_limit =", d["spiral"]["shape_limit"],
      "| 顶级节数", len(d))
