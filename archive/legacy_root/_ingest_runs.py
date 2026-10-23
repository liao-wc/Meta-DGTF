# -*- coding: utf-8 -*-
"""
_ingest_runs.py —— 把历史跑动结构化入库到 runs.sqlite3。

目标（服务两个长期任务）：
  · 为「按需调度」积累 layer_contribution（每层实际圈数 / 停止理由 / 是否空转）
  · 为「零触发机制」积累每次跑动里各机制的触发次数

数据源三处，按**可靠性**排序，同名优先取更硬的那个：
  ① *.full.json 与 产物内嵌 packed JSON —— MetaDGTF.run() 的完整返回，
     含 layer_contribution 与 pools（每层机制清单）。**唯一权威**的结构化源。
  ② outputs/*.md —— 主力源。`## 附：逐层明细` 段有每层实际圈数 + 螺旋停止理由；
     `## 池` 段有每层 amps/threads/probes/主动悬置/延迟债务/子问题；
     `## 悬置总览` 段有对撞悬置与升级。
  ③ 顶层 *.log —— 补 question/route/mode/calls/tokens/耗时，以及
     `layer_contribution={...}` 尾行。

口径复用 _convergence_matrix.py（题型分类 / 停止分类 / 层体正则），不另起一套。
所有计数类字段**无条件写入**（拿不到写 NULL），以区分「值是 0」与「没解析到」——
这是项目记忆里反复强调的坑。

用法：
  python -u _ingest_runs.py            # 全量回填（幂等，重跑不产生重复行）
  python -u _ingest_runs.py --summary  # 只从已有库出统计摘要
"""
import re
import sys
import ast
import json
import sqlite3
import glob
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "runs.sqlite3"
OUT_DIR = HERE / "outputs"

sys.path.insert(0, str(HERE))
# 复用既有口径：停止分类、题型分类、产物层解析、日志解析
from _convergence_matrix import (                     # noqa: E402
    scan_output, scan_log, classify_stop, guess_type,
)

LAYERS = ("0", "1", "both", "all")
# 机制 → 产物 `## 池` 段里对应的中文标签
POOL_LABELS = {
    "amps": "& 印记",
    "threads": "悬空线头",
    "probes": "探针",
    "suspensions": "主动悬置",
    "deferrals": "延迟债务",
}
# 计数表列（顺序即建表顺序）
MECH_COLS = ["amps", "threads", "probes", "suspensions", "duel_suspensions",
             "deferrals", "escalations", "decidability_log", "engagements",
             "refinements", "sub_questions"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id              TEXT PRIMARY KEY,
    source              TEXT,      -- output / log_only
    output_path         TEXT,
    output_stem         TEXT,
    log_path            TEXT,
    full_json_path      TEXT,
    link_src            TEXT,      -- 产物= / mtime / orphan / log_only
    run_time            TEXT,      -- ISO 时间串（产物头部优先，退 mtime）
    qtype               TEXT,      -- 题型 F/O/P/T/?（复用 guess_type 口径）
    question            TEXT,
    route               TEXT,
    mode                TEXT,
    rounds_planned      TEXT,      -- JSON 串（规划给的圈数）
    cost_profile        TEXT,
    orientation         TEXT,
    llm_calls           INTEGER,
    llm_tokens          INTEGER,
    duration_s          INTEGER,   -- 日志「耗时 Ns」
    decidability        TEXT,
    coverage            REAL,      -- 可判定覆盖率 %
    n_layers_md         INTEGER,   -- 产物逐层明细里抽到的层数
    has_layer_contrib   INTEGER,   -- 是否取到 layer_contribution（0/1）
    contrib_src         TEXT       -- full_json / embed_json / log_line / NULL
);

-- 每层明细：来自产物「附：逐层明细」段（每层实际圈数 + 停止理由）
CREATE TABLE IF NOT EXISTS layer_detail (
    run_id          TEXT NOT NULL,
    layer           TEXT NOT NULL,
    rounds_actual   INTEGER,
    cap             INTEGER,
    stop_category   TEXT,          -- 复用 classify_stop 口径
    stop_raw        TEXT,
    defer_n         INTEGER,       -- 「停止判据被未深入方向推迟」次数
    clean           TEXT,
    unsettled       INTEGER,
    debt_active     INTEGER,
    src             TEXT,
    PRIMARY KEY (run_id, layer)
);

