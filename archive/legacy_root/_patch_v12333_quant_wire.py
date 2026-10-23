# 第六期补丁 P6-4：四个读数的**真实入口接线**（进 view.quant_readings）。
# ★ 承本项目最高频事故源：「纯函数判据全绿 ≠ 该能力在引擎里可达」。
#   所以每条读数都必须有**真实入口产出**判据（㉛），不是只测纯函数。
# ★ 接线三处（都是**已有**的层内动作点，零新增路径）：
#   ① 展开后：阴阳分歧度（依据 ②）
#   ② 锚点重述后：保真度（依据 ①）
#   ③ ing 输出后：语义密度（依据 ④）
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

# ── A1：新增 `_quant_note` helper（唯一写 quant_readings 的地方）──
A1 = '''    def _goal_action_hint(self, entry: str, view) -> str:'''
NEW1 = '''    def _quant_note(self, view, key: str, val) -> None:
        """[第六期] 把一条量化读数写进 `view.quant_readings`（**唯一写入口**）。

        ★ 纪律：**值不可用（None / 空 dict / 空串）就不写键** ——
          与 `goal_trace` 出口同款（产物里不出现空壳读数）。
        ★ 只记读数，**不改任何判定**（红线：读数不是分数）。
        """
        if view is None or not key:
            return
        if val is None or val == "" or val == {}:
            return
        try:
            _d = getattr(view, "quant_readings", None)
            if _d is None:
                view.quant_readings = {}
                _d = view.quant_readings
            _d[str(key)] = dict(val) if isinstance(val, dict) else {"value": val}
        except Exception:
            pass

    def _goal_action_hint(self, entry: str, view) -> str:'''

# ── A2：ing 输出后算语义密度（依据 ④）──
A2 = '''                view.collision = self._ing(candidates, inp, view.anchor, view)
                self.vp(f"   🔥 ing 输出 {len(view.collision)} 字")'''
NEW2 = '''                view.collision = self._ing(candidates, inp, view.anchor, view)
                self.vp(f"   🔥 ing 输出 {len(view.collision)} 字")
                # ★ [第六期 · 依据 ④] ing 输出的**语义密度**（零成本纯函数）。
                #   信息瓶颈：>5 个无信息 token ⇒ 性能降 15%+ —— 低密度即提示。
                try:
                    _sd = semantic_density(view.collision)
                    if _sd is not None:
                        self._quant_note(view, "ing_density", {
                            "value": _sd, "chars": len(view.collision or ""),
                            "verdict": ("thin" if _sd < 0.6 else "ok")})
                        if _sd < 0.6:
                            self.vp(f"   ⚑ ing 语义密度偏低 {_sd:.2f}"
                                    f"（<0.60 ⇒ 填充语多，信息量薄）")
                except Exception:
                    pass'''

# ── A3：锚点确定后算保真度（依据 ①）──
#   ★ 落点在**锚点分支汇合之后**（重述开 / 关两种情形都要算）。
A3 = '''            anchor_untouched = []
            _anchor_touched = []
            self.vp("   🪞 锚点重述：已关闭（用透传/原文）")'''
NEW3 = '''            anchor_untouched = []
            _anchor_touched = []
            self.vp("   🪞 锚点重述：已关闭（用透传/原文）")
        # ★ [第六期 · 依据 ①] 锚点对**原问题**的保真度（零成本纯函数）。
        #   BenchDrift(arXiv:2608.11694)：含义保持的重述会让答案漂移，
        #   且**强模型损失更大** ⇒ 这里是最上游的闸门（重述跑偏则下游全白跑）。
        try:
            _q0 = str(inp.root_question or inp.question or "")
            _rf = restate_fidelity(_q0, str(view.anchor or ""))
            if _rf.get("verdict"):
                self._quant_note(view, "restate_fidelity", _rf)
                if _rf["verdict"] == "drifted":
                    self.vp("   ⚑ 锚点保真度偏低 %.2f（关键词覆盖 %.2f）"
                            "——重述可能已跑偏，下游会跟着偏"
                            % (_rf["fidelity"] or 0.0, _rf["coverage"] or 0.0))
        except Exception:
            pass'''

