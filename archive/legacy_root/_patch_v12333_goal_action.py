# 第二期补丁（P2-1）：四层目标读数**进入圈内动作**。
# ★ 用户战略指令：「四层的目标要落实到设计中每层每圈的运行中，而不只是读数」。
#   第一期已把目标接到**停止**（层末）；第二期接到**写法**（圈内）。
#
# 设计（合规性优先）：
#   · 只产出**形状指引文本**（`_goal_hint_text`），插在 `_role_text` 之后
#     —— 那是模型最当真的位置（`【本轮形状】`块）。
#   · **不改配置、不改停止、不改停止判据、不改 role 枚举**（红线「建议与执行分开」）。
#   · 缺读数 ⇒ **返回空串**（不表态）—— 与 `layer_goal_stop_signal` 同规。
#
# 四条前沿依据（承第一期，逐条对应一条指引）：
#   0 修行 Heaps 饱和（Herdan 1960 / arXiv 1806.09419）：边际新增趋零 ⇒ 换**未挖的面**，
#     而不是继续在同一面里加深（那是"挖到不能再挖"的反面：重复挖掘）。
#   1 研究 收敛 = 确定率（非伪收敛）：settle 未达 ⇒ **优先答未答层面**，
#     避免"熵降 = 质量高"的伪收敛（Towards a Science of Collective AI 2025）。
#   2 对撞 CORE（Pandey et al., NeurIPS 2025）：sem_stagnation 高 ⇒ **罚复读**，
#     强制**换融合轴**（不是换措辞）。
#   4 元层 结晶度：四件事（闭环/回看/决策/行动）缺哪件就**补哪件**，
#     Darwin Gödel Machine（Zhang et al. 2025, arXiv:2505.22954）的 archive 思想
#     ⇒ 缺的是"把已发生的记下来"这一动作本身。
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

# ── 锚点 1：在 `layer_goal_stop_signal` 之前插入新纯函数 ──
A1 = '''def layer_goal_stop_signal(entry: str, goal: dict, prev: list = None):'''

