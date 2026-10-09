#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""元 DGTF v1.22.0 六阶段验收脚本。

用法：
    python _v122_verify.py --phase 1 --src 元DGTF-V1.22.0-rc1.py
    python _v122_verify.py --phase all --src 元DGTF-V1.22.0.py

退出码：0 = 全部通过；非 0 = 有失败项（逐条打印 FAIL）。
"""
from __future__ import annotations

import argparse
import ast
import difflib
import importlib.util
import io
import json
import os
import re
import sys
import traceback
from pathlib import Path
from typing import List, Optional

HERE = Path(__file__).resolve().parent
BASELINE = HERE / "_baseline_v12177.py"

# ============================================================
# ★ [v1.23.16] 授权删除清单
# ============================================================
# 本版**经用户明确要求**删除「成本档」这一维（只保留一种行为：不裁剪），
# 于是 9 条「不删机制」类判据同时翻红。这里把「声明过的删除」与
# 「偷偷删」分开：
#   · 符号层：消失的符号必须 ⊆ 本清单 —— **清单外照旧判红**（判别力不减）；
#   · 行数层：纯删除行从「== 0」改成「≤ 预算」（预算写死，下次多删就超）。
# 清单来源：v12316_报告.md §三 的落点表。
_V12316_AUTH_SYMBOLS = (
    "_COST_PROFILES", "_PROBE_SKIP_ROLES", "_profile_plan",
    "_auto_pick_cost_profile", "_auto_profile",
)
#: 授权删除的**行数预算**：上述清单对应的实现体量（本版实测纯删除行 1047~1166）。
_V12316_AUTH_DEL_BUDGET = 1400
#: 授权删除的**配置键**（V3 的允许差异集合）。
_V12316_AUTH_KEYS = {"cost_profile", "spiral.round_window"}


def _auth_removed(gone_list):
    """过滤掉**授权清单**里的消失项；清单外的原样返回（由调用方判红）。

    ★ `mechanism_removed()` 返回的是描述串（如 `_profile_plan(def) 消失`），
      而 `_syms()` 的差集是纯符号名 —— 所以按**前缀**匹配，两种都吃。
    """
    return [g for g in gone_list
            if not any(str(g).startswith(s) for s in _V12316_AUTH_SYMBOLS)]
# [v1.22.1] P3 的「不删机制」按 v1.22.0 基线比（更贴近本版）
BASELINE_V1220 = HERE / "_baseline_v1220.py"

R = {"p": 0, "f": 0}


def check(cid: str, ok, msg: str = "") -> bool:
    ok = bool(ok)
    if ok:
        R["p"] += 1
        print(f"  ✅ [{cid}] {msg}")
    else:
        R["f"] += 1
        print(f"  ❌ FAIL [{cid}] {msg}")
    return ok


def _version_consistent(mod, src, yaml_head_n: int = 900) -> tuple:
    """[v1.23.4] 版本三处一致 —— 版本号**从被验文件名推导**，不写死。

    ★ 别把版本号写成字面量：`--phase all` 会把**旧档判据**与**新主文件**
      放在同一次运行里，写死的锚必然在升版那天翻红，而那次翻红与代码
      质量**毫无关系**（纯噪声，且很容易被误读成回归）。
    ★ 反过来说，这样写**更强**：多钉了「文件名与 `__version__` 不许脱节」。
    """
    import re as _re
    from pathlib import Path as _P

    _m = _re.search(r"V(\d+\.\d+\.\d+)\.py$", _P(src).name)
    _want = _m.group(1) if _m else ""
    _sm = HERE / "smoke_test.py"
    _sm_t = _sm.read_bytes().decode("utf-8") if _sm.is_file() else ""
    _y = HERE / "dgtf_config.yaml"
    _y_t = (_y.read_bytes().decode("utf-8")[0:yaml_head_n]
            if _y.is_file() else "")
    _got = str(getattr(mod, "__version__", "") or "")
    return (bool(_want), _got, _want, _want in _y_t, _P(src).name in _sm_t)


# ── 通用工具 ────────────────────────────────────────────────
def crlf_ok(path) -> dict:
    b = Path(path).read_bytes()
    lf = b.count(b"\n")
    crlf = b.count(b"\r\n")
    cr = b.count(b"\r")
    return {"total_lf": lf, "crlf": crlf, "cr": cr,
            "bare_lf": lf - crlf, "crr_lf": b.count(b"\r\r\n"),
            "ok": (lf == crlf and cr == crlf and b.count(b"\r\r\n") == 0)}


def _lines(p):
    return Path(p).read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")


def count_del_lines(a, b) -> int:
    """**纯删除块**的行数（difflib opcode == "delete"）。

    ★ 口径说明（v122 环境）：任务书要求「不许删任何机制代码」。
      但同一份任务书也要求改签名、把方法正文搬进模块级函数 ——
      这些在 difflib 里是 `replace`（有配对的行被改写），不是 `delete`。
      用「以 '-' 开头的行数」会把**改写**也算成删除，于是结论恒为「违规」，
      判据失去意义。这里按 opcode 分家：
        · `delete`（旧行凭空消失、无对应新行）→ 计删；
        · `replace`（旧行被改写）→ 不计删，其旧侧行数由
          `count_replaced_lines()` 单独如实报出。
      「机制有没有被拿掉」另由 `mechanism_removed()` 按 **AST 符号**判 ——
      那才是这条红线真正想拦的东西。
    """
    sm = difflib.SequenceMatcher(None, _lines(a), _lines(b))
    return sum(blk[2] - blk[1] for blk in sm.get_opcodes()
               if blk[0] == "delete")


def count_replaced_lines(a, b) -> int:
    """被**改写**的行数（replace 块的旧侧）—— 如实报，但不是「删机制」。"""
    sm = difflib.SequenceMatcher(None, _lines(a), _lines(b))
    return sum(blk[2] - blk[1] for blk in sm.get_opcodes()
               if blk[0] == "replace")


def _symbols(path):
    """{符号全名: (kind, 行数)}。类里的方法按 `类.方法` 记。"""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[n.name] = ("def", int(n.end_lineno or 0) - int(n.lineno) + 1)
        elif isinstance(n, ast.ClassDef):
            out[n.name] = ("class", int(n.end_lineno or 0) - int(n.lineno) + 1)
    return out


def mechanism_removed(a, b) -> list:
    """基线里出现过的类名/函数名，在 b 里必须都还在（硬判据）。

    红线「不许删任何机制代码」要拦的是**机制没了**，所以按 AST **符号**
    判，而不是按行数判 —— 改签名、搬正文都会让行数变，但那不是删机制。
    """
    sa, sb = _symbols(a), _symbols(b)
    return [f"{k}({sa[k][0]}) 消失" for k in sa if k not in sb]


def function_shrunk(a, b, ratio: float = 0.4, min_lines: int = 30) -> list:
    """名字还在、但函数体行数骤减的函数（正文疑似被搬走）。

    ★ 这条**只报不判红**：v122 把 `render_landing` 的正文搬进
      `_render_landing_boundary`，行数 259 → 8 —— 那是设计，不是违规。
      这一条的作用是**逼报告解释每一次骤减**，别让它悄悄发生。
    """
    sa, sb = _symbols(a), _symbols(b)
    out = []
    for k, (kind, na) in sa.items():
        if kind != "def" or k not in sb:
            continue
        nb = sb[k][1]
        if na >= min_lines and nb < na * ratio:
            out.append(f"{k} {na} → {nb}")
    return out


def diff_stat(a, b) -> dict:
    la = Path(a).read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    lb = Path(b).read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    sm = difflib.SequenceMatcher(None, la, lb)
    blocks = [b for b in sm.get_opcodes() if b[0] != "equal"]
    add = sum(b[4] - b[3] for b in blocks
              if b[0] in ("insert", "replace"))
    dele = sum(b[2] - b[1] for b in blocks
               if b[0] in ("delete", "replace"))
    return {"blocks": len(blocks), "added": add, "deleted": dele,
            "lines_before": len(la), "lines_after": len(lb)}


def _exec_src(text: str) -> str:
    """抠模块 docstring + 归一化 __version__（AST 等价比较用）。"""
    text = text.replace("\r\n", "\n")
    i = text.index('"""')
    j = text.index('"""', i + 3)
    body, n = re.subn(r'__version__ = "1\.2[12]\.\d+"', '__version__ = "X"',
                      text[j + 3:])
    return '"""X"""' + body


def ast_sig(path):
    return ast.dump(ast.parse(_exec_src(
        Path(path).read_text(encoding="utf-8"))))


def func_node_count(path) -> int:
    t = ast.parse(_exec_src(Path(path).read_text(encoding="utf-8")))
    return sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               for n in ast.walk(t))


