#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.30 补丁 · 第 4 阶段：LDG 阈值可配（默认 = 引擎常量 ⇒ 零行为差）。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.30.py"


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

    # 1) 纯函数支持 floor 覆盖（默认 None ⇒ 用模块常量）
    s = rep(s, "def duty_of_layer(entry, question, deliver_text, objective_words=(),\n"
               "                  corpus=None) -> dict:",
            "def duty_of_layer(entry, question, deliver_text, objective_words=(),\n"
            "                  corpus=None, floor=None) -> dict:",
            "duty_of_layer 签名")
    s = rep(s, '    d["short"] = bool(float(d.get("S", 0.0)) < float(_DUTY_FLOOR))',
            '    _fl = float(_DUTY_FLOOR if floor is None else floor)\n'
            '    d["short"] = bool(float(d.get("S", 0.0)) < _fl)\n'
            '    d["floor"] = _fl',
            "duty_of_layer floor")

    # 2) 实例阈值：构造时从 config.duty 读
    old_i = '''        for _p in self.pools.values():
            _p.merge_semantic = _mg
            _p.merge_sim = _ms'''
    new_i = '''        for _p in self.pools.values():
            _p.merge_semantic = _mg
            _p.merge_sim = _ms
        # [LDG 可配] 层职责守卫的阈值（默认 = 引擎常量 ⇒ 出厂零行为差）。
        try:
            _du = dict(config.get("duty") or {})
        except Exception:
            _du = {}
        try:
            self._duty_floor = float(_du.get("floor", _DUTY_FLOOR))
        except (TypeError, ValueError):
            self._duty_floor = float(_DUTY_FLOOR)
        try:
            self._duty_tau = float(_du.get("tau", _DUTY_TAU))
        except (TypeError, ValueError):
            self._duty_tau = float(_DUTY_TAU)
        try:
            self._duty_patience = int(_du.get("patience", _DUTY_PATIENCE))
        except (TypeError, ValueError):
            self._duty_patience = int(_DUTY_PATIENCE)
        self._duty_carry: List[str] = []'''
    s = rep(s, old_i, new_i, "实例阈值")

    # 3) _layer_duty_now 传 floor
    s = rep(s, '''        d = duty_of_layer(entry, self._question, deliver,
                          objective_words=_DUTY_OBJ_WORDS.get(entry, ()),
                          corpus=getattr(self, "_sim_corpus", None))''',
            '''        d = duty_of_layer(entry, self._question, deliver,
                          objective_words=_DUTY_OBJ_WORDS.get(entry, ()),
                          corpus=getattr(self, "_sim_corpus", None),
                          floor=getattr(self, "_duty_floor", _DUTY_FLOOR))''',
            "传 floor")

    # 4) _duty_marginal_streak 用实例 tau
    s = rep(s, '''        if abs(_last - _prev) < float(_DUTY_TAU):''',
            '''        _tau = float(getattr(self, "_duty_tau", _DUTY_TAU))
        if abs(_last - _prev) < _tau:''',
            "tau 实例化")

    # 5) 停止判据用实例 patience
    s = rep(s, '''            if int(duty_streak or 0) >= int(_DUTY_PATIENCE):''',
            '''            _dpat = int(getattr(self, "_duty_patience", _DUTY_PATIENCE))
            if int(duty_streak or 0) >= _dpat:''',
            "patience 实例化")

    # 6) DEFAULT_CONFIG 新增 duty 段（插在 belief 段之后）
    old_cfg = '''        "merge_sim": 0.85,
    },'''
    new_cfg = '''        "merge_sim": 0.85,
    },

    "duty": {
        # [LDG] 层职责守卫：在**停止/收敛处**算「这层替原始问题干了什么」。
        #   三个读数：C 覆盖（问项按 core/background/followup 加权）·
        #   R 相关（|Direct|/(|Direct|+|Useless|)，惩罚无用断言）·
        #   S = 2CR/(C+R)（调和平均；一项塌了整体塌）。
        #   ★ 它是**读数不是分数**：不进 `_quality_verdict`，只做两件事
        #     —— ① 署名纪律（低于 floor 不许写「自然安住」）；
        #     ② 新停止判据「职责增益收敛」（连续 patience 圈 ΔS<tau）。
        "floor": 0.35,
        "tau": 0.02,
        "patience": 2,
        "remedy_rounds": 1,
    },'''
    s = rep(s, old_cfg, new_cfg, "DEFAULT_CONFIG duty 段")

    _save(s)
    print("OK 第 4 阶段（LDG 阈值可配）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert '"duty": {' in s2 and '"floor": 0.35,' in s2
    assert "self._duty_floor = float(_du.get" in s2
    print("复读校验通过")


if __name__ == "__main__":
    main()