# ── A4：_expand_pair 解析完算阴阳分歧度（依据 ②）──
#   ★ 锚点必须唯一：`return out` 那段在 `_expand_pair` 与
#     `_expand_pair_merged_once` 各有一份 ⇒ 带上前面的 `for label, _prompt,
#     _user in jobs:` 唯一化（「补丁锚点必须断言命中 == 1」的又一次实例）。
A4 = '''        seen: List[str] = []
        out: List[Candidate] = []
        for label, _prompt, _user in jobs:
            raw = raws.get(label)
            if raw is None:
                continue
            self.vp(f"\\n💧 [{label}视角]")
            self.vp(f"   {_vp_preview(raw)}")
            for line in raw.splitlines():
                c = self._parse_candidate_line(line)
                if not c:
                    continue
                if any(_similar(c.desc, s, _DUP_SIM) for s in seen):
                    continue
                seen.append(c.desc)
                c.source = label
                out.append(c)
        return out'''
NEW4 = '''        seen: List[str] = []
        out: List[Candidate] = []
        for label, _prompt, _user in jobs:
            raw = raws.get(label)
            if raw is None:
                continue
            self.vp(f"\\n💧 [{label}视角]")
            self.vp(f"   {_vp_preview(raw)}")
            for line in raw.splitlines():
                c = self._parse_candidate_line(line)
                if not c:
                    continue
                if any(_similar(c.desc, s, _DUP_SIM) for s in seen):
                    continue
                seen.append(c.desc)
                c.source = label
                out.append(c)
        # ★ [第六期 · 依据 ②] 阴阳两臂的**分歧度**（SIEV 对抗性依从率）。
        #   低分歧 ⇒ 假对撞（只是换个说法复述），出读数作下游线索。
        try:
            _by = {}
            for _c in out:
                _by.setdefault(str(getattr(_c, "source", "") or ""), []).append(
                    str(getattr(_c, "desc", "") or ""))
            if len(_by) >= 2:
                _ks = list(_by.keys())
                _yy = yin_yang_divergence(_by[_ks[0]], _by[_ks[1]])
                if _yy:
                    self._quant_pending_yy = _yy
        except Exception:
            pass
        return out'''

# ── A5：`_expand` 调用点把分歧度写进 view（真实入口）──
A5 = '''        candidates = self._expand(inp, pool, view.anchor)'''
NEW5 = '''        candidates = self._expand(inp, pool, view.anchor)
        # ★ [第六期 · 依据 ②] 把阴阳分歧度落到本层 view（**真实入口**）。
        try:
            _yy = getattr(self, "_quant_pending_yy", None)
            if _yy:
                self._quant_note(view, "yin_yang_divergence", _yy)
                if _yy.get("verdict") == "fake_duel":
                    self.vp("   ⚑ 阴阳分歧度偏低 %.2f（重合 %.2f）"
                            "——两臂像复述，对撞未发生"
                            % (_yy.get("divergence") or 0.0,
                               _yy.get("max_sim") or 0.0))
            self._quant_pending_yy = None
        except Exception:
            pass'''

# ── A6：实例初始化 ──
A6 = '''        self.self_memory = ""'''
NEW6 = '''        self.self_memory = ""
        # ★ [第六期] 阴阳分歧度的**圈内暂存**（`_expand_pair` 算完 → 由
        #   `run()` 在同一圈内落到 view）。初始化防 AttributeError。
        self._quant_pending_yy = None'''


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
    for a, n_, tag in [(A1, NEW1, "A1"), (A6, NEW6, "A6"),
                       (A2, NEW2, "A2"), (A3, NEW3, "A3"),
                       (A4, NEW4, "A4"), (A5, NEW5, "A5")]:
        s = _apply(s, a, n_, tag)
    out = s.replace("\n", "\r\n").encode("utf-8")
    if out.decode("utf-8").count("\r\r\n"):
        print("X r-r-n"); sys.exit(1)
    SRC.write_bytes(out)
    print("OK 第六期补丁 P6-4 已打：读数真实入口接线（6 锚点）")


if __name__ == "__main__":
    main()
