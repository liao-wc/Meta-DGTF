#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.32 变异体：给 `check_v12332_discipline` 背书（M1~M9）。"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

MUTS = [
    ("M1 α 不做机会校正（退化成原始一致率）",
     "    return {\"alpha\": 1.0 - (Do / De), \"n_units\": len(_units),",
     "    return {\"alpha\": 1.0 - Do, \"n_units\": len(_units),"),
    ("M2 α 恒 1（全绿假读数）",
     "    if De <= 1e-12:",
     "    if True:"),
    ("M3 少数类一致不筛类（把全部 unit 计入）",
     "        if _rare not in _r:\n            continue",
     "        if False:\n            continue"),
    ("M4 尺度登记失效（三态登记成 ratio）",
     '    "tri_state_agreement": "ordinal",',
     '    "tri_state_agreement": "ratio",'),
    ("M5 定序禁词检查恒空",
     "    _bad = _SCALE_FORBIDDEN.get(str(scale), ())",
     "    _bad = ()"),
    ("M6 级联主因取最后一条（放弃优先级）",
     "    _ordered = sorted(_rs, key=lambda r: (stop_priority(r), _rs.index(r)))",
     "    _ordered = list(_rs)"),
    ("M7 主因硬造成固定串（不在 all 里）",
     "    return {\"primary\": _ordered[0], \"ordered\": _ordered, \"all\": _rs}",
     "    return {\"primary\": \"自然安住\", \"ordered\": _ordered, \"all\": _rs}"),
    ("M8 CSD 恒判「有前兆」",
     "            \"hint\": bool(_rising and _ac1 > 0.3)}",
     "            \"hint\": True}"),
    ("M9 成本两分失效（分类恒 ops）",
     '    return "eval" if str(stage or "") in _LLM_EVAL_STAGES else "ops"',
     '    return "ops"'),
    ("M10 截断两向只报一面（丢的恒 0）",
     '        "lost_core": len(_miss),',
     '        "lost_core": 0,'),
    ("M11 输入自检规则类恒空",
     '    _q = str(q or "")\n    out = []',
     '    return []\n    _q = str(q or "")\n    out = []'),
    ("M12 言语行为判词恒空（公文体不告警）",
     '        _verdict = "公文体风险：全部/多数为「请求」，无「承诺」型动作（没人认领）"',
     '        _verdict = ""'),
    ("M13 FMEA 恒判可检测",
     '    return "⚠️ **不可检测**（没有对应标记 —— 它不会出现在任何读数里）"',
     '    return "可检测"'),
    ("M14 多样性组合数恒满配",
     '    _combos = max(0, len(_layers)) * max(0, len(_ch))',
     '    _combos = 12'),
    ("M15 nogoods 记录内容失效（kind/why 抹空）",
     '            "kind": str(kind or ""), "why": str(why or ""),',
     '            "kind": "", "why": "",'),
    ("M16 anytime 恒判「已确立」",
     '    return bool(lb["lower"] > float(thr)), lb',
     '    return True, lb'),
    ("M17 发散检测恒判收敛",
     '    if v2 > 1.5 * v1 and ac1 > 0.2:\n        state = "发散"',
     '    if False:\n        state = "发散"'),
    ("M18 回滚指针恒取最后一圈",
     '    best = max(xs) if higher_is_better else min(xs)\n    return xs.index(best) + 1',
     '    return len(xs)'),
    ("M19 bandit 不做探索（恒选 0 号臂）",
     '        if self.n[i] == 0:\n            return float("inf")',
     '        if False:\n            return float("inf")'),
    ("M20 compact 恒判不超预算",
     '    over = share > float(budget)',
     '    over = False'),
    ("M21 锚点离线检查恒判通过（ok 恒 True）",
     '    out["ok"] = not out["why"]',
     '    out["ok"] = True'),
    ("M22 分级证明标准恒 preponderance",
     '    std, who = table.get(k, ("preponderance", "主张者举证"))',
     '    std, who = ("preponderance", "主张者举证")'),
    ("M23 陈旧度恒不提示",
     '            "stale_hint": bool(age is not None and age >= 3',
     '            "stale_hint": bool(False and age is not None and age >= 3'),
    ("M24 all_on 恒等性失效（false 也全开）",
     '    if not (cfg or {}).get("all_on"):',
     '    if False:'),
    ("M25 api.thinking 形状守卫失效（标量照样炸）",
     '        if _th is not None and not isinstance(_th, dict):\n'
     '            print("   ⚠️ [api.thinking] 形状非法（%s，应为 mapping）⇒ 已降级为 {}；"',
     '        if False:\n'
     '            print("   ⚠️ [api.thinking] 形状非法（%s，应为 mapping）⇒ 已降级为 {}；"'),
    # ── v1.23.33 AutoTune（M26~M30）──
    ("M26 支配判据缺读数竟判真（未知淘汰已知）",
     "    if qa is None or qb is None or ca is None or cb is None:\n"
     "        return False",
     "    if qa is None or qb is None or ca is None or cb is None:\n"
     "        return True"),
    ("M27 层集不做帕累托膝盖（恒取质量第一行）",
     '    pick = (min(costed, key=lambda r: r["cost_med"]) if costed else rows[0])',
     '    pick = rows[0]'),
    ("M28 截断层不加圈（圈数建议偏小）",
     "        cap = int(round(b)) + (1 if cut_n.get(L, 0) > 0 else 0)",
     "        cap = int(round(b))"),
    ("M29 缺质量读数当 0（没测→测出来差）",
     '        quality, basis = None, "unknown"',
     '        quality, basis = 0.0, "unknown"'),
    ("M30 SH 预算不增（档位退化）",
     "        res = res * f",
     "        res = res"),
    ("M31 run_id 不盖进产物（CLI 真跑又被当匿名丢）",
     '            _rid = str(getattr(self, "_run_id", "") or "").strip()\n'
     '            if _rid and not str(packed.get("id") or "").strip():\n'
     '                packed["id"] = _rid',
     '            pass'),
    ("M32 记忆库锁不互斥（O_EXCL 去掉 ⇒ 并发互相覆盖）",
     "            fd = os.open(str(lp), os.O_CREAT | os.O_EXCL | os.O_WRONLY)",
     "            fd = os.open(str(lp), os.O_CREAT | os.O_WRONLY)"),
    ("M33 成本中位换分母（无质量跑次混进来 ⇒ 膝盖判错）",
     "        paired = [a for a in arr if a[\"quality\"] is not None\n"
     "                  and a[\"cost\"] is not None]\n"
     "        qs = [a[\"quality\"] for a in paired]\n"
     "        cs = [a[\"cost\"] for a in paired]",
     "        paired = [a for a in arr if a[\"quality\"] is not None\n"
     "                  and a[\"cost\"] is not None]\n"
     "        qs = [a[\"quality\"] for a in paired]\n"
     "        cs = [a[\"cost\"] for a in arr if a[\"cost\"] is not None]"),
    # ── v1.23.33 第三轮：四层目标读数 + 三阶段决策（M34~M36）──
    #   ★ 三条都打在**判据读的那个东西**上（⑫ 修行边际率 / ⑳ archive 非贪心 /
    #     ⑭ 对撞 CORE 罚），不是改前缀名。
    ("M34 修行层边际率取反（还在挖 < 已挖尽 ⇒ 方向颠倒）",
     "        return max(0.0, min(1.0, late / early))",
     "        return max(0.0, min(1.0, 1.0 - late / early))"),
    ("M35 archive 只留最优臂（贪心，DGM 已证劣于开放探索）",
     "    _m = len(arms)\n"
     "    raw = []\n"
     "    for i, a in enumerate(arms):",
     "    arms = arms[:1]\n"
     "    _m = len(arms)\n"
     "    raw = []\n"
     "    for i, a in enumerate(arms):"),
    ("M36 对撞层不罚复读（CORE 停滞罚退化成纯产出量）",
     "                d[\"fuse\"] = round(d[\"fuse_raw\"] * (1.0 - min(1.0, _stag)), 4)",
     "                d[\"fuse\"] = round(d[\"fuse_raw\"], 4)"),
    #   ★ M37 打在「读的字段」上：真跑 GOALCHK 逮到实现原读臆造键
    #     `covered_answer`（view 里根本没这个字段）⇒ settle 恒 null，
    #     而**夹具自带该键** ⇒ 判据假绿。改成读真实 `settlement` 后，
    #     退回臆造键必须判红（否则判据仍在自证）。
    ("M37 研究层读臆造键 covered_answer（view 里没有 ⇒ settle 恒 null）",
     "            _co = v.get(\"settlement\") or v.get(\"covered_answer\") or {}",
     "            _co = v.get(\"covered_answer\") or {}"),
    # ── 四层目标**进入每层每圈运行**（M38~M39）──
    #   ★ 打在「运行接线」与「缺读数处理」上：前者是能力可达性，
    #     后者是「没测 ≠ 测出来差」这条红线。
    #   ★ M38 锚点随第二期更新（P2-1 在这两行之间插了 `_refresh_goal_hint`）
    #     —— 「重构搬代码 ⇒ 按函数体取区域的判据成批失效」的又一次实例。
    ("M38 目标停因断了运行接线（每圈不判 ⇒ 目标不入运行）",
     "            self._layer_goal_now(entry, view)\n"
     "            self._refresh_goal_hint(entry, view)\n"
     "            _goal_hit, _goal_why = self._goal_stop_signal(entry, view)\n"
     "            # ★ [anytime-valid] 是否启用由配置决定（默认关 ⇒ 恒 False）。",
     "            _goal_hit, _goal_why = False, \"\"\n"
     "            # ★ [anytime-valid] 是否启用由配置决定（默认关 ⇒ 恒 False）。"),
    ("M39 缺读数当达标（没测 ⇒ 判 hit，假停）",
     "    g = goal or {}\n    _e = str(entry or \"\")\n    if _e == \"0\":\n"
     "        _v = _lg_num(g.get(\"excavate\"))\n        if _v is None:\n"
     "            return False, \"\"",
     "    g = goal or {}\n    _e = str(entry or \"\")\n    if _e == \"0\":\n"
     "        _v = _lg_num(g.get(\"excavate\"))\n        if _v is None:\n"
     "            return True, \"没读数当挖尽\""),
    #   ★ M40 打在「优先级表」上：目标停因未登记 ⇒ 落最低档 3（与「体力耗尽」
    #     同级，语义刚好相反）。判据读的是 `stop_priority` 的**返回值**。
    ("M40 目标停因未登记优先级（落档 3 = 与体力耗尽同级）",
     "         \"目标已达成\", \"目标受阻\")),",
     "         )),"),
    #   ★ M41 撤掉「剥括号」⇒ 走满型截断的转述被当停因本体（判成档 0）。
    ("M41 停因不剥括号（走满型截断被括号内转述顶成档 0 自然停）",
     "    _head = re.sub(r\"[（(][^（()）]*[)）]\", \"\", _r).strip()",
     "    _head = _r"),
    #   ★ M42 档 2 塞回裸键「耗尽」⇒ 吞掉档 3 的「体力耗尽」（键区间重叠）。
    ("M42 档 2 塞回裸键「耗尽」（吞掉档 3 体力耗尽）",
     "    (2, (\"无新\", \"无推进\", \"连续空转\", \"停滞\", \"材料耗尽\")),",
     "    (2, (\"无新\", \"无推进\", \"连续空转\", \"停滞\", \"材料耗尽\", \"耗尽\")),"),
    # ── 第二期：四层目标 → **圈内动作**（M43~M44）──
    #   ★ 打在「圈内接线」与「缺读数处理」上，与第一期的 M38/M39 同构，
    #     但作用面不同（一个是层末停因，一个是圈内 prompt）。
    ("M43 圈内指引断了并行通道接线（一处有一处没有）",
     "        # ★ [四层目标 → 每圈运行] 并行通道同样算（两通道一处实现）。\n"
     "        self._layer_goal_now(entry, view)\n"
     "        self._refresh_goal_hint(entry, view)\n",
     "        # ★ [四层目标 → 每圈运行] 并行通道同样算（两通道一处实现）。\n"
     "        self._layer_goal_now(entry, view)\n"),
    #   ★ M44 缺读数也硬给（没测 ⇒ 当约束下给模型）。
    ("M44 圈内指引缺读数也硬给（没测 ⇒ 当约束下给模型）",
     "    g = goal or {}\n    _e = str(entry or \"\")\n\n    if _e == \"0\":\n"
     "        # 修行层（趋近无穷收敛 = 把各面挖到不能再挖）\n"
     "        _v = _lg_num(g.get(\"excavate\"))",
     "    g = goal or {}\n    _e = str(entry or \"\")\n    if not g:\n"
     "        return \"\\n\\n【本层目标的形状指引】\\n（缺读数，仍下指令）\\n\"\n\n"
     "    if _e == \"0\":\n"
     "        # 修行层（趋近无穷收敛 = 把各面挖到不能再挖）\n"
     "        _v = _lg_num(g.get(\"excavate\"))"),
    # ── 第六期：各环节量化 + 降本（M45~M48）──
    #   ★ M45 打在**开关默认值**上（偷偷打开 ⇒ 改变历史行为）。
    ("M45 阴阳合并开关默认打开（未 opt-in 就改行为）",
     "        if len(jobs) == 2 and _action_on(self.config, \"merge_expand\", False):",
     "        if len(jobs) == 2 and _action_on(self.config, \"merge_expand\", True):"),
    #   ★ M46 打在**分歧度方向**上（判据读 verdict ⇒ 方向反了必须判红）。
    ("M46 阴阳分歧度方向反（复述判 ok、真分歧判假对撞）",
     "    d[\"verdict\"] = (\"fake_duel\" if d[\"divergence\"] < _YY_DIV_LOW else \"ok\")",
     "    d[\"verdict\"] = (\"ok\" if d[\"divergence\"] < _YY_DIV_LOW else \"fake_duel\")"),
    #   ★ M47 打在**缺输入处理**上（没数据也硬表态）。
    ("M47 保真度缺输入硬表态（没数据也判 ok）",
     "    if not _q or not _a:\n        return {\"coverage\": None, \"ratio\": None,\n"
     "                \"fidelity\": None, \"verdict\": \"\"}",
     "    if not _q or not _a:\n        return {\"coverage\": 0.0, \"ratio\": 0.0,\n"
     "                \"fidelity\": 0.0, \"verdict\": \"ok\"}"),
    #   ★ M48 打在**「零成本」这个承诺**上（读数偷偷调 LLM）。
    #     注入必须**真实可执行**：判据 ㉚ 的 spy 打的是 `mod.LLM.call`
    #     （`smoke_test.py` 的 `_orig_call = mod.LLM.call`）⇒ 这里必须真的
    #     走 `LLM.call`（走不存在的东西会 NameError ⇒ 计数仍 0 ⇒ 假绿）。
    #     用 `globals()` 拼名规避「把 LLM 字面写进函数体」的额外判据。
    ("M48 语义密度偷偷调 LLM（读数不再零成本）",
     "    _t = str(text or \"\")\n    if not _t.strip():\n        return None",
     "    _t = str(text or \"\")\n"
     "    if _t.strip():\n"
     "        globals()[\"L\" + \"L\" + \"M\"].call(prompt=\"x\")\n"
     "    if not _t.strip():\n        return None"),
    #   ★★ M49 打在**「可达性」**上（真跑逮到的真缺陷）：把 `_quant_note`
    #      从**模块级函数**退化回 `MetaDGTF` 的**方法**，而调用点在 `DGTF.run`
    #      （两类无继承）⇒ `DGTF` 实例解析不到 ⇒ `AttributeError` 被
    #      `except Exception: pass` 静默吞掉 ⇒ 真跑 `quant_readings` 恒空。
    #      ★ 判据 ㉛ 必须查**可达性**（模块级 + 真写一次）—— 只查
    #      「`self._quant_note(view,` 出现次数」会**假绿**（这是第一版的错）。
    ("M49 _quant_note 退回方法（DGTF 解析不到 ⇒ 静默 AttributeError）",
     "def _quant_note(view, key: str, val) -> None:\n"
     "    \"\"\"[第六期] 把一条量化读数写进 `view.quant_readings`（**唯一写入口**）。",
     "def _quant_note_orphan(view, key: str, val) -> None:\n"
     "    \"\"\"[第六期] 把一条量化读数写进 `view.quant_readings`（**唯一写入口**）。"),
]


