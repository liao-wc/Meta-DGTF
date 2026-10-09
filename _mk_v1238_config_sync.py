# -*- coding: utf-8 -*-
"""v1.23.8：配置文件同步（头部版本 + 升级段；无新键 → 行为必须逐字不变）。

验收：`load_config(改前 yaml)` 与 `load_config(改后 yaml)` 逐字差异 **0 项**。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YML = HERE / "dgtf_config.yaml"
BAK = HERE / "_bak_dgtf_config.pre_v1238"
MAIN = HERE / "元DGTF-V1.23.8.py"

raw = YML.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0, \
    "yaml 不是纯 CRLF"
if not BAK.exists():
    BAK.write_bytes(raw)
    print("回滚点：", BAK.name)

s = raw.decode("utf-8").replace("\r\n", "\n")

old_head = "# 元 DGTF · v1.23.7 配置文件"
assert s.count(old_head) == 1, "头部版本行命中 %d 次" % s.count(old_head)
s = s.replace(old_head, "# 元 DGTF · v1.23.8 配置文件", 1)

UP = """# 【v1.23.7 → v1.23.8】渲染层三处守卫（空节 / 停因上头部 / 悬置渲染去重）
#   ★ **本版不改任何配置键、不改任何默认值** ⇒ 升级后行为**逐字不变**。
#     改动全在**渲染层**（产物 md 怎么写），不碰 prompt、不碰 LLM 调用、
#     不碰判定语义：
#   ① 落地层 decision 模板：「三、所需数据清单」「六、如果只能做一件事」
#      在无内容时输出**显式说明**（不再留一个空标题），节编号保持连续。
#   ② 新增纯函数 `_stop_kind_summary(views)`：把各层 stop_reason 归纳成
#      「自然 n 层 / 被截断（体力耗尽）m 层」，接在产物头部「**调度**」之后；
#      四层全被截断时带 ⚠️「无一层自然收敛」；没有任何停因时**不渲染**
#      （不印 0/0 冒充读数）。
#   ③ 新增纯函数 `_dedup_suspensions_for_render()` + `_susp_key()`：渲染
#      「决定不消解」时按 target 的**首个分句**归并同 target 的重复条
#      （真跑里同一条张力被登记成「X」与「X；元层决定不消解。」，全长不等），
#      合并条数打印留痕。
#   ★ 对你的影响：**无**。本文件无需改动（没有新键、没有改过的默认值）。
#   ★ 判据：`check_v1238_render_guards`（自带负对照 + 3 个变异体）。

"""

anchor = "# 【v1.23.6 → v1.23.7】changelog 搬出代码，落到 `CHANGELOG.md`"
assert s.count(anchor) == 1, "升级段锚点命中 %d 次" % s.count(anchor)
s = s.replace(anchor, UP + anchor, 1)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
YML.write_bytes(out)

# ── 验收：load_config 逐字差异 0 ────────────────────────────────
spec = importlib.util.spec_from_file_location("dgtf_cfgsync", MAIN)
m = importlib.util.module_from_spec(spec)
sys.modules["dgtf_cfgsync"] = m
spec.loader.exec_module(m)

a = m.load_config(str(BAK))
b = m.load_config(str(YML))
ja = json.dumps(a, sort_keys=True, ensure_ascii=False)
jb = json.dumps(b, sort_keys=True, ensure_ascii=False)
print("yaml 头部版本 ->", "v1.23.8")
print("load_config 键数：改前 %d / 改后 %d" % (len(a), len(b)))
print("load_config 逐字差异：", "0 项（行为逐字不变）" if ja == jb else "★ 有差异")
if ja != jb:
    import difflib
    d = list(difflib.unified_diff(ja.split(","), jb.split(","),
                                  lineterm="", n=0))
    print("\n".join(d[:40]))
    sys.exit(1)

# 顺带：DEFAULT_CONFIG 的键是否都在 yaml 里声明（第三向，本版应为「无新增」）
miss = [k for k in m.DEFAULT_CONFIG if k not in a]
print("yaml 缺 DEFAULT_CONFIG 键：", miss or "无")
