# -*- coding: utf-8 -*-
"""V2.2.11 -> V2.2.12：四层目标读数的「结构性读不出」修复。

实测证据（213 个产物包普查）
----------------------------
层          跑了     verdict空   值分布
修行(0)     213      211        0.000/0.000/0.000, n=2
研究(1)     211      19*        0.333/1.000/1.000, n=192   (*8 为旧引擎产物)
对撞(both)  198      2          0.036/0.622/0.940, n=196
元(all)     198      0          0.500/1.000/1.000, n=198 → 195 个 1.000

四个问题：
1. 修行层读数通道**结构性断路**：`_lg_aspect_margin` 要求 ≥3 点，而默认
   soft_max=2 圈只给 2 点 ⇒ 永远 None ⇒ verdict 空。
2. docstring 承诺「无 hist ⇒ 1/(1+total) 单点估计 + basis 标注」——实现里
   `total` 参数被完全忽略、basis 从未设置（承诺与代码不符，且单点估计本身
   是编造读数）。
3. verdict 空时**无法区分「算不出」与「没算」**（goal_now 也没有出口）。
4. 元层 crystallize 天花板效应：「四件事非空即满分」⇒ 195/198 = 1.000，
   读数零区分度。

改动（全部加性，历史读数语义不变）：
  A. `_lg_aspect_margin`：恰 2 点 ⇒ (V2−V1)/V1（2pt 口径）；V1<=0 ⇒ None
     （「没东西可挖」≠「挖尽」）；≤1 点 ⇒ None；docstring 改为诚实描述。
  B. 修行层读数加 `excavate_basis`（halves/2pt/None）与 `n_hist`。
  C. 新纯函数 `_lg_unmeasured_why`：读数算不出时按层给**可指认原因**。
  D. 收尾 verdict：跑了就必有说法 —— 有值给值，没值给「未测出（具体原因）」。
  E. View 新增 `goal_now` 字段 + to_dict 出口（读数明细落盘）。
  F. 元层加 `crystallize_detail`（每件事的量，纯增量）。

行为变化（有意、有据、留痕）：修行层停因「Heaps 挖尽」此前结构性不可达
（excavate 恒 None），2pt 口径下第 2 圈即可判停（阈值仍 0.1 + n_aspects>0）。
"""
from __future__ import annotations

from pathlib import Path

SRC = Path(r"D:\Meta-DGTF-道生三阶模型\dgtf_engine\dgtf_v2\engine\Meta-DGTF-V2.2.10.py")
SRC = Path(r"D:\Meta-DGTF-道生三阶模型\dgtf_engine\dgtf_v2\engine\Meta-DGTF-V2.2.11.py")
DST = Path(r"D:\Meta-DGTF-道生三阶模型\dgtf_engine\dgtf_v2\engine\Meta-DGTF-V2.2.12.py")

data = SRC.read_bytes()
crlf, lf = data.count(b"\r\n"), data.count(b"\n")
assert crlf == lf, "源文件不是纯 CRLF：crlf=%d lf=%d" % (crlf, lf)
src = data.decode("utf-8").replace("\r\n", "\n")
print("read: %s | lines=%d" % (SRC.name, src.count("\n") + 1))

edits = []

# ---- 1. 版本号 ----
edits.append(("Meta-DGTF-道生三阶模型 · V2.2.11",
              "Meta-DGTF-道生三阶模型 · V2.2.12", 1))
edits.append(('__version__ = "2.2.11"', '__version__ = "2.2.12"', 1))

# ---- 2. docstring 补丁段 ----
a = "★ V2.2.11 补丁（就绪原因的出口补齐 + 兜底）：`answer_ready_reason` 此前只写进"
b = (
    "★ V2.2.12 补丁（四层目标读数的「结构性读不出」）：实测 213 包里修行层\n"
    "     goal_verdict 211 个空白 —— `_lg_aspect_margin` 要求 ≥3 个逐圈点，而默认\n"
    "     soft_max=2 圈只给 2 点 ⇒ 读数永远 None。现在恰 2 点用 (V2−V1)/V1 的\n"
    "     2pt 口径（带 `excavate_basis` 标注，不与 halves 混口径）；verdict 恒非空\n"
    "     （算不出给**可指认**的未测出原因，不再是空串）；`goal_now` 读数明细\n"
    "     落盘出口；元层加 `crystallize_detail`（195/198 个 crystallize=1.000 的\n"
    "     天花板效应下，保留语义、另给每件事的量）。\n"
    "★ V2.2.11 补丁（就绪原因的出口补齐 + 兜底）：`answer_ready_reason` 此前只写进"
)
edits.append((a, b, 1))

