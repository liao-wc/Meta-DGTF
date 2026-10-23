# -*- coding: utf-8 -*-
"""v1.23.16 冒烟注入器：删档位相关旧判据 + 注入新判据。

★ 两道原语并用：
  ① 行号 cut/rline（**降序**执行）—— 处理「要保留半段」的位置；
  ② AST 按**内容特征**删最小语句 —— 处理「散在 8 处、边界靠缩进」的 if 块。
  ② 放在 ① 之后：AST 依赖内容而非行号，不受 ① 的漂移影响。
"""
import ast
import re
from pathlib import Path

HERE = Path(".").resolve()
SMOKE = HERE / "smoke_test.py"
_raw = SMOKE.read_bytes()
assert _raw.count(b"\r\n") == _raw.count(b"\n") and _raw.count(b"\r\r\n") == 0
lines = _raw.decode("utf-8").replace("\r\n", "\n").split("\n")
if lines and lines[-1] == "":
    lines = lines[:-1]
N0 = len(lines)
LOG = []


def cut(a, b, new, what, head=None, tail=None):
    assert 1 <= a <= b <= len(lines), "%s：越界 %d-%d" % (what, a, b)
    seg = lines[a - 1:b]
    if head is not None:
        assert seg[0].startswith(head), "%s：首行不符 %r" % (what, seg[0][:80])
    if tail is not None:
        assert seg[-1].startswith(tail), "%s：末行不符 %r" % (what, seg[-1][:80])
    lines[a - 1:b] = list(new)
    LOG.append("%-40s %d-%d → %d 行" % (what, a, b, len(new)))


