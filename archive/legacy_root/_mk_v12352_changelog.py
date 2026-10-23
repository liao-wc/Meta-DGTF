# -*- coding: utf-8 -*-
"""往 CHANGELOG.md 插 v1.23.52 段（最新在最前）。纯 CRLF 往返。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "CHANGELOG.md"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")

SEC = """v1.23.52 相对 v1.23.51

【主题】`paused` 跑次**不写 EML 库**：半程样本不是证据。

【问题】上一版只保证「不重复调用就不多写」。可墙钟预算暂停的跑次**仍会写一条
  半程样本**；续跑跑完后同一个 `run_id` 又写一条完整样本（读数不同 ⇒ 幂等守卫
  **按设计**放行）⇒ 一个跑次还是**两条证据**：`used_outcomes` 记两笔、`weight`
  罚两遍。清账脚本 `_fix_eml_dup_20261016.py` 收拾的正是这一类 —— 上一版只堵了
  「重复调用」这一个口子，没堵「同一跑次分两次收尾」这个口子。

【修法】
  · `_eml_finish` 在 `off` 判完之后**先判暂停**：产物带 `paused` 或
    `pending_layers` ⇒ 直接返回（`skipped_paused`）—— **连库目录都不建、也不抢锁**。
  · 判据取自**产物本身**（`run()` 在调 `_eml_finish` 之前就写好了这两个键），
    所以不依赖调用方传参，任何入口口径一致。
  · **成本不会丢**：`llm_calls` / `llm_tokens` 仍在产物与快照里 ⇒ 暂停/被杀的
    跑次照样能结算。
  · **无新配置键**；`max_minutes` 默认 0 ⇒ 守卫条件恒假 ⇒ 默认行为逐字不变。

---

★ v1.23.52 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.52.py`（26546 行 / 纯 CRLF）+ 冒烟新判据
`check_v12352_paused_no_eml` + 变异体 M103 + 本段。

**改了什么**：`_eml_finish` 加「暂停不写库」守卫（off 之后、取锁之前）；版本号两处；
docstring 补一句。3 个改动块 / 增 16 行。

**验收**：冒烟 251 ✓ / 0 ✗（含新判据）；`--phase all` PASS 319 / FAIL 0；
AUDIT 69/0；变异体 101/101（M103 判红 = 判据有牙）；app 自检 368/0；
两版 `load_config` 逐字相同。**不跑真跑**：默认 `max_minutes=0` ⇒ 守卫恒不触发，
真跑行为与 v1.23.51 逐字相同；能力由「真入口 `run(max_minutes=极小)` ⇒ 零写入」
的构造性判据证明，另有**旧版对照**（v1.23.51 同场景写 1 条）。

**未做**：并行模式续跑；记忆库目录解析归一（bandit 走 `eml_dir()`、不吃
`playbook.dir`）；下一轮 A/B（须冻结 bandit + 同口径比 S）。

"""

ANCHOR = "v1.23.51 相对 v1.23.50\n"
assert s.count(ANCHOR) == 1, "锚点命中 %d 次" % s.count(ANCHOR)
s = s.replace(ANCHOR, SEC + ANCHOR)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
p.write_bytes(out)
print("CHANGELOG.md：%d → %d 行（插入 v1.23.52 段）" % (n0, s.count("\n")))