def load_module(src_path: str):
    os.environ.setdefault("DGTF_API_KEY", "sk-v122-verify-key")
    spec = importlib.util.spec_from_file_location("dgtf_v122_mod", str(src_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_v122_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


def _strip_docstring(src: str) -> str:
    """归一化换行后抠掉模块 docstring（自证抠法有效）。"""
    s = src.replace("\r\n", "\n")
    m = re.match(r'^#![^\n]*\n(# -*- coding[^\n]*\n)?("""[\s\S]*?""")',
                 s)
    if not m:
        return s
    return s[:m.start(3)] + s[m.end(3):]


def _count_in_src(src: str, needle: str) -> int:
    return src.count(needle)


class _Pool:
    """覆盖 coverage_of / DecidabilityFreeze 用的最小池替身。"""

    def __init__(self, subs=None, deferrals=None):
        self.sub_questions = list(subs or [])
        self.deferrals = list(deferrals or [])
        self.meta = []
        self.threads = []
        self.engagements = []


ACTION_SAMPLE = (
    "指派 排水公司 核查 老城区内涝点位台账，汛期前完成，"
    "验收以抽检合格为准，否则回退人工分片排查。"
    "申请 信息科 调取 近三年积水点水位记录，本月内完成，"
    "验收以台账入库为准，否则沿用去年记录。"
    "委托 项目组 试点 海绵改造，本季度完成，"
    "验收以积水频次下降为准，否则回退局部清淤。"
)

ACTION_VIEW = {"decidable_product": {"answer": ACTION_SAMPLE}}


# ── 阶段 1 ──────────────────────────────────────────────────
def phase1(src, mod):
    qdir, gdir = HERE / "bench/questions", HERE / "bench/gold"
    qs = sorted(qdir.glob("*.yaml")) if qdir.is_dir() else []
    gold = sorted(gdir.glob("*.yaml")) if gdir.is_dir() else []
    check("1.1.1", len(qs) >= 20, f"bench/questions/*.yaml = {len(qs)}（≥20）")
    check("1.1.2", len(gold) >= 3, f"bench/gold/*.yaml = {len(gold)}（≥3）")

    # 1.2 必填字段
    bad = []
    try:
        import yaml
        for f in qs:
            try:
                d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except Exception as e:
                bad.append(f"{f.name}: yaml 解析失败 {e}")
                continue
            for k in ("id", "domain", "question", "orientation", "budget"):
                if k not in d:
                    bad.append(f"{f.name}: 缺 {k}")
            b = d.get("budget") or {}
            if isinstance(b, dict):
                for k in ("profile", "max_calls", "rounds", "mode"):
                    if k not in b:
                        bad.append(f"{f.name}: 缺 budget.{k}")
            else:
                bad.append(f"{f.name}: budget 不是 mapping")
    except ImportError:
        bad.append("PyYAML 不可用")
    check("1.2", not bad, f"题库必填字段 bad={bad[:4]}")

    if mod is None:
        for cid in ("1.3.1", "1.3.2", "1.3.3", "1.3.4", "1.4.1", "1.4.2",
                    "1.4.3", "1.4.4", "1.5.1", "1.5.2", "1.5.3",
                    "1.6", "1.7", "1.8"):
            check(cid, False, "模块未加载")
        return

    # 1.3 Phase.objective 四层
    want = {"0": "manifest", "1": "truth", "both": "collision",
            "all": "closure"}
    ph = getattr(mod, "PHASES", {}) or {}
    for i, (k, v) in enumerate(want.items(), 1):
        got = getattr(ph.get(k), "objective", None)
        check(f"1.3.{i}", got == v, f"PHASES[{k!r}].objective={got!r} 期望 {v!r}")

    # 1.4 coverage 只对研究层
    subs = [{"id": "s1", "decidability": "decidable", "status": "answered",
             "weight": 1.0, "depth": 1.0}]
    pool = _Pool(subs)
    co = getattr(mod, "coverage_of", None)
    cp = getattr(mod, "coverage_parts", None)
    if co is None or cp is None:
        for cid in ("1.4.1", "1.4.2", "1.4.3", "1.4.4"):
            check(cid, False, "coverage_of/coverage_parts 缺失")
    else:
        res = {}
        for e in ("0", "both", "all", "1"):
            try:
                res[e] = cp(pool, {}, entry=e)
            except Exception as ex:
                res[e] = f"ERR {ex}"
        check("1.4.1", co(pool, {}, entry="0") is None,
              f"entry=0 → {co(pool, {}, entry='0')!r}（期望 None）")
        check("1.4.2", co(pool, {}, entry="both") is None,
              f"entry=both → {co(pool, {}, entry='both')!r}")
        check("1.4.3", co(pool, {}, entry="all") is None,
              f"entry=all → {co(pool, {}, entry='all')!r}")
        check("1.4.4", co(pool, {}, entry="1") is not None,
              f"entry=1 → {co(pool, {}, entry='1')!r}（应为数值）")

    # 1.5 _classify_unsaid（任务书口径：吃 View 对象；旧 dict 形态仍要能用）
    cu = getattr(mod, "_classify_unsaid", None)
    if cu is None:
        for cid in ("1.5.1", "1.5.2", "1.5.3", "1.5.4", "1.5.5"):
            check(cid, False, "_classify_unsaid 缺失")
    else:
        def _try(fn):
            try:
                return fn()
            except Exception as ex:  # noqa: BLE001
                return f"ERR {type(ex).__name__}: {ex}"
        V = getattr(mod, "View", None)
        a = _try(lambda: cu(V(entry="0", collision="")) if V else cu({}))
        b = _try(lambda: cu(V(entry="0",
                              collision="一、让两端各自把话说完\n二、各推到极端",
                              probes=[{"question": "Q",
                                       "covers": ["T1"]}])) if V
                 else cu({"covers": ["T1"]}))
        # 负对照①：说了「此处未生」，即使 probes 带 covers 也必须 lazy
        c = _try(lambda: cu(V(entry="0", collision="（此处未生）",
                              probes=[{"question": "Q",
                                       "covers": ["T1"]}])) if V
                 else cu({"covers": []}))
        # 负对照②：空 covers 必须 lazy
        d = _try(lambda: cu(V(entry="0", collision="一、让两端各自把话说完",
                              probes=[{"question": "Q", "covers": []}])) if V
                 else cu({"covers": []}))
        e = _try(lambda: cu({"covers": ["T1"]}))
        check("1.5.1", a == "lazy", f"空 collision → {a!r}（期望 lazy）")
        check("1.5.2", b == "real", f"有 covers → {b!r}（期望 real）")
        check("1.5.3", c == "lazy", f"负对照① 未生带 covers → {c!r}（期望 lazy）")
        check("1.5.4", d == "lazy", f"负对照② 空 covers → {d!r}（期望 lazy）")
        check("1.5.5", e == "real", f"旧 dict 形态 → {e!r}（期望 real）")
    # G1.5 修行层停止理由含「未生质量」（源码级）
    try:
        _s = (HERE / src).read_text(encoding="utf-8")
    except Exception:
        _s = ""
    check("1.5.6", "未生质量" in _s and "修行层不追求收敛" in _s,
          "源码含 未生质量 / 修行层不追求收敛")

    # 1.6 头部渲染分层目标（完整版口径：4 行计数，objective 折进括号）
    lof = getattr(mod, "_layer_objective_lines", None)
    if lof is None:
        check("1.6", False, "_layer_objective_lines 缺失")
    else:
        _res = {"views": {
            "0": {"amps": [1, 2], "threads": [1], "suspensions": [],
                  "probes": [1, 2, 3]},
            "1": {"settlement": {"coverage": 0.5},
                  "decidable_product": {"distance": 0.4}},
            "both": {"ing_structured": {"third": True, "tensions": ["a", "b"]}},
            "all": {"meta_closure": {"clean": True, "unsettled": 0}}},
            "pools": {}}
        try:
            lines = list(lof(_res))
        except Exception as ex:
            lines = [f"ERR {type(ex).__name__}: {ex}"]
        joined = "".join(lines)
        kws = ("修行层", "研究层", "对撞层", "元层", "& 2", "线头 1",
               "悬置 0", "探针 3", "覆盖率 50%", "third ✓", "张力 2",
               "clean True", "未交代 0 类", "objective=manifest")
        miss = [k for k in kws if k not in joined]
        check("1.6", len(lines) == 4 and not miss,
              f"分层目标 4 行计数，缺 {miss}；实际 {lines!r}"[:200])

    # 1.7 元层不评价修行层
    sm = getattr(getattr(mod, "MetaDGTF", None), "_settle_meta", None)
    if sm is None:
        check("1.7", False, "MetaDGTF._settle_meta 缺失")
    else:
        import inspect
        try:
            body = inspect.getsource(sm)
        except Exception as ex:
            body = f"ERR {ex}"
        bad = ('pools["0"]' in body) or ("pools['0']" in body)
        check("1.7", not bad,
              f"_settle_meta {'引用' if bad else '未引用'} pools['0']")

    # 1.8 route 分层
    rbd = getattr(getattr(mod, "MetaDGTF", None),
                  "_route_by_decidability", None)
    if rbd is None:
        check("1.8", False, "MetaDGTF._route_by_decidability 缺失")
    else:
        try:
            inst = object.__new__(mod.MetaDGTF)
            inst.config = {}
            inst.vp = lambda *a, **k: None
            out = inst._route_by_decidability(
                "q", ["0", "1", "both", "all"], orientation="boundary")
        except Exception as ex:
            out = f"ERR {ex}"
        check("1.8", out == ["0", "1", "both", "all"],
              f"boundary → {out!r}（期望全四层）")

    # 1.9 / 1.10 bench 脚本
    for cid, fn, needles in (
        ("1.9", "bench_score.py", ("def score_practice", "def score_research")),
        ("1.10.1", "bench_run.py", ()),
        ("1.10.2", "bench_diff.py", ()),
        ("1.10.3", "bench_report.py", ()),
    ):
        p = HERE / "bench" / fn
        if not p.is_file():
            check(cid, False, f"{fn} 不存在")
            continue
        src_txt = p.read_text(encoding="utf-8")
        miss = [n for n in needles if n not in src_txt]
        check(cid, not miss, f"{fn} 存在（缺 {miss}）" if miss else f"{fn} 存在")


# ── 阶段 2 ──────────────────────────────────────────────────
def phase2(src, mod):
    if mod is None:
        for cid in ("2.1", "2.2.1", "2.2.2", "2.3.1", "2.3.2", "2.3.3",
                    "2.4", "2.5", "2.6.1", "2.6.2", "2.7"):
            check(cid, False, "模块未加载")
        return
    tv = getattr(mod, "_TRI_VOTE_PROMPTS", None)
    check("2.1", isinstance(tv, (list, tuple)) and len(tv) == 3,
          f"len(_TRI_VOTE_PROMPTS)={len(tv) if tv is not None else None}（期望 3）")

    multi = getattr(mod.MetaDGTF, "_adjudicate_sub_tristate_multi", None)
    old = getattr(mod.MetaDGTF, "_adjudicate_sub_tristate", None)
    check("2.2.1", multi is not None, "_adjudicate_sub_tristate_multi 存在")
    check("2.2.2", old is not None, "_adjudicate_sub_tristate 旧方法保留")

    fzc = getattr(mod, "DecidabilityFreeze", None)
    if fzc is None:
        for cid in ("2.3.1", "2.3.2", "2.3.3", "2.4"):
            check(cid, False, "DecidabilityFreeze 缺失")
    else:
        subs = [{"id": "s1", "decidability": "decidable"},
                {"id": "s2", "decidability": "undecidable"}]
        pool = _Pool(subs)
        try:
            fz = fzc()
            fz.freeze(pool, layer=1)
        except Exception as ex:
            fz = None
            check("2.3.1", False, f"freeze() 抛错 {ex}")
        if fz is not None:
            got = [s.get("_frozen_answerable") for s in pool.sub_questions]
            check("2.3.1", any(g is not None for g in got),
                  f"冻结写入 _frozen_answerable={got}")
            check("2.3.2", bool(getattr(fz, "signature", "")),
                  f"signature={getattr(fz, 'signature', '')!r}")
            pool.sub_questions[0]["decidability"] = "partial"
            try:
                fz.verify(pool)
                check("2.3.3", False, "篡改后 verify 未抛 RuntimeError")
            except RuntimeError:
                check("2.3.3", True, "篡改 → RuntimeError")
            except Exception as ex:
                check("2.3.3", False, f"篡改抛 {type(ex).__name__}（期望 RuntimeError）")
            # 2.4 coverage 用冻结：改判后分母不变
            try:
                a = mod.coverage_parts(pool, {}, entry="1")
            except Exception as ex:
                a = f"ERR {ex}"
            pool.sub_questions[0]["decidability"] = "undecidable"
            try:
                b = mod.coverage_parts(pool, {}, entry="1")
            except Exception as ex:
                b = f"ERR {ex}"
            try:
                da = a[1] if isinstance(a, tuple) else None
                db = b[1] if isinstance(b, tuple) else None
                check("2.4", da is not None and da == db,
                      f"改判后分母 {da} → {db}（应不变）")
            except Exception as ex:
                check("2.4", False, f"{ex}")

    src_txt = Path(src).read_text(encoding="utf-8")
    check("2.5", ("三态多票" in src_txt and "冻结" in src_txt),
          "源码含『三态多票』+'冻结'")
    p = HERE / "bench/bench_calibrate.py"
    if not p.is_file():
        check("2.6.1", False, "bench_calibrate.py 不存在")
        check("2.6.2", False, "cmd_export/cmd_import 不存在")
    else:
        t = p.read_text(encoding="utf-8")
        check("2.6.1", True, "bench_calibrate.py 存在")
        check("2.6.2", ("cmd_export" in t and "cmd_import" in t),
              "cmd_export / cmd_import 齐备")
    check("2.7", ("calibration_queue" in src_txt and '"freeze"' in src_txt),
          "packed 含 freeze + calibration_queue 渲染点")


# ── 阶段 3 ──────────────────────────────────────────────────
def phase3(src, mod):
    if mod is None:
        for cid in ("3.1", "3.2.1", "3.2.2", "3.2.3", "3.3.1", "3.3.2",
                    "3.4", "3.5.1", "3.5.2", "3.6", "3.7", "3.7b", "3.8"):
            check(cid, False, "模块未加载")
        return
    src_txt = Path(src).read_text(encoding="utf-8")
    check("3.1", "landing_decision" in src_txt, "landing_decision 开关存在")
    check("3.2.1", hasattr(mod, "_render_landing_boundary"),
          "_render_landing_boundary 存在")
    check("3.2.2", hasattr(mod, "_render_landing_decision"),
          "_render_landing_decision 存在")

    ex = getattr(mod, "_extract_actions", None)
    check("3.3.1", ex is not None, "_extract_actions 存在")
    nd = getattr(mod, "_extract_not_do", None)
    if ex is not None:
        try:
            acts = ex(ACTION_VIEW)
        except Exception as e:
            acts = []
            check("3.3.2", False, f"_extract_actions 抛错 {e}")
        else:
            check("3.3.2", isinstance(acts, list) and len(acts) >= 1,
                  f"抽出 {len(acts)} 条（≥1）")
        keys = ("verb", "object", "owner_role", "deadline_hint",
                "acceptance", "fallback")
        try:
            acts = ex(ACTION_VIEW)
            miss = [k for k in keys
                    if not all(k in (a or {}) and (a or {}).get(k)
                               for a in acts)]
            check("3.4", (not miss) and len(acts) >= 1,
                  f"六字段齐备（缺 {miss}）")
        except Exception as e:
            check("3.4", False, f"{e}")
        # 负对照：空结论必须 0 条，否则 action_incomplete 永不亮
        try:
            e1 = ex({"decidable_product": {"answer": ""}})
            e2 = ex({})
            e3 = ex({"decidable_product": {"answer": "这是一句结论，没有动词。"}})
            check("3.7", e1 == [] and e2 == [] and e3 == [],
                  f"负对照 空/无动词 answer → {e1!r}/{e2!r}/{e3!r}（期望 []）")
        except Exception as e:
            check("3.7", False, f"{e}")
        # 已抽过的 dict 不许再抽一遍（两份抽样会不一致）
        try:
            cached = ex({"decidable_product": {"answer": ACTION_SAMPLE},
                         "_actions": [{"id": "A1"}]})
            check("3.7b", cached == [{"id": "A1"}],
                  f"带 _actions 的 dict 应直接用（得到 {cached!r}）")
        except Exception as e:
            check("3.7b", False, f"{e}")
    else:
        for cid in ("3.3.2", "3.4", "3.7", "3.7b"):
            check(cid, False, "_extract_actions 缺失")
    if nd is not None:
        try:
            check("3.8", nd(ACTION_VIEW) == []
                  and len(nd({"decidable_product": {
                      "answer": "不要一次性整体翻新。先做试点。"}})) == 1,
                  "not_do 抽取 + 负对照（无标记 → 空）")
        except Exception as e:
            check("3.8", False, f"{e}")
    else:
        check("3.8", False, "_extract_not_do 缺失")

    # 3.2 分流壳：boundary 走老模板、decision 走新模板
    rl = getattr(mod, "render_landing", None)
    if rl is None:
        check("3.2.3", False, "render_landing 缺失")
    else:
        _res_b = {"orientation": "boundary", "_config": {"actions": {}},
                  "views": {}, "decidability": {}}
        _res_d = {"orientation": "decision",
                  "_config": {"actions": {"landing_decision": True}},
                  "views": {"1": {"decidable_product": {
                      "answer": ACTION_SAMPLE}}},
                  "decidability": {}}
        try:
            b = rl(_res_b)
            d = rl(_res_d)
            check("3.2.3",
                  "落地层（decision 模式）" not in b
                  and "落地层（decision 模式）" in d,
                  f"boundary→老模板 {('落地层（decision 模式）' not in b)} / "
                  f"decision→新模板 {('落地层（decision 模式）' in d)}")
        except Exception as e:
            check("3.2.3", False, f"分流抛错 {type(e).__name__}: {e}")

    check("3.5.1", "action_incomplete" in src_txt, "action_incomplete 硬约束")
    check("3.5.2", "not_do_missing" in src_txt, "not_do_missing 硬约束")
    _score_src = ""
    try:
        _score_src = (HERE / "bench" / "bench_score.py").read_text(
            encoding="utf-8")
    except Exception:
        pass
    check("3.6", "score_decision_rubric" in _score_src,
          "bench_score.score_decision_rubric 存在")


# ── 阶段 4 ──────────────────────────────────────────────────
def phase4(src, mod):
    if mod is None:
        for cid in ("4.1.1", "4.1.2", "4.1.3", "4.2.1", "4.2.2", "4.3",
                    "4.4", "4.5", "4.6", "4.7", "4.8"):
            check(cid, False, "模块未加载")
        return
    ea = (getattr(mod, "DEFAULT_CONFIG", {}) or {}).get("external_anchor", {})
    lv = ["off", "record", "crosscheck", "evidence", "gate"]
    check("4.1.1", ea.get("as_evidence") in lv,
          f"as_evidence={ea.get('as_evidence')!r} ∈ 五档")
    check("4.1.2", "tier_floor" in ea, f"tier_floor={ea.get('tier_floor')!r}")
    check("4.1.3", "api_key_env" in ea, f"api_key_env={ea.get('api_key_env')!r}")
    rank = getattr(mod, "_anchor_evidence_rank", None)
    ent = getattr(mod, "_anchor_enters_citation", None)
    if ent is None:
        check("4.2.1", False, "_anchor_enters_citation 缺失")
        check("4.2.2", False, "_anchor_enters_citation 缺失")
    else:
        try:
            check("4.2.1", ent({"id": "a1", "tier": 1}, ea),
                  "tier=1 进引用表")
            check("4.2.2", not ent({"id": "a4", "tier": 4}, ea),
                  "tier=4 不进引用表")
        except Exception as e:
            check("4.2.1", False, f"{e}")
            check("4.2.2", False, f"{e}")
    check("4.3", hasattr(mod, "AnchorRetriever"), "AnchorRetriever 存在")
    src_txt = Path(src).read_text(encoding="utf-8")
    check("4.4", ('status == "rejected"' in src_txt)
          or ('"rejected"' in src_txt and "apply_decidability_change" in src_txt),
          "X# 支撑 →undecidable 被驳回（rejected）")
    check("4.5", "锚点冲突" in src_txt, "锚点冲突留痕")
    check("4.6", "triage_downgrades" in src_txt, "triage_downgrades")
    check("4.7", ("锚点分级" in src_txt and "triage 降级" in src_txt),
          "头部含『锚点分级』+『triage 降级』")


# ── 阶段 5 ──────────────────────────────────────────────────
def phase5(src, mod):
    import subprocess
    audit_py = HERE / "_audit_v122_dead_mechanisms.py"
    audit_md = HERE / "audit_v122_dead_mechanisms.md"
    if not audit_py.is_file():
        check("5.1", False, "_audit_v122_dead_mechanisms.py 不存在")
    else:
        try:
            r = subprocess.run([sys.executable, str(audit_py)], cwd=str(HERE),
                               capture_output=True, text=True, timeout=300)
            ok = audit_md.is_file()
            check("5.1", ok, f"审计脚本运行 → 退出码 {r.returncode}，报告存在={ok}")
        except Exception as e:
            check("5.1", False, f"审计脚本运行失败 {e}")
    mechs = ["escalate_starve_rounds", "no_push_when_idle",
             "_reopen_closed_debt", "stable_layers", "min_rounds",
             "triage_downgrades"]
    if audit_md.is_file():
        t = audit_md.read_text(encoding="utf-8")
        miss = [m for m in mechs if m not in t]
        check("5.2", not miss, f"审计报告六机制名（缺 {miss}）")
    else:
        check("5.2", False, "审计报告不存在")
    doc = HERE / "docs/机制审计-v122.md"
    if not doc.is_file():
        check("5.3", False, "docs/机制审计-v122.md 不存在")
        check("5.4", False, "文档不存在")
    else:
        t = doc.read_text(encoding="utf-8")
        ok = ("## pending_fix" in t and "## 双实现清单" in t)
        check("5.3", ok, "含 pending_fix + 双实现清单")
        check("5.4", ("auto_plan" in t and "_auto_plan" in t),
              "auto_plan 与 _auto_plan 都检出")
    src_txt = Path(src).read_text(encoding="utf-8")
    check("5.5", "机制审计" in src_txt, "源码含『机制审计』渲染点")
    # 5.7 登记常量与源码注释条数**两向对账**（单向登记会腐烂）
    _n_pf = src_txt.count("# [AUDIT-122] 标 pending_fix：")
    _n_dual = src_txt.count("_AUDIT122_DUAL_IMPL = ")
    _const_pf = getattr(mod, "_AUDIT122_PENDING_FIX", None)
    _const_dual = getattr(mod, "_AUDIT122_DUAL_IMPL", None)
    _doc_dual_rows = 0
    _doc = HERE / "docs/机制审计-v122.md"
    if _doc.is_file():
        _t = _doc.read_text(encoding="utf-8")
        _i = _t.find("## 双实现清单")
        if _i >= 0:
            # 数据行 = 以 `|` 开头、不是分隔行、且含反引号（表头行没有）
            _doc_dual_rows = sum(
                1 for ln in _t[_i:].split("\n")
                if ln.startswith("|") and "---" not in ln and "`" in ln)
    check("5.7",
          _const_pf == _n_pf and _const_dual == _doc_dual_rows
          and _n_dual == 1,
          f"登记对账：pending_fix 常量 {_const_pf} = 注释 {_n_pf}；"
          f"双实现常量 {_const_dual} = 文档行 {_doc_dual_rows}；"
          f"常量定义 {_n_dual} 处")
    if BASELINE.is_file():
        d = count_del_lines(BASELINE, src)
        check("5.6", d <= _V12316_AUTH_DEL_BUDGET,
              f"本版删除代码行 = {d}"
              f"（授权预算 {_V12316_AUTH_DEL_BUDGET}）")
    else:
        check("5.6", False, "基线缺失")


# ── 阶段 6 ──────────────────────────────────────────────────
def phase6(src, mod):
    import inspect
    if mod is None:
        for cid in ("6.2", "6.3"):
            check(cid, False, "模块未加载")
    else:
        ap = getattr(mod.MetaDGTF, "_auto_plan", None)
        m_ap = getattr(mod, "auto_plan", None)
        if ap is None or m_ap is None:
            check("6.2", False, "auto_plan/_auto_plan 缺失")
        else:
            try:
                body = inspect.getsource(ap)
            except Exception as e:
                body = f"ERR {e}"
            thin = ("auto_plan(" in body) and (body.count("\n") < 30)
            check("6.2", thin, f"_auto_plan 薄壳（行数 {body.count(chr(10))}）")
        src_txt = Path(src).read_text(encoding="utf-8")
        # ★ 按 **AST** 数定义，不数字面串：docstring 里提到函数名会被
        #   字面串计数误当成定义（本项目踩过多次，v122 阶段6 又踩一次）。
        _ndef = sum(1 for x in ast.walk(ast.parse(src_txt))
                    if isinstance(x, ast.FunctionDef)
                    and x.name == "_compute_rephrase_streak")
        check("6.3", _ndef == 1,
              f"AST 里 _compute_rephrase_streak 定义 {_ndef} 处（期望 1）；"
              f"字面串出现 {src_txt.count('def _compute_rephrase_streak')} 次")
    doc = HERE / "docs/机制审计-v122.md"
    if doc.is_file():
        t = doc.read_text(encoding="utf-8")
        check("6.5", "resolved" in t, "审计文档 resolved 段存在")
    else:
        check("6.5", False, "审计文档不存在")
    # 6.6 AST：新增符号必须**逐条有解释**（登记表两向对账）
    #   ★ 本版不可能 AST 等价（六个阶段各自新增函数）。任务书的第二条路是
    #     「逐节点差异有解释」—— 判据：新增未登记判红、登记却不存在也判红；
    #     符号**消失**一律判红（红线：不许删机制）。
    if BASELINE.is_file():
        try:
            import ast as _ast
            import json as _json

            def _syms(p):
                t = _ast.parse(Path(p).read_text(encoding="utf-8"))
                return {n.name for n in _ast.walk(t)
                        if isinstance(n, (_ast.FunctionDef, _ast.ClassDef))}
            _a, _b = _syms(BASELINE), _syms(src)
            _added = sorted(_b - _a)
            _gone = _auth_removed(sorted(_a - _b))
            _regf = HERE / "_v122_ast_registry.json"
            _reg = (_json.loads(_regf.read_text(encoding="utf-8")).get("registry")
                    if _regf.is_file() else {})
            _unreg = [x for x in _added if x not in _reg]
            _stale = [k for k in _reg if k not in _added]
            check("6.6", (not _gone) and (not _unreg) and (not _stale),
                  f"AST 登记对账：新增 {len(_added)} / 未登记 {len(_unreg)}"
                  f"{('：' + '、'.join(_unreg[:4])) if _unreg else ''} / "
                  f"过期登记 {len(_stale)} / 符号消失 {len(_gone)}")
            print(f"  ℹ️  符号数 基线 {len(_a)} → 本版 {len(_b)}；新增 "
                  f"{len(_added)} 项逐条有解释（_v122_ast_registry.json）")
        except Exception as e:
            check("6.6", False, f"{e}")
    else:
        check("6.6", False, "基线缺失")
    # 6.4 产物对照。★ 口径按**实测**修正，两条一起才判：
    #   (a) 结构化字段一致（可达判据）：头部标记、四层目标、decision 落地段、
    #       机制审计行 —— 这些是**计算出来的**，不该因重跑而变；
    #   (b) **负对照**：同一个文件跑两次的差异，不得明显小于跨版本差异。
    #       否则「跨版本逐字一致」这句话没有信息量 —— 引擎每一步都是独立
    #       抽样，两次跑本来就不会逐字相同（实测 rc1→定稿改了 3927 行，
    #       而同文件两次跑的差异同量级）。
    import json as _json4
    _g = HERE / "_v122_phase6_g64.json"
    if not _g.is_file():
        check("6.4", False, "产物对照未跑（缺 _v122_phase6_g64.json）")
    else:
        _d = _json4.loads(_g.read_text(encoding="utf-8"))
        _r = _d.get("rc1_vs_final") or {}
        _c = _d.get("same_file_negative_control") or {}
        _a = bool(_d.get("rc1_vs_final_struct_equal"))
        _b = bool(_d.get("same_file_struct_equal"))
        _nr = int(_r.get("changed_lines") or 0)
        _nc = int(_c.get("changed_lines") or 0)
        _neg_ok = _nc > 0 and _nc >= _nr * 0.5
        check("6.4", _a and _b and _neg_ok,
              f"产物对照：结构化一致={_a and _b}；"
              f"跨版本差异 {_nr} 行 / 同文件两次差异 {_nc} 行"
              f"（负对照要求后者 ≥ 前者的 50%：{_neg_ok}）")
        if _a and _b and _neg_ok:
            print(f"  ℹ️  「逐字一致」在本引擎**不可达**（每步独立抽样）："
                  f"跨版本 {_nr} 行差异 ≈ 同文件重跑 {_nc} 行差异 → 无信号；"
                  f"真正判等价的是结构化字段 + 阶段6 的打桩对照")


# ── 全局 ────────────────────────────────────────────────────
def global_checks(src):
    c = crlf_ok(src)
    check("G.crlf", c["ok"],
          f"CRLF 一致：bare_lf={c['bare_lf']} crr_lf={c['crr_lf']}")
    try:
        ast.parse(Path(src).read_text(encoding="utf-8"))
        check("G.parse", True, "AST 可解析")
    except SyntaxError as e:
        check("G.parse", False, f"AST 解析失败 {e}")
    if BASELINE.is_file():
        ds = diff_stat(BASELINE, src)
        print(f"  ℹ️  差异规模：{ds['blocks']} 块 / +{ds['added']} -{ds['deleted']}"
              f"（{ds['lines_before']} → {ds['lines_after']} 行）")
    st = HERE / "smoke_test.py"
    if st.is_file():
        m = re.search(r'SRC = HERE / "([^"]+)"', st.read_text(encoding="utf-8"))
        check("G.smokeSRC", m is not None and m.group(1) == Path(src).name,
              f"smoke_test.SRC = {m.group(1) if m else None}")
    if BASELINE.is_file():
        nd = count_del_lines(BASELINE, src)
        nr = count_replaced_lines(BASELINE, src)
        check("G.del", nd <= _V12316_AUTH_DEL_BUDGET,
              f"纯删除行 {nd}"
              f"（授权预算 {_V12316_AUTH_DEL_BUDGET}）；"
              f"改写行 {nr}（如实报，不计删）")
        try:
            gone = _auth_removed(mechanism_removed(BASELINE, src))
        except Exception as e:  # noqa: BLE001
            gone = [f"AST 对比失败：{e}"]
        check("G.mech", not gone,
              f"授权清单外的机制未被移除（符号消失 {len(gone)} 项"
              f"{('：' + '；'.join(gone[:4])) if gone else ''}）")
        sh = function_shrunk(BASELINE, src)
        print(f"  ℹ️  函数体骤减 {len(sh)} 项"
              f"{('：' + '；'.join(sh) + '（须在报告里解释）') if sh else ''}")


_P1_FIELDS = ("verb", "object", "owner_role", "deadline_hint",
               "acceptance", "fallback")


def _region(txt: str, a: str, b: str) -> str:
    """按源码字面串取区间。整文件 grep 会在 before 也命中，判据就没判别力了。"""
    i = txt.find(a)
    j = txt.find(b)
    return txt[i:j] if i >= 0 and j > i else ""


def _p1_actions_from_md(p) -> dict:
    """从产物 md 的「### 二、行动清单」段数 action 与 rubric。

    rubric（三项各 1 分，上限 3）：
      ① action 条数 ≥ 3；② 每条回退非「（未指定）」；③ 「不做什么」非空。
    """
    import re as _re
    t = p.read_text(encoding="utf-8") if hasattr(p, "read_text") else str(p)
    m = _re.search(r"### 二、行动清单(.*?)### 三、", t, _re.S)
    if not m:
        return {"n": 0, "rubric": 0, "note": "无行动清单段"}
    seg = m.group(1)
    ids = _re.findall(r"- \*\*(A\d+)\*\*", seg)
    fallbacks = _re.findall(r"- 回退：(.+)", seg)
    nd = _re.search(r"### 五、不做什么\n(.*?)(?:\n### |\Z)", t, _re.S)
    nd_n = len([l for l in (nd.group(1).splitlines() if nd else [])
                if l.strip().startswith("- ")]) if nd else 0
    ok_fb = bool(fallbacks) and all("未指定" not in f for f in fallbacks)
    r = (1 if len(ids) >= 3 else 0) + (1 if ok_fb else 0) + (1 if nd_n else 0)
    return {"n": len(ids), "ids": ids[:6], "n_not_do": nd_n,
            "rubric": r, "fallbacks_all": ok_fb}


def phase_p1(src, mod):
    """[v1.22.1 P1] 研究层直接产出结构化 actions 段。"""
    txt = Path(src).read_text(encoding="utf-8").replace("\r\n", "\n")
    sk = _region(txt, '  "decidable_product": {', '  "undecidable_product": {')
    rq = _region(txt, "【A. decidable_product 要求】",
                 "【B. undecidable_product 要求】")
    _miss = [f for f in _P1_FIELDS if f'"{f}"' not in sk]
    check("P1.1.a", '"actions"' in sk, "decidable_product 骨架里有 actions 键")
    check("P1.1.b", not _miss, f"骨架里六字段齐（缺 {_miss}）")
    check("P1.1.c", "decision 取向必须产出" in rq, "prompt 约束段在")

    def _mk(dp):
        v = mod.View(entry="1")
        v.decidable_product = dp
        return v

    def _try(fn):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            return f"ERR {type(e).__name__}: {e}"

    _full = [{"id": f"A{i}", "verb": "指派", "object": f"对象{i}",
              "owner_role": "区防汛办", "deadline_hint": "汛期前 30 天",
              "acceptance": "出具签字人清单", "fallback": "向上级申请"}
             for i in (1, 2, 3)]
    a1 = _try(lambda: mod._extract_actions(
        _mk({"answer": "x", "actions": _full})))
    check("P1.2.a",
          isinstance(a1, list) and len(a1) == 3
          and all(x.get("_source") == "schema" for x in a1),
          f"schema 有 actions → 三条且 _source=schema（实测 "
          f"{a1 if not isinstance(a1, list) else [x.get('_source') for x in a1]}）")
    a2 = _try(lambda: mod._extract_actions(
        _mk({"answer": "先指派区防汛办核查。否则回退上级。"})))
    check("P1.2.b",
          isinstance(a2, list) and a2
          and all(x.get("_source") == "lexical" for x in a2),
          f"schema 无 actions → 走词法并带 _source=lexical（实测 "
          f"{a2 if not isinstance(a2, list) else [x.get('_source') for x in a2]}）")
    a3 = _try(lambda: mod._extract_actions(_mk({"answer": ""})))
    check("P1.2.c", a3 == [], f"负对照 空 answer → []（实测 {a3!r}）")
    a4 = _try(lambda: mod._extract_actions(
        _mk({"answer": "x", "actions": [{"id": "A1", "verb": "指派",
                                        "object": "核查"}]})))
    check("P1.2.d",
          isinstance(a4, list) and a4 and a4[0].get("_missing"),
          f"负对照 schema 缺字段 → _missing 标出（实测 "
          f"{a4 if not isinstance(a4, list) else a4[0].get('_missing')}）")

    check("P1.3.a", "模型没按 schema 产出 actions" in txt,
          "action_incomplete 语义注释已改写")
    check("P1.3.b", "action_fields_missing" in txt, "action_fields_missing 字面串在")
    _n_schema = len([x for x in a1 if x.get("_source") == "schema"]) \
        if isinstance(a1, list) else 0
    _any_miss = any(x.get("_missing") for x in a1) if isinstance(a1, list) else True
    check("P1.3.c", _n_schema >= 3 and not _any_miss,
          f"负对照 三条全字段齐全 → 不满足 action_incomplete 触发条件"
          f"（schema {_n_schema} 条 / 有缺字段 {_any_miss}）")
    a5 = _try(lambda: mod._extract_actions(
        _mk({"answer": "x", "actions": _full[:2]})))
    _n5 = len([x for x in a5 if x.get("_source") == "schema"]) \
        if isinstance(a5, list) else 0
    check("P1.3.d", _n5 == 2, f"正对照 只给 2 条 → 满足触发条件（实测 {_n5}）")
    check("P1.3.e",
          "action_fields_missing" in (getattr(mod, "_V122_HARD_FLAGS", ()) or ()),
          "新 flag 在 _V122_HARD_FLAGS 里（否则被 quality_flags 重算冲掉）")

    # ---- P1.4 三题真跑产物 ----
    tgt = [HERE / "outputs" / f"p1_run{i}" for i in (1, 2, 3)]
    mds = []
    for d in tgt:
        got = sorted(d.glob("*.md")) if d.is_dir() else []
        mds.append(got[0] if got else None)
    if not all(mds):
        check("P1.4.a", False,
              f"三题产物未齐（{sum(1 for x in mds if x)}/3）—— 先跑 _run_v1221_p1.sh")
    else:
        info = [_p1_actions_from_md(x) for x in mds]
        check("P1.4.a", all(i["n"] >= 3 for i in info),
              f"三题 action 均 ≥ 3（实测 {[i['n'] for i in info]}）")
        avg = sum(i["rubric"] for i in info) / 3.0
        check("P1.4.b", avg >= 2.0,
              f"三题 rubric 平均 ≥ 2/3（实测 {avg:.2f}；各项 "
              f"{[i['rubric'] for i in info]}）")
        _inc = []
        for x in mds:
            t = x.read_text(encoding="utf-8")
            _inc.append("actions 段不足" in t or "action_incomplete" in t)
        check("P1.4.c", not any(_inc),
              f"三题 action_incomplete 均为 0（实测 {_inc}）")
        print(f"  ℹ️  P1.4 详情：" + "；".join(
            f"{p.parent.name} n={i['n']} rubric={i['rubric']} 不做={i['n_not_do']}"
            for p, i in zip(mds, info)))


def _phase_todo(name: str):
    """未实现档的占位：**判红**，不许以 PASS 0 / FAIL 0 假绿。"""
    def _f(src, mod):
        check(f"{name}.todo", False,
              f"{name} 尚未实现（本档未开；不许跨档验收）")
    return _f


def _p2_triage_from_md(p) -> dict:
    """从产物 md 取 triage 条数 + 漂移读数（undecidable → partial）。

    md 末尾有 ```json 围栏的 packed 快照，里面有 `pools.*.decidability_log`。
    """
    import re as _re
    t = p.read_text(encoding="utf-8")
    m = _re.search(r"\*\*triage 降级\*\*：(\d+) 条", t)
    n = int(m.group(1)) if m else None
    und = tot = 0
    for blk in _re.findall(r"```json\s*(.*?)```", t, _re.S):
        try:
            d = json.loads(blk)
        except Exception:
            continue
        pools = (d.get("pools") or {}) if isinstance(d, dict) else {}
        for pool in pools.values():
            for ent in ((pool or {}).get("decidability_log") or []):
                tot += 1
                if (str((ent or {}).get("from")) == "undecidable"
                        and str((ent or {}).get("to")) == "partial"):
                    und += 1
    return {"triage": n, "und_from": und, "log_total": tot}


def phase_p2(src, mod):
    """[v1.22.1 P2] triage 触发条件改挂结构标签。"""
    txt = Path(src).read_text(encoding="utf-8").replace("\r\n", "\n")
    # ★ 区域边界要取「_anchor_crosscheck 之后的**下一个** def」：
    #   `_anchor_pooled_total` 在它**前面**，用它当右界会取不到区间
    #   （第一版就这么误报了两条 FAIL）。
    # [v1.23.2] 组装逻辑搬到纯函数 `_triage_suggestions` 之后，「区域」要扩成
    #   两处之和，并**额外钉住调用关系**（否则「搬走了」与「删掉了」看起来一样）。
    def _fn_src(_t, _name):
        for _n in ast.walk(ast.parse(_t)):
            if isinstance(_n, ast.FunctionDef) and _n.name == _name:
                return "\n".join(_t.split("\n")[_n.lineno - 1:_n.end_lineno])
        return ""

    _i0 = txt.find("def _anchor_crosscheck")
    _i1 = txt.find("\n    def ", _i0 + 10) if _i0 >= 0 else -1
    xc = txt[_i0:_i1] if _i0 >= 0 and _i1 > _i0 else txt[_i0:]
    check("P2.1.a", "for k in _TRIAGE_KEYS)" not in xc,
          "旧词表判据已从 crosscheck 换掉")
    _tri_src = _fn_src(txt, "_triage_suggestions")
    _xc_all = xc + "\n" + _tri_src
    check("P2.1.b ★ 判据存在 + 真的被 crosscheck 用到（判据区域 = "
          "_anchor_crosscheck ∪ _triage_suggestions）",
          "_is_triage_candidate(" in _xc_all
          and "_triage_suggestions(" in xc,
          "调用关系缺失：_anchor_crosscheck 未调 _triage_suggestions")
    check("P2.1.c ★ 同上（先过 _is_never_downgrade）",
          "_is_never_downgrade(" in _xc_all,
          "_is_never_downgrade( 不在判据区域内")
    check("P2.1.d",
          '_TRIAGE_KEYS = ("信息不足", "需外部动作", "缺数据", "无外部")' in txt,
          "加性：旧词表一字未删")
    check("P2.2.a", "def _is_triage_candidate" in txt
          and "def _is_never_downgrade" in txt,
          "两个判据函数都在")

    def _try(fn):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            return f"ERR {type(e).__name__}: {e}"

    c1 = _try(lambda: mod._is_triage_candidate("[外] 具体某老城区的最优方案"))
    c2 = _try(lambda: mod._is_triage_candidate("信息不足，无法判断"))
    c3 = _try(lambda: mod._is_triage_candidate("现场取证难度大"))
    c4 = _try(lambda: mod._is_triage_candidate(""))
    c5 = _try(lambda: mod._is_never_downgrade("该判定自指，无共同参照系"))
    c6 = _try(lambda: mod._is_never_downgrade("[外] 具体某老城区的最优方案"))
    check("P2.3.a", c1 is True, f"结构标签 [外] 命中（实测 {c1!r}）")
    check("P2.3.b", c2 is True, f"语义关键词命中（实测 {c2!r}）")
    check("P2.3.c", c3 is False and c4 is False,
          f"负对照：无标签无语义词 → False（实测 {c3!r} / {c4!r}）")
    check("P2.3.d", c5 is True, f"真·自指判为不许降级（实测 {c5!r}）")
    check("P2.3.e", c6 is False,
          f"负对照：[外] 不是自指（实测 {c6!r}）")

    # ===== [v1.23.2] ★ 判据形态修正：能力存在性 → **构造性证明** =====
    # 原判据是「三题真跑里 ≥1 题 triage ≥1 条」—— 那是对**低概率随机机制**
    # 做 n=3 采样：同配置两次批次给出 [1,0,0] 与 [0,…] ⇒ 本质是掷硬币。
    # 组装逻辑已抽成纯函数 `_triage_suggestions`，于是可以直接构造输入证明
    # 「合格输入必产 ≥1 条」，再配 3 条负对照；**采样读数降为观察项**。
    _tri = getattr(mod, "_triage_suggestions", None)
    check("P2.4.a0 机制已抽成纯函数（可构造性验证）", callable(_tri),
          "`_triage_suggestions` 不存在")
    if callable(_tri):
        def _tq(_asp, _anc, _f=2):
            return _tri(_asp, _anc, {"tier_floor": _f})

        _pos = _tq(["[外] 上游是否有官方标准"],
                   [{"id": "X1", "tier": 1,
                     "answers": ["上游是否有官方标准"]}])
        check("P2.4.a ★ 构造性证明：合格输入必产 ≥1 条建议",
              len(_pos) >= 1, repr(_pos)[:130])
        # ★ 样例必须**同时**是「triage 候选」和「真·自指」：
        #   否则拦它的是 `_is_triage_candidate` 那条，`_is_never_downgrade`
        #   那条判据的变异体就测不到东西（第一版用「最优方案本身…」就是这样）。
        _n1 = _tq(["[外] 该方案是否自指（无共同参照系）"],
                  [{"id": "X1", "tier": 1,
                    "answers": ["该方案是否自指（无共同参照系）"]}])
        check("P2.4.a-n1 负对照：真·自指 → 0 条", _n1 == [],
              "自指竟被建议降级：" + repr(_n1))
        _n2 = _tq(["两个候选方案之间的权衡"],
                  [{"id": "X1", "tier": 1, "claim": "两个候选方案之间的权衡"}])
        check("P2.4.a-n2 负对照：不属「缺外部材料」→ 0 条", _n2 == [],
              "非候选竟被建议降级：" + repr(_n2))
        _n3 = _tq(["[外] 上游是否有官方标准"],
                  [{"id": "X1", "tier": 4,
                    "answers": ["上游是否有官方标准"]}])
        check("P2.4.a-n3 负对照：锚点 tier 超门 → 0 条", _n3 == [],
              "超门锚点竟仍命中：" + repr(_n3))
        # ★ 2 个变异体：破坏 tier 门 / 破坏「真·自指」剔除
        import tempfile as _tf
        _mdir = Path(_tf.mkdtemp())
        # ★ 变异体样例里的「视角」必须是**列表**：`_triage_suggestions` 内部是
        #   `for _a in (und_aspects or [])`，传裸字符串会**逐字符迭代** ⇒
        #   全被判非候选 ⇒ 恒 [] ⇒ 变异体永不判红（第一版即此，属假绿）。
        _MUT = (
            ("tier 门",
             '                     if int(x.get("tier", 3) or 3) <= _floor',
             "                     if True",
             (["[外] 上游是否有官方标准"],
              [{"id": "X1", "tier": 4, "answers": ["上游是否有官方标准"]}])),
            ("自指剔除",
             "        if _is_never_downgrade(_a):" + chr(10) + "            continue",
             "        if False:" + chr(10) + "            continue",
             (["[外] 该方案是否自指（无共同参照系）"],
              [{"id": "X1", "tier": 1,
                "answers": ["该方案是否自指（无共同参照系）"]}])),
        )
        # ★ 变异体文件用**序号**命名、模块名**唯一** —— 不要把标签原文
        #   （含中文/空格）拼进路径：实测那样加载出来的模块行为不对，
        #   于是「变异体不判红」⇒ 判据假绿（本项目老坑：判据自己的环境问题
        #   会被读成被测代码没问题）。
        for _k, (_nm, _o, _n, (_asp, _anc)) in enumerate(_MUT):
            if txt.count(_o) != 1:
                check("P2.4.a-mut." + _nm, False,
                      "变异体锚点 %d 次" % txt.count(_o))
                continue
            _mp = _mdir / ("mut_tri_%d.py" % _k)
            _mp.write_bytes(txt.replace(_o, _n).replace(chr(10), chr(13) + chr(10))
                            .encode("utf-8"))
            _red = False
            _why = ""
            try:
                _spec = importlib.util.spec_from_file_location(
                    "dgtf_mut_tri_%d" % _k, str(_mp))
                _mm = importlib.util.module_from_spec(_spec)
                sys.modules["dgtf_mut_tri_%d" % _k] = _mm
                _spec.loader.exec_module(_mm)
                _out = _mm._triage_suggestions(_asp, _anc, {"tier_floor": 2})
                _red = len(_out) >= 1
                _why = repr(_out)[:90]
            except Exception as _e:  # noqa: BLE001
                _red = True
                _why = "加载/执行异常（按判红计）：" + type(_e).__name__
            check("P2.4.a-mut ★ 变异体「破坏%s」→ 对应负对照判红" % _nm, _red,
                  "变异体下判据没判红：" + _why)
    # ---- 真跑采样读数：**观察项**（不判红；能力由上面的构造性证明负责）----
    tgt = [HERE / "outputs" / f"p2_run{i}" for i in (1, 2, 3)]
    mds = []
    for d in tgt:
        # [v1.23.1 遗留4] ★ 取**最新**产物，不取「文件名排序第一」——
        #   目录里可能同时留着历史产物。按名排会读到**旧的那份**，
        #   于是「用当前版复真」变成「拿旧读数冒充新读数」。
        got = (sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime)
               if d.is_dir() else [])
        mds.append(got[-1] if got else None)
    if all(mds):
        info = [_p2_triage_from_md(x) for x in mds]
        _ns = [i["triage"] for i in info]
        print(f"  ℹ️  [观察项] 真跑 triage 采样 = {_ns}（n=3；**低概率机制** ⇒"
              f" 0 次命中属正常，本项**不判红**：能力已由 P2.4.a 构造性证明）")
        print("  ℹ️  P2.4 详情：" + "；".join(
            f"{p.parent.name} triage={i['triage']} 漂移 {i['und_from']}/"
            f"{i['log_total']}" for p, i in zip(mds, info)))
        _drift = []
        for i in info:
            if i["log_total"] == 0:
                _drift.append(None)
            else:
                _drift.append(i["und_from"] / i["log_total"])
        # ★ [v1.23.3] 显式口径：分母 <3 时比率不可判定（Wilson 上界 0.79 > 0.5），
        #   改用**绝对条数 ≤2** 兜底 —— 真「全是 partial」的形态会被它拦住，
        #   而单次正常的 und→partial（机制本来就在做）不再被判红。
        def _drift_ok(_info):
            for _i in _info:
                if (_i["und_from"] or 0) > 2:
                    return False
                if (_i["log_total"] or 0) >= 3:
                    if (_i["und_from"] / _i["log_total"]) > 0.5:
                        return False
            return True

        _ok_drift = _drift_ok(info)
        # 自检负对照：合成一条「很多条 und→partial」必须判红（判据要有牙）
        _negok = not _drift_ok([{"und_from": 5, "log_total": 5}])
        check("P2.4.b", _ok_drift and _negok,
              f"无题出现「全是 partial」漂移 [绝对条数 ≤2；分母 ≥3 时占比 ≤50%：" 
              f"{[(i['und_from'], i['log_total']) for i in info]}]"
              f"（自检负对照 {_negok}）")
        print("  ℹ️  P2 整体判据已由 `--phase p2b` 承担"
              "（P2a 单档记录保留为历史：触发条件已修通，卡在匹配对象；"
              "P2b 换匹配对象后打通）。")
        for p, i in zip(mds, info):
            if i["triage"]:
                _t = p.read_text(encoding="utf-8")
                _ln = [l for l in _t.splitlines()
                       if "triage" in l and "降级" in l][:2]
                print(f"  ℹ️  {p.parent.name} 降级行：{_ln}")
    else:
        print("  ℹ️  [观察项] 三题产物未齐（%d/3），采样读数不可得"
              % sum(1 for x in mds if x))



def phase_p2b(src, mod):
    """[v1.22.1 P2b] triage 端到端：answers 匹配路径（第二条门）。

    P2a 打通了「触发条件」，P2b 打通「匹配对象」：拿「缺什么」与锚点自己
    声明的「我能回答什么」比（`answers`），claim 老路径一字不动、取 OR。
    """
    CRLF = chr(13) + chr(10)
    NL = chr(10)
    txt = Path(src).read_text(encoding="utf-8").replace(CRLF, NL)

    # ---------- P2b.1 锚点快照 ----------
    af = HERE / "_test_anchors.json"
    if not af.is_file():
        check("P2b.1.a", False, "_test_anchors.json 缺失")
    else:
        d = json.loads(af.read_text(encoding="utf-8"))
        ans = d.get("anchors") or []
        n_ans = sum(1 for a in ans if a.get("answers"))
        check("P2b.1.a", n_ans >= 2,
              "有 answers 的锚点 " + str(n_ans) + "/" + str(len(ans)) + " ≥ 2")
        over5 = [a.get("id") for a in ans if len(a.get("answers") or []) > 5]
        check("P2b.1.b", not over5, "单锚点 answers ≤ 5（超限 " + str(over5) + "）")
        over40 = [(a.get("id"), x) for a in ans
                  for x in (a.get("answers") or []) if len(x) > 40]
        check("P2b.1.c", not over40, "单条 answer ≤ 40 字（超长 " + str(over40) + "）")
        # 1.d 静态能力：≥1 条 answer 能在 tier 门内对上一条 [外] 侧面。
        #   参照集 = P2a 三题真跑的 14 条侧面（P2b 的立论依据就是这批读数）。
        _ref = []
        for i in (1, 2, 3):
            _mf = HERE / "outputs" / ("p2_run" + str(i)) / "meta.json"
            if _mf.is_file():
                try:
                    _ref += (json.loads(_mf.read_text(encoding="utf-8"))
                             .get("und_aspects") or [])
                except Exception:
                    pass
        if not _ref:
            check("P2b.1.d", False, "参照集为空（缺 P2a 的 outputs/p2_runN/meta.json）")
        else:
            _hits = []
            for a in ans:
                if int(a.get("tier", 3) or 3) > 2:
                    continue
                for x in (a.get("answers") or []):
                    for s0 in _ref:
                        if mod._hit_by_answers(str(s0), [x]):
                            _hits.append((a.get("id"), x))
            check("P2b.1.d", bool(_hits),
                  "tier 门内 ≥1 条 answer 能对上 [外] 侧面（实测 " + str(len(_hits))
                  + " 条；参照集 " + str(len(_ref)) + " 条）")
            for h in _hits[:3]:
                print("  · P2b.1.d 命中：" + str(h[0]) + " 的 " + repr(h[1]))

    # ---------- P2b.2 两个匹配函数 ----------
    check("P2b.2.a", hasattr(mod, "_hit_by_answers"), "_hit_by_answers 存在")
    check("P2b.2.b", hasattr(mod, "_hit_by_claim"), "_hit_by_claim 存在")
    _i0 = txt.find("def _hit_by_claim")
    _i1 = txt.find(NL + "def ", _i0 + 10) if _i0 >= 0 else -1
    _bc = txt[_i0:_i1] if _i0 >= 0 and _i1 > _i0 else txt[_i0:]
    check("P2b.2.c", "_similar(" in _bc and "0.6" in _bc,
          "claim 路径字面 0.6 未改（宪法级禁令）")
    _j0 = txt.find("def _hit_by_answers")
    _j1 = txt.find(NL + "def ", _j0 + 10) if _j0 >= 0 else -1
    _ba = txt[_j0:_j1] if _j0 >= 0 and _j1 > _j0 else txt[_j0:]
    check("P2b.2.d", "_overlap_coef" in _ba and "_UNTRACED_OVERLAP" in _ba,
          "answers 路径用 _overlap_coef + _UNTRACED_OVERLAP（未新造阈值）")

    def _try(fn):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            return "ERR " + type(e).__name__ + ": " + str(e)

    _pos = _try(lambda: mod._hit_by_answers(
        "老城区现有排水管网的设计标准是多少年一遇",
        ["管网设计重现期", "老城区现有排水管网的设计标准"]))
    _neg1 = _try(lambda: mod._hit_by_answers("本地微观数据", ["管网设计重现期"]))
    _neg2 = _try(lambda: mod._hit_by_answers("任意", []))
    _neg3 = _try(lambda: mod._hit_by_answers("任意", None))
    check("P2b.2.e", _pos is True and _neg1 is False and _neg2 is False
          and _neg3 is False,
          "正向命中 + 三类负对照（实测 " + str([_pos, _neg1, _neg2, _neg3]) + "）")

    # ---------- P2b.3 _load_anchors 读 answers ----------
    _tmp = HERE / "_verify_p2b_ans.json"
    _tmp.write_bytes(json.dumps(
        {"anchors": [{"id": "a1", "claim": "X", "tier": 1,
                      "answers": ["短", "老城区管网设计重现期标准"]}]},
        ensure_ascii=False).encode("utf-8"))
    try:
        _cfg = json.loads(json.dumps(mod.DEFAULT_CONFIG, default=str))
        _cfg["external_anchor"] = dict(_cfg.get("external_anchor") or {})
        _cfg["external_anchor"].update({"enabled": True, "path": str(_tmp)})
        _cfg["output"] = dict(_cfg.get("output") or {})
        _cfg["output"]["verbose"] = False
        _m = mod.MetaDGTF(_cfg)
        _m._load_anchors()
        _got = (_m._anchors[0].get("answers")
                if getattr(_m, "_anchors", None) else None)
        # [v1.22.2 P3] 样本须满足 answers_min_len：短的应被过滤、长的必须
        #   真读进来（原样本 3 字 → 会被新过滤器吃掉。判据随实现更新，不是放宽）。
        check("P2b.3", _got == ["老城区管网设计重现期标准"],
              "answers 键在且值读对 + 短答案被过滤（实测 " + repr(_got) + "）")
    except Exception as e:  # noqa: BLE001
        check("P2b.3", False, type(e).__name__ + ": " + str(e))
    finally:
        try:
            _tmp.unlink()
        except Exception:
            pass

    # ---------- P2b.4 crosscheck 双路径 ----------
    # [v1.23.2] 组装逻辑搬到纯函数 `_triage_suggestions` ⇒ 区域要扩成两处之和，
    #   并**钉住调用关系**（否则「搬走了」与「删掉了」在判据眼里一样）。
    _k0 = txt.find("def _anchor_crosscheck")
    _k1 = txt.find(NL + "    def ", _k0 + 10) if _k0 >= 0 else -1
    _xc = txt[_k0:_k1] if _k0 >= 0 and _k1 > _k0 else txt[_k0:]
    _tsrc = ""
    for _n in ast.walk(ast.parse(txt)):
        if isinstance(_n, ast.FunctionDef) and _n.name == "_triage_suggestions":
            _tsrc = NL.join(txt.split(NL)[_n.lineno - 1:_n.end_lineno])
            break
    _xc_all = _xc + NL + _tsrc
    check("P2b.4.a ★ crosscheck 路径调 _hit_by_answers（区域 = crosscheck ∪ "
          "_triage_suggestions，且跨check 必须真的调用它）",
          "_hit_by_answers(str(" in _xc_all and "_triage_suggestions(" in _xc,
          "调用关系缺失：_anchor_crosscheck 未调 _triage_suggestions")
    check("P2b.4.b ★ 同上（_hit_by_claim）", "_hit_by_claim(str(" in _xc_all,
          "crosscheck 路径没调 _hit_by_claim")
    check("P2b.4.a2 ★ 同上（读 anchors 的 answers 字段）",
          'x.get("answers")' in _xc_all,
          "crosscheck 路径没读 anchors 的 answers 字段")
    check("P2b.4.a3 ★ tier 门仍与双路径**同一处**（同一表达式内）",
          "<= _floor" in _xc_all and "and (" in _xc_all,
          "tier 门不在双路径之内")

    def _hit_sim(aspect, anchors, floor):
        """与 crosscheck 内联谓词同构（源码字面串由 P2b.4.a/b/a3 锁住）。"""
        return next((x for x in anchors
                     if int(x.get("tier", 3) or 3) <= floor
                     and (mod._hit_by_answers(str(aspect), x.get("answers") or [])
                          or mod._hit_by_claim(str(aspect),
                                               str(x.get("claim", ""))))),
                    None)

    _h1 = _try(lambda: _hit_sim("管网设计重现期 3~5 年",
                                [{"id": "n1", "tier": 1,
                                  "claim": "管网设计重现期 3~5 年"}], 2))
    check("P2b.4.c", isinstance(_h1, dict) and _h1.get("id") == "n1",
          "负对照：无 answers → 走 claim 路径（实测 " + str(_h1) + "）")
    _h2 = _try(lambda: _hit_sim("管网设计重现期 3~5 年",
                                [{"id": "n2", "tier": 1, "answers": [],
                                  "claim": "管网设计重现期 3~5 年"}], 2))
    check("P2b.4.d", isinstance(_h2, dict) and _h2.get("id") == "n2",
          "负对照：answers=[] → 也走 claim 路径（实测 " + str(_h2) + "）")
    _h3 = _try(lambda: _hit_sim("重建还是局部改造加海绵",
                                [{"id": "n3", "tier": 4,
                                  "answers": ["重建还是局部改造加海绵"]}], 2))
    check("P2b.4.e", _h3 is None,
          "负对照：tier 超 floor → 即便 answers 命中也不选（实测 " + str(_h3) + "）")

    # ---------- P2b.7 真跑（主判据） ----------
    _tags = ("老城区内涝", "中小制造", "社区医院")
    _rows = []
    for t in _tags:
        _mf = HERE / "outputs" / ("p2b_" + t) / "meta.json"
        _n = None
        _calls = None
        if _mf.is_file():
            try:
                _dd = json.loads(_mf.read_text(encoding="utf-8"))
                _v = _dd.get("triage_downgrades")
                _n = (len(_v) if isinstance(_v, list)
                      else (int(_v) if isinstance(_v, int) else None))
                _calls = _dd.get("calls")
            except Exception:
                pass
        _rows.append((t, _n, _calls))
    _have = [r for r in _rows if r[1] is not None]
    if not _have:
        check("P2b.7.a", False, "三题产物未齐（先跑 `python _run_v1221_p2b.py`）")
    else:
        check("P2b.7.a", any(isinstance(r[1], int) and r[1] >= 1 for r in _have),
              "≥1 题 triage ≥ 1 条（实测 " + str([r[1] for r in _rows])
              + "）-- 主判据")
        print("  · P2b.7 详情：" + "；".join(
            str(r[0]) + " triage=" + str(r[1]) + " calls=" + str(r[2])
            for r in _rows))
        for r in _rows:
            _mf = HERE / "outputs" / ("p2b_" + str(r[0])) / "meta.json"
            if not _mf.is_file():
                continue
            try:
                _dr = (json.loads(_mf.read_text(encoding="utf-8"))
                       .get("drift") or {})
            except Exception:
                _dr = {}
            print("  · P2b.8 漂移观察[" + str(r[0]) + "]（不判 pass/fail）："
                  + json.dumps(_dr, ensure_ascii=False))

    # ---------- P2b.9 不删机制 ----------
    _b1 = HERE / "元DGTF-V1.22.1-rc1.py"
    if _b1.is_file():
        _n_del = count_del_lines(str(_b1), src)
        check("P2b.9.a", _n_del <= _V12316_AUTH_DEL_BUDGET,
              "rc1 → rc1b 删除行 " + str(_n_del)
              + "（授权预算 " + str(_V12316_AUTH_DEL_BUDGET) + "）")
        _gone = _auth_removed(mechanism_removed(str(_b1), src))
        check("P2b.9.b", not _gone,
              "rc1 → rc1b 授权清单外符号消失 "
              + str(len(_gone)) + " 项")
    else:
        check("P2b.9.a", False, "缺 rc1 基线")
        check("P2b.9.b", False, "缺 rc1 基线")


def phase_p3(src, mod):
    """[v1.22.1 P3] 仅源码机制负对照（本版不删任何机制）。"""
    j = HERE / "_negctl_v1221_p3.json"
    md = HERE / "docs" / "机制负对照-v1221.md"
    check("P3.1.a", (HERE / "_negctl_v1221_p3.py").is_file(),
          "_negctl_v1221_p3.py 存在")
    check("P3.1.b", j.is_file() and md.is_file(),
          f"JSON={j.is_file()} 文档={md.is_file()}")
    if not j.is_file():
        check("P3.2", False, "负对照 JSON 缺失 —— 先跑 `python _negctl_v1221_p3.py`")
    else:
        data = json.loads(j.read_text(encoding="utf-8"))
        check("P3.2", len(data) >= 5, f"条数 {len(data)} ≥ 5")
        bad = [k for k, v in data.items()
               if v.get("verdict") not in ("条件不可达", "条件窄但成立",
                                           "机制没工作")]
        check("P3.3", not bad, f"判定全合法（非法 {bad}）")
        # ★ P3.4 对的是**冻结快照**，不是活的审计报告：
        #   语料会长大 —— 原本判「仅源码」的机制会随多跑几题变成「可达」，
        #   拿移动靶当锚会让这条判据**因为数据变大而翻红**，与「本版有
        #   没有删机制」毫无关系（实测：P3 时点 5 条 → 09:42 重跑审计 0 条）。
        _fz = HERE / "_negctl_v1221_p3_frozen.json"
        aud = (HERE / "audit_v122_dead_mechanisms.md")
        if _fz.is_file():
            _fzd = json.loads(_fz.read_text(encoding="utf-8"))
            _snap = set(_fzd.get("src_only_at_p3_time") or [])
            check("P3.4", set(data) == _snap,
                  "与冻结快照两向对账一致（P3 时点 "
                  + str(_fzd.get("n_src_only")) + " 条："
                  + "、".join(sorted(_snap)) + "）")
        else:
            check("P3.4", False,
                  "缺 _negctl_v1221_p3_frozen.json（P3 时点的仅源码快照）")
        if aud.is_file():
            _txt = aud.read_text(encoding="utf-8")
            _only = [ln.split("`")[1] for ln in _txt.splitlines()
                     if ln.startswith("| `") and "仅源码" in ln]
            print("  · P3.4 当前审计判「仅源码」的集合（不判红，语料长大"
                  "会让它缩）：" + str(sorted(_only)))
        fx = [k for k, v in data.items() if v["verdict"] == "机制没工作"]
        print(f"  ℹ️  P3 汇总：条件窄但成立 "
              f"{sum(1 for v in data.values() if v['verdict'] == '条件窄但成立')}"
              f" / 机制没工作 {len(fx)} / 条件不可达 "
              f"{sum(1 for v in data.values() if v['verdict'] == '条件不可达')}"
              f"；进 pending_fix 的 {len(fx) + sum(1 for v in data.values() if v['verdict'] == '条件不可达')} 项")
    _n_p35 = count_del_lines(str(BASELINE_V1220), src)
    check("P3.5", _n_p35 <= _V12316_AUTH_DEL_BUDGET,
          f"本版删除行 {_n_p35}"
          f"（授权预算 {_V12316_AUTH_DEL_BUDGET}）")
    gone = _auth_removed(mechanism_removed(str(BASELINE_V1220), src))
    check("P3.6", not gone,
          f"授权清单外的符号消失应为 0（实测 {len(gone)}）")



def phase_p4(src, mod):
    """[v1.22.1 P4] 一致率 ON/OFF 对照。

    ★ P4.1 的「运行时开关」**在本引擎里早已存在**（v1.22.0 加的
      `_action_on(config, "tri_multi_vote")` + `DEFAULT_CONFIG.actions
      .tri_multi_vote`），本档因此**不需要改引擎**（rc2 与 rc1b 逐字节相同）。
      本函数只判「对照跑完了没 + 结论有没有如实给出」。
    """
    runs = HERE / "runs" / "v1221"
    rows = {}
    for arm in ("ON", "OFF"):
        vs = []
        for i in (1, 2, 3):
            mf = runs / ("p4_" + arm + "_" + str(i)) / "meta.json"
            if not mf.is_file():
                vs.append(None)
                continue
            try:
                d = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                vs.append(None)
                continue
            vs.append(d if d.get("ok") else None)
        rows[arm] = vs
    _ok = [d for arm in rows for d in rows[arm] if d]
    check("P4.1.a", len(_ok) == 6,
          "ON/OFF 各 3 次跑完（实测 " + str(len(_ok)) + "/6）")

    jf = HERE / "_v1221_p4_consistency.json"
    check("P4.1.b", jf.is_file(),
          "_v1221_p4_consistency.json 存在（先跑 `python _v1221_p4_agg.py`）")
    if not (_ok and jf.is_file()):
        return
    d = json.loads(jf.read_text(encoding="utf-8"))
    _on = [x["consistency"] for x in (d.get("ON") or [])]
    _off = [x["consistency"] for x in (d.get("OFF") or [])]
    check("P4.1.c", len(_on) == 3 and len(_off) == 3,
          "两条臂各 3 条读数（" + str(len(_on)) + "/" + str(len(_off)) + "）")

    # ★ 实测发现：任务书指定的 md 口径在 **OFF 臂不可用** —— 那一行读的
    #   `stability` 只有多票路径（ON）才写，OFF 的子问题里连键都没有，
    #   引擎于是按 (0+0)/n 印出「一致率 0%」。那是**非读数**。
    _mm = d.get("md_metric") or {}
    check("P4.1.d", ("usable" in _mm) and bool(_mm.get("stability_key_present")),
          "汇总标了 md 口径可用性（usable=" + str(_mm.get("usable")) + "）")
    _f = d.get("fair") or {}
    check("P4.1.e", bool(_f.get("metric")) and (_f.get("on_avg") is not None)
          and (_f.get("off_avg") is not None),
          "汇总给了两臂都可得的口径：" + str(_f.get("metric")))

    print("  · P4 md 口径（任务书口径，可用=" + str(_mm.get("usable")) + "）：ON "
          + str([None if x is None else round(x, 3) for x in _on])
          + " / OFF " + str([None if x is None else round(x, 3) for x in _off])
          + " → " + ("可比" if _mm.get("usable") else "OFF 臂是**非读数**"))
    print("  · P4 公平口径：ON 平均 " + format(_f.get("on_avg") or 0.0, ".1%")
          + " / OFF 平均 " + format(_f.get("off_avg") or 0.0, ".1%")
          + " / 差 " + format(_f.get("diff") or 0.0, "+.1%"))
    print("  · P4 离散：ON 组内极差 " + format(_f.get("on_spread") or 0.0, ".1%")
          + " / OFF 组内极差 " + format(_f.get("off_spread") or 0.0, ".1%"))
    verdict = str(_f.get("verdict") or "")
    print("  · P4 四档判定（按公平口径）：" + verdict)

    rep = HERE / "v1221_p4_报告.md"
    if not rep.is_file():
        check("P4.2.a", False, "缺 v1221_p4_报告.md")
    else:
        t = rep.read_text(encoding="utf-8")
        check("P4.2.a", ("组内极差" in t) and ("组间差" in t),
              "报告含组内极差与组间差")
        _words = ("多票更好", "多票没做坏", "多票拖后腿", "无结论", "灰带")
        check("P4.2.b", any(w in t for w in _words),
              "报告给出四档之一（本档判定：" + verdict + "）")
        check("P4.2.c", ("非读数" in t) or ("不可用" in t),
              "报告如实写了 md 口径在 OFF 臂不可用（不许把 0% 当测量值）")
    check("P4.3.a", all((x.get("md_reading") for x in _ok)),
          "6 份产物都取到了 md 口径读数")


def phase_p5(src, mod):
    """[v1.22.1 P5] auto 取向回填：判定写入产物头部 + 错配可查。"""
    CRLF = chr(13) + chr(10)
    NL = chr(10)
    Q = chr(34)          # 引号：本文件不写反斜杠
    txt = Path(src).read_text(encoding="utf-8").replace(CRLF, NL)

    check("P5.1.a", "_auto_plan_used" in txt, "run() 记 _auto_plan_used")
    check("P5.1.b", "取向判定（plan_orientation）" in txt and "取向错配" in txt,
          "头部两行（取向判定 / 取向错配）都在")
    check("P5.1.c", Q + "_auto_plan_used" + Q in txt,
          "_pack_result 挂 _auto_plan_used")

    # auto_plan 的单调用分支必须带出 orientation（P5 的**前提**）
    _i0 = txt.find("def auto_plan(")
    _i1 = txt.find(NL + "def ", _i0 + 10) if _i0 >= 0 else -1
    _body = txt[_i0:_i1] if _i0 >= 0 and _i1 > _i0 else txt[_i0:]
    check("P5.2.a", ("data.get(" + Q + "orientation" + Q) in _body,
          "auto_plan 解析 orientation")
    # ★ [v1.23.13 判据随实现更新] 原 P5.2.b 数的是**源码字面**串
    #   `"orientation": _ori` —— v1.23.13 把三条出口收进唯一装配器
    #   `_assemble_plan(orientation=_ori)`，字面没了、**行为没变**。
    #   改成行为判据：早退分支（低置信退回 serial）返回的 orientation
    #   必须仍是解析出来的那个（下面 P5.2.b 的打桩段承担）。

    # 打桩行为：一次调用带出取向 + 只调一次 + 非法取向归一
    class _Stub:
        def __init__(self, ori, conf=0.9, mode="serial"):
            self.calls = []
            self.ori = ori
            self.conf = conf
            self.mode = mode

        def call(self, system, user, *a, **kw):
            self.calls.append((system, user))
            import json as _j
            return _j.dumps({"mode": self.mode, "orientation": self.ori,
                             "rounds": {"0": 4, "1": 4, "both": 4, "all": 5},
                             "reason": "桩", "confidence": self.conf})

        def parse_json(self, raw):
            import json as _j
            return _j.loads(raw)

    try:
        _s1 = _Stub("boundary")
        _p1 = mod.auto_plan("地铁运营效率该怎么衡量？",
                            dict(mod.DEFAULT_CONFIG), llm=_s1)
        _s2 = _Stub("随便")
        _p2 = mod.auto_plan("x", dict(mod.DEFAULT_CONFIG), llm=_s2)
        check("P5.2.c", _p1.get("orientation") == "boundary"
              and len(_s1.calls) == 1 and not _p2.get("orientation")
              and "orientation" in _s1.calls[0][0],
              "打桩：带出 boundary / 只调一次 / prompt 要了取向 / 非法归一")
        # ★ P5.2.b（行为版）：低置信 ⇒ 早退退回 serial，但**取向仍要带出**
        _s3 = _Stub("boundary", conf=0.1, mode="A")
        _p3 = mod.auto_plan("x", dict(mod.DEFAULT_CONFIG), llm=_s3)
        check("P5.2.b", _p3.get("mode") == "serial"
              and _p3.get("orientation") == "boundary",
              "早退分支（低置信退回 serial）也带出取向：mode="
              + repr(_p3.get("mode")) + " orientation="
              + repr(_p3.get("orientation")))
    except Exception as e:  # noqa: BLE001
        check("P5.2.c", False, type(e).__name__ + ": " + str(e))

    # 真跑证据
    _a = HERE / "outputs" / "p5_auto" / "meta.json"
    _b = HERE / "outputs" / "p5_boundary" / "meta.json"
    if not (_a.is_file() and _b.is_file()):
        check("P5.3.a", False, "缺 outputs/p5_auto 或 p5_boundary（先跑 _run_v1221_p56.py P5）")
        check("P5.3.b", False, "同上")
        check("P5.3.c", False, "同上")
        return
    _da = json.loads(_a.read_text(encoding="utf-8"))
    _db = json.loads(_b.read_text(encoding="utf-8"))
    _ha = _da.get("hits") or {}
    _hb = _db.get("hits") or {}
    check("P5.3.a", bool(_ha.get("取向判定（plan_orientation）")),
          "auto 真跑产物含「取向判定」（实测 " + json.dumps(_ha, ensure_ascii=False) + "）")
    check("P5.3.b", not _hb.get("取向错配"),
          "负对照：显式 boundary 时不含「取向错配」")
    _ori = ((_da.get("auto_plan_used") or {}).get("orientation") or "")
    _expect = (_ori not in ("", "decision"))
    check("P5.3.c", (not _expect) or bool(_ha.get("取向错配")),
          "auto 判为 " + repr(_ori) + " → 错配告警 "
          + ("应出现且已出现" if _expect else "不应出现（判成 decision）"))


def phase_p6(src, mod):
    """[v1.22.1 P6] tier 全缺省时的显式提示（+ 红线：无 tier 不入引用表）。"""
    CRLF = chr(13) + chr(10)
    NL = chr(10)
    Q = chr(34)          # 引号：本文件不写反斜杠
    txt = Path(src).read_text(encoding="utf-8").replace(CRLF, NL)
    check("P6.1.a", "_anchor_tier_warning" in txt and "锚点 tier 警告" in txt,
          "字段 + 头部行都在")
    check("P6.1.b", Q + "_anchor_tier_warning" + Q in txt,
          "_pack_result 挂 _anchor_tier_warning")

    # 关键：必须在**原始条目**上判「谁显式声明了 tier」，否则恒为 0
    check("P6.1.c", "_n_explicit_tier" in txt,
          "按原始条目计数显式 tier（任务书骨架在补过默认值的 out 上数，恒 0）")
    _i0 = txt.find("def _load_anchors")
    _i1 = txt.find(NL + "    def ", _i0 + 10) if _i0 >= 0 else -1
    _lb = txt[_i0:_i1] if _i0 >= 0 and _i1 > _i0 else txt[_i0:]
    check("P6.1.d", "_n_explicit_tier" in _lb,
          "计数发生在 _load_anchors 内")

    _notier = HERE / "_verify_p6_notier.json"
    _onetier = HERE / "_verify_p6_onetier.json"
    _notier.write_bytes(json.dumps(
        {"anchors": [{"id": "a1", "claim": "x"},
                     {"id": "a2", "claim": "y"}]}, ensure_ascii=False)
        .encode("utf-8"))
    _onetier.write_bytes(json.dumps(
        {"anchors": [{"id": "a1", "claim": "x"},
                     {"id": "a2", "claim": "y", "tier": 1}]},
        ensure_ascii=False).encode("utf-8"))

    def _load(path):
        cfg = json.loads(json.dumps(mod.DEFAULT_CONFIG, default=str))
        cfg["external_anchor"] = dict(cfg.get("external_anchor") or {})
        cfg["external_anchor"].update({"enabled": True, "path": str(path)})
        cfg["output"] = dict(cfg.get("output") or {})
        cfg["output"]["verbose"] = False
        mm = mod.MetaDGTF(cfg)
        mm._load_anchors()
        return getattr(mm, "_anchor_tier_warning", "<无属性>")

    try:
        w_all, w_one = _load(_notier), _load(_onetier)
        check("P6.2.a", isinstance(w_all, str) and bool(w_all),
              "全缺省 → 有警告（正对照）")
        check("P6.2.b", not w_one, "有显式 tier → 无警告（负对照）")
    except Exception as e:  # noqa: BLE001
        check("P6.2.a", False, type(e).__name__ + ": " + str(e))
        check("P6.2.b", False, "同上")
    finally:
        for _f in (_notier, _onetier):
            try:
                _f.unlink(missing_ok=True)
            except OSError:
                pass

    # 红线：无 tier 的锚点即便挂 evidence 档也不进引用表
    try:
        _p1 = mod.Pool()
        _p1.anchors = [{"id": "a1", "claim": "X"}]
        _p1.anchor_as_evidence = True
        _t1 = mod._citation_table(None, _p1)
        _p2 = mod.Pool()
        _p2.anchors = [{"id": "a2", "claim": "Y", "tier": 1}]
        _p2.anchor_as_evidence = True
        _t2 = mod._citation_table(None, _p2)
        check("P6.3.a", (not any(c.startswith("X") for c, _ in _t1))
              and any(c.startswith("X") for c, _ in _t2),
              "红线：无 tier 不入表 / tier=1 入表")
    except Exception as e:  # noqa: BLE001
        check("P6.3.a", False, type(e).__name__ + ": " + str(e))

    # 真跑证据
    _a = HERE / "outputs" / "p6_notier" / "meta.json"
    _b = HERE / "outputs" / "p6_tier" / "meta.json"
    if not (_a.is_file() and _b.is_file()):
        check("P6.4.a", False, "缺 outputs/p6_notier 或 p6_tier（先跑 _run_v1221_p56.py P6）")
        check("P6.4.b", False, "同上")
        return
    _ha = (json.loads(_a.read_text(encoding="utf-8")).get("hits") or {})
    _hb = (json.loads(_b.read_text(encoding="utf-8")).get("hits") or {})
    check("P6.4.a", bool(_ha.get("锚点 tier 警告")),
          "真跑：全缺省锚点 → 产物含警告")
    check("P6.4.b", not _hb.get("锚点 tier 警告"),
          "负对照：有 tier 的锚点 → 产物不含警告")


def phase_p7(src, mod):
    """[v1.22.1 P7] 明确不做：只查决策记录，不动代码。"""
    CRLF = chr(13) + chr(10)
    NL = chr(10)
    doc = HERE / "docs" / "不做什么-v1221.md"
    check("P7.1.a", doc.is_file(), "docs/不做什么-v1221.md 存在")
    if doc.is_file():
        t = doc.read_text(encoding="utf-8")
        for k in ("不拆模块", "不扩动词白名单", "不删任何机制"):
            check("P7.1.b." + k, k in t, "决策记录含「" + k + "」")
    else:
        for k in ("不拆模块", "不扩动词白名单", "不删任何机制"):
            check("P7.1.b." + k, False, "文档不存在")
    # P7 的骨架检查（与 smoke 同口径）
    try:
        check("P7.2", bool(mod) and hasattr(mod, "__version__"),
              "模块可加载（__version__ = " + str(getattr(mod, "__version__", "?")) + "）")
    except Exception as e:  # noqa: BLE001
        check("P7.2", False, type(e).__name__ + ": " + str(e))
    # 负对照：三条不许进产物头部
    txt = Path(src).read_text(encoding="utf-8").replace(CRLF, NL)
    _i = txt.find("def save_result")
    _head = txt[_i:_i + 20000] if _i >= 0 else ""
    _leak = [k for k in ("不拆模块", "不扩动词白名单", "不删任何机制")
             if k in _head]
    check("P7.3", not _leak, "决策记录不进产物头部（泄漏 " + str(_leak) + "）")




# <<<v1222 phases>>>
def phase_v1222_p1(src, mod):
    """[v1.22.2 P1] P4 两臂口径统一。"""
    t = Path(src).read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10))
    check("P1.1.a", hasattr(mod, "_single_vote_stability") if mod else False,
          "_single_vote_stability 存在")
    check("P1.1.b",
          bool(mod) and hasattr(mod.MetaDGTF, "_write_tri_stability"),
          "MetaDGTF._write_tri_stability 存在")
    check("P1.2.a", "三态判决（" in t, "头部标题按 _vote_mode 分口径")
    check("P1.2.b", "_voted = _hi + _me + _lo" in t, "分母只数已判条")
    check("P1.2.c", '== "abstained"' in t, "弃权独立成档")
    check("P1.3 负对照", "**三态多票**：high {_hi} / medium {_me} / low {_lo}"
          not in t, "旧「无条件三态多票」渲染已撤")
    # 口径函数四向
    if mod and hasattr(mod, "_single_vote_stability"):
        _f = mod._single_vote_stability
        check("P1.4.a", _f({}) == "abstained", "未判条 → abstained")
        check("P1.4.b", _f({"_tri_judged": True, "decidability": "partial"})
              == "medium", "有判无原标签 → medium")
        check("P1.4.c", _f({"_tri_judged": True, "first_label": "decidable",
                            "decidability": "partial"}) == "low",
              "不一致 → low")
        check("P1.4.d", _f({"_tri_judged": True, "first_label": "partial",
                            "decidability": "partial"}) == "high",
              "一致 → high")
    else:
        for k in ("P1.4.a", "P1.4.b", "P1.4.c", "P1.4.d"):
            check(k, False, "口径函数缺失")
    check("P1.5", (HERE / "v1222_p1_报告.md").is_file(), "v1222_p1_报告.md 存在")


