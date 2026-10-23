# -*- coding: utf-8 -*-
"""往 CHANGELOG.md 插 v1.23.54 段（最新在最前）。纯 CRLF 往返。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "CHANGELOG.md"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")

SEC = """v1.23.54 相对 v1.23.53

【主题】并行跑次也能被**墙钟预算**截住、也能**续跑**。

【问题】`max_minutes` 原来只挂在 `_run_serial` 的**层间**守卫上 ⇒ 并行模式
  （A/B/C + D~H）设了预算也照跑到天亮，宿主一回收就**全丢**；而续跑入口又
  **硬拒非 serial** ⇒ 强杀之后连"续"都续不了。**预算保护对并行是空的** ——
  而真跑最常见的死法恰恰是"跑太久被宿主回收"。

【修法】
  · `_wall_clock_over()` 收成**唯一**判据（原来 serial 里内联了一份）。
  · **三个**单层执行器的圈边界都判（漏一个，那些模式就还是裸跑）：
    `_run_layer`（serial + A/B）／C 模式自己的圈循环／`_run_layer_stage`（D~H）。
    到点 ⇒ 该层进 `_paused_rest`，`stop_reason` 带「墙钟预算」标记 ⇒ 整跑 `paused`。
  · serial 层间守卫从「重绑」改「**并集**」：截断层有 view 但仍未跑完，
    重绑会把它丢掉（续跑于是当它已完成 —— 分片跑永远跑不完整）。
  · `load_resume_snapshot`：不再拒绝并行快照，改记源模式；并把带标记的层从
    views/pools **摘掉**（截断层不算完成，续跑重跑它）。
  · `run()` 派发：并行续跑**一律按 serial 跑剩余层**，产物记 `resumed_serial`
    —— 降级留痕，不静默。
  · **无新配置键**；`max_minutes` 默认 0 / 不传 `resume_ckpt` ⇒ 逐字零行为差。

【一个必须知道的细节】`stop_reason` 是**逐圈在循环体末尾**拼的，圈首 break 会跳过
  那一步 ⇒ 标记必须**直接盖到 view 上**。第一版只写了 `_budget_stop_note`，
  判据当场逮到「续跑什么都不重跑」——**假修**。

【判据更新】`check_v12350_resume` 里「mode 非 serial ⇒ 必须拒绝」那条负对照，
  编码的是旧语义 ⇒ 改成「`mode=B` ⇒ 允许 + 必须记下 `src_mode`」。
  这不是放宽，是把断言对准新语义（「题面不同 ⇒ 拒绝」不变）。

---

★ v1.23.54 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.54.py`（26652 行 / 纯 CRLF）+ 冒烟新判据
`check_v12354_parallel_wall_clock` + 变异体 M105 + 本段。

**改了什么**：`_wall_clock_over()` 唯一判据；三个单层执行器圈边界判墙钟 + 标记
直接盖到 view；serial 层间守卫改并集；续跑放开并行 + 摘截断层；派发降级记
`resumed_serial`。12 个改动块 / 删 25 行 / 增 110 行；AST 登记 +1 符号（589）。

**验收**：冒烟 253 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 103/103（M105 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
开发期 16 项全过：真入口证明「A 模式到点 ⇒ paused + 标记 + EML 零写入」，
续跑证明「完成的层不重跑、截断层重跑、层 0 产物逐字复用」。

**未做**：下一轮 A/B（须冻结 bandit + 同口径比 S，**要花钱，等你点头**）；
并行模式的「层内更细粒度」检查点（现在是圈边界，一个圈跑不完仍会超时）。

"""

ANCHOR = "v1.23.53 相对 v1.23.52\n"
assert s.count(ANCHOR) == 1, "锚点命中 %d 次" % s.count(ANCHOR)
s = s.replace(ANCHOR, SEC + ANCHOR)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
p.write_bytes(out)
print("CHANGELOG.md：%d → %d 行（插入 v1.23.54 段）" % (n0, s.count("\n")))