# ---- 3. _lg_aspect_margin：2pt 口径 + 诚实 docstring ----
a = '''    · 无 hist（老产物）⇒ 退回「单点估计」：`1/(1+total)` 的**下限形态**，
      并**显式标注** `basis="fallback"`，不冒充逐圈读数。
    · 两条都没有 ⇒ None（**不是 0** —— 「没测」与「测出是 0」两回事）。
    """
    xs = [float(x) for x in (hist or []) if x is not None]
    if len(xs) >= 3:
        gains = [max(0.0, xs[i] - xs[i - 1]) for i in range(1, len(xs))]
        if not gains:
            return None
        half = max(1, len(gains) // 2)
        late = sum(gains[-half:]) / float(half)
        early = sum(gains[:half]) / float(half)
        if early <= 1e-12:
            return 0.0 if late <= 1e-12 else None
        return max(0.0, min(1.0, late / early))
    return None'''
b = '''    · len(hist) >= 3 ⇒ **halves 口径**：末段新增均值 / 上段新增均值。
    · len(hist) == 2 ⇒ **2pt 口径**：(V2−V1)/V1（最后一段新增 / 已积累存量）。
      ★ 默认 soft_max=2 圈只给 2 个点 —— 此前对 <3 点一律返回 None，实测
        213 个产物包里修行层读数 211 个空白（读数通道结构性断路）。
        ΔV/V 本身就是 Heaps 边际率，是真实读数；但口径与 halves 不同，
        由调用方写 `excavate_basis="2pt"` 标注，消费方不得混口径比较。
    · V1 <= 0（第二点时还没积累任何存量）⇒ None：相对边际无定义；
      [0,0] 是「没东西可挖」，**不是**「挖完了」—— 不冒充读数。
    · len(hist) <= 1 ⇒ None（**不是 0** —— 「没测」与「测出是 0」两回事。
      旧 docstring 承诺过 `1/(1+total)` 的单点估计，那是**编造读数**，已删；
      `total` 参数保留只为签名兼容）。
    """
    xs = [float(x) for x in (hist or []) if x is not None]
    if len(xs) >= 3:
        gains = [max(0.0, xs[i] - xs[i - 1]) for i in range(1, len(xs))]
        if not gains:
            return None
        half = max(1, len(gains) // 2)
        late = sum(gains[-half:]) / float(half)
        early = sum(gains[:half]) / float(half)
        if early <= 1e-12:
            return 0.0 if late <= 1e-12 else None
        return max(0.0, min(1.0, late / early))
    if len(xs) == 2 and xs[0] > 1e-12:
        return max(0.0, min(1.0, (xs[1] - xs[0]) / xs[0]))
    return None'''
edits.append((a, b, 1))

# ---- 4. 修行层读数：basis + n_hist ----
a = '''            d["excavate"] = _margin          # 边际新增率（越低越接近挖尽）
            d["excavate_closed"] = (None if _margin is None
                                    else round(1.0 - _margin, 4))
            d["n_aspects"] = _units'''
b = '''            d["excavate"] = _margin          # 边际新增率（越低越接近挖尽）
            d["excavate_closed"] = (None if _margin is None
                                    else round(1.0 - _margin, 4))
            # ★ 口径标注：halves（≥3 点）/ 2pt（恰 2 点）。两种口径的数值
            #   不可直接比较 —— AutoTune / 停因等消费方必须看 basis。
            d["excavate_basis"] = ("halves" if len(_hist) >= 3
                                   else ("2pt" if len(_hist) == 2 else None))
            d["n_hist"] = len(_hist)
            d["n_aspects"] = _units'''
edits.append((a, b, 1))

# ---- 5. 元层：crystallize_detail ----
a = '''            d["crystallize"] = round(_hits / float(_LG_META_MIN), 4)
            d["n_hits"] = _hits
            d["meta_clean"] = bool(_clo.get("clean")) if _clo else None'''
b = '''            d["crystallize"] = round(_hits / float(_LG_META_MIN), 4)
            d["n_hits"] = _hits
            d["meta_clean"] = bool(_clo.get("clean")) if _clo else None
            # ★ 带量子读数：实测 198 个包里 195 个 crystallize=1.000
            #   （「四件事非空即满分」的天花板效应，主读数零区分度）。
            #   crystallize 语义不变（兼容历史），另给每件事的**量**：
            #   消费方能区分「四件各 1 条」与「四件各 20 条」。
            d["crystallize_detail"] = {
                "closure": bool(_clo),
                "lookback_items": (None if not _clo
                                   else _lg_num(_clo.get("total"))),
                "engagements": len(v.get("engagements") or []),
                "suspensions": len(v.get("suspensions") or []),
            }'''
edits.append((a, b, 1))

