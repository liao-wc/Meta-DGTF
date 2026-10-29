# -*- coding: utf-8 -*-
"""[V2.2.20] 由 V2.2.19 生成：道生支路统一模式（rounds_locked + tick patch 键守卫）。"""
import py_compile
from pathlib import Path

ENG = Path("dgtf_engine/dgtf_v2/engine")
SRC = ENG / "Meta-DGTF-V2.2.19.py"
DST = ENG / "Meta-DGTF-V2.2.20.py"
raw = SRC.read_bytes()
assert raw[:3] != b"\xef\xbb\xbf" and raw.count(b"\n") == raw.count(b"\r\n")
t = raw.decode("utf-8").replace("\r\n", "\n")


def rep(a, b):
    global t
    c = t.count(a)
    assert c == 1, "锚点命中 %d 次: %r" % (c, a[:70])
    t = t.replace(a, b)


rep("Meta-DGTF-道生三阶模型 · V2.2.19\n", "Meta-DGTF-道生三阶模型 · V2.2.20\n")
rep('__version__ = "2.2.19"', '__version__ = "2.2.20"')
rep("★ V2.2.19 补丁（输入驱动自动模式 + 每模式专属配置 + 运行期动态调整 + 模式集裁剪）：",
"""★ V2.2.20 补丁（道生支路接入统一模式体系，方案 A）：
      · 道生 plan 现在把 engine_mode 一并作为 --mode 透传，并带 unified_config
        （MODE_CONFIGS 的专门配置）与 rounds_locked 标记；
      · 引擎 --mode 规划时：若本次显式给了 rounds（道生质量档/快档），
        标记 rounds_locked ⇒ 运行期 dynamic_adjust 只调 thinking/web，不改圈数
        （与「显式圈数优先」补丁口径一致）；
      · _auto_mode_tick 只在 patch 带 cap_rounds / rounds_extra 时才改圈
        ⇒ 锁定场景不会静默改用户的圈数计划，调整仍落 packed.auto_mode。
      · 默认（不给 --mode）逐字保持 V2.2.19 行为；只改道生支路与动态调整守卫。

★ V2.2.19 补丁（输入驱动自动模式 + 每模式专属配置 + 运行期动态调整 + 模式集裁剪）：""")

# 1) main --mode：显式 rounds ⇒ rounds_locked
rep('''            _auto_mode_plan = plan_for_input(_question, _mopts)
            _mc = _auto_mode_plan.get("config") or {}
''',
'''            _auto_mode_plan = plan_for_input(_question, _mopts)
            _mc = _auto_mode_plan.get("config") or {}
            # ★ [V2.2.20] 显式 --rounds（道生质量档/快档会显式给）⇒ 圈数锁定：
            #   运行期动态调整只调 thinking/web，不改圈（与显式圈数优先同口径）。
            if args.rounds:
                _auto_mode_plan["rounds_locked"] = True
''')

# 2) tick：downgrade 的圈数压缩只在 patch 带 cap_rounds 时执行
rep('''                _st = getattr(self, "_b_state", None)
                if isinstance(_st, dict):
                    for _s in _st.values():
                        if _s.get("stopped"):
                            continue
                        _s["total_rounds"] = min(
                            int(_s.get("total_rounds") or 1),
                            max(1, int(wave)) + 1)
                else:
                    _rounds = getattr(self, "_rounds", None)
                    if isinstance(_rounds, dict):
                        for _e in list(_rounds):
                            if _e not in (getattr(self, "_results", {}) or {}):
                                _rounds[_e] = 1
''',
'''                # ★ [V2.2.20] 只有 patch 明确 cap_rounds 时才动圈数：
                #   rounds_locked（道生显式圈数档）场景下动态调整不改圈计划。
                if dec["patch"].get("cap_rounds"):
                    _st = getattr(self, "_b_state", None)
                    if isinstance(_st, dict):
                        for _s in _st.values():
                            if _s.get("stopped"):
                                continue
                            _s["total_rounds"] = min(
                                int(_s.get("total_rounds") or 1),
                                max(1, int(wave)) + 1)
                    else:
                        _rounds = getattr(self, "_rounds", None)
                        if isinstance(_rounds, dict):
                            for _e in list(_rounds):
                                if _e not in (getattr(self, "_results", {}) or {}):
                                    _rounds[_e] = 1
''')

# 3) tick：upgrade 的补圈同理
rep('''            elif dec["action"] == "upgrade":
                self._auto_set_thinking("auto")
                if not isinstance(getattr(self, "_b_state", None), dict):
                    _rounds = getattr(self, "_rounds", None)
                    if isinstance(_rounds, dict):
                        for _e in list(_rounds):
                            if _e not in (getattr(self, "_results", {}) or {}):
                                _rounds[_e] = int(_rounds.get(_e) or 0) + 1
''',
'''            elif dec["action"] == "upgrade":
                self._auto_set_thinking("auto")
                if dec["patch"].get("rounds_extra") and not isinstance(
                        getattr(self, "_b_state", None), dict):
                    _rounds = getattr(self, "_rounds", None)
                    if isinstance(_rounds, dict):
                        for _e in list(_rounds):
                            if _e not in (getattr(self, "_results", {}) or {}):
                                _rounds[_e] = int(_rounds.get(_e) or 0) + 1
''')

out = t.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)
chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(DST), doraise=True)
print("OK:", DST.name, len(chk), "bytes")
