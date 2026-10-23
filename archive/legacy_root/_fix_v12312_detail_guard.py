# -*- coding: utf-8 -*-
"""给 v1.23.12 判据补一段：**锚点明细不许被两条通道吃掉**。

背景（v1.23.12 首版真踩过）：把头部那几行「锚点对照 / 锚点分级 /
triage 降级 / 冲突 / 锚点入池」当成「旧单通道块」整段撤掉后，
`_v122_verify.py` 的 `[4.7]` 当场判红 —— 那些读数是**信息**，不是旧形态。
判据必须自己守住这条，而不是靠别档兜。

插在 `check_v12312_anchor_lanes` 里「联网关 + 决策题」那段之前 ——
该位置由 `_res(_D, ...)` 唯一定位（`check_v12310_render_ops` 里的同段
用的是 `_fake(_DEC, ...)`，锚点不会撞）。
"""
import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE / "smoke_test.py"
raw = SK.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

ANCHOR = '''    with _tf.TemporaryDirectory() as td:
        _cd = Path(m.save_result(
            _res(_D, **{"_runtime": {"web_enabled": False}}),
            save_dir=td)).read_text(encoding="utf-8")
'''
assert s.count(ANCHOR) == 1, "插入锚点命中 %d 次" % s.count(ANCHOR)

GUARD = '''    # ── G · 锚点**明细**不许因为「两条通道」被吃掉 ───────────────
    #   v1.23.12 首版真踩过：把 `锚点对照 / 锚点分级 / triage 降级 /
    #   锚点入池` 当成「旧单通道块」整段撤掉 ⇒ `_v122_verify.py` 的
    #   `[4.7]` 判红。两条通道是**多一条出口**，不是换掉这些读数。
    _ra = _res(_Q, **{
        "_runtime": {"web_enabled": True},
        "external_anchor": {
            "anchors": 3, "source_file": "a.json", "retrieved_at": "t0",
            "as_evidence": "partial", "tier_floor": 2, "triage_downgrades": 1,
            "pooled": 3,
            "summary": {"claims": 2, "supported": 1, "conflicted": 0,
                        "unmatched": 1, "anchor_used": 2}}})
    with _tf.TemporaryDirectory() as td:
        _pa = Path(m.save_result(_ra, save_dir=td)).read_text(
            encoding="utf-8")
    for _need in ("**锚点对照**", "**锚点分级**：partial", "**triage 降级**：1 条",
                  "**锚点入池**", "已接入 3 条", "**外部锚点 · 联网**"):
        if _need not in _pa:
            bad.append("锚点明细被两条通道吃掉了（缺 %s）" % _need)

'''
s = s.replace(ANCHOR, GUARD + ANCHOR, 1)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
ast.parse(out.decode("utf-8"))
SK.write_bytes(out)
print("判据已补 G 段：锚点明细守卫")