# ---- 6. 新纯函数 _lg_unmeasured_why（插在 layer_goal_summary 之前）----
a = "def layer_goal_summary(views: dict) -> dict:"
b = '''def _lg_unmeasured_why(entry: str, d: dict) -> str:
    """[层目标] 读数算不出时的**可指认原因**（不给空串、不给「未知」）。

    ★ 实测 213 个产物包：修行层 verdict 211 个空白、研究层 8 个 —— 空白让
      读产物的人分不清「算不出」与「没算」。按层给出具体原因，让 verdict
      「跑了就必有说法」。
    """
    _d = d or {}
    _e = str(entry or "")
    if _e == "0":
        _n = int(_lg_num(_d.get("n_hist")) or 0)
        if _n <= 1:
            return ("逐圈累计序列只有 %d 点，无增益信息可估边际（至少 2 点）"
                    % _n)
        if not (_lg_num(_d.get("n_aspects")) or 0):
            return "层面累计存量为 0：没东西可挖 ≠ 已挖尽（不冒充读数）"
        return "依据不足"
    if _e == "1":
        if _d.get("non_degenerate") is False:
            return "全部子问题未答（answered=0）：确定率分母为 0"
        return "无可判定子问题（settlement.total=0）：确定率分母为 0"
    if _e == "both":
        return ("上游层面=%s、新层面=%s（融合率分母或分子为 0）"
                % (_lg_num(_d.get("n_upstream")) or 0,
                   _lg_num(_d.get("n_new")) or 0))
    if _e == "all":
        _h = int(_lg_num(_d.get("n_hits")) or 0)
        if _h:
            return ("结晶四件事只齐 %d/4（结晶/回看/决策/行动 有产物才计数）"
                    % _h)
        return "结晶四件事均无产物"
    return "依据不足"


def layer_goal_summary(views: dict) -> dict:'''
edits.append((a, b, 1))

# ---- 7. 收尾 verdict：未测出也要有说法 ----
a = '''                if _gv_f is not None:
                    view.goal_verdict = "本层目标（%s）：%s=%.3f%s" % (
                        _LG_LABELS.get(str(entry), str(entry)), _gk_f,
                        float(_gv_f), _LG_HINT.get(_gk_f, ""))
        except Exception:
            pass'''
b = '''                if _gv_f is not None:
                    view.goal_verdict = "本层目标（%s）：%s=%.3f%s" % (
                        _LG_LABELS.get(str(entry), str(entry)), _gk_f,
                        float(_gv_f), _LG_HINT.get(_gk_f, ""))
                else:
                    # ★ 跑了就要有说法：读数算不出 ⇒ verdict 写**可指认的
                    #   未测出原因**，不留空 —— 空白让人分不清「算不出」
                    #   与「没算」（实测 213 包里修行层 211 个空白）。
                    view.goal_verdict = "本层目标（%s）：%s=未测出（%s）" % (
                        _LG_LABELS.get(str(entry), str(entry)), _gk_f,
                        _lg_unmeasured_why(str(entry), _fresh))
        except Exception:
            pass'''
edits.append((a, b, 1))

# ---- 8. View 字段：goal_now ----
a = '''    goal_verdict: str = ""
    #: [停因级联] 主因（最高优先级的那条）'''
b = '''    goal_verdict: str = ""
    #: [四层目标] 本层目标读数明细（含 None：settle/excavate 等算不出时
    #:   **值是 None 但读数字典仍要落盘** —— 消费方靠它区分「算不出」
    #:   与「没算」。此前只有内存赋值、没有字段与出口）。
    goal_now: dict = field(default_factory=dict)
    #: [停因级联] 主因（最高优先级的那条）'''
edits.append((a, b, 1))

# ---- 9. to_dict：goal_now 出口 ----
a = '''        if getattr(self, "goal_verdict", ""):
            d["goal_verdict"] = str(self.goal_verdict)
        if self.covered_unders:'''
b = '''        if getattr(self, "goal_verdict", ""):
            d["goal_verdict"] = str(self.goal_verdict)
        # ★ [层目标] 读数明细出口：verdict 是一行结论，`goal_now` 是明细
        #   （含 None 与辅读数）。此前只进内存不落盘 —— 又一个单出口问题。
        #   有才出（空 dict 不出键，与 quant_readings 同纪律）。
        if getattr(self, "goal_now", None):
            d["goal_now"] = dict(self.goal_now)
        if self.covered_unders:'''
edits.append((a, b, 1))

for old, new, want in edits:
    got = src.count(old)
    assert got == want, "锚点命中 %d 次（期望 %d）：%r" % (got, want, old[:60])
    src = src.replace(old, new)
    print("  ok: %s" % old[:48].replace("\n", "\\n"))

out = src.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
assert out.count(b"\r\n") == out.count(b"\n"), "输出不是纯 CRLF"
DST.write_bytes(out)
print("written: %s | lines=%d | CRLF=%d"
      % (DST.name, out.count(b"\n") + 1, out.count(b"\r\n")))
print("PATCH OK")
