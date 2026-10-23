# -*- coding: utf-8 -*-
"""[v1.23.2] 把 `P2.4.a` 从**采样判据**改成**构造性证明**（判据形态修正）。

原判据：`any(三题产物里 triage >= 1)`。问题：triage 是**低概率随机机制**，
n=3 采样在同配置下能给出 [1,0,0] 与 [0,…] ⇒ 判据本质是掷硬币。
新判据：triage 的组装逻辑已抽成纯函数 `_triage_suggestions`，
**构造输入直接证明「合格输入必产 ≥1 条」**，再配 3 条负对照 + 2 个变异体。
真跑采样读数降为**观察项**（只打印，不判红）。
"""
import ast
from pathlib import Path

P = Path("_v122_verify.py")
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

OLD = '''    tgt = [HERE / "outputs" / f"p2_run{i}" for i in (1, 2, 3)]
    mds = []
    for d in tgt:
        # [v1.23.1 遗留4] ★ 取**最新**产物，不取「文件名排序第一」——
        #   目录里可能同时留着历史产物（本次就是：04:42 的 P2a 旧跑 +
        #   00:11 的新跑）。按名排会读到**旧的那份**，于是「用当前版复真」
        #   变成「拿旧读数冒充新读数」。同族坑：判据的锚不能是移动靶。
        got = (sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime)
               if d.is_dir() else [])
        mds.append(got[-1] if got else None)
    if not all(mds):
        check("P2.4.a", False,
              f"三题产物未齐（{sum(1 for x in mds if x)}/3）—— 先跑 _run_v1221_p2.py")
    else:
        info = [_p2_triage_from_md(x) for x in mds]
        ns = [i["triage"] for i in info]
        check("P2.4.a", any(isinstance(n, int) and n >= 1 for n in ns),
              f"≥1 题 triage ≥ 1 条（实测 {ns}）")
        _drift = []'''

NEW = '''    # ===== [v1.23.2] ★ 判据形态修正：能力存在性 → **构造性证明** =====
    # 原判据是「三题真跑里 ≥1 题 triage ≥1 条」—— 那是对**低概率随机机制**
    # 做 n=3 采样：同配置两次批次给出 [1,0,0] 与 [0,…] ⇒ 本质是掷硬币。
    # 组装逻辑已抽成纯函数 `_triage_suggestions`，于是可以直接构造输入证明
    # 「合格输入必产 ≥1 条」，再配 3 条负对照；**采样读数降为观察项**。
    _tri = getattr(mod, "_triage_suggestions", None)
    check("P2.4.a0 机制已抽成纯函数（可构造性验证）", callable(_tri),
          "`_triage_suggestions` 不存在")
    if callable(_tri):
        def _tq(_asp, _anc, _f=2):
            return _tri(_asp, _anc, {"tier_floor": _f})

        _pos = _tq(["[外] 上游是否有官方标准"],
                   [{"id": "X1", "tier": 1,
                     "answers": ["上游是否有官方标准"]}])
        check("P2.4.a ★ 构造性证明：合格输入必产 ≥1 条建议",
              len(_pos) >= 1, repr(_pos)[:130])
        _n1 = _tq(["此时此处的最优方案本身（自指，无共同参照系）"],
                  [{"id": "X1", "tier": 1, "claim": "最优方案本身"}])
        check("P2.4.a-n1 负对照：真·自指 → 0 条", _n1 == [],
              "自指竟被建议降级：" + repr(_n1))
        _n2 = _tq(["两个候选方案之间的权衡"],
                  [{"id": "X1", "tier": 1, "claim": "两个候选方案之间的权衡"}])
        check("P2.4.a-n2 负对照：不属「缺外部材料」→ 0 条", _n2 == [],
              "非候选竟被建议降级：" + repr(_n2))
        _n3 = _tq(["[外] 上游是否有官方标准"],
                  [{"id": "X1", "tier": 4,
                    "answers": ["上游是否有官方标准"]}])
        check("P2.4.a-n3 负对照：锚点 tier 超门 → 0 条", _n3 == [],
              "超门锚点竟仍命中：" + repr(_n3))
        # ★ 2 个变异体：破坏 tier 门 / 破坏「真·自指」剔除
        import tempfile as _tf
        _mdir = Path(_tf.mkdtemp())
        _MUT = (
            ("tier 门",
             '                     if int(x.get("tier", 3) or 3) <= _floor',
             "                     if True",
             ("[外] 上游是否有官方标准",
              [{"id": "X1", "tier": 4, "answers": ["上游是否有官方标准"]}])),
            ("自指剔除",
             "        if _is_never_downgrade(_a):" + chr(10) + "            continue",
             "        if False:" + chr(10) + "            continue",
             ("此时此处的最优方案本身（自指，无共同参照系）",
              [{"id": "X1", "tier": 1, "claim": "最优方案本身"}])),
        )
        for _nm, _o, _n, (_asp, _anc) in _MUT:
            if txt.count(_o) != 1:
                check("P2.4.a-mut." + _nm, False,
                      "变异体锚点 %d 次" % txt.count(_o))
                continue
            _mp = _mdir / ("mut_tri_%s.py" % _nm)
            _mp.write_bytes(txt.replace(_o, _n).replace(chr(10), chr(13) + chr(10))
                            .encode("utf-8"))
            _red = True
            try:
                _mm = load_module(str(_mp))
                _red = len(_mm._triage_suggestions(_asp, _anc,
                                                   {"tier_floor": 2})) >= 1
            except Exception:  # noqa: BLE001
                _red = True
            check("P2.4.a-mut ★ 变异体「破坏%s」→ 对应负对照判红" % _nm, _red,
                  "变异体下判据没判红")
    # ---- 真跑采样读数：**观察项**（不判红；能力由上面的构造性证明负责）----
    tgt = [HERE / "outputs" / f"p2_run{i}" for i in (1, 2, 3)]
    mds = []
    for d in tgt:
        # [v1.23.1 遗留4] ★ 取**最新**产物，不取「文件名排序第一」——
        #   目录里可能同时留着历史产物。按名排会读到**旧的那份**，
        #   于是「用当前版复真」变成「拿旧读数冒充新读数」。
        got = (sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime)
               if d.is_dir() else [])
        mds.append(got[-1] if got else None)
    if all(mds):
        info = [_p2_triage_from_md(x) for x in mds]
        _ns = [i["triage"] for i in info]
        print(f"  ℹ️  [观察项] 真跑 triage 采样 = {_ns}（n=3；**低概率机制** ⇒"
              f" 0 次命中属正常，本项**不判红**：能力已由 P2.4.a 构造性证明）")
        print("  ℹ️  P2.4 详情：" + "；".join(
            f"{p.parent.name} triage={i['triage']} 漂移 {i['und_from']}/"
            f"{i['log_total']}" for p, i in zip(mds, info)))
        _drift = []'''