NEW1 = '''_LG_ACT_SETTLE_LOW = 0.6      # 研究层：确定率 < 此值 ⇒ 优先答未答层面
_LG_ACT_ASPECT_MIN = 4         # 修行层：层面数 < 此值 ⇒ 还没铺够，别急着深挖


def layer_goal_action_hint(entry: str, goal: dict, prev: list = None) -> str:
    """[四层目标 → **圈内动作**] 把「本层目标读数」转成一条**形状指引**。

    ★ 与 `layer_goal_stop_signal` 的分工：
      · `stop_signal` 管**停不停**（层末，写进 `_stop_reasons`）；
      · `action_hint` 管**怎么写**（圈内，插进 prompt 的 `【本轮形状】` 之后）。
      两者**共用同一批读数**，但作用在不同时刻 —— 这就是「读数进入运行」的完整形态。

    ★ 红线遵守：
      · **缺读数 ⇒ 返回空串**（不表态）。「没测」不等于「测出来差」，
        更不能因此给模型下指令（那会把"没数据"变成"假约束"）。
      · **不返 role 名、不改 role 枚举**：只出**文本指引**，
        由 prompt 组装处拼接 ⇒ role 语义单一真相源不动。
      · **达标 ⇒ 返回空串**：目标是「做到就闭嘴」，不是「每圈都唠叨」。

    返回：一段以 `\\n\\n【本层目标的形状指引...】` 开头的文本，或空串。
    """
    g = goal or {}
    _e = str(entry or "")

    if _e == "0":
        # 修行层（趋近无穷收敛 = 把各面挖到不能再挖）
        _v = _lg_num(g.get("excavate"))
        _na = _lg_num(g.get("n_aspects"))
        if _v is not None and _v < _LG_STOP_MARGIN:
            # 边际新增趋零 ⇒ Heaps 饱和：别再往同一面里挖，换未挖的面。
            return (
                "\\n\\n【本层目标的形状指引 · 修行层趋近无穷收敛】\\n"
                "上一圈之后，**层面的边际新增已经趋零**（本圈不再是"
                "「还没挖够」，而是「这一面挖到了底」）。\\n"
                "  · 所以这一圈**不要**在已经写出来的面上继续加深——那是重复挖掘。\\n"
                "  · 要换一个**尚未显形的切面**进去（问「这个问题还有哪个面是我"
                "一次都没碰过的」）。\\n"
                "  · 若确实找不出新面，如实说「这一面已见底」，"
                "**不要**把旧面换个说法再交一次。\\n"
            )
        if _na is not None and _na < _LG_ACT_ASPECT_MIN:
            # 面还没铺够 ⇒ 别急着深挖（对应「修行 = 广度优先摊开各面」）。
            return (
                "\\n\\n【本层目标的形状指引 · 修行层趋近无穷收敛】\\n"
                "本层目前显形的层面数还很少（广度不够）。\\n"
                "  · 这一圈**优先摊开新面**，不要把少数几个面往深里挖。\\n"
                "  · 能摆出来的都摆出来，不必每条都追到底。\\n"
            )
        return ""

    if _e == "1":
        # 研究层（趋近有限收敛 = 给各面确定答案）
        _v = _lg_num(g.get("settle"))
        if _v is not None and _v < _LG_ACT_SETTLE_LOW:
            # ★ 伪收敛警告（依据：熵降 ≠ 高质量）：确定率低不等于"写得多"，
            #   而是"该定的没定"。要**优先答未答的层面**。
            return (
                "\\n\\n【本层目标的形状指引 · 研究层趋近有限收敛】\\n"
                "本层的**确定率还偏低**——已经显形的面里，还有一批没有确定答案。\\n"
                "  · 这一圈**优先给未答的面一个答案**（哪怕答案是「此处未生，"
                "缺的是 X」也算答）。\\n"
                "  · 不要把力气花在**重复论证已经定下来的面**上。\\n"
                "  · ★ 注意：写得长不等于收敛——**没定的还是不收敛**。\\n"
            )
        return ""

    if _e == "both":
        # 对撞层（融合生成）
        _st = _lg_num(g.get("sem_stagnation"))
        if _st is not None and _st >= _LG_STOP_STAG:
            # CORE 停滞罚：高停滞 ⇒ 复读，强制换**融合轴**。
            return (
                "\\n\\n【本层目标的形状指引 · 对撞层融合生成】\\n"
                "本层的**语义停滞率偏高**：这一圈产出的东西，与上游 view 的"
                "文本重合太多（像复述，不像融合）。\\n"
                "  · 这一圈**必须换一个融合轴**——不是换措辞，是换"
                "「把哪两个面撞在一起」。\\n"
                "  · 自问：上游给的这些面里，有哪两个**从没被放在一起看过**？"
                "把它们撞一次。\\n"
                "  · 撞出来的东西必须**上游任何一边单独都给不出**，否则不算融合。\\n"
            )
        _fu = _lg_num(g.get("fuse"))
        if _fu is not None and _fu < 0.3:
            return (
                "\\n\\n【本层目标的形状指引 · 对撞层融合生成】\\n"
                "本层的融合产出偏少（新东西不多）。\\n"
                "  · 别停在「两边的共同点」上——那只叫对齐，不叫融合。\\n"
                "  · 去看**两边互相矛盾的地方**，矛盾处才有真融合。\\n"
            )
        return ""

    if _e == "all":
        # 元层（记忆结晶 / 决策 / 行动 / 回看）
        _cr = _lg_num(g.get("crystallize"))
        _hits = _lg_num(g.get("n_hits"))
        if _cr is not None and _cr < 1.0:
            _miss = []
            if _hits is not None:
                # n_hits < 4 ⇒ 四件事里有缺的（顺序对应 layer_goal_readings 的累加序）
                if _hits < 1:
                    _miss.append("闭环清算（把张力盘一遍、看有没有漏交代的）")
                if _hits < 2:
                    _miss.append("回看（说清本层一共处理了多少张力）")
                if _hits < 3:
                    _miss.append("决策（把能裁的裁掉，不能裁的写清缺什么）")
                if _hits < 4:
                    _miss.append("行动/交代（每一条悬置都要有去处）")
            _miss_txt = ("；".join(_miss) if _miss
                         else "四件事里还缺的那件")
            return (
                "\\n\\n【本层目标的形状指引 · 元层记忆结晶】\\n"
                "本层是**元层**：要对下面三层的产物做记忆结晶 / 决策 / 行动，"
                "并回看整个过程。现在还没结晶完整。\\n"
                f"  · 这一圈优先补上：**{_miss_txt}**。\\n"
                "  · 结晶不是「再想一遍」，是**把已经发生的事记下来**"
                "（依据 DGM：archive 的价值在不丢东西，而不是再搜一遍）。\\n"
                "  · 缺的如果补不上，如实标成悬置——**不许拿 both 搪塞**。\\n"
            )
        return ""

    return ""


def layer_goal_stop_signal(entry: str, goal: dict, prev: list = None):'''

# ── 锚点 2：`_goal_action_hint` 方法（放在 `_goal_stop_signal` 之后） ──
A2 = '''        _now = _tr[-1] if _tr else {}
        return layer_goal_stop_signal(str(entry), _now, _tr)
'''

NEW2 = '''        _now = _tr[-1] if _tr else {}
        return layer_goal_stop_signal(str(entry), _now, _tr)

    def _goal_action_hint(self, entry: str, view) -> str:
        """[四层目标 → 圈内动作] 读 `view.goal_trace`，返回本圈的**形状指引**。

        ★ 与 `_goal_stop_signal` 读**同一个** `goal_trace`（同一把尺子），
          但作用在**圈内**（写进 prompt）而不是层末（写进停因）。
        """
        _tr = list(getattr(view, "goal_trace", None) or [])
        _now = _tr[-1] if _tr else {}
        try:
            return layer_goal_action_hint(str(entry), _now, _tr)
        except Exception:
            return ""

    def _refresh_goal_hint(self, entry: str, view) -> str:
        """把本圈目标读数转成**下一圈要用的形状指引**，写到 `self._goal_hint_next`。

        ★ 为什么叫「下一圈」：`_layer_goal_now` 是在**每圈结束时**调的，
          所以此刻算出来的指引自然作用于**下一圈的 prompt**。
          ⇒ 第二期**零新增接线点**（复用第一期的两处 `_layer_goal_now`）。
        ★ 本层最后一圈算出来的指引会被丢弃（没有下一圈了）——这不丢信息，
          因为它对应的`停/不停`由第一期的 `_goal_stop_signal` 负责。
        """
        try:
            _h = self._goal_action_hint(entry, view)
        except Exception:
            _h = ""
        try:
            self._goal_hint_next = str(_h or "")
        except Exception:
            pass
        return str(_h or "")
'''