NEW_CHECK = '''def check_v12316_stop_therapy():
    """[v1.23.16] 自然停治本三条 + 成本档维度已删除。

    ★ 判据不是「某个字符串不存在」，而是**维度不存在** + **行为变了**：
      ① 档位维度：配置键 / auto 项 / 四个符号 / CLI 参数，四处都消失；
      ② 惰性化：`_lazy_every_n` 恒等（含 0 / 1 / 3 三个输入）；
      ③ sat 落点：`_sat_override` 是纯函数，四层同等生效（含 0 层走 stall）、
         未判 / 判有新维度时**一律不动**（负对照）；
      ④ 停止可达：把 sat 的效果喂给 `_stop_reasons`，元层必须给出理由
         —— 这是「元层能不能自然停」的直接判据（旧实现下它恒为空）；
      ⑤ 比对窗口：参照集是**池内全量**（源码里不再有 `win_amps[-r_window:]`），
         且用引擎自己的判重函数证明「跨 3 圈的重复确实是重复」。
    """
    bad = []
    _src_txt = SRC.read_text(encoding="utf-8")

    # ① 档位维度
    if "cost_profile" in (mod.DEFAULT_CONFIG or {}):
        bad.append("DEFAULT_CONFIG 仍有 cost_profile 键")
    for _sym in ("_COST_PROFILES", "_profile_plan", "_PROBE_SKIP_ROLES",
                 "_auto_pick_cost_profile", "_auto_profile"):
        if hasattr(mod, _sym):
            bad.append("维度残留：%s 仍在" % _sym)
    if "cost_profile" in mod._AUTO_ITEM_ORDER:
        bad.append("auto 项里仍有 cost_profile")
    if len(mod._AUTO_ITEM_ORDER) != 11:
        bad.append("auto 项数应为 11，实得 %d" % len(mod._AUTO_ITEM_ORDER))
    if "--profile" in _src_txt:
        bad.append("CLI 仍有 --profile")

    # ② 惰性化：恒等
    _m = mod.MetaDGTF(build_cfg(False))
    if [_m._lazy_every_n(x) for x in (0, 1, 3)] != [0, 1, 3]:
        bad.append("_lazy_every_n 仍会惰性化：%r"
                   % [_m._lazy_every_n(x) for x in (0, 1, 3)])
    _mm = mod.MetaDGTF(build_cfg(False))
    if int(_mm._mcfg.get("shape_chars", 900)) != 900:
        bad.append("shape_chars 仍被缩放：%r" % _mm._mcfg.get("shape_chars"))
    if int(_mm._mcfg.get("shape_items", 6)) != 6:
        bad.append("shape_items 仍被缩放：%r" % _mm._mcfg.get("shape_items"))
    if 'in _plan["probe_skip_roles"]' in _src_txt:
        bad.append("探针仍按角色跳过")
    if "_cands = view.candidates if not _lim" in _src_txt:
        bad.append("候选仍被截断")

    # ③ sat 落点：四层同等 + 负对照
    _so = getattr(mod, "_sat_override", None)
    if not callable(_so):
        bad.append("缺 _sat_override 纯函数")
    else:
        if _so("all", False, 0, 0, 2, 2) != (2, 2, True):
            bad.append("元层判「无新维度」后没推计数：%r"
                       % (_so("all", False, 0, 0, 2, 2),))
        if _so("1", False, 0, 0, 2, 2) != (2, 2, True):
            bad.append("研究层判「无新维度」后没推计数")
        if _so("0", False, 0, 0, 2, 2) != (2, 2, False):
            bad.append("0 层应走 idle_stall 且 sat_override=False：%r"
                       % (_so("0", False, 0, 0, 2, 2),))
        if _so("both", False, 5, 0, 2, 2) != (5, 2, True):
            bad.append("对撞层同样该生效，且取 max 不缩：%r"
                       % (_so("both", False, 5, 0, 2, 2),))
        if _so("all", None, 0, 0, 2, 2) != (0, 0, False):
            bad.append("未判定（None）时不该动任何计数")
        if _so("all", True, 7, 3, 2, 2) != (7, 3, False):
            bad.append("判「有新维度」时不该动任何计数")
    # 接线：两处 sat 块都过它
    if _src_txt.count("_sat_override(") < 3:
        bad.append("sat 接线没走 _sat_override（源里出现 %d 次）"
                   % _src_txt.count("_sat_override("))

    # ④ 停止可达：sat 的效果 → 元层给出理由
    try:
        _mr = mod.MetaDGTF(build_cfg(False))
        _rs, _ = _mr._stop_reasons(
            entry="all", layer_no=3, rounds_n=3, total_rounds=3,
            sp=dict(mod.DEFAULT_CONFIG["spiral"]), soft_max=3, sim_thr=0.8,
            stable_need=2, idle_limit=2, r_idle_limit=2, r_stall_limit=2,
            rephrase_streak=0, carry_streak=0,
            idle_new_amp=2, idle_new_thread=0, idle_stall=0,
            stall_why="", sat_override=True,
            prev_product="", view=mod.View(entry="all"), idles=0)
        if not any("结构饱和度" in str(x) for x in _rs):
            bad.append("元层拿到 sat 结论后仍不停（理由 %r）" % (_rs,))
    except Exception as _e:  # noqa: BLE001
        bad.append("停止可达判据异常：%s: %s" % (type(_e).__name__, _e))

    # ⑤ 比对窗口 = 池内全量
    if "win_amps[-r_window:]" in _src_txt:
        bad.append("serial 侧参照集仍是近 N 圈窗口")
    if 'state["win_amps"][-r_window:]' in _src_txt:
        bad.append("并行侧参照集仍是近 N 圈窗口")
    # ★ 只看「窗口串没了」不够 —— 有人把参照集换成 `[]` 或别的弱形态也过。
    #   必须断言它**真的是池内全量**（两处：serial + 并行 B）。
    if _src_txt.count("recent_amps = list(snap_amps)") != 2:
        bad.append("参照集不是池内全量（`recent_amps = list(snap_amps)` 出现 %d 次）"
                   % _src_txt.count("recent_amps = list(snap_amps)"))
    if _src_txt.count("recent_threads = list(snap_threads)") != 2:
        bad.append("线头参照集不是池内全量")
    # ★ `_is_dup` 是 `_run_layer` / `_b_check_stop` 里的**局部函数**，模块级取不到
    #   ⇒ 用它的两个组成函数（模块级）复现同一口径：overlap ≥ thr 或 similar(thr)。
    _sp0 = mod.DEFAULT_CONFIG.get("spiral") or {}
    _ovthr = float(_sp0.get("new_item_overlap", 0.55) or 0.55)
    _simthr = float(_sp0.get("new_item_similarity", 0.55) or 0.55)
    _a1 = "槽位状态列可空但不能由人名填充，人名列可填但不能改写槽位状态"
    _a4 = "槽位状态列可空但不能由人名填充，人名列可填但不能改写槽位状态列"
    if not (mod._overlap_coef(_a4, _a1) >= _ovthr
            or mod._similar(_a4, _a1, _simthr)):
        bad.append("跨圈重复样例在引擎判重口径下不算重复 —— 判据前提不成立")

    if bad:
        for _x in bad:
            print("  ✗ [v12316] %s" % _x)
        return False
    print("  ✓ [v12316] 档位维度已删（配置/auto 项/符号/CLI 四处）；"
          "惰性化归零；sat 落点四层同等（含 0 层走 stall）；"
          "元层拿到 sat 结论后会停；参照集改池内全量")
    return True
'''

