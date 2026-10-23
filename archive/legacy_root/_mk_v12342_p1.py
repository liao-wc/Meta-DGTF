# -*- coding: utf-8 -*-
"""v1.23.42 · P-1：上下文裁剪 —— `View.shape_of` 窗口化（默认不限 ⇒ 逐字不变）。

根因（真跑实测）：`View.shape_of` **无窗口**渲染整个 view（候选/&/线头/探针/
悬置/裁决…全量），而 `_expand_from_views` 每圈把它当 `views_text` 重灌 ⇒ 后段圈
单次 prompt token 随圈数上涨（最贵调用 25–32k tok/次；最贵 20% 占 46.5%）。
SOTA：observation masking —— 保留最近 N 条、更老的换成**结构化占位**（成本↓52%）。

修法：`shape_of(v, limit=0)`；`limit>0` 时每类只列最近 `limit` 条 + 表头标总数
（如「候选（共 48，只列最近 8）」）；`limit=0` ⇒ **逐字不变**。
接线：`_expand_from_views` 读 `spiral.shape_limit`（默认 0）传入。
"""
import ast
from pathlib import Path

TGT = Path("元DGTF-V1.23.42.py")

HEADERS = [
    ('lines.append("候选：")', 'lines.append(_hdr("候选：", len(v.candidates)))'),
    ('lines.append("& 印记：")', 'lines.append(_hdr("& 印记：", len(v.amps)))'),
    ('lines.append("悬空线头：")',
     'lines.append(_hdr("悬空线头：", len(v.threads)))'),
    ('lines.append("还没带走的自问：")',
     'lines.append(_hdr("还没带走的自问：", len(v.probes)))'),
    ('lines.append("元反思：")', 'lines.append(_hdr("元反思：", len(v.meta)))'),
    ('lines.append("尚未触及的方面：")',
     'lines.append(_hdr("尚未触及的方面：", len(v.untouched)))'),
    ('lines.append("本层碰了的：")',
     'lines.append(_hdr("本层碰了的：", len(v.engagements)))'),
    ('lines.append("主动悬置（判断过、决定不碰）：")',
     'lines.append(_hdr("主动悬置（判断过、决定不碰）：", len(v.suspensions)))'),
    ('lines.append("延迟债务（暂缓，非悬置）：")',
     'lines.append(_hdr("延迟债务（暂缓，非悬置）：", len(v.deferrals)))'),
    ('lines.append("裁决的张力（极性，回溯）：")',
     'lines.append(_hdr("裁决的张力（极性，回溯）：", len(v.adjudications)))'),
    ('lines.append("悬置的张力（不解决什么分歧）：")',
     'lines.append(_hdr("悬置的张力（不解决什么分歧）：", len(v.duel_suspensions)))'),
]
LOOPS = [
    ("for c in v.candidates:", "for c in _w(v.candidates):"),
    ("for a in v.amps:", "for a in _w(v.amps):"),
    ("for t in v.threads:", "for t in _w(v.threads):"),
    ("for p in v.probes:", "for p in _w(v.probes):"),
    ("for m in v.meta:", "for m in _w(v.meta):"),
    ("for u in v.untouched:", "for u in _w(v.untouched):"),
    ("for e in v.engagements:", "for e in _w(v.engagements):"),
    ("for s in v.suspensions:", "for s in _w(v.suspensions):"),
    ("for d in v.deferrals:", "for d in _w(v.deferrals):"),
    ("for a in v.adjudications:", "for a in _w(v.adjudications):"),
    ("for s in v.duel_suspensions:", "for s in _w(v.duel_suspensions):"),
]

SIG_OLD = ('    def shape_of(v: "View") -> str:\n'
           '        lines = [f"【view｜entry={v.entry}】", f"锚点：{v.anchor}"]')
SIG_NEW = ('    def shape_of(v: "View", limit: int = 0) -> str:\n'
           '        # ★ [P-1] `limit > 0` ⇒ 每类只列最近 `limit` 条 + 表头标总数\n'
           '        #   （SOTA observation masking：保留最近 N 条、更老的换结构化占位，\n'
           '        #    实测成本↓52% 而任务完成率不降）。`limit = 0` ⇒ **逐字不变**。\n'
           '        _lim = int(limit or 0)\n'
           '\n'
           '        def _w(xs):\n'
           '            _xs = list(xs or [])\n'
           '            return (_xs[-_lim:] if (_lim > 0 and len(_xs) > _lim)\n'
           '                    else _xs)\n'
           '\n'
           '        def _hdr(name, n):\n'
           '            return (f"{name}（共 {n}，只列最近 {_lim}）"\n'
           '                    if (_lim > 0 and int(n) > _lim) else name)\n'
           '        lines = [f"【view｜entry={v.entry}】", f"锚点：{v.anchor}"]')