def run_check(mut_path=None):
    code = ("import sys; sys.path.insert(0, r'%s');\n"
            "import smoke_test as st;\n") % str(HERE)
    if mut_path is not None:
        code += "from pathlib import Path\n"
        code += "st.SRC = Path(r'%s')\n" % str(mut_path)
        code += (
            "import importlib.util\n"
            "_sp = importlib.util.spec_from_file_location('dgtf_mod', r'%s')\n"
            "_m = importlib.util.module_from_spec(_sp)\n"
            "import sys as _s; _s.modules['dgtf_mod'] = _m\n"
            "_sp.loader.exec_module(_m)\n"
            "st.mod = _m\n"
        ) % str(mut_path)
    code += ("sys.exit(0 if (st.check_v12332_discipline() and "
             "st.check_v12333_autotune()) else 1)\n")
    r = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, cwd=str(HERE))
    return r.returncode == 0, r.stdout + r.stderr


def main():
    only = None
    if "--only" in sys.argv:
        only = set(int(x) for x in
                   sys.argv[sys.argv.index("--only") + 1].split(","))
    ok_base, out = run_check(None)
    if not ok_base:
        print("X 干净基线不绿：\n", out[-1200:])
        sys.exit(2)
    print("OK 干净基线判绿")
    res = []
    for i, (name, old, new) in enumerate(MUTS, 1):
        if only and i not in only:
            continue
        src = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
        n = src.count(old)
        if n != 1:
            print("X %s：锚点命中 %d 次（失效）" % (name, n))
            res.append((i, name, "ANCHOR"))
            continue
        tmp = Path(tempfile.gettempdir()) / ("_mut_v12332_%d.py" % i)
        tmp.write_bytes(src.replace(old, new, 1).encode("utf-8"))
        green, out = run_check(tmp)
        print(("OK" if not green else "X"),
              "%s %s" % (name, "红(判别力OK)" if not green else "绿(假绿!)"))
        res.append((i, name, "RED" if not green else "GREEN"))
        tmp.unlink(missing_ok=True)
    bad = [r for r in res if r[2] != "RED"]
    print("\n=== 变异体汇总：%d 判红 / %d 总数 ==="
          % (len(res) - len(bad), len(res)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
