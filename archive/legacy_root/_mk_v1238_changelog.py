# -*- coding: utf-8 -*-
"""v1.23.8：在仓库根 CHANGELOG.md 最前面插入本版段（最新在最前）。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
CL = HERE / "CHANGELOG.md"
raw = CL.read_bytes()
is_crlf = raw.count(b"\r\n") == raw.count(b"\n")
s = raw.decode("utf-8")
s = s.replace("\r\n", "\n")

SEP = "  " + "\u2500" * 60

NEW = """v1.23.8 相对 v1.23.7

【主题】渲染层三处守卫 —— 把最近一次真跑暴露的「形态错配」在产物层收口。

【为什么】2026-10-09 09:33 一次真跑（题面「新中国的成立时间是什么时候」）在产物里暴露：
  · 落地层出现**有标题、没内容**的节（`### 三、所需数据清单`）；
  · 四层**全部**「体力耗尽（被截断不是自然停止）」，但读者从产物头部看不出来 ——
    与「四层都自然收敛」在头部长得一样；
  · 「决定不消解」6 条里有 **2 组同 target 重复**（池内已有 ⊘ 去重，这一类没接）。

【做什么】（全在渲染层：不碰 prompt / 不碰 LLM 调用 / 不碰判定语义）
  · `_render_landing_decision`：「三、所需数据清单」与「六、如果只能做一件事」
    在无内容时输出**显式说明**，不再留空标题，节编号保持连续。
    ★ 首版补丁把「六」的节标题一起吞掉了 —— 被探针读数 `A1_节数` 当场抓到（6→5）。
  · 新增纯函数 `_stop_kind_summary(views)`：把各层 stop_reason 归纳成
    「自然 n 层 / 被截断（体力耗尽）m 层」，接在产物头部「**调度**」之后；
    全被截断时带 ⚠️「无一层自然收敛」；无停因时返回空串（不印 0/0）。
  · 新增纯函数 `_dedup_suspensions_for_render(items)` + `_susp_key(target)`：
    按 target 的**首个分句**归并同 target 的重复条（真跑里同一条张力被登记成
    「X」与「X；元层决定不消解。」，全长不等 ⇒ 按全长去重完全无效）；
    合并条数打印留痕，不假装池里没有重复。

【验收】
  · 探针 `_probe_v1238_rendering.py` before→after 对表：空节 2→0（无 actions）与
    1→0（有 actions），三/六标题仍在；停因三个读数正确；去重 5 条 → 保留 3 / 合并 2；
    异 target 不误合并、单条不吞。文件 `_probe_v1238_before.txt` / `_after.txt`。
  · 冒烟 0 ✗；新增判据 `check_v1238_render_guards`（守卫 95 → 96）。
  · 变异体 `_probe_v1238_mutants.py`：control 判绿；M1 空节复活 / M2 停因恒空 /
    M3 去重失效 **三个全部判红**。
  · AST 登记表同步（added 93→96，current → 本版）。

【未做】（逐条记账在 `v1238_报告.md`）
  R1 自省→动作回写、R2 取向路由短路（单点事实询问不套 decision 模板）、
  R8 附录默认裁剪、R9 成本档按难度路由、R10 事实题外部锚点开关 ——
  都属于**机制级改动 / 需要真跑才看得出效果**，与本轮「不跑真跑、只做离线可验」
  的约束不匹配。

@@SEP@@
★ v1.23.8 收束摘要
@@SEP@@

**交付物**：`元DGTF-V1.23.8.py`（16974 行 / 纯 CRLF）；本段；`dgtf_config.yaml`
  头部版本 + 升级段（**无新键 ⇒ 行为逐字不变**，`load_config` 逐字差异 0 项）。

**改了什么**：渲染层三处守卫 —— ① decision 模板的空节显式化（三/六两节）；
  ② 产物头部新增一行「停止：自然 n 层 / 被截断 m 层」；③ 悬置条目渲染时按
  target 首个分句归并同 target 重复条。三处都是**加性 / 守卫型**：不改任何判定
  语义、不加任何配置键。

**验收**：探针 before→after 对表逐项符合预期；冒烟 0 ✗；
  3 个变异体全部判红；`load_config` 逐字差异 0 项；主文件纯 CRLF（CRCRLF 0）；
  AST 登记两向对账绿。

**未做**：R1 / R2 / R8 / R9 / R10 五条（机制级改动或需真跑验证），理由见上。

""".replace("@@SEP@@", SEP)

anchor = "---\n\nv1.23.7 相对 v1.23.6"
assert s.count(anchor) == 1, "CHANGELOG 锚点命中 %d 次" % s.count(anchor)
s = s.replace(anchor, "---\n\n" + NEW + "v1.23.7 相对 v1.23.6", 1)

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
