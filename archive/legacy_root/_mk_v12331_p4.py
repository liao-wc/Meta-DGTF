#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.31 补丁 · 第 5 阶段：吸收开源对照（RRIF 频率维 + 访问加强）。

对照的开源实现（检索所得）：
  · `ulandz/evermind` —— **RRIF 模型**：Recency / Relevance / Importance /
    **Frequency**。本实现原有 recency×evidence，缺「被用频次」这一维 ⇒ 补上。
  · `hanishkeloth/agentmemory` —— procedural memory 带
    **execution tracking**（`update_execution(proc_id, success)`）+
    auto-consolidation。⇒ 补 `used_outcomes` 并在**读数达标**时才加强。
  · `aravindvaddi/MemoryMCP` —— 「Memory Strength: memories strengthen with
    access」。⇒ 采用，但**加一条闸**：只有「用了且读数达标」才加强，
    否则只记负面（防**自我强化**：用过 ≠ 有用）。
  · `kvyb/llmace` —— ACE 的 Python 实现（reflect/curate + playbook 存取）：
    印证「增量条目 + 确定性合并 + 不重写」这条主线。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.31.py"


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


OLD_RECALL = '''        _age_days = max(0.0, (float(now) - float(e.get("t_last", now))) / 86400.0)
        _rec = 0.5 ** (_age_days / float(halflife or 14.0))
        _ev = 1.0 - 0.5 ** float(e.get("n_evidence", 0) or 0)
        _w = float(e.get("weight", 1.0) or 1.0)
        _score = (_rec ** 0.5) * _ev * _w'''

NEW_RECALL = '''        _age_days = max(0.0, (float(now) - float(e.get("t_last", now))) / 86400.0)
        _rec = 0.5 ** (_age_days / float(halflife or 14.0))
        _ev = 1.0 - 0.5 ** float(e.get("n_evidence", 0) or 0)
        _w = float(e.get("weight", 1.0) or 1.0)
        # ★ [RRIF · 吸收 evermind] 第四维 **Frequency**：被用过几次。上限 1.5
        #   防止「高频但低质」的条目永远霸榜（recency 与 weight 仍在制衡）。
        _freq = min(1.5, 1.0 + 0.1 * len(e.get("t_used") or []))
        _score = (_rec ** 0.5) * _ev * _w * _freq'''

NEW_FN = '''    def _eml_note_use(self, _pb, result) -> dict:
        """**访问加强 + 执行留痕**（吸收 agentmemory / MemoryMCP），带一条闸。

        ★ 闸（防**自我强化**）：只有「本条**真生效**」且「本跑读数**达标**」
          才加强（`weight` / `t_last`）；否则只在 `used_outcomes` 记一笔负面。
          —— 用过 ≠ 有用；这正是「只升不降的指标是自欺」在记忆层的落点。
        ★ 对照：MemoryMCP「memory strength strengthens with access」，
          本实现加了「达标才加强」的限定；agentmemory 的 execution tracking
          对应 `used_outcomes`。
        """
        _used = [x for x in (getattr(self, "_eml_used", None) or [])
                 if x.get("applied")]
        if not _used:
            return {"strengthened": 0, "negative": 0}
        _ep = episode_from_result(result, t=time.time())
        _dmed = None
        _dv = []
        for _e in ("0", "1", "both", "all"):
            _s = ((result.get("views") or {}).get(_e) or {}).get("duty") or {}
            if _s.get("S") is not None:
                _dv.append(float(_s["S"]))
        if _dv:
            _dv.sort()
            _dmed = _dv[len(_dv) // 2]
        _ok = _dmed is not None and _dmed >= float(
            getattr(self, "_duty_floor", _DUTY_FLOOR))
        _n_pos = _n_neg = 0
        _ids = {x.get("id") for x in _used}
        for _e in (_pb or []):
            if _e.get("id") not in _ids:
                continue
            _e.setdefault("used_outcomes", []).append(
                {"run": _ep.get("run_id"), "duty_med": _dmed, "ok": bool(_ok)})
            _tu = list(_e.get("t_used") or [])
            if _ep.get("run_id") and _ep.get("run_id") not in _tu:
                _tu.append(_ep.get("run_id"))
            _e["t_used"] = _tu
            if _ok:
                _e["weight"] = min(1.0, float(_e.get("weight", 1.0) or 1.0)
                                   + 0.05)
                _e["t_last"] = float(time.time())
                _n_pos += 1
            else:
                _e["weight"] = max(0.1, float(_e.get("weight", 1.0) or 1.0)
                                   - 0.05)
                _n_neg += 1
        return {"strengthened": _n_pos, "negative": _n_neg,
                "duty_med": _dmed}


'''


def main():
    s = _load()

    # 1) RRIF 第四维
    s = rep(s, OLD_RECALL, NEW_RECALL, "RRIF 频率维")

    # 2) 访问加强方法：插在 _eml_finish 之前
    anchor = "    def _eml_finish(self, result: dict) -> dict:"
    s = rep(s, anchor, NEW_FN + anchor, "访问加强方法")

    # 3) _eml_finish 里调用它（放在 promote 之后、sweep 之前）
    old_call = '''            _blk["promoted"] = eml_promote(_pb, promote_n=_pn)'''
    new_call = '''            _blk["promoted"] = eml_promote(_pb, promote_n=_pn)
            # ★ 访问加强（吸收 agentmemory / MemoryMCP；带「达标才加强」的闸）
            _blk["strengthen"] = self._eml_note_use(_pb, result)'''
    s = rep(s, old_call, new_call, "_eml_finish 调访问加强")

    _save(s)
    print("OK 第 5 阶段（RRIF 频率 + 访问加强）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert "_freq = min(1.5, 1.0 + 0.1 * len(e.get(\"t_used\") or []))" in s2
    assert "def _eml_note_use(self, _pb, result) -> dict:" in s2
    assert 'self._eml_note_use(_pb, result)' in s2
    print("复读校验通过")


if __name__ == "__main__":
    main()
