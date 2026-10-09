# -*- coding: utf-8 -*-
"""v1.23.17 配置同步：头部版本 + 升级段 + 三个键（sat 1→2 / soft_max 3→2）
   + 销掉 CONFIG_TUNED 里的 spiral.structure_saturation_every_n（改后 == 默认）。

★ 幂等：升级段用 MARK 判重；改文件类脚本必须可重复执行。
"""
from pathlib import Path

HERE = Path(".").resolve()
YML = HERE / "dgtf_config.yaml"
SMOKE = HERE / "smoke_test.py"

MARK = "# 【v1.23.16 → v1.23.17】"

UP = '''# 【v1.23.16 → v1.23.17】三个停止阈值/门槛：sat 间隔 2 / soft_max 2 / 条件 1 四层通用
#   ★ 本版**会改变默认行为**（默认路径下更容易、也更早停）—— 三处都改了出厂值：
#     ① `spiral.structure_saturation_every_n`：3 → **2**
#        （检查点落在第 2/4/6…圈。研究层上限 4 时，旧间隔 3 只在第 3 圈查过
#          —— 第 4 圈**没有检查点**；间隔 2 让最后一圈也被查到。）
#     ② `spiral.soft_max`：3 → **2**
#        （「自然安住」与条件 1 的 `layer_no >= soft_max` 推迟，都从第 2 圈起生效。）
#     ③ 停止判据**条件 1（复述 / 自省点名未消化）**：原先只对 `all` / `both` 开放，
#        本版对**四层**通用；并让 0 / 1 层的「连续复述圈数」写进 `view` 载体
#        （否则那半条信号对 0/1 永远是 0，改了门槛也等于没改）。
#   ★ 为什么改：真跑诊断显示研究层**六条停止通路全够不到**（`idle_*` 恒 0、
#     悬置 0 条、双通道收敛那条又被 `idle≥2` 挡住），它唯一现实的出口是 sat 判定，
#     而 sat 的检查点相位又漏掉最后一圈 —— 于是跑满上限被截断。
#   ★ ⚠️ 历史风险（v1.21.48 / v1.21.49 的实测记录）：间隔 **2** 曾让研究层
#     **第 2 圈就停**、可判定覆盖率只有 **33%**；v1.21.49 把间隔放宽到 **3**
#     才让研究层走到第 3 圈。本版回到 2 是**有意**的（间隔 3 漏检查点）。
#     若你更看重可判定覆盖率：把这里改回 3、`soft_max` 改回 3 即可（两项独立）。
#   ★ 判据：`check_v12317_stop_all_layers`（三处缺省 + 四层行为 + 两条负对照）
#     + 5 个变异体。
#   ★ 附带修复（**引擎代码不受影响**）：v1.23.16 把 `check_cost_profile`「整条
#     重写」成 `check_v12316_stop_therapy` 时，把里面与成本档**无关**的判据
#     （覆盖率双口径 / 不可判定命中轨迹）留在了 `return True` 之后 ⇒ 约 90 行
#     判据**再没跑过**。本版恢复成 `check_v12317_und_coverage_trace` 并接线。
#
'''

raw = YML.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")


def repl(old, new, what, expect=1):
    o, n = old.split("\n"), new.split("\n")
    hits = [i for i in range(len(lines) - len(o) + 1) if lines[i:i + len(o)] == o]
    assert len(hits) == expect, "%s：命中 %d 次（要求 %d）" % (what, len(hits), expect)
    for i in reversed(hits):
        lines[i:i + len(o)] = n
    print("%-38s 改 %d 处" % (what, len(hits)))


# ① 头部版本
repl("# 元 DGTF · v1.23.16 配置文件", "# 元 DGTF · v1.23.17 配置文件", "头部版本")

# ② 升级段（幂等：MARK 已在就跳过）—— 插在升级段列表最前（最新在最前）
if MARK in "\n".join(lines):
    print("%-38s 已存在，跳过" % "升级段")
