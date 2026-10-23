# -*- coding: utf-8 -*-
"""CHANGELOG 加 v1.23.36 段（联网全接 + 读数全量 + 三层 trace + 控制面）。"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "CHANGELOG.md"

ANCHOR = "---\n\nv1.23.34 相对 v1.23.33"

NEW = """---

v1.23.36 相对 v1.23.34

【主题】**联网全接 + 读数全量显示 + 决策可追溯 + 显式控制面**
—— 「自由调度 × 自我学习一体」的三件地基（用户口径见下）。

  用户指令（本版）：
  ① 「联网全接**配置可控开关**」；
  ② 「**所有层都注入**」；
  ③ 「运行中和结束时所有读数都**完整显示在日志中**，同时**结构化显示在产物文档中**」；
  ④ 「自由调度和自我学习是**一体**的，渗透到整个元DGTF的运行中，所有行为逻辑都有
     **追溯和可控性**；先检索最前沿技术和算法和学科知识进行融合创新并应用于元DGTF」。

【五条前沿依据（逐条对应一处落地）】
  ① ★★ **E³-Agent**（arXiv 2605.27428, 2026）—— **快慢双路径 + 显式控制面**：
     毫秒级调度（fast-path）与事件驱动的 LLM 元控制器（slow-path）分开，两者经
     **一个小的、显式的控制面**连接；**从执行反馈在线学习**。
     ⇒ 落地 `ControlSurface`（所有运行时调度调整的唯一收口）。
  ② ★ **Heartbeat-Driven Activity Scheduling**（arXiv 2604.14178, 2026）——
     用**周期性心跳主动**编排（不是等失败才反思），策略由**历史日志元学习**改进。
     ⇒ 落地方向：`_before_round`（已是两条通道共用的「圈前统一动作」）作心跳位。
  ③ ★ **MetaClaw**（arXiv 2603.17187, 2026）—— **双时间尺度学习**：快适应
     （单次失败⇒合成技能⇒零停机注入）与慢适应（策略优化）**互相强化**。
     ⇒ 与既有 EML（`shadow→on` 为慢、`_eml_note_contra` 为快）对齐。
  ④ ★★ **可追溯三层**（agent observability, 2026）—— **L1 决策（why，含
     「考虑过的选项」）/ L2 动作（what）/ L3 归因（did it matter）**；
     OpenTelemetry 的 **`decision.chain` span kind** 与 **Decision Log Format**
     都要求**记录被否的选项**（审计要看得见「没走的路」）。
     ⇒ 落地 `_trace_note` / `trace_decide` / `trace_outcome` + `view.trace_log`。
  ⑤ ★ **Observing ≠ Auditability**（specswriter）—— 观测平台会**采样/截断**，
     **审计级不许采样**；另记「不到 5% 的部署 agent 记录了 temperature/top-k/seed」
     ⇒ 参数要变成**可追溯属性**。⇒ 落地：trace **全量不截断**。

【落地一：联网全接（一处改覆盖 30 个环节）】
  · **30 个环节**（AST 实测：含 LLM 调用的函数，扣 `_call_long`）——
    原先只有 **7 个**能联网，**差 23 个**；
  · 实现放在 **`LLM.call`**（所有环节的必经之路）：新增 `_web_augment`，
    按需给该环节的 prompt 挂「外部参考」段 ⇒ **一处改、全部生效**
    （逐处改 30 个 prompt 既慢又散、且必然漏）；
  · **依赖注入**：`LLM` 是模块级类、拿不到 `_web_search`（它在 `MetaDGTF` 上）
    ⇒ 用 **thread-local 上下文**注入 `web_searcher` / `question` / `entry` / `round`
    （thread-local 是因为并行模式下多层同进程多线程，全局变量会串台）；
  · **stage 推断**：多数调用点没显式传 `stage=` ⇒ 从**调用栈**推断环节名
    （`_infer_stage_from_stack`，去前导下划线）⇒ 30 个环节**各自一个开关**；
  · **配置**：`web_search.stages` 从 7 键 → **37 键**（新增 30 个环节开关，默认
    **全 false**）；配置叶子键 **193 → 223**。
  · ★ **零行为差**：总闸 `web_search.enabled` 出厂 false ∧ 逐环节默认 false
    ⇒ 不打开就与今天逐字相同。

