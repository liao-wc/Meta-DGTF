#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 smoke_test.py 打补丁：SRC → v1.21.70；追加 6 条 check_v70_*；接入 main()。

smoke_test.py 是**纯 CRLF**，所以走同一套 CRLF 往返纪律。
每条补丁块断言出现次数 == 1。
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DST = HERE / "smoke_test.py"
BAK = HERE / "_smoke_test_v69_backup.py"

shutil.copy2(DST, BAK)
s = DST.read_bytes().decode("utf-8")
assert s.count("\r\n") == s.count("\n") == s.count("\r"), "smoke_test.py 不是纯 CRLF"
n_lines_before = s.count("\r\n")
s = s.replace("\r\n", "\n")

EDITS = []


def add(name, old, new):
    EDITS.append((name, old, new))


# ---------------------------------------------------------------- SRC
add("SRC → v1.21.70",
    'SRC = HERE / "元DGTF-V1.21.69.py"',
    'SRC = HERE / "元DGTF-V1.21.70.py"')

# ------------------------------------------------------- 6 个 check 函数
NEW_CHECKS = '''def _v70_anchor(payload):
    """[v70 公用] 用桩 LLM 走生产入口 `DGTF._re_anchor`。"""
    import json as _json

    class _Stub:
        def call(self, *a, **k):
            return _json.dumps(payload, ensure_ascii=False)

        def parse_json(self, raw):
            return _json.loads(raw)

    cfg = build_cfg(False)
    dg = mod.DGTF("0", mod.LLM(cfg), cfg)
    dg.verbose = False
    dg.llm = _Stub()
    inp = mod.Input(question="原始问题", round_role="摊开", round_no=1)
    inp.pool = mod.Pool()
    import contextlib as _cl
    import io as _io
    with _cl.redirect_stdout(_io.StringIO()):
        return dg._re_anchor(inp)


def check_v70_f_trace():
    """[v1.21.70 F] 不可判定轨迹与 B 的双口径对齐：拆出 aligned_trace。

    ★ 任务书写「加性 …… 旧断言原样成立」是**笔误** —— 结构那条的标签从
      「不可判定覆盖轨迹」变成「不可判定独立结构覆盖轨迹」，是破坏性文案
      改动。本检查把这件事**明写出来**（断言新标签在、旧标签不在），
      免得下次有人照着任务书以为它是加性。
    ★ 任务书要求断言 `aligned_first_hit == {"A 的复述": 1}` 也是笔误 ——
      键是**方面**不是 amp。并且单字方面（"A"）永远撞不上：`_kw("A")`
      是空集（单字被分词器滤掉）⇒ `_overlap_coef` 直接返回 0.0。
      样例一律用长句方面。
    """
    import inspect as _ins
    import tempfile
    bad = []

    ASPECTS = ["时间尺度结论相反且无仲裁规则",
               "档案与记忆两份留痕之差不可对撞消掉"]
    prod = {"structural_amps": ["毫不相干的一段"],
            "aligned_amps": [ASPECTS[0]], "clarity": 0.5}
    p = mod.Pool()
    for ly in (1, 2):
        p.add_undecidable(dict(prod), list(ASPECTS), layer=ly)
    ch = p.undecidable_channel

    # ---- 新键存在且同构 ----
    if not ch.get("aligned_trace"):
        bad.append("[F] aligned_trace 没建起来（B 的收尾没做）")
    elif len(ch["aligned_trace"]) != 2:
        bad.append(f"[F] aligned_trace 应 2 条（两圈各一条），"
                   f"实得 {len(ch['aligned_trace'])}")
    if ch.get("aligned_first_hit") != {ASPECTS[0]: 1}:
        bad.append(f"[F] aligned_first_hit 应为 {{方面: 1}}，"
                   f"实得 {ch.get('aligned_first_hit')!r}")
    # 只记第一次：第二圈不该再记 newly
    if ch.get("aligned_trace") and ch["aligned_trace"][-1].get("newly"):
        bad.append(f"[F] 第二圈又记了一次 newly："
                   f"{ch['aligned_trace'][-1].get('newly')!r}")
    # 负对照：独立结构那条必须**原样保留**（两圈两条），不许被"顺手删掉"
    if len(ch.get("struct_trace") or []) != 2:
        bad.append(f"[F] struct_trace 被破坏了：应仍有 2 条，实得 "
                   f"{len(ch.get('struct_trace') or [])}")
    if ch.get("aspect_first_hit") != {}:
        bad.append(f"[F] 独立结构本不该命中（structural_amps 撞不上），"
                   f"aspect_first_hit 实得 {ch.get('aspect_first_hit')!r}")

    # ---- 渲染出口：两条轨迹行必须同时在 ----
    fake = {"question": "轨迹渲染", "route": ["0", "1"],
            "keep": {"1": "all"}, "rounds": {"1": 2},
            "dispatch": {"_parallel_mode": "serial", "order": ["0", "1"],
                         "requested": ["0", "1"], "skipped": []},
            "views": {},
            "pools": {"1": {"amps": [], "threads": [], "probes": [],
                            "suspensions": [], "meta": [],
                            "sub_questions": [], "deferrals": [],
                            "escalations": [], "decidability_log": [],
                            "duel_suspensions": [],
                            "undecidable_channel": ch}},
            "llm_calls": 1, "llm_tokens": 1,
            "decidability": {"decidability": "decidable"},
            "channels": ["content"], "cost_profile": "balanced",
            "orientation": "auto", "tri_state": [0, 0]}
    with tempfile.TemporaryDirectory() as td:
        txt = mod.save_result(fake, td).read_text(
            encoding="utf-8").replace("\\r\\n", "\\n")
    if "不可判定独立结构覆盖轨迹：" not in txt:
        bad.append("[F] 独立结构轨迹行没渲染")
    if "不可判定对齐结构覆盖轨迹：" not in txt:
        bad.append("[F] 对齐结构轨迹行没渲染（有算法没出口）")
    if "不可判定覆盖轨迹" in txt.replace("不可判定独立结构覆盖轨迹", "") \\
            .replace("不可判定对齐结构覆盖轨迹", ""):
        bad.append("[F] 冒出第三种轨迹标签（渲染拆得不干净）")

    # 负对照：老 dict（没有 aligned_trace）⇒ 对齐那行必须不出现，
    #   结构那行必须照旧出现（证明是"加性"，不是"无条件渲染"）
    _old_ch = {"und_aspects": list(ASPECTS),
               "struct_trace": ch["struct_trace"],
               "aspect_first_hit": ch["aspect_first_hit"],
               "structural_amps": ["毫不相干的一段"]}
    fake2 = dict(fake)
    fake2["pools"] = {"1": dict(fake["pools"]["1"],
                                undecidable_channel=_old_ch)}
    with tempfile.TemporaryDirectory() as td:
        txt2 = mod.save_result(fake2, td).read_text(
            encoding="utf-8").replace("\\r\\n", "\\n")
    if "不可判定对齐结构覆盖轨迹" in txt2:
        bad.append("[F] 老 dict（无 aligned_trace）也打了对齐行（不是加性）")
    if "不可判定独立结构覆盖轨迹：" not in txt2:
        bad.append("[F] 老 dict 的独立结构行被打丢了（破坏性改动）")

    # ---- 接线 ----
    src = _ins.getsource(mod.Pool.add_undecidable)
    for k in ('"aligned_trace"', '"aligned_first_hit"'):
        if k not in src:
            bad.append(f"[F] add_undecidable 里没有 {k}（没接线）")
    ssrc = _ins.getsource(mod.save_result)
    if "_render_trace(uc.get(\\"aligned_trace\\")" not in ssrc:
        bad.append("[F] save_result 没渲染 aligned_trace（死数据）")

    if bad:
        for m in bad:
            print(f"  \\u2717 [v70 F] {m}")
        return False
    print("  \\u2713 [v70 F] aligned_trace / aligned_first_hit 建起来且只记首次；"
          "struct_trace 原样保留；")
    print("          两条轨迹行同时渲染，老 dict 仍只出独立那条"
          "（加性成立）；接线在")
    return True


def check_v70_k_coverage():
    """[v1.21.70 K] 覆盖率段不再只挂 all 层：研究层收尾也调一次。

    这条要**两个方向都锁**：entry=1 必须追加（新出口）、entry=all 必须
    照旧追加（不许回归）、entry=0 **不许**追加（证明是定点补出口，
    不是"所有层都无脑调一次"）。
    """
    import contextlib
    import inspect as _ins
    import io
    bad = []
    cfg = build_cfg(False)
    SENT = "SENTINEL_COVERAGE"
    orig_qc = mod.DGTF._quality_check
    mod.DGTF._quality_check = lambda self, *a, **k: []
    try:
        got = {}
        for ent in ("0", "1", "all"):
            m = mod.MetaDGTF(cfg)
            m._coverage_segment = lambda: ("\\n\\n## 七、原始问题覆盖率\\n"
                                           + SENT)
            v = mod.View(entry=ent)
            st = {"roles_hist": ["摊开", "转向"], "total_rounds": 2,
                  "round_log": [], "all_rehashed": [], "all_candidates": [],
                  "all_amps": [], "all_threads": [],
                  "all_expanded_descs": [], "all_dec_products": [],
                  "all_und_products": [], "r": 2, "rounds_n": 2,
                  "sp": mod._spiral_for(cfg, ent)}
            with contextlib.redirect_stdout(io.StringIO()):
                m._finalize_layer_common(ent, v, st)
            got[ent] = SENT in (v.manifest or "")
    finally:
        mod.DGTF._quality_check = orig_qc
    if not got["1"]:
        bad.append("[K] 研究层(entry=1)收尾后 manifest 里没有覆盖率段"
                   "（route 不含 all 时仍然没有出口）")
    if not got["all"]:
        bad.append("[K] 元层(entry=all)的旧出口被改坏了（回归）")
    if got["0"]:
        bad.append("[K] entry=0 也追加了 —— 改成了「所有层都调」，"
                   "不是定点补出口")
    # 接线：辅助函数必须被两个分支各调一次
    _fin = _ins.getsource(mod.MetaDGTF._finalize_layer_common)
    if "_append_coverage(view, " not in _fin:
        bad.append("[K] _append_coverage 没接线")
    if 'elif entry == "1":' not in _fin:
        bad.append('[K] 没有 `elif entry == "1"` 分支')
    if _fin.count("_append_coverage(view, ") < 2:
        bad.append("[K] _append_coverage 调用点少于 2 个"
                   "（两处都该追加）")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v70 K] {m}")
        return False
    print("  \\u2713 [v70 K] entry=1 与 entry=all 都追加覆盖率段"
          "（entry=0 不追加，条目是定点的）；接线在")
    return True


def check_v70_g_anchor():
    """[v1.21.70 G] 锚点重述的 _clean 加占位符黑名单（唯一还没修的真 bug）。

    两个方向都锁：占位符必须被挡、正常方面**不许**被误杀（所以只挡
    完全相等，不做子串匹配）。
    """
    import inspect as _ins
    bad = []
    _a, t1, u1 = _v70_anchor({"anchor": "x",
                              "touched": ["此处未生", "正常方面"],
                              "untouched": ["（无）", "另一个方面"]})
    if t1 != ["正常方面"]:
        bad.append(f"[G] 半角/普通占位符没挡住：touched={t1!r}")
    if u1 != ["另一个方面"]:
        bad.append(f"[G] 全角「（无）」没挡住：untouched={u1!r}")
    _a, t2, u2 = _v70_anchor({"anchor": "x",
                              "touched": ["此处未生", "（无）"],
                              "untouched": ["(此处未生)", "无", "N/A"]})
    if t2 != [] or u2 != []:
        bad.append(f"[G] 全占位符时留了残渣：touched={t2!r} untouched={u2!r}")
    # 负对照：含"无"字的正常方面不许被误杀（证明没做子串匹配）
    _a, t3, u3 = _v70_anchor({"anchor": "x",
                              "touched": ["无仲裁规则时两侧结论不可比"],
                              "untouched": ["未知量由谁定义尚未确定"]})
    if t3 != ["无仲裁规则时两侧结论不可比"]:
        bad.append(f"[G] 正常方面被误杀（做了子串匹配）：{t3!r}")
    if u3 != ["未知量由谁定义尚未确定"]:
        bad.append(f"[G] 正常方面被误杀（做了子串匹配）：{u3!r}")
    # 接线
    if "_ANCHOR_PLACEHOLDERS" not in _ins.getsource(mod.DGTF._re_anchor):
        bad.append("[G] _re_anchor 里没有 _ANCHOR_PLACEHOLDERS（没接线）")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v70 G] {m}")
        return False
    print("  \\u2713 [v70 G] 占位符（含全角/半角）全挡、全占位符不留残渣；"
          "含「无」字的正常方面不被误杀；接线在")
    return True


def check_v70_h_oversized():
    """[v1.21.70 H] rendered / manifest 只打长度，正文不落日志。

    负对照：**非**超大字段（collision / candidates）的正文必须照旧全文在，
    且字段覆盖计数不许掉（`\\u251c ` 行数 >= View 的字段数）。
    """
    import contextlib
    import dataclasses
    import inspect as _ins
    import io
    bad = []
    cfg = build_cfg(False)
    dg = mod.DGTF("0", mod.LLM(cfg), cfg)
    dg.verbose = True
    v = mod.View(entry="0")
    v.rendered = "a" * 5000
    v.manifest = "m" * 3000
    v.collision = "ing 正文" * 40
    v.candidates = [{"desc": "候选甲", "attribute": "0", "position": "0"}]
    inp = mod.Input(question="q", round_role="摊开", round_no=1)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        dg.dump_round(v, inp)
    out = buf.getvalue()
    if "rendered：str 5000 字" not in out:
        bad.append("[H] rendered 没打成长度行")
    if "manifest：str 3000 字" not in out:
        bad.append("[H] manifest 没打成长度行")
    if "a" * 50 in out:
        bad.append("[H] rendered 正文仍进了日志（超大字段没挡住）")
    if "m" * 50 in out:
        bad.append("[H] manifest 正文仍进了日志（超大字段没挡住）")
    # 负对照 1：非超大字段正文必须在
    _flat = out.replace("\\n", "").replace("   \\u2502 ", "")
    if ("ing 正文" * 40) not in _flat:
        bad.append("[H] collision 正文被打丢了（误伤）")
    if "候选甲" not in out:
        bad.append("[H] candidates 正文被打丢了（误伤）")
    # 负对照 2：字段覆盖计数不许掉
    fields = {f.name for f in dataclasses.fields(mod.View)}
    if out.count("   \\u251c ") < len(fields):
        bad.append(f"[H] 字段覆盖计数掉了：{out.count('   \\u251c ')} "
                   f"< {len(fields)}")
    if "_OVERSIZED" not in _ins.getsource(mod.dump_view_fields):
        bad.append("[H] dump_view_fields 里没有 _OVERSIZED（没接线）")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v70 H] {m}")
        return False
    print("  \\u2713 [v70 H] rendered/manifest 只留长度、正文不落日志；"
          "collision/candidates 正文照旧全文在；字段覆盖计数未掉")
    return True


def check_v70_i_note():
    """[v1.21.70 I] dump_round 顶部有「本圈留痕」说明，且在字段 dump **之前**。"""
    import contextlib
    import inspect as _ins
    import io
    bad = []
    _src = _ins.getsource(mod.DGTF.dump_round)
    if "本段是**本圈**留痕" not in _src:
        bad.append("[I] dump_round 源码里没有这句说明")
    elif _src.index("本段是**本圈**留痕") > _src.index("dump_view_fields("):
        bad.append("[I] 说明打在了字段 dump 之后（读者看到 0 项时已经误读了）")
    cfg = build_cfg(False)
    dg = mod.DGTF("0", mod.LLM(cfg), cfg)
    dg.verbose = True
    v = mod.View(entry="0")
    inp = mod.Input(question="q", round_role="摊开", round_no=1)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        dg.dump_round(v, inp)
    out = buf.getvalue()
    if "本段是**本圈**留痕" not in out:
        bad.append("[I] 说明没真打出来")
    if "roles_run" not in out:
        bad.append("[I] 说明里没点名 roles_run（不等于说明白）")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v70 I] {m}")
        return False
    print("  \\u2713 [v70 I] 「本圈留痕」说明打在字段 dump 之前，"
          "并点名跨圈回填字段")
    return True


def check_v70_j_reuse():
    """[v1.21.70 J] _merge_decidability 复用池评估算好的 _und_untraced。

    两个方向都锁：带缓存时必须**用缓存**（哪怕它与 evidence 矛盾）、
    不带缓存时必须**退回重算且不崩**。
    """
    import inspect as _ins
    bad = []
    cfg = build_cfg(False)
    mt = mod.MetaDGTF(cfg)
    ext = {"decidability": "undecidable", "decidable_aspects": [],
           "undecidable_aspects": [], "reason": "", "features": []}
    base = {"decidability": "undecidable",
            "undecidable_aspects": ["凭空说的一条"],
            "evidence": [{"aspect": "完全不相干的另一条"}]}
    _r = mt._merge_decidability(dict(base, _und_untraced=["CACHED_SENTINEL"]),
                                dict(ext))
    if _r.get("_und_untraced") != ["CACHED_SENTINEL"]:
        bad.append(f"[J] 没复用缓存（拿 evidence 重算了）："
                   f"{_r.get('_und_untraced')!r}")
    # 反方向：不带缓存 ⇒ 退回重算，值应与独立调用 _untraced_undecidable 一致
    _r2 = mt._merge_decidability(dict(base), dict(ext))
    _exp = mod._untraced_undecidable(base["undecidable_aspects"],
                                     base["evidence"])
    if _r2.get("_und_untraced") != _exp:
        bad.append(f"[J] 兜底重算的值不对：{_r2.get('_und_untraced')!r} "
                   f"≠ {_exp!r}")
    if not _exp:
        bad.append("[J] 负对照失效：样例本身就算不出无追溯条目，"
                   "这条判据没有判别力")
    if 'pool_res.get("_und_untraced")' not in _ins.getsource(
            mod.MetaDGTF._merge_decidability):
        bad.append("[J] _merge_decidability 里没读缓存键（没接线）")
    if bad:
        for m in bad:
            print(f"  \\u2717 [v70 J] {m}")
        return False
    print("  \\u2713 [v70 J] 缓存优先（与 evidence 矛盾也认缓存）、"
          "无缓存时退回重算且值正确；接线在")
    return True


'''
add("插入 6 个 check_v70_*", "def check_config_parses():",
    NEW_CHECKS + "def check_config_parses():")