else:
    ANCHOR = "# 【v1.23.11 → v1.23.12】外部锚点拆成两条通道分别写明（文本 / 联网）"
    assert lines.count(ANCHOR) == 1, "升级段锚点命中 %d 次" % lines.count(ANCHOR)
    i = lines.index(ANCHOR)
    lines[i:i] = UP.split("\n")
    print("%-38s 已插入" % "升级段")

# ③ soft_max
repl("""  # 【用途】软最大圈数：超过它才开始检查"自然安住"。
  # 【建议】3。
  # 【注意】soft_max 必须 < hard_max 才能触发自然安住。
  soft_max: 3""",
     """  # 【用途】软最大圈数：超过它才开始检查"自然安住"。
  # 【建议】2（v1.23.17：3 → 2）。
  # 【注意】soft_max 必须 < hard_max 才能触发自然安住。
  soft_max: 2""", "soft_max 3→2")

# ④ sat 段注释 + 值
repl("""  # 【用途】每 N 圈检查一次结构饱和度。
  # 【v1.21.58 起全层统一 3】
  #   · 这个检查只在**研究层与元层**跑（条件里写着 entry in ("1","all")），
  #     所以统一成 3 与原先把这两层各写成 3 **行为完全相同**。
  #   · 为什么是 3 不是 2：v1.21.48 研究层 2 圈就停，可判定覆盖率仅 33%；
  #     v1.21.49 把间隔放宽到 3，研究层才走到 3 圈。
  # 【注意】
  #   every_n: 1 → 每圈都跑 LLM，慢
  #   every_n: 3 → 3 圈才检查一次，可能错过
  #   该检查额外消耗 LLM 调用（每 N 圈 1 次）。
  structure_saturation_every_n: 1   # v1.21.60 对齐：原为过期值 2""",
     """  # 【用途】每 N 圈检查一次结构饱和度。
  # 【v1.23.17 起 = 2】检查点落在第 2/4/6…圈。
  #   · 这个检查两条跑圈通道都会过（`_run_layer` / `_b_check_stop` 各一处）；
  #     但 v1.23.16 之前只有研究层把结论推进停止计数（元层判出来只打日志），
  #     v1.23.16 起 `_sat_override` 四层同等生效。
  #   · ⚠️ 历史：v1.21.48 间隔 2 ⇒ 研究层第 2 圈就停、可判定覆盖率仅 33%；
  #     v1.21.49 放宽到 3 才让研究层走到第 3 圈。本版回到 2 是**有意**的
  #     （间隔 3 时上限 4 的层最后一圈没有检查点）—— 要退回就改 3。
  # 【注意】
  #   every_n: 1 → 每圈都跑 LLM，慢
  #   every_n: 2 → 每 2 圈一次（本版出厂值）
  #   该检查额外消耗 LLM 调用（每 N 圈 1 次）。
  structure_saturation_every_n: 2   # v1.23.17：3 → 2（与出厂默认一致）""",
     "sat 段注释 + 1→2")

out = "\n".join(lines)
enc = out.replace("\n", "\r\n").encode("utf-8")
assert enc.count(b"\r\r\n") == 0
YML.write_bytes(enc)
import yaml
yaml.safe_load(enc.decode("utf-8"))
print("yaml 语法 OK；行数 %d" % out.count("\n"))

# ⑤ CONFIG_TUNED 销账（sat 已 == 默认 ⇒ 登记过期）
s = SMOKE.read_bytes()
assert s.count(b"\r\n") == s.count(b"\n") and s.count(b"\r\r\n") == 0
st = s.decode("utf-8").replace("\r\n", "\n")
ENTRY = ('    "spiral.structure_saturation_every_n": '
         '"螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",\n')
assert st.count(ENTRY) == 1, "登记项命中 %d 次" % st.count(ENTRY)
st = st.replace(ENTRY, "", 1)
se = st.replace("\n", "\r\n").encode("utf-8")
assert se.count(b"\r\r\n") == 0
SMOKE.write_bytes(se)
print("CONFIG_TUNED 已销账 spiral.structure_saturation_every_n")
