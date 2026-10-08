# -*- coding: utf-8 -*-
"""[v1.23.3] 思考录播：改成**多次录播合并**（覆盖更多 stage）。

原版只跑一次 `orientation=auto / parallel_mode=serial / route 0,1 / 1 圈`
⇒ 只触达 12 个 stage（含 yaml 15 键里的 7 个）。yaml 里剩下的
（`decompose_normal` / `probe_duel` / `probe_meta` / `decide_parallel_mode` …）
需要**别的模式**才会跑。

改法：`--capture-only` 按预设的 **3 组配置**各录一次，合并 stage 集合；
已存在的 `_v1233_think_capture.json` 作为第 0 组（不重复跑）。
"""
from pathlib import Path
import ast

P = Path("_ab_thinking_v1233.py")
s = P.read_text(encoding="utf-8")

O = '''    m.LLM.call = _patched
    cfg = m.DEFAULT_CONFIG.copy()
    cfg["external_anchor"] = dict(cfg["external_anchor"])
    cfg["external_anchor"].update({"enabled": True,
                                   "path": "_test_anchors.json",
                                   "as_evidence": "evidence", "tier_floor": 2})
    cfg["output"] = dict(cfg.get("output") or {})
    cfg["output"]["save_dir"] = str(HERE / "outputs" / "_v1233_think_cap")
    cfg["output"]["verbose"] = False
    (HERE / "outputs" / "_v1233_think_cap").mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    t0 = time.time()
    with contextlib.redirect_stdout(buf):
        meta = m.MetaDGTF(cfg)
        meta.run("老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？"
                 "怎么权衡？", route=["0", "1"], rounds={"0": 1, "1": 1},
                 parallel_mode="serial", orientation="auto")
    m.LLM.call = _orig
    print("[think] 录播完成：%d 次调用 / %.0fs" % (len(rec_calls),
                                                   time.time() - t0), flush=True)'''

N = '''    Q1 = ("老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？"
          "怎么权衡？")
    Q2 = ("某市要决定是否把全部政务系统迁到自建机房，但机房选址、"
          "预算上限与迁移窗口都还没定。请给出取舍。")
    # 三组配置：模式不同 ⇒ 触达的 stage 不同（「有接线」≠「这跑走得到」）。
    RUNS = (
        (Q1, "auto", "serial", ["0", "1"], {"0": 1, "1": 1}),
        (Q1, "normal", "auto", ["0", "1", "both", "all"],
         {"0": 2, "1": 2, "both": 1, "all": 1}),
        (Q2, "koan", "serial", ["0", "1"], {"0": 1, "1": 1}),
    )
    m.LLM.call = _patched
    _t0 = time.time()
    for _k, (_q, _ori, _pm, _rt, _rd) in enumerate(RUNS):
        cfg = m.DEFAULT_CONFIG.copy()
        cfg["external_anchor"] = dict(cfg["external_anchor"])
        cfg["external_anchor"].update(
            {"enabled": True, "path": "_test_anchors.json",
             "as_evidence": "evidence", "tier_floor": 2})
        cfg["output"] = dict(cfg.get("output") or {})
        _d = HERE / "outputs" / ("_v1233_think_cap%d" % _k)
        _d.mkdir(parents=True, exist_ok=True)
        cfg["output"]["save_dir"] = str(_d)
        cfg["output"]["verbose"] = False
        _buf = io.StringIO()
        _n0 = len(rec_calls)
        try:
            with contextlib.redirect_stdout(_buf):
                meta = m.MetaDGTF(cfg)
                meta.run(_q, route=_rt, rounds=_rd, parallel_mode=_pm,
                         orientation=_ori)
            print("[think] 组%d ori=%s pm=%s 录到 %d 次调用"
                  % (_k, _ori, _pm, len(rec_calls) - _n0), flush=True)
        except Exception as _e:  # noqa: BLE001
            print("[think] 组%d 失败：%s: %s" % (_k, type(_e).__name__, _e),
                  flush=True)
    m.LLM.call = _orig
    print("[think] 录播完成：%d 次调用 / %.0fs" % (len(rec_calls),
                                                   time.time() - _t0), flush=True)'''
assert s.count(O) == 1, "录播块锚点 %d 次" % s.count(O)
s = s.replace(O, N)
P.write_text(s, encoding="utf-8")
ast.parse(s)
print("录播改为三组配置合并")
