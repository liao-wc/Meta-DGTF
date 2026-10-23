# -*- coding: utf-8 -*-
"""[v1.23.40 补丁2] 放宽表扩到 12 + 加 `web_search.relax_force`（强制放宽）。

【用户口径】「放宽表中步扩展要扩，先强制它使用，可能有些题目需要，扩也无妨」

【两件事】
  ① **扩表 8 → 12**：补 `decompose_normal` / `decompose_hybrid` /
     `decompose_koan` / `decompose_from_pool`（拆解类四兄弟）。
  ② **强制放宽开关** `web_search.relax_force`（默认 **false** ⇒ 零行为差）：
     为 true 时**每圈都**对放宽表全集放行（不再要求「上一圈零增量」）
     —— 「先强制它使用」的落地形态；仍**只走 ControlSurface**（带
     why + trace_ref）⇒ 留痕与边界一条不丢。

协议：纯 CRLF 往返；锚点命中 == 1；写完 AST + 自检。
"""
from pathlib import Path

TGT = Path(__file__).resolve().parent / "元DGTF-V1.23.40.py"

# ── ① 扩表 ─────────────────────────────────────────────────────────
OLD_RELAX = '''    _TICK_WEB_RELAX = ("ing", "probe_research", "probe_duel", "probe_meta",
                       "he", "phase_probe",
                       "expand_pair", "expand_pair_merged_once")'''

NEW_RELAX = '''    _TICK_WEB_RELAX = ("ing", "probe_research", "probe_duel", "probe_meta",
                       "he", "phase_probe",
                       "expand_pair", "expand_pair_merged_once",
                       # ★ [用户口径] 拆解类四兄弟也纳入（8 → 12）：
                       #   「可能有些题目需要」—— 拆解是**开新子问题**的环节，
                       #   停滞时若它拿不到外部素材，只会把同一批子问题
                       #   换个说法再拆一遍（本项目已观测：结构饱和反复出现）。
                       #   ★ 它们只在放宽时开（默认仍关）⇒ 成本受控。
                       "decompose_normal", "decompose_hybrid",
                       "decompose_koan", "decompose_from_pool")'''

# ── ② 强制放宽：`_before_round` 里加 _force 判据 ─────────────────────
OLD_TICK = '''            _n_prev = getattr(self, "_tick_prev_n", None)
            if _n_prev is not None and int(layer_no or 0) > 1:
                _grew = _n_now - int(_n_prev)
                if _grew <= 0:
                    _done = []
                    for _st in (self._TICK_WEB_RELAX or ()):
                        if self._control.write(
                                "web.allow.%s" % _st, True,
                                why="圈级心跳：第 %d 圈池零增量（复述/停滞）"
                                    "⇒ 放宽 %s 联网" % (int(layer_no) - 1, _st),
                                trace_ref="tick_round:%s:%d:%s"
                                          % (entry, layer_no, _st)):
                            _done.append(_st)
                    if _done:
                        try:
                            _trace_note(getattr(self, "_last_view", None),
                                        "tune",
                                        what="圈级心跳：放宽联网",
                                        layer=str(entry),
                                        round=int(layer_no),
                                        why="上一圈池零增量（新增 0 条）",
                                        adjusted=_done)
                        except Exception:
                            pass'''

NEW_TICK = '''            _n_prev = getattr(self, "_tick_prev_n", None)
            # ★ [强制放宽] `web_search.relax_force=true` ⇒ **每圈**都放宽
            #   （不再要求「上一圈零增量」）—— 「先强制它使用」的落地形态。
            #   ★ 默认 false ⇒ `_force=False` ⇒ 下面的判据与改前**逐字等价**
            #     （零行为差）；仍**只走 ControlSurface**（边界 + 必留痕）。
            try:
                _force = bool((_web_cfg_of(getattr(self, "config", None))
                               or {}).get("relax_force", False))
            except Exception:
                _force = False
            if _n_prev is not None and int(layer_no or 0) > 1:
                _grew = _n_now - int(_n_prev)
                if _force or _grew <= 0:
                    _why = (("[强制放宽] relax_force=true ⇒ 第 %d 圈无条件"
                             "放宽 %s 联网（不等零增量）"
                             % (int(layer_no) - 1, "%s"))
                            if _force else
                            ("圈级心跳：第 %d 圈池零增量（复述/停滞）"
                             "⇒ 放宽 %s 联网" % (int(layer_no) - 1, "%s")))
                    _done = []
                    for _st in (self._TICK_WEB_RELAX or ()):
                        if self._control.write(
                                "web.allow.%s" % _st, True,
                                why=_why % _st,
                                trace_ref="tick_round:%s:%d:%s"
                                          % (entry, layer_no, _st)):
                            _done.append(_st)
                    if _done:
                        try:
                            _trace_note(getattr(self, "_last_view", None),
                                        "tune",
                                        what="圈级心跳：放宽联网",
                                        layer=str(entry),
                                        round=int(layer_no),
                                        why=("[强制放宽] relax_force=true"
                                             if _force else
                                             "上一圈池零增量（新增 0 条）"),
                                        adjusted=_done)
                        except Exception:
                            pass'''