def phase_v1222_p2(src, mod):
    """[v1.22.2 P2] schema 加 not_do（四处打通）。"""
    t = Path(src).read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10))
    _reg = t[t.find('"decidable_product": {'):t.find('"undecidable_product": {')]
    check("P2.1", '"not_do"' in _reg, "prompt schema 含 not_do")
    check("P2.2", "not_do 段 · decision 取向必须产出" in t, "prompt 约束段存在")
    check("P2.3 ★", '"not_do": _norm_schema_not_do(dec.get("not_do")),' in t,
          "dec_norm 白名单含 not_do（不加会静默吞字段）")
    check("P2.4", bool(mod) and hasattr(mod, "_norm_schema_not_do"),
          "_norm_schema_not_do 存在")
    check("P2.5", bool(mod) and hasattr(mod, "_extract_not_do_lexical"),
          "_extract_not_do_lexical 保留（词法兜底）")
    check("P2.6", "_nd_schema = [x for x in _nd_d" in t,
          "not_do_missing 只认 schema 来源")
    if mod and hasattr(mod, "_norm_schema_not_do"):
        _n = mod._norm_schema_not_do
        check("P2.7.a 负对照", _n(None) == [] and _n("x") == [], "非 list → 空")
        check("P2.7.b 负对照", _n([{"what": ""}, {"what": " "}]) == [],
              "空 what 被过滤")
        check("P2.7.c", len(_n([{"what": "w%d" % i} for i in range(9)])) == 6,
              "上限 6 条")
    if mod and hasattr(mod, "_extract_not_do"):
        _v = {"decidable_product": {"not_do": [
            {"what": "不在成因未定时动工", "why": "判据未立"}]}}
        _g = mod._extract_not_do(_v)
        check("P2.8", len(_g) == 1 and _g[0]["_source"] == "schema",
              "schema 路径命中 + _source")
        _e = type("V", (), {"decidable_product": {}})()
        check("P2.9 负对照", mod._extract_not_do(_e) == [], "空 view → 0 条")
    try:
        sys.path.insert(0, str(HERE / "bench"))
        from bench_score import score_actions
        _a3 = [{"fallback": "退路%d" % i} for i in range(3)]
        check("P2.10.a 负对照", score_actions([], [])["score"] == 0,
              "空/空 → 0/3")
        check("P2.10.b", score_actions(_a3, [])["score"] == 2,
              "actions 满 + not_do 空 → 2/3")
        check("P2.10.c", score_actions(_a3, [{"what": "x"}])["score"] == 3,
              "actions 满 + not_do 非空 → 3/3")
        check("P2.10.d", score_actions(_a3, [{"what": "x"}])["max"] == 3,
              "rubric max 未变（没改判据）")
    except Exception as e:  # noqa: BLE001
        check("P2.10 rubic", False, type(e).__name__ + ": " + str(e))
    check("P2.11", (HERE / "v1222_p2_报告.md").is_file(), "v1222_p2_报告.md 存在")


