# -*- coding: utf-8 -*-
"""v1.23.16 补丁：自然停治本三条 + 删除成本档维度。

★ 单一真相源：只操作一个行表 `lines`，全部编辑（含整块替换）都在它上面做，
  最后一次 join、转一次 CRLF、写一次盘。
★ 定位方式：**行号（取自 v1.23.15）+ 首尾特征断言**，按行号**降序**执行
  （前面的编辑不会挪动后面待编辑的行）。行号断言用的是「首行/末行的前缀」，
  不用整行字面 —— 长行会被截断，拿截断串当锚点必然失配。
"""
import ast
import re
from pathlib import Path

HERE = Path(".").resolve()
SRC = HERE / "元DGTF-V1.23.16.py"
BLOCKS = HERE / "_v12316_block_stop.py"

_raw = SRC.read_bytes()
if _raw.count(b"\r\n") == _raw.count(b"\n") and _raw.count(b"\r\r\n") == 0:
    lines = _raw.decode("utf-8").replace("\r\n", "\n").split("\n")
else:
    raise SystemExit("源文件不是纯 CRLF")
if not lines or lines[-1] == "":
    lines = lines[:-1]
N0 = len(lines)

# ── 读块 ─────────────────────────────────────────────────────
_bt = BLOCKS.read_text(encoding="utf-8").replace("\r\n", "\n")


def block(name):
    i = _bt.index("# @@%s@@" % name)
    j = _bt.index("# @@END@@", i)
    return _bt[i:j].split("\n", 1)[1].rstrip("\n")


B_SAT = block("BLOCK_SAT_OVERRIDE")
B_SER = block("BLOCK_SAT_SERIAL")
B_B = block("BLOCK_SAT_B")

# ── 编辑原语 ─────────────────────────────────────────────────
LOG = []


def cut(a, b, new, what, head=None, tail=None):
    """替换 lines[a-1:b]（1-based，闭区间）。new 为 list[str]（空 = 删除）。"""
    assert 1 <= a <= b <= len(lines), "%s：行号越界 %d-%d" % (what, a, b)
    seg = lines[a - 1:b]
    if head is not None:
        assert seg[0].startswith(head), \
            "%s：首行不符\n  期望前缀 %r\n  实得 %r" % (what, head, seg[0][:90])
    if tail is not None:
        assert seg[-1].startswith(tail), \
            "%s：末行不符\n  期望前缀 %r\n  实得 %r" % (what, tail, seg[-1][:90])
    lines[a - 1:b] = list(new)
    LOG.append("%-44s %d-%d → %d 行" % (what, a, b, len(new)))


