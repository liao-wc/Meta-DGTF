def _hist_wquant(pairs, p, as_int: bool = True):
    """**加权**分位数（线性插值）。`pairs = [(值, 权重)]`；空 → None。

    ★ 为什么要加权：语料跨了十几天，旧样本的「成本/停圈」是**旧配置**下的读数
      （那时默认给满 12 圈），直接与今天的读数拉平均会系统性偏向旧行为。
      时间衰减（半衰期可配）让新样本说话更响。
    ★ `as_int=False` 用于比率类读数（如三态一致率），否则会被截成 0/1。
    """
    _ps = [(float(v), float(w)) for v, w in (pairs or [])
           if v is not None and w and w > 0]
    if not _ps:
        return None
    _ps.sort(key=lambda x: x[0])
    _tot = sum(w for _, w in _ps)
    if _tot <= 0:
        return None
    _target = p * _tot
    _acc = 0.0
    for _i, (_v, _w) in enumerate(_ps):
        _nxt = _acc + _w
        if _nxt >= _target:
            if _i == 0 or _w <= 0:
                _r = _v
            else:
                _prev = _ps[_i - 1][0]
                _r = _prev + (_v - _prev) * ((_target - _acc) / _w)
            return int(round(_r)) if as_int else round(_r, 4)
        _acc = _nxt
    _last = _ps[-1][0]
    return int(round(_last)) if as_int else round(_last, 4)


def _hist_quant(xs, p):
    """无权重的分位数（`_hist_wquant` 的退化情形）。保留给「权重全等」对照。"""
    return _hist_wquant([(x, 1.0) for x in (xs or [])], p)


def _hist_blank() -> dict:
    return {"n": 0, "sources": {}, "calls": [], "tokens": [], "tri": [],
            "stop_nat": 0, "stop_cut": 0, "actual": {}, "cap": {},
            "modes": {}, "profiles": {}, "orientations": {},
            "web_hit": 0, "web_fail": 0, "web_empty": 0, "web_runs": 0,
            "mismatch": 0}


def _hist_add(acc, rec, w: float = 1.0) -> None:
    """把一条记录并进累加器（带权重）。字段缺省一律容忍。"""
    if not isinstance(rec, dict):
        return
    _w = float(w) if (w and w > 0) else 1.0
    acc["n"] += 1
    _s = str(rec.get("src") or "?")
    acc["sources"][_s] = acc["sources"].get(_s, 0) + 1
    for _k in ("calls", "tokens"):
        _v = rec.get(_k)
        if isinstance(_v, int) and _v > 0:
            acc[_k].append((_v, _w))
    _t = rec.get("tri")
    if isinstance(_t, (int, float)):
        acc["tri"].append((float(_t), _w))
    for _a, _b in (("stop_nat", "nat"), ("stop_cut", "cut")):
        _v = rec.get(_b)
        if isinstance(_v, int) and _v >= 0:
            acc[_a] += _v
    for _key, _dst in (("actual_rounds", "actual"), ("cap_rounds", "cap")):
        for _e, _v in (rec.get(_key) or {}).items():
            if isinstance(_v, int) and _v > 0:
                acc[_dst].setdefault(_e, []).append((_v, _w))
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
        "calls_med": _hist_wquant(acc["calls"], .5) or 0,
        "calls_p75": _hist_wquant(acc["calls"], .75) or 0,
        "tokens_med": _hist_wquant(acc["tokens"], .5) or 0,
        "tokens_p75": _hist_wquant(acc["tokens"], .75) or 0,
        "tri_n": len(acc["tri"]),
        "tri_rate": _hist_wquant(acc["tri"], .5, as_int=False),
        "tri_p10": _hist_wquant(acc["tri"], .10, as_int=False),
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
        _xs = acc["actual"].get(_e) or []
        if _xs:
            # ★ 样本数**总是**记（哪怕中位数因不足门槛而没被采纳）——
            #   否则读产物的人分不清「没有样本」与「有样本但没采纳」。
            out["layer_rounds_n"][_e] = len(_xs)
        _v = _hist_wquant(_xs, .5)
        if _v and len(_xs) >= _AUTO_ACT_MIN:
            out["layer_rounds"][_e] = _v
        _xs2 = acc["cap"].get(_e) or []
        if _xs2:
            out["cap_rounds_n"][_e] = len(_xs2)
        _v2 = _hist_wquant(_xs2, .5)
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
_HIST_RE_TRI = re.compile(r"\*\*三态判决一致率\*\*[:：]\s*(\d+)\s*/\s*(\d+)")
_HIST_RE_WEB = re.compile(
    r"\*\*外部锚点 · 联网\*\*（`web_search`）[:：](.*)")