def phase_v1222_p3(src, mod):
    """[v1.22.2 P3] answers 最短长度 + 双告警分离。"""
    t = Path(src).read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10))
    _ea = (getattr(mod, "DEFAULT_CONFIG", {}) or {}).get("external_anchor") or {}
    check("P3.1", _ea.get("answers_min_len") == 6, "answers_min_len 默认 6")
    check("P3.2", _ea.get("answers_max_n") == 5, "answers_max_n 默认 5")
    check("P3.3", '"answers": _ans_kept' in t, "answers = 过滤后结果")
    check("P3.4", "_answers_dropped" in t, "被丢项留痕")
    check("P3.5", "**锚点 answers 警告**" in t, "产物渲染已加")
    check("P3.6 ★ 双告警分离",
          t.count("self._anchor_answers_warning = (") == 1
          and "_anchor_answers_filtered" in t,
          "「未声明」与「被过滤」两条告警不混用同一属性")
    check("P3.7 负对照", "return inter / min(len(ka), len(kb))" in t,
          "_overlap_coef 分母仍 min（阈值未动）")
    # 行为：短丢长留
    if mod:
        import json as _j
        import tempfile as _tf
        p = Path(_tf.mkdtemp()) / "a.json"
        p.write_text(_j.dumps({"anchors": [{
            "id": "a1", "claim": "x",
            "answers": ["重现期", "老城区现有排水管网的设计标准是多少年一遇"]}]},
            ensure_ascii=False), encoding="utf-8")
        cfg = mod.load_config(str(HERE / "__nonexistent__.yaml"))
        cfg["external_anchor"] = dict(cfg["external_anchor"])
        cfg["external_anchor"].update({"enabled": True, "path": str(p)})
        o = object.__new__(mod.MetaDGTF)
        o.config = cfg
        o.vp = lambda *a, **k: None
        o._load_anchors()
        _ans = o._anchors[0].get("answers") or []
        check("P3.8.a", "重现期" not in _ans, "短 answer 被丢弃")
        check("P3.8.b", any("老城区" in x for x in _ans), "长 answer 保留")
        check("P3.8.c", bool(getattr(o, "_anchor_answers_filtered", "")),
              "过滤留痕非空")
        check("P3.8.d 负对照", getattr(o, "_anchor_answers_warning", None) == "",
              "「未声明」告警未被误触发")
    check("P3.9", (HERE / "v1222_p3_报告.md").is_file(), "v1222_p3_报告.md 存在")


