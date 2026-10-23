# -*- coding: utf-8 -*-
"""[v1.22.2 P1] P4 OFF 臂口径统一 —— 打补丁脚本（唯一事实源）。

设计（据 _taskbook_audit_v1222.md 的 #3/#4/#5 改过，不照抄任务书）：
  · 口径：单票 stability = 单票 vs 拆解原标签；多票 = 票间一致度。
  · 弃权条（判决官未返回该条）**显式**记 `abstained`，不混进 high/low。
  · stability 必须在**每个出口前**写（单票有 5 处早退 return 0,0）。
  · 头部按 `_vote_mode` **多数**取值，分母只数已判条。
幂等：已改则整脚本跳过（哨兵串）。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.2.py"
SENTINEL = "[v1.22.2 P1]"

src_bytes = TARGET.read_bytes()
src = src_bytes.decode("utf-8")
if src.count("\r\n") != src.count("\n"):
    print("!! 源文件不是纯 CRLF，中止"); sys.exit(1)
src = src.replace("\r\n", "\n")
if SENTINEL in src:
    print("== 已打过 v1.22.2 P1 补丁，跳过 =="); sys.exit(0)


def sub_once(text, old, new, tag):
    n = text.count(old)
    assert n == 1, f"[{tag}] 锚点出现 {n} 次（应为 1）"
    return text.replace(old, new)


# ---------------------------------------------------------------- A. 模块级口径函数
A_OLD = (
    'def _extract_actions(view) -> list:\n'
    '    """优先读 schema 产出的 actions；schema 缺失时才回退词法抽取。'
)
A_NEW = (
    'def _single_vote_stability(sq: dict) -> str:\n'
    '    """[v1.22.2 P1] 单票路径的 stability 口径，与多票路径**同层级可比**。\n'
    '\n'
    '    · 该条未被判决（判决官弃权）→ "abstained"（**不参与**一致率统计）\n'
    '    · 与拆解原标签一致          → "high"\n'
    '    · 不一致                    → "low"\n'
    '    · 有判决但无原标签          → "medium"\n'
    '\n'
    '    ★ 与多票路径的 `stability` **不是同一把尺子**（多票那份量的是\n'
    '      「三票之间」）。两者都叫 stability 但必须按 `_vote_mode` 分口径读，\n'
    '      头部标题会印出当前口径 —— 拿两臂的数直接比会得到错结论。\n'
    '    """\n'
    '    if not sq.get("_tri_judged"):\n'
    '        return "abstained"\n'
    '    first = str(sq.get("first_label", "") or "").strip().lower()\n'
    '    curr = str(sq.get("decidability", "") or "").strip().lower()\n'
    '    if not first:\n'
    '        return "medium"\n'
    '    return "high" if first == curr else "low"\n'
    '\n'
    '\n'
    + A_OLD
)
src = sub_once(src, A_OLD, A_NEW, "A")

# ---------------------------------------------------------------- B. 写 stability 的方法
B_OLD = (
    '    # ---------- [v122 阶段2 G2.1/G2.2] 三态多票判决 ----------\n'
    '    def _adjudicate_sub_tristate_multi(self, subs: List[dict],\n'
)
B_NEW = (
    '    def _write_tri_stability(self, subs, mode: str, from_votes: bool) -> None:\n'
    '        """[v1.22.2 P1] 给**每一条** sub 写 `stability` + `_vote_mode`。\n'
    '\n'
    '        · from_votes=False（单票）：口径 = 单票 vs 拆解原标签；\n'
    '        · from_votes=True（多票）：票间口径已由判决循环写好，不动，\n'
    '          只补「未被判到」的那些条。\n'
    '        · 未被判到的条 → "abstained"（判决官弃权），**不**混进 high/low。\n'
    '\n'
    '        ★ 必须在**每个出口前**调用。单票实现有 5 处早退 `return 0, 0`，\n'
    '          只写在尾部会让「判决失败」这一情形在产物里彻底读不到\n'
    '          —— 那正是 v1.22.1 P4 那个 bug 的同类形态。\n'
    '        """\n'
    '        for s in subs:\n'
    '            if not isinstance(s, dict):\n'
    '                continue\n'
    '            s["_vote_mode"] = mode\n'
    '            if not s.get("_tri_judged"):\n'
    '                s["stability"] = "abstained"\n'
    '            elif not from_votes:\n'
    '                s["stability"] = _single_vote_stability(s)\n'
    '\n'
    '    # ---------- [v122 阶段2 G2.1/G2.2] 三态多票判决 ----------\n'
    '    def _adjudicate_sub_tristate_multi(self, subs: List[dict],\n'
)
src = sub_once(src, B_OLD, B_NEW, "B")