VIEWS_OLD = ('        views_text = "\\n\\n".join(\n'
             '            View.shape_of(v) for v in views\n'
             '        )')
VIEWS_NEW = ('        # ★ [P-1] 上游 view 形状按 `spiral.shape_limit` **窗口化**\n'
             '        #   （默认 0 = 不限 ⇒ 逐字不变）。真跑实测：`shape_of` 无窗口\n'
             '        #   渲染整个 view，而它每圈当 `views_text` 重灌 ⇒ 后段圈单次\n'
             '        #   prompt 随圈数上涨（最贵 25–32k tok/次）。\n'
             '        _shape_lim = 0\n'
             '        try:\n'
             '            _shape_lim = int((self.config.get("spiral") or {}).get(\n'
             '                "shape_limit", 0) or 0)\n'
             '        except Exception:\n'
             '            _shape_lim = 0\n'
             '        views_text = "\\n\\n".join(\n'
             '            View.shape_of(v, limit=_shape_lim) for v in views\n'
             '        )')


def _rw(path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s
    path.write_bytes(s2.replace("\n", "\r\n").encode("utf-8"))
    chk = path.read_bytes()
    assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
    ast.parse(chk.decode("utf-8"))
    return chk


def apply(s):
    # ── ① 段内编辑 shape_of（防误伤 speech_of 的同名循环）──
    i = s.index('    def shape_of(v: "View") -> str:')
    j = s.index("    @staticmethod", i + 10)
    seg = s[i:j]
    assert seg.count(SIG_OLD) == 1, "签名锚点 %d" % seg.count(SIG_OLD)
    seg = seg.replace(SIG_OLD, SIG_NEW)
    for old, new in HEADERS:
        n = seg.count("            " + old)
        assert n == 1, "表头 %r 段内命中 %d" % (old, n)
        seg = seg.replace("            " + old, "            " + new)
    for old, new in LOOPS:
        n = seg.count("            " + old)
        assert n == 1, "循环 %r 段内命中 %d" % (old, n)
        seg = seg.replace("            " + old, "            " + new)
    s = s[:i] + seg + s[j:]

    # ── ② 接线 _expand_from_views ──
    assert s.count(VIEWS_OLD) == 1, "views_text 锚点 %d" % s.count(VIEWS_OLD)
    s = s.replace(VIEWS_OLD, VIEWS_NEW)

    # ── ③ 配置键 spiral.shape_limit ──（插在 spiral 段首键前）
    cfg_anchor = '    "spiral": {\n'
    assert s.count(cfg_anchor) == 1, "spiral 锚点 %d" % s.count(cfg_anchor)
    s = s.replace(cfg_anchor,
                  cfg_anchor
                  + '        # [P-1] view 形状窗口化：> 0 ⇒ 每类只列最近 N 条\n'
                    '        #   （压 prompt token；0 = 不限 = 逐字不变）。\n'
                    '        "shape_limit": 0,\n', 1)
    return s


if __name__ == "__main__":
    out = _rw(TGT, apply)
    # 自检
    t = out.decode("utf-8").replace("\r\n", "\n")
    for tok, want in (('def shape_of(v: "View", limit: int = 0) -> str:', 1),
                      ("View.shape_of(v, limit=_shape_lim)", 1),
                      ('"shape_limit": 0,', 1),
                      ("def _w(xs):", 1), ("def _hdr(name, n):", 1)):
        assert t.count(tok) == want, "自检 %r = %d" % (tok, t.count(tok))
    # 段外（speech_of）必须未被动：`for a in v.amps:` 应仍存在于 speech_of
    assert t.count("for a in v.amps:") == 1, "speech_of 被误改"
    print("[ok] P-1 补丁已落 | 行数", out.count(b"\n"), "| 纯 CRLF | AST OK")
    print("     并行：spiral.shape_limit=0（默认关）；shape_of(v,limit=0) 逐字不变")