_HIST_RE_WEB_OK = re.compile(r"收\s*(\d+)\s*条")
_HIST_RE_WEB_FAIL = re.compile(r"失败\s*(\d+)\s*条")
_HIST_LAYER2E = {"修行": "0", "研究": "1", "对撞": "both", "元": "all"}


def _hist_from_md(head: str) -> dict:
    """从产物 md 的**头部片段**抽一条记录。

    ★ 只读前 8KB：头部信息全在里面，产物正文可能几百 KB。
    ★ 这里的圈数是**配置给的种子上限**（`**调度**：修行(4圈)`），
      不是实际停圈 —— 归到 `cap_rounds`，不与 `actual_rounds` 混。
    ★ 抽不到的字段就**不写键**（不要写 0）—— 否则「零样本」与「样本值为 0」
      会被混为一谈（`web_fail = 0` 与「没有联网这一行」是两件事）。
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
    # ★ 三态一致率：产物里 254/368 都写了，而上一版抽取器漏了它 ——
    #   于是「同类题一致率」这条读数只有 n=1，规则形同没校准。
    _mt = _HIST_RE_TRI.search(head)
    if _mt and int(_mt.group(2)) > 0:
        rec["tri"] = int(_mt.group(1)) / int(_mt.group(2))
    # ★ 联网行（本版起产物才有）：把「收了 N 条 / 失败 N 条」也吃进来。
    _mw = _HIST_RE_WEB.search(head)
    if _mw:
        _body = _mw.group(1)
        _ok = _HIST_RE_WEB_OK.search(_body)
        _fa = _HIST_RE_WEB_FAIL.search(_body)
        if _ok:
            rec["web_hit"] = int(_ok.group(1))
        if _fa:
            rec["web_fail"] = int(_fa.group(1))
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


def _hist_decay(cfg) -> float:
    """时间衰减的半衰期（天）。`auto.history_halflife_days`，缺省 14；0 = 不衰减。"""
    try:
        v = float((((cfg or {}).get("auto") or {}).get(
            "history_halflife_days", 14)) or 0)
    except (TypeError, ValueError):
        v = 14.0
    return max(0.0, v)


def _hist_weight(mtime, half_life: float, now: float = None) -> float:
    """`0.5 ** (age_days / half_life)`；半衰期 ≤0 或 mtime 缺失 → 1.0（不衰减）。"""
    if not half_life or not mtime:
        return 1.0
    _now = now if now is not None else time.time()
    _age = max(0.0, (_now - float(mtime)) / 86400.0)
    return float(0.5 ** (_age / half_life))


def _auto_history(save_dir, limit: int = 200, cfg=None,
                  want_md: bool = True, want_batch: bool = True) -> dict:
    """把历史真跑语料抽成可复用的读数 —— 三类来源 + 分层 + 时间衰减。

    ① `**/*.packed.json`  —— 全量字段（最准），含 `views.*.rounds_run`；
    ② `**/*.md`           —— 头部行（覆盖最广）；只读前 8KB；
    ③ `*_runs.json`（仓库根）—— 跑批记录，富字段（llm_calls / web_*），样本少。

    ★ **`limit` 是「每题型上限」**（不是总数）：按题型分两桶各自最多取 `limit`
      条 —— 否则窗口一缩，某一型（尤其是事实型）会被整体挤掉，
      「按题型比同类」就退化成「比全语料」。
    ★ **时间衰减**：权重 `0.5 ** (age_days / 半衰期)`。旧样本是旧配置下的读数，
      不加权会让新读数被系统性拉向旧行为。半衰期 0 = 关掉衰减。
    ★ 半损坏样本只跳过自己；零样本不崩；抽不到的字段**不写键**。
    """
    _cfg = cfg if isinstance(cfg, dict) else {}
    _lim = max(1, int(limit or 200))
    _hl = _hist_decay(_cfg)
    _now = time.time()
    _acc_all, _acc_f, _acc_nf = _hist_blank(), _hist_blank(), _hist_blank()
    _cnt = {"f": 0, "nf": 0}

    def _put(rec, mtime):
        if not rec:
            return False
        _q = str(rec.get("q") or "")
        _w = _hist_weight(mtime, _hl, _now)
        _hist_add(_acc_all, rec, _w)
        if _q and _has_decision_context(_q):
            if _cnt["nf"] < _lim:
                _hist_add(_acc_nf, rec, _w)
                _cnt["nf"] += 1
        elif _q:
            if _cnt["f"] < _lim:
                _hist_add(_acc_f, rec, _w)
                _cnt["f"] += 1
        # 两桶都满 ⇒ 可以提前停（不再往下扫旧文件）
        return _cnt["f"] >= _lim and _cnt["nf"] >= _lim

    try:
        _root = Path(str(save_dir or "outputs"))
    except Exception:  # noqa: BLE001
        return _hist_finish(_acc_all)

    def _files(pat, cap):
        try:
            if not _root.is_dir():
                return []
            _fs = sorted(_root.rglob(pat),
                         key=lambda p: p.stat().st_mtime, reverse=True)
            return _fs[:cap]
        except Exception as exc:  # noqa: BLE001
            logger.warning("调度历史：列 %s 失败（%s）", pat, exc)
            return []

    # ★ 扫描上限 4×limit：两桶各要 limit 条，留 2 倍余量给「某一型被挤掉」的情况。
    _cap = max(_lim * 4, _lim)
    for _f in _files("*.packed.json", _cap):
        try:
            _done = _put(_hist_from_packed(json.loads(
                _f.read_text(encoding="utf-8"))), _f.stat().st_mtime)
            if _done:
                break
        except Exception:  # noqa: BLE001
            continue
    if want_md:
        for _f in _files("*.md", _cap):
            try:
                with open(_f, "r", encoding="utf-8",
                          errors="replace") as _fh:
                    _rec = _hist_from_md(_fh.read(8192))
                if _put(_rec, _f.stat().st_mtime):
                    break
            except Exception:  # noqa: BLE001
                continue
    if want_batch:
        try:
            _broot = _root.resolve().parent
            for _f in sorted(_broot.glob("*_runs.json")):
                if _f.name.startswith("_bak_"):
                    continue
                try:
                    _mt = _f.stat().st_mtime
                    for _r in _hist_from_batch(
                            json.loads(_f.read_text(encoding="utf-8"))):
                        _put(_r, _mt)
                except Exception:  # noqa: BLE001
                    continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("调度历史：跑批 JSON 失败（%s）", exc)

    out = _hist_finish(_acc_all)
    out["_limit_per_type"] = _lim
    out["_half_life_days"] = _hl
    out["by_type"] = {"fact": _hist_finish(_acc_f),
                      "nonfact": _hist_finish(_acc_nf)}
    return out


def _hist_for(feat, hist) -> dict:
    """取**与本题同题型**的那份历史（无同型样本则退全语料）。"""
    _bt = (hist or {}).get("by_type") or {}
    _k = "fact" if feat.get("fact") else "nonfact"
    _sub = _bt.get(_k) or {}
    return _sub if int(_sub.get("n") or 0) > 0 else (hist or {})
