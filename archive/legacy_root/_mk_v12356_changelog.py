# -*- coding: utf-8 -*-
"""往 CHANGELOG.md 插 v1.23.56 段。纯 CRLF 往返。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "CHANGELOG.md"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")

SEC = """v1.23.56 相对 v1.23.55

【主题】快照记账改成**跨窗口累计**（`llm_calls` / `llm_tokens` 不再被续跑抹掉）。

【问题（A/B 真跑暴露）】快照里的计数取自 `self.llm.total_calls` —— 那是**按实例**
  的计数器。续跑新建实例就归零 ⇒ 第二个窗口的快照只记本窗口。实测：A 臂那条
  `V1255A` 实际花了 **230 calls**，快照里写的是 **97**。
  按这个数结算成本，**前面那个窗口的钱查不到** —— 直接打穿 v1.23.50 立命的
  「被杀跑次也能结算成本」。我这次只能另建外部账本兜底。

【修法】
  · `load_resume_snapshot` 把快照里的 `llm_calls` / `llm_tokens` 一起返回；
  · `run()` 拿到续跑快照时记进 `self._ck_base`（跨窗口基线），并把基线打进日志；
  · `_ckpt_snapshot` 落盘写 **累计 = 基线 + 本实例**，同时**另存**
    `window_calls` / `window_tokens` 保留本窗口读数。
    ⇒ **结算看累计，分析看窗口**，两个口径都能读。
  · **无新配置键**；不传 `resume_ckpt` ⇒ 基线为 0 ⇒ 数值与旧版**逐字相同**。

【判据更新】`check_v12350_resume` 里那条**静态字面量**断言
  `"llm_calls": int(getattr(_llm, "total_calls", 0) or 0),` 随实现失配 ⇒
  改成新字面量（登记式）。该 check 本来就有行为级断言（快照 `llm_calls > 0`），
  静态那条只是顺带指纹，留着继续挡"记账字段被删"。

---

★ v1.23.56 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.56.py`（26701 行 / 纯 CRLF）+ 冒烟新判据
`check_v12356_ckpt_cumulative` + 变异体 M107 + 本段。

**改了什么**：快照记账累计 + `window_*` 两口径；`load_resume_snapshot` 带回计数；
`run()` 设基线。7 个改动块 / 删 5 行 / 增 29 行；无新符号（325 / 589）。

**验收**：冒烟 255 ✓ / 0 ✗；`--phase all` PASS 319 / FAIL 0；AUDIT 69/0；
变异体 105/105（M107 判红）；app 自检 368/0；两版 `load_config` 逐字相同。
新判据两窗口真入口：第二窗口 `llm_calls` **恰好等于** 基线 + 本窗口，
且 `window_calls` 严格小于它（两口径分得开）；开发期另有**旧版对照**
（同链路跑 v1.23.55 ⇒ 第二窗口归零、没有 `window_calls` 字段）。

**未做**：`shape_limit` 取值扫描（6/8/12，各一跑 ≈¥12）；给
`gain_floor` / `eml_adaptive` / `eml_semantic_merge` 造可触发场景；更细粒度检查点。

"""

ANCHOR = "v1.23.55 相对 v1.23.54\n"
assert s.count(ANCHOR) == 1, "锚点命中 %d 次" % s.count(ANCHOR)
s = s.replace(ANCHOR, SEC + ANCHOR)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
p.write_bytes(out)
print("CHANGELOG.md：%d → %d 行（插入 v1.23.56 段）" % (n0, s.count("\n")))
