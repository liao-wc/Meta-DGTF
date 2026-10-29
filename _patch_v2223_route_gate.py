# -*- coding: utf-8 -*-
"""[V2.2.23 / App 2.0.48] route 安全门：默认 union（预测默认不砍层），可配置 predict/preset。"""
from pathlib import Path
import py_compile

# 1) 引擎 V2.2.23（零行为差，版本/说明；route 门在 App 侧）
ENG = Path("dgtf_engine/dgtf_v2/engine")
SRC = ENG / "Meta-DGTF-V2.2.22.py"
DST = ENG / "Meta-DGTF-V2.2.23.py"
raw = SRC.read_bytes()
assert raw[:3] != b"\xef\xbb\xbf" and raw.count(b"\n") == raw.count(b"\r\n")
t = raw.decode("utf-8").replace("\r\n", "\n")


def rep(a, b):
    global t
    c = t.count(a)
    assert c == 1, "锚点 %d: %r" % (c, a[:60])
    t = t.replace(a, b)


rep("Meta-DGTF-道生三阶模型 · V2.2.22\n", "Meta-DGTF-道生三阶模型 · V2.2.23\n")
rep('__version__ = "2.2.22"', '__version__ = "2.2.23"')
rep("★ V2.2.22 补丁（动态最优配置全流程可达）：",
"""★ V2.2.23 补丁（route 安全门；引擎侧零行为差）：
      本版为 App 修复发版：道生 route 预测默认改为 union（预测只增不减，默认仍四层），
      可用 route_policy: preset|union|predict 显式选择；引擎参数通道复用 V2.2.22。

★ V2.2.22 补丁（动态最优配置全流程可达）：""")
out = t.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)
chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(DST), doraise=True)
print("OK", DST.name, len(chk))

# 2) daosheng_mode：route_policy 安全门
D = Path("dgtf_app/daosheng_mode.py")
t = D.read_text(encoding="utf-8")
old = '''    route = ",".join((local.get("route") or _norm_route(ds.get("route"))))
'''
new = '''    # ★ [V2.2.23] route 安全门：本地 route 预测默认**不砍层**。
    #   route_policy:
    #     union（默认）: 预设 route ∪ 预测 route（预设为四层时结果恒四层，预测仅供审计/补充）
    #     preset       : 完全忽略预测（纯预设）
    #     predict      : 旧行为（预测非空即采用，可砍层；用于显式省层实验）
    _route_preset = _norm_route(ds.get("route"))
    _route_pred = [str(x) for x in (local.get("route") or []) if str(x)]
    _route_policy = str(ds.get("route_policy") or "union").strip().lower()
    if _route_policy not in ("union", "preset", "predict"):
        _route_policy = "union"
    if _route_policy == "predict":
        _route_list = _route_pred or _route_preset
        _route_source = "predict" if _route_pred else "preset"
    elif _route_policy == "preset":
        _route_list = _route_preset
        _route_source = "preset"
    else:  # union
        _route_list = list(_route_preset)
        for _e in _route_pred:
            if _e not in _route_list:
                _route_list.append(_e)
        _route_source = ("union" if _route_pred and _route_pred != _route_preset
                         else "preset")
    route = ",".join(_route_list)
    if _route_policy != "predict" and _route_pred and _route_pred != _route_preset:
        warnings.append("route 安全门（%s）：预测=%s 未砍层，实际=%s"
                        % (_route_policy, ",".join(_route_pred), route))
'''
assert t.count(old) == 1
t = t.replace(old, new)
old2 = '''        "route": route,
        "rounds": rounds,
'''
new2 = '''        "route": route,
        # [V2.2.23] route 安全门读数（可审计）
        "route_policy": _route_policy,
        "route_source": _route_source,
        "route_prediction": list(_route_pred),
        "rounds": rounds,
'''
assert t.count(old2) == 1
t = t.replace(old2, new2)
D.write_text(t, encoding="utf-8")
py_compile.compile(str(D), doraise=True)
print("OK daosheng route safety gate")

# 3) 道生预设 yaml：route_policy 默认 union
Y = Path("configs/道生专属模式.yaml")
t = Y.read_text(encoding="utf-8")
if "route_policy:" not in t:
    old3 = 'route: "0,1,both,all"\n'
    new3 = ('route: "0,1,both,all"\n'
            '# ★ [V2.2.23] route 安全门：union（默认，预测不砍层）/ preset / predict（旧行为）\n'
            '#   V2.2.22 前本地 route 预测可直接把四层砍成 1 层（实测「极端天气」只跑研究层），\n'
            '#   默认改 union 后预测只增不减；要做省层实验再显式改 predict。\n'
            'route_policy: union\n')
    assert t.count(old3) == 1
    t = t.replace(old3, new3)
    Y.write_text(t, encoding="utf-8")
    print("OK preset route_policy=union")
else:
    print("preset already has route_policy")

# 4) _BUILTIN_DS 默认：union
t = D.read_text(encoding="utf-8")
old4 = '''    "route": "0,1,both,all",
    "rounds": "auto",
'''
new4 = '''    "route": "0,1,both,all",
    # [V2.2.23] route 安全门默认：预测不砍层
    "route_policy": "union",
    "rounds": "auto",
'''
assert t.count(old4) == 1
t = t.replace(old4, new4)
D.write_text(t, encoding="utf-8")
py_compile.compile(str(D), doraise=True)
print("OK builtin route_policy=union")
