# -*- coding: utf-8 -*-
"""零成本干跑：验证 _fullrun_V1248AB.py 的 plumbing（不花一分钱）。

做三件事：
  1. cfg 构建：A/B 两套，回读五个新键（确认 B 真开、A 真关）；
  2. mock LLM.call ⇒ 跑 route=['0'] rounds={'0':1}，验证 run_id 记账 + `_eml_finish`
     不抛错 + 产物里有 calls/tokens/duty/playbook；
  3. 打印「将要花的钱」的估算口径（只读，不调用 API）。
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.48.py"
sys.path.insert(0, str(HERE))
import _fullrun_V1248AB as R  # noqa: E402


def _load(tag):
    spec = importlib.util.spec_from_file_location("eng_%s" % tag, str(SRC))
    m = importlib.util.module_from_spec(spec)
    sys.modules["eng_%s" % tag] = m
    spec.loader.exec_module(m)
    return m


def _read(cfg, dotted):
    c = cfg
    for k in dotted.split("."):
        if not isinstance(c, dict) or k not in c:
            return "缺键"
        c = c[k]
    return c


bad = []
for tag, on in (("A", False), ("B", True)):
    eng = _load("dry_" + tag)
    cfg = R._build(eng, on)
    # 全开清单回读
    for k, v, _w in eng._ALL_ON_ITEMS:
        got = _read(cfg, k)
        if got != v:
            bad.append("[%s] 全开项 %s 回读=%r 期望=%r" % (tag, k, got, v))
    # 新键
    for k, v in R.NEW_KEYS.items():
        got = _read(cfg, k)
        want = v if on else ("出厂" if k not in () else None)
        if on and got != v:
            bad.append("[%s] 新键 %s 回读=%r 期望=%r" % (tag, k, got, v))
        if not on and got is True:
            bad.append("[%s] 新键 %s 竟然开着（基线不纯）" % (tag, k))
    print("[%s] 新键回读：%s" % (tag, {k: _read(cfg, k) for k in R.NEW_KEYS}))

    # mock LLM ⇒ 跑通 plumbing（★ 用临时 EML 目录，绝不污染生产记忆库）
    import tempfile
    _tmp = tempfile.mkdtemp(prefix="dgtf_dry_")
    eng.eml_dir = lambda *a, **k: Path(_tmp)
    eng.LLM.call = lambda system, user, *a, **k: (
        "- [concept] 占位候选：一段足够长的占位输出，用来过解析门槛。" * 2)
    m = eng.MetaDGTF(cfg)
    rid = "DRY_%s_%d" % (tag, int(time.time()))
    res = m.run(R.QUESTION, route=["0"], rounds={"0": 1},
                parallel_mode="serial", run_id=rid)
    res["playbook"] = m._eml_finish(res)
    for key in ("llm_calls", "llm_tokens", "views", "id", "playbook"):
        if key not in res:
            bad.append("[%s] 产物缺键 %s" % (tag, key))
    if str(res.get("id") or "") != rid:
        bad.append("[%s] run_id 没记账上（键名 id）：%r" % (tag, res.get("id")))
    _vs = res.get("views") or {}
    if "0" not in _vs:
        bad.append("[%s] 产物 views 缺层 0" % tag)
    elif "duty_trace" not in (_vs.get("0") or {}):
        bad.append("[%s] views[0] 缺 duty_trace" % tag)
    print("[%s] id=%s | calls=%s | tokens=%s | playbook.mode=%s"
          % (tag, res.get("id"), json.dumps(res.get("llm_calls")),
             json.dumps(res.get("llm_tokens")),
             (res.get("playbook") or {}).get("mode")))
    print("[%s] duty_trace(层0) 末条=%s"
          % (tag, json.dumps(((_vs.get("0") or {}).get("duty_trace") or [{}])[-1],
                             ensure_ascii=False)))

print("\n=== 干跑结论 ===")
if bad:
    for x in bad:
        print("  X", x)
    sys.exit(1)
print("  ✓ cfg 构建/新键开关/run_id 记账/_eml_finish/产物结构 全通（未调用任何 API）")
print("  ⇒ 可以开真跑。")
