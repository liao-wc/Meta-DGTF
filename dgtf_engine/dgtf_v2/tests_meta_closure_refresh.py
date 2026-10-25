# -*- coding: utf-8 -*-
"""元层闭环清算刷新回归：池汇总之后必须重算 all.meta_closure。

真跑实测（2026-10-24 12:27）：all 层收尾时先算 meta_closure，随后
`_totalize_all_pool()` 才把跨层 engagements 汇总进 all 池 ⇒ 产物里的
meta_closure 仍是汇总前的 clean=False（t_001 实际已被 all 的 engagement
文本覆盖，相似度 1.00）⇒ process_ledger 的 all.standard_ok=False ⇒
process_ready=False。本判据锁 `_refresh_all_meta_closure` 的刷新语义。
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "engine" / "Meta-DGTF-V2.2.3.py"


def _load():
    spec = importlib.util.spec_from_file_location("metadgtf_meta_closure", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["metadgtf_meta_closure"] = mod
    spec.loader.exec_module(mod)
    return mod


ENG = _load()
P = []
F = []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if info and not ok else ""))


class _FakeView:
    def __init__(self):
        self.meta_closure = {}
        self.closure_reason = "stale"


def _fake_engine(duel, engagements):
    eng = object.__new__(ENG.MetaDGTF)
    eng.config = {"spiral": {"meta_cover_similarity": 0.7}}
    eng.pools = {"both": ENG.Pool(), "all": ENG.Pool()}
    eng.pools["both"].duel_suspensions = list(duel)
    eng.pools["all"].engagements = list(engagements)
    view = _FakeView()
    eng._results = {"all": view}
    return eng, view


def main():
    duel = [{"id": "t_001", "status": "active",
             "target": "夜间风与稳定度阈值判据"}]
    # ① 汇总前 clean=False，汇总后有跨层 engagement（换说法）⇒ 刷新后 clean=True
    eng, view = _fake_engine(duel, [])
    eng._refresh_all_meta_closure()
    ck("无交代时 clean=False", view.meta_closure.get("clean") is False, view.meta_closure)
    ck("未交代理由写进 closure_reason",
       "meta_unsettled" in (view.closure_reason or ""), view.closure_reason)

    eng, view = _fake_engine(duel, [{"target": "夜间风与稳定度的阈值判据"}])
    eng._refresh_all_meta_closure()
    ck("汇总后按文本相似度覆盖 ⇒ clean=True",
       view.meta_closure.get("clean") is True, view.meta_closure)
    ck("clean 后清空 closure_reason", view.closure_reason == "", view.closure_reason)

    # ② 负对照：相似度不达标（不同张力）仍算未交代
    eng, view = _fake_engine(duel, [{"target": "城市站公园还是路口"}])
    eng._refresh_all_meta_closure()
    ck("不相似不冒充覆盖", view.meta_closure.get("clean") is False, view.meta_closure)

    # ③ 按 id 覆盖（tension_id 对上）
    eng, view = _fake_engine(duel, [{"tension_id": "t_001", "target": "别的说法"}])
    eng._refresh_all_meta_closure()
    ck("按 tension_id 覆盖 ⇒ clean=True",
       view.meta_closure.get("clean") is True, view.meta_closure)

    # ④ 没有 all 视图 / 没有 _results 时不得抛错
    eng, _ = _fake_engine(duel, [])
    eng._results = {}
    eng._refresh_all_meta_closure()
    ck("无 all 视图时不抛错", True)

    print()
    print("PASS %d / FAIL %d" % (len(P), len(F)))
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