def phase_v1222_p4(src, mod):
    """[v1.22.2 P4] W 系列启动检查清单（只出清单，不出代码）。"""
    doc = HERE / "docs" / "W系列启动检查清单-v1222.md"
    check("P4.1", doc.is_file(), "docs/W系列启动检查清单-v1222.md 存在")
    if doc.is_file():
        dt = doc.read_text(encoding="utf-8")
        for k in ("A. v1.22.2 前置", "B. W 系列任务书核验", "C. 四条宪法级特性",
                  "D. 独立通道", "E. 配额三层", "F. 锚点与联网的边界"):
            check("P4.2." + k.split(".")[0], k in dt, "清单含 " + k)
        check("P4.3 结论二选一",
              ("可以启动" in dt) or ("不启动" in dt), "结论有启动/不启动判定")
        check("P4.4 每条有依据",
              dt.count("断言") + dt.count("命令") + dt.count("文件") >= 6,
              "条目带断言/命令/文件路径依据")
    check("P4.5", (HERE / "v1222_p4_报告.md").is_file(), "v1222_p4_报告.md 存在")
# <<<end v1222 phases>>>

# <<<v123 phase>>>
def phase_v123_w1(src, mod):
    """[v1.23.0 W1] 核心联网基础设施（不接入任何环节）。"""
    t = Path(src).read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10))
    ws = (getattr(mod, "DEFAULT_CONFIG", {}) or {}).get("web_search") or {}
    check("W1.1", ws.get("enabled") is False, "web_search.enabled 默认 False")
    _q = ws.get("quota") or {}
    check("W1.2", all(k in _q for k in ("per_stage_round", "per_stage_total",
                                        "per_run_total")),
          "配额三层齐（" + str(sorted(_q)) + "）")
    _st = ws.get("stages") or {}
    check("W1.3", _st.get("practice_term_calibration") is False
          and _st.get("stop_criteria") is False, "修行层/停止判据默认关")
    lw = getattr(mod, "logger_web", None)
    check("W1.4.a", lw is not None and lw.name == "dgtf.websearch",
          "logger_web 名字 dgtf.websearch")
    check("W1.4.b ★", lw is not None and lw.propagate is False,
          "propagate=False（修正 B2）")
    check("W1.5", tuple(getattr(mod, "WEB_FAIL_KINDS", ())) ==
          ("timeout", "rate_limit", "empty", "dirty", "api_error"),
          "五档失败类型常量")
    for k in ("WebSearchCache", "WebSearchClient", "WebSearchGate",
              "build_web_search"):
        check("W1.6." + k, hasattr(mod, k), k + " 存在")

    if not (hasattr(mod, "WebSearchGate") and mod.WebSearchGate):
        return
    _def = {"web_search": dict(ws)}
    _def["web_search"]["quota"] = dict(_q)
    _def["web_search"]["stages"] = dict(_st)

    def _cfg(**over):
        c = {"web_search": dict(ws)}
        c["web_search"]["quota"] = dict(_q)
        c["web_search"]["stages"] = dict(_st)
        c["web_search"].update(over)
        return c

    G = mod.WebSearchGate
    check("W1.7 负对照", G(_cfg()).allow("research_decompose", 1)[0] is False,
          "默认关 → allow False")
    g = G(_cfg(enabled=True))
    check("W1.8", g.allow("research_decompose", 1)[0] is True, "授权环节 allow")
    check("W1.9", g.allow("stop_criteria", 1)[0] is False, "未授权环节拒")
    g.note_call("research_decompose", 1)
    g.note_call("research_decompose", 1)
    check("W1.10", g.allow("research_decompose", 1)[0] is False, "本圈配额拦住")
    g2 = G(_cfg(enabled=True))
    for i in range(8):
        g2.note_call("research_decompose", 100 + i)
    check("W1.11", g2.allow("research_decompose", 5)[0] is False, "全程配额拦住")
    g4 = G(_cfg(enabled=True))
    g4.note_failure("timeout")
    g4.note_failure("timeout")
    _r3 = g4.note_failure("timeout")
    check("W1.12.a ★", _r3 is True and g4.disabled is True,
          "第 3 次失败真的置 disabled（修正 B3）")
    check("W1.12.b", "连续失败 3 次" in g4.disable_reason
          and "降级" in g4.allow("research_decompose", 1)[1],
          "降级理由可读且 allow 与 disabled 状态一致")
    g5 = G(_cfg(enabled=True))
    g5.note_failure("t")
    g5.note_failure("t")
    g5.note_success()
    g5.note_failure("t")
    check("W1.13", g5.consecutive_failures == 1 and g5.disabled is False,
          "note_success 清零")

    if hasattr(mod, "WebSearchClient") and hasattr(mod, "WebSearchCache"):
        import tempfile as _tf
        C, Ca = mod.WebSearchClient, mod.WebSearchCache
        d = Path(_tf.mkdtemp())
        ca = Ca(24, root=str(d / "websearch"))
        c = C("tavily", "k", 1, 2, 0.0, ca)
        c._http = lambda q, n: ([{"claim": "x", "url": "u"}], "")
        c.search("Q1")
        c.search("Q1")
        check("W1.14", c.calls == 1 and c.cache_hits == 1,
              "缓存命中不增 calls（" + str([c.calls, c.cache_hits]) + "）")
        for kind, want in (("timeout", 3), ("rate_limit", 3), ("api_error", 3),
                           ("dirty", 3), ("empty", 1)):
            _c2 = C("tavily", "k", 1, 2, 0.0, None)
            _c2._http = (lambda _k: (lambda q, n: ([], _k)))(kind)
            _r, _got = _c2.search("Q-" + kind)
            check("W1.15." + kind, _got == kind and _c2.calls == want,
                  "%s → 分类 %s / 重试 %d" % (kind, _got, _c2.calls))
        _c3 = C("bing", "k", 1, 0, 0.0, None)
        try:
            _c3.search("Q")
            check("W1.16 负对照", False, "未知后端竟未抛错")
        except RuntimeError as e:
            check("W1.16 负对照", "尚未实现" in str(e), "未知后端抛错不降级")
        check("W1.17", str(Ca().root).replace("\\", "/").endswith(
            "cache/websearch"), "默认缓存目录 cache/websearch")
        _ra = getattr(mod, "AnchorRetriever", None)
        if _ra is not None:
            check("W1.18", "anchors" in str(_ra("tavily", "k")._cache_path(["q"])),
                  "锚点缓存目录未动（不与联网混用）")
        _g, _c = mod.build_web_search(_cfg(enabled=True))
        check("W1.19", _c.calls == 0 and isinstance(_g, G),
              "工厂不发起任何调用")
    check("W1.20", (HERE / "v1230_w1_报告.md").is_file(), "v1230_w1_报告.md 存在")