EDITS = [
    # ── 注入守卫 ─────────────────────────────────────────────
    (10334, 10335, ['    if not check_v12315_history_calibration():',
                    '        return 1',
                    '    if not check_v12316_stop_therapy():',
                    '        return 1'],
     "注入新守卫", None, None),
    # ── main 里的旧档位断言 ──────────────────────────────────
    (10437, 10437, [], "非法档位断言删",
     '        assert p2["cost_profile"] != "luxury"', None),
    (10430, 10430, ['            "route": "不存在的档", "mode": "Z", "rounds": {"0": 999},',
                    '            "max_calls": -5,'],
     "脏值夹具去档位", '            "cost_profile": "luxury"', None),
    (10427, 10427, ['        # 脏值：负预算/越界圈数/未知 route —— 都要被兜住'],
     "脏值注释改", '        # 脏值：非法档位/负预算', None),
    (10380, 10384, [], "auto_plan 档位断言删",
     '        # ★ 成本档**不再问模型**', None),
    (10148, 10149, [],
     "旧守卫删（新判据在 main 尾部统一接）",
     '    if not check_cost_profile():', '        return 1'),
    # ── v12313 判据里的档位部分 ──────────────────────────────
    (9497, 9498, ['    for _k in ("route", "mode", "rounds", "max_calls",',
                  '               "orientation"):'],
     "schema 键去档位", '    for _k in ("route", "mode", "rounds", "cost_profile", "max_calls",', None),
    (9411, 9414, [], "auto 项写配置段删（web 项已覆盖）",
     '    _c4 = _copy.deepcopy(cfg0)', None),
    (9409, 9410, [], "显式档位落配置断言删",
     '    if _c2.get("cost_profile") != "quality":', None),
    (9404, 9405, ['    _dp2 = m.auto_dispatch(_FACT, _c2, explicit={"web": "off"})'],
     "显式夹具去档位", '    _dp2 = m.auto_dispatch(_FACT, _c2, explicit={"web": "off",', None),
    (9400, 9400, ['    #     `--web off` / `--thinking on` / `--effort max`'],
     "注释去 --profile", '    #     `--web off` / `--profile quality`', None),
    (9379, 9381, ['    _EX = {"route": ["0", "1"], "mode": "A",',
                  '           "rounds": "0:9,1:9,both:9,all:9", "orientation": "decision",',
                  '           "web": "off", "thinking": "on", "effort": "max",'],
     "_EX 去档位", '    _EX = {"route": ["0", "1"], "cost_profile": "quality", "mode": "A",', None),
    # ── 十二项 → 十一项（断言 + 三条档位断言 + 调度表行数）────
    (9343, 9344, ['    if len(_ORDER) != 11:',
                  '        bad.append("十一项不齐：%d 项" % len(_ORDER))'],
     "十二项断言→十一", '    if len(_ORDER) != 12:', None),
    (9443, 9456, [], "三条档位断言删",
     '    if _val(m.auto_dispatch(_DEC, cfg0, history=H), "cost_profile") != ', None),
    (9507, 9508, ['    if len(_rows) != 11:',
                  '        bad.append("调度表不是十一行（%d）" % len(_rows))'],
     "调度表行数→十一", '    if len(_rows) != 12:', None),
    (9323, 9323, ['    """[v1.23.13] 统一自适应调度器：十一项逐项可单独接管 + 历史自适应 + 技术债。'],
     "docstring 十一项", '    """[v1.23.13] 统一自适应调度器：十二项', None),
    (9326, 9326, ['      · 十一项各自都有留痕（值 / 来源 / 理由），缺一项即判红；'],
     "docstring 十一项2", '      · 十二项各自都有留痕', None),
    # ── 配置登记表销账（键已删 ⇒ 旧登记成「过期条目」）────────
    (5915, 5915, [], "登记表销账 cost_profile", '    "cost_profile": "质量档', None),
    (5940, 5940, [], "登记表销账 round_window",
     '    "spiral.round_window":', None),
    # ── P0-2：把「与重试无关」的变量固定住 ───────────────────
    (2549, 2551, ['            _c0 = build_cfg(False)',
                  '            # ★ [v1.23.16 判据随实现更新] 池重估的间隔曾随成本档',
                  '            #   惰性化（balanced 下 1→2）；本版去惰性化 ⇒ 1 圈也会跑',
                  '            #   重估，而「池空」时重估不适用（少一次调用）⇒ 两条路径的',
                  '            #   调用数被这个**与重试无关**的变量拉开。判据只关心重试，',
                  '            #   所以先把重估关掉再比（不是放宽阈值）。',
                  '            _c0.setdefault("spiral", {})["re_eval_every_n"] = 0',
                  '            r = mod.MetaDGTF(_c0).run(',
                  '                "冒烟：至少碰一个", route=["0"], rounds={"0": n_rounds},',
                  '                parallel_mode="serial")'],
     "P0-2 固定重估频率", '            r = mod.MetaDGTF(build_cfg(False)).run(', None),
    # ── 旧的 shape 收紧判据 ──────────────────────────────────
    (1154, 1171, [], "shape 收紧判据删",
     '    # ---- [④ 修正] shape_scale 只能缩', None),
    # ── check_cost_profile 头段 → 新判据 ─────────────────────
    (1027, 1063, NEW_CHECK.rstrip("\n").split("\n"),
     "三档判据 → 档位已删判据",
     'def check_cost_profile():', None),
]

