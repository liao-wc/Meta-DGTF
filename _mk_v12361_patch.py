# -*- coding: utf-8 -*-
"""v1.23.60 → v1.23.61：`run()` 的**空题守卫**（拒绝运行，不凭空产出、不花钱）。

问题（健壮性探针发现）：
  退化输入 9 例没有一个把引擎打挂 —— 但 **`run("")` 照样跑了，产出 2 个候选**。
  空题没有任何可研究的东西，跑下去只会产生**凭空编造的候选**，违背项目红线
  「没有读数就不假装有 / 未对齐要如实说」。而且它**白花一次调用**。

  app 那边有挡（`server.py` 里 `if not question: 400`），但**引擎是库** ——
  任何脚本（包括我自己的探针）都能直接传空串。

修法：
  `run()` 在**任何 LLM 调用之前**检查 `str(question).strip()`；
  为空 ⇒ 立刻返回一个**结构化拒绝**：
    `refused = {reason: "empty_question", why: ...}`、`views={}`、
    `llm_calls=0`、`llm_tokens=0`，并 `vp` 一行说明。
  ★ 不是抛异常（会打断调用方），也不是 `paused`（那是"没跑完"，这是"不该跑"）。

无新配置键；题面非空 ⇒ 行为逐字不变。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.60.py"
DST = HERE / "元DGTF-V1.23.61.py"

raw = SRC.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")


def rep(old, new, what, expect=1):
    global s
    c = s.count(old)
    assert c == expect, "%s：命中 %d 次（要求 %d）" % (what, c, expect)
    s = s.replace(old, new)
    print("  [OK] %s" % what)


# ── 1) 空题守卫 ────────────────────────────────────────────────────
rep('''        route = route or ["0", "1", "both", "all"]
        self._ext_assess_cache = {}''',
    '''        # ★★ [空题守卫] 空题**不跑**：没有可研究的东西，跑下去只会凭空编造候选
        #   （违背「没有读数就不假装 / 未对齐如实说」），而且白花一次调用。
        #   放在任何 LLM 调用之前 ⇒ 拒绝是零成本的。
        #   ★ 不抛异常（会打断调用方）；也不用 `paused`（那是"没跑完"，这是"不该跑"）。
        if not str(question or "").strip():
            self.vp("\\n⛔ 拒绝运行：题面为空 —— 没有可研究的东西")
            self.vp("   （空题硬跑只会产出凭空编造的候选，违背「不假装」红线）")
            return {"id": self._run_id, "question": str(question or ""),
                    "route": [], "views": {}, "pools": {},
                    "rounds": {}, "llm_calls": 0, "llm_tokens": 0,
                    "paused": False, "pending_layers": [],
                    "refused": {"reason": "empty_question",
                                "why": "题面去空白后为空；空题不跑（不凭空产出）"}}
        route = route or ["0", "1", "both", "all"]
        self._ext_assess_cache = {}''',
    "run() 空题守卫")

# ── 2) 版本号 ──────────────────────────────────────────────────────
rep("元 DGTF · v1.23.60\n", "元 DGTF · v1.23.61\n", "docstring 标题")
rep('__version__ = "1.23.60"\n', '__version__ = "1.23.61"\n', "__version__")

ast.parse(s)
assert s.count('"reason": "empty_question"') == 1
assert s.count("if not str(question or \"\").strip():") == 1
print("  [OK] 结构性自检：守卫在任何 LLM 调用之前（返回体里 llm_calls=0）")

n1 = s.count("\n")
print("  [OK] 行数 %d → %d（+%d）" % (n0, n1, n1 - n0))

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
DST.write_bytes(out)
print("\n写出 %s（%d 字节 / %d 行 / 纯 CRLF）"
      % (DST.name, len(out), out.count(b"\r\n")))
