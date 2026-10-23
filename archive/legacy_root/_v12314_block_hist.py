def _hist_quant(xs, p):
    """分位数（线性插值）。空输入 / None 输入 → None。"""
    if not xs:
        return None
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * float(p)
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return int(round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo)))


def _hist_blank() -> dict:
    return {"n": 0, "sources": {}, "calls": [], "tokens": [], "tri": [],
            "stop_nat": 0, "stop_cut": 0, "actual": {}, "cap": {},
            "modes": {}, "profiles": {}, "orientations": {},
            "web_hit": 0, "web_fail": 0, "web_empty": 0, "web_runs": 0,
            "mismatch": 0}


def _hist_add(acc, rec) -> None:
    """把一条记录并进累加器。字段缺省一律容忍（半损坏样本只丢自己那几项）。"""
    if not isinstance(rec, dict):
        return
    acc["n"] += 1
    _s = str(rec.get("src") or "?")
    acc["sources"][_s] = acc["sources"].get(_s, 0) + 1
    for _k in ("calls", "tokens"):
        _v = rec.get(_k)
        if isinstance(_v, int) and _v > 0:
            acc[_k].append(_v)
    _t = rec.get("tri")
    if isinstance(_t, (int, float)):
        acc["tri"].append(float(_t))
    for _a, _b in (("stop_nat", "nat"), ("stop_cut", "cut")):
        _v = rec.get(_b)
        if isinstance(_v, int) and _v >= 0:
            acc[_a] += _v
    for _key, _dst in (("actual_rounds", "actual"), ("cap_rounds", "cap")):
        for _e, _v in (rec.get(_key) or {}).items():
            if isinstance(_v, int) and _v > 0:
                acc[_dst].setdefault(_e, []).append(_v)
    for _key, _dst in (("mode", "modes"), ("profile", "profiles"),
                       ("orientation", "orientations")):
        _v = str(rec.get(_key) or "")
        if _v:
            acc[_dst][_v] = acc[_dst].get(_v, 0) + 1
    for _k in ("web_hit", "web_fail", "web_empty", "mismatch"):
        _v = rec.get(_k)
        if isinstance(_v, int) and _v > 0:
            acc[_k] += _v
    if isinstance(rec.get("web_hit"), int) and rec.get("web_hit") > 0:
        acc["web_runs"] += 1


def _hist_finish(acc) -> dict:
    out = {
        "n": acc["n"], "sources": dict(acc["sources"]),
        "calls_med": _hist_quant(acc["calls"], .5) or 0,
        "calls_p75": _hist_quant(acc["calls"], .75) or 0,
        "tokens_med": _hist_quant(acc["tokens"], .5) or 0,
        "tokens_p75": _hist_quant(acc["tokens"], .75) or 0,
        "tri_n": len(acc["tri"]),
        "tri_rate": (sum(acc["tri"]) / len(acc["tri"])) if acc["tri"] else None,
        "stop_n": acc["stop_nat"] + acc["stop_cut"],
        "cut_rate": ((acc["stop_cut"] / (acc["stop_nat"] + acc["stop_cut"]))
                     if (acc["stop_nat"] + acc["stop_cut"]) else None),
        "layer_rounds": {}, "cap_rounds": {},
        "layer_rounds_n": {}, "cap_rounds_n": {},
        "modes": dict(acc["modes"]), "profiles": dict(acc["profiles"]),
        "orientations": dict(acc["orientations"]),
        "web_hit": acc["web_hit"], "web_fail": acc["web_fail"],
        "web_empty": acc["web_empty"], "web_runs": acc["web_runs"],
        "mismatch": acc["mismatch"],
    }
    for _e in _ENTRIES:
        # ★ 每层**样本数**必须一起报出来：只有 1 份样本的「中位」不可用，
        #   策略要按样本数决定信不信它（否则会被单条噪声带跑）。
        _xs = acc["actual"].get(_e) or []
        if _xs:
            # ★ 样本数**总是**记（哪怕中位数因不足门槛而没被采纳）——
            #   否则读产物的人分不清「没有样本」与「有样本但没采纳」。
            out["layer_rounds_n"][_e] = len(_xs)
        _v = _hist_quant(_xs, .5)
        if _v and len(_xs) >= _AUTO_ACT_MIN:
            out["layer_rounds"][_e] = _v
        _xs2 = acc["cap"].get(_e) or []
        if _xs2:
            out["cap_rounds_n"][_e] = len(_xs2)
        _v2 = _hist_quant(_xs2, .5)
        if _v2:
            out["cap_rounds"][_e] = _v2
    return out


