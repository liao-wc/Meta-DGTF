#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.31 补丁 · 第 2 阶段：EML 接线（跑前 recall / 跑后 consolidate）。"""
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


METHODS = '''    # ================================================== EML 经验记忆回路
    def _eml_prepare(self, question: str) -> dict:
        """**跑前**：recall（读）→ 决定生效面 → 留痕。返回 `{used_ids, applied}`。

        ★ 生效面只有两处（都属「调度/守卫阈值」，不碰答案）：
          · `rounds_plan`：截断过的层 +1 圈（`schedule/rounds_delta`）；
          · `self._duty_floor`：guard 类条目建议的阈值。
        ★ `mode == "shadow"` ⇒ 读出来**只留痕不生效**（F1 隔离；与 off 的差别
          只是「记录下我本来会怎么做」）。
        """
        _c = getattr(self, "_eml_cfg", None) or {}
        _mode = str(_c.get("mode", _EML_MODE_DEFAULT))
        self._eml_used = []
        self._eml_applied = []
        self._eml_mode = _mode
        if _mode == "off":
            return {"mode": _mode, "used_ids": [], "applied": []}
        _dir = Path(str(_c.get("dir") or eml_dir()))
        _pb = eml_read_jsonl(_dir / _EML_PLAYBOOK)
        _now = time.time()
        _h = float(_c.get("halflife_days", _EML_HALFLIFE_DAYS) or 14.0)
        _k = int(_c.get("top_k", _EML_TOP_K) or 3)
        _rec = []
        for _kind in _EML_KINDS:
            for _it in eml_recall(_pb, _kind, _now, halflife=_h, top_k=_k):
                _it["kind"] = _kind
                _rec.append(_it)
        _rec.sort(key=lambda x: -x["score"])
        self._eml_used = [{"id": x["id"], "kind": x["kind"],
                           "score": x["score"], "action": x["action"],
                           "applied": False} for x in _rec]
        return {"mode": _mode, "used_ids": [x["id"] for x in _rec],
                "applied": self._eml_applied}

    def _eml_apply(self, rounds_plan: dict) -> list:
        """把 recall 到的 active 条目落到**生效面**（仅 `mode=="on"`）。"""
        _applied = []
        if str(getattr(self, "_eml_mode", "off")) != "on":
            return _applied
        for _it in (getattr(self, "_eml_used", None) or []):
            _a = _it.get("action") or {}
            _key = str(_a.get("key") or "")
            if _key == "rounds_delta" and isinstance(rounds_plan, dict):
                _lyr = str(_a.get("layer") or "")
                _d = int(_a.get("delta", 1) or 1)
                if _lyr in rounds_plan:
                    _old = int(rounds_plan.get(_lyr) or 1)
                    rounds_plan[_lyr] = max(1, _old + _d)
                    _it["applied"] = True
                    _applied.append({"id": _it["id"], "key": _key,
                                     "layer": _lyr, "rounds": "%d→%d"
                                     % (_old, rounds_plan[_lyr])})
            elif _key == "duty_floor":
                _fl = _a.get("floor")
                try:
                    self._duty_floor = float(_fl)
                except (TypeError, ValueError):
                    continue
                _it["applied"] = True
                _applied.append({"id": _it["id"], "key": _key,
                                 "floor": self._duty_floor})
        self._eml_applied = _applied
        return _applied

    def _eml_finish(self, result: dict) -> dict:
        """**跑后**：micro 反思 → 质量闸 → 合并（只增）→ meso 升级 → 遗忘 → 摘要。

        ★ 返回写进产物 `result["playbook"]` 的块（口径：读数 + 留痕，不是打分）。
        """
        _c = getattr(self, "_eml_cfg", None) or {}
        _mode = str(_c.get("mode", _EML_MODE_DEFAULT))
        _blk = {"mode": _mode, "used": list(getattr(self, "_eml_used", None) or []),
                "applied": list(getattr(self, "_eml_applied", None) or []),
                "candidates": [], "gated_out": [], "merged": [],
                "promoted": [], "retired": [], "parents": []}
        if _mode == "off":
            return _blk
        try:
            _dir = Path(str(_c.get("dir") or eml_dir()))
            _dir.mkdir(parents=True, exist_ok=True)
            _now = time.time()
            _ep = episode_from_result(result, t=_now)
            _ep["used_ids"] = _blk["used"]
            eml_append_jsonl(_dir / _EML_EPISODES, _ep)
            _pb = eml_read_jsonl(_dir / _EML_PLAYBOOK)
            _n0 = len(_pb)
            _pn = int(_c.get("promote_n", _EML_PROMOTE_N) or 3)
            _cands = eml_candidates_from_result(result, ep=_ep)
            for _cd in _cands:
                _ok, _why = gate_check(_cd, _pb, promote_n=_pn)
                if not _ok:
                    _blk["gated_out"].append({"cand": _cd.get("action"),
                                              "why": _why})
                    continue
                _ent = eml_merge_candidate(_pb, _cd, _now)
                _blk["candidates"].append(_cd.get("action"))
                _blk["merged"].append(_ent.get("id"))
            _blk["promoted"] = eml_promote(_pb, promote_n=_pn)
            _blk["retired"] = [e.get("id") for e in
                               eml_sweep_forget(_pb, _now, promote_n=_pn)]
            _blk["parents"] = eml_aggregate_macro(_pb, _now)
            # ★ 落盘两条路（F5「只增不删」的物理保证）：
            #   · 有新行 ⇒ 整表写（行数**只增**，写前断言不减少）；
            #   · 无新行 ⇒ 走 `eml_rewrite_jsonl`（它自断言行数/id 集合不变）。
            if len(_pb) > _n0:
                with (_dir / _EML_PLAYBOOK).open(
                        "w", encoding="utf-8", newline="\n") as _f:
                    for _r in _pb:
                        _f.write(json.dumps(_r, ensure_ascii=False) + "\n")
            elif len(_pb) == _n0:
                eml_rewrite_jsonl(_dir / _EML_PLAYBOOK, _pb)
            else:
                raise RuntimeError("EML 行数减少（%d→%d），违反只增不删"
                                   % (_n0, len(_pb)))
            eml_write_memory_md(_pb, base=_c.get("dir_base"))
            _blk["n_playbook"] = len(_pb)
            self.vp(f"\\n🧠 EML：用 {len(_blk['used'])} 条（生效 "
                    f"{len(_blk['applied'])}）· 过闸新增 "
                    f"{len(_blk['merged'])} · 隔离 "
                    f"{len(_blk['gated_out'])} · 升级 {len(_blk['promoted'])} "
                    f"· 遗忘 {len(_blk['retired'])} · 库 {len(_pb)} 条")
        except Exception as _e:
            _blk["error"] = "%s: %s" % (type(_e).__name__, _e)
            self.vp(f"\\n🧠 EML：异常（已留痕，不阻断）{_blk['error']}")
        return _blk

'''