# ---------------------------------------------------------------- C. 单票：标 _tri_judged
C_OLD = (
    '            s["first_label"] = old\n'
    '            if new == old:\n'
)
C_NEW = (
    '            s["_tri_judged"] = True\n'
    '            s["first_label"] = old\n'
    '            if new == old:\n'
)
src = sub_once(src, C_OLD, C_NEW, "C")

# ---------------------------------------------------------------- D. 单票 5 处出口前写
D1_OLD = (
    '        except Exception as e:\n'
    '            logger.warning("三态独立判决失败（保留拆解原标签）: %s", e)\n'
    '            return 0, 0\n'
)
D1_NEW = (
    '        except Exception as e:\n'
    '            logger.warning("三态独立判决失败（保留拆解原标签）: %s", e)\n'
    '            self._write_tri_stability(subs, "single", False)\n'
    '            return 0, 0\n'
)
src = sub_once(src, D1_OLD, D1_NEW, "D1")

D2_OLD = (
    '            logger.warning("三态独立判决 JSON 解析异常（保留原标签）: %s", e)\n'
    '            return 0, 0\n'
)
D2_NEW = (
    '            logger.warning("三态独立判决 JSON 解析异常（保留原标签）: %s", e)\n'
    '            self._write_tri_stability(subs, "single", False)\n'
    '            return 0, 0\n'
)
src = sub_once(src, D2_OLD, D2_NEW, "D2")

D3_OLD = (
    '            logger.warning("三态独立判决返回非对象（%s，保留原标签）",\n'
    '                           type(_parsed).__name__)\n'
    '            return 0, 0\n'
)
D3_NEW = (
    '            logger.warning("三态独立判决返回非对象（%s，保留原标签）",\n'
    '                           type(_parsed).__name__)\n'
    '            self._write_tri_stability(subs, "single", False)\n'
    '            return 0, 0\n'
)
src = sub_once(src, D3_OLD, D3_NEW, "D3")

D4_OLD = (
    '            logger.warning("三态独立判决返回空（保留拆解原标签）")\n'
    '            return 0, 0\n'
)
D4_NEW = (
    '            logger.warning("三态独立判决返回空（保留拆解原标签）")\n'
    '            self._write_tri_stability(subs, "single", False)\n'
    '            return 0, 0\n'
)
src = sub_once(src, D4_OLD, D4_NEW, "D4")

D5_OLD = (
    '        self.vp(f"   🎯 三态独立判决：{agree}/{n} 一致"\n'
    '                f"（{n - agree} 条分歧落 partial）")\n'
    '        return agree, n\n'
)
D5_NEW = (
    '        self.vp(f"   🎯 三态独立判决：{agree}/{n} 一致"\n'
    '                f"（{n - agree} 条分歧落 partial）")\n'
    '        self._write_tri_stability(subs, "single", False)\n'
    '        return agree, n\n'
)
src = sub_once(src, D5_OLD, D5_NEW, "D5")

# ---------------------------------------------------------------- E. 多票：标 judged + 2 处出口
E1_OLD = (
    '            s["_tri_final"] = s["decidability"]\n'
)
E1_NEW = (
    '            s["_tri_judged"] = True\n'
    '            s["_tri_final"] = s["decidability"]\n'
)
src = sub_once(src, E1_OLD, E1_NEW, "E1")

E2_OLD = (
    '            logger.warning("三态多票：三票全失败 → 保留拆解原标签")\n'
    '            return 0, 0\n'
)
E2_NEW = (
    '            logger.warning("三态多票：三票全失败 → 保留拆解原标签")\n'
    '            self._write_tri_stability(subs, "multi", True)\n'
    '            return 0, 0\n'
)
src = sub_once(src, E2_OLD, E2_NEW, "E2")

E3_OLD = (
    '                f"与拆解原标签一致 {agree}/{n}）")\n'
    '        return agree, n\n'
)
E3_NEW = (
    '                f"与拆解原标签一致 {agree}/{n}）")\n'
    '        self._write_tri_stability(subs, "multi", True)\n'
    '        return agree, n\n'
)
src = sub_once(src, E3_OLD, E3_NEW, "E3")