【落地二：★ 红线调整（用户指令）—— 「所有层都注入」】
  · 原实现按 yaml 注释（「修行层联网会污染『输入是形状不是数据』」）设了
    **修行层硬豁免**（entry == "0" 永不注入）；
  · 用户指令「**所有层都注入**」⇒ **硬豁免取消**；
  · ★ 保护**没有消失，而是从硬编码改成配置式**：30 个环节开关出厂全 false
    ⇒ 不打开就不注入（默认行为逐字不变）；要注入须**显式打开**（谁开谁负责）。
  · ★ `practice_term_calibration`（修行层术语校准）**仍只留痕、不注入** ——
    它与本条是两条独立路径，本次不动它。

【落地三：读数全量显示（日志 + 产物同一份）】
  · 新增 `_readings_bundle`（**单一真相源**：把一层的全部读数收成一个 dict）→
    `_readings_line`（运行中一行）/ `_readings_table`（结束总表 + Markdown 版）；
  · 三处显示：**运行中**每层一行（`logger.info`，★ **不受 verbose 控制** ——
    走 `vp` 会被 `verbose=False` 静默吞掉，第一版正是这么错的）；
    **结束**时跨层总表；**产物** md 的「## 读数总表（四层）」表格；
  · ★ 日志版与产物版**渲染自同一份 bundle**，且产物那张表是**日志那次渲染的
    同一个字符串**（`packed["readings_table"]`）⇒ **不可能漂移**。

【落地四：可追溯地基（三层 trace）】
  · `View.trace_log` 字段 + `_trace_note`（**模块级**写入口：调用点分布在
    `DGTF`/`MetaDGTF` 两类无继承关系的类上，做成方法会解析不到）；
  · `trace_decide`（**必须带「考虑过的全部选项」**，没有备选就不算决策）+
    `trace_outcome`（动作前后的读数对比 = EML 唯一能依赖的学习信号）；
  · ★ **空值不写**（缺读数 ≠ 读数是空）；★ **不采样、不截断**（审计级）。

【落地五：显式控制面 `ControlSurface`】
  · 白名单 + 边界 + **必留痕**（缺 `why`/`trace_ref` ⇒ 拒；越界 ⇒ 拒，**不夹取**）；
  · **接线**到 EML 的 `_eml_apply`（`rounds_delta` / `duty_floor` 两处写入改经它）
    —— ★ 是**接线**不是**登记豁免**：审计判据「A2 死类已登记」抓到它「定义后零引用」，
      正确修法是让它真的被用（这正是「可控性本体」）；
  · **绝不写配置**（红线：建议与执行分开）——只改内存态，快照可进产物对账。

【★ 两个插错位置的事故（都已修，值得记）】
  ① 30 个开关**插进了 `api.thinking.stages`**（不是 `web_search.stages`）——
     `s.find('"web_search"')` 命中的是别处。★ 危害不只是"位置丑"：那些 `False`
     会让环节的思考档**优先返回 False** ⇒ **全开时被强制关思考**（行为退化）。
     修法：撤销 + 用「先找段起点、再在段内找键」的**两段定位**，并加**段内校验**。
  ② `practice_term_calibration` / `stop_criteria` 的判据断言「默认关时走到 Gate」
     —— 但那两个方法**开头就判 `enabled`**（与既有 `_research_web_prep` 同惯例）
     ⇒ 根本不调 `_web_search`。判据改为断言**结果**（零检索 + 没走到 Gate）。

【验收】判据 `check_v12336_allweb`（源码级 + **构造性**：未接线不增强 /
  总闸关不增强 / 开+授权即增强 / **四层全可注入** / 未授权被 Gate 拒且有拒因）
  + `check_v12336_readings`（**三处显示 + 同源核对**：日志表与产物表的圈数必须一致）。
  变异体见 `_mut_v12332.py`（M60 起）。

---

v1.23.34 相对 v1.23.33"""


def main():
    raw = P.read_bytes()
    assert raw.count(b"\r\n") == 0, "CHANGELOG 应为 LF-only"
    s = raw.decode("utf-8")
    assert s.count(ANCHOR) == 1, "锚点命中 %d 次" % s.count(ANCHOR)
    s = s.replace(ANCHOR, NEW, 1)
    io.open(P, "wb").write(s.encode("utf-8"))
    print("OK CHANGELOG 已加 v1.23.36 段；行数 %d" % s.count("\n"))


main()