def _run_probe(name, src):
    """把探针当**验收命令**跑（子进程）：探针本身就是该档的判据集合，
    不在这里重抄一遍 —— 重抄必然两处分叉（本项目的老坑）。"""
    import subprocess
    import sys as _s
    _pp = HERE / name
    check("X." + name, _pp.is_file(), name + " 存在")
    if not _pp.is_file():
        return
    _r = subprocess.run([_s.executable, str(_pp), str(src)],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=900)
    _tail = (_r.stdout or "").strip().splitlines()[-1:] or [""]
    check("X." + name + ".exit", _r.returncode == 0,
          name + " exit=" + str(_r.returncode) + " " + _tail[0][:90])
    for _ln in (_r.stdout or "").splitlines():
        if _ln.strip().startswith("✗"):
            check("X." + name + ".fail", False, _ln.strip()[:150])


def phase_v123_w2(src, mod):
    """[W2] 研究层接入 + W# 引用门 + W# 硬约束（判据在探针里，含 3 变异体）。"""
    _run_probe("_probe_v123_w2.py", src)
    check("W2.rep", (HERE / "v1230_w2_报告.md").is_file(),
          "v1230_w2_报告.md 存在")


def phase_v123_w34(src, mod):
    """[W3+W4] 对撞/元层接入 + 三票正交化 + 宪法 C3/C4（含 2 变异体）。"""
    _run_probe("_probe_v123_w34.py", src)
    check("W34.rep", (HERE / "v1230_w34_报告.md").is_file(),
          "v1230_w34_报告.md 存在")


