# -*- coding: utf-8 -*-
"""[v1.23.2] 给 `_v122_verify.py` 加验收档 `v1232`（幂等；哨兵用**最后一项**）。"""
import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "_v122_verify.py"
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

SENTINEL = '"v1232": phase_v1232'
if SENTINEL in s:
    print("已注册 v1232，跳过")
    sys.exit(0)

NEW = '''def phase_v1232(src, mod):
    """[v1.23.2] 整体审计 + thinking 接线「行为不变」的机器证明 + 遗留收尾。

    判据本体在 `_probe_v1232_audit.py`（8 类机械检查 + 4 自检变异体）。
    这里补三条只有「两版配置对读」才能证的：
      V1 解析结果逐步与改前逐字相同（接线 + yaml 对齐的净效果）
      V2 改动的配置键**只允许**是「改前从未生效」的那两类
      V3 yaml 里那 15 个 stage 与 `thinking.default` 一致（与注释「关」一致）
    """
    import re as _re
    _run_probe("_probe_v1232_audit.py", src)

    _txt = Path(src).read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    # 本版新接线的 stage（改前调用点没传 stage ⇒ 掉回 default）
    # ★ 注入的字面量是**单引号**（%r 生成），且 `_check_input_sanity` 那处
    #   参数里有**逗号**（`getattr(d, 'config', None)`）⇒ 正则要容忍嵌套括号。
    _wired = set(_re.findall(
        r\"\"\"stage=_thinking_stage\\([^\\n]*?,\\s*["'](\\w+)["']\\)\"\"\", _txt))
    # 一直就在传字面 stage 的调用点
    _lit = set(_re.findall(r'stage="(\\w+)"', _txt))
    check("V2 抽样非空（防空过）", bool(_wired) and bool(_lit),
          "wired=%d lit=%d" % (len(_wired), len(_lit)))

    _old = mod.load_config(str(HERE / "_bak_dgtf_config.pre_v1232"))
    _new = mod.load_config(str(HERE / "dgtf_config.yaml"))
    _ot = ((_old.get("api") or {}).get("thinking") or {})
    _nt = ((_new.get("api") or {}).get("thinking") or {})
    _os, _ns = _ot.get("stages") or {}, _nt.get("stages") or {}
    _od, _nd = _ot.get("default"), _nt.get("default")

    _bad = []
    for _k in sorted(_wired | _lit):
        # 改前：_wired 的调用点传 None ⇒ 掉回 _od；_lit 的取 _os[_k]
        _before = _od if _k in _wired else _os.get(_k, _od)
        _after = _ns.get(_k, _nd)
        if _before != _after:
            _bad.append((_k, _before, _after))
    check("V1 ★ thinking 接线 + yaml 对齐后，每个 stage 的解析结果与改前逐字相同",
          not _bad, repr(_bad[:4]))

    def _flat(d, pre=""):
        out = {}
        for k, v in (d or {}).items():
            key = "%s.%s" % (pre, k) if pre else str(k)
            if isinstance(v, dict):
                out.update(_flat(v, key))
            else:
                out[key] = v
        return out

    _fo, _fn = _flat(_old), _flat(_new)
    _chg = sorted(k for k in set(_fo) | set(_fn) if _fo.get(k) != _fn.get(k))
    _allow = {"api.thinking.stages." + k for k in _wired} | {"web_search.tier_floor"}
    _unexpected = [k for k in _chg if k not in _allow]
    check("V3 ★ 两版配置的差异**只允许**是「改前从未生效」的两类（thinking 接线 / tier_floor）",
          not _unexpected, "意外改动：" + repr(_unexpected[:5]))
    _kw = [k for k in _chg if k.startswith("api.thinking.stages.")]
    _sv = {k: _ns.get(k.split(".")[-1]) for k in _kw}
    check("V4 yaml 里被改的 stage 一律 == thinking.default（与注释「关」一致）",
          all(v == _nd for v in _sv.values()), repr(_sv))

    check("V5", (HERE / "v1232_报告.md").is_file(), "v1232_报告.md 存在")


'''

A = "PHASES = {"
assert s.count(A) == 1, "PHASES 锚点 %d 次" % s.count(A)
s = s.replace(A, NEW + A)

O = '          "v123_w6": phase_v123_w6}'
assert s.count(O) == 1, "注册锚点 %d 次" % s.count(O)
s = s.replace(O, '          "v123_w6": phase_v123_w6,\n'
                 '          "v1232": phase_v1232}')

P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
ast.parse(s)
print("已加并注册 phase_v1232")
