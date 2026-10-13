#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.32 补丁第 2 段：停因级联 + CSD 早期预警接线与渲染。

· 停因级联（SHP）：`_stop_reasons` 内部按优先级重排并写 `view.stop_primary`，
  产物渲染「主因（最高优先级）」+「全部触发」；不变量：主因 ∈ 全部触发。
· CSD 早期预警（复杂系统）：每层逐圈序列的方差/AC1 → `view.csd` 读数，
  渲染一行；**只作读数，不改任何停止行为**。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.32.py"


def _load(p=SRC):
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "含 CRCRLF"
    return b.decode("utf-8").replace("\r\n", "\n")


def _save(s, p=SRC):
    assert "\r\r\n" not in s
    p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))


def rep(s, old, new, what, expect=1):
    n = s.count(old)
    assert n == expect, "%s：命中 %d 次（要求 %d）" % (what, n, expect)
    return s.replace(old, new)


def main():
    s = _load()

    # 1) View 新字段
    s = rep(s, "    duty_verdict: str = \"\"",
            "    duty_verdict: str = \"\"\n"
            "    #: [停因级联] 主因（最高优先级的那条）—— ★ 不变量：它必须出现在\n"
            "    #:   `stop_reason` 里（报告的原因不能是「没触发的那个」）。\n"
            "    stop_primary: str = \"\"\n"
            "    #: [CSD 早期预警] 逐圈序列的方差/AC1 读数（**只作读数**）。\n"
            "    csd: dict = field(default_factory=dict)",
            "View 新字段")

    # 2) 停因级联：在 _stop_reasons 返回前按优先级重排 + 写主因
    s = rep(s, "            elif not view.idle:\n                idles = 0\n\n"
               "        return reasons, idles",
            "            elif not view.idle:\n                idles = 0\n\n"
            "        # ★ [停因级联 · 吸收 SHP]\n"
            "        #   把全部停因按**优先级**排序（判定/收敛 > 熵收敛 > 无信息增益 > 硬上限），\n"
            "        #   并写出去「主因」。纪律：**报告的主因必须就是真正停下来的那个** ——\n"
            "        #   一个级联、无漂移；主因不许是「没触发的原因」。\n"
            "        if reasons:\n"
            "            try:\n"
            "                _cas = stop_cascade(reasons)\n"
            "                if _cas.get(\"primary\"):\n"
            "                    reasons = list(_cas[\"ordered\"])\n"
            "                    view.stop_primary = str(_cas[\"primary\"])\n"
            "            except Exception:\n"
            "                pass\n\n"
            "        return reasons, idles",
            "停因级联")

    # 3) CSD 读数方法：插在 _layer_duty_now 之前
    s = rep(s, "    def _layer_duty_now(self, entry: str, view) -> dict:",
            "    def _layer_csd_now(self, entry: str, view) -> dict:\n"
            "        \"\"\"[CSD 早期预警] 逐圈序列的方差 / lag-1 自相关（**只作读数**）。\n\n"
            "        ★ 依据（复杂系统 / 生态学）：系统接近临界转变时恢复速率下降 ⇒\n"
            "          方差与 AC(1) 上升。\n"
            "        ★ **口径写死**：这是「韧性的**概率性评估**，不是迫近崩溃的预测」\n"
            "          —— 六种 regime shift 机制里多数没有 CSD 前兆。\n"
            "        ★ **不参与任何停止判定**（不改变行为，只出读数）。\n"
            "        \"\"\"\n"
            "        if view is None:\n"
            "            return {}\n"
            "        _rl = list(getattr(view, \"round_log\", None) or [])\n"
            "        _s_new = [int(r.get(\"new_amps\", 0) or 0) for r in _rl\n"
            "                  if isinstance(r, dict)]\n"
            "        _s_idle = [int(r.get(\"idle_stall\", 0) or 0) for r in _rl\n"
            "                   if isinstance(r, dict)]\n"
            "        d = {}\n"
            "        try:\n"
            "            d[\"new_amps\"] = csd_indicators(_s_new)\n"
            "            d[\"idle_stall\"] = csd_indicators(_s_idle)\n"
            "        except Exception:\n"
            "            d = {}\n"
            "        view.csd = d\n"
            "        return d\n\n"
            "    def _layer_duty_now(self, entry: str, view) -> dict:",
            "CSD 读数方法")

    # 4) 收尾调用 CSD（紧跟职责读数之前那行）
    s = rep(s, "        # ★ [LDG] 最终职责读数先算出来（**只算不写**：署名必须等其他",
            "        # ★ [CSD 早期预警] 逐圈序列读数（只算，不改行为）。\n"
            "        try:\n"
            "            self._layer_csd_now(entry, view)\n"
            "        except Exception:\n"
            "            pass\n"
            "        # ★ [LDG] 最终职责读数先算出来（**只算不写**：署名必须等其他",
            "收尾调用 CSD")

    # 5) 渲染：层明细里，职责判定行之后补 CSD 行
    s = rep(s, '''            if view.duty_verdict:
                lines += [f"【职责判定】{view.duty_verdict}"]''',
            '''            if view.duty_verdict:
                lines += [f"【职责判定】{view.duty_verdict}"]
            # ★ [停因级联] 主因单列 —— 与「全部触发」并列，读者一眼看到
            #   「真正停下来的是哪一个」，不必自己从 " + " 串里猜。
            if view.stop_primary:
                lines += [f"【主因（最高优先级）】{view.stop_primary}"]
            # ★ [CSD 早期预警] 读数（不是判定）：口径写在文案里，防被读成预测。
            try:
                _cd = (view.csd or {}).get("new_amps")
                if _cd:
                    lines += [f"【早期预警】{csd_line(_cd)}"]
            except Exception:
                pass''',
            "主因 + CSD 渲染")

    _save(s)
    print("OK v1.23.32 第 2 段（级联 + CSD）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert s2.count("stop_cascade(reasons)") == 1
    assert s2.count("def _layer_csd_now(self, entry: str, view) -> dict:") == 1
    assert "【主因（最高优先级）】" in s2
    print("复读校验通过")


if __name__ == "__main__":
    main()