def main():
    s = _load()

    # 0) 导入 time（若未导入）
    if "\nimport time\n" not in s:
        s = rep(s, "\nimport sys\n", "\nimport sys\nimport time\n",
                "import time", expect=1)

    # 1) 实例字段（挂在既有 LDG 阈值初始化之后）
    old_i = '''        self._duty_carry: List[str] = []'''
    new_i = '''        self._duty_carry: List[str] = []
        # [EML 可配] 经验记忆回路（默认 shadow ⇒ 出厂零行为差）。
        try:
            _pl = dict(config.get("playbook") or {})
        except Exception:
            _pl = {}
        self._eml_cfg = _pl
        self._eml_mode = str(_pl.get("mode", _EML_MODE_DEFAULT))
        self._eml_used: List[dict] = []
        self._eml_applied: List[dict] = []'''
    s = rep(s, old_i, new_i, "EML 实例字段")

    # 2) 方法：插在 `def run(self, question: str,` 之前
    _anchor = "    def run(self, question: str,"
    s = rep(s, _anchor, METHODS + _anchor, "EML 方法插入")

    # 3) run() 跑前：recall（在 rounds_plan 算好之后）
    old_pre = "        rounds_plan = self._rounds_plan(rounds)"
    new_pre = '''        rounds_plan = self._rounds_plan(rounds)
        # ★ [EML] 跑前：读记忆（recall）→（仅 mode=on）落到生效面 → 留痕。
        try:
            self._eml_prepare(question)
            self._eml_apply(rounds_plan)
        except Exception as _ee:
            self.vp(f"\\n🧠 EML 读记忆异常（不阻断）：{_ee}")'''
    s = rep(s, old_pre, new_pre, "run 跑前 recall")

    # 4) run() 跑后：consolidate（在 return 之前）
    old_post = '''        if isinstance(packed, dict):
            self._layer_guard(packed)
        return packed'''
    new_post = '''        if isinstance(packed, dict):
            self._layer_guard(packed)
        # ★ [EML] 跑后：写 episode + 抽候选 + 过闸 + 只增合并 + 升级 + 遗忘。
        if isinstance(packed, dict):
            try:
                packed["playbook"] = self._eml_finish(packed)
            except Exception as _ef:
                packed["playbook"] = {"error": "%s: %s"
                                      % (type(_ef).__name__, _ef)}
        return packed'''
    s = rep(s, old_post, new_post, "run 跑后 consolidate")

    _save(s)
    print("OK 第 2 阶段（EML 接线）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert s2.count("def _eml_prepare(self, question: str) -> dict:") == 1
    assert s2.count("self._eml_finish(packed)") == 1
    assert s2.count("self._eml_apply(rounds_plan)") == 1
    print("复读校验通过")


if __name__ == "__main__":
    main()
