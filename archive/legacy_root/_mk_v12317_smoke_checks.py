# -*- coding: utf-8 -*-
"""v1.23.17 冒烟注入器：SRC 换版 + 新增两批判据 + 恢复 v1.23.16 孤儿化的判据。

★ 同时修一个**v1.23.16 引入的回归**：`check_cost_profile` 被「整条重写」时，
  它里面与成本档无关的判据（覆盖率双口径 / 命中轨迹）留在了 `return True`
  之后，成了死代码（约 90 行，33 条语句从没跑过）。这里把它们的 `def` 补回来。
"""
import ast
import re
from pathlib import Path

HERE = Path(".").resolve()
SMOKE = HERE / "smoke_test.py"
raw = SMOKE.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")


def repl_block(old, new, what, expect=1):
    o, n = old.split("\n"), new.split("\n")
    hits = [i for i in range(len(lines) - len(o) + 1) if lines[i:i + len(o)] == o]
    assert len(hits) == expect, "%s：命中 %d 次（要求 %d）" % (what, len(hits), expect)
    for i in reversed(hits):
        lines[i:i + len(o)] = n
    print("%-40s 改 %d 处" % (what, len(hits)))


# ① SRC 换版
repl_block('SRC = HERE / "元DGTF-V1.23.16.py"',
           'SRC = HERE / "元DGTF-V1.23.17.py"', "SRC → v1.23.17")

NEW_FUNCS = '''def check_v12317_stop_all_layers():
    """[v1.23.17] 三处停止阈值/门槛：sat 间隔 2 / soft_max 2 / 条件 1 四层通用。

    ★ 每条判据都带负对照 —— 否则「把阈值降到 0」也能过。
    """
    import re as _re
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")

    # ① 缺省字面：sat 两处 + soft_max 四处，全为 2
    _sat2 = 'int(sp.get("structure_saturation_every_n", 2))'
    if src.count(_sat2) != 2:
        bad.append("sat 缺省不是两处 2（%d 处）" % src.count(_sat2))
    if _re.search(r'structure_saturation_every_n",\\s*3\\)', src):
        bad.append("还有 sat 缺省写成 3 的地方")
    _sm2 = 'int(sp.get("soft_max", 2))'
    if src.count(_sm2) != 2:
        bad.append("soft_max 缺省不是两处 2（%d 处）" % src.count(_sm2))
    if src.count('spiral.get("soft_max", 2) or 2') != 2:
        bad.append("plan 系列的 soft 缺省不是两处 2")
    if _re.search(r'soft_max",\\s*3\\)', src):
        bad.append("还有 soft_max 缺省写成 3 的地方")

    # ② 出厂默认值
    _sp = mod.DEFAULT_CONFIG.get("spiral") or {}
    if _sp.get("soft_max") != 2:
        bad.append("DEFAULT_CONFIG soft_max = %r（应 2）" % _sp.get("soft_max"))
    if _sp.get("structure_saturation_every_n") != 2:
        bad.append("DEFAULT_CONFIG sat = %r（应 2）"
                   % _sp.get("structure_saturation_every_n"))

    # ③ 条件 1 对四层通用（行为）+ 两条负对照
    _mr = mod.MetaDGTF(build_cfg(False))

    def _rs(entry, ln, soft, carry, reph):
        _r, _ = _mr._stop_reasons(
            entry=entry, layer_no=ln, rounds_n=3, total_rounds=3,
            sp=dict(_sp), soft_max=soft, sim_thr=0.8, stable_need=2,
            idle_limit=2, r_idle_limit=2, r_stall_limit=2,
            rephrase_streak=reph, carry_streak=carry,
            idle_new_amp=0, idle_new_thread=0, idle_stall=0,
            stall_why="", sat_override=False,
            prev_product="", view=mod.View(entry=entry), idles=0)
        return " | ".join(str(x) for x in _r)

    try:
        for _e in ("0", "1", "both", "all"):
            _t = _rs(_e, 2, 2, 2, 2)
            if "圈复述" not in _t or "点名同一批问题未消化" not in _t:
                bad.append("条件 1 没对 %s 层生效（%r）" % (_e, _t[:40]))
        if "圈复述" in _rs("1", 2, 2, 1, 1):
            bad.append("只累计 1 圈就给了理由（阈值被放宽）")
        if "圈复述" in _rs("1", 2, 3, 2, 2):
            bad.append("layer_no < soft_max 的推迟失效了")
    except Exception as _e:  # noqa: BLE001
        bad.append("条件 1 行为判据异常：%s: %s" % (type(_e).__name__, _e))

    # ④ 0/1 层的复述圈数能被 _compute_rephrase_streak 读回 + 负对照
    def _streak(ratio):
        _pool = mod.Pool()
        _v = mod.View(entry="1")
        _v._ing_rephrase_ratio = ratio
        _st = {"rephrased_streak": 0, "meta_idle_streak": 0}
        for _k in range(2):
            _st["rephrased_streak"], _st["meta_idle_streak"] = (
                _mr._apply_view_to_pool_locked(
                    _v, _pool, "1", _st["rephrased_streak"],
                    _st["meta_idle_streak"], 2))
        return mod._compute_rephrase_streak(_v, _st)

    try:
        if _streak(0.6) < 2:
            bad.append("0/1 层的复述圈数读不回来（= %s）" % _streak(0.6))
        if _streak(0.0) != 0:
            bad.append("不复述的圈却被记成复述（负对照失效）")
    except Exception as _e:  # noqa: BLE001
        bad.append("复述载体判据异常：%s: %s" % (type(_e).__name__, _e))

    if bad:
        for _x in bad:
            print("  ✗ [v12317] %s" % _x)
        return False
    print("  ✓ [v12317] sat 间隔 2（三处缺省）；soft_max 2（五处缺省）；"
          "条件 1 四层通用（含 0/1）；0/1 复述信号可读；两向负对照都在")
    return True


def check_v12317_und_coverage_trace():
    """[v1.23.17] 恢复 v1.23.16 孤儿化的判据：覆盖率双口径 + 不可判定命中轨迹。

    ★ 这些判据原本在 `check_cost_profile` 里，与该函数名（成本档）**无关**。
      v1.23.16 把它「整条重写」成 `check_v12316_stop_therapy` 时连它们一起丢在
      `return True` 之后 —— 成了死代码，约 90 行 / 33 条语句**再没跑过**。
      这里原样恢复，只把 ✓ 文案里已不存在的「成本档 / 探针按角色跳」半句去掉。
    """'''

