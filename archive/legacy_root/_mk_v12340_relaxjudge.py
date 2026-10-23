# -*- coding: utf-8 -*-
"""[v1.23.40 补丁3] smoke_test.py：加 check_v12340_relax_force。

三臂（构造性，真驱动 `MetaDGTF._before_round`）：
  ① 默认（force=false）+ **有增量** ⇒ **不放宽**（零行为差基线）
  ② force=true + **有增量** ⇒ **也放宽**（「强制它使用」的核心）
  ③ 默认 + **零增量** ⇒ 仍放宽（旧机制未破）
  ④ 静态：放宽表含 4 个 `decompose_*`（用户口径「要扩」钉住）
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"

NEW_FN = '''def check_v12340_relax_force():
    """[v1.23.40] 强制放宽 `web_search.relax_force` + 放宽表扩到 12。

    ★ 用户口径：「放宽表中步扩展要扩，先强制它使用，可能有些题目需要，
      扩也无妨」⇒ ① 放宽表补 4 个 `decompose_*`（8 → 12）；
      ② 新增 `relax_force`（默认 false）⇒ true 时**每圈都**放宽，
         不再要求「上一圈池零增量」。
    ★ 零行为差：force=false 时判据与改前**逐字等价**（有增量 ⇒ 不放宽）。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")

    # ── ④ 静态：放宽表含 4 个 decompose_* ──
    _m = re.search(r"_TICK_WEB_RELAX = \\(([^)]*)\\)", src, re.S)
    _members = re.findall(r'"([a-z_]+)"', _m.group(1)) if _m else []
    for _st in ("decompose_normal", "decompose_hybrid", "decompose_koan",
                "decompose_from_pool"):
        if _st not in _members:
            bad.append("[强制放宽] 放宽表缺 `%s`（用户口径「要扩」）" % _st)
    if len(_members) != 12:
        bad.append("[强制放宽] 放宽表成员 %d 个（要求 12）" % len(_members))
    if '"relax_force": False' not in src:
        bad.append("[强制放宽] DEFAULT_CONFIG 缺 `web_search.relax_force`")

    # ── 构造性：真驱动 `_before_round` ──
    class _P:
        def __init__(self):
            self.amps = []
            self.threads = []

    def _run(force, grow):
        cfg = build_cfg(False)
        cfg.setdefault("web_search", {})
        cfg["web_search"]["relax_force"] = bool(force)
        mt = mod.MetaDGTF(cfg)
        p = _P()
        mt._before_round("0", p, 1)          # 第一圈：只记基线
        if grow:
            p.amps = [{"desc": "新 & 1"}]     # 有增量
        mt._before_round("0", p, 2)          # 第二圈：看是否放宽
        return [x.get("key") for x in (mt._control.applied or [])]

    try:
        # ① 默认 + 有增量 ⇒ 不放宽（零行为差基线）
        _k1 = _run(False, True)
        if any(str(k).startswith("web.allow.") for k in _k1):
            bad.append("[强制放宽] 默认配置下**有增量**却放宽了"
                       "（零行为差被破）：%r" % (_k1,))
        # ② force=true + 有增量 ⇒ 也放宽（核心）
        _k2 = _run(True, True)
        if not any(str(k).startswith("web.allow.") for k in _k2):
            bad.append("[强制放宽] force=true 时**没放宽**（开关不生效）：%r"
                       % (_k2,))
        #   放宽的应含 decompose_*（12 个全表）
        _fk = [str(k)[len("web.allow."):] for k in _k2
               if str(k).startswith("web.allow.")]
        for _st in ("decompose_normal", "decompose_from_pool"):
            if _st not in _fk:
                bad.append("[强制放宽] force=true 时未放行 `%s`：%r"
                           % (_st, _fk))
        #   留下「是不是强制」的痕迹（why 里应写明）
        _whys = [str(x.get("why") or "") for x in (mt._control.applied or [])]
        if not any("强制" in w or "relax_force" in w for w in _whys):
            bad.append("[强制放宽] 留痕里看不出是强制放宽：%r" % (_whys[:3],))
        # ③ 默认 + 零增量 ⇒ 仍放宽（旧机制未破）
        _k3 = _run(False, False)
        if not any(str(k).startswith("web.allow.") for k in _k3):
            bad.append("[强制放宽] 默认配置下**零增量**却没放宽"
                       "（旧机制破了）：%r" % (_k3,))
    except Exception as _e:
        bad.append("[强制放宽] 构造性驱动抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.40 强制放宽（表 12 个含 decompose_* · force=true 每圈放行 · "
          "默认有增量不放宽/零增量仍放宽 · 留痕可辨）全过")
    return True


def check_v12340_backfeed_stage():'''

CALL_OLD = """    if not check_v12340_backfeed_stage():
        return 1"""
CALL_NEW = """    if not check_v12340_relax_force():
        return 1
    if not check_v12340_backfeed_stage():
        return 1"""


def _rw(p, fn):
    raw = p.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "%s 不是纯 CRLF" % p.name
    assert b"\r\r\n" not in raw, "%s 含 CRLF 双写" % p.name
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out, "%s 写出后含 CRLF 双写" % p.name
    assert out.count(b"\n") == out.count(b"\r\n"), "%s 写出后不是纯 CRLF" % p.name
    p.write_bytes(out)


def apply(s):
    n = s.count("def check_v12340_backfeed_stage():")
    assert n == 1, "插入锚点命中 %d 次（要求 1）" % n
    s = s.replace("def check_v12340_backfeed_stage():", NEW_FN)
    n = s.count(CALL_OLD)
    assert n == 1, "调用锚点命中 %d 次（要求 1）" % n
    s = s.replace(CALL_OLD, CALL_NEW)
    return s


if __name__ == "__main__":
    _rw(SM, apply)
    raw = SM.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n")
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8")
    assert s.count("def check_v12340_relax_force():") == 1
    assert s.count("if not check_v12340_relax_force():") == 1
    import ast
    ast.parse(s)
    print("[ok] smoke_test.py 已加 check_v12340_relax_force + 调用")
    print("[ok] 行数（LF 计）=", s.count("\n"), "| 纯 CRLF | AST OK")