def phase_v123_w5(src, mod):
    """[W5] 缩减版全量回归：真后端单点 + ON/OFF 各 1 跑 + 报告。"""
    _j = HERE / "_v1230_w5_consistency.json"
    check("W5.1", _j.is_file(), "_v1230_w5_consistency.json 存在")
    if _j.is_file():
        import json as _json
        _d = _json.loads(_j.read_text(encoding="utf-8"))
        _rb = _d.get("real_backend") or {}
        check("W5.2 真后端单点跑通",
              _rb.get("kind") == "" and _rb.get("n", 0) > 0,
              "真 tavily 返回 %s 条（kind=%r）" % (_rb.get("n"), _rb.get("kind")))
        # ★ 口径放宽到「缓存**确实**命中过」：若该 query 在上一轮已被缓存，
        #   本次 calls_total 会是 0（直接命中），那不是缺陷。
        check("W5.3 真后端缓存生效", _rb.get("cache_hits", 0) >= 1,
              "命中缓存 %s 次；本次真打网络 %s 次"
              % (_rb.get("cache_hits"), _rb.get("calls_total")))
        _runs = {x["arm"]: x for x in (_d.get("runs") or [])}
        check("W5.4 ON/OFF 两跑都在", {"WON", "WOFF"} <= set(_runs),
              repr(sorted(_runs)))
        if "WOFF" in _runs:
            check("W5.5 负对照：OFF 臂零检索",
                  _runs["WOFF"]["web_results"] == 0
                  and _runs["WOFF"].get("gate", {}).get("run_total", 0) == 0,
                  "OFF 臂 web_results=%s" % _runs["WOFF"]["web_results"])
        if "WON" in _runs:
            check("W5.6 ON 臂真的检索了（W# 或失败留痕）",
                  _runs["WON"]["web_results"] > 0
                  or _runs["WON"]["web_errors"] > 0,
                  "W#=%s errors=%s stages=%s"
                  % (_runs["WON"]["web_results"], _runs["WON"]["web_errors"],
                     _runs["WON"]["web_stages"]))
            check("W5.7 ON 臂 stability 口径可读",
                  all(x in ("high", "medium", "low", "abstained")
                      for x in _runs["WON"]["stability"]),
                  repr(_runs["WON"]["stability"]))
    check("W5.8", (HERE / "v123_报告.md").is_file(), "v123_报告.md 存在")

# <<<end v123 phase>>>

def phase_v123_w6(src, mod):
    """[v1.23.1 遗留收尾] 真圈号 + tier 提案 + 三场景/正交度 + P2.4 复真。

    判据在 `_probe_v1231_left.py`（24 条，含 3 变异体）；这里只补
    「产物级」的三条：P2.4 的三题产物必须由**本版**产出、分析文件在。
    """
    import json as _json
    _run_probe("_probe_v1231_left.py", src)
    check("L1.rep", (HERE / "v1231_报告.md").is_file(), "v1231_报告.md 存在")
    _jf = HERE / "_v1230_w6_runs.json"
    check("L1.json", _jf.is_file(), "_v1230_w6_runs.json 存在")
    if _jf.is_file():
        _d = _json.loads(_jf.read_text(encoding="utf-8"))
        _want = Path(src).name
        check("L1.src ★ 跑批产物出自本版（不是旧版的陈旧读数）",
              _d.get("src") == _want,
              "跑批 src=%r，本版=%r" % (_d.get("src"), _want))
        _runs = [r for r in (_d.get("runs") or []) if r.get("ok")]
        check("L1.n 跑数 ≥ 9（3 题 × (1 OFF + 2 ON)）", len(_runs) >= 9,
              "成功跑 %d 条" % len(_runs))
        _on = [r for r in _runs if r.get("arm") == "ON"]
        _off = [r for r in _runs if r.get("arm") == "OFF"]
        check("L1.arm 两臂都在", bool(_on) and bool(_off),
              "ON %d / OFF %d" % (len(_on), len(_off)))
        # 负对照：OFF 臂零检索（默认关 = 零调用）
        check("L1.off0 ★ 负对照：OFF 臂 web_n 全 0 且 gate 零调用",
              all((r.get("web_n") or 0) == 0
                  and ((r.get("gate") or {}).get("run_total") or 0) == 0
                  for r in _off),
              repr([(r.get("tag"), r.get("web_n")) for r in _off]))
        # ON 臂真的走了真圈号（round_kind 只能是 in；前置的 pre 也应有）
        _kinds = sorted({k for r in _on for k in (r.get("web_round_kinds") or [])})
        check("L1.kind ON 臂留痕 round_kind 合法",
              all(k in ("pre", "in") for k in _kinds), repr(_kinds))
        _it = [x for r in _on for x in (r.get("web_items") or [])]
        check("L1.pair ★ round_kind 与 round 自洽（pre ⟺ 0；in ⟹ ≥1）",
              bool(_it) and all(
                  (int(x.get("round", -1)) == 0)
                  if str(x.get("round_kind")) == "pre"
                  else int(x.get("round", -1)) >= 1
                  for x in _it),
              repr([(x.get("round"), x.get("round_kind"))
                    for x in _it][:6]))
        _fu = [r for r in _runs if r.get("arm") == "ONFULL"]
        _fin = [x for r in _fu for x in (r.get("web_items") or [])
                if str(x.get("round_kind")) == "in"]
        check("L1.w3 ★ 全路由跑里 W3 环节的条必须是**真圈号**（≥1）",
              (not _fu) or (bool(_fin) and all(int(x.get("round", -1)) >= 1
                                               for x in _fin)),
              repr([(x.get("stage"), x.get("round")) for x in _fin][:4]))
    _ana = HERE / "_v1230_w6_analysis.md"
    check("L1.ana", _ana.is_file(), "_v1230_w6_analysis.md 存在")
    if _ana.is_file():
        _t = _ana.read_text(encoding="utf-8")
        check("L1.ana2 分析含「命中率」与「组间/组内」两段",
              "命中率" in _t and "组内" in _t, "")
    # P2.4 的判据锚：三题产物必须存在（由本版跑批产出）
    for _i in (1, 2, 3):
        _dd = HERE / "outputs" / ("p2_run%d" % _i)
        _mds = sorted(_dd.glob("*.md")) if _dd.is_dir() else []
        check("L1.p24.%d" % _i, bool(_mds), "p2_run%d 有产物" % _i)


def phase_v1232(src, mod):
    """[v1.23.2] 整体审计 + thinking 接线「行为不变」的机器证明 + 遗留收尾。

    判据本体在 `_probe_v1232_audit.py`（8 类机械检查 + 4 自检变异体）。
    这里补三条只有「两版配置对读」才能证的：
      V1 解析结果逐步与改前逐字相同（接线 + yaml 对齐的净效果）
      V2 改动的配置键**只允许**是「改前从未生效」的那两类
      V3 yaml 里那 15 个 stage 与 `thinking.default` 一致（与注释「关」一致）
    """
    import re as _re
    _run_probe("_probe_v1232_audit.py", src)

    _txt = Path(src).read_text(encoding="utf-8").replace("\r\n", "\n")
    # 本版新接线的 stage（改前调用点没传 stage ⇒ 掉回 default）
    # ★ 注入器用 %r 生成的字面量是**单引号**；只认双引号会抠到 0 个
    #   ⇒ V1/V3 变成空过（第一版即此）。两种引号都收。
    _wired = set(_re.findall(
        r"""stage=_thinking_stage\([^\n]*?,\s*["'](\w+)["']\)""", _txt))
    # 一直就在传字面 stage 的调用点
    _lit = set(_re.findall(r'stage="(\w+)"', _txt))
    check("V2 抽样非空（防空过）", bool(_wired) and bool(_lit),
          "wired=%d lit=%d" % (len(_wired), len(_lit)))

    _old = mod.load_config(str(HERE / "_bak_dgtf_config.pre_v1232"))
    _new = mod.load_config(str(HERE / "dgtf_config.yaml"))
    _ot = ((_old.get("api") or {}).get("thinking") or {})
    _nt = ((_new.get("api") or {}).get("thinking") or {})
    _os, _ns = _ot.get("stages") or {}, _nt.get("stages") or {}
    _od, _nd = _ot.get("default"), _nt.get("default")

    _bad = []
    for _k in sorted(_wired | _lit):
        # 改前：_wired 的调用点传 None ⇒ 掉回 _od；_lit 的取 _os[_k]
        _before = _od if _k in _wired else _os.get(_k, _od)
        _after = _ns.get(_k, _nd)
        if _before != _after:
            _bad.append((_k, _before, _after))
    check("V1 ★ thinking 接线 + yaml 对齐后，每个 stage 的解析结果与改前逐字相同",
          not _bad, repr(_bad[:4]))

    def _flat(d, pre=""):
        out = {}
        for k, v in (d or {}).items():
            key = "%s.%s" % (pre, k) if pre else str(k)
            if isinstance(v, dict):
                out.update(_flat(v, key))
            else:
                out[key] = v
        return out

    _fo, _fn = _flat(_old), _flat(_new)
    _chg = sorted(k for k in set(_fo) | set(_fn) if _fo.get(k) != _fn.get(k))
    _allow = ({"api.thinking.stages." + k for k in _wired}
              | {"web_search.tier_floor"} | _V12316_AUTH_KEYS)
    _unexpected = [k for k in _chg if k not in _allow]
    check("V3 ★ 两版配置的差异**只允许**是「改前从未生效」的两类（thinking 接线 / tier_floor）",
          not _unexpected, "意外改动：" + repr(_unexpected[:5]))
    _kw = [k for k in _chg if k.startswith("api.thinking.stages.")]
    _sv = {k: _ns.get(k.split(".")[-1]) for k in _kw}
    check("V4 yaml 里被改的 stage 一律 == thinking.default（与注释「关」一致）",
          all(v == _nd for v in _sv.values()), repr(_sv))

    check("V5", (HERE / "v1232_报告.md").is_file(), "v1232_报告.md 存在")


