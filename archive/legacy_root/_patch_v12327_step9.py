# -*- coding: utf-8 -*-
"""E6 · 自适应停止规则（patch for 元DGTF v1.23.27）

设计报告 §3.5 E6：
  E1 的 G 天然给出停止信号 —— 若 max G < stop_floor ⇒ 本轮**只出不进**
  （探针数 0 是**合法**的，红线）。对应文献里的 stability-detection
  stopping rule（实测省 30-60% 算力）。

落地：
  1) 模块级常量 `_GAIN_STOP_FLOOR = 0.02` + 配置键 `probe.stop_floor`。
  2) 模块级纯函数 `e6_stop_verdict(seen, max_gain, min_gain, stop_floor)`
     —— 返回 `(is_stop, reason)`。**纯函数**便于变异体打判据。
  3) `Pool.probe_stop_history`：每圈一条停止信号记录（**可观测化**，
     不是评分）。`DGTF._e6_note_stop(...)` 统一写入点。
  4) 四处探针解析处调用：仅当「本轮一个探针都没留下」时留痕。
     ★ 只留痕，不改任何既有行为（不拦、不罚、不提前 return）。
  5) `to_dict` 出口 `probe_stop_history`。

红线：
  - 探针数 0 合法 ⇒ 本补丁**只加读出不加罚则**。
  - 「只出不进」≠「本层无事可做」：入口的 `if not residue: return []`
    那种是「没东西可谈」，与「谈得动但增益太低」是两回事。本补丁
    只落在**解析之后**的过滤门，不进那个入口。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.27.py"


def sub(text, anchor, new, tag, count=1):
    n = text.count(anchor)
    assert n == count, (
        f"[{tag}] 锚点命中 {n} 次（期望 {count}）\n锚点={anchor[:140]!r}")
    return text.replace(anchor, new, count)


def main():
    raw = SRC.read_bytes()
    txt = raw.decode("utf-8")
    assert txt.count("\r\n") == txt.count("\n"), "主文件不是纯 CRLF"
    assert "\r\r\n" not in txt, "主文件含 \\r\\r\\n"
    t = txt.replace("\r\n", "\n")

    # ══ 1) 常量 + 纯函数 ═════════════════════════════════════════
    t = sub(
        t,
        '_GAIN_MARGINAL_FLOOR = 0.0\n',
        '_GAIN_MARGINAL_FLOOR = 0.0\n'
        '#: [E6] 自适应停止阈值：本轮所有候选探针的 G（模型自报期望增益）\n'
        '#: 都低于它 ⇒ 停止信号（本轮只出不进，探针数 0 是**合法**的）。\n'
        '#: ★ 与 `min_gain`（0.3）是**两把尺子**：那是「模型说这条值不值得\n'
        '#:   做」，这是「还能不能推得动」。默认 0.02 取「比噪声高一点点」——\n'
        '#:   刻意压低：停止是强动作，宁可多跑一圈也别误停。\n'
        '_GAIN_STOP_FLOOR = 0.02\n'
        '\n'
        '\n'
        'def e6_stop_verdict(seen, max_gain, min_gain, stop_floor):\n'
        '    """[E6] 停止裁决（纯函数，判据与变异体的落点）。\n'
        '\n'
        '    返回 `(is_stop: bool, reason: str)`：\n'
        '      - `seen == 0`          ⇒ `(False, "no_candidate")`\n'
        '        **不是停止**：模型根本没给候选，那是「没得谈」不是\n'
        '        「谈不动」。混为一谈会让「模型偷懒」被读成「已收敛」。\n'
        '      - `max_gain < stop_floor` ⇒ `(True, "max_gain_below_floor")`\n'
        '      - 其余                  ⇒ `(False, "gain_ok")`\n'
        '    ★ 边界取**严格小于**：`max_gain == stop_floor` 不算停。\n'
        '    """\n'
        '    _seen = int(seen or 0)\n'
        '    if _seen <= 0:\n'
        '        return False, "no_candidate"\n'
        '    _mg = float(max_gain or 0.0)\n'
        '    _fl = float(_GAIN_STOP_FLOOR if stop_floor is None\n'
        '                else stop_floor)\n'
        '    if _mg < _fl:\n'
        '        return True, "max_gain_below_floor"\n'
        '    return False, "gain_ok"\n',
        "const+fn", 1)

    # ══ 2) Pool.probe_stop_history 字段 ═════════════════════════
    t = sub(
        t,
        '    # [D1 信念条目] 信念条目（与 structural_amps 双写，不是替换）\n'
        '    belief_items: List[dict] = field(default_factory=list)\n'
        '    belief_transitions: List[dict] = field(default_factory=list)\n',
        '    # [D1 信念条目] 信念条目（与 structural_amps 双写，不是替换）\n'
        '    belief_items: List[dict] = field(default_factory=list)\n'
        '    belief_transitions: List[dict] = field(default_factory=list)\n'
        '    # [E6] 每圈一条停止信号（可观测化；不参与评分）\n'
        '    probe_stop_history: List[dict] = field(default_factory=list)\n',
        "pool.field", 1)

    # ══ 3) to_dict 出口 ═════════════════════════════════════════
    t = sub(
        t,
        '    def belief_status_counts(self) -> dict:\n',
        '    def note_probe_stop(self, layer, seen, max_gain, min_gain,\n'
        '                        stop_floor) -> dict:\n'
        '        """[E6] 记一条停止信号痕迹。**只留痕**，不拦不改行为。\n'
        '\n'
        '        ★ `reason == "no_candidate"` 也记 —— 「没候选」与「有候选\n'
        '          但全低于阈」必须能分开审计，否则读不出模型是懒还是池收敛。\n'
        '        """\n'
        '        _stop, _why = e6_stop_verdict(seen, max_gain, min_gain,\n'
        '                                      stop_floor)\n'
        '        _rec = {"layer": str(layer),\n'
        '                "seen": int(seen or 0),\n'
        '                "max_gain": round(float(max_gain or 0.0), 4),\n'
        '                "stop_floor": float(_GAIN_STOP_FLOOR if stop_floor\n'
        '                                    is None else stop_floor),\n'
        '                "stop": bool(_stop), "reason": _why}\n'
        '        self.probe_stop_history.append(_rec)\n'
        '        return _rec\n'
        '\n'
        '    def belief_status_counts(self) -> dict:\n',
        "pool.note", 1)

    t = sub(
        t,
        '        if self.belief_transitions:\n'
        '            d["belief_transitions"] = self.belief_transitions\n',
        '        if self.belief_transitions:\n'
        '            d["belief_transitions"] = self.belief_transitions\n'
        '        # [E6 停止信号] 与 belief_items 同样走白名单出口。\n'
        '        if self.probe_stop_history:\n'
        '            d["probe_stop_history"] = self.probe_stop_history\n',
        "to_dict", 1)

    # ══ 4) DGTF 侧统一写入点 ════════════════════════════════════
    t = sub(
        t,
        '    def _phase_probe(self, view: "View", inp: Input, pool: Pool) -> List[dict]:\n',
        '    def _e6_note_stop(self, pool, view, layer, seen, max_gain,\n'
        '                      min_gain, stop_floor):\n'
        '        """[E6] 本轮 0 探针时统一留痕（四处探针解析共用这一处）。"""\n'
        '        _rec = pool.note_probe_stop(layer, seen, max_gain,\n'
        '                                    min_gain, stop_floor)\n'
        '        if _rec["stop"]:\n'
        '            self.vp(f"   ⏹ [E6] 停止信号：{layer} 层所有候选探针"\n'
        '                    f" max_gain={_rec[\'max_gain\']} < "\n'
        '                    f"floor={_rec[\'stop_floor\']} ⇒ 本轮只出不进"\n'
        '                    f"（空探针合法）")\n'
        '        else:\n'
        '            self.vp(f"   ⏹ [E6] 本轮无探针（{_rec[\'reason\']}，"\n'
        '                    f"seen={_rec[\'seen\']}）")\n'
        '        return _rec\n'
        '\n'
        '    def _phase_probe(self, view: "View", inp: Input, pool: Pool) -> List[dict]:\n',
        "dgtf.note", 1)

    # ══ 5) 四处过滤门：记 seen / max_gain ═══════════════════════

    # (a) research / duel / meta：同一个 for 头（共 3 处）
    t = sub(
        t,
        '        out: List[dict] = []\n'
        '        for p in (data.get("probes") or []):\n'
        '            if not isinstance(p, dict):\n'
        '                continue\n'
        '            q = str(p.get("question", "")).strip()[:200]\n',
        '        out: List[dict] = []\n'
        '        _e6_seen = 0        # [E6] 候选探针数（含被剪掉的）\n'
        '        _e6_max_gain = 0.0  # [E6] 候选里最大的 G\n'
        '        for p in (data.get("probes") or []):\n'
        '            if not isinstance(p, dict):\n'
        '                continue\n'
        '            q = str(p.get("question", "")).strip()[:200]\n',
        "e6.collect", 3)

    # (b) 三处的计数点，各按其后继语句区分
    t = sub(
        t,
        '            gain = max(0.0, min(1.0, gain))\n'
        '            if not q or len(q) < 6 or not link or gain < min_gain:\n'
        '                continue\n'
        '            covers_raw = p.get("covers") or []\n',
        '            gain = max(0.0, min(1.0, gain))\n'
        '            _e6_seen += 1\n'
        '            _e6_max_gain = max(_e6_max_gain, gain)\n'
        '            if not q or len(q) < 6 or not link or gain < min_gain:\n'
        '                continue\n'
        '            covers_raw = p.get("covers") or []\n',
        "e6.cnt.research", 1)

    t = sub(
        t,
        '            gain = max(0.0, min(1.0, gain))\n'
        '            if not q or len(q) < 6 or not link or gain < min_gain:\n'
        '                continue\n'
        '            out.append({"question": q, "link": link,\n'
        '                        "expected_gain": round(gain, 2)})\n'
        '\n'
        '        for a in (data.get("adjudications") or []):\n',
        '            gain = max(0.0, min(1.0, gain))\n'
        '            _e6_seen += 1\n'
        '            _e6_max_gain = max(_e6_max_gain, gain)\n'
        '            if not q or len(q) < 6 or not link or gain < min_gain:\n'
        '                continue\n'
        '            out.append({"question": q, "link": link,\n'
        '                        "expected_gain": round(gain, 2)})\n'
        '\n'
        '        for a in (data.get("adjudications") or []):\n',
        "e6.cnt.duel", 1)

    t = sub(
        t,
        '            gain = max(0.0, min(1.0, gain))\n'
        '            if not q or len(q) < 6 or not link or gain < min_gain:\n'
        '                continue\n'
        '            out.append({"question": q, "link": link,\n'
        '                        "expected_gain": round(gain, 2)})\n'
        '\n'
        '        _valid_tids = {str(s.get("id")) for s in duel_tensions',
        '            gain = max(0.0, min(1.0, gain))\n'
        '            _e6_seen += 1\n'
        '            _e6_max_gain = max(_e6_max_gain, gain)\n'
        '            if not q or len(q) < 6 or not link or gain < min_gain:\n'
        '                continue\n'
        '            out.append({"question": q, "link": link,\n'
        '                        "expected_gain": round(gain, 2)})\n'
        '\n'
        '        _valid_tids = {str(s.get("id")) for s in duel_tensions',
        "e6.cnt.meta", 1)

    # (c) phase 层（_parse_probe_resp 内）
    t = sub(
        t,
        '            _probes: List[dict] = []\n'
        '            for p in (_data.get("probes") or []):\n',
        '            _probes: List[dict] = []\n'
        '            _e6_seen = 0        # [E6] 候选探针数（含被剪掉的）\n'
        '            _e6_max_gain = 0.0  # [E6] 候选里最大的 G\n'
        '            for p in (_data.get("probes") or []):\n',
        "e6.collect.phase", 1)

    t = sub(
        t,
        '                gain = max(0.0, min(1.0, gain))\n'
        '                if not q or len(q) < 6 or not link or gain < min_gain:\n'
        '                    continue\n',
        '                gain = max(0.0, min(1.0, gain))\n'
        '                _e6_seen += 1\n'
        '                _e6_max_gain = max(_e6_max_gain, gain)\n'
        '                if not q or len(q) < 6 or not link or gain < min_gain:\n'
        '                    continue\n',
        "e6.cnt.phase", 1)

    t = sub(
        t,
        '            _probes.sort(key=lambda x: -x["expected_gain"])\n'
        '            return {"probes": _probes[:3],\n',
        '            _probes.sort(key=lambda x: -x["expected_gain"])\n'
        '            return {"probes": _probes[:3],\n'
        '                    "e6_seen": _e6_seen,\n'
        '                    "e6_max_gain": _e6_max_gain,\n',
        "e6.ret.phase", 1)

    # ══ 6) 四处「0 探针 ⇒ 留痕」 ═════════════════════════════════

    # 6a) research
    t = sub(
        t,
        '        sub_by_id = {s.get("id"): s for s in pool.sub_questions}\n'
        '\n'
        '        def _sub_text(sid):',
        '        if not out:\n'
        '            self._e6_note_stop(pool, view, "research",\n'
        '                               _e6_seen, _e6_max_gain, min_gain,\n'
        '                               stop_floor)\n'
        '\n'
        '        sub_by_id = {s.get("id"): s for s in pool.sub_questions}\n'
        '\n'
        '        def _sub_text(sid):',
        "e6.note.research", 1)

    # 6b) duel（用其后继 `for a in view.adjudications` 区分）
    t = sub(
        t,
        '        out.sort(key=lambda x: -x["expected_gain"])\n'
        '        out = out[:3]\n'
        '        for p in out:\n'
        '            self.vp(f"   \U0001f331 {p[\'question\']}")\n'
        '            self.vp(f"      \u21a9 回来：{p[\'link\']}｜增益{p[\'expected_gain\']}")\n'
        '        for a in view.adjudications:\n',
        '        if not out:\n'
        '            self._e6_note_stop(pool, view, "duel", _e6_seen,\n'
        '                               _e6_max_gain, min_gain, stop_floor)\n'
        '\n'
        '        out.sort(key=lambda x: -x["expected_gain"])\n'
        '        out = out[:3]\n'
        '        for p in out:\n'
        '            self.vp(f"   \U0001f331 {p[\'question\']}")\n'
        '            self.vp(f"      \u21a9 回来：{p[\'link\']}｜增益{p[\'expected_gain\']}")\n'
        '        for a in view.adjudications:\n',
        "e6.note.duel", 1)

    # 6c) meta（用其后继 `for e in view.engagements:` + 元决策 区分）
    t = sub(
        t,
        '        for p in out:\n'
        '            self.vp(f"   \U0001f331 {p[\'question\']}")\n'
        '            self.vp(f"      \u21a9 回来：{p[\'link\']}｜增益{p[\'expected_gain\']}")\n'
        '            if p.get("covers"):\n'
        '                self.vp(f"      \u2713 covers={p[\'covers\']}")\n'
        '        for e in view.engagements:\n'
        '            self.vp(f"   \U0001f91d 元决策：{e[\'target\']}（{e[\'how\']}）")\n',
        '        if not out:\n'
        '            self._e6_note_stop(pool, view, "meta", _e6_seen,\n'
        '                               _e6_max_gain, min_gain, stop_floor)\n'
        '\n'
        '        for p in out:\n'
        '            self.vp(f"   \U0001f331 {p[\'question\']}")\n'
        '            self.vp(f"      \u21a9 回来：{p[\'link\']}｜增益{p[\'expected_gain\']}")\n'
        '            if p.get("covers"):\n'
        '                self.vp(f"      \u2713 covers={p[\'covers\']}")\n'
        '        for e in view.engagements:\n'
        '            self.vp(f"   \U0001f91d 元决策：{e[\'target\']}（{e[\'how\']}）")\n',
        "e6.note.meta", 1)

    # 6d) phase：_p1 解析后（主路径），以及重试后（_p2）
    t = sub(
        t,
        '        _p1 = _parse_probe_resp(data)\n'
        '        _absorb_probe(_p1)\n'
        '        _boundary_threads = _p1["boundary_threads"]\n'
        '        out = list(_p1["probes"])\n',
        '        _p1 = _parse_probe_resp(data)\n'
        '        _absorb_probe(_p1)\n'
        '        _boundary_threads = _p1["boundary_threads"]\n'
        '        out = list(_p1["probes"])\n'
        '        _e6_p1_seen = _p1.get("e6_seen", 0)\n'
        '        _e6_p1_gain = _p1.get("e6_max_gain", 0.0)\n',
        "e6.phase.capture", 1)

    t = sub(
        t,
        '        for p in out:\n'
        '            self.vp(f"   \U0001f331 {p[\'question\']}")\n'
        '            self.vp(f"      \u21a9 回来：{p[\'link\']}｜增益{p[\'expected_gain\']}")\n'
        '            _cov = p.get("covers") or []\n'
        '            if _cov:\n'
        '                self.vp(f"      \u2713 covers={_cov}")\n'
        '            else:\n'
        '                self.vp("      \u2717 covers=（空，模型未输出或输出为空）")\n',
        '        if not out:\n'
        '            self._e6_note_stop(pool, view, "phase", _e6_p1_seen,\n'
        '                               _e6_p1_gain, min_gain, stop_floor)\n'
        '\n'
        '        for p in out:\n'
        '            self.vp(f"   \U0001f331 {p[\'question\']}")\n'
        '            self.vp(f"      \u21a9 回来：{p[\'link\']}｜增益{p[\'expected_gain\']}")\n'
        '            _cov = p.get("covers") or []\n'
        '            if _cov:\n'
        '                self.vp(f"      \u2713 covers={_cov}")\n'
        '            else:\n'
        '                self.vp("      \u2717 covers=（空，模型未输出或输出为空）")\n',
        "e6.note.phase", 1)

    out = t.replace("\n", "\r\n")
    SRC.write_bytes(out.encode("utf-8"))
    print("STEP9 PATCH OK")


if __name__ == "__main__":
    main()
