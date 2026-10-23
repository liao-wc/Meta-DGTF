# -*- coding: utf-8 -*-
"""把 v1.23.13 的判据注入 smoke_test.py，并把 SRC 指到新版。

新增 `check_v12313_auto_dispatch`：
  · 十二项齐全 + 每项都带留痕（值 / 来源 / 理由）；
  · **逐项显式接管**：改一项只改这一项（十项各验一次）；
  · **总开关**：`auto.enabled=false` ⇒ 一项都不进 auto；
  · **历史自适应**：五条正 + 三条负对照（中位补圈 / 砍层 / 不砍 /
    降档 / 不降档 / 联网不再接 / 降级阈值）；
  · **技术债**：取向归一化唯一实现、装配器唯一实现、两条路径 schema 相同；
  · **产物渲染**：十二行表 + 无 plan 时为空。
"""
import ast
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE / "smoke_test.py"
raw = SK.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

NEWFN = '''def check_v12313_auto_dispatch():
    """[v1.23.13] 统一自适应调度器：十二项逐项可单独接管 + 历史自适应 + 技术债。

    ★ 负对照全部内置（没有负对照的「全绿」只说明判据没跑）：
      · 十二项各自都有留痕（值 / 来源 / 理由），缺一项即判红；
      · **逐项独立**：显式给一项，只改那一项，其余仍是 auto
        —— 变异体「explicit 泄漏到全部项」必须判红；
      · 总开关关掉 ⇒ 一项都不进 auto（回 v1.23.12 行为）；
      · 历史自适应**两向**：高截断率不砍层 / 低截断率才砍；
        高 token 降档 / 有限 token 不降；失败多则降级阈值收紧；
      · 技术债：`_normalize_orientation` 与 `_assemble_plan` 各只有 1 处定义，
        且 `auto_plan()` 两条路径的返回 **schema 逐键相同**。
    """
    import copy as _copy
    import json as _json
    m = globals().get("mod")
    bad = []
    if m is None or not hasattr(m, "auto_dispatch"):
        print("  \\u2717 [v12313] 命名空间里没有 auto_dispatch")
        return False
    _ORDER = m._AUTO_ITEM_ORDER
    if len(_ORDER) != 12:
        bad.append("十二项不齐：%d 项" % len(_ORDER))
    _FACT = "新中国的成立时间是什么时候"
    _DEC = "这份方案怎么落地"
    cfg0 = m.load_config("")

    def _pick(plan, k):
        return (plan.get("_items") or {}).get(k) or {}

    def _src(plan, k):
        return _pick(plan, k).get("source")

    def _val(plan, k):
        return _pick(plan, k).get("value")

    # ── A 十二项齐全 + 留痕 ───────────────────────────────────
    p = m.auto_dispatch(_FACT, cfg0)
    for k in _ORDER:
        if k not in (p.get("_items") or {}):
            bad.append("缺留痕：%s" % k)
        elif not str(_pick(p, k).get("reason") or ""):
            bad.append("留痕没有理由：%s" % k)
    if not str(p.get("mode") or ""):
        bad.append("事实短题的模式没定下来")

    # ── B 逐项显式接管：只改这一项 ────────────────────────────
    _EX = {"route": ["0", "1"], "cost_profile": "quality", "mode": "A",
           "rounds": "0:9,1:9,both:9,all:9", "orientation": "decision",
           "web": "off", "thinking": "on", "effort": "max",
           "landing": "decision", "decidability": "off"}
    for _k, _v in _EX.items():
        _p1 = m.auto_dispatch(_FACT, cfg0, explicit={_k: _v})
        if _src(_p1, _k) != "explicit":
            bad.append("显式给了 %s 但来源不是显式（%r）" % (_k, _src(_p1, _k)))
        _leak = [x for x in _ORDER if x != _k
                 and x not in ("stop", "web_downgrade")
                 and _src(_p1, x) != "auto"]
        if _leak:
            bad.append("显式 %s 泄漏到了别的项：%s" % (_k, _leak))
    # 配置级接管（stop / web_downgrade 无 CLI，靠配置改过）
    _cs = _copy.deepcopy(cfg0)
    _cs["spiral"]["round_stall_limit"] = 9
    if _src(m.auto_dispatch(_FACT, _cs), "stop") != "config":
        bad.append("配置改了 round_stall_limit，stop 来源却不是配置")

    # ── C 总开关 ─────────────────────────────────────────────
    _co = _copy.deepcopy(cfg0)
    _co["auto"]["enabled"] = False
    _pf = m.auto_dispatch(_FACT, _co)
    _hit = [k for k in _ORDER if _src(_pf, k) == "auto"]
    if _hit:
        bad.append("总开关关掉仍有 auto 项：%s" % _hit)

    # ── D 历史自适应（正向 + 负对照）──────────────────────────
    H = {"n": 5, "tokens_med": 100000, "tri_rate": 0.8, "cut_rate": 0.1,
         "layer_rounds": {"0": 3, "1": 3, "both": 2, "all": 2},
         "modes": {}, "profiles": {}, "web_hit": 12, "web_fail": 0,
         "web_empty": 0, "mismatch": 0}
    _ph = m.auto_dispatch(_FACT, cfg0, history=H)
    if "中位" not in str(_pick(_ph, "rounds").get("reason")):
        bad.append("有历史却没按中位数补圈")
    if _val(_ph, "route") != ["0", "1", "both"]:
        bad.append("低截断率 + 事实短题应砍到 0/1/both，实得 %r"
                   % (_val(_ph, "route"),))
    if _val(m.auto_dispatch(_FACT, cfg0,
                            history=dict(H, cut_rate=0.9)), "route") != \\
            list(m._ENTRIES):
        bad.append("高截断率时不该砍层（负对照失效）")
    if _val(m.auto_dispatch(_DEC, cfg0, history=H), "cost_profile") != \\
            "balanced":
        bad.append("有限 token 的决策题不该降档（负对照失效）")
    if _val(m.auto_dispatch(_DEC, cfg0,
                            history=dict(H, tokens_med=900000)),
            "cost_profile") != "economy":
        bad.append("高 token 中位数没有降档")
    if _val(m.auto_dispatch(_DEC, cfg0,
                            history=dict(H, tri_rate=0.2)),
            "cost_profile") != "balanced":
        bad.append("低三态一致率时不该降档（质量优先）")
    if not _val(m.auto_dispatch(_FACT, cfg0,
                                history=dict(H, web_fail=5)),
                "web_downgrade").get("auto_disable_after_failures") == 2:
        bad.append("历史联网失败多，降级阈值没收紧")
    if _val(m.auto_dispatch(_FACT, cfg0,
                            history=dict(H, n=4, web_hit=0,
                                         web_empty=4)), "web") is not False:
        bad.append("历史联网长期收 0 条，却仍自动接入")

    # ── E 技术债：唯一实现 + 两条路径同 schema ────────────────
    _src_txt = SRC.read_text(encoding="utf-8")
    if _src_txt.count("def _normalize_orientation(") != 1:
        bad.append("取向归一化不是唯一实现")
    if _src_txt.count("def _assemble_plan(") != 1:
        bad.append("装配器不是唯一实现")
    _left = sum(_src_txt.count(x) for x in
                ('if _o not in ("boundary", "decision"):',
                 'if _ori not in ("decision", "boundary"):'))
    if _left:
        bad.append("旧的取向归一化残留 %d 处（没合并干净）" % _left)

    class _Stub:
        def call(self, *a, **kw):
            return _json.dumps({"mode": "A", "orientation": "boundary",
                                "rounds": {"0": 5, "1": 5, "both": 5,
                                           "all": 5},
                                "reason": "stub", "confidence": 0.9},
                               ensure_ascii=False)

        def parse_json(self, raw):
            try:
                return _json.loads(raw)
            except Exception:  # noqa: BLE001
                return {}

    _p1 = m.auto_plan(_FACT, cfg0, llm=_Stub())
    _p2 = m.auto_plan(_FACT, cfg0)          # 无 key ⇒ 两段式降级出口
    if sorted(_p1) != sorted(_p2):
        bad.append("auto_plan 两条路径 schema 不同：%s vs %s"
                   % (sorted(_p1), sorted(_p2)))
    for _k in ("route", "mode", "rounds", "cost_profile", "max_calls",
               "orientation"):
        if _k not in _p1:
            bad.append("技术债未清：单调用路径缺键 %s" % _k)

    # ── F 产物渲染 ───────────────────────────────────────────
    _ls = "".join(m._auto_dispatch_lines({"_auto_dispatch": p}))
    if "**自动调度**" not in _ls:
        bad.append("产物没有「自动调度」表")
    _rows = [l for l in _ls.split("\\n") if l.startswith("| ") and "来源" not in l]
    if len(_rows) != 12:
        bad.append("调度表不是十二行（%d）" % len(_rows))
    if m._auto_dispatch_lines({}) != []:
        bad.append("没有 plan 时调度表不是空")

    if bad:
        for _x in bad:
            print("  \\u2717 [v12313] %s" % _x)
        return False
    print("  \\u2713 [v12313] 十二项逐项接管（10 项 CLI + 2 项配置）/ 总开关 / "
          "历史自适应（5 正 3 负）/ 技术债（唯一实现 + 两路同 schema）/ 产物表")
    return True


'''
ANCHOR = "def check_v12310_render_ops():"
assert s.count(ANCHOR) == 1, "check_v12310_render_ops 命中 %d 次" % s.count(ANCHOR)
s = s.replace(ANCHOR, NEWFN + ANCHOR, 1)

OLD_REG = '''    if not check_v12312_anchor_lanes():
        return 1
'''
NEW_REG = OLD_REG + '''    if not check_v12313_auto_dispatch():
        return 1
'''
assert s.count(OLD_REG) == 1, "runner 注册点命中 %d 次" % s.count(OLD_REG)
s = s.replace(OLD_REG, NEW_REG, 1)

pat = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
assert len(pat.findall(s)) == 1, "SRC 行不是 1 行"
s = pat.sub('SRC = HERE / "元DGTF-V1.23.13.py"', s, count=1)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
ast.parse(out.decode("utf-8"))
SK.write_bytes(out)
print("smoke_test.py 已更新：新增 check_v12313_auto_dispatch 并挂进 runner；"
      "SRC ->",
      re.findall(r"SRC = HERE / .*", out.decode("utf-8"))[:1])