EDITS = [
    # ---------- ① 十二项 → 十一项 / CLI ----------
    (18269, 18269, ['        "route": args.route,',
                    '        "mode": args.parallel, "rounds": args.rounds,'],
     "--profile 从 explicit 删", '        "route": args.route', None),
    (18203, 18206, [], "argparse --profile 删",
     '    parser.add_argument("--profile"', '                             "（不给则用配置 cost_profile，默认 balanced）")'),
    # ---------- ② 配置键 ----------
    (17675, 17675, [], "DEFAULT_CONFIG round_window 删",
     '        "round_window": 2,', None),
    (17523, 17531, [], "DEFAULT_CONFIG cost_profile 段删",
     "    # ============================================================",
     '    "cost_profile": "balanced",'),
    # ---------- ③ 产物渲染 ----------
    (16716, 16723, [], "save_result 成本档位行删",
     '            _cp = result.get("cost_profile")', '                f.write(f"**成本档位**：{_cp_disp}\\n\\n")'),
    (13905, 13908, ['    out.append(',
                    '        f"**这份产物以什么方式显化**：取向={_o_disp}，并行={_pm}。\\n\\n")'],
     "显化行去掉成本档", '    _cp = res.get("cost_profile")',
     '        f"成本档={_cp}。\\n\\n")'),
    (13944, 13950, [], "落地层成本档行删",
     '    _cp_disp = {', '               f"这是 **token 层的取舍**，不改判据。\\n")'),
    # ---------- ④ auto 调度器 ----------
    (16594, 16596, [], "auto_plan prof 归一化删",
     '    prof = str((cfg or {}).get("cost_profile", "balanced")).strip().lower()',
     '        prof = "balanced"'),
    (16603, 16604, ['        extra={"_orientation_reason": o.get("reason", "")})'],
     "extra 去掉 cost_profile", '        extra={"_orientation_reason"', None),
    (16200, 16203, [], "_apply_auto_dispatch 成本档段删",
     '    if _is_mine("cost_profile"):', None),
    (16117, 16117, [], "_AUTO_PICKERS 删 cost_profile",
     '    "cost_profile": _auto_pick_cost_profile,', None),
    (16092, 16096, ['    _q = {"per_run_total": 30, "per_stage_total": 8, "per_stage_round": 2}'],
     "联网降级配额去掉档位", '    _prof = _auto_pick_cost_profile(feat, hist, cfg)[0]',
     '        _why += "；economy 档配额减半"'),
    (15919, 15957, [], "_auto_pick_cost_profile 删", "def _auto_pick_cost_profile(feat, hist, cfg):", None),
    (15474, 15475, ['        if k in ("mode", "orientation", "landing",',
                    '                 "decidability"):'],
     "_normalize_explicit 去掉档位", '        if k in ("cost_profile", "mode", "orientation", "landing",', None),
    (15404, 15404, [], "_AUTO_CONFIG_PATHS 删 cost_profile",
     '    "cost_profile": [("cost_profile",)],', None),
    (15379, 15380, [], "_AUTO_PROFILES_ORDER 删（死常量）",
     '_AUTO_PROFILES_ORDER = ("quality", "balanced", "economy")', None),
    (15359, 15359, [], "_AUTO_ITEM_LABEL 删 cost_profile",
     '    "cost_profile": "成本档",', None),
    (15353, 15355, ['_AUTO_ITEM_ORDER = ("route", "mode", "rounds", "orientation",',
                    '                    "web", "thinking", "effort", "stop", "web_downgrade",',
                    '                    "decidability", "landing")'],
     "_AUTO_ITEM_ORDER → 十一项", '_AUTO_ITEM_ORDER = ("route", "cost_profile", "mode"', None),
    (15258, 15258, [], "_assemble_plan schema 删 cost_profile",
     '        "cost_profile": prof,', None),
    (15251, 15253, [], "_assemble_plan prof 归一化删",
     '    prof = str((cfg or {}).get("cost_profile", "balanced")).strip().lower()', None),
    (15244, 15246, ['    ★ 技术债（v1.21.71 F8 起挂账）：单调用路径返回 `{mode, rounds, reason,',
                    '      orientation, confidence}`，两段式路径返回 `{route, mode, rounds,',
                    '      max_calls, orientation, reason, confidence, _auto}` ——'],
     "_assemble_plan docstring schema 说明", '    ★ 技术债（v1.21.71 F8 起挂账）', None),
    (14357, 14366, [], "_auto_profile 删",
     "def _auto_profile(question: str) -> str:", '    return "economy" if not _has_decision_context(question) else "balanced"'),
    # ---------- ⑤ 五个消费点 ----------
    (11786, 11807, B_B.split("\n"), "B 通道 sat 接线（四层同等）",
     '        sat_enabled = bool(sp.get("structure_saturation_enabled", True))',
     '                self.vp(f"      ↳ 有新维度，idle_new_amp 重置为 0")'),
    (11762, 11763, [], "B 通道 win_amps.append 删", '        state["win_amps"].append(new_amps)', None),
    (11736, 11739, ['        recent_amps = list(snap_amps)',
                    '        recent_threads = list(snap_threads)'],
     "B 通道参照集改池内全量", '        recent_amps = [x for lst in state["win_amps"][-r_window:]', None),
    (11724, 11724, [], "B 通道 r_window 删", '        r_window = state["r_window"]', None),
    (11300, 11301, [], "B 通道 state win_* 删", '            "win_amps": [],', None),
    (11281, 11281, [], "B 通道 state r_window 删", '            "r_window": max(1, int(sp.get("round_window", 2))),', None),
    (10337, 10358, B_SER.split("\n"), "serial sat 接线（四层同等）",
     '            sat_enabled = bool(sp.get("structure_saturation_enabled", True))',
     '                    self.vp(f"      ↳ 有新维度，idle_new_amp 重置为 0")'),
    (10319, 10320, [], "serial win_amps.append 删", '            win_amps.append(new_amps)', None),
    (10294, 10296, ['            recent_amps = list(snap_amps)',
                    '            recent_threads = list(snap_threads)'],
     "serial 参照集改池内全量", '            recent_amps = [x for lst in win_amps[-r_window:]', None),
    (10075, 10076, [], "serial win_* 定义删", '        win_amps: List[List[str]] = []', None),
    (10065, 10065, [], "serial r_window 删", '        r_window = max(1, int(sp.get("round_window", 2)))', None),
    (8203, 8212, ['    def _lazy_every_n(self, n: int) -> int:',
                  '        """低频项（结构饱和度 / 池重估）的间隔。',
                  '',
                  '        ★ 曾经按成本档「拉大一档」（balanced / economy ⇒ n+1）省调用。',
                  '          档位维度删除后不再惰性化 —— 那个做法还有个反效果：间隔被',
                  '          拉到 `structure_saturation_every_n + 1` 之后，**上限低于它的',
                  '          层永远跑不到这条判据**（实测某组层上限 ≤3、间隔 4 ⇒ 一次都',
                  '          不触发）。停止判据的检查频率不该由省钱档位决定。',
                  '        """',
                  '        return n'],
     "_lazy_every_n 去惰性化", '    def _lazy_every_n(self, n: int) -> int:',
     '        return n + 1 if _plan["lazy_lowfreq"] else n'),
    (7998, 8005, [], "shape 缩放 + _cost_profile 删",
     '        _plan = _profile_plan(config)', '                2, int(self._mcfg.get("shape_items", 6) * _scale))'),
    (5463, 5470, ['        cand_text = "\\n".join(',
                  '            f"- [{c.attribute}×{c.position}] {c.desc}" for c in normal)'],
     "候选截断删", '        _plan = _profile_plan(self.config)',
     '            f"不影响对撞）"'),
    (4784, 4789, [], "阴阳合并分支删",
     '        _plan = _profile_plan(self.config)', '            self.vp("   ⚠️ 合并展开失败，回落到阴阳分开")'),
    (4548, 4550, ['        _role_now = (inp.round_role or "").strip()',
                  '        # 档位维度已删除 ⇒ 探针不再按角色跳过（回到「不省」）。',
                  '        _skip_probe = False'],
     "探针跳过删", '        _plan = _profile_plan(self.config)',
     '        _skip_probe = (_role_now in _plan["probe_skip_roles"])'),
    (755, 794, B_SAT.split("\n") + ["", ""],
     "定义区 → _sat_override",
     '# ============================================================',
     '    }'),
    # ---------- ⑥ sat prompt 措辞 ----------
    (9085, 9085, ['            f"【池内已有 &（{len(recent_amps)} 条）】\\n{recent_text}"'],
     "sat prompt 措辞：近几圈→池内",
     '            f"【近几圈已有 &（{len(recent_amps)} 条）】', None),
    # ---------- ⑦ 补漏：第二处候选截断 / 日志文案 / 注释 ----------
    (7527, 7529, ['        _cands = view.candidates'],
     "_self_check 候选截断删", '        _plan = _profile_plan(self.config)',
     '        _cands = view.candidates if not _lim else view.candidates[:_lim]'),
    (7534, 7536, [], "_self_check 截断提示删",
     '        if _lim and len(view.candidates) > _lim:', None),
    (10363, 10363, ['                        f"（近似不算，比对池内全部；"'],
     "日志文案去 r_window",
     '                        f"（近似不算，比对近 {r_window} 圈；"', None),
    (15136, 15139, ['# ★ 为什么要放在构造前：规划里的 route / rounds 决定层与圈数，',
                    '#   而 `MetaDGTF.__init__` 会按它们建池与状态。构造之后再想改，',
                    '#   改不动。所以完整规划必须在**拿到 MetaDGTF 之前**完成。'],
     "自动规划注释改述", '# ★ 为什么要放在构造前：', None),
    (15141, 15142, ['# 四个维度：route（走哪几层）/ mode（怎么并行）/ rounds（每层几圈）',
                    '#           / max_calls（总调用预算）'],
     "五维度→四维度", '# 五个维度：route', None),
    (15146, 15146, [], "注释里的 cfg cost_profile 删",
     '#', None),
    (15160, 15160, ['#           所以上限放回 6。'],
     "注释去 cost_profile", '#', None),
    (16187, 16187, ['      `--web off` / `--thinking on` / `--effort max`'],
     "docstring 去 --profile", '      `--web off` / `--profile quality`', None),
]

