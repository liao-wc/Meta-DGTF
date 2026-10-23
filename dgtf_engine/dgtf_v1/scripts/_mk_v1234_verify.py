# -*- coding: utf-8 -*-
"""[v1.23.4] 给 `_v122_verify.py` 加验收档 `v1234`（幂等；哨兵用**最后一项**）。"""
import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "_v122_verify.py"
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

SENTINEL = '"v1234": phase_v1234'
if SENTINEL in s:
    print("已注册 v1234，跳过")
    sys.exit(0)

NEW = '''def phase_v1234(src, mod):
    """[v1.23.4] 运行期三项总控（联网 / 思考 / 强度）。

    判据分四层：
      V1~V6 代码层：版本一致 / auto 恒等 / **思考总开关连 stages 整表** /
                    effort 取值集与拒非法 / 纯函数不改入参 /
                    load_config 四个出口都过它
      V7    接线层：CLI 三开关 + 交互询问 + 产物 `_runtime` 留痕
      V8    产物层：出厂 yaml 的 runtime 段是 auto（不覆盖）
      V9    报告层：`v1234_报告.md` 存在且写了设计取舍
    """
    import json as _json
    from pathlib import Path as _P

    _run_probe("_probe_v1234_runtime.py", src)

    _txt = _P(src).read_bytes().decode("utf-8").replace(chr(13) + chr(10),
                                                        chr(10))
    _D = _json.loads(_json.dumps(mod.DEFAULT_CONFIG))
    _J = lambda o: _json.dumps(o, sort_keys=True, ensure_ascii=False)

    check("V1 版本一致：主文件 __version__ / 冒烟 SRC / yaml 头",
          (getattr(mod, "__version__", "") == "1.23.4"
           and "元DGTF-V1.23.4.py" in (HERE / "smoke_test.py")
           .read_bytes().decode("utf-8")
           and "v1.23.4" in (HERE / "dgtf_config.yaml")
           .read_bytes().decode("utf-8")[:900]),
          "ver=%s" % getattr(mod, "__version__", "?"))

    # ---- V2 ★ 出厂恒等（这是「本版不改行为」的全部依据）----
    _a = getattr(mod, "_apply_runtime", None)
    _c0, _n0 = _a(_D) if _a else (None, None)
    check("V2 ★ 三项 auto ⇒ 配置**逐字恒等**（出厂零行为变化）",
          _a is not None and _J(_c0) == _J(_D) and _n0 == [],
          "notes=" + repr(_n0))

    # ---- V3 ★ 思考总开关必须连 stages 整表 ----
    def _stage_vals(cfg):
        return set(((cfg.get("api") or {}).get("thinking") or {})
                   .get("stages", {}).values())

    def _resolve(cfg, stage=None):
        _th = ((cfg.get("api") or {}).get("thinking") or {})
        _v = (_th.get("stages") or {}).get(stage) if stage else None
        if _v is None:
            _v = _th.get("default")
        return str(_v or "").lower() == "enabled"

    _off, _ = _a(_D, {"thinking": "off"}) if _a else ({}, None)
    _on, _ = _a(_D, {"thinking": "on"}) if _a else ({}, None)
    # 判别力自检：合成「只改 default、不动 stages」的配置必须**不满足**该判据
    _syn = _json.loads(_json.dumps(_D))
    _syn["api"]["thinking"]["default"] = "disabled"
    check("V3 ★ thinking=off ⇒ default 与 **stages 每一个键**都关",
          _a is not None and set(_stage_vals(_off)) == {"disabled"}
          and ((_off.get("api") or {}).get("thinking") or {})
          .get("default") == "disabled"
          and not any(_resolve(_off, k)
                      for k in (_D["api"]["thinking"]["stages"])),
          "stages 取值=" + repr(_stage_vals(_off)))
    check("V3.b 自检（判别力）：合成『只改 default』的配置必须**不满足**该判据",
          set(_stage_vals(_syn)) != {"disabled"}, "合成值不该全关")
    check("V3.c thinking=on ⇒ default 与 stages 全开（含出厂为 disabled 的）",
          _a is not None and set(_stage_vals(_on)) == {"enabled"}
          and all(_resolve(_on, k)
                  for k in (_D["api"]["thinking"]["stages"])), "")

    # ---- V4 effort 取值集 + 拒非法 ----
    _ef = getattr(mod, "_normalize_runtime_effort", None)
    _bad = [_a(_D, {"effort": "mediun"})[0] if _a else None,
            _a(_D, {"web": "maybe"})[0] if _a else None,
            _a(_D, {"thinking": "??"})[0] if _a else None]
    check("V4 ★ effort 取值集 = auto/low/high/max（low/high/max 三档可用）",
          tuple(getattr(mod, "_RUNTIME_EFFORTS", ())) == ("auto", "low",
                                                          "high", "max")
          and _ef is not None and _ef("max") == "max" and _ef("low") == "low"
          and _ef("high") == "high", repr(getattr(mod, "_RUNTIME_EFFORTS", None)))
    check("V4.b ★ 集合外的值（含 medium）一律被拒，且配置一字未改",
          _ef is not None and _ef("medium") is None
          and all(x is not None and _J(x) == _J(_D) for x in _bad),
          "三处非法值都应不改配置")

    # ---- V5 纯函数：不改入参 ----
    _b4 = _J(_D)
    if _a:
        _a(_D, {"web": "on", "thinking": "on", "effort": "max"})
    check("V5 ★ `_apply_runtime` 是纯函数（入参配置一字未改）",
          _a is not None and _J(_D) == _b4, "")

    # ---- V6 load_config 四个出口 ----
    _ok = True
    try:
        _ok = (_J(mod.load_config("")) == _J(_D)
               and _J(mod.load_config(str(HERE / "_no_such_rt.yaml")))
               == _J(_D))
    except Exception:  # noqa: BLE001
        _ok = False
    check("V6 ★ load_config 的缺省/空路径出口仍恒等且不炸",
          _ok and hasattr(mod, "_load_config_raw"), "")

    # ---- V7 接线 ----
    check("V7.a CLI 三开关已接线且 choices 收紧",
          all(x in _txt for x in ("--web", "--thinking", "--effort"))
          and "choices=list(_RUNTIME_SWITCHES)" in _txt
          and "choices=list(_RUNTIME_EFFORTS)" in _txt
          and "cfg, _rt_notes = _apply_runtime(cfg, {" in _txt, "")
    check("V7.b 交互：`_ask_runtime` + 5 元组 + **深拷副本** run_cfg",
          ("def _ask_runtime(cfg):" in _txt)
          and ("runtime = _ask_runtime(" in _txt)
          and ("run_cfg, _rt_notes = _apply_runtime(cfg, runtime)" in _txt)
          and ("meta = MetaDGTF(run_cfg)" in _txt), "")
    check("V7.c 产物带 `_runtime` 生效读数",
          '"_runtime": _runtime_snapshot(self.config)' in _txt, "")

    # ---- V8 出厂 yaml 的 runtime 段 ----
    try:
        import yaml as _yaml
        _ry = _yaml.safe_load((HERE / "dgtf_config.yaml")
                              .read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        _ry = {}
    check("V8 ★ 出厂 yaml 的 runtime 三项都是 auto（出厂 = 不覆盖既有键）",
          isinstance(_ry.get("runtime"), dict)
          and all(_ry["runtime"].get(k) == "auto"
                  for k in ("web", "thinking", "effort")),
          repr(_ry.get("runtime")))

    # ---- V9 报告层 ----
    _rp = HERE / "v1234_报告.md"
    _rt = _rp.read_bytes().decode("utf-8").replace(chr(13) + chr(10), chr(10)) \\
        if _rp.is_file() else ""
    check("V9 ★ 报告存在且写了「设计取舍」与三层优先级",
          bool(_rt) and ("取舍" in _rt)
          and ("auto" in _rt)
          and ("stages" in _rt), "报告 %d 字节" % len(_rt))


'''

A = "PHASES = {"
assert s.count(A) == 1, "PHASES 锚点 %d 次" % s.count(A)
s = s.replace(A, NEW + A)

O = '          "v1233": phase_v1233}'
assert s.count(O) == 1, "注册锚点 %d 次" % s.count(O)
s = s.replace(O, '          "v1233": phase_v1233,\n'
                 '          "v1234": phase_v1234}')

P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
ast.parse(s)
print("已加并注册 phase_v1234")
