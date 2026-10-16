# -*- coding: utf-8 -*-
"""v1.23.45：yaml 头 + 升级段（P-4 无新配置键）。"""
import yaml
from pathlib import Path

p = Path("dgtf_config.yaml")
raw = p.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
i = next(k for k, l in enumerate(lines)
         if l.startswith("# 元 DGTF · v1.23.44 配置文件"))
lines[i] = "# 元 DGTF · v1.23.45 配置文件"
j = next(k for k, l in enumerate(lines) if l.startswith("# 【v1.23.43 → v1.23.44】"))
NEW = [
    "# 【v1.23.44 → v1.23.45】P-4 输出内复读率读数 —— **无新增配置键**",
    "#   依据：Reflective Budget Governor（Zenodo 22844856）实测「集合式 trigram 信号对",
    "#   输出内逐字复读结构盲」（两次灾难性退化—约 50 段逐字重复—都没被发现）。",
    "#   新增纯函数 output_repetition：输出内重复 n-gram 占比（0=全新鲜，1=全复读）；",
    "#   接进 ing 环节的零成本读数（含 _READING_LABELS / _QUANT_LABELS 两个出口）。",
    "#   阈值 _OUTREP_N=3 / _OUTREP_ALERT=0.3 为模块常量（随代码走，不进配置面板）。",
    "",
]
lines[j:j] = NEW
p.write_bytes("\n".join(lines).replace("\n", "\r\n").encode("utf-8"))
chk = p.read_bytes()
assert chk.count(b"\n") == chk.count(b"\r\n") and chk.count(b"\r\r\n") == 0
assert "`" not in "\n".join(NEW)
d = yaml.safe_load(chk.decode("utf-8"))
print("[ok] yaml -> v1.23.45 | 顶级节数", len(d))
