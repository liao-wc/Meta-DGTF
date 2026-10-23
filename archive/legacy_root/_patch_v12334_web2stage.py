# -*- coding: utf-8 -*-
"""v1.23.34：给 `practice_term_calibration` / `stop_criteria` **接线**。

## 用户指令
「修行层联网/停止判据联网这两个也可通过开关进行作用。」
⇒ 现状是「配了不做」（键存在、**代码里没有调用点**、登记在 `_AUDIT_CONFIG_EXEMPT`）；
   要改成「**默认不做、显式打开就真做**」。

## 为什么不违反红线
yaml 原话：「修行层与停止判据**默认关** —— **修行层联网会污染『输入是形状不是
数据』这条宪法级特性**」。红线保护的是「**默认**不污染」⇒ 出厂仍 false、
判定路径不变，只在开关打开时**多检索一次并留痕**。

## 两处接线（都挂在**两条通道共用的统一实现**上）
  A. `practice_term_calibration` → `_before_round`（圈前统一动作；
     注释明说「做成一个方法而不是在两处各写一份」）。**只在前置**（第一圈前）。
  B. `stop_criteria` → `_finalize_layer_common`（两条跑圈通道共用的收尾）。

## 红线守卫（写进代码注释，并配变异体）
  · A **不注入**修行层的展开 prompt —— 修行层输入**必须**只有形状；
    产物只进 pool（W# 编号）+ 产物留痕，供人复核、供后续层按需引用。
  · B **不改停止决策** —— 只回答「这个理由有没有明显反证」，
    决策仍由原判据做（留痕 vs 拦截的分界）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

# ── A1：`_WEB_USED_AS` 加两个枚举值 ──
OLD_USED = '''_WEB_USED_AS = ("evidence", "record", "arbitration", "clean_check", "tri_vote")'''
NEW_USED = '''_WEB_USED_AS = ("evidence", "record", "arbitration", "clean_check", "tri_vote",
                # ★ 两个「默认不做、显式打开才做」的 stage 的用途标记
                #   （有判据钉「不得出现未登记取值」⇒ 接线必须同步登记）。
                "term_calibration", "stop_criteria")'''

# ── A2：豁免清单清空（它们不再是「声明了不做」）──
OLD_EXEMPT = '''_AUDIT_CONFIG_EXEMPT = (
    "web_search.stages.practice_term_calibration",
    "web_search.stages.stop_criteria",
)
#   声明了「不做」的配置键（任务书 §七：不做修行层联网、不做停止判据联网）。
#   它们**永远不会**被 `_web_search(stage=...)` 调用到 ⇒ 属「声明了不做」，
#   不是漏接线。登记在这里，两向对账防它悄悄变成真装饰品。'''
NEW_EXEMPT = '''_AUDIT_CONFIG_EXEMPT = ()
#   原先这里登记着 `web_search.stages.practice_term_calibration` 与
#   `stop_criteria`，理由写的是「声明了**不做**」（任务书 §七）。现按用户口径
#   改为「**默认不做、显式打开就真做**」⇒ 两者**已接线**（见
#   `_practice_term_calibration_prep` / `_stop_criteria_check`），
#   不再是「配了不读」⇒ 豁免取消（两向对账自动回到「有键必有读点」）。
#   ★ 保留本常量（空元组）以免审计侧代码要改；将来若真有「声明不做」的键，
#     仍登记在这里并写清原因。'''

# ── A3：新增「修行层术语校准」方法（放在 `_research_web_prep` 之前）──
ANCHOR_FN = '''    def _research_web_prep(self, question: str, _unused: int = 0) -> str:'''
NEW_FN = '''    def _practice_term_calibration_prep(self) -> None:
        """[修行层联网] 术语校准 —— **默认关；显式打开才做**。

        ★ 为什么出厂默认关：修行层的宪法级特性是「**输入是形状不是数据**」，
          联网会把它污染成「数据驱动」。默认关 = 保护不动。
        ★ 打开后**也只做一半**：本方法的产物**只进 pool（W# 编号）+ 产物留痕**，
          **绝不注入**修行层的展开 prompt —— 修行层看到的仍然只有锚点与池。
          它回答的是「题面里的术语在这个领域通常指什么」，供**人**复核、
          供**后续层**按需引用（后续层本就有引用通道）。
        ★ `enabled=False` 或 stage 未授权 ⇒ `_web_search` 直接返回 []，
          **一次 Gate 都不判**（零调用是可验证的）。
        """
        if not bool((self.config.get("web_search") or {}).get("enabled")):
            return
        _q = str(getattr(self, "_question", "") or "").strip()
        if not _q:
            return
        self._web_prep_seq = int(getattr(self, "_web_prep_seq", 0) or 0) + 1
        # 前置：圈号传 0、序号走 pre_seq（与 `research_decompose` 同规矩）。
        _qs = [f"{_q[:120]} 术语 定义 含义",
               f"{_q[:120]} 关键词 概念 边界"]
        try:
            self._web_search("practice_term_calibration", _qs, 0,
                             used_as="term_calibration",
                             pre_seq=self._web_prep_seq)
        except Exception as _e_tc:  # noqa: BLE001
            logger_web.warning("[W-TERM-CAL] 术语校准失败：%s", _e_tc)

    def _stop_criteria_check(self, entry: str, view) -> None:
        """[停止判据联网] 停止理由复核 —— **默认关；显式打开才做**。

        ★ 它**不改停止决策**（留痕 vs 拦截的分界）：只回答「这个理由有没有
          明显反证」，结论进 pool + 产物；决策仍由原判据做。
        ★ 只在**真的停了**（`view.stop_reason` 非空）时做 —— 没停就没有可复核的。
        """
        if not bool((self.config.get("web_search") or {}).get("enabled")):
            return
        _sr = str(getattr(view, "stop_reason", "") or "").strip()
        if not _sr:
            return
        _q = str(getattr(self, "_question", "") or "").strip()
        self._web_prep_seq = int(getattr(self, "_web_prep_seq", 0) or 0) + 1
        _qs = [f"{_q[:100]} {_sr[:80]} 反证",
               f"{_q[:100]} 是否已经 {_sr[:80]}"]
        try:
            self._web_search("stop_criteria", _qs, 0,
                             used_as="stop_criteria",
                             pre_seq=self._web_prep_seq)
        except Exception as _e_sc:  # noqa: BLE001
            logger_web.warning("[W-STOP-CRIT] 判据复核失败：%s", _e_sc)

    def _research_web_prep(self, question: str, _unused: int = 0) -> str:'''

# ── A4：`_before_round` 接线（前置一次；圈号 1 才触发）──
OLD_BR = '''        self._print_polarity_snapshot(pool, entry, layer_no)
        self._anchor_round(entry, pool, layer_no - 1)
'''
NEW_BR = '''        self._print_polarity_snapshot(pool, entry, layer_no)
        self._anchor_round(entry, pool, layer_no - 1)
        # ★ [修行层联网] 术语校准：**只在前置**（本层第一圈之前）做一次。
        #   挂在 `_before_round` 上是因为它是**两条跑圈通道共用的唯一实现**
        #   （serial 与 B/C 都走这里）—— 在两处各写一份必然分叉（本项目已 7 次）。
        #   ★ 默认关 ⇒ 一次 Gate 都不判；打开后产物只进 pool + 留痕，
        #     **不注入**修行层的展开 prompt（红线：输入是形状不是数据）。
        if entry == "0" and int(layer_no or 0) == 1:
            try:
                self._practice_term_calibration_prep()
            except Exception as _e_tc2:  # noqa: BLE001
                logger_web.warning("[W-TERM-CAL] 调用失败：%s", _e_tc2)
'''

# ── A5：`_finalize_layer_common` 末尾接线 ──
OLD_FIN = '''        try:
            _dg.verbose = self.verbose
            _dg.dump_final(view)
        except Exception as _e:
            self.vp(f"   ✗ 收尾留痕失败：{type(_e).__name__}: {_e}")
'''
NEW_FIN = '''        try:
            _dg.verbose = self.verbose
            _dg.dump_final(view)
        except Exception as _e:
            self.vp(f"   ✗ 收尾留痕失败：{type(_e).__name__}: {_e}")

        # ★ [停止判据联网] 停止理由复核：**默认关**；打开后只留痕、不改决策。
        #   放在本函数末尾是因为此刻 `stop_reason` 的所有来源（自然停 /
        #   体力耗尽 / 停因级联）都已确定（本函数是两条通道共用的唯一收尾）。
        try:
            self._stop_criteria_check(entry, view)
        except Exception as _e_sc2:  # noqa: BLE001
            logger_web.warning("[W-STOP-CRIT] 调用失败：%s", _e_sc2)
'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new, tag in ((OLD_USED, NEW_USED, "A1 _WEB_USED_AS"),
                          (OLD_EXEMPT, NEW_EXEMPT, "A2 豁免清单"),
                          (ANCHOR_FN, NEW_FN, "A3 两个新方法"),
                          (OLD_BR, NEW_BR, "A4 _before_round"),
                          (OLD_FIN, NEW_FIN, "A5 层收尾")):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（应为 1）" % (tag, n)
        s = s.replace(old, new, 1)
    # ── 自检 ──
    for _t in ("_practice_term_calibration_prep", "_stop_criteria_check"):
        assert s.count(_t) == 3, "%s 应为 1 定义 + 2 引用，实得 %d" % (
            _t, s.count(_t))
    assert '"term_calibration"' in s and '"stop_criteria"' in s
    assert "practice_term_calibration" in s and "stop_criteria" in s
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 两个 stage 已接线；行数 %d" % out.count(b"\n"))


main()