# ── ③ DEFAULT_CONFIG 新增键 ─────────────────────────────────────────
OLD_CFG = '''        # 【配额三层】每环节每圈 / 每环节全程 / 每跑总。三层都过才允许调用。
        "quota": {
            "per_stage_round": 2,
            "per_stage_total": 8,
            "per_run_total": 30,
        },'''

NEW_CFG = '''        # 【配额三层】每环节每圈 / 每环节全程 / 每跑总。三层都过才允许调用。
        "quota": {
            "per_stage_round": 2,
            "per_stage_total": 8,
            "per_run_total": 30,
        },
        # 【强制放宽】为 true 时**每圈都**对放宽表
        #   （`MetaDGTF._TICK_WEB_RELAX`，12 个环节）放行联网 ——
        #   不再要求「上一圈池零增量」。用于实验与特需题型。
        #   ★ 默认 false ⇒ 与改前**逐字等价**（零行为差）；
        #     仍只走 `ControlSurface`（边界 + 必留痕 + trace_ref）。
        "relax_force": False,'''

# ── ④ yaml 加键 ────────────────────────────────────────────────────
YAML = Path(__file__).resolve().parent / "dgtf_config.yaml"
Y_OLD = '''  # 【失败降级】连续失败达到此值 → 本跑联网关闭（留痕 [W-DISABLED]）。
  auto_disable_after_failures: 3'''
Y_NEW = '''  # 【失败降级】连续失败达到此值 → 本跑联网关闭（留痕 [W-DISABLED]）。
  auto_disable_after_failures: 3
  # 【强制放宽】true ⇒ **每圈都**对放宽表（12 个环节）放行联网，
  #   不再要求「上一圈池零增量」。实验/特需题型用；默认 false。
  relax_force: false'''


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
    for nm, old, new in (("放宽表", OLD_RELAX, NEW_RELAX),
                         ("心跳块", OLD_TICK, NEW_TICK),
                         ("DEFAULT_CONFIG", OLD_CFG, NEW_CFG)):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（要求 1）" % (nm, n)
        s = s.replace(old, new)

    for tok, want in (('"decompose_from_pool")', 1),
                      ('_force = bool((_web_cfg_of(getattr(self, "config", None))', 1),
                      ('"relax_force": False,', 1)):
        got = s.count(tok)
        assert got == want, "自检 %r 出现 %d 次（要求 %d）" % (tok, got, want)
    return s


def apply_yaml():
    raw = YAML.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "yaml 不是纯 CRLF"
    assert b"\r\r\n" not in raw
    t = raw.decode("utf-8").replace("\r\n", "\n")
    if "relax_force: false" in t:
        print("[info] yaml 已有 relax_force（幂等）")
        return
    n = t.count(Y_OLD)
    assert n == 1, "yaml 锚点命中 %d 次（要求 1）" % n
    t = t.replace(Y_OLD, Y_NEW)
    out = t.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    YAML.write_bytes(out)
    import yaml as _y
    d = _y.safe_load(YAML.read_bytes().decode("utf-8"))
    assert d["web_search"]["relax_force"] is False
    print("[ok] dgtf_config.yaml 已加 relax_force: false（默认关）")


_rw(TGT, apply)
apply_yaml()

raw = TGT.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n")
assert b"\r\r\n" not in raw
src = raw.decode("utf-8")
import ast
import re

ast.parse(src)
m = re.search(r"_TICK_WEB_RELAX = \(([^)]*)\)", src, re.S)
members = re.findall(r'"([a-z_]+)"', m.group(1))
print("[ok] 放宽表成员 %d 个：" % len(members), members)
assert len(members) == 12
print("[ok] relax_force 开关已加（DEFAULT_CONFIG + 心跳判据）")
print("[ok] 行数（LF 计）=", src.count("\n"), "| 纯 CRLF | AST OK")