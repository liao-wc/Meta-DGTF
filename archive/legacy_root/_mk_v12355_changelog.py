# -*- coding: utf-8 -*-
"""往 CHANGELOG.md 插 v1.23.55 段（最新在最前）。纯 CRLF 往返。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "CHANGELOG.md"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")

SEC = """v1.23.55 相对 v1.23.54

【主题】`paused` 时的缺层从「❌ 缺陷」改成「⏸ 待续」。

【问题（A/B 真跑时亲眼看到）】墙钟预算暂停的跑次会打：

    ❌ 缺层：请求了但这些层没有产出 —— 这份产物是不完整的
    · 元：未记录原因（这是缺陷）

可暂停时缺层是**设计**（续跑会接着跑）。这条提示会让人去查一个不存在的 bug；
更糟的是它把 `layer_gap` 写进产物 ⇒ **下游任何「缺层 = 缺陷」的判据都跟着误判**。

【修法】`_layer_guard` 把缺层拆两拨：
  · 在 `pending_layers` 里且 `packed["paused"]` ⇒ 记 `paused_gap`，说"待续"
    （提示 `resume_ckpt`），**不写** `layer_gap`；
  · 其余 ⇒ 仍是真缺陷，`layer_gap` 原样大声报。
  ★ 真缺陷**不许**被暂停豁免：暂停时某层既没产出、也不在 pending 里，照样报红。
  ★ 无新配置键；**非暂停路径逐字不变**。

---

★ v1.23.55 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.55.py`（26677 行 / 纯 CRLF）+ 冒烟新判据
`check_v12355_paused_gap` + 变异体 M106 + 本段。

**改了什么**：`_layer_guard` 拆分「待续 / 真缺」两条分支；docstring 补说明；
版本号两处。4 个改动块 / 删 14 行 / 增 39 行；无新符号（325 条 / 589）。

**验收**：冒烟 254 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 104/104（M106 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
新判据三臂：暂停+pending ⇒ 只记 `paused_gap`；暂停+非 pending ⇒ 仍报 `layer_gap`；
非暂停 ⇒ 旧行为逐字不变（旧判据 `check_layer_guard` 同时仍绿）。

**未做**：元层单层对照（`route=["all"]`）**实测不成立** —— 层守卫直接拒绝
（「需要至少 2 个上游 view，当前只有 0 个」），只花了 1 次调用。要定性元层那个
分歧只能再跑一次全跑（≈¥7.8）。

"""

ANCHOR = "v1.23.54 相对 v1.23.53\n"
assert s.count(ANCHOR) == 1, "锚点命中 %d 次" % s.count(ANCHOR)
s = s.replace(ANCHOR, SEC + ANCHOR)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
p.write_bytes(out)
print("CHANGELOG.md：%d → %d 行（插入 v1.23.55 段）" % (n0, s.count("\n")))
