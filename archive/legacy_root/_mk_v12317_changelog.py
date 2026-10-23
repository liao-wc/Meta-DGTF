# -*- coding: utf-8 -*-
"""v1.23.17 CHANGELOG 段（幂等：先抠旧的同版段再插）。"""
from pathlib import Path

P = Path(".").resolve() / "CHANGELOG.md"
raw = P.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

HEAD = "v1.23.17 相对 v1.23.16"
NEXT = "v1.23.16 相对 v1.23.15"

NEW = '''v1.23.17 相对 v1.23.16

【要解决的问题】v1.23.16 的同题真跑里四层只剩研究层被截断。逐条核它六条停止通路：
  条件 1 不对它开放；条件 2/3/4/5 都要 `idle >= 2`（它每圈都在产新 & ⇒ 恒 0）；
  条件 6 要 ≥2 条 `stable` 悬置（它悬置 0 条）⇒ **唯一现实的出口是 sat 判定**，
  而 sat 的检查点（`layer_no % sat_every_n == 0`，间隔 3）在它上限 4 时**只在第 3 圈
  查过**，第 4 圈没有检查点。三处出厂值随之下调。

【改了什么】
- `spiral.structure_saturation_every_n` **3 → 2**（含两条通道的各一处 `.get` 缺省）：
  检查点落在第 2/4/6…圈，上限 4 的层最后一圈也被查到。
- `spiral.soft_max` **3 → 2**（含四处缺省）：条件 6「自然安住」与条件 1 的
  `layer_no >= soft_max` 推迟都从第 2 圈起生效。
- **停止判据条件 1（复述 / 自省点名未消化）四层通用**，两处：
  ① `_stop_reasons` 去掉 `if entry in ("all", "both")` 门槛（`layer_no < soft_max`
     的推迟保留）；
  ② `_apply_view_to_pool_locked` 的 else 分支把 0/1 层的连续复述圈数写进
     `view._meta_idle_streak` —— 否则 `_compute_rephrase_streak` 对 0/1 恒返回 0，
     **门槛去掉了行为也不变**。不改 `view.idle` 的既有语义。
- 出厂 yaml 顺带**统一**：`structure_saturation_every_n` 原为 **1**（引擎默认 3，
  两者本就不一致 ⇒ 同一版本「裸跑」与「带 yaml 跑」行为不同），本版两处统一为 2。
- 修 **v1.23.16 引入的两个真缺陷**：
  · `check_cost_profile` 被「整条重写」时，与成本档**无关**的判据（覆盖率双口径 /
    不可判定命中轨迹）被留在 `return True` 之后 ⇒ 约 90 行 / 33 条语句**从没跑过**。
    恢复为 `check_v12317_und_coverage_trace` 并接线（✓ 数 207 → 210 即为佐证）。
  · 两处夹具把「停止」当常量（P1-6 晚写者 3/3、#13 预算 barrier 4/4）⇒ 本版让 0/1
    层更容易停之后当场失效；改成**固定该变量**（抬 `soft_max` / 抬 idle 阈值 / 关
    sat），不是改小期望值。

【验收】
- 探针 12 项读数变化 + 1 项负对照不变：改前 0/1 层无理由 → 改后「复述 + 自省点名」
  两半理由都有；`view._meta_idle_streak` `None`→`2`、`_compute_rephrase_streak`
  `0`→`2`；**负对照** `soft_max=3 & layer_no=2` 仍被推迟（没被一起改坏）。
- 冒烟 `exit 0 / 0 ✗ / 210 ✓`；新增判据与**恢复的判据**都真跑到。
- 变异体 **5/5 判红**（条件 1 重关门 / `soft_max` 回 3 / sat 回 3 / 复述载体不写 /
  去推迟），control 判绿。
- 整体审计 **PASS 67 / FAIL 0**；`load_config` 差异**恰为**有意改的两项
  （`spiral.soft_max` 3→2、`spiral.structure_saturation_every_n` 1→2）；
  `CONFIG_TUNED` 无过期条目；主文件 18249 → **18258** 行 / 纯 CRLF。

【未做 / 风险】
- ⚠️ 出厂 yaml 里留着的 v1.21.48 / v1.21.49 实测记录：间隔 **2** 曾让研究层
  **第 2 圈就停**、可判定覆盖率仅 **33%**（v1.21.49 才把它放宽到 3）。本版回到 2 是
  **有意**的（间隔 3 漏检查点）；但**本版未单独测可判定覆盖率**，如实记。
  要回退：把该项与 `soft_max` 各自改回 3（两项独立）。
- 修行层（0）的复述理由文案仍是「ing」（元 / 对撞层的用词）—— 文案债未清。
- 条件 1 的两条 streak 载体（`rephrased_streak` / `meta_idle_streak`）**未合并** ——
  本版只把 0/1 的圈数镜像进后者，属结构债。

'''

# —— 幂等：先抠掉已有同版段 ——
if HEAD in s:
    i = s.index(HEAD)
    j = s.index(NEXT, i)
    s = s[:i] + s[j:]
    print("已抠掉旧的 v1.23.17 段")

assert s.count(NEXT) == 1, "下一段锚点命中 %d 次" % s.count(NEXT)
s = s.replace(NEXT, NEW + NEXT, 1)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
P.write_bytes(out)
t = out.decode("utf-8")
print("v1.23.17 段数:", t.count("v1.23.17 相对 v1.23.16"),
      "| 段序前 4:",
      [x for x in t.split("\n") if x.startswith("v1.23.1")][:4])