assert s.count(OLD) == 1, "P2.4 块锚点命中 %d 次" % s.count(OLD)
s = s.replace(OLD, NEW)

# 把原 else 分支里剩下的「漂移 + 打印」接回来（现在是 all(mds) 分支）
OLD2 = '''        for i in info:
            if i["log_total"] == 0:
                _drift.append(None)
            else:
                _drift.append(i["und_from"] / i["log_total"])
        _ok_drift = all((d is None) or (d <= 0.5) for d in _drift)
        check("P2.4.b", _ok_drift,
              f"无题出现「全是 partial」漂移（und→partial 占比 ≤50%："
              f"{[None if d is None else round(d, 2) for d in _drift]}）")
        print("  ℹ️  P2 整体判据已由 `--phase p2b` 承担"
              "（P2a 单档记录保留为历史：触发条件已修通，卡在匹配对象；"
              "P2b 换匹配对象后打通）。")
        print("  ℹ️  P2.4 详情：" + "；".join(
            f"{p.parent.name} triage={i['triage']} 漂移 {i['und_from']}/"
            f"{i['log_total']}" for p, i in zip(mds, info)))
        for p, i in zip(mds, info):
            if i["triage"]:
                _t = p.read_text(encoding="utf-8")
                _ln = [l for l in _t.splitlines()
                       if "triage" in l and "降级" in l][:2]
                print(f"  ℹ️  {p.parent.name} 降级行：{_ln}")'''
NEW2 = '''        for i in info:
            if i["log_total"] == 0:
                _drift.append(None)
            else:
                _drift.append(i["und_from"] / i["log_total"])
        _ok_drift = all((d is None) or (d <= 0.5) for d in _drift)
        check("P2.4.b", _ok_drift,
              f"无题出现「全是 partial」漂移（und→partial 占比 ≤50%："
              f"{[None if d is None else round(d, 2) for d in _drift]}）")
        print("  ℹ️  P2 整体判据已由 `--phase p2b` 承担"
              "（P2a 单档记录保留为历史：触发条件已修通，卡在匹配对象；"
              "P2b 换匹配对象后打通）。")
        for p, i in zip(mds, info):
            if i["triage"]:
                _t = p.read_text(encoding="utf-8")
                _ln = [l for l in _t.splitlines()
                       if "triage" in l and "降级" in l][:2]
                print(f"  ℹ️  {p.parent.name} 降级行：{_ln}")
    else:
        print("  ℹ️  [观察项] 三题产物未齐（%d/3），采样读数不可得"
              % sum(1 for x in mds if x))'''
assert s.count(OLD2) == 1, "P2.4 尾块锚点命中 %d 次" % s.count(OLD2)
s = s.replace(OLD2, NEW2)

ast.parse(s)
P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("P2.4.a 已改为构造性证明（+3 负对照 +2 变异体；采样降为观察项）")
