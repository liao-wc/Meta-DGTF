# -*- coding: utf-8 -*-
"""v1.23.9：在仓库根 CHANGELOG.md 最前面插入本版段（最新在最前）。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
CL = HERE / "CHANGELOG.md"
raw = CL.read_bytes()
is_crlf = raw.count(b"\r\n") == raw.count(b"\n")
s = raw.decode("utf-8").replace("\r\n", "\n")

SEP = "  " + "\u2500" * 60

NEW = """v1.23.9 相对 v1.23.8

【主题】取向分流守卫 —— 无决策语境的题面不再套 decision 模板。

【为什么】v1.23.7 的真跑（题面「新中国的成立时间是什么时候」）在落地层留下一整套
  **不存在的执行流程**：行动清单里写着「负责人：党史研究室编研岗」
  「时限：定稿会前2个工作日」「验收：出具四节点原文摘录，逐条注出处并签字」。
  这个岗、这个会、这个签发人全是按 decision 模板的字段结构填出来的。
  根因不在模型，在**分流**：`orientation=auto` 无条件走 decision 模板。

【做什么】（只在渲染层分流壳 `render_landing`）
  · 新增纯函数 `_has_decision_context(question)` + 决策语汇词表（只增不减）。
  · `render_landing` 加一条分流：`auto` **且**题面无决策语境 → boundary 五块模板。
  · **显式 `--orientation decision` 仍走 decision**（不覆盖用户显式选择）；
    `boundary` 与「关掉开关」两条老短路保持原样；题面取不到（空 / 缺 `question`
    键）时保守走 boundary —— 不知道题面就不套决策模板。

【验收】
  · 探针 `_probe_v1239_orientation.py` before→after 7 例：auto+事实题
    decision→boundary；auto+决策题**不变**；显式 decision+事实题**不变**；
    空题面 / 缺 question 键 decision→boundary；词表 3 例命中 + 4 例不命中。
    （`_probe_v1239_before.txt` / `_probe_v1239_after.txt`）
  · 冒烟 exit 0 / 0 ✗ / 204 ✓（守卫 96→97）。
  · 变异体 `_probe_v1239_mutants.py`：control 判绿；M1 ctx 恒 True / M2 ctx 恒 False /
    M3 删 auto 短路 / M4 短路放宽到 decision —— **四个全部判红**。
  · **真跑一次**（同题、对照 v1.23.7 旧产物，`_cmp_v1237_vs_v1239.py`）：
    落地层由 decision 模板变为 boundary —— 「行动清单」段与「负责人：党史研究室编研岗」
    这类编出来的执行流程**整段消失**；产物无空节；头部出现
    `**停止**：自然 4 层 / 被截断（体力耗尽）0 层`；悬置渲染出现合并标注。
    ★ 如实记账：`--profile economy` 只改 token 裁剪、不改圈数上限，本次实跑
    188 次 LLM / 141.8 万 tokens，比 quality 那次更贵 —— 要控成本须同时限 `--rounds`。
  · AST 登记 added 96→97（两向对账）；`load_config` 逐字差异 0 项。

【未做】R1 自省→动作回写 / R8 附录默认裁剪 / R9 成本档按难度路由 /
  R10 事实题外部锚点开关 —— 逐条记账在 `v1239_报告.md` §五。

@@SEP@@
★ v1.23.9 收束摘要
@@SEP@@

**交付物**：`元DGTF-V1.23.9.py`（17013 行 / 纯 CRLF）；本段；`dgtf_config.yaml`
  （头部版本 + 升级段，**无新键 ⇒ 行为逐字不变**，`load_config` 逐字差异 0 项）。

**改了什么**：`render_landing` 的分流加上「题面有无决策语境」这一维 ——
  新增纯函数 `_has_decision_context` + 词表；`auto` 且无决策语境 → boundary 模板。

**验收**：探针 7 例分流全中（含 3 例负对照）；冒烟 exit 0 / 0 ✗ / 204 ✓；
  4 个变异体全部判红；真跑一次同题对照 —— 落地层转为 boundary 模板、
  编出来的执行流程整段消失、无空节、头部停因行 4/0、悬置去重标注生效；
  `load_config` 逐字差异 0 项；AST 登记两向对账绿。

**未做**：R1 / R8 / R9 / R10（理由见报告 §五）。

""".replace("@@SEP@@", SEP)

anchor = "---\n\nv1.23.8 相对 v1.23.7"
assert s.count(anchor) == 1, "CHANGELOG 锚点命中 %d 次" % s.count(anchor)
s = s.replace(anchor, "---\n\n" + NEW + "v1.23.8 相对 v1.23.7", 1)

out = s.replace("\n", "\r\n").encode("utf-8") if is_crlf else s.encode("utf-8")
CL.write_bytes(out)

import re  # noqa: E402
chk = CL.read_bytes().decode("utf-8").replace("\r\n", "\n")
secs = re.findall(r"^v(1\.2\d(?:\.\d+)?) 相对", chk, re.M)
sums = [ln.strip() for ln in chk.split("\n")
        if "★ v1.2" in ln and "收束摘要" in ln]
dup = {t: sums.count(t) for t in set(sums) if sums.count(t) > 1}
print("CRLF=%s | 段数 %d | 首三段 %s | 收束标题 %d 个 | 重复 %s"
      % (is_crlf, len(secs), secs[:3], len(sums), dup or "无"))
