#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P5/P6] 把 `check_v1221_p5` / `check_v1221_p6` 追加进检查仓库，
并把冒烟 SRC 指向 rc3。

★ 本文件**不写反斜杠**：需要引号/花括号一律用 chr() 或 json.dumps 拼，
  避免「多级转义吃掉一层反斜杠」那个老坑。所有换行用 chr(10)。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

CR = chr(13)
LF = chr(10)
NL = chr(10)
REPO = Path("_v1221_checks.py")
INJ = Path("_mk_v1221_smoke_checks.py")

FUNC5 = '''def check_v1221_p5(SRC=None):
    """[v1.22.1 P5] auto 取向回填：判定留痕 + 错配告警。

    ★ 任务书前提与实现不符：`auto_plan` 的**单调用**分支（`run()` 走的就是
      它）原来不带 `orientation`，所以 `_auto_plan_used` 永远没有取向。
      本检查直接**打桩跑一次 `auto_plan`**，锁「同一次调用里带出取向」。
    """
    try:
        NL = chr(10)
        Q = chr(34)
        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        # 1/2 静态串
        assert "_auto_plan_used" in src, "run()/_pack_result 未记 _auto_plan_used"
        assert "取向判定（plan_orientation）" in src, "缺头部「取向判定」行"
        assert "取向错配" in src, "缺「取向错配」告警"

        # 3 auto_plan 单调用分支要解析并带出 orientation
        _i0 = src.find("def auto_plan(")
        _i1 = src.find(NL + "def ", _i0 + 10) if _i0 >= 0 else -1
        _body = src[_i0:_i1] if _i0 >= 0 and _i1 > _i0 else src[_i0:]
        assert ("data.get(" + Q + "orientation" + Q + ")") in _body, (
            "auto_plan 未解析 orientation")
        assert _body.count(Q + "orientation" + Q + ": _ori") >= 2, (
            "auto_plan 的早退分支没把 orientation 带出")

        # 4 行为：打桩一次调用，验带出 + 只调一次 + prompt 里要了取向
        class _StubLLM:
            def __init__(self):
                self.calls = []

            def call(self, system, user, *a, **kw):
                self.calls.append((system, user))
                import json as _j
                return _j.dumps({"mode": "serial",
                                 "orientation": "boundary",
                                 "rounds": {"0": 4, "1": 4,
                                            "both": 4, "all": 5},
                                 "reason": "桩", "confidence": 0.9})

            def parse_json(self, raw):
                import json as _j
                return _j.loads(raw)

        _st = _StubLLM()
        _plan = m.auto_plan("地铁运营效率该怎么衡量？",
                            dict(m.DEFAULT_CONFIG), llm=_st)
        assert _plan.get("orientation") == "boundary", (
            "orientation 未带出：" + repr(_plan.get("orientation")))
        assert len(_st.calls) == 1, "单调用路径被改成多次（成本变化）"
        assert "orientation" in _st.calls[0][0], "prompt 里没要取向"

        # 5 负对照：桩回一个非法取向 → 归一成空串（不许把垃圾当取向）
        class _Stub2(_StubLLM):
            def call(self, system, user, *a, **kw):
                self.calls.append((system, user))
                import json as _j
                return _j.dumps({"mode": "serial", "orientation": "随便"})

        _p2 = m.auto_plan("x", dict(m.DEFAULT_CONFIG), llm=_Stub2())
        assert not _p2.get("orientation"), "非法取向竟被采纳：" + repr(_p2)

        print("  ✓ v1.22.1 P5：判定留痕 + 错配告警 + 单调用带出取向（打桩实测）"
              " + 非法取向归一负对照")
        return True
    except Exception as e:  # noqa: BLE001
        print("  ✗ v1.22.1 P5 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False


'''