# ★ 降序执行：从文件尾部往前改，前面的行号不会被挪动
for a, b, new, what, head, tail in sorted(EDITS, key=lambda x: -x[0]):
    cut(a, b, new, what, head, tail)

out = "\n".join(lines) + "\n"
ast.parse(out)
print("\n".join(LOG))
print("\n行数：%d → %d（%+d）" % (N0, out.count("\n"), out.count("\n") - N0))

# ── 结构性自检（不只看语法，看**符号与行为**）──────────────────
CHECKS = [
    ("_sat_override 已定义", "def _sat_override(" in out, True),
    ("_COST_PROFILES 已消失", "_COST_PROFILES" in out, False),
    ("_profile_plan 已消失", "def _profile_plan(" in out, False),
    ("_profile_plan 调用已消失", "_profile_plan(" in out, False),
    ("_auto_pick_cost_profile 已消失", "_auto_pick_cost_profile" in out, False),
    ("_auto_profile 已消失", "_auto_profile(" in out, False),
    ("_PROBE_SKIP_ROLES 已消失", "_PROBE_SKIP_ROLES" in out, False),
    ("_AUTO_PROFILES_ORDER 已消失", "_AUTO_PROFILES_ORDER" in out, False),
    ("--profile 已消失", "--profile" in out, False),
    ("DEFAULT_CONFIG 无 cost_profile", '"cost_profile": "balanced"' in out, False),
    ("round_window 已消失", "round_window" in out, False),
    ("win_amps 已消失", "win_amps" in out, False),
    ("r_window 已消失", "r_window" in out, False),
    ("sat 接线走过 _sat_override", out.count("_sat_override("), 3),
    ("参照集改池内全量", out.count("recent_amps = list(snap_amps)"), 2),
    ("_lazy_every_n 恒等", "        return n + 1 if _plan" in out, False),
    ("_AUTO_ITEM_ORDER 十一项", '_AUTO_ITEM_ORDER = ("route", "mode", "rounds", "orientation",' in out, True),
    ("历史兼容侧保留 profile 读取", '"profile": str(d.get("cost_profile") or "")' in out, True),
]
bad = 0
for name, got, want in CHECKS:
    ok = (got == want)
    bad += 0 if ok else 1
    print("  %s %s（实得 %r，期望 %r）" % ("✓" if ok else "✗", name, got, want))
assert bad == 0, "结构性自检 %d 项不过" % bad

_new = out.replace("\n", "\r\n").encode("utf-8")
assert _new.count(b"\r\r\n") == 0 and _new.count(b"\r\n") == _new.count(b"\n")
SRC.write_bytes(_new)
print("\n已写 %s（CRLF 校验通过）" % SRC.name)