for a, b, new, what, head, tail in sorted(EDITS, key=lambda x: -x[0]):
    cut(a, b, new, what, head, tail)

# ── 按「语句首行含特征」删语句 ───────────────────────────────
# ★ 两个坑都踩过：
#   ① 取「最小语句」⇒ 只删掉 `bad.append(...)`、留下孤立 `if ...:` ⇒
#      IndentationError；
#   ② 取「最外层」⇒ 上溯到包装它的**大 If**（甚至刚注入的新判据本身，
#      因为它的 `for _sym in (...)` 里出现了那个符号名）⇒ 整段被误删。
#   正解：只看**首行**含不含特征 —— 既不孤立 if、也不上溯。
#   ★ 特征串**不带左括号**：`if not hasattr(mod, "_auto_profile"): … else:`
#     的 `else` 分支里才是带括号的调用 —— 只匹配带括号的那个会把 else 拆空。
FEATS = ["_auto_pick_cost_profile", "_auto_profile",
         '"auto", "quality", "balanced", "economy"']
_tree = ast.parse("\n".join(lines))
_ranges = []
for _feat in FEATS:
    _c = [n for n in ast.walk(_tree) if isinstance(n, ast.stmt)
          and _feat in lines[n.lineno - 1]]
    assert _c, "AST 锚点找不到语句：%r" % _feat
    for _n in _c:
        _ranges.append((_n.lineno, _n.end_lineno, _feat))