# ---------------------------------------------------------------- F. 头部渲染分口径
F_OLD = (
    '            # [v122 阶段2b] 任务书 Step 2.5 口径：按逐条 `stability` 统计。\n'
    '            _sq1 = ((result.get("pools") or {}).get("1") or {}).get(\n'
    '                "sub_questions") or []\n'
    '            _hi = sum(1 for s in _sq1 if s.get("stability") == "high")\n'
    '            _me = sum(1 for s in _sq1 if s.get("stability") == "medium")\n'
    '            _lo = sum(1 for s in _sq1 if s.get("stability") == "low")\n'
    '            if _sq1:\n'
    '                _rate = (_hi + _me) / max(1, len(_sq1))\n'
    '                _flag = "" if _rate >= 0.5 else "\u3000⚠️ unstable（＜50%）"\n'
    '                f.write(f"**三态多票**：high {_hi} / medium {_me} / low {_lo}"\n'
    '                        f"（共 {len(_sq1)} 条）\u3000一致率 {_rate:.0%}{_flag}\\n")\n'
)
F_NEW = (
    '            # [v1.22.2 P1] 按逐条 `stability` 统计，**按 `_vote_mode` 分口径**。\n'
    '            #   ★ 旧版（v1.22.1）无条件印「三态多票：high/medium/low …\n'
    '            #     一致率 0% ⚠️ unstable」—— 单票路径根本不写 stability，\n'
    '            #     于是**非读数被当成测量值**。现在：口径印在标题里，\n'
    '            #     分母只数已判条，弃权条单列。\n'
    '            _sq1 = ((result.get("pools") or {}).get("1") or {}).get(\n'
    '                "sub_questions") or []\n'
    '            _hi = sum(1 for s in _sq1 if s.get("stability") == "high")\n'
    '            _me = sum(1 for s in _sq1 if s.get("stability") == "medium")\n'
    '            _lo = sum(1 for s in _sq1 if s.get("stability") == "low")\n'
    '            _ab = sum(1 for s in _sq1\n'
    '                      if s.get("stability") == "abstained")\n'
    '            _voted = _hi + _me + _lo\n'
    '            if _sq1:\n'
    '                _cm: Dict[str, int] = {}\n'
    '                for s in _sq1:\n'
    '                    _m = str(s.get("_vote_mode") or "?")\n'
    '                    _cm[_m] = _cm.get(_m, 0) + 1\n'
    '                _mode = max(_cm, key=lambda k: _cm[k])\n'
    '                _label = {"single": "单票", "multi": "多票"}.get(\n'
    '                    _mode, "口径未知")\n'
    '                _cal = {"single": "单票 vs 拆解原标签",\n'
    '                        "multi": "三票之间"}.get(_mode, "未知")\n'
    '                if _voted:\n'
    '                    _rate = (_hi + _me) / _voted\n'
    '                    _flag = ("" if _rate >= 0.5\n'
    '                             else "\u3000⚠️ unstable（＜50%）")\n'
    '                    _line = (f"**三态判决（{_label}）**：high {_hi} / "\n'
    '                             f"medium {_me} / low {_lo}"\n'
    '                             f"（已判 {_voted} 条）\u3000"\n'
    '                             f"一致率 {_rate:.0%}{_flag}")\n'
    '                else:\n'
    '                    _line = (f"**三态判决（{_label}）**：无可判读数"\n'
    '                             f"（判决官未返回任何一条）")\n'
    '                if _ab:\n'
    '                    _line += f"\u3000弃权 {_ab} 条"\n'
    '                f.write(_line + f"\u3000口径={_cal}"\n'
    '                        f"（共 {len(_sq1)} 条）\\n")\n'
)
src = sub_once(src, F_OLD, F_NEW, "F")

# ---------------------------------------------------------------- 写回
assert src.count("\n") == src.count("\r\n") or "\r\n" not in src
out = src.replace("\n", "\r\n")
b = out.encode("utf-8")
assert b.count(b"\r\n") == b.count(b"\n")
assert b.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert b.count(b"\r") == b.count(b"\r\n"), "出现裸 CR"
TARGET.write_bytes(b)
print("OK: v1.22.2 P1 补丁已写入")
print("  新增符号：_single_vote_stability / MetaDGTF._write_tri_stability")
print("  出口前写 stability：单票 5 处 + 多票 2 处")
