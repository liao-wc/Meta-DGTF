# -*- coding: utf-8 -*-
"""成本归因 · 真实入口判据（两臂对照）。

为什么需要
----------
`tests_cost_attribution.py` 只证明「源码里每处调用都带 stage」。那是**静态**判据：
它证明不了这个 stage 真的走到 `LLM.call` 的统计分支里 —— 而本项目反复吃过
「纯函数判据全绿 ≠ 能力在引擎里可达」的亏（调用点被守卫/去重/默认值挡死）。

本文件驱动**真实入口**：拿 `MetaDGTF._expand_pair` 本体跑一遍，走真实的
`LLM.call` → 真实的 `stage_calls/stage_tokens` 累加，只用底层 `openai` client 打桩
（★ 打桩必须打在**最底层**；把 `LLM.call` 整体换掉等于把被测对象一起换掉，
观测恒空）。

两臂对照（同一把尺子）
----------------------
· 旧臂 V2.2.4（改造前）：应落 `unknown`
· 新臂 V2.2.5（改造后）：应落 `expand_pair`，`unknown` 归零
· 两臂解析出的候选**数量与内容必须逐字相同** ⇒ 证明「只加标签、不改行为」

任何一臂缺失或读数相同，都说明这个判据没在测东西。
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import re
import sys
from types import SimpleNamespace

V2 = pathlib.Path(__file__).resolve().parent
ENG = V2 / "engine"
sys.path.insert(0, str(V2.parent))

PASS, FAIL = [], []

#: 桩输出：两行合法候选（5~200 字、无问号堆叠），足以走通解析与去重
STUB_TEXT = (
    "- [concept] 用于验证成本归因是否真正落到统计分支的占位候选甲\n"
    "- [risk] 另一个占位候选乙用来确认候选解析路径未被本次改动影响\n"
)

ORDER = [("阴", "SYSTEM-YIN"), ("阳", "SYSTEM-YANG")]

#: ★ 改造前的最后一个版本 —— 旧臂的**固定基座**（不用「上一版」）。
#:   「上一版」会随改版向前滚动，滚过改造点之后旧臂也是修好的，
#:   于是「旧臂应落 unknown」变成假红（V2.2.6 那轮实测踩过）。
BASELINE_BEFORE_FIX = "Meta-DGTF-V2.2.4.py"


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("  OK  " if ok else "  FAIL") + " " + name +
          (("  — " + str(detail)) if detail else ""))


def _versions():
    out = []
    for p in ENG.glob("Meta-DGTF-V*.py"):
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
        if m:
            out.append((tuple(int(x) for x in m.groups()), p))
    return sorted(out)


def _load_mod(path: pathlib.Path, tag: str):
    spec = importlib.util.spec_from_file_location(tag, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[tag] = mod
    spec.loader.exec_module(mod)
    return mod


class _FakeCompletions:
    def create(self, **kw):
        return SimpleNamespace(
            model=str(kw.get("model") or "stub"),
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=STUB_TEXT),
                finish_reason="stop")],
            usage=SimpleNamespace(total_tokens=42),
        )


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def drive(path: pathlib.Path, tag: str) -> dict:
    """驱动真实 `_expand_pair`，返回观测到的读数。"""
    os.environ.setdefault("DGTF_API_KEY", "test-key-for-live-check")
    mod = _load_mod(path, tag)

    orig = mod.openai.OpenAI
    mod.openai.OpenAI = lambda **kw: _FakeClient()   # ★ 只打底层 client
    try:
        cfg = {
            "api": {"key": "test-key-for-live-check", "default_model": "stub",
                    "base_url": "http://127.0.0.1:1/v1", "timeout": 2},
            "actions": {"expand_yin": True, "expand_yang": True,
                        # 关掉合并与并行 ⇒ 走**串行两臂独立调用**这条主路径
                        "merge_expand": False, "parallel_expand": False},
        }
        llm = mod.LLM(cfg)
        obj = mod.DGTF.__new__(mod.DGTF)      # 不跑 __init__，只补所需状态
        obj.llm = llm
        obj.config = cfg
        obj.vp = lambda *a, **k: None
        obj._quant_pending_yy = None

        cands = obj._expand_pair(list(ORDER), lambda label: "USER-" + label)
        return {
            "stage_calls": dict(getattr(llm, "stage_calls", {}) or {}),
            "stage_tokens": dict(getattr(llm, "stage_tokens", {}) or {}),
            "total_calls": int(getattr(llm, "total_calls", 0) or 0),
            "d1": [c.desc for c in cands],
            "n": len(cands),
        }
    finally:
        mod.openai.OpenAI = orig


def main():
    vs = _versions()
    check("至少两个版本可对照", len(vs) >= 2, [p.name for _, p in vs])
    if len(vs) < 2:
        print("\nPASS %d / FAIL %d" % (len(PASS), len(FAIL)))
        return 1

    _, new_p = vs[-1]
    old_p = ENG / BASELINE_BEFORE_FIX
    if not old_p.exists():
        check("旧臂基座存在（改造前版本不应被删）", False, str(old_p.name))
        print("\nPASS %d / FAIL %d" % (len(PASS), len(FAIL)))
        return 1
    print("  新臂：%s\n  旧臂：%s" % (new_p.name, old_p.name))

    try:
        old = drive(old_p, "_eng_old")
    except Exception as e:
        check("旧臂可驱动", False, "%s: %s" % (type(e).__name__, e))
        old = None
    try:
        new = drive(new_p, "_eng_new")
    except Exception as e:
        check("新臂可驱动", False, "%s: %s" % (type(e).__name__, e))
        new = None

    if old and new:
        # ── 1. 两臂都真的发出了两次调用（否则「对照」是空的）──────────
        check("两臂都发出 2 次真实调用",
              old["total_calls"] == 2 and new["total_calls"] == 2,
              "old=%d new=%d" % (old["total_calls"], new["total_calls"]))

        # ── 2. 旧臂确实落在 unknown（证明改造前是盲区）──────────────
        check("★ 旧臂成本落在 unknown（改造前盲区确实存在）",
              old["stage_calls"].get("unknown", 0) == 2
              and not old["stage_calls"].get("expand_pair"),
              old["stage_calls"])

        # ── 3. 新臂全部归因到 expand_pair，unknown 归零 ──────────────
        check("★ 新臂全部归因到 expand_pair",
              new["stage_calls"].get("expand_pair", 0) == 2,
              new["stage_calls"])
        check("★ 新臂 unknown 归零",
              new["stage_calls"].get("unknown", 0) == 0,
              new["stage_calls"])
        check("新臂 tokens 同步归因（不是只有 calls）",
              new["stage_tokens"].get("expand_pair", 0) > 0,
              new["stage_tokens"])

        # ── 4. 行为不变：候选数量与内容逐字相同 ─────────────────────
        check("★ 两臂候选数量相同（行为不变）",
              old["n"] == new["n"] and new["n"] > 0,
              "old=%d new=%d" % (old["n"], new["n"]))
        check("★ 两臂候选内容逐字相同（只加标签不改输出）",
              old["d1"] == new["d1"],
              "" if old["d1"] == new["d1"] else "内容不一致")

        # ── 5. 归因没把调用算到别的桶 ─────────────────────────────
        check("新臂没有任何其它 stage 被顺带记账",
              set(new["stage_calls"]) == {"expand_pair"},
              sorted(new["stage_calls"]))

    print("\nPASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print("  - " + f)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