def _hist_from_packed(d: dict) -> dict:
    """从 packed 快照抽一条记录（**全量字段**，最准）。"""
    if not isinstance(d, dict):
        return {}
    q = str(d.get("question") or "")
    rec = {"src": "packed", "q": q,
           "calls": int(d.get("llm_calls") or 0),
           "tokens": int(d.get("llm_tokens") or 0),
           "mode": str(((d.get("dispatch") or {}).get("_parallel_mode")) or ""),
           "profile": str(d.get("cost_profile") or ""),
           "orientation": str(d.get("orientation") or ""),
           "actual_rounds": {}, "cap_rounds": {}}
    _t = d.get("tri_state") or [0, 0]
    try:
        if int(_t[1]):
            rec["tri"] = int(_t[0]) / int(_t[1])
    except (TypeError, ValueError, IndexError):
        pass
    for _e, _v in (d.get("views") or {}).items():
        if not isinstance(_v, dict):
            continue
        _sr = str(_v.get("stop_reason") or "")
        if _sr:
            if any(_m in _sr for _m in _STOP_CUT_MARKS):
                rec["cut"] = rec.get("cut", 0) + 1
            else:
                rec["nat"] = rec.get("nat", 0) + 1
        # ★ 字段名是 `rounds_run`（实际跑了几圈），不是 `rounds`
        #   —— 上一版这里读错，实际停圈**永远取不到**（静默）。
        _rn = _v.get("rounds_run")
        if isinstance(_rn, int) and _rn > 0:
            rec["actual_rounds"][str(_e)] = _rn
        _rc = _v.get("rounds_cap")
        if isinstance(_rc, int) and _rc > 0:
            rec["cap_rounds"][str(_e)] = _rc
    for _p in (d.get("pools") or {}).values():
        if not isinstance(_p, dict):
            continue
        rec["web_hit"] = rec.get("web_hit", 0) + len(_p.get("web_results") or [])
        rec["web_fail"] = rec.get("web_fail", 0) + len(_p.get("web_errors") or [])
        rec["web_empty"] = rec.get("web_empty", 0) + sum(
            1 for _x in (_p.get("meta") or []) if "[W-EMPTY]" in str(_x))
    _ap = d.get("_auto_plan_used") or {}
    _sug = str(_ap.get("orientation") or "")
    _act = str(d.get("orientation") or "")
    if _sug and _act and _sug != _act:
        rec["mismatch"] = 1
    return rec


_HIST_RE_CALLS = re.compile(
    r"\*\*资源\*\*[:：]\s*(\d+) 次 LLM \| (\d+) tokens")
_HIST_RE_MODE = re.compile(r"\*\*并行模式\*\*[:：]\s*([A-H]) ·")
_HIST_RE_MODE_SER = re.compile(r"\*\*并行模式\*\*[:：]\s*(严格串行)")
_HIST_RE_PROF = re.compile(r"\*\*成本档位\*\*[:：]\s*(\w+)")
_HIST_RE_ROUTE = re.compile(r"\*\*调度\*\*[:：]\s*(.+)")
_HIST_RE_LAYER = re.compile(r"([\u4e00-\u9fff]+)\((\d+)圈\)")
_HIST_RE_STOP = re.compile(
    r"\*\*停止\*\*[:：]\s*自然 (\d+) 层 / 被截断（体力耗尽）(\d+) 层")
_HIST_RE_ORI = re.compile(r"\*\*取向\*\*[:：]\s*(auto|boundary|decision)")
_HIST_RE_Q = re.compile(r"^# 元 DGTF · (.+)$", re.M)
_HIST_LAYER2E = {"修行": "0", "研究": "1", "对撞": "both", "元": "all"}


def _hist_from_md(head: str) -> dict:
    """从产物 md 的**头部片段**抽一条记录。

    ★ 只读前 8KB：头部信息全在里面，产物正文可能几百 KB。
    ★ 这里的圈数是**配置给的种子上限**（`**调度**：修行(4圈)`），
      不是实际停圈 —— 归到 `cap_rounds`，不与 `actual_rounds` 混。
    """
    if not head:
        return {}
    m = _HIST_RE_CALLS.search(head)
    if not m:
        return {}
    rec = {"src": "md", "calls": int(m.group(1)), "tokens": int(m.group(2)),
           "actual_rounds": {}, "cap_rounds": {}}
    _mq = _HIST_RE_Q.search(head)
    rec["q"] = _mq.group(1).strip() if _mq else ""
    _mm = _HIST_RE_MODE.search(head) or _HIST_RE_MODE_SER.search(head)
    rec["mode"] = _mm.group(1) if _mm else ""
    _mp = _HIST_RE_PROF.search(head)
    rec["profile"] = _mp.group(1) if _mp else ""
    _mo = _HIST_RE_ORI.search(head)
    rec["orientation"] = _mo.group(1) if _mo else ""
    _mr = _HIST_RE_ROUTE.search(head)
    if _mr:
        for _a, _b in _HIST_RE_LAYER.findall(_mr.group(1)):
            rec["cap_rounds"][_HIST_LAYER2E.get(_a, _a)] = int(_b)
    _ms = _HIST_RE_STOP.search(head)
    if _ms:
        rec["nat"], rec["cut"] = int(_ms.group(1)), int(_ms.group(2))
    return rec


