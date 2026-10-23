# -*- coding: utf-8 -*-
"""v1.23.16：只做 CHANGELOG 与记忆的定稿更新（报告已在第一次跑时改完）。

★ 逐条独立、幂等 —— 不整批断言（前一条失败不该拖死后面的）。
"""
import json
from pathlib import Path

HERE = Path(".")
an = json.loads((HERE / "_v12316_realrun_analysis.json").read_text(encoding="utf-8"))
CALLS = an.get("llm_calls") or an.get("calls")
TOK = an.get("llm_tokens") or an.get("tokens")

RC = [
    ("#   （真跑读数见 v12316_报告.md）",
     "#   · 自然停 **1/4 → 3/4** 层；截断 3/4 → **1/4**；实际停圈 4/4/5/7 → **3/4/3/7**；\n"
     "#     sat 判定触发 2 → **5** 次；用时 ~45 min → **2093 s**；联网 24 → 18 条。\n"
     "#   · ★ 直接证据：**对撞层**的停止理由里出现「结构饱和度判定连续无新维度」\n"
     "#     —— sat 对**非研究层**生效的直接证据；元层也在第 7 圈自然停。"),
    ("**交付物**：`元DGTF-V1.23.16.py`（18408 → 18247 行，纯 CRLF）",
     "**交付物**：`元DGTF-V1.23.16.py`（18408 → 18249 行，纯 CRLF）"),
    ("· 真跑同题对照（v1.23.15 auto 组：自然停 1/4 层）：见 `v12316_报告.md` §5.4。",
     "· 真跑同题对照：自然停 **1/4 → 3/4** 层、实际停圈 4/4/5/7 → 3/4/3/7、\n"
     "  sat 触发 2 → 5 次；对撞层停因出现「结构饱和度判定连续无新维度」。"),
    ("18408 → 18247 行", "18408 → 18249 行"),
]

# ① CHANGELOG（CRLF）
c = HERE / "CHANGELOG.md"
raw = c.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
cs = raw.decode("utf-8").replace("\r\n", "\n")
n = 0
for old, new in RC:
    if cs.count(old) == 1:
        cs = cs.replace(old, new, 1)
        n += 1
    elif cs.count(old) == 0:
        print("  跳过（已是新版）:", old[:40])
    else:
        print("  ★ 命中 %d 次，跳过:" % cs.count(old), old[:40])
ob = cs.replace("\n", "\r\n").encode("utf-8")
assert ob.count(b"\r\r\n") == 0
c.write_bytes(ob)
print("① CHANGELOG：替换 %d 处" % n)

# ② 记忆（追加，幂等）
mp = HERE / ".workbuddy" / "memory" / "2026-10-09.md"
ms = mp.read_text(encoding="utf-8")
NOTE = """
**真跑裁决（同题 × auto 默认，用时 2093 s）**：
自然停 **1/4 → 3/4** 层；截断 3/4 → 1/4；实际停圈 4/4/5/7 → **3/4/3/7**；
sat 判定触发 2 → **5** 次；联网 24 → 18 条；calls/tokens = %s / %s。
★ 直接证据：**对撞层**的停止理由出现「结构饱和度判定连续无新维度」
（旧版该结论只对研究层生效）；元层第 7 圈自然停（旧版跑满被截断）。
★ 定稿前发现产物表头写死「十二项」而表体 11 行 ⇒ 改成动态并用真跑 packed
零成本重渲染验证（表头 11 项 / 表体 11 行）。行数订正为 **18249**。
""" % (CALLS, TOK)
if "真跑裁决（同题" not in ms:
    mp.write_text(ms.rstrip("\n") + "\n" + NOTE, encoding="utf-8")
    print("② 记忆已追加")
else:
    print("② 记忆已是最新（跳过）")