# ------------------------------------------------------------- main() 接线
add("main() 接线",
    "    if not check_v69_abcde():\n        return 1\n"
    "    if not check_config_parses():",
    "    if not check_v69_abcde():\n        return 1\n"
    "    if not check_v70_f_trace():\n        return 1\n"
    "    if not check_v70_k_coverage():\n        return 1\n"
    "    if not check_v70_g_anchor():\n        return 1\n"
    "    if not check_v70_h_oversized():\n        return 1\n"
    "    if not check_v70_i_note():\n        return 1\n"
    "    if not check_v70_j_reuse():\n        return 1\n"
    "    if not check_config_parses():")

for name, old, new in EDITS:
    n = s.count(old)
    if n != 1:
        print(f"!! [{name}] 出现 {n} 次（应为 1）—— 停止")
        sys.exit(2)
    s = s.replace(old, new, 1)
    print(f"   ok [{name}] 命中 1 次")

assert s.count("\r") == 0
n_lf = s.count("\n")
assert n_lf > n_lines_before
s = s.replace("\n", "\r\n")
assert s.count("\r\n") == s.count("\n") == n_lf and s.count("\r") == n_lf
DST.write_bytes(s.encode("utf-8"))
print(f"\n写盘：{DST.name} {len(s.encode('utf-8'))} 字节 / {n_lf} 行（CRLF）")
print(f"备份：{BAK.name}")
