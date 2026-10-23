# -*- coding: utf-8 -*-
"""追加今日记忆第十六节 + 更新长期约定（本轮通则）。"""
import io, os

HERE = os.path.dirname(os.path.abspath(__file__))
DAY = os.path.join(HERE, ".workbuddy", "memory", "2026-10-14.md")
LONG = os.path.join(HERE, ".workbuddy", "memory", "MEMORY.md")

ADD_DAY = u"""
---

## 十六、v1.23.36：联网全接 + 所有层注入 + 读数全量 + 三层 trace + 显式控制面

### 用户指令（本轮）
① 「联网全接**配置可控开关**」；② 「**所有层都注入**」；
③ 「运行中和结束时**所有读数完整显示在日志中**，同时**结构化显示在产物文档中**」；
④ 「自由调度和自我学习是**一体**的，渗透到整个元DGTF；所有行为逻辑都有
**追溯和可控性**；先检索最前沿技术算法学科知识融合创新并应用于元DGTF」。

### 前沿依据（四篇，都已落地）
- ★★ **E³-Agent**（arXiv 2605.27428, 2026）：**快慢双路径 + 一个小的显式控制面**
  ⇒ 落地 `ControlSurface`（运行时调度调整的唯一收口）。
- ★ **Heartbeat-Driven Scheduling**（arXiv 2604.14178, 2026）：**周期性心跳主动**
  编排（不是等失败才反思）⇒ `_before_round`（已是两条通道共用的圈前统一动作）作心跳位。
- ★ **MetaClaw**（arXiv 2603.17187, 2026）：**双时间尺度**（快适应合成技能 +
  慢适应策略优化，互相强化）⇒ 与既有 EML 的两条路径对齐。
- ★★ **可追溯三层 + decision.chain + DLF**（agent observability 2026）：
  **L1 决策（含「考虑过的选项」）/ L2 动作 / L3 归因**；**审计级不许采样**；
  「不到 5% 的 agent 记录了 temperature/top-k/seed」⇒ 参数要可追溯。
  ⇒ 落地 `_trace_note` / `trace_decide` / `trace_outcome` + `view.trace_log`。

### 落地（五件）
1. **联网全接**：30 个环节（AST 实测）原先只有 7 个能联网 ⇒ 实现在 **`LLM.call`**
   （所有环节必经）⇒ **一处改全覆盖**；用 **thread-local 注入** `web_searcher`
   （`LLM` 是模块级类，拿不到 `MetaDGTF._web_search`）；**调用栈推断环节名**
   ⇒ 每环节一个开关；配置 `web_search.stages` 7 → **37 键**（叶子键 193 → 223）。
2. **★ 红线调整（用户指令）**：原「修行层**硬豁免**不注入」→ 用户要「**所有层都注入**」
   ⇒ 硬豁免取消。★ 保护**改为配置式**（30 开关默认 false ⇒ 默认逐字不变）。
   `practice_term_calibration` 仍只留痕、不注入（另一条独立路径，未动）。
3. **读数全量显示**：`_readings_bundle`（**单一真相源**）→ `_readings_line`（运行中一行）
   / `_readings_table`（结束总表 + Markdown 版）；三处显示；**产物那张表就是日志
   那次渲染的同一个字符串**（`packed["readings_table"]`）⇒ **不可能漂移**。
4. **三层 trace**：`View.trace_log` + 模块级 `_trace_note`（调用点在两个无继承关系的
   类上 ⇒ 必须模块级，与 `_quant_note` 同因）；`trace_decide` **必须带「考虑过的
   全部选项」**；`trace_outcome` 记动作前后读数（EML 唯一能依赖的学习信号）。
5. **显式控制面** `ControlSurface`：白名单 + 边界 + **必留痕**（缺 why/trace_ref ⇒ 拒；
   越界**不夹取**直接拒）；**接线**到 EML 两处写入；**绝不写配置**。

### ★★ 两个「插错位置」事故（都已修，比「没插」更危险）
1. **30 个开关插进了 `api.thinking.stages`**（不是 `web_search.stages`）——
   `s.find('"web_search"')` 命中的是别处。**危害**：那些 `False` 让环节的思考档
   **优先返回 False** ⇒ **全开时被强制关思考**（行为退化）。
   修法：撤销 + **两段定位**（先找段起点、再在段内找键）+ **段内校验**。
2. **判据假设错**：`practice_term_calibration` / `stop_criteria` 的判据断言
   「默认关时走到 Gate」—— 但它们**开头就判 `enabled`**（与 `_research_web_prep`
   同惯例）⇒ 根本不调 `_web_search`。判据改为断言**结果**（零检索）。

### ★★ 本轮最重要的两条通则（已写入长期约定）
1. **观测要在「被测逻辑真正执行的那一层」**：本轮**第二次**栽 ——
   第一版探针把 `LLM.call` **整体**替换成 spy ⇒ `_web_augment`（在被替换的方法
   **内部**）**根本不会执行** ⇒ 观测恒空，表现为「接线不可达」的**假象**。
   同理，早前把 `_web_search` 整体替换 ⇒ Gate 一次没被调到。
2. **插错位置 > 没插**：插到「同名键的别处」不会报错、不会被常规判据抓到，
   却会**静默改变行为**（如强制关思考）。凡按名字找插入点，必须**两段定位 +
   段内校验**。

### 验收（v1.23.36）
- 主文件 **25288 行 / 纯 CRLF**（CR-CR-LF 0）/ AST OK；
- 探针 `_probe_v12336_allweb.py`：未接线不增强 / 总闸关不增强 / 开+授权即增强 /
  **四层全可注入** / 未授权被 Gate 拒**且有拒因** —— 全过；
- 读数三处显示实测：`📊 [0] 圈 2 ｜ 候选 2 · & 0 · 线头 1 · 悬置 1 ｜ 量化
  保真=drifted 分歧=— 密度=ok 候选=collapsed ｜ 职责 S=0.0` + 结束总表 + 产物 Markdown 表；
- 配置叶子键 **223**；`web_search.stages` **37 键**（全 false）；
- ⏳ 冒烟 / `--phase all` / 变异体 / 全开真跑（143+ calls 进行中）
"""