def phase_v1233(src, mod):
    """[v1.23.3] §十 五条全清：受控实验 / 思考 A/B / tier 真跑 / triage 频度
    + id 归一化（两处 + 一类）。

    判据分三层：
      V1~V4 代码层（版本一致 / 两个纯函数 / **模型 id 全部归一化**的不变式）
      V5    实验产物层（四份 json 的关键不变式，含**负对照**）
      V6    报告层（`v1233_报告.md` 存在且 §十 明确为「无遗留」）
    """
    import json as _json
    import re as _re
    from pathlib import Path as _P

    _run_probe("_probe_v1233_voteids.py", src)

    _txt = _P(src).read_bytes().decode("utf-8").replace(chr(13) + chr(10),
                                                        chr(10))
    _vc = _version_consistent(mod, src)
    check("V1 版本一致：主文件 __version__ / 冒烟 SRC / yaml 头",
          _vc[0] and _vc[1] == _vc[2] and _vc[3] and _vc[4],
          "ver=%s want=%s yaml=%s smoke=%s" % _vc[1:])

    # ---- V2 票 id 归一化（纯函数四向）----
    _f = getattr(mod, "_normalize_judgment_ids", None)
    check("V2 ★ `_normalize_judgment_ids` 四向（1起/0起/越界/空）",
          _f is not None
          and _f({1: "a", 2: "b"}, 2) == ({1: "a", 2: "b"}, "1起")
          and _f({0: "a", 1: "b"}, 2) == ({1: "a", 2: "b"}, "0起+1")
          and _f({1: "a", 9: "b"}, 2)[0] is None
          and _f({}, 2)[0] is None, "符号缺失或行为不符")

    # ---- V3 子问题 id 规范化 ----
    _c = getattr(mod, "_canonical_sub_ids", None)
    _demo = [{"id": 0, "q": "a"}, {"id": 0, "q": "b"}, {"id": 7, "q": "c"}]
    _out = _c([dict(x) for x in _demo]) if _c else None
    check("V3 ★ `_canonical_sub_ids` 把 0 起/重复/带洞的子问题 id 重编号成 1..n",
          _c is not None and [x["id"] for x in _out] == [1, 2, 3]
          and [x["q"] for x in _out] == ["a", "b", "c"],
          repr(_out))

    # ---- V4 不变式：所有「读模型返回的 id」的点都过了归一化 ----
    def _bad_sites(txtx):
        _bad = []
        _tr = ast.parse(txtx)
        _L = txtx.split(chr(10))
        for _fn in ast.walk(_tr):
            if not isinstance(_fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            _body = chr(10).join(_L[_fn.lineno - 1:_fn.end_lineno])
            if ("_normalize_judgment_ids(" in _body
                    or "_canonical_sub_ids(" in _body):
                continue
            for _n in ast.walk(_fn):
                if not (isinstance(_n, ast.Call)
                        and isinstance(_n.func, ast.Name)
                        and _n.func.id == "int" and _n.args):
                    continue
                _a = _n.args[0]
                if (isinstance(_a, ast.Call)
                        and isinstance(_a.func, ast.Attribute)
                        and _a.func.attr == "get" and _a.args
                        and isinstance(_a.args[0], ast.Constant)
                        and _a.args[0].value == "id"):
                    _bad.append((_fn.name, _n.lineno))
        return _bad

    _bs = _bad_sites(_txt)
    check("V4 ★ 所有读模型返回 id 的调用点都过了归一化（一类不变式）",
          not _bs, "未归一化：" + repr(_bs))
    _syn = ("def f(it):" + chr(10) + "    return int(it.get(" + chr(34)
            + "id" + chr(34) + ", 0))" + chr(10))
    check("V4.b 自检：合成源码必须被这套扫描报出（判别力）",
          len(_bad_sites(_syn)) == 1, repr(_bad_sites(_syn)))

    # ---- V5 实验产物层 ----
    _vj = HERE / "_v1233_votes.json"
    _vk = {}
    if _vj.is_file():
        _vk = _json.loads(_vj.read_text(encoding="utf-8"))
    _arms = ("w4_off_t0", "w4_on_t0", "w4_off_t7", "w4_on_t7")
    check("V5.a ★ 受控投票实验：四臂齐 + 每臂 3 个指标的 ICC 判定都有",
          _vk.get("src") == "元DGTF-V1.23.3.py"
          and all(a in (_vk.get("icc") or {}) for a in _arms)
          and all(all((_vk["icc"][a].get(mk) or {}).get("verdict")
                      for mk in ("a12", "a13", "a23")) for a in _arms),
          "src=%s arms=%s" % (_vk.get("src"), sorted(_vk.get("icc") or {})))
    _idb = _vk.get("id_base") or {}
    check("V5.b ★ 票 id 基准统计存在（0 起那条 bug 的频度证据）",
          all(a in _idb for a in _arms)
          and all(sum(_idb[a].values()) > 0 for a in _arms),
          repr(_idb))
    check("V5.c 字面口径「组间 ≥ 组内」的判定列非空（判据 B）",
          all((_vk.get("pair") or {}).get(t, {}).get("verdict_B")
              for t in ("t0", "t7")),
          repr(_vk.get("pair")))

    _th = HERE / "_v1233_thinking.json"
    _tk = _json.loads(_th.read_text(encoding="utf-8")) if _th.is_file() else {}
    _stg = _tk.get("stages") or {}
    check("V5.d ★ 思考 A/B：每个环节都有判定，且至少一个**可判定**",
          bool(_stg) and all(v.get("verdict") for v in _stg.values())
          and any(("不可判定" not in str(v.get("verdict")))
                  for v in _stg.values()),
          "环节 %d 个" % len(_stg))

    _tr = HERE / "_v1233_triage_runs.json"
    _trk = _json.loads(_tr.read_text(encoding="utf-8")) if _tr.is_file() else {}
    _nc = HERE / "_v1233_triage_negctl.json"
    _nck = _json.loads(_nc.read_text(encoding="utf-8")) if _nc.is_file() else {}
    check("V5.e ★ triage 频度专项批：报告了 k/n + Wilson 区间",
          (_trk.get("n_ok") or 0) >= 5 and _trk.get("wilson")
          and _trk.get("rate") is not None,
          "n_ok=%s rate=%s" % (_trk.get("n_ok"), _trk.get("rate")))
    check("V5.f ★ 负对照：锚点覆盖不到时 triage **必须 0 触发**",
          _nck and (_nck.get("hit") == 0) and (_nck.get("n_ok") or 0) >= 2,
          repr({k: _nck.get(k) for k in ("hit", "n_ok", "rate")}))

    _tl = HERE / "_v1233_tier_apply.json"
    _tlk = _json.loads(_tl.read_text(encoding="utf-8")) if _tl.is_file() else {}
    _r = _tlk.get("run") or {}
    _its = _r.get("items") or []
    check("V5.g ★ tier 确认真跑：留痕 + 生效/未生效两向 + 引用表按门收",
          bool(_r.get("tier_meta"))
          and any(x.get("tier_effective") is not None for x in _its)
          and any(x.get("tier_effective") is None for x in _its)
          and bool(_r.get("w_in_table")),
          "留痕=%s 进表=%s" % (str(_r.get("tier_meta"))[:80],
                             str(_r.get("w_in_table"))[:60]))
    check("V5.h ★ tier 基线（空确认表 + floor=2）引用表里**没有** W#",
          not ((_tlk.get("baseline") or {}).get("w_in_table")),
          repr((_tlk.get("baseline") or {}).get("w_in_table")))

    # ---- V6 报告层 ----
    _rp = HERE / "v1233_报告.md"
    _rt = _rp.read_bytes().decode("utf-8").replace(chr(13) + chr(10), chr(10)) \
        if _rp.is_file() else ""
    _i = _rt.find("## 十、")
    _sec = _rt[_i:_i + 900] if _i >= 0 else ""
    check("V6 ★ 报告存在且 §十「仍未做 / 如实记账」明确为**无遗留**",
          bool(_rt) and ("仍未做" in _sec) and ("无遗留" in _sec)
          and ("### " not in _sec),
          "§十 片段：" + repr(_sec[:120]))


def phase_v1234(src, mod):
    """[v1.23.4] 运行期三项总控（联网 / 思考 / 强度）。

    判据分四层：
      V1~V6 代码层：版本一致 / auto 恒等 / **思考总开关连 stages 整表** /
                    effort 取值集与拒非法 / 纯函数不改入参 /
                    load_config 四个出口都过它
      V7    接线层：CLI 三开关 + 交互询问 + 产物 `_runtime` 留痕
      V8    产物层：出厂 yaml 的 runtime 段是 auto（不覆盖）
      V9    报告层：`v1234_报告.md` 存在且写了设计取舍
    """
    import json as _json
    from pathlib import Path as _P

    _run_probe("_probe_v1234_runtime.py", src)

    _txt = _P(src).read_bytes().decode("utf-8").replace(chr(13) + chr(10),
                                                        chr(10))
    _D = _json.loads(_json.dumps(mod.DEFAULT_CONFIG))
    _J = lambda o: _json.dumps(o, sort_keys=True, ensure_ascii=False)

    _vc = _version_consistent(mod, src)
    check("V1 版本一致：主文件 __version__ / 冒烟 SRC / yaml 头",
          _vc[0] and _vc[1] == _vc[2] and _vc[3] and _vc[4],
          "ver=%s want=%s yaml=%s smoke=%s" % _vc[1:])

    # ---- V2 ★ 出厂恒等（这是「本版不改行为」的全部依据）----
    _a = getattr(mod, "_apply_runtime", None)
    _c0, _n0 = _a(_D) if _a else (None, None)
    check("V2 ★ 三项 auto ⇒ 配置**逐字恒等**（出厂零行为变化）",
          _a is not None and _J(_c0) == _J(_D) and _n0 == [],
          "notes=" + repr(_n0))

    # ---- V3 ★ 思考总开关必须连 stages 整表 ----
    def _stage_vals(cfg):
        return set(((cfg.get("api") or {}).get("thinking") or {})
                   .get("stages", {}).values())

    def _resolve(cfg, stage=None):
        _th = ((cfg.get("api") or {}).get("thinking") or {})
        _v = (_th.get("stages") or {}).get(stage) if stage else None
        if _v is None:
            _v = _th.get("default")
        return str(_v or "").lower() == "enabled"

    _off, _ = _a(_D, {"thinking": "off"}) if _a else ({}, None)
    _on, _ = _a(_D, {"thinking": "on"}) if _a else ({}, None)
    # 判别力自检：合成「只改 default、不动 stages」的配置必须**不满足**该判据
    _syn = _json.loads(_json.dumps(_D))
    _syn["api"]["thinking"]["default"] = "disabled"
    check("V3 ★ thinking=off ⇒ default 与 **stages 每一个键**都关",
          _a is not None and set(_stage_vals(_off)) == {"disabled"}
          and ((_off.get("api") or {}).get("thinking") or {})
          .get("default") == "disabled"
          and not any(_resolve(_off, k)
                      for k in (_D["api"]["thinking"]["stages"])),
          "stages 取值=" + repr(_stage_vals(_off)))
    check("V3.b 自检（判别力）：合成『只改 default』的配置必须**不满足**该判据",
          set(_stage_vals(_syn)) != {"disabled"}, "合成值不该全关")
    check("V3.c thinking=on ⇒ default 与 stages 全开（含出厂为 disabled 的）",
          _a is not None and set(_stage_vals(_on)) == {"enabled"}
          and all(_resolve(_on, k)
                  for k in (_D["api"]["thinking"]["stages"])), "")

    # ---- V4 effort 取值集 + 拒非法 ----
    _ef = getattr(mod, "_normalize_runtime_effort", None)
    _bad = [_a(_D, {"effort": "mediun"})[0] if _a else None,
            _a(_D, {"web": "maybe"})[0] if _a else None,
            _a(_D, {"thinking": "??"})[0] if _a else None]
    check("V4 ★ effort 取值集 = auto/low/high/max（low/high/max 三档可用）",
          tuple(getattr(mod, "_RUNTIME_EFFORTS", ())) == ("auto", "low",
                                                          "high", "max")
          and _ef is not None and _ef("max") == "max" and _ef("low") == "low"
          and _ef("high") == "high", repr(getattr(mod, "_RUNTIME_EFFORTS", None)))
    check("V4.b ★ 集合外的值（含 medium）一律被拒，且配置一字未改",
          _ef is not None and _ef("medium") is None
          and all(x is not None and _J(x) == _J(_D) for x in _bad),
          "三处非法值都应不改配置")

    # ---- V5 纯函数：不改入参 ----
    _b4 = _J(_D)
    if _a:
        _a(_D, {"web": "on", "thinking": "on", "effort": "max"})
    check("V5 ★ `_apply_runtime` 是纯函数（入参配置一字未改）",
          _a is not None and _J(_D) == _b4, "")

    # ---- V6 load_config 四个出口 ----
    _ok = True
    try:
        _ok = (_J(mod.load_config("")) == _J(_D)
               and _J(mod.load_config(str(HERE / "_no_such_rt.yaml")))
               == _J(_D))
    except Exception:  # noqa: BLE001
        _ok = False
    check("V6 ★ load_config 的缺省/空路径出口仍恒等且不炸",
          _ok and hasattr(mod, "_load_config_raw"), "")

    # ---- V7 接线 ----
    # ★ [v1.23.13 判据随实现更新] 末一条从「接线字面」改成**行为**：
    #   显式传三个开关 → 配置真的变（字面随重构消失，行为不变）。
    _wired = (all(x in _txt for x in ("--web", "--thinking", "--effort"))
              and "choices=list(_RUNTIME_SWITCHES)" in _txt
              and "choices=list(_RUNTIME_EFFORTS)" in _txt)
    try:
        _c3 = json.loads(json.dumps(mod.DEFAULT_CONFIG))
        _dp3 = mod.auto_dispatch("q", _c3, explicit={"web": "off",
                                                     "thinking": "on",
                                                     "effort": "max"})
        mod._apply_auto_dispatch(_c3, _dp3)
        _c3b, _ = mod._apply_runtime(_c3)
        _wired = _wired and _c3b["web_search"]["enabled"] is False \
            and _c3b["api"]["thinking"]["default"] == "enabled" \
            and _c3b["api"]["thinking"]["effort"] == "max"
    except Exception:  # noqa: BLE001
        _wired = False
    check("V7.a ★ CLI 三开关已接线（行为：显式值真落进配置）且 choices 收紧",
          _wired, "")
    check("V7.b 交互：`_ask_runtime` + 5 元组 + **深拷副本** run_cfg",
          ("def _ask_runtime(cfg):" in _txt)
          and ("runtime = _ask_runtime(" in _txt)
          and ("run_cfg, _rt_notes = _apply_runtime(cfg, runtime)" in _txt)
          and ("meta = MetaDGTF(run_cfg)" in _txt), "")
    check("V7.c 产物带 `_runtime` 生效读数",
          '"_runtime": _runtime_snapshot(self.config)' in _txt, "")

    # ---- V8 出厂 yaml 的 runtime 段 ----
    try:
        import yaml as _yaml
        _ry = _yaml.safe_load((HERE / "dgtf_config.yaml")
                              .read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        _ry = {}
    check("V8 ★ 出厂 yaml 的 runtime 三项都是 auto（出厂 = 不覆盖既有键）",
          isinstance(_ry.get("runtime"), dict)
          and all(_ry["runtime"].get(k) == "auto"
                  for k in ("web", "thinking", "effort")),
          repr(_ry.get("runtime")))

    # ---- V9 报告层 ----
    _rp = HERE / "v1234_报告.md"
    _rt = _rp.read_bytes().decode("utf-8").replace(chr(13) + chr(10), chr(10)) \
        if _rp.is_file() else ""
    check("V9 ★ 报告存在且写了「设计取舍」与三层优先级",
          bool(_rt) and ("取舍" in _rt)
          and ("auto" in _rt)
          and ("stages" in _rt), "报告 %d 字节" % len(_rt))


PHASES = {"1": phase1, "2": phase2, "3": phase3, "4": phase4,
          "5": phase5, "6": phase6,
          "p1": phase_p1, "p2": phase_p2, "p3": phase_p3,
          "p2b": phase_p2b,
          "p4": phase_p4, "p5": phase_p5, "p6": phase_p6,
          "p7": phase_p7,
          "v1222_p1": phase_v1222_p1, "v1222_p2": phase_v1222_p2,
          "v1222_p3": phase_v1222_p3, "v1222_p4": phase_v1222_p4,
          "v123_w1": phase_v123_w1,
          "v123_w2": phase_v123_w2,
          "v123_w34": phase_v123_w34,
          "v123_w5": phase_v123_w5,
          "v123_w6": phase_v123_w6,
          "v1232": phase_v1232,
          "v1233": phase_v1233,
          "v1234": phase_v1234}


def main():
    ap = argparse.ArgumentParser(
        description="元 DGTF v1.22 六阶段 + v1.22.1 三档验收")
    ap.add_argument("--phase", default="all")
    ap.add_argument("--src", required=True)
    args = ap.parse_args()
    src = args.src
    if not Path(src).is_absolute():
        src = str(HERE / src)
    print(f"═══ v1.22 验收 · phase={args.phase} · src={Path(src).name} ═══")
    mod = None
    try:
        mod = load_module(src)
        print("  ℹ️  模块加载成功")
    except Exception as e:
        print(f"  ⚠️  模块加载失败：{e}")
        traceback.print_exc(limit=3)
    global_checks(src)
    want = list(PHASES) if args.phase == "all" else [args.phase]
    for k in want:
        fn = PHASES.get(k)
        if not fn:
            continue
        print(f"\n── 阶段 {k} ──")
        try:
            fn(src, mod)
        except Exception as e:
            check(f"{k}.crash", False, f"阶段 {k} 验收函数抛错：{e}")
            traceback.print_exc(limit=4)
    print(f"\n━━━ PASS {R['p']} / FAIL {R['f']} ━━━")
    return 0 if R["f"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