def _hist_from_batch(d) -> List[dict]:
    """从跑批 JSON（`*_runs.json`）抽记录：富字段、样本少。"""
    out: List[dict] = []
    if not isinstance(d, dict):
        return out
    for _x in (d.get("runs") or []):
        if not isinstance(_x, dict) or not _x.get("ok"):
            continue
        out.append({"src": "batch",
                    "q": str(_x.get("question") or ""),
                    "calls": int(_x.get("llm_calls") or _x.get("calls") or 0),
                    "mode": "", "profile": "", "orientation": "",
                    "actual_rounds": {}, "cap_rounds": {},
                    "web_hit": int(_x.get("web_n") or 0),
                    "web_fail": int(_x.get("web_errors_n") or 0),
                    "web_empty": int(_x.get("web_empty_n") or 0)})
    return out


def _auto_history(save_dir, limit: int = 200, cfg=None,
                  want_md: bool = True, want_batch: bool = True) -> dict:
    """把历史真跑语料抽成可复用的读数 —— **三类来源**，样本量从 1 涨到几百。

    ① `**/*.packed.json`  —— 全量字段（最准），含 `views.*.rounds_run`；
    ② `**/*.md`           —— 头部行（覆盖最广）；只读前 8KB；
    ③ `*_runs.json`（仓库根）—— 跑批记录，富字段（llm_calls / web_*），样本少。

    ★ 为什么三类都要：`outputs/` 里产物 md 有几百份，而 packed 只有最近几份
      （旧版本不落 packed）。只读 packed ⇒ 历史几乎为空，自适应形同虚设。
    ★ 读数按**题型分桶**（`by_type.fact` / `by_type.nonfact`），策略才能
      「同类题比同类题」；扁平那份是全语料，用作**相对基准**。
    ★ 半损坏样本只跳过自己：单文件解析失败不影响其它样本，零样本也不崩。
    """
    _cfg = cfg if isinstance(cfg, dict) else {}
    _lim = max(1, int(limit or 200))
    _acc_all, _acc_f, _acc_nf = _hist_blank(), _hist_blank(), _hist_blank()

    def _put(rec):
        if not rec:
            return
        _hist_add(_acc_all, rec)
        _q = str(rec.get("q") or "")
        if not _q:
            return
        if _has_decision_context(_q):
            _hist_add(_acc_nf, rec)
        else:
            _hist_add(_acc_f, rec)

    try:
        _root = Path(str(save_dir or "outputs"))
    except Exception:  # noqa: BLE001
        return _hist_finish(_acc_all)

    def _files(pat):
        try:
            if not _root.is_dir():
                return []
            _fs = sorted(_root.rglob(pat),
                         key=lambda p: p.stat().st_mtime, reverse=True)
            return _fs[:_lim]
        except Exception as exc:  # noqa: BLE001
            logger.warning("调度历史：列 %s 失败（%s）", pat, exc)
            return []

    for _f in _files("*.packed.json"):
        try:
            _put(_hist_from_packed(json.loads(
                _f.read_text(encoding="utf-8"))))
        except Exception:  # noqa: BLE001
            continue
    if want_md:
        for _f in _files("*.md"):
            try:
                with open(_f, "r", encoding="utf-8",
                          errors="replace") as _fh:
                    _put(_hist_from_md(_fh.read(8192)))
            except Exception:  # noqa: BLE001
                continue
    if want_batch:
        try:
            _broot = _root.resolve().parent
            for _f in sorted(_broot.glob("*_runs.json")):
                if _f.name.startswith("_bak_"):
                    continue
                try:
                    for _r in _hist_from_batch(
                            json.loads(_f.read_text(encoding="utf-8"))):
                        _put(_r)
                except Exception:  # noqa: BLE001
                    continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("调度历史：跑批 JSON 失败（%s）", exc)

    out = _hist_finish(_acc_all)
    out["by_type"] = {"fact": _hist_finish(_acc_f),
                      "nonfact": _hist_finish(_acc_nf)}
    return out


def _hist_for(feat, hist) -> dict:
    """取**与本题同题型**的那份历史（无同型样本则退全语料）。"""
    _bt = (hist or {}).get("by_type") or {}
    _k = "fact" if feat.get("fact") else "nonfact"
    _sub = _bt.get(_k) or {}
    return _sub if int(_sub.get("n") or 0) > 0 else (hist or {})