# ★ 区间可能**嵌套**（`if hasattr(mod, "_auto_profile"): … else:` 的 body 里
#   还有两个含同名特征的 if）⇒ 必须先合并重叠区间再按下标删，
#   否则先删内层、再按**旧行号**删外层 ⇒ 删错位置（实测踩到）。
_flat = sorted({(a, b) for a, b, _ in _ranges})
_merged = []
for _a, _b in _flat:
    if _merged and _a <= _merged[-1][1]:
        _merged[-1][1] = max(_merged[-1][1], _b)
    else:
        _merged.append([_a, _b])
for _a, _b in reversed(_merged):
    LOG.append("%-40s %d-%d 删" % ("按首行删语句", _a, _b))
    del lines[_a - 1:_b]
LOG.append("按首行删语句：命中 %d 条 → 合并为 %d 段"
           % (len(set(_ranges)), len(_merged)))
# 多行判据里被删掉的 if 会留下空行连排，收一下
_txt = "\n".join(lines)
_txt = re.sub(r"\n{3,}", "\n\n", _txt)
lines = _txt.split("\n")

# ── SRC 指向本版 ────────────────────────────────────────────
_txt = "\n".join(lines)
_src_pat = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')
assert len(_src_pat.findall(_txt)) == 1, "SRC 行不是 1 行"
_txt = _src_pat.sub('SRC = HERE / "元DGTF-V1.23.16.py"', _txt)
lines = _txt.split("\n")

out = "\n".join(lines) + "\n"
ast.parse(out)

# ── 自检 ────────────────────────────────────────────────────
C = [
    ("SRC 指向 v1.23.16", 'SRC = HERE / "元DGTF-V1.23.16.py"' in out, True),
    ("新判据已注入", "def check_v12316_stop_therapy():" in out, True),
    ("新守卫已接", "if not check_v12316_stop_therapy():" in out, True),
    ("旧函数名已无", "def check_cost_profile():" in out, False),
    ("旧守卫已无", "if not check_cost_profile():" in out, False),
    ("_auto_pick_cost_profile 的旧判据已无",
     "m._auto_pick_cost_profile(" in out, False),
    ("_auto_profile 已无", "_auto_profile(" in out, False),
    ("--profile choices 判据已无", '"auto", "quality", "balanced", "economy"' in out, False),
    ("档位 shape 判据已无", "balanced 下 shape_chars" in out, False),
    ("p[cost_profile] 断言已无", 'p["cost_profile"]' in out, False),
    ("luxury 断言已无", '!= "luxury"' in out, False),
    ("原 check_cost_profile 的其它判据仍在", "覆盖率双口径" in out, True),
    ("原 check_cost_profile 的轨迹判据仍在", "不可判定命中轨迹逐圈记录" in out, True),
]
_bad = 0
for name, got, want in C:
    ok = got == want
    _bad += 0 if ok else 1
    print("  %s %s（%r vs %r）" % ("✓" if ok else "✗", name, got, want))
print("\n".join(LOG))
print("\n行数 %d → %d" % (N0, out.count("\n")))
assert _bad == 0, "自检 %d 项不过" % _bad

_new = out.replace("\n", "\r\n").encode("utf-8")
assert _new.count(b"\r\r\n") == 0 and _new.count(b"\r\n") == _new.count(b"\n")
SMOKE.write_bytes(_new)
print("\n已写 smoke_test.py")
