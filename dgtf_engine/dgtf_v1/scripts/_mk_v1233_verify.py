# -*- coding: utf-8 -*-
"""[v1.23.3] 给 `_v122_verify.py` 加验收档 `v1233`（幂等；哨兵用**最后一项**）。"""
import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "_v122_verify.py"
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

SENTINEL = '"v1233": phase_v1233'
if SENTINEL in s:
    print("已注册 v1233，跳过")
    sys.exit(0)

NEW = '''def phase_v1233(src, mod):
    """[v1.23.3] §十 五条全清：受控实验 / 思考 A/B / tier 真跑 / triage 频度
    + id 归一化（两处 + 一类）。

    判据分三层：
      V1~V4 代码层（版本一致 / 两个纯函数 / **模型 id 全部归一化**的不变式）
      V5    实验产物层（四份 json 的关键不变式，含**负对照**）
      V6    报告层（`v1233_报告.md` 存在且 §十 明确为「无遗留」）
    """
    import json as _json
    import re as _re
    from pathlib import Path as _P

    _run_probe("_probe_v1233_voteids.py", src)

    _txt = _P(src).read_bytes().decode("utf-8").replace(chr(13) + chr(10),
                                                        chr(10))
    check("V1 版本一致：主文件 __version__ / 冒烟 SRC / yaml 头",
          (getattr(mod, "__version__", "") == "1.23.3"
           and '元DGTF-V1.23.3.py' in (HERE / "smoke_test.py")
           .read_bytes().decode("utf-8")
           and "1.23.3" in (HERE / "dgtf_config.yaml")
           .read_bytes().decode("utf-8")[:600]),
          "ver=%s" % getattr(mod, "__version__", "?"))

    # ---- V2 票 id 归一化（纯函数四向）----
    _f = getattr(mod, "_normalize_judgment_ids", None)
    check("V2 ★ `_normalize_judgment_ids` 四向（1起/0起/越界/空）",
          _f is not None
          and _f({1: "a", 2: "b"}, 2) == ({1: "a", 2: "b"}, "1起")
          and _f({0: "a", 1: "b"}, 2) == ({1: "a", 2: "b"}, "0起+1")
          and _f({1: "a", 9: "b"}, 2)[0] is None
          and _f({}, 2)[0] is None, "符号缺失或行为不符")

    # ---- V3 子问题 id 规范化 ----
    _c = getattr(mod, "_canonical_sub_ids", None)
    _demo = [{"id": 0, "q": "a"}, {"id": 0, "q": "b"}, {"id": 7, "q": "c"}]
    _out = _c([dict(x) for x in _demo]) if _c else None
    check("V3 ★ `_canonical_sub_ids` 把 0 起/重复/带洞的子问题 id 重编号成 1..n",
          _c is not None and [x["id"] for x in _out] == [1, 2, 3]
          and [x["q"] for x in _out] == ["a", "b", "c"],
          repr(_out))

    # ---- V4 不变式：所有「读模型返回的 id」的点都过了归一化 ----
    def _bad_sites(txtx):
        _bad = []
        _tr = ast.parse(txtx)
        _L = txtx.split(chr(10))
        for _fn in ast.walk(_tr):
            if not isinstance(_fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            _body = chr(10).join(_L[_fn.lineno - 1:_fn.end_lineno])
            if ("_normalize_judgment_ids(" in _body
                    or "_canonical_sub_ids(" in _body):
                continue
            for _n in ast.walk(_fn):
                if not (isinstance(_n, ast.Call)
                        and isinstance(_n.func, ast.Name)
                        and _n.func.id == "int" and _n.args):
                    continue
                _a = _n.args[0]
                if (isinstance(_a, ast.Call)
                        and isinstance(_a.func, ast.Attribute)
                        and _a.func.attr == "get" and _a.args
                        and isinstance(_a.args[0], ast.Constant)
                        and _a.args[0].value == "id"):
                    _bad.append((_fn.name, _n.lineno))
        return _bad

    _bs = _bad_sites(_txt)
    check("V4 ★ 所有读模型返回 id 的调用点都过了归一化（一类不变式）",
          not _bs, "未归一化：" + repr(_bs))
    _syn = ("def f(it):" + chr(10) + "    return int(it.get(" + chr(34)
            + "id" + chr(34) + ", 0))" + chr(10))
    check("V4.b 自检：合成源码必须被这套扫描报出（判别力）",
          len(_bad_sites(_syn)) == 1, repr(_bad_sites(_syn)))

    # ---- V5 实验产物层 ----
    _vj = HERE / "_v1233_votes.json"
    _vk = {}
    if _vj.is_file():
        _vk = _json.loads(_vj.read_text(encoding="utf-8"))
    _arms = ("w4_off_t0", "w4_on_t0", "w4_off_t7", "w4_on_t7")
    check("V5.a ★ 受控投票实验：四臂齐 + 每臂 3 个指标的 ICC 判定都有",
          _vk.get("src") == "元DGTF-V1.23.3.py"
          and all(a in (_vk.get("icc") or {}) for a in _arms)
          and all(all((_vk["icc"][a].get(mk) or {}).get("verdict")
                      for mk in ("a12", "a13", "a23")) for a in _arms),
          "src=%s arms=%s" % (_vk.get("src"), sorted(_vk.get("icc") or {})))
    _idb = _vk.get("id_base") or {}
    check("V5.b ★ 票 id 基准统计存在（0 起那条 bug 的频度证据）",
          all(a in _idb for a in _arms)
          and all(sum(_idb[a].values()) > 0 for a in _arms),
          repr(_idb))
    check("V5.c 字面口径「组间 ≥ 组内」的判定列非空（判据 B）",
          all((_vk.get("pair") or {}).get(t, {}).get("verdict_B")
              for t in ("t0", "t7")),
          repr(_vk.get("pair")))

    _th = HERE / "_v1233_thinking.json"
    _tk = _json.loads(_th.read_text(encoding="utf-8")) if _th.is_file() else {}
    _stg = _tk.get("stages") or {}
    check("V5.d ★ 思考 A/B：每个环节都有判定，且至少一个**可判定**",
          bool(_stg) and all(v.get("verdict") for v in _stg.values())
          and any(("不可判定" not in str(v.get("verdict")))
                  for v in _stg.values()),
          "环节 %d 个" % len(_stg))

    _tr = HERE / "_v1233_triage_runs.json"
    _trk = _json.loads(_tr.read_text(encoding="utf-8")) if _tr.is_file() else {}
    _nc = HERE / "_v1233_triage_negctl.json"
    _nck = _json.loads(_nc.read_text(encoding="utf-8")) if _nc.is_file() else {}
    check("V5.e ★ triage 频度专项批：报告了 k/n + Wilson 区间",
          (_trk.get("n_ok") or 0) >= 5 and _trk.get("wilson")
          and _trk.get("rate") is not None,
          "n_ok=%s rate=%s" % (_trk.get("n_ok"), _trk.get("rate")))
    check("V5.f ★ 负对照：锚点覆盖不到时 triage **必须 0 触发**",
          _nck and (_nck.get("hit") == 0) and (_nck.get("n_ok") or 0) >= 2,
          repr({k: _nck.get(k) for k in ("hit", "n_ok", "rate")}))

    _tl = HERE / "_v1233_tier_apply.json"
    _tlk = _json.loads(_tl.read_text(encoding="utf-8")) if _tl.is_file() else {}
    _r = _tlk.get("run") or {}
    _its = _r.get("items") or []
    check("V5.g ★ tier 确认真跑：留痕 + 生效/未生效两向 + 引用表按门收",
          bool(_r.get("tier_meta"))
          and any(x.get("tier_effective") is not None for x in _its)
          and any(x.get("tier_effective") is None for x in _its)
          and bool(_r.get("w_in_table")),
          "留痕=%s 进表=%s" % (str(_r.get("tier_meta"))[:80],
                             str(_r.get("w_in_table"))[:60]))
    check("V5.h ★ tier 基线（空确认表 + floor=2）引用表里**没有** W#",
          not ((_tlk.get("baseline") or {}).get("w_in_table")),
          repr((_tlk.get("baseline") or {}).get("w_in_table")))

    # ---- V6 报告层 ----
    _rp = HERE / "v1233_报告.md"
    _rt = _rp.read_bytes().decode("utf-8").replace(chr(13) + chr(10), chr(10)) \\
        if _rp.is_file() else ""
    _i = _rt.find("## 十、")
    _sec = _rt[_i:_i + 900] if _i >= 0 else ""
    check("V6 ★ 报告存在且 §十「仍未做 / 如实记账」明确为**无遗留**",
          bool(_rt) and ("仍未做" in _sec) and ("无遗留" in _sec)
          and ("### " not in _sec),
          "§十 片段：" + repr(_sec[:120]))


'''

A = "PHASES = {"
assert s.count(A) == 1, "PHASES 锚点 %d 次" % s.count(A)
s = s.replace(A, NEW + A)

O = '          "v1232": phase_v1232}'
assert s.count(O) == 1, "注册锚点 %d 次" % s.count(O)
s = s.replace(O, '          "v1232": phase_v1232,\n'
                 '          "v1233": phase_v1233}')

P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
ast.parse(s)
print("已加并注册 phase_v1233")