FUNC6 = '''def check_v1221_p6(SRC=None):
    """[v1.22.1 P6] tier 全缺省时的显式提示。

    ★ 任务书骨架在 `out` 上数「谁没声明 tier」—— 而 `out` 里每条都补了
      缺省 3，计数恒为 0，警告**永远不触发**。这里在**原始条目**上判，
      并用两份临时锚点文件做正/负对照。
    """
    try:
        import json as _json
        from pathlib import Path as _P
        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        assert "_anchor_tier_warning" in src, "缺 _anchor_tier_warning"
        assert "锚点 tier 警告" in src, "缺头部「锚点 tier 警告」行"

        _notier = _P("_smoke_p6_notier.json")
        _notier.write_bytes(_json.dumps(
            {"anchors": [{"id": "a1", "claim": "x"},
                         {"id": "a2", "claim": "y"}]},
            ensure_ascii=False).encode("utf-8"))
        _onetier = _P("_smoke_p6_onetier.json")
        _onetier.write_bytes(_json.dumps(
            {"anchors": [{"id": "a1", "claim": "x"},
                         {"id": "a2", "claim": "y", "tier": 1}]},
            ensure_ascii=False).encode("utf-8"))

        def _load(path):
            cfg = _json.loads(_json.dumps(m.DEFAULT_CONFIG, default=str))
            cfg["external_anchor"] = dict(cfg.get("external_anchor") or {})
            cfg["external_anchor"].update({"enabled": True, "path": str(path)})
            cfg["output"] = dict(cfg.get("output") or {})
            cfg["output"]["verbose"] = False
            mm = m.MetaDGTF(cfg)
            mm._load_anchors()
            return getattr(mm, "_anchor_tier_warning", "<无属性>")

        try:
            w_all = _load(_notier)
            w_one = _load(_onetier)
            assert isinstance(w_all, str) and w_all, (
                "全缺省竟无警告（正对照失败）：" + repr(w_all))
            assert not w_one, (
                "有显式 tier 仍有警告（负对照失败）：" + repr(w_one))
        finally:
            _notier.unlink(missing_ok=True)
            _onetier.unlink(missing_ok=True)

        # 红线保留：无 tier 的锚点**不进引用表**（即便挂了 evidence 档）
        _p1 = m.Pool()
        _p1.anchors = [{"id": "a1", "claim": "X"}]
        _p1.anchor_as_evidence = True
        _t1 = m._citation_table(None, _p1)
        assert not any(c.startswith("X") for c, _ in _t1), (
            "无 tier 的锚点竟进了引用表（红线破了）")
        _p2 = m.Pool()
        _p2.anchors = [{"id": "a2", "claim": "Y", "tier": 1}]
        _p2.anchor_as_evidence = True
        _t2 = m._citation_table(None, _p2)
        assert any(c.startswith("X") for c, _ in _t2), (
            "有 tier=1 的锚点却进不了引用表")

        print("  ✓ v1.22.1 P6：全缺省告警（正对照）+ 有显式 tier 不告警（负对照）"
              " + 无 tier 不入引用表（红线）")
        return True
    except Exception as e:  # noqa: BLE001
        print("  ✗ v1.22.1 P6 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False


'''


def main() -> int:
    t = REPO.read_bytes().decode("utf-8").replace(CR + LF, LF)
    for name, fn in (("check_v1221_p5", FUNC5), ("check_v1221_p6", FUNC6)):
        i = t.find("def " + name)
        if i >= 0:
            t = t[:i]
        t = t.rstrip(NL) + NL + NL + NL + fn
        REPO.write_bytes(t.replace(NL, CR + LF).encode("utf-8"))
        t = REPO.read_bytes().decode("utf-8").replace(CR + LF, LF)
        ast.parse(t)
        print("  ✓ 追加 " + name)

    s = INJ.read_bytes().decode("utf-8").replace(CR + LF, LF)
    old = 'SRC_NEW = "元DGTF-V1.22.1-rc1b.py"   # [P2b] 工作版'
    assert s.count(old) == 1, s.count(old)
    s = s.replace(old, 'SRC_NEW = "元DGTF-V1.22.1-rc3.py"   # [P5/P6] 工作版', 1)
    INJ.write_bytes(s.replace(NL, CR + LF).encode("utf-8"))
    print("  ✓ 注入器 SRC_NEW → rc3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
