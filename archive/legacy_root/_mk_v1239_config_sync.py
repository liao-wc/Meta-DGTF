# -*- coding: utf-8 -*-
"""v1.23.9：配置文件同步（头部版本 + 升级段；无新键 → 行为必须逐字不变）。

验收：`load_config(改前 yaml)` 与 `load_config(改后 yaml)` 逐字差异 **0 项**。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YML = HERE / "dgtf_config.yaml"
BAK = HERE / "_bak_dgtf_config.pre_v1239"
MAIN = HERE / "元DGTF-V1.23.9.py"

raw = YML.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0, \
    "yaml 不是纯 CRLF"
if not BAK.exists():
    BAK.write_bytes(raw)
    print("回滚点：", BAK.name)

s = raw.decode("utf-8").replace("\r\n", "\n")
old_head = "# 元 DGTF · v1.23.8 配置文件"
assert s.count(old_head) == 1, "头部版本行命中 %d 次" % s.count(old_head)
s = s.replace(old_head, "# 元 DGTF · v1.23.9 配置文件", 1)

UP = """# 【v1.23.8 → v1.23.9】取向分流守卫：无决策语境的题面不再套 decision 模板
#   ★ **本版不改任何配置键、不改任何默认值** ⇒ 升级后行为**逐字不变**。
#     改动只在**渲染层分流壳** `render_landing`（产物用哪套模板渲染）。
#   ① 问题（真跑实证）：单点事实询问（「新中国的成立时间是什么时候」）走
#      decision 模板后，落地层出现一整套**不存在的执行流程** ——
#      行动清单 / 负责人（「党史研究室编研岗」）/ 时限 / 验收 / 回退。
#   ② 改法：新增纯函数 `_has_decision_context(question)`（词表只增不减）+
#      在 `render_landing` 里加一条分流：`orientation == "auto"` **且**题面
#      无决策语境 → 走 boundary 五块模板。
#      **显式 `--orientation decision` 仍走 decision**（不覆盖用户选择）；
#      `boundary` 与「关掉开关」两条老短路保持原样；题面取不到时保守走
#      boundary（不知道题面就不套决策模板）。
#   ③ 对你的影响：**无**（没有新键、没有改过的默认值）。默认取向仍写
#      `auto`；只是 auto 现在会看题面了。
#   ★ 判据：`check_v1239_orientation_guard`（7 例分流 + 词表 3+3 + 接线 + 4 变异体）。

"""

anchor = "# 【v1.23.7 → v1.23.8】渲染层三处守卫（空节 / 停因上头部 / 悬置渲染去重）"
assert s.count(anchor) == 1, "升级段锚点命中 %d 次" % s.count(anchor)
s = s.replace(anchor, UP + anchor, 1)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
YML.write_bytes(out)

spec = importlib.util.spec_from_file_location("dgtf_cfgsync9", MAIN)
m = importlib.util.module_from_spec(spec)
sys.modules["dgtf_cfgsync9"] = m
spec.loader.exec_module(m)

a = m.load_config(str(BAK))
b = m.load_config(str(YML))
ja = json.dumps(a, sort_keys=True, ensure_ascii=False)
jb = json.dumps(b, sort_keys=True, ensure_ascii=False)
print("yaml 头部版本 -> v1.23.9")
print("load_config 键数：改前 %d / 改后 %d" % (len(a), len(b)))
print("load_config 逐字差异：", "0 项（行为逐字不变）" if ja == jb else "★ 有差异")
if ja != jb:
    import difflib
    d = list(difflib.unified_diff(ja.split(","), jb.split(","), lineterm="", n=0))
    print("\n".join(d[:40]))
    sys.exit(1)
print("yaml 缺 DEFAULT_CONFIG 键：",
      [k for k in m.DEFAULT_CONFIG if k not in a] or "无")
