#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.32 变异体：给 `check_v12332_discipline` 背书（M1~M9）。"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.45.py"

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
    #   ★ M50 打在**候选产出率的方向**上（判据读 verdict ⇒ 方向反了必须判红）。
    ("M50 候选产出率方向反（整批复述判 ok、全新生判 collapsed）",
     "    _v = \"collapsed\" if _ratio < 0.34 else \"ok\"",
     "    _v = \"ok\" if _ratio < 0.34 else \"collapsed\""),
    #   ★ M51 打在**缺输入处理**上（首次跑被当成「真没长」⇒ 假告警）。
    ("M51 候选产出率缺输入硬给（首次跑也被判 collapsed）",
     "    if not _c or not _p:\n"
     "        return {\"n\": len(_c), \"n_new\": None, \"new_ratio\": None,\n"
     "                \"max_sim\": None, \"collapsed\": None, \"verdict\": \"\"}",
     "    if not _c or not _p:\n"
     "        return {\"n\": len(_c), \"n_new\": 0, \"new_ratio\": 0.0,\n"
     "                \"max_sim\": 0.0, \"collapsed\": True, \"verdict\": \"collapsed\"}"),
    #   ★ M52 打在**取向规则的方向**上（判据两向测 ⇒ 方向反了必须判红）。
    ("M52 取向规则方向反（有决策语汇判 boundary、无则判 decision）",
     "    if _has_decision_context(_q):\n"
     "        return {\"orientation\": \"decision\",",
     "    if not _has_decision_context(_q):\n"
     "        return {\"orientation\": \"decision\","),
    #   ★ M53 打在**「规则命中不花调用」的接线**上（判据用 spy 计 0 次 ⇒
    #     退回 LLM 版即必须判红）。这是「有接线 ≠ 这跑走得到」的成本侧形态。
    ("M53 规则命中又偷调 LLM（退回 plan_orientation 补取向）",
     "                _or = orientation_rule(q)\n"
     "                _ori = str((_or or {}).get(\"orientation\", \"\") or \"\")\n"
     "                if not _ori:\n"
     "                    raise ValueError(\"取向规则未定\")",
     "                _or = {\"orientation\": \"\"}\n"
     "                _ori = str((_or or {}).get(\"orientation\", \"\") or \"\")\n"
     "                if not _ori:\n"
     "                    raise ValueError(\"取向规则未定\")"),
    #   ★ M54 打在**候选历史的载体**上（判据 ㉞ 跑真实入口断言落盘 ⇒
    #     挂回每圈重建的 view 必然「永不落盘」，必须判红）。
    ("M54 候选历史挂回每圈重建的 view（时序颠倒 ⇒ 永不落盘）",
     "        _cypool = getattr(inp, \"pool\", None)\n"
     "        try:\n"
     "            _cy = candidate_yield(\n"
     "                [getattr(c, \"desc\", \"\") for c in candidates],\n"
     "                getattr(_cypool, \"_prev_cand_descs\", None))",
     "        _cypool = None\n"
     "        try:\n"
     "            _cy = candidate_yield(\n"
     "                [getattr(c, \"desc\", \"\") for c in candidates],\n"
     "                getattr(view, \"_prev_cand_descs\", None))"),
    #   ★ M55 打在**可读性出口**上（判据 ㉟ 捕获 `_render` 正文 ⇒ 段没了必判红）。
    ("M55 量化读数不进产物正文（只在附录 JSON ⇒ 人类与工作台都看不见）",
     "        _qr = getattr(view, \"quant_readings\", None) or {}\n"
     "        if _qr:",
     "        _qr = getattr(view, \"quant_readings\", None) or {}\n"
     "        if False:"),
    #   ★ M56 打在**新规范接线**上（判据 ①b 数使用处 ⇒ 少一处必判红）。
    #     ★ 锚点必须**唯一**：六处视角共用的 `+ VOICE` 不能当靶，
    #       故用 `_yin_prompt` 的独特上下文（「从锚点里看出去」那一句）。
    ("M56 阴视角漏接 VOICE（新规范只接一半）",
     "            \"从锚点里看出去，找出还没显形的部分。\\n\"\n"
     "            + EXPLORE_FORMAT\n"
     "            + VOICE\n",
     "            \"从锚点里看出去，找出还没显形的部分。\\n\"\n"
     "            + EXPLORE_FORMAT\n"),
    #   ★ M57 打在**第四面墙的禁止清单**上（判据 ④ 查三个禁止词 ⇒ 删必判红）。
    ("M57 EVIDENCE 丢掉管道级禁止清单（第四面墙失效）",
     "- ★ 不要说\"资料里说\"\"检索显示\"\"上下文提到\"\"根据提供的信息\"这类话 ——\n",
     "- 想怎么说就怎么说。\n"),
    #   ★ M58 打在**输出格式契约**上（判据 ② 是「不许变」⇒ 改了必判红）。
    ("M58 EXPLORE_FORMAT 改掉格式契约（下游解析会坏）",
     "    \"每行格式：- [kind] 描述（20-80字；说清一条算一条，\"\n",
     "    \"每行随便写点，无所谓。\"\n"),
    #   ★ M59 打在**view 输出结构**上（判据在 ㉟ 段跑真实入口 ⇒ 去了必判红）。
    ("M59 _render 去掉「本层速览」（view 输出结构没生效）",
     "            _render_layer_glance(view),\n",
     ""),
    #   ★ M60 打在**读数的输出通道**上（判据捕获 logging ⇒ 走 vp 就看不到，
    #     而 vp 受 verbose 控制 ⇒ 会「静默吞掉读数」——这正是第一版的真错）。
    ("M60 读数行改走 vp（verbose=False 时被静默吞掉）",
     "            logger.info(_readings_line(entry, view))",
     "            self.vp(_readings_line(entry, view))"),
    #   ★ M61 打在**产物出口**上（判据查 `packed["readings_table"]` ⇒ 不写必判红）。
    ("M61 读数总表不进产物（产物侧拿不到结构化读数）",
     "                packed[\"readings_table\"] = _readings_table(_rt_views, as_md=True)",
     "                packed[\"readings_table\"] = \"\""),
    #   ★ M62 打在**总闸**上（判据查「总闸关不增强」⇒ 去掉判断必判红）。
    ("M62 `_web_augment` 不判总闸（关了也注入 ⇒ 零行为差被破坏）",
     "        _searcher = _llm_ctx_get(\"web_searcher\")\n"
     "        if not callable(_searcher):\n"
     "            return None                       # 没接线（如独立调用 LLM）⇒ 不增强",
     "        _searcher = _llm_ctx_get(\"web_searcher\")\n"
     "        if _searcher is None:\n"
     "            _searcher = lambda *a, **kw: [{\"claim\": \"M62\"}]"),
    #   ★ M63 打在**控制面的必留痕**上（「缺 why 就拒」是可追溯性的本体 ⇒
    #     去掉它，任何写入都不需要理由 ⇒ 必判红）。
    ("M63 控制面不再要求 why（可追溯性被削弱）",
     "        if not str(why or \"\").strip():",
     "        if False:"),
    #   ★ M64 打在**四层都可注入**上（用户口径 ⇒ 若有人把修行层豁免加回来必判红）。
    ("M64 把修行层硬豁免加回来（破「所有层都注入」）",
     "        _st = str(stage or _infer_stage_from_stack() or \"\")\n"
     "        if not _st:\n"
     "            return None",
     "        if str(_llm_ctx_get(\"entry\", \"\")) == \"0\":\n"
     "            return None\n"
     "        _st = str(stage or _infer_stage_from_stack() or \"\")\n"
     "        if not _st:\n"
     "            return None"),
    #   ★ M65 打在**心跳的触发条件**上（判据 ③ 查「读数正常不该放宽」⇒
    #     去掉 verdict 判断 ⇒ 正常也放宽 ⇒ 必判红）。
    ("M65 心跳不看读数就放宽（默认零行为差被破坏）",
     "        if str(_q.get(\"候选\") or \"\") == \"collapsed\":",
     "        if True:"),
    #   ★ M66 打在**控制面的必留痕**上（心跳不带 why ⇒ 控制面应拒 ⇒
    #     放宽不生效 ⇒ 判据 ① 判红）。
    ("M66 心跳写入不带 why（控制面应当拒 ⇒ 放宽不生效）",
     "                    why=\"心跳：本层候选产出率 collapsed（复述多）⇒ \"\n"
     "                        \"放宽该环节联网，让它能问外面\",",
     "                    why=\"\","),
    #   ★ M67 打在**主文件**的豁免表上（两向对账的反向：「登记了必须仍在
    #     生成」）。原锚点是「豁免表丢一项」，但 v1.23.36 已把豁免表**清空**
    #     （三个 key 全部接线）⇒ 原锚点不存在（实测命中 0 次）。
    #     ⇒ 换锚为「塞一个不再生成的 key 进去」：语义等价（都让过期登记
    #     判据判红），且锚点在**主文件**里（变异体机制要求）。
    ("M67 EML 豁免表塞入过期登记（反向对账应判红）",
     "_EML_RECORD_ONLY = {}",
     "_EML_RECORD_ONLY = {\"__never_generated__\": \"判据探针\"}"),
    #   ★ M68 打在**放宽能否落地**上（不同步进 Gate ⇒ 放宽只是内存里的一个数，
    #     检索照旧被拒 ⇒ 判据源码级判红）。
    ("M68 放宽不同步进 Gate（放宽永远不生效）",
     "                gate._relaxed = _relaxed",
     "                gate._relaxed = set()"),
    #   ★ M69 打在**「学了要做」**上（删 `carve_first` 分支 ⇒ 它落回
    #     "无分支且无豁免" ⇒ 判据的两向对账必判红）。
    ("M69 删 carve_first 分支（又变成学而不做）",
     "            elif _key == \"carve_first\":",
     "            elif _key == \"carve_first_DISABLED\":"),
    #   ★ M70 打在**「分支真的改调度量」**上（分支还在，但什么都不做 ⇒
    #     源码级判据仍绿，必须靠**功能性**断言抓 ⇒ 这就是那条断言存在的理由）。
    ("M70 tri_advisory_only 分支空转（分支在、不做事）",
     "                _new_fl = round(min(1.0, (_cur if _cur > 0 else 0.35) * 1.15), 4)",
     "                _new_fl = _cur"),
    #   ★ M71 打在**方向**上（`note_cost_no_gain` 该降圈却写成加圈 ⇒
    #     "花多赚少反而多跑" ⇒ 判据必判红）。
    ("M71 note_cost_no_gain 方向反了（该降圈却加圈）",
     "                    _new = max(1, _old - 1)\n"
     "                    if _new == _old:\n"
     "                        continue",
     "                    _new = max(1, _old + 1)"),
    #   ★ M72 打在**真跑逮到的那处**上：合并路径去掉「已合并」标记
    #     ⇒ 判据（查 `self._quant_pending_yy = {` 与 `"merged": True` 同在）必判红。
    #     ★ 用**最小改动**（只删一行）而不是整块替换 ——
    #     整块替换会因缩进对不上而产生**语法错**，那样子进程直接崩、
    #     变异体报的是"崩溃"而不是"判红"，**理由就不对了**。
    ("M72 合并路径不记「已合并」档（真跑逮到的缺陷复现）",
     '                        "merged": True,\n',
     ''),
    #   ★ M73 打在**「所有可配置行为纳入学习」的接线**上：
    #     `action_hint` 写到白名单外 ⇒ 控制面拒 ⇒ 它成了"只记账不生效"
    #     （★ 源码级判据仍绿，只有**功能性**断言能抓）。
    ("M73 action_hint 写到白名单外（新的学了不做）",
     '                        "actions.%s" % _nm, bool(_a.get("value")),',
     '                        "actionsXX.%s" % _nm, bool(_a.get("value")),'),
    #   ★ M74 打在**思考档的同步**上：只写控制面、不写 `llm.thinking_stages`
    #     ⇒ 开关记了但**消费方读不到**（同样只有功能性断言能抓）。
    ("M74 thinking_hint 不同步到 llm.thinking_stages（消费方读不到）",
     '                        if isinstance(_ts, dict):\n'
     '                            _ts[_st] = _val',
     '                        if False:\n'
     '                            _ts[_st] = _val'),
    #   ★ M75 打在**「可运行时调」的根**上：`_action_on` 去掉运行时覆盖
    #     ⇒ 所有 actions.* 又变回"改了也不生效"（判据源码级判红）。
    ("M75 _action_on 去掉运行时覆盖（所有 actions.* 不可运行时调）",
     '    _s = (config or {}).get("_control")',
     '    _s = None'),
    #   ★ M78 打在**圈级心跳的跨圈基线**上：不记基线 ⇒ 触发条件永远为假
    #     （判据的「零增量应放宽」必判红）。
    ("M78 圈级心跳不记基线（触发条件恒假）",
     '            self._tick_prev_n = _n_now',
     '            self._tick_prev_n = _n_now if False else None'),
    #   ★ M79 打在**"有增量不该放宽"**上：去掉增量判断 ⇒ 每圈都放宽
    #     （判据的负对照必判红）。
    ("M79 圈级心跳不看增量（有产出也放宽）",
     '                if _force or _grew <= 0:\n                    _why = (',
     '                if True:\n                    _why = ('),
    #   ★ M80 打在**回喂的消费侧**上：把「按 used_as=record 筛选」去掉 ⇒
    #     池里任何条目都算按需结果（判据的「stage 不匹配不复用」负对照必判红）。
    ("M80 回喂不按 used_as=record 筛选（来源不明也复用）",
     '                    if str((_it or {}).get("used_as") or "") == "record"',
     '                    if True'),
    #   ★ M81 打在**回喂的复用分支**上：把「先查池」整段短路 ⇒ 永远去检索
    #     （判据的「searcher 零调用」必判红 ⇒ 回喂失效）。
    ("M81 回喂短路（永远重新检索，池里有也不用）",
     '        _bf = _llm_ctx_get("backfeed_pool")',
     '        _bf = None'),
    #   ★ M82 打在**放宽表的成员有效性**上：塞一个 `web_search.stages` 里
    #     不存在的环节名 ⇒ 放宽了也不生效（死配置）⇒ 两向对账判据必判红。
    ("M82 放宽表塞入不存在的环节名（死配置）",
     '                       "decompose_koan", "decompose_from_pool")',
     '                       "decompose_koan", "decompose_from_pool",\n'
     '                       "__no_such_stage__")'),
    #   ★ M83 打在**按需四层一致**上：去掉 on_demand 豁免 ⇒ 修行层环节
    #     即使声明了 ===WEB-NEED=== 也会被 stages 未授权挡掉
    #     （= v1.23.38 的老问题；判据「修行层按需仍被拒」必判红）。
    ("M83 按需不豁免逐环节授权（修行层声明也查不到）",
     '        if not on_demand \
',
     '        if True or not on_demand \
'),
    #   ★ M84 打在**成本闸门**上：总闸检查被短路 ⇒ 按需路径在
    #     web_search.enabled=False 时也放行（按需=无上限 ⇒ 成本失控）。
    #   ★ M84 打在**成本闸门**上：总闸检查被短路 ⇒ 按需路径在
    #     web_search.enabled=False 时也放行（按需=无上限 ⇒ 成本失控）。
    #   ★ M84 打在**成本闸门**上：总闸检查被短路 ⇒ 按需路径在
    #     web_search.enabled=False 时也放行（按需=无上限 ⇒ 成本失控）。
    ("M84 按需短路总闸（关了也能查）",
     '        if not bool(self.cfg.get("enabled", False)):\n            return False, "web_search 未启用（默认关）"',
     '        if False:\n            return False, "web_search 未启用（默认关）"'),
    #   ★ M85 打在**stage 兜底**上：不再用 `_infer_stage_from_stack()`
    #     取真实环节名 ⇒ record 的 stage 为空 ⇒ 回喂永远匹配不上
    #     （= v1.23.39 真跑前的状态；判据「stage 兜底失败」必判红）。
    ("M85 回喂 stage 不兜底（记录无名 ⇒ 回喂匹配不上）",
     '        _st = str(stage or "").strip()',
     '        _st = str(stage or "").strip()  # M85 故意不兜底',),
    #   ★ M86 打在**跳过元组**上：`_web_need_report` 不被跳过 ⇒
    #     从它内部调 `_infer_stage_from_stack()` 会把**它自己**当成
    #     环节名 ⇒ 入库 stage = "web_need_report"（判据必判红）。
    ("M86 跳过元组漏本函数（把自己当环节名）",
     '            if _n not in ("call", "_call_long", "_web_augment",\n'
     '                          "_web_need_report", "<module>") \\\n',
     '            if _n not in ("call", "_call_long", "_web_augment",\n'
     '                          "<module>") \\\n'),
    #   ★ M87 打在**强制放宽判据**上：`_force` 被忽略 ⇒ `relax_force=true`
    #     在有增量时不再放宽（开关成了摆设）；判据「force=true 也放宽」必判红。
    ("M87 强制放宽开关被忽略（force 成摆设）",
     '                if _force or _grew <= 0:',
     '                if _grew <= 0:'),
    #   ★ M88 打在**放宽表扩项**上：去掉 `decompose_from_pool` ⇒
    #     用户口径「要扩」被回退；判据「放宽表缺 decompose_*」必判红。
    ("M88 放宽表扩项被回退（少一个 decompose_*）",
     '                       "decompose_koan", "decompose_from_pool")',
     '                       "decompose_koan")'),
    ("M89 目标读数收尾不刷新（crystallize 恒层停止那刻的旧值）",
     '_fresh = layer_goal_readings({str(entry): _vd_f}).get(str(entry)) or {}',
     '_fresh = {}'),
    ("M90 excavate 显示丢方向提示（易被误读成没挖）",
     '_LG_HINT.get(_gk_f, "")',
     '""'),
    ("M91 截断不附近阈读数（不可判离触发多远）",
     'f"  近阈读数：{_near}")',
     'f"（略）")'),
    ("M92 自省未消化不附点名（不知是哪批）",
     'if "自省连续" in _sr4 and "未消化点名" not in _sr4:',
     'if False:'),
    ("M93 shape_of 窗口不生效（退回升全量渲染）",
     '            return (_xs[-_lim:] if (_lim > 0 and len(_xs) > _lim)\n                    else _xs)',
     '            return _xs'),
    ("M94 单标量早停失效（增益恒不命中）",
     '    if _gf <= 0:\n        return False, ""',
     '    if True:\n        return False, ""'),
    ("M95 EML 冷启自适应失效（门槛不降）",
     '            if len(playbook or []) < int(_EML_COLD_LIB):\n                _eff_n = 1',
     '            if False:\n                _eff_n = 1'),
    ("M96 输出内复读率恒 0（盲区又回去了）",
     '    return round(1.0 - len(set(_g)) / float(len(_g)), 4)',
     '    return 0.0'),
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
             "st.check_v12333_autotune() and "
             "st.check_v12334_prompt() and "
             "st.check_v12336_allweb() and "
             "st.check_v12336_readings() and "
             "st.check_v12336_tick() and "
             "st.check_v12336_eml() and "
             "st.check_v12336_webneed() and "
             "st.check_v12337_roundtick() and "
             "st.check_v12340_backfeed_stage() and "
             "st.check_v12340_relax_force() and "
             "st.check_v12341_goal_fresh() and "
             "st.check_v12341_excavate_dir() and "
             "st.check_v12341_attribution() and "
             "st.check_v12342_ctx_shape() and "
             "st.check_v12343_gain_stop() and "
             "st.check_v12344_eml_adaptive() and "
             "st.check_v12345_output_rep() and "
             "st.check_v12339_ondemand() and "
             "st.check_v12338_relax_targets() and "
             "st.check_v12338_backfeed()) else 1)\n")
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
        # ★ 输出**带索引**：`--only N` 用的是索引，名字自带 `Mn` ——
        #   两者不一致时（插入导致偏移）当场可见（本轮栽过两次）。
        print(("OK" if not green else "X"),
              "[%d] %s %s" % (i, name,
                              "红(判别力OK)" if not green else "绿(假绿!)"))
        res.append((i, name, "RED" if not green else "GREEN"))
        tmp.unlink(missing_ok=True)
    bad = [r for r in res if r[2] != "RED"]
    print("\n=== 变异体汇总：%d 判红 / %d 总数 ==="
          % (len(res) - len(bad), len(res)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