# ── 锚点 3/4：两条 prompt 路径接线 ──
A3 = '''        def build_user(label):
            return (
                f"{carry_block}\\n"
                f"【原始问题】\\n{question}\\n\\n"
                f"【锚点重述】\\n{anchor}\\n"
                f"{self._role_text(role, round_no)}\\n"
                f"{dec_block}\\n\\n"'''
NEW3 = '''        def build_user(label):
            return (
                f"{carry_block}\\n"
                f"【原始问题】\\n{question}\\n\\n"
                f"【锚点重述】\\n{anchor}\\n"
                f"{self._role_text(role, round_no)}\\n"
                f"{goal_hint}\\n"
                f"{dec_block}\\n\\n"'''

A4 = '''        def build_user(label):
            return (
                f"{carry_block}\\n"
                f"{anchor_block}\\n"
                f"{self._role_text(role, round_no)}\\n"
                f"{dec_block}\\n\\n"'''
NEW4 = '''        def build_user(label):
            return (
                f"{carry_block}\\n"
                f"{anchor_block}\\n"
                f"{self._role_text(role, round_no)}\\n"
                f"{goal_hint}\\n"
                f"{dec_block}\\n\\n"'''

# ── 锚点 5/6：两处 `goal_hint` 的读取（各自 build_user 之前） ──
#   ★ 设计：提示**不在这里现算**，而是读 `self._goal_hint_next`
#     —— 它在上一圈的 `_layer_goal_now` 处写定（那条路径**已有接线**，
#     第二期因此**零新增接线点**，与第一期「复用链」的做法一致）。
A5 = '''        def build_user(label):
            return (
                f"{carry_block}\\n"
                f"【原始问题】\\n{question}\\n\\n"'''
NEW5 = '''        goal_hint = str(getattr(self, "_goal_hint_next", "") or "")

        def build_user(label):
            return (
                f"{carry_block}\\n"
                f"【原始问题】\\n{question}\\n\\n"'''

A6 = '''        def build_user(label):
            return (
                f"{carry_block}\\n"
                f"{anchor_block}\\n"'''
NEW6 = '''        goal_hint = str(getattr(self, "_goal_hint_next", "") or "")

        def build_user(label):
            return (
                f"{carry_block}\\n"
                f"{anchor_block}\\n"'''

# ── 锚点 7/8：两处 `_layer_goal_now` 之后刷新「下一圈指引」 ──
A7 = '''            self._layer_goal_now(entry, view)
            _goal_hit, _goal_why = self._goal_stop_signal(entry, view)'''
NEW7 = '''            self._layer_goal_now(entry, view)
            self._refresh_goal_hint(entry, view)
            _goal_hit, _goal_why = self._goal_stop_signal(entry, view)'''

# ── 锚点 9：实例初始化（与 `_goal_hint_next` 同源，防 AttributeError） ──
A9 = '''        self.self_memory = ""
        self.sp = sp if sp is not None else _spiral_for(config, entry)'''
NEW9 = '''        self.self_memory = ""
        # ★ [四层目标·第二期] 上一圈算出的**下一圈形状指引**（空串 = 不表态）。
        #   初始为空 ⇒ 第 1 圈不带指引（那时也确实还没有读数）。
        self._goal_hint_next = ""
        self.sp = sp if sp is not None else _spiral_for(config, entry)'''


def _apply(text, anchor, new, tag):
    n = text.count(anchor)
    if n != 1:
        print("X %s 锚点命中 %d 次" % (tag, n)); sys.exit(1)
    return text.replace(anchor, new, 1)


def main():
    b = SRC.read_bytes()
    txt = b.decode("utf-8")
    if txt.count("\r\n") != txt.count("\n") or "\r\r\n" in txt:
        print("X 非纯 CRLF"); sys.exit(1)
    s = txt.replace("\r\n", "\n")
    for a, n_, tag in [(A1, NEW1, "A1"), (A2, NEW2, "A2"),
                       (A9, NEW9, "A9"),
                       (A3, NEW3, "A3"), (A4, NEW4, "A4"),
                       (A5, NEW5, "A5"), (A6, NEW6, "A6"),
                       (A7, NEW7, "A7")]:
        s = _apply(s, a, n_, tag)
    out = s.replace("\n", "\r\n").encode("utf-8")
    if out.decode("utf-8").count("\r\r\n"):
        print("X r-r-n"); sys.exit(1)
    SRC.write_bytes(out)
    print("OK 第二期补丁 P2-1 已打（8 锚点）")


if __name__ == "__main__":
    main()

