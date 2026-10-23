# -*- coding: utf-8 -*-
"""v1.23.17 补丁：三处停止阈值/门槛（sat 间隔 2 / soft_max 2 / 条件 1 四层通用）。

★ 单一真相源：全部编辑都在 `lines` 上做，最后一次 join、一次 CRLF、一次写盘。
"""
import ast
import re
from pathlib import Path

HERE = Path(".").resolve()
P = HERE / "元DGTF-V1.23.17.py"

raw = P.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n"), "不是纯 CRLF"
assert raw.count(b"\r\r\n") == 0
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
LOG = []


def repl(old, new, what, expect=1):
    o, n = old.split("\n"), new.split("\n")
    hits = [i for i in range(len(lines) - len(o) + 1)
            if lines[i:i + len(o)] == o]
    assert len(hits) == expect, "%s：块命中 %d 次（要求 %d）" % (what, len(hits), expect)
    for i in reversed(hits):
        lines[i:i + len(o)] = n
    LOG.append("%-34s 改 %d 处" % (what, len(hits)))


# ═════════════════════════════════════ ① sat 间隔 3 → 2
repl('        "structure_saturation_every_n": 3,',
     '        "structure_saturation_every_n": 2,',
     "定义区 structure_saturation_every_n=2")
repl('            sat_every_n = int(sp.get("structure_saturation_every_n", 3))',
     '            sat_every_n = int(sp.get("structure_saturation_every_n", 2))',
     "serial 侧 sat 缺省 2")
repl('        sat_every_n = int(sp.get("structure_saturation_every_n", 3))',
     '        sat_every_n = int(sp.get("structure_saturation_every_n", 2))',
     "并行侧 sat 缺省 2")

# ═════════════════════════════════════ ② soft_max 3 → 2
repl('        "soft_max": 3,', '        "soft_max": 2,', "定义区 soft_max=2")
repl('        soft_max = int(sp.get("soft_max", 3))',
     '        soft_max = int(sp.get("soft_max", 2))', "serial 侧 soft_max 缺省 2")
repl('            "soft_max": int(sp.get("soft_max", 3)),',
     '            "soft_max": int(sp.get("soft_max", 2)),', "并行 state soft_max 缺省 2")
repl('    soft = int(spiral.get("soft_max", 3) or 3)',
     '    soft = int(spiral.get("soft_max", 2) or 2)', "plan_resources soft 缺省 2")
repl('        soft = int(spiral.get("soft_max", 3) or 3)',
     '        soft = int(spiral.get("soft_max", 2) or 2)', "方法级 _auto_plan soft 缺省 2")

# ═════════════════════════════════════ ③ 条件 1 门槛去掉（含缩进整理）
OLD1 = '''        # ---- 1) 复述 / 自省点名未消化（只对 all/both）----
        if entry in ("all", "both"):
            if diag:
                print(f"   🔬 [fix-78 diag] entry={entry} "
                      f"复述={rephrase_streak}｜自省点名未消={carry_streak}"
                      f" soft_max={soft_max}")
            _src: List[str] = []
            if rephrase_streak >= 2:
                _src.append(f"ing 连续 {rephrase_streak} 圈复述（层内空转）")
            if carry_streak >= 2:
                _src.append(f"自省连续 {carry_streak} 圈点名同一批问题未消化"
                            f"（层内空转）")
            if _src:
                if layer_no < soft_max:
                    if diag:
                        print(f"   ⏸ [fix-82] fix-72 v4 待触发"
                              f"（{' + '.join(_src)}），"
                              f"但 layer_no={layer_no} < soft_max={soft_max}，"
                              f"先不停止")
                    elif defer_vp:
                        self.vp(f"   ⏸ [fix-82] fix-72 v4 待触发"
                                f"（{' + '.join(_src)}）")
                else:
                    reasons.extend(_src)'''
