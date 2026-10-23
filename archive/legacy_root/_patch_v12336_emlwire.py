# -*- coding: utf-8 -*-
"""「学了要做，与调度层融合」：给 EML 的**每条** action.key 接上真实调度消费方。

## 用户口径
「学了要做，与调度层进行融合。」

## 现状（本版实测）
`eml_candidates_from_result` 生成 4 种 key，`_eml_apply` 只有 2 个分支
⇒ `carve_first` / `tri_advisory_only` / `note_cost_no_gain` **学而不做**
（`playbook.jsonl` 里 `L0010`/`L0011` 就是活证据：真实生成了 `carve_first`
条目，却**没有任何代码会执行它**）。

本版此前用「**豁免表 + 两向对账**」把它**显式化**了（从「像是忘了」变成
「显式的决定」）—— 但用户要求**更进一步**：**要真的做**。

## 修法：每条 key 接到**有真实消费方**的调度参数

| key | 调度动作 | 消费方（read 得到的那一方） |
|---|---|---|
| `rounds_delta` | `rounds.<层> += delta` | `rounds_plan`（既有的层圈数计划） |
| `duty_floor` | `self._duty_floor = floor` | 职责守卫 |
| **`carve_first`** | **`rounds.<层> += 1`** | `rounds_plan` |
| **`tri_advisory_only`** | **`duty_floor` 上调一档** | 职责守卫 |
| **`note_cost_no_gain`** | **`rounds.<层> -= 1`** | `rounds_plan` |

★ **为什么这些是「融合」而不是「硬接」**：四条调度动作**都改的是本跑真正
  读的那几个量**（`rounds_plan` / `_duty_floor`）—— 不是记账、不是留痕就完，
  而是**下一次决策会因此不同**。
★ **为什么保留 5 个不同的 key**（而不是合并成 2 个）：**理由不同**
  （被截断 / 职责不足 / 三态不可信 / 花多赚少），产物里要能区分
  「这一圈是为了什么加的」。**动作同形没关系，语义要可分辨**。
★ 全部经 `ControlSurface`：白名单 + 边界（圈数 1..hard_max、duty_floor 0..1）
  + 必留痕（why + trace_ref）⇒ 可控 + 可追溯。**绝不写配置**。

## 连带改动
`_EML_RECORD_ONLY` **清空**（不再有「只记录不做」的 key）——
判据 `check_v12336_eml` 的两向对账会自动验证这一点。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.36.py"

# ── A：把 `_eml_apply` 扩成 5 个分支 ──
OLD = '''            elif _key == "duty_floor":
                try:
                    _fl = float(_a.get("floor"))
                except (TypeError, ValueError):
                    continue
                # ★ 同上：经控制面（0..1 边界 + 必留痕）。
                if self._control.write(
                        "duty_floor", _fl,
                        why="EML duty_floor（条目 %s）" % _it.get("id"),
                        trace_ref=_it.get("id")):
                    self._duty_floor = _fl
                    _it["applied"] = True
                    _applied.append({"id": _it["id"], "key": _key,
                                     "floor": self._duty_floor})'''

NEW = '''            elif _key == "duty_floor":
                try:
                    _fl = float(_a.get("floor"))
                except (TypeError, ValueError):
                    continue
                # ★ 同上：经控制面（0..1 边界 + 必留痕）。
                if self._control.write(
                        "duty_floor", _fl,
                        why="EML duty_floor（条目 %s）" % _it.get("id"),
                        trace_ref=_it.get("id")):
                    self._duty_floor = _fl
                    _it["applied"] = True
                    _applied.append({"id": _it["id"], "key": _key,
                                     "floor": self._duty_floor})
            elif _key == "carve_first":
                # ★ [学了要做 · 与调度融合] 职责不足 ⇒ 给该层**多一圈**
                #   （多一次 `_he` 沉淀「撞不动的东西」的机会）。
                #   与 `rounds_delta` 的**理由不同**（职责不足 vs 被截断），
                #   动作同形 —— 保留两个 key 是为了产物里能分辨「为什么加」。
                _done = []
                for _lyr in (_a.get("layers") or []):
                    _lyr = str(_lyr)
                    if _lyr not in rounds_plan:
                        continue
                    _old = int(rounds_plan.get(_lyr) or 1)
                    _new = max(1, _old + 1)
                    if self._control.write(
                            "rounds.%s" % _lyr, _new,
                            why="EML carve_first：该层职责不足 ⇒ "
                                "加一圈给雕（条目 %s）" % _it.get("id"),
                            trace_ref=_it.get("id")):
                        rounds_plan[_lyr] = _new
                        _done.append("%s:%d→%d" % (_lyr, _old, _new))
                if _done:
                    _it["applied"] = True
                    _applied.append({"id": _it["id"], "key": _key,
                                     "layers": _done})
            elif _key == "tri_advisory_only":
                # ★ [学了要做 · 与调度融合] 三态一致率低 ⇒ **该题型的三态读数
                #   不可当判据** ⇒ 把**职责下限上调一档**（要得更严，别信松判据）。
                _cur = float(getattr(self, "_duty_floor", 0.0) or 0.0)
                _new_fl = round(min(1.0, (_cur if _cur > 0 else 0.35) * 1.15), 4)
                if self._control.write(
                        "duty_floor", _new_fl,
                        why="EML tri_advisory_only：三态一致率低 ⇒ "
                            "判据不可信 ⇒ 上调职责下限（条目 %s）" % _it.get("id"),
                        trace_ref=_it.get("id")):
                    self._duty_floor = _new_fl
                    _it["applied"] = True
                    _applied.append({"id": _it["id"], "key": _key,
                                     "floor": _new_fl})
            elif _key == "note_cost_no_gain":
                # ★ [学了要做 · 与调度融合] 成本高于历史 p75 而职责未升
                #   ⇒ **降本**：把**层圈数各减一圈**（最直接的一刀，且可逆）。
                _done2 = []
                for _lyr in sorted(rounds_plan):
                    _old = int(rounds_plan.get(_lyr) or 1)
                    _new = max(1, _old - 1)
                    if _new == _old:
                        continue
                    if self._control.write(
                            "rounds.%s" % _lyr, _new,
                            why="EML note_cost_no_gain：成本高于 p75 而职责未升 "
                                "⇒ 减一圈（条目 %s）" % _it.get("id"),
                            trace_ref=_it.get("id")):
                        rounds_plan[_lyr] = _new
                        _done2.append("%s:%d→%d" % (_lyr, _old, _new))
                if _done2:
                    _it["applied"] = True
                    _applied.append({"id": _it["id"], "key": _key,
                                     "layers": _done2})'''

# ── B：豁免表清空（不再有「只记录不做」）──
OLD_EX = '''_EML_RECORD_ONLY = {
    "tri_advisory_only":
        "证据类：记「三态只做建议」这个事实，本身不是动作（无可执行面）",
    "note_cost_no_gain":
        "证据类：成本账（花了钱没增益），供人/AutoTune 读，不自动调参",
    "carve_first":
        "跨跑类：它要的是「**下一跑**这些层优先雕」，而本引擎没有跨跑调度"
        "接口（跨跑建议走 AutoTune 的建议文件，红线：建议与执行分开）"
        "⇒ 硬接会变成「在一次跑中途改另一件事的优先级」，语义不对",
}'''
NEW_EX = '''_EML_RECORD_ONLY = {}
#   ★ **现在是空的** —— 原先登记在这里的 3 个 key（`carve_first` /
#     `tri_advisory_only` / `note_cost_no_gain`）**已全部接线**（按用户口径
#     「学了要做，与调度层融合」）：见 `_eml_apply` 里对应的三个分支，
#     它们分别改 `rounds_plan` 与 `_duty_floor` —— 都是**本跑真正会读**的量。
#   ★ 保留这个空表：将来若真有「只记录、不做」的 key，仍登记在这里并写清原因
#     （判据两向对账会查「过期登记」）。'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new, tag in ((OLD, NEW, "A _eml_apply 扩分支"),
                          (OLD_EX, NEW_EX, "B 豁免表清空")):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（应为 1）" % (tag, n)
        s = s.replace(old, new, 1)
    # 自检：5 个分支齐
    _ap = s[s.find("def _eml_apply"):s.find("def ", s.find("def _eml_apply") + 10)]
    for _k in ("rounds_delta", "duty_floor", "carve_first",
               "tri_advisory_only", "note_cost_no_gain"):
        assert '_key == "%s"' % _k in _ap, "缺分支 %s" % _k
    assert "_EML_RECORD_ONLY = {}" in s
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK EML 五分支已接线（豁免表清空）；行数 %d" % out.count(b"\n"))


main()
