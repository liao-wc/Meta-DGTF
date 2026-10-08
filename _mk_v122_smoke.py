#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122] 给 smoke_test.py 打补丁：SRC 指向当前版 + 新增六条 v122 阶段检查。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "smoke_test.py"
SRC_NEW = "元DGTF-V1.22.0-rc1.py"

CHECK_P1 = '''
def check_v122_phase1():
    """[v122 阶段1] 目标函数分层 / 覆盖率只对研究层 / 未生分类。

    每条判据都带负对照（两个方向都锁），否则把阈值改坏也能通过。
    """
    print("  · v1.22 阶段1：四层 objective / 覆盖率归属 / 未生分类")
    try:
        # ① Phase.objective 四层各就各位
        want = {"0": "manifest", "1": "truth",
                "both": "collision", "all": "closure"}
        for k, v in want.items():
            got = getattr(mod.PHASES.get(k), "objective", None)
            assert got == v, f"PHASES[{k!r}].objective={got!r} ≠ {v!r}"

        # ② 覆盖率只对研究层：entry≠"1" → None
        class _P:
            def __init__(self):
                self.sub_questions = [{"id": "s1",
                                       "decidability": "decidable",
                                       "status": "answered",
                                       "weight": 1.0, "depth": 1.0}]
                self.deferrals = []

        p = _P()
        assert mod.coverage_of(p, {}, entry="0") is None, "entry=0 必须 None"
        assert mod.coverage_of(p, {}, entry="both") is None, "entry=both 必须 None"
        assert mod.coverage_of(p, {}, entry="all") is None, "entry=all 必须 None"
        # 负对照：研究层不许被一起挡掉
        assert mod.coverage_of(p, {}, entry="1") is not None, \
            "entry=1 不该是 None（挡住了就是过度收窄）"
        # 向下兼容：不传 entry 的旧调用点行为不变
        assert mod.coverage_of(p, {}) == mod.coverage_of(p, {}, entry="1"), \\
            "不传 entry 时旧行为应逐字不变"
        # ★ 判据不能只信函数自己：真拿一份非研究层池子，返回的必须是 None
        assert mod.coverage_parts(p, {}, entry="0") == (0, 0, None), \\
            "coverage_parts(entry=0) 必须是 (0,0,None)"

        # ③ 未生分类 + 负对照
        assert mod._classify_unsaid({}) == "lazy"
        assert mod._classify_unsaid({"covers": ["T1"]}) == "real"
        assert mod._classify_unsaid({"covers": []}) == "lazy", \\
            "空 covers 必须是 lazy（否则这个判据永远亮）"
        assert mod._classify_unsaid(None) == "lazy"
        assert mod._classify_unsaid({"covers": "T1"}) == "real"

        # ④ 头部四行分层目标
        lines = mod._layer_objective_lines()
        assert len(lines) == 4, f"分层目标应为 4 行，得到 {len(lines)}"
        joined = "".join(lines)
        for n in ("修行层", "研究层", "对撞层", "元层"):
            assert n in joined, f"分层目标缺 {n}"

        # ⑤ 元层不评价修行层
        import inspect as _ins
        body = _ins.getsource(mod.MetaDGTF._settle_meta)
        assert 'pools["0"]' not in body and "pools['0']" not in body, \\
            "_settle_meta 仍在读修行池"

        # ⑥ route 分层：boundary 保留全四层
        inst = object.__new__(mod.MetaDGTF)
        inst.config = {}
        inst.vp = lambda *a, **k: None
        r = inst._route_by_decidability("q", ["0", "1", "both", "all"],
                                        orientation="boundary")
        assert r == ["0", "1", "both", "all"], \\
            f"boundary 应保留全四层，得到 {r}"

        print("  ✓ v1.22 阶段1：四层 objective / 覆盖率归属 / 未生分类 / "
              "头部四行 / 元层不读修行池 / route 分层")
        return True
    except Exception as e:
        print(f"  ✗ v1.22 阶段1 失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


'''


def main():
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "smoke_test 不是纯 CRLF"
    s = s.replace("\r\n", "\n")

    # 1) SRC 指向当前版
    pat = re.compile(r'SRC = HERE / "元DGTF-V1\.21\.\d+\.py"')
    assert len(pat.findall(s)) == 1, "SRC 行不唯一"
    s = pat.sub(f'SRC = HERE / "{SRC_NEW}"', s, count=1)

    # 2) 插入检查函数（在 def main() 之前）
    anchor = "\ndef main():\n"
    assert s.count(anchor) == 1, "main 定义锚点不唯一"
    s = s.replace(anchor, CHECK_P1 + anchor, 1)

    # 3) 接进 main()（放在第一条检查之前）
    a2 = ("def main():\n"
          '    verbose = os.environ.get("SMOKE_VERBOSE", "0") == "1"\n'
          "    if not check_thread_isolation():\n")
    assert s.count(a2) == 1, "main 首条检查锚点不唯一"
    s = s.replace(a2,
                  "def main():\n"
                  '    verbose = os.environ.get("SMOKE_VERBOSE", "0") == "1"\n'
                  "    if not check_v122_phase1():\n"
                  "        return 1\n"
                  "    if not check_thread_isolation():\n", 1)

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n")
    TARGET.write_bytes(out.encode("utf-8"))
    print(f"✓ smoke_test 补丁完成：SRC → {SRC_NEW}，已加 check_v122_phase1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
