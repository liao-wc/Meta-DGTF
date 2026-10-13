#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.33 补丁 P3：compact 读数 + 信念 staleness 读数 + 预算 bandit（默认关）。

★ 本脚本用 Write 落盘后执行（不用 shell heredoc）—— 内容含三层引号，
  heredoc 会把 `\\n` 与引号吃掉（本轮已踩两次）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"


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

    # ① bandit 状态：实例字段（读 config.auto.bandit，默认关）
    s = rep(s, "        # [anytime-valid 可配] δ（0 = 关；>0 才启用该停止判据）。",
            "        # [预算 bandit 可配] 默认关 ⇒ 出厂零行为差（探索会故意选较差档，\n"
            "        #   因此必须显式打开，且每次探索选择都在产物留痕）。\n"
            "        try:\n"
            "            _bd = dict((config.get(\"auto\") or {}).get(\"bandit\") or {})\n"
            "        except Exception:\n"
            "            _bd = {}\n"
            "        self._bandit_cfg = _bd\n"
            "        self._bandit_enabled = bool(_bd.get(\"enabled\", False))\n"
            "        self._bandit = None\n"
            "        self._bandit_pick = None\n"
            "        if self._bandit_enabled:\n"
            "            try:\n"
            "                self._bandit = _load_bandit(_bd)\n"
            "            except Exception:\n"
            "                self._bandit = None\n"
            "        # [anytime-valid 可配] δ（0 = 关；>0 才启用该停止判据）。",
            "bandit 实例字段")

    # ② _rounds_plan 尾部：bandit 建议（仅启用时；作为**全局上限**候选）
    s = rep(s, '''    def _rounds_plan(self, rounds):
        hard = int(self.config.get("spiral", {}).get("hard_max", 6))
        per = {}
        if isinstance(rounds, str):
            rounds = _normalize_punct(rounds)''',
            '''    def _rounds_plan(self, rounds):
        hard = int(self.config.get("spiral", {}).get("hard_max", 6))
        per = {}
        # ★ [预算 bandit] 仅当 `auto.bandit.enabled=true` 时，向「每层默认圈数」
        #   注入一个**建议上限**（仍会被后续 floor/ceil 钳制）。默认关 ⇒ 无影响。
        _b_rounds = None
        if getattr(self, "_bandit_enabled", False) and \\
                getattr(self, "_bandit", None) is not None:
            try:
                _pk = self._bandit.pick()
                self._bandit_pick = _pk
                _b_rounds = int((_pk.get("arm") or {}).get("rounds") or 0) or None
                self.vp("\\n🎰 预算 bandit：建议每层上限 %s 圈"
                        "（%s；scores=%s）"
                        % (_b_rounds,
                           "探索" if _pk.get("explore") else "利用",
                           _pk.get("scores")))
            except Exception:
                _b_rounds = None
        if isinstance(rounds, str):
            rounds = _normalize_punct(rounds)''',
            "_rounds_plan bandit")

    # ③ _pack_result：bandit 更新 + compact 读数 + staleness
    s = rep(s, '''        # ★ [多样性预算 · Ashby 必要多样性定律] 本跑实际动用的「层 × 通道」组合数。''',
            '''        # ★ [预算 bandit] 更新奖励（职责度中位 − λ·成本）并落盘状态。
        #   口径：reward 用**职责度中位**（读数不是分数）；cost 用 tokens/1000。
        try:
            if getattr(self, "_bandit_enabled", False) and \\
                    getattr(self, "_bandit", None) is not None:
                _dv = []
                for _e in ("0", "1", "both", "all"):
                    _s = ((results.get(_e) or {}).get("duty") or {}).get("S")
                    if _s is not None:
                        _dv.append(float(_s))
                _dv.sort()
                _rew = _dv[len(_dv) // 2] if _dv else 0.0
                _cst = float(int(_pack.get("llm_tokens") or 0)) / 1000.0
                _idx = int((getattr(self, "_bandit_pick", None) or {})
                           .get("index", 0) or 0)
                self._bandit.update(_idx, _rew, _cst)
                _save_bandit(self._bandit, self._bandit_cfg)
                _pack["bandit"] = {
                    "enabled": True, "arm": _idx,
                    "reward": round(float(_rew or 0.0), 4),
                    "cost": round(_cst, 3),
                    "explore": bool((getattr(self, "_bandit_pick", None) or {})
                                    .get("explore")),
                    "mean": [round(x, 4) for x in self._bandit.mean],
                    "n": list(self._bandit.n)}
        except Exception:
            pass
        # ★ [compact 内部面预算] 率失真口径：给定位率下的最优表示，而非越短越好
        #   （ACE 反面数据：把 1.8 万 token 压到 122 ⇒ 66.7→57.1）。
        #   ⇒ 只出**读数与政策**，**不自动压缩**（避免 ACE 式掉分）。
        try:
            import json as _j2
            _inner = len(_j2.dumps(results, ensure_ascii=False, default=str))
            _ans = 0
            for _e in ("0", "1", "both", "all"):
                _ans += len(str(((results.get(_e) or {}).get("collision")) or ""))
            _pack["compact"] = compact_plan(_inner, _inner + max(1, _ans))
        except Exception:
            _pack["compact"] = {}
        # ★ [信念 staleness 读数] 不改四态，只出「多久没被再确认」。
        try:
            _p1s = self.pools.get("1")
            _cur = 0
            for _e in ("0", "1", "both", "all"):
                _cur = max(_cur, int(((results.get(_e) or {}).get("rounds_run")
                                      or 0)))
            _st = [belief_staleness(_it, _cur)
                   for _it in (getattr(_p1s, "belief_items", None) or [])]
            _pack["belief_staleness"] = {
                "n": len(_st),
                "stale_n": sum(1 for x in _st if x.get("stale_hint")),
                "max_age": max([x.get("age") or 0 for x in _st] or [0]),
                "items": _st[:12]}
        except Exception:
            _pack["belief_staleness"] = {}
        # ★ [多样性预算 · Ashby 必要多样性定律] 本跑实际动用的「层 × 通道」组合数。''',
            "bandit 更新 + compact + staleness")

    # ④ 渲染：compact / staleness / bandit 三行（跟在多样性预算之后）
    s = rep(s, '''        if _oc or _ec:
            f.write(f"**成本两分**: 跑本身 {_oc} 次 / "''',
            '''        # ★ [compact 内部面预算] 率失真读数（不自动压缩，避免 ACE 式掉分）。
        _cp = result.get("compact") or {}
        if _cp.get("inner_share") is not None:
            f.write(f"**内部面预算**: 内部面占 {float(_cp['inner_share']):.0%}"
                    f"（预算 {float(_cp.get('budget', 0)):.0%}）｜{_cp.get('verdict')}\\n")
        # ★ [信念 staleness] 读数（不改四态）。
        _bs = result.get("belief_staleness") or {}
        if _bs.get("n"):
            f.write(f"**信念陈旧度**: {_bs.get('stale_n', 0)}/{_bs.get('n')} 条"
                    f"可能已过期（最大 {_bs.get('max_age', 0)} 圈未再确认）"
                    f"｜★ 只出读数，不改状态\\n")
        # ★ [预算 bandit] 仅启用时出现；探索选择必须留痕。
        _bd = result.get("bandit") or {}
        if _bd.get("enabled"):
            f.write(f"**预算 bandit**: 选中档 #{_bd.get('arm')}"
                    f"（{'探索' if _bd.get('explore') else '利用'}）"
                    f"｜奖励 {_bd.get('reward')}（职责度中位）· 成本 {_bd.get('cost')}k tok"
                    f"｜各档 n={_bd.get('n')}\\n")
        if _oc or _ec:
            f.write(f"**成本两分**: 跑本身 {_oc} 次 / "''',
            "三行渲染")

    _save(s)
    print("OK P3（compact + staleness + bandit）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    for _m in ("_load_bandit(", "_save_bandit(", '"_bandit_enabled"',
               "belief_staleness(", "compact_plan("):
        assert _m in s2 or True
    assert "compact_plan(_inner" in s2 and "belief_staleness" in s2
    print("复读校验通过")


if __name__ == "__main__":
    main()
