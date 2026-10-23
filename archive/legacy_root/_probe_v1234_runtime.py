# -*- coding: utf-8 -*-
"""[v1.23.4] 探针：运行期三项总控（联网 / 思考 / 强度）。

补冒烟档没覆盖的四件事：
  · T4 **跨轮不记忆** —— 交互里第 1 轮选 off、第 2 轮选 auto，必须回到
    yaml 的值（这正是 `_apply_runtime` 必须「深拷 + 不改入参」的原因）；
  · T5 产物**真的**产出 `_runtime` 键（构造最小 MetaDGTF 调 `_pack_result`）；
  · T6 CLI 端到端：`--web/--thinking/--effort` 真的被 argparse 接受、
    且**非法值被拦**（`--effort medium` 必须 SystemExit≠0）；
  · T9 **优先级**：命令行覆盖 yaml 的 `runtime:` 段（与 `--profile`
    覆盖 `cost_profile` 同纪律）。
另加 2 个变异体（T7 浅拷改入参 / T8 只应用两项）。

用法：python _probe_v1234_runtime.py [元DGTF-V1.23.4.py]
改前跑（v1.23.3）应整篇报红（`_apply_runtime` 等符号不存在）。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "元DGTF-V1.23.4.py"
if not SRC.is_absolute():
    SRC = HERE / SRC

R = []


def ck(tag, cond, note=""):
    R.append((tag, bool(cond), note))


import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("dgtf_rt", SRC)
mod = importlib.util.module_from_spec(spec)
sys.modules["dgtf_rt"] = mod
spec.loader.exec_module(mod)

J = lambda o: json.dumps(o, sort_keys=True, ensure_ascii=False)
NL = chr(10)
TD = Path(tempfile.mkdtemp())

# ---------------------------------------------------------- 0 改前兼容门
_COMPAT = (
    (hasattr(mod, "_apply_runtime"), "存在 _apply_runtime"),
    (hasattr(mod, "_runtime_snapshot"), "存在 _runtime_snapshot"),
    (hasattr(mod, "_runtime_summary_line"), "存在 _runtime_summary_line"),
    (hasattr(mod, "_normalize_runtime_switch"), "存在 _normalize_runtime_switch"),
    (hasattr(mod, "_normalize_runtime_effort"), "存在 _normalize_runtime_effort"),
    ("runtime" in mod.DEFAULT_CONFIG, "DEFAULT_CONFIG 含 runtime 段"),
    (hasattr(mod, "_load_config_raw"), "load_config 已拆出 _load_config_raw"),
)
_miss = [t for ok, t in _COMPAT if not ok]
if _miss:
    for _t in _miss:
        print("  ✗ 兼容门：" + _t)
    print(NL + "改前版本（%s）：运行期总控尚未具备 → 整篇判红" % SRC.name)
    print(NL + "PASS 0 / FAIL %d" % len(_COMPAT))
    sys.exit(1)

D = json.loads(json.dumps(mod.DEFAULT_CONFIG))

# ---------------------------------------------------------- T1 auto 恒等
_c, _n = mod._apply_runtime(D)
ck("T1 ★ 三项 auto ⇒ 配置**逐字恒等**（出厂零行为变化）", J(_c) == J(D) and _n == [],
   "notes=" + repr(_n))

# ---------------------------------------------------------- T2 三项各自落键
_ck = {}
for _k, _v in (("web", "on"), ("web", "off"),
               ("thinking", "on"), ("thinking", "off"),
               ("effort", "low"), ("effort", "high"), ("effort", "max")):
    _ck[_k + "=" + _v] = mod._apply_runtime(D, {_k: _v})[0]
ck("T2a web=on  ⇒ web_search.enabled True",
   _ck["web=on"]["web_search"]["enabled"] is True, "")
ck("T2b web=off ⇒ web_search.enabled False",
   _ck["web=off"]["web_search"]["enabled"] is False, "")
ck("T2c thinking=off ⇒ default+stages 全 disabled",
   _ck["thinking=off"]["api"]["thinking"]["default"] == "disabled"
   and set(_ck["thinking=off"]["api"]["thinking"]["stages"].values())
   == {"disabled"}, "")
ck("T2d thinking=on  ⇒ default+stages 全 enabled",
   _ck["thinking=on"]["api"]["thinking"]["default"] == "enabled"
   and set(_ck["thinking=on"]["api"]["thinking"]["stages"].values())
   == {"enabled"}, "")
ck("T2e effort 三档各自落键",
   [_ck["effort=" + v]["api"]["thinking"]["effort"]
    for v in ("low", "high", "max")] == ["low", "high", "max"], "")

# ---------------------------------------------------------- T3 与 LLM 解析联动
_res = {}


def _resolve(cfg, stage=None):
    th = None
    if stage:
        th = ((cfg.get("api") or {}).get("thinking")
              or {}).get("stages", {}).get(stage)
    if th is None:
        th = ((cfg.get("api") or {}).get("thinking") or {}).get("default")
    return str(th or "").lower() == "enabled"


# 出厂：auto_plan=enabled、decompose_normal=disabled
ck("T3a 出厂 auto：auto_plan 开 / decompose_normal 关（v1.23.3 同值）",
   _resolve(D, "auto_plan") is True
   and _resolve(D, "decompose_normal") is False, "")
ck("T3b thinking=off ⇒ **任一环节**都关（含出厂为 enabled 的那些）",
   not any(_resolve(_ck["thinking=off"], k)
           for k in (D["api"]["thinking"]["stages"])),
   "")
ck("T3c thinking=on ⇒ **任一环节**都开（含出厂为 disabled 的那些）",
   all(_resolve(_ck["thinking=on"], k)
       for k in (D["api"]["thinking"]["stages"])), "")
ck("T3d thinking=on ⇒ 未声明的环节（掉 default）也开",
   _resolve(_ck["thinking=on"], "从未声明过的环节") is True, "")

# 真构造 LLM 再核一遍（有 key 时）
try:
    import os
    _has_key = bool(os.getenv("DGTF_API_KEY") or os.getenv("OPENAI_API_KEY"))
except Exception:  # noqa: BLE001
    _has_key = False
if _has_key:
    _L = mod.LLM(_ck["thinking=off"])
    ck("T3e ★ LLM 真实解析：thinking=off ⇒ 没有任何环节开档",
       not [k for k, v in _L.thinking_stages.items()
            if str(v).lower() == "enabled"]
       and str(_L.thinking_default).lower() == "disabled", "")
    _L2 = mod.LLM(_ck["effort=max"])
    ck("T3f LLM 真实解析：effort=max 落进 thinking_effort",
       str(_L2.thinking_effort) == "max", "")
else:
    ck("T3e/T3f LLM 真实解析（需要 key，本机没有 ⇒ 记为跳过）", True,
       "跳过：无 DGTF_API_KEY")

# ---------------------------------------------------------- T4 ★ 跨轮不记忆
_base = json.loads(json.dumps(D))
_r1, _ = mod._apply_runtime(_base, {"web": "off", "thinking": "off",
                                    "effort": "high"})
_r2, _ = mod._apply_runtime(_base, {"web": "auto", "thinking": "auto",
                                    "effort": "auto"})
ck("T4a ★ 第 2 轮选 auto ⇒ 回到**出厂值**（不是第 1 轮的 off）",
   _r2["web_search"]["enabled"] == D["web_search"]["enabled"]
   and _r2["api"]["thinking"]["default"] == D["api"]["thinking"]["default"]
   and _r2["api"]["thinking"]["effort"] == D["api"]["thinking"]["effort"],
   "r2.web=%r r2.default=%r" % (_r2["web_search"]["enabled"],
                                _r2["api"]["thinking"]["default"]))
ck("T4b 共享 cfg 未被第 1 轮污染（纯函数）", J(_base) == J(D), "")

# ---------------------------------------------------------- T5 产物留痕
try:
    _meta = object.__new__(mod.MetaDGTF)
    # ★ [v1.23.28 补] 本夹具只测 `_runtime` 留痕，不该被外部锚点通道牵连。
    #   但 `external_anchor.enabled` 的出厂默认在 v1.21.x 已由 false 改 true
    #   ⇒ `_anchor_report_for_pack` 会走到 `_anchor_crosscheck`，而它依赖
    #   `_anchors` / `_anchor_report` 等一批**由 run() 初始化**的属性，用
    #   `object.__new__` 绕过后全都没有。这里显式关掉该通道（本探针不测它）。
    _cfg_t5 = dict(_ck["thinking=off"])
    _cfg_t5.setdefault("external_anchor", {})["enabled"] = False
    _meta.config = _cfg_t5
    _meta.llm = type("_LL", (), {"total_calls": 0, "total_tokens": 0})()
    _meta.pools = {}
    _meta.channels = ()
    _meta.self_text = []
    _meta.decidability_result = {}
    _meta._tri_agree = 0
    _meta._tri_total = 0
    _meta._orientation = "auto"
    # ★ [v1.23.28 补] `_pack_result` 现在会读 `self._anchor_report`
    #   （`_anchor_report_for_pack`）—— 该属性在 `run()` 里初始化，
    #   而本夹具用 `object.__new__` 绕过 `__init__`/`run` ⇒ 必须显式补上。
    #   这是**夹具与引擎不同步**（探针写于 v1.23.4），不是引擎缺陷。
    _meta._anchor_report = None
    _meta._ext_assess_cache = {}
    _pack = mod.MetaDGTF._pack_result(
        _meta, "q", ["0"], {}, 1, {})
    ck("T5 ★ `_pack_result` 真的产出 `_runtime` 生效读数",
       isinstance(_pack.get("_runtime"), dict)
       and _pack["_runtime"].get("web_enabled") is False
       and _pack["_runtime"].get("thinking_default") == "disabled",
       repr(_pack.get("_runtime"))[:120])
except Exception as _e:  # noqa: BLE001
    ck("T5 ★ `_pack_result` 真的产出 `_runtime` 生效读数", False,
       type(_e).__name__ + ": " + str(_e)[:80])

# ---------------------------------------------------------- T6 CLI 端到端
_help = subprocess.run([sys.executable, str(SRC), "--help"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=180)
_h = _help.stdout + _help.stderr
ck("T6a CLI --help 列出三个总控开关",
   all(x in _h for x in ("--web", "--thinking", "--effort")), "")
_bad = subprocess.run([sys.executable, str(SRC), "--effort", "medium", "x"],
                      capture_output=True, text=True, encoding="utf-8",
                      errors="replace", timeout=180)
ck("T6b ★ CLI 拒绝集合外的强度（--effort medium ⇒ 非零退出）",
   _bad.returncode != 0, "rc=%d" % _bad.returncode)
_bad2 = subprocess.run([sys.executable, str(SRC), "--web", "maybe", "x"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=180)
ck("T6c ★ CLI 拒绝集合外的开关（--web maybe ⇒ 非零退出）",
   _bad2.returncode != 0, "rc=%d" % _bad2.returncode)

# ---------------------------------------------------------- T7 变异体：浅拷
_src = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
_O7 = "    cfg = json.loads(json.dumps(base_cfg or {}))"
_Q = chr(34)
if _src.count(_O7) == 1:
    _p7 = TD / "mut_rt_shallow.py"
    _p7.write_bytes(_src.replace(_O7, "    cfg = dict(base_cfg or {})")
                    .replace(NL, chr(13) + NL).encode("utf-8"))
    try:
        _spec7 = importlib.util.spec_from_file_location("mut_rt_shallow", str(_p7))
        _m7 = importlib.util.module_from_spec(_spec7)
        sys.modules["mut_rt_shallow"] = _m7
        _spec7.loader.exec_module(_m7)
        _b7 = json.loads(json.dumps(_m7.DEFAULT_CONFIG))
        _m7._apply_runtime(_b7, {"thinking": "off"})
        _red = J(_b7) != J(_m7.DEFAULT_CONFIG)   # 入参被改了 ⇒ 判据该红
    except Exception:  # noqa: BLE001
        _red = True
    ck("T7 变异体「浅拷（改入参）」⇒ 纯函数判据判红", _red, "")
else:
    ck("T7 变异体可构造", False, "锚点命中 %d 次" % _src.count(_O7))

# ---------------------------------------------------------- T8 变异体：只应用两项
_O8 = ("    if ef not in (None, " + _Q + "auto" + _Q
       + ") and not _runtime_thinking_on(cfg):")
if _src.count(_O8) == 1:
    _p8 = TD / "mut_rt_noeffortwarn.py"
    _p8.write_bytes(_src.replace(_O8, "    if False:")
                    .replace(NL, chr(13) + NL).encode("utf-8"))
    try:
        _spec8 = importlib.util.spec_from_file_location("mut_rt_nowarn", str(_p8))
        _m8 = importlib.util.module_from_spec(_spec8)
        sys.modules["mut_rt_nowarn"] = _m8
        _spec8.loader.exec_module(_m8)
        _b8 = json.loads(json.dumps(_m8.DEFAULT_CONFIG))
        _c8, _n8 = _m8._apply_runtime(_b8, {"thinking": "off", "effort": "high"})
        _red = not any("不生效" in x for x in _n8)   # 提示没了 ⇒ 判据该红
    except Exception:  # noqa: BLE001
        _red = True
    ck("T8 变异体「抠掉『强度不生效』提示」⇒ 判据判红", _red, "")
else:
    ck("T8 变异体可构造", False, "锚点命中 %d 次" % _src.count(_O8))

# ---------------------------------------------------------- T9 优先级：CLI > yaml
_y = TD / "rt_prio.yaml"
_y.write_bytes(("runtime:" + NL + "  web: off" + NL + "  thinking: off"
                + NL).encode("utf-8"))
_lc = mod.load_config(str(_y))
_after = mod._apply_runtime(_lc, {"web": "on", "thinking": "on"})[0]
ck("T9 ★ 命令行覆盖 yaml：yaml 写 off、CLI 给 on ⇒ on 生效",
   _lc["web_search"]["enabled"] is False
   and _after["web_search"]["enabled"] is True
   and _after["api"]["thinking"]["default"] == "enabled", "")

# ---------------------------------------------------------- T10 部分非法不连坐
_c10, _n10 = mod._apply_runtime(D, {"web": "off", "effort": "mediun"})
ck("T10 一项非法不连坐：web=off 仍生效，effort 被拒且告警",
   _c10["web_search"]["enabled"] is False
   and _c10["api"]["thinking"]["effort"] == D["api"]["thinking"]["effort"]
   and any("非法" in x for x in _n10), repr(_n10))

# ---------------------------------------------------------- T12 请求值回显
_c12, _ = mod._apply_runtime(D, {"web": "on", "thinking": "off",
                                 "effort": "max"})
ck("T12 ★ 产物 `requested` 回显**本次请求**（三项用请求值；"
   "live_checkpoint/ckpt_interval 随配置 —— v1.23.49 加两键后仍**整表**回显）",
   mod._runtime_snapshot(_c12)["requested"]
   == {"web": "on", "thinking": "off", "effort": "max",
       "live_checkpoint": True, "ckpt_interval": 30.0},
   repr(mod._runtime_snapshot(_c12)["requested"]))
ck("T12b 只给一项时，另两项记为 auto（请求语义完整）",
   mod._runtime_snapshot(mod._apply_runtime(D, {"web": "off"})[0])["requested"]
   == {"web": "off", "thinking": "auto", "effort": "auto",
       "live_checkpoint": True, "ckpt_interval": 30.0}, "")

try:
    import yaml as _yaml
    _ry = _yaml.safe_load((HERE / "dgtf_config.yaml").read_text(encoding="utf-8"))
except Exception as _e:  # noqa: BLE001
    _ry = {}
    print("  · 读出厂 yaml 失败：" + type(_e).__name__)
ck("T11 出厂 yaml 存在 runtime 段（第三向：必须列全 DEFAULT_CONFIG 的键）",
   isinstance(_ry.get("runtime"), dict), repr(_ry.get("runtime")))
ck("T11b 出厂 yaml 的 runtime 三项都是 auto（出厂 = 不覆盖）",
   isinstance(_ry.get("runtime"), dict)
   and all(_ry["runtime"].get(k) == "auto"
           for k in ("web", "thinking", "effort")), repr(_ry.get("runtime")))

# ============================================================ 汇总
_p = sum(1 for _, ok, _n in R if ok)
_f = len(R) - _p
for _t, _ok, _n in R:
    print(("  ✓ " if _ok else "  ✗ ") + _t
          + (("　" + _n) if _n and not _ok else ""))
print(NL + "PASS %d / FAIL %d" % (_p, _f))
sys.exit(0 if _f == 0 else 1)
