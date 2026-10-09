# @@BLOCK_SAT_OVERRIDE@@
# ============================================================
# 停止判据：结构饱和度判定的落点
# ============================================================
# 「本圈新 & 是否引入了新的结构维度」这件事，语义判定比词集重叠准：
# 实测（真跑产物）研究层 16 条 & 两两词集重叠**峰值 0.45**、达标 0 对，
# 而 LLM 两次都判「无新维度（仅换措辞 / 与上圈逐字相同）」。
# 所以 sat 判定的结论必须能真正改变停止行为 —— 它此前只对研究层生效
# （元层判出来只打一行日志，于是元层结构上不可能自然停）。
# 本函数是「sat 判定 → 两条计数」的唯一实现，serial 与并行 B 共用。


def _sat_override(entry, sat_verdict, idle_new_amp, idle_stall,
                  r_idle_limit, r_stall_limit):
    """sat 判「无新维度」时，把计数推到各自的停止门槛。

    ★ 为什么**四层同等生效**：判据问的是「本圈新 & 有没有引入新的结构
      维度」，与层无关（四层都产 &）。此前只有研究层推计数 —— 元层
      （跑得最多的层）判出「无新维度」只打日志。
    ★ 0 层没有「无新 &」这条通路（`_stop_reasons` 的条件 2 排除了 "0"），
      它的落点是 `idle_stall`（条件 3，四层通用）；`sat_override` 只
      影响条件 2 的理由文案，故 0 层返回 False。

    返回 `(idle_new_amp, idle_stall, sat_override)`。
    """
    if sat_verdict is not False:
        return idle_new_amp, idle_stall, False
    return (max(idle_new_amp, r_idle_limit),
            max(idle_stall, r_stall_limit),
            entry != "0")
# @@END@@
# @@BLOCK_SAT_SERIAL@@
            sat_enabled = bool(sp.get("structure_saturation_enabled", True))
            sat_every_n = int(sp.get("structure_saturation_every_n", 3))
            if (sat_enabled and sat_every_n > 0
                    and layer_no % sat_every_n == 0
                    and new_amps):
                sat_verdict = self._check_structure_saturation(
                    new_amps, list(snap_amps))
                idle_new_amp, idle_stall, sat_override = _sat_override(
                    entry, sat_verdict, idle_new_amp, idle_stall,
                    r_idle_limit, r_stall_limit)
                if sat_verdict is False:
                    self.vp(f"      ↳ 无新维度：idle_new_amp→"
                            f"{idle_new_amp}、idle_stall→{idle_stall}"
                            f"（四层同等生效）")
                elif sat_verdict is True:
                    self.vp(f"      ↳ 有新维度，idle_new_amp 重置为 0")
# @@END@@
# @@BLOCK_SAT_B@@
        sat_enabled = bool(sp.get("structure_saturation_enabled", True))
        sat_every_n = int(sp.get("structure_saturation_every_n", 3))
        if (sat_enabled and sat_every_n > 0
                and r % sat_every_n == 0
                and new_amps):
            sat_verdict = self._check_structure_saturation(
                new_amps, list(snap_amps))
            idle_new_amp, idle_stall, sat_override = _sat_override(
                entry, sat_verdict, idle_new_amp, idle_stall,
                r_idle_limit, r_stall_limit)
            state["idle_new_amp"] = idle_new_amp
            if sat_verdict is False:
                self.vp(f"      ↳ 无新维度：idle_new_amp→"
                        f"{idle_new_amp}、idle_stall→{idle_stall}"
                        f"（四层同等生效）")
            elif sat_verdict is True:
                self.vp(f"      ↳ 有新维度，idle_new_amp 重置为 0")
# @@END@@