# ② 在死代码块之前插入新函数 + 恢复函数的头
ANCHOR = "    # ---- [覆盖率双口径] 自报值和代码实算必须同时出现 ----"
assert lines.count(ANCHOR) == 1, "锚点命中 %d 次" % lines.count(ANCHOR)
_i = lines.index(ANCHOR)
lines[_i:_i] = NEW_FUNCS.split("\n") + [""]
print("%-40s 插入 2 个函数" % "新函数 + 恢复函数头")

# ③ 修 ✓ 文案（去掉已不存在的成本档半句）
repl_block('''    print("  ✓ [成本档] 探针按角色跳（收束/复裁）；"
          "可判定/不可判定两条通道都是双口径")''',
           '''    print("  ✓ [覆盖率] 可判定/不可判定两条通道都是双口径"
          "（自评折算 + 代码实算）")''',
           "✓ 文案去成本档")

# ⑤ P1-6 夹具：把「停止」这个与本题无关的变量固定住（不是把 3 改成 2）
repl_block('''            try:
                mod.DGTF.run = _patched_run
                mod.update_deferrals = _patched_ud
                res = mod.MetaDGTF(build_cfg(False)).run(
                    "冒烟：跨圈 errors 累积", route=["0", "1"],
                    rounds={"0": 2, "1": 3}, parallel_mode=mode)''',
           '''            try:
                mod.DGTF.run = _patched_run
                mod.update_deferrals = _patched_ud
                # ★ [v1.23.17 判据随实现更新] 本判据量的是「errors 跨圈累积」，
                #   与层跑几圈无关。v1.23.17 起条件 1（复述/自省点名）对四层生效、
                #   且 soft_max 降到 2 ⇒ 研究层第 2 圈就停（实测停因含「ing 连续
                #   2 圈复述… + 自省连续 2 圈点名同一批问题未消化」），「3 圈」这个
                #   夹具假设不再成立。**把停止固定住**（不是把 3 改小）：soft_max 抬高
                #   同时关掉条件 1 的推迟与条件 6，三条 idle 阈值抬到 99，sat 关掉
                #   ⇒ 各层跑满自己的上限（实测 0 层 2 圈 / 1 层 3 圈）。
                _cfg_p16 = build_cfg(False)
                _sp16 = _cfg_p16.setdefault("spiral", {})
                _sp16["soft_max"] = 99
                _sp16["round_idle_limit"] = 99
                _sp16["round_stall_limit"] = 99
                _sp16["idle_limit"] = 99
                _sp16["structure_saturation_enabled"] = False
                res = mod.MetaDGTF(_cfg_p16).run(
                    "冒烟：跨圈 errors 累积", route=["0", "1"],
                    rounds={"0": 2, "1": 3}, parallel_mode=mode)''',
           "P1-6 夹具固定停止")