NEW1 = '''        # ---- 1) 复述 / 自省点名未消化（四层通用）----
        #   ★ 以前这条只对 all/both 开放。四层都产 & 与自省反馈，判据问的是
        #     「本层这几圈是不是在换措辞重复」，与层无关 —— 门槛去掉。
        #     `layer_no < soft_max` 的推迟仍然保留（早圈不许停）。
        if diag:
            print(f"   🔬 [fix-78 diag] entry={entry} "
                  f"复述={rephrase_streak}｜自省点名未消={carry_streak}"
                  f" soft_max={soft_max}")
        _src: List[str] = []
        if rephrase_streak >= 2:
            _src.append(f"ing 连续 {rephrase_streak} 圈复述（层内空转）")
        if carry_streak >= 2:
            _src.append(f"自省连续 {carry_streak} 圈点名同一批问题未消化"
                        f"（层内空转）")
        if _src:
            if layer_no < soft_max:
                if diag:
                    print(f"   ⏸ [fix-82] fix-72 v4 待触发"
                          f"（{' + '.join(_src)}），"
                          f"但 layer_no={layer_no} < soft_max={soft_max}，"
                          f"先不停止")
                elif defer_vp:
                    self.vp(f"   ⏸ [fix-82] fix-72 v4 待触发"
                            f"（{' + '.join(_src)}）")
            else:
                reasons.extend(_src)'''
repl(OLD1, NEW1, "条件 1 门槛去掉（四层通用）")

# ═════════════════════════════════════ ④ 0/1 层的复述圈数写进可读载体
OLD2 = '''            if rephrased_streak >= 2:
                view.idle = True
                if getattr(self, "verbose", False):
                    _why_parts = []
                    if _sc_rephrase:
                        _why_parts.append("self-check")
                    if _direct_rephrase:
                        _why_parts.append("direct")
                    _why_str = "+".join(_why_parts) or "?"
                    print(f"   ⏸ self-check 反复复述"
                          f"（连续 {rephrased_streak} 圈，"
                          f"why={_why_str}），"
                          f"标记为空转")'''
NEW2 = OLD2 + '''
            # ★ 让 0/1 层的「连续复述圈数」也**可读**：`_compute_rephrase_streak`
            #   （唯一消费点）读的就是这个属性。条件 1 已四层通用，没有这一行，
            #   它那半条信号对 0/1 永远是 0。**不改 view.idle 的既有语义。**
            try:
                view._meta_idle_streak = rephrased_streak
            except Exception:
                pass'''
repl(OLD2, NEW2, "0/1 复述圈数写入 view 载体")

# ═════════════════════════════════════ ⑤ fix-78 diag 门槛同步放开
repl('            if entry in ("all", "both") and getattr(self, "verbose", False):\n'
     '                print(f"   🔬 [fix-78 diag] entry={entry} "',
     '            if getattr(self, "verbose", False):\n'
     '                print(f"   🔬 [fix-78 diag] entry={entry} "',
     "serial diag 门槛放开")

# ═════════════════════════════════════ 结构自检
out = "\n".join(lines)
ast.parse(out)
assert out.count('if entry in ("all", "both"):') == 0, \
    "条件 1 门槛没去干净"
assert '"soft_max": 2,' in out
assert '"structure_saturation_every_n": 2,' in out
assert "view._meta_idle_streak = rephrased_streak" in out
assert out.count('int(sp.get("soft_max", 2))') == 2
assert out.count('int(sp.get("structure_saturation_every_n", 2))') == 2
assert out.count('spiral.get("soft_max", 2) or 2') == 2

enc = out.replace("\n", "\r\n").encode("utf-8")
assert enc.count(b"\r\r\n") == 0
P.write_bytes(enc)
print("\n".join(LOG))
print("行数：%d → %d" % (len(raw.decode("utf-8").replace("\r\n", "\n").split("\n")) - 1,
                         out.count("\n")))
print("CRLF %d | CRCRLF %d" % (enc.count(b"\r\n"), enc.count(b"\r\r\n")))