-- 层贡献：来自 packed 的 layer_contribution 字段（权威；含 idle）
CREATE TABLE IF NOT EXISTS layer_contribution (
    run_id          TEXT NOT NULL,
    layer           TEXT NOT NULL,
    rounds_actual   INTEGER,
    stop_reason     TEXT,
    stop_category   TEXT,
    idle            INTEGER,       -- 1/0，取不到写 NULL
    src             TEXT,          -- full_json / embed_json / log_line
    PRIMARY KEY (run_id, layer)
);

-- 零触发机制计数：逐层。rate 类统计由摘要现算。
-- 拿不到 = NULL（不是 0）；能数出来但为 0 = 0。
CREATE TABLE IF NOT EXISTS mechanisms (
    run_id          TEXT NOT NULL,
    layer           TEXT NOT NULL,
    amps            INTEGER,
    threads         INTEGER,
    probes          INTEGER,
    suspensions     INTEGER,
    duel_suspensions INTEGER,
    deferrals       INTEGER,
    escalations     INTEGER,
    decidability_log INTEGER,
    engagements     INTEGER,
    refinements     INTEGER,
    sub_questions   INTEGER,
    src             TEXT,          -- pools_json / pool_section / xuanzhi
    PRIMARY KEY (run_id, layer)
);
CREATE INDEX IF NOT EXISTS idx_lc_run ON layer_contribution(run_id);
CREATE INDEX IF NOT EXISTS idx_mech_run ON mechanisms(run_id);
"""


# ---------------- 产物头部解析 ----------------

def _num_after(text, pat, cast=int):
    m = re.search(pat, text)
    if not m:
        return None
    try:
        return cast(m.group(1))
    except (ValueError, IndexError):
        return None


def parse_output_header(text):
    """从产物头部抽：时间/版权/取向/资源/可判定性/调度/路由。"""
    d = {}
    m = re.search(r"^\*\*时间\*\*[:：]\s*(\S+)", text, re.M)
    d["run_time"] = m.group(1) if m else None

    m = re.search(r"\*\*成本档位\*\*[:：]\s*([^\s（(]+)", text)
    d["cost_profile"] = m.group(1) if m else None

    m = re.search(r"\*\*取向\*\*[:：]\s*([^\s（(]+)", text)
    d["orientation"] = m.group(1) if m else None

    m = re.search(r"\*\*并行模式\*\*[:：]\s*([^\s（(]+)", text)
    if m:
        d["mode"] = "serial" if m.group(1) == "严格串行" else m.group(1)

    m = re.search(r"\*\*资源\*\*[:：]\s*(\d+)\s*次\s*LLM\s*[|｜]\s*(\d+)\s*tokens", text)
    if m:
        d["llm_calls"] = int(m.group(1))
        d["llm_tokens"] = int(m.group(2))

    m = re.search(r"^\*\*可判定性\*\*[:：]\s*(\w+)", text, re.M)
    d["decidability"] = m.group(1) if m else None

    m = re.search(r"^\*\*调度\*\*[:：]\s*(.+)$", text, re.M)
    d["dispatch_raw"] = m.group(1).strip() if m else None

    # 路由：显化段的「route=0 → 1」
    m = re.search(r"路由选择\*\*[:：]\s*route=([^\s（(]+)", text)
    if m:
        d["route"] = m.group(1)

    # 题面：一级标题「# 元 DGTF · <question>」
    m = re.search(r"^#\s*元\s*DGTF\s*[·・]\s*(.+)$", text, re.M)
    d["question"] = m.group(1).strip() if m else None
    return d


def parse_pool_section(text):
    """解析 `## 池` 段，返回 {layer: {mech: count}}（逐层）。"""
    sec = None
    m = re.search(r"^##\s*池\s*$", text, re.M)
    if not m:
        return {}
    rest = text[m.end():]
    e = re.search(r"^##\s", rest, re.M)
    sec = rest[:e.start()] if e else rest

    heads = [(h.start(), h.group(1), h.end())
             for h in re.finditer(r"^###\s+(0|1|both|all)\s*池", sec, re.M)]
    out = {}
    for i, (start, lid, hend) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(sec)
        body = sec[hend:end]
        rec = {}
        for mech, label in POOL_LABELS.items():
            rec[mech] = _num_after(body, re.escape(label) + r"\s*(\d+)\s*条")
        # 子问题行带冒号：「子问题 6 条：可判定 …」——加冒号避免误配
        # 「名下有挂账的子问题 0 条｜」这类无冒号的行
        rec["sub_questions"] = _num_after(body, r"子问题\s*(\d+)\s*条[：:]")
        if any(v is not None for v in rec.values()):
            out[lid] = rec
    return out


def parse_xuanzhi(text):
    """解析 `## 悬置总览`，返回 {layer: {mech: count}}。
    只取产物池段没有的两个：对撞悬置（both）、升级（归 1 层「研究延迟处理」）。"""
    m = re.search(r"^##\s*悬置总览\s*$", text, re.M)
    if not m:
        return {}
    rest = text[m.end():]
    e = re.search(r"^##\s", rest, re.M)
    sec = rest[:e.start()] if e else rest

    subs = re.split(r"^###\s+", sec, flags=re.M)[1:]
    out = {}
    for chunk in subs:
        lines = chunk.splitlines()
        title = lines[0].strip() if lines else ""
        items = [ln.strip() for ln in lines
                 if ln.strip().startswith("- ")]
        # 去掉「（无）」这类占位
        items = [it for it in items
                 if it[2:].strip() and "（无）" not in it[2:]]
        if "对撞悬置的张力" in title:
            out.setdefault("both", {})["duel_suspensions"] = len(items)
        elif "研究延迟处理的" in title:
            esc = sum(1 for it in items if "escalated" in it)
            out.setdefault("1", {})["escalations"] = esc
    return out


def parse_embedded_json(text):
    """产物末尾「附录 · 全量字段」里内嵌的 packed JSON。取首个可解析块。"""
    if "附录 · 全量字段" not in text:
        return None
    for m in re.finditer(r"```json\s*(\{.*?\})\s*```", text, re.S):
        try:
            return json.loads(m.group(1))
        except Exception:
            continue
    return None


# ---------------- packed 结构抽取 ----------------

def contrib_from_packed(packed, src):
    """从 packed 取 layer_contribution → [(layer, rounds, stop, category, idle, src)]。"""
    lc = packed.get("layer_contribution")
    if not isinstance(lc, dict) or not lc:
        return []
    rows = []
    for lid, v in lc.items():
        if not isinstance(v, dict):
            continue
        stop = v.get("stop")
        rows.append((str(lid), v.get("rounds"), stop,
                     classify_stop(stop) if stop else None,
                     v.get("idle"), src))
    return rows


def mech_from_packed(packed, src):
    """从 packed.pools 取逐层机制计数 → {(layer): {mech: n}}。"""
    pools = packed.get("pools")
    if not isinstance(pools, dict):
        return {}
    out = {}
    for lid, pool in pools.items():
        if not isinstance(pool, dict):
            continue
        rec = {}
        for mech in MECH_COLS:
            v = pool.get(mech)
            rec[mech] = len(v) if isinstance(v, (list, dict)) else None
        out[str(lid)] = rec
    return out


# ---------------- 日志尾行 layer_contribution ----------------

def lc_from_log_line(text):
    """日志尾部的 `layer_contribution={...}`（单行 JSON）。"""
    m = re.search(r"^layer_contribution=(\{.*\})\s*$", text, re.M)
    if not m:
        return []
    try:
        # 日志尾行是 Python 的 str(dict)（单引号），不是 JSON —— 用 literal_eval
        obj = ast.literal_eval(m.group(1))
    except Exception:
        return []
    rows = []
    for lid, v in obj.items():
        if not isinstance(v, dict):
            continue
        stop = v.get("stop")
        rows.append((str(lid), v.get("rounds"), stop,
                     classify_stop(stop) if stop else None,
                     v.get("idle"), "log_line"))
    return rows


def duration_from_log(text):
    m = re.search(r"耗时\s*(\d+)\s*s", text)
    return int(m.group(1)) if m else None


# ---------------- 组装 run ----------------

def _iso_mtime(p):
    import datetime
    return datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat()


def build_runs():
    outputs = sorted(OUT_DIR.glob("*.md"))
    logs = sorted(HERE.glob("*.log"))
    fulls = sorted(HERE.glob("*.full.json"))

    runs = {}          # run_id -> dict
    log_index = {}     # log stem -> parsed log dict

    def new_run(run_id, source):
        return {
            "run_id": run_id, "source": source, "output_path": None,
            "output_stem": None, "log_path": None, "full_json_path": None,
            "link_src": None, "run_time": None, "qtype": None, "question": None,
            "route": None, "mode": None, "rounds_planned": None,
            "cost_profile": None, "orientation": None, "llm_calls": None,
            "llm_tokens": None, "duration_s": None, "decidability": None,
            "coverage": None, "n_layers_md": None, "has_layer_contrib": 0,
            "contrib_src": None,
            "_packed": None, "_mdlayers": None, "_mdpool": None,
            "_xuanzhi": None, "_logtext": None,
        }

    # ---- 第一遍：扫日志 ----
    parsed_logs = {}
    for lp in logs:
        parsed_logs[lp.name] = (lp, scan_log(lp))

    out_by_stem = {op.stem: op for op in outputs}
    out_mtime = {op.stem: op.stat().st_mtime for op in outputs}
    used_logs = set()          # log 名 -> 已归到某个 run
    claimed_out = set()        # output stem -> 已被认领
    log_of_out = {}            # output stem -> log Path
    log_src = {}               # output stem -> link_src（产物= / mtime）
    fj_of_out = {}             # output stem -> full.json Path
    fj_to_out = {}             # full.json 路径 -> output stem

    # ---- A. 权威认领：日志里的 `产物=` ----
    for lp in logs:
        _, d = parsed_logs[lp.name]
        if d.get("out") and d.get("out_src") == "log":
            stem = Path(d["out"]).stem
            if stem in out_by_stem and stem not in claimed_out:
                claimed_out.add(stem)
                log_of_out[stem] = lp
                log_src[stem] = "产物="
                used_logs.add(lp.name)

    # ---- B. full.json → 产物 ----
    #  实测 full.json 的 mtime 与产物文件名里的时间戳**精确相等**，
    #  所以按 mtime 找最近产物是可靠的一对一映射（比日志的 mtime 猜测稳，
    #  因为它不经过「多日志猜同一产物、后写覆盖」那条路）。
    for fp in sorted(fulls):
        stem = fp.name.replace(".full.json", "")
        lp = HERE / (stem + ".log")
        # 同名日志若已在 A 认领过某产物 → 直接沿用（最稳）
        reused = None
        if lp.exists() and lp.name in used_logs:
            for ostem, lg in log_of_out.items():
                if lg.name == lp.name:
                    reused = ostem
                    break
        if reused:
            fj_of_out[reused] = fp
            fj_to_out[str(fp)] = reused
            continue
        # 否则按 mtime 就近匹配未认领产物
        t0 = fp.stat().st_mtime
        best, bd = None, None
        for ostem, mt in out_mtime.items():
            if ostem in claimed_out or ostem in fj_of_out:
                continue
            dt = abs(mt - t0)
            if dt <= 120 and (bd is None or dt < bd):
                best, bd = ostem, dt
        if best:
            claimed_out.add(best)
            fj_of_out[best] = fp
            fj_to_out[str(fp)] = best
            if lp.exists() and lp.name not in used_logs:
                log_of_out[best] = lp
                log_src[best] = "mtime"
                used_logs.add(lp.name)

    # ---- C. 剩余日志 → 产物：贪心按 mtime 距离，一对一（防两日志抢同一产物）----
    cands = []
    for lp in logs:
        if lp.name in used_logs:
            continue
        t0 = lp.stat().st_mtime
        for ostem, mt in out_mtime.items():
            if ostem in claimed_out:
                continue
            dt = mt - t0
            if -60 <= dt <= 1800:
                cands.append((dt, lp.name, ostem))
    cands.sort()
    for dt, lname, ostem in cands:
        if lname in used_logs or ostem in claimed_out:
            continue
        used_logs.add(lname)
        claimed_out.add(ostem)
        log_of_out[ostem] = HERE / lname
        log_src[ostem] = "mtime"

    # ---- 建 run 记录（每个产物一行）----
    for op in outputs:
        rid = op.stem
        r = new_run(rid, "output")
        r["output_path"] = str(op)
        r["output_stem"] = rid
        lp = log_of_out.get(rid)
        if lp and lp.exists():
            r["log_path"] = str(lp)
            r["link_src"] = log_src.get(rid, "mtime")
            r["_logtext"] = lp.read_text(encoding="utf-8", errors="replace")
        if rid in fj_of_out:
            r["full_json_path"] = str(fj_of_out[rid])
        if not lp and rid not in fj_of_out:
            r["link_src"] = "orphan"
        runs[rid] = r
    orphan_logs = [(lp, parsed_logs[lp.name][1])
                   for lp in logs if lp.name not in used_logs]

    # ---- 产物内嵌 packed JSON（22 份）+ 头部/池/悬置段 ----
    for rid, r in runs.items():
        if not r["output_path"]:
            continue
        text = Path(r["output_path"]).read_text(encoding="utf-8", errors="replace")
        hdr = parse_output_header(text)
        r["_mdpool"] = parse_pool_section(text)
        r["_xuanzhi"] = parse_xuanzhi(text)
        packed = parse_embedded_json(text)
        if packed:
            r["_packed"] = packed
        o = scan_output(Path(r["output_path"]))
        r["_mdlayers"] = o.get("layers") or {}
        # 头部字段
        r["run_time"] = hdr.get("run_time") or _iso_mtime(Path(r["output_path"]))
        r["question"] = hdr.get("question")
        r["route"] = hdr.get("route")
        r["mode"] = hdr.get("mode") or (o.get("pmode") if o.get("pmode") != "-" else None)
        r["cost_profile"] = hdr.get("cost_profile")
        r["orientation"] = hdr.get("orientation")
        r["llm_calls"] = hdr.get("llm_calls")
        r["llm_tokens"] = hdr.get("llm_tokens")
        r["decidability"] = o.get("decidability") if o.get("decidability") != "-" \
            else hdr.get("decidability")
        r["coverage"] = o.get("coverage")
        r["n_layers_md"] = len(r["_mdlayers"])
        # route：产物头部没有显式 route 时，用「逐层明细里实际出现的层」兜底
        # （这是**实际跑过的层**，不是规划 route；规划 route 只在显化段/日志里）
        if not r["route"] and r["_mdlayers"]:
            r["route"] = json.dumps(sorted(r["_mdlayers"].keys()), ensure_ascii=False)
        r["qtype"] = guess_type(r["output_path"] + " " + rid)

    # ---- 日志补字段（calls/tokens/耗时/route/rounds/题面）----
    for rid, r in runs.items():
        if not r.get("_logtext"):
            continue
        t = r["_logtext"]
        d = None
        # 从 parsed_logs 找对应日志
        if r["log_path"]:
            d = parsed_logs.get(Path(r["log_path"]).name, (None, None))[1]
        if d:
            if r["llm_calls"] is None:
                r["llm_calls"] = d.get("calls")
            if r["llm_tokens"] is None:
                r["llm_tokens"] = d.get("tokens")
            if not r.get("route") and d.get("route") not in (None, "-"):
                r["route"] = d["route"]
            if not r.get("mode") and d.get("mode") not in (None, "?", "-"):
                mm = d["mode"]
                r["mode"] = "serial" if mm == "严格串行" else mm
            if not r.get("cost_profile") and d.get("profile") not in (None, "-"):
                r["cost_profile"] = d["profile"]
            if d.get("rounds") not in (None, "-"):
                r["rounds_planned"] = d["rounds"]
            if not r.get("question"):
                mq = re.search(r"^题目[:：]\s*(.+)$", t, re.M)
                if mq:
                    r["question"] = mq.group(1).strip()
        if r["duration_s"] is None:
            r["duration_s"] = duration_from_log(t)

    # ---- full.json → run（按同名 log 归并；无则单独成 run）----
    for fp in fulls:
        try:
            packed = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        stem = fp.name.replace(".full.json", "")
        # 优先用 B 步算出的 mtime 精确映射；无则单独成 run
        target_rid = fj_to_out.get(str(fp))
        if target_rid is None:
            target_rid = "full:" + stem
            runs[target_rid] = new_run(target_rid, "full_json")
            runs[target_rid]["run_time"] = _iso_mtime(fp)
            lp = HERE / (stem + ".log")
            if lp.exists():
                runs[target_rid]["log_path"] = str(lp)
                runs[target_rid]["_logtext"] = lp.read_text(
                    encoding="utf-8", errors="replace")
        r = runs[target_rid]
        r["full_json_path"] = str(fp)
        r["_packed_fj"] = packed
        # 从 packed 补顶层（若缺）
        if not r.get("question"):
            r["question"] = packed.get("question")
        if not r.get("route") and packed.get("route") is not None:
            r["route"] = json.dumps(packed.get("route"), ensure_ascii=False)
        if r.get("llm_calls") is None:
            r["llm_calls"] = packed.get("llm_calls")
        if r.get("llm_tokens") is None:
            r["llm_tokens"] = packed.get("llm_tokens")
        if not r.get("cost_profile"):
            r["cost_profile"] = packed.get("cost_profile")
        if not r.get("rounds_planned") and isinstance(packed.get("rounds"), dict):
            r["rounds_planned"] = json.dumps(packed["rounds"], ensure_ascii=False)
        disp = packed.get("dispatch")
        if not r.get("mode") and isinstance(disp, dict):
            r["mode"] = disp.get("_parallel_mode")
        if not r.get("qtype"):
            r["qtype"] = guess_type(str(packed.get("question", "")) + " " + stem)

    # ---- 独立日志 run（既没产物、也没内嵌包：仍是一次真跑）----
    for lp, d in orphan_logs:
        t = lp.read_text(encoding="utf-8", errors="replace")
        has_sig = ("llm_calls=" in t) or ("【0】" in t) or ("题目：" in t)
        if not has_sig:
            continue
        rid = "log:" + lp.stem
        r = new_run(rid, "log_only")
        r["log_path"] = str(lp)
        r["link_src"] = "log_only"
        r["run_time"] = _iso_mtime(lp)
        r["llm_calls"] = d.get("calls")
        r["llm_tokens"] = d.get("tokens")
        r["mode"] = d.get("mode") if d.get("mode") not in (None, "?", "-") else None
        r["cost_profile"] = d.get("profile") if d.get("profile") not in (None, "-") else None
        if d.get("rounds") not in (None, "-"):
            r["rounds_planned"] = d["rounds"]
        if d.get("decidability") not in (None, "-"):
            r["decidability"] = d["decidability"]
        r["duration_s"] = duration_from_log(t)
        mq = re.search(r"^题目[:：]\s*(.+)$", t, re.M)
        r["question"] = mq.group(1).strip() if mq else None
        r["qtype"] = guess_type(lp.name + " " + t[:200])
    return runs


# ---------------- 落库 ----------------

def ingest(runs):
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    cur = con.cursor()
    n = 0
    for rid, r in runs.items():
        packed = r.get("_packed") or r.get("_packed_fj")
        # layer_contribution 优先级：full_json > embed_json > log_line
        lc_rows = []
        if r.get("_packed_fj"):
            lc_rows = contrib_from_packed(r["_packed_fj"], "full_json")
        if not lc_rows and r.get("_packed"):
            lc_rows = contrib_from_packed(r["_packed"], "embed_json")
        if not lc_rows and r.get("_logtext"):
            lc_rows = lc_from_log_line(r["_logtext"])
        r["has_layer_contrib"] = 1 if lc_rows else 0
        r["contrib_src"] = lc_rows[0][5] if lc_rows else None

        # 逐层明细（产物段）
        md = r.get("_mdlayers") or {}

        cur.execute("DELETE FROM runs WHERE run_id=?", (rid,))
        cur.execute(
            "INSERT INTO runs (run_id,source,output_path,output_stem,log_path,"
            "full_json_path,link_src,run_time,qtype,question,route,mode,"
            "rounds_planned,cost_profile,orientation,llm_calls,llm_tokens,"
            "duration_s,decidability,coverage,n_layers_md,has_layer_contrib,"
            "contrib_src) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (r["run_id"], r["source"], r["output_path"], r["output_stem"],
             r["log_path"], r["full_json_path"], r["link_src"], r["run_time"],
             r["qtype"], r["question"], r["route"], r["mode"],
             r["rounds_planned"], r["cost_profile"], r["orientation"],
             r["llm_calls"], r["llm_tokens"], r["duration_s"],
             r["decidability"], r["coverage"], r["n_layers_md"],
             r["has_layer_contrib"], r["contrib_src"]))
        n += 1

        # layer_detail
        cur.execute("DELETE FROM layer_detail WHERE run_id=?", (rid,))
        for lid, lr in md.items():
            cur.execute(
                "INSERT INTO layer_detail (run_id,layer,rounds_actual,cap,"
                "stop_category,stop_raw,defer_n,clean,unsettled,debt_active,src)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (rid, lid, lr.get("rounds"), lr.get("cap"), lr.get("stop"),
                 lr.get("stop_raw"), lr.get("defer_n"), lr.get("clean"),
                 lr.get("unsettled"), lr.get("debt_active"), "md"))

        # layer_contribution
        cur.execute("DELETE FROM layer_contribution WHERE run_id=?", (rid,))
        for (lid, rounds, stop, cat, idle, src) in lc_rows:
            cur.execute(
                "INSERT OR REPLACE INTO layer_contribution "
                "(run_id,layer,rounds_actual,stop_reason,stop_category,idle,src)"
                " VALUES (?,?,?,?,?,?,?)",
                (rid, lid, rounds, stop, cat,
                 None if idle is None else (1 if idle else 0), src))

        # mechanisms
        cur.execute("DELETE FROM mechanisms WHERE run_id=?", (rid,))
        mech_src = {}
        if packed:
            mech_src = mech_from_packed(packed, "pools_json")
            for lid, rec in mech_src.items():
                _ins_mech(cur, rid, lid, rec, "pools_json")
        if not mech_src:
            # 产物池段 + 悬置总览
            pool = dict(r.get("_mdpool") or {})
            xz = r.get("_xuanzhi") or {}
            for lid in LAYERS:
                rec = dict(pool.get(lid, {}))
                for k, v in (xz.get(lid) or {}).items():
                    rec.setdefault(k, v)
                if any(rec.get(m) is not None for m in MECH_COLS):
                    _ins_mech(cur, rid, lid, rec, "pool_section")
    con.commit()
    con.close()
    return n


def _ins_mech(cur, rid, lid, rec, src):
    cur.execute(
        "INSERT OR REPLACE INTO mechanisms (run_id,layer,amps,threads,probes,"
        "suspensions,duel_suspensions,deferrals,escalations,decidability_log,"
        "engagements,refinements,sub_questions,src) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (rid, lid,
         rec.get("amps"), rec.get("threads"), rec.get("probes"),
         rec.get("suspensions"), rec.get("duel_suspensions"),
         rec.get("deferrals"), rec.get("escalations"),
         rec.get("decidability_log"), rec.get("engagements"),
         rec.get("refinements"), rec.get("sub_questions"), src))


# ---------------- 摘要 ----------------

def summary():
    con = sqlite3.connect(DB)
    c = con.cursor()
    L = []
    A = L.append
    n_runs = c.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    n_md = c.execute("SELECT COUNT(*) FROM runs WHERE output_path IS NOT NULL").fetchone()[0]
    n_logonly = c.execute("SELECT COUNT(*) FROM runs WHERE source='log_only'").fetchone()[0]
    n_full = c.execute("SELECT COUNT(*) FROM runs WHERE full_json_path IS NOT NULL").fetchone()[0]
    tmin, tmax = c.execute("SELECT MIN(run_time),MAX(run_time) FROM runs").fetchone()
    n_lc = c.execute("SELECT COUNT(DISTINCT run_id) FROM layer_contribution").fetchone()[0]
    n_ld = c.execute("SELECT COUNT(DISTINCT run_id) FROM layer_detail").fetchone()[0]
    n_mech = c.execute("SELECT COUNT(DISTINCT run_id) FROM mechanisms").fetchone()[0]

    A("# 入库统计摘要（runs.sqlite3）\n")
    A(f"- 跑动总数：**{n_runs}**（有产物的 {n_md}，仅日志的 {n_logonly}）")
    A(f"- 时间跨度：{tmin} ～ {tmax}")
    A("- 表规模：runs "
      f"{n_runs} / layer_detail "
      f"{c.execute('SELECT COUNT(*) FROM layer_detail').fetchone()[0]} / "
      "layer_contribution "
      f"{c.execute('SELECT COUNT(*) FROM layer_contribution').fetchone()[0]} / "
      "mechanisms "
      f"{c.execute('SELECT COUNT(*) FROM mechanisms').fetchone()[0]}")
    A("")
    A("## 来源构成\n")
    A("日志↔产物的关联方式（`link_src`）：")
    for k, v in c.execute("SELECT COALESCE(link_src,'?'),COUNT(*) "
                          "FROM runs GROUP BY 1 ORDER BY 2 DESC"):
        A(f"- {k}：{v}")
    A("")
    A("`layer_contribution` 的实际来源（去重到 run）：")
    for k, v in c.execute("SELECT src,COUNT(DISTINCT run_id) "
                          "FROM layer_contribution GROUP BY 1 ORDER BY 2 DESC"):
        A(f"- {k}：{v}")
    A("")
    A("机制计数的来源（去重到 run）：")
    for k, v in c.execute("SELECT src,COUNT(DISTINCT run_id) "
                          "FROM mechanisms GROUP BY 1 ORDER BY 2 DESC"):
        A(f"- {k}：{v}")
    A("")
    A("## 字段可用率\n")
    A(f"- `layer_contribution`（含 idle）：{n_lc}/{n_runs}"
      f" = {n_lc / max(n_runs,1) * 100:.0f}%")
    A(f"- `layer_detail`（产物逐层，实际圈数/停止理由）：{n_ld}/{n_runs}"
      f" = {n_ld / max(n_runs,1) * 100:.0f}%")
    A(f"- 机制计数（任一机制非 NULL）：{n_mech}/{n_runs}"
      f" = {n_mech / max(n_runs,1) * 100:.0f}%")
    for col in ["question", "route", "mode", "cost_profile", "llm_calls",
                "llm_tokens", "duration_s", "decidability"]:
        v = c.execute(f"SELECT COUNT({col}) FROM runs").fetchone()[0]
        A(f"- `{col}`：{v}/{n_runs} = {v / max(n_runs,1) * 100:.0f}%")
    A("")
    A("## 机制触发分布（逐层累加）\n")
    A("「可判定」= 该机制在至少一层被数出来（非 NULL）；"
      "「零触发跑动」= 可判定且总值=0；`NULL 跑动`= 全部层都取不到。\n")
    A("| 机制 | 总触发次数 | 可判定跑动 | 零触发跑动 | 零触发占比 | NULL 跑动 |")
    A("|---|---|---|---|---|---|")
    for mech in MECH_COLS:
        # 每个 run 该机制的合计（层间求和）
        rows = c.execute(
            f"SELECT run_id, SUM({mech}) AS s, COUNT({mech}) AS k "
            f"FROM mechanisms GROUP BY run_id").fetchall()
        total = sum(r[1] for r in rows if r[1] is not None)
        known = sum(1 for r in rows if r[2] > 0)
        zero = sum(1 for r in rows if r[2] > 0 and (r[1] or 0) == 0)
        nullruns = n_runs - known
        pct = (zero / known * 100) if known else float("nan")
        A(f"| {mech} | {total} | {known} | {zero} | "
          f"{pct:.0f}% | {nullruns} |")
    A("")
    A("## layer_contribution 停止类别分布（逐层）\n")
    A("| 停止类别 | 层数 |")
    A("|---|---|")
    for cat, n in c.execute(
            "SELECT COALESCE(stop_category,'(NULL)'),COUNT(*) "
            "FROM layer_contribution GROUP BY 1 ORDER BY 2 DESC"):
        A(f"| {cat} | {n} |")
    A("")
    A("## 停止类别 × 实际圈数（layer_detail，逐层）\n")
    A("| 停止类别 | 层数 | 圈数中位 | 圈数范围 |")
    A("|---|---|---|---|")
    for cat, n, mid, lo, hi in c.execute(
            "SELECT stop_category, COUNT(*), "
            "CAST(AVG(rounds_actual) AS INT), MIN(rounds_actual), "
            "MAX(rounds_actual) FROM layer_detail "
            "WHERE rounds_actual IS NOT NULL GROUP BY 1 ORDER BY 2 DESC"):
        A(f"| {cat} | {n} | ~{mid} | {lo}~{hi} |")
    A("")
    A("## 数据缺口与口径说明\n")
    A("- **layer_contribution** 只在三处出现：`*.full.json`、产物末尾内嵌的 "
      "packed JSON（22 份产物有）、日志尾行 `layer_contribution={...}`（Python "
      "dict repr，非 JSON）。三者重叠，去重后覆盖上面「来源构成」所列的跑动数；"
      "其余跑动该字段为 **NULL（不是 0，也不是空圈）**。")
    A("- **route**：有显式 route 的写原值；产物没有显式 route 时用「逐层明细里"
      "实际出现的层」兜底 —— 那是**实际跑过的层**，不等于规划 route。")
    A("- **机制计数**：`decidability_log / engagements / refinements` 只在 packed "
      "JSON 里有（产物池段无对应行）→ 非 JSON 跑动一律 NULL。"
      "`escalations` 由产物「悬置总览·研究延迟处理」的 `(escalated)` 标记推出。"
      "其余机制来自产物 `## 池` 段逐层计数。")
    A("- **escalations** 只在「研究延迟处理的」清单里可见，归到 1 层；"
      "若某次跑动没有该段，则该跑动的此机制为 NULL。")
    A("- **idle** 只在 packed 有；`layer_detail` 表不含 idle 列。")
    A("- 计数类字段**无条件写入**：值是 0 表示「数出来确实是 0」，"
      "NULL 表示「这个数据源里数不出来」——两者不可混。")
    A("- `layer_detail` 的停止类别与 `layer_contribution` 的停止类别都走 "
      "`_convergence_matrix.classify_stop()`，口径一致；认不出的归 OTHER。")
    con.close()
    return "\n".join(L)


def main():
    if "--summary" not in sys.argv:
        runs = build_runs()
        n = ingest(runs)
        print(f"入库 {n} 条跑动 → {DB}")
    md = summary()
    (HERE / "_ingest_summary.md").write_bytes(
        md.replace("\n", "\r\n").encode("utf-8"))
    print(md)


if __name__ == "__main__":
    main()
