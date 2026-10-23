# -*- coding: utf-8 -*-
"""v1.23.16 配置同步：删 cost_profile 与 round_window + 头部版本 + 升级段。

★ 本版是**删键**版（不是加键版），验收口径与 v1.23.13/14/15 不同：
  `load_config` 把 yaml 叠到 DEFAULT_CONFIG 上 ⇒ 两边都删 ⇒ 差异应为
  「这两个键在新版里**不存在**」。
"""
import json
import re
from pathlib import Path

HERE = Path(".").resolve()
YML = HERE / "dgtf_config.yaml"
_raw = YML.read_bytes()
assert _raw.count(b"\r\n") == _raw.count(b"\n") and _raw.count(b"\r\r\n") == 0
lines = _raw.decode("utf-8").replace("\r\n", "\n").split("\n")
if lines and lines[-1] == "":
    lines = lines[:-1]
N0 = len(lines)


def cut(a, b, new, what, head=None, tail=None):
    seg = lines[a - 1:b]
    if head is not None:
        assert seg[0].startswith(head), "%s：首行不符 %r" % (what, seg[0][:80])
    if tail is not None:
        assert seg[-1].startswith(tail), "%s：末行不符 %r" % (what, seg[-1][:80])
    lines[a - 1:b] = list(new)
    print("  %-30s %d-%d → %d 行" % (what, a, b, len(new)))


UP = """# 【v1.23.15 → v1.23.16】自然停治本三条 + 删除成本档维度
#   ★ 删除项（**本版唯一会改变默认行为的改动**）：
#     · 顶层 `cost_profile` 键与 `--profile` 参数**一并删除** —— 只剩一种行为
#       （原 quality：不裁剪）。它带走的五类省法全部下线：
#       ① 阴阳展开合并成一次调用 ② 探针按「收束/复裁」角色跳过 ③ 候选截断
#       ④ shape_chars/items 缩放  ⑤ 低频项（结构饱和度/池重估）惰性化
#     · `spiral.round_window` 删除 —— 跨圈比对改成**池内全量**。
#     为什么删：省法省的是 token，但它把「停止判据的检查频率」也一起动了
#     （间隔被 `_lazy_every_n` 拉到 4 ⇒ 层上限低于 4 的层永远跑不到那条判据）。
#     省钱不该改判据。
#   ★ 三条治本（都在停止判据上）：
#     ① sat 判定（LLM 判「本圈新 & 有没有引入新结构维度」）的结论对**四层
#        同等生效** —— 此前只有研究层会把结论推进计数，元层判出来只打一行
#        日志，于是元层结构上不可能自然停。
#     ② `_lazy_every_n` 不再惰性化（恒等返回）。
#     ③ 比对参照集从「近 N 圈的 new_amps」改成「**池内全部 &**」——
#        跨 3 圈以上的重复此前抓不到（窗口只有 2 圈）。
#   ★ auto 项：十二项 → **十一项**（去掉「成本档」），产物头部表少一行。
#   ★ 怎么退回旧行为：本版**没有**对应开关 —— 成本档维度不是配置项而是代码
#     路径。要旧行为请用 v1.23.15 那份主文件。
#   ★ 验收：冒烟 0 ✗；真跑同题对照（v1.23.15 的 auto 组是自然停 1/4 层）：
#   （真跑读数见 v12316_报告.md）
"""

EDITS = [
    # 头部版本
    (2, 2, ["# 元 DGTF · v1.23.16 配置文件"], "头部版本",
     "# 元 DGTF · v1.23.15 配置文件", None),
    # 顶部说明里的 --profile
    (15, 15, ["# ★ 想固定某一项：命令行显式传（`--route/--parallel/--rounds/"],
     "顶部说明去 --profile",
     "# ★ 想固定某一项：命令行显式传（`--route/--profile/--parallel/--rounds/", None),
    # 分层说明里的 cost_profile 行
    (441, 441, [], "分层说明去 cost_profile",
     "#   cost_profile    —— 成本档位", None),
    # 成本档位段（注释 + 键）
    (468, 479, [], "成本档位段删",
     "# ------------------------------------------------------------", None),
    # round_window 段
    (1294, 1298, [], "round_window 段删",
     "  # ---------- 跨圈比对窗口 ----------", None),
]
for a, b, new, what, head, tail in sorted(EDITS, key=lambda x: -x[0]):
    cut(a, b, new, what, head, tail)

# ── 升级段（幂等：标记在就不插）─────────────────────────────
_txt = "\n".join(lines)
MARK = "# 【v1.23.14 → v1.23.15】"
NEW_MARK = "# 【v1.23.15 → v1.23.16】"
if NEW_MARK in _txt:
    print("  升级段已存在（跳过）")
else:
    assert _txt.count(MARK) == 1, "升级段锚点命中 %d 次" % _txt.count(MARK)
    _txt = _txt.replace(MARK, UP.rstrip("\n") + "\n" + MARK, 1)
    print("  升级段已插入")
lines = _txt.split("\n")

out = "\n".join(lines) + "\n"
_dupm = out.count(NEW_MARK)
print("  升级段出现 %d 次（应为 1）" % _dupm)

new_bytes = out.replace("\n", "\r\n").encode("utf-8")
assert new_bytes.count(b"\r\r\n") == 0
assert new_bytes.count(b"\r\n") == new_bytes.count(b"\n")
YML.write_bytes(new_bytes)
print("行数 %d → %d" % (N0, out.count("\n")))
print("已写 dgtf_config.yaml")