ADD_LONG = u"""
### ★★ v1.23.36 新增通则（跨轮复用，与上面并列）
- **观测要在「被测逻辑真正执行的那一层」** —— 把外层包装**整体**替换成 spy，
  等于把被测对象一起换掉（`_web_augment` 在 `LLM.call` **内部**、`allow` 在
  `_web_search` **内部**）⇒ 观测恒空、表现为「接线不可达」的**假象**。
  **本轮栽了两次**（`_web_search`、`LLM.call`）⇒ 只 spy **更下层**：
  真正的判点（`WebSearchGate.allow`）或官方打桩缝（`WebSearchClient._http`）。
- **插错位置 > 没插**：按键名找插入点（`find('"web_search"')`）会命中的**别处**，
  不报错、常规判据抓不到，却**静默改行为**（本轮：30 个开关插进
  `api.thinking.stages` ⇒ 全开时**强制关思考**）。
  ⇒ 凡按名字定位：**两段定位**（先找段起点、再在段内找键）+ **段内校验**
  （断言目标键在 `下一个段起点` 之前）。
- **「配了不做」要两向对账**：EML 的 `carve_first` / `tri_advisory_only` /
  `note_cost_no_gain` **各只出现 1 次**（候选生成处）⇒ `_eml_apply` 无分支
  ⇒ **生成→存库→召回但永不生效**。规则：**每个 `action.key` 必须有 `_eml_apply`
  分支，或在豁免表里显式登记并写原因**（配两向对账判据）。
- **读数是「日志」不是「啰嗦」**：`vp` 受 `output.verbose` 控制 ⇒
  `verbose=False` 时**静默吞掉**（第一版读数显示就这么错的）。
  要事后审计的东西一律走 `logger`。
- **同源渲染**：同一份内容在日志与产物两处显示时，**必须渲染自同一份数据**
  （最好是**同一个字符串** —— 如 `packed["readings_table"]`）⇒ 不可能漂移。
- **红线可以从「硬编码」改成「配置式」**（用户决策时可改）：修行层的
  「不注入」原为硬豁免，用户要求「所有层都注入」后改为**开关式保护**
  （默认全关 ⇒ 默认行为逐字不变；打开才生效）—— **保护没消失，只是可配了**，
  且必须在文档里**显式记档**是谁改的、为什么。
"""


def main():
    # ① 今日日志（append-only）
    src = io.open(DAY, encoding="utf-8").read()
    if "## 十六、v1.23.36" not in src:
        raw = io.open(DAY, "rb").read()
        assert raw.count(b"\r\n") == 0, "今日记忆应为 LF-only"
        s = raw.decode("utf-8").rstrip("\n") + "\n" + ADD_DAY
        io.open(DAY, "wb").write(s.encode("utf-8"))
        print("OK 今日记忆第十六节已追加，行数 %d" % s.count("\n"))
    else:
        print("今日记忆已有第十六节")

    # ② 长期约定（就地更新）
    raw2 = io.open(LONG, "rb").read()
    assert raw2.count(b"\n") == raw2.count(b"\r\n"), "MEMORY.md 应为纯 CRLF"
    s2 = raw2.decode("utf-8").replace("\r\n", "\n")
    if "v1.23.36 新增通则" not in s2:
        _anchor = "## 清理红线"
        assert s2.count(_anchor) == 1, "长期约定锚点命中 %d 次" % s2.count(_anchor)
        s2 = s2.replace(_anchor, ADD_LONG.strip() + "\n\n" + _anchor, 1)
        out2 = s2.replace("\n", "\r\n").encode("utf-8")
        assert b"\r\r\n" not in out2
        io.open(LONG, "wb").write(out2)
        print("OK 长期约定已更新；字符 %d" % len(out2.decode("utf-8")))
    else:
        print("长期约定已有 v1.23.36 段")


main()
