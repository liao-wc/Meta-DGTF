# -*- coding: utf-8 -*-
"""生成 元DGTF-V1.23.65.py：token 软预算 + all_on 成本修正。"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.64.py"
DST = HERE / "元DGTF-V1.23.65.py"
txt = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")


def rep(old: str, new: str, n: int = 1) -> None:
    global txt
    c = txt.count(old)
    assert c == n, "命中 %d 次（期望 %d）：%r" % (c, n, old[:90])
    txt = txt.replace(old, new)


rep("元 DGTF · v1.23.64", "元 DGTF · v1.23.65")
rep('__version__ = "1.23.64"', '__version__ = "1.23.65"')

rep(
    '''    ("api.thinking.effort", "high", "思考强度 high"),
    ("actions.merge_expand", True,
     "阴阳展开合并成一次调用（降本开关，出厂关）"),
)''',
    '''    ("api.thinking.effort", "low",
     "思考强度 low：high 无质量证据，probe 四档打平；成本最小化是唯一有把握的理由"),
    ("spiral.shape_limit", 8,
     "上下文形状窗口化：真跑 A/B tokens −8.8%、复述率降到 1/3，无过裁证据"),
    ("actions.merge_expand", True,
     "阴阳展开合并成一次调用（降本开关，出厂关）"),
)''',
)
rep(
    '''    ("auto.bandit.enabled", True, "预算 bandit 生效（探索必留痕）"),
''',
    "",
)
rep(
    '''_ALL_ON_EXEMPT = {}''',
    '''_ALL_ON_EXEMPT = {
    "auto.bandit.enabled": "bandit 是探索型调度：A/B 已把它当混淆因素关掉，"
                           "且跨跑 cap 会漂移；改为显式 opt-in，不进 all_on",
}''',
)

rep(
    '''    "all_on": False,

    "playbook": {''',
    '''    "all_on": False,

    # 总 token 预算（0 = 不设限）。★ 与 max_calls 互补：调用次数挡不住
    #   「单次上下文暴涨」—— 实测有 199 calls / 2.94M tokens 的跑次，
    #   而同期 129 calls / 1.16M 的覆盖更高。到点走层/圈边界优雅停，
    #   可 resume_ckpt 续跑，不静默截断。
    "max_tokens": 0,

    "playbook": {''',
)

rep(
    '''    def _note_budget_stop(self, where: str = "") -> None:
        """记下"因为预算而提前收尾"，并打进日志。"""
        b = int(getattr(self, "_call_budget", 0) or 0)
        used = int(getattr(self.llm, "total_calls", 0) or 0)
        self._budget_stop_note = (
            f"预算用尽（已用 {used}/{b} 次调用"
            + (f"，{where}" if where else "") + "）")
        self.vp(f"\\n   ⏹ {self._budget_stop_note}，提前收尾"
                f"（不是自然停止）")''',
    '''    def _token_budget_over(self) -> bool:
        """总 token 预算是否用尽（0 = 不设限）。

        ★ 与调用次数预算互补：调用次数挡不住「单次上下文暴涨」。实测有
          199 calls / 2.94M tokens 的跑次，同期 129 calls / 1.16M 的覆盖更高
          —— 贵不等于好，预算必须能按 token 立闸。
        ★ 续跑时把上一窗口的累计带上（_ck_base），否则分片跑会重置额度。
        """
        b = int(getattr(self, "_token_budget", 0) or 0)
        if b <= 0:
            return False
        used = int(getattr(self.llm, "total_tokens", 0) or 0)
        used += int((getattr(self, "_ck_base", None) or {}).get("tokens", 0) or 0)
        return used >= b

    def _note_budget_stop(self, where: str = "") -> None:
        """记下"因为预算而提前收尾"，并打进日志。"""
        b = int(getattr(self, "_call_budget", 0) or 0)
        used = int(getattr(self.llm, "total_calls", 0) or 0)
        tb = int(getattr(self, "_token_budget", 0) or 0)
        tok = int(getattr(self.llm, "total_tokens", 0) or 0)
        tok += int((getattr(self, "_ck_base", None) or {}).get("tokens", 0) or 0)
        bits = []
        if b > 0:
            bits.append(f"{used}/{b} 次调用")
        if tb > 0:
            bits.append(f"{tok}/{tb} tokens")
        detail = "；".join(bits) if bits else f"{used} 次调用"
        self._budget_stop_note = (
            f"预算用尽（已用 {detail}"
            + (f"，{where}" if where else "") + "）")
        self.vp(f"\\n   ⏹ {self._budget_stop_note}，提前收尾"
                f"（不是自然停止）")''',
)

rep(
    '''            resume_ckpt: str = "",
            max_minutes: float = 0.0) -> dict:''',
    '''            resume_ckpt: str = "",
            max_minutes: float = 0.0,
            max_tokens: float = 0.0) -> dict:''',
)
rep(
    '''        self._ck_base = {"calls": 0, "tokens": 0}''',
    '''        self._ck_base = {"calls": 0, "tokens": 0}
        # [v1.23.65] 总 token 软预算：参数优先，其次配置，0 = 不设限。
        self._token_budget = int(
            max_tokens or (self.config.get("max_tokens", 0) or 0) or 0)''',
)

# 串行层：圈首
rep(
    '''            if r > 0:
                _wc = self._wall_clock_over()
                if _wc or self._budget_exhausted():''',
    '''            if r > 0:
                _wc = self._wall_clock_over()
                _tk = self._token_budget_over()
                if _wc or _tk or self._budget_exhausted():''',
)
rep(
    '''                    if _wc:
                        self._budget_stop_note = (
                            "墙钟预算到点（第 %d 圈截断，续跑会重跑这一层）" % (r + 1))''',
    '''                    if _wc or _tk:
                        _why = "墙钟预算到点" if _wc else "Token 预算到点"
                        self._budget_stop_note = (
                            "%s（第 %d 圈截断，续跑会重跑这一层）"
                            % (_why, r + 1))''',
)

# C 模式
rep(
    '''                if r > start_r:
                    _wc = self._wall_clock_over()
                    if _wc or self._budget_exhausted():
                        self._note_budget_stop(
                            f"C 模式 {entry} 跑到第 {r} 圈"
                            + ("（墙钟预算到点）" if _wc else ""))
                        if _wc:
                            state["stop_reason"] = (
                                "墙钟预算到点（第 %d 圈截断，续跑会重跑这一层）" % r)''',
    '''                if r > start_r:
                    _wc = self._wall_clock_over()
                    _tk = self._token_budget_over()
                    if _wc or _tk or self._budget_exhausted():
                        self._note_budget_stop(
                            f"C 模式 {entry} 跑到第 {r} 圈"
                            + ("（墙钟预算到点）" if _wc
                               else "（Token 预算到点）" if _tk else ""))
                        if _wc or _tk:
                            state["stop_reason"] = (
                                ("墙钟预算到点" if _wc else "Token 预算到点")
                                + "（第 %d 圈截断，续跑会重跑这一层）" % r)''',
)

# D~H 模式
rep(
    '''                if r > start_r:
                    _wc = self._wall_clock_over()
                    if _wc or self._budget_exhausted():
                        self._note_budget_stop(
                            f"{self._parallel_label} 模式 {entry} 跑到第 {r} 圈"
                            + ("（墙钟预算到点）" if _wc else ""))
                        if _wc:
                            state["stop_reason"] = (
                                "墙钟预算到点（第 %d 圈截断，续跑会重跑这一层）" % r)''',
    '''                if r > start_r:
                    _wc = self._wall_clock_over()
                    _tk = self._token_budget_over()
                    if _wc or _tk or self._budget_exhausted():
                        self._note_budget_stop(
                            f"{self._parallel_label} 模式 {entry} 跑到第 {r} 圈"
                            + ("（墙钟预算到点）" if _wc
                               else "（Token 预算到点）" if _tk else ""))
                        if _wc or _tk:
                            state["stop_reason"] = (
                                ("墙钟预算到点" if _wc else "Token 预算到点")
                                + "（第 %d 圈截断，续跑会重跑这一层）" % r)''',
)

# B 模式波循环
rep(
    '''            if k > warm + 1 and self._budget_exhausted():''',
    '''            if k > warm + 1 and (self._budget_exhausted()
                                 or self._token_budget_over()):''',
)

# 串行层间守卫
rep(
    '''            _mx = float(getattr(self, "_max_minutes", 0.0) or 0.0)
            if self._wall_clock_over():''',
    '''            _mx = float(getattr(self, "_max_minutes", 0.0) or 0.0)
            _wc = self._wall_clock_over()
            _tk = self._token_budget_over()
            if _wc or _tk:''',
)
rep(
    '''                self.vp(f"\\n⏸ 墙钟预算 {_mx:.1f} 分钟到 ⇒ 优雅停：已完成 "''',
    '''                _why = (f"墙钟预算 {_mx:.1f} 分钟到" if _wc
                        else "Token 预算到点")
                self.vp(f"\\n⏸ {_why} ⇒ 优雅停：已完成 "''',
)

out = txt.replace("\n", "\r\n")
DST.write_bytes(out.encode("utf-8"))
print("WROTE", DST.name, "bytes", len(out.encode("utf-8")))