# ⑥ #13 夹具：同样把自然停固定住（预算才是要量的那个停止来源）
repl_block('''    def _run(budget):
        cfg = build_cfg(False)
        cfg["max_calls"] = budget
        meta = mod.MetaDGTF(cfg)''',
           '''    def _run(budget):
        cfg = build_cfg(False)
        cfg["max_calls"] = budget
        # ★ [v1.23.17 判据随实现更新] 本判据量的是「预算耗尽是不是四层一起停」，
        #   与**自然停**无关。本版条件 1 对四层生效 + soft_max 降到 2 ⇒ 修行层
        #   第 2 圈就自然停（实测停因含条件 1 与「产物相似度高，自然安住」），
        #   「四层都带预算用尽」不再成立。**把自然停固定住**（不是改期望值）：
        #   soft_max 抬高同时关掉条件 1 的推迟与条件 6，三条 idle 阈值抬到 99，
        #   sat 关掉 ⇒ 预算成为唯一的停止来源（实测预算 30 → 四层全带「预算用尽」、
        #   预算 0 → 0 层）。
        _sp = cfg.setdefault("spiral", {})
        _sp["soft_max"] = 99
        _sp["round_idle_limit"] = 99
        _sp["round_stall_limit"] = 99
        _sp["idle_limit"] = 99
        _sp["structure_saturation_enabled"] = False
        meta = mod.MetaDGTF(cfg)''',
           "#13 夹具固定自然停")

# ⑦ 接线：在 v12316 守卫之后
repl_block('''    if not check_v12316_stop_therapy():
        return 1''',
           '''    if not check_v12316_stop_therapy():
        return 1
    if not check_v12317_stop_all_layers():
        return 1
    if not check_v12317_und_coverage_trace():
        return 1''',
           "注入两条守卫")

out = "\n".join(lines)
t = ast.parse(out)

# ⑤ 自检：不许再有「return 之后的死代码」
_dead = []
for _n in ast.walk(t):
    if isinstance(_n, ast.FunctionDef):
        _seen, _d = False, 0
        for _s in _n.body:
            if _seen:
                _d += 1
            elif (isinstance(_s, ast.Return)
                  and isinstance(_s.value, ast.Constant)):
                _seen = True          # ★ 只数「return 之后**还有**语句」的
        if _d:
            _dead.append("%s(+%d)" % (_n.name, _d))
assert not _dead, "仍有死代码：%s" % _dead
assert out.count("def check_v12317_stop_all_layers(") == 1
assert out.count("def check_v12317_und_coverage_trace(") == 1
assert out.count("check_v12317_stop_all_layers()") == 2  # def + guard

enc = out.replace("\n", "\n").replace("\n", "\r\n").encode("utf-8")
assert enc.count(b"\r\r\n") == 0
SMOKE.write_bytes(enc)
print("死代码自检：0 处；行数 %d；CRLF %d"
      % (out.count("\n"), enc.count(b"\r\n")))
