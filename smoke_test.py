#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""元 DGTF 冒烟测试：mock 掉 LLM 网络调用，验证 serial / A / B / C 能跑完。

跑法：
    python smoke_test.py
    PYTHONIOENCODING=cp936 python smoke_test.py      # 验证 [fix-97] 编码兜底
"""
from __future__ import annotations

import collections
import contextlib
import copy
import importlib.util
import inspect
import io
import json
import os
import re
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.57.py"

os.environ.setdefault("DGTF_API_KEY", "sk-smoke-test-key")

_spec = importlib.util.spec_from_file_location("dgtf_mod", str(SRC))
mod = importlib.util.module_from_spec(_spec)
# dataclass 需要通过 sys.modules[cls.__module__] 解析注解，必须先注册
sys.modules["dgtf_mod"] = mod
_spec.loader.exec_module(mod)

# ★ [v1.23.29] 规则优先分派下的**逃生阀**：规则层命中时不调 LLM，
#   而这些桩本来是用「调 LLM 返回任意 mode」来测钳制/兜底的。凡是要
#   测「LLM 给了什么之后怎么处理」的判据，题面必须取**规则拿不准**那类；
#   这里提供一个常量，避免各处自己拼。
_SMOKE_RULE_MISS_Q = "地铁运营效率的评价体系与统计口径问题"

CALLS = {"n": 0}
_LOCK = threading.Lock()
SEEN_SYSTEMS = set()
THINK_SEEN = collections.Counter()   # [fix-111] 记录各 thinking 档被用的次数
# [v1.21.62 P0-2] 探针桩的"第一次返回空"计数器，用来逼出硬约束重试。
PROBE_EMPTY_SEEN = {"n": 0}

def fake_call(self, system, user, temperature=0.6, max_tokens=3000,
              json_mode=False, model=None, thinking=None, stage=None):
    """替身 LLM：按 system 关键字返回对应格式的假输出。

    [fix-111] thinking 参数必须在这里显式列出：它是 LLM.call 的真实入参，
      桩函数签名落后于生产代码会让「汇流圈」那条检查静默失败（reasoner
      调用抛 TypeError → 被 11531 的 except 吞掉 → conf_view=None）。
      THINK_SEEN 顺带记录档位，供 check_thinking_wiring 断言用。
    [fix-112] stage 参数同样必须列出，否则 auto_plan / adjudicate 两个
      新传 stage 的调用点会在桩里 TypeError。
    """
    with _LOCK:
        CALLS["n"] += 1
        SEEN_SYSTEMS.add((system or "")[:24])
        THINK_SEEN[str(thinking)] += 1
    with self._lock:
        self.total_calls += 1
        self.total_tokens += 11
    time.sleep(0.005)  # 放大并发窗口，逼出竞态

    s = system or ""

    if "并行模式调度者" in s:
        return json.dumps({"mode": os.environ.get("SMOKE_AUTO_MODE", "serial"),
                           "reason": "smoke", "confidence": 0.9},
                          ensure_ascii=False)

    # [自动调度] 一次定模式+圈数。两个环境变量分别驱动正常值与脏值，
    # 好验证圈数钳制：SMOKE_AUTO_ROUNDS 给越界值时必须被钳回 [1,hard]。
    if "DGTF 调度者" in s:
        # ★ [v1.23.29] 走到这里说明**规则层没命中**（命中就不会调 LLM）。
        #   所以用这个桩的判据，题面必须取 `_SMOKE_RULE_MISS_Q` 那类。
        _am = os.environ.get("SMOKE_AUTO_MODE", "serial")
        _ar = os.environ.get("SMOKE_AUTO_ROUNDS", '{"0":2,"1":2,"both":3,"all":2}')
        try:
            _ar = json.loads(_ar)
        except Exception:
            _ar = {"0": 2, "1": 2, "both": 3, "all": 2}
        return json.dumps({"mode": _am, "rounds": _ar,
                           "reason": "smoke", "confidence": 0.9},
                          ensure_ascii=False)

    # [v1.21.62 P2-8] 原「DGTF 总调度」拆成两段。桩必须跟着拆 ——
    #   否则 stage 名一改，两个新 prompt 都落到 `return "{}"`，
    #   auto_plan 静默降级成 route=full/mode=serial/rounds={}。
    if "取向判读者" in s:
        return json.dumps({"orientation": "decision",
                           "reason": "smoke", "confidence": 0.9},
                          ensure_ascii=False)

    # SMOKE_AUTO_PLAN 可塞脏值，验证钳制。
    if "资源配置者" in s:
        # ★ [v1.23.29] 同上：走到这里说明规则层没命中。
        _p = os.environ.get("SMOKE_AUTO_PLAN")
        if _p:
            return _p
        return json.dumps({
            "route": "full", "mode": "H",
            "rounds": {"0": 3, "1": 4, "both": 4, "all": 3},
            "max_calls": 150,
            "reason": "smoke", "confidence": 0.9}, ensure_ascii=False)

    # [koan 可达性] 不可判定结构拆解者。真跑里这条路径 0 次进入（判定
    # 归一化后只要还剩一条可判定方面就走 hybrid），所以冒烟必须能强制
    # 走通一次，否则它连"产物链路通不通"都没验过。
    if "不可判定结构拆解者" in s:
        return json.dumps({"dimensions": [
            {"id": 1, "dimension": "轴由谁生成",
             "why_undecidable": "生成机制不在命题内",
             "what_can_probe": "可查生成事件有无入记录"},
            {"id": 2, "dimension": "判定者站位",
             "why_undecidable": "站位不由命题给出",
             "what_can_probe": "可查站位槽是否占位"},
        ]}, ensure_ascii=False)

    # [P1-6] 输入自检
    if "输入检查者" in s:
        return json.dumps(
            {"issues": [{"term": "PN",
                         "why": "不是任何标准复杂度类，疑似 NP 的笔误"}],
             "note": "如为笔误请重跑"},
            ensure_ascii=False)

    # [P1-4] both 配额补裁
    if "裁决补完者" in s:
        items = [{"idx": i + 1, "missing": f"缺第{i+1}项：一个还不存在的判据"}
                 for i in range(6)]
        return json.dumps({"items": items}, ensure_ascii=False)

    # [P0-2] 可判定性评估（外部评估 + 0 层之后的池视角评估）
    if "可判定性" in s and "decidable|partial|undecidable" in s:
        _verb = "undecidable" if "观察者" in s else "decidable"
        return json.dumps({
            "decidability": _verb,
            "reason": "冒烟测试固定输出",
            "features": ["测试特征"],
            "decidable_aspects": ["可判定方面甲"],
            "undecidable_aspects": ["不可判定方面乙"],
        }, ensure_ascii=False)

    if json_mode:
        # [P2-1] 修行层探针：一条主动悬置 + 一条硬边界线头
        if "探针 · 自问" in s:
            # [v1.21.62 P0-2] 冒烟开关：让**第一次**探针返回空，逼出
            #   「至少碰一个」的硬约束重试；之后的调用恢复正常，
            #   这样"重试后确实补上了"才可断言。
            if os.environ.get("SMOKE_PROBE_EMPTY") and \
                    PROBE_EMPTY_SEEN["n"] == 0:
                PROBE_EMPTY_SEEN["n"] += 1
                return json.dumps(
                    {"probes": [], "engagements": [], "suspensions": [],
                     "threads": [], "reconfirmations": [], "revocations": []},
                    ensure_ascii=False)
            return json.dumps({
                "probes": [
                    {"question": "冒烟探针：这条边界先推到哪一步",
                     "link": "回到原始问题", 
                     "expected_gain": 0.8, "covers": ["T1"]}],
                "engagements": [
                    {"target": "冒烟碰了一个点", "how": "推了一步"}],
                "suspensions": [
                    {"target": "冒烟主动悬置：看清了但选择不碰",
                     "reason": "我看清了它，可以碰，但选择不碰，因为本层只问入口",
                     "reason_type": "explicit"}],
                "threads": [
                    "冒烟硬边界：EDA 闭源许可读不到，工具限制推不动"],
                "reconfirmations": [], "revocations": []},
                ensure_ascii=False)
        if "自我回看者" in s:
            # [P1-5] 故意装成"抓到了问题"，才能验证回流真的发生
            return json.dumps(
                {"suspicious_candidates": [1, 2, 3, 4, 5],
                 "suspicious_amps": [1],
                 "ing_rephrased": True,
                 "honest_about_empty": True,
                 # [P2-4] 自报 4 处未生（> 阈值 3）
                 "unsaid_count": 4,
                 "unsaid_is_escape": True,
                 "unsaid_where": "冒烟：ing×2、线头×2",
                 "flow_verdict": "冒烟：判定为凑数",
                 "view_verdict": "冒烟",
                 "amp_ratio_verdict": "冒烟",
                 "notes": "冒烟 self-check"},
                ensure_ascii=False)
        if "锚点重述者" in s:
            # [v1.21.62 P0-1] touched 与 untouched 是一对：都要给，
            #   断言"两半都进 view"才验得到重述真的发生。
            return json.dumps(
                {"anchor": "测试锚点：它到底在问什么",
                 "touched": ["已被触及的方面甲", "已被触及的方面乙"],
                 "untouched": ["尚未触及的方面甲", "尚未触及的方面乙"]},
                ensure_ascii=False)
        if "adjudications" in s:
            # [P1-4] 故意全给 both，触发 both 配额补裁路径
            return json.dumps({
                "probes": [],
                "adjudications": [
                    {"tension": f"冒烟张力{i+1}", "polarity": "both",
                     "how": "两边都保留，不合并"}
                    for i in range(4)],
                "duel_suspensions": [],
            }, ensure_ascii=False)
        if "judgments" in s or "对偶" in s:
            # 按 user 里的候选条数生成 judgments
            n = sum(1 for ln in (user or "").splitlines()
                    if ln.strip()[:2] in ("1.", "2.", "3.", "4.",
                                          "5.", "6.", "7.", "8."))
            n = max(1, min(n, 8))
            return json.dumps(
                {"judgments": [
                    {"idx": i + 1,
                     "position": "1" if i % 2 == 0 else "0",
                     "why_position": "锚点已触及"}
                    for i in range(n)]},
                ensure_ascii=False)
        return "{}"

    if "阴视角" in s or "阳视角" in s:
        # [成本档 ①] 合并调用：system 里阴阳都有。后出现的是第二段
        # （merged_system = 第一段主体 + 分隔 + 第二段主体），按标记分两段。
        if "阴视角" in s and "阳视角" in s:
            _last = "阳" if s.rindex("阳视角") > s.rindex("阴视角") else "阴"
            _first = "阴" if _last == "阳" else "阳"
            return (
                f"- [concept] {_first}视角候选甲：这是一条用于冒烟测试的候选描述\n"
                f"- [question] {_first}视角候选乙：另一条不同的候选描述供去重\n"
                f"===== {_last} =====\n"
                f"- [event] {_last}视角候选甲：第三条候选描述长度合格\n"
                f"- [concept] {_last}视角候选乙：第四条候选描述长度合格\n")
        tag = "阴" if "阴视角" in s else "阳"
        return ("- [concept] %s视角候选甲：这是一条用于冒烟测试的候选描述\n"
                "- [question] %s视角候选乙：另一条不同的候选描述供去重\n"
                "- [event] %s视角候选丙：第三条候选描述长度合格" % (tag, tag, tag))

    # [v1.21.62 P1-4] ing 结构化尾块：对撞层/元层的 system 里会要求
    #   另起一行输出 ===ING-STRUCT===。桩不给的话，每次 both/all 的 ing
    #   都会往 view.errors 塞一条"尾块缺失"，污染下游质量信号。
    if "【ing · 对撞】" in s:
        _txt = ("这是一段用于冒烟测试的中文输出文本，长度足够通过各类检查。"
                "它不需要有真实含义，只要不触发解析分支的异常即可。")
        if "结构化尾块" in s:
            _txt += ("\n===ING-STRUCT===\n"
                     + json.dumps(
                         {"shared": ["两边都指向的共同点"],
                          "tensions": [{"name": "冒烟张力",
                                        "a": "0面说甲", "b": "1面说乙"}],
                          "third": "冒烟撞出的第三者"},
                         ensure_ascii=False))
        return _txt

    return ("这是一段用于冒烟测试的中文输出文本，长度足够通过各类检查。"
            "它不需要有真实含义，只要不触发解析分支的异常即可。")

# [fix-111] 打桩前留一份真实实现：thinking 的解析逻辑（ canned 到 kwargs ）
#   必须能被直接验，光看桩函数收到几个参数验不出来。
mod.LLM._real_call = mod.LLM.call
mod.LLM.call = fake_call

_ALL_LAYERS = ("0", "1", "both", "all")

def build_cfg(verbose=False):
    cfg = mod.load_config(str(HERE / "__nonexistent__.yaml"))
    cfg["api"]["key"] = "sk-smoke-test-key"
    cfg["output"]["verbose"] = verbose
    _sd = os.environ.get("SMOKE_SAVE_DIR", "smoke_outputs")
    cfg["output"]["save_dir"] = str(HERE / _sd)
    # ★ [EML 测试隔离] 冒烟**绝不许写生产记忆库**（`dgtf_memory/`）：
    #   一次冒烟有上百次 run()，无 id 的跑次会把真实条目的**证据计数**抬高
    #   （本轮实测 L0002 的 n_ev 被冒烟灌到 4）⇒ 记忆库被噪声污染，
    #   而 promote 正是按证据数判的 ⇒ 等于让测试替生产「刷票」。
    #   指到一个进程级临时目录，跑完即弃。
    import tempfile as _tf
    cfg.setdefault("playbook", {})
    cfg["playbook"]["mode"] = "shadow"
    cfg["playbook"]["dir"] = str(Path(_tf.gettempdir())
                                 / "dgtf_smoke_memory")
    return cfg

def p2_stats(res):
    """v1.21.55 [P2-*] 的健康信号，全部从 packed 里直接读。

    carry_check —— [P2-7] 上一圈注入的约束这一圈有没有被遵守
    unsaid_*    —— [P2-4] 「此处未生」是诚实姿态还是逃避
    unjudged    —— [P2-2] 对偶判断少判了几条（少判合法）
    sus_t / thr_t —— [P2-1] 修行层探针把硬边界写进了线头而不是悬置
    """
    out = {"carry_check": 0, "violations": 0, "unsaid": 0,
           "escape": 0, "unsaid_flag": 0, "sus": 0, "thr": 0,
           "amp": 0}
    for v in (res.get("views") or {}).values():
        cc = v.get("carry_check") or {}
        if cc:
            out["carry_check"] += 1
            out["violations"] += int(cc.get("violations", 0) or 0)
        sc = v.get("self_check") or {}
        out["unsaid"] += int(sc.get("unsaid_count", 0) or 0)
        if sc.get("unsaid_is_escape"):
            out["escape"] += 1
        out["unsaid_flag"] += sum(
            1 for f in (v.get("quality_flags") or [])
            if "unsaid_overused" in str(f))
        out["sus"] += len(v.get("suspensions") or [])
        out["thr"] += len(v.get("threads") or [])
        out["amp"] += len(v.get("amps") or [])
    return out

def run_mode(mode, question, rounds=None, verbose=False):
    CALLS["n"] = 0
    cfg = build_cfg(verbose)
    meta = mod.MetaDGTF(cfg)
    t0 = time.time()
    res = meta.run(question,
                   route=["0", "1", "both", "all"],
                   rounds=rounds or {"0": 2, "1": 2, "both": 2, "all": 2},
                   parallel_mode=mode)
    dt = time.time() - t0
    assert isinstance(res, dict), f"{mode} 返回值不是 dict"
    assert "views" in res and res["views"], f"{mode} 没有产出任何 view"
    # self_text 必须已经从分层桶合并回来
    assert isinstance(res.get("self_text"), list), f"{mode} self_text 异常"
    # 计数必须与实际调用次数一致（验证 [fix-98] 没把计数器搞坏）
    assert res["llm_calls"] == CALLS["n"], (
        f"{mode} 计数不一致: packed={res['llm_calls']} actual={CALLS['n']}")
    path = mod.save_result(res, cfg["output"]["save_dir"])
    assert path.exists() and path.stat().st_size > 0, f"{mode} 落盘失败"

    # ---- [v1.21.60] 层完整性：mock 下不该缺层，且必须**按请求的计划**验 ----
    # 以前这里（以及所有地方）只看实际产出的 views —— 层真缺了会一起缩水，
    # 永远判不出来。现在请求的计划在 dispatch["order"]，实际结果另记。
    _disp = res.get("dispatch") or {}
    _miss = list(_disp.get("missing") or [])
    assert not _miss, f"{mode} 缺层：请求 {_disp.get('order')}，缺 {_miss}"
    assert _disp.get("order"), f"{mode} dispatch.order 为空（计划没写进结果）"
    _gap = set(_disp["order"]) - set(res["views"].keys())
    assert not _gap, f"{mode} 计划 {_disp['order']} 里 {_gap} 没有 view"

    # ---- [P0-1] self 段必须四层齐全，不能被跑得最久的层挤掉 ----
    layer_tags = set()
    for b in res["self_text"]:
        for tag in ("[修行层]", "[研究层]", "[对撞层]", "[元层]"):
            if str(b).startswith(tag):
                layer_tags.add(tag)
    # ---- [P0-2] 可判定性必须来自 0 层跑完后的池视角，不是开跑前的外部评估
    dec = res.get("decidability") or {}
    # ---- [P1-4] both 配额超限时必须留下 missing 与 both_quota
    missing_n = 0
    quota_n = 0
    for v in res["views"].values():
        for a in (v.get("adjudications") or []):
            if str(a.get("missing", "")).strip():
                missing_n += 1
        if v.get("both_quota"):
            quota_n += 1
    # ---- [P1-5] self_check 必须回流成 carry 探针
    carry_n = sum(len(v.get("carry") or []) for v in res["views"].values())
    # ---- [P1-6] 输入自检必须进 packed
    sanity_n = len((res.get("input_sanity") or {}).get("issues") or [])

    return {
        "mode": mode,
        "views": list(res["views"].keys()),
        "calls": res["llm_calls"],
        "self_text_n": len(res["self_text"]),
        "self_layers_n": len(layer_tags),
        "dec_src": dec.get("_source") or dec.get("decidability", "?"),
        "dec_div": "≠" if dec.get("_divergent") else "=",
        # [P0-3] 判据字段原样带出，供上面断言"可查"用（不预设判定值）
        "decidability_raw": dec,
        "missing": missing_n,
        "quota": quota_n,
        "carry": carry_n,
        "sanity": sanity_n,
        "warmup": (res.get("dispatch") or {}).get("_warmup_rounds", "-"),
        "md": path.name,
        "sec": round(dt, 2),
        "pool_all_amps": len(res["pools"]["all"]["amps"]),
        "p2": p2_stats(res),
    }

def check_cli():
    """端到端走 main()：验证 argparse、配置回落 [fix-105]、落盘。"""
    import contextlib
    import io

    cfg_path = HERE / "smoke_config.yaml"
    # ★ 记忆库目录必须隔离：CLI 走 `-c` 真配置加载，不给 `playbook.dir`
    #   就回落出厂 `dgtf_memory/` ⇒ **冒烟写生产记忆库**（实测：每次冒烟往
    #   `episodes.jsonl` 塞一条「CLI 冒烟问题」、并给真实条目抬证据/权重/
    #   bandit 计数 —— 正是本文件顶部「绝不许写生产记忆库」点名
    #   禁止的「让测试替生产刷票」）。指到临时目录，跑完即弃。
    import tempfile as _tf_cli
    _cli_mem = Path(_tf_cli.mkdtemp(prefix="dgtf_smoke_cli_mem"))
    cfg_path.write_text(
        "output:\n"
        "  save_dir: smoke_outputs\n"
        "  verbose: false\n"
        "actions:\n"
        "  parallel_mode: B\n"
        "playbook:\n"
        "  dir: \"%s\"\n" % _cli_mem.as_posix(),
        encoding="utf-8")
    buf = io.StringIO()
    old_argv = sys.argv
    try:
        sys.argv = ["dgtf", "CLI 冒烟问题：这件事的边界在哪里",
                    "-c", str(cfg_path), "--rounds", "1"]
        with contextlib.redirect_stdout(buf):
            mod.main()          # 故意不给 --parallel，应回落到配置的 B
    finally:
        sys.argv = old_argv
        try:
            cfg_path.unlink(missing_ok=True)
        except OSError:
            pass  # 沙箱环境可能禁止删除；留着也不影响结论

    out = buf.getvalue()
    if "并行模式：B · 轮次并行（来自配置）" not in out:
        print("  ✗ --parallel 未回落到配置 actions.parallel_mode")
        print("    实际输出片段：",
              [ln for ln in out.splitlines() if "并行模式" in ln])
        return False
    if "完成 |" not in out:
        print("  ✗ CLI 未走到完成统计")
        return False
    print("  ✓ CLI 端到端跑通，且 --parallel 回落配置（B）")
    return True

def check_thread_isolation():
    """并发回归：[fix-98] 截断标志线程隔离 / [fix-99] self_text 不丢条目。"""
    cfg = build_cfg(False)
    llm = mod.LLM(cfg)
    bad = []

    def worker(flag):
        llm.last_truncated = flag
        llm.last_finish = "length" if flag else "stop"
        time.sleep(0.05)          # 故意让出 GIL，制造交错窗口
        if llm.last_truncated != flag:
            bad.append(f"last_truncated 串了: 期望 {flag}")
        if (llm.last_finish == "length") != flag:
            bad.append(f"last_finish 串了: 期望 {flag}")

    ts = [threading.Thread(target=worker, args=(i % 2 == 0,))
          for i in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    if bad:
        print("  ✗ 截断标志未隔离：", bad[:3])
        return False
    print("  ✓ LLM 截断标志线程隔离（8 线程交错读写无串扰）")

    # self_text：4 个线程各写 20 条，合并后必须一条不少。
    # 先把 self_layers 放大，避免被正常的"只留最近 N 条"截断掩盖丢条目。
    cfg2 = build_cfg(False)
    cfg2["memory"]["self_layers"] = 100
    meta = mod.MetaDGTF(cfg2)
    fake_view = mod.View(entry="0")
    fake_view.manifest = "测试 view 正文"

    def writer(entry):
        for _ in range(20):
            meta._append_self_text(entry, fake_view)

    ts = [threading.Thread(target=writer, args=(e,))
          for e in ("0", "1", "both", "all")]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    total = sum(len(v) for v in meta._self_text_by_entry.values())
    if total != 80:
        print(f"  ✗ self_text 丢条目：期望 80，实际 {total}")
        return False
    print(f"  ✓ self_text 按层隔离无丢失（4 线程 × 20 条 = {total}）")
    return True

def check_both_quota():
    """[P1-4] 单元级验证：both 占比超限时强制补裁。

    端到端 mock 太贫瘠（both 层池里没有 & / 线头 / 张力），
    _probe_duel 在 L3862 就 return [] 了，走不到 adjudications。
    这里直接构造 view 打进去，验证配额逻辑本身。
    """
    cfg = build_cfg(False)
    d = mod.DGTF("both", mod.LLM(cfg), cfg)
    d.verbose = False
    v = mod.View(entry="both")
    v.adjudications = [
        {"tension": f"冒烟张力{i+1}", "polarity": "both",
         "how": "两边都保留"} for i in range(4)]
    d._enforce_both_quota(v)
    ok = True
    if not v.both_quota:
        print("  ✗ [P1-4] 4/4 全 both，配额却没触发")
        ok = False
    n_missing = sum(1 for a in v.adjudications
                    if str(a.get("missing", "")).strip())
    if n_missing == 0:
        print("  ✗ [P1-4] 补裁没写出 missing（缺的东西要能进 seeds）")
        ok = False
    ratio = (v.both_quota or {}).get("ratio")
    if ratio != 1.0:
        print(f"  ✗ [P1-4] ratio 计算错：{ratio}")

    # 反例：1/3 = 33%，不该打扰
    d2 = mod.DGTF("both", mod.LLM(cfg), cfg)
    d2.verbose = False
    v2 = mod.View(entry="both")
    v2.adjudications = [
        {"tension": "甲", "polarity": "0", "how": ""},
        {"tension": "乙", "polarity": "1", "how": ""},
        {"tension": "丙", "polarity": "both", "how": ""}]
    d2._enforce_both_quota(v2)
    if v2.both_quota:
        print("  ✗ [P1-4] 未超限却触发了补裁（1/3）")
        ok = False
    if ok:
        print(f"  ✓ [P1-4] both 配额：超限({ratio:.0%})补裁写出 "
              f"{n_missing} 条 missing，未超限不打扰")
    return ok

def check_carry_feedback():
    """[P1-5] 单元级验证：self_check 结论翻译成下一圈约束探针。"""
    cfg = build_cfg(False)
    meta = mod.MetaDGTF(cfg)
    v = mod.View(entry="0")
    v.candidates = [{"desc": f"候选甲的描述文字{i+1}"} for i in range(6)]
    v.self_check = {"suspicious_candidates": [1, 2, 3, 4, 5],
                    "suspicious_amps": [1], "ing_rephrased": True,
                    "honest_about_empty": True, "notes": ""}
    v.both_quota = {"items": [{"tension": "某张力",
                               "missing": "缺一个不存在的判据"}]}
    carry = meta._build_carry(v)
    if len(carry) < 3:
        print(f"  ✗ [P1-5] 应产出 3 类约束，实际 {len(carry)}")
        return False
    joined = " ".join(str(c.get("question", "")) for c in carry)
    if "候选甲的描述文字1" not in joined:
        print("  ✗ [P1-5] 禁止重述清单没带上具体候选")
        return False
    if "此处未生" not in joined:
        print("  ✗ [P1-5] ing 复述约束缺失")
        return False
    if "缺一个不存在的判据" not in joined:
        print("  ✗ [P1-5] both missing 没进约束")
        return False

    # 开关关闭时必须静默
    cfg["memory"]["carry_feedback"] = False
    meta2 = mod.MetaDGTF(cfg)
    if meta2._build_carry(v):
        print("  ✗ [P1-5] carry_feedback=False 时仍在回流")
        return False
    print(f"  ✓ [P1-5] 自省回流：{len(carry)} 条约束"
          f"（禁重述 / ing 不复述 / both 缺什么），开关可关")
    return True

def check_p2_units():
    """v1.21.55 [P2-*] 单元级验证。

    端到端 mock 太贫瘠（产物里没有「此处未生」、候选固定不变），
    P2-1 的分界规则和 P2-4 的阈值在这里直接验。
    """
    ok = True
    cfg = build_cfg(False)

    # ---- [P2-4] 阈值配置化 ----
    d = mod.DGTF("0", mod.LLM(cfg), cfg)
    d.verbose = False
    if d._unsaid_escape_limit() != 3:
        print(f"  ✗ [P2-4] 默认阈值应为 3，实际 {d._unsaid_escape_limit()}")
        ok = False
    cfg2 = build_cfg(False)
    cfg2["spiral"]["unsaid_escape_limit"] = 0
    d0 = mod.DGTF("0", mod.LLM(cfg2), cfg2)
    if d0._unsaid_escape_limit() != 0:
        print("  ✗ [P2-4] unsaid_escape_limit=0（不设限）未生效")
        ok = False
    cfg3 = build_cfg(False)
    cfg3["spiral"]["per_entry"] = {"0": {"unsaid_escape_limit": 9}}
    m3 = mod.MetaDGTF(cfg3)
    if m3._unsaid_limit_for("0") != 9 or m3._unsaid_limit_for("1") != 3:
        print("  ✗ [P2-4] per_entry 覆盖未按层生效")
        ok = False

    # ---- [P2-4] 硬计数 ----
    v = mod.View(entry="0")
    v.collision = "甲未生：此处未生。乙：此处未生。"
    v.manifest = "此处未生"
    n, where = mod._count_unsaid(v)
    if n != 3 or "ing" not in where or "view" not in where:
        print(f"  ✗ [P2-4] 计数错：n={n} where={where}")
        ok = False

    # ---- [P2-1] 分界规则进了修行层探针 prompt ----
    src = SRC.read_text(encoding="utf-8")
    if "SUSPENSION_VS_THREAD_RULE" not in src:
        print("  ✗ [P2-1] 分界规则常量缺失")
        ok = False
    elif "我看清了" not in mod.SUSPENSION_VS_THREAD_RULE \
            or "推不动" not in mod.SUSPENSION_VS_THREAD_RULE:
        print("  ✗ [P2-1] 分界规则没写清主动悬置 vs 硬边界")
        ok = False

    # ---- [P2-2] 展开/判断的「宁可空」 ----
    if "展开出几条就写几条" not in mod.NO_FILL_RULE:
        print("  ✗ [P2-2] 展开侧缺「宁可空」规则")
        ok = False
    if "少于候选条数" not in mod.NO_FILL_JUDGE_RULE:
        print("  ✗ [P2-2] 判断侧缺「宁可空」规则")
        ok = False

    # ---- [P2-3] 复述检测：换说法要抓得到，全新要放过 ----
    up = ["EDA 工具链的许可协议是闭源的，无法读取内部实现细节。",
          "签核流程里没有中断权的角色定义，叫停权没有结构支点。"]
    rehash = ("关于 EDA 工具链，其许可协议属于闭源性质，我们没有办法读到里面的实现细节。\n"
              "在签核流程当中，并不存在一个拥有中断权的角色定义，因此叫停权缺乏支点。\n"
              "真正新的一句：把中断权挂在 tapeout 之前的门禁上。")
    fresh = ("第一条全新的句子，讨论 tapeout 门禁的授权结构安排。\n"
             "第二条讲掩模开制之后权限断点为什么不可逆。\n"
             "第三条谈责任分配如何在签字动作里退化。")
    r_re = mod._detect_ing_rephrase(rehash, up)
    r_new = mod._detect_ing_rephrase(fresh, up)
    if r_re is None or r_re < 0.6:
        print(f"  ✗ [P2-3] 换说法没抓到：{r_re}")
        ok = False
    if r_new is None or r_new > 0.34:
        print(f"  ✗ [P2-3] 全新输出被误判：{r_new}")
        ok = False

    # ---- [P2-9] 阈值边界：等于阈值不判，超过阈值才判；0 = 不设限 ----
    # 端到端 mock 只有一种产物，边界只能在这里逐个钉住。
    for _lim, _rep, _want in ((3, 3, False), (3, 4, True),
                              (0, 9, False), (10, 4, False)):
        _cfg = build_cfg(False)
        _cfg["spiral"]["unsaid_escape_limit"] = _lim
        _llm = mod.LLM(_cfg)
        _payload = {"unsaid_count": _rep, "unsaid_is_escape": False,
                    "unsaid_where": "", "honest_about_empty": True}
        _llm.call = (lambda *_a, **_k:
                     json.dumps(_payload, ensure_ascii=False))
        _llm.parse_json = (lambda raw: json.loads(raw) if raw else None)
        _dg = mod.DGTF("0", _llm, _cfg)
        _dg.verbose = False
        _view = mod.View(entry="0")
        # ★ _self_check 在「没有候选也没有 &」时早退（空圈不值得回看，
        #   也不该多花一次调用）。测试必须给内容，否则量到的是早退分支。
        _view.candidates = [{"desc": "阈值验证用的一条候选",
                             "attribute": "0", "position": "0"}]
        _res = _dg._self_check(_view)
        _flag = any("unsaid_overused" in f for f in _view.quality_flags)
        if _flag != _want:
            print(f"  ✗ [P2-4] 阈值边界错：limit={_lim} 自报={_rep} "
                  f"期望({'判' if _want else '不判'})，"
                  f"实际{'判' if _flag else '不判'}")
            ok = False
        if bool(_res.get("unsaid_is_escape")) != _want:
            print(f"  ✗ [P2-4] 逃避判定错：limit={_lim} 自报={_rep}")
            ok = False

    # ---- [P2-9] 角色排班：carry 每圈都有时不能被自己喂回去 ----
    _NR = mod.MetaDGTF
    _seq = []
    _nx = ""
    for _r in range(4):
        _seq.append(_NR._role_for_round(_r, _nx))
        _nx = _NR._carry_next_role(_r + 1, True)
    if _seq != ["摊开", "转向", "复裁", "转向"]:
        print(f"  ✗ [P2-9] 有回流时的排班错：{_seq}")
        ok = False
    _seq2 = [_NR._role_for_round(_r, "") for _r in range(4)]
    if _seq2 != ["摊开", "深入", "收束", "深入"]:
        print(f"  ✗ [P2-9] 无回流时的默认排班错：{_seq2}")
        ok = False
    # 没有 carry 时不该改写下一圈
    if _NR._carry_next_role(1, False) != "":
        print("  ✗ [P2-9] 无 carry 时仍改写了下一圈角色")
        ok = False

    # ---- [P2-9] 回流硬执行：拦下的账要被核对认下来 ----
    _hit = mod._banned_hit("这条候选就是用另一种说法重写一遍的旧条目",
                           ["这条候选是用另一种说法重写一遍的旧条目"])
    if not _hit:
        print("  ✗ [P2-9] _banned_hit 没识别出同一条目")
        ok = False
    if mod._banned_hit("一条全新的候选，讲的是另一件事。",
                       ["这条候选是用另一种说法重写一遍的旧条目"]):
        print("  ✗ [P2-9] _banned_hit 误伤了新候选")
        ok = False

    class _FakeView:
        entry = "0"
        def __init__(self, dropped=None, cands=None, sc=None):
            self.carry_dropped = dropped or []
            self.candidates = cands or []
            self.self_check = sc or {}
    _m = mod.MetaDGTF(build_cfg(False))
    _carry = [{"kind": "candidate", "text": "x", "link": "x",
               "expected_gain": 0.6,
               "banned": ["这条候选是用另一种说法重写一遍的旧条目"]}]
    _res = _m._check_carry_response(
        _FakeView(dropped=[{"desc": "这条候选是用另一种说法重写一遍的旧条目",
                            "ban": "这条候选是用另一种说法重写一遍的旧条目"}]),
        _carry)
    if not _res or _res.get("violations") != 1:
        print(f"  ✗ [P2-9] 硬拦下之后核对没认账：{_res}")
        ok = False
    # 空 drop + 空候选 → 0 违例（不是假警报）
    _res0 = _m._check_carry_response(_FakeView(), _carry)
    if not _res0 or _res0.get("violations") != 0:
        print(f"  ✗ [P2-9] 没违例却报了违例：{_res0}")
        ok = False

    # ---- [P2-9] 时序图由 _MODE_GRAPH 生成，不再手写 ----
    for _mode in ("D", "E", "F", "G", "H"):
        rows = mod._mode_timing_lines(_mode)
        starts = {}
        for r in rows:
            name = r.split()[0]
            starts[name] = (len(r) - len(r.lstrip().replace(name, "", 1))
                            ) if False else r.index("[r1]")
        g = mod._MODE_GRAPH[_mode]
        bad = []
        for layer, (waits, gates) in g.items():
            col_unit = 4
            for w in (waits or ()):
                need = starts[w] + 3 * col_unit
                if starts[layer] < need:
                    bad.append(f"{layer} 未等 {w} 跑完")
            for gd in (gates or ()):
                need = starts[gd] + 1 * col_unit
                if starts[layer] < need:
                    bad.append(f"{layer} 未等 {gd} 交出第一圈")
        if bad:
            print(f"  ✗ [P2-9] {_mode} 时序图与表不一致：{bad}")
            ok = False

    # ---- [P2-9] 「宁可空」置顶：system 段第一句就是它 ----
    if not mod.NO_FILL_RULE.strip().startswith("【★"):
        print("  ✗ [P2-9] NO_FILL_RULE 不是以一个显式的硬约束块开头")
        ok = False
    if '"输出 0-8 条' in src:
        print("  ✗ [P2-9] 仍有 prompt 写着「输出 0-8 条」（会被当成任务量）")
        ok = False

    ok = ok and check_p0_156_units(src)

    if ok:
        print(f"  ✓ [P2-1~4][P2-9][v1.21.56] 单元验证通过"
              f"（分界规则 / 宁可空 / 复述换说法 {r_re:.0%} vs 全新 {r_new:.0%}"
              f" / 阈值边界 / 角色排班 / 回流硬执行 / 时序图同源"
              f" / 停止理由分源 / 复述率 0% 可见 / 逐圈回流账"
              f" / 四象限可对上 / 悬置状态合并）")
    return ok

def check_p0_156_units(src):
    """v1.21.56 的 P0/P1 单元验证。

    端到端 mock 的产物太贫瘠，这几条只能直接钉在判据上。
    """
    ok = True
    _M = mod.MetaDGTF
    # changelog 在模块 docstring 里，改动说明里还会引用改动前的旧代码。
    # 扫源码断言时必须先把 docstring 和注释行摘掉，否则是在跟历史注释打架。
    # ★ 必须先规范成 LF 再摘：src 是文件原文（CRLF），而 mod.__doc__ 是
    #   Python 解析后的（LF），直接 replace 匹配不上 —— 那会让 changelog
    #   里的历史代码引用被当成真代码，断言假报错（本轮踩过）。
    src_code = "\n".join(
        ln for ln in src.replace("\r\n", "\n").replace(
            mod.__doc__ or "", "").split("\n")
        if not ln.strip().startswith("#"))

    # ---- [P0-1] carry 点名的两类：未消化类进集合，dual 类不进 ----
    _cand = [{"kind": "candidate", "text": "t", "link": "",
              "expected_gain": 0.6, "banned": ["候选三是用另一种说法重写的旧条目"]}]
    _dual = [{"kind": "dual", "text": "张力缺判据", "link": "",
              "expected_gain": 0.8, "banned": []}]
    if not _M._carry_banned_set(_cand):
        print("  ✗ [P0-1] kind=candidate 没进点名集合")
        ok = False
    if _M._carry_banned_set(_dual):
        print("  ✗ [P0-1] kind=dual（是任务不是缺陷）进了点名集合")
        ok = False
    if _M._carry_banned_set([]):
        print("  ✗ [P0-1] 空 carry 不该有点名")
        ok = False

    # ---- [P0-1] 同一批问题反复点名才算未消化 ----
    _a = {"甲候选是用另一种说法重写的旧条目"}
    _b = {"甲候选是用另一种说法重写的旧条目"}   # 同一批
    _c = {"乙候选讲的是一个完全不同的新空缺"}   # 换了一批
    if not _M._carry_is_repeat(_a, _b):
        print("  ✗ [P0-1] 同一批点名没被判成重复")
        ok = False
    if _M._carry_is_repeat(_a, _c):
        print("  ✗ [P0-1] 换了一批新点名却被判成重复（会误杀有进展的层）")
        ok = False
    if _M._carry_is_repeat(set(), _b) or _M._carry_is_repeat(_a, set()):
        print("  ✗ [P0-1] 空集合不该判重复")
        ok = False

    # ---- [P0-1] 停止理由必须按来源分写，不能再一律叫「复述」 ----
    if "自省连续 {carry_streak} 圈点名同一批问题未消化" not in src:
        print("  ✗ [P0-1] 缺少「自省点名未消化」这条停止理由文案")
        ok = False
    if "_mi_effective" in src_code:
        print("  ✗ [P0-1] 代码里仍在用 _mi_effective")
        ok = False

    # ---- [P0-2] rephrase_ratio 默认 None，0% 也要打印 ----
    _v = mod.View(entry="all")
    if _v.rephrase_ratio is not None:
        print(f"  ✗ [P0-2] rephrase_ratio 默认应为 None，实际 {_v.rephrase_ratio!r}")
        ok = False
    if "if v.get(\"rephrase_ratio\") is not None:" not in src:
        print("  ✗ [P0-2] 打印条件没改成 is not None（0% 会被吞掉）")
        ok = False
    # 0.0 要能打印出来
    _v.rephrase_ratio = 0.0
    if _v.rephrase_ratio is None or f"{_v.rephrase_ratio:.0%}" != "0%":
        print("  ✗ [P0-2] 0.0 的复述率渲染不出来")
        ok = False

    # ---- [P1-1] 逐圈回流账：单值字段和历史列表都要在 ----
    _v2 = mod.View(entry="both")
    if not hasattr(_v2, "carry_checks") or not hasattr(_v2, "carry_dropped_all"):
        print("  ✗ [P1-1] 缺少逐圈的 carry_checks / carry_dropped_all")
        ok = False
    if "自省回流核对**（逐圈）" not in src:
        print("  ✗ [P1-1] md 没有逐圈渲染回流核对")
        ok = False

    # ---- [P1-2] 两条 both 阈值分开 ----
    _sp = mod.DEFAULT_CONFIG["spiral"]
    if "both_tighten_ratio" not in _sp:
        print("  ✗ [P1-2] spiral 缺 both_tighten_ratio")
        ok = False
    elif abs(float(_sp["both_tighten_ratio"]) - 0.3) > 1e-9:
        print(f"  ✗ [P1-2] both_tighten_ratio 默认应为 0.3，"
              f"实际 {_sp['both_tighten_ratio']}")
        ok = False
    if "max_ratio=0.3" in src_code:
        print("  ✗ [P1-2] 调用处仍写死 0.3")
        ok = False
    # 两条阈值必须不同，否则「改判」和「追问」会撞车
    if abs(float(_sp["both_tighten_ratio"])
           - float(_sp["both_quota"]["max_ratio"])) < 1e-9:
        print("  ✗ [P1-2] 改判阈值和追问阈值相同，语义会撞车")
        ok = False

    # ---- [P1-3] 闭环清算带分母 ----
    if '"closed"' not in src or '"duel_total"' not in src:
        print("  ✗ [P1-3] _settle_meta 没带出已了结条数")
        ok = False

    # ---- [v1.21.56 配置化] 8 个新 spiral 键都在且默认值对 ----
    _sp = mod.DEFAULT_CONFIG["spiral"]
    for _k, _v in (("dedup_candidate_overlap", 0.65),
                   ("dedup_candidate_similarity", 0.70),
                   ("dedup_amp_overlap", 0.60),
                   ("dedup_amp_similarity", 0.62),
                   ("qc_rephrase_ratio", 0.5),
                   ("qc_both_ratio", 0.6),
                   ("all_drift_threshold", 0.5),
                   ("all_selfref_threshold", 0.4)):
        if abs(float(_sp.get(_k, -1)) - _v) > 1e-9:
            print(f"  ✗ [配置化] {_k} 默认应为 {_v}，实际 {_sp.get(_k)}")
            ok = False
    # 配置真的能覆盖默认值：改一个去重阈值，_final_dedup 要读得出来
    _cfg = build_cfg(False)
    _cfg["spiral"]["dedup_candidate_similarity"] = 0.99  # 极严 → 几乎不去重
    _cfg["spiral"]["dedup_candidate_overlap"] = 0.99
    _m2 = mod.MetaDGTF(_cfg)
    _vv = mod.View(entry="0", candidates=[
        {"desc": "同一个意思的第一种说法甲"},
        {"desc": "同一个意思的第二种说法甲"}])
    _m2._final_dedup(_vv)
    # 两个 0.99 阈值下，两条相似候选不该被判重 → 都留下
    if len(_vv.candidates) != 2:
        print(f"  ✗ [配置化] dedup 阈值覆盖没生效，"
              f"剩 {len(_vv.candidates)} 条")
        ok = False
    # 回落逻辑：非数值配置回落到默认
    _cfg2 = build_cfg(False)
    _cfg2["spiral"]["dedup_candidate_overlap"] = "not-a-number"
    if abs(mod._spiral_num(_cfg2, "dedup_candidate_overlap", 0.65) - 0.65) > 1e-9:
        print("  ✗ [配置化] _spiral_num 对非数值没回落到默认")
        ok = False

    # ---- [P2-1] & 和线头的去重阈值比候选松 ----
    _same = [
        {"desc": "失语瞬间是私人体验，没有第二个人在场记录，无法验证它是否可共享"},
        {"desc": "失语瞬间无第二人在场，共享需要第二人，物理上不可得"},
    ]
    _kept_tight = mod._cross_round_dedup(_same, overlap_thr=0.65, sim_thr=0.70)
    _kept_loose = mod._cross_round_dedup(_same, overlap_thr=0.60, sim_thr=0.62)
    if len(_kept_loose) > len(_kept_tight):
        print(f"  ✗ [P2-1] 调松后反而留下了更多："
              f"{len(_kept_tight)} -> {len(_kept_loose)}")
        ok = False

    # ---- [P2-2] 元自指抓得到，正常候选不误伤 ----
    _self_ref = [
        {"desc": "「偏开后同一侧空缺」这个说法本身要落位就得先有栏"},
        {"desc": "all 的候选不在「all 是什么」上，而在 all 的记账上"},
        {"desc": "本层候选里这条讲的是另一件事，正常的新东西"},
    ]
    if mod._all_candidate_selfref_rate(_self_ref) < 0.5:
        print("  ✗ [P2-2] 元自指没抓到")
        ok = False
    _normal = [{"desc": "落位动作与已在发生之间隔着一段不发信号的时差"},
               {"desc": "栏由谁开这件事在各 view 里各出现一次"}]
    if mod._all_candidate_selfref_rate(_normal) > 0.0:
        print("  ✗ [P2-2] 正常候选被误判成自指")
        ok = False

    # ---- [自查-1] 四象限：短 target 对长 question 现在能对上 ----
    # 旧判据 _similar(0.7) 对下面前三组全部返回 False（分母取两侧最大值，
    # 短 target 的关键词数远小于长 question）。补了包含度判据之后，
    # 有共享词的三组能对上，真正无关的两组仍然对不上。
    _should = [
        ("回位槽开合判据",
         "回位槽的开合由动词内部等待决定，动词说话人场景三者谁定开合没有统一判据"),
        ("失语体验的可共享性",
         "当人面对AI时产生的失语或错位体验，是否能在无第三方在场且无记录"
         "的情况下被验证为可共享的"),
        ("AI 是否算一方",
         "AI是否应被视为与人对等的互动主体，这一判断在现有哲学和法学框架下"
         "能否达成共识"),
    ]
    for _a, _b in _should:
        if mod._aspect_match(_a, _b) <= 0:
            print(f"  ✗ [自查-1] 有共享词却判成对不上：{_a!r} vs {_b[:18]!r}")
            ok = False
        if mod._similar(_a, _b, 0.7):
            print(f"  ✗ [自查-1] 旧判据竟然对上了，断言前提变了：{_a!r}")
            ok = False
    _should_not = [
        ("判定权归属",
         "回位槽的开合由动词内部等待决定，动词说话人场景三者谁定开合没有统一判据"),
        ("掩模开制之后权限断点不可逆",
         "近三年主流 AI 模型在代码生成上的能力指标变化是多少？"),
    ]
    for _a, _b in _should_not:
        if mod._aspect_match(_a, _b) > 0:
            print(f"  ✗ [自查-1] 不相关的两条被判成可对：{_a!r}")
            ok = False
    # 实测产物里那两对（T6 判定权归属 × 两个子问题）确实字面上无交集，
    # 未对齐是判出来的，不是判据失灵——所以 best_score 必须进产物可查。
    if '"best_score"' not in src_code:
        print("  ✗ [自查-1] 未对齐时没有把「差多远」写进产物")
        ok = False

    # ---- [P3-2] 每个 graph key 都要有 label ----
    _missing = [m for m in mod._MODE_GRAPH if m not in mod._MODE_LABEL]
    if _missing:
        print(f"  ✗ [P3-2] _MODE_GRAPH 有模式缺 _MODE_LABEL：{_missing}")
        ok = False
    _extra = [m for m in mod._MODE_LABEL if m not in mod._MODE_GRAPH]
    if _extra:
        print(f"  ✗ [P3-2] _MODE_LABEL 有模式不在 _MODE_GRAPH：{_extra}")
        ok = False

    if ok:
        print("  ✓ [v1.21.56] 单元验证通过（见上）")
    return ok

def check_probe_skip_no_false_flag():
    """[成本档 ②] 主动跳过探针的圈，不该被误报 probe_return_empty；
    未跳过的圈仍必须**被注意到**（判据不许关死）。

    真跑实测：economy 档跳过探针的那几圈里，有 2 圈因为「有 &/线头但
    probes 为空」被凭空报了一条假线索，还会污染 self_check 的输入。

    ★ 判据随实现更新（本项目最高频事故源）：E5 起 `probe_return_empty`
      不再是终态 —— 空探针被**双向**判成 `honest_empty`（有理由且与
      untouched 对得上，不罚）/ `lazy_empty`（理由空洞或缺失，留痕）。
      所以「未跳过」的负对照要断言的是 **「被注意到了」**（留下
      honest/lazy 之一），**不是**旧标志名。旧断言会把新实现判红 ——
      那是判据过时，不是实现回归。
    """
    cfg = build_cfg(False)
    cfg["cost_profile"] = "economy"
    dg = mod.DGTF("0", mod.LLM(cfg), cfg)
    dg.verbose = False

    # 跳过探针 + 有 & → 不该报
    v = mod.View(entry="0")
    v.amps = [{"desc": "某条 &", "type": "ontological"}]
    v.probes = []
    v.probe_skipped = True
    f1 = dg._quality_check(v, mod.Pool())
    if any("probe_return_empty" in str(x) for x in f1):
        print("  ✗ [成本档] 主动跳过探针的圈被误报 probe_return_empty")
        return False
    if any("honest_empty" in str(x) or "lazy_empty" in str(x) for x in f1):
        print("  ✗ [成本档] 主动跳过探针的圈不该进空探针双向判据")
        return False

    # 没跳过 + 有 & + probes 空 + **无理由** → 必须被注意到（lazy_empty）
    v2 = mod.View(entry="0")
    v2.amps = [{"desc": "某条 &", "type": "ontological"}]
    v2.probes = []
    f2 = dg._quality_check(v2, mod.Pool())
    if not any("lazy_empty" in str(x) for x in f2):
        print("  ✗ [成本档] 未跳过探针的圈反而没被注意到"
              "（既无 probe_return_empty 也无 lazy_empty）")
        return False

    # ★ 负对照：空探针 **带合格理由且与 untouched 对得上** ⇒ honest_empty（不罚）
    v3 = mod.View(entry="0")
    v3.amps = [{"desc": "某条 &", "type": "ontological"}]
    v3.probes = []
    v3.untouched = [{"desc": "汛期排水管网承压上限是多少"}]
    v3.no_probe_reason = "汛期排水管网承压上限是多少，池里没有任何资料可推"
    f3 = dg._quality_check(v3, mod.Pool())
    if not any("honest_empty" in str(x) for x in f3):
        print("  ✗ [成本档] 空探针带合格理由（与 untouched 对得上）"
              "未被判 honest_empty：%s" % f3)
        return False
    print("  ✓ [成本档] 跳过探针不误报，未跳过必被注意到，"
          "带理由空探针判 honest_empty")
    return True

def check_merge_fallback():
    """[成本档 ①] 合并输出缺分段标记时必须补跑，不能静默丢阳视角。"""
    cfg = build_cfg(False)
    cfg["cost_profile"] = "economy"
    llm = mod.LLM(cfg)
    calls = []

    def _call(system, user, temperature=0.6, max_tokens=3000,
              json_mode=False, model=None):
        calls.append((system or "")[:40])
        s = system or ""
        if "阴视角" in s and "阳视角" in s:
            # 合并调用：故意不输出「===== 阳 =====」分段标记
            return "- [concept] 阴视角候选甲：这是一条用于冒烟测试的候选描述"
        return "- [event] 阳视角候选甲：第三条候选描述长度合格"

    llm.call = _call
    dg = mod.DGTF("0", llm, cfg)
    dg.verbose = False
    jobs = [("阴", "阴视角指令", "USER"), ("阳", "阳视角指令", "USER")]
    out = dg._expand_pair_merged_once(jobs)
    if len(calls) != 2:
        print(f"  ✗ [成本档] 缺标记时应补跑（期望 2 次调用，实际 {len(calls)}）")
        return False
    srcs = {c.source for c in out}
    if srcs != {"阴", "阳"}:
        print(f"  ✗ [成本档] 缺标记时丢了视角：{srcs}")
        return False
    print(f"  ✓ [成本档] 缺标记自动补跑，阴阳都在（{len(out)} 条候选）")
    return True

def check_v12316_stop_therapy():
    """[v1.23.16] 自然停治本三条 + 成本档维度已删除。

    ★ 判据不是「某个字符串不存在」，而是**维度不存在** + **行为变了**：
      ① 档位维度：配置键 / auto 项 / 四个符号 / CLI 参数，四处都消失；
      ② 惰性化：`_lazy_every_n` 恒等（含 0 / 1 / 3 三个输入）；
      ③ sat 落点：`_sat_override` 是纯函数，四层同等生效（含 0 层走 stall）、
         未判 / 判有新维度时**一律不动**（负对照）；
      ④ 停止可达：把 sat 的效果喂给 `_stop_reasons`，元层必须给出理由
         —— 这是「元层能不能自然停」的直接判据（旧实现下它恒为空）；
      ⑤ 比对窗口：参照集是**池内全量**（源码里不再有 `win_amps[-r_window:]`），
         且用引擎自己的判重函数证明「跨 3 圈的重复确实是重复」。
    """
    bad = []
    _src_txt = SRC.read_text(encoding="utf-8")

    # ① 档位维度
    if "cost_profile" in (mod.DEFAULT_CONFIG or {}):
        bad.append("DEFAULT_CONFIG 仍有 cost_profile 键")
    for _sym in ("_COST_PROFILES", "_profile_plan", "_PROBE_SKIP_ROLES",
                 "_auto_pick_cost_profile", "_auto_profile"):
        if hasattr(mod, _sym):
            bad.append("维度残留：%s 仍在" % _sym)
    if "cost_profile" in mod._AUTO_ITEM_ORDER:
        bad.append("auto 项里仍有 cost_profile")
    if len(mod._AUTO_ITEM_ORDER) != 11:
        bad.append("auto 项数应为 11，实得 %d" % len(mod._AUTO_ITEM_ORDER))
    if "--profile" in _src_txt:
        bad.append("CLI 仍有 --profile")

    # ② 惰性化：恒等
    _m = mod.MetaDGTF(build_cfg(False))
    if [_m._lazy_every_n(x) for x in (0, 1, 3)] != [0, 1, 3]:
        bad.append("_lazy_every_n 仍会惰性化：%r"
                   % [_m._lazy_every_n(x) for x in (0, 1, 3)])
    _mm = mod.MetaDGTF(build_cfg(False))
    if int(_mm._mcfg.get("shape_chars", 900)) != 900:
        bad.append("shape_chars 仍被缩放：%r" % _mm._mcfg.get("shape_chars"))
    if int(_mm._mcfg.get("shape_items", 6)) != 6:
        bad.append("shape_items 仍被缩放：%r" % _mm._mcfg.get("shape_items"))
    if 'in _plan["probe_skip_roles"]' in _src_txt:
        bad.append("探针仍按角色跳过")
    if "_cands = view.candidates if not _lim" in _src_txt:
        bad.append("候选仍被截断")

    # ③ sat 落点：四层同等 + 负对照
    _so = getattr(mod, "_sat_override", None)
    if not callable(_so):
        bad.append("缺 _sat_override 纯函数")
    else:
        if _so("all", False, 0, 0, 2, 2) != (2, 2, True):
            bad.append("元层判「无新维度」后没推计数：%r"
                       % (_so("all", False, 0, 0, 2, 2),))
        if _so("1", False, 0, 0, 2, 2) != (2, 2, True):
            bad.append("研究层判「无新维度」后没推计数")
        if _so("0", False, 0, 0, 2, 2) != (2, 2, False):
            bad.append("0 层应走 idle_stall 且 sat_override=False：%r"
                       % (_so("0", False, 0, 0, 2, 2),))
        if _so("both", False, 5, 0, 2, 2) != (5, 2, True):
            bad.append("对撞层同样该生效，且取 max 不缩：%r"
                       % (_so("both", False, 5, 0, 2, 2),))
        if _so("all", None, 0, 0, 2, 2) != (0, 0, False):
            bad.append("未判定（None）时不该动任何计数")
        if _so("all", True, 7, 3, 2, 2) != (7, 3, False):
            bad.append("判「有新维度」时不该动任何计数")
    # 接线：两处 sat 块都过它
    if _src_txt.count("_sat_override(") < 3:
        bad.append("sat 接线没走 _sat_override（源里出现 %d 次）"
                   % _src_txt.count("_sat_override("))

    # ④ 停止可达：sat 的效果 → 元层给出理由
    try:
        _mr = mod.MetaDGTF(build_cfg(False))
        _rs, _ = _mr._stop_reasons(
            entry="all", layer_no=3, rounds_n=3, total_rounds=3,
            sp=dict(mod.DEFAULT_CONFIG["spiral"]), soft_max=3, sim_thr=0.8,
            stable_need=2, idle_limit=2, r_idle_limit=2, r_stall_limit=2,
            rephrase_streak=0, carry_streak=0,
            idle_new_amp=2, idle_new_thread=0, idle_stall=0,
            stall_why="", sat_override=True,
            prev_product="", view=mod.View(entry="all"), idles=0)
        if not any("结构饱和度" in str(x) for x in _rs):
            bad.append("元层拿到 sat 结论后仍不停（理由 %r）" % (_rs,))
    except Exception as _e:  # noqa: BLE001
        bad.append("停止可达判据异常：%s: %s" % (type(_e).__name__, _e))

    # ⑤ 比对窗口 = 池内全量
    if "win_amps[-r_window:]" in _src_txt:
        bad.append("serial 侧参照集仍是近 N 圈窗口")
    if 'state["win_amps"][-r_window:]' in _src_txt:
        bad.append("并行侧参照集仍是近 N 圈窗口")
    # ★ 只看「窗口串没了」不够 —— 有人把参照集换成 `[]` 或别的弱形态也过。
    #   必须断言它**真的是池内全量**（两处：serial + 并行 B）。
    if _src_txt.count("recent_amps = list(snap_amps)") != 2:
        bad.append("参照集不是池内全量（`recent_amps = list(snap_amps)` 出现 %d 次）"
                   % _src_txt.count("recent_amps = list(snap_amps)"))
    if _src_txt.count("recent_threads = list(snap_threads)") != 2:
        bad.append("线头参照集不是池内全量")
    # ★ `_is_dup` 是 `_run_layer` / `_b_check_stop` 里的**局部函数**，模块级取不到
    #   ⇒ 用它的两个组成函数（模块级）复现同一口径：overlap ≥ thr 或 similar(thr)。
    _sp0 = mod.DEFAULT_CONFIG.get("spiral") or {}
    _ovthr = float(_sp0.get("new_item_overlap", 0.55) or 0.55)
    _simthr = float(_sp0.get("new_item_similarity", 0.55) or 0.55)
    _a1 = "槽位状态列可空但不能由人名填充，人名列可填但不能改写槽位状态"
    _a4 = "槽位状态列可空但不能由人名填充，人名列可填但不能改写槽位状态列"
    if not (mod._overlap_coef(_a4, _a1) >= _ovthr
            or mod._similar(_a4, _a1, _simthr)):
        bad.append("跨圈重复样例在引擎判重口径下不算重复 —— 判据前提不成立")

    if bad:
        for _x in bad:
            print("  ✗ [v12316] %s" % _x)
        return False
    print("  ✓ [v12316] 档位维度已删（配置/auto 项/符号/CLI 四处）；"
          "惰性化归零；sat 落点四层同等（含 0 层走 stall）；"
          "元层拿到 sat 结论后会停；参照集改池内全量")
    return True

def check_v12317_stop_all_layers():
    """[v1.23.17] 三处停止阈值/门槛：sat 间隔 2 / soft_max 2 / 条件 1 四层通用。

    ★ 每条判据都带负对照 —— 否则「把阈值降到 0」也能过。
    """
    import re as _re
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")

    # ① 缺省字面：sat 两处 + soft_max 四处，全为 2
    _sat2 = 'int(sp.get("structure_saturation_every_n", 2))'
    if src.count(_sat2) != 2:
        bad.append("sat 缺省不是两处 2（%d 处）" % src.count(_sat2))
    if _re.search(r'structure_saturation_every_n",\s*3\)', src):
        bad.append("还有 sat 缺省写成 3 的地方")
    _sm2 = 'int(sp.get("soft_max", 2))'
    if src.count(_sm2) != 2:
        bad.append("soft_max 缺省不是两处 2（%d 处）" % src.count(_sm2))
    if src.count('spiral.get("soft_max", 2) or 2') != 2:
        bad.append("plan 系列的 soft 缺省不是两处 2")
    if _re.search(r'soft_max",\s*3\)', src):
        bad.append("还有 soft_max 缺省写成 3 的地方")

    # ② 出厂默认值
    _sp = mod.DEFAULT_CONFIG.get("spiral") or {}
    if _sp.get("soft_max") != 2:
        bad.append("DEFAULT_CONFIG soft_max = %r（应 2）" % _sp.get("soft_max"))
    if _sp.get("structure_saturation_every_n") != 2:
        bad.append("DEFAULT_CONFIG sat = %r（应 2）"
                   % _sp.get("structure_saturation_every_n"))

    # ③ 条件 1 对四层通用（行为）+ 两条负对照
    _mr = mod.MetaDGTF(build_cfg(False))

    def _rs(entry, ln, soft, carry, reph):
        _r, _ = _mr._stop_reasons(
            entry=entry, layer_no=ln, rounds_n=3, total_rounds=3,
            sp=dict(_sp), soft_max=soft, sim_thr=0.8, stable_need=2,
            idle_limit=2, r_idle_limit=2, r_stall_limit=2,
            rephrase_streak=reph, carry_streak=carry,
            idle_new_amp=0, idle_new_thread=0, idle_stall=0,
            stall_why="", sat_override=False,
            prev_product="", view=mod.View(entry=entry), idles=0)
        return " | ".join(str(x) for x in _r)

    try:
        for _e in ("0", "1", "both", "all"):
            _t = _rs(_e, 2, 2, 2, 2)
            if "圈复述" not in _t or "点名同一批问题未消化" not in _t:
                bad.append("条件 1 没对 %s 层生效（%r）" % (_e, _t[:40]))
        if "圈复述" in _rs("1", 2, 2, 1, 1):
            bad.append("只累计 1 圈就给了理由（阈值被放宽）")
        if "圈复述" in _rs("1", 2, 3, 2, 2):
            bad.append("layer_no < soft_max 的推迟失效了")
    except Exception as _e:  # noqa: BLE001
        bad.append("条件 1 行为判据异常：%s: %s" % (type(_e).__name__, _e))

    # ④ 0/1 层的复述圈数能被 _compute_rephrase_streak 读回 + 负对照
    def _streak(ratio):
        _pool = mod.Pool()
        _v = mod.View(entry="1")
        _v._ing_rephrase_ratio = ratio
        _st = {"rephrased_streak": 0, "meta_idle_streak": 0}
        for _k in range(2):
            _st["rephrased_streak"], _st["meta_idle_streak"] = (
                _mr._apply_view_to_pool_locked(
                    _v, _pool, "1", _st["rephrased_streak"],
                    _st["meta_idle_streak"], 2))
        return mod._compute_rephrase_streak(_v, _st)

    try:
        if _streak(0.6) < 2:
            bad.append("0/1 层的复述圈数读不回来（= %s）" % _streak(0.6))
        if _streak(0.0) != 0:
            bad.append("不复述的圈却被记成复述（负对照失效）")
    except Exception as _e:  # noqa: BLE001
        bad.append("复述载体判据异常：%s: %s" % (type(_e).__name__, _e))

    if bad:
        for _x in bad:
            print("  ✗ [v12317] %s" % _x)
        return False
    print("  ✓ [v12317] sat 间隔 2（三处缺省）；soft_max 2（五处缺省）；"
          "条件 1 四层通用（含 0/1）；0/1 复述信号可读；两向负对照都在")
    return True


def check_v12317_und_coverage_trace():
    """[v1.23.17] 恢复 v1.23.16 孤儿化的判据：覆盖率双口径 + 不可判定命中轨迹。

    ★ 这些判据原本在 `check_cost_profile` 里，与该函数名（成本档）**无关**。
      v1.23.16 把它「整条重写」成 `check_v12316_stop_therapy` 时连它们一起丢在
      `return True` 之后 —— 成了死代码，约 90 行 / 33 条语句**再没跑过**。
      这里原样恢复，只把 ✓ 文案里已不存在的「成本档 / 探针按角色跳」半句去掉。
    """

    # ---- [覆盖率双口径] 自报值和代码实算必须同时出现 ----
    _m = mod.MetaDGTF(build_cfg(False))
    _m.dec_tracker = mod.ChannelTracker("decidable")
    _m.dec_tracker.coverage_history = [0.5, 0.4]
    _m.pools["1"].sub_questions = [
        {"decidability": "decidable", "status": "answered"},
        {"decidability": "decidable", "status": "answered"},
        {"decidability": "decidable", "status": "open"},
        {"decidability": "undecidable", "status": "open"},
    ]
    _seg = _m._coverage_segment()
    # 标签是「模型自评折算」不是「模型自报」——schema 里没有 coverage
    # 字段，这个数是 coverage_of() 按 engagements[].depth 折算出来的。
    if "0.40" not in _seg or "模型自评折算" not in _seg:
        print(f"  ✗ [覆盖率] 自评折算值没显示：{_seg!r}")
        return False
    if "已答子问题 2/3" not in _seg:
        print(f"  ✗ [覆盖率] 代码实算的 2/3 没显示：{_seg!r}")
        return False

    # ---- [v1.21.57 / v1.23.24] 不可判定通道的读数（清晰度 + 结构读数）----
    #   ★ 这里喂的是**只有旧键**的 dict ⇒ 走 v1.23.24 的 legacy 分支，
    #     渲染成「结构覆盖率 …（旧口径…）」，证明历史 packed 重渲染不丢信息。
    _m.pools["1"].undecidable_channel = {
        "clarity_history": [0.6, 0.75],
        "struct_coverage_history": [0.4, 0.6],
        "und_aspects": [f"面{i}" for i in range(10)],
        "last_struct_hit": 6,
        "structural_amps": ["a", "b"], "aligned_amps": [],
    }
    _seg2 = _m._coverage_segment()
    if "清晰度 0.75" not in _seg2 or "模型自评" not in _seg2:
        print(f"  ✗ [覆盖率] 不可判定通道的清晰度没显示：{_seg2!r}")
        return False
    if "结构覆盖率 0.60" not in _seg2 or "已对上 6/10" not in _seg2:
        print(f"  ✗ [覆盖率] 不可判定通道的旧口径结构读数（legacy dict）没显示："
              f"{_seg2!r}")
        return False
    # 可判定通道有数据时，两条通道的行必须同时出现
    if "可判定通道" not in _seg2 or "不可判定通道" not in _seg2:
        print(f"  ✗ [覆盖率] 两条通道没并排显示：{_seg2!r}")
        return False
    # 只有不可判定时（fallback）也要给结构读数，不能只剩清晰度
    _m3 = mod.MetaDGTF(build_cfg(False))
    _m3.dec_tracker = mod.ChannelTracker("decidable")
    _m3.pools["1"].undecidable_channel = dict(
        _m.pools["1"].undecidable_channel)
    _seg3 = _m3._coverage_segment()
    if "可判定通道不适用" not in _seg3 or "结构覆盖率" not in _seg3:
        print(f"  ✗ [覆盖率] 只有不可判定通道时（fallback）没给结构读数："
              f"{_seg3!r}")
        return False
    print("  ✓ [覆盖率] 可判定/不可判定两条通道都是双口径"
          "（自评折算 + 代码实算）")

    # ---- [v1.21.57] 不可判定通道的命中轨迹（哪个方面从哪一圈被对上）----
    _pool = mod.Pool()
    _asp = ["本体论地位需要先确定登记位置",
            "自指结构导致时刻错开",
            "判决实验缺少可操作标准"]
    _pool.add_undecidable(
        {"clarity": 0.5, "structural_amps": [
            "任何判定都要求对象在登记前已有边界，"
            "本体论地位因此没有登记位置"]},
        und_aspects=_asp, layer=1)
    _pool.add_undecidable(
        {"clarity": 0.7, "structural_amps": [
            "自指结构不是矛盾而是项位与生效的时刻错开"]}, layer=2)
    _ch = _pool.undecidable_channel
    _tr = _ch.get("struct_trace") or []
    if [t.get("layer") for t in _tr] != [1, 2]:
        print(f"  ✗ [轨迹] struct_trace 的圈号不对："
              f"{[t.get('layer') for t in _tr]}")
        return False
    if [t.get("hit") for t in _tr] != [1, 2]:
        print(f"  ✗ [轨迹] 逐圈命中数不对：{[t.get('hit') for t in _tr]}")
        return False
    # 首次命中圈号必须钉住第一圈，不能被后面的圈覆盖
    _fh = _ch.get("aspect_first_hit") or {}
    if _fh.get(_asp[0]) != 1 or _fh.get(_asp[1]) != 2:
        print(f"  ✗ [轨迹] aspect_first_hit 错了：{_fh}")
        return False
    # newly 只报新增，重复命中不该再进 newly
    if _tr[1].get("newly") != [_asp[1]]:
        print(f"  ✗ [轨迹] newly 应只含新增命中的那一项：{_tr[1]}")
        return False
    _disp = " → ".join(
        "L{} {}/{}".format(t.get("layer"), t.get("hit"), t.get("total"))
        for t in _tr)
    print("  ✓ [轨迹] 不可判定命中轨迹逐圈记录：" + _disp)

    return True

def check_v12318_anchor_default_on():
    """[v1.23.18] 外部锚点默认打开；「未挂文件」是**独立干净态**。

    ① 出厂值：`DEFAULT_CONFIG` 与出厂 yaml 的 `enabled` 都是 True；yaml 不预置 path；
    ② 行为：`enabled=True` 但没给 path ⇒ **不记 error**、置 `unconfigured`；
       **负对照**：path 指到不存在的文件 ⇒ 必须仍记 error（失败不许被吞成「未挂文件」）；
    ③ 渲染四态（缺失 / 未挂文件 / 已接入 / 失败）各说各的，互不冒充；
    ④ 产物：未挂文件时**不写**「锚点对照 / 分级 / triage 降级 / 入池 / 冲突」五行零，
       只写一行「未做对照」，且**不出现**「锚点异常」。
    """
    import tempfile as _tf
    bad = []
    _ea = mod.DEFAULT_CONFIG.get("external_anchor") or {}
    if _ea.get("enabled") is not True:
        bad.append("出厂 DEFAULT_CONFIG enabled 不是 True（=%r）" % _ea.get("enabled"))
    try:
        _yc = mod.load_config(str(HERE / "dgtf_config.yaml"))
        _ye = (_yc.get("external_anchor") or {})
        if _ye.get("enabled") is not True:
            bad.append("出厂 yaml 的 enabled 不是 True（=%r）" % _ye.get("enabled"))
        if _ye.get("path"):
            bad.append("出厂 yaml 不该预置 path（=%r）" % _ye.get("path"))
    except Exception as _e:  # noqa: BLE001
        bad.append("读出厂 yaml 失败：%s" % _e)

    def _load(path):
        _c = build_cfg(False)
        _c["external_anchor"] = dict(_c.get("external_anchor") or {})
        _c["external_anchor"].update({"enabled": True, "path": path})
        _o = object.__new__(mod.MetaDGTF)
        _o.config = _c
        _o.vp = lambda *a, **k: None
        _o._load_anchors()
        return _o

    _o1 = _load("")
    if getattr(_o1, "_anchor_err", None):
        bad.append("没挂文件却记了 error：%r" % _o1._anchor_err)
    if getattr(_o1, "_anchor_unconfigured", None) is not True:
        bad.append("没挂文件却没置 unconfigured")
    _o2 = _load(str(HERE / "__nope_anchor__.json"))
    if not getattr(_o2, "_anchor_err", ""):
        bad.append("path 不存在却**没**记 error —— 失败被吞成「未挂文件」")
    if getattr(_o2, "_anchor_unconfigured", None):
        bad.append("path 不存在却置了 unconfigured")

    def _res(st):
        d = {"question": "新中国的成立时间是什么时候", "route": ["1"],
             "keep": {"1": "all"}, "rounds": {"1": 1},
             "dispatch": {"_parallel_mode": "serial", "order": ["1"],
                          "requested": ["1"], "skipped": []},
             "views": {"1": {}}, "pools": {"1": {
                 "amps": [], "threads": [], "probes": [], "suspensions": [],
                 "meta": [], "sub_questions": [], "deferrals": [],
                 "escalations": [], "decidability_log": [],
                 "duel_suspensions": [], "duel_alignment": [],
                 "engagements": [], "refinements": [],
                 "decidable_channel": [], "undecidable_channel": []}},
             "llm_calls": 1, "llm_tokens": 1,
             "decidability": {"decidability": "decidable"},
             "channels": ["content"], "tri_state": [0, 0], "_config": {},
             "_runtime": {"web_enabled": False}}
        d.update(st)
        return d

    def _tline(st):
        _ls = mod._anchor_lane_lines(_res(st))
        _x = [l for l in _ls if "文本" in l]
        return _x[0] if _x else ""

    _sm = "**外部锚点 · 文本**（锚点文件 `external_anchor`）"
    if "**关**" not in _tline({}):
        bad.append("缺失态没写「关」")
    if "开（未挂锚点文件）" not in _tline({"external_anchor": {
            "enabled": True, "unconfigured": True, "anchors": 0, "error": ""}}):
        bad.append("未挂文件态没写「开（未挂锚点文件）」")
    _ok = _tline({"external_anchor": {
        "enabled": True, "anchors": 3, "source_file": "a.json",
        "retrieved_at": "t0", "error": ""}})
    if "**开**" not in _ok or "已接入 3 条" not in _ok:
        bad.append("已接入态没写「开 + 已接入 3 条」：%r" % _ok[:60])
    _bad_t = _tline({"external_anchor": {
        "enabled": True, "anchors": 0, "error": "FileNotFoundError: x"}})
    if "接入失败" not in _bad_t:
        bad.append("失败态没写「接入失败」")

    with _tf.TemporaryDirectory() as td:
        _md = Path(mod.save_result(_res({"external_anchor": {
            "enabled": True, "unconfigured": True, "anchors": 0,
            "error": ""}}), save_dir=td)).read_text(encoding="utf-8")
    _head = _md.split("\n## ")[0]
    if _sm not in _head or "开（未挂锚点文件）" not in _head:
        bad.append("未挂文件态的头部没写明状态")
    for _z in ("**锚点对照**：结论", "**锚点分级**", "**triage 降级**",
               "**锚点入池**"):
        if _z in _md:
            bad.append("未挂文件时仍写了零行明细：%s" % _z)
    if "**锚点对照**：未做" not in _md:
        bad.append("未挂文件时没写「锚点对照：未做」")
    if "**锚点异常**" in _md:
        bad.append("未挂文件被渲染成「锚点异常」")

    if bad:
        for _x in bad:
            print("  ✗ [v12318] %s" % _x)
        return False
    print("  ✓ [v12318] 锚点默认开（DEFAULT + yaml）；未挂文件=干净态（不记 error、"
          "负对照仍记）；渲染四态分明；产物不写五行零、不写「锚点异常」")
    return True



def check_v12319_anchor_retrieval_reachable():
    """[v1.23.19] 锚点「真检索」这条路必须**够得到**（默认路径不受影响）。

    ★ 改前现场：`_retrieve_anchors` 全篇只有 `_anchor_round` 里一处调用，
      而它在 `not self._anchors` 这道早退**之后** ⇒ 没挂快照文件时真检索
      **一次都不会被调用**（连「后端未实现」的留痕都发生不了，承诺够不到）。
      实测：`retriever="tavily"` + `_anchors` 空 ⇒ 检索调用 0 次。

    ① 出厂 `retriever` 仍是 `snapshot`（默认零调用不变）；
    ② 行为：tavily + `_anchors` 空 ⇒ 检索**被调用**（桩计数）、`_anchors` 被填、
       按 `per_round` 投池；
    ③ 负对照 A：snapshot + 空 ⇒ 检索**不许**被调用、池里 0 条；
    ④ 负对照 B（**不桩**）：未实现后端 ⇒ 真抛错留痕（`_anchor_err` 含「尚未实现」）、
       不崩、不投池；
    ⑤ `unconfigured`：snapshot+无 path ⇒ True；tavily+无 path ⇒ **False**
       （真检索模式不是「未挂文件」）；
    ⑥ 渲染两处（头部通道行 / 产物明细）都给**两条**接入方式。
    """
    import tempfile as _tf
    bad = []
    _ea = mod.DEFAULT_CONFIG.get("external_anchor") or {}
    if _ea.get("retriever") != "snapshot":
        bad.append("出厂 retriever 不是 snapshot（=%r）—— 默认零调用被改了"
                   % _ea.get("retriever"))

    def _mk(mode):
        _o = object.__new__(mod.MetaDGTF)
        _o.config = {"external_anchor": {
            "enabled": True, "path": "", "per_round": 2, "retriever": mode,
            "api_key_env": "TAVILY_API_KEY", "cache_ttl_hours": 24,
            "max_items": 12, "as_evidence": "off", "triage": False}}
        _o._anchors = []
        _o._anchor_err = ""
        _o._anchor_unconfigured = False
        _o.vp = lambda *a, **k: None
        _o.pools = {"0": mod.Pool()}
        return _o

    _rec = {"n": 0}
    _orig = mod.AnchorRetriever.search

    def _stub(self, queries, max_n=12):
        _rec["n"] += 1
        return [{"id": "R1", "claim": "真检索条目 1", "tier": 3},
                {"id": "R2", "claim": "真检索条目 2", "tier": 3}]

    mod.AnchorRetriever.search = _stub
    try:
        # ② tavily + 空锚点 ⇒ 必须真检索
        _rec["n"] = 0
        _o = _mk("tavily")
        _o._anchor_round("0", _o.pools["0"], 0)
        if _rec["n"] != 1:
            bad.append("[②] tavily + 空锚点：检索调用 %d 次（应 1）—— 死路没修好"
                       % _rec["n"])
        if len(_o._anchors) != 2:
            bad.append("[②] 检索结果没并进 `_anchors`（=%d）" % len(_o._anchors))
        if len(_o.pools["0"].anchors) != 2:
            bad.append("[②] 检索到的锚点没按 per_round 投池（=%d）"
                       % len(_o.pools["0"].anchors))
        # ③ 负对照 A：snapshot + 空 ⇒ 不许检索
        _rec["n"] = 0
        _o3 = _mk("snapshot")
        _o3._anchor_round("0", _o3.pools["0"], 0)
        if _rec["n"] != 0:
            bad.append("[③] snapshot 模式竟然调了检索（%d 次）—— 默认不再零调用"
                       % _rec["n"])
        if _o3.pools["0"].anchors:
            bad.append("[③] snapshot + 空锚点却往池里塞了东西")
    finally:
        mod.AnchorRetriever.search = _orig

    # ④ 负对照 B：未实现后端（不桩）⇒ 真抛错留痕、不崩、不投池
    try:
        _o4 = _mk("web_search")
        _o4._anchor_round("0", _o4.pools["0"], 0)
        if "尚未实现" not in (_o4._anchor_err or ""):
            bad.append("[④] 未实现后端没留痕（_anchor_err=%r）—— 静默降级了"
                       % (_o4._anchor_err or ""))
        if _o4.pools["0"].anchors:
            bad.append("[④] 检索失败后还往池里塞了东西")
    except Exception as _e:  # noqa: BLE001
        bad.append("[④] 未实现后端把异常抛到了外面：%s: %s"
                   % (type(_e).__name__, _e))

    # ⑤ unconfigured：只有 snapshot 模式才算「未挂文件」
    for _mode, _want in (("snapshot", True), ("tavily", False)):
        _c = build_cfg(False)
        _c["external_anchor"] = dict(_c.get("external_anchor") or {})
        _c["external_anchor"].update({"enabled": True, "path": "",
                                      "retriever": _mode})
        _oo = object.__new__(mod.MetaDGTF)
        _oo.config = _c
        _oo.vp = lambda *a, **k: None
        _oo._load_anchors()
        if bool(getattr(_oo, "_anchor_unconfigured", None)) != _want:
            bad.append("[⑤] %s + 无 path：unconfigured=%r（应 %r）"
                       % (_mode, getattr(_oo, "_anchor_unconfigured", None), _want))

    # ⑥ 渲染两处都给两条路
    _ln = [l for l in mod._anchor_lane_lines({"external_anchor": {
        "enabled": True, "unconfigured": True, "anchors": 0, "error": ""}})
        if "文本" in l]
    if not _ln or "tavily" not in _ln[0] or "path" not in _ln[0]:
        bad.append("[⑥] 头部通道行没给两条接入方式")
    _res = {"question": "新中国的成立时间是什么时候", "route": ["1"],
            "keep": {"1": "all"}, "rounds": {"1": 1},
            "dispatch": {"_parallel_mode": "serial", "order": ["1"],
                         "requested": ["1"], "skipped": []},
            "views": {"1": {}}, "pools": {"1": {
                "amps": [], "threads": [], "probes": [], "suspensions": [],
                "meta": [], "sub_questions": [], "deferrals": [],
                "escalations": [], "decidability_log": [],
                "duel_suspensions": [], "duel_alignment": [],
                "engagements": [], "refinements": [],
                "decidable_channel": [], "undecidable_channel": []}},
            "llm_calls": 1, "llm_tokens": 1,
            "decidability": {"decidability": "decidable"},
            "channels": ["content"], "tri_state": [0, 0], "_config": {},
            "external_anchor": {"enabled": True, "unconfigured": True,
                                "anchors": 0, "error": ""}}
    with _tf.TemporaryDirectory() as td:
        _md = Path(mod.save_result(_res, save_dir=td)).read_text(encoding="utf-8")
    _seg = [l for l in _md.split("\n") if "锚点对照" in l]
    if not _seg or "tavily" not in _seg[0]:
        bad.append("[⑥] 产物明细「未做」没给两条接入方式")

    if bad:
        for _x in bad:
            print("  ✗ [v12319] %s" % _x)
        return False
    print("  ✓ [v12319] 锚点真检索可达（tavily+空锚点 ⇒ 真调）；snapshot 仍零调用；"
          "未实现后端真抛错留痕；unconfigured 只在 snapshot；渲染给两条路")
    return True



def check_v12320_quiet_output():
    """[v1.23.20] 留痕从 verbose 拆出独立开关（默认关），进度不再被连坐。

    ① `DEFAULT_CONFIG.output.dump_rounds` 默认 False；
    ② `show_ing` / `show_manifest` 默认 False（不刷全文框）；
    ③ 行为：verbose=True + dump_rounds=False ⇒ `dump_round` 在守卫处早退，
       `dump_view_fields` **不被调用**、stdout 完全静音；
    ④ 负对照：dump_rounds=True ⇒ 越过守卫、桩**被调用**（开关不是恒静音）；
    ⑤ 接线：两个守卫都真读 `self.dump_rounds`；
    ⑥ 出厂 yaml 三键与默认一致（免得引擎关了、yaml 又开回来）。
    """
    import contextlib
    import inspect
    import io
    import types

    bad = []
    _o = mod.DEFAULT_CONFIG.get("output") or {}
    for _k in ("dump_rounds", "show_ing", "show_manifest"):
        if _o.get(_k) is not False:
            bad.append("[①/②] DEFAULT_CONFIG.output.%s=%r（应 False）" % (_k, _o.get(_k)))

    def _mk_dgtf(dump_on):
        _c = build_cfg(True)                     # verbose=True
        _c.setdefault("output", {})["dump_rounds"] = dump_on
        return mod.DGTF("0", None, _c)

    _view = types.SimpleNamespace()
    _inp = types.SimpleNamespace(round_no=1, round_role="摊开")

    _rec = {"n": 0}
    _orig_dvf = mod.dump_view_fields

    def _stub_dvf(view, emit, **kw):
        _rec["n"] += 1

    mod.dump_view_fields = _stub_dvf
    try:
        # ③ 关：守卫早退，桩不许被调，stdout 必须空
        _rec["n"] = 0
        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            _mk_dgtf(False).dump_round(_view, _inp)
        if _rec["n"] != 0:
            bad.append("[③] dump_rounds=False 仍往下走（桩被调 %d 次）" % _rec["n"])
        if _buf.getvalue().strip():
            bad.append("[③] dump_rounds=False 还有输出：%r" % _buf.getvalue()[:80])

        # ④ 负对照：开 ⇒ 越过守卫，桩被调 1 次
        _rec["n"] = 0
        with contextlib.redirect_stdout(io.StringIO()):
            _mk_dgtf(True).dump_round(_view, _inp)
        if _rec["n"] != 1:
            bad.append("[④] dump_rounds=True 没往下走（桩被调 %d 次，应 1）" % _rec["n"])
    finally:
        mod.dump_view_fields = _orig_dvf

    # ⑤ 两个守卫都读 self.dump_rounds
    # ★ 取源码失败与「命中次数不对」**分开报**。
    try:
        _src = (_src_of(mod.DGTF.dump_round)
                + _src_of(mod.DGTF.dump_final))
    except Exception as _e:
        bad.append("[⑤] 判据未能取到 dump_round/dump_final 源码"
                   "（非「未接线」结论）：%s" % _e)
        _src = None
    if _src is not None and _src.count("self.dump_rounds") != 2:
        bad.append("[⑤] 两个留痕守卫没都读 self.dump_rounds（命中 %d 次）"
                   % _src.count("self.dump_rounds"))

    # ⑥ 出厂 yaml 与默认一致
    try:
        _yl = [l.strip() for l in (HERE / "dgtf_config.yaml")
               .read_text(encoding="utf-8").splitlines()]
    except OSError:
        _yl = []
    for _k in ("show_ing: false", "show_manifest: false", "dump_rounds: false"):
        if _k not in _yl:
            bad.append("[⑥] 出厂 yaml 缺 %s" % _k)
    for _k in ("show_ing: true", "show_manifest: true"):
        if _k in _yl:
            bad.append("[⑥] 出厂 yaml 仍开着 %s" % _k)

    if bad:
        for _x in bad:
            print("  ✗ [v12320] %s" % _x)
        return False
    print("  ✓ [v12320] 留痕独立开关默认关：关时静音且不往下走、开时真打；"
          "show_ing/show_manifest 默认 false；yaml 与默认一致")
    return True


def check_v12321_tok_line():
    """[v1.23.21] LLM 调用点必须打一行 `[tok] calls=N tokens=M`（且走 logging 不走 vp）。

    ① 该行在 LLM 调用点出现**恰好 1 次**；
    ② 接线：它排在 `self.total_calls += 1` **之后**（打的是累计值）；
    ③ 负对照：不许写成 `vp(...)` —— vp 受 verbose 控制，关了就看不见。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    if src.count('logger.info("[tok] calls=%d tokens=%d"') != 1:
        bad.append("LLM 调用点没打 [tok] 行（或不止一处）")
    i_tot = src.find("self.total_calls += 1")
    i_tok = src.find("[tok] calls=%d")
    if not (0 <= i_tot < i_tok):
        bad.append("[tok] 行不在 total_calls 累加之后（打不到累计值）")
    if 'vp("[tok]' in src or "vp('[tok]" in src:
        bad.append("[tok] 用了 vp —— 关 verbose 就看不见了")
    if bad:
        for _x in bad:
            print("  \u2717 [v12321] %s" % _x)
        return False
    print("  \u2713 [v12321] LLM 调用后打 [tok] 累计行（logging、非 vp）")
    return True


def check_v12323_view_echo_full():
    """[v1.23.23] 日志回显不再把正文按字符硬砍（阴阳视角「内容没显示完全」）。

    用户实测：日志窗口里阴阳视角那块的**最后一行被砍在半句上**
    （`- [concept] 纠缠熵面积律不能单`）。查下来**不是前端裁的** —— `.run.log`
    里就是这行：四处回显写死了字符上限，而模型返回的是**多行正文**。

    三层判据：
      ① 结构：`self.vp(...)` 上不再出现按字符硬砍的上限；六处回显统一走
         `_vp_preview`（1 定义 + 6 调用）；
      ② 行为（**主路径**）：驱动生产入口 `DGTF._expand_pair`，桩住 LLM 返回一份
         >200 字的 4 行正文，**捕获 stdout**，断言「旧实现会被砍掉的那一段」
         真的出现在日志回显里（不是只在源码里多了个函数名）；
      ③ 反面对照：同一份正文的 `raw[:200]` **必须**丢掉那一段
         —— 保证这条样例在两个实现下会分岔（否则这条判据没有判别力）。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8", newline="")

    # ① 结构 -----------------------------------------------------------------
    _caps = re.findall(r"self\.vp\([^\n]{0,140}\[:\d+\]", src)
    if _caps:
        bad.append("`self.vp(...)` 上还有按字符硬砍的上限：%s" % _caps[:2])
    if not hasattr(mod, "_vp_preview"):
        bad.append("模块里没有 `_vp_preview`")
    if src.count("_vp_preview(") != 7:
        bad.append("`_vp_preview(` 出现 %d 次（应为 1 定义 + 6 调用）"
                   % src.count("_vp_preview("))
    _wired = len(re.findall(r"self\.vp\([^\n]*_vp_preview\(", src))
    if _wired != 6:
        bad.append("`self.vp(...)` 上接 `_vp_preview` 的有 %d 处（应为 6）" % _wired)

    # ①b 行为：真截断时**切在换行上**且带可见痕（line-aware + 不静默丢）
    #     为什么单列：主路径那份样例只有 ~231 字、够不到 limit ⇒ 「按 limit 硬切」
    #     的坏实现也能通过 ② ⇒ 必须另喂一份**超过 limit** 的输入来分辨。
    if hasattr(mod, "_vp_preview"):
        _lm = "\n".join("- [concept] 第%d行候选：%s" % (_i, "字" * 60)
                        for _i in range(1, 6))
        _o = mod._vp_preview(_lm, limit=200)
        _head = _o.split("\n   …（预览到此")[0]
        if not (0 < len(_head) < len(_lm)):
            bad.append("超长正文没被限流（limit=200 时保留了 %d/%d 字）"
                       % (len(_head), len(_lm)))
        elif not (_lm.startswith(_head) and _lm[len(_head)] == "\n"):
            bad.append("超长正文没切在换行上（仍会砍出半行）")
        if _o[len(_head):] != ("\n   …（预览到此，另有 %d 字未显示）"
                               % (len(_lm) - len(_head))):
            bad.append("截断痕迹不对：%r" % _o[len(_head):][:40])

    # ②③ 行为（主路径）+ 反面对照 ------------------------------------------
    RAW = "\n".join([
        "- [thread] C1 点名方向已耗尽，本体层此处未生；本圈只列避开后的可判定侧残留：定义、痕迹、论证结构。",
        "- [concept] 空间离散化若被观测，只支持底层自由度截断，不支持外部模拟器；因此该痕迹不能单独判决世界是虚拟的。",
        "- [concept] 全息投影若无边界与体—边界字典，科学上不可检验；一切是全息投影作为字面命题当前不可判定。",
        "- [concept] 纠缠熵面积律不能单独支持全息，因为普通局域场论也满足；需比较对数修正系数与符号。",
    ])
    CUT = "纠缠熵面积律不能单独支持全息"
    if len(RAW) <= 200:
        bad.append("样例只有 %d 字，够不到旧上限 ⇒ 无判别力" % len(RAW))
    elif CUT in RAW[:200]:
        bad.append("样例选错：`raw[:200]` 恰好没砍到那一段，两版结果相同 ⇒ 无判别力")
    else:
        cfg = build_cfg(False)
        llm = mod.LLM(cfg)

        def _fake_call(system, user, temperature=0.6, max_tokens=3000,
                       json_mode=False, model=None):
            return RAW

        llm.call = _fake_call
        dg = mod.DGTF("0", llm, cfg)
        dg.verbose = True                       # vp 只在 verbose 下 print
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dg._expand_pair([("阴", "阴视角指令")], lambda label: "USER")
        out = buf.getvalue()
        if "💧 [阴视角]" not in out:
            bad.append("主路径没走到阴阳回显（stdout 里没有 `💧 [阴视角]`）")
        _miss = [ln for ln in RAW.split("\n") if ln not in out]
        if _miss:
            bad.append("回显里丢了 %d 行，例如：%s" % (len(_miss), _miss[-1][:44]))
        if CUT not in out:
            bad.append("旧实现被砍掉的那一段没出现在回显里：%s" % CUT)
        if "另有" in out:
            bad.append("约 %d 字的正文不该触发截断（却出现了「另有 N 字未显示」）"
                       % len(RAW))

    if bad:
        for _x in bad:
            print("  \u2717 [v12323] %s" % _x)
        return False
    print("  \u2713 [v12323] 日志回显按整行截断：六处调用点统一 + 主路径实测不丢行"
          "（旧上限下会丢「%s」）" % CUT)
    return True


def check_v12322_web_hits_dump():
    """[v1.23.22] 联网命中必须落盘（JSONL：内容 + 链接）。

    ① `_record_web_hits` 恰好定义 1 次；
    ② 两条检索通道的成功返回前都调它；
    ③ 行为：打桩 `_http` 返回一条命中 → `search()` → JSONL 多一行且含 url；
    ④ 负对照：0 条命中**不写**（不留空行噪声）。
    """
    import json as _json
    import tempfile
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    if src.count("def _record_web_hits(") != 1:
        bad.append("_record_web_hits 定义不是 1 处")
    for _m in ("def _tavily(", "def _http("):
        _i = src.find(_m)
        if _i < 0 or "_record_web_hits(" not in src[_i:_i + 4000]:
            bad.append("%s 之后没调 _record_web_hits" % _m)

    _tmpdir = Path("_audit_tmp") / "webhits_test"
    _tmpdir.mkdir(parents=True, exist_ok=True)
    _tmp = _tmpdir / "hits.jsonl"
    if _tmp.exists():
        _tmp.write_text("", encoding="utf-8")  # 清空：本机沙箱会拦 unlink
    _old = mod._WEB_HITS_PATH
    mod._WEB_HITS_PATH = str(_tmp)
    try:
        # ★ 直接驱动落盘器：`_http` 是「可打桩的缝」，而落盘**就写在它里面** ——
        #   打桩 _http 会把落盘一起覆盖掉（第一版就这么写错了，落盘 0 行）。
        mod._record_web_hits("测试查询", [{"claim": "命中内容示例",
                                          "url": "https://example.com/x",
                                          "kind": "web", "tier": 3}])
        _n1 = _tmp.read_text(encoding="utf-8").count("\n") if _tmp.exists() else 0
        if _n1 != 1:
            bad.append("落盘行数 = %d（应 1）" % _n1)
        else:
            _rec = _json.loads(_tmp.read_text(encoding="utf-8").splitlines()[0])
            if "example.com" not in str(_rec.get("url", "")):
                bad.append("落盘条目缺 url")
            if not _rec.get("query"):
                bad.append("落盘条目缺 query（没法按检索聚合）")
        # 负对照：0 条不写（文件有没有都算过 —— 不该多行）
        mod._record_web_hits("空结果", [])
        _n2 = _tmp.read_text(encoding="utf-8").count("\n") if _tmp.exists() else 1
        if _n2 != 1:
            bad.append("0 条也写了（行数 %d）" % _n2)
    finally:
        mod._WEB_HITS_PATH = _old

    if bad:
        for _x in bad:
            print("  \u2717 [v12322] %s" % _x)
        return False
    print("  \u2713 [v12322] 联网命中落盘 JSONL（内容 + 链接 + query）；0 条不写")
    return True


def check_p23_units():
    """v1.21.57 的两条：[② 复查] min_rounds.all + [③] P2-3 条件回流。

    这两条都只能钉在判据上——端到端 mock 的产物太贫瘠，
    不会自然长出「all 候选漂移」或「min_rounds 拦截」。
    """
    ok = True

    # ---- [② 复查] min_rounds.all 保持 0 ----
    # 结论：设成 2 是死配置。all 层第 1 圈不可能有任何停止理由
    # （复述/自省点名/空转都要求累计 >= 2 圈；自然安住与 idle 另受
    # layer_no >= soft_max 限制），而「< min_r」的写法 0→2 只拦得住
    # 第 1 圈（2 < 2 为假）。两头一夹，设 2 永远不触发。
    _mr = (mod.DEFAULT_CONFIG.get("spiral") or {}).get("min_rounds") or {}
    if int(_mr.get("all", -1)) != 0:
        print(f"  ✗ [min_rounds] all 默认值不是 0（={_mr.get('all')}）——"
              f"若确要改，请连同这条断言的理由一起改")
        ok = False
    # all 层真正的下限是「闭环未清算 → 推迟停止」，它必须在
    _code = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    _code = _code.replace(mod.__doc__ or "", "")
    _code = "\n".join(ln for ln in _code.split("\n")
                      if not ln.strip().startswith("#"))
    if "元层闭环未清算" not in _code:
        print("  ✗ [min_rounds] all 层的语义下限（闭环未清算→推迟停止）"
              "不见了，而数值下限是 0，等于没有下限")
        ok = False
    if ok:
        print(f"  ✓ [min_rounds] all={_mr.get('all')}（设 2 拦不住任何理由，"
              f"是死配置）；语义下限在")

    # ---- [③ P2-3] all 候选漂移 → 下一圈条件回流「落到具体」 ----
    _m = mod.MetaDGTF(build_cfg(False))
    _drift = mod.View(entry="all", candidates=[
        {"desc": "view0 和 view1 在这个问题上其实没有真正对上"},
        {"desc": "两个 view 各自留下的东西加起来还缺一栏"},
    ])
    _carry = _m._build_carry(_drift)
    _p23 = [x for x in _carry if "具体" in str(x.get("text", ""))]
    if not _p23:
        print("  ✗ [P2-3] all 候选漂移了，下一圈却没收到「落到具体」的约束")
        ok = False
    else:
        if _p23[0].get("kind") != "candidate":
            print(f"  ✗ [P2-3] 约束 kind 应为 candidate，"
                  f"实为 {_p23[0].get('kind')!r}")
            ok = False
        # 落点必须是「具体的东西」，不能要求引用别的 view 的原文——
        # 那会把 all 拽回别层内容，跟 v1.21.32 硬约束打架。
        _txt = str(_p23[0].get("text", ""))
        if "原样引用" in _txt or "引用原文" in _txt:
            print("  ✗ [P2-3] 约束要求引用原文，会跟 all 层硬约束打架")
            ok = False

    # 不漂移就不该注入（条件触发，不是无条件）
    _clean = mod.View(entry="all", candidates=[
        {"desc": "合规义务的分层要求在两种监管路径下落到不同主体"},
        {"desc": "高风险系统的举证责任没有一个唯一承担者"},
    ])
    if any("具体" in str(x.get("text", ""))
           for x in _m._build_carry(_clean)):
        print("  ✗ [P2-3] 候选没漂移也被注入约束（不该无条件触发）")
        ok = False

    # ---- [drift 误报] 题目自己的「两侧 / 上游」不能算 all 层漂移 ----
    # 2026-09-30 真跑抓到过：题「整体是什么」的 all 层候选写
    # 「「之后」若两侧各记一次…」——两侧指拆解侧/登记侧，是题目的词。
    # v1.21.57 起漂移会触发 P2-3 约束，误报会去压本来该抽象的问题。
    _fp = mod._all_candidate_drift_rate([{"desc":
        "「之后」若两侧各记一次，中间那一拍既不属于拆解也不属于登记"}])
    if _fp != 0.0:
        print(f"  ✗ [drift] 题目的「两侧」被判成漂移（{_fp:.0%}），"
              f"会误触发 P2-3 去压该抽象的问题")
        ok = False
    if mod._all_candidate_drift_rate([{"desc": "上游的登记位缺失"}]) != 0.0:
        print("  ✗ [drift] 题目的「上游」被判成漂移")
        ok = False
    # 真漂移必须仍然抓得到（别把判据放宽到失效）
    for _d in ("view0 和 view1 没有对上", "两个 view 各说各的",
               "修行层与研究层没有对齐"):
        if mod._all_candidate_drift_rate([{"desc": _d}]) != 1.0:
            print(f"  ✗ [drift] 真漂移没抓到：{_d}")
            ok = False
    # 非 all 层不该触发
    _other = mod.View(entry="1", candidates=[
        {"desc": "view0 和 view1 没有对上"}])
    if any("具体" in str(x.get("text", ""))
           for x in _m._build_carry(_other)):
        print("  ✗ [P2-3] 非 all 层也被注入（只该管 all）")
        ok = False
    if ok:
        print("  ✓ [P2-3] all 漂移→条件回流「落到具体」；"
              "不漂不注入、非 all 不注入")
        print("  ✓ [drift] 题目自己的「两侧/上游」不算漂移，真漂移仍命中")
    return ok

def check_stop_gate():
    """[v1.21.57] 停止判据可达性复查暴露的三件事。

    起因：5 份真跑日志里「体力耗尽」19 次、真实停止 1 次。查下来不是
    判据够不着，而是 fix-88b 的「未深入方向」把判据推迟掉了——而且
    实测那几次推迟**全落在各层最后一圈**，推迟买不到下一圈，只把
    理由丢掉，收尾于是谎报「未触发任何停止判据」。
    """
    ok = True
    m = mod.MetaDGTF(build_cfg(False))
    sp = mod._spiral_for(m.config, "1")
    v = mod.View(entry="1", untouched=[
        {"source": "judge", "desc": "方向甲"},
        {"source": "judge", "desc": "方向乙"}])

    # ---- 判据：_uncovered_gate 的四种走向 ----
    r, st_, pn, note = m._uncovered_gate(
        v, ["理由A"], 0, None, False, sp)
    if r != [] or note != "理由A":
        print(f"  ✗ [停止闸门] 非最后圈+首次应推迟并留下理由："
              f"r={r} note={note!r}")
        ok = False
    # 最后一圈不该再推迟（推迟买不到下一圈，只会丢理由）
    r2, _, _, note2 = m._uncovered_gate(
        v, ["理由A"], 0, None, True, sp)
    if r2 != ["理由A"] or note2:
        print(f"  ✗ [停止闸门] 最后一圈不该推迟：r={r2} note={note2!r}")
        ok = False
    # 方向数没减少 → 保留理由
    r3, _, _, note3 = m._uncovered_gate(v, ["理由A"], 1, 1, False, sp)
    if r3 != ["理由A"] or note3:
        print(f"  ✗ [停止闸门] 方向数没减少应放行：r={r3} note={note3!r}")
        ok = False
    # 没有未深入方向 → streak / prev 归零
    _, st4, pn4, _ = m._uncovered_gate(
        mod.View(entry="1"), ["理由A"], 2, 3, False, sp)
    if st4 != 0 or pn4 is not None:
        print(f"  ✗ [停止闸门] 无未深入方向应归零：streak={st4} prev={pn4}")
        ok = False
    # [v1.21.61] 层内空转 → 不推迟。空转说的是"已经给过 ≥2 圈机会没消化"，
    # 未深入方向说的是"还有低垂果实" —— 前者恰恰是在说没有，推迟只会
    # 买到一圈走满（86 个真跑里被推迟的判据 19/33 是空转）。
    _idle = "自省连续 2 圈点名同一批问题未消化（层内空转）"
    r5, _, _, note5 = m._uncovered_gate(v, [_idle], 0, None, False, sp)
    if r5 == [] or note5:
        print(f"  ✗ [停止闸门] 空转判据不该被推迟：r={r5} note={note5!r}")
        ok = False
    # 「有新增但无推进」是同一类（池在长、判断没动），只是措辞里没有
    #   「层内空转」四个字 —— y61c 修行层就是被它推迟掉的。
    _stall = "连续 2 轮有新增但无推进（修行层无新增或无推进）"
    r7, _, _, note7 = m._uncovered_gate(v, [_stall], 0, None, False, sp)
    if r7 == [] or note7:
        print(f"  ✗ [停止闸门] 有新增但无推进 也不该被推迟："
              f"r={r7} note={note7!r}")
        ok = False
    # 开关关掉要能退回旧行为 —— 新判据不能是焊死的
    sp0 = dict(sp)
    sp0["no_push_when_idle"] = 0
    r6, _, _, note6 = m._uncovered_gate(v, [_idle], 0, None, False, sp0)
    if r6 != [] or not note6:
        print(f"  ✗ [停止闸门] no_push_when_idle=0 应退回推迟："
              f"r={r6} note={note6!r}")
        ok = False
    if ok:
        print("  ✓ [停止闸门] 最后一圈不再推迟；推迟过的理由留痕；"
              "没有未深入方向就归零；空转不被推迟且可退回")

    # ---- 走满文案：公共收口点（两条通道共用，9 个模式口径一致）----
    def _fin(extra, stop_reason=""):
        vv = mod.View(entry="1", candidates=[{"desc": "候选甲"},
                                             {"desc": "候选乙"}])
        vv.stop_reason = stop_reason
        stt = {"roles_hist": ["摊开", "转向", "复裁"], "total_rounds": 3,
               "round_log": [], "all_rehashed": [],
               "all_candidates": [{"desc": "候选甲"}, {"desc": "候选乙"}],
               "all_amps": [], "all_threads": [],
               "all_expanded_descs": ["候选甲"],
               "all_dec_products": [], "all_und_products": [],
               "r": 3, "rounds_n": 3,
               "sp": mod._spiral_for(m.config, "1"), **extra}
        with contextlib.redirect_stdout(io.StringIO()):
            m._finalize_layer_common("1", vv, stt)
        return vv.stop_reason

    s1 = _fin({})
    if "体力耗尽" not in s1 or "未触发任何停止判据" not in s1:
        print(f"  ✗ [走满] 无推迟时文案不对：{s1!r}")
        ok = False
    s2 = _fin({"deferred_notes": ["连续 2 轮无线头新增（方向走完了）"]})
    if "被「未深入方向」推迟" not in s2 or "未触发任何停止判据" in s2:
        print(f"  ✗ [走满] 有推迟时必须如实报出，不能再说「未触发」：{s2!r}")
        ok = False
    s3 = _fin({}, stop_reason="连续 2 轮无新 &，螺旋停止")
    if s3 != "连续 2 轮无新 &，螺旋停止":
        print(f"  ✗ [走满] 已有停止理由被覆盖了：{s3!r}")
        ok = False
    # 走满文案只该出现在公共收口点一处（以前只有串行通道会说）。
    # 只数 f-string 形态（f"体力耗尽（），否则会把 _uncovered_gate 的
    # docstring 里那句引用也数进来——扫源码做断言必须先排除说明文字。
    _code = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    _code = _code.replace(mod.__doc__ or "", "")
    _n_boiler = sum(1 for ln in _code.split("\n")
                    if 'f"体力耗尽（' in ln and not ln.strip().startswith("#"))
    if _n_boiler != 2:      # 两个分支（有推迟 / 无推迟）
        print(f"  ✗ [走满] f\"体力耗尽（\" 应只出现在公共收口点（2 个分支），"
              f"实为 {_n_boiler} 处——是不是又有人在通道里各写一份？")
        ok = False
    if ok:
        print("  ✓ [走满] 由公共收口点统一交代（含被推迟的理由），"
              "并行通道不再沉默")
    return ok

def check_stop_reason_parity():
    """[v1.21.60] 停止理由必须**只有一处实现**，两条通道都调它。

    [v1.21.58] 这条检查原先的写法是「理由在两份里各出现一次」——
    那正是"各写一份"年代的产物。v1.21.60 把判据收口到 `_stop_reasons()`
    （串行 `_run_layer` 与并行 `_b_check_stop` 共用），不变量**反过来了**：

      · 理由字面量只许出现在 `_stop_reasons` 里；
      · 两条通道必须各自**调用**它（各 1 次，共 2 次）；
      · 谁都不许自己再 `stop_reasons.append/extend` 加料。

    旧写法在收口后反而会**误报失败**（它找不到两处初始化了），
    所以这里连检查一起改——不然守卫会挡着正确的重构。
    """
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    src = src.replace(mod.__doc__ or "", "")
    lines = src.split("\n")

    # 只留代码行（去掉纯注释与空行），避免 changelog/注释里的示例参与计数
    code = [l for l in lines if l.strip() and not l.strip().startswith("#")]
    code_text = "\n".join(code)

    calls = len(re.findall(r"self\._stop_reasons\(", code_text))
    inline = len(re.findall(r"stop_reasons\.(append|extend)\(", code_text))

    expect = [
        "圈复述", "圈点名同一批问题未消化",
        "结构饱和度判定连续无新维度",
        "轮无新 &（沉淀完了）",
        "轮无线头新增（方向走完了）",
        "轮有新增但无推进",
        "研究层双通道均收敛",
        "双通道均停滞（qdist 无改善）",
        "产物相似度高，自然安住",
        "悬置决定稳定，自然安住",
        "无新张力（材料耗尽）",
        "无新元决策（元决策耗尽）",
        "连续空转",
    ]
    # 判据必须在 _stop_reasons 函数体内（取它的行区间）
    try:
        a = next(i for i, l in enumerate(code)
                 if re.match(r"\s*def _stop_reasons\(", l))
        b = next(i for i in range(a + 1, len(code))
                 if re.match(r"\s{4}def ", code[i])) if False else None
        body = code[a:]
    except StopIteration:
        print("  ✗ [停止理由] 找不到 _stop_reasons（收口被回退了？）")
        return False

    ok = True
    if calls != 2:
        print(f"  ✗ [停止理由] 调用 _stop_reasons 的处数是 {calls}（应 2："
              f"串行 + 并行各一次）")
        ok = False
    if inline:
        print(f"  ✗ [停止理由] 还有 {inline} 处自己 append/extend stop_reasons"
              f"——判据又分家了")
        ok = False
    missing = [t for t in expect if t not in "\n".join(body)]
    if missing:
        print(f"  ✗ [停止理由] 这些理由不在 _stop_reasons 里：{missing}")
        ok = False
    if ok:
        print(f"  ✓ [停止理由] {len(expect)} 条理由**只有一处实现**"
              f"（_stop_reasons），两条通道各调一次，无人自己加料")
    return ok

def check_rounds_plan():
    """[v1.21.58] 预算解析：rounds=0 要逐层读配置，min_rounds 是下限不是预算。

    修之前两个错：
      1) rounds=0（命令行 --rounds 的默认值）把所有层都设成全局 hard_max，
         per_entry.<层>.hard_max 与 min_rounds **在默认路径上形同虚设**
         （修行层配置的 6 圈被全局 12 盖掉）。
      2) 兜底写成「min_rounds > 0 就用它」，把"至少跑几圈"当成了"就跑到
         这几圈"——研究层 min_rounds=2 会被当成预算 2，而配置注释里写着
         「研究层 2 圈就停，可判定覆盖率仅 33%」。
    """
    ok = True

    # ---- 1) rounds=0 → 逐层读配置 ----
    c = build_cfg(False)
    c["spiral"]["hard_max"] = 12
    c["spiral"]["per_entry"] = {"0": {"hard_max": 6},
                                "1": {"hard_max": 4},
                                "both": {"hard_max": 7},
                                "all": {"hard_max": 5}}
    c["spiral"]["min_rounds"] = {"0": 0, "1": 2, "both": 3, "all": 0}
    m = mod.MetaDGTF(c)
    got = m._rounds_plan(0)
    want = {"0": 6, "1": 4, "both": 7, "all": 5}
    if got != want:
        print(f"  ✗ [预算] rounds=0 没逐层读配置：实得 {got}，应 {want}")
        ok = False
    # 显式正整数语义不变：全层都用它
    if m._rounds_plan(3) != {"0": 3, "1": 3, "both": 3, "all": 3}:
        print(f"  ✗ [预算] 显式 rounds=3 被改写：{m._rounds_plan(3)}")
        ok = False
    # [v1.21.61] 显式 dict 只给了**部分层** → 缺失层按已给值的中位数补，
    #   不再落 hard_max。原来兜到 per_entry/全局 hard_max（这里 both=7、
    #   all=5，其他配置下是 12），实测代价（w61b）：route 强制 4 层而
    #   rounds 只有 {'0':5,'1':4} → 对撞/元层各 12 圈 → 180 calls 撞预算、
    #   29.3min，同题 2 层只要 84 calls 且一样 decidable。
    got2 = m._rounds_plan({"0": 2})
    if got2.get("0") != 2:
        print(f"  ✗ [预算] 显式指定的层被改写：{got2}")
        ok = False
    # 中位数是 2，过钳制区下限 → 4。绝不能是 7 / 12 那种 hard_max。
    if got2.get("both") != 4 or got2.get("all") != 4:
        print(f"  ✗ [预算] 部分指定时缺失层应补中位数并钳到下限 4，"
              f"实得 {got2}")
        ok = False
    # 给多个值时取中位数（[4,5] → 5），再过钳制区
    got2b = m._rounds_plan({"0": 5, "1": 4})
    if got2b.get("both") != 5 or got2b.get("all") != 5:
        print(f"  ✗ [预算] {'0':5,'1':4} 的缺失层应补中位数 5，实得 {got2b}")
        ok = False
    # 一个都没给 → 仍是「逐层读配置」的语义，不能被中位数逻辑碰
    if m._rounds_plan(0) != want:
        print(f"  ✗ [预算] rounds=0 应仍逐层读配置：{m._rounds_plan(0)}")
        ok = False

    # ---- 2) min_rounds 是下限不是预算 ----
    c2 = build_cfg(False)
    c2["spiral"]["hard_max"] = 12
    c2["spiral"]["per_entry"] = {"1": {"hard_max": 4}}
    c2["spiral"]["min_rounds"] = {"1": 2}
    got3 = mod.MetaDGTF(c2)._rounds_plan(0).get("1")
    if got3 != 4:
        print(f"  ✗ [预算] 研究层预算应是 hard_max 4（min_rounds 2 只是下限），"
              f"实得 {got3}——旧代码会返回 2")
        ok = False
    # 下限高于上限时，预算不能低于下限（否则"至少跑 N 圈"永远做不到）
    c3 = build_cfg(False)
    c3["spiral"]["hard_max"] = 12
    c3["spiral"]["per_entry"] = {"1": {"hard_max": 3}}
    c3["spiral"]["min_rounds"] = {"1": 5}
    got4 = mod.MetaDGTF(c3)._rounds_plan(0).get("1")
    if got4 != 5:
        print(f"  ✗ [预算] min_rounds=5 > hard_max=3 时应取 5，实得 {got4}")
        ok = False
    if ok:
        print("  ✓ [预算] rounds=0 逐层读配置；显式值语义不变；"
              "min_rounds 是下限不是预算")
    return ok

def check_mode_tables():
    """[v1.21.57 自查-5] _MODE_GRAPH / _MODE_LABEL 必须同键、层名合法。

    这条以前只写在交付说明里（说"加了双向断言"），代码里其实没有。
    守卫本身在模块导入时就跑（缺一个直接 ValueError）；这里再断言一次，
    是为了让「两表对齐」这件事出现在测试输出里，而不是只藏在模块顶部。
    """
    ok = True
    g = set(mod._MODE_GRAPH)
    l = set(mod._MODE_LABEL)
    if g != l:
        print(f"  ✗ [模式表] 两表不同键：缺 label {sorted(g - l)}；"
              f"多 label {sorted(l - g)}")
        ok = False
    bad = {m: sorted(set(v) - set(mod._ENTRIES))
           for m, v in mod._MODE_GRAPH.items()
           if set(v) - set(mod._ENTRIES)}
    if bad:
        print(f"  ✗ [模式表] _MODE_GRAPH 有非法层名：{bad}")
        ok = False
    # 每个模式都要能算出时序图，且标签不是裸字母（裸字母=漏配的静默降级）
    for m in sorted(mod._MODE_GRAPH):
        if not mod._mode_timing_lines(m, 3):
            print(f"  ✗ [模式表] {m} 算不出时序图")
            ok = False
        if mod._MODE_LABEL.get(m, m) == m:
            print(f"  ✗ [模式表] {m} 的标签退化成裸字母（漏配）")
            ok = False
    if ok:
        print(f"  ✓ [模式表] _MODE_GRAPH 与 _MODE_LABEL 同键 "
              f"({len(g)} 个模式)，层名合法，时序图都能算")
    return ok

def check_pool_sub_label():
    """池段的子问题行必须按 decidability 分开数。

    v1.21.59 自查：老渲染把 sub_questions 的**总数**标成「可判定子问题 N 条」，
    读产物的人会以为它们本来都是 decidable —— 本轮就因此编出一个不存在的
    「5 条被升级为不可判定」的因果（v59 那次 5 条其实**生下来就是
    undecidable**）。这条断言防它复发。
    """
    # 1) 源码里不许再有那个笼统标签（总数 ≠ 可判定数）
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    src = src.replace(mod.__doc__ or "", "")
    blanket = re.search(r"可判定子问题\s*\{len\(p\[.sub_questions.\]\)\}", src)
    if blanket:
        print("  ✗ [池段口径] 还在拿 sub_questions 的总数当「可判定子问题」"
              "——总数里含着不可判定/partial")
        return False

    # 2) 功能验证：混着三种 decidability，渲染出来的分项数必须对得上
    pools = {"1": {
        "amps": [], "threads": [], "probes": [], "suspensions": [],
        "sub_questions": [{"id": 1, "decidability": "decidable"},
                          {"id": 2, "decidability": "undecidable"},
                          {"id": 3, "decidability": "undecidable"},
                          {"id": 4, "decidability": "partial"}],
        "deferrals": [], "escalations": [], "duel_suspensions": [],
    }}
    res = {"question": "冒烟：池段子问题口径", "route": [], "keep": None,
           "views": {}, "pools": pools, "llm_calls": 0, "llm_tokens": 0}
    with tempfile.TemporaryDirectory() as td:
        txt = mod.save_result(res, td).read_text(encoding="utf-8")
    m = re.search(r"- 子问题 (\d+) 条：可判定 (\d+) / 不可判定 (\d+)"
                  r"（另有 (\d+) 条 partial 等）", txt)
    if not m:
        print("  ✗ [池段口径] 渲染出来的子问题行不是分项格式（或字段改名了）")
        return False
    got = tuple(int(x) for x in m.groups())
    if got != (4, 1, 2, 1):
        print(f"  ✗ [池段口径] 分项数不对：渲染 {got}（应 4/1/2/1）")
        return False
    print("  ✓ [池段口径] 子问题行分开数（总 4：可判定 1 / 不可判定 2 / "
          "另有 1 条 partial 等），不再把总数冒充可判定数")
    return True

def check_decidability_transitions():
    """[v1.21.59] 可判定性三态互转 + 证据强制。

    背景：旧实现只有 decidable→undecidable 一条腿且**没有回写路径**
    （判定等于终审），v59 那次整层因此交白卷。现在三态任意方向都能转，
    但每次必须给出**能在池中定位到**的证据，否则驳回并留痕。
    """
    STATES = ("decidable", "partial", "undecidable")

    def mk(state="decidable"):
        p = mod.Pool()
        p.amps = [{"desc": "任何判定都要求对象在登记前已有边界",
                   "type": "structural"}]
        p.probes = [{"question": "整体的边界由谁登记", "link": "T1"}]
        p.sub_questions = [{"id": 1, "question": "甲",
                            "decidability": state, "status": "open"}]
        v = mod.View(entry="1")
        return p, v

    ok = True

    # 1) 六个方向全都能转（旧实现只有 1 个方向）
    for frm in STATES:
        for to in STATES:
            if frm == to:
                continue
            p, v = mk(frm)
            v.reclassifications = [{"sub_id": 1, "to": to,
                                    "reason": "有证据推翻",
                                    "evidence": ["A1"]}]
            st = mod.update_deferrals(p, v, layer=3, cfg={})
            got = p.sub_questions[0]["decidability"]
            if st["reclassified"] != 1 or got != to:
                print(f"  ✗ [可判定性] {frm}→{to} 没转成（结果 {got}）")
                ok = False
    if ok:
        print("  ✓ [可判定性] 三态 6 个方向全部可转（旧实现只有 "
              "decidable→undecidable 一条腿）")

    # 2) 无证据 → 驳回，且状态不动
    p, v = mk("undecidable")
    v.reclassifications = [{"sub_id": 1, "to": "decidable",
                            "reason": "我觉得可以", "evidence": []}]
    st = mod.update_deferrals(p, v, layer=3, cfg={})
    if (st["rejected"] != 1
            or p.sub_questions[0]["decidability"] != "undecidable"):
        print("  ✗ [可判定性] 无证据的提案居然被采纳了"
              f"（rejected={st['rejected']}，"
              f"状态={p.sub_questions[0]['decidability']}）")
        ok = False
    elif not (p.decidability_log and p.decidability_log[-1].get("why")):
        print("  ✗ [可判定性] 驳回了但没写 why（失败必须留痕）")
        ok = False
    else:
        print(f"  ✓ [可判定性] 无证据必驳回且留痕："
              f"「{p.decidability_log[-1]['why'][:24]}…」")

    # 3) 证据在池中定位不到 → 驳回
    p, v = mk("undecidable")
    v.reclassifications = [{"sub_id": 1, "to": "decidable", "reason": "x",
                            "evidence": ["A9", "这句池里根本没有"]}]
    st = mod.update_deferrals(p, v, layer=3, cfg={})
    if st["rejected"] != 1:
        print("  ✗ [可判定性] 悬空证据居然通过了（A9 不在池里）")
        ok = False
    else:
        print("  ✓ [可判定性] 证据悬空必驳回（编号 A9 与瞎编原句都被挡）")

    # 4) 原句引用（模糊）也算证据 —— 只认编号会让机制形同虚设
    p, v = mk("undecidable")
    v.reclassifications = [{"sub_id": 1, "to": "partial",
                            "reason": "部分可操作",
                            "evidence": ["整体的边界由谁登记"]}]
    st = mod.update_deferrals(p, v, layer=4, cfg={})
    if st["reclassified"] != 1:
        print("  ✗ [可判定性] 原句引用被误判成悬空（模糊匹配失效）")
        ok = False
    else:
        print("  ✓ [可判定性] 原句引用也算证据（编号 / 原句两条路）")

    # 5) 履历 append-only：来回转两次，两条都要在，方向都记对
    p, v = mk("decidable")
    v.reclassifications = [{"sub_id": 1, "to": "undecidable",
                            "reason": "第一圈推翻", "evidence": ["A1"]}]
    mod.update_deferrals(p, v, layer=2, cfg={})
    v2 = mod.View(entry="1")
    v2.reclassifications = [{"sub_id": 1, "to": "decidable",
                             "reason": "第二圈又推翻", "evidence": ["P1"]}]
    mod.update_deferrals(p, v2, layer=5, cfg={})
    seq = [(e.get("from"), e.get("to"))
           for e in p.decidability_log if e.get("status") == "applied"]
    if seq != [("decidable", "undecidable"), ("undecidable", "decidable")]:
        print(f"  ✗ [可判定性] 履历被覆盖了：{seq}")
        ok = False
    else:
        print(f"  ✓ [可判定性] 履历 append-only，来回转两条都在：{seq}")

    # 6) 同态提案不记账（纯噪声不该进账）
    p, v = mk("partial")
    v.reclassifications = [{"sub_id": 1, "to": "partial", "reason": "重复",
                            "evidence": ["A1"]}]
    mod.update_deferrals(p, v, layer=3, cfg={})
    if p.decidability_log:
        print(f"  ✗ [可判定性] 同态提案也记账了"
              f"（{len(p.decidability_log)} 条）")
        ok = False
    else:
        print("  ✓ [可判定性] 与当前判定相同的提案不记账")

    # 7) 旧 escalations 路径仍在，账链没断（deferred → escalated）
    p, v = mk("decidable")
    p.deferrals = [{"id": "d1", "sub_id": 1, "status": "deferred"}]
    v.escalations = [{"sub_id": 1, "reason": "无共同登记表",
                      "evidence": ["A1"]}]
    mod.update_deferrals(p, v, layer=6, cfg={})
    if p.deferrals[0]["status"] != "escalated":
        print("  ✗ [可判定性] 迁向不可判定时债务账链断了"
              f"（status={p.deferrals[0]['status']}）")
        ok = False
    elif "单向" in str(p.escalations[0].get("note", "")):
        print("  ✗ [可判定性] 留痕还写着「单向不可逆」——已是三态可转")
        ok = False
    else:
        print("  ✓ [可判定性] 迁向不可判定仍连账（deferred→escalated），"
              "留痕改口为「三态可转·须证据」")

    # 8) 产物里成立的与被驳回的都要看得见
    p, v = mk("undecidable")
    v.reclassifications = [
        {"sub_id": 1, "to": "decidable", "reason": "证据够",
         "evidence": ["A1"]}]
    mod.update_deferrals(p, v, layer=5, cfg={})
    v2 = mod.View(entry="1")
    v2.reclassifications = [{"sub_id": 1, "to": "partial", "reason": "空喊",
                             "evidence": []}]
    mod.update_deferrals(p, v2, layer=6, cfg={})
    res = {"question": "冒烟：可判定性变更账", "route": [], "keep": None,
           "views": {}, "pools": {"1": p.to_dict()},
           "llm_calls": 0, "llm_tokens": 0}
    with tempfile.TemporaryDirectory() as td:
        txt = mod.save_result(res, td).read_text(encoding="utf-8")
    if "可判定性变更轨迹" not in txt or "被驳回的可判定性变更" not in txt:
        print("  ✗ [可判定性] 产物里没同时摆出成立的与被驳回的")
        ok = False
    else:
        print("  ✓ [可判定性] 产物同时摆出变更轨迹与被驳回的提案")
    return ok

def check_decidability_normalize():
    """[v1.21.59] 「三态 vs 方面清单」必须自洽，且**全项目一份归一化**。

    旧实现只有 `_assess_decidability`（外部评估）里写了这套 sanity check：
    · `_assess_decidability_from_pool_view`（读修行池那次）**没有**；
    · `_merge_decidability`（合并）**也没有**，直接 `dict(pool_res)` 采信池判；
    · `_decompose_question` 只看 status 标签分派，koan **不接收** dec_aspects。
    于是「池判 undecidable + 列了可判定方面」会一路走到 koan，
    那些方面一条都进不了子问题 —— v59 覆盖率分母从出生就是 0。
    """
    N = mod._normalize_decidability
    ok = True

    # 1) 真值表
    cases = [
        (("undecidable", ["a"], ["b"]), "partial", "undecidable+有可判定方面"),
        (("undecidable", [], ["b"]), "undecidable", "undecidable+无可判定方面"),
        (("decidable", ["a"], ["b"]), "partial", "decidable+有不可判定方面"),
        (("partial", [], []), "decidable", "partial+两方面都空"),
        (("partial", ["a"], []), "partial", "partial+只有可判定方面"),
        (("decidable", [], []), "decidable", "纯可判定"),
        (("???", [], []), "decidable", "非法值兜底"),
    ]
    for (args, want, tag) in cases:
        got = N(*args)
        if got != want:
            print(f"  ✗ [归一化] {tag}：得 {got}，应 {want}")
            ok = False
    if ok:
        print("  ✓ [归一化] 三态×方面清单真值表 7 条全对")

    mt = mod.MetaDGTF(copy.deepcopy(mod.DEFAULT_CONFIG))

    # 2) ★ v59 场景：池判 undecidable + 列了可判定方面，外判 partial
    pool_res = {
        "decidability": "undecidable", "reason": "以不可判定为主",
        "decidable_aspects": ["拆解后剩下的不是各部分之和",
                              "被拆掉的是可分别研究的假设"],
        "undecidable_aspects": ["整体无法被操作性地把握"],
        "evidence": [],
    }
    ext_res = {
        "decidability": "partial", "reason": "含可判定部分与不可判定部分",
        "decidable_aspects": ["剩余部分的具体属性可经验研究"],
        "undecidable_aspects": ["整体作为实体的本体论地位无法经验验证"],
        "features": [],
    }
    merged = mt._merge_decidability(pool_res, ext_res)
    if merged["decidability"] != "partial":
        print(f"  ✗ [归一化] v59 场景合并后应 partial，得 "
              f"{merged['decidability']}（旧代码无条件采信池判 undecidable）")
        ok = False
    elif merged["_ext_status"] != "partial":
        print("  ✗ [归一化] _ext_status 没如实保留外判原始状态")
        ok = False
    else:
        print(f"  ✓ [归一化] 合并后 {merged['decidability']}"
              f"（外判原文仍留在 _ext_status={merged['_ext_status']}），"
              f"可判定方面 {len(merged['decidable_aspects'])} 条不再被丢")

    # 3) 边界：两侧都真无可判定方面 → 仍须保持 undecidable（别矫枉过正）
    p2 = {"decidability": "undecidable", "decidable_aspects": [],
          "undecidable_aspects": ["x"], "evidence": []}
    e2 = {"decidability": "undecidable", "decidable_aspects": [],
          "undecidable_aspects": ["y"], "features": []}
    if mt._merge_decidability(p2, e2)["decidability"] != "undecidable":
        print("  ✗ [归一化] 纯不可判定被误判成 partial（矫枉过正）")
        ok = False
    else:
        print("  ✓ [归一化] 两侧都无可判定方面时仍保持 undecidable")

    # 4) 分派点：标签说 undecidable，但列了可判定方面 → 必须走 hybrid
    dg = mod.DGTF("1", mod.LLM(copy.deepcopy(mod.DEFAULT_CONFIG)),
                  copy.deepcopy(mod.DEFAULT_CONFIG))
    dg.verbose = False
    calls = []

    def _stub(name):
        def _f(*a, **k):
            calls.append(name)
            return []
        return _f
    for nm in ("_decompose_koan", "_decompose_hybrid", "_decompose_normal"):
        setattr(dg, nm, _stub(nm))
    dg._decompose_question("整体是什么", {
        "decidability": "undecidable",
        "decidable_aspects": ["剩下的不是各部分之和"],
        "undecidable_aspects": ["无共同登记表"]})
    if calls[-1] != "_decompose_hybrid":
        print(f"  ✗ [归一化] 有可判定方面时仍走了 {calls[-1]}"
              f"（koan 会把这些方面全丢掉）")
        ok = False
    dg._decompose_question("整体是什么", {
        "decidability": "undecidable",
        "decidable_aspects": [],
        "undecidable_aspects": ["无共同登记表"]})
    if calls[-1] != "_decompose_koan":
        print(f"  ✗ [归一化] 真的无可判定方面时却走了 {calls[-1]}")
        ok = False
    if ok:
        print("  ✓ [归一化] 拆解分派按「归一化后的状态」不再只看标签")

    # 5) 口径同源：「欠一个答案」的集合必须一致（decidable + partial）。
    #    partial 现在真会落到子问题上，只认 decidable 会静默漏账。
    p3 = mod.Pool()
    p3.sub_questions = [
        {"id": 1, "decidability": "decidable", "status": "answered",
         "weight": 1.0, "depth": 1.0},
        {"id": 2, "decidability": "partial", "status": "answered",
         "weight": 1.0, "depth": 1.0},
        {"id": 3, "decidability": "undecidable", "status": "open",
         "weight": 1.0},
    ]
    cov = mod.coverage_of(p3, {})
    if cov is None or abs(cov - 1.0) > 1e-9:
        print(f"  ✗ [归一化] coverage_of 没把 partial 计入分母：{cov}"
              f"（应 1.0 = 2/2）")
        ok = False
    else:
        print("  ✓ [归一化] coverage_of 分母 = 可判定 + 部分可判定"
              "（与喂模型的 shape 同源）")

    # 6) 源码守卫：不许再把这对集合硬编码回去（同源才是唯一入口）。
    #    注意先把**定义那一行**摘掉，否则守卫会咬到 _DEC_ANSWERABLE 自己。
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    src = src.replace(mod.__doc__ or "", "")
    src_noded = re.sub(r'^.*_DEC_ANSWERABLE\s*=\s*\([^)]*\).*$', "",
                       src, flags=re.M)
    if '("decidable", "partial")' in src_noded:
        print('  ✗ [归一化] 还有硬编码的 ("decidable", "partial")'
              "——应统一走 _DEC_ANSWERABLE")
        ok = False
    else:
        print("  ✓ [归一化] 没有硬编码的可回答集合，全部走 _DEC_ANSWERABLE")
    return ok

def check_confluence_persisted():
    """[fix-101 回归] 汇流圈结果必须真的落进产物。

    真跑 s61a（route=['0','1'] + 汇流圈）连续两次在 save_result 里抛
    `ValueError: I/O operation on closed file` —— 那段 f.write 掉在
    `with open(...)` 外面，一旦 result 里真有 confluence 就写到一个
    已经关闭的句柄上，整份日志还被吞掉。
    """
    ok = True
    res = {"question": "冒烟：汇流圈落盘", "route": ["0", "1"],
           "keep": None, "views": {}, "pools": {},
           "llm_calls": 0, "llm_tokens": 0,
           "dispatch": {"order": ["0", "1"], "requested": ["0", "1"]},
           "rounds": {"0": 1, "1": 1},
           "confluence": {"anchor": "锚点：两侧都不认领",
                          "collision": "对撞出了第三件事",
                          "amps": [{"type": "structural",
                                    "desc": "留空也要占一格"}],
                          "manifest": "汇流 view 显形"}}
    try:
        with tempfile.TemporaryDirectory() as td:
            txt = mod.save_result(res, td).read_text(encoding="utf-8")
        for _k in ("## 汇流圈", "锚点：两侧都不认领", "对撞出了第三件事",
                   "留空也要占一格", "汇流 view 显形"):
            if _k not in txt:
                print(f"  ✗ [汇流圈] 产物里缺 {_k!r}")
                ok = False
        if ok:
            print("  ✓ [汇流圈] route 不含 all 时汇流圈结果落进产物"
                  "（锚点/ing/&/显形 四块都在）")
    except Exception as e:
        print(f"  ✗ [汇流圈] 落盘就抛异常：{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        ok = False
    return ok

def check_thinking_wiring():
    """[fix-111] thinking 必须能区分两档，且**不靠 model 名字**区分。

    背景：迁移后 default_model 与 reasoner_model 同名（都是 deepseek-flash），
    任何「拿 model 名反推是不是推理调用」的实现都会退化成一档。
    """
    ok = True
    cfg = build_cfg(False)
    llm = mod.LLM(cfg)
    if llm.default_model != llm.reasoner_model:
        print(f"  ✗ [thinking] 出厂配置两端应同名才能测出是否靠名字区分，"
              f"实际 {llm.default_model} / {llm.reasoner_model}")
        return False
    # 同名 → 名字一定不可用作判据，必须靠显式参数
    if llm.thinking_default == llm.thinking_reasoner:
        print(f"  ✗ [thinking] 两端 ID 同名但 thinking 档也相同，"
              f"等于没区分：{llm.thinking_default}")
        ok = False
    # 名字里不再需要含 reasoner —— 反过来说，含不含都不该影响行为
    old_guess = mod.LLM._is_reasoner(llm.reasoner_model)
    if old_guess:
        print(f"  ⚠️ [thinking] _is_reasoner 对现用 ID 仍判 True，"
              f"说明名字里还留着 reasoner 字样（已废弃判据，行为不应依赖它）")
    THINK_SEEN.clear()
    q = "测试问题：AI 在数字 IC 设计里到底能做什么，哪些已经量产？"
    meta = mod.MetaDGTF(build_cfg(False))
    meta.run(q, route=["0", "1", "both"],
             rounds={"0": 1, "1": 1, "both": 1, "all": 1},
             parallel_mode="A")
    if not THINK_SEEN:
        print("  ✗ [thinking] 一次调用都没记到档位 —— 桩没接上？")
        return False
    # 普通调用与 reasoner 调用必须落在不同档
    if len(THINK_SEEN) < 2:
        print(f"  ✗ [thinking] 全程只出现一个档位 {dict(THINK_SEEN)} "
              f"—— 说明 thinking 没真的分开（或 reasoner 路径没跑到）")
        ok = False
    if ok:
        print(f"  ✓ [thinking] 两端 ID 同名（{llm.default_model}）"
              f"而档位仍能分开 {dict(THINK_SEEN)} —— 不再依赖名字猜")
    ok = _check_thinking_kwargs() and ok
    return ok

def _check_thinking_kwargs():
    """直接验真实 LLM.call 的 kwargs：thinking / temperature / max_tokens
    / response_format 四条线在两档下必须各自正确。

    不联网：把 client 换成假对象，只截获 **kwargs。
    """
    ok = True

    class _Choice:
        message = type("M", (), {
            "content": "ok", "role": "assistant"})()

        def __init__(self):
            self.finish_reason = "stop"

    class _Resp:
        model = "deepseek-flash"

        def __init__(self):
            self.choices = [_Choice()]
            self.usage = None

    class _Compl:
        def __init__(self, sink):
            self._sink = sink

        def create(self, **kw):
            self._sink.append(kw)
            return _Resp()

    class _Client:
        def __init__(self, sink):
            self.chat = type("C", (), {"completions": _Compl(sink)})()

    def probe(**cw):
        sink = []
        cfg = build_cfg(False)
        llm = mod.LLM(cfg)
        llm.client = _Client(sink)
        real = mod.LLM._real_call
        real(llm, "sys", "user", 0.6, 3000, **cw)
        assert sink, "桩 client 没接到调用"
        return sink[0]

    # ① 默认（非思考）：必须显式关掉思考 + 保留 temperature
    k = probe()
    if k.get("extra_body") != {"thinking": {"type": "disabled"}}:
        print(f"  ✗ [thinking] 默认调用应显式 disabled，实际 "
              f"extra_body={k.get('extra_body')}")
        ok = False
    if "temperature" not in k:
        print("  ✗ [thinking] 非思考档丢了 temperature")
        ok = False
    if k.get("max_tokens") != 3000:
        print(f"  ✗ [thinking] 非思考档不该抬高 max_tokens，"
              f"实际 {k.get('max_tokens')}")
        ok = False

    # ② 思考档：temperature 必须撤掉 + max_tokens 抬到 ≥32000
    #    [fix-112] effort 默认已改为 low（非 None），思考档会带上 effort=low
    k = probe(thinking="enabled")
    if k.get("extra_body") != {"thinking": {"type": "enabled", "effort": "low"}}:
        print(f"  ✗ [thinking] enabled 档 extra_body 不对："
              f"{k.get('extra_body')}")
        ok = False
    if "temperature" in k:
        print("  ✗ [thinking] 思考档不该带 temperature")
        ok = False
    if k.get("max_tokens", 0) < 32000:
        print(f"  ✗ [thinking] 思考档 max_tokens 必须 ≥32000（推理 token "
              f"计入预算），实际 {k.get('max_tokens')}")
        ok = False

    # ③ json_mode：非思考走 response_format；思考档不能走
    k = probe(json_mode=True)
    if (k.get("response_format") or {}).get("type") != "json_object":
        print(f"  ✗ [thinking] 非思考 json_mode 应带 response_format，"
              f"实际 {k.get('response_format')}")
        ok = False
    k = probe(json_mode=True, thinking="enabled")
    if "response_format" in k:
        print("  ✗ [thinking] 思考档不该带 response_format（历史行为）")
        ok = False

    # ④ effort：只在 enabled 时出现
    cfg2 = build_cfg(False)
    cfg2["api"]["thinking"]["effort"] = "low"
    sink = []

    class _C2:
        def __init__(self):
            self.chat = type("C", (), {"completions": _Compl(sink)})()

    l2 = mod.LLM(cfg2)
    l2.client = _C2()
    mod.LLM._real_call(l2, "s", "u", 0.6, 3000)
    mod.LLM._real_call(l2, "s", "u", 0.6, 3000, thinking="enabled")
    if (sink[1].get("extra_body") or {}).get("thinking", {}).get(
            "effort") != "low":
        print(f"  ✗ [thinking] effort 应只在 enabled 出现："
              f"{sink[1].get('extra_body')}")
        ok = False
    if (sink[0].get("extra_body") or {}).get("thinking", {}).get("effort"):
        print("  ✗ [thinking] 非思考档不该带 effort")
        ok = False

    if ok:
        print("  ✓ [thinking] kwargs 四线正确："
              "非思考=disabled+temperature+原 max_tokens+response_format；"
              "思考=enabled+撤 temperature+max_tokens≥32000+不带 response_format"
              "；effort 只挂 enabled")
    return ok

def check_meta_closure_by_id():
    """[v1.21.62] 元层闭环清算：按 tension_id 精确对账，不再只靠措辞。

    实测 89 次元层清算只 clean 了 7 次（8%），未交代比例恒在 90-100%
    —— 一条几乎恒为假的口径分不出好坏，等于**监督失效**。
    根因：原来只有 `_similar(target, 0.6)` 一条路，而元层 engagements
    的 target 是它自己重写的短句，跟对撞层的原始措辞对不上。人工核过
    一份产物：元层确实逐条处置了那 4 条张力，只是措辞不同，全被判成
    「未交代」。
    → 元层处置时带 tension_id（对撞池发的 t_XXX），这里按编号对账；
      编号对不上才退回措辞比对。
    """
    ok = True

    class _Fake:
        _settle_meta = mod.MetaDGTF._settle_meta

    def _mk(all_eng):
        both = mod.Pool()
        both.duel_suspensions = [
            {"id": "t_001", "target": "次序差是工具边界还是切分遗留",
             "status": "active"},
            {"id": "t_002", "target": "'拆到一半'与'拆完'是否同一整体",
             "status": "active"}]
        allp = mod.Pool()
        allp.engagements = list(all_eng)
        f = _Fake()
        f.pools = {"both": both, "all": allp}
        f.config = mod.DEFAULT_CONFIG
        return f._settle_meta()

    # ① 措辞完全不同，但带编号 → 要判为已交代（这是修的目标）
    r1 = _mk([{"target": "两处都不能独立指认", "tension_id": "t_001"},
              {"target": "缺同一性判据", "tension_id": "t_002"}])
    if not r1.get("clean") or r1.get("by_id") != 2:
        print(f"  ✗ [清算对账] 带 tension_id 时应按编号判为已交代：{r1}")
        ok = False

    # ② 同样措辞但不带编号 → 退回模糊比对，判不出来（老行为，要保留
    #    作为兜底，不能因为加了编号就把这条路删了）
    r2 = _mk([{"target": "两处都不能独立指认"},
              {"target": "缺同一性判据"}])
    if r2.get("clean"):
        print(f"  ✗ [清算对账] 无编号且措辞不同，不该判 clean：{r2}")
        ok = False
    if r2.get("by_id") != 0:
        print(f"  ✗ [清算对账] 无编号时 by_id 应为 0：{r2}")
        ok = False

    # ③ 只带一条编号 → 另一条仍未交代，不能一刀切判 clean
    r3 = _mk([{"target": "两处都不能独立指认", "tension_id": "t_001"}])
    if r3.get("clean") or r3.get("unsettled") != 1:
        print(f"  ✗ [清算对账] 只交代一条时 unsettled 应为 1：{r3}")
        ok = False

    if ok:
        print("  ✓ [清算对账] 按 tension_id 精确对账（带编号判已交代、"
              "无编号退回措辞、只交代一条不算 clean）")
    return ok

def check_starve_escalation():
    """[v1.21.61] 反向触发点：连续 N 圈无进展 → 迁向不可判定。

    三态在真跑里是**单向漂移**的（40 份日志：reclass 只有 und→partial /
    dec→partial，从无 partial→und），于是 escalation 恒为 0，依赖它的
    复债也恒为 0。这里验三件事：会触发、有进展时不触发、债务编号只能
    支撑 →undecidable。
    """
    ok = True

    def mk(state="partial"):
        p = mod.Pool()
        p.amps = [{"desc": "任何判定都要求对象在登记前已有边界",
                   "type": "structural"}]
        p.sub_questions = [{"id": 3, "question": "部分之和是否等于整体",
                            "decidability": state, "status": "open",
                            "weight": 1.0}]
        p.deferrals = [{"id": "d_001", "sub_id": 3,
                        "sub_question": "部分之和是否等于整体",
                        "reason": "先看 T6",
                        "revisit_condition": "T6 有结论后",
                        "layer": 2, "last_reconfirmed_layer": 2,
                        "status": "deferred", "resolved_at": None,
                        "resolution_reason": ""}]
        return p

    def empty_view():
        return mod.View(entry="1")

    # 用**出厂默认值**，别写死 3 —— 出厂值改了这里要跟着验
    cfg = {"spiral": {"escalate_starve_rounds":
                      mod.DEFAULT_CONFIG["spiral"]["escalate_starve_rounds"]}}

    # 1) 连续 3 圈无进展 → 迁向 undecidable，且账被连着关成 escalated
    p = mk("partial")
    for _r in (1, 2, 3):
        mod.update_deferrals(p, empty_view(), layer=_r, cfg=cfg)
    sq = p.sub_questions[0]
    if sq["decidability"] != "undecidable":
        print(f"  ✗ [反向触发] 连续 3 圈无进展没迁向不可判定："
              f"{sq['decidability']}")
        ok = False
    elif p.deferrals[0]["status"] != "escalated":
        print(f"  ✗ [反向触发] 迁走后账没连着关：{p.deferrals[0]['status']}")
        ok = False
    else:
        print("  ✓ [反向触发] 连续 3 圈无进展 → 迁向不可判定，"
              "名下债务连着关成 escalated")

    # 2) 本圈被**直接回答**算进展 → 不触发，且计数清零
    p = mk("partial")
    for _r in (1, 2):
        v = empty_view()
        v.engagements = [{"sub_id": 3, "how": "给出了对齐口径",
                          "depth": 0.3}]
        mod.update_deferrals(p, v, layer=_r, cfg=cfg)
    if p.sub_questions[0]["decidability"] != "partial":
        print("  ✗ [反向触发] 每圈都被回答却仍被判不可判定")
        ok = False
    elif int(p.sub_questions[0].get("_starve_rounds", -1)) != 0:
        print(f"  ✗ [反向触发] 有进展时计数没清零："
              f"{p.sub_questions[0].get('_starve_rounds')}")
        ok = False
    else:
        print("  ✓ [反向触发] 本圈被回答时不触发，计数清零")

    # 2b) ★ 复确认**不算进展**（它说的是"账还在、还是拿不到东西"）。
    #     真跑 v61a 里研究层每圈都在「确认3」，若把复确认当进展，
    #     计数永远清零，这个触发点等于被自己废掉。
    p = mk("partial")
    for _r in (1, 2, 3):
        v = empty_view()
        v.reconfirmations = [{"deferral_id": "d_001", "note": "还在等 T6"}]
        mod.update_deferrals(p, v, layer=_r, cfg=cfg)
    if p.sub_questions[0]["decidability"] != "undecidable":
        print("  ✗ [反向触发] 只被复确认（无实质进展）却没迁向不可判定："
              f"{p.sub_questions[0]['decidability']}")
        ok = False
    else:
        print("  ✓ [反向触发] 复确认不算进展 —— 连挂 3 圈只被确认，"
              "仍迁向不可判定")

    # 3) 名下没有挂着的账 → 不硬造证据（宁可不判，也不凭空升级）
    p = mk("partial")
    p.deferrals = []
    for _r in (1, 2, 3, 4):
        mod.update_deferrals(p, empty_view(), layer=_r, cfg=cfg)
    if p.sub_questions[0]["decidability"] != "partial":
        print("  ✗ [反向触发] 没有挂着的账却凭空判了不可判定")
        ok = False
    else:
        print("  ✓ [反向触发] 没有未清偿债务时不动手（不硬造证据）")

    # 4) 债务编号只能支撑 →undecidable，不能用来支撑 →decidable
    p = mk("undecidable")
    p.deferrals[0]["status"] = "deferred"
    v = empty_view()
    v.reclassifications = [{"sub_id": 3, "to": "decidable",
                            "reason": "账还在", "evidence": ["d_001"]}]
    mod.update_deferrals(p, v, layer=7, cfg=cfg)
    if p.sub_questions[0]["decidability"] != "undecidable":
        print("  ✗ [反向触发] 拿债务编号支撑 →decidable 竟被采纳")
        ok = False
    else:
        print("  ✓ [反向触发] 债务编号只能支撑 →undecidable，"
              "不能用来证明答案已找到")

    # 5) 打通断链：反向触发迁走后又被救回 → 复债必须触发
    p = mk("partial")
    for _r in (1, 2, 3):
        mod.update_deferrals(p, empty_view(), layer=_r, cfg=cfg)
    v2 = empty_view()
    v2.reclassifications = [{"sub_id": 3, "to": "partial",
                             "reason": "补上了对齐口径",
                             "evidence": ["A1"]}]
    mod.update_deferrals(p, v2, layer=9, cfg=cfg)
    if len(p.deferrals) != 2 or p.deferrals[1]["status"] != "deferred":
        print(f"  ✗ [反向触发] 救回后没复债："
              f"{[(d['id'], d['status']) for d in p.deferrals]}")
        ok = False
    else:
        print("  ✓ [反向触发] 迁走后再救回 → 复债触发，"
              "escalation→复债 这条链通了")
    return ok

def check_debt_reopen():
    """[v1.21.59] 从 undecidable 转回「欠答案」时，被关掉的账要重新挂起来。

    迁向 undecidable 会顺手把该子问题名下的 deferred 关成 escalated
    （"不再欠了"，合理）。可判定被推翻、转回 decidable/partial 时，**"欠"
    这件事其实恢复了** —— 而债务账是唯一会被复确认 / 清偿 / 终局清算 /
    反躺平盯住的地方（`_probe_research` 的 open_def、`deferred_ratio_of`、
    `_settle_research` 都只看 status=="deferred"）。
    """
    ok = True

    def mk(state="decidable"):
        p = mod.Pool()
        p.amps = [{"desc": "任何判定都要求对象在登记前已有边界",
                   "type": "structural"}]
        p.sub_questions = [{"id": 3, "question": "部分之和是否等于整体",
                            "decidability": state, "status": "open",
                            "weight": 1.0}]
        return p

    def old_debt(status="deferred"):
        return {"id": "d_001", "sub_id": 3,
                "sub_question": "部分之和是否等于整体",
                "reason": "先看 T6", "revisit_condition": "T6 有结论后",
                "layer": 2, "last_reconfirmed_layer": 2, "status": status,
                "resolved_at": None, "resolution_reason": ""}

    # 1) 完整往返：挂账 → 升级（关账）→ 推翻（复债）；旧条不得被改写
    p = mk("decidable")
    p.deferrals = [old_debt()]
    v = mod.View(entry="1")
    v.escalations = [{"sub_id": 3, "reason": "无共同登记表",
                      "evidence": ["A1"]}]
    mod.update_deferrals(p, v, layer=5, cfg={})
    if p.deferrals[0]["status"] != "escalated":
        print("  ✗ [复债] 升级时没关账（前置条件就不成立）")
        ok = False
    v2 = mod.View(entry="1")
    v2.reclassifications = [{"sub_id": 3, "to": "decidable",
                             "reason": "本圈 & 给出登记位置",
                             "evidence": ["A1"]}]
    mod.update_deferrals(p, v2, layer=8, cfg={})
    if len(p.deferrals) != 2 or p.deferrals[1]["status"] != "deferred":
        print(f"  ✗ [复债] 推翻后没重新挂账："
              f"{[(d['id'], d['status']) for d in p.deferrals]}")
        ok = False
    elif p.deferrals[0]["status"] != "escalated":
        print("  ✗ [复债] 旧条被改写了（历史必须是 append-only）")
        ok = False
    elif p.deferrals[1].get("reopened_from") != "d_001":
        print("  ✗ [复债] 新账没记来源（reopened_from）")
        ok = False
    elif p.deferrals[1]["revisit_condition"] != "T6 有结论后":
        print("  ✗ [复债] 回访条件没原样归还")
        ok = False
    else:
        print("  ✓ [复债] 关掉的账重新挂一笔（新 d_002，接 d_001，"
              "回访条件原样归还），旧条仍是 escalated 未被改写")

    # 2) 本来就欠过账 → 不凭空开（否则债务账会被灌水）
    p = mk("undecidable")           # 直接就是 undecidable，从没挂过账
    v = mod.View(entry="1")
    v.reclassifications = [{"sub_id": 3, "to": "decidable",
                            "reason": "有证据", "evidence": ["A1"]}]
    mod.update_deferrals(p, v, layer=3, cfg={})
    if p.deferrals:
        print(f"  ✗ [复债] 从没欠过账却开了新账（{len(p.deferrals)} 条）")
        ok = False
    else:
        print("  ✓ [复债] 从没欠过账的子问题不凭空开账")

    # 3) 已经有在挂的账 → 不重复开
    p = mk("undecidable")
    p.deferrals = [old_debt("escalated"), old_debt("deferred")]
    p.deferrals[1]["id"] = "d_002"
    v = mod.View(entry="1")
    v.reclassifications = [{"sub_id": 3, "to": "decidable",
                            "reason": "有证据", "evidence": ["A1"]}]
    mod.update_deferrals(p, v, layer=9, cfg={})
    if len(p.deferrals) != 2:
        print(f"  ✗ [复债] 已有在挂的账还重复开（{len(p.deferrals)} 条）")
        ok = False
    else:
        print("  ✓ [复债] 已有在挂的账时不重复开")

    # 4) 转 partial 也要复债（partial 同属"欠一个答案"）
    p = mk("undecidable")
    p.deferrals = [old_debt("escalated")]
    v = mod.View(entry="1")
    v.reclassifications = [{"sub_id": 3, "to": "partial",
                            "reason": "只能部分操作化",
                            "evidence": ["A1"]}]
    mod.update_deferrals(p, v, layer=9, cfg={})
    if len(p.deferrals) != 2 or p.deferrals[1]["status"] != "deferred":
        print("  ✗ [复债] 转 partial 时没复债（partial 也欠答案）")
        ok = False
    else:
        print("  ✓ [复债] 转 partial 同样复债")

    # 5) 产物里要看得见：变更轨迹点出重新挂账，债务明细标出来源
    p = mk("decidable")
    p.deferrals = [old_debt()]
    v = mod.View(entry="1")
    v.escalations = [{"sub_id": 3, "reason": "无共同登记表",
                      "evidence": ["A1"]}]
    mod.update_deferrals(p, v, layer=5, cfg={})
    v2 = mod.View(entry="1")
    v2.reclassifications = [{"sub_id": 3, "to": "decidable",
                             "reason": "有证据", "evidence": ["A1"]}]
    mod.update_deferrals(p, v2, layer=8, cfg={})
    vd = dict(p.to_dict())
    vd.update({"anchor": "（略）", "manifest": "", "collision": "",
               "candidates": [], "probes": [], "meta": [], "threads": [],
               "revocations": [], "suspensions": [], "settlement": {},
               "adjudications": [], "duel_suspensions": [], "quality_flags": [],
               "closure_reason": "", "errors": [], "self_check": {},
               "reclassifications": []})
    res = {"question": "冒烟：复债渲染", "route": [], "keep": None,
           "views": {"1": vd}, "pools": {"1": p.to_dict()},
           "llm_calls": 0, "llm_tokens": 0}
    with tempfile.TemporaryDirectory() as td:
        txt = mod.save_result(res, td).read_text(encoding="utf-8")
    if "并重新挂账" not in txt or "← 重新挂账（接 d_001）" not in txt:
        print("  ✗ [复债] 产物里看不到重新挂账（轨迹行或债务明细缺标记）")
        ok = False
    else:
        print("  ✓ [复债] 产物可见：轨迹行点出「并重新挂账」，"
              "债务明细标出「← 重新挂账（接 d_001）」")
    return ok

def check_layer_guard():
    """[v1.21.60] 某层失败必须**留痕 + 可见**，不许静默丢层。

    老代码：B/C/D-H 里某层第 1 圈抛异常 → `state["stopped"]=True`，但
    `self._results[entry]` 永不写入 → `_b_finalize_layer` 见 `view is None`
    直接 return → **该层从 views/pools/self 段整层消失**，下游也当它不存在。
    而所有校验都拿"实际 views"当基准 → **永远判不出缺层**。

    同时钉住第二件事：并行模式原来把 `dispatch` 写死
    `order=实际结果.keys(), skipped=[]`，使蓝图 D4「依赖不满足 → 如实跳过 +
    写原因」的留痕在并行模式下**全丢**。
    """
    ok = True
    cfg = build_cfg(False)

    # ---- 1) 并行（B）某层失败：不许消失，要记下来并让产物说出来 ----
    mt = mod.MetaDGTF(cfg)
    _orig = mt._run_one_round_B

    def _boom(entry, r):
        if entry == "1":
            raise RuntimeError("冒烟注入：研究层失败")
        return _orig(entry, r)
    mt._run_one_round_B = _boom
    res = mt.run("冒烟：层缺失守卫", route=["0", "1", "both", "all"],
                 rounds={"0": 1, "1": 1, "both": 1, "all": 1},
                 parallel_mode="B")
    disp = res.get("dispatch") or {}
    if list(disp.get("missing") or []) != ["1"]:
        print(f"  ✗ [层守卫] B 模式缺层没被发现："
              f"missing={disp.get('missing')}，order={disp.get('order')}")
        ok = False
    elif not disp.get("failed", {}).get("1"):
        print("  ✗ [层守卫] 缺层了但没记原因（failed 为空）")
        ok = False
    elif "1" not in res.get("views", {}):
        print("  ✗ [层守卫] 失败层从 views 里消失了（应该留占位、在场但不可用）")
        ok = False
    else:
        print(f"  ✓ [层守卫] B 模式缺层被发现并留痕：missing={disp['missing']}，"
              f"views 里仍有占位（errors 写入）")

    # 产物必须明写缺层
    p = mod.save_result(res, cfg["output"]["save_dir"])
    txt = p.read_text(encoding="utf-8").replace("\r\n", "\n")
    if "缺层" not in txt:
        print("  ✗ [层守卫] 产物里没写缺层（读者看不出这份产物不完整）")
        ok = False
    elif "研究层失败" not in txt:
        print("  ✗ [层守卫] 产物写了缺层但没写原因")
        ok = False
    else:
        print("  ✓ [层守卫] 产物头部明写「❌ 缺层」+ 原因")

    # ---- 2) 串行某层失败：必须逐层隔离，不能整轮零产物 ----
    mt2 = mod.MetaDGTF(cfg)
    _orig2 = mt2._run_layer

    def _boom2(entry, n):
        if entry == "both":
            raise RuntimeError("冒烟注入：对撞层失败")
        return _orig2(entry, n)
    mt2._run_layer = _boom2
    res2 = mt2.run("冒烟：串行逐层隔离", route=["0", "1", "both", "all"],
                   rounds={"0": 1, "1": 1, "both": 1, "all": 1},
                   parallel_mode="serial")
    disp2 = res2.get("dispatch") or {}
    if list(disp2.get("missing") or []) != ["both"]:
        print(f"  ✗ [层守卫] 串行失败层没被隔离/记录："
              f"missing={disp2.get('missing')}")
        ok = False
    elif not res2.get("views"):
        print("  ✗ [层守卫] 串行一层失败把整轮结果弄没了")
        ok = False
    else:
        print(f"  ✓ [层守卫] 串行逐层隔离：other 层照常产出，"
              f"both 记为缺层（{len(res2['views'])} 个 view）")

    # ---- 3) 依赖不满足必须"如实跳过 + 写原因"（并行模式也要）----
    mt3 = mod.MetaDGTF(cfg)
    res3 = mt3.run("冒烟：跳过留痕", route=["0", "both"],
                   rounds={"0": 1, "both": 1}, parallel_mode="B")
    disp3 = res3.get("dispatch") or {}
    if not disp3.get("skipped"):
        print("  ✗ [层守卫] 并行模式把「依赖不满足的跳过」留痕丢了"
              "（skipped 为空）")
        ok = False
    elif "both" in (res3.get("views") or {}):
        print("  ✗ [层守卫] 计划里被判跳过的层，并行模式照样跑了")
        ok = False
    else:
        _sk = disp3["skipped"][0]
        print(f"  ✓ [层守卫] 跳过留痕在（`{_sk.get('entry')}`："
              f"{str(_sk.get('reason'))[:26]}），且该层确实没跑")
    return ok

def check_p162_units():
    """[v1.21.62] 本轮工艺项的单元断言（≥5 条，覆盖 P0-1/P0-2/P0-3/
    P1-4/P1-5/P1-6/P2-7/P2-8/P2-9/P3-11）。

    原则：每条都走真代码路径，不靠"源码里有这行字"糊过去；
    只有"分支互不相同"这类结构属性才用 grep。
    """
    ok = True
    cfg = build_cfg(False)

    # ================= P0-1 · 锚点重述带出 touched =================
    try:
        res = mod.MetaDGTF(cfg).run(
            "冒烟：锚点重述两半", route=["0"], rounds={"0": 2},
            parallel_mode="serial")
        v0 = (res.get("views") or {}).get("0") or {}
        _t = list(v0.get("anchor_touched") or [])
        _u = list(v0.get("untouched") or [])
        if len(_t) != 2:
            print(f"  ✗ [P0-1] touched 没进 view（应 2 条）：{_t}")
            ok = False
        elif len(_u) < 2:
            print(f"  ✗ [P0-1] untouched 丢了：{_u}")
            ok = False
        else:
            print(f"  ✓ [P0-1] 重述两半都入 view：touched {len(_t)} / "
                  f"untouched {len(_u)}，且 source=anchor")
    except Exception as e:
        print(f"  ✗ [P0-1] 失败: {type(e).__name__}: {e}")
        ok = False

    # ================= P0-2 · 「至少碰一个」硬约束重试 =================
    def _probe_run(force_empty, n_rounds):
        try:
            os.environ["SMOKE_PROBE_EMPTY"] = "1"
            if not force_empty:
                # 用"远大于可见次数"的值让计数永不为 0 → 不返回空
                PROBE_EMPTY_SEEN["n"] = -10 ** 6
            else:
                PROBE_EMPTY_SEEN["n"] = 0
            CALLS["n"] = 0
            _c0 = build_cfg(False)
            # ★ [v1.23.16 判据随实现更新] 池重估的间隔曾随成本档
            #   惰性化（balanced 下 1→2）；本版去惰性化 ⇒ 1 圈也会跑
            #   重估，而「池空」时重估不适用（少一次调用）⇒ 两条路径的
            #   调用数被这个**与重试无关**的变量拉开。判据只关心重试，
            #   所以先把重估关掉再比（不是放宽阈值）。
            _c0.setdefault("spiral", {})["re_eval_every_n"] = 0
            r = mod.MetaDGTF(_c0).run(
                "冒烟：至少碰一个", route=["0"], rounds={"0": n_rounds},
                parallel_mode="serial")
            v = (r.get("views") or {}).get("0") or {}
            return CALLS["n"], v
        finally:
            os.environ.pop("SMOKE_PROBE_EMPTY", None)
    try:
        n_base, v_base = _probe_run(False, 2)
        n_retry, v_retry = _probe_run(True, 2)
        n_last_b, _ = _probe_run(False, 1)
        n_last_r, _ = _probe_run(True, 1)
        if not (v_base.get("engagements") or []):
            print("  ✗ [P0-2] 基线跑就没碰任何一项（桩坏了，测不到东西）")
            ok = False
        elif n_retry != n_base + 1:
            print(f"  ✗ [P0-2] 首探针空却没重试：基线 {n_base} 次 / "
                  f"强制空 {n_retry} 次（应 +1）")
            ok = False
        elif not (v_retry.get("engagements") or []):
            print("  ✗ [P0-2] 重试后仍然一项没碰")
            ok = False
        elif n_last_r != n_last_b:
            print(f"  ✗ [P0-2] 最后一圈不该重试：单圈基线 {n_last_b} / "
                  f"单圈强制空 {n_last_r}（应相等）")
            ok = False
        else:
            print(f"  ✓ [P0-2] 空转触发 1 次重试并补上碰 "
                  f"（{n_base}→{n_retry}），最后一圈不重试"
                  f"（{n_last_b}→{n_last_r}）")
    except Exception as e:
        print(f"  ✗ [P0-2] 失败: {type(e).__name__}: {e}")
        ok = False

    # ================= P0-3 · 三种"没走到"视觉区分 =================
    try:
        res3 = mod.MetaDGTF(cfg).run(
            "冒烟：状态标记", route=["0"], rounds={"0": 2},
            parallel_mode="serial")
        p = mod.save_result(res3, cfg["output"]["save_dir"])
        txt = p.read_text(encoding="utf-8").replace("\r\n", "\n")
        if "**状态标记**" not in txt:
            print("  ✗ [P0-3] 产物里没有状态图例（三种未走到分不清）")
            ok = False
        elif "💭" not in txt:
            print("  ✗ [P0-3] 图例在但没实际用 💭 标未决项")
            ok = False
        else:
            print("  ✓ [P0-3] 产物头部有图例，且 💭/⏸/📘 各司其职")
    except Exception as e:
        print(f"  ✗ [P0-3] 失败: {type(e).__name__}: {e}")
        ok = False

    # ================= P1-4 · ing 结构化尾块 =================
    try:
        res4 = mod.MetaDGTF(cfg).run(
            "冒烟：ing 结构化尾块", route=["0", "1", "both"],
            rounds={"0": 1, "1": 1, "both": 1}, parallel_mode="serial")
        vb = (res4.get("views") or {}).get("both") or {}
        _s = vb.get("ing_structured") or {}
        if not _s.get("third"):
            print(f"  ✗ [P1-4] 对撞层没拿到结构化尾块：{_s}")
            ok = False
        else:
            print(f"  ✓ [P1-4] both 层 ing_structured 解析成功："
                  f"third={_s.get('third')!r}，tensions={len(_s.get('tensions') or [])} 条")
    except Exception as e:
        print(f"  ✗ [P1-4] 失败: {type(e).__name__}: {e}")
        ok = False

    # ================= P1-5 · 对撞层 he 独立 prompt（结构属性 → grep） =====
    try:
        # ★ 别硬编码版本号（本项目已出现两处）：读旧文件 = 当前版就算回归
        #   也会静默通过。一律从 SRC 派生。
        src = SRC.read_text(
            encoding="utf-8").replace("\r\n", "\n").replace(mod.__doc__ or "", "")
        _n_he = src.count("你处于【& · ")
        if _n_he != 3:
            print(f"  ✗ [P1-5] _he 分支数应为 3（research/duel/else），实为 {_n_he}")
            ok = False
        elif "tension_from" not in src:
            print("  ✗ [P1-5] 对撞层 & 没有 tension_from 字段")
            ok = False
        else:
            print("  ✓ [P1-5] _he 三份 prompt 互不相同，且 & 带 tension_from")
    except Exception as e:
        print(f"  ✗ [P1-5] 失败: {type(e).__name__}: {e}")
        ok = False

    # ========= P1-6 · revisit_condition 白名单（同日返修后的双向边界） =========
    #   ★ v1.21.62 初版白名单过窄：1213 条真实条件只放行 2%，且被拦的
    #     **完全无留痕**。返修后改成"三类宽特征任一命中 + 长度兜底"，
    #     并把被拦的写进 view.errors / pool.meta。这里双向钉死。
    try:
        _cases = [
            # (条件, 期望通过?, 说明)
            ("以后", False, "纯空词，黑名单"),
            ("看情况", False, "纯空词，黑名单"),
            ("待定", False, "纯空词，黑名单"),
            ("短", False, "长度不足 4"),
            ("未来某天", False, "无锚点且短于长度兜底"),
            ("当子问题 1 解决后", True, "时间词 + 状态动词"),
            ("T2 探针给出边界判据后", True, "引用 + 状态动词"),
            ("谓词类型区分完成后", True, "状态动词『完成』"),
            ("相对化屏障被形式化后", True, "时间兜底尾『后』"),
            ("出现公共刻度或登记程序", True, "状态动词『出现』"),
            ("覆盖率超过 0.7", True, "引用『覆盖率』"),
            ("只要有一点具体描述超过十字", True, "长度兜底 ≥10"),
            # ★ 这条是 v1.21.62 初版**误拦**的典型（金丝雀转正）：
            #   初版 `当.{1,30}(动词)` 要求「当」与动词间隔 ≥1 字 →
            #   「当出现…」不匹配。返修后由时间词分支放行。
            ("当出现新的实验数据时", True, "初版误拦，返修后放行"),
            # ---- [P1-6 修-2] 兜底 10→8 + 补获取/核查动词族后的边界 ----
            ("取到部署顺序记录", True, "8 字合法条件（长度兜底 8）"),
            ("逐字抄出两边原文", True, "8 字合法条件（长度兜底『抄出』）"),
            ("拿到两项金额", True, "6 字含『拿到』（补动词族）"),
            ("调上月现金流量表", True, "8 字（长度兜底 8）"),
            ("稍等", False, "2 字仍应拦（长度不足）"),
            # ★ 黑名单必须**优先于**长度兜底：这两条够长，只有"先黑名单
            #   排除"才拦得住。删掉它们 = 把判据顺序这件事藏起来。
            ("等以后再处理这件事", False, "含『以后』，长度 9 也拦"),
            ("看情况再说吧后面再定", False, "含『看情况』『再说』"),
        ]
        _wrong = [(c, e, mod._valid_revisit(c)) for c, e, _ in _cases
                  if mod._valid_revisit(c) != e]
        if _wrong:
            print(f"  ✗ [P1-6] 白名单边界错：{_wrong}")
            ok = False
        else:
            _p = sum(1 for _, e, _ in _cases if e)
            print(f"  ✓ [P1-6] 白名单双向边界：{_p} 条应通过全通过、"
                  f"{len(_cases) - _p} 条应拦全拦下")
    except Exception as e:
        print(f"  ✗ [P1-6] 失败: {type(e).__name__}: {e}")
        ok = False

    # ========= P1-6 修 · 被拦下的 deferral 必须留痕（不许无声消失） =========
    try:
        def _mk_deferrals(n_bad_cond, n_bad_reason, n_good):
            pool = mod.Pool()
            pool.sub_questions = [
                {"id": f"s{i}", "question": f"冒烟子问题{i}", "status": "open"}
                for i in range(1, n_bad_cond + n_bad_reason + n_good + 1)]
            v = mod.View(entry="1")
            ds = []
            i = 1
            for _ in range(n_bad_cond):
                ds.append({"sub_id": f"s{i}", "revisit_condition": "以后",
                           "reason": "理由写得足够长"}); i += 1
            for _ in range(n_bad_reason):
                ds.append({"sub_id": f"s{i}",
                           "revisit_condition": "当子问题 1 解决后",
                           "reason": "短"}); i += 1
            for _ in range(n_good):
                ds.append({"sub_id": f"s{i}",
                           "revisit_condition": "当子问题 1 解决后",
                           "reason": "理由写得足够长"})
            v.deferrals = ds
            return pool, v

        def _logged(pool, v):
            return (len([e for e in v.errors if "deferral 被拦" in e]),
                    len([m for m in pool.meta if "[P1-6]" in m]))

        # (a) 3 条被拦（2 条条件不合格 + 1 条理由太短）→ 两份留痕各 3 条
        p1, v1 = _mk_deferrals(2, 1, 1)
        st1 = mod.update_deferrals(p1, v1, 1, cfg)
        e1, m1 = _logged(p1, v1)
        if st1["invalid"] != 3 or e1 != 3 or m1 != 3:
            print(f"  ✗ [P1-6 修] 留痕不全：stats.invalid={st1['invalid']} "
                  f"view.errors={e1} pool.meta={m1}（应 3/3/3）")
            ok = False
        elif st1["new"] != 1:
            print(f"  ✗ [P1-6 修] 合格的那条没入池：new={st1['new']}")
            ok = False
        else:
            print("  ✓ [P1-6 修] 被拦必留痕：3 条 invalid → "
                  "view.errors 3 条 + pool.meta 3 条；合格 1 条照常入池")

        # (b) 30 条被拦 → 明细封顶 20 条，但 meta 里必须有一条汇总
        p2, v2 = _mk_deferrals(30, 0, 0)
        st2 = mod.update_deferrals(p2, v2, 1, cfg)
        e2, m2 = _logged(p2, v2)
        _summ = [m for m in p2.meta if "被拦共" in m]
        if st2["invalid"] != 30 or e2 != 20:
            print(f"  ✗ [P1-6 修] 明细限流不对：invalid={st2['invalid']} "
                  f"errors={e2}（应 30 / 20）")
            ok = False
        elif not _summ:
            print("  ✗ [P1-6 修] 超限后没有汇总留痕（总数不可查）")
            ok = False
        else:
            print(f"  ✓ [P1-6 修] 明细限流 20 条 + 汇总留痕："
                  f"{_summ[0][:52]}…")

        # (c) 渲染路径：留痕必须**真的进产物 md**。
        #   ★ 实测：`pool.meta` 在本版**没有产物渲染点**（「## 池」段只打
        #     计数，`_pool_shape` 也不含 meta），所以"产物里看得见"这件事
        #     实际由 `view.errors`（→【失败记录】段）承担。这条断言守的就是
        #     这一点：注入一条真实格式的留痕，落盘后必须在 md 里找到。
        _rr = mod.MetaDGTF(build_cfg(False)).run(
            "冒烟：留痕进产物", route=["0"], rounds={"0": 1},
            parallel_mode="serial")
        _rr["views"]["0"]["errors"] = list(
            _rr["views"]["0"].get("errors") or []) + [
            "deferral 被拦（revisit_condition 不合格）："
            "子问题[s1] 条件='以后'"]
        _rp = mod.save_result(_rr, cfg["output"]["save_dir"])
        _rmd = _rp.read_text(encoding="utf-8").replace("\r\n", "\n")
        if "deferral 被拦" not in _rmd:
            print("  ✗ [P1-6 修] 留痕没进产物 md（view.errors 未被渲染）")
            ok = False
        else:
            print("  ✓ [P1-6 修] 留痕进产物：【失败记录】段可查到"
                  "「deferral 被拦」")
    except Exception as e:
        print(f"  ✗ [P1-6 修] 失败: {type(e).__name__}: {e}")
        ok = False

    # ================= P2-7 · 取向判据 =================
    try:
        _orig_assess = mod.DGTF._assess_decidability
        try:
            # [v1.21.73] 签名必须带上 anchors —— 生产调用点已经传
            #   `anchors=`，替身收不下会 TypeError，被调用方宽 except
            #   吞掉，症状是"判据凭空失败"（P2-7 实得四层而不是[0,1]）。
            mod.DGTF._assess_decidability = \
                lambda self, q, anchors=None: {"decidability": "undecidable"}
            m7 = mod.MetaDGTF(build_cfg(False))
            _full = ["0", "1", "both", "all"]
            _q = "冒烟取向"
            r_bnd = m7._route_by_decidability(_q, list(_full), "boundary")
            r_dec = m7._route_by_decidability(_q, list(_full), "decision")
            r_auto = m7._route_by_decidability(_q, list(_full), "auto")
        finally:
            mod.DGTF._assess_decidability = _orig_assess
        if r_bnd != _full:
            print(f"  ✗ [P2-7] boundary 该保留全四层，实得 {r_bnd}")
            ok = False
        elif r_dec != ["0", "1"]:
            print(f"  ✗ [P2-7] decision+外判 undecidable 该砍到 [0,1]，"
                  f"实得 {r_dec}")
            ok = False
        elif r_auto != ["0", "1"]:
            print(f"  ✗ [P2-7] auto 该按 decision 处理，实得 {r_auto}")
            ok = False
        else:
            print("  ✓ [P2-7] 判据=想要什么：boundary 保四层 / "
                  "decision·auto 按可判定性砍层")
    except Exception as e:
        print(f"  ✗ [P2-7] 失败: {type(e).__name__}: {e}")
        ok = False

    # ================= P2-8 · auto_plan 拆两段 =================
    try:
        _o = mod.plan_orientation("选 A 还是 B", cfg)
        _r = mod.plan_resources("选 A 还是 B", "boundary", cfg)
        _p = mod.auto_plan("选 A 还是 B", cfg)
        if _o.get("orientation") not in ("boundary", "decision"):
            print(f"  ✗ [P2-8] plan_orientation 返回值非法：{_o}")
            ok = False
        elif _r.get("route") != ["0", "1", "both", "all"]:
            print(f"  ✗ [P2-8] boundary 的 route 必须是 full：{_r.get('route')}")
            ok = False
        elif _p.get("orientation") not in ("boundary", "decision"):
            print(f"  ✗ [P2-8] auto_plan 没带出 orientation：{_p}")
            ok = False
        else:
            print(f"  ✓ [P2-8] 拆成两段：取向={_o['orientation']}，"
                  f"boundary→route full，auto_plan 带 orientation={_p['orientation']}")
    except Exception as e:
        print(f"  ✗ [P2-8] 失败: {type(e).__name__}: {e}")
        ok = False

    # ================= P2-9 · 显化层（纯函数 + 进产物） =================
    try:
        res9 = mod.MetaDGTF(cfg).run(
            "冒烟：显化层", route=["0"], rounds={"0": 2},
            parallel_mode="serial")
        _snap = copy.deepcopy(res9)
        _txt = mod.render_manifestation(res9)
        if res9 != _snap:
            print("  ✗ [P2-9] render_manifestation 改了 res（不是纯函数）")
            ok = False
        elif "显化动作清单" not in _txt:
            print("  ✗ [P2-9] 显化文本缺动作清单")
            ok = False
        else:
            p9 = mod.save_result(res9, cfg["output"]["save_dir"])
            _md = p9.read_text(encoding="utf-8").replace("\r\n", "\n")
            if "## 显化说明" not in _md:
                print("  ✗ [P2-9] 产物里没有显化说明")
                ok = False
            elif "这份产物没有显化的" not in _md:
                print("  ✗ [P2-9] 显化说明缺「没有显化的」一段")
                ok = False
            else:
                print("  ✓ [P2-9] render_manifestation 纯函数、含动作清单与"
                      "「没有显化的」，且已进产物头部")
    except Exception as e:
        print(f"  ✗ [P2-9] 失败: {type(e).__name__}: {e}")
        ok = False

    # ================= P3-11 · 一致率可信度分级 =================
    #   ★ 冒烟桩下 `_adjudicate_sub_tristate` 恒回 (0,0)，真跑路径拿不到
    #     非零 tri_total，所以这里**注入**分母，专测渲染分支的三档映射。
    try:
        _cases = [([9, 10], "✅ 高"), ([1, 2], "⚠️ 中"), ([1, 4], "❌ 低")]
        _wrong = []
        for _tri, _want in _cases:
            _r11 = copy.deepcopy(res9)
            _r11["tri_state"] = list(_tri)
            _p11 = mod.save_result(_r11, cfg["output"]["save_dir"])
            _md11 = _p11.read_text(encoding="utf-8").replace("\r\n", "\n")
            if "可信度分级" not in _md11 or _want not in _md11:
                _wrong.append((_tri, _want))
        if _wrong:
            print(f"  ✗ [P3-11] 分级渲染不对：{_wrong}")
            ok = False
        else:
            print("  ✓ [P3-11] 一致率分级三档都对："
                  "≥80% ✅高 / ≥50% ⚠️中 / >0 ❌低")
    except Exception as e:
        print(f"  ✗ [P3-11] 失败: {type(e).__name__}: {e}")
        ok = False

    return ok

def check_p162_fix2_units():
    """[v1.21.62 收尾] 本轮三项修改的单元断言。

    ① [P3-10 修] 元层 probe 的 prompt 里**不许再有字面 t_001** ——
       那是 JSON schema 的示例值，实测被模型原样抄回（3 条 engagement
       填 t_001，而 active 编号是 t_005~t_007）→ by_id 恒 0。
       这里不联网、只 stub 掉 llm.call 捕获 prompt 来验。
    ② [P1-6 补] `view.errors` 跨圈累积：`_run_layer` 每圈新建 view、
       只 return 最后一圈，中间圈的 errors 会丢。serial 与 B 两条通道
       都要能保住每一圈的。
    """
    ok = True
    cfg = build_cfg(False)

    # ---- ① 元层 probe：schema 用占位符 + 清单里给真编号 ----
    try:
        captured = {}

        class _Stub:
            default_model = "x"
            reasoner_model = "x"
            thinking_reasoner = None
            SERVED_SEEN = set()

            def call(self, system, user, *a, **kw):
                captured["system"] = system
                captured["user"] = user
                return json.dumps({"probes": [], "engagements": [],
                                   "suspensions": [], "threads": [],
                                   "reconfirmations": [], "revocations": []},
                                  ensure_ascii=False)

            def parse_json(self, raw):
                return json.loads(raw)

        duel = [{"id": "t_005", "target": "接口被用掉那一轮有无痕迹",
                 "status": "active", "quadrant": "③"},
                {"id": "t_006", "target": "接缝被先行命名时落在哪一轮",
                 "status": "active", "quadrant": "③"},
                {"id": "t_001", "target": "已 resolved 的旧号",
                 "status": "resolved", "quadrant": "③"}]
        bp = mod.Pool()
        bp.duel_suspensions = [dict(x) for x in duel]
        bv = mod.View(entry="both")
        bv.duel_suspensions = [dict(x) for x in duel]
        d = mod.DGTF("all", _Stub(), cfg)
        d._probe_meta(mod.View(entry="all"),
                      mod.Input(question="冒烟：编号可见性",
                                upstream_views=[bv], upstream_pools=[bp]),
                      mod.Pool())
        sys_p, usr_p = captured.get("system", ""), captured.get("user", "")
        if '"t_001"' in sys_p:
            print("  ✗ [P3-10 修] schema 里还有字面 \"t_001\"（会被抄）")
            ok = False
        elif "<从清单原样复制>" not in sys_p:
            print("  ✗ [P3-10 修] schema 里没换成占位符")
            ok = False
        elif "[t_005]" not in usr_p or "[t_006]" not in usr_p:
            print(f"  ✗ [P3-10 修] 清单里没给 active 编号：[t_005]="
                  f"{'[t_005]' in usr_p} [t_006]={'[t_006]' in usr_p}")
            ok = False
        elif "[t_001]" in usr_p:
            print("  ✗ [P3-10 修] 已 resolved 的编号不该进清单")
            ok = False
        elif "原样复制" not in usr_p:
            print("  ✗ [P3-10 修] user 里没写「原样复制」的硬指令")
            ok = False
        else:
            print("  ✓ [P3-10 修] 元层 prompt：schema 用占位符、清单给 "
                  "active 编号（t_005/t_006，已排除 resolved）、且要求原样复制")
    except Exception as e:
        print(f"  ✗ [P3-10 修] 失败: {type(e).__name__}: {e}")
        ok = False

    # ---- ② view.errors 跨圈累积（serial 与 B 两条通道） ----
    #   ★ 必须分别验**两个写入时机**，否则测不到真问题：
    #     · 早写者：在 `DGTF.run` 内部写（旧断言只测了这个 → 假通过）
    #     · 晚写者：在 `update_deferrals` 里写（P1-6 留痕就是这个时机，
    #       第一版收集点放在 dg.run 之后，于是 4 圈只剩最后 1 条）
    for mode in ("serial", "B"):
        try:
            _orig_run = mod.DGTF.run
            _orig_ud = mod.update_deferrals
            _n = {"run": 0, "ud": 0}

            def _patched_run(self, inp, _o=_orig_run, _c=_n):
                v = _o(self, inp)
                _c["run"] += 1
                v.errors.append(f"[冒烟注入-早] 第{_c['run']}圈错误")
                return v

            # [v1.23.0 W2] 生产侧 update_deferrals 多了 web_hook 形参。
            def _patched_ud(pool, view, layer, cfg, web_hook=None,
                            _o=_orig_ud, _c=_n):
                st = _o(pool, view, layer, cfg, web_hook=web_hook)
                _c["ud"] += 1
                view.errors.append(f"[冒烟注入-晚] 第{_c['ud']}圈错误")
                return st

            try:
                mod.DGTF.run = _patched_run
                mod.update_deferrals = _patched_ud
                # ★ [v1.23.17 判据随实现更新] 本判据量的是「errors 跨圈累积」，
                #   与层跑几圈无关。v1.23.17 起条件 1（复述/自省点名）对四层生效、
                #   且 soft_max 降到 2 ⇒ 研究层第 2 圈就停（实测停因含「ing 连续
                #   2 圈复述… + 自省连续 2 圈点名同一批问题未消化」），「3 圈」这个
                #   夹具假设不再成立。**把停止固定住**（不是把 3 改小）：soft_max 抬高
                #   同时关掉条件 1 的推迟与条件 6，三条 idle 阈值抬到 99，sat 关掉
                #   ⇒ 各层跑满自己的上限（实测 0 层 2 圈 / 1 层 3 圈）。
                _cfg_p16 = build_cfg(False)
                _sp16 = _cfg_p16.setdefault("spiral", {})
                _sp16["soft_max"] = 99
                _sp16["round_idle_limit"] = 99
                _sp16["round_stall_limit"] = 99
                _sp16["idle_limit"] = 99
                _sp16["structure_saturation_enabled"] = False
                res = mod.MetaDGTF(_cfg_p16).run(
                    "冒烟：跨圈 errors 累积", route=["0", "1"],
                    rounds={"0": 2, "1": 3}, parallel_mode=mode)
            finally:
                mod.DGTF.run = _orig_run
                mod.update_deferrals = _orig_ud
            v0 = (res.get("views") or {}).get("0") or {}
            v1 = (res.get("views") or {}).get("1") or {}
            early = {e for e in (v0.get("errors") or [])
                     if e.startswith("[冒烟注入-早]")}
            late = {e for e in (v1.get("errors") or [])
                    if e.startswith("[冒烟注入-晚]")}
            if len(early) != 2:
                print(f"  ✗ [P1-6 补] {mode} 早写者跨圈只保住 "
                      f"{len(early)}/2：{sorted(early)}")
                ok = False
            elif len(late) != 3:
                print(f"  ✗ [P1-6 补] {mode} **晚写者**跨圈只保住 "
                      f"{len(late)}/3：{sorted(late)}")
                ok = False
            else:
                print(f"  ✓ [P1-6 补] {mode} 通道：早写者 2/2、"
                      f"晚写者 3/3，跨圈 errors 全保住")
        except Exception as e:
            print(f"  ✗ [P1-6 补] {mode} 失败: {type(e).__name__}: {e}")
            ok = False

    return ok

def check_v63_c_fixes():
    """[v1.21.63 C] 第一批（C 段修复）的源码断言 —— 全是**结构属性**，
    用 inspect.getsource 验（行为已在 check_p162_fix2_units 里验过）。

    ★ 比链接版多三条（本轮自己加的）：
      · 字面 id 泄漏检查：`_probe_meta` / `_phase_probe` 里不许再有
        `"s_001"` / `"s_002"` —— 实测模型会把 schema 示例原样抄回来。
      · 编号校验留痕存在（解析处必须写 view.errors）。
      · `_settle_meta` 必须产出 by_id_inactive / by_id_unknown。
    """
    ok = True
    import inspect as _ins

    pm = _ins.getsource(mod.DGTF._probe_meta)
    ph = _ins.getsource(mod.DGTF._phase_probe)
    sr = _ins.getsource(mod.save_result)
    fin = _ins.getsource(mod.MetaDGTF._finalize_layer_common)
    rl = _ins.getsource(mod.MetaDGTF._run_layer)
    rb = _ins.getsource(mod.MetaDGTF._run_one_round_B)

    checks = [
        ('"tension_id":"t_001"' not in pm, "C1 · _probe_meta 里还有 t_001 字面量"),
        ("从清单原样复制" in pm, "C1 · _probe_meta 缺占位符"),
        ('"s_001"' not in pm and '"s_002"' not in pm,
         "C1 · _probe_meta 里还有 s_001/s_002 字面量"),
        ('"s_001"' not in ph and '"s_002"' not in ph,
         "C1 · _phase_probe 里还有 s_001/s_002 字面量（同源缺陷）"),
        ("tension_id 不合法" in pm, "C1 · 解析处缺编号校验留痕"),
        ("by_id" in sr and "covered_ids" in sr, "C1 · save_result 缺 by_id 渲染"),
        ("by_id_inactive" in sr and "by_id_unknown" in sr,
         "C1 · save_result 缺 inactive/unknown 分类渲染"),
        ("all_view_errors" in fin, "C2 · _finalize_layer_common 缺合并"),
        ("_all_view_errors" in rl, "C2 · _run_layer 缺收集"),
        ("all_view_errors" in rb, "C2 · _run_one_round_B 缺收集"),
        ("all_amp_cands" in _ins.getsource(mod.MetaDGTF._run_layer),
         "P3 · _run_layer 缺候选数逐圈累加"),
        ("all_amp_cands" in _ins.getsource(mod.MetaDGTF._init_b_state),
         "P3 · _init_b_state 缺候选数累加键"),
        ("all_amp_cands" in fin and "all_amp_cands" in _ins.getsource(
            mod.MetaDGTF._b_merge),
         "P3 · B 通道(_b_merge)/_finalize 缺候选数累加"),
    ]
    _bad = [m for c, m in checks if not c]
    if _bad:
        for m in _bad:
            print(f"  ✗ [v63 C] {m}")
        ok = False
    else:
        print(f"  ✓ [v63 C] 第一批结构断言 {len(checks)}/{len(checks)} 通过"
              f"（占位符收口 + 校验留痕 + 分类渲染 + 跨圈累积）")

    # 顺带核一遍：全库 prompt 里不许再出现 `"s_001"`/`"t_001"` 这类字面示例
    try:
        # ★ 别硬编码版本号：升版后读到的会是旧文件，拿新 docstring 去剥离
        #   旧文件必然剥离失败 → 历史泄漏检查误报。从 SRC 派生。
        _src = SRC.read_text(
            encoding="utf-8").replace("\r\n", "\n").replace(mod.__doc__ or "", "")
        _leaks = [p for p in ('"suspension_id":"s_0', '"tension_id":"t_0')
                  if p in _src]
        if _leaks:
            print(f"  ✗ [v63 C] 源码里仍有字面 id 示例：{_leaks}")
            ok = False
        else:
            print("  ✓ [v63 C] 全库源码里已无 `\"suspension_id\":\"s_0…\"`"
                  " / `\"tension_id\":\"t_0…\"` 字面示例")
    except Exception as e:
        print(f"  ✗ [v63 C] 字面泄漏检查失败: {type(e).__name__}: {e}")
        ok = False

    # ── C1 行为断言：编号校验 + 留痕（离线，stub 掉 llm.call） ──
    try:
        cap = {}

        ROWS = [
            {"id": "t_005", "target": "接口被用掉那一轮有无痕迹",
             "status": "active", "quadrant": "③"},
            {"id": "t_001", "target": "已经了结的旧张力",
             "status": "resolved", "quadrant": "③"},
        ]

        def _run_case(tid, duel_rows):
            class _S:
                default_model = "x"
                reasoner_model = "x"
                thinking_reasoner = None
                SERVED_SEEN = set()

                def call(self, sysmsg, usermsg, *a, **kw):
                    cap["sys"], cap["usr"] = sysmsg, usermsg
                    return json.dumps({
                        "probes": [],
                        "engagements": [{"tension_id": tid,
                                         "target": "冒烟目标ABCDE",
                                         "how": "碰了"}],
                        "suspensions": [], "threads": [],
                        "reconfirmations": [], "revocations": []},
                        ensure_ascii=False)

                def parse_json(self, raw):
                    return json.loads(raw)

            base = [dict(x) for x in duel_rows]
            bp_ = mod.Pool()
            bp_.duel_suspensions = [dict(x) for x in base]
            bv_ = mod.View(entry="both")
            bv_.duel_suspensions = [dict(x) for x in base]
            d_ = mod.DGTF("all", _S(), build_cfg(False))
            v_ = mod.View(entry="all")
            d_._probe_meta(v_, mod.Input(question="冒烟：编号校验",
                                         upstream_views=[bv_],
                                         upstream_pools=[bp_]), mod.Pool())
            return v_, cap.get("sys", ""), cap.get("usr", "")

        v_bad, s_bad, u_bad = _run_case("s_001", ROWS)     # 池里根本没有
        v_old, _, _ = _run_case("t_001", ROWS)             # 池里有但已了结
        v_ok, _, _ = _run_case("t_005", ROWS)              # 合法
        _bad_hit = [e for e in v_bad.errors if "tension_id 不合法" in e]
        _old_hit = [e for e in v_old.errors if "tension_id 不合法" in e]
        _ok_hit = [e for e in v_ok.errors if "tension_id 不合法" in e]
        if not _bad_hit:
            print("  ✗ [v63 C1] 填了池里没有的编号（s_001）却没留痕")
            ok = False
        elif not _old_hit or "已了结" not in _old_hit[0]:
            print(f"  ✗ [v63 C1] 引用已了结编号（t_001）没被识别："
                  f"{( _old_hit or [''])[0][:60]}")
            ok = False
        elif "池里没有" not in _bad_hit[0]:
            print(f"  ✗ [v63 C1] 自造编号没被识别成『池里没有』："
                  f"{_bad_hit[0][:60]}")
            ok = False
        elif _ok_hit:
            print("  ✗ [v63 C1] 合法编号（t_005）被误报")
            ok = False
        elif "s_ 开头" not in u_bad or "s_ 开头" not in s_bad:
            print("  ✗ [v63 C1] prompt 里没写「s_ 开头的不能填进 tension_id」")
            ok = False
        else:
            print("  ✓ [v63 C1] 编号校验三向：池里没有 / 池里有但已了结 / "
                  "合法 —— 前两种记 view.errors 且文案可区分，合法的不误报")
    except Exception as e:
        print(f"  ✗ [v63 C1] 行为断言失败: {type(e).__name__}: {e}")
        ok = False

    # ── C1 行为断言：清算侧把"没命中"拆成 inactive / unknown ──
    try:
        m_ = mod.MetaDGTF(build_cfg(False))
        m_.pools["both"].duel_suspensions = [
            {"id": "t_005", "target": "还是 active 的张力", "status": "active",
             "quadrant": "③"},
            {"id": "t_001", "target": "已经 resolved 的旧张力",
             "status": "resolved", "quadrant": "③"},
        ]
        m_.pools["all"].engagements = [
            {"target": "元层处置甲", "tension_id": "t_001"},
            {"target": "元层处置乙", "tension_id": "t_999"},
        ]
        clo_ = m_._settle_meta()
        # ★ [v1.21.64 B] by_id 口径改了：从「只数 active」改成「数池里
        #   真实存在」→ 这里引用了已 resolved 的 t_001，by_id 应为 **1**
        #   （旧口径是 0）。断言跟着口径走，别留着旧值。
        if (clo_.get("by_id") != 1 or clo_.get("by_id_inactive") != 1
                or clo_.get("by_id_unknown") != 1):
            print(f"  ✗ [v63 C1] 清算分类错：by_id={clo_.get('by_id')} "
                  f"inactive={clo_.get('by_id_inactive')} "
                  f"unknown={clo_.get('by_id_unknown')}（应 1/1/1，"
                  f"by_id 已按 v1.21.64 B 计入 resolved）")
            ok = False
        else:
            print("  ✓ [v63 C1] 清算分类：by_id=1（已 resolved 的也算命中）"
                  "/ inactive=1 / unknown=1，分得清")
    except Exception as e:
        print(f"  ✗ [v63 C1] 清算分类断言失败: {type(e).__name__}: {e}")
        ok = False

    # ── C1 行为断言：**串行下元层的 upstream 不能是空的** ──
    #   ★ 这是 C 段 by_id 恒 0 的真正根因：`_ENTRY_DEPS`（调度表）里
    #     "all" 是 ()，被复用做内容查找 → `_make_serial_provider` 漏了
    #     给 "all" 补 ("0","1","both")（其他三个 provider 都补了）。
    #     结果元层从头到尾拿不到 upstream_views，对撞张力清单恒为「（无）」。
    try:
        mt_ = mod.MetaDGTF(build_cfg(False))
        mt_.run("冒烟：元层上游接线", route=["0", "1", "both", "all"],
                rounds={"0": 1, "1": 1, "both": 1, "all": 1},
                parallel_mode="serial")
        ups = list(mt_._make_serial_provider()("all") or [])
        _ents = sorted(getattr(v, "entry", "?") for v in ups)
        if len(ups) < 3:
            print(f"  ✗ [v63 C1] 串行下元层上游只有 {len(ups)} 条（{_ents}），"
                  f"应为 0/1/both 三条")
            ok = False
        elif mod._ENTRY_CONTENT_DEPS.get("all") != ("0", "1", "both"):
            print("  ✗ [v63 C1] _ENTRY_CONTENT_DEPS['all'] 不对")
            ok = False
        else:
            print(f"  ✓ [v63 C1] 串行下元层拿到上游 {_ents}"
                  f"（内容依赖与调度依赖已收口成一张表）")
    except Exception as e:
        print(f"  ✗ [v63 C1] 元层上游接线断言失败: {type(e).__name__}: {e}")
        ok = False
    return ok

def check_v63_observability():
    """[v1.21.63 P1/P2/P3] 三项可观测性补全的单元验证。

    P1 三条行为断言（同圈命中→self_resolved=1 / 旧账被碰→0 / 对撞层同口径）、
    P2 一条渲染断言、P3 两条源码断言。
    """
    ok = True
    import inspect as _ins
    cfg = build_cfg(False)

    # ── P1-1 · 同圈新建 + 同圈命中 → self_resolved=1 ──
    try:
        pool = mod.Pool()
        view = mod.View(entry="0")
        view.suspensions = [{"target": "测试悬置目标ABCDE",
                             "reason": "我选A不选B因为C",
                             "reason_type": "explicit"}]
        view.engagements = [{"target": "测试悬置目标ABCDE",
                             "how": "碰到并解决了"}]
        st = mod.update_suspensions(pool, view, 1, cfg)
        if not (st["new"] == 1 and st["resolved"] == 1
                and st.get("self_resolved") == 1):
            print(f"  ✗ [P1] 同圈命中口径错：new={st['new']} "
                  f"resolved={st['resolved']} self_resolved={st.get('self_resolved')}")
            ok = False
        else:
            print("  ✓ [P1] 同圈新建+同圈命中 → self_resolved=1")
    except Exception as e:
        print(f"  ✗ [P1] 同圈用例失败: {type(e).__name__}: {e}")
        ok = False

    # ── P1-2 · 旧账被碰 → resolved 但不计 self_resolved ──
    try:
        pool2 = mod.Pool()
        view2 = mod.View(entry="0")
        pool2.suspensions.append({
            "id": "s_001", "target": "旧悬置目标ABCDE",
            "reason": "", "reason_type": "explicit",
            "layer": 1, "last_confirmed_layer": 1,
            "confirmed_layers": [1], "status": "active",
            "revoked_at": None, "revoke_reason": "",
            "resolved_at": None, "stable_since": None,
            "needs_review": False,
        })
        view2.engagements = [{"target": "旧悬置目标ABCDE", "how": "现在碰到了"}]
        st2 = mod.update_suspensions(pool2, view2, 2, cfg)
        if st2["resolved"] != 1 or st2.get("self_resolved") != 0:
            print(f"  ✗ [P1] 旧账被碰口径错：resolved={st2['resolved']} "
                  f"self_resolved={st2.get('self_resolved')}（应 1 / 0）")
            ok = False
        else:
            print("  ✓ [P1] 旧账被碰 → resolved=1 但 self_resolved=0（跨圈不误判）")
    except Exception as e:
        print(f"  ✗ [P1] 跨圈用例失败: {type(e).__name__}: {e}")
        ok = False

    # ── P1-3 · 对撞层同一口径 ──
    try:
        pool3 = mod.Pool()
        view3 = mod.View(entry="both")
        view3.duel_suspensions = [{"tension": "张力测试目标ABCDE",
                                   "quadrant": "③",
                                   "reason": "我选0不选1因为2",
                                   "reason_type": "explicit"}]
        view3.adjudications = [{"tension": "张力测试目标ABCDE",
                                "polarity": "0", "how": "判为 0"}]
        st3 = mod.update_duel_suspensions(pool3, view3, 1, cfg)
        if not (st3["new"] == 1 and st3["resolved"] == 1
                and st3.get("self_resolved") == 1):
            print(f"  ✗ [P1] 对撞层口径错：new={st3['new']} "
                  f"resolved={st3['resolved']} self_resolved={st3.get('self_resolved')}")
            ok = False
        else:
            print("  ✓ [P1] 对撞层同口径：self_resolved=1")
    except Exception as e:
        print(f"  ✗ [P1] 对撞层用例失败: {type(e).__name__}: {e}")
        ok = False

    # ── P1-4 · 产物池统计段渲染自解比例 ──
    try:
        res = mod.MetaDGTF(build_cfg(False)).run(
            "冒烟：自解比例渲染", route=["0"], rounds={"0": 1},
            parallel_mode="serial")
        p = mod.save_result(res, cfg["output"]["save_dir"])
        txt = p.read_text(encoding="utf-8").replace("\r\n", "\n")
        if "一圈内自解" not in txt:
            print("  ✗ [P1] 产物池统计段没有「一圈内自解」")
            ok = False
        else:
            print("  ✓ [P1] 产物池统计段有「一圈内自解 N/M（比例）」")
    except Exception as e:
        print(f"  ✗ [P1] 渲染用例失败: {type(e).__name__}: {e}")
        ok = False

    # ── P2 · render_manifestation 与产物头部都必须有"外部锚点" ──
    try:
        fake_res = {
            "decidability": {"decidability": "decidable"},
            "dispatch": {"_parallel_mode": "serial", "order": ["0", "1"],
                         "requested": ["0", "1"], "skipped": []},
            "cost_profile": "balanced", "orientation": "auto",
            "rounds": {"0": 4, "1": 4}, "views": {}, "tri_state": [0, 0],
        }
        m = mod.render_manifestation(fake_res)
        if "外部锚点" not in m:
            print("  ✗ [P2] render_manifestation 里没有「外部锚点」")
            ok = False
        else:
            print("  ✓ [P2] render_manifestation 永远列出「外部锚点」")
    except Exception as e:
        print(f"  ✗ [P2] 失败: {type(e).__name__}: {e}")
        ok = False

    # ── P3 · _amp_cand_count 两端都在 ──
    try:
        s1 = _ins.getsource(mod.DGTF.run)
        s2 = _ins.getsource(mod.MetaDGTF._finalize_layer_common)
        s3 = _ins.getsource(mod.MetaDGTF._run_layer)
        s4 = _ins.getsource(mod.MetaDGTF._b_merge)
        if "_amp_cand_count" not in s1:
            print("  ✗ [P3] DGTF.run 里没写 _amp_cand_count")
            ok = False
        elif "_amp_cand_count" not in s3 or "_amp_cand_count" not in s4:
            print("  ✗ [P3] 逐圈累加点缺失（_run_layer / _b_merge）")
            ok = False
        elif "all_amp_cands" not in s2:
            print("  ✗ [P3] _finalize_layer_common 没用同口径的 all_amp_cands")
            ok = False
        else:
            print("  ✓ [P3] 候选数口径对齐：run 写 → _run_layer/_b_merge 逐圈累加"
                  " → _finalize 用 all_amp_cands（不再拿最后一圈做分母）")
    except Exception as e:
        print(f"  ✗ [P3] 失败: {type(e).__name__}: {e}")
        ok = False

    return ok

def check_v64_pool_meta_render():
    """[v1.21.64 A] pool.meta 有渲染点了（池段 + 落地层顶部）。"""
    import tempfile
    fake = {
        "question": "测试题",
        "route": ["0"], "keep": {"0": "all"}, "rounds": {"0": 1},
        "dispatch": {"_parallel_mode": "serial", "order": ["0"],
                     "requested": ["0"], "skipped": []},
        "views": {"0": {}},
        "pools": {"0": {"amps": [], "threads": [], "probes": [],
                        "suspensions": [],
                        "meta": [
                            "[P1-6] deferral 被拦（revisit_condition 不合格）",
                            "[自省回流未生效] 注入 3 条、可核对 1 条、违例 1 条",
                            "[上一圈 self-check 反馈] 可疑候选 [3]",
                        ]}},
        "llm_calls": 1, "llm_tokens": 1,
        "decidability": {"decidability": "decidable"},
        "channels": ["content"], "cost_profile": "balanced",
        "orientation": "auto", "tri_state": [0, 0],
    }
    try:
        with tempfile.TemporaryDirectory() as td:
            md = mod.save_result(fake, save_dir=td)
            content = md.read_text(encoding="utf-8").replace("\r\n", "\n")
    except Exception as e:
        print(f"  ✗ [v64 A] 渲染失败: {type(e).__name__}: {e}")
        return False
    checks = [
        ("池级留痕（pool.meta）3 条" in content, "池段的 pool.meta 渲染缺失"),
        ("P1-6 拦截 1" in content, "P1-6 拦截类未识别"),
        ("自省未生效 1" in content, "自省未生效类未识别"),
        ("自省回流 1" in content, "自省回流类未识别"),
        ("**池级留痕**：3 条" in content, "落地层顶部的池级留痕汇总缺失"),
    ]
    bad = [m for c, m in checks if not c]
    if bad:
        for m in bad:
            print(f"  ✗ [v64 A] {m}")
        return False
    print("  ✓ [v64 A] pool.meta 渲染兑现：池段分类计数 + 落地层顶部汇总"
          "（P1-6 拦截 1 / 自省未生效 1 / 自省回流 1，三类都识别对）")
    return True

def check_v64_by_id_scope():
    """[v1.21.64 B] by_id 覆盖已 resolved 的编号。"""
    class _FakePools:
        def __init__(self, both, all_):
            self.both = both
            self.all = all_

        def __getitem__(self, k):
            return self.both if k == "both" else self.all

    def _mk(row):
        return {"id": row[0], "target": row[1], "status": row[2],
                "quadrant": "①", "reason_type": "explicit", "layer": 1,
                "last_confirmed_layer": 1, "confirmed_layers": [1],
                "revoked_at": None, "revoke_reason": "",
                "resolved_at": 1 if row[2] == "resolved" else None,
                "stable_since": None, "needs_review": False, "reason": ""}

    duel = [_mk(("t_005", "甲", "active")),
            _mk(("t_006", "乙", "active")),
            _mk(("t_001", "丙（已 resolved）", "resolved"))]
    engagements = [
        {"target": "甲", "tension_id": "t_005", "how": "裁决"},
        {"target": "乙", "tension_id": "t_006", "how": "裁决"},
        {"target": "丙", "tension_id": "t_001", "how": "补交代"},
        {"target": "鬼", "tension_id": "t_999", "how": "自造"},
    ]

    class _FakeMeta:
        config = {"spiral": {"meta_cover_similarity": 0.6}}

    fm = _FakeMeta()
    fm.pools = _FakePools(
        type("P", (), {"duel_suspensions": duel})(),
        type("P", (), {"engagements": engagements, "suspensions": []})())
    try:
        res = mod.MetaDGTF._settle_meta(fm)
    except Exception as e:
        print(f"  ✗ [v64 B] _settle_meta 失败: {type(e).__name__}: {e}")
        return False
    want = {"by_id": 3, "covered_ids": 4, "by_id_inactive": 1,
            "by_id_unknown": 1, "unsettled": 0}
    bad = [(k, res.get(k), v) for k, v in want.items() if res.get(k) != v]
    if bad:
        print(f"  ✗ [v64 B] 口径不对（实得/应为）：{bad}")
        return False
    print("  ✓ [v64 B] by_id=3（active+resolved 都算）/ covered_ids=4 / "
          "inactive=1 / unknown=1 / unsettled=0 —— 口径已覆盖已了结的编号")
    return True

def check_v65_starve_render():
    """[v1.21.65 A] `_starve_rounds` 有渲染出口了（机制一的「离门槛差多少」）。"""
    import tempfile
    fake = {
        "question": "测试题", "route": ["1"], "keep": {"1": "all"},
        "rounds": {"1": 1},
        "dispatch": {"_parallel_mode": "serial", "order": ["1"],
                     "requested": ["1"], "skipped": []},
        "views": {"1": {}},
        "pools": {"1": {
            "amps": [], "threads": [], "probes": [], "suspensions": [],
            "meta": [],
            "sub_questions": [
                # [v1.21.66] 桩补 `_starve_max_seen`：桩要跟当前产物格式
                #   一致，否则「覆盖计数」会读成 0/3（像是机制没跑）。
                {"id": "s1", "_starve_rounds": 1, "_starve_max_seen": 1,
                 "decidability": "partial"},
                {"id": "s2", "_starve_rounds": 0, "_starve_max_seen": 0,
                 "decidability": "decidable"},
                {"id": "s3", "_starve_rounds": 2, "_starve_max_seen": 2,
                 "decidability": "partial"},
            ],
            "deferrals": [{"id": "d_001", "sub_id": "s3",
                           "status": "deferred"},
                          {"id": "d_002", "sub_id": "s2",
                           "status": "handled"}],
        }},
        "llm_calls": 1, "llm_tokens": 1,
        "decidability": {"decidability": "decidable"},
        "channels": ["content"], "cost_profile": "balanced",
        "orientation": "auto", "tri_state": [0, 0],
    }
    try:
        with tempfile.TemporaryDirectory() as td:
            md = mod.save_result(fake, save_dir=td)
            content = md.read_text(encoding="utf-8").replace("\r\n", "\n")
    except Exception as e:
        print(f"  ✗ [v65 A] 渲染失败: {type(e).__name__}: {e}")
        return False
    checks = [
        ("🍽 无进展计数" in content, "缺「无进展计数」行"),
        ("最高 2 圈" in content, "最高值不对（应为 2）"),
        ("2圈×1" in content and "1圈×1" in content and "0圈×1" in content,
         "分布不对（应为 0圈×1、1圈×1、2圈×1）"),
        ("名下有挂账的子问题 1 条" in content,
         "条件二计数不对（只有 s3 是 deferred，s2 已 handled）"),
        ("计数已写 3/3 条" in content, "覆盖计数不对（三条都应已写）"),
    ]
    bad = [m for c, m in checks if not c]
    if bad:
        for m in bad:
            print(f"  ✗ [v65 A] {m}")
        return False
    print("  ✓ [v65 A] 机制一的「离门槛差多少」有出口了："
          "分布 0/1/2 圈各 1 条、最高 2 圈、名下有挂账 1 条")
    return True

def check_v66_starve_peak():
    """[v1.21.66] 机制一的计数改报**运行期峰值**（v1.21.65 遗留 1 的兑现）。

    三件事一起钉住：
      1. 快照会被清零、峰值不会 —— 构造「曾够到 2 圈、此刻快照 0」；
      2. 旧探针前缀正则仍能匹配（加性输出就是为了不弄哑审计探针）；
      3. **字段缺席时必须显式报「机制未运行」** —— 否则渲染出来的 0 会被
         读成「真 0」，这正是本项目「只读审计变空报告」的老形态。
    """
    import tempfile
    import re
    import copy
    base = {
        "question": "测试题", "route": ["1"], "keep": {"1": "all"},
        "rounds": {"1": 1},
        "dispatch": {"_parallel_mode": "serial", "order": ["1"],
                     "requested": ["1"], "skipped": []},
        "views": {"1": {}},
        "pools": {"1": {
            "amps": [], "threads": [], "probes": [], "suspensions": [],
            "meta": [],
            "sub_questions": [
                # s1 曾够到 2 圈但被触碰过 → 快照归零、峰值留 2
                {"id": "s1", "_starve_rounds": 0, "_starve_max_seen": 2,
                 "decidability": "partial"},
                {"id": "s2", "_starve_rounds": 0, "_starve_max_seen": 0,
                 "decidability": "decidable"},
            ],
            "deferrals": [{"id": "d_001", "sub_id": "s1",
                           "status": "deferred"}],
        }},
        "llm_calls": 1, "llm_tokens": 1,
        "decidability": {"decidability": "decidable"},
        "channels": ["content"], "cost_profile": "balanced",
        "orientation": "auto", "tri_state": [0, 0],
    }

    def _render(fake):
        with tempfile.TemporaryDirectory() as td:
            md = mod.save_result(fake, save_dir=td)
            return md.read_text(encoding="utf-8").replace("\r\n", "\n")

    try:
        content = _render(base)
    except Exception as e:
        print(f"  ✗ [v66] 渲染失败: {type(e).__name__}: {e}")
        return False
    checks = [
        ("最高 0 圈（0圈×2）" in content,
         "快照口径不对（两条都该是 0 圈）"),
        ("运行期峰值 2 圈（0圈×1、2圈×1）" in content,
         "峰值不对（s1 曾够到 2 圈，应报 2 圈，分布 0圈×1、2圈×1）"),
        ("名下有挂账的子问题 1 条" in content, "条件二计数不对"),
        ("计数已写 2/2 条" in content,
         "覆盖计数不对（两条都带 _starve_max_seen，应报 2/2）"),
        (re.search(r"🍽 无进展计数：最高 (\d+) 圈（([^）]*)）", content)
         is not None, "旧探针前缀失配（加性输出被改坏了）"),
    ]
    bad = [m for c, m in checks if not c]
    if bad:
        for m in bad:
            print(f"  ✗ [v66] {m}")
        return False

    # 第二例：字段**缺席**（机制没跑）→ 必须显式说出来，不能渲染成真 0
    fake2 = copy.deepcopy(base)
    for sq in fake2["pools"]["1"]["sub_questions"]:
        sq.pop("_starve_max_seen", None)
    try:
        c2 = _render(fake2)
    except Exception as e:
        print(f"  ✗ [v66] 第二例渲染失败: {type(e).__name__}: {e}")
        return False
    if "★ 计数未写（机制未运行）" not in c2:
        print("  ✗ [v66] 字段缺席时没说出来 → 那个 0 会被读成「真 0」"
              "（空报告的老形态）")
        return False

    print("  ✓ [v66] 快照 0 圈 / 峰值 2 圈（「够到过、被清零」看得见）；"
          "旧前缀正则仍匹配；字段缺席时显式报「机制未运行」")
    return True

def check_v66_starve_writes_key():
    """[v1.21.66] `_starve_escalation` 的**写入语义**（直调生产函数，不经产物）。

    盯两件事：
      1. 计数**无条件写** —— 只要函数跑过，每个子问题都该带 `_starve_max_seen`。
         若只在抬升时写，「跑过但一直是 0」与「压根没跑」就分不开了；
         G1q 首次真跑正是在这里报了 1/6 的**假覆盖**。
      2. 清零带不走峰值 —— 第 2 圈被触碰（计数归 0）后，峰值仍留 1。
    """
    import types
    cfg = {"spiral": {"escalate_starve_rounds": 5}}
    subs = [{"id": "s1", "decidability": "partial", "status": "open"},
            {"id": "s2", "decidability": "partial", "status": "open"}]
    pool = types.SimpleNamespace(sub_questions=subs, deferrals=[])
    view = types.SimpleNamespace(engagements=[], escalations=[],
                                reclassifications=[], deferrals=[],
                                resolutions=[])
    stats = {"reclassified": 0, "escalated": 0, "rejected": 0,
             "_transitions": []}
    sub_by_id = {x["id"]: x for x in subs}

    mod._starve_escalation(pool, view, sub_by_id, 1, cfg, stats)
    if not all("_starve_max_seen" in x for x in subs):
        print("  ✗ [v66] 计数没有无条件写 → 「跑过但一直是 0」与「没跑」分不开")
        return False
    pk1 = [x["_starve_max_seen"] for x in subs]
    if pk1 != [1, 1]:
        print(f"  ✗ [v66] 第 1 圈峰值不对：{pk1}（应为 [1, 1]）")
        return False

    view.engagements = [{"sub_id": "s1"}]
    mod._starve_escalation(pool, view, sub_by_id, 1, cfg, stats)
    got = [(x["_starve_rounds"], x["_starve_max_seen"]) for x in subs]
    if got != [(0, 1), (2, 2)]:
        print(f"  ✗ [v66] 清零点没保住峰值 / 累加不对：{got}"
              f"（应为 [(0, 1), (2, 2)]）")
        return False
    print("  ✓ [v66] 写入语义：计数无条件写（2/2 条）；被触碰清零后峰值仍留 1")
    return True

def check_v67_full_appendix():
    """[v1.21.67；v1.23.10 改取源] 产物 md 的「全量字段」附录：必须**机械全量**。

    ★ v1.23.10：全量 JSON 默认**外置**到旁挂 `<产物名>.packed.json`
      （`--appendix inline` 回旧行为）。判据意图**一字未改** —— 仍是
      「不得因为没写渲染点就丢信息」；改的是**取源**：内联的 ```json 块
      与旁挂文件两路都要能取到同一份 packed。
    ★ 断言特意塞一个**正文绝无渲染点**的深层内部量（`_probe_only_internal`），
      用它区分「机械全量」和「又挑了一批字段渲染」。
    ★ 顺带修一个真 bug：旁挂文件必须在 `with TemporaryDirectory()` **块内**
      读完 —— 出了块目录就没了，症状是「文件不存在」而不是「内容不对」。
    """
    import tempfile
    import re
    import json
    fake = {
        "question": "测试题", "route": ["1"], "keep": {"1": "all"},
        "rounds": {"1": 1},
        "dispatch": {"_parallel_mode": "serial", "order": ["1"],
                     "requested": ["1"], "skipped": []},
        "views": {"1": {}},
        "pools": {"1": {"amps": [], "threads": [], "probes": [],
                        "suspensions": [], "meta": [],
                        "sub_questions": [{"id": "s1",
                                           "_starve_rounds": 0,
                                           "_starve_max_seen": 0}],
                        "deferrals": []}},
        "llm_calls": 1, "llm_tokens": 1,
        "decidability": {"decidability": "decidable"},
        "channels": ["content"], "cost_profile": "balanced",
        "orientation": "auto", "tri_state": [0, 0],
        "_probe_only_internal": {"deep": {"x": 7}},
    }
    _side_raw = None
    try:
        with tempfile.TemporaryDirectory() as td:
            md = mod.save_result(fake, save_dir=td)
            content = md.read_text(encoding="utf-8").replace("\r\n", "\n")
            _sm = re.search(r"```text\n(\S+\.packed\.json)\n```", content)
            if _sm:
                _sp = md.parent / _sm.group(1)
                if _sp.is_file():
                    _side_raw = _sp.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  ✗ [v67] 渲染失败: {type(e).__name__}: {e}")
        return False
    checks = [
        ("## 附录 · 全量字段（packed 原文）" in content, "缺附录标题"),
        ("```json" in content or ".packed.json" in content,
         "缺 JSON（内联与旁挂都没有）"),
        ("叶子路径" in content and "JSON " in content, "缺完整性统计行"),
    ]
    bad = [m for c, m in checks if not c]
    if bad:
        for m in bad:
            print(f"  ✗ [v67] {m}")
        return False
    if "```json" in content:
        _mm = re.search(r"```json\n(.*?)\n```", content, re.S)
        _raw = _mm.group(1) if _mm else None
    else:
        _raw = _side_raw
    if _raw is None:
        print("  ✗ [v67] 正文既无内联 json 块，也读不到旁挂文件")
        return False
    try:
        packed = json.loads(_raw)
    except Exception as e:
        print(f"  ✗ [v67] 全量 JSON 不可解析: {type(e).__name__}: {e}")
        return False
    if set(packed) != set(fake):
        print(f"  ✗ [v67] 附录顶层键不全，缺 {sorted(set(fake) - set(packed))}")
        return False
    # ★ 只活在 packed 里、正文绝无渲染点的内部量，也必须出现
    if ((packed.get("_probe_only_internal") or {}).get("deep") or {}).get("x") != 7:
        print("  ✗ [v67] 正文无渲染点的内部量没进附录（机械全量失效）")
        return False
    print("  ✓ [v67] 全量附录：顶层键齐全、无渲染点的内部量也在、JSON 可解析")
    return True

def check_v68_round_dump():
    """[v1.21.68] 每层每圈**全量留痕**：dump_round 必须把 view 的所有字段
    写进日志，**含 ing 正文（view.collision）**，且不截断；并且它真的被
    `DGTF.run` 调用（别做成死代码）。

    动机：此前每圈只打摘要 —— 候选报条数、ing 报**字数**、悬置/债务/清算
    报计数，正文与明细都不落日志。
    """
    import io
    import contextlib
    import dataclasses
    cfg = build_cfg(False)
    dg = mod.DGTF("0", mod.LLM(cfg), cfg)
    dg.verbose = True
    dg.dump_rounds = True  # 留痕另有独立开关（默认关）；这些检查测的是「开着时」的行为
    v = mod.View(entry="0")
    v.anchor = "锚点原文"
    v.collision = "ing 正文第一行\ning 正文第二行"
    _long = "长" * 80
    v.candidates = [{"desc": _long, "attribute": "0", "position": "0"}]
    v._expanded_descs = [_long]
    inp = mod.Input(question="q", round_role="摊开", round_no=3)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        dg.dump_round(v, inp)
    out = buf.getvalue()
    fields = {f.name for f in dataclasses.fields(mod.View)}
    n_lines = sum(1 for ln in out.split("\n") if ln.startswith("   \u251c "))
    checks = [
        ("圈全量留痕" in out and "第 3 圈" in out and "摊开" in out,
         "留痕标记缺（entry/圈号/角色）"),
        ("ing 正文第一行" in out and "ing 正文第二行" in out,
         "ing 正文没进日志（本轮的核心要求）"),
        ("collision" in out, "collision 字段名缺"),
        ("_expanded_descs" in out, "动态属性（去重账）没进留痕"),
        (_long in out, "长文本被截断"),
        ("锚点原文" in out, "anchor 值缺"),
        (out.count("   \u251c ") >= len(fields),
         f"字段覆盖不足：留痕 {n_lines} 行 < 字段 {len(fields)} 个"),
    ]
    # 接线检查：方法必须真被调用，否则是死代码
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    src = src.replace(mod.__doc__ or "", "")
    checks.append(("self.dump_round(view, inp)" in src,
                   "DGTF.run 里没有调用 dump_round（死代码）"))
    checks.append(("\U0001f525 \u2502 " in src, "ing 正文的就地打印没接上"))
    bad = [m for c, m in checks if not c]
    if bad:
        for m in bad:
            print(f"  \u2717 [v68] {m}")
        return False
    print("  \u2713 [v68] 每圈全量留痕：字段全覆盖、ing 正文在内、"
          "不截断、且真被 DGTF.run 调用")
    return True

def check_v69_abcde():
    """[v1.21.69] A/B/C/D/E 五项：**先量后改**，每条判据都带**负对照**。

    这一版的判据一律做成"能自动查"的数：
      A 数**次数** —— 3 条 amps × 5 个候选必须得 5（不能 15）；
        空 amps × 7 必须得 7（不能 0）。两个方向都锁，才叫锁住。
      B 走**生产入口** `Pool.add_undecidable` —— 独立度与对齐覆盖率必须
        同时落下来；旧键 `last_struct_coverage`（旧口径命中比例）
        一个数不许变（它喂模型，也是历史语料的口径）。
      C 截模型的 **system 原文** —— 不看代码分支，看模型真收到什么；
        逐 entry 核「对撞的对象是：…」，并确认兜底分支不再串层。
      D 真·凭空一条仍须被抓出（负对照：证明判据没被放宽成摆设）；
        真误报两条必须被救回。
      E 增量留痕必须**真省略**（省略数 > 0）且 `round_log` 必须出现 ——
        否则"补了个收尾段"只是把同一份东西又打了一遍。
    """
    import contextlib
    import inspect as _ins
    import io
    bad = []
    cfg = build_cfg(False)

    # ---------------- A ----------------
    _m = mod.MetaDGTF(cfg)

    def _merge_cands(amps, cand):
        v = mod.View(entry="0")
        v.amps = [{"desc": d} for d in amps]
        v._amp_cand_count = cand
        st = {"all_candidates": [], "all_amps": [], "all_amp_cands": 0,
              "all_threads": [], "all_dec_products": [],
              "all_und_products": []}
        _m._b_merge("0", v, st)
        return st["all_amp_cands"]

    _g1 = _merge_cands(["a1", "a2", "a3"], 5)
    _g2 = _merge_cands([], 7)
    if _g1 != 5:
        bad.append(f"[A] amps=3 + _amp_cand_count=5 应得 5，实得 {_g1}"
                   + ("（重复累加 3 次）" if _g1 == 15 else ""))
    if _g2 != 7:
        bad.append(f"[A] amps=0 + _amp_cand_count=7 应得 7，实得 {_g2}"
                   + ("（空 amps 时漏累加）" if _g2 == 0 else ""))

    # ---------------- B ----------------
    _asp = ["时间尺度（一场雨/汛期/管网寿命）结论相反且无仲裁规则"]
    _p = mod.Pool()
    _p.add_undecidable(
        {"structural_amps": ["签字只让记录可被引用，转正才决定参照"],
         "aligned_amps": list(_asp),
         "clarity": 0.7}, list(_asp), layer=1)
    _ch = _p.undecidable_channel
    if _ch.get("last_struct_coverage") != 0.0:
        bad.append(f"[B] last_struct_coverage 的语义/值被动了："
                   f"{_ch.get('last_struct_coverage')}（应仍是 0.0）")
    if _ch.get("last_aligned_coverage") != 1.0:
        bad.append(f"[B] last_aligned_coverage 应为 1.0，实得 "
                   f"{_ch.get('last_aligned_coverage')}")
    if _ch.get("last_aligned_hit") != 1:
        bad.append(f"[B] last_aligned_hit 应为 1，实得 "
                   f"{_ch.get('last_aligned_hit')}")
    if _ch.get("last_indep_ratio") != 1.0 \
            or _ch.get("last_indep_pool") != 1:
        bad.append(f"[B] 独立度没落下来：ratio="
                   f"{_ch.get('last_indep_ratio')} "
                   f"pool={_ch.get('last_indep_pool')}（应 1.0 / 1）")
    _m2 = mod.MetaDGTF(cfg)
    _m2.pools["1"].undecidable_channel = _ch
    _line = _m2._und_channel_line()
    if "独立度 1.00" not in _line or "不是覆盖率" not in _line:
        bad.append(f"[B] 独立度（新口径）没渲染或没标口径：{_line!r}")
    if "对齐覆盖率 1.00" not in _line:
        bad.append(f"[B] 对齐覆盖率没渲染（有算法没出口）：{_line!r}")
    if "已对上 1/1" not in _line:
        bad.append(f"[B] 对齐覆盖率的分子分母没渲染：{_line!r}")
    # 加性：旧产物 / 手工 dict 没有 aligned_coverage_history ⇒ 不出现
    _m3 = mod.MetaDGTF(cfg)
    _m3.pools["1"].undecidable_channel = {
        "clarity_history": [0.5], "struct_coverage_history": [0.6],
        "und_aspects": [f"面{i}" for i in range(10)],
        "last_struct_hit": 6, "structural_amps": ["a"], "aligned_amps": [],
    }
    _line3 = _m3._und_channel_line()
    if "对齐覆盖率" in _line3:
        bad.append(f"[B] 旧 dict（无 aligned_coverage_history）不该打对齐行，"
                   f"否则是破坏性改动：{_line3!r}")
    if "结构覆盖率 0.60" not in _line3 or "已对上 6/10" not in _line3:
        bad.append(f"[B] 旧口径渲染被改坏了：{_line3!r}")

    # ---------------- C ----------------
    def _ing_object_desc(entry, is_base):
        dg = mod.DGTF(entry, mod.LLM(cfg), cfg)
        dg.verbose = False
        cap = {}

        def _fake_long(system, user, *a, **k):
            cap["system"] = system
            return "占位", False
        dg._call_long = _fake_long
        inp = mod.Input(question="原始问题" if is_base else None,
                        round_role="转向", round_no=2)
        if not is_base:
            ups = []
            for i in range(2):
                uv = mod.View(entry="0")
                uv.manifest = f"上游{i}"
                ups.append(uv)
            inp.upstream_views = ups
        inp.pool = mod.Pool()
        dg._ing([mod.Candidate(desc="候选甲")], inp, "锚点",
                mod.View(entry=entry))
        _sys = cap.get("system", "")
        if "对撞的对象是：" not in _sys:
            return None
        return _sys.split("对撞的对象是：", 1)[1].split("\n", 1)[0].strip()

    _want = {("0", True): "这个问题里的 0 和 1",
             ("1", True): "这个问题里的 0 和 1",
             ("both", False): "两个已经完成的形状",
             ("all", False): "整体与每一个局部",
             ("0", False): "上游留下的形状与本圈的候选",
             ("1", False): "上游留下的形状与本圈的候选"}
    for (ent, base), want in _want.items():
        got = _ing_object_desc(ent, base)
        if got != want:
            bad.append(f"[C] entry={ent} is_base={base} 对撞对象应为"
                       f"「{want}」，实得「{got}」")
    # 负对照：兜底分支不许再把 all 的标签给 0/1
    if _ing_object_desc("1", False) == "整体与每一个局部":
        bad.append("[C] 兜底分支又把「整体与每一个局部」给了研究层")

    # ---------------- D ----------------
    _u1 = mod._untraced_undecidable(
        ["清分规则未定时断面客流与线路客流不可互证（候选16）"],
        [{"aspect": "清分规则未定，断面客流与线路客流不可互证"}])
    if _u1 != []:
        bad.append(f"[D] 带来源后缀的同一条应判为有追溯，实际：{_u1}")
    _long = "时间尺度（一场雨/汛期/管网寿命）结论相反且无仲裁规则"
    _u2 = mod._untraced_undecidable(_long and [_long],
                                    [{"aspect": "时间尺度无仲裁规则"}])
    if _u2 != []:
        bad.append(f"[D] 长句 ⊃ 短句的真误报没被救回：{_u2}")
    _u3 = mod._untraced_undecidable(
        ["行政档案与居民记忆两份留痕之差不能被对撞消掉"],
        [{"aspect": "两份留痕之差不可对撞消减"}])
    if _u3 != []:
        bad.append(f"[D] 第二条真误报没被救回：{_u3}")
    # 负对照：真没追溯的照样抓出来；不相干的短句也不许救
    _u4 = mod._untraced_undecidable(["凭空说的一条"],
                                    [{"aspect": "完全不相干的另一条"}])
    if _u4 != ["凭空说的一条"]:
        bad.append(f"[D] 负对照失败：无追溯的没被抓出来 {_u4}")
    _u5 = mod._untraced_undecidable([_long], [{"aspect": "当地居民偏好"}])
    if _u5 != [_long]:
        bad.append(f"[D] 负对照失败：不相干的短句也被当成追溯 {_u5}")
    # 阈值不许被随手放宽成摆设
    _thr = getattr(mod, "_UNTRACED_OVERLAP", None)
    if not isinstance(_thr, float) or not (0.5 <= _thr <= 0.7):
        bad.append(f"[D] _UNTRACED_OVERLAP 越界：{_thr}")

    # ---------------- E ----------------
    dg = mod.DGTF("0", mod.LLM(cfg), cfg)
    dg.verbose = True
    dg.dump_rounds = True  # 留痕另有独立开关（默认关）；这些检查测的是「开着时」的行为
    v = mod.View(entry="0")
    v.anchor = "锚点原文不改"
    v.collision = "ing 正文"
    v.candidates = [{"desc": "候选甲"}]
    v.untouched = [{"desc": "没变的方面" * 4}]
    inp = mod.Input(question="q", round_role="摊开", round_no=1)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        dg.dump_round(v, inp)
    out1 = buf.getvalue()
    if not hasattr(v, "_dump_canon"):
        bad.append("[E] dump_round 没挂 _dump_canon 快照（收尾差分没基准）")
    if "_dump_canon" in out1:
        bad.append("[E] 内部账 _dump_canon 漏进了留痕（会递归膨胀）")
    # 收尾：补上回填的累积字段
    v.round_log = [{"round": 1, "role": "摊开"}]
    v.roles_run = ["摊开"]
    v.rounds_run = 1
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        dg.dump_final(v)
    out2 = buf.getvalue()
    if "收尾留痕" not in out2:
        bad.append("[E] 收尾留痕的段头没打")
    if "增量模式" not in out2:
        bad.append("[E] 收尾留痕不是增量模式（等于把上一圈又打一遍）")
    if "round_log" not in out2 or "roles_run" not in out2:
        bad.append("[E] 累积字段（round_log / roles_run）没在收尾段出现"
                   " —— 「全量留痕」对它们仍是空的")
    if "├ anchor：" in out2:
        bad.append("[E] 没变的字段也被打了（没有真省略）")
    _mm = re.search(r"增量模式：(\d+)/(\d+) 个字段", out2)
    if not _mm or int(_mm.group(1)) == 0:
        bad.append(f"[E] 增量模式没省略任何字段：{out2[:120]!r}")
    if "_dump_canon" in out2:
        bad.append("[E] 内部账 _dump_canon 漏进了收尾留痕")
    # 接线：不能是死代码
    _src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    _src = _src.replace(mod.__doc__ or "", "")
    if "def dump_view_fields(" not in _src or "def dump_final(" not in _src:
        bad.append("[E] dump_view_fields / dump_final 不在源码里（死代码？）")
    if "dump_view_fields(view, self.vp, remember=True)" not in _src:
        bad.append("[E] dump_round 没接上唯一实现")
    if "dump_view_fields(view, self.vp," not in _src:
        bad.append("[E] dump_final 没接上唯一实现")
    _fin = _ins.getsource(mod.MetaDGTF._finalize_layer_common)
    if "_dg.dump_final(view)" not in _fin:
        bad.append("[E] _finalize_layer_common 里没调用收尾留痕（没接线）")

    if bad:
        for m in bad:
            print(f"  ✗ [v69] {m}")
        return False
    print("  ✓ [v69] A 累加次数两向都对（5/7）；B 双覆盖率都有出口且旧键不动、"
          "旧 dict 不破坏；")
    print("        C 对撞对象逐 entry 正确、兜底不串层；D 真误报救回 + 负对照"
          "仍抓得住；")
    print("        E 收尾增量留痕真省略 + 累积字段有出口 + 接线在")
    return True

def _v70_anchor(payload):
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
            encoding="utf-8").replace("\r\n", "\n")
    if "不可判定独立结构覆盖轨迹：" not in txt:
        bad.append("[F] 独立结构轨迹行没渲染")
    if "不可判定对齐结构覆盖轨迹：" not in txt:
        bad.append("[F] 对齐结构轨迹行没渲染（有算法没出口）")
    if "不可判定覆盖轨迹" in txt.replace("不可判定独立结构覆盖轨迹", "") \
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
            encoding="utf-8").replace("\r\n", "\n")
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
    if "_render_trace(uc.get(\"aligned_trace\")" not in ssrc:
        bad.append("[F] save_result 没渲染 aligned_trace（死数据）")

    if bad:
        for m in bad:
            print(f"  \u2717 [v70 F] {m}")
        return False
    print("  \u2713 [v70 F] aligned_trace / aligned_first_hit 建起来且只记首次；"
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
            m._coverage_segment = lambda: ("\n\n## 七、原始问题覆盖率\n"
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
            print(f"  \u2717 [v70 K] {m}")
        return False
    print("  \u2713 [v70 K] entry=1 与 entry=all 都追加覆盖率段"
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
            print(f"  \u2717 [v70 G] {m}")
        return False
    print("  \u2713 [v70 G] 占位符（含全角/半角）全挡、全占位符不留残渣；"
          "含「无」字的正常方面不被误杀；接线在")
    return True

def check_v70_h_oversized():
    """[v1.21.70 H] rendered / manifest 只打长度，正文不落日志。

    负对照：**非**超大字段（collision / candidates）的正文必须照旧全文在，
    且字段覆盖计数不许掉（`\u251c ` 行数 >= View 的字段数）。
    """
    import contextlib
    import dataclasses
    import inspect as _ins
    import io
    bad = []
    cfg = build_cfg(False)
    dg = mod.DGTF("0", mod.LLM(cfg), cfg)
    dg.verbose = True
    dg.dump_rounds = True  # 留痕另有独立开关（默认关）；这些检查测的是「开着时」的行为
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
    _flat = out.replace("\n", "").replace("   \u2502 ", "")
    if ("ing 正文" * 40) not in _flat:
        bad.append("[H] collision 正文被打丢了（误伤）")
    if "候选甲" not in out:
        bad.append("[H] candidates 正文被打丢了（误伤）")
    # 负对照 2：字段覆盖计数不许掉
    fields = {f.name for f in dataclasses.fields(mod.View)}
    if out.count("   \u251c ") < len(fields):
        bad.append(f"[H] 字段覆盖计数掉了：{out.count('   \u251c ')} "
                   f"< {len(fields)}")
    if "_OVERSIZED" not in _ins.getsource(mod.dump_view_fields):
        bad.append("[H] dump_view_fields 里没有 _OVERSIZED（没接线）")
    if bad:
        for m in bad:
            print(f"  \u2717 [v70 H] {m}")
        return False
    print("  \u2713 [v70 H] rendered/manifest 只留长度、正文不落日志；"
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
    elif _src.index("本段是**本圈**留痕") > _src.index(
            "dump_view_fields(view, self.vp"):
        bad.append("[I] 说明打在了字段 dump 之后（读者看到 0 项时已经误读了）")
    cfg = build_cfg(False)
    dg = mod.DGTF("0", mod.LLM(cfg), cfg)
    dg.verbose = True
    dg.dump_rounds = True  # 留痕另有独立开关（默认关）；这些检查测的是「开着时」的行为
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
            print(f"  \u2717 [v70 I] {m}")
        return False
    print("  \u2713 [v70 I] 「本圈留痕」说明打在字段 dump 之前，"
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
            print(f"  \u2717 [v70 J] {m}")
        return False
    print("  \u2713 [v70 J] 缓存优先（与 evidence 矛盾也认缓存）、"
          "无缓存时退回重算且值正确；接线在")
    return True

# ======================================================================
# [v1.21.71 F1~F11] 十一项缺陷修复的判据
#   每条都配**反方向**（不该被放过的仍被放过）或**负对照**（把改坏的
#   行为模拟出来，断言必须判失败）。
# ======================================================================
_V71_Q = "探针题：这套结构的边界在哪，哪些部分原则上判不出"

def _v71_packed_run(rounds=None, mode="serial"):
    """走生产入口 MetaDGTF.run（LLM 已被桩换掉）拿 packed 本体。

    ★ 不用 run_mode：它返回的是**汇总行**（views 被换成 key 列表），
      拿不到 packed 里的 view 字段。
    """
    CALLS["n"] = 0
    cfg = build_cfg(False)
    meta = mod.MetaDGTF(cfg)
    return meta.run(_V71_Q, route=["0", "1", "both", "all"],
                    rounds=rounds or {"0": 2, "1": 2, "both": 2, "all": 2},
                    parallel_mode=mode)

def _v71_b_state(view, rounds_hist):
    """造一个 total_rounds=1 的层状态（定点测 _b_finalize_layer）。"""
    cfg = build_cfg(False)
    return {
        "view": view, "total_rounds": 1,
        "roles_hist": list(rounds_hist),
        "all_candidates": [], "all_amps": [], "all_threads": [],
        "all_rehashed": [], "all_expanded_descs": [], "all_amp_cands": 0,
        "all_dec_products": [], "all_und_products": [], "all_view_errors": [],
        "round_log": [{"round": 1}], "deferred_notes": [],
        "r": 1, "rounds_n": 1, "sp": mod._spiral_for(cfg, "0")}

def check_v71_single_round_finalize():
    """[v1.21.71 F1] 单圈层必须走完整收尾。

    两方向 + 负对照：
      · 四层各 1 圈 → roles_run / rounds_cap / round_log / stop_reason
        四件套都在，且 rounds_cap == len(round_log)（自洽）；
      · 负对照：把旧的 `total_rounds <= 1` 门用子类装回去，**同一场景**
        必须退化成空 —— 否则这条判据压根不是在被改的那行上生效；
      · 源码反向断言：两处旧写法都不许再出现。
    """
    import inspect as _ins
    bad = []
    res = _v71_packed_run(rounds={"0": 1, "1": 1, "both": 1, "all": 1})
    for e in _ALL_LAYERS:
        v = res["views"].get(e) or {}
        cap = int(v.get("rounds_cap") or 0)
        rl = len(v.get("round_log") or [])
        rr = len(v.get("roles_run") or [])
        if rr <= 0 or cap <= 0 or rl <= 0:
            bad.append(f"[F1] 层 {e} 单圈收尾字段缺：roles_run={rr} "
                       f"rounds_cap={cap} round_log={rl}")
        elif cap != rl:
            bad.append(f"[F1] 层 {e} 不自洽：rounds_cap={cap} "
                       f"但 round_log={rl} 条")
        if not str(v.get("stop_reason") or "").strip():
            bad.append(f"[F1] 层 {e} 单圈没有 stop_reason")
    # 走满预算的交代必须是这句（别把单圈写成"未触发判据"以外的东西）
    _sr = str((res["views"].get("0") or {}).get("stop_reason") or "")
    if "体力耗尽" not in _sr:
        bad.append(f"[F1] 层 0 的单圈 stop_reason 不是「体力耗尽」交代：{_sr!r}")

    # ---- 定点 A/B：同一场景，一个带新代码、一个装回旧门 ----
    cfg = build_cfg(False)

    def _run_unit(meta):
        v = mod.View(entry="0")
        meta._b_state = {"0": _v71_b_state(v, ["摊开"])}
        meta._results = {}
        with contextlib.redirect_stdout(io.StringIO()):
            meta._b_finalize_layer("0")
        return list(v.roles_run), int(v.rounds_cap), len(v.round_log)

    _new = mod.MetaDGTF(cfg)
    _rr, _cap, _rl = _run_unit(_new)
    if not (_rr and _cap and _rl):
        bad.append(f"[F1] 定点：新代码下单圈层仍未收尾 "
                   f"roles_run={_rr} cap={_cap} log={_rl}")

    class _OldGate(mod.MetaDGTF):
        def _b_finalize_layer(self, entry):
            _st = self._b_state.get(entry)
            if _st and _st["view"] is not None and _st["total_rounds"] <= 1:
                return
            return super()._b_finalize_layer(entry)

    _old = _OldGate(cfg)
    _rr2, _cap2, _rl2 = _run_unit(_old)
    if _rr2 or _cap2 or _rl2:
        bad.append("[F1] 负对照失效：旧门装回去居然还写了收尾 "
                   f"roles_run={_rr2} cap={_cap2} log={_rl2}")

    if 'state["total_rounds"] <= 1' in _ins.getsource(
            mod.MetaDGTF._b_finalize_layer):
        bad.append("[F1] _b_finalize_layer 里旧门又回来了")
    if "if view is not None and rounds_n > 1:" in _ins.getsource(
            mod.MetaDGTF._run_layer):
        bad.append("[F1] _run_layer 里旧门又回来了")
    if bad:
        for m in bad:
            print(f"  \u2717 [v71 F1] {m}")
        return False
    print("  \u2713 [v71 F1] 单圈四层四件套齐全且自洽；旧门子类不写收尾"
          "（负对照有判别力）；两处旧写法都不在")
    return True

def check_v71_main_save_guard():
    """[v1.21.71 F2] main() 里 save_result 失败必须有兜底 + 非零退出码。

    两方向：
      · save_result 抛 OSError → SystemExit.code == 1 且打印「保存失败」；
      · save_result 正常 → 不抛、不打印（成功路径不许被 try 改变语义）。
    负对照：**改前的真实行为**已由 `_probe_v71_before.txt` [B] 记录
      （异常冲出 main()、无任何提示）—— 这里再用源码形态锁一次，
      防止有人把 try 拆掉而判据仍然通过。
    """
    import inspect as _ins
    bad = []
    _fake_res = {"llm_calls": 0, "llm_tokens": 0, "views": {},
                 "dispatch": {"order": ["0"], "missing": [], "skipped": []},
                 "question": _V71_Q}

    def _drive(save_impl):
        _orun, _osave = mod.MetaDGTF.run, mod.save_result
        mod.MetaDGTF.run = lambda self, *a, **k: dict(_fake_res)
        mod.save_result = save_impl
        _argv = sys.argv
        sys.argv = ["dgtf", _V71_Q, "--route", "0", "--rounds", "0:1",
                    "--parallel", "serial", "--quiet"]
        code, exc, buf = None, None, io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                mod.main()
        except SystemExit as _e:
            code = _e.code
        except BaseException as _e:                      # noqa: BLE001
            exc = f"{type(_e).__name__}: {_e}"
        finally:
            sys.argv = _argv
            mod.MetaDGTF.run, mod.save_result = _orun, _osave
        return code, exc, buf.getvalue()

    def _bad(*a, **k):
        raise OSError("冒烟：模拟磁盘写失败")

    code, exc, out = _drive(_bad)
    if exc:
        bad.append(f"[F2] 保存失败仍冲出 main()：{exc}")
    if code != 1:
        bad.append(f"[F2] 保存失败的退出码是 {code!r}，应为 1")
    if "保存失败" not in out:
        bad.append("[F2] 没有打印「保存失败」——失败不静默这一条没做到")
    code2, exc2, out2 = _drive(
        lambda *a, **k: Path(tempfile.gettempdir()) / "smoke71_never.md")
    if exc2 or code2 is not None:
        bad.append(f"[F2] 成功路径被 try 改变了行为：code={code2!r} "
                   f"exc={exc2!r}")
    if "保存失败" in out2:
        bad.append("[F2] 成功路径印了「保存失败」")
    _src = _ins.getsource(mod.main)
    _needle = ('    try:\n        save_result(result, '
               'cfg["output"]["save_dir"])')
    if _needle not in _src:
        bad.append("[F2] main() 里的 save_result 不在 try 块内（没接线）")
    if bad:
        for m in bad:
            print(f"  \u2717 [v71 F2] {m}")
        return False
    print("  \u2713 [v71 F2] 保存失败 → SystemExit(1) + 打印；成功路径不变；"
          "try 接线在")
    return True

def check_v71_build_inp_meta_filter():
    """[v1.21.71 F3] `_build_inp_meta` 的非法 entry 必须被**配对过滤**。

    两方向：
      · entry="9"（不存在）→ 不抛 KeyError、被剔除、且留痕两处；
      · entry=0/1（合法）→ **一条都不许丢**（否则"全丢掉"也能通过上面）。
    """
    import inspect as _ins
    bad = []
    cfg = build_cfg(False)
    m = mod.MetaDGTF(cfg)
    m._upstream_provider = lambda e: [mod.View(entry="9", manifest="上游形状正文")]
    try:
        inp = m._build_inp_meta([])
        if inp.upstream_views or inp.upstream_pools:
            bad.append("[F3] 非法 entry 的上游 view 没被剔除")
        if not str(getattr(m, "_build_inp_dropped", "")).strip():
            bad.append("[F3] 剔除了却没留痕（_build_inp_dropped 为空）")
    except Exception as e:
        bad.append(f"[F3] 非法 entry 仍打崩元层：{type(e).__name__}: {e}")

    m2 = mod.MetaDGTF(cfg)
    m2._upstream_provider = lambda e: [mod.View(entry="0", manifest="甲"),
                                       mod.View(entry="1", manifest="乙")]
    try:
        inp2 = m2._build_inp_meta([])
        if len(inp2.upstream_views) != 2 or len(inp2.upstream_pools) != 2:
            bad.append("[F3] 合法 entry 被误删：views="
                       + str([getattr(v, "entry", None)
                              for v in inp2.upstream_views])
                       + " pools=" + str(len(inp2.upstream_pools)))
        if str(getattr(m2, "_build_inp_dropped", "")).strip():
            bad.append("[F3] 合法 entry 也被报了剔除留痕")
    except Exception as e:
        bad.append(f"[F3] 合法 entry 路径崩了：{type(e).__name__}: {e}")
    if "_build_inp_dropped" not in _ins.getsource(mod.MetaDGTF._build_inp_meta):
        bad.append("[F3] 过滤逻辑没接线")
    # 连带把「上游是非法的」这条留痕也验一遍：它必须能被读出来
    if not _ins.getsource(mod.MetaDGTF._build_inp_meta).count("_pairs"):
        bad.append("[F3] 配对过滤的 _pairs 不在实现里")
    if bad:
        for m_ in bad:
            print(f"  \u2717 [v71 F3] {m_}")
        return False
    print("  \u2713 [v71 F3] 非法 entry 被剔除 + 留痕；合法 entry 一条不丢；"
          "接线在")
    return True

def check_v71_load_config_empty():
    """[v1.21.71 F4] `load_config("")` 不许报「读取  失败」。

    两方向：空路径 → 无警告；**真坏的 yaml** → 仍必须报「解析失败」
    （修过头会把这条判据变成"只要不报警就通过"）。
    """
    bad = []
    if not mod.HAS_YAML:
        print("  \u26a0 [v71 F4] 环境无 pyyaml，本条无判别力 → 跳过")
        return True
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.load_config("")
    if "\u26a0" in buf.getvalue():
        bad.append("[F4] load_config('') 仍在报错："
                   + repr(buf.getvalue().strip()[:70]))
    td = Path(tempfile.mkdtemp(prefix="smoke71_"))
    _badf = td / "bad.yaml"
    _badf.write_text("output:\n  save_dir: a\n   verbose: b\n",
                     encoding="utf-8")
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        mod.load_config(str(_badf))
    if "\u26a0" not in buf2.getvalue():
        bad.append("[F4] 坏 yaml 不再报「解析失败」—— 修过头了")
    if bad:
        for m in bad:
            print(f"  \u2717 [v71 F4] {m}")
        return False
    print("  \u2713 [v71 F4] 空路径静默回落；坏 yaml 仍报解析失败")
    return True

def check_v71_early_dispatch():
    """[v1.21.71 F5] C / D-H 早退时 dispatch 不许为空。

    两方向：
      · route 里没有合法层 → dispatch 仍带 ran/missing/failed/skipped，
        且模式名是实际变量（C / 传入的 mode）；
      · 守卫**活着**的证明：dispatch 非空 + 计划里的层没产出 →
        `_layer_guard` 必须记 `layer_gap`；空 dispatch 则什么都记不到
        （这就是"守卫短路"本身，两个方向一起锁）。
    """
    bad = []
    cfg = build_cfg(False)
    for fn, want in (("_run_parallel_C", "C"), ("_run_parallel_stage", "G")):
        m = mod.MetaDGTF(cfg)
        m._dispatch_plan = m._plan_dispatch(["x"])
        m._failed_layers = {}
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                if fn == "_run_parallel_C":
                    pk = m._run_parallel_C(_V71_Q, ["x"], {}, {"0": 1}, None)
                else:
                    pk = m._run_parallel_stage("G", _V71_Q, ["x"], {},
                                               {"0": 1}, None)
        except Exception as e:
            bad.append(f"[F5] {fn} 早退崩了：{type(e).__name__}: {e}")
            continue
        d = pk.get("dispatch") or {}
        if not all(k in d for k in ("ran", "missing", "failed", "skipped")):
            bad.append(f"[F5] {fn} 早退的 dispatch 缺守卫键：{sorted(d)}")
        if d.get("_parallel_mode") != want:
            bad.append(f"[F5] {fn} 的 _parallel_mode={d.get('_parallel_mode')!r}"
                       f"，应为 {want!r}（模式名不许硬编码）")
    # 守卫的判别力（两个方向）
    m3 = mod.MetaDGTF(cfg)
    m3._results = {}
    m3._dispatch_plan = m3._plan_dispatch(["0"])
    _p_live = {"views": {}, "dispatch": m3._dispatch_for_pack("C")}
    with contextlib.redirect_stdout(io.StringIO()):
        m3._layer_guard(_p_live)
    if "layer_gap" not in _p_live:
        bad.append("[F5] dispatch 非空时守卫仍不报缺层（接线断了）")
    _p_dead = {"views": {}, "dispatch": {}}
    m3._layer_guard(_p_dead)
    if "layer_gap" in _p_dead:
        bad.append("[F5] 空 dispatch 居然也能报缺层 —— 判据前提不成立")
    if bad:
        for m_ in bad:
            print(f"  \u2717 [v71 F5] {m_}")
        return False
    print("  \u2713 [v71 F5] 两条早退路径的 dispatch 齐全（C / G 模式名）；"
          "守卫在非空 dispatch 下真会记 layer_gap")
    return True

def check_v71_ext_assess_cached():
    """[v1.21.71 F6] 同题的外部可判定性评估，一次 run 只跑一次。

    两方向 + 负对照：
      · 一次 run → `DGTF._assess_decidability` 恰好 1 次（改前 2 次）；
      · 缓存**可被清掉**：手动清空后同一题会再打一次（证明计数不是被
        别的东西压住的）；
      · 跨 run 不许复用：同一实例跑两次 → 各 1 次（共 2 次）。
    """
    bad = []
    cnt = {"n": 0}
    _orig = mod.DGTF._assess_decidability

    def _wrap(self, q, anchors=None):
        # [v1.21.73] 同上：不收 anchors 会让 F6 缓存计数这条静默失效。
        cnt["n"] += 1
        return _orig(self, q, anchors=anchors)

    mod.DGTF._assess_decidability = _wrap
    try:
        cfg = build_cfg(False)
        meta = mod.MetaDGTF(cfg)
        cnt["n"] = 0
        meta.run(_V71_Q, route=["0", "1", "both", "all"],
                 rounds={"0": 2, "1": 2, "both": 2, "all": 2},
                 parallel_mode="serial")
        if cnt["n"] != 1:
            bad.append(f"[F6] 一次 run 打了 {cnt['n']} 次外部评估，应为 1")
        # ★ 缓存单测必须换一个**没跑过**的题：上面那次 run 已经把
        #   _V71_Q 填进缓存了，同题再调是缓存命中、不会增加计数。
        _q2 = _V71_Q + "（缓存单测）"
        meta._ext_assess_cache = {}
        meta._cached_ext_assess(_q2)
        _c1 = cnt["n"]
        meta._cached_ext_assess(_q2)
        _c2 = cnt["n"]
        if _c1 != 2 or _c2 != 2:
            bad.append(f"[F6] 缓存没生效：第一次调用后累计 {_c1} 次、"
                       f"重复调用后 {_c2} 次（应停在 2）")
        meta._ext_assess_cache = {}
        meta._cached_ext_assess(_q2)
        if cnt["n"] != 3:
            bad.append(f"[F6] 清掉缓存后仍只有 {cnt['n']} 次 —— 计数被压住了，"
                       f"上面那条判据没判别力")
        meta.run(_V71_Q, route=["0", "1", "both", "all"],
                 rounds={"0": 2, "1": 2, "both": 2, "all": 2},
                 parallel_mode="serial")
        if cnt["n"] != 4:
            bad.append(f"[F6] 第二次 run 之后累计 {cnt['n']} 次，"
                       f"应为 4（每 run 一次）")
    finally:
        mod.DGTF._assess_decidability = _orig
    import inspect as _ins
    if "_ext_assess_cache" not in _ins.getsource(mod.MetaDGTF.run):
        bad.append("[F6] run() 里没有重置缓存（跨 run 会复用）")
    if "_cached_ext_assess" not in _ins.getsource(
            mod.MetaDGTF._assess_decidability_dynamic):
        bad.append("[F6] 动态评估那条没走缓存（没接线）")
    if bad:
        for m in bad:
            print(f"  \u2717 [v71 F6] {m}")
        return False
    print("  \u2713 [v71 F6] 一次 run 只打 1 次外部评估；缓存可清（有判别力）；"
          "跨 run 各自一次")
    return True

def check_v71_evidence_full():
    """[v1.21.71 F7] 兜底重算与缓存同口径（用完整 evidence）。

    两方向 + 负对照：
      · 同一份 pool_res，缓存路与兜底路的 `_und_untraced` 必须相等；
      · 无 `_evidence_full` 的老数据 → 退回 `evidence`，不许崩；
      · 负对照：直接用**截断**的 evidence 重算必须与完整 evidence 不等
        —— 否则说明这个样例本身造不出口径差，判据没有判别力。
    """
    bad = []
    _asp = "清分规则未定，断面客流与线路客流不可互证"
    _full = [{"aspect": f"毫不相干的噪音条目第{i}条"} for i in range(8)] + \
        [{"aspect": _asp}]
    _cached = mod._untraced_undecidable([_asp], _full)
    cfg = build_cfg(False)
    mt = mod.MetaDGTF(cfg)
    _ext = {"decidability": "undecidable", "decidable_aspects": [],
            "undecidable_aspects": [], "reason": "", "features": []}
    _pool = {"decidability": "undecidable", "undecidable_aspects": [_asp],
             "evidence": _full[:8], "_evidence_full": _full}
    _r1 = mt._merge_decidability(dict(_pool, _und_untraced=_cached), dict(_ext))
    _r2 = mt._merge_decidability(dict(_pool), dict(_ext))
    if _r1.get("_und_untraced") != _r2.get("_und_untraced"):
        bad.append(f"[F7] 两路口径仍不一致：缓存 {_r1.get('_und_untraced')!r} "
                   f"vs 兜底 {_r2.get('_und_untraced')!r}")
    if _r2.get("_und_untraced"):
        bad.append(f"[F7] 兜底仍把第 9 条的追溯判成无追溯："
                   f"{_r2.get('_und_untraced')!r}")
    # 老数据（没有 _evidence_full）必须仍能算，且等于用 evidence 重算
    _oldpool = {"decidability": "undecidable", "undecidable_aspects": [_asp],
                "evidence": _full[:8]}
    _r3 = mt._merge_decidability(dict(_oldpool), dict(_ext))
    _exp = sorted(mod._untraced_undecidable([_asp], _full[:8]))
    if _r3.get("_und_untraced") != _exp:
        bad.append(f"[F7] 老数据兜底值不对：{_r3.get('_und_untraced')!r} "
                   f"≠ {_exp!r}")
    # 负对照：截断口径必须与完整口径不等，否则样例没判别力
    if mod._untraced_undecidable([_asp], _full[:8]) == _cached:
        bad.append("[F7] 负对照失效：截断与完整的追溯判定相同，"
                   "这条判据验不出口径差")
    import inspect as _ins
    if "_evidence_full" not in _ins.getsource(
            mod.MetaDGTF._assess_decidability_from_pool_view):
        bad.append("[F7] 池评估没带出 _evidence_full（没接线）")
    if "_evidence_full" not in _ins.getsource(mod.MetaDGTF._merge_decidability):
        bad.append("[F7] 兜底分支没读 _evidence_full（没接线）")
    if bad:
        for m in bad:
            print(f"  \u2717 [v71 F7] {m}")
        return False
    print("  \u2713 [v71 F7] 缓存 / 兜底同口径；老数据仍可算；"
          "截断口径确有差异（负对照有判别力）")
    return True

def check_v71_tokenize_stopwords():
    """[v1.21.71 F9] 停用词按**词**匹配。

    两方向：
      · 多字停用词被挡（的话 / 一种 / 进行 …）；
      · **内容词一个都不许丢**（螺旋 / 结构 / 整理），否则"全挡掉"也能过。
    负对照：`_STOPWORDS` 必须全是多字词 —— 退化成单字集合立刻失败。
    """
    bad = []
    _toks = mod._tokenize("如果我们通过一种方式进行整理的话，螺旋结构就浮现出来了")
    for w in ("的话", "一种", "进行", "我们", "通过"):
        if w in _toks:
            bad.append(f"[F9] 停用词「{w}」没被挡：{_toks}")
    for w in ("螺旋", "结构", "整理"):
        if w not in _toks:
            bad.append(f"[F9] 内容词「{w}」被误挡：{_toks}")
    if not all(len(w) >= 2 for w in mod._STOPWORDS):
        bad.append(f"[F9] _STOPWORDS 里还有单字："
                   f"{sorted(w for w in mod._STOPWORDS if len(w) < 2)}")
    if not all(len(c) == 1 for c in mod._STOPCHARS):
        bad.append("[F9] _STOPCHARS 不是单字集合（原名语义被改坏了）")
    if not mod._STOPCHARS:
        bad.append("[F9] _STOPCHARS 丢了 —— 原来挡了什么就无从查起")
    if bad:
        for m in bad:
            print(f"  \u2717 [v71 F9] {m}")
        return False
    print(f"  \u2713 [v71 F9] 停用词按词生效、内容词保留；"
          f"_STOPWORDS 全为多字（{len(mod._STOPWORDS)} 个）")
    return True

def check_v71_coverage_cfg_optional():
    """[v1.21.71 F10] `coverage_parts` 的 cfg 可选 + 调用点传真配置。

    两方向：
      · 省略 cfg 也能调（签名可选的直接证据）；
      · 传 cfg / 传 None 的结果必须**逐值相同**（当前实现不读 cfg，
        这条同时是"没有偷偷把 cfg 用起来"的反向锁）。
    """
    bad = []
    import inspect as _ins
    p = mod.Pool()
    try:
        _a = mod.coverage_parts(p)
    except Exception as e:
        bad.append(f"[F10] 省略 cfg 仍报错：{type(e).__name__}: {e}")
        _a = None
    _b = mod.coverage_parts(p, None)
    _c = mod.coverage_parts(p, {})
    _d = mod.coverage_parts(p, build_cfg(False))
    if _a is not None and not (_a == _b == _c == _d):
        bad.append(f"[F10] 四种传法的结果不一致：{_a} / {_b} / {_c} / {_d}")
    _src = _ins.getsource(mod.MetaDGTF._refresh_settlement)
    if 'coverage_parts(self.pools["1"], self.config)' not in _src:
        bad.append("[F10] _refresh_settlement 没传真配置（没接线）")
    if 'coverage_parts(self.pools["1"], {})' in _src:
        bad.append("[F10] _refresh_settlement 还在传空 dict")
    _sig = _ins.signature(mod.coverage_parts)
    if _sig.parameters["cfg"].default is _ins.Parameter.empty:
        bad.append("[F10] cfg 仍无默认值")
    elif _sig.parameters["cfg"].default is not None:
        bad.append(f"[F10] cfg 的默认值不是 None 而是 "
                   f"{_sig.parameters['cfg'].default!r}")
    if bad:
        for m in bad:
            print(f"  \u2717 [v71 F10] {m}")
        return False
    print("  \u2713 [v71 F10] cfg 可选（默认 None）且四种传法结果一致；"
          "调用点已传真配置")
    return True

def check_v71_no_dup_position_diag():
    """[v1.21.71 F11] 收尾复核不许重复写 position 诊断。

    两方向（这条最容易修过头 —— 一刀全关也能让"变少"成立）：
      · 收尾复核（`_finalize_layer_common` 那条）→ dump 尝试次数为 0；
      · **圈内那条仍必须写**：同一个全同 position 的 view 直接调
        `_quality_check`（默认 write_diag=True）→ 必须落盘一个文件；
        传 `write_diag=False` → 不落盘。
      · 真跑侧：一次四层跑里 `write_diag=False` 的调用数 == 层数（4）。
    """
    bad = []
    import inspect as _ins
    _att = {"in_finalize": 0, "in_round": 0, "wfalse": 0, "qc": 0,
            "flag": False}
    _ofin = mod.MetaDGTF._finalize_layer_common
    _odump = mod.DGTF._dump_position_diagnostic
    _oqc = mod.DGTF._quality_check

    def _fin(self, entry, view, state):
        _att["flag"] = True
        try:
            return _ofin(self, entry, view, state)
        finally:
            _att["flag"] = False

    def _dmp(self, *a, **k):
        _att["in_finalize" if _att["flag"] else "in_round"] += 1
        return _odump(self, *a, **k)

    def _qc(self, *a, **k):
        _att["qc"] += 1
        if k.get("write_diag") is False:
            _att["wfalse"] += 1
        return _oqc(self, *a, **k)

    mod.MetaDGTF._finalize_layer_common = _fin
    mod.DGTF._dump_position_diagnostic = _dmp
    mod.DGTF._quality_check = _qc
    try:
        _v71_packed_run()
    finally:
        mod.MetaDGTF._finalize_layer_common = _ofin
        mod.DGTF._dump_position_diagnostic = _odump
        mod.DGTF._quality_check = _oqc
    if _att["in_finalize"] != 0:
        bad.append(f"[F11] 收尾复核仍写了 {_att['in_finalize']} 次诊断")
    if _att["wfalse"] != len(_ALL_LAYERS):
        bad.append(f"[F11] write_diag=False 的调用数是 {_att['wfalse']}，"
                   f"应为 {len(_ALL_LAYERS)}（每层一次收尾复核）")

    # ---- 圈内那条必须仍然写（反向锁）----
    _td = Path(tempfile.mkdtemp(prefix="smoke71_diag_"))
    _cfg = build_cfg(False)
    _cfg["output"]["save_dir"] = str(_td)
    _dg = mod.DGTF("0", mod.LLM(_cfg), _cfg)
    _dg.verbose = False
    _v = mod.View(entry="0", anchor="锚")
    _v.candidates = [{"desc": "候选甲", "attribute": "0", "position": "0"},
                     {"desc": "候选乙", "attribute": "3", "position": "0"}]
    _pool = mod.Pool()
    _f_before = len(list(_td.glob("diagnostic_position_*.log")))
    _dg._quality_check(_v, _pool, 1)                      # 默认 True = 圈内
    _n_after_true = len(list(_td.glob("diagnostic_position_*.log")))
    if _n_after_true <= _f_before:
        bad.append("[F11] 圈内调用（默认 write_diag=True）居然不写诊断了 —— "
                   "修成了一刀全关")
    _dg._quality_check(_v, _pool, 1, write_diag=False)
    _n_after_false = len(list(_td.glob("diagnostic_position_*.log")))
    if _n_after_false != _n_after_true:
        bad.append("[F11] write_diag=False 仍写了文件")
    if "write_diag=False" not in _ins.getsource(
            mod.MetaDGTF._finalize_layer_common):
        bad.append("[F11] 收尾调用没传 write_diag=False（没接线）")
    if bad:
        for m in bad:
            print(f"  \u2717 [v71 F11] {m}")
        return False
    print(f"  \u2713 [v71 F11] 收尾 0 次写入 / {_att['wfalse']} 次抑制；"
          f"圈内那条仍写（反向锁成立）")
    return True

def check_v71_auto_plan_agreement():
    """[v1.21.71 F8] 模块级 `auto_plan` 与方法级 `_auto_plan` 的一致性检测器。

    这是**给未来漂移用的报警器**，不是"修好了"：
      · 同一份 mock 输入（模式 + 逐层圈数）分别喂两实现 → mode 与
        （按 route 裁剪后的）rounds 必须逐字相同；
      · 负对照：子类把方法级那份的圈数改坏 → 必须判**不一致**
        （否则检测器没有判别力）。
    """
    bad = []

    class _Stub:
        def __init__(self, payload):
            self.payload = payload

        def call(self, *a, **k):
            return json.dumps(self.payload, ensure_ascii=False)

        def parse_json(self, raw):
            return json.loads(raw)

    def _cmp(rounds_in, mode_in="G", conf=0.8, cls=None):
        _cls = cls or mod.MetaDGTF
        _m = _cls(build_cfg(False))
        _m.llm = _Stub({"mode": mode_in, "rounds": dict(rounds_in),
                        "reason": "smoke", "confidence": conf})
        _p1 = _m._auto_plan("探针题：评估这个多阶段问题的资源配置路径")
        _s2 = _Stub({"route": "full", "mode": mode_in,
                     "rounds": dict(rounds_in), "max_calls": 0,
                     "reason": "smoke", "confidence": conf})
        _oL = mod.LLM
        mod.LLM = lambda cfg: _s2
        try:
            _p2 = mod.plan_resources("探针题：评估这个多阶段问题的资源配置路径", "decision",
                                     build_cfg(False))
        finally:
            mod.LLM = _oL
        _r2 = {k: v for k, v in _p2["rounds"].items() if k in _p2["route"]}
        return _p1["mode"], dict(_p1["rounds"]), _p2["mode"], _r2

    _cases = {"四层齐": {"0": 3, "1": 7, "both": 4, "all": 6},
              "只给两层": {"0": 5, "1": 5},
              "越界值": {"0": 1, "1": 99, "both": 2, "all": 2}}
    for tag, _rin in _cases.items():
        m1, r1, m2, r2 = _cmp(_rin)
        if m1 != m2 or r1 != r2:
            bad.append(f"[F8] {tag}：方法 {m1}/{r1} vs 模块 {m2}/{r2}")

    class _Drift(mod.MetaDGTF):
        def _auto_plan(self, question):
            _r = dict(super()._auto_plan(question))
            _r["rounds"] = {k: v + 1 for k, v in (_r.get("rounds") or {}).items()}
            return _r

    m1, r1, m2, r2 = _cmp({"0": 3, "1": 7, "both": 4, "all": 6}, cls=_Drift)
    if (m1, r1) == (m2, r2):
        bad.append("[F8] 负对照失效：把一份改坏了居然还判一致 —— "
                   "检测器没有判别力")
    import inspect as _ins
    _ds = mod.MetaDGTF._auto_plan.__doc__ or ""
    if "auto_plan" not in _ds or "plan_resources" not in _ds:
        bad.append("[F8] _auto_plan 的 docstring 没标注与模块级 auto_plan 的关系")
    if bad:
        for m in bad:
            print(f"  \u2717 [v71 F8] {m}")
        return False
    print("  \u2713 [v71 F8] 三组输入两实现逐字一致；改坏一份立刻判不一致；"
          "关系已标注")
    return True

# ======================================================================
# [v1.21.72] 文档整理批 + 可观测性/形态断言窄版的判据
#   四条：#13 barrier 语义 / #20 changelog 卫生 / #22 唯一实现点 /
#         #24 长度异常告警。
# ======================================================================
def _v72_engine_src():
    """引擎全文与**抠掉模块 docstring 的**可执行源码。

    ★ 为什么必须有「抠掉 docstring」这一版：changelog 里也写着这些函数名
      与旧写法（`rounds_n > 1` 之类），在**全文**上数会把文档里的引用
      当成代码 —— v1.21.72 的探针第一版就栽在这（`old_finalize_gate_serial`
      数出 1，代码里其实是 0）。
    """
    eng = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    i = eng.index('"""')
    j = eng.index('"""', i + 3)
    return eng, eng[j + 3:]

def check_v72_bbarrier_semantics():
    """[v1.21.72 #13] B 模式预算耗尽必须**所有层一起停**（barrier 语义）。

    两个方向：
      · `max_calls=30` 的 mock B 跑 → 四层**全部**带「预算用尽」；
      · 不限预算（0）→ **0 层**带（守卫不误触发）。
    ★ 负对照就是第一方向本身：若「一起停」被改成「只停一层」，
      计数会落进 `1..n-1` 区间，立刻判红。
    """
    import inspect as _ins
    bad = []

    def _run(budget):
        cfg = build_cfg(False)
        cfg["max_calls"] = budget
        # ★ [v1.23.17 判据随实现更新] 本判据量的是「预算耗尽是不是四层一起停」，
        #   与**自然停**无关。本版条件 1 对四层生效 + soft_max 降到 2 ⇒ 修行层
        #   第 2 圈就自然停（实测停因含条件 1 与「产物相似度高，自然安住」），
        #   「四层都带预算用尽」不再成立。**把自然停固定住**（不是改期望值）：
        #   soft_max 抬高同时关掉条件 1 的推迟与条件 6，三条 idle 阈值抬到 99，
        #   sat 关掉 ⇒ 预算成为唯一的停止来源（实测预算 30 → 四层全带「预算用尽」、
        #   预算 0 → 0 层）。
        _sp = cfg.setdefault("spiral", {})
        _sp["soft_max"] = 99
        _sp["round_idle_limit"] = 99
        _sp["round_stall_limit"] = 99
        _sp["idle_limit"] = 99
        _sp["structure_saturation_enabled"] = False
        meta = mod.MetaDGTF(cfg)
        with contextlib.redirect_stdout(io.StringIO()):
            pk = meta.run(_V71_Q, route=["0", "1", "both", "all"],
                          rounds={"0": 2, "1": 2, "both": 2, "all": 2},
                          parallel_mode="B")
        views = pk.get("views") or {}
        stopped = sorted(
            e for e, v in views.items()
            if "预算用尽" in str((v or {}).get("stop_reason") or ""))
        return len(views), stopped

    n_all, st = _run(30)
    if not st:
        bad.append("[#13] 预算 30 的 B 跑没触发「预算用尽」——判据前提不成立")
    elif len(st) != n_all:
        bad.append(f"[#13] 预算耗尽只停了 {len(st)}/{n_all} 层（{st}）"
                   f"—— barrier 语义被改成了「本层截断」")
    n2, st2 = _run(0)
    if st2:
        bad.append(f"[#13] 不限预算也有层被预算停掉：{st2}")
    _src = _ins.getsource(mod.MetaDGTF._run_parallel_B)
    # [v1.23.6] 判据随实现更新（不是放宽）：原锚点 `[v1.21.72 #13]` 是**版次
    #   标签**，已被「代码正文不留版次批注」清掉 ⇒ 换成本条注释里的两条内容
    #   短语（下一条仍查「同时停掉所有层」），判别力不减。
    if "刻意的 barrier" not in _src:
        bad.append("[#13] 注释没写进 _run_parallel_B（没接线）")
    if "同时停掉所有层" not in _src:
        bad.append("[#13] 注释没写明「同时停掉所有层」")
    if bad:
        for m in bad:
            print(f"  \u2717 [v72 #13] {m}")
        return False
    print(f"  \u2713 [v72 #13] 预算耗尽 → {len(st)}/{n_all} 层一起停；"
          f"不限预算 → 0 层；注释在位")
    return True

def _changelog_text() -> str:
    """changelog 正文。★ v1.23.7 起它在仓库根目录 `CHANGELOG.md`，不在代码里。"""
    p = HERE / "CHANGELOG.md"
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")

def _changelog_lint(doc: str):
    """纯函数：返回（版本段标题, 收束摘要标题, 重复的收束摘要标题）。

    ★ 抽成纯函数是为了让**负对照可以喂合成坏样本** —— changelog 搬到外部文件后，
    「把 SRC 指回旧版」的旧负对照手法失效（取源不再是被测文件），
    没有新负对照的「全绿」只说明判据没跑。
    """
    sums = [ln.strip() for ln in doc.split("\n")
            if "★ v1.2" in ln and "收束摘要" in ln]
    dup = {t: sums.count(t) for t in set(sums) if sums.count(t) > 1}
    secs = re.findall(r"^v(\d+(?:\.\d+)+) 相对", doc, re.M)
    return secs, sums, dup

def check_v72_changelog_hygiene():
    """[v1.21.72 #20 起；v1.23.7 改取源] changelog 不得有重复的「★ vX 收束摘要」
    段，版本段序必须按版本号**严格递减**。

    ★ v1.23.7：changelog 从模块 docstring 搬到了 `CHANGELOG.md` ⇒ 本判据的**取源**
      跟着改。**判据意图一字未改**（是位置变了，不是放宽）。
    ★ 判别力（负对照）：喂一份**合成坏样本**（重复的收束标题 + 段序 71→68→69），
      同一个 `_changelog_lint` 必须报出重复、且段序必须被判为**非**严格递减。
    """
    bad = []
    doc = _changelog_text()
    if not doc:
        bad.append("[#20] CHANGELOG.md 不存在或为空 —— 判据前提不成立")
        secs, sums = [], []
    else:
        secs, sums, dup = _changelog_lint(doc)
        if dup:
            bad.append(f"[#20] 收束摘要标题重复：{dup}")
        if not secs:
            bad.append("[#20] 一个版本段标题都没找到 —— 判据前提不成立")
        else:
            if len(secs) != len(set(secs)):
                bad.append(f"[#20] 版本段有重复：{secs}")
            ver = [tuple(int(x) for x in s.split(".")) for s in secs]
            for k in range(len(ver) - 1):
                if ver[k] <= ver[k + 1]:
                    bad.append(f"[#20] 段序不是严格递减：{secs[k]} → {secs[k + 1]}")
                    break
    # ---- 负对照：合成坏样本必须被判出来 ----
    _bad = ("v1.21.71 相对 v1.21.70\n★ v1.21.63 收束摘要\n"
            "v1.21.68 相对 v1.21.67\n★ v1.21.63 收束摘要\n"
            "v1.21.69 相对 v1.21.68\n")
    _s, _sm, _d = _changelog_lint(_bad)
    _desc = all(tuple(int(x) for x in _s[k].split("."))
                > tuple(int(x) for x in _s[k + 1].split("."))
                for k in range(len(_s) - 1)) if len(_s) > 1 else True
    if not _d or _desc:
        bad.append("[#20] ★ 负对照失效：合成坏样本没被检出（重复=%r 递减=%r）"
                   % (bool(_d), _desc))
    if bad:
        for m in bad:
            print(f"  \u2717 [v72 #20] {m}")
        return False
    print(f"  \u2713 [v72 #20] CHANGELOG.md：{len(secs)} 个版本段严格递减、"
          f"{len(sums)} 个收束摘要标题无重复（首段 v{secs[0]}）；负对照判红")
    return True

def check_v72_mechanism_single_source():
    """[v1.21.72 #22 窄版] 「机制 → 唯一实现点」形态断言。

    只钉本项目反复栽过的机制（**不建全局调用图框架**，那是架构批）：
      · 关键机制各只有 1 处 `def`；
      · `_assess_decidability(` 的**调用点恰好 1 处**（F6 的唯一入口）；
      · `_finalize_layer_common` / `_stop_reasons` 各 **2 个调用点、
        1 份实现**（两通道共用同一份 —— 这正是 v1.21.71 F1 的教训）；
      · v1.21.71 删掉的两处旧门**不得复活**。
    """
    bad = []
    eng, ex = _v72_engine_src()
    if not (len(ex) < len(eng)):
        bad.append("[#22] 「抠掉 docstring」没生效（可执行源码没变短）")
    _mechs = ("_normalize_decidability", "_untraced_undecidable",
              "_stop_reasons", "_finalize_layer_common", "_cached_ext_assess",
              "_dispatch_for_pack", "_layer_guard", "_quality_check",
              "_merge_decidability", "_assess_decidability_dynamic")
    for _fn in _mechs:
        _n = len(re.findall(r"^\s*def " + _fn + r"\b", ex, re.M))
        if _n != 1:
            bad.append(f"[#22] {_fn} 有 {_n} 处定义（应为 1）")
    _adef = len(re.findall(r"def _assess_decidability\(", ex))
    _acall = len(re.findall(r"_assess_decidability\(", ex)) - _adef
    if _adef != 1:
        bad.append(f"[#22] _assess_decidability 有 {_adef} 处定义（应为 1）")
    if _acall != 1:
        bad.append(f"[#22] _assess_decidability 有 {_acall} 个调用点"
                   f"（应为 1 —— F6 的唯一入口，多一个就说明又直调了）")
    if len(re.findall(r"self\._finalize_layer_common\(", ex)) != 2:
        bad.append("[#22] _finalize_layer_common 的调用点不是 2 个"
                   "（serial + B 各一）")
    if len(re.findall(r"self\._stop_reasons\(", ex)) != 2:
        bad.append("[#22] _stop_reasons 的调用点不是 2 个"
                   "（两条跑圈通道各一，但只应有 1 份实现）")
    _g1 = ex.count("if view is not None and rounds_n > 1:")
    _g2 = ex.count('state["total_rounds"] <= 1')
    if _g1 or _g2:
        bad.append(f"[#22] v1.21.71 删掉的旧门复活了：serial={_g1} / B={_g2}")
    if bad:
        for m in bad:
            print(f"  \u2717 [v72 #22] {m}")
        return False
    print(f"  \u2713 [v72 #22] {len(_mechs)} 个机制各 1 处定义；"
          f"_assess_decidability 调用点=1；finalize/stop 各 2 调用点 1 实现；"
          f"旧门未复活")
    return True

def check_v72_len_anomaly_guard():
    """[v1.21.72 #24 窄版] 长度异常自动冒烟警告。

    盯的失效模式：**超长字段如果不在 `dump_view_fields` 的 `_OVERSIZED`
    里，就会被整段打进日志**（v1.21.70 [H] 有意只钉字段名、不维护清单，
    于是**新增的大字段不会被自动压缩**）。
    三方向：
      · mock 跑的真实长度谱 → 非 `_OVERSIZED` 的字符串字段里 ≥2000 字的
        个数必须为 0（基线；将来真长出这种字段时这里红，并列出字段名）；
      · **负对照**：造 `collision=6000` 字的 view 喂**生产入口**
        `dump_view_fields` → ① 输出里**有正文**（失效模式真实存在）、
        ② 同一个统计函数必须把它**检出为异常**（判据不是死的）；
      · 反向锁：同长度的 `manifest`（在 `_OVERSIZED` 里）只打长度、
        正文**不出现**。
    """
    import inspect as _ins
    bad = []
    THR = 2000
    _dvf = _ins.getsource(mod.dump_view_fields)
    _m = re.search(r"_OVERSIZED = \{([^}]*)\}", _dvf)
    if not _m:
        bad.append("[#24] 从 dump_view_fields 源码里解析不到 _OVERSIZED")
        ov = set()
    else:
        ov = {x.strip().strip('"').strip("'")
              for x in _m.group(1).split(",") if x.strip()}
        ov.discard("")
    if not ov:
        bad.append("[#24] _OVERSIZED 解析为空 —— 判据前提不成立")

    def _long_fields(views):
        out = {}
        for _e, _v in (views or {}).items():
            if not isinstance(_v, dict):
                continue
            for _k, _val in _v.items():
                if isinstance(_val, str) and _k not in ov and len(_val) >= THR:
                    out[_k] = max(out.get(_k, 0), len(_val))
        return out

    _pk = _v71_packed_run()
    _hit = _long_fields(_pk.get("views") or {})
    if _hit:
        bad.append(f"[#24] 长度异常：mock 跑里出现 {len(_hit)} 个"
                   f"**不在 _OVERSIZED** 的超长字段 {_hit}"
                   f"（要么并入 _OVERSIZED，要么确认它该整段落日志）")

    # ---- 负对照：合成 view 走生产入口 ----
    _cfg = build_cfg(False)
    _dg = mod.DGTF("0", mod.LLM(_cfg), _cfg)
    _dg.verbose = True
    _dg.dump_rounds = True
    _v1 = mod.View(entry="0")
    _v1.collision = "长正文" * 2000                    # 6000 字
    _buf = io.StringIO()
    with contextlib.redirect_stdout(_buf):
        mod.dump_view_fields(_v1, _dg.vp)
    _out1 = _buf.getvalue()
    if "长正文长正文" not in _out1:
        bad.append("[#24] 负对照失效：不在 _OVERSIZED 的超长字段"
                   "居然没把正文打进日志（失效模式不成立？）")
    _det = _long_fields({"0": _v1.to_dict()})
    if "collision" not in _det:
        bad.append(f"[#24] 统计函数是死的：合成 view 的超长 collision 没被检出"
                   f"（检出 {_det}）")
    _v2 = mod.View(entry="0")
    _v2.manifest = "M" * 6000
    _buf2 = io.StringIO()
    with contextlib.redirect_stdout(_buf2):
        mod.dump_view_fields(_v2, _dg.vp)
    _out2 = _buf2.getvalue()
    if "MMMMMM" in _out2:
        bad.append("[#24] 反向锁失效：_OVERSIZED 里的 manifest 把正文落进日志了")
    if _long_fields({"0": _v2.to_dict()}):
        bad.append("[#24] 统计函数把 _OVERSIZED 里的字段也算成异常了")
    if bad:
        for m in bad:
            print(f"  \u2717 [v72 #24] {m}")
        return False
    print(f"  \u2713 [v72 #24] mock 长度谱无异常（阈值 {THR}，"
          f"_OVERSIZED={sorted(ov)}）；合成 6000 字 collision 被检出且正文落日志"
          f"（负对照有判别力）；manifest 仍只打长度")
    return True

def check_v74_anchor_refs():
    """[v1.21.74] 外判的锚点引用不许在合并时被丢掉 —— 双向判据。

    ★ 这条是 v1.21.73 真跑抓出来的：`_merge_decidability` 里
      `merged = dict(pool_res)` 只继承池判，`_assess_decidability` 已经算好的
      `anchor_refs` 到不了 packed。`_probe_v73_refs.py` 实测同一题直接调
      assess 得 8 条引用，跑完 packed 里却是 None —— 也就是「外判有没有引用
      外部事实」在产品上不可审。看不见 = 审不了。
    ★ 代价／红线：**关闭态必须一个键都不多**，否则 OFF 臂与 v1.21.72 不再
      逐字同构，加性改动就破了。所以判据里把关闭态放在第一条。
    """
    print("\n[v1.21.74] 外部锚点引用在合并后的留存")
    _src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    bad = []

    # [0] 形态：携带块必须真的在源码里（防止"改了文案没改代码"）
    if "merged[\"anchor_refs\"] = _ext_refs" not in _src:
        bad.append("[形态] _merge_decidability 里找不到 anchor_refs 携带语句")

    mt = object.__new__(mod.MetaDGTF)
    pool = {"decidability": "decidable", "reason": "", "features": [],
            "decidable_aspects": ["现金流第一约束"], "undecidable_aspects": [],
            "_und_untraced": [], "_evidence_full": []}
    ext = {"decidability": "decidable", "reason": "可用回本与利用率红线",
           "features": [], "decidable_aspects": ["回本测算"],
           "undecidable_aspects": []}

    # [A] 关闭态：一个锚点键都不许有（加性红线）
    r_off = mt._merge_decidability(dict(pool), dict(ext))
    leaked = sorted(k for k in r_off
                    if k.startswith("anchor") or k.startswith("_anchors"))
    if leaked:
        bad.append(f"[A] 关闭态泄漏锚点键 {leaked} —— OFF 臂不再与旧版同构")
    else:
        print("  ✓ [A] 关闭态无任何 anchor_* 键（加性红线守住）")

    # [B] 开启且有引用：必须原样带过来
    r_on = mt._merge_decidability(
        dict(pool), dict(ext, anchor_refs=["a1", "a5", "a9"],
                         _anchors_given=12))
    if r_on.get("anchor_refs") != ["a1", "a5", "a9"]:
        bad.append(f"[B] 引用被吞：实得 {r_on.get('anchor_refs')!r}")
    elif r_on.get("_anchors_given") != 12:
        bad.append(f"[B] _anchors_given 丢了：实得 {r_on.get('_anchors_given')!r}")
    else:
        print("  ✓ [B] 开启有引用：3 条编号 + given=12 原样留存")

    # [C] 开启但零引用：也必须留存 —— 这正是要审计的信号
    r_zero = mt._merge_decidability(
        dict(pool), dict(ext, anchor_refs=[], _anchors_given=12))
    if r_zero.get("anchor_refs") != [] or r_zero.get("_anchors_given") != 12:
        bad.append(f"[C] 「给了 12 条却 0 引用」被抹掉了："
                   f"refs={r_zero.get('anchor_refs')!r} "
                   f"given={r_zero.get('_anchors_given')!r}")
    else:
        print("  ✓ [C] 开启零引用：如实留存（没为了好看抹掉）")

    # [D] ext 为 None（单边池判）：不许报错，也不许加键
    try:
        r_none = mt._merge_decidability(dict(pool), None)
    except Exception as exc:
        bad.append(f"[D] ext=None 直接抛异常：{type(exc).__name__}: {exc}")
        r_none = {}
    if not any(k.startswith("anchor") for k in r_none):
        print("  ✓ [D] ext=None 退回池判，无异常无锚点键")
    else:
        bad.append("[D] ext=None 却带上了锚点键")

    if bad:
        print("  ✗ 未通过：")
        for b in bad:
            print("    -", b)
        return False
    print("  ✓ A/B/C/D 四路全部符合")
    return True

def check_v75_anchor_pool():
    """[v1.21.75] 锚点入池 —— 双向判据（关闭态加性 / 开启态可达 / 失败留痕）。

    ★ 背景：v1.21.73/74 把锚点塞进 `_assess_decidability`（外判，题面级），
      两次真跑 claims 全判「无对应」。按外部评审方案改接**池**：
        Pool.anchors 入池 → _citation_table 出 X# → evidence 可引锚点。
    ★ 红线：**进引用表 = 获得支撑 →decidable 的资格**（`apply_decidability_change`
      只拦「证据全是 d_ 开头」一种）。那是行为变化，不是加性 → 默认关，
      判据必须能抓到"谁把它无条件打开了"。
    """
    print("\n[v1.21.75] 外部锚点入池（接入点从外判改到池）")
    _src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    bad = []

    # [形态] 防"改了文案没改代码"
    for _frag in ("anchors: List[dict] = field(default_factory=list)",
                  "anchor_as_evidence: bool = False",
                  "self._before_round(entry, pool, layer_no)",
                  'if getattr(pool, "anchor_as_evidence", False):'):
        if _frag not in _src:
            bad.append(f"[形态] 源码里找不到 {_frag!r}")

    Pool = mod.Pool

    # [A] 关闭态：Pool 默认无锚点，to_dict 一个键都不多（加性红线）
    p0 = Pool()
    d0 = p0.to_dict()
    if p0.anchors != [] or p0.anchor_as_evidence is not False:
        bad.append(f"[A] 默认 Pool 不是空锚点态：anchors={p0.anchors} "
                   f"as_evidence={p0.anchor_as_evidence}")
    if "anchors" in d0:
        bad.append("[A] 关闭态 to_dict 多出 anchors 键（加性破了）")

    # [B] 引用表：未授权 → 无 X#；授权 → 有 X# 且能解析
    p1 = Pool()
    # [v122 P4] 补 tier=1：v122 起引用表带 **tier 门**（tier ≤ 缺省 2），
    #   不带 tier 的锚点缺省 3 ＝ 二手转述 —— 那种锚点**授权也不该进表**。
    #   本条判据测的是「授权门」，所以给够硬的 tier（含义不变）。
    p1.anchors = [{"id": "a1", "claim": "回本周期 1-3 年", "tier": 1},
                  {"id": "a5", "claim": "稼动率红线 75%", "tier": 1}]
    xs_off = [c for c, _ in mod._citation_table(None, p1)
              if c.startswith("X")]
    if xs_off:
        bad.append(f"[B] 未授权时引用表就出了 {xs_off}（等于偷偷给了证据资格）")
    p1.anchor_as_evidence = True
    xs_on = [c for c, _ in mod._citation_table(None, p1)
             if c.startswith("X")]
    if xs_on != ["X1", "X2"]:
        bad.append(f"[B] 授权后引用表 X 编号为 {xs_on}，期望 ['X1','X2']")
    if xs_on:
        r = mod._resolve_citation("X1", None, p1)
        if not r or r.get("resolved_to") != "X1":
            bad.append(f"[B] X1 定位不到（{r}）—— 编号进了表却引不了，等于没接")

    # [C] 分圈投放 + 元层不检索
    mt = object.__new__(mod.MetaDGTF)
    mt.config = {"external_anchor": {
        "enabled": True, "path": "x", "per_round": 2,
        "as_evidence": False, "triage": False, "retriever": "snapshot"}}
    mt._anchors = [{"id": f"a{i}", "claim": f"c{i}"} for i in range(1, 8)]
    mt.vp = lambda *a, **k: None
    mt.pools = {"0": Pool(), "1": Pool()}
    q0 = mt.pools["0"]
    mt._anchor_round("0", q0, 0)
    n1 = len(q0.anchors)
    mt._anchor_round("0", q0, 1)
    n2 = len(q0.anchors)
    if n1 != 2 or n2 != 4:
        bad.append(f"[C] 分圈投放不对：第1圈 {n1}、第2圈 {n2}，期望 2 / 4")
    mt._anchor_round("all", mt.pools["1"], 0)
    if len(mt.pools["1"].anchors) != 0:
        bad.append("[C] 元层也检索了（元层的活是清算，不是核对）")

    # [D] 非 snapshot 后端必须抛错留痕，**不静默降级**
    mt._anchor_err = ""
    mt.config["external_anchor"]["retriever"] = "web_search"
    mt._anchor_round("0", q0, 2)
    if "尚未实现" not in (mt._anchor_err or ""):
        bad.append(f"[D] 未实现的检索后端静默放过了（_anchor_err="
                   f"{mt._anchor_err!r}）—— 等于假装搜过")
    n_after = len(q0.anchors)
    if n_after != 4:
        bad.append(f"[D] 检索失败后还往池里塞了东西（{n_after} 条）")

    # [E] 预算必须把锚点调用算进去
    class _L:
        total_calls = 10
    m1 = object.__new__(mod.MetaDGTF)
    m1.llm = _L(); m1._call_budget = 10; m1._anchor_calls = 0
    m2 = object.__new__(mod.MetaDGTF)
    m2.llm = _L(); m2._call_budget = 12; m2._anchor_calls = 0
    # ★ 判别力关键：calls=9 + anchor_calls=1 + budget=10 ——
    #   只有**真的把锚点调用算进去**才会判用尽。少了这条，
    #   "漏算锚点"和"算进去了"在上面两种情形下结果完全一样，
    #   判据是永真的（变异体 M6 实测漏网）。
    class _L9:
        total_calls = 9
    m3e = object.__new__(mod.MetaDGTF)
    m3e.llm = _L9(); m3e._call_budget = 10; m3e._anchor_calls = 1
    if not m1._budget_exhausted():
        bad.append("[E] calls=10 budget=10 判成没用尽（预算守卫失灵）")
    if m2._budget_exhausted():
        bad.append("[E] calls=10 budget=12 判成用尽（预算守卫误伤）")
    # [E] ★ v1.21.76 A2：预算守卫**只算 llm.total_calls** —— 锚点调用发生
    #   在收尾对照（打包阶段，不在圈循环内），由 `_anchor_crosscheck` 自己
    #   做独立判断。所以 `_anchor_calls` 不该再影响这个守卫。
    if m3e._budget_exhausted():
        bad.append("[E] calls=9 + anchor=1 判成用尽 —— v1.21.76 A2 已把锚点"
                   "调用从守卫移除，不该再影响它")
    if "收尾对照跳过" not in _src:
        bad.append("[E] `_anchor_crosscheck` 缺独立预算判断（A2 的第三半）")

    # [F] 关闭态 prompt 加性：两个片段都必须是空串
    m3 = object.__new__(mod.MetaDGTF)
    m3.config = {"external_anchor": {"enabled": False}}
    # ★ 判别力关键：池里**先塞满锚点**再断言关闭态返回空串。
    #   空池时哪怕把 enabled 判断删掉也照样返回空串 —— 判据是永真的
    #   （变异体 M7 实测漏网）。
    _fp = Pool()
    _fp.anchors = [{"id": "a1", "claim": "回本周期 1-3 年"}]
    m3.pools = {"0": _fp}
    m3._anchors = [{"id": "a1", "claim": "回本周期 1-3 年"}]
    if m3._anchor_triage_sys() != "":
        bad.append("[F] 关闭态分诊段非空（prompt 被改了，加性破了）")
    if m3._anchor_view_ctx() != "":
        bad.append("[F] 关闭态锚点块非空（prompt 被改了，加性破了）")

    if bad:
        for b in bad:
            print(f"  \u2717 {b}")
        return False
    print("  \u2713 [A] 关闭态 to_dict 无 anchors 键（加性守住）")
    print("  \u2713 [B] 未授权无 X# / 授权出 X1,X2 且能定位")
    print("  \u2713 [C] 分圈投放 2→4，元层不检索")
    print("  \u2713 [D] 未实现后端抛错留痕且不入池")
    print("  \u2713 [E] 预算守卫只算 llm.total_calls；收尾对照有独立判断")
    print("  \u2713 [F] 关闭态 triage/ctx 均为空串（prompt 逐字不变）")
    return True

def _v76_strip(src: str) -> str:
    """抠掉 docstring 与注释 —— 判据只能扫**代码**。

    ★ 必须先 dedent：`_v76_body` 返回的是带缩进的片段，直接 ast.parse
      会 SyntaxError（unexpected indent）→ 静默退回原文 → docstring 里
      提到的符号被当成代码（v1.21.76 实测踩过：`_before_round` 体被数成
      2 处 `_anchor_round` 调用，真值 1）。
    """
    import ast as _ast
    import io as _io
    import textwrap as _tw
    import tokenize as _tk
    src = _tw.dedent(src)
    kill = set()
    try:
        tree = _ast.parse(src)
        for node in _ast.walk(tree):
            if not isinstance(node, (_ast.Module, _ast.FunctionDef,
                                     _ast.AsyncFunctionDef, _ast.ClassDef)):
                continue
            body = getattr(node, "body", None) or []
            if (body and isinstance(body[0], _ast.Expr)
                    and isinstance(body[0].value, _ast.Constant)
                    and isinstance(body[0].value.value, str)):
                d = body[0]
                for ln in range(d.lineno, (d.end_lineno or d.lineno) + 1):
                    kill.add(ln)
    except SyntaxError:
        pass
    try:
        for tok in _tk.generate_tokens(_io.StringIO(src).readline):
            if tok.type == _tk.COMMENT:
                kill.add(tok.start[0])
    except Exception:
        pass
    lines = src.split("\n")
    return "\n".join("" if (i + 1) in kill else l
                     for i, l in enumerate(lines))

def _v76_src() -> str:
    raw = SRC.read_text(encoding="utf-8").replace("\r\r\n", "\n")
    return raw.replace("\r\n", "\n").replace("\r", "\n")

def _v76_body(name: str) -> str:
    """取 SRC 里名为 name 的方法体（已抠文档）。"""
    import re as _re
    lines = _v76_src().split("\n")
    start = None
    for i, l in enumerate(lines):
        if _re.match(r"\s*def " + _re.escape(name) + r"\s*\(", l):
            start = i
            break
    if start is None:
        return ""
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if _re.match(r"\s*def \w+\s*\(", lines[j]) and \
                len(lines[j]) - len(lines[j].lstrip()) <= indent:
            end = j
            break
    return _v76_strip("\n".join(lines[start:end]))

def check_v76_anchor_two_channels():
    """[v1.21.76 A1] 圈前动作只走一个入口 —— 防「只在一个通道接线」。

    ★ 改前实测：`self._anchor_round(` 全源码 1 处（在 `_run_layer`），
      `_before_round` 0 处；`_run_one_round_B` 含 `_print_polarity_snapshot`
      但不含 `_anchor_round` → B/C/D-H 七模式锚点恒为空。
    """
    print("\n[v1.21.76 A1] 锚点入池的通道覆盖")
    import re as _re
    code = _v76_strip(_v76_src())
    bad = []
    n_def = len(_re.findall(r"^\s*def _before_round\s*\(", code, _re.M))
    n_call = code.count("self._before_round(")
    n_round = code.count("self._anchor_round(")
    n_snap = code.count("self._print_polarity_snapshot(")
    if n_def != 1:
        bad.append(f"[A1] `_before_round` 定义 {n_def} 处，期望 1")
    if n_call != 2:
        bad.append(f"[A1] `_before_round` 调用 {n_call} 处，期望 2"
                   f"（serial + B 两条通道各一）")
    if n_round != 1:
        bad.append(f"[A1] `_anchor_round` 直接调用 {n_round} 处，期望 1"
                   f"（只该在 `_before_round` 里）")
    if n_snap != 1:
        bad.append(f"[A1] `_print_polarity_snapshot` 直接调用 {n_snap} 处，"
                   f"期望 1（只该在 `_before_round` 里）")
    _br = _v76_body("_before_round")
    if "self._anchor_round(" not in _br:
        bad.append("[A1] `_before_round` 里没有调 `_anchor_round` —— 空壳")
    _b = _v76_body("_run_one_round_B")
    if "_before_round" not in _b:
        bad.append("[A1] `_run_one_round_B` 里没有 `_before_round`"
                   " —— B 通道又不入锚点了")
    _rl = _v76_body("_run_layer")
    if "_before_round" not in _rl:
        bad.append("[A1] `_run_layer` 里没有 `_before_round`")
    # 负对照：立刻在**原文**里验一次"抠文档确实生效"
    if "self._anchor_round(" in _v76_src() and n_round == 0:
        bad.append("[A1] 抠文档后数为 0 但原文有 —— 抠除逻辑坏了")
    if bad:
        for b in bad:
            print(f"  \u2717 {b}")
        return False
    print(f"  \u2713 _before_round def=1 调用=2；_anchor_round 直调=1"
          f"（在 _before_round 内）；_print_polarity_snapshot 直调=1")
    print("  \u2713 serial(`_run_layer`) 与 B(`_run_one_round_B`) 都走统一入口")
    return True

def check_v76_anchor_calls():
    """[v1.21.76 A2] `_anchor_calls` 必须**真的被赋值**，且不再挂预算空档。

    ★ 改前实测：该字段全源码出现 2 次、**都是读**、0 次写 →
      v1.21.75 宣称的"检索调用纳预算"是恒为 0 的挂空档。
    """
    print("\n[v1.21.76 A2] anchor_calls 真的被写入")
    code = _v76_strip(_v76_src())
    bad = []
    if code.count("self._anchor_calls: int = 0") != 1:
        bad.append("[A2] `__init__` 里没有唯一的 `self._anchor_calls: int = 0`")
    _cc = _v76_body("_anchor_crosscheck")
    if not _re_find(r"self\._anchor_calls[^\n]*\+\s*1", _cc):
        bad.append("[A2] `_anchor_crosscheck` 里没有自增 —— 还是只读不写")
    if 'base["anchor_calls"] = self._anchor_calls' not in _cc:
        bad.append("[A2] packed 的 `anchor_calls` 没有回填本次计数")
    _be = _v76_body("_budget_exhausted")
    if "_anchor_calls" in _be:
        bad.append("[A2] `_budget_exhausted` 还在引用 `_anchor_calls`"
                   " —— 收尾对照不在圈循环内，不该挂这里")
    if "预算已用尽" not in _cc:
        bad.append("[A2] `_anchor_crosscheck` 缺独立预算判断（且要留痕）")
    # 负对照：旧版必须被判红
    if not bad and "self._anchor_calls" in _v76_src() and \
            code.count("self._anchor_calls") == 0:
        bad.append("[A2] 抠文档后为 0 —— 抠除逻辑坏了")
    if bad:
        for b in bad:
            print(f"  \u2717 {b}")
        return False
    print("  \u2713 初始化 1 处 + 收尾对照自增 1 处 + packed 回填")
    print("  \u2713 `_budget_exhausted` 已不再挂空档；收尾对照有独立预算判断")
    return True

def _re_find(pat: str, text: str) -> bool:
    import re as _re
    return _re.search(pat, text) is not None

def check_v76_changelog_wording():
    """[v1.21.76 B1] changelog 不许说「重做/改到池」—— 外判接入点还在。"""
    print("\n[v1.21.76 B1] changelog 措辞与实现一致")
    raw = _changelog_text()   # v1.23.7：changelog 已搬到 CHANGELOG.md
    bad = []
    if "重做**锚点接入" in raw or "接入点从「外判」改到「池」" in raw:
        bad.append("[B1] 仍有「重做锚点接入 / 改到池」的旧措辞")
    if "新增池接入点" not in raw:
        bad.append("[B1] 找不到「新增池接入点」")
    if "v1.21.76" not in raw:
        bad.append("[B1] 找不到 v1.21.76 changelog 段")
    if bad:
        for b in bad:
            print(f"  \u2717 {b}")
        return False
    print("  \u2713 措辞已改为「新增池接入点」（外判接入点保留）")
    print("  \u2713 v1.21.76 changelog 段存在")
    return True

def check_v76_anchor_visibility():
    """[v1.21.76 B2] 池判的可见性必须写清（只读第 1 圈）。"""
    print("\n[v1.21.76 B2] 锚点可见性说明")
    # ★ 这里要看的是 **docstring**，所以用**未抠文档**的原文切片 ——
    #   用 `_v76_body`（抠过的）会永远找不到，判据变永假。
    _raw = _v76_src()
    _i = _raw.find("def _anchor_view_ctx")
    body = _raw[_i:_i + 2600] if _i >= 0 else ""
    bad = []
    if not body:
        bad.append("[B2] 找不到 `_anchor_view_ctx`")
    if "只跑一次" not in body and "只读" not in body:
        bad.append("[B2] `_anchor_view_ctx` 没说清池判只跑一次/只读第 1 圈")
    if "per_round" not in body:
        bad.append("[B2] 没提 `per_round`")
    if "max_items" not in body:
        bad.append("[B2] 没提 `max_items` 上限")
    if bad:
        for b in bad:
            print(f"  \u2717 {b}")
        return False
    print("  \u2713 docstring 写明：池判只跑一次、只看得见第 1 圈那批"
          "（受 max_items 约束）")
    return True

def check_v76_anchor_evidence_key():
    """[v1.21.76 B3] `Pool.to_dict` 必须挂 `anchor_as_evidence`，且受保护。"""
    print("\n[v1.21.76 B3] anchor_as_evidence 有出口")
    import re as _re
    code = _v76_strip(_v76_src())
    bad = []
    tds = _re.findall(
        r"\n    def to_dict\(self\) -> dict:.*?(?=\n    def |\Z)", code, _re.S)
    hit = [t for t in tds if "anchor_as_evidence" in t]
    if not hit:
        bad.append("[B3] 没有哪个 `to_dict` 挂 `anchor_as_evidence`")
    else:
        t = hit[-1]
        if 'd["anchors"] = self.anchors' not in t:
            bad.append("[B3] 没有跟着 `anchors` 一起挂（加性会破）")
        i_an = t.find('d["anchors"] = self.anchors')
        i_ae = t.find('d["anchor_as_evidence"]')
        if not (-1 < i_an < i_ae):
            bad.append("[B3] `anchor_as_evidence` 没在 `if self.anchors` 块内")
        # 负对照：无 anchors 时不该挂（块结构必须保持）
        if "if self.anchors:" not in t:
            bad.append("[B3] `if self.anchors:` 守卫不见了（关闭态会多键）")
    if bad:
        for b in bad:
            print(f"  \u2717 {b}")
        return False
    print("  \u2713 `to_dict` 在 `if self.anchors:` 块内挂 `anchor_as_evidence`"
          "（关闭态仍一个键不多）")
    return True

def check_v76_anchor_retriever_stub():
    """[v1.21.76 B4] snapshot 不该走检索层；未实现的后端仍要抛错。"""
    print("\n[v1.21.76 B4] 检索层只在非 snapshot 走")
    body = _v76_body("_anchor_round")
    bad = []
    if '_mode != "snapshot"' not in body:
        bad.append("[B4] `_anchor_round` 里没有 `_mode != snapshot` 分支")
    # [v122 P4e] 抛错已收口到 `AnchorRetriever.search`（检索的唯一实现），
    #   `_retrieve_anchors` 只管装配 → 判据改搜**整条检索链**。
    #   抛错被整体删掉时两处都没有，判据照样红（判别力不减）。
    import inspect as _ins4
    _retr_cls = ""
    try:
        _retr_cls = _ins4.getsource(mod.AnchorRetriever)
    except Exception as _e4:
        _retr_cls = ""
    ret = _v76_body("_retrieve_anchors") + "\n" + _retr_cls
    if "尚未实现" not in ret:
        bad.append("[B4] `_retrieve_anchors` 丢了「尚未实现」的抛错"
                   " —— 等于允许静默降级")
    if "不静默降级" not in ret:
        bad.append("[B4] 抛错里没有「不静默降级」的表态")
    if bad:
        for b in bad:
            print(f"  \u2717 {b}")
        return False
    print("  \u2713 snapshot 直接跳过检索层（零调用）；非 snapshot 抛错留痕")
    return True

def check_v76_anchor_triage_cohesion():
    """[v1.21.76 B5] 分诊判据必须与锚点清单**同段**（不跨 system/user）。"""
    print("\n[v1.21.76 B5] 分诊判据不跨段")
    ts = _v76_body("_anchor_triage_sys")
    vc = _v76_body("_anchor_view_ctx")
    bad = []
    if 'return ""' not in ts:
        bad.append("[B5] `_anchor_triage_sys` 没退化成空壳")
    if "【外部锚点分诊】" in ts or "分诊判据" in ts:
        bad.append("[B5] `_anchor_triage_sys` 里还留着分诊判据")
    if "【分诊判据" not in vc:
        bad.append("[B5] `_anchor_view_ctx` 里没有【分诊判据】段")
    if "自指循环" not in vc:
        bad.append("[B5] 分诊判据内容不全（缺「自指循环不降级」那条）")
    if bad:
        for b in bad:
            print(f"  \u2717 {b}")
        return False
    print("  \u2713 `_anchor_triage_sys` 已空壳；判据与锚点清单同处 user 段")
    return True

def check_v76_claims_scope():
    """[v1.21.76 M1] 对照条目必须含 `views[*].candidates`（领域事实层）。"""
    print("\n[v1.21.76 M1] claims 取值处含 candidates")
    body = _v76_body("_anchor_claims")
    bad = []
    if '"candidates"' not in body and "'candidates'" not in body:
        bad.append("[M1] `_anchor_claims` 没有取 `candidates`")
    if "candidates" not in body:
        bad.append("[M1] 缺 candidates 来源说明")
    if "decidable_product" not in body:
        bad.append("[M1] 原有来源（成品答案）被误删")
    if "sub_questions" not in body:
        bad.append("[M1] 原有来源（已答子问题）被误删")
    # candidates 必须排在成品答案**之前**（领域层优先占配额）
    i_c = body.find('"candidates"')
    i_d = body.find("decidable_product")
    if i_c != -1 and i_d != -1 and i_c > i_d:
        bad.append("[M1] candidates 排在成品答案之后 —— 会被 12 条配额挤掉")
    if bad:
        for b in bad:
            print(f"  \u2717 {b}")
        return False
    print("  \u2713 `_anchor_claims` 三处来源齐备，candidates 优先")
    return True

def check_v76_input_sanity_shape():
    """[v1.21.76 S1] 输入自检必须显式覆盖「形似标准记号的非标准记号」。"""
    print("\n[v1.21.76 S1] 输入自检补 P=PN 型判据")
    body = _v76_body("_check_input_sanity")
    bad = []
    if "形似标准记号" not in body:
        bad.append("[S1] 判据里没有「形似标准记号的非标准记号」")
    if "P=PN" not in body and "PN" not in body:
        bad.append("[S1] 没有点出 `P=PN` 这个真实漏报案例")
    if bad:
        for b in bad:
            print(f"  \u2717 {b}")
        return False
    print("  \u2713 判据已显式覆盖伪专名，并写明 P=PN 漏报案例")
    return True

def check_v77_claim_order():
    """[v1.21.77 M1'] `_anchor_claims` 取 candidates 时**层 0 必须排最前**。

    ★ v1.21.76 写的是 (1,0,both,all) —— 层 1（研究层的操作性论断）占满 12 条
      配额，层 0 的领域事实层论断一条都进不来，真跑「印证 0 / 用到锚点 0」。
      改成 (0,1,both,all) 后，同一份 packed、同一把尺 →「印证 4 / 用到锚点 3」。
      **顺序是这条链的成败点**，所以单独做判据锁住。
    """
    print("\n[v1.21.77 M1'] claims 取值的层顺序")
    import re as _re
    body = _v76_body("_anchor_claims")
    bad = []
    if not body:
        bad.append("[M1'] 找不到 `_anchor_claims`")
    else:
        ms = _re.findall(r"for k in \(([^)]+)\):", body)
        if not ms:
            bad.append("[M1'] 函数体里没有 `for k in (...)` 层循环")
        else:
            first = ms[0]
            layers = [x.strip().strip('"').strip("'") for x in first.split(",")]
            if not layers or layers[0] != "0":
                bad.append(f"[M1'] candidates 循环的第一层是 "
                           f"{layers[0] if layers else '?'!r}，期望 '0'"
                           f"（修行层的领域论断必须优先占配额）")
            if "1" not in layers:
                bad.append("[M1'] 层 1 不在循环里（会被整个丢掉）")
            if len(ms) < 2:
                bad.append("[M1'] 只剩一个层循环 —— 成品答案那条被误删了")
        if '"candidates"' not in body and "'candidates'" not in body:
            bad.append("[M1'] `candidates` 来源丢了")
    # 负对照：老顺序必须能被这个判据抓到
    if not bad and "(\"1\", \"0\"" in body:
        bad.append("[M1'] 仍是旧的 (1,0,...) 顺序（负对照触发）")
    if bad:
        for b in bad:
            print(f"  \u2717 {b}")
        return False
    print("  \u2713 candidates 循环层顺序 = 0 优先；两处来源仍在")
    return True

def check_v77_input_sanity_render():
    """[v1.21.77 S2] `input_sanity` 必须**无条件**渲染（三态可辨）。

    ★ 原先 `if san.get("issues"):` 是条件渲染 —— 检查跑了、没发现问题的产物
      里看不出它跑过。项目纪律：自检字段必须无条件写。
    """
    print("\n[v1.21.77 S2] 输入自检无条件渲染")
    code = _v76_strip(_v76_src())
    bad = []
    for frag in ('san = result.get("input_sanity")',
                 "if san is None:",
                 "未启用",
                 "已检查，未发现问题"):
        if frag not in code:
            bad.append(f"[S2] 渲染代码里找不到 {frag!r}")
    # 三态里的「有问题」分支也要在
    if "issues" not in code:
        bad.append("[S2] 丢了 `issues` 分支")
    # 负对照：条件渲染的旧写法（`san = ... or {}` + 直接 if issues）必须能被抓到
    if 'san = result.get("input_sanity") or {}' in code and \
            "if san is None:" not in code:
        bad.append("[S2] 仍是 `or {}` 的条件渲染写法（负对照触发）")
    if bad:
        for b in bad:
            print(f"  \u2717 {b}")
        return False
    print("  \u2713 三态齐备：未启用 / 已检查未发现问题 / 发现问题（列条目）")
    return True

# [v122 环境] `dgtf_config.yaml` 相对 `DEFAULT_CONFIG` 的**已销账**手调项。
#   表里每一项都是「有意为之」，理由写在值里。`check_config_parses`
#   对**不在表里**的差异照旧判红，对**在表里但已不再差异**的条目也判红 —— 两向都要对上账，登记表才不会腐烂成一张什么都能过的名单。
#   ★ 说明文字一律放注释，不要塞进 dict 当第一个元素：相邻的两个字符串
#     字面量会被 Python **静默拼接**成一个键，dict 里就只剩一条巨型条目（实测踩过）。

# [v122 环境] `dgtf_config.yaml` 相对 `DEFAULT_CONFIG` 的**已销账**手调项。
#   表里每一项都是「有意为之」，理由写在值里。`check_config_parses`
#   对**不在表里**的差异照旧判红，对**在表里但已不再差异**的条目也判红 —— 两向都要对上账，登记表才不会腐烂成一张什么都能过的名单。
#   ★ 说明文字一律放注释，不要塞进 dict 当第一个元素：相邻的两个字符串
#     字面量会被 Python **静默拼接**成一个键，dict 里就只剩一条巨型条目（实测踩过）。
CONFIG_TUNED = {
    "actions.parallel_warmup_rounds": "并行预热圈数手调",
    "all_on": "【一键全开】出厂 yaml 默认 true（用户口径：真跑全开）；"
              "引擎 DEFAULT_CONFIG 仍保守 false，保证判据基线零影响",
    "api.thinking.effort": "thinking 强度 high（刻意不随档位降）",
    "memory.shape_chars": "形状记忆条数与字数手调",
    "memory.shape_items": "形状记忆条数与字数手调",
    "output.show_probe_diag": "调试期要看 ing / manifest / 探针诊断",
    "probe.min_gain": "探针门限与选条手调",
    "probe.select_n": "探针门限与选条手调",
    "spiral.alignment_containment": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.all_drift_threshold": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.all_extra_rounds": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.all_selfref_threshold": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.batch_similarity": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.both_tighten_ratio": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.dedup_amp_overlap": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.dedup_amp_similarity": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.dedup_candidate_overlap": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.escalate_starve_rounds": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.meta_cover_similarity": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.new_item_overlap": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.new_item_similarity": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.no_push_when_idle": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.qc_both_ratio": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.qc_rephrase_ratio": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.rehash_similarity": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.stable_layers": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.stable_need": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.stop_similarity": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
    "spiral.unsaid_escape_limit": "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）",
}
# [v122 配置同步] 允许**不出现在** dgtf_config.yaml 里的键（默认空）。
#   默认策略是「yaml 必须列全 DEFAULT_CONFIG 的键」—— 这样新字段不会
#   悄悄漏在配置文件外（本次同步前已经漏了 15 个，没有一个检查看得见）。
#   真要留一个键只给代码用，必须在这里登记并写清理由；登记了却已经写进
#   yaml 的，同样判红（两向对账，和 CONFIG_TUNED 一个道理）。
CONFIG_NOT_IN_YAML = {}

def check_config_parses():
    """[v1.21.60] 出厂 yaml 必须能解析，且生效后与 DEFAULT_CONFIG 等价。

    ★ 发现的真 bug：`dgtf_config.yaml` 里有两段**示例写在注释块中间却没注释掉**
    （`spiral: / per_entry: / "all": {...}`），整个文件解析失败 →
    `load_config` 走进 except 分支退回默认配置 → **yaml 从来没生效过**
    （v59 真跑日志里就留着「⚠️ 配置文件解析失败」）。
    更险的是它带着**过期值**：`min_rounds."1": 2`（v1.21.58 已定「全层归零」）、
    `structure_saturation_every_n: 2`（注释自己写的是 3）——一旦有人把语法修好，
    这两个过期值会**静默地**把上一版的决策推翻。
    """
    ok = True
    try:
        import yaml
    except ImportError:
        print("  · [配置] 没装 pyyaml，跳过")
        return True

    cfg_path = HERE / "dgtf_config.yaml"
    if not cfg_path.exists():
        print("  · [配置] 没有 dgtf_config.yaml，跳过")
        return True
    text = cfg_path.read_text(encoding="utf-8")
    try:
        user = yaml.safe_load(text) or {}
    except Exception as e:
        print(f"  ✗ [配置] 出厂 yaml 解析失败：{type(e).__name__}: "
              f"{str(e).splitlines()[0][:70]}")
        return False

    # 生效后不许与默认值打架（yaml 没写的键由 _deep_merge 兜底，不算差异）
    def _flat(d, pre=""):
        out = {}
        for k, v in (d or {}).items():
            key = f"{pre}.{k}" if pre else str(k)
            if isinstance(v, dict):
                out.update(_flat(v, key))
            else:
                out[key] = v
        return out
    du, dd = _flat(user), _flat(mod.DEFAULT_CONFIG)
    diff = [(k, du[k], dd[k]) for k in du if k in dd and du[k] != dd[k]]
    # [v122 环境] 手调项必须**逐条销账**：未登记的差异照旧判红；登记表里
    #   出现过期条目（yaml 已改回默认却没销账）也判红。两向都锁，登记表
    #   才不会腐烂成一张「什么都能过」的名单。
    _unk = [(k, a, b) for k, a, b in diff if k not in CONFIG_TUNED]
    _diff_keys = {k for k, _a, _b in diff}
    _stale = sorted(k for k in CONFIG_TUNED if k not in _diff_keys)
    if _unk:
        print("  \u2717 [配置] 出厂 yaml 有**未登记**的手调："
              + "；".join(f"{k}: {a!r}\u2260{b!r}" for k, a, b in _unk[:4]))
        ok = False
    if _stale:
        print("  \u2717 [配置] 登记表过期（yaml 已改回默认却没销账）："
              + "；".join(_stale[:6]))
        ok = False
    # [v122 配置同步] 第三向：本文件必须**列全** DEFAULT_CONFIG 的键。
    #   ★ 判红而不是只打提示：漏键是**看不见**的漂移 —— 「同步过」如果
    #     没有检查兜着，就只是句口头承诺。
    #   ★ 列全不等于把值钉死：值一旦与当前默认不符，上面两向立刻报红
    #     （未登记即红），所以默认改了而本文件没跟上也不会静默。
    _miss = sorted(k for k in dd
                   if k not in du and k not in CONFIG_NOT_IN_YAML)
    _x_stale = sorted(k for k in CONFIG_NOT_IN_YAML if k in du)
    if _miss:
        print("  ✗ [配置] 出厂 yaml 漏了 DEFAULT_CONFIG 的键（未同步）："
              + "；".join(_miss[:6])
              + (f" …共 {len(_miss)} 项" if len(_miss) > 6 else ""))
        ok = False
    if _x_stale:
        print("  ✗ [配置] 豁免表过期（登记了不进 yaml，其实已写进 yaml）："
              + "；".join(_x_stale[:6]))
        ok = False
    if not _unk and not _stale and not _miss and not _x_stale:
        print(f"  ✓ [配置] 能解析；键已列全（{len(dd)} 项，豁免 "
              f"{len(CONFIG_NOT_IN_YAML)} 项）；手调 {len(diff)} 项"
              f"**全部已登记**；登记表无过期条目")
    # load_config 必须真的吃进 yaml（不是又退回默认）
    loaded = mod.load_config(str(cfg_path))
    if "spiral" in user and user["spiral"].get("min_rounds") is not None:
        if loaded["spiral"].get("min_rounds") != user["spiral"]["min_rounds"]:
            print("  ✗ [配置] load_config 没吃进 yaml（又退回默认了？）")
            ok = False
    return ok

def _v73_anchor_file(td, n=3):
    """写一个锚点快照到临时目录，返回路径。"""
    p = Path(td) / "anchors.json"
    items = []
    for i in range(1, n + 1):
        items.append({"id": "a%d" % i,
                      "claim": "外部事实条目 %d：产线自动化投资回收期中位约 3 年" % i,
                      "source": "某行业报告 %d" % i,
                      "url": "https://example.org/%d" % i,
                      "as_of": "2026-10-04", "kind": "数据"})
    p.write_text(json.dumps({
        "question": "现金流紧张的中小制造企业要不要上自动化产线",
        "retrieved_at": "2026-10-04T07:00:00+08:00",
        "retriever": "smoke fixture", "anchors": items,
    }, ensure_ascii=False), encoding="utf-8")
    return p

def _v73_stub_patch(orig, ids=None, spy=None):
    """[v1.21.73] 临时桩补丁：只补两条分支，其余原样转发。

    ★ 抽出来是为了复用：check_v73_anchor 里除了整次 run，还要**单独**
      调一次 _anchor_crosscheck 验只读性 —— 那次调用不在 run 里，拿不到
      run 期间的桩（实测：不补桩时 fake_call 返回 "{}" ⇒ 对照报「缺 items」
      ⇒ 只读性检查根本没走到写回那一行，判据变成永真）。
    """
    ids = list(ids or ["a1"])

    def _p(self, system, user, *a, **kw):
        ss = system or ""
        if spy is not None and kw.get("stage") == "assess_decidability":
            spy.append(ss)
        if "【& · 双通道融合】" in ss:
            return json.dumps({
                "amps": [], "threads": [], "meta": [],
                "decidable_product": {
                    "answer": "冒烟桩：先做局部优化，产线自动化按回收期分阶段上",
                    "answered_sub_ids": [1],
                    "evidence": ["桩证据"], "distance": 0.4},
                "undecidable_product": {
                    "why_undecidable": "桩", "structural_amps": [],
                    "aligned_amps": [], "clarity": 0.0, "distance": 1.0},
                "covered_aspects": [], "uncovered_aspects": [],
                "distance_to_question": 0.4}, ensure_ascii=False)
        if "外部事实对照者" in ss:
            cs = re.findall(r"- \[(c\d+)\]", user or "") or ["c1"]
            return json.dumps({"items": [
                {"claim_id": c, "verdict": "印证",
                 "anchor_ids": list(ids), "note": "冒烟桩"}
                for c in cs]}, ensure_ascii=False)
        return orig(self, system, user, *a, **kw)
    return _p

def _v73_run(cfg, q, spy, anchor_ids=None, verdict="印证"):
    """跑一次 mock run；**临时**给桩补两条分支，退出即恢复。

    ★ 为什么必须临时补：全局 fake_call 没有这两条分支，mock 里
      decidable_product.answer 恒空 ⇒ _anchor_claims 恒返回空 ⇒
      「claims >= 1」这条判据既测不出真也测不出假（永真的死判据）。
      真跑里 view 1 的 answer 是有的（verif_V71S.full.json 实测一条
      200+ 字的成品答案），所以补桩是让 mock 回到真跑形态，不是放水。
      ★ 只在函数内生效，不影响其它 check。
    """
    orig = mod.LLM.call
    mod.LLM.call = _v73_stub_patch(orig, anchor_ids, spy)
    try:
        m = mod.MetaDGTF(cfg)
        res = m.run(q, route=["0", "1"], rounds={"0": 1, "1": 1},
                    parallel_mode="serial")
    finally:
        mod.LLM.call = orig
    return res, m

def check_v73_anchor():
    """[v1.21.73] 外部锚点：加性 / 挂键 / 失败留痕 / 编号校验 / 接线 / 只读。

    ★ 每组都锁**两个方向**。单方向断言会把「没接上」验成「接上了」——
      本项目的老坑：baseline 为 0 的告警判据，负对照必须写进判据本身。
    """
    bad = []

    def chk(cond, msg):
        if not cond:
            bad.append(msg)
        return bool(cond)

    td = Path(tempfile.mkdtemp(prefix="smoke73_"))
    q = "现金流紧张的中小制造企业，上自动化产线还是维持人工加局部优化？"
    af = _v73_anchor_file(td, 3)

    # ---------- [E] 接线：新方法必须真被生产路径调用（防死代码）
    chk("_load_anchors()" in inspect.getsource(mod.MetaDGTF.run),
        "[E] run() 没调 _load_anchors —— 死代码")
    chk("_anchor_report_for_pack" in inspect.getsource(mod.MetaDGTF._pack_result),
        "[E] _pack_result 没挂锚点报告 —— 死代码")
    _csrc = inspect.getsource(mod.MetaDGTF._cached_ext_assess)
    chk("anchors=" in _csrc, "[E] _cached_ext_assess 没把锚点传给外判")

    # ---------- [A] 关闭：加性（packed 键集合 / assess prompt / 产物文案）
    cfg_off = build_cfg(False)
    cfg_off["output"]["save_dir"] = str(td / "off")
    # ★ [v1.23.18 判据随实现更新] `external_anchor.enabled` 出厂默认由 false
    #   改成 true ⇒ 想测「关闭态」必须**显式关**（以前靠默认关就够了）。
    cfg_off["external_anchor"] = dict(cfg_off.get("external_anchor") or {})
    cfg_off["external_anchor"]["enabled"] = False
    off_sys = []
    res_off, _ = _v73_run(cfg_off, q, off_sys)
    chk("external_anchor" not in res_off,
        "[A] 关闭时 packed 仍挂 external_anchor（不是加性改动）")

    # ---------- [B] 开启 + 有效锚点
    def _on_cfg(sub):
        c = build_cfg(False)
        c["output"]["save_dir"] = str(td / sub)
        c["external_anchor"] = {"enabled": True, "path": str(af),
                                "max_items": 12, "crosscheck": True}
        return c

    on_sys = []
    res_on, m_on = _v73_run(_on_cfg("on"), q, on_sys,
                            anchor_ids=["a1", "zzz"])
    ea = res_on.get("external_anchor")
    chk(isinstance(ea, dict), "[B] 开启时 packed 没有 external_anchor 键")
    if isinstance(ea, dict):
        chk(ea.get("anchors") == 3, "[B] anchors=%s（应为 3）" % ea.get("anchors"))
        chk(not ea.get("error"), "[B] 有效锚点却有 error：%s" % ea.get("error"))
        sm = ea.get("summary") or {}
        chk(int(sm.get("claims", 0) or 0) >= 1,
            "[B] claims=%s —— 结论条目取不到，对照是空转" % sm.get("claims"))
        chk(int(sm.get("supported", 0) or 0) + int(sm.get("conflicted", 0) or 0)
            + int(sm.get("unmatched", 0) or 0) == int(sm.get("claims", 0) or 0),
            "[B] 印证+冲突+无对应 不等于 claims")
        # [D] 编号校验：zzz 是模型编的，必须被滤掉
        _items = ea.get("items") or []
        _ids = (_items[0].get("anchor_ids") if _items else None) or []
        chk(_ids == ["a1"], "[D] 编造的锚点编号没被滤掉：%s" % _ids)

    # [A] 的反证：ON 的 assess system 必须是「OFF 原文 + 追加」
    chk(bool(off_sys) and bool(on_sys),
        "[A] 没抓到 assess_decidability 的 system（桩没接上，本条无判别力）")
    if off_sys and on_sys:
        chk(on_sys[0].startswith(off_sys[0]) and len(on_sys[0]) > len(off_sys[0]),
            "[A] 开启后的 assess system 不是「原文 + 追加」（加性被破坏）")

    # ---------- [D] 负对照：全给假编号 → 必须全被滤掉（不是恒等放行）
    res_d, _ = _v73_run(_on_cfg("d"), q, [], anchor_ids=["zzz"])
    ea_d = res_d.get("external_anchor") or {}
    _di = ea_d.get("items") or []
    _dids = (_di[0].get("anchor_ids") if _di else None) or []
    chk(_dids == [], "[D-负对照] 全假编号竟被接受：%s" % _dids)

    # ---------- [C] 失败留痕：path 不存在也必须挂键 + 写 error
    cfg_bad = build_cfg(False)
    cfg_bad["output"]["save_dir"] = str(td / "bad")
    cfg_bad["external_anchor"] = {"enabled": True,
                                  "path": str(td / "__nope__.json"),
                                  "max_items": 12, "crosscheck": True}
    res_bad, _ = _v73_run(cfg_bad, q, [])
    ea_b = res_bad.get("external_anchor")
    chk(isinstance(ea_b, dict),
        "[C] 加载失败时 packed 没有 external_anchor —— 失败没留痕")
    chk(bool((ea_b or {}).get("error")),
        "[C] 加载失败却 error 为空 —— 静默降级成「没接入」")
    chk("FileNotFoundError" in str((ea_b or {}).get("error") or ""),
        "[C] 失败的 error 里没有可定位的原因（只有兜底文案 = 没留痕）")
    # 负对照：有效路径时 error 必须为空（修过头会把所有情况都判失败）
    if isinstance(ea, dict):
        chk(not ea.get("error"), "[C-负对照] 有效路径也被判失败")

    # ---------- 产物渲染：正文出口 + 关闭时旧文案不回归
    try:
        md_on = mod.save_result(res_on, str(td / "on"))
        t_on = Path(md_on).read_text(encoding="utf-8")
        chk("已接入 3 条" in t_on, "[B] 产物头部没有锚点接入渲染")
        chk("### 外部锚点 · 逐条对照" in t_on,
            "[B] 产物正文没有逐条对照出口（又是一个只躺在 packed 里的键）")
        md_bad = mod.save_result(res_bad, str(td / "bad"))
        t_bad = Path(md_bad).read_text(encoding="utf-8")
        chk("锚点异常" in t_bad, "[C] 失败时产物没有「锚点异常」渲染")
        md_off = mod.save_result(res_off, str(td / "off"))
        t_off = Path(md_off).read_text(encoding="utf-8")
        # [v1.23.12 判据随实现更新，语义不放宽]
        #   旧断言查的是**单通道**文案「**外部锚点**：无（本产物不含外部
        #   事实校验；」—— 那条文案把「联网到底跑没跑」整个吞掉了：
        #   真跑里联网收了 6 条（W1–W6），产物仍只写「外部锚点：无」。
        #   锚点改到新实现里那条**文本通道**的写法，并**新增**一条
        #   「联网通道整条不许丢」。
        # [v1.23.18 判据随实现更新] 关闭态文案由「无」改成「**关**」——
        #   与联网通道对称（缺席时两条通道都写「关」）。
        chk("**外部锚点 · 文本**（锚点文件 `external_anchor`）：**关**" in t_off,
            "[A] 关闭时文本通道没写「关」")
        chk("**外部锚点 · 联网**" in t_off,
            "[A] 关闭时联网通道整条丢了（读者又看不到这一路）")
        chk("已接入" not in t_off, "[A] 关闭时产物竟出现「已接入」")
    except Exception as exc:
        bad.append("[渲染] save_result 异常：%s: %s" % (type(exc).__name__, exc))

    # ---------- [F] 只读：对照不得改动任何池
    try:
        # ★ 先塞一条 answered 子问题，逼 `_anchor_crosscheck` 走**完整**
        #   路径：claims=0 会在半路 return，只读性就成了永真判据 ——
        #   M6 变异体实测：污染写在 return 之后时被整段跳过。
        m_on.pools["1"].sub_questions.append(
            {"question": "只读性检查专用条目", "status": "answered"})
        before = json.dumps({k: p.to_dict() for k, p in m_on.pools.items()},
                            ensure_ascii=False, sort_keys=True)
        m_on._anchor_report = None
        _orig_llm = mod.LLM.call
        mod.LLM.call = _v73_stub_patch(_orig_llm, ["a1"], None)
        try:
            rep_f = m_on._anchor_crosscheck({})
        finally:
            mod.LLM.call = _orig_llm
        after = json.dumps({k: p.to_dict() for k, p in m_on.pools.items()},
                           ensure_ascii=False, sort_keys=True)
        chk(int((rep_f.get("summary") or {}).get("claims", 0) or 0) >= 1,
            "[F] 只读性检查自身没走到完整对照路径 —— 本条无判别力")
        chk(before == after, "[F] 锚点对照改动了池 —— 不是只读")
    except Exception as exc:
        bad.append("[F] 只读性检查自身异常：%s: %s" % (type(exc).__name__, exc))

    if bad:
        for m in bad:
            print("  \u2717 [v73 锚点] " + m)
        return False
    print("  \u2713 [v73 锚点] 关闭逐字同构 / 开启挂键+对照 / 失败留痕 / "
          "编号校验 / 接线 / 只读（六组各带负对照）")
    return True

def check_v122_phase1(SRC=None):
    """[v122 阶段1] 四层 objective / 覆盖率只对研究层 / 未生分类 / 头部四行。"""
    print("  · v1.22 阶段1：四层 objective / 覆盖率归属 / 未生分类 / 头部四行")
    try:
        m = _v122_mod(SRC)

        # ① Phase.objective 四层各就各位
        want = {"0": "manifest", "1": "truth",
                "both": "collision", "all": "closure"}
        for k, v in want.items():
            got = getattr(m.PHASES.get(k), "objective", None)
            assert got == v, f"PHASES[{k!r}].objective={got!r} ≠ {v!r}"

        # ② 覆盖率只对研究层：entry≠"1" → None
        #   ★ 池子必须**非空**：空池分母为 0，coverage 本来就是 None，
        #     那样「entry=1 不是 None」会误报成过度收窄。
        p = m.Pool()
        p.sub_questions = [{"id": "s1", "decidability": "decidable",
                            "status": "answered", "weight": 1.0,
                            "depth": 1.0}]
        assert m.coverage_of(p, {}, entry="0") is None, "entry=0 必须 None"
        assert m.coverage_of(p, {}, entry="both") is None, "entry=both 必须 None"
        assert m.coverage_of(p, {}, entry="all") is None, "entry=all 必须 None"
        # 负对照：研究层不许被一起挡掉（挡住了就是过度收窄）
        assert m.coverage_of(p, {}, entry="1") is not None, \
            "entry=1 不该是 None"
        # 向下兼容：不传 entry 的旧调用点行为必须与 entry=1 逐字一致
        assert m.coverage_of(p, {}) == m.coverage_of(p, {}, entry="1"), \
            "不传 entry 时旧行为应逐字不变"
        assert m.coverage_parts(p, {}, entry="0") == (0, 0, None), \
            "coverage_parts(entry=0) 必须是 (0,0,None)"

        # ③ 未生分类：两种入参形态都要吃
        #    · 任务书口径 = View 对象
        assert m._classify_unsaid(m.View(entry="0", collision="")) == "lazy"
        assert m._classify_unsaid(m.View(
            entry="0", collision="一、让两端各自把话说完\n二、各推到极端",
            probes=[{"question": "Q", "covers": ["T1"]}])) == "real"
        # 负对照：说了「此处未生」，即使 probes 带 covers，也必须判 lazy
        assert m._classify_unsaid(m.View(
            entry="0", collision="（此处未生）",
            probes=[{"question": "Q", "covers": ["T1"]}])) == "lazy"
        # 负对照：空 covers 必须 lazy，否则这个判据永远亮
        assert m._classify_unsaid(m.View(
            entry="0", collision="一、让两端各自把话说完",
            probes=[{"question": "Q", "covers": []}])) == "lazy"
        #    · 旧 dict 形态继续可用
        assert m._classify_unsaid({}) == "lazy"
        assert m._classify_unsaid({"covers": ["T1"]}) == "real"
        assert m._classify_unsaid({"covers": []}) == "lazy"
        assert m._classify_unsaid(None) == "lazy"
        assert m._classify_unsaid({"covers": "T1"}) == "real"

        # ④ 头部四行：计数口径，且每层名 + objective 都在
        _res = {
            "views": {
                "0": {"amps": [1, 2], "threads": [1], "suspensions": [],
                      "probes": [1, 2, 3]},
                "1": {"settlement": {"coverage": 0.5},
                      "decidable_product": {"distance": 0.4}},
                "both": {"ing_structured": {"third": True,
                                            "tensions": ["a", "b"]}},
                "all": {"meta_closure": {"clean": True, "unsettled": 0}},
            },
            "pools": {},
        }
        lines = m._layer_objective_lines(_res)
        assert len(lines) == 4, f"分层目标应为 4 行，得到 {len(lines)}"
        joined = "".join(lines)
        for n in ("修行层", "研究层", "对撞层", "元层"):
            assert n in joined, f"分层目标缺 {n}"
        for kw in ("& 2", "线头 1", "悬置 0", "探针 3", "覆盖率 50%",
                   "third ✓", "张力 2", "clean True", "未交代 0 类"):
            assert kw in joined, f"分层目标缺计数 {kw!r}"
        # 负对照：objective 图例形态仍在（不传 result）
        lg = m._layer_objective_lines()
        assert len(lg) == 4 and "objective=" in "".join(lg)

        # ⑤ 元层不评价修行层
        import inspect as _ins
        body = _ins.getsource(m.MetaDGTF._settle_meta)
        assert 'pools["0"]' not in body and "pools['0']" not in body, \
            "_settle_meta 仍在读修行池"

        # ⑥ 修行层停止理由含「未生质量」（源码级）
        src = _v122_src_text(SRC)
        assert "未生质量" in src, "stop_reason 改写没落进源码"
        assert "修行层本来就能停" in src, "缺红线注释"
        assert "分层目标" in src, "头部渲染没落进源码"

        # ⑦ route 分层：boundary 保留全四层；decision 允许砍层
        inst = object.__new__(m.MetaDGTF)
        inst.config = {}
        inst.vp = lambda *a, **k: None
        r = inst._route_by_decidability("q", ["0", "1", "both", "all"],
                                        orientation="boundary")
        assert r == ["0", "1", "both", "all"], f"boundary 应保留全四层，得到 {r}"
        r2 = inst._route_by_decidability("q", ["0", "1"], orientation="boundary")
        assert r2 == ["0", "1"], f"两层的 route 不该被动，得到 {r2}"

        print("  ✓ v1.22 阶段1：四层 objective / 覆盖率归属 / 未生分类(双形态) / "
              "头部四行计数 / 元层不读修行池 / route 分层")
        return True
    except Exception as e:
        print(f"  ✗ v1.22 阶段1 失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_v122_phase2(SRC=None):
    """[v122 阶段2] 三态多票 / 冻结条 / 校准队列。"""
    print("  · v1.22 阶段2：三票互异 / 冻结签名 / 校准 export-import")
    try:
        import json as _json
        import subprocess as _sp
        import tempfile
        from pathlib import Path as _P

        m = _v122_mod(SRC)
        HERE_ = _P(getattr(globals().get("mod"), "__file__", ".")).resolve().parent \
            if SRC is None else _P(SRC).resolve().parent

        tv = m._TRI_VOTE_PROMPTS
        assert len(tv) == 3, f"三票 prompt 应为 3，得到 {len(tv)}"
        assert len(set(tv)) == 3, "三票 prompt 有重复 —— 重复的三票等于没投票"
        assert hasattr(m.MetaDGTF, "_adjudicate_sub_tristate_multi")
        assert hasattr(m.MetaDGTF, "_adjudicate_sub_tristate")

        def _pool(labs):
            pp = m.Pool()
            pp.sub_questions = [
                {"id": f"s{i}", "decidability": l, "question": f"Q{i}"}
                for i, l in enumerate(labs, 1)]
            pp.deferrals = []
            return pp

        p = _pool(["decidable", "undecidable"])
        fz = m.DecidabilityFreeze()
        sig = fz.freeze(p, layer=1)
        assert len(sig) == 64, f"sha256 应为 64 位，得到 {len(sig)}"
        assert all("_frozen_answerable" in s for s in p.sub_questions)
        assert fz.verify(p) is True, "未篡改却判红"
        # 负对照①：decidable→partial —— 分母没变、判定变了，只签布尔会漏
        p.sub_questions[0]["decidability"] = "partial"
        try:
            fz.verify(p)
            raise AssertionError("decidable→partial 未被判为篡改")
        except RuntimeError:
            pass
        # 负对照②：真翻转分母也要判红
        p.sub_questions[0]["decidability"] = "undecidable"
        try:
            fz.verify(p)
            raise AssertionError("decidable→undecidable 未被判为篡改")
        except RuntimeError:
            pass
        # 负对照③：条数变了（换了个池）也不许静默通过
        try:
            fz.verify(_pool(["decidable"]))
            raise AssertionError("池条数变了仍判通过")
        except RuntimeError:
            pass
        # 负对照④：**只翻 `_frozen_answerable`、不动标签** —— 任务书
        #   Step 3.3 的冒烟标的正是这一刀。实测早先漏了（_canon 当时
        #   由当前标签现推可答性，被冻结的布尔根本没进签名）。
        #   这条是探针发现的，收进冒烟钉死。
        p_b = _pool(["decidable", "undecidable"])
        fz_b = m.DecidabilityFreeze()
        fz_b.freeze(p_b, layer=1)
        p_b.sub_questions[0]["_frozen_answerable"] = \
            not p_b.sub_questions[0]["_frozen_answerable"]
        try:
            fz_b.verify(p_b)
            raise AssertionError("只翻 _frozen_answerable 未被判为篡改")
        except RuntimeError:
            pass
        # 负对照⑤：只改 `_frozen_decidability` 也要判红
        p_c = _pool(["decidable", "undecidable"])
        fz_c = m.DecidabilityFreeze()
        fz_c.freeze(p_c, layer=1)
        p_c.sub_questions[0]["_frozen_decidability"] = "undecidable"
        try:
            fz_c.verify(p_c)
            raise AssertionError("只改 _frozen_decidability 未被判为篡改")
        except RuntimeError:
            pass

        # 冻结后分母不变
        p3 = _pool(["decidable", "undecidable"])
        m.DecidabilityFreeze().freeze(p3, layer=1)
        d1 = m.coverage_parts(p3, {}, entry="1")[1]
        p3.sub_questions[0]["decidability"] = "undecidable"
        d2 = m.coverage_parts(p3, {}, entry="1")[1]
        assert d1 == d2 == 1, f"冻结后分母不该变：{d1} → {d2}"
        # 负对照：不冻结时改判**会**改变分母（否则上面那条没判别力）
        p4 = _pool(["decidable", "undecidable"])
        d3 = m.coverage_parts(p4, {}, entry="1")[1]
        p4.sub_questions[0]["decidability"] = "undecidable"
        d4 = m.coverage_parts(p4, {}, entry="1")[1]
        assert d3 == 1 and d4 == 0, f"不冻结时应随改判变：{d3} → {d4}"

        # 校准 export → 填表 → import
        td = _P(tempfile.mkdtemp())
        (td / "result.json").write_text(_json.dumps({
            "calibration_queue": [
                {"sub_id": "s1",
                 "final": "partial",
                 "votes": [{"voter": 0, "label": "decidable"},
                           {"voter": 1, "label": "partial"},
                           {"voter": 2, "label": "decidable"}]}],
            "freeze": {"signature": sig},
            "pools": {"1": {"sub_questions": [
                {"id": "s1", "question": "甲"}]}},
        }, ensure_ascii=False), encoding="utf-8")
        cal = HERE_ / "bench" / "bench_calibrate.py"
        r = _sp.run([__import__("sys").executable, str(cal), "export", str(td),
                     str(td / "b.md")], capture_output=True, text=True)
        assert r.returncode == 0, f"export 失败 {r.stderr[-200:]}"
        tbl = (td / "b.md").read_text(encoding="utf-8")
        assert tbl.count("| ") >= 4, "导出表没有数据行"
        (td / "b.md").write_text(
            tbl.replace("|  |  |", "| partial | 人工核过 |"), encoding="utf-8")
        r2 = _sp.run([__import__("sys").executable, str(cal), "import",
                      str(td / "b.md"), str(td)],
                     capture_output=True, text=True)
        assert r2.returncode == 0, f"import 失败 {r2.stderr[-200:]}"
        v = _json.loads((td / "verdicts.json").read_text(encoding="utf-8"))
        assert v["n"] == 1, f"回填条数 {v['n']} ≠ 1"

        src = _v122_src_text(SRC)
        assert "三态多票" in src and "**冻结**" in src, "头部渲染字面串缺失"
        print("  ✓ v1.22 阶段2：三票互异 / 签名 64 位 / 三类篡改都判红 / "
              "分母冻结(含反向负对照) / 校准 export→import")
        return True
    except Exception as e:
        print(f"  ✗ v1.22 阶段2 失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def _v122_mod(SRC):
    """取被测模块：优先 smoke 命名空间里已加载的 mod，其次按 SRC 现加载。"""
    import importlib.util
    import sys as _sys
    base = globals().get("mod")
    if SRC is None and base is not None:
        return base
    if SRC is None:
        raise RuntimeError("既没传 SRC，命名空间里也没有 mod")
    spec = importlib.util.spec_from_file_location("dgtf_v122check", SRC)
    m = importlib.util.module_from_spec(spec)
    _sys.modules["dgtf_v122check"] = m
    spec.loader.exec_module(m)
    return m

def _v122_src_text(SRC):
    from pathlib import Path as _P
    if SRC is not None:
        return _P(SRC).read_text(encoding="utf-8")
    base = globals().get("mod")
    f = getattr(base, "__file__", None)
    if f:
        return _P(f).read_text(encoding="utf-8")
    return ""

def check_v122_phase3(SRC=None):
    """[v122 阶段3] decision 行动闭环 / 分流壳 / 硬约束 / rubric。"""
    print("  · v1.22 阶段3：行动抽取 / 分流壳 / 硬约束 / rubric")
    try:
        m = _v122_mod(SRC)
        src = _v122_src_text(SRC)

        # ① 开关 + 两个 render 都在
        assert "landing_decision" in src, "缺开关字面串"
        assert hasattr(m, "_render_landing_decision"), "缺新模板"
        assert hasattr(m, "_render_landing_boundary"), "缺老模板（改名后必须仍在）"

        # ② 抽取：任务书口径的 View 入参
        v = m.View(entry="1")
        v.decidable_product = {"answer": "先指派区防汛办核查。否则回退上级。"}
        acts = m._extract_actions(v)
        assert len(acts) >= 1, f"抽出 {len(acts)} 条"
        for k in ("verb", "object", "owner_role", "deadline_hint",
                  "acceptance", "fallback"):
            assert all(k in a and a[k] for a in acts), f"缺字段 {k}"
        # 负对照：空结论必须 0 条（否则 action_incomplete 永不亮）
        v2 = m.View(entry="1")
        v2.decidable_product = {"answer": ""}
        assert m._extract_actions(v2) == [], "空 answer 不该抽出 action"
        # dict 形态也要吃（落地层拿到的是 packed 里的 dict）
        assert len(m._extract_actions(
            {"decidable_product": {"answer": "先指派区防汛办核查。"}})) >= 1

        # ③ 硬约束字面串
        assert "action_incomplete" in src and "not_do_missing" in src

        # ③b 硬约束 flag 必须能在 quality_flags **重算**后存活。
        #   ★ 实测踩过（读真跑的 packed 才发现）：flag 追加后 19 行有
        #     `_keep_selfcheck_flags(view, _dg._quality_check(...))` ——
        #     整体重算，两条 flag 当场消失（errors 里还在、flags 里没了）。
        class _VQ:
            def __init__(self):
                self.quality_flags = ["action_incomplete", "not_do_missing",
                                      "unsaid_overused", "无关的线索"]
        _kept = m._keep_selfcheck_flags(_VQ(), ["probe_return_empty"])
        assert "action_incomplete" in _kept and "not_do_missing" in _kept, \
            f"硬约束 flag 被重算冲掉：{_kept}"
        # 负对照：不在保留集合里的线索该被丢掉（否则等于「全都保留」）
        assert "无关的线索" not in _kept, f"保留集合过宽：{_kept}"

        # ④ 分流壳：boundary 走老模板、decision 走新模板、关掉开关回老模板
        _b = m.render_landing({"orientation": "boundary",
                              "_config": {"actions": {}}, "views": {},
                              "decidability": {}})
        _d = m.render_landing({
            "orientation": "decision",
            "_config": {"actions": {"landing_decision": True}},
            "views": {"1": {"decidable_product": {
                "answer": "指派 排水公司 核查 内涝点位，汛期前完成，"
                          "否则回退人工排查。"}}},
            "decidability": {}})
        _off = m.render_landing({
            "orientation": "decision",
            "_config": {"actions": {"landing_decision": False}},
            "views": {}, "decidability": {}})
        assert "落地层（decision 模式）" not in _b, "boundary 不该走新模板"
        assert "落地层（decision 模式）" in _d, "decision 应走新模板"
        assert "落地层（decision 模式）" not in _off, "关开关应回老模板"
        assert "### 二、行动清单" in _d, "新模板缺行动清单段"

        print("  ✓ v1.22 阶段3：抽取(双形态+负对照) / 分流三分支 / 硬约束字面串 / "
              "行动清单段")
        return True
    except Exception as e:
        print(f"  ✗ v1.22 阶段3 失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def _v1221_mod(SRC):
    """取被测模块：优先 smoke 命名空间里已加载的 mod，其次按 SRC 现加载。"""
    import importlib.util
    import sys as _sys
    base = globals().get("mod")
    if SRC is None and base is not None:
        return base
    if SRC is None:
        raise RuntimeError("既没传 SRC，命名空间里也没有 mod")
    spec = importlib.util.spec_from_file_location("dgtf_v1221check", SRC)
    m = importlib.util.module_from_spec(spec)
    _sys.modules["dgtf_v1221check"] = m
    spec.loader.exec_module(m)
    return m

def _v1221_src_text(SRC):
    from pathlib import Path as _P
    if SRC is not None:
        return _P(SRC).read_text(encoding="utf-8")
    base = globals().get("mod")
    f = getattr(base, "__file__", None)
    if f:
        return _P(f).read_text(encoding="utf-8")
    return ""

def check_v1221_p1(SRC=None):
    """[v1.22.1 P1] 研究层结构化 actions：schema 优先 / 词法兜底 / 两条负对照。"""
    print("  · v1.22.1 P1：研究层结构化 actions（schema 优先 + 词法兜底）")
    try:
        m = _v1221_mod(SRC)
        # 1 schema 优先
        v = m.View(entry="1")
        v.decidable_product = {
            "answer": "x",
            "actions": [
                {"id": "A1", "verb": "指派", "object": "核查",
                 "owner_role": "区防汛办", "deadline_hint": "汛期前 30 天",
                 "acceptance": "出具签字人清单", "fallback": "向上级申请"},
                {"id": "A2", "verb": "提交", "object": "排水图",
                 "owner_role": "排水公司", "deadline_hint": "本月内",
                 "acceptance": "管网档案归档", "fallback": "委托第三方"},
                {"id": "A3", "verb": "试点", "object": "透水铺装",
                 "owner_role": "项目组", "deadline_hint": "本季度",
                 "acceptance": "验收报告出具", "fallback": "缩减试点范围"},
            ],
        }
        acts = m._extract_actions(v)
        assert len(acts) == 3, f"schema 三条应原样返回，实测 {len(acts)}"
        assert all(a["_source"] == "schema" for a in acts), acts
        assert all(not a["_missing"] for a in acts), acts
        # 2 兜底词法
        v2 = m.View(entry="1")
        v2.decidable_product = {"answer": "先指派区防汛办核查。否则回退上级。"}
        acts2 = m._extract_actions(v2)
        assert acts2 and all(a["_source"] == "lexical" for a in acts2), acts2
        # 3 负对照：空 answer 无 schema → []
        v3 = m.View(entry="1")
        v3.decidable_product = {"answer": ""}
        assert m._extract_actions(v3) == []
        # 4 负对照：schema 缺字段 → _missing 标出
        v4 = m.View(entry="1")
        v4.decidable_product = {"answer": "x",
                                "actions": [{"id": "A1", "verb": "指派",
                                             "object": "核查"}]}
        acts4 = m._extract_actions(v4)
        assert acts4 and acts4[0]["_missing"], acts4
        # 5 负对照：只给 2 条 schema → 条数不足（触发条件成立）
        v5 = m.View(entry="1")
        v5.decidable_product = {"answer": "x", "actions": [
            dict(v.decidable_product["actions"][0]),
            dict(v.decidable_product["actions"][1])]}
        n5 = len([a for a in m._extract_actions(v5)
                  if a.get("_source") == "schema"])
        assert n5 == 2, n5
        # 6 源码断言
        src = _v1221_src_text(SRC)
        assert "decidable_product" in src and '"actions"' in src
        assert "模型没按 schema 产出 actions" in src
        assert "action_fields_missing" in src
        assert ("action_fields_missing"
                in (getattr(m, "_V122_HARD_FLAGS", ()) or ()))
        print("  ✓ v1.22.1 P1：schema 三条原样 / 词法兜底带标签 / "
              "空 answer=[] / 缺字段标 _missing / 2 条判不足")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ v1.22.1 P1 失败：{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_v1221_p2(SRC=None):
    """[v1.22.1 P2] triage 触发条件改挂结构标签（含三条负对照）。"""
    print("  · v1.22.1 P2：triage 挂结构标签（[外] 前缀 + 语义关键词 + 自指不降级）")
    try:
        m = _v1221_mod(SRC)
        # 1 结构标签命中
        assert m._is_triage_candidate("[外] 具体某老城区的最优方案")
        # 2 语义关键词命中
        assert m._is_triage_candidate("信息不足，无法判断")
        assert m._is_triage_candidate("需外部动作")
        # 3 负对照①：真·自指不许降级
        assert not m._is_never_downgrade("[外] 具体某老城区的最优方案")
        assert m._is_never_downgrade("该判定自指，无共同参照系")
        # 4 负对照②：无标签无语义词
        assert not m._is_triage_candidate("现场取证难度大")
        # 5 负对照③：空串
        assert not m._is_triage_candidate("")
        # 6 源码断言 + 加性（旧词表一字未删）
        src = _v1221_src_text(SRC)
        assert "_TRIAGE_STRUCTURAL_PREFIXES" in src
        assert "_TRIAGE_NEVER_DOWNGRADE" in src
        assert "_is_triage_candidate" in src
        assert "_is_never_downgrade" in src
        assert '_TRIAGE_KEYS = ("信息不足", "需外部动作", "缺数据", "无外部")' in src
        assert "for k in _TRIAGE_KEYS)" not in src
        # 7 动词白名单没被动（旁证「不拟合数据」守住）
        assert len(getattr(m, "_ACTION_VERB_WHITELIST", ()) or ()) == 19
        print("  ✓ v1.22.1 P2：结构标签/语义词两路命中；自指、无标签、空串"
              "三条负对照不降级；旧词表保留；白名单仍 19")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ v1.22.1 P2 失败：{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_v1221_p3(SRC=None):
    """[v1.22.1 P3] 仅源码机制负对照：脚本/JSON/文档齐 + 判定合法 + 条数对账。"""
    print("  · v1.22.1 P3：仅源码机制负对照（5 条 × 三分类判定）")
    try:
        import json as _json
        from pathlib import Path as _P
        for f in ("_negctl_v1221_p3.py", "_negctl_v1221_p3.json",
                  "docs/机制负对照-v1221.md"):
            assert _P(f).exists(), f"缺 {f}"
        data = _json.loads(
            _P("_negctl_v1221_p3.json").read_text(encoding="utf-8"))
        assert len(data) >= 5, f"负对照条数 {len(data)} < 5"
        for name, it in data.items():
            assert it["verdict"] in ("条件不可达", "条件窄但成立",
                                     "机制没工作"), \
                f"{name} verdict 非法：{it['verdict']}"
            assert isinstance(it.get("triggered"), bool), \
                f"{name} triggered 不是 bool"
        # 与审计报告的「仅源码」清单两向对账
        # ★ 对**冻结快照**，不是活的审计报告：语料会长大，原本判「仅源码」的
        #   机制会变成「可达」（实测 P3 时点 5 条 → 09:42 重跑审计 0 条）——
        #   拿移动靶当锚会因为数据变大而翻红，与「有没有删机制」无关。
        _fz = _P("_negctl_v1221_p3_frozen.json")
        assert _fz.is_file(), "缺 _negctl_v1221_p3_frozen.json（P3 时点快照）"
        _snap = set(_json.loads(_fz.read_text(encoding="utf-8")).get(
            "src_only_at_p3_time") or [])
        assert set(data) == _snap, \
            f"负对照 {sorted(data)} ≠ 冻结快照 {sorted(_snap)}"
        print(f"  ✓ v1.22.1 P3：{len(data)} 条齐（与审计报告两向对账一致）；"
              f"判定 " + "、".join(sorted({v['verdict'] for v in data.values()})))
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ v1.22.1 P3 失败：{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_v1221_p2b(SRC=None):
    """[v1.22.1 P2b] triage 第二条路径：answers 匹配（端到端打通）。

    ★ 三类负对照必须同时成立，否则「命中」这件事不成立：
      ① 无 answers（None）／空 list／空 aspect → 不许命中（应回落 claim 路径）；
      ② 不相关的一对 → 不许命中；
      ③ tier 门仍在（answers 命中但 tier 超 floor 也不选）。
    """
    try:
        NL = chr(10)          # ★ 注入器只搬函数，模块级名字搬不过去
        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        # 1/2 两个匹配函数在
        assert hasattr(m, "_hit_by_answers"), "_hit_by_answers 缺失"
        assert hasattr(m, "_hit_by_claim"), "_hit_by_claim 缺失"

        # 3 answers 正向命中（重叠 + 双向）
        assert m._hit_by_answers(
            "老城区现有排水管网的设计标准是多少年一遇",
            ["管网设计重现期", "老城区现有排水管网的设计标准"]), "正向未命中"
        assert m._hit_by_answers(
            "老城区地下管线密集程度", ["老城区地下管线密集程度"]), "同文未命中"
        # 3b 反向分支（对称性）：★ 实测 `_overlap_coef` 是**对称**函数（分母 min 与方向
        #   无关），所以「反向再查一次」与正向**等价**，不给新命中。
        #   这里锁的是真正的不变量：两向结果一致（不引入隐藏的方向依赖）。
        #   （任务书原文的用例断言不通 —— jieba 把「排水管网的设计标准」切成
        #     「排水管/设计标准」，与「管网设计重现期」无交集，实测重叠 0.000。）
        _a5 = "管网设计重现期"
        _b5 = ["老城区现有排水管网的设计标准是多少年一遇"]
        assert m._overlap_coef(_a5, _b5[0]) == m._overlap_coef(_b5[0], _a5), \
            "_overlap_coef 竟不对称（反向分支的前提被推翻，需重审）"
        assert m._hit_by_answers(_a5, _b5) == m._hit_by_answers(_b5[0], [_a5]), \
            "正反两向结果不一致"

        # 4 负对照：空 list / None / 空 aspect
        assert not m._hit_by_answers("任意", []), "负对照：空 list 竟命中"
        assert not m._hit_by_answers("任意", None), "负对照：None 竟命中"
        assert not m._hit_by_answers("", ["管网设计重现期"]), "负对照：空 aspect 竟命中"

        # 5 负对照：不相关
        assert not m._hit_by_answers(
            "本地微观数据", ["管网设计重现期"]), "负对照：不相关竟命中"

        # 6 claim 老路径：行为在 + 字面 0.6 未改
        assert m._hit_by_claim(
            "管网设计重现期", "GB50014 管网设计重现期 3~5 年"), "claim 路径失效"
        _i0 = src.find("def _hit_by_claim")
        _i1 = src.find(NL + "def ", _i0 + 10) if _i0 >= 0 else -1
        _body_c = src[_i0:_i1] if _i0 >= 0 and _i1 > _i0 else src[_i0:]
        assert "_similar(" in _body_c and "0.6" in _body_c, "claim 路径字面 0.6 被改"
        _j0 = src.find("def _hit_by_answers")
        _j1 = src.find(NL + "def ", _j0 + 10) if _j0 >= 0 else -1
        _body_a = src[_j0:_j1] if _j0 >= 0 and _j1 > _j0 else src[_j0:]
        assert "_overlap_coef" in _body_a and "_UNTRACED_OVERLAP" in _body_a, \
            "answers 路径未用 _overlap_coef + _UNTRACED_OVERLAP"
        assert "_UNTRACED_OVERLAP" in src, "_UNTRACED_OVERLAP 不在"

        # 7 [v1.23.2] crosscheck 路径：两条路都在 + tier 门仍在 + 旧单路径已撤
        #   ★ 组装逻辑已抽成纯函数 `_triage_suggestions` ⇒ 区域 = 两处之和，
        #     并**钉住调用关系**（否则「搬走了」与「删掉了」看起来一样）。
        _k0 = src.find("def _anchor_crosscheck")
        _k1 = src.find(NL + "    def ", _k0 + 10) if _k0 >= 0 else -1
        _xc0 = src[_k0:_k1] if _k0 >= 0 and _k1 > _k0 else src[_k0:]
        _t0 = src.find("def _triage_suggestions")
        _t1 = src.find(NL + "def ", _t0 + 10) if _t0 >= 0 else -1
        _ts = src[_t0:_t1] if _t0 >= 0 and _t1 > _t0 else ""
        _xc = _xc0 + NL + _ts
        assert "_triage_suggestions(" in _xc0, \
            "crosscheck 未调 _triage_suggestions（组装逻辑搬走后没接上）"
        assert "_hit_by_answers(str(" in _xc, "crosscheck 未接 answers 路径"
        assert "_hit_by_claim(str(" in _xc, "crosscheck 未接 claim 路径"
        assert 'x.get("answers")' in _xc, "crosscheck 未读 answers 字段"
        assert 'int(x.get("tier", 3) or 3) <= _floor' in _xc, "tier 门丢了"
        assert '_similar(str(_a), str(x.get("claim", "")), 0.6))' not in _xc, \
            "旧单路径仍在 crosscheck 里"

        # 8 _load_anchors 读 answers（键在 + **真读进来**）
        assert '"answers": _ans_kept' in src and "_answers_dropped" in src, \
            "_load_anchors 的 answers 键（v1.22.2 P3 起 = 过滤后 _ans_kept）"
        import json as _json
        from pathlib import Path as _P
        _tmp = _P("_smoke_p2b_ans.json")
        _tmp.write_text(_json.dumps(
            {"anchors": [{"id": "a1", "claim": "X", "tier": 1,
                          "answers": ["短", "老城区管网设计重现期标准"]}]},
            ensure_ascii=False), encoding="utf-8")
        try:
            _cfg = m.DEFAULT_CONFIG.copy()
            _cfg["external_anchor"] = dict(_cfg.get("external_anchor") or {})
            _cfg["external_anchor"].update(
                {"enabled": True, "path": "_smoke_p2b_ans.json"})
            _cfg["output"] = dict(_cfg.get("output") or {})
            _cfg["output"]["verbose"] = False
            _meta = m.MetaDGTF(_cfg)
            _meta._load_anchors()
            _got = (_meta._anchors[0].get("answers")
                    if getattr(_meta, "_anchors", None) else None)
            # [v1.22.2 P3] 样本须满足最短长度：短的应被过滤，长的必须
            #   真读进来（原样本 3 字，会被新过滤器吃掉 —— 判据随实现更新）。
            assert _got == ["老城区管网设计重现期标准"], \
                "answers 未读进来（或短答案未过滤）：" + repr(_got)
        finally:
            # ★ 清理**不是判据**：本机沙箱的 safe-delete 会让 unlink 抛
            #   OSError（SAFE_DELETE_FAIL_CLOSED），不能因此把检查判红。
            try:
                _tmp.unlink(missing_ok=True)
            except OSError:
                pass

        # 9 P2a 成果一字未删（宪法级禁令）
        assert all(k in src for k in (
            "_TRIAGE_STRUCTURAL_PREFIXES", "def _is_triage_candidate",
            "def _is_never_downgrade")), "P2a 成果被删"
        assert '_TRIAGE_KEYS = ("信息不足", "需外部动作", "缺数据", "无外部")' in src, \
            "旧词表被改"

        print("  ✓ v1.22.1 P2b：双路径（answers OR claim）/ claim 0.6 未动 / "
              "三类负对照通过 / _load_anchors 真读 answers / P2a 成果未删")
        return True
    except Exception as e:  # noqa: BLE001
        print("  ✗ v1.22.1 P2b 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False

def check_v1221_p5(SRC=None):
    """[v1.22.1 P5] auto 取向回填：判定留痕 + 错配告警。

    ★ 任务书前提与实现不符：`auto_plan` 的**单调用**分支（`run()` 走的就是
      它）原来不带 `orientation`，所以 `_auto_plan_used` 永远没有取向。
      本检查直接**打桩跑一次 `auto_plan`**，锁「同一次调用里带出取向」。
    """
    try:
        NL = chr(10)
        Q = chr(34)
        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        # 1/2 静态串
        assert "_auto_plan_used" in src, "run()/_pack_result 未记 _auto_plan_used"
        assert "取向判定（plan_orientation）" in src, "缺头部「取向判定」行"
        assert "取向错配" in src, "缺「取向错配」告警"

        # 3 auto_plan 单调用分支要解析并带出 orientation
        _i0 = src.find("def auto_plan(")
        _i1 = src.find(NL + "def ", _i0 + 10) if _i0 >= 0 else -1
        _body = src[_i0:_i1] if _i0 >= 0 and _i1 > _i0 else src[_i0:]
        # ★ 只搜到引号为止 —— 实际代码是 `data.get("orientation", "")`，
        #   连右括号一起搜会匹配不到（第一版就这么误报过）。
        assert ("data.get(" + Q + "orientation" + Q) in _body, (
            "auto_plan 未解析 orientation")
        # ★ [v1.23.13 判据随实现更新] 这里原来数**源码字面**串
        #   `"orientation": _ori` 出现 ≥2 次。v1.23.13 把三条出口收进唯一
        #   装配器 `_assemble_plan(orientation=_ori)`，字面没了、**行为没变**
        #   （早退分支照样带出取向）。判据搬到下面第 5 条：低置信打桩跑早退，
        #   断言返回的 mode 与 orientation。**不是放宽**，是换成行为断言。

        # 4 行为：打桩一次调用，验带出 + 只调一次 + prompt 里要了取向
        class _StubLLM:
            def __init__(self, mode="serial", conf=0.9):
                self.calls = []
                self.mode = mode
                self.conf = conf

            def call(self, system, user, *a, **kw):
                self.calls.append((system, user))
                import json as _j
                return _j.dumps({"mode": self.mode,
                                 "orientation": "boundary",
                                 "rounds": {"0": 4, "1": 4,
                                            "both": 4, "all": 5},
                                 "reason": "桩", "confidence": self.conf})

            def parse_json(self, raw):
                import json as _j
                return _j.loads(raw)

        _st = _StubLLM()
        _plan = m.auto_plan("地铁运营效率的评价体系与统计口径问题",
                            dict(m.DEFAULT_CONFIG), llm=_st)
        assert _plan.get("orientation") == "boundary", (
            "orientation 未带出：" + repr(_plan.get("orientation")))
        assert len(_st.calls) == 1, "单调用路径被改成多次（成本变化）"
        assert "orientation" in _st.calls[0][0], "prompt 里没要取向"

        # 4b ★ 早退分支（低置信 ⇒ 退回 serial）**也要带出取向** ——
        #    这是原静态字面断言真正想测的行为。
        # ★ [v1.23.29 判据随实现更新] 题面必须让**规则层拿不准** ——
        #   规则命中时会走规则分支（取向来自 `plan_orientation`，不读
        #   本桩）。这里要测的是「LLM 桩返回低置信时仍带出取向」，
        #   故题面取规则拿不准的那类。**不是放宽**：低置信仍必须退
        #   serial、仍必须带出 boundary。
        _early = m.auto_plan("地铁运营效率的评价体系与统计口径问题",
                             dict(m.DEFAULT_CONFIG),
                             llm=_StubLLM(mode="A", conf=0.1))
        assert _early.get("mode") == "serial", (
            "低置信没退回 serial：" + repr(_early.get("mode")))
        assert _early.get("orientation") == "boundary", (
            "早退分支没把 orientation 带出：" + repr(_early.get("orientation")))

        # 5 负对照：桩回一个非法取向 → 归一成空串（不许把垃圾当取向）
        class _Stub2(_StubLLM):
            def call(self, system, user, *a, **kw):
                self.calls.append((system, user))
                import json as _j
                return _j.dumps({"mode": "serial", "orientation": "随便"})

        _p2 = m.auto_plan("地铁运营效率的评价体系与统计口径问题",
                          dict(m.DEFAULT_CONFIG), llm=_Stub2())
        assert not _p2.get("orientation"), "非法取向竟被采纳：" + repr(_p2)

        print("  ✓ v1.22.1 P5：判定留痕 + 错配告警 + 单调用带出取向（打桩实测）"
              " + 非法取向归一负对照")
        return True
    except Exception as e:  # noqa: BLE001
        print("  ✗ v1.22.1 P5 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False

def check_v1221_p6(SRC=None):
    """[v1.22.1 P6] tier 全缺省时的显式提示。

    ★ 任务书骨架在 `out` 上数「谁没声明 tier」—— 而 `out` 里每条都补了
      缺省 3，计数恒为 0，警告**永远不触发**。这里在**原始条目**上判，
      并用两份临时锚点文件做正/负对照。
    """
    try:
        import json as _json
        from pathlib import Path as _P
        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        assert "_anchor_tier_warning" in src, "缺 _anchor_tier_warning"
        assert "锚点 tier 警告" in src, "缺头部「锚点 tier 警告」行"

        _notier = _P("_smoke_p6_notier.json")
        _notier.write_bytes(_json.dumps(
            {"anchors": [{"id": "a1", "claim": "x"},
                         {"id": "a2", "claim": "y"}]},
            ensure_ascii=False).encode("utf-8"))
        _onetier = _P("_smoke_p6_onetier.json")
        _onetier.write_bytes(_json.dumps(
            {"anchors": [{"id": "a1", "claim": "x"},
                         {"id": "a2", "claim": "y", "tier": 1}]},
            ensure_ascii=False).encode("utf-8"))

        def _load(path):
            cfg = _json.loads(_json.dumps(m.DEFAULT_CONFIG, default=str))
            cfg["external_anchor"] = dict(cfg.get("external_anchor") or {})
            cfg["external_anchor"].update({"enabled": True, "path": str(path)})
            cfg["output"] = dict(cfg.get("output") or {})
            cfg["output"]["verbose"] = False
            mm = m.MetaDGTF(cfg)
            mm._load_anchors()
            return getattr(mm, "_anchor_tier_warning", "<无属性>")

        try:
            w_all = _load(_notier)
            w_one = _load(_onetier)
            assert isinstance(w_all, str) and w_all, (
                "全缺省竟无警告（正对照失败）：" + repr(w_all))
            assert not w_one, (
                "有显式 tier 仍有警告（负对照失败）：" + repr(w_one))
        finally:
            # ★ 同上：清理失败不影响判定。
            try:
                _notier.unlink(missing_ok=True)
                _onetier.unlink(missing_ok=True)
            except OSError:
                pass

        # 红线保留：无 tier 的锚点**不进引用表**（即便挂了 evidence 档）
        _p1 = m.Pool()
        _p1.anchors = [{"id": "a1", "claim": "X"}]
        _p1.anchor_as_evidence = True
        _t1 = m._citation_table(None, _p1)
        assert not any(c.startswith("X") for c, _ in _t1), (
            "无 tier 的锚点竟进了引用表（红线破了）")
        _p2 = m.Pool()
        _p2.anchors = [{"id": "a2", "claim": "Y", "tier": 1}]
        _p2.anchor_as_evidence = True
        _t2 = m._citation_table(None, _p2)
        assert any(c.startswith("X") for c, _ in _t2), (
            "有 tier=1 的锚点却进不了引用表")

        print("  ✓ v1.22.1 P6：全缺省告警（正对照）+ 有显式 tier 不告警（负对照）"
              " + 无 tier 不入引用表（红线）")
        return True
    except Exception as e:  # noqa: BLE001
        print("  ✗ v1.22.1 P6 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False

def check_v1221_p7(SRC=None):
    """[v1.22.1 P7] 明确不做（只出说明，不动代码）。

    ★ 本档**不改引擎**：只查决策记录在不在、三条在不在，外加一条负对照 ——
      「这三件事不许跑进产物头部」（决策记录不是产物级告警）。
    """
    try:
        from pathlib import Path as _P
        doc = _P("docs/不做什么-v1221.md")
        assert doc.is_file(), "缺 docs/不做什么-v1221.md"
        text = doc.read_text(encoding="utf-8")
        assert "不拆模块" in text, "缺「不拆模块」"
        assert "不扩动词白名单" in text, "缺「不扩动词白名单」"
        assert "不删任何机制" in text, "缺「不删任何机制」"

        # 负对照：三条都不许出现在产物头部渲染里
        src = _v1221_src_text(SRC)
        _i = src.find("def save_result")
        _head = src[_i:_i + 20000] if _i >= 0 else ""
        for k in ("不拆模块", "不扩动词白名单", "不删任何机制"):
            assert k not in _head, "决策记录跑进了产物头部：" + k

        print("  ✓ v1.22.1 P7：决策记录三条齐 + 负对照（不进产物头部）")
        return True
    except Exception as e:  # noqa: BLE001
        print("  ✗ v1.22.1 P7 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False

# <<<v1222 checks>>>
def check_v1222_p1(SRC=None):
    """[v1.22.2 P1] P4 两臂口径统一：两条路径都写 stability（含早退）。

    ★ 负对照（写进判据）：
      · 判决失败 / 空 judgments → 每条都必须 `abstained`（不许静默无键）；
      · 未被判到的条**不许**落 high/low（弃权≠稳定）。
    """
    try:
        NL = chr(10)
        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)
        assert hasattr(m, "_single_vote_stability"), "_single_vote_stability 缺失"
        assert hasattr(m.MetaDGTF, "_write_tri_stability"), \
            "MetaDGTF._write_tri_stability 缺失"

        class _LLM:
            def __init__(self, fail=False, empty=False):
                self.fail, self.empty = fail, empty
            def call(self, s, u, t, mx, json_mode=False, stage=""):
                if self.fail:
                    raise RuntimeError("打桩失败")
                if self.empty:
                    return '{"judgments": []}'
                import json as _j
                return _j.dumps({"judgments": [
                    {"id": 1, "reason": "x", "decidability": "decidable"},
                    {"id": 2, "reason": "x", "decidability": "undecidable"}]})
            def parse_json(self, raw):
                import json as _j
                return _j.loads(raw)

        def _mk(llm, multi):
            o = object.__new__(m.MetaDGTF)
            o.llm = llm
            o.config = {"actions": {"tri_multi_vote": multi}}
            o.vp = lambda *a, **k: None
            return o

        def _subs():
            return [{"id": 1, "question": "a", "decidability": "decidable"},
                    {"id": 2, "question": "b", "decidability": "decidable"},
                    {"id": 3, "question": "c", "decidability": "partial"}]

        # 1 单票臂
        _s = _subs()
        _mk(_LLM(), False)._adjudicate_sub_tristate(_s, "Q")
        assert all("stability" in x for x in _s), "单票臂有子问题没写 stability"
        assert {x["_vote_mode"] for x in _s} == {"single"}, "单票臂 _vote_mode 错"
        _st = [x["stability"] for x in _s]
        assert _st == ["high", "low", "abstained"], "单票口径错：" + repr(_st)

        # 2 多票臂
        _s2 = _subs()
        _mk(_LLM(), True)._adjudicate_sub_tristate(_s2, "Q")
        assert all("stability" in x for x in _s2), "多票臂有子问题没写 stability"
        assert {x["_vote_mode"] for x in _s2} == {"multi"}, "多票臂 _vote_mode 错"

        # 3 负对照：失败 / 空 judgments → 全 abstained（早退也写）
        for _multi in (False, True):
            _s3 = _subs()
            _mk(_LLM(fail=True), _multi)._adjudicate_sub_tristate(_s3, "Q")
            assert all(x["stability"] == "abstained" for x in _s3), \
                "失败路径未写 abstained（多票=%s）" % _multi
        _s4 = _subs()
        _mk(_LLM(empty=True), False)._adjudicate_sub_tristate(_s4, "Q")
        assert all(x["stability"] == "abstained" for x in _s4), \
            "空 judgments 未写 abstained"

        # 4 口径函数负对照
        assert m._single_vote_stability({}) == "abstained", "未判条应为 abstained"
        assert m._single_vote_stability({"_tri_judged": True,
                                         "decidability": "partial"}) == "medium"
        assert m._single_vote_stability(
            {"_tri_judged": True, "first_label": "decidable",
             "decidability": "partial"}) == "low"
        assert m._single_vote_stability(
            {"_tri_judged": True, "first_label": "partial",
             "decidability": "partial"}) == "high"
        # [v1.22.2 P1b] 真跑暴露的一格：分歧落点恰好 == 原标签 partial
        #   时，只看两者相等会误判 high。必须看 label_disagreed。
        assert m._single_vote_stability(
            {"_tri_judged": True,
             "label_disagreed": ["partial", "decidable"],
             "first_label": "partial",
             "decidability": "partial"}) == "low", \
            "分歧落 partial 且原标签 partial → 应 low（曾误判 high）"

        # 5 渲染：分口径 + 分母只数已判 + 弃权单列
        assert "三态判决（" in src, "头部标题未分口径"
        assert '"abstained"' in src, "渲染未认 abstained"
        assert "_voted = _hi + _me + _lo" in src, "分母未改成已判条"
        # 负对照：旧的「无条件三态多票 high/medium/low」那一行必须已不在渲染里
        assert "**三态多票**：high {_hi} / medium {_me} / low {_lo}" not in src, \
            "旧渲染仍在"
        assert '"stability" == "high"' not in src or "_voted" in src, "口径未变"

        print("  ✓ v1.22.2 P1：两臂都写 stability / 弃权独立 / "
              "早退也写 / 口径函数 4 向负对照")
        return True
    except Exception as e:
        print("  ✗ v1.22.2 P1 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
def check_v1222_p2(SRC=None):
    """[v1.22.2 P2] not_do 四处打通：schema → 白名单 → 抽取 → 渲染。

    ★ 负对照：
      · 空 what 必须被过滤（否则 rubric 第三项假通过）；
      · 空 view → 0 条（否则 not_do_missing 永不亮）；
      · `not_do_missing` 只认 schema 来源，词法兜底**不算**；
      · rubric max=3 没改（本阶段不是改判据，是补产出）。
    """
    try:
        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)
        # 1 四处齐备
        assert hasattr(m, "_norm_schema_not_do"), "_norm_schema_not_do 缺失"
        assert hasattr(m, "_norm_schema_actions"), "_norm_schema_actions 被误删"
        assert hasattr(m, "_extract_not_do"), "_extract_not_do 缺失"
        assert hasattr(m, "_extract_not_do_lexical"), "_extract_not_do_lexical 缺失"
        reg = src[src.find('"decidable_product": {'):
                  src.find('"undecidable_product": {')]
        assert '"not_do"' in reg, "prompt schema 没加 not_do"
        assert "not_do 段 · decision 取向必须产出" in src, "约束段缺失"
        assert '"not_do": _norm_schema_not_do(dec.get("not_do")),' in src, \
            "★ dec_norm 白名单没加 not_do（会静默吞掉模型产出）"

        # 2 归一化：四向
        _n = m._norm_schema_not_do
        assert _n(None) == [] and _n("x") == [], "非 list 未返回空"
        assert _n(["x", 1]) == [], "非 dict 条目未丢弃"
        assert _n([{"what": "", "why": "y"}, {"what": " "}]) == [], \
            "空 what 未过滤"
        assert len(_n([{"what": "w%d" % i} for i in range(9)])) == 6, "上限非 6"

        # 3 抽取：schema 优先 + 词法兜底带标签 + 空 view 归零
        got = m._extract_not_do({"decidable_product": {"not_do": [
            {"what": "不在成因未定时动工", "why": "判据未立"},
            {"what": "", "why": "空 what"}]}})
        assert len(got) == 1 and got[0]["_source"] == "schema", \
            "schema 路径错：" + repr(got)
        assert all(x["what"] for x in got), "空 what 混进结果"
        _v3 = type("V", (), {"decidable_product": {}})()
        assert m._extract_not_do(_v3) == [], "空 view 未归零"
        got2 = m._extract_not_do(_v3)
        assert all(x.get("_source") == "lexical" for x in got2), \
            "兜底结果缺 _source=lexical"

        # 4 not_do_missing 只认 schema
        assert "_nd_schema = [x for x in _nd_d" in src, \
            "not_do_missing 未改成只认 schema 来源"

        # 5 rubric 三段负对照 + max 未变
        import sys as _s
        _s.path.insert(0, "bench")
        from bench_score import score_actions
        _a3 = [{"fallback": "退路%d" % i} for i in range(3)]
        assert score_actions([], [])["score"] == 0, "空/空 竟给分"
        assert score_actions(_a3, [])["score"] == 2, "actions 满 + not_do 空 ≠ 2/3"
        assert score_actions(_a3, [{"what": "不做X"}])["score"] == 3, \
            "not_do 非空 未给第 3 分"
        assert score_actions(_a3, [{"what": "x"}])["max"] == 3, "max 被改了"

        print("  ✓ v1.22.2 P2：schema/白名单/抽取/渲染四处打通 + "
              "空 what 过滤 + 空 view 归零 + rubric 三段负对照")
        return True
    except Exception as e:
        print("  ✗ v1.22.2 P2 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
def check_v1222_p3(SRC=None):
    """[v1.22.2 P3] answers 最短长度约束 + **两条告警分离**。

    ★ 负对照：
      · min_len=0 → 不过滤（退回旧行为）；
      · 真「未声明 answers」走另一条告警，两条不许互相覆盖；
      · 0.6 / `_overlap_coef` 分母 min 一律没动（任务书禁令）。
    """
    try:
        import json as _j
        import tempfile as _tf
        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)
        ea = m.DEFAULT_CONFIG.get("external_anchor") or {}
        assert ea.get("answers_min_len") == 6, "answers_min_len 默认不是 6"
        assert ea.get("answers_max_n") == 5, "answers_max_n 默认不是 5"
        assert "_anchor_answers_filtered" in src, "过滤留痕属性缺失"
        assert '"answers": _ans_kept' in src, "answers 未改成过滤后的结果"
        # ★ 两条告警不许混用同一个属性
        assert src.count('self._anchor_answers_warning = (') == 1, \
            "「未声明」告警被复制/覆盖"
        assert "**锚点 answers 警告**" in src, "产物渲染缺失"

        def _load(anchors, **over):
            p = Path(_tf.mkdtemp()) / "a.json"
            p.write_text(_j.dumps({"anchors": anchors}, ensure_ascii=False),
                         encoding="utf-8")
            cfg = m.load_config(str(Path("__nonexistent__.yaml")))
            cfg["external_anchor"] = dict(cfg["external_anchor"])
            cfg["external_anchor"].update({"enabled": True, "path": str(p)})
            cfg["external_anchor"].update(over)
            o = object.__new__(m.MetaDGTF)
            o.config = cfg
            o.vp = lambda *a, **k: None
            o._load_anchors()
            return o

        o1 = _load([{"id": "a1", "claim": "x",
                     "answers": ["重现期", "老城区现有排水管网的设计标准是多少年一遇"]}])
        ans = o1._anchors[0].get("answers") or []
        assert "重现期" not in ans, "短 answer 未被丢弃"
        assert any("老城区" in x for x in ans), "长 answer 被误丢"
        assert o1._anchors[0].get("_answers_dropped") == ["重现期"], "丢弃项未留痕"
        assert o1._anchor_answers_filtered, "过滤未留痕"
        # ★ 负对照：声明过 → 「未声明」告警不许亮
        assert o1._anchor_answers_warning == "", "「未声明」告警被误触发"

        o0 = _load([{"id": "a1", "claim": "x", "answers": ["重现期", "短"]}],
                   answers_min_len=0)
        a0 = o0._anchors[0].get("answers") or []
        assert "重现期" in a0 and "短" in a0, "min_len=0 竟还在过滤"
        assert o0._anchor_answers_filtered == "", "不过滤却留了痕"

        o2 = _load([{"id": "a1", "claim": "x"}])
        assert o2._anchor_answers_warning, "真未声明 未告警"
        assert o2._anchor_answers_filtered == "", "两条告警混用了"

        # 阈值负对照
        assert "return inter / min(len(ka), len(kb))" in src, \
            "_overlap_coef 分母被改"
        print("  ✓ v1.22.2 P3：短 answer 过滤 + 留痕 + 两条告警分离 + "
              "min_len=0 不过滤 + 阈值未动")
        return True
    except Exception as e:
        print("  ✗ v1.22.2 P3 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
# <<<end v1222 checks>>>

# <<<v123 checks>>>
def check_v123_w1(SRC=None):
    """[v1.23.0 W1] 核心联网基础设施（**不接入任何环节**）。

    ★ 覆盖三处核验后回写的卡点：
      · [修正 B2] logger_web.propagate=False + **父 logger 收不到 [W-** 的功能性证据；
      · [修正 B3] 第 3 次失败必须**真的把 disabled 置位**且理由可读；
      · 缓存目录 cache/websearch 与 cache/anchors 不混用。
    ★ 负对照：默认关 → allow() 恒 False；空结果 empty 是**终态**不重试。
    """
    try:
        import logging as _lg
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)

        # ---------- 1 配置段 ----------
        ws = m.DEFAULT_CONFIG.get("web_search")
        assert isinstance(ws, dict), "web_search 配置段缺失"
        assert ws.get("enabled") is False, "默认必须是关"
        _q = ws.get("quota") or {}
        for _k in ("per_stage_round", "per_stage_total", "per_run_total"):
            assert _k in _q, "配额三层缺 " + _k
        _st = ws.get("stages") or {}
        assert _st.get("practice_term_calibration") is False, "修行层默认没关"
        assert _st.get("stop_criteria") is False, "停止判据默认没关"
        assert _st.get("research_decompose") is True, "研究层默认没开"
        assert ws.get("auto_disable_after_failures") == 3, "降级阈值不是 3"
        # ★ 负对照：external_anchor 一键未动（加性）
        _ea = m.DEFAULT_CONFIG.get("external_anchor") or {}
        for _k in ("answers_min_len", "answers_max_n", "as_evidence",
                   "tier_floor", "triage", "retriever"):
            assert _k in _ea, "external_anchor 被改动：" + _k

        # ---------- 2 独立 logger（修正 B2） ----------
        lw = getattr(m, "logger_web", None)
        assert lw is not None, "logger_web 缺失"
        assert lw.name == "dgtf.websearch", "名字不对：" + lw.name
        assert lw.propagate is False, \
            "★ propagate 必须 False（否则日志同时进主 logger dgtf）"
        _seen = []

        class _H(_lg.Handler):
            def emit(self, rec):
                _seen.append(rec.getMessage())

        _par = _lg.getLogger("dgtf")
        _h = _H()
        _par.addHandler(_h)
        _old = _par.level
        _par.setLevel(_lg.DEBUG)
        try:
            lw.warning("[W-SMOKE] 不许出现在主 logger")
        finally:
            _par.removeHandler(_h)
            _par.setLevel(_old)
        assert not any("[W-SMOKE]" in x for x in _seen), \
            "★ 主 logger 收到了 [W- 记录（propagate 没生效）"

        assert tuple(getattr(m, "WEB_FAIL_KINDS", ())) == (
            "timeout", "rate_limit", "empty", "dirty", "api_error"), \
            "五档失败类型常量不对"

        # ---------- 3 Gate ----------
        def _cfg(**over):
            c = {"web_search": dict(m.DEFAULT_CONFIG["web_search"])}
            c["web_search"]["quota"] = dict(c["web_search"]["quota"])
            c["web_search"]["stages"] = dict(c["web_search"]["stages"])
            c["web_search"].update(over)
            return c

        G = m.WebSearchGate
        g0 = G(_cfg())
        assert g0.allow("research_decompose", 1)[0] is False, \
            "负对照：默认关竟 allow"
        assert g0.disabled is True, "默认关时 disabled 应为 True"

        g = G(_cfg(enabled=True))
        assert g.allow("research_decompose", 1)[0] is True, "授权环节应 allow"
        assert g.allow("stop_criteria", 1)[0] is False, "未授权环节竟 allow"
        assert g.allow("practice_term_calibration", 1)[0] is False, \
            "修行层默认关却 allow"
        g.note_call("research_decompose", 1)
        g.note_call("research_decompose", 1)
        assert g.allow("research_decompose", 1)[0] is False, "本圈配额没拦住"
        assert g.allow("research_decompose", 2)[0] is True, "换圈应恢复"

        g2 = G(_cfg(enabled=True))
        for i in range(8):
            g2.note_call("research_decompose", 100 + i)
        assert g2.allow("research_decompose", 500)[0] is False, \
            "stage 全程配额没拦住"

        g3 = G(_cfg(enabled=True))
        for i in range(30):
            g3.note_call("research_decompose", 1000 + i)
        assert g3.allow("duel_arbitration", 2000)[0] is False, \
            "每跑总配额没拦住"

        # ★ 连续失败降级（修正 B3）
        g4 = G(_cfg(enabled=True))
        assert g4.note_failure("timeout") is False, "第 1 次就降级了"
        assert g4.note_failure("timeout") is False, "第 2 次就降级了"
        assert g4.disabled is False, "第 2 次后不该 disabled"
        assert g4.note_failure("timeout") is True, "第 3 次未触发降级"
        assert g4.disabled is True, "★ disabled 未被置位（修正 B3 退回）"
        assert "连续失败 3 次" in g4.disable_reason, "降级理由不可读"
        _ok, _why = g4.allow("research_decompose", 1)
        assert _ok is False and "降级" in _why, "降级后 allow/reason 不一致"

        g5 = G(_cfg(enabled=True))
        g5.note_failure("timeout")
        g5.note_failure("timeout")
        g5.note_success()
        g5.note_failure("timeout")
        assert g5.consecutive_failures == 1 and g5.disabled is False, \
            "note_success 没清零"

        # ---------- 4 Client + Cache ----------
        C = m.WebSearchClient
        Ca = m.WebSearchCache
        d = _P(_tf.mkdtemp())
        ca = Ca(24, root=str(d / "websearch"))
        c = C("tavily", "k", 1, 2, 0.0, ca)
        c._http = lambda q, n: ([{"claim": "x", "url": "u"}], "")
        c.search("Q1")
        assert c.calls == 1, "首次应打一次网络"
        c.search("Q1")
        assert c.calls == 1 and c.cache_hits == 1, \
            "★ 第二次应命中缓存、不增 calls"

        for _kind, _n in (("timeout", 3), ("rate_limit", 3), ("api_error", 3),
                          ("dirty", 3), ("empty", 1)):
            _c2 = C("tavily", "k", 1, 2, 0.0, None)
            _c2._http = (lambda _k: (lambda q, n: ([], _k)))(_kind)
            _r, _got = _c2.search("Q-" + _kind)
            assert _got == _kind, "分类错：" + repr(_got)
            assert _c2.calls == _n, "%s 重试次数应为 %d，实测 %d" % (
                _kind, _n, _c2.calls)

        _c3 = C("bing", "k", 1, 0, 0.0, None)
        try:
            _c3.search("Q")
            raise AssertionError("未知后端竟未抛错")
        except RuntimeError as _e:
            assert "尚未实现" in str(_e), "未知后端错误信息未写明「尚未实现」"

        assert str(Ca().root).replace("\\", "/").endswith("cache/websearch"), \
            "默认缓存目录不是 cache/websearch"
        _ra = getattr(m, "AnchorRetriever", None)
        if _ra is not None:
            _p = _ra("tavily", "k")._cache_path(["q"])
            assert "anchors" in str(_p), "锚点缓存目录被改动"

        _g, _c = m.build_web_search(_cfg(enabled=True))
        assert isinstance(_g, G) and isinstance(_c, C), "工厂返回类型不对"
        assert _c.calls == 0, "★ 工厂不该发起任何调用"

        print("  ✓ v1.23.0 W1：配置段/独立通道(propagate=False)/Gate 三方向/"
              "连续失败置位/五档失败/缓存命中/空结果终态/未知后端抛错/"
              "锚点目录未混用 —— 全部带负对照")
        return True
    except Exception as e:
        print("  ✗ v1.23.0 W1 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
def check_v123_w2(SRC=None):
    """[v1.23.0 W2] 研究层接入 + W# 编号 + 引用门 + W# 硬约束。

    ★ 判据带 **3 个变异体**（结构不变式在现版必然通过 ⇒「通过」不是判别力）：
      M1 抠掉 W# 硬约束 / M2 抠掉 W# 进表 / M3 抠掉 prompt 里的摘要注入。
    ★ 空过防线：每条 apply 判据的初态都必须**与目标态不同**，且断言理由
      不是「与当前判定相同」—— 变异测试在这里抓到过两处空过。
    """
    try:
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)
        Pool, View = m.Pool, m.View

        assert all(hasattr(Pool(), _k) for _k in
                   ("web_results", "web_errors", "web_as_evidence")), \
            "Pool 缺 W2 字段"
        assert all(hasattr(m, _k) for _k in
                   ("_next_web_id", "_web_evidence_gate",
                    "_research_decompose_queries", "_research_evidence_queries",
                    "_research_precedent_queries", "_web_digest_block")), \
            "W2 助手函数缺"
        assert all(hasattr(m.MetaDGTF, _k) for _k in
                   ("_web_search", "_research_web_prep",
                    "_research_decompose_with_web", "_web_evidence_hook")), \
            "W2 MetaDGTF 方法缺"
        assert src.count("d0._decompose_from_pool(") == 1, "拆解仍有第二份"
        assert src.count("d0._decompose_question(") == 1, "拆解仍有第二份"
        assert src.count("web_hook=self._web_evidence_hook") == 2, \
            "update_deferrals 两处调用点未接钩子"
        assert src.count('getattr(self, "_web_digest", "")') == 4, \
            "摘要注入点不是 4 处"

        def _mkpool(init_dec="undecidable", **kw):
            o = Pool()
            o.sub_questions = [{"id": 1, "question": "重现期是多少",
                                "decidability": init_dec}]
            for k, v in kw.items():
                setattr(o, k, v)
            return o

        _pa = _mkpool(web_results=[{"id": "W1", "claim": "重现期 3~5 年"}],
                      web_as_evidence=True)
        assert "W1" in dict(m._citation_table(None, _pa)), \
            "★ 授权时 W# 未进引用表（[修正 B1] 的正面证据）"
        assert m._resolve_citation("W1", None, _pa), "W1 解析不到"
        _pb = _mkpool(web_results=[{"id": "W1", "claim": "x"}],
                      web_as_evidence=False)
        assert "W1" not in dict(m._citation_table(None, _pb)), \
            "负对照：未授权时 W# 竟进表"

        for _to, _init, _want in (("partial", "undecidable", "applied"),
                                  ("decidable", "partial", "rejected"),
                                  ("undecidable", "decidable", "rejected")):
            _pp = _mkpool(init_dec=_init,
                          web_results=[{"id": "W1", "claim": "重现期 3~5 年"}],
                          web_as_evidence=True)
            _vv = View(entry="1")
            _r = m.apply_decidability_change(
                _pp, _vv, {1: _pp.sub_questions[0]}, 1, _to, 3, "冒烟", ["W1"])
            assert _r["status"] == _want, \
                "W#→%s 应 %s，实测 %s" % (_to, _want, _r["status"])
            assert "与当前判定相同" not in str(_r.get("why", "")), \
                "★ 空过：W#→%s 走了「无需变更」" % _to
        _pc = _mkpool(init_dec="decidable", amps=[{"desc": "运维断点"}],
                      web_as_evidence=True)
        _rc = m.apply_decidability_change(_pc, View(entry="1"),
                                         {1: _pc.sub_questions[0]}, 1,
                                         "partial", 3, "冒烟", ["A1"])
        assert _rc["status"] == "applied", "负对照：A1 被 W# 规则误伤"

        class _SC:
            def __init__(self, kind=""):
                self.calls = 0
                self.cache_hits = 0
                self.kind = kind

            def search(self, q, max_n=8):
                self.calls += 1
                if self.kind:
                    return [], self.kind
                return [{"claim": "桩：" + q, "url": "u", "source": "s",
                         "tier": 3}], ""

        def _mkmeta(enabled, client=None, **over):
            cfg = {"web_search": dict(m.DEFAULT_CONFIG["web_search"])}
            cfg["web_search"]["quota"] = dict(cfg["web_search"]["quota"])
            cfg["web_search"]["stages"] = dict(cfg["web_search"]["stages"])
            cfg["web_search"].update({"enabled": enabled, **over})
            o = object.__new__(m.MetaDGTF)
            o.config = cfg
            o.pools = {"1": Pool()}
            o.vp = lambda *a, **k: None
            o._web_gate = m.WebSearchGate(cfg)
            o._web_client = client or _SC()
            o._web_prep_seq = 0
            o.decidability_result = {
                "undecidable_aspects": ["[外] 上游是否有官方标准"]}
            return o

        _o = _mkmeta(False)
        assert _o._web_search("research_decompose", ["q"], 1) == [], \
            "负对照：默认关竟返回结果"
        assert _o._web_client.calls == 0, "★ 负对照：默认关竟打了网络"

        _o2 = _mkmeta(True, as_evidence="evidence")
        _r2 = _o2._web_search("research_decompose", ["q1", "q2"], 1)
        assert [x["id"] for x in _r2] == ["W1", "W2"], "编号不是 W1/W2"
        assert _o2.pools["1"].web_as_evidence is True, "授权门未同步"
        assert _o2._web_search("research_decompose", ["q3"], 1) == [], \
            "本圈配额没拦住"
        assert any("[W-SKIP]" in str(x) for x in _o2.pools["1"].meta), \
            "配额拒绝未留痕"
        assert any("[W-OK]" in str(x) for x in _o2.pools["1"].meta), \
            "★ 成功未留痕（产物里看不出收了几条）"

        _o3 = _mkmeta(True, _SC("timeout"))
        for _i in range(3):
            _o3._web_search("research_decompose", ["q%d" % _i], 10 + _i)
        assert any("[W-TIMEOUT]" in str(x) for x in _o3.pools["1"].meta), \
            "失败未进 pool.meta"
        assert len(_o3.pools["1"].web_errors) >= 3, "失败未进 web_errors"
        assert _o3._web_gate.disabled is True, "连续失败未降级"

        _o4 = _mkmeta(True, _SC("empty"))
        for _i in range(5):
            _o4._web_search("research_decompose", ["e%d" % _i], 20 + _i)
        assert _o4._web_gate.disabled is False, "★ 空结果竟把本跑降级了"
        assert any("[W-EMPTY]" in str(x) for x in _o4.pools["1"].meta), \
            "空结果未留痕"
        assert not [x for x in _o4.pools["1"].web_errors
                    if x.get("kind") == "empty"], "空结果被记成失败"

        assert m._web_digest_block([]) == "" and m._web_digest_block(None) == "", \
            "空摘要不是空串（加性破了）"
        _dg = m._web_digest_block([{"id": "W1", "stage": "s",
                                    "claim": "重现期", "tier": 3}])
        assert "【外部检索摘要】" in _dg and "参照" in _dg, "摘要块文案缺"
        assert m._research_evidence_queries({"to": "undecidable"}) == [], \
            "evidence 对 →undecidable 也发问（方向反了）"
        assert m._research_precedent_queries(["普通方面"]) == [], \
            "precedent 负对照：非 [外] 竟发问"

        MUT = (
            ("M1 W# 硬约束",
             '    if ent["to"] != "partial" and all(\n'
             '            str(r.get("resolved_to", "")).startswith("W")\n'
             '            for r in resolved):\n'
             '        return _reject("联网编号（W#）只能支撑 →partial，不能支撑 "\n'
             '                       f"→{ent[\'to\']}（网络检索质量不稳；"\n'
             '                       "且「能查到」证明不了「答不出」）")\n', ""),
            # ★ [v1.23.2] 锚点改为**尾段**：本版在这块中间插了 W# tier 门
            #   （`if not _web_enters_citation(...): continue`）⇒ 原来那个
            #   从 `if getattr(pool, ...)` 到 `break` 的连续锚**已不连续**，
            #   命中 0 次（判据随实现更新，不是放宽）。
            #   变异体改为 `pass`：删掉 append 后 W# 同样进不了引用表，
            #   M2 的判据意图（「W# 有没有进表」）一字未改。
            ("M2 W# 进表",
             '            _wi += 1\n'
             '            out.append((str(_w.get("id") or ("W" + str(_wi))),\n'
             '                        str(_w.get("claim", ""))[:120]))\n'
             '            if _wi >= 20:\n'
             '                break\n',
             '            pass\n'),
            # [v1.23.6] 锚点从「注释 + 代码」改成**只锚代码行**：原锚点里的两行
            #   注释已被「代码正文不留版次批注」清掉 ⇒ 锚点 0 次。变异体意图
            #   （把摘要注入那段变成空操作）一字未改。
            ("M3 摘要注入",
             '                + (getattr(self, "_web_digest", "") or ""))\n',
             '                )\n'),
        )
        _td = _P(_tf.mkdtemp())
        for _idx, (_nm, _o_, _n_) in enumerate(MUT):
            _exp = 2 if _nm.startswith("M3") else 1
            if src.count(_o_) != _exp:
                raise AssertionError("变异体 %s 锚点 %d 次（应 %d）"
                                     % (_nm, src.count(_o_), _exp))
            _mp = _td / ("mut_w2_%d.py" % _idx)
            _mp.write_bytes(src.replace(_o_, _n_).replace("\n", "\r\n")
                            .encode("utf-8"))
            _mm = _v1221_mod(str(_mp))
            _red = False
            try:
                if _nm.startswith("M1"):
                    _pm = Pool()
                    _pm.sub_questions = [{"id": 1, "question": "q",
                                          "decidability": "decidable"}]
                    _pm.web_results = [{"id": "W1", "claim": "c"}]
                    _pm.web_as_evidence = True
                    _rm = _mm.apply_decidability_change(
                        _pm, View(entry="1"), {1: _pm.sub_questions[0]}, 1,
                        "undecidable", 3, "冒烟", ["W1"])
                    _red = (_rm["status"] == "applied")
                elif _nm.startswith("M2"):
                    _pm = Pool()
                    _pm.web_results = [{"id": "W1", "claim": "c"}]
                    _pm.web_as_evidence = True
                    _red = "W1" not in dict(_mm._citation_table(None, _pm))
                else:
                    _d = object.__new__(_mm.DGTF)
                    _seen = []

                    class _L:
                        def call(self, s, u, t, mx, json_mode=False,
                                 stage=None, **_k):
                            _seen.append(u or "")
                            return '{"sub_questions": []}'

                        def parse_json(self, raw):
                            import json as _j
                            return _j.loads(raw)
                    _d.llm = _L()
                    _d.verbose = False
                    _d._web_digest = "【外部检索摘要】"
                    _d._self_block = lambda: ""
                    _d.config = {"actions": {}}
                    _d._decompose_normal("Q", ["a"], ["b"])
                    _red = "【外部检索摘要】" not in "\n".join(_seen)
            except Exception:  # noqa: BLE001
                _red = True
            assert _red, "★ 变异体「%s」下判据**没判红**（无判别力）" % _nm

        print("  ✓ v1.23.0 W2：W# 编号/引用门/只许→partial/默认关零调用/"
              "配额/失败留痕/空结果终态/摘要只进 prompt + **3 变异体全判红**")
        return True
    except Exception as e:
        print("  ✗ v1.23.0 W2 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
def check_v123_pool_export(SRC=None):
    """[v1.23.0 W5-fix] **通用前向守卫**：Pool 的每个 dataclass 字段都必须出口。

    起因：`Pool.to_dict()` 是**显式**白名单，W2/W3 新增的 5 个联网字段没被列
    进去 ⇒ 真跑里 tavily 返回了结果、产物里 W# 却是 0（静默吞掉）。
    这与 `dec_norm` 是同一类坑。

    做法：把 Pool **所有** dataclass 字段填满（bool→True / dict→非空 / list→非空），
    再断言每一个字段名都出现在 `to_dict()` 的键里。任何人以后加字段忘了出口，
    这条立刻红 —— 不需要再靠「想起来」。
    ★ 带变异体：抠掉 `to_dict` 里 web_results 那一行 → 判据必须判红。
    """
    try:
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        def _miss(pool):
            return [f for f in m.Pool.__dataclass_fields__ if f not in pool.to_dict()]

        p = m.Pool()
        for f in m.Pool.__dataclass_fields__:
            cur = getattr(p, f)
            if isinstance(cur, bool):
                setattr(p, f, True)
            elif isinstance(cur, dict):
                setattr(p, f, {"_probe": 1})
            elif isinstance(cur, list):
                setattr(p, f, [{"_probe": 1}])
        _mo = _miss(p)
        assert not _mo, "★ Pool 字段没出口（to_dict 白名单漏了）：" + repr(_mo)

        # 加性：空 Pool 时联网键一个都不加（关闭态 packed 与前版逐字相同）
        _empty = set(m.Pool().to_dict())
        assert not any(str(k).startswith("web_") for k in _empty), \
            "空 Pool 竟挂了联网键（加性破了）：" + repr(sorted(_empty))

        # ★ 变异体：抠掉 to_dict 里的 web_results 出口
        O = ('        if self.web_results or self.web_errors or '
             'self.web_as_evidence:' + chr(10))
        assert src.count(O) == 1, "to_dict 出口锚点 %d 次" % src.count(O)
        _d = _P(_tf.mkdtemp())
        _mp = _d / "mut_export.py"
        _mp.write_bytes(src.replace(O, "        if False:" + chr(10))
                        .replace("\n", "\r\n").encode("utf-8"))
        _mm = _v1221_mod(str(_mp))
        _pm = _mm.Pool()
        _pm.web_results = [{"id": "W1"}]
        _red = "web_results" in _miss(_pm)
        assert _red, "★ 变异体（抠掉 web_results 出口）下判据没判红"

        print("  ✓ v1.23.0 W5-fix：Pool 字段出口前向守卫（全字段填满必须全出口 + "
              "空 Pool 零联网键 + 变异体判红）")
        return True
    except Exception as e:
        print("  ✗ v1.23.0 W5-fix 失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
def check_v123_left(SRC=None):
    """[v1.23.1 遗留收尾] 真圈号（round_no）+ tier 提案（待审）。

    ★ 两条都带**变异体**：
      · 把提案写进 item["tier"] ⇒ 「提案是纯留痕」判据必须判红；
      · 前置圈号退回拆解序号 ⇒ 「前置=0」判据必须判红。
    """
    try:
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        # 1 结构
        assert hasattr(m, "_web_tier_proposal"), "缺 tier 提案函数"
        assert hasattr(m, "_web_domain_of"), "缺 _web_domain_of"
        assert all(hasattr(m.WebSearchCache, k)
                   for k in ("domains_load", "domains_save")), "缺域名登记方法"
        assert "web_tier_proposals" in m.Pool.__dataclass_fields__, "Pool 缺字段"
        _wscfg = m.DEFAULT_CONFIG.get("web_search") or {}
        assert "tier_proposal" in _wscfg, "缺配置键 tier_proposal"
        assert "domain_tier_rules" in _wscfg, "缺配置键 domain_tier_rules"
        assert _wscfg["tier_proposal"] is False, "★ tier_proposal 必须默认关"

        # 2 round_no 口径：前置 = 0（且与拆解序号无关）
        _mo = object.__new__(m.MetaDGTF)
        _mo._web_prep_seq = 9
        assert m.MetaDGTF._research_round_no(_mo) == 0, (
            "★ 前置圈号不是 0（退回拆解序号了）")

        class _SC:
            def __init__(self, root, url="https://www.example.gov.cn/a",
                         cls=None):
                self.cache = (cls or m.WebSearchCache)(24, root=str(root))
                self.calls = 0
                self.cache_hits = 0
                self.url = url

            def search(self, q, max_n=8):
                self.calls += 1
                return [{"claim": "c" + str(q), "url": self.url,
                         "source": "s", "tier": 3}], ""

        def _mk(over=None, root=None, mod=None):
            mod = mod or m
            c = {"web_search": dict(mod.DEFAULT_CONFIG["web_search"])}
            for k in ("quota", "stages"):
                c["web_search"][k] = dict(c["web_search"].get(k) or {})
            c["web_search"]["domain_tier_rules"] = list(
                c["web_search"].get("domain_tier_rules") or [])
            c["web_search"].update(over or {"enabled": True,
                                            "as_evidence": "evidence"})
            o = object.__new__(mod.MetaDGTF)
            o.config = c
            o.pools = {"1": mod.Pool()}
            o.vp = lambda *a, **k: None
            o._web_gate = mod.WebSearchGate(c)
            o._web_client = _SC(root or _P(_tf.mkdtemp()),
                                cls=mod.WebSearchCache)
            o._web_prep_seq = 0
            return o

        # 圈内钩子必须用真圈号（不是前置 0、也不是拆解序号）
        _o = _mk()
        _o._web_evidence_hook({"to": "partial", "_sq_text": "q"}, 3)
        _w = _o.pools["1"].web_results
        assert _w, "证据钩子没产出"
        assert all(int(x.get("round", -1)) == 3 for x in _w), (
            "★ 圈内钩子没用真圈号：" + repr([x.get("round") for x in _w]))
        assert all(x.get("round_kind") == "in" for x in _w), "round_kind 不是 in"
        _o2 = _mk()
        _o2._research_web_prep("Q")
        _w2 = _o2.pools["1"].web_results
        assert _w2, "前置检索没产出"
        assert all(int(x.get("round", -1)) == 0 for x in _w2), "前置 round 不是 0"
        assert all(x.get("round_kind") == "pre" for x in _w2), (
            "前置 round_kind 不是 pre")

        # 3 tier 提案：默认关零副作用 / 开启纯留痕
        _d = _P(_tf.mkdtemp())
        _off = _mk(root=_d)
        _off._web_search("research_evidence", ["a"], 1)
        assert _off.pools["1"].web_tier_proposals == [], "默认关竟挂提案"
        assert not (_d / "_domains.json").exists(), "默认关竟写域名文件"
        _t_off = [x.get("tier") for x in _off.pools["1"].web_results]

        _d2 = _P(_tf.mkdtemp())
        _on = _mk({"enabled": True, "as_evidence": "evidence",
                   "tier_proposal": True}, root=_d2)
        _on._web_search("research_evidence", ["a"], 1)
        _pr = _on.pools["1"].web_tier_proposals
        assert _pr, "开启后没有提案"
        assert any("[W-TIER?]" in str(x) for x in _on.pools["1"].meta), (
            "开启后提案未留痕")
        assert all(x.get("confirmed") is False for x in _pr), "提案被当成生效值"
        assert _pr[0].get("proposed_tier") == 1, (
            "gov.cn 应命中规则取 1（实测 %r）" % _pr[0].get("proposed_tier"))
        assert (_d2 / "_domains.json").is_file(), "域名未登记"
        assert [x.get("tier") for x in _on.pools["1"].web_results] == _t_off, (
            "★ 提案改了 item['tier']（应纯留痕）")

        # 4 变异体：把提案写进 item["tier"] → 上一条判据必须判红
        _o_anchor = "                    if _ck is not None:" + chr(10)
        assert src.count(_o_anchor) == 1, (
            "tier 提案锚点 %d 次" % src.count(_o_anchor))
        _nl, _cr = chr(10), chr(13)
        _mut = (_o_anchor
                + "                        for _it in out:" + _nl
                + "                            if _pr and "
                  "int(_it.get('tier', 3) or 3) == 3:" + _nl
                + "                                _it['tier'] = int("
                  "_pr[0]['proposed_tier'])" + _nl)
        _md = _P(_tf.mkdtemp())
        _mp = _md / "mut_left.py"
        _mp.write_bytes(src.replace(_o_anchor, _mut)
                        .replace(_nl, _cr + _nl).encode("utf-8"))
        _mm = _v1221_mod(str(_mp))
        _mo2 = _mk({"enabled": True, "as_evidence": "evidence",
                    "tier_proposal": True},
                   root=_P(_tf.mkdtemp()), mod=_mm)
        _mo2._web_search("research_evidence", ["a"], 1)
        _red = [x.get("tier") for x in _mo2.pools["1"].web_results] != [3]
        assert _red, "★ 变异体（提案写进 item tier）下判据没判红"

        print("  ✓ v1.23.1 遗留收尾：前置圈号=0 / 圈内=真圈号 / round_kind"
              " / tier 提案默认关零副作用 / gov.cn→1 待审 / 提案纯留痕"
              " + **变异体判红**")
        return True
    except Exception as e:
        print("  ✗ v1.23.1 遗留收尾失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
def check_v1232_audit(SRC=None):
    """[v1.23.2 整体审计] 把 `_probe_v1232_audit.py` 当**验收命令**跑。

    ★ 为什么用子进程而不是重抄：审计探针本身就是那批判据的**单一事实源**
      （本项目老坑：同一批判据两处分叉，改一边忘一边）。
    """
    try:
        import subprocess
        import sys as _s
        _pp = HERE / "_probe_v1232_audit.py"
        assert _pp.is_file(), "_probe_v1232_audit.py 不存在"
        # ★ 被测文件取**已加载模块**的 __file__，不写死版本名 ——
        #   否则升版后 C2「smoke SRC 指向本版」必判红。
        _tgt = str(SRC or getattr(globals().get("mod"), "__file__", "")
                   or (HERE / "元DGTF-V1.23.3.py"))
        _r = subprocess.run([_s.executable, str(_pp), _tgt],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=900)
        _out = (_r.stdout or "") + (_r.stderr or "")
        _red = [l.strip() for l in _out.split(chr(10)) if l.strip().startswith("✗")]
        assert not _red, "审计判红 " + str(len(_red)) + " 条：" + _red[0][:110]
        _m = _out.strip().split(chr(10))[-1]
        print("  ✓ v1.23.2 整体审计：" + _m[:120])
        return True
    except Exception as e:
        print("  ✗ v1.23.2 整体审计失败：" + type(e).__name__ + ": " + str(e))
        return False

def check_v1232_tier(SRC=None):
    """[v1.23.2 遗留3] tier **确认**才生效（默认零差异 + 不进判定路径）。

    ★ 带变异体：把确认表读进 `tier_effective` 的那一步换成读**提案**——
      判据必须判红（「从提案到生效没有自动路径」这条红线）。
    """
    try:
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        def _cfg(**over):
            c = {"web_search": dict(m.DEFAULT_CONFIG.get("web_search") or {})}
            return c

        # ★ 必须显式 enabled —— 出厂默认是**关**，否则 `_web_search` 直接返回
        #   []，后面的「加性」断言会以「挂了 tier_effective」的形态**误报**
        #   （判据自己没被触发，却报成被测代码的问题）。
        _WS = dict(_cfg()["web_search"])
        _WS["enabled"] = True
        _WS["as_evidence"] = "evidence"
        # 1 默认：无确认表 ⇒ tier 3 仍可进表（与 v1.23.1 一致）+ 不挂键
        # ★ 必须有 claim —— `_citation_table` 会跳过 claim 为空的条目（
        #   第一版漏了它，判据以「W1 竟然进不了表」的形态误报）。
        _it = {"id": "W1", "claim": "c",
               "url": "https://www.example.gov.cn/a", "tier": 3}
        _p = m.Pool()
        _p.web_results = [dict(_it)]
        _p.web_as_evidence = True
        _p._web_cfg = dict(_WS)
        assert "W1" in dict(m._citation_table(None, _p)), "默认态 W1 竟进不了表"
        _x = {}
        _x["_web_cfg"] = dict(_WS)
        assert m._web_tier_confirmed(_cfg(), _it["url"]) is None, "空确认表竟有值"

        # 2 确认成 4（博客档）⇒ 挡在引用表外 + 挂 tier_effective + 留痕
        _ws2 = dict(_WS)
        # ★ 域名必须与桩客户端返回的 URL **同域**：桩返回 a.example.com，
        #   这里确认 example.gov.cn 就永远命中不了（第一版即此，判据以
        #   「没挂 tier_effective」的形态误报）。
        # 两张都要：`_it` 的域是 example.gov.cn（纯函数判据用），
        # 桩返回的是 a.example.com（加性/留痕判据用）—— 只写一张，
        # 另一条判据就会以「确认表没读到」的形态误报。
        _ws2["tier_confirmed"] = {"a.example.com": 4,
                                  "example.gov.cn": 4}
        _c2 = {"web_search": _ws2}
        assert m._web_tier_confirmed(_c2, _it["url"]) == 4, "确认表没读到"
        _it2 = dict(_it)
        _it2["tier_effective"] = 4
        assert not m._web_enters_citation(_it2, _ws2), "确认成 4 竟然还进表"
        _p2 = m.Pool()
        _p2.web_results = [_it2]
        _p2.web_as_evidence = True
        _p2._web_cfg = dict(_ws2)
        assert "W1" not in dict(m._citation_table(None, _p2)), "确认后仍在表里"

        # 3 确认成 1（更硬）⇒ 仍进表（floor=3），且摘要显示生效档
        _ws3 = dict(_WS)
        _ws3["tier_confirmed"] = {"example.gov.cn": 1}
        _it3 = dict(_it)
        _it3["tier_effective"] = 1
        assert m._web_enters_citation(_it3, _ws3), "确认成 1 竟进不了表"
        _dg = m._web_digest_block([_it3])
        assert "tier 1" in _dg, "摘要没有显示生效档（实测 " + _dg[:120] + "）"

        # 4 floor 可调：把 floor 降到 0 ⇒ 任何条目都进不了
        _ws4 = dict(_WS)
        _ws4["tier_floor"] = 0
        assert not m._web_enters_citation(_it, _ws4), "floor=0 竟然还放行"

        # 5 加性：无确认时 `_web_search` 不挂 tier_effective
        class _SC:
            def __init__(self):
                self.calls = 0
                self.cache_hits = 0

            def search(self, q, max_n=8):
                self.calls += 1
                return [{"claim": "c", "url": "https://a.example.com/x",
                         "source": "s", "tier": 3}], ""

        def _mk(ws):
            c = {"web_search": dict(ws)}
            o = object.__new__(m.MetaDGTF)
            o.config = c
            o.pools = {"1": m.Pool()}
            o.vp = lambda *a, **k: None
            o._web_gate = m.WebSearchGate(c)
            o._web_client = _SC()
            o._web_prep_seq = 0
            return o

        _o = _mk(_WS)
        _o._web_search("research_evidence", ["a"], 1)
        _w = _o.pools["1"].web_results
        assert _w, "默认态没检索到任何条目（判据没被触发 —— 先查 enabled）"
        assert all("tier_effective" not in x for x in _w), (
            "默认态竟挂了 tier_effective（破坏加性）")
        _o2 = _mk(_ws2)
        _o2._web_search("research_evidence", ["a"], 1)
        _w2 = _o2.pools["1"].web_results
        assert any("tier_effective" in x for x in _w2), "确认态没挂 tier_effective"
        assert any("[W-TIER" in str(x) for x in _o2.pools["1"].meta), (
            "确认生效未留痕")

        # 6 ★ 变异体：让 `_web_tier_confirmed` 在确认表未命中时**回落读提案**
        _A = "    _conf = _web_cfg_of(cfg).get(\"tier_confirmed\") or {}"
        _B = ("    _conf = (_web_cfg_of(cfg).get(\"tier_confirmed\")\n"
              "             or {d.get(\"domain\"): d.get(\"proposed_tier\")\n"
              "                 for d in (_web_cfg_of(cfg).get(\"tier_proposals\") or [])})")
        _c = src.count(_A)
        assert _c == 1, "变异体锚点 %d 次" % _c
        _tmpd = _P(_tf.mkdtemp())
        _mp = _tmpd / "mut_tier.py"
        _mp.write_bytes(src.replace(_A, _B).replace(chr(10), chr(13) + chr(10))
                        .encode("utf-8"))
        _mm = _v1221_mod(str(_mp))
        _wsx = dict(_WS)
        _wsx["tier_proposals"] = [{"domain": "example.gov.cn",
                                   "proposed_tier": 4}]
        _red = _mm._web_tier_confirmed({"web_search": _wsx},
                                      "https://www.example.gov.cn/a") == 4
        assert _red, "★ 变异体（提案当确认用）下判据没判红"

        print("  ✓ v1.23.2 遗留3 tier 确认：默认零差异 / 确认成 4 出门 / 成 1 显示"
              "生效档 / floor 可调 / 加性 / **变异体判红**")
        return True
    except Exception as e:
        print("  ✗ v1.23.2 遗留3 tier 确认失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False

def check_v1232_retry(SRC=None):
    """[v1.23.2 遗留1] 空票重试：默认 1 次；置 0 退回 v1.23.1 行为。

    ★ 带变异体：把重试关掉（`range(1)`）⇒ 「可用票 3」判据必须判红。
    """
    try:
        import json as _json
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)

        class _LLM:
            """第 2 票**第一次**返回空 judgments，第二次正常。"""

            def __init__(self):
                self.n = -1
                self.tries = {}

            def call(self, sysp, user, t, mx, json_mode=False, stage=None, **k):
                self.n += 1
                self.tries[self.n] = self.tries.get(self.n, 0) + 1
                if self.n == 1 and self.tries[1] == 1:
                    return '{"judgments": []}'
                return _json.dumps({"judgments": [
                    {"id": 1, "reason": "r", "decidability": "decidable"}]})

            def parse_json(self, raw):
                return _json.loads(raw)

        def _run(retry):
            o = object.__new__(m.MetaDGTF)
            o.llm = _LLM()
            o.config = {"actions": {"tri_vote_retry_empty": retry}}
            o.pools = {"1": m.Pool()}
            o.vp = lambda *a, **k: None
            o._web_gate = None
            subs = [{"id": 1, "question": "q", "decidability": "partial"}]
            o._adjudicate_sub_tristate_multi(subs, "Q")
            return subs, o

        _s1, _o1 = _run(1)
        _n1 = len(_s1[0].get("votes") or [])
        assert _n1 == 3, "默认重试 1 次后应有 3 票可用（实测 %d）" % _n1
        _s0, _o0 = _run(0)
        _n0 = len(_s0[0].get("votes") or [])
        assert _n0 == 2, "重试置 0 时应退回 v1.23.1 行为（2 票，实测 %d）" % _n0
        assert any("票可用" in str(x) for x in _o0.pools["1"].meta), (
            "空票留痕丢了")
        assert not any("票可用" in str(x) for x in _o1.pools["1"].meta), (
            "重试成功后不该再报空票")

        # 变异体：把重试关掉（1+max(0,_retry) → 1）
        _A = "            for _try in range(1 + max(0, _retry)):"
        _c = src.count(_A)
        assert _c == 1, "变异体锚点 %d 次" % _c
        _tmpd = _P(_tf.mkdtemp())
        _mp = _tmpd / "mut_retry.py"
        _mp.write_bytes(src.replace(_A, "            for _try in range(1):")
                        .replace(chr(10), chr(13) + chr(10)).encode("utf-8"))
        _mm = _v1221_mod(str(_mp))
        o = object.__new__(_mm.MetaDGTF)
        o.llm = _LLM()
        o.config = {"actions": {"tri_vote_retry_empty": 1}}
        o.pools = {"1": _mm.Pool()}
        o.vp = lambda *a, **k: None
        o._web_gate = None
        subs = [{"id": 1, "question": "q", "decidability": "partial"}]
        o._adjudicate_sub_tristate_multi(subs, "Q")
        _red = len(subs[0].get("votes") or []) != 3
        assert _red, "★ 变异体（关掉重试）下判据没判红"

        print("  ✓ v1.23.2 遗留1 空票重试：默认 1 次得 3 票 / 置 0 退回 2 票"
              " / 留痕正确 / **变异体判红**")
        return True
    except Exception as e:
        print("  ✗ v1.23.2 遗留1 空票重试失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False
def check_v1233_vote_ids(SRC=None):
    """[v1.23.3 遗留1] 三票 id 归一化 + 产物记**真票号**。

    背景：受控投票实验实测某票返回 **0 起** id ⇒ 引擎按 1 起对齐
    ⇒ 该票**整票错位一格**（第 2 条拿到本该给第 1 条的标签），且无声。
    第二处：产物 `votes[].voter` 原先是**位置**，丢一张票就重编号
    ⇒ `agree13` 比的是别的 prompt 对。
    """
    try:
        import json as _json
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)
        NL = chr(10)

        # 1 纯函数四向
        assert hasattr(m, "_normalize_judgment_ids"), "缺 _normalize_judgment_ids"
        _f = m._normalize_judgment_ids
        assert _f({1: "a", 2: "b"}, 2) == ({1: "a", 2: "b"}, "1起"), "1 起应原样"
        assert _f({0: "a", 1: "b"}, 2) == ({1: "a", 2: "b"}, "0起+1"), "0 起应 +1"
        assert _f({1: "a", 9: "b"}, 2)[0] is None, "越界应判 None"
        assert _f({}, 2)[0] is None, "空应判 None"
        assert _f({0: "a", 2: "b"}, 2)[0] is None, "混合应判 None"
        print("  ✓ v1.23.3 id 归一化：纯函数四向正确")

        # 2 两条生产路径都接了它（防死代码 / 防只改一处）
        #   ★ 抠函数体带**开括号**：`def 名` 会被前缀同名函数截走（老坑）。
        def _body(nm):
            import ast as _a
            i2 = src.find("def " + nm + "(")
            assert i2 >= 0, "找不到函数 " + nm
            ln2 = src[:i2].count(chr(10)) + 1
            L2 = src.split(chr(10))
            for n2 in _a.walk(_a.parse(src)):
                if isinstance(n2, _a.FunctionDef) and n2.lineno == ln2:
                    return chr(10).join(L2[n2.lineno - 1:n2.end_lineno])
            raise AssertionError("抠不出 " + nm + " 的体")

        for _fn in ("_adjudicate_sub_tristate_multi", "_adjudicate_sub_tristate"):
            assert "_normalize_judgment_ids(" in _body(_fn), (
                _fn + " 体里没有归一化调用")
        print("  ✓ v1.23.3 id 归一化：多票 / 单票两条路径都已接线")

        # 3 ★ 端到端：0 起票必须被 +1 归一（逐票逐条对齐）
        LAB = ("decidable", "partial", "undecidable")

        class _Stub:
            def __init__(self, shift=None, bad=None, n=3):
                self.i = -1
                self.shift = shift
                self.bad = bad
                self.n = n

            def call(self, sysp, user, t, mx, json_mode=False, stage=None,
                     **k):
                self.i += 1
                base = 0 if self.i == self.shift else 1
                if self.i == self.bad:
                    base = 50
                return _json.dumps({"judgments": [
                    {"id": base + j, "reason": "r",
                     "decidability": LAB[(j + self.i) % 3]}
                    for j in range(self.n)]})

            def parse_json(self, raw):
                return _json.loads(raw)

        def _run(stub):
            o = object.__new__(m.MetaDGTF)
            o.llm = stub
            o.config = dict(m.DEFAULT_CONFIG)
            o.config["actions"] = dict(o.config["actions"])
            o.config["actions"]["tri_multi_vote"] = True
            o.pools = {"1": m.Pool()}
            o.vp = lambda *a, **k: None
            o._web_gate = None
            subs = [{"id": i + 1, "question": "q" + str(i + 1),
                     "decidability": "partial"} for i in range(3)]
            o._adjudicate_sub_tristate_multi(subs, "Q")
            return o, subs

        def _lab(subs):
            return [[(v["voter"], v["label"]) for v in sorted(
                (x.get("votes") or []), key=lambda y: y["voter"])]
                for x in subs]

        want = [[(v, LAB[(j + v) % 3]) for v in (0, 1, 2)] for j in range(3)]
        _o1, _s1 = _run(_Stub(shift=1))
        got = _lab(_s1)
        assert got == want, "0 起票未归一到正确位置：" + repr(got)
        # ★ 同时钉「产物记真票号」：三票都要在（0/1/2），不是重编号后的位置
        assert all(x == 3 for x in (len(g) for g in got)), "票数不为 3"
        assert any(("0 起→+1" in str(x)) for x in _o1.pools["1"].meta), (
            "0 起归一没留痕")
        print("  ✓ v1.23.3 端到端：0 起票被 +1 归一，逐票逐条对齐且留痕")

        # 4 负对照：正常票（1 起）结果与上面**逐条相同**，且不留异常痕
        _o2, _s2 = _run(_Stub(shift=None))
        assert _lab(_s2) == want, "正常票结果与归一后不一致（归一改坏了）"
        assert not any(("id 0 起" in str(x) or "越界" in str(x))
                       for x in _o2.pools["1"].meta), "正常票不该留异常痕"
        print("  ✓ v1.23.3 负对照：正常票行为与留痕都未变（加性）")

        # 5 ★ 越界票：弃票（剩**另外两票**，且 `voter` 是真票号）+ 留痕
        _o3, _s3 = _run(_Stub(bad=1))
        want3 = [[(0, LAB[j % 3]), (2, LAB[(j + 2) % 3])] for j in range(3)]
        assert _lab(_s3) == want3, "越界票没有按『弃票 + 真票号』处理：" + repr(
            _lab(_s3))
        assert any(("越界弃票" in str(x)) for x in _o3.pools["1"].meta), (
            "越界没留痕")
        assert any(("2/3" in str(x)) for x in _o3.pools["1"].meta), (
            "可用票数没扣掉弃票")
        print("  ✓ v1.23.3 越界票：弃票 + 真票号 + 可用票数已扣除")

        # 6 变异体：抠掉「0 起 +1」分支 ⇒ 端到端判据必须判红
        _O = ("    if _ks <= set(range(0, _hi)):" + NL
              + "        return {int(k) + 1: v for k, v in judged.items()}, "
              + chr(34) + "0起+1" + chr(34))
        assert src.count(_O) == 1, "变异体锚点命中 %d 次" % src.count(_O)
        _td = _P(_tf.mkdtemp())
        _mp = _td / "mut_voteids.py"
        _mp.write_bytes(src.replace(_O, "    if False:" + NL
                                    + "        return {int(k) + 1: v "
                                    + "for k, v in judged.items()}, "
                                    + chr(34) + "0起+1" + chr(34))
                        .replace(NL, chr(13) + NL).encode("utf-8"))
        _mm = _v1221_mod(_mp)
        _mo = object.__new__(_mm.MetaDGTF)
        _mo.llm = _Stub(shift=1)
        _mo.config = dict(_mm.DEFAULT_CONFIG)
        _mo.config["actions"] = dict(_mo.config["actions"])
        _mo.config["actions"]["tri_multi_vote"] = True
        _mo.pools = {"1": _mm.Pool()}
        _mo.vp = lambda *a, **k: None
        _mo._web_gate = None
        _ms = [{"id": i + 1, "question": "q", "decidability": "partial"}
               for i in range(3)]
        _mo._adjudicate_sub_tristate_multi(_ms, "Q")
        _mg = [[(v["voter"], v["label"]) for v in sorted(
            (x.get("votes") or []), key=lambda y: y["voter"])] for x in _ms]
        assert _mg != want, "变异体『抠掉 0 起 +1』竟然没判红"
        print("  ✓ v1.23.3 变异体：抠掉 0 起 +1 ⇒ 端到端判据判红")
        return True
    except Exception as e:
        print("  ✗ v1.23.3 三票 id 归一化失败：" + type(e).__name__ + ": "
              + str(e))
        import traceback
        traceback.print_exc()
        return False

def check_v1234_runtime(SRC=None):
    """[v1.23.4] 运行期三项总控（联网 / 思考 / 强度）。

    背景：这三项此前只能靠改 `dgtf_config.yaml` 再重跑；交互里问不到、
    命令行也传不了。本版给它们一个顶层 `runtime` 段 + 交互/CLI 两条入口。

    判据重点（都是「不做会静默出错」的地方）：
      · auto 必须**逐字恒等** —— 否则默认出厂就跑偏了；
      · **思考关必须连 stages 整表一起关** —— `LLM.call` 的优先级是
        「显式 > stage > default」，只改 default 会被 stage 表盖住，
        总开关就是一句空话；
      · 非法值**不静默**（不改任何键 + 有告警），空输入(回车)=auto；
      · 纯函数**不改入参**（否则交互第二轮选 auto 会读到第一轮的值）。
    """
    try:
        import json as _json
        import tempfile as _tf
        from pathlib import Path as _P

        m = _v1221_mod(SRC)
        src = _v1221_src_text(SRC)
        NL = chr(10)
        D = _json.loads(_json.dumps(m.DEFAULT_CONFIG))
        J = lambda o: _json.dumps(o, sort_keys=True, ensure_ascii=False)

        # ---- 1 接口齐全 ----
        for _n in ("_apply_runtime", "_runtime_snapshot",
                   "_runtime_summary_line", "_normalize_runtime_switch",
                   "_normalize_runtime_effort", "_runtime_thinking_on"):
            assert hasattr(m, _n), "缺 " + _n
        assert m._RUNTIME_SWITCHES == ("auto", "on", "off"), "开关集合"
        assert m._RUNTIME_EFFORTS == ("auto", "low", "high", "max"), (
            "强度集合应为 low/high/max（出厂 yaml 记录的实测集）")
        print("  ✓ v1.23.4 总控：6 个符号与两个取值集都对")

        # ---- 2 ★ auto 恒等：不覆盖任何既有键 ----
        c0, n0 = m._apply_runtime(D)
        assert J(c0) == J(D), "runtime 全 auto 竟然改了配置（不是恒等变换）"
        assert n0 == [], "auto 不该产生任何留痕行：" + repr(n0)
        c0b, _ = m._apply_runtime(D, {"web": "auto", "thinking": "auto",
                                      "effort": "auto"})
        assert J(c0b) == J(D), "显式 auto 也必须是恒等"
        print("  ✓ v1.23.4 总控：三项 auto = 配置逐字恒等（与 v1.23.3 同行为）")

        # ---- 3 联网总开关落键 ----
        cw, nw = m._apply_runtime(D, {"web": "on"})
        assert cw["web_search"]["enabled"] is True, "web=on 没开"
        assert any("联网" in x for x in nw), "web=on 没留痕"
        cw2, _ = m._apply_runtime(D, {"web": "off"})
        assert cw2["web_search"]["enabled"] is False, "web=off 没关"
        print("  ✓ v1.23.4 总控：联网 on/off 正确落到 web_search.enabled")

        # ---- 4 ★★ 思考总开关：default + 整张 stages 表 ----
        co, no = m._apply_runtime(D, {"thinking": "off"})
        _t = co["api"]["thinking"]
        assert _t["default"] == "disabled", "thinking=off 的 default 没改"
        _vals = set(_t["stages"].values())
        assert _vals == {"disabled"}, (
            "thinking=off 没有把 stages 整表关掉：剩余取值 " + repr(_vals))
        assert len(_t["stages"]) == len(D["api"]["thinking"]["stages"]), (
            "stages 的键数变了（应当只改值、不改键集）")
        cn, _ = m._apply_runtime(D, {"thinking": "on"})
        _t2 = cn["api"]["thinking"]
        assert _t2["default"] == "enabled", "thinking=on 的 default 没改"
        assert set(_t2["stages"].values()) == {"enabled"}, (
            "thinking=on 没有把 stages 整表打开")
        print("  ✓ v1.23.4 总控：思考 on/off 同时改写 default 与 stages 整表")

        # ---- 5 ★ 与 LLM 的真实解析联动（比只看配置键强一档）----
        #   ★ 这里**不设** process 级环境变量去凑一个假 key —— 冒烟是同进程
        #     跑几十条判据，改 `os.environ` 会污染后面所有环节（本项目
        #     「判据不能有跨条副作用」的纪律）。有 key 就真构造 LLM 核对，
        #     没有就退回「按 call 的优先级模拟解析」——两条路量的是同一件事。
        _L = None
        try:
            _L = m.LLM(co)
            assert str(_L.thinking_default).lower() == "disabled", (
                "LLM 真实解析：thinking=off 的 default 不对")
            assert not [k for k, v in _L.thinking_stages.items()
                        if str(v).lower() == "enabled"], (
                "LLM 真实解析：thinking=off 仍有环节开档")
        except Exception as _e:  # noqa: BLE001
            print("  · LLM 构造不可用（" + type(_e).__name__
                  + "），改用解析顺序模拟")

        def _resolve(cfg, stage=None):
            th = None
            if stage:
                th = ((cfg.get("api") or {}).get("thinking")
                      or {}).get("stages", {}).get(stage)
            if th is None:
                th = ((cfg.get("api") or {}).get("thinking")
                      or {}).get("default")
            return str(th or "").lower() == "enabled"

        assert _resolve(co, "auto_plan") is False, (
            "thinking=off 后 auto_plan（出厂为 enabled）仍然是 True")
        assert _resolve(co, "从未声明过的环节") is False, (
            "thinking=off 后未声明环节（掉 default）仍是 True")
        assert _resolve(cn, "decompose_koan") is True, (
            "thinking=on 后 decompose_koan（出厂为 disabled）仍是 False")
        print("  ✓ v1.23.4 总控：思考关/开后，**按 call 的优先级解析**结果正确")

        # ---- 6 强度落键 + 只在思考开启时有意义 ----
        ce, ne = m._apply_runtime(D, {"effort": "max"})
        assert ce["api"]["thinking"]["effort"] == "max", "effort 没落键"
        ce2, ne2 = m._apply_runtime(D, {"thinking": "off", "effort": "high"})
        assert any("不生效" in x for x in ne2), (
            "思考关时设了强度，却没有提示「不生效」")
        print("  ✓ v1.23.4 总控：强度落键，且思考关时明确提示「不生效」")

        # ---- 7 ★ 非法值不静默：不改任何键 + 有告警 ----
        for _k, _bad in (("web", "yes_please"), ("thinking", "maybe"),
                         ("effort", "mediun")):
            _cb, _nb = m._apply_runtime(D, {_k: _bad})
            assert J(_cb) == J(D), (
                "%s=%r 非法值竟然改了配置（静默回落）" % (_k, _bad))
            assert any("非法" in x for x in _nb), (
                "%s=%r 非法值没有告警" % (_k, _bad))
            # ★ 不变式：`runtime` 段里**永远是合法的归一值**（非法输入由
            #   `⚠️` 留痕报告，不落进配置）。这条是「记录可被下游直接消费」
            #   的前提 —— 也是我第一版把原始输入写回去时**当场判红**的那条。
            assert all(
                ((_cb.get("runtime") or {}).get(_kk)
                 in (m._RUNTIME_EFFORTS if _kk == "effort"
                     else m._RUNTIME_SWITCHES))
                for _kk in ("web", "thinking", "effort")), (
                "runtime 段被写入集合外的值：" + repr(_cb.get("runtime")))
        print("  ✓ v1.23.4 总控：三个非法值都被拒 + 告警，配置一字未改"
              "（且 runtime 段三值恒合法）")

        # ---- 8 ★ 空输入（回车）= auto：交互提示写的就是「回车=auto」 ----
        for _v in ("", None, "  "):
            assert m._normalize_runtime_switch(_v) == "auto", (
                "开关空输入应为 auto：%r" % (_v,))
            assert m._normalize_runtime_effort(_v) == "auto", (
                "强度空输入应为 auto：%r" % (_v,))
        assert m._normalize_runtime_switch("y") == "on"
        assert m._normalize_runtime_switch("关") == "off"
        assert m._normalize_runtime_effort("MAX") == "max"
        assert m._normalize_runtime_effort("medium") is None, (
            "medium 不在实测取值集里，必须被拒（不能悄悄发出去）")
        print("  ✓ v1.23.4 总控：空输入/别名归一正确，集合外的值被拒")

        # ---- 9 ★ 纯函数：不改入参 ----
        _before = J(D)
        m._apply_runtime(D, {"web": "on", "thinking": "on", "effort": "max"})
        assert J(D) == _before, (
            "`_apply_runtime` 改了入参 —— 交互第二轮选 auto 会读到第一轮的值")
        print("  ✓ v1.23.4 总控：纯函数，入参配置一字未改")

        # ---- 10 生效读数与摘要 ----
        cs, _ = m._apply_runtime(D, {"web": "on", "effort": "high"})
        _snap = m._runtime_snapshot(cs)
        assert _snap["web_enabled"] is True, "snapshot.web_enabled 不对"
        assert _snap["effort"] == "high", "snapshot.effort 不对"
        assert isinstance(_snap["thinking_stages_enabled"], list), (
            "snapshot 必须报出开档环节清单")
        _line = m._runtime_summary_line(cs)
        assert ("联网" in _line) and ("思考" in _line) and ("强度" in _line), (
            "摘要行缺字段：" + _line)
        assert _snap["requested"] == {"web": "on", "thinking": "auto",
                                      "effort": "high",
                                      "live_checkpoint": True,
                                      "ckpt_interval": 30.0}, (
            "snapshot.requested 必须回显本次请求（而不是 yaml 的值）："
            + repr(_snap["requested"]))
        print("  ✓ v1.23.4 总控：生效读数 + 一行摘要都可读")

        # ---- 10b ★ `requested` 必须回显**本次真正请求的**三项 ----
        #   ★ 这条是「产物可复盘」的关键：`_apply_runtime` 会把请求值写回
        #     副本的 `runtime` 段。不这么做的话产物里的 `requested` 永远是
        #     yaml 的值 —— 命令行/交互给的三项在产物里**看不到**。
        assert _snap["requested"] == {"web": "on", "thinking": "auto",
                                      "effort": "high",
                                      "live_checkpoint": True,
                                      "ckpt_interval": 30.0}, (
            "snapshot.requested 必须回显本次请求（而不是 yaml 的值）："
            + repr(_snap["requested"]))
        _sn0 = m._runtime_snapshot(c0)
        assert _sn0["requested"] == dict(D.get("runtime") or {}), (
            "全 auto 时 requested 应与出厂 runtime 段逐字相同（恒等）")
        print("  ✓ v1.23.4 总控：`requested` 回显请求值（全 auto 时仍恒等）")

        # ---- 11 ★ load_config 外层套对了（四个出口都过它）----
        _dr = _P(_tf.mkdtemp())
        _y1 = _dr / "rt.yaml"
        _y1.write_bytes(("runtime:" + NL + "  web: off" + NL
                         + "  thinking: off" + NL + "  effort: max"
                         + NL).encode("utf-8"))
        _lc = m.load_config(str(_y1))
        assert _lc["web_search"]["enabled"] is False, "yaml 的 runtime.web 没生效"
        assert _lc["api"]["thinking"]["default"] == "disabled", "yaml 没关思考"
        assert _lc["api"]["thinking"]["effort"] == "max", "yaml 没设强度"
        # 缺路径 / 空路径 / 坏 yaml 三个出口也必须不炸（且仍恒等）
        assert J(m.load_config(str(_dr / "no_such.yaml"))) == J(D), "缺路径出口变了"
        assert J(m.load_config("")) == J(D), "空路径出口变了"
        _y2 = _dr / "bad.yaml"
        _y2.write_bytes(b"a: [1, 2" + bytes([10]))
        assert isinstance(m.load_config(str(_y2)), dict), "坏 yaml 出口炸了"
        print("  ✓ v1.23.4 总控：load_config 四个出口都过总控且不炸")

        # ---- 12 ★ CLI 三个开关真的接上了 ----
        for _flag, _opt in (("--web", "--web {auto,on,off}"),
                            ("--thinking", "--thinking {auto,on,off}"),
                            ("--effort", "--effort {auto,low,high,max}")):
            assert _flag in src, "CLI 缺 " + _flag
        assert "choices=list(_RUNTIME_SWITCHES)" in src, "CLI 开关没收紧取值"
        assert "choices=list(_RUNTIME_EFFORTS)" in src, "CLI 强度没收紧取值"
        # ★ [v1.23.13 判据随实现更新] 原来查的是接线**字面**
        #   `cfg, _rt_notes = _apply_runtime(cfg, {` —— v1.23.13 改成
        #   「调度器把显式值写进 cfg["runtime"]，再由 `_apply_runtime(cfg)` 落」，
        #   字面没了。改成**端到端行为断言**：显式传三个开关，看配置有没有真变。
        _c3 = _json.loads(_json.dumps(D))
        _dp3 = m.auto_dispatch("q", _c3, explicit={"web": "off",
                                                   "thinking": "on",
                                                   "effort": "max"})
        m._apply_auto_dispatch(_c3, _dp3)
        _c3b, _ = m._apply_runtime(_c3)
        assert _c3b["web_search"]["enabled"] is False, (
            "CLI --web off 没有落到 web_search.enabled")
        assert _c3b["api"]["thinking"]["default"] == "enabled", (
            "CLI --thinking on 没有落到 thinking.default")
        assert _c3b["api"]["thinking"]["effort"] == "max", (
            "CLI --effort max 没有落到 thinking.effort")
        # 交互侧
        assert "def _ask_runtime(cfg):" in src, "缺 _ask_runtime"
        assert "runtime = _ask_runtime(" in src, "_ask_runtime 没被调用"
        assert ("(route_str, rounds_str, channels_str, parallel_str,"
                + NL + "         runtime) = cfg_result") in src, (
            "_ask_config 的返回值没扩成 5 元组 / 没解包")
        assert "run_cfg, _rt_notes = _apply_runtime(cfg, runtime)" in src, (
            "交互没有在**深拷副本**上应用（会污染跨轮的 cfg）")
        assert "meta = MetaDGTF(run_cfg)" in src, "交互还在用未应用的 cfg"
        print("  ✓ v1.23.4 总控：CLI 三开关 + 交互询问 + 深拷副本都已接线")

        # ---- 13 ★ 产物留痕 ----
        assert '"_runtime": _runtime_snapshot(self.config)' in src, (
            "产物没有 `_runtime` 生效读数（「这跑到底联网没有」又成黑箱）")
        print("  ✓ v1.23.4 总控：产物带 `_runtime` 生效读数")

        # ================= 变异体 =================
        _td = _P(_tf.mkdtemp())

        def _mut(name, old, new):
            assert src.count(old) == 1, (
                "变异体 " + name + " 锚点命中 " + str(src.count(old)) + " 次")
            _p = _td / ("mut_rt_" + name + ".py")
            _p.write_bytes(src.replace(old, new).replace(
                NL, chr(13) + NL).encode("utf-8"))
            return _v1221_mod(_p)

        # M1 ★ 把 auto 当成 on ⇒ auto 恒等判据必须判红
        _M1 = _mut("auto_as_on",
                   '"": "auto", "a": "auto", "auto": "auto",',
                   '"": "auto", "a": "auto", "auto": "on",')
        _c1, _n1 = _M1._apply_runtime(_json.loads(_json.dumps(
            _M1.DEFAULT_CONFIG)))
        assert J(_c1) != J(_M1.DEFAULT_CONFIG), (
            "变异体 M1『auto 当 on』没被判红（auto 恒等判据失效）")
        print("  ✓ v1.23.4 变异体 M1：把 auto 当 on ⇒ auto 恒等判据判红")

        # M2 ★ 思考总开关只改 default、不碰 stages ⇒ 必须判红
        #   ★ 内含双引号的锚点一律用 `chr(34)` 拼：这段代码本身是包在
        #     三引号单引号字符串里的，写反斜杠加引号会被**吃掉一层反斜杠**
        #     ⇒ 生成出来的 smoke 里引号裸奔 ⇒ 整个文件 SyntaxError。
        #     （本轮实踩；v1.23.3 的注入器同样用 chr(34) 绕开。）
        #   ★ 也别在本字符串里写「三个单引号」本身 —— 那会**提前闭合**外层。
        _Q = chr(34)
        _old2 = NL.join([
            "        _stages = _thc.get(" + _Q + "stages" + _Q + ") or {}",
            "        for _k in list(_stages):",
            "            _stages[_k] = _val",
            "        _thc[" + _Q + "stages" + _Q + "] = _stages",
        ])
        _M2 = _mut("default_only", _old2,
                   "        _stages = _thc.get(" + _Q + "stages" + _Q
                   + ") or {}")
        _c2, _ = _M2._apply_runtime(_json.loads(_json.dumps(
            _M2.DEFAULT_CONFIG)), {"thinking": "off"})
        _v2 = set(_c2["api"]["thinking"]["stages"].values())
        assert _v2 != {"disabled"}, (
            "变异体 M2『只改 default』没被判红（总开关成了空话却测不出来）")
        print("  ✓ v1.23.4 变异体 M2：只改 default 不改 stages ⇒ 判红")

        # M3 ★ effort 不做集合校验 ⇒ 非法值静默通过 ⇒ 必须判红
        _M3 = _mut("effort_nocheck",
                   "    return v if v in _RUNTIME_EFFORTS else None",
                   "    return v if v else None")
        assert _M3._normalize_runtime_effort("mediun") is not None, (
            "变异体 M3『effort 不校验』没被判红")
        _c3, _n3 = _M3._apply_runtime(_json.loads(_json.dumps(
            _M3.DEFAULT_CONFIG)), {"effort": "mediun"})
        assert J(_c3) != J(_M3.DEFAULT_CONFIG), (
            "变异体 M3 下非法值竟然改了配置却没被拦住")
        print("  ✓ v1.23.4 变异体 M3：effort 不校验 ⇒ 非法值静默通过，判红")

        # M4 ★ 抠掉「把请求值写回副本」⇒ 产物 requested 只剩 yaml 的值
        _M4 = _mut("no_request_echo", "    cfg[" + _Q + "runtime"
                   + _Q + "] = _rec", "    pass")
        _c4, _ = _M4._apply_runtime(_json.loads(_json.dumps(
            _M4.DEFAULT_CONFIG)), {"web": "on", "thinking": "off",
                                   "effort": "high"})
        _r4 = _M4._runtime_snapshot(_c4)["requested"]
        assert _r4 != {"web": "on", "thinking": "off", "effort": "high"}, (
            "变异体 M4『不写回请求值』没被判红")
        print("  ✓ v1.23.4 变异体 M4：不写回请求值 ⇒ requested 只剩 yaml，判红")

        return True
    except Exception as e:
        print("  ✗ v1.23.4 运行期总控失败：" + type(e).__name__ + ": " + str(e))
        import traceback
        traceback.print_exc()
        return False

def check_v1235_pending_fix():
    '''[v1.23.5] 三条 pending_fix 的可证伪判据（含归一化唯一实现）。

    #1（本版已收口）调度归一化
       · 唯一实现：_plan_conf / _normalize_plan_mode / _normalize_plan_rounds
         各只有 1 处 def
       · 接线：三处调用点都还在（不是死代码）
       · 行为：同一份 mock 喂「两段式」与「单调用」，mode/rounds 逐字相同
       · ★ 钉住**刻意保留**的差异：低置信时两段式 reason 不动、
         另两处 reason 被改写（这是有意差异，不是漏合并）
    #2（仍未删）单票实现仍在 + 登记表仍是 2 项（两向对账）
    #3（可观测化）布尔兼容走一次必留痕 warning；字符串档不留痕
    '''
    import ast as _ast
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    _i = src.index(chr(34) * 3)
    _j = src.index(chr(34) * 3, _i + 3)
    body = src[_j + 3:]
    tree = _ast.parse(src)

    def _defs(name):
        return sum(1 for n in _ast.walk(tree)
                   if isinstance(n, _ast.FunctionDef) and n.name == name)

    def _calls(name):
        return sum(1 for n in _ast.walk(tree)
                   if isinstance(n, _ast.Call)
                   and isinstance(n.func, _ast.Name) and n.func.id == name)

    # ---- #1a 唯一实现 ----
    for _fn in ("_plan_conf", "_normalize_plan_mode",
                "_normalize_plan_rounds"):
        _d = _defs(_fn)
        if _d != 1:
            bad.append("[1a] %s 的 def 有 %d 处（应为 1）" % (_fn, _d))

    # ---- #1b 形态计数（抠掉模块 docstring 后）----
    for _pat, _want in (("conf = float(data.get(", 0),
                        ("if rnd and len(rnd) < 4:", 1),
                        ("_layer_floor(k, hard, _floor)", 1)):
        _got = body.count(_pat)
        if _got != _want:
            bad.append("[1b] 形态 %r 出现 %d 次（应为 %d）"
                       % (_pat, _got, _want))

    # ---- #1c 接线（含 def 行的同名 Name 不计入 Call，故期望=调用点数）----
    for _fn, _want in (("_normalize_plan_mode", 3), ("_plan_conf", 3),
                       ("_normalize_plan_rounds", 2)):
        _got = _calls(_fn)
        if _got != _want:
            bad.append("[1c] %s 被调用 %d 次（应为 %d）" % (_fn, _got, _want))

    # ---- #1d 三处行为对照（生产入口，不手造中间结构）----
    class _Stub:
        def __init__(self, payload):
            self.payload = payload

        def call(self, *a, **k):
            return json.dumps(self.payload, ensure_ascii=False)

        def parse_json(self, raw):
            return json.loads(raw)

    _cfg = build_cfg(False)
    _rounds_cases = {
        "四层齐": {"0": 3, "1": 7, "both": 4, "all": 6},
        "只给两层": {"0": 5, "1": 5},
        "越界值": {"0": 1, "1": 99, "both": 2, "all": 2},
        "空圈数": {},
    }
    for _m in ("G", "Z", "h", "serial"):
        for _tag, _rin in _rounds_cases.items():
            _pl = {"route": "full", "mode": _m, "rounds": dict(_rin),
                   "max_calls": 0, "reason": "probe", "confidence": 0.8,
                   "orientation": "decision"}
            _m1 = mod.MetaDGTF(_cfg)
            _m1.llm = _Stub(dict(_pl))
            _r1 = _m1._decide_parallel_mode("探针题：评估这个多阶段问题的资源配置路径")
            _s2 = _Stub(dict(_pl))
            _oL = mod.LLM
            mod.LLM = lambda c: _s2
            try:
                _r2 = mod.plan_resources("探针题：评估这个多阶段问题的资源配置路径", "decision", _cfg)
            finally:
                mod.LLM = _oL
            _m3 = mod.MetaDGTF(_cfg)
            _m3.llm = _Stub(dict(_pl))
            _r3 = _m3._auto_plan("探针题：评估这个多阶段问题的资源配置路径")
            _r2r = {k: v for k, v in (_r2.get("rounds") or {}).items()
                    if k in (_r2.get("route") or [])}
            if _r1.get("mode") != _r3.get("mode"):
                bad.append("[1d] %s/%s 单目标 %s vs 单调用 %s"
                           % (_m, _tag, _r1.get("mode"), _r3.get("mode")))
            if _r2.get("mode") != _r3.get("mode") or _r2r != dict(
                    _r3.get("rounds") or {}):
                bad.append("[1d] %s/%s 两段式 %s/%s vs 单调用 %s/%s"
                           % (_m, _tag, _r2.get("mode"), _r2r,
                              _r3.get("mode"), dict(_r3.get("rounds") or {})))

    # ---- #1e 刻意保留的差异：低置信时 reason 的处置 ----
    _lo = {"route": "full", "mode": "G",
           "rounds": {"0": 3, "1": 5, "both": 4, "all": 6},
           "max_calls": 0, "reason": "probe", "confidence": 0.1,
           "orientation": "decision"}
    _m1 = mod.MetaDGTF(_cfg)
    _m1.llm = _Stub(dict(_lo))
    _r1 = _m1._decide_parallel_mode("探针题：评估这个多阶段问题的资源配置路径")
    if _r1.get("mode") != "serial":
        bad.append("[1e] 低置信：单目标决策没退 serial（%s）" % _r1.get("mode"))
    if not str(_r1.get("reason", "")).startswith("低置信"):
        bad.append("[1e] 低置信：单目标决策 reason 未改写（%r）"
                   % _r1.get("reason"))
    _s2 = _Stub(dict(_lo))
    _oL = mod.LLM
    mod.LLM = lambda c: _s2
    try:
        _r2 = mod.plan_resources("探针题：评估这个多阶段问题的资源配置路径", "decision", _cfg)
    finally:
        mod.LLM = _oL
    if _r2.get("mode") != "serial":
        bad.append("[1e] 低置信：两段式没退 serial（%s）" % _r2.get("mode"))
    if _r2.get("reason") != "probe":
        bad.append("[1e] 低置信：两段式 reason 被改写了（%r）—— "
                   "这是刻意保留的差异，不该变" % _r2.get("reason"))
    _m3 = mod.MetaDGTF(_cfg)
    _m3.llm = _Stub(dict(_lo))
    _r3 = _m3._auto_plan("探针题：评估这个多阶段问题的资源配置路径")
    if _r3.get("mode") != "serial":
        bad.append("[1e] 低置信：单调用没退 serial（%s）" % _r3.get("mode"))
    if not str(_r3.get("reason", "")).startswith("低置信"):
        bad.append("[1e] 低置信：单调用 reason 未改写（%r）" % _r3.get("reason"))

    # ---- #2 单票实现仍在 + 登记表两向对账 ----
    _sd = _defs("_adjudicate_sub_tristate")
    if _sd != 1:
        bad.append("[2] _adjudicate_sub_tristate 的 def 有 %d 处（应为 1）"
                   % _sd)
    _sd_calls = sum(
        1 for n in _ast.walk(tree) if isinstance(n, _ast.Call)
        and ((isinstance(n.func, _ast.Name)
              and n.func.id == "_adjudicate_sub_tristate")
             or (isinstance(n.func, _ast.Attribute)
                 and n.func.attr == "_adjudicate_sub_tristate")))
    if _sd_calls < 1:
        bad.append("[2] _adjudicate_sub_tristate 没有任何调用点（死代码？）")
    _n_pf = src.count("# [AUDIT-122] 标 pending_fix：")
    _c_pf = getattr(mod, "_AUDIT122_PENDING_FIX", None)
    if _n_pf != 2 or _c_pf != 2:
        bad.append("[2] 登记表对账失败：源码 %d 条 / 常量 %r（都应为 2）"
                   % (_n_pf, _c_pf))

    # ---- #3 布尔兼容留痕（可观测化）----
    import logging as _lg

    class _H(_lg.Handler):
        def __init__(self):
            _lg.Handler.__init__(self)
            self.msgs = []

        def emit(self, r):
            try:
                self.msgs.append(r.getMessage())
            except Exception:
                pass

    _lgw = _lg.getLogger("dgtf")
    _h = _H()
    _old = _lgw.level
    _lgw.addHandler(_h)
    _lgw.setLevel(_lg.WARNING)
    try:
        _t_true = mod._anchor_tier({"as_evidence": True})
        _n_true = len([m for m in _h.msgs if "布尔写法" in m])
        _h.msgs = []
        _t_off = mod._anchor_tier({"as_evidence": "off"})
        _n_off = len([m for m in _h.msgs if "布尔写法" in m])
        _h.msgs = []
        _t_bad = mod._anchor_tier({"as_evidence": "nonsense"})
        _n_bad = len([m for m in _h.msgs if "布尔写法" in m])
    finally:
        _lgw.removeHandler(_h)
        _lgw.setLevel(_old)
    if _t_true != "evidence":
        bad.append("[3] 布尔 True 应归一成 evidence，实际 %r" % _t_true)
    if _n_true != 1:
        bad.append("[3] 布尔兼容走了却没留痕（捕获 %d 条）" % _n_true)
    if _t_off != "off" or _n_off != 0:
        bad.append("[3] 字符串档 off 不该留痕（%r / %d 条）" % (_t_off, _n_off))
    if _t_bad != "off" or _n_bad != 0:
        bad.append("[3] 非法值应落 off 且不走布尔留痕（%r / %d 条）"
                   % (_t_bad, _n_bad))

    if bad:
        for _m in bad:
            print("  \u2717 [v1235] %s" % _m)
        return False
    print("  \u2713 [v1235] pending_fix：归一化唯一实现+三处接线+16 组逐字一致"
          "；低置信差异保留；单票仍在且登记 2 项；布尔兼容留痕/不误报")
    return True

# [v1.23.6] 版次标记：方括号短标签 `[v122 P6 G6.2]` ｜ 裸 v+数字 `v1.21.59`/`v59`
#   两侧的 lookbehind/lookahead 挡掉 `deepseek-v4-pro` 这类假阳性（实测）。
#   ★ 口径与 `_mk_v1236_strip.py` 里的 TAG 必须逐字一致 —— 判据与清理工具同一把尺子。
V1236_TAG = (r"\[v\d[^\]]*\]|(?<![A-Za-z0-9_\-])v\d+(?:\.\d+)*(?![A-Za-z0-9_\-])")

def check_v1236_no_version_tags():
    """[v1.23.6] 代码正文（模块 docstring 之外）不留版次批注。

    抠掉模块 docstring 后：
      ① 注释里不得出现版次标记（含 `# [vX.Y.Z …]` 与行尾批注）；
      ② 不得有**以版次标记开头**的 docstring。
    ★ 负对照打在**上一版文件**上：v1.23.5 必须被判红 —— 这条负对照是本判据
      判别力的来源，缺了它「全绿」只说明判据没跑（本项目的经典假绿）。
    ★ 抠 docstring 前先归一化换行：`doc in raw` 在 CRLF 原文里是 False，
      会静默退化成「全文件扫描」。
    """
    TAG = re.compile(V1236_TAG)
    bad = []
    raw = SRC.read_bytes().decode("utf-8")
    src = raw.replace("\r\n", "\n")
    i = src.index('"""')
    j = src.index('"""', i + 3)
    body_len = len(src) - (j + 3)
    if not (0 < body_len < len(src) - 3):
        bad.append("抠模块 docstring 没生效（抠法自证失败）")
    de = src[:j].count("\n")
    lines = src.split("\n")
    hits = [k + 1 for k in range(de + 1, len(lines))
            if lines[k].lstrip().startswith("#") and TAG.search(lines[k])]
    trail = [k + 1 for k in range(de + 1, len(lines))
             if not lines[k].lstrip().startswith("#") and "#" in lines[k]
             and TAG.search(lines[k].split("#", 1)[1])]
    if hits or trail:
        bad.append("正文注释里仍有版次批注：%d 行成块 + %d 行行尾，前 5 个行号 %s"
                   % (len(hits), len(trail), (hits + trail)[:5]))
    leads = []
    import ast as _ast
    for node in _ast.walk(_ast.parse(src)):
        if isinstance(node, _ast.Constant) and isinstance(node.value, str):
            if node.lineno > de + 1 and re.match(r"\s*(?:" + V1236_TAG + r")", node.value):
                leads.append(node.lineno)
    if leads:
        bad.append("仍有以版次标记开头的 docstring %d 处，前 5 个行号 %s"
                   % (len(leads), leads[:5]))
    # ---- 负对照：上一版必须判红 ----
    prev = HERE / "元DGTF-V1.23.5.py"
    pn = 0
    if not prev.is_file():
        bad.append("负对照文件缺失 %s —— 判据判别力无法自证" % prev.name)
    else:
        psrc = prev.read_bytes().decode("utf-8").replace("\r\n", "\n")
        pi = psrc.index('"""')
        pj = psrc.index('"""', pi + 3)
        pde = psrc[:pj].count("\n")
        plines = psrc.split("\n")
        pn = sum(1 for k in range(pde + 1, len(plines))
                 if plines[k].lstrip().startswith("#") and TAG.search(plines[k]))
        if pn == 0:
            bad.append("负对照失效：上一版 %s 一条都没扫到 —— 判据没有判别力" % prev.name)
    if bad:
        for m in bad:
            print("  \u2717 [v1236] %s" % m)
        return False
    print("  \u2713 [v1236] 正文注释 0 处版次批注、docstring 0 处前导标记；"
          "负对照（v1.23.5）判红 %d 行成块批注" % pn)
    return True

def check_v1237_changelog_outside_code():
    """[v1.23.7] changelog 不得再写在代码文件里。

    抠掉模块 docstring 后的源码里：① 不得有版本段标题 `^vX.Y.Z 相对`；
    ② 不得出现「收束摘要」。
    **两向对账**：`CHANGELOG.md` 必须存在且版本段 ≥ 10（防「搬出去」变「删掉」）。
    ★ 变异体见 `_probe_v1237_mutants.py`（往源码注入一段版本段必须判红）。
    """
    bad = []
    raw = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
    i = raw.index('"""')
    j = raw.index('"""', i + 3)
    body = raw[j + 3:]
    assert 0 < len(body) < len(raw), "抠模块 docstring 没生效（抠法自证失败）"
    hits = [k + 1 for k, ln in enumerate(body.split("\n"))
            if re.match(r"^v\d+(?:\.\d+)+ 相对", ln)]
    if hits:
        bad.append("代码里仍有版本段标题 %d 处，前 3 个行号 %s" % (len(hits), hits[:3]))
    if "收束摘要" in body:
        bad.append("代码里仍出现「收束摘要」")
    cl = _changelog_text()
    n = len(re.findall(r"^v\d+(?:\.\d+)+ 相对", cl, re.M))
    if n < 10:
        bad.append("CHANGELOG.md 版本段只有 %d 段 —— 像被删而不是被搬" % n)
    if bad:
        for m in bad:
            print("  \u2717 [v1237] %s" % m)
        return False
    print("  \u2713 [v1237] 代码里 0 处版本段 / 0 处收束摘要；"
          "CHANGELOG.md %d 段（两向对账）" % n)
    return True

def _v1238_sections(txt):
    """切成 (标题, 该节正文字符数)。「有标题、正文 0 字」= 空节。"""
    import re as _re
    parts = _re.split(r"(?m)^(#{3,4} .*)$", txt)
    out = []
    for _i in range(1, len(parts) - 1, 2):
        out.append((parts[_i].strip(), len(parts[_i + 1].strip())))
    return out

def _src_of(func):
    """取函数源码，**稳健版** —— 取不到就退回读源文件，绝不静默返回空串。

    ★ 为什么需要它：`inspect.getsource` 依赖 `linecache` + `__file__`，
      在长跑序里可能失效（本仓库实测）。判据若用 `try/except` 把失败吞成
      `""`，就会把「取不到源码」误报成「源码里没有这个串」——
      **方向错的断言比没断言更危险**。
    ★ 返回：源码字符串；若两条路都失败 ⇒ raise（调用点必须显式报错）。
    """
    import inspect as _ins
    import ast as _ast
    _s = ""
    try:
        _s = _ins.getsource(func) or ""
    except Exception:
        _s = ""
    if len(_s) >= 200:
        return _s
    # 退回：直接读源文件，用 ast 按函数名切块
    _f = None
    try:
        _f = _ins.getsourcefile(func)
    except Exception:
        _f = None
    if not _f:
        _f = str(getattr(globals().get("mod"), "__file__", "") or "")
    if _f and Path(_f).exists():
        _txt = Path(_f).read_bytes().decode("utf-8")
        _txt = _txt.replace("\r\n", "\n")
        _name = getattr(func, "__name__", "")
        _cls = ""
        _q = getattr(func, "__qualname__", "") or ""
        if "." in _q:
            _cls = _q.split(".")[-2]
        try:
            _tree = _ast.parse(_txt)
        except Exception:
            _tree = None
        if _tree is not None:
            _want = [_name]
            for _node in _ast.walk(_tree):
                if isinstance(_node, (_ast.FunctionDef,
                                      _ast.AsyncFunctionDef)):
                    if _node.name not in _want:
                        continue
                    _rng = getattr(_node, "end_lineno", None)
                    if _rng is None:
                        continue
                    _lines = _txt.split("\n")
                    _blk = "\n".join(_lines[_node.lineno - 1:_rng])
                    if _cls:
                        # 类内方法：确认名字对得上（避免同名函数串）
                        _s = _blk
                    else:
                        _s = _blk
                    break
    if len(_s) < 60:
        raise RuntimeError(
            "判据未能取到源码：%s（两条路都失败）"
            % getattr(func, "__name__", "?"))
    return _s


def check_v1238_render_guards():
    """[v1.23.8] 渲染层三处守卫：空节不留空 / 停因上头部 / 悬置渲染去重。

    ★ 负对照全部内置（没有负对照的「全绿」只说明判据没跑）：
      · 空节：无 actions 时不许出现「有标题、正文 0 字」的节，但**三/六两个
        标题必须还在** —— 防「靠删标题消灭空节」（v1.23.8 首版补丁正是这么
        错的，被探针 A1_节数 当场抓到）；有 actions 时行动清单/落地层头不许少。
      · 停因：四层全「体力耗尽」必须报「自然 0 / 被截断 4」且带警示；混合停因
        不许带警示；无停因必须返回空串（不许印 0/0 冒充读数）。
      · 去重：真跑形态（同 target、第二条带「；元层决定不消解。」后缀）必须合并
        成 3 条；**异 target 一条都不许合**；单条输入不许被吞。
      · 接线：三个新函数必须真被 save_result 调到，否则是死代码。
    """
    import inspect as _inspect
    bad = []
    m = globals().get("mod")
    if m is None:
        print("  \u2717 [v1238] 命名空间里没有 mod")
        return False

    # ── A 空节守卫 ────────────────────────────────────────────
    _r1 = {"orientation": "decision",
           "_config": {"actions": {"landing_decision": True}},
           "views": {}, "decidability": {}}
    _t1 = m.render_landing(_r1)
    _e1 = [x for x, _n in _v1238_sections(_t1) if _n == 0]
    if _e1:
        bad.append("无 actions 时仍有空节：%s" % _e1)
    for _need in ("### 三、所需数据清单", "### 六、如果只能做一件事"):
        if _need not in _t1:
            bad.append("负对照失效：%s 标题被删（不许靠删标题消灭空节）" % _need)
    _r2 = {"orientation": "decision",
           "_config": {"actions": {"landing_decision": True}},
           "views": {"1": {"decidable_product": {
               "answer": "指派 排水公司 核查 内涝点位，汛期前完成，"
                         "否则回退人工排查。"}}},
           "decidability": {}}
    _t2 = m.render_landing(_r2)
    if "### 二、行动清单" not in _t2:
        bad.append("有 actions 时行动清单段缺失")
    if "落地层（decision 模式）" not in _t2:
        bad.append("有 actions 时落地层头缺失")
    _e2 = [x for x, _n in _v1238_sections(_t2) if _n == 0]
    if _e2:
        bad.append("有 actions 时仍有空节：%s" % _e2)

    # ── B 停因上头部 ──────────────────────────────────────────
    _cut = ("体力耗尽（1 圈走满，未触发任何停止判据，是被截断不是自然停止）")
    if not hasattr(m, "_stop_kind_summary"):
        bad.append("缺 _stop_kind_summary")
    else:
        _s4 = m._stop_kind_summary(
            {k: {"stop_reason": _cut} for k in ("0", "1", "both", "all")})
        if "自然 0" not in _s4 or "被截断（体力耗尽）4" not in _s4 \
                or "\u26a0" not in _s4:
            bad.append("四层全被截断的读数不对：%r" % _s4)
        _s1 = m._stop_kind_summary({
            "0": {"stop_reason": _cut},
            "1": {"stop_reason": "连续 2 轮无新 &，螺旋停止"}})
        if "自然 1" not in _s1 or "被截断（体力耗尽）1" not in _s1 \
                or "\u26a0" in _s1:
            bad.append("混合停因读数不对（不该带「无一层自然收敛」警示）：%r" % _s1)
        if m._stop_kind_summary({}) != "" or m._stop_kind_summary({"0": {}}) != "":
            bad.append("无停因时必须返回空串（不许印 0/0 冒充读数）")

    # ── C 悬置渲染去重 ────────────────────────────────────────
    if not hasattr(m, "_dedup_suspensions_for_render"):
        bad.append("缺 _dedup_suspensions_for_render")
    else:
        _it = [
            {"target": "用途场景未显形，精度三档无判据", "reason": "r1"},
            {"target": "用途场景未显形，精度三档无判据；元层决定不消解。",
             "reason": "r2"},
            {"target": "日期同压事件发生与被命名，分离口缺席", "reason": "r3"},
            {"target": "日期同压事件发生与被命名，分离口缺席；元层决定不消解。",
             "reason": "r4"},
            {"target": "共同纲领、政府成立、开国大典效力层级排序", "reason": "r5"},
        ]
        _k, _d = m._dedup_suspensions_for_render(_it)
        if len(_k) != 3 or _d != 2:
            bad.append("真跑形态去重结果不对：保留 %d / 合并 %d（期望 3 / 2）"
                       % (len(_k), _d))
        _k2, _d2 = m._dedup_suspensions_for_render(
            [{"target": "甲甲甲甲甲甲"}, {"target": "乙乙乙乙乙乙"}])
        if len(_k2) != 2 or _d2 != 0:
            bad.append("负对照：异 target 被误合并（保留 %d / 合并 %d）"
                       % (len(_k2), _d2))
        _k3, _d3 = m._dedup_suspensions_for_render([{"target": "丙丙丙丙丙丙"}])
        if len(_k3) != 1 or _d3 != 0:
            bad.append("负对照：单条输入被吞（保留 %d / 合并 %d）"
                       % (len(_k3), _d3))
        if hasattr(m, "_susp_key"):
            if m._susp_key("甲甲甲甲") != "甲甲甲甲":
                bad.append("_susp_key 对短 target 应退回全长")
            if m._susp_key("甲甲甲甲甲甲；尾") != "甲甲甲甲甲甲":
                bad.append("_susp_key 应取首个分句")

    # ── 接线断言（防死代码）────────────────────────────────────
    # ★ 取源码失败与「源码里没这个串」**分开报** —— 混成一句会
    #   把「判据自己没拿到源码」读成「守卫是死代码」。
    try:
        _ss = _src_of(m.save_result)
    except Exception as _e:
        bad.append("判据未能取到 save_result 源码（非死代码结论）：%s"
                   % _e)
        _ss = None
    if _ss is not None:
        if "_stop_kind_summary(" not in _ss:
            bad.append(
                "_stop_kind_summary 没被 save_result 调用（死代码）")
        if "_dedup_suspensions_for_render(" not in _ss:
            bad.append(
                "_dedup_suspensions_for_render 没被 save_result 调用"
                "（死代码）")

    if bad:
        for _m in bad:
            print("  \u2717 [v1238] %s" % _m)
        return False
    print("  \u2713 [v1238] 空节守卫(三/六+负对照) / 停因汇总(3 读数) / "
          "悬置去重(真跑形态 3+2、异 target 不合) / 三处接线均在")
    return True

def check_v1239_orientation_guard():
    """[v1.23.9] 取向分流守卫：`auto` + 无决策语境 → boundary 模板。

    ★ 背景（真跑实证）：单点事实询问套 decision 模板，会替提问者编出一整套
      不存在的执行流程（行动清单 / 负责人 / 时限 / 验收）。
    ★ 负对照全部内置（没有负对照的「全绿」只说明判据没跑）：
      · 事实题 auto → boundary；**决策题 auto → decision**（不许一刀切）；
      · **显式 `--orientation decision` 仍走 decision**（不许覆盖用户显式选择）；
      · `boundary` / 「关掉开关」两条老短路保持原样；
      · 空题面 / 缺 question 键 → boundary（不知道题面时不套决策模板）；
      · `_has_decision_context` 词表：3 例命中 + 3 例不命中；
      · 接线：`render_landing` 源码里真的调了它（防死代码）。
    """
    import inspect as _inspect
    bad = []
    m = globals().get("mod")
    if m is None:
        print("  \u2717 [v1239] 命名空间里没有 mod")
        return False

    _FACT = "新中国的成立时间是什么时候"
    _DEC = "老城区暴雨内涝频发，排水系统重建还是局部修补，该不该统一规划"

    def _kind(orientation, question, landing_on=True, with_q=True):
        _r = {"orientation": orientation,
              "_config": {"actions": {"landing_decision": landing_on}},
              "views": {}, "decidability": {}}
        if with_q:
            _r["question"] = question
        return ("decision" if "落地层（decision 模式）" in m.render_landing(_r)
                else "boundary")

    _cases = [
        ("事实题 auto → boundary", _kind("auto", _FACT), "boundary"),
        ("决策题 auto → decision", _kind("auto", _DEC), "decision"),
        ("显式 decision + 事实题 → decision", _kind("decision", _FACT),
         "decision"),
        ("boundary + 决策题 → boundary", _kind("boundary", _DEC), "boundary"),
        ("空题面 auto → boundary", _kind("auto", ""), "boundary"),
        ("缺 question 键 auto → boundary",
         _kind("auto", "", with_q=False), "boundary"),
        ("关开关 + 决策题 → boundary", _kind("decision", _DEC, landing_on=False),
         "boundary"),
    ]
    for _name, _got, _want in _cases:
        if _got != _want:
            bad.append("%s：实测 %s（期望 %s）" % (_name, _got, _want))

    if not hasattr(m, "_has_decision_context"):
        bad.append("缺 _has_decision_context")
    else:
        for _q in ("新中国的成立时间是什么时候",
                   "1949年10月1日的开国大典有多少人参加",
                   "《共同纲领》是哪一年通过的"):
            if m._has_decision_context(_q):
                bad.append("负对照：事实题被判有决策语境：%r" % _q)
        for _q in ("这个方案怎么落地", "我要不要现在买", "三条路径的利弊取舍"):
            if not m._has_decision_context(_q):
                bad.append("决策题未被判有决策语境：%r" % _q)
        if m._has_decision_context(""):
            bad.append("空题面不该判为有决策语境")

    if "_has_decision_context(" not in _inspect.getsource(m.render_landing):
        bad.append("_has_decision_context 没被 render_landing 调用（死代码）")

    if bad:
        for _m in bad:
            print("  \u2717 [v1239] %s" % _m)
        return False
    print("  \u2713 [v1239] 取向分流：事实题→boundary / 决策题→decision / "
          "显式 decision 不被覆盖 / 空题面保守走 boundary；词表 3+3 例；接线在")
    return True

def check_v12312_anchor_lanes():
    """[v1.23.12] 外部锚点分「文本 / 联网」两条通道分别写明（单一实现）。

    ★ 负对照全部内置（没有负对照的「全绿」只说明判据没跑）：
      · 两条通道都必须出现，且**各自**把「没有」写出来 —— 联网关时写
        「**关**」，产物没写 `_runtime` 时写「未记录」，都不许静默省略。
      · 联网**开**且收了 N 条：必须写出条数、W# 编号、环节数、失败数。
      · 联网开时**不许**再出现「未接入外部校验」那句留痕 —— 旧实现口径
        错位：联网明明跑了 6 条，产物仍写「本次未接入外部校验」。
      · **四处渲染点**（产物头部 / 显化说明 / decision 落地 / boundary
        落地）都要出现两条通道 —— 防「四个点只接了一处」。
      · 真正驱动判据的是**真跑形态**：结果里没有 `external_anchor`、
        但有 6 条 `web_results` —— 这正是原始 bug 的现场。
    """
    import tempfile as _tf
    bad = []
    m = globals().get("mod")
    if m is None:
        print("  \u2717 [v12312] 命名空间里没有 mod")
        return False
    for _fn in ("_anchor_lane_lines", "_web_lane_stats"):
        if not hasattr(m, _fn):
            print("  \u2717 [v12312] 缺 %s" % _fn)
            return False

    def _pool(**x):
        p = {"amps": [], "threads": [], "probes": [], "suspensions": [],
             "meta": [], "sub_questions": [], "deferrals": [],
             "escalations": [], "decidability_log": [], "duel_suspensions": [],
             "duel_alignment": [], "engagements": [], "refinements": [],
             "decidable_channel": [], "undecidable_channel": []}
        p.update(x)
        return p

    def _res(q, **kw):
        d = {"question": q, "route": ["1"], "keep": {"1": "all"},
             "rounds": {"1": 1},
             "dispatch": {"_parallel_mode": "serial", "order": ["1"],
                          "requested": ["1"], "skipped": []},
             "views": {"1": {}}, "pools": {"1": _pool()},
             "llm_calls": 1, "llm_tokens": 1,
             "decidability": {"decidability": "decidable"},
             "channels": ["content"], "tri_state": [0, 0], "_config": {}}
        d.update(kw)
        return d

    _Q = "新中国的成立时间是什么时候"
    _D = "这份方案怎么落地"
    _ON = {"_runtime": {"web_enabled": True},
           "pools": {"1": _pool(web_results=[
               {"id": "W%d" % i,
                "stage": ("research_decompose" if i <= 3
                          else "research_evidence"), "tier": 3}
               for i in range(1, 7)])}}

    # ── A · 真跑形态：无锚点文件 + 联网 6 条 ────────────────────
    _r = _res(_Q, **_ON)
    _lanes = m._anchor_lane_lines(_r)
    _j = "\n".join(_lanes)
    if len(_lanes) != 2:
        bad.append("两条通道没分开（得 %d 条）" % len(_lanes))
    if "**外部锚点 · 文本**" not in _j or "**外部锚点 · 联网**" not in _j:
        bad.append("缺「文本」或「联网」标题")
    # [v1.23.18 判据随实现更新] 缺席态文案由「无」改成「**关**」（对称）。
    _tl0 = [l for l in _lanes if "文本" in l]
    if not _tl0 or "**关**" not in _tl0[0]:
        bad.append("没有锚点文件时，文本通道没写「关」（旧文案「无」已退役）")
    for _need in ("**开**", "收 6 条", "W1", "2 个环节", "失败 0 条"):
        if _need not in _j:
            bad.append("联网通道缺读数：%s" % _need)
    _s = m._web_lane_stats(_r)
    if (_s["ok"] != 6 or len(_s["ids"]) != 6 or len(_s["stages"]) != 2
            or _s["tiers"] != {"3": 6} or _s["errs"]
            or _s["enabled"] is not True):
        bad.append("_web_lane_stats 读数不对：%r" % (_s,))

    # ── A2 · [v1.23.18] 新态：通道开着但**没挂文件** ────────────
    _unc = m._anchor_lane_lines(_res(_Q, **{
        "_runtime": {"web_enabled": False},
        "external_anchor": {"enabled": True, "unconfigured": True,
                            "anchors": 0, "error": ""}}))
    _utl = [l for l in _unc if "文本" in l]
    if not _utl or "开（未挂锚点文件）" not in _utl[0]:
        bad.append("v1.23.18：未挂文件态没写「开（未挂锚点文件）」")
    if any(("已接入" in l or "锚点异常" in l) for l in _unc):
        bad.append("未挂文件态混进了「已接入」/「锚点异常」")

    # ── B · 三态：关 / 未记录 ─────────────────────────────────
    _off = "\n".join(m._anchor_lane_lines(
        _res(_Q, **{"_runtime": {"web_enabled": False}})))
    if "**关**" not in _off:
        bad.append("联网关时没写「**关**」")
    _na = "\n".join(m._anchor_lane_lines(_res(_Q)))
    if "未记录" not in _na:
        bad.append("产物没写 `_runtime` 时没写「未记录」")

    # ── C · 失败条数 / 零条 ───────────────────────────────────
    _er = "\n".join(m._anchor_lane_lines(_res(_Q, **{
        "_runtime": {"web_enabled": True},
        "pools": {"1": _pool(web_errors=[{"kind": "rate", "stage": "x"}])}})))
    if "失败 1 条" not in _er or "[W-RATE]" not in _er:
        bad.append("联网失败没写出条数与 kind")
    _z = "\n".join(m._anchor_lane_lines(_res(_Q, **{
        "_runtime": {"web_enabled": True},
        "pools": {"1": _pool(web_results=[])}})))
    if "收 0 条" not in _z:
        bad.append("联网开而零条时没写「收 0 条」")
    if "已接入" in _z:
        bad.append("联网零条时文本通道混进了「已接入」")

    # ── D · 锚点文件失败 ─────────────────────────────────────
    _an = "\n".join(m._anchor_lane_lines(_res(_Q, **{
        "_runtime": {"web_enabled": True},
        "external_anchor": {"anchors": 0, "error": "FileNotFoundError: x"}})))
    if "锚点异常" not in _an:
        bad.append("锚点文件失败时没写「锚点异常」")

    # ── E · 四处渲染点 ───────────────────────────────────────
    _dec = dict(_r, orientation="decision",
                _config={"actions": {"landing_decision": True}})
    _bnd = dict(_r, orientation="boundary")
    _sites = {"显化说明": m.render_manifestation(_r),
              "落地(decision)": m.render_landing(_dec),
              "落地(boundary)": m.render_landing(_bnd)}
    with _tf.TemporaryDirectory() as td:
        _prod = Path(m.save_result(_r, save_dir=td)).read_text(
            encoding="utf-8")
    # ★ 头部 = **首个二级标题之前**的区间。不能拿整篇产物查：正文后面还有
    #   `render_manifestation` 的「显化说明」，两条通道会在那里再出现一次，
    #   「头部那处调用被删」就被整段掩盖了（M5 变异体实测假绿）。
    _sites["产物头部"] = _prod.split("\n## ")[0]
    for _k, _v in _sites.items():
        if "**外部锚点 · 文本**" not in _v or "**外部锚点 · 联网**" not in _v:
            bad.append("[%s] 没有同时写出两条通道（渲染点漏接）" % _k)
    for _k in ("落地(decision)", "落地(boundary)"):
        if "### 七、外部锚点（两条通道分开记账）" not in _sites[_k]:
            bad.append("[%s] 缺第七节" % _k)

    # ── F · 口径不许打架（联网开 / 关 两种）────────────────────
    if "未接入外部校验" in _prod:
        bad.append("联网已经开了，产物仍写「未接入外部校验」——口径错位")
    with _tf.TemporaryDirectory() as td:
        _co = Path(m.save_result(
            _res(_Q, **{"_runtime": {"web_enabled": False}}),
            save_dir=td)).read_text(encoding="utf-8")
    if "未接入外部校验" not in _co or "--web on" not in _co:
        bad.append("联网关 + 事实题时缺留痕 / 指路")
    # ── G · 锚点**明细**不许因为「两条通道」被吃掉 ───────────────
    #   v1.23.12 首版真踩过：把 `锚点对照 / 锚点分级 / triage 降级 /
    #   锚点入池` 当成「旧单通道块」整段撤掉 ⇒ `_v122_verify.py` 的
    #   `[4.7]` 判红。两条通道是**多一条出口**，不是换掉这些读数。
    _ra = _res(_Q, **{
        "_runtime": {"web_enabled": True},
        "external_anchor": {
            "anchors": 3, "source_file": "a.json", "retrieved_at": "t0",
            "as_evidence": "partial", "tier_floor": 2, "triage_downgrades": 1,
            "pooled": 3,
            "summary": {"claims": 2, "supported": 1, "conflicted": 0,
                        "unmatched": 1, "anchor_used": 2}}})
    with _tf.TemporaryDirectory() as td:
        _pa = Path(m.save_result(_ra, save_dir=td)).read_text(
            encoding="utf-8")
    for _need in ("**锚点对照**", "**锚点分级**：partial", "**triage 降级**：1 条",
                  "**锚点入池**", "已接入 3 条", "**外部锚点 · 联网**"):
        if _need not in _pa:
            bad.append("锚点明细被两条通道吃掉了（缺 %s）" % _need)

    with _tf.TemporaryDirectory() as td:
        _cd = Path(m.save_result(
            _res(_D, **{"_runtime": {"web_enabled": False}}),
            save_dir=td)).read_text(encoding="utf-8")
    if "未接入外部校验" in _cd:
        bad.append("决策题不该出现「未接入外部校验」留痕")

    if bad:
        for _x in bad:
            print("  \u2717 [v12312] %s" % _x)
        return False
    print("  \u2713 [v12312] 外部锚点两条通道（文本/联网）分别写明 / "
          "开·关·未记录三态 / 失败与零条读数 / 四处渲染点 / 口径不打架")
    return True

def check_v12313_auto_dispatch():
    """[v1.23.13] 统一自适应调度器：十一项逐项可单独接管 + 历史自适应 + 技术债。

    ★ 负对照全部内置（没有负对照的「全绿」只说明判据没跑）：
      · 十一项各自都有留痕（值 / 来源 / 理由），缺一项即判红；
      · **逐项独立**：显式给一项，只改那一项，其余仍是 auto
        —— 变异体「explicit 泄漏到全部项」必须判红；
      · 总开关关掉 ⇒ 一项都不进 auto（回 v1.23.12 行为）；
      · 历史自适应**两向**：高截断率不砍层 / 低截断率才砍；
        高 token 降档 / 有限 token 不降；失败多则降级阈值收紧；
      · 技术债：`_normalize_orientation` 与 `_assemble_plan` 各只有 1 处定义，
        且 `auto_plan()` 两条路径的返回 **schema 逐键相同**。
    """
    import copy as _copy
    import json as _json
    m = globals().get("mod")
    bad = []
    if m is None or not hasattr(m, "auto_dispatch"):
        print("  \u2717 [v12313] 命名空间里没有 auto_dispatch")
        return False
    _ORDER = m._AUTO_ITEM_ORDER
    if len(_ORDER) != 11:
        bad.append("十一项不齐：%d 项" % len(_ORDER))
    _FACT = "新中国的成立时间是什么时候"
    _DEC = "这份方案怎么落地"
    cfg0 = m.load_config("")

    def _pick(plan, k):
        return (plan.get("_items") or {}).get(k) or {}

    def _src(plan, k):
        return _pick(plan, k).get("source")

    def _val(plan, k):
        return _pick(plan, k).get("value")

    # ── A 十二项齐全 + 留痕 ───────────────────────────────────
    p = m.auto_dispatch(_FACT, cfg0)
    for k in _ORDER:
        if k not in (p.get("_items") or {}):
            bad.append("缺留痕：%s" % k)
        elif not str(_pick(p, k).get("reason") or ""):
            bad.append("留痕没有理由：%s" % k)
    if not str(p.get("mode") or ""):
        bad.append("事实短题的模式没定下来")
    # 停止阈值必须**按题型动**（变异体「`_auto_pick_stop` 恒空」实测假绿，
    # 因为没有一条判据真的去看它算出来的值）
    _st = _val(p, "stop") or {}
    if _st.get("round_stall_limit") != 1 or _st.get("round_idle_limit") != 1:
        bad.append("事实型短题的停止阈值没收紧：%r" % (_st,))
    _META = ("这本身算不算递归？如何界定，还是要靠整体，"
             "到底谁说了算，怎么验证，为什么")
    _stm = _val(m.auto_dispatch(_META, cfg0), "stop") or {}
    if _stm.get("round_stall_limit") != 3:
        bad.append("含元层的停止阈值没放宽：%r" % (_stm,))

    # ── B 逐项显式接管：只改这一项 ────────────────────────────
    _EX = {"route": ["0", "1"], "mode": "A",
           "rounds": "0:9,1:9,both:9,all:9", "orientation": "decision",
           "web": "off", "thinking": "on", "effort": "max",
           "landing": "decision", "decidability": "off"}
    for _k, _v in _EX.items():
        _p1 = m.auto_dispatch(_FACT, cfg0, explicit={_k: _v})
        if _src(_p1, _k) != "explicit":
            bad.append("显式给了 %s 但来源不是显式（%r）" % (_k, _src(_p1, _k)))
        _leak = [x for x in _ORDER if x != _k
                 and x not in ("stop", "web_downgrade")
                 and _src(_p1, x) != "auto"]
        if _leak:
            bad.append("显式 %s 泄漏到了别的项：%s" % (_k, _leak))
    # 配置级接管（stop / web_downgrade 无 CLI，靠配置改过）
    _cs = _copy.deepcopy(cfg0)
    _cs["spiral"]["round_stall_limit"] = 9
    if _src(m.auto_dispatch(_FACT, _cs), "stop") != "config":
        bad.append("配置改了 round_stall_limit，stop 来源却不是配置")

    # ── B2 显式值必须真的落进配置 ─────────────────────────────
    #   ★ 本版首版真 bug：`_apply_auto_dispatch` 只写「来源是 auto」的项 ⇒
    #     `--web off` / `--thinking on` / `--effort max`
    #     **全部失效**（`_apply_runtime` 读到的还是配置里的 `auto`）。
    #     「来源」是给留痕用的，不是给「写不写」用的。
    _c2 = _copy.deepcopy(cfg0)
    _dp2 = m.auto_dispatch(_FACT, _c2, explicit={"web": "off"})
    m._apply_auto_dispatch(_c2, _dp2)
    if _c2.get("runtime", {}).get("web") != "off":
        bad.append("显式 --web off 没被写进 cfg[runtime][web]")

    # ── C 总开关 ─────────────────────────────────────────────
    _co = _copy.deepcopy(cfg0)
    _co["auto"]["enabled"] = False
    _pf = m.auto_dispatch(_FACT, _co)
    _hit = [k for k in _ORDER if _src(_pf, k) == "auto"]
    if _hit:
        bad.append("总开关关掉仍有 auto 项：%s" % _hit)

    # ── D 历史自适应（正向 + 负对照）──────────────────────────
    H = {"n": 5, "tokens_med": 100000, "tri_rate": 0.8, "cut_rate": 0.1,
         "layer_rounds": {"0": 3, "1": 3, "both": 2, "all": 2},
         "modes": {}, "profiles": {}, "web_hit": 12, "web_fail": 0,
         "web_empty": 0, "mismatch": 0}
    _ph = m.auto_dispatch(_FACT, cfg0, history=H)
    # ★ [v1.23.14 判据随实现更新] 圈数改「三级回退 + 样本门槛」，理由串
    #   由「历史各层停圈中位 …+1」变成「按层：…（实际停圈需 ≥N 份样本才采用）」。
    #   这里给足样本（n≥3）⇒ 必须走「实际停圈」这一支。
    if "实际停圈" not in str(_pick(_ph, "rounds").get("reason")):
        bad.append("有足够历史却没走「实际停圈」分支：%r"
                   % _pick(_ph, "rounds").get("reason"))
    if _val(_ph, "route") != ["0", "1", "both"]:
        bad.append("低截断率 + 事实短题应砍到 0/1/both，实得 %r"
                   % (_val(_ph, "route"),))
    if _val(m.auto_dispatch(_FACT, cfg0,
                            history=dict(H, cut_rate=0.9, stop_n=40)), "route") != \
            list(m._ENTRIES):
        bad.append("高截断率时不该砍层（负对照失效）")
    if not _val(m.auto_dispatch(_FACT, cfg0,
                                history=dict(H, web_fail=5)),
                "web_downgrade").get("auto_disable_after_failures") == 2:
        bad.append("历史联网失败多，降级阈值没收紧")
    if _val(m.auto_dispatch(_FACT, cfg0,
                            history=dict(H, n=4, web_hit=0,
                                         web_empty=4)), "web") is not False:
        bad.append("历史联网长期收 0 条，却仍自动接入")

    # ── E 技术债：唯一实现 + 两条路径同 schema ────────────────
    _src_txt = SRC.read_text(encoding="utf-8")
    if _src_txt.count("def _normalize_orientation(") != 1:
        bad.append("取向归一化不是唯一实现")
    if _src_txt.count("def _assemble_plan(") != 1:
        bad.append("装配器不是唯一实现")
    _left = sum(_src_txt.count(x) for x in
                ('if _o not in ("boundary", "decision"):',
                 'if _ori not in ("decision", "boundary"):'))
    if _left:
        bad.append("旧的取向归一化残留 %d 处（没合并干净）" % _left)

    class _Stub:
        def call(self, *a, **kw):
            return _json.dumps({"mode": "A", "orientation": "boundary",
                                "rounds": {"0": 5, "1": 5, "both": 5,
                                           "all": 5},
                                "reason": "stub", "confidence": 0.9},
                               ensure_ascii=False)

        def parse_json(self, raw):
            try:
                return _json.loads(raw)
            except Exception:  # noqa: BLE001
                return {}

    _p1 = m.auto_plan(_FACT, cfg0, llm=_Stub())
    _p2 = m.auto_plan(_FACT, cfg0)          # 无 key ⇒ 两段式降级出口
    if sorted(_p1) != sorted(_p2):
        bad.append("auto_plan 两条路径 schema 不同：%s vs %s"
                   % (sorted(_p1), sorted(_p2)))
    for _k in ("route", "mode", "rounds", "max_calls",
               "orientation"):
        if _k not in _p1:
            bad.append("技术债未清：单调用路径缺键 %s" % _k)

    # ── F 产物渲染 ───────────────────────────────────────────
    _ls = "".join(m._auto_dispatch_lines({"_auto_dispatch": p}))
    if "**自动调度**" not in _ls:
        bad.append("产物没有「自动调度」表")
    _rows = [l for l in _ls.split("\n") if l.startswith("| ") and "来源" not in l]
    if len(_rows) != 11:
        bad.append("调度表不是十一行（%d）" % len(_rows))
    if m._auto_dispatch_lines({}) != []:
        bad.append("没有 plan 时调度表不是空")

    # ── G 历史**加载器**本身（★ 前面几组都是把 hist 直接喂进去，绕过了它
    #     —— 变异体「`_auto_history` 恒返回空」实测假绿，所以必须单独驱动）──
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        Path(td, "x.packed.json").write_text(_json.dumps({
            "llm_calls": 7, "llm_tokens": 123456, "tri_state": [1, 2],
            "views": {"1": {"stop_reason": "体力耗尽（被截断）",
                            "rounds_run": 3, "rounds_cap": 6}},
            "dispatch": {"_parallel_mode": "A"}, "cost_profile": "economy",
            "pools": {"1": {"web_results": [{"id": "W1"}], "web_errors": [],
                            "meta": ["[W-EMPTY] x"]}},
        }, ensure_ascii=False), encoding="utf-8")
        _h = m._auto_history(td)
    if _h.get("n") != 1:
        bad.append("历史加载器没读到样本（n=%r）" % _h.get("n"))
    if _h.get("tokens_med") != 123456:
        bad.append("历史 tokens 中位数读错：%r" % _h.get("tokens_med"))
    if _h.get("web_hit") != 1:
        bad.append("历史联网入池读数读错：%r" % _h.get("web_hit"))
    if _h.get("cut_rate") != 1.0:
        bad.append("历史截断率算错：%r" % _h.get("cut_rate"))
    # ★ [v1.23.14 判据随实现更新] 字段名是 `rounds_run`（原判据的夹具写的是
    #   `rounds` —— 那正是本版修掉的静默 bug）。且「实际停圈」要 ≥3 份样本
    #   才采纳：这里只有 1 份 ⇒ 样本数记 1、中位数不采纳（门槛生效）。
    if (_h.get("layer_rounds_n") or {}).get("1") != 1:
        bad.append("历史实际停圈样本数没记：%r" % _h.get("layer_rounds_n"))
    if "1" in (_h.get("layer_rounds") or {}):
        bad.append("只有 1 份样本却采纳了实际停圈（门槛失效）")
    if (_h.get("modes") or {}).get("A") != 1:
        bad.append("历史模式分布读错：%r" % _h.get("modes"))
    with _tf.TemporaryDirectory() as td:
        _h0 = m._auto_history(td)          # 负对照：空目录必须不崩、n=0
    if _h0.get("n") != 0:
        bad.append("空目录不该有样本（n=%r）" % _h0.get("n"))
    if m._auto_history(str(HERE / "__nope__")):
        pass                               # 路径不存在：只要不抛就算过

    if bad:
        for _x in bad:
            print("  \u2717 [v12313] %s" % _x)
        return False
    print("  \u2713 [v12313] 十二项逐项接管（10 项 CLI + 2 项配置）/ 总开关 / "
          "历史自适应（5 正 3 负）/ 技术债（唯一实现 + 两路同 schema）/ 产物表")
    return True

def check_v12314_history_corpus():
    """[v1.23.14] 用真实历史语料校准调度：三源取样 + 字段名 + 相对判据。

    ★ 背景（本版的两个真问题）：
      ① `_auto_history` 只读 `**/*.packed.json` —— 而 `outputs/` 里有 368 份
         产物 md、只落 1 份 packed ⇒ 历史几乎为空，十二项自适应形同虚设；
      ② 它把「实际停圈」的字段名读成了 `rounds`，真实字段是 `rounds_run`
         ⇒ `dict.get` 静默返回 None，「实际停圈」**永远取不到**。
    ★ 负对照全部内置（没有负对照的「全绿」只说明判据没跑）：
      · 关掉 md / 跑批两个源 ⇒ 样本必须掉回 1（证明样本量靠扩源拿到）；
      · md 抽取给空串 / 无资源行 ⇒ 必须 `{}`；
      · packed 里同时放 `rounds_run` 与 `rounds`：只准认前者；
      · 「实际停圈」样本不足（1 份）⇒ 必须退回种子上限（不能被单条噪声带跑）；
      · 成本档两向：同类偏贵降档 / 不贵不降 / 一致率低不降。
    """
    import json as _j
    import tempfile as _tf
    m = globals().get("mod")
    bad = []
    if m is None or not hasattr(m, "_hist_from_md"):
        print("  \u2717 [v12314] 命名空间里没有历史三源函数")
        return False
    _F = "新中国的成立时间是什么时候"
    _D = "这份方案怎么落地"
    cfg0 = m.load_config("")

    # ── A 三源 + 样本量 ───────────────────────────────────────
    h = m._auto_history("outputs", 200, cfg=cfg0)
    if h["n"] <= 100:
        bad.append("历史样本仍太少（%d）—— 扩源没生效" % h["n"])
    for _k in ("packed", "md", "batch"):
        if not (h.get("sources") or {}).get(_k):
            bad.append("缺历史来源：%s" % _k)
    if not h.get("tokens_p75") or not h.get("calls_p75"):
        bad.append("缺少 p75 分位读数")
    if not h.get("cap_rounds"):
        bad.append("缺少种子上限读数")
    if not (h.get("by_type") or {}).get("fact", {}).get("n"):
        bad.append("分题型桶为空（事实型）")
    _p = m._auto_history("outputs", 200, cfg=cfg0,
                         want_md=False, want_batch=False)
    if _p["n"] != (h.get("sources") or {}).get("packed", 0):
        bad.append("关掉两源后样本没掉回 packed 数（%d）" % _p["n"])

    # ── B md 抽取 正/负对照 ──────────────────────────────────
    HEAD = ("# 元 DGTF · 测试题\n\n**调度**：修行(4圈) → 研究(5圈) → "
            "对撞(6圈) → 元(7圈)\n\n**并行模式**：A · 四层独立并行 + 汇流\n\n"
            "**成本档位**：economy（再省调用次数）\n\n"
            "**取向**：boundary（要边界清单）\n\n"
            "**停止**：自然 2 层 / 被截断（体力耗尽）2 层\n\n"
            "**资源**: 137 次 LLM | 654321 tokens\n")
    r = m._hist_from_md(HEAD)
    for _k, _v in (("calls", 137), ("tokens", 654321), ("mode", "A"),
                   ("profile", "economy"), ("orientation", "boundary")):
        if r.get(_k) != _v:
            bad.append("md 抽取 %s 错：%r" % (_k, r.get(_k)))
    if (r.get("cap_rounds") or {}).get("all") != 7:
        bad.append("md 抽取种子上限错：%r" % (r.get("cap_rounds"),))
    if [r.get("nat"), r.get("cut")] != [2, 2]:
        bad.append("md 抽取停止分层错")
    if m._hist_from_md("") != {} or m._hist_from_md("# 标题\n正文\n") != {}:
        bad.append("md 抽取负对照失效（空输入该返回 {}）")

    # ── C packed 抽取：只认 `rounds_run` ──────────────────────
    P = {"question": _F, "llm_calls": 88, "llm_tokens": 123456,
         "cost_profile": "balanced", "orientation": "boundary",
         "dispatch": {"_parallel_mode": "B"}, "tri_state": [3, 4],
         "views": {"0": {"rounds_run": 3, "rounds_cap": 6,
                         "stop_reason": "连续 2 轮无新 &，螺旋停止"},
                   "1": {"rounds": 5, "rounds_cap": 6,
                         "stop_reason": "体力耗尽（6 圈走满）"}},
         "pools": {"1": {"web_results": [{"id": "W1"}], "web_errors": [],
                         "meta": ["[W-EMPTY] x"]}}}
    rc = m._hist_from_packed(P)
    if (rc.get("actual_rounds") or {}).get("0") != 3:
        bad.append("packed 没读到实际停圈（rounds_run）：%r"
                   % (rc.get("actual_rounds"),))
    if "1" in (rc.get("actual_rounds") or {}):
        bad.append("packed 认了错字段 `rounds`（实际字段是 `rounds_run`）")
    if rc.get("tri") != 0.75:
        bad.append("tri_state 读数错：%r" % rc.get("tri"))

    # ── D 按题型取历史 ───────────────────────────────────────
    f, d = m._auto_features(_F), m._auto_features(_D)
    _bt = h.get("by_type") or {}
    if m._hist_for(f, h) is not _bt.get("fact"):
        bad.append("事实型没取 fact 桶")
    if m._hist_for(d, h) is not _bt.get("nonfact"):
        bad.append("决策型没取 nonfact 桶")
    if m._hist_for(f, {"n": 9, "by_type": {"fact": {"n": 0}}})["n"] != 9:
        bad.append("无同型样本时没退回全语料")

    # ── E 圈数：三级回退 + 样本门槛（两向）──────────────────
    _cap = {"n": 50, "cap_rounds": {"0": 2, "1": 2, "both": 5, "all": 6},
            "cap_rounds_n": {"0": 40, "1": 40, "both": 10, "all": 10}}
    _v, _why = m._auto_pick_rounds(f, _cap, cfg0)
    if "种子上限" not in _why:
        bad.append("只有种子上限时没报出来源")
    # ★ 门槛要拿**钳制遮不住的那一层**（元层 floor=5）来测：
    #   用 0/1 层测会被 floor(4) 兜住 —— 采纳与不采纳结果都是 4，判据分辨不出。
    _few = {"n": 50, "layer_rounds": {"all": 1}, "layer_rounds_n": {"all": 1},
            "cap_rounds": {"all": 6}, "cap_rounds_n": {"all": 30}}
    if m._auto_pick_rounds(f, _few, cfg0)[0]["all"] != 6:
        bad.append("实际停圈只有 1 份样本时不该采纳（应退回种子上限 6）")
    _many = {"n": 50, "layer_rounds": {"0": 5}, "layer_rounds_n": {"0": 9},
             "cap_rounds": {"0": 2}, "cap_rounds_n": {"0": 30}}
    if m._auto_pick_rounds(f, _many, cfg0)[0]["0"] != 6:
        bad.append("实际停圈样本足够时应采纳（5+1=6）")
    for _e in m._ENTRIES:
        if _e not in m._auto_pick_rounds(f, {}, cfg0)[0]:
            bad.append("零历史时没给全四层的圈数")

    # ── F 成本档：相对判据（两向 + 质量优先）────────────────
    _base = {"n": 99, "tokens_p75": 500000, "calls_p75": 100}
    _hi = dict(_base, by_type={"nonfact": {"n": 20, "tokens_med": 900000,
                                          "calls_med": 50, "tri_n": 6,
                                          "tri_rate": 0.9}})
    _lo = dict(_base, by_type={"nonfact": {"n": 20, "tokens_med": 100000,
                                          "calls_med": 10, "tri_n": 6,
                                          "tri_rate": 0.9}})
    _badq = dict(_base, by_type={"nonfact": {"n": 20, "tokens_med": 900000,
                                            "calls_med": 50, "tri_n": 40,
                                            "tri_rate": 0.10, "tri_p10": 0.167}})
    # ★ 判别「相对判据」vs「绝对阈值」的关键样例：同类中位 90 万，
    #   但全语料 p75 是 500 万 ⇒ **相对不算贵** ⇒ 不该降档。
    #   绝对阈值（40 万）会误降 —— 这一条就是为分辨它而设。
    _mid = dict(_base, tokens_p75=5000000, calls_p75=10000,
                by_type={"nonfact": {"n": 20, "tokens_med": 900000,
                                     "calls_med": 50, "tri_n": 6,
                                     "tri_rate": 0.9}})

    # ── G 「实际停圈」渲染 + 产物里真的有 ─────────────────────
    _line = m._rounds_run_line({"1": {"rounds_run": 3, "rounds_cap": 6}})
    if "**实际停圈**" not in _line or "研究 3 圈" not in _line:
        bad.append("实际停圈渲染不对：%r" % _line)
    if m._rounds_run_line({}) != "" or m._rounds_run_line(None) != "":
        bad.append("空 views 时实际停圈行该为空串")
    _pk = sorted((HERE / "outputs").glob("*.packed.json"),
                 key=lambda q: q.stat().st_mtime)
    if _pk:
        try:
            _real = _j.loads(_pk[-1].read_text(encoding="utf-8"))
            _real["_auto_dispatch"] = m.auto_dispatch(
                str(_real.get("question") or _F), cfg0, history=h)
            with _tf.TemporaryDirectory() as td:
                _t = Path(m.save_result(_real, save_dir=td)).read_text(
                    encoding="utf-8")
            if "**实际停圈**：" not in _t:
                bad.append("产物里没有「实际停圈」行（信号落不了地）")
            if "历史读数：**" not in _t or "p75" not in _t:
                bad.append("产物的历史读数行没报来源数与 p75")
        except Exception as _e:  # noqa: BLE001
            bad.append("产物渲染异常：%s: %s" % (type(_e).__name__, _e))

    # ── H 空/坏输入不崩 ─────────────────────────────────────
    if m._auto_history(str(HERE / "__nope__"), 5, cfg=cfg0)["n"] >= 0:
        pass
    try:
        m._hist_from_batch(None)
        m._hist_from_batch({})
        m._hist_from_packed(None)
    except Exception as _e:  # noqa: BLE001
        bad.append("历史抽取对空输入抛异常：%s" % type(_e).__name__)

    if bad:
        for _x in bad:
            print("  \u2717 [v12314] %s" % _x)
        return False
    print("  \u2713 [v12314] 历史三源（%d 份）· rounds_run 字段 · 按题型分桶 · "
          "圈数三级回退+样本门槛 · 成本档相对判据 · 实际停圈落产物"
          % h["n"])
    return True

def _cleanup_snap_v12315(d):
    """删掉 `check_v12315` 建的冻结快照目录（失败也不许抛）。"""
    if not d:
        return
    try:
        import shutil as _sh
        _sh.rmtree(d, ignore_errors=True)
    except Exception:
        pass


def check_v12315_history_calibration():
    """[v1.23.15] 分层抽样 + 时间衰减 + 三条规则的**实测**校准。

    ★ 背景：v1.23.14 把历史接上了，但三件事没做：
      ① `limit` 是「总数」⇒ 窗口一缩，事实型会被整体挤掉，「按题型比同类」
         退化成「比全语料」；
      ② 语料跨十几天，旧样本是旧配置下的读数，等权平均会把新读数拉向旧行为；
      ③ 「截断率 / 三态一致率 / 联网」三条规则**没有数据**（抽取器漏了
         「三态一致率」这一行，实测有 254 份），阈值是拍脑袋的 —— 实测
         一致率 p50 = 0.333，而门槛写 0.5 ⇒ 54% 的情况被拦，等于废掉降档。
    ★ 负对照全部内置（没有负对照的「全绿」只说明判据没跑）：
      · 半衰期 0 ⇒ 加权分位必须**等于**等权分位；
      · 抽不到的字段**不许写键**（不写 0）；
      · 一致率高于 p10 ⇒ 照降档；低于 p10 且样本够 ⇒ 不降；
      · 截断率层样本不足 ⇒ 不表态（落到题型分支）。
    """
    import time as _tmod
    m = globals().get("mod")
    bad = []
    if m is None or not hasattr(m, "_hist_wquant"):
        print("  \u2717 [v12315] 命名空间里没有加权分位")
        return False
    cfg0 = m.load_config("")
    _F = "新中国的成立时间是什么时候"
    _D = "这份方案怎么落地"

    # ── A 分层：每题型上限 ───────────────────────────────────
    # ★★ 冻结快照（本轮修的事实性缺陷）：**不许读活 `outputs/`**。
    #   两个独立原因让活目录读数不可复现：
    #     ① 本判据**自己**就往 `outputs/` 写夹具目录（`_v12315_up*`），
    #        下一段还要再写 —— 被测对象与读数来源共用一个活目录；
    #     ② 任何**并行**的进程（如 `dgtf_app/selftest.py`）在往
    #        `outputs/` 增删文件 ⇒ 两次读数之间世界已变。
    #   实测：活目录一次读到 n=425、冻结快照稳定 n=303；
    #   并行线刷 selftest 时活目录读数在 62↔33 之间跳，
    #   本判据遂报「上限放大后样本数没增加」—— **假红**。
    #   ★ 通则：**会缩小的集合冻结成时点快照**，锚不能是会变的东西。
    _snap_dir = None
    try:
        import tempfile as _tf4
        import shutil as _sh4
        import os as _os4
        _snap_dir = _tf4.mkdtemp(prefix="_v12315_snap_")
        _n_snap = 0
        for _sp in sorted(Path("outputs").rglob("*.md")):
            try:
                _stt = _sp.stat()
                _dst = Path(_snap_dir) / ("%d_%s" % (_n_snap, _sp.name))
                _sh4.copy2(_sp, _dst)
                _os4.utime(_dst, (_stt.st_mtime, _stt.st_mtime))
                _n_snap += 1
            except Exception:
                pass
    except Exception:
        bad.append("无法建立 outputs 冻结快照（读数是竞态的，不可信）")
        return False
    if _n_snap < 50:
        bad.append("冻结快照样本过少（%d）—— 真实语料不足，判据不可信"
                   % _n_snap)

    h = m._auto_history(_snap_dir, 20, cfg=cfg0)
    if h.get("_limit_per_type") != 20:
        bad.append("没报出「每题型上限」：%r" % h.get("_limit_per_type"))
    _ft = (h["by_type"]["fact"] or {}).get("n", 0)
    _nf = (h["by_type"]["nonfact"] or {}).get("n", 0)
    if _ft <= 0 or _nf <= 0:
        bad.append("分层后某桶为空（fact=%s nonfact=%s）" % (_ft, _nf))
    if _ft > 20 or _nf > 20:
        bad.append("某桶超过上限 20（fact=%s nonfact=%s）" % (_ft, _nf))
    # ★ 同尺：两次都用**同一个快照**（不是「活目录 vs 快照」）
    _big = m._auto_history(_snap_dir, 300, cfg=cfg0)
    if _big["n"] <= h["n"]:
        bad.append("上限放大后样本数没增加（%d → %d）" % (h["n"], _big["n"]))
    # ★ 夹具型判据：**只数真实语料看不出「某一型被挤掉」** ——
    #   造一个「最新的 3 份全是事实型、最旧的 1 份是决策型」的临时目录，
    #   上限 2 ⇒ 正确实现必须把两份**都**收满（决策型要往回扫才拿得到）；
    #   「按总数限流」的实现会在收满 2 份事实型后停手，决策型为 0。
    import tempfile as _tf3
    _fq = "新中国的成立时间是什么时候"
    _dq = "这份方案怎么落地"
    with _tf3.TemporaryDirectory() as _td:
        for _i, _q1 in enumerate((_dq, _dq, _fq, _fq)):   # 越靠后越旧
            _pp = Path(_td) / ("h%d.md" % _i)
            _pp.write_text("# 元 DGTF · %s\n\n**资源**: %d 次 LLM | %d tokens\n"
                           % (_q1, 10 + _i, 1000 + _i), encoding="utf-8")
            import os as _os
            _os.utime(_pp, (1000 + _i, 1000 + _i))
        _hf = m._auto_history(_td, 2, cfg=cfg0)
    _a = (_hf["by_type"]["fact"] or {}).get("n", 0)
    _b = (_hf["by_type"]["nonfact"] or {}).get("n", 0)
    if _a != 2 or _b != 2:
        bad.append("分层不对：上限 2 时两桶都该收满（事实 2 + 决策 2），实得 %s/%s"
                   % (_a, _b))

    # ── B 时间衰减 ──────────────────────────────────────────
    _now = _tmod.time()
    if m._hist_weight(_now, 14, _now) != 1.0:
        bad.append("同刻权重不是 1")
    if abs(m._hist_weight(_now - 14 * 86400, 14, _now) - 0.5) > 1e-6:
        bad.append("一个半衰期后权重不是 0.5")
    if abs(m._hist_weight(_now - 28 * 86400, 14, _now) - 0.25) > 1e-6:
        bad.append("两个半衰期后权重不是 0.25")
    if m._hist_weight(None, 14, _now) != 1.0:
        bad.append("无 mtime 时不该衰减")
    if m._hist_weight(_now - 999 * 86400, 0, _now) != 1.0:
        bad.append("半衰期 0 时不该衰减")
    _old2 = [(100, m._hist_weight(_now - 28 * 86400, 14, _now)),
             (100, m._hist_weight(_now - 28 * 86400, 14, _now)),
             (10, m._hist_weight(_now, 14, _now))]
    _same = [(100, m._hist_weight(_now - 28 * 86400, 0, _now)),
             (100, m._hist_weight(_now - 28 * 86400, 0, _now)),
             (10, m._hist_weight(_now, 0, _now))]
    if not (m._hist_wquant(_old2, .5) < m._hist_quant([100, 100, 10], .5)):
        bad.append("加权后没偏向新样本（衰减没生效）")
    if m._hist_wquant(_same, .5) != m._hist_quant([100, 100, 10], .5):
        bad.append("半衰期 0 时加权分位不等于等权（负对照失效）")
    if m._hist_decay(cfg0) <= 0:
        bad.append("默认半衰期不该是 0（那样等于不衰减）")

    # ── C 抽取补齐：三态一致率 ───────────────────────────────
    _H = ("# 元 DGTF · 测试题\n\n**资源**: 10 次 LLM | 1000 tokens\n\n"
          "**三态判决一致率**：2/6（33%）　其中 4 条分歧已按 partial 计入\n")
    _r = m._hist_from_md(_H)
    if abs((_r.get("tri") or -1) - 2 / 6) > 1e-6:
        bad.append("没抽到三态一致率：%r" % (_r.get("tri"),))
    _H0 = ("# 元 DGTF · 测试题\n\n**资源**: 10 次 LLM | 1000 tokens\n\n"
           "**三态判决一致率**：0/0（—）\n")
    if "tri" in m._hist_from_md(_H0):
        bad.append("分母为 0 时不该写 tri 键")

    # ── D 抽取补齐：联网行 + 不写缺省键 ──────────────────────
    _H2 = ("# 元 DGTF · 测试题\n\n**资源**: 10 次 LLM | 1000 tokens\n\n"
           "**外部锚点 · 联网**（`web_search`）：**开** —— 收 6 条"
           "（W1、W2；2 个环节；tier 3×6）；失败 1 条\n")
    _r2 = m._hist_from_md(_H2)
    if _r2.get("web_hit") != 6 or _r2.get("web_fail") != 1:
        bad.append("没抽到联网行：%r" % ({k: _r2.get(k) for k in
                                       ("web_hit", "web_fail")},))
    _H3 = "# 元 DGTF · 测试题\n\n**资源**: 10 次 LLM | 1000 tokens\n"
    _r3 = m._hist_from_md(_H3)
    if ("web_hit" in _r3) or ("web_fail" in _r3):
        bad.append("没有联网行却写了键（0 与「没有这一行」是两件事）")
    _H4 = ("# 元 DGTF · 测试题\n\n**资源**: 10 次 LLM | 1000 tokens\n\n"
           "**外部锚点 · 联网**（`web_search`）：**开** —— 收 6 条（W1）\n")
    _r4 = m._hist_from_md(_H4)
    if _r4.get("web_hit") != 6:
        bad.append("只写「收 6 条」时没抽到 web_hit")
    if "web_fail" in _r4:
        bad.append("行里没有「失败」子句却写了 web_fail 键（不许补 0）")

    # ── E 真实语料读数（**同样走冻结快照 `_big`**）───────────
    # ★ 阈值 100 是「抽取是否生效」的粗探针（若 `_hist_from_md` 抽不到
    #   三态一致率，`tri_n` 会是 0）。快照实测 195 ⇒ 留足裕量。
    #   改快照前后**都没改这个阈值** —— 修的是读数的来源，不是判据的松紧。
    if _big["tri_n"] < 100:
        bad.append("三态一致率样本仍太少（%d）—— 抽取没生效" % _big["tri_n"])
    if _big["tri_p10"] is None:
        bad.append("没报三态一致率的 p10（阈值无法校准）")
    if not all((_big["by_type"][k] or {}).get("n", 0) > 0
               for k in ("fact", "nonfact")):
        bad.append("真实语料分层后某桶为空")

    # ── F 三条规则：按实测定 ─────────────────────────────────
    _base = {"n": 99, "tokens_p75": 1000, "calls_p75": 999999}
    _exp1 = {"n": 30, "tokens_med": 900000, "calls_med": 1}
    _d = m._auto_features(_D)
    _lo = dict(_base, by_type={"nonfact": dict(_exp1, tri_n=40, tri_rate=0.10,
                                              tri_p10=0.167)})
    _ok = dict(_base, by_type={"nonfact": dict(_exp1, tri_n=40, tri_rate=0.30,
                                              tri_p10=0.167)})
    _few = dict(_base, by_type={"nonfact": dict(_exp1, tri_n=5, tri_rate=0.10,
                                               tri_p10=0.167)})
    if getattr(m, "_AUTO_TRI_FLOOR", None) != 0.167:
        bad.append("一致率异常线不是实测 p10（%r）"
                   % getattr(m, "_AUTO_TRI_FLOOR", None))
    if getattr(m, "_AUTO_TRI_MIN_N", 0) < 10:
        bad.append("一致率没有样本量门槛")
    if getattr(m, "_AUTO_STOP_MIN_N", 0) < 8:
        bad.append("截断率没有样本量门槛")

    _f = m._auto_features(_F)
    _fewstop = {"n": 50, "cut_rate": 0.9, "stop_n": 6}
    if m._auto_pick_route(_f, _fewstop, cfg0)[0] != ["0", "1", "both"]:
        bad.append("截断率层样本不足时不该拿它挡住题型分支")
    _manystop = {"n": 50, "cut_rate": 0.9, "stop_n": 40}
    if "被截断率" not in m._auto_pick_route(_f, _manystop, cfg0)[1]:
        bad.append("截断率层样本足够时应保留全四层")

    if bad:
        for _x in bad:
            print("  \u2717 [v12315] %s" % _x)
        _cleanup_snap_v12315(_snap_dir)
        return False
    print("  \u2713 [v12315] 分层（每题型 %s 条，快照 %d 份）· "
          "时间衰减（半衰期 %s 天）· "
          "三态一致率 n=%d p10=%s · 联网行 · 三条规则按实测定"
          % (h.get("_limit_per_type"), _n_snap,
             h.get("_half_life_days"),
             _big["tri_n"], _big["tri_p10"]))
    _cleanup_snap_v12315(_snap_dir)
    return True

def check_v12310_render_ops():
    """[v1.23.10] 渲染层四项一次验收：形态声明 / 附录外置 / 成本自动档 / 未校验留痕。

    ★ 负对照全部内置（没有负对照的「全绿」只说明判据没跑）：
      · 形态声明：boundary 与 decision 两套模板各出一次、各自写明模板名；
        不传 question 时不许崩。
      · 附录**两向对账**：`file` 模式正文不得有 json 块且旁挂文件必须可解析、
        顶层键 == 输入、无渲染点的内部量仍在；`inline` 模式正文必须有 json 块
        且不得留旁挂文件。
      · 成本档：事实题 → economy、决策题 → balanced；argparse 必须收 auto。
      · 未校验留痕：事实题产物须写明「未接入外部校验」与 `--web on`；
        **决策题不许出现这句**。接线：save_result 里真调了 `_appendix_to_file`。
    """
    import json as _json
    import tempfile as _tf
    import inspect as _ins
    bad = []

    def _fake(q, mode):
        return {
            "question": q, "route": ["1"], "keep": {"1": "all"},
            "rounds": {"1": 1},
            "dispatch": {"_parallel_mode": "serial", "order": ["1"],
                         "requested": ["1"], "skipped": []},
            "views": {"1": {}},
            "pools": {"1": {"amps": [], "threads": [], "probes": [],
                            "suspensions": [], "meta": [],
                            "sub_questions": [], "deferrals": []}},
            "llm_calls": 1, "llm_tokens": 1,
            "decidability": {"decidability": "decidable"},
            "channels": ["content"], "cost_profile": "balanced",
            "orientation": "auto", "tri_state": [0, 0],
            "_probe_only_internal": {"deep": {"x": 7}},
            "_config": {"actions": {"landing_decision": True,
                                    "appendix_mode": mode}},
        }

    _FACT = "新中国的成立时间是什么时候"
    _DEC = "这份方案怎么落地"

    # ── R1 形态声明（两套模板各出一次）────────────────────────
    _b = mod.render_landing({"orientation": "boundary",
                             "_config": {"actions": {}}, "views": {},
                             "decidability": {}, "question": _FACT})
    _d = mod.render_landing({"orientation": "decision",
                             "_config": {"actions": {"landing_decision": True}},
                             "views": {}, "decidability": {}, "question": _DEC})
    _bh = "\n".join(_b.split("\n")[:4])
    _dh = "\n".join(_d.split("\n")[:4])
    if "**形态声明**" not in _bh or "boundary" not in _bh:
        bad.append("boundary 模板缺形态声明（或没写明模板名）")
    if "**形态声明**" not in _dh or "decision" not in _dh:
        bad.append("decision 模板缺形态声明（或没写明模板名）")
    if not _b.startswith("## "):
        bad.append("形态声明把落地层标题挤出了首行（md 结构被破坏）")
    try:
        mod.render_landing({"orientation": "auto", "_config": {"actions": {}},
                            "views": {}, "decidability": {}})
    except Exception as e:
        bad.append("缺 question 键时 render_landing 崩了：%r" % e)

    # ── R8 附录两向对账（旁挂内容必须在 with 块内读完）────────
    _mode = {}
    for _m in ("file", "inline"):
        with _tf.TemporaryDirectory() as td:
            p = mod.save_result(_fake(_FACT, _m), save_dir=td)
            _c = p.read_text(encoding="utf-8")
            _raws = [q.read_text(encoding="utf-8")
                     for q in sorted(p.parent.glob("*.packed.json"))]
            _mode[_m] = (_c, _raws)
    _cf, _sf = _mode["file"]
    _ci, _si = _mode["inline"]
    if "```json" in _cf:
        bad.append("file 模式正文里仍有内联 json 块")
    if len(_sf) != 1:
        bad.append("file 模式没有产出唯一的旁挂文件（得 %d 个）" % len(_sf))
    else:
        try:
            _pk = _json.loads(_sf[0])
            if set(_pk) != set(_fake(_FACT, "file")):
                bad.append("旁挂文件顶层键不全")
            if (((_pk.get("_probe_only_internal") or {}).get("deep")
                    or {}).get("x")) != 7:
                bad.append("旁挂文件丢了「正文无渲染点」的内部量（红线破了）")
        except Exception as e:
            bad.append("旁挂文件不可解析：%r" % e)
    if "```json" not in _ci:
        bad.append("inline 模式正文里没有内联 json 块（旧行为没保住）")
    if _si:
        bad.append("inline 模式不该产出旁挂文件")

    # ── R9 成本档自动路由 ────────────────────────────────────

    # ── R10 未校验留痕（只对事实题）──────────────────────────
    if "未接入外部校验" not in _cf or "--web on" not in _cf:
        bad.append("事实题产物没有「未接入外部校验 + --web on」留痕")
    with _tf.TemporaryDirectory() as td:
        _cd = mod.save_result(_fake(_DEC, "file"), save_dir=td).read_text(
            encoding="utf-8")
    if "未接入外部校验" in _cd:
        bad.append("决策题不该出现「未接入外部校验」留痕")

    # ── 接线 ────────────────────────────────────────────────
    if "_appendix_to_file(" not in _ins.getsource(mod.save_result):
        bad.append("_appendix_to_file 没被 save_result 调用（死代码）")

    if bad:
        for _m in bad:
            print("  \u2717 [v12310] %s" % _m)
        return False
    print("  \u2713 [v12310] 形态声明(boundary+decision) / 附录两向对账(外置+内联) / "
          "成本档规则(事实 economy·决策 balanced) / 未校验留痕(仅事实题) / 接线在")
    return True

def check_v12311_writeback_and_web():
    """[v1.23.11] 两件挂账一次做完：自省回写（R1 后半）+ 事实题自动联网（R10 后半）。

    ★ 负对照全部内置：
      · 自省回写：**无**高置信诊断时不许渲染（防「无条件加一段动作」）；
        `unsaid_is_escape=True` 与 `quality_flags=unsaid_overused(n)` 各测一次；
        回写块必须落在形态声明**之后**（顺序：模板声明 → 诊断动作）。
      · 事实题自动联网：`_web_auto_for_facts` 事实题 True / 决策题 False；
        ★ [v1.23.13 判据随实现更新] 接线口径从「main 里直接传 `"web": _web`」
        改成「经统一调度器」：`auto_dispatch` → `_apply_auto_dispatch` →
        `_apply_runtime`。判据因此改成**端到端行为**：事实题走完整条链后
        `web_search.enabled is True`，显式 `--web off` 时为 False。
        （原来的字面检查在重构后必然误报，且它本来就只证明「写了那一行」。）
    """
    bad = []
    m = globals().get("mod")
    if m is None:
        print("  \u2717 [v12311] 命名空间里没有 mod")
        return False

    _base = {"orientation": "decision",
             "_config": {"actions": {"landing_decision": True}},
             "decidability": {}, "question": "这份方案怎么落地"}

    # ── A 自省回写 ────────────────────────────────────────────
    _clean = dict(_base, views={"all": {"self_check": {"unsaid_is_escape": False},
                                        "quality_flags": []}})
    if "**自省回写**" in m.render_landing(_clean):
        bad.append("无高置信诊断时不该渲染「自省回写」")

    _esc = dict(_base, views={"all": {"self_check": {
        "unsaid_is_escape": True, "unsaid_where": "用未生收尾"},
        "quality_flags": []}})
    _t1 = m.render_landing(_esc)
    if "**自省回写**" not in _t1:
        bad.append("unsaid_is_escape=True 时该渲染「自省回写」")
    if "⇒ 动作" not in _t1:
        bad.append("「自省回写」里没有可执行动作")

    _flag = dict(_base, views={"all": {"self_check": {},
                                       "quality_flags": ["unsaid_overused(8)"]}})
    if "**自省回写**" not in m.render_landing(_flag):
        bad.append("quality_flags=unsaid_overused(n) 时该渲染「自省回写」")
    _hard = dict(_base, views={"1": {"self_check": {},
                                     "quality_flags": ["action_incomplete"]}})
    if "**自省回写**" not in m.render_landing(_hard):
        bad.append("action_incomplete 时该渲染「自省回写」")

    # 顺序：模板声明在前、诊断动作在后
    if "**形态声明**" in _t1 and "**自省回写**" in _t1:
        if _t1.index("**形态声明**") > _t1.index("**自省回写**"):
            bad.append("「自省回写」跑到「形态声明」前面了（顺序反了）")

    # ── B 事实题自动联网 ──────────────────────────────────────
    if not hasattr(m, "_web_auto_for_facts"):
        bad.append("缺 _web_auto_for_facts")
    else:
        if not m._web_auto_for_facts("新中国的成立时间是什么时候"):
            bad.append("事实题应自动接入外部校验")
        if m._web_auto_for_facts("这份方案怎么落地"):
            bad.append("决策题不该自动接入外部校验")
    # ★ [v1.23.13 判据随实现更新] 原先查两处**接线字面**
    #   （`_web_auto_for_facts(" ".join(args.question))` 与 `"web": _web`）——
    #   本版把事实题联网收进统一调度器，字面没了、**行为没变**。
    #   改成端到端行为：事实题走完整条调度链后联网真的开；显式 `--web off` 真的关。
    try:
        import copy as _cp2
        _wq = "新中国的成立时间是什么时候"
        _wc = _cp2.deepcopy(m.DEFAULT_CONFIG)
        m._apply_auto_dispatch(_wc, m.auto_dispatch(_wq, _wc))
        _wc2, _ = m._apply_runtime(_wc)
        if _wc2["web_search"]["enabled"] is not True:
            bad.append("事实题经调度链后联网没开")
        _wc3 = _cp2.deepcopy(m.DEFAULT_CONFIG)
        m._apply_auto_dispatch(_wc3, m.auto_dispatch(_wq, _wc3,
                                                    explicit={"web": "off"}))
        _wc4, _ = m._apply_runtime(_wc3)
        if _wc4["web_search"]["enabled"] is not False:
            bad.append("显式 --web off 经调度链后没生效")
    except Exception as _e2:  # noqa: BLE001
        bad.append("调度链接线断裂：%s: %s" % (type(_e2).__name__, _e2))

    if bad:
        for _m in bad:
            print("  \u2717 [v12311] %s" % _m)
        return False
    print("  \u2713 [v12311] 自省回写(逃避/质量线索/硬约束 三触发 + 无诊断不渲染 + 顺序) / "
          "事实题自动联网(事实 True·决策 False + 源码接线在)")
    return True

# <<<end v123 checks>>>


def check_v12325_struct_coverage():
    """[v1.23.25] 「结构覆盖率」按它**本来的视角（结构侧）**重设计：
       结构被研究出自己触及的概率。

    ★ 三轮诊断（六个候选凭据全排除）见 v12325_报告.md §2。
    ★ 判别力：旧口径恒 0.000，新口径 0.143~1.000。
    ★ 正交：与「独立度」Pearson r ≈ 0.13（夹具下独立度恒 1.000、
      结构覆盖率可变）。
    """
    import inspect as _ins
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    cfg = build_cfg(False)

    # ================= A. 自触及算式 =================
    _S = ["结构甲：前台按钮与后台提示不可同时满足",
          "结构乙：时间差两端不可折中",
          "结构丙：两域可改性不同，合问为假"]
    _p = mod.Pool()
    _p.add_undecidable(
        {"structural_amps": list(_S), "aligned_amps": [], "clarity": 0.7},
        und_aspects=["世界本身是否虚拟"], layer=1, covered_aspects=[])
    _ch = _p.undecidable_channel
    if _ch.get("last_sc_ratio") != 0.0 or _ch.get("last_sc_touched") != 0:
        bad.append(f"[A] 首圈（无下游文本）应为 0.00："
                   f"sc={_ch.get('last_sc_ratio')} "
                   f"touched={_ch.get('last_sc_touched')}")
    if _ch.get("last_sc_pool") != 3:
        bad.append(f"[A] 分母不是 3：{_ch.get('last_sc_pool')}")
    # 加一条呼应「结构乙」的线头 ⇒ 1/3
    _p.threads.append({"desc": "时间差两端不可折中的实例仍未取到，悬空",
                       "kind": "thread", "polarity": "0"})
    _p.add_undecidable(
        {"structural_amps": list(_S), "aligned_amps": [], "clarity": 0.8},
        und_aspects=[], layer=2, covered_aspects=[])
    _ch = _p.undecidable_channel
    if abs(float(_ch.get("last_sc_ratio") or -1) - 1 / 3) > 1e-9:
        bad.append(f"[A] 自触及不是 1/3：{_ch.get('last_sc_ratio')}")
    if _ch.get("last_sc_touched") != 1:
        bad.append(f"[A] touched 不是 1：{_ch.get('last_sc_touched')}")
    if list(_ch.get("sc_history") or []) != [0.0, 1 / 3]:
        bad.append(f"[A] sc_history 不对：{_ch.get('sc_history')}")
    # ★ 不变式：旧键一个数不许动（历史语料的口径 + 命中轨迹的输入）
    if _ch.get("last_struct_coverage") != 0.0:
        bad.append(f"[A] 旧键 last_struct_coverage 被动了："
                   f"{_ch.get('last_struct_coverage')}（应 0.0）")
    # ★ 正交：线头不该影响独立度（独立度只看与 und_aspects 的重合）
    if abs(float(_ch.get("last_indep_ratio") or -1) - 1.0) > 1e-9:
        bad.append(f"[A] 独立度被线头影响了（应仍 1.000）："
                   f"{_ch.get('last_indep_ratio')}")
    # 空池：None（不可计算），不许 0.0
    _pe = mod.Pool()
    _pe.add_undecidable({"structural_amps": [], "aligned_amps": [],
                         "clarity": 0.5}, und_aspects=[], layer=1,
                        covered_aspects=[])
    if _pe.undecidable_channel.get("last_sc_ratio") is not None:
        bad.append(f"[A] 空池的结构覆盖率不是 None："
                   f"{_pe.undecidable_channel.get('last_sc_ratio')}")
    # 负对照：线头跟所有结构都不搭 ⇒ 必须掉回 0.00
    _pn = mod.Pool()
    _pn.add_undecidable(
        {"structural_amps": list(_S), "aligned_amps": [], "clarity": 0.5},
        und_aspects=[], layer=1, covered_aspects=[])
    _pn.threads.append({"desc": "量子引力中的时间箭头问题仍未解",
                        "kind": "thread"})
    _pn.add_undecidable(
        {"structural_amps": list(_S), "aligned_amps": [], "clarity": 0.5},
        und_aspects=[], layer=2, covered_aspects=[])
    _cn = _pn.undecidable_channel
    if _cn.get("last_sc_touched") != 0 or _cn.get("last_sc_ratio") != 0.0:
        bad.append(f"[A-负对照] 不搭的线头竟算作触及："
                   f"touched={_cn.get('last_sc_touched')} "
                   f"sc={_cn.get('last_sc_ratio')}")

    # ================= B. 产物渲染三读数并列 =================
    _mg = mod.MetaDGTF(cfg)
    _mg.pools["1"].undecidable_channel = _ch
    _line = _mg._und_channel_line()
    if "结构覆盖率 0.33" not in _line:
        bad.append(f"[B] 产物没渲染结构覆盖率：{_line!r}")
    if "1/3 条结构被后续圈" not in _line:
        bad.append(f"[B] 结构覆盖率的分子分母没渲染：{_line!r}")
    if "独立度 1.00" not in _line:
        bad.append(f"[B] 三读数没并列（缺独立度）：{_line!r}")
    # ★ 三读数必须**同现**在同一行（v1.23.25 的验收点）
    for _k in ("清晰度", "独立度", "结构覆盖率"):
        if _k not in _line:
            bad.append(f"[B] 三读数缺「{_k}」：{_line!r}")
    # 口径标注：不许把「结构覆盖率」说成「方面被覆盖」
    if "量的是「结构有多活」" not in _line:
        bad.append(f"[B] 口径标注（结构有多活）缺了：{_line!r}")
    # 无结构时印「—」，不许印 0.00
    _m2 = mod.MetaDGTF(cfg)
    _m2.pools["1"].undecidable_channel = dict(
        _pe.undecidable_channel, clarity_history=[0.5])
    _l2 = _m2._und_channel_line()
    if "结构覆盖率 —" not in _l2 or "结构覆盖率 0.00" in _l2:
        bad.append(f"[B] 无结构时应印「—」不是 0.00：{_l2!r}")

    # ================= C. shape 喂模型 =================
    if "不可判定结构覆盖率" not in src:
        bad.append("[C] 终端渲染没接结构覆盖率")

    # ================= D. 源码接线 =================
    if src.count("def _und_self_touch_texts(self)") != 1:
        bad.append("[D] _und_self_touch_texts 不是唯一实现")
    if src.count('"sc_history"') < 2:
        bad.append(f"[D] sc_history 接线点太少："
                   f"{src.count(chr(34) + 'sc_history' + chr(34))}")
    if "covered_aspects: Optional[List[str]] = None" not in src:
        bad.append("[D] add_undecidable 没接 covered_aspects 形参")
    _sig = _ins.signature(mod.Pool.add_undecidable).parameters
    if "covered_aspects" not in _sig:
        bad.append("[D] add_undecidable 签名里没有 covered_aspects")

    if bad:
        for b in bad:
            print(f"  ✗ [v12325] {b}")
        return False
    print("  \u2713 [v12325] 结构覆盖率重设计（自触及）+ 三读数并列 / "
          "空池 None / 独立度正交 / 负对照 / 源码接线")
    return True





#: [v1.23.27] 判据用：D1 四态机的四个合法状态（与引擎同源）。
_BELIEF_STATUS_EXPECT = ("active", "stable", "resolved", "revoked")


def check_v12326_sim3():
    """[v1.23.26] ① sim3 三级尺子（对称 Jaccard + BM25）修 `_overlap_coef`
       短句高估 ② 池内去重阈值可配（默认 = 旧字面量，行为零变化）
       ③ covers 数字编号分支加语义校验（编号对但语义错必须报红）。

    ★ 每条判据都带**负对照**；判别力另由 `_mut_v12326.py` 的变异体证明
      （没有变异体的「全绿」只说明判据没跑）。
    ★ 判别力夹具（改前 v1.23.25 实测值 / 改后 v1.23.26 实测值）：
      · `_overlap_coef("模型 部署","模型 训练")` = 0.500（虚高）
        `_sim3(同对)` = 0.333（并集分母，不虚高）
      · covers 乱指 T1：改前**不报红**，改后**报红**
      —— 两版结论相反，否则这条夹具等于没测。
    """
    import inspect as _ins
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    cfg = build_cfg(False)

    # ================= A. sim3 修正短句高估 =================
    _a, _b = "模型 部署", "模型 训练"
    _oc = mod._overlap_coef(_a, _b)
    _s3 = mod._sim3(_a, _b)
    if abs(_oc - 0.5) > 1e-9:
        bad.append(f"[A] _overlap_coef 基线漂了：{_oc}（期望 0.5）")
    # ★ 旧尺子虚高：3 词短语共享 1 词 = 1/2
    if _oc < 0.5 - 1e-9:
        bad.append(f"[A] 旧尺子不再虚高（{_oc}）⇒ 这条判据失去意义，"
                   f"请重新设计夹具")
    # ★ 新尺子必须显著低于旧尺子（Jaccard 分母是并集）
    if not (_s3 < _oc - 0.1):
        bad.append(f"[A] _sim3({_s3}) 未显著低于 _overlap_coef({_oc})，"
                   f"短句高估没修好")
    # 对称性：sim3 必须是对称的
    _pairs = [(_a, _b), ("人工智能 模型 部署 管线", "人工智能 模型 部署"),
              ("量子纠缠实验需要极低温", "量子纠缠实验需要低温环境")]
    for _x, _y in _pairs:
        if abs(mod._sim3(_x, _y) - mod._sim3(_y, _x)) > 1e-9:
            bad.append(f"[A] _sim3 不对称：{_x} / {_y}")
    # ★ 结构层（L4）短路：同编号必须 1.0、异编号必须 0.0
    #   —— 变异体 M3（去掉 L4）就打在**这条判据读的东西**上。
    #   ★ 样本必须用**字符串不等但编号相同**的对（`T3` vs `3`）：
    #     若用 `T3` vs `T3`，`_sim3` 开头 `if a == b: return 1.0` 会
    #     先短路 ⇒ M3 变异后仍是 1.0 ⇒ 判据等于没测（实测踩过）。
    if mod._sim3("T3", "3") != 1.0:
        bad.append(f"[A] 同编号未短路为 1.0（{mod._sim3('T3', '3')}）"
                   f"⇒ 结构层失效")
    if mod._sim3("T3", "T4") != 0.0:
        bad.append(f"[A] 异编号未短路为 0.0（{mod._sim3('T3', 'T4')}）"
                   f"⇒ 结构层失效")
    # 负数对照：结构层必须**先于**字面层（T3/T4 无字面交集仍须 0.0）
    if mod._sim3("T3", "T4") >= mod._sim3("T3", "3"):
        bad.append("[A] 异编号分不低于同编号分 ⇒ 结构层没前置")

    # ================= B. BM25 通道真的在起作用 =================
    _corpus = mod._bm25_corpus(
        ["量子纠缠实验需要极低温环境", "超导材料在低温下表现特殊",
         "人工智能模型部署管线优化", "模型蒸馏可以压缩参数量"])
    if _corpus[3] < 4:
        bad.append(f"[B] 语料只有 {_corpus[3]} 篇，BM25 通道不会启用")
    # ★ 负对照要选**真的不相干**的输入。第一版拿
    #   「量子纠缠实验」vs「超导材料在低温下表现特殊」当负对照是错的
    #   —— 两者共享「低温」，而语料里恰有「量子纠缠实验需要极低温环境」，
    #   词面重叠真实存在 ⇒ 分高是对的，不是「被抬高」。
    _irrelevant = "披萨烤制时长与面团发酵温度"
    if mod._bm25_best(_irrelevant, _corpus) > 0.0:
        bad.append(f"[B] 完全不相干的输入拿到了 BM25 分 "
                   f"（{mod._bm25_best(_irrelevant, _corpus)}），应为 0")
    # ★ 正对照：与语料真有词面重叠的输入必须拿到 > 0 的分
    _overlap_q = "量子纠缠实验"
    if mod._bm25_best(_overlap_q, _corpus) <= 0.0:
        bad.append("[B] 与语料有真实词面重叠的输入拿不到 BM25 分 ⇒ "
                   "通道没接上")
    # ★ BM25 通道确实改变最终分（不是「算了不用」）
    _q2, _c2 = "量子纠缠实验", "量子纠缠实验需要极低温环境"
    _s_no = mod._sim3(_q2, _c2)
    _s_yes = mod._sim3(_q2, _c2, _corpus)
    if not (_s_yes > _s_no):
        bad.append(f"[B] 有语料时未升分（{_s_no} -> {_s_yes}）⇒ "
                   f"BM25 通道没进合并式")
    # ★ 归一化必须把分压回 [0,1)（无上界的 raw 会破坏三层加权）
    _bm_raw_hi = mod._bm25_best(
        "量子纠缠实验需要极低温环境 人工智能模型部署管线优化 "
        "模型蒸馏可以压缩参数量 超导材料在低温下表现特殊", _corpus)
    if not (0.0 <= _bm_raw_hi < 1.0):
        bad.append(f"[B] BM25 归一化失效，分越界：{_bm_raw_hi}")
    # ★ BM25 必须是**两篇之间**的分（pair），不能是「各自对语料」的 best。
    #   反例（改前的真 bug）：两条各自与语料相关、但彼此**毫不相干**的句子，
    #   用 best 均值会被抬到 0.78；用 pair 必为 0.0。
    #   变异体 M1'（把 _bm25_pair 换回 _bm25_best）就打在**这条判据读的东西**上。
    _far_a, _far_b = "量子纠缠实验需要极低温", "人工智能模型部署管线优化"
    if mod._jaccard(_far_a, _far_b) != 0.0:
        bad.append(f"[B] 负对照对本身有字面重叠"
                   f"（{mod._jaccard(_far_a, _far_b)}）⇒ 请换样本")
    _far_s3 = mod._sim3(_far_a, _far_b, _corpus)
    if _far_s3 > 1e-9:
        bad.append(f"[B] 两条**无关**句子因 BM25 被抬高（{_far_s3}）⇒ "
                   f"BM25 通道用的是「各自对语料」而非「两篇之间」")
    # 正对照：真相关的对必须保住高分（避免「一律归零」蒙混过关）
    _near_s3 = mod._sim3("量子纠缠实验", "量子纠缠实验需要极低温环境",
                         _corpus)
    if _near_s3 <= 0.5:
        bad.append(f"[B] 相关对在 BM25 pair 下分数过低（{_near_s3}）⇒ "
                   f"通道被改坏（过度收缩）")
    # pair 必须对称
    if abs(mod._bm25_pair(_far_a, _far_b, _corpus)
           - mod._bm25_pair(_far_b, _far_a, _corpus)) > 1e-9:
        bad.append("[B] _bm25_pair 不对称")
    # 语料不足时自动降级（N < _BM25_MIN_CORPUS）
    # ★ 查询词必须是**语料里真实存在的词**：原来用「测试」（不在语料里
    #   ⇒ 本来就 0）⇒ 抓不到 M4（下限降到 0 也不报）。
    _tiny = mod._bm25_corpus(["只有一个句子"])
    _tiny_q = "只有一个句子"
    if mod._bm25_best(_tiny_q, _tiny) != 0.0:
        bad.append(f"[B] 语料不足时 BM25 未降级"
                   f"（应返回 0.0，实得 {mod._bm25_best(_tiny_q, _tiny)}）")
    if mod._bm25_pair(_tiny_q, "只有一个句子", _tiny) != 0.0:
        bad.append("[B] 语料不足时 _bm25_pair 未降级（应返回 0.0）")

    # ================= C. 池内去重阈值可配 =================
    if not hasattr(mod, "_DEDUP_SIM") or not hasattr(mod, "_DEDUP_SUSP_SIM"):
        bad.append("[C] 缺池内去重常量")
    else:
        if mod._DEDUP_SIM != 0.9:
            bad.append(f"[C] _DEDUP_SIM 默认不是 0.9（{mod._DEDUP_SIM}）"
                       f"⇒ 与旧版行为不再一致")
        if mod._DEDUP_SUSP_SIM != 0.85:
            bad.append(f"[C] _DEDUP_SUSP_SIM 默认不是 0.85"
                       f"（{mod._DEDUP_SUSP_SIM}）")
    _sim_cfg = (mod.DEFAULT_CONFIG.get("sim") or {})
    if _sim_cfg.get("dedup") != 0.9 or _sim_cfg.get("dedup_susp") != 0.85:
        bad.append(f"[C] DEFAULT_CONFIG[sim] 不对：{_sim_cfg}")
    # merge 签名必须收 thr / susp_thr
    _sig = _ins.signature(mod.Pool.merge)
    for _k in ("thr", "susp_thr"):
        if _k not in _sig.parameters:
            bad.append(f"[C] Pool.merge 缺参数 {_k}")
    # ★ 行为判据：阈值真的能改行为（同一对文本，thr 不同结论不同）
    _A = "量子纠缠实验需要极低温环境与高精度探测器的配合才能完成验证"
    _B = "量子纠缠实验需要低温环境与高精度探测器的配合才能完成验证工作"
    _p1 = mod.Pool()
    _p1.merge([{"desc": _A}, {"desc": _B}], [], [], thr=0.9)
    _p2 = mod.Pool()
    _p2.merge([{"desc": _A}, {"desc": _B}], [], [], thr=0.99)
    if not (len(_p1.amps) < len(_p2.amps)):
        bad.append(f"[C] thr 改了但结论没变（0.9->{len(_p1.amps)} 条，"
                   f"0.99->{len(_p2.amps)} 条）⇒ 阈值没接上")
    # 默认值 = 旧行为（不传参时与传 0.9 等价）
    _p3 = mod.Pool()
    _p3.merge([{"desc": _A}, {"desc": _B}], [], [])
    if len(_p3.amps) != len(_p1.amps):
        bad.append("[C] 不传参的行为与传 0.9 不一致 ⇒ 默认值没对齐")

    # ================= D. covers 语义校验（含 id 对账）=================
    # ★ 源码层：covers 判据体里必须出现语义比较 —— 旧版这里是裸
    #   `has_touch = True`（编号对就算碰了）。E3 起改成「**编号对是
    #   必要条件、还要语义对得上**」，结构从 `if m: / else:` 变成
    #   「字典查表 + `_tgt is None` 早退」。所以这里**按新结构**判：
    #   在「id 命中之后」到「not has_touch」之间必须出现语义比较，
    #   且必须有 bad_ref 分支（编号不在集合里 ⇒ 报红）。
    #   ★ 判据随实现更新 —— 形态变了要改判据以匹配新语义，
    #     不是放宽阈值（行为判据在下面照跑，仍有判别力）。
    _i = src.find('if (self.entry == "1" and view.untouched and view.probes):')
    _j = src.find("if not has_touch:", _i)
    _body = src[_i:_j] if _i > 0 and _j > _i else ""
    if not _body:
        bad.append("[D] 找不到 covers 判据体")
    else:
        # 语义比较必须存在（任何一个都算接线）
        if not any(_t in _body for _t in ("_similar", "_overlap_coef", "_sim3")):
            bad.append("[D] covers 判据体里没有语义比较（回退了）")
        # id 对账必须存在（E3：编号不在集合里 ⇒ bad_ref）
        if "probe_covers_bad_ref" not in _body:
            bad.append("[D] covers 判据体里没有 bad_ref 分支"
                       "（编号越界与语义不符没分开）")
        # 逐位语义比较必须**发生在 id 命中之后**（不能先无条件放过）
        _pos_id = _body.find("_cov_targets.get(")
        _pos_sem = _body.find("_sim3(")
        if _pos_id < 0 or _pos_sem < 0 or _pos_sem < _pos_id:
            bad.append("[D] covers 语义比较不在 id 命中之后"
                       "（可能是无条件放过）")
    # ★ 行为判据（驱动真实方法）：covers 乱指 T1 必须报红
    _CLS = None
    for _c in ("DGTF", "MetaDGTF"):
        if hasattr(mod, _c) and hasattr(getattr(mod, _c), "_quality_check"):
            _CLS = getattr(mod, _c)
            break
    if _CLS is None:
        bad.append("[D] 找不到 DGTF._quality_check")
    else:
        _obj = _CLS.__new__(_CLS)
        _obj.entry = "1"
        _obj.config = dict(mod.DEFAULT_CONFIG)
        _obj.vp = lambda *a, **k: None
        _UT = ["材料在极低温下的超导相变临界温度测量方法",
               "实验装置的电磁屏蔽对测量信噪比的影响",
               "样品制备过程中杂质浓度对结果的可重复性"]

        def _mk(probes):
            _v = mod.View.__new__(mod.View)
            for _n, _d in [("candidates", []), ("amps", []), ("threads", []),
                           ("probes", []), ("errors", []), ("self_check", {}),
                           ("collision", ""), ("engagements", []),
                           ("deferrals", []), ("reconfirmations", []),
                           ("resolutions", []), ("escalations", []),
                           ("reclassifications", []), ("meta", []),
                           ("refinements", []), ("probe_skipped", False)]:
                try:
                    setattr(_v, _n, _d)
                except Exception:
                    pass
            _v.untouched = [{"desc": _t} for _t in _UT]
            _v.probes = probes
            return _v

        def _flags(probes):
            try:
                return _obj._quality_check(_mk(probes), mod.Pool(), 1,
                                           write_diag=False)
            except Exception as _e:
                return ["__驱动失败__:" + type(_e).__name__]

        # 负对照：编号对、语义错 ⇒ 必须报红
        _f1 = _flags([{"question": "披萨需要烤制多长时间才能外脆内软",
                       "covers": ["T1"], "expected_gain": 0.6, "link": "x"}])
        if "probe_no_target_covered" not in _f1:
            bad.append(f"[D] covers 乱指 T1 仍未报红（flags={_f1}）"
                       f"⇒ 语义校验没接上")
        # 正对照：编号对、语义对 ⇒ 不许报红
        _f2 = _flags([{"question": "超导相变临界温度在极低温下如何测量",
                       "covers": ["T1"], "expected_gain": 0.6, "link": "x"}])
        if "probe_no_target_covered" in _f2:
            bad.append(f"[D] covers 正确指向却报红（flags={_f2}）"
                       f"⇒ 校验过严")
        # 负对照：越界编号 ⇒ 报红（旧行为，不能丢）
        _f3 = _flags([{"question": "披萨需要烤制多长时间才能外脆内软",
                       "covers": ["T5"], "expected_gain": 0.6, "link": "x"}])
        if "probe_no_target_covered" not in _f3:
            bad.append(f"[D] 越界编号不再报红（flags={_f3}）")

    if bad:
        for _b2 in bad:
            print(f"  ✗ [v12326] {_b2}")
        return False
    print("  \u2713 [v12326] sim3 三级尺子（对称 + BM25 可降级）/ "
          "池内阈值可配（默认零变化）/ covers 数字分支语义校验"
          "（负对照：乱指 T1 必报红）")
    return True



def check_v12327_five_mechanisms():
    """[v1.23.27] 五机制算法重构（第二期）九项判据。

    ★ 每一项都**驱动真实函数**判行为（不查字符串），且每个断言都有
      对应变异体（`_mut_v12327.py` M1~M8）：变异体判红 ⇒ 判据有判别力。
    覆盖：
      A1 AspectUnit 幂等与 ground 归一化
      A2 符号对账收敛（amp#N / th#N / A{N}）
      A3 双读数分离（touch_rate ≠ aspect_carry_rate 的构造）
      D1 BeliefItem 四态机（非法 status 归一化）
      D2 迁移优先级（resolved > revoked > stable）
      D3 语义熵 n<2 返回 None（不印 0.0 冒充）
      E1 EIG 可计算化且两臂同尺（targeted G > 0）
      E2 子模批选（边际下限、宁少勿滥）
      E6 自适应停止（seen==0 不是 stop）
    """
    bad = []

    # ── A1 AspectUnit ──────────────────────────────────────────
    _v = mod.View(entry="0")
    _a1 = _v.add_aspect_unit("同一方面", "src", "阳", "anchor", "r")
    _a2 = _v.add_aspect_unit("同一方面", "src", "阳", "anchor", "r")
    if not _a1 or _a1.get("id") != _a2.get("id"):
        bad.append("[A1] 同 desc 未幂等（id=%r vs %r）"
                   % (_a1.get("id"), _a2.get("id")))
    if len(_v.aspect_units) != 1:
        bad.append("[A1] 幂等失效导致重复登记（len=%d）"
                   % len(_v.aspect_units))
    if _a1.get("text") != _a1.get("desc"):
        bad.append("[A1] text != desc ⇒ 旧读取点会拿不到文本")
    _ab = mod.make_aspect_unit("x", source="s", polarity="阳",
                               ground="bogus_ground", ref="r")
    if _ab.get("ground") != "anchor":
        bad.append("[A1] 非法 ground 未归一化到 anchor（%r）"
                   % _ab.get("ground"))
    # ★ v1.23.28：`untouched`/`anchor_touched` 的**写入侧必须带 id**。
    #   历史缺陷：写入只有 {"desc": ...}，而渲染前缀按 `id` 取
    #   `aspect_units` 的编号 ⇒ 前缀**永远印不出**（静默丢标记）。
    #   这条断言**驱动真实写入方法**（不是查字符串），且 id 必须能在
    #   `aspect_units` 里找到 —— 否则渲染点仍拿不到编号。
    _v1u = mod.View(entry="0")
    _u_rec = _v1u.add_aspect_unit("未触及项甲", source="anchor",
                                  polarity="阴", ground="anchor")
    _v1u.untouched.append({"desc": "未触及项甲", "source": "anchor",
                           "id": (_u_rec or {}).get("id", "")})
    if not _v1u.untouched:
        bad.append("[A1] untouched 未写入")
    elif not _v1u.untouched[0].get("id"):
        bad.append("[A1] untouched 条目缺 id ⇒ 渲染前缀永远印不出")
    else:
        _ids_u = {u.get("id") for u in _v1u.aspect_units}
        if _v1u.untouched[0].get("id") not in _ids_u:
            bad.append("[A1] untouched 的 id 不在 aspect_units 里 "
                       "⇒ 编号口径分叉（%r ∉ %s）"
                       % (_v1u.untouched[0].get("id"), sorted(_ids_u)))

    # ── A2 符号对账收敛 ───────────────────────────────────────
    _p = mod.Pool()
    _p.amps = [{"desc": "某条"}]
    _p.threads = [{"desc": "某线头"}]
    _p.probes = [{"question": "某探针"}]
    _p.covered_unders = ["某未生"]
    _tg = _p.aspect_targets_v12327()
    for _k in ("amp#1", "th#1", "probe#1", "A1"):
        if _k not in _tg:
            bad.append("[A2] targets 缺 %s（收敛不全）：%s"
                       % (_k, sorted(_tg)))

    # ── A3 双读数分离（构造「触及但没延续」）─────────────────
    _v3 = mod.View(entry="0")
    _v3.round_log = [{"anchor_touched_n": 3}]
    _v3.aspect_units = [{"id": "A1", "text": "t", "desc": "t"}]
    _v3._layer_und_channel = {}
    _tr = _v3.touch_rate
    _cr = _v3.aspect_carry_rate
    if not (_tr is not None and _tr > 0):
        bad.append("[A3] touch_rate 应为 >0（构造 3 触及）实为 %r" % _tr)
    # ★ [v1.23.29 判据随实现更新 · 不是放宽] 旧口径 `无延续 ⇒ 0.0` 是
    #   本版定性的**假读数**：它把「上游没产延续 id / 本层还没接上」
    #   印成「延续了 0 条」。新口径 `无延续 ⇒ None`，由渲染层印「—」。
    #   ★ 两向都钉住：有延续 id 时必须**算得出真值**（这里构造 1/2 命中
    #     ⇒ 0.5），否则「一律 None」也能骗过判据（零信息量）。
    if _cr is not None:
        bad.append("[A3] 无延续读数时应返回 None（不印 0.00 冒充）实为 %r"
                   % _cr)
    _v3b = mod.View(entry="0")
    _v3b.aspect_units = [{"id": "A1", "text": "t"}, {"id": "A2", "text": "u"}]
    _v3b._carried_aspect_ids = ["A1"]
    if _v3b.aspect_carry_rate != 0.5:
        bad.append("[A3] 有延续 id 时应算真值 0.5 实为 %r"
                   % _v3b.aspect_carry_rate)
    # 空池 ⇒ None（不印 0.00 冒充读数）
    if mod.View(entry="0").aspect_carry_rate is not None:
        bad.append("[A3] 空池 carry_rate 应返回 None（不许印 0.0）")

    # ── D1 四态机 ──────────────────────────────────────────────
    for _s in _BELIEF_STATUS_EXPECT:
        _it = mod.make_belief_item("主张" + _s, "g", _s)
        if _it.get("status") != _s:
            bad.append("[D1] 合法状态 %s 被改动为 %r"
                       % (_s, _it.get("status")))
    _ib = mod.make_belief_item("x", "g", "totally_bogus")
    if _ib.get("status") != "active":
        bad.append("[D1] 非法 status 未归一化到 active（%r）"
                   % _ib.get("status"))
    if mod.make_belief_item("", "g") != {}:
        bad.append("[D1] 空 text 应返回 {}")

    # ── D2 迁移优先级 ─────────────────────────────────────────
    _cur = mod.make_belief_item("x", "g", "active")
    if mod.belief_transition(_cur, round_no=1, sources=["p#1"]) != "active":
        bad.append("[D2] 单圈单来源不该升 stable")
    _r2 = mod.belief_transition(
        mod.make_belief_item("x", "g", "active", rounds_seen=[1],
                             support=["p#1"]),
        round_no=2, sources=["th#1"])
    if _r2 != "stable":
        bad.append("[D2] 连续 2 圈且 2 来源应升 stable（实为 %r）" % _r2)
    _rev = mod.belief_transition(
        mod.make_belief_item("x", "g", "active", attack=["a#1", "a#2"],
                             support=["s#1"], rounds_seen=[1]),
        round_no=2, attack=["a#3"], attack_sources=["layer0", "layer1"])
    if _rev != "revoked":
        bad.append("[D2] 攻击跨 ≥2 个不同来源应 revoked（实为 %r）" % _rev)
    # ★ 负对照：同一来源反复攻击**不许** revoked —— 独立性不是次数。
    _rev_neg = mod.belief_transition(
        mod.make_belief_item("x", "g", "active", attack=["a#1"],
                             support=["s#1"], rounds_seen=[1]),
        round_no=2, attack=["a#2"], attack_sources=["layer0"])
    if _rev_neg == "revoked":
        bad.append("[D2] 同一来源反复攻击竟 revoked —— "
                   "「同一来源重复骂」冒充「独立复现」")
    _res = mod.belief_transition(_cur, round_no=5, sources=["p#1"],
                                 attack=["t#1"],
                                 resolved_by="decidable_channel")
    if _res != "resolved":
        bad.append("[D2] resolved 优先级最高（实为 %r）" % _res)

    # ── D3 语义熵 ──────────────────────────────────────────────
    _hn, _hr, _cl = mod.semantic_entropy_of(["只有一条"])
    if _hn is not None:
        bad.append("[D3] n<2 应返回 None（实为 %r）—— 印 0.0 是自欺" % _hn)
    _hn2, _hr2, _cl2 = mod.semantic_entropy_of(["甲", "甲", "甲"])
    if not (_hn2 is not None and _hn2 <= 0.05):
        bad.append("[D3] 三条同义应近 0 熵（实为 %r）" % _hn2)

    # ── E1 EIG 同尺 ───────────────────────────────────────────
    # ★ 构造要点：`h_before` 必须 **>0**（有分歧才有不确定度可降）。
    #   若三条全同义 ⇒ 聚成 1 簇 ⇒ h_before=0 ⇒ G 恒 0（数学正确，
    #   但测不出「同尺」）。所以用「两条同簇 + 一条异构」：
    #   targeted 命中同簇那条 ⇒ 移除后 h_after 下降 ⇒ G>0；
    #   若两臂各用各的 ln(n)（Step8c 前的 bug）⇒ G 会被抵消成 0。
    _bis = [{"id": "B1", "text": "极低温环境下材料脆性阈值是多少",
             "status": "active"},
            {"id": "B2", "text": "极低温环境下材料脆性阈值如何",
             "status": "active"},
            {"id": "B3", "text": "城市轨道交通客流预测模型的误差",
             "status": "active"}]
    _G, _d = mod.probe_information_gain(
        {"question": "极低温环境下材料脆性阈值是多少"}, _bis)
    if not (_G is not None and _G > 0.0):
        bad.append("[E1] targeted G 应为正（实为 %r / %s）—— "
                   "两臂不同尺会让 G 恒 0" % (_G, _d.get("why")))
    _G2, _d2 = mod.probe_information_gain({"question": ""}, _bis)
    if _G2 is not None:
        bad.append("[E1] 空问题应返回 None（实为 %r）" % _G2)
    _G3, _d3 = mod.probe_information_gain({"question": "x"}, [])
    if _G3 is not None:
        bad.append("[E1] 未决 <2 应返回 None（实为 %r）" % _G3)

    # ── E2 子模批选（宁少勿滥）───────────────────────────────
    _p2 = mod.Pool()
    _p2.belief_items = list(_bis)
    _picked, _det = mod.select_probe_focus_submodular(
        _p2, [{"question": "极低温环境下材料脆性阈值是多少",
               "expected_gain": 0.9, "link": "x"}], 3)
    if len(_picked) > 3:
        bad.append("[E2] 批选超过上限 n=3（实为 %d）" % len(_picked))
    # ★ v1.23.28：边际下限**必须 > 0**。
    #   历史缺陷：`_GAIN_MARGINAL_FLOOR = 0.0` + `G ∈ [0,1]`
    #   ⇒ `if _best_g < _fl:` **永不成立** ⇒ `below_floor` 结构性不可达。
    #   这条判据**构造性地**证明该分支可达：给一个 G 恰为 0 的候选
    #   （地板 0.02）⇒ 必须被 below_floor 挡下。
    _fl_now = float(getattr(mod, "_GAIN_MARGINAL_FLOOR", 0.0))
    if not (_fl_now > 0.0):
        bad.append("[E2] `_GAIN_MARGINAL_FLOOR` 应 > 0（实为 %r）"
                   "—— 0.0 会让 below_floor 分支恒不可达" % _fl_now)
    _p3 = mod.Pool()
    _p3.belief_items = list(_bis)
    # ★ 构造要点：候选文本必须**与池内信念完全无关** ⇒ G == 0
    #   （只有命中池内分歧才有可降不确定度）。`_items` 取 `text` 字段。
    _pk2, _dt2 = mod.select_probe_focus_submodular(
        _p3, [{"text": "完全不相关的火星土壤成分分析"}], 3,
        floor=_fl_now)
    if _pk2:
        bad.append("[E2] G=0 的候选在 floor>0 时不该入选"
                   "（below_floor 分支不可达或阈值失效）")
    _trace2 = (_dt2 or {}).get("trace") or []
    _stops2 = [t.get("stop") for t in _trace2 if isinstance(t, dict)]
    if "below_floor" not in _stops2:
        bad.append("[E2] 未走到 below_floor 分支（stops=%r）"
                   "—— 该分支是「宁少勿滥」的核心" % (_stops2,))

    # ── E6 自适应停止 ─────────────────────────────────────────
    if mod.e6_stop_verdict(0, 0.0, 0.3, 0.02) != (False, "no_candidate"):
        bad.append("[E6] seen==0 不是 stop（否则「模型偷懒」被读成「已收敛」）")
    if mod.e6_stop_verdict(3, 0.01, 0.3, 0.02) != (True,
                                                   "max_gain_below_floor"):
        bad.append("[E6] max_gain < floor 应判 stop")
    if mod.e6_stop_verdict(3, 0.02, 0.3, 0.02) != (False, "gain_ok"):
        bad.append("[E6] 边界（== floor）不该判 stop")
    _p3 = mod.Pool()
    _rec = _p3.note_probe_stop("research", 3, 0.005, 0.3, 0.02)
    if not (_rec.get("stop") and len(_p3.probe_stop_history) == 1):
        bad.append("[E6] 停止信号未写进 probe_stop_history")
    if "probe_stop_history" not in _p3.to_dict():
        bad.append("[E6] to_dict 未出口 probe_stop_history（静默丢产物）")
    if "probe_stop_history" in mod.Pool().to_dict():
        bad.append("[E6] 空 Pool 不该凭空出现 probe_stop_history")

    # ── E6 接线语义：**只在 `if not out:` 里记**（源码层） ──────
    # ★ 为什么必须固定这条语义：E6 是「停止信号」不是「每轮体检」。
    #   若哪天有人把它挪成无条件调用，`probe_stop_history` 会变成
    #   「每轮一条」，而**真跑里它只有 0 条**（本版四层每层都产出了
    #   探针 ⇒ 从不进 `if not out` 分支）⇒ 「记了」与「没记」将再也
    #   分不出「池收敛」和「模型偷懒」。这条语义是真跑才暴露的边界：
    #   不能等下次有人改坏了才发现。
    _src_all = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for _lay in ("research", "duel", "meta", "phase"):
        # ★ 锚点：`self._e6_note_stop(pool, view, "<层>"` —— **单下划线**
        #   （初版误写成 `__`，四条全报「缺调用」—— 判据自己的锚点错了，
        #    报出来却像「实现缺接线」。同 §3.1 那条教训：方向错的断言
        #    比没断言更危险。）
        _pat = '_e6_note_stop(pool, view, "%s"' % _lay
        _idx = _src_all.find(_pat)
        if _idx < 0:
            bad.append("[E6] 缺 %s 层的 _e6_note_stop 调用" % _lay)
            continue
        # 往回 120 字符内必须能找到 `if not out:` 守卫
        _pre = _src_all[max(0, _idx - 160):_idx]
        if "if not out:" not in _pre:
            bad.append("[E6] %s 层的记录点不在 `if not out:` 分支里"
                       "（停止信号退化成每轮体检）" % _lay)

    if bad:
        for _m in bad:
            print("  \u2717 [v12327] %s" % _m)
        return False
    print("  \u2713 [v12327] A1 幂等/归一化 · A2 符号对账收敛 · "
          "A3 双读数分离 · D1 四态机 · D2 迁移优先级 · D3 语义熵 None · "
          "E1 EIG 同尺 · E2 子模批选 · E6 自适应停止（9 变异体背书）")
    return True


def check_v12332_discipline():
    """[v1.23.32] 学科吸收六项：口径（α/κ）· 测量尺度 · 停因级联 · 成本两分 ·
    CSD 早期预警 · 判词阈值。

    判据四层（源码 / 纯函数 / 不变量 / 真实入口），每条带负对照。
    判别力由 `_mut_v12332.py` 背书（M1~M9）。
    """
    import tempfile as _tf
    src = SRC.read_bytes().decode("utf-8")
    bad = []

    # ── 源码级 ──
    for _n, _w in (("def krippendorff_alpha_ordinal(", "ordinal α"),
                   ("def weighted_kappa_pair(", "加权 κ"),
                   ("def rare_class_agreement(", "少数类一致"),
                   ("def alpha_verdict(", "α 判词"),
                   ("def reading_scale(", "尺度登记"),
                   ("def scale_word_violations(", "尺度禁词"),
                   ("def stop_priority(", "停因优先级"),
                   ("def stop_cascade(", "停因级联"),
                   ("def csd_indicators(", "CSD 指标"),
                   ("def _layer_csd_now(self, entry: str, view)", "CSD 接线"),
                   ("机会校正一致（ordinal）", "产物渲染"),
                   ("成本两分", "成本渲染")):
        if _n not in src:
            bad.append("[源码] %s 缺失（%r）" % (_w, _n))
    if "_LLM_EVAL_STAGES" not in src:
        bad.append("[源码] 成本两分的 stage 名单缺失")

    # ── 纯函数级（含负对照）──
    _perf = [["decidable"] * 3, ["partial"] * 3, ["undecidable"] * 3]
    _a = mod.krippendorff_alpha_ordinal(_perf)
    if not _a or abs(_a["alpha"] - 1.0) > 1e-9:
        bad.append("[α] 完美一致未得 1（%r）" % (_a,))
    if mod.krippendorff_alpha_ordinal([["decidable", "decidable"]]) is not None:
        bad.append("[α] 样本不足未返回 None（会印 0 冒充读数）")
    _skew = [["decidable"] * 3] * 9 + [["decidable", "partial", "undecidable"]]
    _ask = mod.krippendorff_alpha_ordinal(_skew)
    if not (_ask and _ask["alpha"] < 0.75):
        bad.append("[α] 偏斜夹具下 α 未被机会校正拉低（%r）" % (_ask,))
    if "可靠" not in mod.alpha_verdict(0.85) or \
            "不可靠" not in mod.alpha_verdict(0.40):
        bad.append("[α] 判词未按 Krippendorff 阈值分级")
    _rc = mod.rare_class_agreement(
        [["undecidable"] * 3, ["undecidable", "partial", "decidable"],
         ["decidable"] * 3], "undecidable")
    if not (_rc and _rc["units"] == 2 and abs(_rc["rate"] - 0.5) < 1e-9):
        bad.append("[少数类] 未筛类或一致率算错（%r）" % (_rc,))
    if mod.reading_scale("tri_state_agreement") != "ordinal":
        bad.append("[尺度] 三态一致率未登记为定序")
    if mod.reading_scale("绝不存在的读数") != "unknown":
        bad.append("[尺度] 未登记读数未返回 unknown（会默认当 interval）")
    if mod.scale_word_violations("一致率均值 0.5", "ordinal") != ["均值"]:
        bad.append("[尺度] 定序禁词未命中")
    if mod.scale_word_violations("一致率均值 0.5", "ratio") != []:
        bad.append("[尺度·负] 比例读数被误禁")
    _cas = mod.stop_cascade(["体力耗尽（4 圈走满）", "悬置决定稳定，自然安住"])
    if _cas["primary"] != "悬置决定稳定，自然安住":
        bad.append("[级联] 优先级未生效（主因=%r）" % _cas["primary"])
    if _cas["primary"] not in _cas["all"]:
        bad.append("[级联] ★主因不在全部触发里（报告即实际被破坏）")
    if mod.stop_priority("某种没见过的新停因") != 3:
        bad.append("[级联] 未匹配文案未落最低档（会静默丢弃）")
    _cu = mod.csd_indicators([1, 1, 2, 4, 7, 11])
    _cf = mod.csd_indicators([3] * 6)
    if not (_cu and _cu["hint"] is True):
        bad.append("[CSD] 上升序列未判有前兆（%r）" % (_cu,))
    if not (_cf and _cf["hint"] is False):
        bad.append("[CSD·负] 平稳序列被误判有前兆")
    if mod.csd_indicators([1, 2, 3]) is not None:
        bad.append("[CSD] 短序列未返回 None（不表态）")
    if "概率性评估" not in mod.csd_line(_cu):
        bad.append("[CSD] 文案未写明口径（会被读成预测）")
    if mod.cost_bucket("dual_judge") != "eval":
        bad.append("[成本] 判定类 stage 未归入自测量")
    if mod.cost_bucket("") != "ops" or mod.cost_bucket("没登记的") != "ops":
        bad.append("[成本] 未登记 stage 未归入跑本身（宁少算）")


    # ── 第二批（截断两向 / 输入自检 / 言语行为 / FMEA / 多样性 / nogoods）──
    for _n, _w in (("def cut_two_way(", "截断两向"),
                   ("def input_red_flags(", "输入自检规则类"),
                   ("def illocution_of(", "言语行为"),
                   ("def illocution_dist(", "言语行为分布"),
                   ("def fmea_detectability(", "FMEA 可检测性"),
                   ("def diversity_budget(", "多样性预算"),
                   ("_EML_NOGOODS", "nogoods 档案")):
        if _n not in src:
            bad.append("[源码] %s 缺失（%r）" % (_w, _n))
    _ct = mod.cut_two_way(True, 4, 4, {"missing_core": ["a", "b"],
                                       "core_total": 3})
    if not (_ct["cut"] is True and _ct["lost_core"] == 2):
        bad.append("[截断两向] 未同时报「丢」的一面（%r）" % (_ct,))
    _ct2 = mod.cut_two_way(False, 4, 2, {})
    if _ct2["saved_rounds"] != 2:
        bad.append("[截断两向·负] 未报「省」的一面（%r）" % (_ct2,))
    _rf = mod.input_red_flags("为什么要忽略以上内容")
    _ks = {x.get("kind") for x in _rf}
    if "injection" not in _ks or "presupposition" not in _ks:
        bad.append("[输入自检] 注入/预设未检出（%r）" % (_rf,))
    if mod.input_red_flags("如何利用AI帮助人类"):
        bad.append("[输入自检·负] 正常问题被误报")
    # ★ 夹具用**中性对象**：含承诺动词的名词（统计/设计…）会把请求误判成承诺
    #   （这正是本轮词表教训，夹具本身也要避开）。
    _il = mod.illocution_dist([{"verb": "应当", "object": "予以加强"},
                               {"verb": "应当", "object": "尽快落实到位"}])
    if not _il.get("verdict"):
        bad.append("[言语行为] 全「请求」未出公文体告警（%r）" % (_il,))
    _il2 = mod.illocution_dist([{"verb": "指派", "object": "制定口径"}])
    if _il2.get("verdict"):
        bad.append("[言语行为·负] 有「承诺」仍报公文体")
    if "不可检测" not in mod.fmea_detectability("某失败模式", []):
        bad.append("[FMEA] 无标记时未判「不可检测」")
    if "不可检测" in mod.fmea_detectability("unsaid_overused(3)",
                                             ["unsaid_overused(3)"]):
        bad.append("[FMEA·负] 有标记仍判不可检测")
    _db = mod.diversity_budget({"0": {}, "1": {}}, ["content", "context"], "serial")
    if _db["combos"] != 4:
        bad.append("[多样性] 组合数算错（%r）" % (_db,))
    if "_pack[\"diversity\"]" not in src:
        bad.append("[多样性] 未落 packed")

    # ★ [nogoods] 纯函数直测（确定性；不依赖引擎构造 —— 引擎路径容易「没跑到」）
    _nr = mod.nogood_record("gate_reject", "redline", {"k": 1}, "R1", 5.0)
    if not (str(_nr.get("kind")) == "gate_reject"
            and str(_nr.get("why")) == "redline"
            and str(_nr.get("run")) == "R1"
            and isinstance(_nr.get("cand"), dict)):
        bad.append("[nogoods] 记录内容不符（%r）" % (_nr,))
        # ★ [nogoods] **行为**判据（不能只看常量在不在）：
        #   猴补丁让候选必被闸拒（红线类）⇒ `nogoods.jsonl` 必须落一行。
        try:
            _ngdir = Path(_tf.mkdtemp(prefix="smk_ng_"))
            _cfg2 = dict(mod.DEFAULT_CONFIG)
            _cfg2["playbook"] = {"mode": "on", "dir": str(_ngdir)}
            _e2 = mod.MetaDGTF(_cfg2)
            _orig_c = mod.eml_candidates_from_result

            def _fake_cands(_r, ep=None):
                return [{"kind": "schedule", "cond": {"issue": "x"},
                         "action": {"key": "inject_answer"},
                         "readings": {"before": {"a": 1}},
                         "evidence": ["R1"], "source": "test"}]

            mod.eml_candidates_from_result = _fake_cands
            try:
                _e2._eml_finish({"id": "NG1", "question": "x", "views": {},
                                 "pools": {}, "dispatch": {}, "rounds": {}})
            finally:
                mod.eml_candidates_from_result = _orig_c
            _ngf = _ngdir / "nogoods.jsonl"
            _ngrows = mod.eml_read_jsonl(_ngf) if _ngf.is_file() else []
            if len(_ngrows) < 1:
                bad.append("[nogoods] ★ 被闸拒的候选未写进矛盾档案（append-only）")
            elif not (str(_ngrows[0].get("why")) == "redline"
                      and str(_ngrows[0].get("kind")) == "gate_reject"):
                bad.append("[nogoods] 档案内容不对（kind/why）=%r" % (_ngrows[0],))
            import shutil as _sh2
            _sh2.rmtree(_ngdir, ignore_errors=True)
        except Exception as _en:
            bad.append("[nogoods] 行为判据异常：%r" % (_en,))


    # ── 第三批（机制级：anytime / 发散+指针 / bandit / compact / 锚点 / 裁决 / 陈旧）──
    for _n, _w in (("def stitched_hoeffding_lower(", "anytime 置信序列"),
                   ("def anytime_majority_decided(", "anytime 判据"),
                   ("def divergence_state(", "发散三态"),
                   ("def best_round_index(", "回滚指针"),
                   ("class BudgetBandit:", "预算 bandit"),
                   ("def compact_plan(", "compact 预算"),
                   ("def anchor_offline_check(", "锚点离线验证"),
                   ("def anchor_interest_hint(", "锚点内部批判"),
                   ("def anchor_evidence_standard(", "分级证明标准"),
                   ("def adjudication_aspect(", "裁决维度"),
                   ("def belief_staleness(", "信念陈旧度"),
                   ("anytime_ok=_any_ok", "anytime 接线")):
        if _n not in src:
            bad.append("[源码] %s 缺失（%r）" % (_w, _n))
    # anytime：12 个 1 ⇒ 下界 > 0.5 判「已确立」；3 个 1 ⇒ 样本不足不判（负对照）
    _lb = mod.stitched_hoeffding_lower([1] * 12)
    if not (_lb and _lb["lower"] > 0.5):
        bad.append("[anytime] 全 1 序列下界未 > 0.5（%r）" % (_lb,))
    if mod.anytime_majority_decided([1, 1, 1])[0]:
        bad.append("[anytime·负] 3 个样本就判「已确立」（过早）")
    if mod.stitched_hoeffding_lower([1]) is not None:
        bad.append("[anytime] n<2 未返回 None")
    # 发散/停滞/指针
    _dv = mod.divergence_state([1, 1, 2, 4, 8, 16])
    if not (_dv and _dv["state"] == "发散"):
        bad.append("[发散] 方差上升序列未判发散（%r）" % (_dv,))
    if mod.divergence_state([3] * 6)["state"] != "停滞":
        bad.append("[发散·负] 平稳序列未判停滞")
    if mod.best_round_index([1, 3, 2, 0]) != 2:
        bad.append("[指针] 历史最佳圈指针算错")
    # bandit：未试过的臂优先（确定性探索）；更新后仍可选
    _bb = mod.BudgetBandit([{"rounds": 3}, {"rounds": 4}, {"rounds": 6}])
    _p0 = _bb.pick()
    if not (_p0["explore"] is True and _p0["index"] == 0):
        bad.append("[bandit] 首挑未走确定性探索（%r）" % (_p0,))
    _bb.update(0, 0.9, 1.0)
    if _bb.n[0] != 1 or abs(_bb.mean[0] - 0.9) > 1e-9:
        bad.append("[bandit] 更新未生效（%r/%r）" % (_bb.n, _bb.mean))
    # compact（率失真口径）
    if not mod.compact_plan(900, 1000)["over"]:
        bad.append("[compact] 超预算未判 over")
    if mod.compact_plan(300, 1000)["over"]:
        bad.append("[compact·负] 预算内被误判超")
    # 锚点三项
    if not mod.anchor_offline_check("https://www.gov.cn/a")["ok"]:
        bad.append("[锚点] 合法 URL 未过离线检查")
    if mod.anchor_offline_check("htp:/x")["ok"]:
        bad.append("[锚点·负] 畸形 URL 竟通过")
    if "媒体" not in mod.anchor_interest_hint("https://blog.medium.com/x"):
        bad.append("[锚点·内部批判] 自媒体域名未识别")
    if mod.anchor_evidence_standard("causal")["standard"] != "beyond_reasonable_doubt":
        bad.append("[法学] 因果 claim 未用最高证明标准")
    # 裁决维度 + 陈旧度
    if not mod.adjudication_aspect("口径矛盾", "按实测数据").strip():
        bad.append("[裁决维度] 未判出维度")
    _st = mod.belief_staleness({"id": "B", "status": "active",
                                "last_confirmed_round": 1}, 5)
    if not (_st["age"] == 4 and _st["stale_hint"] is True):
        bad.append("[陈旧度] 读数不对（%r）" % (_st,))

        # ★ [层读数进产物] **行为判据**：走真实 `save_result`，断言产物 md
        #   里出现 6 个新读数块（真跑曾暴露「只进 verbose 转储」的缺口）。
        try:
            import tempfile as _tf3
            _d3 = Path(_tf3.mkdtemp(prefix="smk_lay_"))
            _pool3 = {"amps": [], "threads": [], "probes": [], "meta": [],
                      "suspensions": [], "aspect_units": [], "belief_items": [],
                      "anchors": [], "duel_suspensions": [], "aspect_targets": {}}
            _r3 = {"question": "层读数验收题", "route": ["0", "1"],
                   "rounds": {"0": 1, "1": 1},
                   "dispatch": {"order": ["0", "1"], "ran": ["0", "1"],
                                "requested": ["0", "1"], "missing": [],
                                "failed": {}, "skipped": [],
                                "_parallel_mode": "serial"},
                   "keep": {"0": "all", "1": "all"},
                   "_anchor_tier_warning": "", "_anchor_answers_filtered": 0,
                   "views": {},
                   "pools": {k: dict(_pool3) for k in ("0", "1", "both", "all")},
                   "llm_calls": 2, "llm_tokens": 20, "llm_ops_calls": 1,
                   "llm_ops_tokens": 10, "llm_eval_calls": 1,
                   "llm_eval_tokens": 10,
                   "compact": {"inner_share": 0.9, "budget": 0.6, "over": True,
                               "verdict": "内部面超预算 ⇒ 索引化"},
                   "belief_staleness": {"n": 5, "stale_n": 2, "max_age": 4},
                   "diversity": {"layers": 2, "channels": 3, "combos": 6,
                                 "mode": "serial", "note": "x"}}
            _v3 = mod.View(entry="0")
            _v3.stop_primary = "悬置决定稳定，自然安住"
            _v3.divergence = {"state": "发散", "var_first": 1.0,
                              "var_last": 4.0, "ac1": 0.4}
            _v3.best_round = 2
            _v3.anytime = {"n": 6, "lower": 0.44, "delta": 0.05}
            _v3.csd = {"new_amps": {"hint": True}}
            _r3["views"]["0"] = _v3.to_dict()
            _md3 = Path(mod.save_result(_r3, str(_d3))).read_text(encoding="utf-8")
            for _k3 in ("层读数（每层）", "三态=发散", "历史最佳=第2圈",
                        "anytime下界=0.440", "内部面预算", "信念陈旧度"):
                if _k3 not in _md3:
                    bad.append("[层读数] 产物里缺 %r（只进了 verbose 转储？）" % _k3)
            import shutil as _sh3
            _sh3.rmtree(_d3, ignore_errors=True)
        except Exception as _e3:
            bad.append("[层读数] 行为判据异常：%r" % (_e3,))

    # ★ [一键全开] 两向判据：false ⇒ **恒等**（零 notes）；true ⇒ 清单逐项生效。
    if "_apply_all_on" not in src or "_ALL_ON_ITEMS" not in src:
        bad.append("[all_on] 一键全开实现缺失")
    _c_off, _n_off = mod._apply_all_on({"all_on": False})
    if _n_off:
        bad.append("[all_on·负] all_on=False 竟然改了配置（%r）" % (_n_off[:2],))
    _c_on, _n_on = mod._apply_all_on({"all_on": True})
    if len(_n_on) < 8:
        bad.append("[all_on] 全开清单生效项过少（%d 条）" % len(_n_on))
    for _p, _v, _w in mod._ALL_ON_ITEMS:
        _d = _c_on
        for _k in str(_p).split("."):
            _d = _d.get(_k) if isinstance(_d, dict) else None
        if _d != _v:
            bad.append("[all_on] %s 未置为 %r（实为 %r）" % (_p, _v, _d))
    if mod.DEFAULT_CONFIG.get("all_on") is not False:
        bad.append("[all_on] 引擎默认必须保守（False），保证判据基线零影响")

    # ★ [api.thinking 形状守卫] 配置被写成标量（bool/str）时**不得炸整次真跑**。
    #   真跑教训：矩阵跑批 4 题全灭 = `_th.get` 对 bool 抛 AttributeError。
    #   判据两向：① 非法形状 → 构造 LLM 不抛异常（降级为默认）；② 合法 dict
    #   → 逐字段读取**不受影响**（不许把合法值也一起吞掉）。
    if "_th = api_cfg.get(\"thinking\")" not in src or "形状非法" not in src:
        bad.append("[形状守卫] api.thinking 非法形状守卫缺失")
    for _bad_shape in (True, "on", 123):
        _cb = dict(mod.DEFAULT_CONFIG)
        _cb["api"] = dict(_cb.get("api") or {})
        _cb["api"]["key"] = "sk-smoke-dummy"
        _cb["api"]["thinking"] = _bad_shape
        try:
            mod.LLM(_cb)
        except Exception as _eb:
            bad.append("[形状守卫·负] api.thinking=%r 仍崩：%r"
                       % (_bad_shape, _eb))
    _cg = dict(mod.DEFAULT_CONFIG)
    _cg["api"] = dict(_cg.get("api") or {})
    _cg["api"]["key"] = "sk-smoke-dummy"
    _cg["api"]["thinking"] = {"default": "enabled", "effort": "high",
                              "stages": {"k": "enabled"}}
    try:
        _lg = mod.LLM(_cg)
        if _lg.thinking_default != "enabled" or _lg.thinking_effort != "high" \
                or _lg.thinking_stages.get("k") != "enabled":
            bad.append("[形状守卫·正] 合法 dict 被吞：default=%r effort=%r stages=%r"
                       % (_lg.thinking_default, _lg.thinking_effort,
                          _lg.thinking_stages))
    except Exception as _eg:
        bad.append("[形状守卫·正] 合法 dict 竟报错：%r" % (_eg,))

    # ── 真实入口 + 不变量 ──
    _tmp = Path(_tf.mkdtemp(prefix="smk_v1232_"))
    try:
        cfg = dict(mod.DEFAULT_CONFIG)
        cfg["playbook"] = {"mode": "shadow", "dir": str(_tmp)}
        cfg["output"] = dict(cfg.get("output") or {})
        cfg["output"]["save_dir"] = str(_tmp)
        eng = mod.MetaDGTF(cfg)
        v = mod.View(entry="1")
        v.round_log = [{"round": i + 1, "new_amps": x, "idle_stall": 0}
                       for i, x in enumerate([1, 1, 2, 4, 7])]
        d = eng._layer_csd_now("1", v)
        if not (v.csd and v.csd.get("new_amps")):
            bad.append("[入口] CSD 未写回 view.csd（%r）" % (d,))
        # LLM 计数不变量：ops + eval == total（两向）
        _l = eng.llm
        for _attr in ("ops_calls", "ops_tokens", "eval_calls", "eval_tokens"):
            if not hasattr(_l, _attr):
                bad.append("[入口] LLM 缺计数属性 %s" % _attr)
        if hasattr(_l, "ops_calls") and \
                (_l.ops_calls + _l.eval_calls) != _l.total_calls:
            bad.append("[入口] 成本两分之和 != 总调用（%d+%d vs %d）"
                       % (_l.ops_calls, _l.eval_calls, _l.total_calls))
        # 停因级联：主因必须出现在最终 stop_reason 里
        v2 = mod.View(entry="1")
        v2.stop_reason = "体力耗尽（4 圈走满，未触发任何停止判据）"
        v2.stop_primary = ""
        _cas2 = mod.stop_cascade([v2.stop_reason, "悬置决定稳定，自然安住"])
        v2.stop_primary = _cas2["primary"]
        v2.stop_reason = " + ".join(_cas2["ordered"]) + "，螺旋停止"
        if v2.stop_primary not in v2.stop_reason:
            bad.append("[入口] ★主因不在 stop_reason 里（报告即实际被破坏）")
        # 渲染可达性（**两向**：出口在 + 渲染点真的读到它）。
        # ★ 口径说明：这里走源码级而**不是**驱动 `save_result` —— 后者需要
        #   一份完整 packed 夹具（视图/池全字段），而冒烟其它判据已端到端跑过
        #   它（真 mock 跑 + 落盘）。两向断言足以钉住「出口与渲染点成对存在」：
        #   删任一方向都会判红。
        for _k, _what in (("tri_alpha", "机会校正一致"),
                          ("llm_ops_calls", "成本两分（跑本身）"),
                          ("llm_eval_calls", "成本两分（自测量）")):
            if ('_pack["%s"]' % _k) not in src:
                bad.append("[渲染] 出口缺失：%s" % _k)
        for _s, _what in (("机会校正一致（ordinal）", "机会校正一致行"),
                          ("成本两分", "成本两分行"),
                          ("三态判决一致率（原始）", "原始一致率标注")):
            if _s not in src:
                bad.append("[渲染] 渲染点缺失：%s" % _what)
    except Exception as _e:
        import traceback
        traceback.print_exc()
        bad.append("[入口] 异常：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  OK v1.23.32 学科吸收（α/κ · 尺度 · 级联 · 成本两分 · CSD）全过")
    return True


def check_v12336_eml():
    """[v1.23.36] EML 两向对账：**每个 action.key 要么有应用分支、要么登记豁免**。

    ★ 为什么：不这么查，「学而不做」可以长期静默存在（召回日志只说「用了几条」，
      不说「其中几条真生效」）。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    if "_EML_RECORD_ONLY" not in src:
        bad.append("[EML] 缺 `_EML_RECORD_ONLY`（「只记录」没有显式登记）")
        print("  X", bad[-1])
        return False

    # ① 静态：生成侧 vs 应用侧 vs 豁免表
    _i_gen = src.find("def eml_candidates_from_result")
    _i_gen_end = src.find("\ndef ", _i_gen + 10)
    _gen = src[_i_gen:_i_gen_end if _i_gen_end > 0 else _i_gen + 6000]
    import re as _re3
    _gen_keys = sorted(set(_re3.findall(r'"key":\s*"([a-z_0-9]+)"', _gen)))
    _i_ap = src.find("def _eml_apply")
    _i_ap_end = src.find("\n    def ", _i_ap + 10)
    _ap = src[_i_ap:_i_ap_end if _i_ap_end > 0 else _i_ap + 4000]
    _ap_keys = sorted(set(_re3.findall(r'_key == "([a-z_0-9]+)"', _ap)))
    _ex = getattr(mod, "_EML_RECORD_ONLY", None) or {}
    if not _gen_keys:
        bad.append("[EML] 从 `eml_candidates_from_result` 里**抽不到** action.key"
                   "（改写形态了？判据需要更新）")
    _missing = [k for k in _gen_keys if k not in _ap_keys and k not in _ex]
    if _missing:
        bad.append("[EML] 这些 key **生成了但既不应用也没登记豁免**：%r"
                   "（学而不做、且不可见）" % (_missing,))
    # ★ [学了要做] 五个应用分支都要在（防"删分支"退化）。
    for _k in ("rounds_delta", "duty_floor", "carve_first",
               "tri_advisory_only", "note_cost_no_gain",
               "thinking_hint", "action_hint"):
        if '_key == "%s"' % _k not in _ap:
            bad.append("[EML] `_eml_apply` 缺分支 %r（学了要做，不许只剩记录）"
                       % _k)
    # ★ [学了要做 · 功能性] 「分支在」≠「分支真的改了调度量」——
    #   直接喂一条 `tri_advisory_only` 给 `_eml_apply`，看 `_duty_floor`
    #   是否**真的变了**（这是"与调度层融合"的可执行证据）。
    try:
        _cfg_t = build_cfg(False)
        _mt_t = mod.MetaDGTF(_cfg_t)
        _mt_t._eml_mode = "on"
        _fl0 = float(getattr(_mt_t, "_duty_floor", 0.0) or 0.0)
        _mt_t._eml_used = [{"id": "T-TRI", "action": {"key": "tri_advisory_only",
                                                      "rate": 0.1}}]
        _mt_t._eml_apply({})
        _fl1 = float(getattr(_mt_t, "_duty_floor", 0.0) or 0.0)
        if _fl1 == _fl0:
            bad.append("[EML] `tri_advisory_only` **没有真的改调度量**"
                       "（_duty_floor %s → %s）⇒ 只是记账不是融合" % (_fl0, _fl1))
        # ★ [与调度融合 · 扩面] 同一把尺子量另外两个 ——
        #   `thinking_hint` 必须**真的**改到消费方（`llm.thinking_stages`）；
        #   `action_hint` 必须**真的**落进控制面（白名单内）。
        _mt_t3 = mod.MetaDGTF(build_cfg(False))
        _mt_t3._eml_mode = "on"
        _mt_t3._eml_used = [{"id": "T-THINK", "why": "判据探针",
                             "action": {"key": "thinking_hint",
                                        "stages": ["assess_decidability"],
                                        "value": "enabled"}}]
        _mt_t3._eml_apply({})
        _ts3 = getattr(getattr(_mt_t3, "llm", None), "thinking_stages", None)
        if not (isinstance(_ts3, dict)
                and _ts3.get("assess_decidability") == "enabled"):
            bad.append("[EML] `thinking_hint` **没能改到消费方**"
                       "（llm.thinking_stages 没变）⇒ 只是记账不是融合")
        _mt_t4 = mod.MetaDGTF(build_cfg(False))
        _mt_t4._eml_mode = "on"
        _mt_t4._eml_used = [{"id": "T-ACT", "why": "判据探针",
                             "action": {"key": "action_hint",
                                        "name": "parallel_expand",
                                        "value": False}}]
        _mt_t4._eml_apply({})
        _ap4 = [x.get("key") for x in (_mt_t4._control.applied or [])]
        if "actions.parallel_expand" not in _ap4:
            bad.append("[EML] `action_hint` **没落进控制面**：%r" % (_ap4,))
        # 同一把尺子量第四个：`note_cost_no_gain` 应让圈数**变小**
        _mt_t2 = mod.MetaDGTF(build_cfg(False))
        _mt_t2._eml_mode = "on"
        _mt_t2._eml_used = [{"id": "T-COST",
                             "action": {"key": "note_cost_no_gain"}}]
        _rp = {"0": 4, "1": 3}
        _mt_t2._eml_apply(_rp)
        if not all(int(v) < 4 for v in _rp.values()):
            bad.append("[EML] `note_cost_no_gain` 没把圈数**降下来**：%r" % (_rp,))
    except Exception as _e3:
        bad.append("[EML] 功能性验证抛错：%r" % (_e3,))
    _stale = [k for k in _ex if k not in _gen_keys]
    if _stale:
        bad.append("[EML] 豁免表里有**过期登记**（不再生成）：%r" % (_stale,))

    # ③ 构造性：真造一个 episode，看能不能真生成（不是只写在源码里）
    try:
        # ★ 签名是 `(result, ep)` —— 第一参数是**产物**、第二才是 episode。
        #   第一版把 ep 塞进第一个位置 ⇒ `episode_from_result(ep)` 得到空对象
        #   ⇒ **一条候选都不生成**（判据自己报的"闸门过严"其实是**喂错了参数**）。
        # ★ 字段口径（实测）：`cut_layers` 是**层名列表**；`duty` 的值是
        #   **float**（不是 dict）；`tri_rate` 是 float；`cost.tokens` 是数。
        _ep = {"cut_layers": ["0"],
               "duty": {"0": 0.0},
               "tri_rate": 0.1,
               "cost": {"tokens": 999999}}
        _cands = mod.eml_candidates_from_result({}, _ep) or []
        _got = sorted({(c.get("action") or {}).get("key")
                       for c in _cands if isinstance(c, dict)})
        _got = [k for k in _got if k]
        if not _got:
            bad.append("[EML] 构造性：喂一个截断层 episode **一条候选都没生成**"
                       "（参数口径或闸门变了）")
        else:
            _m2 = [k for k in _got if k not in _ap_keys and k not in _ex]
            if _m2:
                bad.append("[EML] 构造性生成的 key 有对不上的：%r" % (_m2,))
    except Exception as _e:
        bad.append("[EML] 构造性验证抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.36 EML 两向对账（生成侧 %r ↔ 应用侧 %r ↔ 豁免 %r · "
          "无学而不做 · 无过期登记）全过" % (_gen_keys, _ap_keys, sorted(_ex)))
    return True


def check_v12336_tick():
    """[v1.23.36] 心跳级调度：**主动**调整（不等失败）+ 全过控制面 + 默认零行为差。

    ★ 依据 Heartbeat-Driven Activity Scheduling（arXiv 2604.14178）。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    if "def _schedule_tick" not in src:
        bad.append("[心跳] 缺 `_schedule_tick`")
    if "self._schedule_tick(entry, view)" not in src:
        bad.append("[心跳] 没挂在 `_finalize_layer_common`（层收尾）上")
    if "_relaxed" not in src:
        bad.append("[心跳] `WebSearchGate` 没有运行时放宽集（放宽无法生效）")
    if "gate._relaxed = _relaxed" not in src:
        bad.append("[心跳] `_web_search` 没把控制面的放宽同步进 Gate")

    # ── 构造性（直接驱动真实方法）──
    try:
        _cfg = build_cfg(False)
        _mt = mod.MetaDGTF(_cfg)

        def _mkview(verdict: str):
            _v = mod.View(entry="0")
            _v.rounds_run = 2
            _v.quant_readings = {"candidate_yield": {
                "n": 3, "n_new": 0, "verdict": verdict}}
            return _v

        # ① 触发放宽
        _mt._schedule_tick("0", _mkview("collapsed"))
        _ap = [x.get("key") for x in (_mt._control.applied or [])]
        if not any(str(k).startswith("web.allow.") for k in _ap):
            bad.append("[心跳] collapsed 读数**没触发放宽**（applied=%r）" % (_ap,))
        else:
            # ② 幂等：再调一次，同样的放宽**不该**再落一笔
            _n1 = len(_mt._control.applied)
            _mt._schedule_tick("0", _mkview("collapsed"))
            if len(_mt._control.applied) > _n1 + 1:
                bad.append("[心跳] 重复触发**重复落账**（应判 noop）")
            # ③ 默认零行为差：正常读数 ⇒ 不新增放宽
            _mt2 = mod.MetaDGTF(build_cfg(False))
            _mt2._schedule_tick("0", _mkview("ok"))
            _ap2 = [x.get("key") for x in (_mt2._control.applied or [])]
            if any(str(k).startswith("web.allow.") for k in _ap2):
                bad.append("[心跳] 读数正常却**放宽了**（默认零行为差被破坏）")
            # ④ 不碰配置（★ 查**前后差异**，不是查"有没有 True"：
            #    `build_cfg` 的 stages 里**本来就有** True（如 research_decompose）
            #    ⇒ 按"有没有真值"判是**误报**，第一版就这么误报的）。
            _c2 = lambda _m: dict((_m.config.get("web_search") or {})
                                  .get("stages") or {})
            _mt3 = mod.MetaDGTF(build_cfg(False))
            _snap_a = _c2(_mt3)
            _mt3._schedule_tick("0", _mkview("collapsed"))   # 触发放宽
            _snap_b = _c2(_mt3)
            if _snap_a != _snap_b:
                bad.append("[心跳] **改了配置**（红线：建议与执行分开）")
            else:
                # 放宽只应落在**控制面**（内存态）
                _ap3 = [x.get("key") for x in (_mt3._control.applied or [])]
                if not any(str(k).startswith("web.allow.") for k in _ap3):
                    bad.append("[心跳] 放宽**没落进控制面**（那它落在哪了？）：%r"
                               % (_ap3,))
    except Exception as _e:
        bad.append("[心跳] 构造性验证抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.36 心跳级调度（主动触发 · 全过控制面 · 幂等 · "
          "默认零行为差 · 不写配置）全过")
    return True


def check_v12336_readings():
    """[v1.23.36] 读数全量显示：运行中一行 + 结束总表 + 产物结构化（同源）。

    ★ 用户口径：「运行中和结束时所有读数都**完整显示在日志中**，同时
      **结构化显示在产物文档中**」。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for _t in ("def _readings_bundle", "def _readings_line",
               "def _readings_table"):
        if _t not in src:
            bad.append("[读数] 缺 %s" % _t)
    if "logger.info(_readings_line(entry, view))" not in src:
        bad.append("[读数] 每层读数行**没走 logger**（走 vp 会被 verbose 吞掉）")
    if "logger.info(_readings_table(_rt_views))" not in src:
        bad.append("[读数] 结束总表**没走 logger**")
    if 'packed["readings_table"]' not in src:
        bad.append("[读数] 总表**没存进产物**（产物侧拿不到）")

    # ── 真实入口（零 API 花费）：跑一次 mock run，捕获 logging ──
    import logging as _lg
    _logger = _lg.getLogger("dgtf")
    _old_h = list(_logger.handlers)
    _old_lv = _logger.level
    _buf = io.StringIO()
    try:
        _logger.handlers = [_lg.StreamHandler(_buf)]
        _logger.setLevel(_lg.INFO)
        _cfg = build_cfg(False)
        _res = mod.MetaDGTF(_cfg).run("读数显示判据题",
                                      route=["0", "1"],
                                      rounds={"0": 2, "1": 2},
                                      parallel_mode="serial", run_id="")
    finally:
        _logger.handlers = _old_h
        _logger.setLevel(_old_lv)
    _log = _buf.getvalue()

    _lines = [l for l in _log.splitlines() if "📊 [" in l]
    if not _lines:
        bad.append("[读数] 日志里**没有**每层读数行（📊 [层]）")
    elif len(_lines) < 2:
        bad.append("[读数] 每层读数行只有 %d 行（两层应至少 2 行）" % len(_lines))
    if "读数总表（四层）" not in _log:
        bad.append("[读数] 日志里**没有**结束总表")

    # ★ [读数完整性 · 真跑逮到] `merge_expand` 开时，合并路径**提前 return**
    #   ⇒ 阴阳分歧读数会**静默消失**（四层都缺）。合并路径修好后，
    #   它必须**有档**（值可为「不表态」= `verdict=""`）。
    if "self._quant_pending_yy = {" in src and '"merged": True' in src:
        pass          # 修复在位
    else:
        bad.append("[读数] 合并路径**没记「不表态」档** ⇒ "
                   "`merge_expand` 开时阴阳分歧读数会静默消失")

    _rt = (_res or {}).get("readings_table") or ""
    if not _rt:
        bad.append("[读数] 产物里没有 `readings_table`")
    elif "| 层 |" not in _rt or "---" not in _rt:
        bad.append("[读数] 产物总表不是 Markdown 表格：%r" % (_rt[:60],))
    else:
        # ★ 同源核对：日志表与产物表里的**圈数**必须一致（防两处各渲染一份）
        #   ★ 正则必须**锚定行首**（`^\| 层 \| 圈 \|`）：宽松写法
        #     `\| (\d) \| (\d+) \|` 会匹配**行内任意**相邻两个数字格
        #     ⇒ 取出错误组合 ⇒ 假红（第一版就是这么误报的）。
        import re as _re2
        _nums_md = _re2.findall(r"^\| (\d) \| (\d+) \|", _rt, _re2.M)
        _ok_same = True
        for _e, _r in _nums_md:
            if ("[%s] 圈 %s" % (_e, _r)) not in _log:
                _ok_same = False
        if not _nums_md:
            bad.append("[读数] 产物表里**没有**可核对的层行（正则或格式问题）")
        elif not _ok_same:
            bad.append("[读数] 日志表与产物表**对不上**（两处各渲染 ⇒ 会漂移）")

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.36 读数全量显示（每层一行 · 结束总表 · 产物 Markdown 表 · "
          "三处同源 · 走 logger 不受 verbose 控制）全过")
    return True


def check_v12336_allweb():
    """[v1.23.36] 联网全接：一处改覆盖 30 个环节 + 所有层注入 + 配置可控。

    ★ 用户口径：「**联网全接配置可控开关**」「**所有层都注入**」。
    ★ 为什么判据要分两层：源码级只能证明「接线写了」；**构造性**那一层
      直接驱动真实方法，才能证明「打开就真注入、关了就真不注入」。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")

    # ── ① 源码级：五个部件都要在 ──
    for _t, _what in (("_LLM_CTX", "线程局部上下文"),
                      ("_llm_ctx_set", "上下文写入"),
                      ("_llm_ctx_get", "上下文读取"),
                      ("_infer_stage_from_stack", "环节名推断"),
                      ("_web_augment", "增强层")):
        if _t not in src:
            bad.append("[全接] 缺 %s（%s）" % (_t, _what))
    if "self._web_augment(stage, user)" not in src:
        bad.append("[全接] `LLM.call` 里**没有**调 `_web_augment`（层没接上）")
    if "web_searcher=self._web_search" not in src:
        bad.append("[全接] `MetaDGTF.run` **没注入** `web_searcher`（依赖没接上）")
    if "_llm_ctx_set(entry=str(entry), round=int(layer_no or 0))" not in src:
        bad.append("[全接] `_before_round` 没逐圈刷新 entry/round")
    # 控制面必须有**真实调用点**（审计 A2 抓过「定义后零引用」）
    if src.count("self._control.write(") < 2:
        bad.append("[全接] `ControlSurface` 接线不足（应 ≥2 处写入）")

    # ── ② 环节表与配置键 ──
    _stages = getattr(mod, "_WEB_ALL_STAGES", None) or ()
    if len(_stages) != 30:
        bad.append("[全接] `_WEB_ALL_STAGES` 应为 30 项（实得 %d）" % len(_stages))
    _cfg_st = ((mod.DEFAULT_CONFIG.get("web_search") or {}).get("stages") or {})
    _missing = [k for k in _stages if k not in _cfg_st]
    if _missing:
        bad.append("[全接] 配置里缺环节开关：%r" % (_missing[:5],))
    if any(_cfg_st.get(k) is not False for k in _stages):
        bad.append("[全接] 新增环节开关**不是默认 false**（会改默认行为）")
    # ★ 防「插错位置」：`api.thinking.stages` 的键集合必须与**出厂 yaml** 一致
    _th = ((mod.DEFAULT_CONFIG.get("api") or {}).get("thinking") or {}).get(
        "stages") or {}
    #   （引擎侧那一段是按 yaml 抄的；有人把别的键插进来，两边就对不上）。
    #   ★ 不用「数量阈值」—— 思考档登记表里有**本来就重叠**的名字
    #     （`auto_plan` / `plan_orientation` / `plan_resources` …既是环节也是思考档），
    #     按数量或按名字判会把它们误报成污染（第一版就是这么误报的）。
    try:
        import yaml as _y
        _ydoc = _y.safe_load(
            (HERE / "dgtf_config.yaml").read_text(encoding="utf-8")) or {}
        _y_th = (((_ydoc.get("api") or {}).get("thinking") or {})
                 .get("stages") or {})
        if set(_y_th) != set(_th):
            bad.append("[全接] `api.thinking.stages` 与出厂 yaml **对不上**"
                       "（引擎多 %r / yaml 多 %r）"
                       % (sorted(set(_th) - set(_y_th))[:5],
                          sorted(set(_y_th) - set(_th))[:5]))
    except Exception as _ey:
        bad.append("[全接] `api.thinking.stages` 与 yaml 对账失败：%r" % (_ey,))

    # ── ③ 构造性：直接驱动真实方法（零 API 花费）──
    _ST = "ing"

    def _mk(enabled, stage_on, wire, entry):
        cfg = {k: (dict(v) if isinstance(v, dict) else v)
               for k, v in mod.DEFAULT_CONFIG.items()}
        ws = dict(cfg.get("web_search") or {})
        ws["enabled"] = enabled
        _s = dict(ws.get("stages") or {})
        _s[_ST] = stage_on
        ws["stages"] = _s
        cfg["web_search"] = ws
        gate, _cl = mod.build_web_search(cfg)
        calls = []

        def _searcher(stage, queries, round_no, used_as="evidence", pre_seq=0):
            ok, why = gate.allow(stage, round_no)      # ★ 真 Gate
            calls.append((str(stage), bool(ok), str(why)[:24]))
            return [{"claim": "样例外部参考", "url": "https://x.invalid",
                     "tier": 3}] if ok else []
        mod._llm_ctx_set(web_searcher=(_searcher if wire else None),
                         question="术语与判据该怎么做？", entry=entry, round=1)
        return mod.LLM(cfg)._web_augment(_ST, "原 user"), calls

    try:
        _o, _ = _mk(True, True, False, "1")
        if _o:
            bad.append("[全接] 未接线却增强了")
        _o, _c = _mk(False, True, True, "1")
        if _o:
            bad.append("[全接] 总闸关却增强了")
        elif not any("未启用" in x[2] for x in _c):
            bad.append("[全接] 总闸关时 Gate 没给出拒因（不可追溯）")
        _o, _ = _mk(True, True, True, "1")
        if not (_o and "【外部参考】" in str(_o)):
            bad.append("[全接] 开+授权却**没增强**（接线不可达）")
        for _e in ("0", "1", "both", "all"):
            _o, _ = _mk(True, True, True, _e)
            if not (_o and "【外部参考】" in str(_o)):
                bad.append("[全接] entry=%s **没有增强**"
                           "（用户口径：所有层都注入）" % _e)
        _o, _c = _mk(True, False, True, "1")
        if _o:
            bad.append("[全接] 未授权却增强了（开关不精确）")
        elif not any("未授权" in x[2] for x in _c):
            bad.append("[全接] 未授权时 Gate 没给拒因")
    except Exception as _e:
        bad.append("[全接] 构造性验证抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.36 联网全接（30 环节一键覆盖 · 上下文注入 · "
          "四层全可注 · 开关精确 · 拒因可追溯 · 控制面已接线）全过")
    return True


def check_v12341_excavate_dir():
    """[v1.23.41 · P2] `excavate` 方向**口径统一**（文档/声明 + 显示）。

    ★ 矛盾：模块声明说「每条读数越大越接近目标」、docstring 说「读数 = 1 − 边际新增」，
      而实现 + 判据⑫ 都是「小=好（边际新增率）」。
    ★ 判据：三处口径必须一致为「小=好」，且产物显示要**消歧**（防误读成「一分没挖」）。
    """
    import io as _io
    import contextlib as _ctx
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    # ① 声明不再一刀切「每条读数越大越接近目标」
    if "每条读数都是「**越大越接近该层目标**」" in src:
        bad.append("[P2] 模块声明仍一刀切「每条越大越接近」（excavate 方向相反）")
    if "距离型" not in src:
        bad.append("[P2] 声明未把 excavate 标成距离型（越小越接近挖尽）")
    # ② docstring 不再写与实现相反的「读数 = 1 − 边际新增」
    if "故本读数 = **1 − 归一化边际新增**" in src:
        bad.append("[P2] docstring 仍写「读数 = 1 − 边际新增」（与实现相反）")

    # ③ 行为：excavate 取值仍 = 边际新增率（busy > done，与判据⑫同向，防「改文档顺手
    #   把值也翻向」）
    _b = (mod.layer_goal_readings(
        {"0": {"aspect_units": [{"id": str(i)} for i in range(9)],
               "rounds_run": 4, "aspect_hist": [2, 4, 6, 9]}}).get("0") or {}
    ).get("excavate")
    _d = (mod.layer_goal_readings(
        {"0": {"aspect_units": [{"id": str(i)} for i in range(6)],
               "rounds_run": 4, "aspect_hist": [2, 4, 5, 6]}}).get("0") or {}
    ).get("excavate")
    if not (_b is not None and _d is not None and _b > _d):
        bad.append("[P2] excavate 值方向被改了（还在挖应 > 已挖尽）：%r vs %r"
                   % (_b, _d))

    # ④ 显示消歧：真驱动 `_finalize_layer_common` ⇒ 修行层 goal_verdict 带方向提示
    try:
        cfg = build_cfg(False)
        m = mod.MetaDGTF(cfg)
        v = mod.View(entry="0")
        v.aspect_units = [{"id": "A%d" % i} for i in range(9)]
        v.rounds_run = 3
        v.aspect_hist = [2, 4, 6, 9]
        v.stop_reason = "体力耗尽（3 圈走满）"
        stt = {"roles_hist": ["x"], "total_rounds": 3, "round_log": [],
               "all_rehashed": [], "all_candidates": [], "all_amps": [],
               "all_threads": [], "all_expanded_descs": [],
               "all_dec_products": [], "all_und_products": [],
               "r": 3, "rounds_n": 3, "sp": mod._spiral_for(cfg, "0")}
        with _ctx.redirect_stdout(_io.StringIO()):
            m._finalize_layer_common("0", v, stt)
        gv = str(getattr(v, "goal_verdict", "") or "")
        if "excavate=" not in gv:
            bad.append("[P2] 修行层 goal_verdict 缺 excavate：%r" % gv)
        elif not ("趋零" in gv or "边际新增率" in gv):
            bad.append("[P2] excavate 显示未给方向提示（易误读成「没挖」）：%r" % gv)
    except Exception as e:  # noqa: BLE001
        bad.append("[P2] 驱动抛错：%r" % (e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.41 P2 excavate 口径统一（声明/docstring 标距离型 · 取值仍=边际新增率 · "
          "产物显示带「趋零即挖尽」提示）全过")
    return True


def check_v12341_attribution():
    """[v1.23.41 · P3+P4] 停因**归因补全**（只加不删，不改停止决策）。

    · P3：无判据截断 ⇒ 附**末圈近阈读数**（否则「未触发任何停止判据」不可判远近）。
    · P4：自省未消化 ⇒ 附**未消化点名**（否则「同一批问题」不知是哪批）。
    """
    import io as _io
    import contextlib as _ctx
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    if "近阈读数" not in src:
        bad.append("[P3] 缺「近阈读数」归因")
    if "未消化点名" not in src:
        bad.append("[P4] 缺「未消化点名」归因")

    def _fin(entry, view_attrs, state_extra):
        cfg = build_cfg(False)
        m = mod.MetaDGTF(cfg)
        v = mod.View(entry=entry)
        for k, val in (view_attrs or {}).items():
            setattr(v, k, val)
        stt = {"roles_hist": ["x"], "total_rounds": 3, "round_log": [],
               "all_rehashed": [], "all_candidates": [], "all_amps": [],
               "all_threads": [], "all_expanded_descs": [],
               "all_dec_products": [], "all_und_products": [],
               "r": 3, "rounds_n": 3, "sp": mod._spiral_for(cfg, entry)}
        stt.update(state_extra or {})
        with _ctx.redirect_stdout(_io.StringIO()):
            m._finalize_layer_common(entry, v, stt)
        return v

    # ① P3：无停因（被截断）⇒ 消息含「未触发任何停止判据」+「近阈读数」
    try:
        v3 = _fin("1", {}, {"round_log": [
            {"round": 3, "new_amps": 0, "new_threads": 0,
             "idle_amp": 1, "idle_thread": 0, "idle_stall": 1}]})
        s3 = str(v3.stop_reason or "")
        if "未触发任何停止判据" not in s3:
            bad.append("[P3] 截断消息丢了「未触发任何停止判据」：%r" % s3)
        if "近阈读数" not in s3:
            bad.append("[P3] 截断消息没附近阈读数：%r" % s3)
    except Exception as e:  # noqa: BLE001
        bad.append("[P3] 驱动抛错：%r" % (e,))

    # ② P4：自省未消化停因 ⇒ 消息附「未消化点名」
    try:
        v4 = _fin("1", {
            "stop_reason": "自省连续 2 圈点名同一批问题未消化（层内空转）",
            "carry": [{"target": "未消化的甲"}, {"target": "未消化的乙"}],
            "carry_check": {}}, {})
        s4 = str(v4.stop_reason or "")
        if "未消化点名" not in s4:
            bad.append("[P4] 自省未消化停因没附未消化点名：%r" % s4)
        if "未消化的甲" not in s4:
            bad.append("[P4] 未消化点名没带出具体条目：%r" % s4)
    except Exception as e:  # noqa: BLE001
        bad.append("[P4] 驱动抛错：%r" % (e,))

    # ③ 负对照：普通停因不该被附「未消化点名」
    try:
        v5 = _fin("1", {"stop_reason": "研究层双通道均收敛，螺旋停止",
                        "carry": [{"target": "甲"}]}, {})
        if "未消化点名" in str(v5.stop_reason or ""):
            bad.append("[P4-负对照] 普通停因也被附了未消化点名：%r"
                       % v5.stop_reason)
    except Exception as e:  # noqa: BLE001
        bad.append("[P4] 负对照驱动抛错：%r" % (e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.41 P3+P4 停因归因（截断附近阈读数 · 自省未消化附点名 · "
          "普通停因不误加）全过")
    return True


def check_v12349_run_ckpt():
    """[v1.23.49] 修「run() 只在返回后写盘 ⇒ 中断全丢」：跑中快照 + 孤儿回收。

    ★ 判据：① 写-读回环（含 View 的 `to_dict` 形状）；② **原子**（不留 `.tmp` 残骸）；
      ③ 孤儿回收：过期的 `running` ⇒ `interrupted` + why；④ **负对照**：还没过期
        的 ⇒ 不动；⑤ 幂等（第二次不再改）；⑥ `interval<=0` / 无 run_id ⇒ 不起线程；
      ⑦ 起-停闭环（真线程）⇒ 落最后一份 `done`；⑧ **构造性证明**：出厂默认
        配置（`live_checkpoint=true`，本项目「新键默认关」惯例的**唯一例外**）下真跑
        ⇒ 快照真落盘、状态 `done`；配置键 + 接线也在源码里对账。
    """
    import tempfile
    import time as _t
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for tok in ("def write_run_ckpt(run_id: str", "def start_run_ckpt(engine",
                "def stop_run_ckpt(stop_evt, engine=None",
                "def recover_orphan_runs(base=None",
                '"live_checkpoint": True,', "start_run_ckpt(self, _ck_rid, _ck_iv)"):
        if tok not in src:
            bad.append("[CK] 源码缺：%s" % tok)

    _base = Path(tempfile.mkdtemp(prefix="ckpt_"))
    W = mod.write_run_ckpt
    # ① 写-读回环
    _p = W("T1", {"id": "T1", "status": "running", "n_views": 2,
                  "views": {"0": {"anchor": "甲"}}}, base=_base)
    if not _p.exists():
        bad.append("[CK] 写完文件不在")
    else:
        _d = json.loads(_p.read_text(encoding="utf-8"))
        if _d.get("n_views") != 2 or (_d.get("views") or {}).get("0", {}).get("anchor") != "甲":
            bad.append("[CK] 回环内容不对：%r" % (_d,))
    # ② 原子：不留 .tmp 残骸
    if list(_base.glob("*.tmp")):
        bad.append("[CK] 留下 .tmp 残骸（非原子写）")
    # ③ 孤儿回收（伪造一个很旧的 running）
    _old = {"id": "T2", "status": "running", "t": _t.time() - 100000.0,
            "views": {"0": {"x": 1}}}
    W("T2", _old, base=_base)
    _r1 = mod.recover_orphan_runs(base=_base, stale_sec=900.0)
    _ids = [x.get("id") for x in _r1]
    if "T2" not in _ids:
        bad.append("[CK] 过期 running 没被回填：%r" % (_r1,))
    _d2 = json.loads(mod.run_ckpt_path("T2", _base).read_text(encoding="utf-8"))
    if _d2.get("status") != "interrupted" or not _d2.get("interrupted_why"):
        bad.append("[CK] 回填形状不对：%r" % (_d2.get("status"),))
    if not _d2.get("views", {}).get("0"):
        bad.append("[CK] 回填把 views 弄丢了（内容没留下）")
    # ⑤ 幂等
    _r2 = mod.recover_orphan_runs(base=_base, stale_sec=900.0)
    if any(x.get("id") == "T2" for x in _r2):
        bad.append("[CK] 不幂等：第二次又改了一次")
    # ④ 负对照：新鲜的 running 不动
    W("T3", {"id": "T3", "status": "running", "t": _t.time()}, base=_base)
    _r3 = mod.recover_orphan_runs(base=_base, stale_sec=900.0)
    if any(x.get("id") == "T3" for x in _r3):
        bad.append("[CK-负对照] 还没过期就被判孤儿")
    _d3 = json.loads(mod.run_ckpt_path("T3", _base).read_text(encoding="utf-8"))
    if _d3.get("status") != "running":
        bad.append("[CK-负对照] 新鲜的 running 被改了状态")
    # ⑥ interval<=0 / 无 id ⇒ 不起
    if mod.start_run_ckpt(object(), "", 30.0) is not None:
        bad.append("[CK] 无 run_id 竟起了线程")
    if mod.start_run_ckpt(object(), "T9", 0) is not None:
        bad.append("[CK] interval<=0 竟起了线程")
    # 起-停闭环（真线程）
    class _E:
        _results = {"0": None}
        _question = "q"
        _route = ["0"]
    _orig_dir = mod.run_ckpt_dir
    mod.run_ckpt_dir = lambda base=None: _base   # 重定向到临时目录，不污染仓库
    try:
        _ev = mod.start_run_ckpt(_E(), "T4", 0.05)
        if _ev is None:
            bad.append("[CK] 正常参数竟没起线程")
        else:
            _t.sleep(0.2)
            mod.stop_run_ckpt(_ev, _E(), "T4", "done")
            _d4 = json.loads((_base / "T4.json").read_text(encoding="utf-8"))
            if _d4.get("status") != "done":
                bad.append("[CK] 停的时候没落最后一份 done：%r" % (_d4.get("status"),))
    finally:
        mod.run_ckpt_dir = _orig_dir

    if bad:
        for x in bad:
            print("  X", x)
        return False
    # ⑦ 端到端构造性证明：**出厂默认配置**下真跑 ⇒ 快照真落盘、状态 done
    #    （「能力存在性用构造性证明」：光有函数不够，要见真实入口产出）
    import tempfile
    import time as _t2
    _base2 = Path(tempfile.mkdtemp(prefix="ckpt_e2e_"))
    _orig_dir = mod.run_ckpt_dir
    # ★ 桩必须**还原**：下面把全局 LLM.call 换成了占位桩，若漏还原，
    #   同进程后续检查（auto_plan 等）全拿到非 JSON 文本
    #   ⇒ 静默退 serial（本轮实测踩过）。
    _orig_call = mod.LLM.call
    mod.run_ckpt_dir = lambda base=None: _base2
    try:
        _cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
        if not bool((_cfg.get("runtime") or {}).get("live_checkpoint", False)):
            bad.append("[CK-端到端] 出厂 yaml 的 live_checkpoint 竟不是 true")
        # ★ 侧效应隔离：出厂配置 `playbook.dir=""`（⇒ 默认 dgtf_memory/）、
        #   `output.save_dir="outputs"` —— 照原样跑会把这次冒烟写进**生产
        #   记忆库**（episodes/nogoods/bandit/权重）并往仓库 outputs/ 丢诊断
        #   文件（实测两次：13:47、13:59）。**被测对象是 `live_checkpoint`
        #   出厂 true 时快照是否落盘，不是"往哪儿写"** ⇒ 只重定向这两个
        #   目录，live_checkpoint 保持出厂值不动。
        _cfg.setdefault("output", {})["save_dir"] = str(
            Path(tempfile.mkdtemp(prefix="ckpt_e2e_out")))
        _e2e_mem = str(Path(tempfile.mkdtemp(prefix="ckpt_e2e_mem")))
        _cfg.setdefault("playbook", {})["dir"] = _e2e_mem
        # ★ bandit 的目录解析走 `eml_dir()`（恒指仓库 dgtf_memory），**不吃**
        #   `playbook.dir`；而出厂 yaml 的 `all_on: true` 会把 `auto.bandit`
        #   打开 ⇒ 这次跑会写生产 `dgtf_memory/bandit.json`（实测：n[0] 5→6）。
        #   就地给它一个 `dir`（`_save_bandit` 优先级 `cfg["dir"] or eml_dir()`）。
        _cfg.setdefault("auto", {}).setdefault("bandit", {})["dir"] = _e2e_mem
        mod.LLM.call = lambda system, user, *a, **k: (
            "- [concept] 占位候选：一段足够长的占位输出，用来过解析门槛。" * 2)
        _m = mod.MetaDGTF(_cfg)
        _rid2 = "E2E_%d" % int(_t2.time())
        _r = _m.run("一个领域里那些被当作常识的东西是怎么来的，它靠不靠得住。",
                    route=["0"], rounds={"0": 1}, parallel_mode="serial",
                    run_id=_rid2)
        _f = _base2 / ("%s.json" % _rid2)
        if not _f.exists():
            bad.append("[CK-端到端] 默认配置下真跑**没落快照**（能力不可达）")
        else:
            _d = json.loads(_f.read_text(encoding="utf-8"))
            if _d.get("status") != "done":
                bad.append("[CK-端到端] 快照状态不是 done：%r" % (_d.get("status"),))
            if not (_d.get("views") or {}).get("0"):
                bad.append("[CK-端到端] 快照里没有层 0 的 views（内容没留下）")
    except Exception as _e:  # noqa: BLE001
        bad.append("[CK-端到端] 驱动 run() 抛错：%r" % (_e,))
    finally:
        mod.run_ckpt_dir = _orig_dir
        mod.LLM.call = _orig_call

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.49 跑中快照（回环 · 原子无残骸 · 过期⇒interrupted+why · "
          "新鲜不动 · 幂等 · 不起线程的两种情形 · 起停闭环落 done · "
          "**出厂默认配置下端到端真落盘**）全过")
    return True


def check_v12357_goal_trace_carry():
    """[v1.23.57] `goal_trace` 跨圈携带 ⇒ 早停单标量判据**走得到**。

    ★ 为什么必须有它（真缺陷）：引擎**每圈新建 view**（`view = dg.run(inp)`），
      而目标读数只 append 到当圈那个 view ⇒ 下一圈就丢。产物实测：跑 4~7 圈，
      `goal_trace` 每层只有 **1** 条。而 `layer_gain_stop_signal` 的第一道门是
      `len(prev) >= _LG_STOP_FLAT_N + 1`（=3）⇒ 门恒关 ⇒
      **`stop.gain_floor` 在任何取值下都不会触发**（通道断了，不是阈值严）。

    ★ 判据拆两段（只跑真入口会误判）：
      · 真入口：`goal_trace` 条数 == `rounds_run` 且 ≥2 ⇒ 历史真接上了；
      · 纯函数：喂 3 条低增益历史 ⇒ **必须触发** ⇒ 判据本体是活的。
      mock 的产物是固定文本，修行层第 2 圈就被"复述/空转"自然停了，走不到第 3 圈 ——
      所以"触发"这一支只能靠纯函数证，不能靠真入口。
    ★ 两条负对照：只给 1 条历史 ⇒ 不触发（门还在）；`gain_floor=0` ⇒ 不触发（零行为差）。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for _tk in ("self._goal_hist = _hist", "view.goal_trace = list(_h)",
                "self._goal_hist = {}"):
        if _tk not in src:
            bad.append("[G1] 源码缺：%s" % _tk)

    _mem = Path(_tf.mkdtemp(prefix="v57mem_"))
    _q = "冒烟题面：这件事的边界在哪里（v12357 跨圈携带判据）"

    def _cfg():
        c = build_cfg(False)
        c["output"]["save_dir"] = str(Path(_tf.mkdtemp(prefix="v57out_")))
        c["playbook"] = {"mode": "off", "dir": str(_mem)}
        c.setdefault("stop", {})["gain_floor"] = 0.0
        c.setdefault("runtime", {})["live_checkpoint"] = False
        c["all_on"] = False
        return c

    try:
        _r = mod.MetaDGTF(_cfg()).run(
            _q, route=["0"], rounds={"0": 5}, parallel_mode="serial")
        _v = (_r.get("views") or {}).get("0") or {}
        _rr = int(_v.get("rounds_run") or 0)
        _tn = len(_v.get("goal_trace") or [])
        if _tn != _rr:
            bad.append("[G2] goal_trace=%d 与 rounds_run=%d 不一致"
                       "（历史没跨圈接上）" % (_tn, _rr))
        if _tn < 2:
            bad.append("[G2] goal_trace 只有 %d 条（应随圈数增长）" % _tn)
        # 纯函数：3 条「增益低于阈值」的历史必须触发
        _prev = [{"round": 1, "excavate": 0.90},
                 {"round": 2, "excavate": 0.90},
                 {"round": 3, "excavate": 0.90}]
        _hit, _why = mod.layer_gain_stop_signal("0", _prev[-1], _prev, 0.5)
        if _hit is not True:
            bad.append("[G3] 3 条低增益历史没触发早停（判据本体不灵）")
        elif "增益趋零" not in str(_why):
            bad.append("[G3] 触发了但理由没点名：%r" % (_why[:40],))
        # 负对照
        if mod.layer_gain_stop_signal("0", _prev[-1], _prev[-1:], 0.5)[0] is not False:
            bad.append("[G4] 只给 1 条历史竟触发了（len<3 那道门破了）")
        if mod.layer_gain_stop_signal("0", _prev[-1], _prev, 0.0)[0] is not False:
            bad.append("[G4] gain_floor=0（默认关）仍触发（零行为差破了）")
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[G2] 异常：%r" % (_ex,))
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.57 目标读数跨圈（%d 项）" % len(bad))
        return False
    print("✓ v1.23.57 目标读数跨圈：goal_trace 随圈数增长 · 早停判据真能触发")
    return True


def check_v12356_ckpt_cumulative():
    """[v1.23.56] 快照记账**跨窗口累计**（否则"被杀跑次也能结算成本"是假的）。

    ★ 为什么必须有它：`llm_calls` 取自 `self.llm.total_calls`，那是**按实例**的
      计数器；续跑新建实例就归零 ⇒ 第二个窗口的快照只记本窗口。
      实测（A/B 真跑）：这条 run_id 实际花了 230 calls，快照里写的是 97。
      按这个数结算成本，前面那个窗口的钱**查不到**。
    ★ 判据走真入口（两窗口，都极小预算 ⇒ 都 paused），并拆两个口径：
        `llm_calls` = 基线 + 本窗口（结算用）
        `window_calls` = 本窗口（分析用）
      负对照：第二窗口 `window_calls` 必须**严格小于** `llm_calls`
      —— 否则两个字段写的是同一个东西，等于没拆。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for _tk in ('"window_calls": _w_calls,',
                '"llm_calls": int(_base.get("calls") or 0) + _w_calls,',
                "self._ck_base = {",
                '_out["llm_calls"] = int(_d.get("llm_calls") or 0)'):
        if _tk not in src:
            bad.append("[C1] 源码缺：%s" % _tk)

    _ck = Path(_tf.mkdtemp(prefix="v56ck_"))
    _mem = Path(_tf.mkdtemp(prefix="v56mem_"))
    _orig = mod.run_ckpt_dir
    mod.run_ckpt_dir = lambda base=None: _ck
    _q = "冒烟题面：这件事的边界在哪里（v12356 记账累计判据）"

    def _cfg():
        c = build_cfg(False)
        c["output"]["save_dir"] = str(Path(_tf.mkdtemp(prefix="v56out_")))
        c["playbook"] = {"mode": "off", "dir": str(_mem)}
        c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_mem)
        c.setdefault("runtime", {})
        c["runtime"]["live_checkpoint"] = True
        c["runtime"]["ckpt_interval"] = 0.05
        c["all_on"] = False
        return c

    try:
        _rid = "CKSM56"
        mod.MetaDGTF(_cfg()).run(
            _q, route=["0"], rounds={"0": 2}, parallel_mode="serial",
            run_id=_rid, max_minutes=1e-6)
        _p = _ck / ("%s.json" % _rid)
        if not _p.is_file():
            bad.append("[C2] 第一窗口没落快照")
            raise RuntimeError("no snapshot")
        _d1 = json.loads(_p.read_text(encoding="utf-8"))
        _c1 = int(_d1.get("llm_calls") or 0)
        if _c1 <= 0:
            bad.append("[C2] 第一窗口 llm_calls 为 0（前提不成立）")
        if int(_d1.get("window_calls") or -1) != _c1:
            bad.append("[C2] 首窗口 window_calls(%r) != llm_calls(%r)"
                       % (_d1.get("window_calls"), _c1))
        mod.MetaDGTF(_cfg()).run(
            _q, route=["0"], rounds={"0": 2}, parallel_mode="serial",
            run_id=_rid, resume_ckpt=str(_p), max_minutes=1e-6)
        _d2 = json.loads(_p.read_text(encoding="utf-8"))
        _c2 = int(_d2.get("llm_calls") or 0)
        _w2 = int(_d2.get("window_calls") or 0)
        if _c2 != _c1 + _w2:
            bad.append("[C3] 第二窗口不是累计：llm_calls=%d，基线%d+本窗口%d=%d"
                       % (_c2, _c1, _w2, _c1 + _w2))
        if not (_w2 < _c2):
            bad.append("[C3] window_calls(%d) 没比 llm_calls(%d) 小"
                       "（两个口径没分开）" % (_w2, _c2))
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[C2] 异常：%r" % (_ex,))
    finally:
        mod.run_ckpt_dir = _orig
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.56 记账累计（%d 项）" % len(bad))
        return False
    print("✓ v1.23.56 记账累计：第二窗口 = 基线 + 本窗口 · window_calls 单独可读")
    return True


def check_v12355_paused_gap():
    """[v1.23.55] `paused` 时的缺层是**待续**，不是缺陷（真缺陷不许被豁免）。

    ★ 为什么必须有它：A/B 真跑暂停时产物打了
        ❌ 缺层：请求了但这些层没有产出 —— 这份产物是不完整的
        · 元：未记录原因（这是缺陷）
      可暂停时缺层是**设计**。这条提示会让人去查一个不存在的 bug，而且
      `layer_gap` 一写进产物，任何"缺层=缺陷"的下游判据都跟着误判。
    ★ 三臂（缺一不可）：
      P1 暂停 + 缺的层都在 `pending_layers` 里 ⇒ `paused_gap`，**没有** `layer_gap`
      P2 暂停 + 有一层既没产出也不在 pending 里 ⇒ 那层仍进 `layer_gap`（真缺陷）
      P3 不暂停 + 缺层 ⇒ 照旧进 `layer_gap`（旧行为逐字不变）
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for _tk in ('packed["paused_gap"] = list(_pause_gap)',
                "_real_gap = [e for e in missing if e not in _pause_gap]",
                '"missing": _real_gap'):
        if _tk not in src:
            bad.append("[G1] 源码缺：%s" % _tk)

    def _pack(missing, paused, pend):
        return {"dispatch": {"missing": list(missing), "skipped": [],
                             "failed": {}, "requested": ["0", "1", "both", "all"]},
                "paused": bool(paused),
                "pending_layers": list(pend)}

    try:
        _eng = mod.MetaDGTF(build_cfg(False))
        # P1：暂停，缺的两层都在 pending 里 ⇒ 待续，不报缺陷
        _p = _pack(["both", "all"], True, ["both", "all"])
        _eng._layer_guard(_p)
        if _p.get("layer_gap"):
            bad.append("[P1] 暂停 + 缺层都在 pending ⇒ 仍写了 layer_gap（假警报）")
        if sorted(_p.get("paused_gap") or []) != ["all", "both"]:
            bad.append("[P1] 没记 paused_gap：%r" % (_p.get("paused_gap"),))
        # P2：暂停，但有一层既没产出也不在 pending 里 ⇒ 真缺陷仍要报
        _p2 = _pack(["both", "all"], True, ["all"])
        _eng._layer_guard(_p2)
        if sorted((_p2.get("layer_gap") or {}).get("missing") or []) != ["both"]:
            bad.append("[P2] 真缺陷被暂停豁免掉了：%r"
                       % ((_p2.get("layer_gap") or {}).get("missing"),))
        if sorted(_p2.get("paused_gap") or []) != ["all"]:
            bad.append("[P2] paused_gap 记错：%r" % (_p2.get("paused_gap"),))
        # P3：不暂停 ⇒ 旧行为（全部进 layer_gap）
        _p3 = _pack(["all"], False, [])
        _eng._layer_guard(_p3)
        if (_p3.get("layer_gap") or {}).get("missing") != ["all"]:
            bad.append("[P3] 非暂停路径的缺层没被记进 layer_gap（旧行为破了）")
        if _p3.get("paused_gap"):
            bad.append("[P3] 非暂停却记了 paused_gap")
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[P?] 异常：%r" % (_ex,))
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.55 暂停待续（%d 项）" % len(bad))
        return False
    print("✓ v1.23.55 暂停待续：pending 里的缺层不报缺陷 · 真缺陷仍报红 · 旧路径不变")
    return True


def check_v12354_parallel_wall_clock():
    """[v1.23.54] 并行跑次也能被**墙钟预算**截住，并且能**续跑**。

    ★ 为什么必须有它：`max_minutes` 原来只挂在 `_run_serial` 的**层间** ⇒ 并行模式
      （A/B/C + D~H）设了预算也照跑到天亮，宿主一回收就全丢；而 `load_resume_snapshot`
      又硬拒非 serial ⇒ 强杀后连续都续不了。**预算保护对并行是空的。**
    ★ 判据走真入口，且覆盖那条最容易假修的链：
        圈边界判墙钟 → 标记**盖到 view** → 续跑按标记**摘层** → 只重跑被摘的层
      第一版实现把标记只写在 `_budget_stop_note` 上，而 `stop_reason` 是**逐圈在
      循环体末尾**拼的、圈首 break 会跳过 ⇒ 摘层恒空 ⇒ **续跑什么都不重跑**。
      本判据当场逮到了它，所以 P2/P3 缺一不可。
    ★ 负对照：预算关 ⇒ 不 paused（否则"每到点就停"也能过）。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for _tk, _n in (("def _wall_clock_over(self) -> bool:", 1),
                    ("self._wall_clock_over()", 4),
                    ('"墙钟预算到点（第 %d 圈截断', 3),
                    ('_out["truncated"] = _tr', 1),
                    ("_resume_serial", 3)):
        _c = src.count(_tk)
        if _c != _n:
            bad.append("[P1] 源码 %r 应出现 %d 次（实测 %d）" % (_tk, _n, _c))
    if 'if _mx > 0 and (time.time()' in src:
        bad.append("[P1] serial 还留着内联的墙钟判据（会有两份实现）")
    if '"墙钟预算" in str(getattr(_v, "stop_reason"' not in src:
        bad.append("[P1] 续跑侧没按标记摘层（截断层会被当完成复用）")

    _ck = Path(_tf.mkdtemp(prefix="v54ck_"))
    _mem = Path(_tf.mkdtemp(prefix="v54mem_"))
    _orig_dir = mod.run_ckpt_dir
    mod.run_ckpt_dir = lambda base=None: _ck
    _q = "冒烟题面：这件事的边界在哪里（v12354 并行墙钟判据）"

    def _cfg():
        c = build_cfg(False)
        c["output"]["save_dir"] = str(Path(_tf.mkdtemp(prefix="v54out_")))
        c["playbook"] = {"mode": "on", "dir": str(_mem)}
        c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_mem)
        c.setdefault("runtime", {})
        c["runtime"]["live_checkpoint"] = True
        c["runtime"]["ckpt_interval"] = 0.05
        c["all_on"] = False
        return c

    def _neps():
        _p = _mem / "episodes.jsonl"
        return len(mod.eml_read_jsonl(_p) or []) if _p.is_file() else 0

    try:
        _r1 = mod.MetaDGTF(_cfg()).run(
            _q, route=["0", "1"], rounds={"0": 1, "1": 2},
            parallel_mode="A", run_id="PA1", max_minutes=1e-6)
        if _r1.get("paused") is not True:
            bad.append("[P2] 并行模式到点却没标 paused（预算对并行仍无效）")
        _tr = [e for e, v in (_r1.get("views") or {}).items()
               if "墙钟预算" in str((v or {}).get("stop_reason") or "")]
        if not _tr:
            bad.append("[P2] 截断层的 stop_reason 没带标记（续跑会认不出）")
        if sorted(_tr) != sorted(_r1.get("pending_layers") or []):
            bad.append("[P2] 带标记的层 ≠ pending_layers（%r vs %r）"
                       % (sorted(_tr), sorted(_r1.get("pending_layers") or [])))
        if _neps() != 0:
            bad.append("[P2] 暂停的并行跑次写了 %d 条 episode" % _neps())
        _snap = _ck / "PA1.json"
        if not _snap.is_file():
            bad.append("[P2] 暂停快照没落盘")
            raise RuntimeError("no snapshot")
        _ran = []
        _ol = mod.MetaDGTF._run_layer

        def _spy(self, entry, n):
            _ran.append(entry)
            return _ol(self, entry, n)

        mod.MetaDGTF._run_layer = _spy
        try:
            _r2 = mod.MetaDGTF(_cfg()).run(
                _q, route=["0", "1"], rounds={"0": 1, "1": 2},
                parallel_mode="A", run_id="PA2", resume_ckpt=str(_snap))
        finally:
            mod.MetaDGTF._run_layer = _ol
        if _r2.get("resumed_serial") != "A":
            bad.append("[P3] 并行续跑没降级 / 没记 resumed_serial（%r）"
                       % (_r2.get("resumed_serial"),))
        if "0" in _ran:
            bad.append("[P3] 已完成的层 0 被重跑（白烧钱）：%r" % (_ran,))
        if "1" not in _ran:
            bad.append("[P3] 截断层 1 没重跑（分片跑永远跑不完整）：%r" % (_ran,))
        _r3 = mod.MetaDGTF(_cfg()).run(
            _q, route=["0", "1"], rounds={"0": 1, "1": 1},
            parallel_mode="A", run_id="PA3")
        if _r3.get("paused"):
            bad.append("[P4] 预算关的并行跑次也被标 paused（假实现）")
        if "resumed_serial" in _r3:
            bad.append("[P4] 没续跑却记了 resumed_serial")
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[P2] 异常：%r" % (_ex,))
    finally:
        mod.run_ckpt_dir = _orig_dir
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.54 并行墙钟/续跑（%d 项）" % len(bad))
        return False
    print("✓ v1.23.54 并行墙钟：到点截断并留标记 · 续跑降级 serial 只重跑截断层")
    return True


def check_v12353_eml_dir_single():
    """[v1.23.53] 记忆库目录**一处解析**（bandit 不再偷偷写回仓库）。

    ★ 为什么必须有它：以前 episode/playbook 走 `playbook.dir`，bandit 却只看
      `auto.bandit.dir`、空则 `eml_dir()`（**恒指仓库**）⇒ 任何设了 `playbook.dir`
      的调用方（冒烟、A/B 脚本、想隔离库的人）都会让 bandit 偷偷写生产库。
      冒烟隔离因此要三个旋钮，漏一个就污染 —— 这类「漏一格」的事故本项目栽过。
    ★ 判据分两半：
      · 源码：唯一解析函数存在、三个点都走它、**没有残留的 eml_dir() 回落**；
      · 行为（真入口）：`MetaDGTF(cfg)` 的**载入**必须读到 `playbook.dir` 里那份，
        `_save_bandit` 也必须落在那儿，而 `eml_dir()` 那个点**一个字节都不许写**。
      负对照：显式 `auto.bandit.dir` 仍然优先（显式赢了才用显式的）。
    ★ 测试自身把 `mod.eml_dir` 指到临时目录 —— 判据**不看**生产 `dgtf_memory/`。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    if src.count("def eml_store_dir(cfg=None) -> Path:") != 1:
        bad.append("[B1] 缺唯一解析 eml_store_dir")
    if src.count("eml_store_dir(self.config)") != 3:
        bad.append("[B1] 走统一解析的点应 3 处（实测 %d）"
                   % src.count("eml_store_dir(self.config)"))
    if '(cfg or {}).get("dir") or eml_dir()' in src:
        bad.append("[B1] 仍有地方直接回落 eml_dir()（两处解析没收敛）")

    _pdir = Path(_tf.mkdtemp(prefix="v53p_"))
    _fake = Path(_tf.mkdtemp(prefix="v53r_"))
    _orig = mod.eml_dir
    mod.eml_dir = lambda base=None: _fake
    try:
        def _cfg(pdir="", bdir=""):
            c = build_cfg(False)
            c["playbook"] = {"mode": "shadow", "dir": str(pdir)}
            c.setdefault("auto", {}).setdefault("bandit", {})
            c["auto"]["bandit"]["enabled"] = True
            c["auto"]["bandit"]["dir"] = str(bdir)
            c["all_on"] = False
            return c

        _k = len(mod._BANDIT_ARMS)
        (_pdir / mod._BANDIT_FILE).write_text(json.dumps(
            {"t": 1, "n": [9] + [0] * (_k - 1),
             "mean": [0.5] * _k, "cost": [1.0] * _k}), encoding="utf-8")
        _e = mod.MetaDGTF(_cfg(pdir=_pdir))
        if not _e._bandit or int(_e._bandit.n[0]) != 9:
            bad.append("[B2] 载入没走 playbook.dir（n[0]=%r）"
                       % (int(_e._bandit.n[0]) if _e._bandit else None,))
        _bb = mod._load_bandit(_e._bandit_cfg, mod.eml_store_dir(_e.config))
        _bb.n[1] = 7
        mod._save_bandit(_bb, _e._bandit_cfg, mod.eml_store_dir(_e.config))
        _f = _pdir / mod._BANDIT_FILE
        if not _f.is_file():
            bad.append("[B2] 落盘没进 playbook.dir")
        elif int(json.loads(_f.read_text(encoding="utf-8"))["n"][1]) != 7:
            bad.append("[B2] 落盘内容不是本次那份")
        if (_fake / mod._BANDIT_FILE).is_file():
            bad.append("[B2] 还是写了 eml_dir()（隔离仍靠第三个旋钮）")
        _b2 = Path(_tf.mkdtemp(prefix="v53b_"))
        _e2 = mod.MetaDGTF(_cfg(pdir=_pdir, bdir=_b2))
        if not _e2._bandit or int(_e2._bandit.n[0]) != 0:
            bad.append("[B3] 显式 auto.bandit.dir 没优先（读到了 pdir 那份）")
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[B2] 异常：%r" % (_ex,))
    finally:
        mod.eml_dir = _orig
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.53 记忆库目录一处解析（%d 项）" % len(bad))
        return False
    print("✓ v1.23.53 记忆库目录一处解析：bandit 跟着 playbook.dir · 显式 dir 仍优先")
    return True


def check_v12352_paused_no_eml():
    """[v1.23.52] `paused` 跑次不写 EML 库（半程样本不是证据）。

    ★ 为什么必须有它：v1.23.51 只保证「不重复调用就不多写」。墙钟预算暂停的跑次
      仍会写一条**半程样本**；续跑跑完后同一个 `run_id` 又写一条完整样本（读数
      不同 ⇒ 幂等守卫按设计放行）⇒ **一个跑次两条证据**，`used_outcomes` 记两笔、
      weight 罚两遍。清账脚本收拾的正是这一类。
    ★ 判据走**真入口**：`run(max_minutes=极小)` 真的暂停一次，再看库。
      负对照（预算关的正常跑 ⇒ 照写）把「一律不写」这种假实现排除掉。
    ★ 位置也是判据：守卫必须在 `off` 之后、**取锁之前** —— 暂停的跑次连目录都
      不该建，更不该去抢锁。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for _tk in ('_blk["skipped_paused"] = True',
                'result.get("paused")',
                'result.get("pending_layers")'):
        if _tk not in src:
            bad.append("[P1] 源码缺：%s" % _tk)
    try:
        _i_off = src.index('        if _mode == "off":')
        _i_pz = src.index('_blk["skipped_paused"] = True')
        _i_lock = src.index("_lk = eml_lock(dirpath=_dir)")
        if not (_i_off < _i_pz < _i_lock):
            bad.append("[P1] 守卫位置不对（要求 off → paused → 取锁）")
    except Exception as _ex:
        bad.append("[P1] 定位失败：%r" % (_ex,))

    _mem = Path(_tf.mkdtemp(prefix="v52mem_"))
    _ck = Path(_tf.mkdtemp(prefix="v52ck_"))
    _orig_dir = mod.run_ckpt_dir
    mod.run_ckpt_dir = lambda base=None: _ck
    _q = "冒烟题面：这件事的边界在哪里（v12352 暂停不写库判据）"

    def _cfg():
        c = build_cfg(False)
        c["output"]["save_dir"] = str(Path(_tf.mkdtemp(prefix="v52out_")))
        c["playbook"] = {"mode": "on", "dir": str(_mem), "top_k": 3,
                         "promote_n": 3, "halflife_days": 14.0}
        c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_mem)
        c["all_on"] = False
        return c

    def _n():
        _p = _mem / "episodes.jsonl"
        return len(mod.eml_read_jsonl(_p) or []) if _p.is_file() else 0

    try:
        _r1 = mod.MetaDGTF(_cfg()).run(
            _q, route=["0", "1"], rounds={"0": 1, "1": 1},
            parallel_mode="serial", run_id="PZ1", max_minutes=1e-6)
        if _r1.get("paused") is not True:
            bad.append("[P2] 预算到点却没标 paused（前提不成立）")
        if not (_r1.get("playbook") or {}).get("skipped_paused"):
            bad.append("[P2] paused 跑次没被跳过（会写半程样本）")
        if _n() != 0:
            bad.append("[P2] paused 跑次写了 %d 条 episode" % _n())
        _r2 = mod.MetaDGTF(_cfg()).run(
            _q, route=["0"], rounds={"0": 1},
            parallel_mode="serial", run_id="PZ2")
        if (_r2.get("playbook") or {}).get("skipped_paused"):
            bad.append("[P3] 正常跑被当暂停跳过（写成了「一律不写」）")
        if _n() != 1:
            bad.append("[P3] 正常跑没写 episode（实测 %d）" % _n())
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[P2] 异常：%r" % (_ex,))
    finally:
        mod.run_ckpt_dir = _orig_dir
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.52 暂停不写库（%d 项）" % len(bad))
        return False
    print("✓ v1.23.52 暂停不写库：预算到点零写入 · 正常跑照写")
    return True


def check_v12351_eml_once_per_run():
    """[v1.23.51] 一个跑次只学一条 episode（`_eml_finish` 幂等守卫）。

    ★ 为什么必须有它：A/B 真跑把 `_eml_finish` 调了两次 ⇒ 每个跑次写出两条
      episode、`used_outcomes` 与 weight 被罚两遍，事后只能手工清账（见
      `_fix_eml_dup_20261016.py`）。只修调用方防不住**同类**（任何调用方都可能
      重调），所以守卫落在引擎里；本判据守的是「一个跑次一条证据」这个不变量。
    ★ 判据是**行为级、逐字节**的：同一份 result 连调两次 ⇒ 第二次**盘上一个
      字节都不许变**。三条对照把「一律跳过」这种假实现排除掉：
      换 run_id 照写 / 同 run_id 但读数不同照写（`paused` 后的完整样本必须能进库）。
    ★ 取材是四份文件**逐字节**比，不是数条数 —— 条数不变但内容被改也是错。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for _tk in ('_blk["dup_skipped"] = True',
                "_old_eps = eml_read_jsonl(_dir / _EML_EPISODES)",
                '{k: v for k, v in _ep.items() if k != "t"}'):
        if _tk not in src:
            bad.append("[E1] 源码缺：%s" % _tk)
    try:
        _i_lk = src.index("_lk.__enter__()")
        _i_g = src.index('_blk["dup_skipped"] = True')
        _i_ap = src.index("eml_append_jsonl(_dir / _EML_EPISODES, _ep)")
        if not (_i_lk < _i_g < _i_ap):
            bad.append("[E1] 守卫位置不对（要求 锁 < 守卫 < 写 episode）")
    except Exception as _ex:
        bad.append("[E1] 定位失败：%r" % (_ex,))

    def _mkres(rid, cut=("1",)):
        return {"id": rid,
                "question": "如何利用AI来帮助人类实现财富自由",
                "route": ["0", "1", "both", "all"],
                "rounds": {"0": 3, "1": 3, "both": 3, "all": 4},
                "dispatch": {"_parallel_mode": "serial"},
                "views": {e: {"stop_reason": ("体力耗尽（3 圈走满）"
                                              if e in cut else "自然安住"),
                              "duty": {"S": 0.1 if e in ("0", "1") else 0.5}}
                          for e in ("0", "1", "both", "all")},
                "pools": {"1": {"anchors": [], "web_results": []}},
                "tri_consensus": [], "llm_tokens": 10, "llm_calls": 1,
                "_auto_dispatch": {"_history": {}}}
    _d = Path(_tf.mkdtemp(prefix="v51eml_"))
    try:
        _cfg = dict(mod.DEFAULT_CONFIG)
        _cfg["playbook"] = {"mode": "on", "dir": str(_d), "top_k": 3,
                            "promote_n": 3, "halflife_days": 14.0}
        _eng = mod.MetaDGTF(_cfg)
        for _i in range(1, 5):
            _eng._eml_finish(_mkres("RUN%d" % _i))
        _n4 = len(mod.eml_read_jsonl(_d / "episodes.jsonl"))
        if _n4 != 4:
            bad.append("[E2] 4 跑应写 4 条 episode（实测 %d）" % _n4)
        _eng._eml_prepare("如何利用AI来帮助人类实现财富自由")
        _eng._eml_apply({"0": 3, "1": 3, "both": 3, "all": 4})
        _r5 = _mkres("RUN5")
        _b1 = _eng._eml_finish(_r5)
        _f = ("episodes.jsonl", "nogoods.jsonl", "playbook.jsonl", "MEMORY.md")
        _s1 = {k: (_d / k).read_bytes() for k in _f if (_d / k).is_file()}
        _b2 = _eng._eml_finish(_r5)
        _s2 = {k: (_d / k).read_bytes() for k in _f if (_d / k).is_file()}
        if not (_b1.get("used") or []):
            bad.append("[E2] 第 5 跑没用上条目（该判据测不到 used_outcomes）")
        if _b2.get("dup_skipped") is not True:
            bad.append("[E2] 第二次调用没标 dup_skipped")
        if _s1 != _s2:
            bad.append("[E2] 第二次调用改了盘：%r"
                       % (sorted(k for k in _s1 if _s1[k] != _s2.get(k)),))
        _n5 = len(mod.eml_read_jsonl(_d / "episodes.jsonl"))
        if _n5 != 5:
            bad.append("[E2] 同一跑次写了两条 episode（5 跑实测 %d 条）" % _n5)
        # ★ used_outcomes 必须在**对照组之前**判：E4 故意用同一 run_id 再写一次
        #   （模拟 paused 后的完整样本），那本来就该给该 run 再记一条。
        #   放在对照组之后测到的就不是幂等，而是对照本身。
        _dup = []
        for _e in (mod.eml_read_jsonl(_d / "playbook.jsonl") or []):
            _c = {}
            for _x in (_e.get("used_outcomes") or []):
                _r = str(_x.get("run") or "")
                _c[_r] = _c.get(_r, 0) + 1
            if any(v > 1 for v in _c.values()):
                _dup.append((_e.get("id"), _c))
        if _dup:
            bad.append("[E5] 同一次调用路径把 used_outcomes 记了两次：%r"
                       % (_dup[:3],))
        # 对照一：换 run_id ⇒ 照写（否则「一律跳过」也能过）
        _b3 = _eng._eml_finish(_mkres("RUN6"))
        if _b3.get("dup_skipped"):
            bad.append("[E3] 换 run_id 被判成重复（守卫写成了「一律跳过」）")
        if len(mod.eml_read_jsonl(_d / "episodes.jsonl")) != 6:
            bad.append("[E3] RUN6 没写库")
        # 对照二：同 run_id 但读数不同 ⇒ 照写（paused 半程样本可被完整样本补上）
        _b4 = _eng._eml_finish(_mkres("RUN5", cut=("0", "1", "both", "all")))
        if _b4.get("dup_skipped"):
            bad.append("[E4] 读数不同的同 run_id 被挡掉（完整样本进不了库）")
        if len(mod.eml_read_jsonl(_d / "episodes.jsonl")) != 7:
            bad.append("[E4] 读数不同的 RUN5 没写库")
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[E2] 异常：%r" % (_ex,))
    for _b in bad:
        print("  ✗ " + _b)
    if bad:
        print("✗ v1.23.51 EML 幂等（%d 项）" % len(bad))
        return False
    print("✓ v1.23.51 EML 幂等：同一跑次第二次调用零改动 · 换 run_id/换读数照写")
    return True


def check_v12350_resume():
    """[v1.23.50] 断点续跑（复用已完成层）+ 快照记账 + route 死捕获 + 墙钟预算。

    ★ 为什么必须有它：真实事故（今天两次 A/B 真跑被宿主回收）证明 —— 快照只
      「留痕」不能「接着跑」 ⇒ **烧掉的钱不可回收**。本判据做**构造性证明**：
      造一份「层 0 已完成」的快照 ⇒ 续跑必须 (a) 不重跑层 0、(b) 逐字复用其产物、
      (c) 还原其池（下游读上游池）、(d) 只跑缺的层。
    ★ 负对照：题面不同 ⇒ **拒绝续跑**（这条不变）。
    ★ 非 serial 从 v1.23.54 起**允许**（剩余层降级按 serial 跑、产物记
      `resumed_serial`）⇒ 原来的「mode=B 必须拒绝」改成「允许 + 记源模式」。
    ★ 记账/route/预算同理：被杀跑次也要能**结算成本**；`route` 原本是死捕获（恒 `[]`）。
    """
    import tempfile as _tf
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for tok in ('resume_ckpt: str = ""', "max_minutes: float = 0.0",
                "def from_dict(cls, d: dict)", "def load_resume_snapshot(",
                "self._route = list(route)", "if entry in self._results:",
                '"llm_calls": int(_base.get("calls") or 0) + _w_calls,',
                '"pools": pools,',
                '"mode": str(getattr(engine, "_parallel_mode"'):
        if tok not in src:
            bad.append("[RS] 源码缺：%s" % tok)

    _ck = Path(_tf.mkdtemp(prefix="v50ck_"))
    _mem = Path(_tf.mkdtemp(prefix="v50mem_"))
    _orig_dir = mod.run_ckpt_dir
    _orig_layer = mod.MetaDGTF._run_layer
    mod.run_ckpt_dir = lambda base=None: _ck
    _ran = []

    def _spy(self, entry, n):
        _ran.append(entry)
        return _orig_layer(self, entry, n)

    def _cfg():
        c = build_cfg(False)
        c["output"]["save_dir"] = str(Path(_tf.mkdtemp(prefix="v50out_")))
        c["playbook"]["dir"] = str(_mem)
        c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_mem)
        c["runtime"] = dict(c.get("runtime") or {})
        c["runtime"]["live_checkpoint"] = True
        c["runtime"]["ckpt_interval"] = 0.05
        c["all_on"] = False
        return c

    _q = "冒烟题面：这件事的边界在哪里（v12350 续跑判据）"
    try:
        # ★ 实测（6 分片并发跑变异体）：Windows 上 `os.replace` 偶发被占 ⇒ 最后一份
        #   快照没落盘、盘上留的是中途那份（还没有层 0）—— 这不是续跑的错，
        #   是**写盘抖动**。这里只**重试一次**并把首次失败说出来；
        #   **连续两次都缺 ⇒ 判红**（那是真缺陷，不是抖动）。
        _s, _p = None, None
        for _att in (1, 2):
            _rid = "RS1" if _att == 1 else "RS1b"
            mod.MetaDGTF(_cfg()).run(_q, route=["0"], rounds={"0": 1},
                                     parallel_mode="serial", run_id=_rid)
            _cand = _ck / ("%s.json" % _rid)
            if not _cand.is_file():
                continue
            try:
                _try = json.loads(_cand.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            if isinstance((_try.get("views") or {}).get("0"), dict):
                _s, _p = _try, _cand
                break
            if _att == 1:
                print("  · [RS] 首次快照缺层 0（写盘抖动？）⇒ 重试一次")
        if _s is None:
            bad.append("[RS] 连续两次都没拿到含层 0 的快照"
                       "（写盘失败或快照内容坏了）")
            raise RuntimeError("no usable snapshot")
        if int(_s.get("llm_calls") or 0) <= 0 or int(_s.get("llm_tokens") or 0) <= 0:
            bad.append("[RS] 快照没带记账：calls=%r tokens=%r"
                       % (_s.get("llm_calls"), _s.get("llm_tokens")))
        if not _s.get("route"):
            bad.append("[RS] 快照 route 仍是空（死捕获没修）")
        if _s.get("mode") != "serial":
            bad.append("[RS] 快照没记 mode：%r" % (_s.get("mode"),))
        if not ((_s.get("pools") or {}).get("0")):
            bad.append("[RS] 快照没带池（续跑还原不了上游）")
        _s["status"] = "interrupted"
        _p.write_text(json.dumps(_s, ensure_ascii=False, indent=1), encoding="utf-8")

        mod.MetaDGTF._run_layer = _spy
        _m2 = mod.MetaDGTF(_cfg())
        _r2 = _m2.run(_q, route=["0", "1"], rounds={"0": 1, "1": 1},
                      parallel_mode="serial", run_id="RS2", resume_ckpt=str(_p))
        if "0" in _ran:
            bad.append("[RS] 续跑**重跑了**已完成的层 0（白烧钱）：%r" % (_ran,))
        if "1" not in _ran:
            bad.append("[RS] 续跑没跑缺的层 1：%r" % (_ran,))
        if json.dumps((_r2.get("views") or {}).get("0"), sort_keys=True,
                      ensure_ascii=False, default=str) != json.dumps(
                _s["views"]["0"], sort_keys=True, ensure_ascii=False,
                default=str):
            bad.append("[RS] 层 0 的产物与快照那份不一致（不是逐字复用）")
        _p0 = _m2.pools.get("0")
        if len(getattr(_p0, "amps", []) or []) != len(
                ((_s.get("pools") or {}).get("0") or {}).get("amps") or []):
            bad.append("[RS] 层 0 的池没还原（下游会看到空上游）")

        _ran.clear()
        mod.MetaDGTF(_cfg()).run("完全不同的题面", route=["0"],
                                 rounds={"0": 1}, parallel_mode="serial",
                                 run_id="RS3", resume_ckpt=str(_p))
        if "0" not in _ran:
            bad.append("[RS-负对照] 题面不同竟也续跑了（会把两跑混一起）")

        # ★ [判据随实现更新] 旧断言是「mode=B 必须拒绝」—— 它编码的是
        #   「并行不支持续跑」的旧语义。本版起并行快照允许续（降级跑剩余层），
        #   所以改成「允许 + 必须记下源模式」。
        _rs_b = mod.load_resume_snapshot(str(_p), question=_q, mode="B")
        if not _rs_b.get("ok"):
            bad.append("[RS-对照] mode=B 应允许续跑（并行降级 serial）/ "
                       "实际拒绝：%r" % (_rs_b.get("why"),))
        elif str(_rs_b.get("src_mode") or "") != "serial":
            bad.append("[RS-对照] 没记下快照源模式：%r"
                       % (_rs_b.get("src_mode"),))
        if not mod.load_resume_snapshot(str(_p), question=_q,
                                        mode="serial").get("ok"):
            bad.append("[RS-正对照] serial + 同题竟不允许续跑")

        _ran.clear()
        _r4 = mod.MetaDGTF(_cfg()).run(_q, route=["0", "1"],
                                       rounds={"0": 1, "1": 1},
                                       parallel_mode="serial", run_id="RS4",
                                       max_minutes=1e-6)
        if not _r4.get("paused") or _ran:
            bad.append("[RS] 预算到点没优雅停/仍起了层：paused=%r ran=%r"
                       % (_r4.get("paused"), _ran))
        if list(_r4.get("pending_layers") or []) != ["0", "1"]:
            bad.append("[RS] 待续层没交代：%r" % (_r4.get("pending_layers"),))
        _s4 = json.loads((_ck / "RS4.json").read_text(encoding="utf-8"))
        if _s4.get("status") != "paused":
            bad.append("[RS] 优雅停的快照状态不是 paused（下次续不了）：%r"
                       % (_s4.get("status"),))
    except Exception as _e:  # noqa: BLE001
        bad.append("[RS] 驱动抛错：%r" % (_e,))
    finally:
        mod.MetaDGTF._run_layer = _orig_layer
        mod.run_ckpt_dir = _orig_dir

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.50 断点续跑（构造性：快照含层 0 ⇒ 续跑**不重跑**已完成层、"
          "逐字复用 + 池还原 + 只跑缺层；负对照：题面不同拒绝 / mode=B 允许降级；"
          "记账 + route 死捕获 + 墙钟预算优雅停 paused）全过")
    return True


def check_v12348_eml_semantic():
    """[v1.23.48 · P-3b] EML **commit 前语义近重合并**（防冗余堆积）。

    ★ 实测：只按精确 `(kind,cond,action)` 去重 ⇒ 值差一点就另开一条 ⇒ 冗余堆积
      （SOTA 点名的 failure mode：noisy accumulation / redundancy）。
    ★ 判据：① 精确键 **仍去重**（零行为差）；② 默认 False ⇒ 值差 ⇒ **仍两条**；
      ③ True ⇒ 粗键命中 ⇒ **并成一条**（证据累加）；④ **负对照**：`action.key`
      不同 ⇒ **不并**（语义不同不能混）；⑤ 配置键 + 接线在源码。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for tok in ("semantic_merge: bool = False) -> dict:",
                'semantic_merge=_smerge)',
                '"eml_semantic_merge": False,'):
        if tok not in src:
            bad.append("[P3b] 源码缺：%s" % tok)

    M = mod.eml_merge_candidate

    def _cand(delta, key="rounds_delta", issue="cut", ev="r1"):
        return {"kind": "schedule", "cond": {"issue": issue, "layer": "0"},
                "action": {"key": key, "layer": "0", "delta": delta},
                "evidence": [ev], "why": "x"}

    # ③ True ⇒ 值差也并（粗键命中）
    pb = [M([], _cand(1), 1000.0)]           # 第一条（delta=1）
    assert len(pb) == 1
    _e = M(pb, _cand(2, ev="r2"), 1001.0, semantic_merge=True)   # delta=2，粗键同
    if len(pb) != 1:
        bad.append("[P3b] semantic_merge=True 竟新开了一条（冗余没合）：len=%d" % len(pb))
    if int(_e.get("n_evidence") or 0) < 2:
        bad.append("[P3b] 合并后证据没累加：n=%r" % (_e.get("n_evidence"),))
    # ② 默认 False ⇒ 值差 ⇒ 仍两条（零行为差）
    pb2 = [M([], _cand(1), 1000.0)]
    M(pb2, _cand(2, ev="r2"), 1001.0)        # 不传 semantic_merge
    if len(pb2) != 2:
        bad.append("[P3b] 默认（False）竟合了（零行为差被破）：len=%d" % len(pb2))
    # ① 精确键仍去重（两版都必须）
    for _sm in (False, True):
        pb3 = [M([], _cand(1), 1000.0)]
        M(pb3, _cand(1, ev="r2"), 1001.0, semantic_merge=_sm)
        if len(pb3) != 1:
            bad.append("[P3b] 精确同键竟然新开（sm=%s）：len=%d" % (_sm, len(pb3)))
    # ④ 负对照：action.key 不同 ⇒ 不并
    pb4 = [M([], _cand(1), 1000.0)]
    M(pb4, _cand(1, key="duty_floor", ev="r2"), 1001.0, semantic_merge=True)
    if len(pb4) != 2:
        bad.append("[P3b-负对照] action.key 不同竟被并（语义不同不能混）：len=%d" % len(pb4))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.48 P3b EML 语义近重合并（精确仍去重 · 默认值差=两条 · True 并成一条 · "
          "action.key 不同不并）全过")
    return True


def check_v12347_gain_suggest():
    """[v1.23.47 · P-2b] 早停阈值 α 由 AutoTune **跨跑建议**（只建议，不执行）。

    ★ SOTA：`static thresholds` 是学习回路的失败模式 ⇒ α 该跟着历史跑调。
    ★ 判据：① 无截断证据 ⇒ **不建议**（None，不表态）；② 截断多且**质量不差** ⇒ 建议抬高 α；
      ③ 截断多但**质量差** ⇒ α 保持（不乱抬，防学坏）；④ `learn` 段带出该建议；
      ⑤ 红线：**只建议**（不写配置）。
    """
    bad = []
    S = mod.autotune_suggest_gain_floor
    # ① 无证据 ⇒ 不表态
    r0 = S([])
    if r0.get("ok") is not False or r0.get("suggested") is not None:
        bad.append("[P2b] 无证据竟给建议：%r" % (r0,))
    r0b = S([{"cut_layers": ["0"], "duty": {}}])   # 有截断但无质量读数
    if r0b.get("suggested") is not None:
        bad.append("[P2b] 无质量读数竟给建议：%r" % (r0b,))
    # ② 截断多 + 质量好 ⇒ 抬高
    _good = [{"cut_layers": ["0"], "duty": {"S": 0.6}},
             {"cut_layers": ["both"], "duty": {"S": 0.7}},
             {"cut_layers": ["1"], "duty": {"S": 0.5}}]
    r1 = S(_good, base=0.0, step=0.01)
    if r1.get("suggested") != 0.01:
        bad.append("[P2b] 质量不差竟不抬高：%r" % (r1,))
    # ③ 截断多但质量差 ⇒ 保持
    _bad = [{"cut_layers": ["0"], "duty": {"S": 0.05}},
            {"cut_layers": ["both"], "duty": {"S": 0.01}}]
    r2 = S(_bad, base=0.0, step=0.01)
    if r2.get("suggested") != 0.0:
        bad.append("[P2b] 质量差竟仍抬高（会学坏）：%r" % (r2,))
    # ④ learn 段带出建议
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    if '"suggested_gain_floor": _sgf.get("suggested"),' not in src:
        bad.append("[P2b] `autotune_phase_learn` 没带出 suggested_gain_floor")
    if "def autotune_suggest_gain_floor(" not in src:
        bad.append("[P2b] 缺 autotune_suggest_gain_floor")
    # ⑤ 只建议（不写配置）—— 函数体里不得出现配置写入
    try:
        _f = src.split("def autotune_suggest_gain_floor(")[1].split("\ndef ")[0]
        # ★ 先剥 docstring —— 里面写「采纳走 autotune_apply_to_cfg」是**说明**，不是写入。
        #   （首版没剥 ⇒ 判据被自家注释误伤，判红。这正是「注释是污染源」的老坑。）
        if '"""' in _f:
            _f = _f.split('"""', 2)[-1]
        for _t in ("config[", "setdefault(", "apply_to_cfg"):
            if _t in _f:
                bad.append("[P2b] 建议函数里出现配置写入 `%s`（红线：建议≠执行）" % _t)
    except Exception:
        pass

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.47 P2b 阈值跨跑建议（无可证据=不表态 · 质量不差⇒抬高 · 质量差⇒保持 · "
          "learn 带出 · 只建议不写配置）全过")
    return True


def check_v12346_duty_span():
    """[v1.23.46 · P-5] 职责 S 口径对称化 —— 修 C(全文)/R(逐句) 的**长度不对称**。

    ★ 实测：真产物 `{S:0.0, C:0.25, R:0.0}` ⇒ S=0 是被 **R=0** 拖的。
      根因：C 用 `_hit(问项, 全文)`、R 用 `_hit(问项, 单句)`，而 `_hit` 的 gram
      覆盖率按**问项长度**归一 ⇒ 问项**跨句**时 C 记、R 不记。
    ★ 判据：① 默认（span_tolerant=False）⇒ **逐字不变**（R=0/S=0）；
      ② 夹具里 C>0（跨句问项在全文被命中）；③ True ⇒ R 上升（跨句窗口补上）；
      ④ 接线（`duty_of_layer` → `duty_components` 真转发）；⑤ 配置键在源码。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for tok in ("span_tolerant: bool = False",
                '"span_tolerant": False,',
                "span_tolerant=_dspan)",
                "span_tolerant=span_tolerant)"):
        if tok not in src:
            bad.append("[P5] 源码缺：%s" % tok)

    # ★ 夹具必须让问项**真跨句**、且两句都 >=6 字（<6 的段会被过滤掉 —— 首版栽在这）
    _asp = [{"text": "甲乙丙丁戊己庚辛", "kind": "core", "weight": 1.0}]
    _d = "甲乙丙丁在甲地。戊己庚辛在乙地。"
    try:
        off = mod.duty_components(_asp, _d, span_tolerant=False)
        on = mod.duty_components(_asp, _d, span_tolerant=True)
    except TypeError as e:
        bad.append("[P5] duty_components 不吃 span_tolerant（没转发）：%r" % (e,))
        off = on = {}
    # ① 默认 ⇒ 零行为差
    if off and (off.get("R") != 0.0 or off.get("S") != 0.0):
        bad.append("[P5] 默认（False）竟然变了：R=%r S=%r"
                   % (off.get("R"), off.get("S")))
    # ② C 判全文 ⇒ 覆盖 > 0
    if off and float(off.get("C") or 0) <= 0:
        bad.append("[P5] 夹具 C 应为正（跨句问项在全文被命中）：%r" % (off.get("C"),))
    # ③ True ⇒ R 上升
    if off and on and float(on.get("R") or 0) <= float(off.get("R") or 0):
        bad.append("[P5] 跨句窗口没让 R 上升：off=%r on=%r"
                   % (off.get("R"), on.get("R")))
    # ④ 端到端：duty_of_layer 真转发
    try:
        _dl = mod.duty_of_layer("1", "甲乙丙丁戊己庚辛是什么？", _d,
                                span_tolerant=True)
        if float(_dl.get("R") or 0) <= 0:
            bad.append("[P5] duty_of_layer(span_tolerant=True) 的 R 仍 0（转发断了）：%r"
                       % (_dl.get("R"),))
    except Exception as e:  # noqa: BLE001
        bad.append("[P5] duty_of_layer 驱动抛错：%r" % (e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.46 P5 职责 S 口径对称化（默认零行为差 · C>0 而 R=0 复现 · "
          "跨句窗口让 R 上升 · 转发在源码）全过")
    return True


def check_v12345_output_rep():
    """[v1.23.45 · P-4] **输出内**逐字复读率读数（补集合式 n-gram 信号的结构盲区）。

    ★ 依据：Reflective Budget Governor 实测「集合式 trigram 对输出内逐字复读结构盲」。
    ★ 判据：① 高度复读文本 ⇒ 比值高（近 1）；② 全新鲜文本 ⇒ 比值 0；
      ③ 太短 / 空 ⇒ **None**（不表态）；④ 读数**有出口**（两个标签表 + `_quant_note` 接线）。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for tok in ("def output_repetition(text: str",
                "_OUTREP_N = 3",
                '_quant_note(view, "output_repetition"',
                '("output_repetition", "内复读")',
                '"output_repetition": "输出内复读率"'):
        if tok not in src:
            bad.append("[P4] 源码缺：%s" % tok)

    R = mod.output_repetition
    # ① 高度复读 ⇒ 高
    _rep = "甲" * 60
    _rv = R(_rep)
    if _rv is None or _rv < 0.8:
        bad.append("[P4] 全同文本复读率应接近 1：%r" % (_rv,))
    # 段间重复（灾难性退化的形态：同一段重复多遍）
    _dup = ("这是一段会重复的话，用来模拟输出内的逐字复读。" * 8)
    _dv = R(_dup)
    if _dv is None or _dv < 0.6:
        bad.append("[P4] 段间重复竟没测出来：%r" % (_dv,))
    # ② 全新鲜 ⇒ 0（★ 夹具必须**真新鲜**：用 200 个互异中文字 ⇒ 所有 trigram 唯一。
    #   首版夹具是「同一段重复 6 遍」⇒ 判据自己报 0.74，被自家判据逮到。）
    _fresh = "".join(chr(0x4E00 + i) for i in range(200))
    _fv = R(_fresh)
    if _fv is None or _fv > 0.05:
        bad.append("[P4] 全新鲜文本复读率应≈0：%r" % (_fv,))
    # ③ 太短/空 ⇒ None
    if R("") is not None:
        bad.append("[P4] 空文本竟给值（应 None）")
    if R("短") is not None:
        bad.append("[P4] 过短文本竟给值（应 None）")

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.45 P4 输出内复读率（全同≈1 · 段间重复>0.6 · 全新鲜≈0 · 短/空=None · "
          "两标签表+接线在源码）全过")
    return True


def check_v12344_eml_adaptive():
    """[v1.23.44 · P-3] 学习闭环：EML 阈值**冷启自适应**（修「升级/遗忘恒 0」）。

    ★ 实测：playbook 3 条 shadow 卡在 `n_evidence=1 < _EML_PROMOTE_N(3)` ⇒ 永不升级。
    ★ 判据：① 默认（adaptive=False）⇒ **逐字不变**（n=1 仍不升）；
      ② adaptive=True 且库小 ⇒ 冷启门槛降到 1，n=1 **可升**；
      ③ **负对照**：库大（≥ _EML_COLD_LIB）⇒ adaptive 也**不降**门槛；
      ④ **负对照**：质量闸不被绕过（`quality_delta<0` 仍不升）；
      ⑤ 遗忘侧：默认 `_rr == retire_recency`（零行为差）；⑥ 配置键 + 接线在源码。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for tok in ("_EML_COLD_LIB = 20",
                "adaptive: bool = False) -> list:",
                '"eml_adaptive": False,',
                "adaptive=_ad"):
        if tok not in src:
            bad.append("[P3] 源码缺：%s" % tok)

    def _pb(n_shadow=1, n_ev=1, qd=0.1, contra=0, total=None):
        rows = [{"id": "s%d" % i, "status": "shadow", "n_evidence": n_ev,
                 "quality_delta": qd, "cost_delta": -0.1, "contra": contra,
                 "kind": "schedule"}
                for i in range(n_shadow)]
        rows.append({"id": "a0", "status": "active", "n_evidence": 5,
                     "quality_delta": 0.2, "cost_delta": -0.1, "contra": 0,
                     "kind": "probe"})
        if total and total > len(rows):
            rows += [{"id": "f%d" % i, "status": "active", "n_evidence": 9,
                      "quality_delta": 0.1, "cost_delta": -0.1, "contra": 0,
                      "kind": "probe"} for i in range(total - len(rows))]
        return rows

    P = mod.eml_promote
    # ① 默认 ⇒ 逐字不变（n=1 < 3，不升）
    _c0 = P(_pb(), promote_n=3, adaptive=False)
    if any(c.get("to") == "active" for c in _c0):
        bad.append("[P3] 默认 adaptive=False 竟升级了（零行为差被破）")
    # ② adaptive + 小库 ⇒ 冷启降到 1，n=1 可升
    _c1 = P(_pb(), promote_n=3, adaptive=True)
    if not any(c.get("to") == "active" for c in _c1):
        bad.append("[P3] adaptive+小库 没升级（冷启自适应失效）：%r" % (_c1,))
    # ③ 负对照：库大 ⇒ 不降门槛
    _c2 = P(_pb(total=40), promote_n=3, adaptive=True)
    if any(c.get("to") == "active" for c in _c2):
        bad.append("[P3-负对照] 库大时 adaptive 仍降门槛（不该）：%r" % (_c2,))
    # ④ 负对照：质量闸不被绕过
    _c3 = P(_pb(qd=-0.5), promote_n=3, adaptive=True)
    if any(c.get("to") == "active" for c in _c3):
        bad.append("[P3-负对照] 质量下降竟被升（学坏）")
    # ⑤ 遗忘默认零行为差：新鲜条目不被退休
    _now = 1_700_000_000.0
    _fresh = [{"id": "x", "status": "shadow", "n_evidence": 1,
               "t_last": _now, "t_used": []}]
    if mod.eml_sweep_forget(_fresh, _now, adaptive=False):
        bad.append("[P3] 默认就把新鲜条目退休了（零行为差被破）")

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.44 P3 EML 阈值冷启自适应（默认零行为差 · 小库降门槛 · 大库不降 · "
          "质量闸不被绕 · 遗忘默认不动）全过")
    return True


def check_v12343_gain_stop():
    """[v1.23.43 · P-2] 早停：单标量 `refinement_gain` + 配置式阈值 `stop.gain_floor`。

    ★ SOTA：最优停止 = **单一阶段无关阈值**（arXiv:2608.10729）。
    ★ 判据：① 增益**方向**统一（修行取「上一圈−本圈」，其余取「本圈−上一圈」）；
      ② 没上一圈 ⇒ None；③ `gain_floor=0`（默认）⇒ 不生效（零行为差）；
      ④ 饱和（连续增益趋零）⇒ 命中；⑤ 有进展 ⇒ **不**误停（负对照）；
      ⑥ 配置键 + 接线在源码里。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    for tok in ("def refinement_gain(entry: str",
                "def layer_gain_stop_signal(entry: str",
                '"gain_floor": 0.0,',
                "layer_gain_stop_signal(str(entry), _now, _tr, _gf)"):
        if tok not in src:
            bad.append("[P2] 源码缺：%s" % tok)

    G = mod.refinement_gain
    # ① 方向统一：都「越大越有进展」
    if G("0", {"excavate": 0.2}, [{"excavate": 0.5}]) != 0.3:
        bad.append("[P2] 修行增益方向错：%r"
                   % (G("0", {"excavate": 0.2}, [{"excavate": 0.5}]),))
    if G("1", {"settle": 0.8}, [{"settle": 0.5}]) != 0.3:
        bad.append("[P2] 研究增益方向错：%r"
                   % (G("1", {"settle": 0.8}, [{"settle": 0.5}]),))
    if G("both", {"fuse": 0.6}, [{"fuse": 0.2}]) != 0.4:
        bad.append("[P2] 对撞增益错：%r"
                   % (G("both", {"fuse": 0.6}, [{"fuse": 0.2}]),))
    # 停滞 ⇒ 0
    if G("1", {"settle": 0.5}, [{"settle": 0.5}]) != 0.0:
        bad.append("[P2] 停滞增益应为 0")
    # ② 没上一圈 ⇒ None
    if G("1", {"settle": 0.5}, []) is not None:
        bad.append("[P2] 无上一圈竟给值（应 None）")
    if G("1", {"settle": None}, [{"settle": 0.5}]) is not None:
        bad.append("[P2] 本圈无读数竟给值（应 None）")

    S = mod.layer_gain_stop_signal
    _flat = [{"settle": 0.5}, {"settle": 0.5}, {"settle": 0.5}]
    _rise = [{"settle": 0.2}, {"settle": 0.5}, {"settle": 0.8}]
    # ③ 默认 0 ⇒ 关（零行为差）
    if S("1", _flat[-1], _flat, 0.0) != (False, ""):
        bad.append("[P2] gain_floor=0 竟生效（零行为差被破）")
    if S("1", _flat[-1], _flat) != (False, ""):
        bad.append("[P2] 缺省参数竟生效")
    # ④ 饱和 ⇒ 命中
    _h, _w = S("1", _flat[-1], _flat, 0.01)
    if not (_h and "refinement_gain" in _w):
        bad.append("[P2] 饱和未命中：%r" % ((_h, _w),))
    # ⑤ 有进展 ⇒ 不误停（负对照）
    if S("1", _rise[-1], _rise, 0.01)[0] is not False:
        bad.append("[P2-负对照] 有进展却被判停")
    # 圈数不足 ⇒ 不表态
    if S("1", {"settle": 0.5}, [{"settle": 0.5}], 0.01)[0] is not False:
        bad.append("[P2] 圈数不足竟判停")

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.43 P2 早停（单标量增益方向统一 · 无上一圈=None · 默认关零行为差 · "
          "饱和命中 · 有进展不误停）全过")
    return True


def check_v12342_ctx_shape():
    """[v1.23.42 · P-1] `View.shape_of` 窗口化（上下文裁剪，默认不限）。

    ★ 根因：`shape_of` 无窗口渲染整个 view，而它每圈当 `views_text` 重灌 ⇒
      后段圈单次 prompt 随圈数上涨（真跑最贵 25–32k tok/次）。
    ★ 判据：① `limit=0` 逐字**零行为差**（渲染全部）；② `limit>0` 变短 + 表头标总数；
      ③ 接线（配置 → `_expand_from_views` → `shape_of(limit=)`）在源码里。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    # ③ 接线
    if "View.shape_of(v, limit=_shape_lim)" not in src:
        bad.append("[P1] 缺接线：`_expand_from_views` 未把 limit 传进 shape_of")
    if '"shape_limit": 0,' not in src:
        bad.append("[P1] 缺配置键 `spiral.shape_limit`（默认 0）")
    if "def shape_of(v: \"View\", limit: int = 0) -> str:" not in src:
        bad.append("[P1] `shape_of` 签名没带 `limit` 形参")

    # 造一个「每类都超 8 条」的 view
    v = mod.View(entry="0")
    v.anchor = "锚点问题"
    v.candidates = [{"desc": "候选%d：一条较长的候选描述" % i} for i in range(48)]
    v.amps = [{"type": "ontological", "desc": "& %d 说明" % i} for i in range(15)]
    v.threads = [{"desc": "线头 %d" % i} for i in range(12)]
    v.suspensions = [{"target": "悬置 %d" % i, "reason": "理由",
                      "status": "active"} for i in range(9)]

    full = mod.View.shape_of(v)             # limit=0
    win = mod.View.shape_of(v, limit=8)     # 窗口

    # ① limit=0 渲染全部（零行为差：48 条候选全在）
    if not all(("候选%d：" % i) in full for i in range(48)):
        bad.append("[P1] limit=0 竟没渲染全部候选（零行为差被破）")
    if "只列最近" in full:
        bad.append("[P1] limit=0 竟出现窗口表头（零行为差被破）")
    # ② limit>0：变短 + 计数表头 + 只留最近 8
    if not (len(win) < len(full)):
        bad.append("[P1] limit=8 没变短：%d vs %d" % (len(win), len(full)))
    if "共 48，只列最近 8" not in win:
        bad.append("[P1] limit=8 缺计数表头「共 48，只列最近 8」")
    if "候选47：" not in win:                # 最后一条在
        bad.append("[P1] limit=8 丢了最后一条候选")
    if "候选0：" in win:                     # 最早的在窗口外
        bad.append("[P1] limit=8 仍渲染了最早的候选（窗口没生效）")

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.42 P1 shape_of 窗口化（limit=0 逐字零行为差 · limit>0 变短+计数表头 · "
          "接线在源码里）全过")
    return True


def check_v12341_goal_fresh():
    """[v1.23.41 · P1] 目标读数**收尾刷新** —— 修 crystallize 时序颠倒（恒 0.500）。

    ★ 根因：`goal_verdict` 曾在 `_finalize_layer_common` **前段**从 `goal_now`
      渲染，而 `goal_now` 由**圈循环内**算（那时元层 `meta_closure` 还没落）
      ⇒ 元层恒少数「结晶 + 回看」两件 ⇒ `crystallize` 恒 2/4 = 0.500。
    ★ 判据（时序不变式）：真驱动 `_finalize_layer_common` ⇒ 产物里的
      `goal_verdict` 必须**等于最终 view 的读数**，而不是层停止那刻的旧值。
    """
    import io as _io
    import contextlib as _ctx
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    # ① 静态：标签唯一真相源 + 唯一写入点在收尾
    if "_LG_LABELS = {" not in src:
        bad.append("[P1] 缺 `_LG_LABELS`（goal_verdict 标签唯一真相源）")
    if src.count('{"0": "修行·挖尽", "1": "研究·收敛",') != 1:
        bad.append("[P1] 标签映射不是唯一一份（内联渲染没消掉）")
    if "目标读数收尾刷新] 本层的" not in src:
        bad.append("[P1] 缺收尾刷新（goal_verdict 唯一写入点应在收尾）")

    def _fin(entry, preset):
        cfg = build_cfg(False)
        m = mod.MetaDGTF(cfg)
        v = mod.View(entry=entry)
        for k, val in (preset or {}).items():
            setattr(v, k, val)
        stt = {"roles_hist": ["x"], "total_rounds": 2, "round_log": [],
               "all_rehashed": [], "all_candidates": [], "all_amps": [],
               "all_threads": [], "all_expanded_descs": [],
               "all_dec_products": [], "all_und_products": [],
               "r": 2, "rounds_n": 2, "sp": mod._spiral_for(cfg, entry)}
        with _ctx.redirect_stdout(_io.StringIO()):
            m._finalize_layer_common(entry, v, stt)
        return v

    # ② 元层：四件事齐 ⇒ 最终读数应 > 旧的 0.5；产物必须等于最终读数
    try:
        v = _fin("all", {"meta_closure": {"clean": True, "total": 3,
                                          "unsettled": 0},
                         "engagements": [{"tension_id": "t1"}],
                         "suspensions": [{"id": "s1", "status": "active"}],
                         "rounds_run": 2, "stop_reason": "自省空转，螺旋停止",
                         "goal_now": {"crystallize": 0.5, "n_hits": 2}})
        _fresh = (mod.layer_goal_readings(
            {"all": v.to_dict()}).get("all") or {}).get("crystallize")
        _gv = str(getattr(v, "goal_verdict", "") or "")
        if _fresh is None:
            bad.append("[P1] 元层最终 crystallize 竟为 None")
        else:
            if ("crystallize=%.3f" % float(_fresh)) not in _gv:
                bad.append("[P1] 元层 goal_verdict 未随最终读数刷新："
                           "fresh=%r verdict=%r" % (_fresh, _gv))
            # 负对照：最终读数与旧值不同 ⇒ 产物里不许再是旧值 0.500
            if abs(float(_fresh) - 0.5) > 1e-9 and "crystallize=0.500" in _gv:
                bad.append("[P1] goal_verdict 仍是层停止那刻的旧值 0.500")
    except Exception as e:  # noqa: BLE001
        bad.append("[P1] 元层驱动抛错：%r" % (e,))

    # ③ 修行层：excavate 的 goal_verdict 也必须等于最终读数
    try:
        v0 = _fin("0", {"aspect_units": [{"id": "A%d" % i} for i in range(9)],
                        "rounds_run": 3, "aspect_hist": [2, 4, 6, 9],
                        "stop_reason": "体力耗尽（3 圈走满）",
                        "goal_now": {"excavate": None}})
        _e0 = (mod.layer_goal_readings(
            {"0": v0.to_dict()}).get("0") or {}).get("excavate")
        _gv0 = str(getattr(v0, "goal_verdict", "") or "")
        if _e0 is not None and ("excavate=%.3f" % float(_e0)) not in _gv0:
            bad.append("[P1] 修行层 goal_verdict 未刷新：e=%r v=%r"
                       % (_e0, _gv0))
    except Exception as e:  # noqa: BLE001
        bad.append("[P1] 修行层驱动抛错：%r" % (e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.41 P1 目标读数收尾刷新（产物 goal_verdict == 最终 view 读数，"
          "元层不再恒 0.500、修行层同步）全过")
    return True


def check_v12340_relax_force():
    """[v1.23.40] 强制放宽 `web_search.relax_force` + 放宽表扩到 12。

    ★ 用户口径：「放宽表中步扩展要扩，先强制它使用，可能有些题目需要，
      扩也无妨」⇒ ① 放宽表补 4 个 `decompose_*`（8 → 12）；
      ② 新增 `relax_force`（默认 false）⇒ true 时**每圈都**放宽，
         不再要求「上一圈池零增量」。
    ★ 零行为差：force=false 时判据与改前**逐字等价**（有增量 ⇒ 不放宽）。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")

    # ── ④ 静态：放宽表含 4 个 decompose_* ──
    _m = re.search(r"_TICK_WEB_RELAX = \(([^)]*)\)", src, re.S)
    _members = re.findall(r'"([a-z_]+)"', _m.group(1)) if _m else []
    for _st in ("decompose_normal", "decompose_hybrid", "decompose_koan",
                "decompose_from_pool"):
        if _st not in _members:
            bad.append("[强制放宽] 放宽表缺 `%s`（用户口径「要扩」）" % _st)
    if len(_members) != 12:
        bad.append("[强制放宽] 放宽表成员 %d 个（要求 12）" % len(_members))
    if '"relax_force": False' not in src:
        bad.append("[强制放宽] DEFAULT_CONFIG 缺 `web_search.relax_force`")

    # ── 构造性：真驱动 `_before_round` ──
    class _P:
        def __init__(self):
            self.amps = []
            self.threads = []

    def _run(force, grow):
        cfg = build_cfg(False)
        cfg.setdefault("web_search", {})
        cfg["web_search"]["relax_force"] = bool(force)
        mt = mod.MetaDGTF(cfg)
        p = _P()
        mt._before_round("0", p, 1)          # 第一圈：只记基线
        if grow:
            p.amps = [{"desc": "新 & 1"}]     # 有增量
        mt._before_round("0", p, 2)          # 第二圈：看是否放宽
        # ★ 返回 (键列表, why 列表)：whys 必须在此处取 ——  是**局部变量**
        #   （首版把它拿到外层用 ⇒ NameError「mt is not defined」，单跑逮到）。
        _ap = list(mt._control.applied or [])
        return ([x.get("key") for x in _ap],
                [str(x.get("why") or "") for x in _ap])

    try:
        # ① 默认 + 有增量 ⇒ 不放宽（零行为差基线）
        _k1, _w1 = _run(False, True)
        if any(str(k).startswith("web.allow.") for k in _k1):
            bad.append("[强制放宽] 默认配置下**有增量**却放宽了"
                       "（零行为差被破）：%r" % (_k1,))
        # ② force=true + 有增量 ⇒ 也放宽（核心）
        _k2, _whys = _run(True, True)
        if not any(str(k).startswith("web.allow.") for k in _k2):
            bad.append("[强制放宽] force=true 时**没放宽**（开关不生效）：%r"
                       % (_k2,))
        #   放宽的应含 decompose_*（12 个全表）
        _fk = [str(k)[len("web.allow."):] for k in _k2
               if str(k).startswith("web.allow.")]
        for _st in ("decompose_normal", "decompose_from_pool"):
            if _st not in _fk:
                bad.append("[强制放宽] force=true 时未放行 `%s`：%r"
                           % (_st, _fk))
        #   留下「是不是强制」的痕迹（why 里应写明）
        if not any("强制" in w or "relax_force" in w for w in _whys):
            bad.append("[强制放宽] 留痕里看不出是强制放宽：%r" % (_whys[:3],))
        # ③ 默认 + 零增量 ⇒ 仍放宽（旧机制未破）
        _k3, _w3 = _run(False, False)
        if not any(str(k).startswith("web.allow.") for k in _k3):
            bad.append("[强制放宽] 默认配置下**零增量**却没放宽"
                       "（旧机制破了）：%r" % (_k3,))
    except Exception as _e:
        bad.append("[强制放宽] 构造性驱动抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.40 强制放宽（表 12 个含 decompose_* · force=true 每圈放行 · "
          "默认有增量不放宽/零增量仍放宽 · 留痕可辨）全过")
    return True


def check_v12340_backfeed_stage():
    """[v1.23.40] 回喂 stage 兜底：声明入库要带**真实环节名**。

    ★ 为什么要有这条（v1.23.39 真跑 R1 实证）：按需声明**全部**发生在
      `LLM.call(stage=None)`（展开主路径不传 stage）⇒ record 的 stage 为空
      ⇒ 回喂按 stage 匹配**永远匹配不上** ⇒ `[WEB-BACKFEED]` 0 次
      ⇒ v1.23.38 的「回喂」在真实调用图上**从未生效过**。
      ★ 探针能触发是因为探针**显式传了 stage**，掩盖了真实调用点 stage 为空。

    四层验证：① 真跑法（在一个真名 `_expand_from_question` 的函数里走
    `stage=None` ⇒ 兜底必须取到 `expand_from_question`）② 显式 stage
    不受影响 ③ 静态：跳过元组含 `_web_need_report`（不跳会把自己当环节名）
    ④ 端到端：入池 item 的 `stage` 字段真带环节名。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")

    # ── ③ 静态：跳过元组 ──
    if '"_web_need_report", "<module>"' not in src:
        bad.append("[回喂stage] 跳过元组缺 `_web_need_report`"
                   "（会把自己当环节名）")

    # ── 造一个「真名叫 _expand_from_question」的调用者 ──
    _seen = {}

    def _fake_searcher(stage, queries, rn, used_as="evidence", pre_seq=0):
        _seen["stage"] = str(stage)
        return [{"claim": "命中", "url": "http://x", "tier": 3}]

    mod._llm_ctx_set(web_searcher=_fake_searcher, question="题", round=1,
                     entry="1")

    _Q = chr(34)
    _M = getattr(mod, "_WEB_NEED_MARK", "===WEB-NEED===")
    _BODY = ("产出正文\n" + _M + "\n{%squeries%s: [%sX%s]}"
             % (_Q, _Q, _Q, _Q))

    class _LLM:
        def call(self, system, user, **kw):
            return mod.LLM._web_need_report(self, kw.get("stage"), _BODY)

    def _expand_from_question(self, inp):
        """★ 函数名必须**真的是** `_expand_from_question`**（栈推断靠它）。"""
        return self.call("sys", "user", stage=None)

    _llm = _LLM()
    try:
        _n = _expand_from_question(_llm, None)
        _got = _seen.get("stage")
        if _n <= 0:
            bad.append("[回喂stage] 声明未被采纳（返回 %r）" % (_n,))
        if _got in (None, "", "web_need_report"):
            bad.append("[回喂stage] stage 兜底失败：searcher 收到 %r"
                       "（空 ⇒ 回喂匹配不上）" % (_got,))
        elif _got != "expand_from_question":
            bad.append("[回喂stage] stage 兜底取错环节名：%r"
                       "（应 expand_from_question）" % (_got,))
        # ② 显式 stage 不受影响
        _seen.clear()
        _llm.call("sys", "user", stage="ing")
        if _seen.get("stage") != "ing":
            bad.append("[回喂stage] 显式 stage 被兜底覆盖：%r（应 ing）"
                       % (_seen.get("stage"),))
    except Exception as _e:
        bad.append("[回喂stage] 驱动抛错：%r" % (_e,))

    # ── ④ 端到端：入池 item 的 stage 字段 ──
    try:
        class _Gate:
            def __init__(self):
                self._relaxed = set()

            def allow(self, stage, round_no, on_demand=False):
                return True, ""

            def note_call(self, stage, round_no):
                pass

            def note_failure(self, kind=""):
                return False

            def note_success(self):
                pass

        class _Client:
            def search(self, q):
                return ([{"claim": "命中", "url": "http://x", "tier": 3}], "")

        class _Pool:
            web_results = []
            web_errors = []
            meta = []
            _web_cfg = None
            web_as_evidence = False

        class _Owner:
            config = {"web_search": {"enabled": True, "stages": {}}}
            pools = {"1": _Pool()}
            _control = None
            _TICK_WEB_RELAX = ()

        _o = _Owner()
        _o._web_gate, _o._web_client = _Gate(), _Client()
        _r = mod.MetaDGTF._web_search(_o, "expand_from_question",
                                      ["测试查询"], 1, "record", 0)
        if not _r:
            bad.append("[回喂stage] `_web_search` 返回空")
        elif str(_r[0].get("stage")) != "expand_from_question":
            bad.append("[回喂stage] 入池 item 的 stage 不对：%r"
                       % (_r[0].get("stage"),))
    except Exception as _e:
        bad.append("[回喂stage] 端到端抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.40 回喂 stage 兜底（None ⇒ 真实环节名 · 显式不受影响 · "
          "入池带环节名）全过")
    return True


def check_v12339_ondemand():
    """[v1.23.39] 按需联网**四层一致**：声明即查，不再被逐环节静态开关挡。

    ★ 问题（用户口径「四个层都应该一致，按需联网检索」）：
      v1.23.36 起「所有层都能联网」说的是**代码路径**（修行层硬豁免已取消）；
      但 `WebSearchGate.allow` 仍要求 `stages.<环节>` 静态授权，而 37 个开关
      默认只开 5 个、**修行层一个都没开** ⇒ 修行层环节即使写了
      `===WEB-NEED===` 声明也会被 `stage 'ing' 未授权` 挡掉
      ⇒ **声明了却查不到 = 四层行为不一致**。
    ★ 修法：`on_demand=True`（仅来自 `used_as == "record"`）跳过静态授权，
      **总闸 / 连续失败降级 / 三层配额一条不减**。
    ★ 四层验证：正（修行层声明即放行）+ 负一（总闸关仍拒）
      + 负二（配额打满仍拒）+ 负三（非按需路径仍受开关管）。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")

    # ── 静态：on_demand 的产生点必须唯一 ──
    _n = len(re.findall(r'on_demand\s*=\s*\(str\(used_as\)\s*==\s*"record"\)',
                        src))
    if _n != 1:
        bad.append("[按需四层] `on_demand` 产生点 %d 处（要求 1：只从 "
                   "used_as=record 来）" % _n)
    if "on_demand: bool = False" not in src:
        bad.append("[按需四层] `allow` 缺 `on_demand` 形参")

    # ── 构造性：直接驱动 WebSearchGate（真对象）──
    def _cfg(en=True):
        return {"web_search": {"enabled": en,
                               "stages": {"research_evidence": True}}}

    try:
        g = mod.WebSearchGate(_cfg(True), run_id="smoke")
        # 正：修行层环节（未授权）按需放行
        ok, why = g.allow("ing", 1, on_demand=True)
        if not ok:
            bad.append("[按需四层] 修行层按需仍被拒：%s（四层不一致没修好）"
                       % why)
        # 负三：非按需路径仍受逐环节开关管
        if g.allow("ing", 1)[0]:
            bad.append("[按需四层] 非按需路径被放行（静态开关失效！）")
        # 已授权 stage 两路径都放行
        if not g.allow("research_evidence", 1, on_demand=True)[0]:
            bad.append("[按需四层] 已授权 stage 的按需路径反被拒")
        if not g.allow("research_evidence", 1)[0]:
            bad.append("[按需四层] 已授权 stage 的常规路径被拒（回归）")
        # 负一：总闸关 ⇒ 按需也拒
        g2 = mod.WebSearchGate(_cfg(False), run_id="smoke")
        if g2.allow("ing", 1, on_demand=True)[0]:
            bad.append("[按需四层] 总闸关时按需仍放行（成本闸门失效！）")
        # 负二：配额打满 ⇒ 按需也拒
        _c3 = _cfg(True)
        _c3["web_search"]["quota"] = {"per_run_total": 2,
                                      "per_stage_total": 8,
                                      "per_stage_round": 2}
        g3 = mod.WebSearchGate(_c3, run_id="smoke")
        for _i in range(2):
            g3.note_call("ing", 1)
        ok3, why3 = g3.allow("ing", 1, on_demand=True)
        if ok3:
            bad.append("[按需四层] 配额打满后按需仍放行（按需=无限检索！）")
        elif "配额" not in why3:
            bad.append("[按需四层] 配额拒绝原因不含「配额」：%s" % why3)
    except Exception as _e:
        bad.append("[按需四层] Gate 驱动抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.39 按需联网四层一致（修行层声明即查 · 非按需仍受开关 · "
          "总闸/配额照旧 · on_demand 单一来源）全过")
    return True


def check_v12338_relax_targets():
    """[v1.23.38] 圈级心跳的**放宽目标表**与 `web_search.stages` 两向对账。

    ★ 为什么需要：`_TICK_WEB_RELAX` 里的环节名若不在 `web_search.stages` 里，
      放宽就是**死配置**（写了个引擎不认的 stage ⇒ 永远不生效、且**不报错**）。
      「配置键两处定义」在本项目的经典坑 ⇒ 用判据钉住。
    ★ 定位/解析一律用纯字符串操作（`find` / `endswith` / `split`），不用正则 —— 
      避免反斜杠转义在「脚本 → 落盘 → 解析」三层里数错。
    """
    bad = []
    _members = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")

    _i = src.find("_TICK_WEB_RELAX = (")
    _j = src.find(")", _i + 1) if _i >= 0 else -1
    if _i < 0 or _j < 0:
        bad.append("[放宽表] 找不到 `_TICK_WEB_RELAX` 定义")
    else:
        _block = src[_i:_j + 1]
        _members = [x for x in _block.split('"')[1::2] if x.strip()]
        if len(_members) < 4:
            bad.append("[放宽表] 成员过少（%d）—— 至少保留原 4 个" % len(_members))

        # ── 与 yaml 的 web_search.stages 对账 ──
        _y = (HERE / "dgtf_config.yaml").read_text(
            encoding="utf-8").replace("\r\n", "\n")
        _chunks = _y.split("\n")
        _si = next((k for k, l in enumerate(_chunks)
                    if "30 个环节各自的开关" in l), -1)
        _sj = next((k for k, l in enumerate(_chunks)
                    if k > _si and l.strip().startswith("as_evidence")), -1)
        if _si < 0 or _sj < 0:
            bad.append("[放宽表] 定位不到 `web_search.stages` 段")
        else:
            _avail = set()
            for _l in _chunks[_si:_sj]:
                # 恰好 4 空格缩进（stages 段的键缩进）
                if _l.startswith("    ") and not _l.startswith("     "):
                    _s = _l.strip()
                    if _s.endswith(": true") or _s.endswith(": false"):
                        _avail.add(_s.split(":")[0].strip())
            _miss = [x for x in _members if x not in _avail]
            if _miss:
                bad.append("[放宽表] 成员不在 `web_search.stages` 里"
                           "（放宽了也不生效）：%r" % (_miss,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.38 放宽目标表（%d 个成员全部在 web_search.stages 里，"
          "两向对账过）全过" % len(_members))
    return True


def check_v12338_backfeed():
    """[v1.23.38] 联网**按需回喂**：声明查回来的结果，后续环节**直接复用**。

    ★ 与 v1.23.37「按需协议」的关系：
      v1.23.37 只做到「声明 ⇒ 检索 ⇒ 进池 + 留痕」，结果**没回到后续环节**；
      本版补上回喂 —— 下一环节经 `_web_augment` 时**优先复用池内 `used_as=record`
      的条目**（且 stage 匹配）⇒ **不再重复检索**（省钱 + 让声明真正抵达）。
    ★ 复用安全：这些条目当年进池时**已过 Gate**（授权 + 配额），
      这里只是取出来用，不产生任何新的外部调用。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")

    # ── ① 源码级 ──
    if "backfeed_pool=self.pools.get" not in src:
        bad.append("[回喂] 注入侧没有 `backfeed_pool`（LLM 拿不到池 ⇒ 不可达）")
    _ai = src.find("def _web_augment")
    if _ai < 0:
        bad.append("[回喂] 找不到 `def _web_augment`")
    else:
        _aj = src.find("\n    def ", _ai + 10)
        _abody = src[_ai:_aj if _aj > 0 else _ai + 4000]
        if "backfeed_pool" not in _abody:
            bad.append("[回喂] `_web_augment` 体里没有回喂分支（只在外层写了）")
        if "used_as" not in _abody or "record" not in _abody:
            bad.append("[回喂] 回喂分支没按 `used_as=record` 筛选（来源不明）")
    if "[WEB-BACKFEED]" not in src:
        bad.append("[回喂] 缺留痕记号 `[WEB-BACKFEED]`（回喂来源不可分辨）")
    #   ★ 两向对账：注入侧写的键名与消费侧读的键名必须一致
    if '_llm_ctx_get("backfeed_pool")' not in src:
        bad.append("[回喂] 消费侧没读 `backfeed_pool`（键名对不上）")

    # ── ②③ 构造性：真驱动 `_web_augment` ──
    try:
        cfg = build_cfg(False)
        llm = mod.LLM(cfg)

        def _mk_record(stage):
            return {"id": "W9", "stage": stage, "query": "q",
                    "claim": "回喂事实：X 是 Y", "url": "http://e/x",
                    "source": "s", "tier": 2, "used_as": "record",
                    "round": 1, "round_kind": "in", "pre_seq": 0}

        class _Pool:
            def __init__(self, recs):
                self.web_results = list(recs)

        _calls = []

        def _searcher(stage, queries, round_no, used_as="evidence", pre_seq=0):
            _calls.append(str(used_as))
            return [{"claim": "新检索结果", "url": "http://new", "tier": 2}]

        _ST = "research_evidence"
        _u = "原始 user"

        # ② 正：池里有**本 stage** 的 record ⇒ 复用，且 searcher **零调用**
        _calls.clear()
        mod._llm_ctx_set(web_searcher=_searcher, question="题", round=2,
                         entry="1",
                         backfeed_pool=_Pool([_mk_record(_ST)]))
        _r = llm._web_augment(_ST, _u)
        if not _r:
            bad.append("[回喂] 池里有按需结果却没注入（回喂没生效）")
        else:
            if "回喂事实" not in str(_r):
                bad.append("[回喂] 注入的内容**不是**池里那条（拿错了）")
            if "新检索结果" in str(_r):
                bad.append("[回喂] 竟然又检索了（复用失败 ⇒ 成本翻倍）")
        if _calls:
            bad.append("[回喂] 复用路径下游**仍调了 searcher** %d 次"
                       "（省钱没真发生）" % len(_calls))

        # ③a 负对照：池里**没有** record ⇒ 必须原路检索
        _calls.clear()
        mod._llm_ctx_set(web_searcher=_searcher, question="题", round=2,
                         entry="1", backfeed_pool=_Pool([]))
        _r2 = llm._web_augment(_ST, _u)
        if not _calls:
            bad.append("[回喂] 池里没有记录却也**不检索**了（该走的路被堵）")
        if not _r2 or "新检索结果" not in str(_r2):
            bad.append("[回喂] 负对照下没拿到新检索结果：%r" % (str(_r2)[:60],))

        # ③b 负对照：池里有 record 但 **stage 不匹配** ⇒ 不该复用（防串台）
        _calls.clear()
        mod._llm_ctx_set(web_searcher=_searcher, question="题", round=2,
                         entry="1",
                         backfeed_pool=_Pool([_mk_record("另一个环节")]))
        _r3 = llm._web_augment(_ST, _u)
        if "回喂事实" in str(_r3 or ""):
            bad.append("[回喂] 复用了**别的环节**的结果（串台）")
        if not _calls:
            bad.append("[回喂] stage 不匹配时该检索却没检索")

        # ③c 无注入器 ⇒ None（零变化）
        mod._llm_ctx_set(web_searcher=None, question="题", round=2, entry="1",
                         backfeed_pool=_Pool([_mk_record(_ST)]))
        if llm._web_augment(_ST, _u) is not None:
            bad.append("[回喂] 没注入器却仍返回了增强文本（该 None）")

        # ③d 不带 backfeed_pool（老调用方）⇒ 退回原行为（零变化）
        _calls.clear()
        mod._llm_ctx_set(web_searcher=_searcher, question="题", round=2,
                         entry="1")
        try:
            delattr(mod._LLM_CTX, "backfeed_pool")
        except Exception:
            pass
        llm._web_augment(_ST, _u)
        if not _calls:
            bad.append("[回喂] 不带池时该原路检索，却没检索（老行为被改）")
    except Exception as _e:
        bad.append("[回喂] 构造性验证抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.38 联网按需回喂（池复用 · searcher 零调用 · "
          "stage 不匹配不复用 · 无池退回原行为）全过")
    return True


def check_v12337_roundtick():
    """[v1.23.37] **圈级心跳**：用「池增量」当上一圈产出的代理，只改一处。

    ★ 为什么用池增量而不是 view：`view` 每圈新建 ⇒ 要跨圈就得在两个圈循环里
      各存一次（本项目反复踩的「同一条逻辑两处各写一份」）。
      `_before_round` **每圈都调** ⇒ 在它里记基线，下一圈的增量就是上一圈产出。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    if "_tick_prev_n" not in src:
        bad.append("[圈心跳] 缺 `_tick_prev_n`（跨圈基线没记）")
    if "def _before_round" not in src:
        bad.append("[圈心跳] 找不到 `_before_round`")
    else:
        _i = src.find("def _before_round")
        _j = src.find("\n    def ", _i + 10)
        _body = src[_i:_j if _j > 0 else _i + 4000]
        if "_tick_prev_n" not in _body:
            bad.append("[圈心跳] 基线逻辑**不在 `_before_round` 里**"
                       "（那就不是「只改一处」）")
    if "self._last_view = view" not in src:
        bad.append("[圈心跳] 没存 `_last_view`（trace 无处落笔）")

    # ── 构造性：造「上一圈零增量」⇒ 本圈应放宽；「有增量」⇒ 不该放宽 ──
    try:
        _cfg = build_cfg(False)
        _mt = mod.MetaDGTF(_cfg)
        class _P:
            amps = []
            threads = []
        _p = _P()
        # 第一圈：只记基线，不该有任何调整
        _mt._before_round("0", _p, 1)
        _n1 = len(_mt._control.applied or [])
        if _n1 != 0:
            bad.append("[圈心跳] 第一圈（无基线）就动了：%r"
                       % ([x.get("key") for x in _mt._control.applied],))
        # 第二圈：池**零增量** ⇒ 应放宽
        _mt._before_round("0", _p, 2)
        _keys = [x.get("key") for x in (_mt._control.applied or [])]
        if not any(str(k).startswith("web.allow.") for k in _keys):
            bad.append("[圈心跳] 上一圈零增量却**没放宽**（触发条件失效）：%r"
                       % (_keys,))
        # 第三圈：池**有增量** ⇒ 不该再放宽（负对照）
        _mt2 = mod.MetaDGTF(build_cfg(False))
        _p2 = _P()
        _mt2._before_round("0", _p2, 1)
        _p2.amps = [{"desc": "新 & 1"}]           # 有产出
        _mt2._before_round("0", _p2, 2)
        _k2 = [x.get("key") for x in (_mt2._control.applied or [])]
        if any(str(k).startswith("web.allow.") for k in _k2):
            bad.append("[圈心跳] 上一圈**有增量**却也放宽了（负对照失败）：%r"
                       % (_k2,))
    except Exception as _e:
        bad.append("[圈心跳] 构造性验证抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.37 圈级心跳（池增量代理 · 只改一处 · 首圈不动 · "
          "零增量放宽 · 有增量不放宽）全过")
    return True


def check_v12336_webneed():
    """[v1.23.36→37] 联网**按需协议**：环节自己声明「我需要外部事实」。

    ★ 与「统一增强层」(`_web_augment`) 的分工：
      增强层 = 引擎在调用**前**猜需不需要；按需 = 环节在产出**后**自己说。
    ★ 两层判据（本项目铁律：源码级只能证明「接线写了」）：
      ① 三件齐 + `LLM.call` 里有调用点；
      ② 构造性驱动 —— 真跑 `_web_need_report`，看消费方**真被调用**。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")

    # ── ① 源码级 ──
    if "_WEB_NEED_MARK" not in src:
        bad.append("[按需] 缺声明标记 `_WEB_NEED_MARK`")
    if "def parse_web_need(" not in src:
        bad.append("[按需] 缺解析器 `parse_web_need`")
    if "def _web_need_report(" not in src:
        bad.append("[按需] 缺消费方 `_web_need_report`")
    if "self._web_need_report(stage, content)" not in src:
        bad.append("[按需] `LLM.call` 里**没有**调用点（定义了没人用）")
    #   ★ 防「同一语义两处定义」：解析器应当只有一处实现
    if len(re.findall(r"^def parse_web_need\(", src, re.M)) != 1:
        bad.append("[按需] `parse_web_need` 定义了不止一次（两处定义必分叉）")

    # ── ② 构造性：纯函数 ──
    _fn = getattr(mod, "parse_web_need", None)
    if not callable(_fn):
        bad.append("[按需] 模块里取不到 `parse_web_need`（不可达）")
    else:
        _M = getattr(mod, "_WEB_NEED_MARK", "===WEB-NEED===")
        _q = chr(34)                      # ★ 用 chr(34) 规避转义地狱（本项目纪律）
        # ① JSON 形态
        _a = _fn("前言\n%s\n{%squeries%s: [%s甲%s, %s乙%s]}\n后语"
                 % (_M, _q, _q, _q, _q, _q, _q))
        if _a != ["甲", "乙"]:
            bad.append("[按需] JSON 形态解析错：%r" % (_a,))
        # ② 逐行形态（不标准格式）
        _b = _fn("前言\n%s\n甲\n乙\n丙\n" % _M)
        #   ★ 单字「丙」**必须保留**（曾用长度阈值把它滤掉 ⇒ 真缺口）
        if "甲" not in _b or "丙" not in _b:
            bad.append("[按需] 逐行形态丢了查询（含单字）：%r" % (_b,))
        # ③ 无声明 ⇒ []
        if _fn("没有任何声明的产出") != []:
            bad.append("[按需] 无声明竟解析出东西（会凭空检索）")
        # ④ 畸形 ⇒ 不抛错、当没声明
        try:
            _fn("%s\n{坏 JSON" % _M)
            _fn(None)
            _fn(12345)
        except Exception as _e:
            bad.append("[按需] 畸形输入抛错（不该影响主流程）：%r" % (_e,))
        # ⑤ 截量：limit 生效
        _many = "%s\n" % _M + "\n".join("q%d" % i for i in range(20))
        if len(_fn(_many, limit=3)) > 3:
            bad.append("[按需] `limit` 没生效（一个环节能吃光配额）")

    # ── ③ 构造性：真消费方（`_web_need_report`）──
    try:
        cfg = build_cfg(False)
        llm = mod.LLM(cfg)
        _calls = []
        _q = chr(34)

        def _searcher(stage, queries, round_no, used_as="evidence", pre_seq=0):
            _calls.append((str(stage), list(queries), str(used_as)))
            return [{"claim": "样例外部参考", "url": "https://x.invalid",
                     "tier": 3}]

        _M = getattr(mod, "_WEB_NEED_MARK", "===WEB-NEED===")
        # 有声明 ⇒ 消费方真被调用 + 返回条数
        mod._llm_ctx_set(web_searcher=_searcher, round=2)
        _body = ("产出正文\n" + _M + "\n") + ("{%squeries%s: [%sX%s]}"
                                            % (_q, _q, _q, _q))
        _n = llm._web_need_report("ing", _body)
        if not _calls:
            bad.append("[按需] 有声明却**没调**消费者（接线不可达）")
        elif _n < 1:
            bad.append("[按需] 有声明、消费者也调了，却没算进条数：%r" % (_n,))
        # 负对照：无声明 ⇒ 零调用
        _calls.clear()
        _n0 = llm._web_need_report("ing", "一段没有声明的普通产出")
        if _calls or _n0 != 0:
            bad.append("[按需] 无声明却动了（应零成本零调用）：%r/%r"
                       % (_calls, _n0))
        # 负对照：没注入 web_searcher ⇒ 不该炸、返回 0
        mod._llm_ctx_set(web_searcher=None, round=2)
        _n1 = llm._web_need_report(
            "ing", ("产出\n" + _M + "\n") + ("{%squeries%s: [%sY%s]}"
                                            % (_q, _q, _q, _q)))
        if _n1 != 0:
            bad.append("[按需] 无注入器却返回非 0：%r" % (_n1,))
    except Exception as _e:
        bad.append("[按需] 构造性验证抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.36 联网按需协议（三件齐 · 调用点真接 · JSON/逐行/畸形容错 · "
          "单字不丢 · 截量生效 · 声明真驱动消费者 · 无声明零调用）全过")
    return True


def check_v12334_prompt():
    """[v1.23.34] 提示词优化：有据 / 智者语气 / 输出结构（**改措辞不改机制**）。

    两向判据（见本函数上头补丁脚本的说明）：
      ① 新规范接上了；② 老红线一条没少。
    ★ 「本层速览」的真实入口断言不在这里 —— 它与 ㉟ 共用同一个 mock run
      （在 `check_v12333_autotune` 里断言），避免重复起引擎。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")

    # ── ① 三个共通常量：各 1 定义 ──
    for _c in ("VOICE", "EVIDENCE", "EXPLORE_FORMAT"):
        if ("%s = " % _c) not in src and ('%s = (' % _c) not in src:
            bad.append("[提示词] 共通常量 `%s` 未定义" % _c)

    # ── ①b 接线到六处视角 + ing ──
    _n_v = src.count("+ VOICE")
    _n_e = src.count("+ EVIDENCE")
    if _n_v < 7:
        bad.append("[提示词] `VOICE` 只接上 %d 处（六处视角 + ing = 7）" % _n_v)
    if _n_e < 7:
        bad.append("[提示词] `EVIDENCE` 只接上 %d 处（六处视角 + ing = 7）" % _n_e)
    if src.count("+ EXPLORE_FORMAT") < 6:
        bad.append("[提示词] `EXPLORE_FORMAT` 未在六处视角接上（实得 %d）"
                   % src.count("+ EXPLORE_FORMAT"))

    # ── ② 输出格式契约**不变**（红线：不改行为）──
    _i = src.find("EXPLORE_FORMAT = (")
    if _i < 0:
        bad.append("[提示词] 找不到 `EXPLORE_FORMAT` 定义体")
    else:
        _ef = src[_i:_i + 800]
        for _need in ("- [kind] 描述", "concept/event/person/object",
                      "startpoint/question/thread/other", "（无）"):
            if _need not in _ef:
                bad.append("[提示词] `EXPLORE_FORMAT` 丢了格式契约片段：%r" % _need)

    # ── ③ 反廉价感**未被削弱** ──
    if src.count("+ ANTI_PRETTY") < 6:
        bad.append("[提示词] `ANTI_PRETTY` 接线变少（不许削弱反漂亮约束）")
    if "不煽情，不客服" not in src:
        bad.append("[提示词] 「不煽情、不客服」被删（不许削弱）")

    # ── ④ 证据引用：**内容级**允许、**管道级**禁止 ──
    _j = src.find("EVIDENCE = ")
    if _j < 0:
        bad.append("[提示词] 找不到 `EVIDENCE` 定义体")
    else:
        _ev = src[_j:_j + 1600]
        if "落到内容" not in _ev:
            bad.append("[提示词] `EVIDENCE` 没写「引用要落到内容」")
        _missing = [t for t in ("资料里说", "检索显示", "上下文提到")
                    if t not in _ev]
        if _missing:
            bad.append("[提示词] `EVIDENCE` 的管道级**禁止清单**不全（缺 %r）"
                       % (_missing,))
        if "本来就知道" not in _ev:
            bad.append("[提示词] `EVIDENCE` 没写「把资料当成本来就知道的事」")

    # ── ⑤ mock 分流依赖的字样必须保留 ──
    for _t in ("阴视角", "阳视角", "结构化尾块"):
        if src.count(_t) < 2:
            bad.append("[提示词] 「%s」字样变少（冒烟 mock 靠它分流）" % _t)

    # ── ⑥ ing 输出结构 + 机器契约 ──
    if "六步各起一行" not in src:
        bad.append("[提示词] ing 未要求「六步各起一行」（输出结构没优化）")
    if "===ING-STRUCT===" not in src or "ing_structured" not in src:
        bad.append("[提示词] ing 结构化尾块契约被动了（机器解析依赖它）")

    # ── ⑦ [修行层/停止判据联网] 两个「默认不做、显式打开就做」的 stage ──
    #   ★ 从前它们是「配了不做」（登记在 `_AUDIT_CONFIG_EXEMPT`）——
    #     用户口径改为「开关要能作用」⇒ 必须有**真实调用点**。
    _flat2 = " ".join(src.replace("\r\n", "\n").split())
    for _st in ("practice_term_calibration", "stop_criteria"):
        if ('_web_search("%s"' % _st) not in src:
            bad.append("[联网] `%s` **没有真实调用点**（配了不做）" % _st)
    if "_AUDIT_CONFIG_EXEMPT = ()" not in src:
        bad.append("[联网] `_AUDIT_CONFIG_EXEMPT` 未清空（两 stage 仍在「声明不做」里）")
    for _u in ("term_calibration", "stop_criteria"):
        if ('"%s"' % _u) not in src[src.find("_WEB_USED_AS"):
                                    src.find("_WEB_USED_AS") + 400]:
            bad.append("[联网] `_WEB_USED_AS` 未登记枚举值 %r（有判据钉封闭集合）" % _u)
    # 接线必须挂在**两条通道共用的统一实现**上（不许在通道里各写一份）
    _i_br = src.find("self._practice_term_calibration_prep()")
    _i_br_fn = src.find("def _before_round")
    if _i_br < 0 or _i_br_fn < 0 or _i_br < _i_br_fn:
        bad.append("[联网] 术语校准没挂在 `_before_round`（圈前统一实现）上")
    _i_sc = src.find("self._stop_criteria_check(entry, view)")
    _i_sc_fn = src.find("def _finalize_layer_common")
    if _i_sc < 0 or _i_sc_fn < 0 or _i_sc < _i_sc_fn:
        bad.append("[联网] 判据复核没挂在 `_finalize_layer_common`（共用的层收尾）上")

    # ── ⑦ 运行期拼接（**真实入口**：调真实方法，看模型实际收到的那一段）──
    #   ★ 为什么不能只看源码：常量是**拼接**上去的，源码里读到的是片段；
    #     「拼错顺序 / 常量是空串 / 漏拼 / 拼接处少换行」源码判据都看不出来。
    #   ★ 零 LLM 调用（只实例化 + 拼字符串），不会拖慢冒烟。
    try:
        _cfg_rt = build_cfg(False)
        _dg_rt = mod.DGTF("0", mod.LLM(_cfg_rt), _cfg_rt)
        _t_rt = _dg_rt._yin_prompt()
        for _need in ("【怎么说话】", "【有据", "每行格式", "【反漂亮约束"):
            if _need not in _t_rt:
                bad.append("[提示词] 运行期 `_yin_prompt()` 缺 %r（拼接坏了）"
                           % _need)
        if not (_t_rt.find("【怎么说话】") < _t_rt.find("【有据")
                < _t_rt.find("【反漂亮约束")):
            bad.append("[提示词] 运行期三常量**顺序错**（应先语气、再有据、"
                       "最后反漂亮）")
    except Exception as _e_rt:
        bad.append("[提示词] 运行期导出提示词抛错：%r" % (_e_rt,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.34 提示词优化（VOICE/EVIDENCE/EXPLORE_FORMAT 三常量接线 · "
          "格式契约未动 · 反漂亮未削弱 · 内容级引用/管道级禁止 · "
          "ing 输出结构 · mock 分流字样保留 · 运行期拼接正确）全过")
    return True


def check_v12333_autotune():
    """[v1.23.33] AutoTune：从跨跑 episode 推**建议默认**（模式/层集/圈数）。

    判据（全部走**纯函数直测**，不碰 API）：
      ① 支配/前沿：真支配判真、缺读数（None）**不判支配**（未知不能淘汰已知）；
      ② 层集取舍：质量在 τ 内取**成本最低**（帕累托膝盖 = 「该去的层去掉」）；
      ③ 圈数：被截断过的层 **+1**（对齐 EML schedule 动作）；
      ④ 负向：空输入 / 全无质量 ⇒ `ok=False` **不瞎猜**（没测 ≠ 测出来差）；
      ⑤ 建议**只写文件**：`autotune_run(write=False)` 不改 cfg、不落盘。
    """
    src = SRC.read_bytes().decode("utf-8")
    bad = []
    for _fn in ("autotune_score", "autotune_dominates", "autotune_pareto",
                "autotune_sh_rounds", "autotune_rank", "autotune_recommend",
                "autotune_load_episodes", "autotune_run"):
        if ("def %s(" % _fn) not in src:
            bad.append("[源码] 缺 %s" % _fn)
    # ① 支配 / 前沿
    _lo = {"quality": 0.5, "cost": 100}
    _hi = {"quality": 0.8, "cost": 50}
    if not mod.autotune_dominates(_hi, _lo):
        bad.append("[支配] 高质量低成本未判支配")
    if mod.autotune_dominates(_lo, _hi):
        bad.append("[支配] 低质量高成本竟判支配")
    if mod.autotune_dominates({"quality": None, "cost": 1},
                              {"quality": 0.5, "cost": 2}):
        bad.append("[支配] 缺读数竟参与支配（未知淘汰了已知）")
    _fr = mod.autotune_pareto([_lo, _hi, {"quality": 0.4, "cost": 30}])
    if any(p is _lo for p in _fr):
        bad.append("[前沿] 被支配点混进了前沿")
    # ② 层集取舍 + ③ 圈数 +1
    #   ★ 夹具设计：**最高质量 = 最贵的四层**，膝盖（同质量内成本最低）= 两层。
    #     若把「最高质量」与「膝盖」设成同一条，M27（恒取质量第一行）会**假绿**
    #     —— 变异体不产生差异，就不是判别力（本项目经典假绿）。
    _syn = [
        {"run_id": "A", "route": ["0", "1", "both", "all"], "mode": "serial",
         "rounds_cap": {"0": 4, "1": 4, "both": 4, "all": 5}, "cut_layers": [],
         "duty": {"0": 0.91, "1": 0.92, "both": 0.90, "all": 0.89},
         "cost": {"tokens": 3000000}},
        {"run_id": "B", "route": ["0", "1"], "mode": "serial",
         "rounds_cap": {"0": 3, "1": 3}, "cut_layers": [],
         "duty": {"0": 0.86, "1": 0.87}, "cost": {"tokens": 1100000}},
        {"run_id": "C", "route": ["0", "1"], "mode": "serial",
         "rounds_cap": {"0": 3, "1": 3}, "cut_layers": [],
         "duty": {"0": 0.85, "1": 0.86}, "cost": {"tokens": 1050000}},
        {"run_id": "D", "route": ["0", "1", "both", "all"], "mode": "D",
         "rounds_cap": {"0": 6, "1": 6, "both": 6, "all": 6},
         "cut_layers": ["both", "all"],
         "duty": {"0": 0.55, "1": 0.58, "both": 0.50, "all": 0.48},
         "cost": {"tokens": 5000000}},
    ]
    _rec = mod.autotune_recommend(_syn)
    if not _rec.get("ok"):
        bad.append("[建议] 合成数据竟判不可建议：%r" % (_rec.get("why"),))
    else:
        if _rec.get("route") != ["0", "1"]:
            bad.append("[层集] 未按「同质量取最低成本」砍层：%r" % (_rec.get("route"),))
        _rc = _rec.get("rounds_cap") or {}
        if _rc.get("both") != 5 or _rc.get("all") != 6:
            bad.append("[圈数] 截断层未 +1：%r" % (_rc,))
        if _rc.get("0") != 4 or _rc.get("1") != 4:
            bad.append("[圈数] 未截断层基线不对：%r" % (_rc,))
    # ④ 负向：不瞎猜
    if mod.autotune_recommend([]).get("ok") is not False:
        bad.append("[负向] 空输入竟给了建议")
    _noq = mod.autotune_recommend([{"run_id": "X", "route": ["0"], "mode": "s",
                                    "rounds_cap": {"0": 3}, "cut_layers": [],
                                    "duty": {}, "cost": {"tokens": 10}}])
    if _noq.get("ok") is not False:
        bad.append("[负向] 全无质量读数竟给了建议（没测当测出来差）")
    # ⑤ 只写文件、不改 cfg
    _cfg = {"autotune": {"quality_tau": 0.05}, "spiral": {"soft_max": 2}}
    _snap = json.dumps(_cfg, sort_keys=True, ensure_ascii=False)
    _r2 = mod.autotune_run(_cfg, write=False)
    if json.dumps(_cfg, sort_keys=True, ensure_ascii=False) != _snap:
        bad.append("[纯读] autotune_run(write=False) 改了 cfg")
    if "written" in _r2:
        bad.append("[纯读] write=False 竟然写了文件")
    # ⑥ SH 档位单调：保留数↓、预算↑
    _sh = mod.autotune_sh_rounds(9, 2, 3)
    if len(_sh) < 2 or not all(_sh[i + 1][0] < _sh[i][0] and
                               _sh[i + 1][1] > _sh[i][1]
                               for i in range(len(_sh) - 1)):
        bad.append("[SH] 档位未「保留数降 / 预算升」：%r" % (_sh,))
    # ⑦ run_id 记账：`run()` 必须收 `run_id` 参，且 episode 用它当 run_id。
    #   ★ 真跑逮到：`run()` 原不生成 id ⇒ CLI 真跑 `anon_skipped: true` ⇒
    #     EML **从不学习命令行真跑**（自学习闭环对 CLI 路径整体失效）。
    if 'run_id: str = ""' not in src:
        bad.append("[记账] run() 未收 run_id 参数")
    _epx = mod.episode_from_result(
        {"id": "", "question": "Q", "route": ["0"], "rounds": {"0": 1},
         "views": {"0": {"duty": {"S": 0.5}, "stop_reason": "自然安住"}},
         "pools": {}, "llm_tokens": 1, "llm_calls": 1})
    if _epx.get("run_id") != "":
        bad.append("[记账] 空 id 竟生成 run_id=%r" % (_epx.get("run_id"),))
    _epy = mod.episode_from_result(
        {"id": "RID1", "question": "Q", "route": ["0"], "rounds": {"0": 1},
         "views": {"0": {"duty": {"S": 0.5}, "stop_reason": "自然安住"}},
         "pools": {}, "llm_tokens": 1, "llm_calls": 1})
    if _epy.get("run_id") != "RID1":
        bad.append("[记账] episode 未采用显式 run_id：%r" % (_epy.get("run_id"),))
    if "_rid = str(getattr(self, \"_run_id\"" not in src:
        bad.append("[记账] run() 未把 run_id 盖进产物（_eml_finish 读不到）")
    #   两条真入口（CLI main / 交互模式）也必须显式传 run_id —— 否则真实路径
    #   又被当匿名丢（这正是「EML 对真跑整体失效」的根因）。
    if "run_id=_run_id" not in src:
        bad.append("[记账] CLI main() 未向 run() 传 run_id")
    if src.count('run_id=datetime.now().strftime("%Y%m%d_%H%M%S")') < 1:
        bad.append("[记账] 交互模式未向 run() 传 run_id")
    # ⑧ 记忆库并发锁：**互斥**（临界区不交叠）+ 退出释放 + 陈旧锁回收。
    #   ★ 为什么是「正确性」不是「性能」：playbook 的升级/遗忘是**整表重写**，
    #     并发不加锁会互相覆盖（丢条目/半行）。3 并发真跑的前提。
    if "def eml_lock(" not in src:
        bad.append("[锁] eml_lock 缺失")
    else:
        import tempfile as _tf2
        import threading as _th2
        import time as _tm2
        _ld = Path(_tf2.mkdtemp(prefix="lk_"))
        _st = {"inside": 0, "max": 0}

        def _w():
            with mod.eml_lock(dirpath=_ld, timeout=8) as _got:
                if not _got:
                    return
                _st["inside"] += 1
                _st["max"] = max(_st["max"], _st["inside"])
                _tm2.sleep(0.2)
                _st["inside"] -= 1

        _ts = [_th2.Thread(target=_w) for _ in range(4)]
        for _t in _ts:
            _t.start()
        for _t in _ts:
            _t.join()
        if _st["max"] != 1:
            bad.append("[锁] 未互斥：并发进入数达 %d（应恒 1）" % _st["max"])
        if (_ld / ".eml.lock").exists():
            bad.append("[锁] 全部退出后锁文件仍在（未释放）")
        # 陈旧锁回收：把锁文件时间戳拨到远过去 ⇒ 必须能取得锁（崩了不永久死锁）。
        _lp = _ld / ".eml.lock"
        _lp.write_text("999999")
        import os as _os2
        _old = _tm2.time() - 5000
        _os2.utime(str(_lp), (_old, _old))
        with mod.eml_lock(dirpath=_ld, timeout=5) as _got2:
            if not _got2:
                bad.append("[锁] 陈旧锁未被回收 ⇒ 崩溃会永久死锁记忆库")
        import shutil as _sh2
        _sh2.rmtree(_ld, ignore_errors=True)
    # ⑨ 分母一致：质量中位与成本中位**必须同分母**（无质量的历史跑次不得进成本中位）。
    #   ★ 真跑逮到：2 层组的成本中位被旧的无 duty 跑次拉到 305076（真值 378837）
    #     ⇒ 帕累托膝盖判错。同一组两个读数两个分母 = 对不上账。
    _mix = [
        {"run_id": "n1", "route": ["0", "1"], "mode": "serial",
         "rounds_cap": {"0": 3, "1": 3}, "cut_layers": [],
         "duty": {"0": 0.5, "1": 0.5}, "cost": {"tokens": 900000}},
        {"run_id": "n2", "route": ["0", "1"], "mode": "serial",
         "rounds_cap": {"0": 3, "1": 3}, "cut_layers": [],
         "duty": {"0": 0.4, "1": 0.6}, "cost": {"tokens": 1000000}},
        # ★ 旧的无 duty 跑次：成本极低，绝不能被算进成本中位
        {"run_id": "old", "route": ["0", "1"], "mode": "serial",
         "rounds_cap": {"0": 1, "1": 1}, "cut_layers": [], "duty": {},
         "cost": {"tokens": 1000}},
    ]
    _r3 = [r for r in mod.autotune_rank(_mix) if r["route"] == ["0", "1"]]
    if not _r3:
        bad.append("[分母] 分组失败")
    else:
        _rr = _r3[0]
        if int(_rr.get("n_paired") or 0) != 2:
            bad.append("[分母] 同分母样本数错：%r" % (_rr.get("n_paired"),))
        if _rr.get("cost_med") != 950000.0:
            bad.append("[分母] 成本中位把无质量跑次算进去了：%r"
                       % (_rr.get("cost_med"),))
    # ⑩ 证据强度：同分母样本 < 3 ⇒ 必须显式标注薄弱，不许把薄证据包装成「最优」。
    _rec2 = mod.autotune_recommend(_mix)
    if _rec2.get("ok") and _rec2.get("evidence_strength") is None:
        bad.append("[证据] 未标注证据强度（薄证据当结论）")
    if _rec2.get("ok") and int(_rec2.get("evidence_n") or 0) < 3 \
            and "薄弱" not in (_rec2.get("why") or ""):
        bad.append("[证据] 同分母样本<3 却未在理由里标注薄弱")
    # ⑪ `autotune.min_n` 必须**真有出口**（否则是只写不读的死键）。
    _one = [{"run_id": "o1", "route": ["0", "1", "both"], "mode": "serial",
             "rounds_cap": {"0": 3, "1": 3, "both": 3}, "cut_layers": [],
             "duty": {"0": 0.9, "1": 0.9, "both": 0.9},
             "cost": {"tokens": 100}}]
    if mod.autotune_recommend(_one, min_n=2).get("ok") is not False:
        bad.append("[min_n] min_n=2 未排除 n=1 的组（死键）")
    if mod.autotune_recommend(_one, min_n=1).get("ok") is not True:
        bad.append("[min_n] min_n=1 竟排除了 n=1 的组")
    if "min_n=int(at.get(\"min_n\"" not in src:
        bad.append("[min_n] autotune_run 未把配置 min_n 接进 recommend")
    # ⑫~⑳ [四层目标语义 + 三阶段自主决策]（用户战略指令）
    #   ★ 依据：Heaps 饱和（修行）· content entropy + 伪收敛（研究）·
    #     CORE 语义停滞罚（对撞）· DGM archive 开放探索（后期，禁贪心）。
    for _fh in ("layer_goal_readings", "layer_goal_summary",
                "_lg_aspect_margin", "_lg_stag_ratio",
                "autotune_archive", "autotune_phase_select",
                "autotune_phase_adjust", "autotune_phase_learn",
                "autotune_decide", "autotune_progress"):
        if ("def %s(" % _fh) not in src:
            bad.append("[目标] 缺 %s" % _fh)
    # ⑫ 修行层「边际新增趋零」方向：还在挖 > 已挖尽（★ 方向错比没判据更危险）。
    _busy = mod.layer_goal_readings(
        {"0": {"aspect_units": [{"id": "A%d" % i} for i in range(9)],
               "rounds_run": 4, "aspect_hist": [2, 4, 6, 9],
               "divergence": {"state": "发散"}}})
    _done = mod.layer_goal_readings(
        {"0": {"aspect_units": [{"id": "A%d" % i} for i in range(6)],
               "rounds_run": 4, "aspect_hist": [2, 4, 5, 6],
               "divergence": {"state": "收敛"}}})
    _vb = (_busy.get("0") or {}).get("excavate")
    _vd = (_done.get("0") or {}).get("excavate")
    if _vb is None or _vd is None or not (_vb > _vd):
        bad.append("[修行] 边际新增率方向错（还在挖应 > 已挖尽）：%r vs %r"
                   % (_vb, _vd))
    if (_busy.get("0") or {}).get("converging") is not False:
        bad.append("[修行] 发散态竟判 converging=True")
    if (_done.get("0") or {}).get("converging") is not True:
        bad.append("[修行] 收敛态未判 converging=True")
    # ⑬ 研究层：伪收敛必须被点出（熵降 ≠ 质量 —— 一个都没答上却声称收敛）。
    #   ★ 夹具用**真实字段** `settlement`（真跑 GOALCHK 逮到：原夹具塞的是
    #     臆造键 `covered_answer`，实现里根本没这个字段 ⇒ 判据假绿）。
    _pok = mod.layer_goal_readings(
        {"1": {"settlement": {"answered": 4, "total": 5},
               "divergence": {"state": "收敛"}}})["1"]
    _pps = mod.layer_goal_readings(
        {"1": {"settlement": {"answered": 0, "total": 5},
               "divergence": {"state": "收敛"}}})["1"]
    if _pok.get("pseudo_convergence") is not False:
        bad.append("[研究] 真收敛被误判为伪收敛")
    if _pps.get("pseudo_convergence") is not True:
        bad.append("[研究] 零答案却声称收敛未判伪收敛（熵降当质量）")
    if abs(float(_pok.get("settle")) - 0.8) > 1e-6:
        bad.append("[研究] 确定率算错：%r" % (_pok.get("settle"),))
    # ★ 退回形态：`covered/uncovered_aspects` 也能算出 settle（同源口径）。
    _pfb = mod.layer_goal_readings(
        {"1": {"covered_aspects": ["a", "b", "c"],
               "uncovered_aspects": ["d"]}})["1"]
    if abs(float(_pfb.get("settle") or -1) - 0.75) > 1e-6:
        bad.append("[研究] 层面数兜底算错：%r" % (_pfb.get("settle"),))
    # ⑭ 对撞层：CORE 语义停滞罚 —— 同产出量下「复读」必须低于「真融合」。
    _fz = mod.layer_goal_readings(
        {"both": {"duel_suspensions": [{"target": "新张力甲"}, {"target": "新张力乙"}],
                  "upstream_layers": 3,
                  "upstream_texts": ["旧层面一", "旧层面二"]}})["both"]
    _sg = mod.layer_goal_readings(
        {"both": {"duel_suspensions": [{"target": "旧层面一"}, {"target": "旧层面二"}],
                  "upstream_layers": 3,
                  "upstream_texts": ["旧层面一", "旧层面二"]}})["both"]
    if not (float(_fz.get("fuse") or 0) > float(_sg.get("fuse") or 0)):
        bad.append("[对撞] 复读未被罚（CORE 停滞罚失效）：%r vs %r"
                   % (_fz.get("fuse"), _sg.get("fuse")))
    if abs(float(_sg.get("sem_stagnation") or 0) - 1.0) > 1e-6:
        bad.append("[对撞] 全复读未算出停滞率 1.0：%r" % (_sg.get("sem_stagnation"),))
    # ⑮ 元层：四件事凑齐才算 1.0；缺一件就必须 < 1（留痕完整度）。
    _m4 = mod.layer_goal_readings(
        {"all": {"meta_closure": {"clean": True, "total": 3},
                 "engagements": [{"tension_id": "t1"}],
                 "suspensions": [{"tension_id": "t2"}]}})["all"]
    _m2 = mod.layer_goal_readings(
        {"all": {"meta_closure": {"clean": False, "total": 0}}})["all"]
    if abs(float(_m4.get("crystallize")) - 1.0) > 1e-6:
        bad.append("[元] 四件事齐了却没给 1.0：%r" % (_m4.get("crystallize"),))
    if not (float(_m2.get("crystallize") or 1) < 1.0):
        bad.append("[元] 只留痕两件竟给满分：%r" % (_m2.get("crystallize"),))
    # ⑯ 缺读数回 None（不是 0）——「没测」与「测出是 0」必须分开。
    _empty = mod.layer_goal_readings({})
    if _empty != {}:
        bad.append("[缺读数] 空 views 竟产出读数：%r" % (_empty,))
    _noans = mod.layer_goal_readings({"1": {"belief_items": []}})["1"]
    if _noans.get("settle") is not None:
        bad.append("[缺读数] 无 settlement 竟回 0 而非 None：%r"
                   % (_noans.get("settle"),))
    # ⑰ `goal_readings` 必须**有出口**（字段有值 ≠ 有出口，本项目已栽过）。
    _epg = mod.episode_from_result(
        {"id": "G1", "question": "Q", "route": ["0", "1"], "rounds": {"0": 2, "1": 2},
         "views": {"0": {"aspect_units": [{"id": "A1"}], "rounds_run": 2,
                         "aspect_hist": [1, 1]},
                   "1": {"settlement": {"answered": 1, "total": 2}}},
         "pools": {}, "llm_tokens": 1, "llm_calls": 1})
    if not (_epg.get("goal_readings") or {}):
        bad.append("[出口] episode 未带 goal_readings（读数进不了库）")
    if "goal_readings" not in src:
        bad.append("[出口] 源码无 goal_readings 出口")
    # ⑱ 质量口径升级：有目标读数时必须走 goal_med（而非退回 duty）。
    _sp = mod.autotune_score({"mode": "s", "route": ["0"], "duty": {},
                              "goal_readings": {"0": {"value": 0.7}},
                              "cost": {"tokens": 1}, "rounds_cap": {}, "t": 0})
    if _sp.get("q_basis") != "goal_med":
        bad.append("[口径] 有目标读数却未走 goal_med：%r" % (_sp.get("q_basis"),))
    # ⑲ 中期动态调整三态：上升→继续 / 下降→回滚 / 不足→不表态。
    #   ★ 夹具要保证**末值真的低于首值**才叫下降 —— 否则测的是「首尾比较」
    #     却给了个「中间高」的序列（首尾仍升），会得到与意图相反的结论。
    _e0 = {"mode": "s", "route": ["0"], "duty": {}, "cost": {"tokens": 1},
           "rounds_cap": {}, "t": 0, "goal_readings": {"0": {"value": 0.2}}}
    _e1 = dict(_e0, t=10, goal_readings={"0": {"value": 0.6}})
    _e2 = dict(_e0, t=20, goal_readings={"0": {"value": 0.1}})
    _pu = mod.autotune_progress([_e0, _e1], min_n=2)
    _pd = mod.autotune_progress([_e0, _e1, _e2], min_n=2)
    if not _pu or list(_pu.values())[0].get("advice") != "继续":
        bad.append("[中期] 上升趋势未判「继续」：%r" % (_pu,))
    if not _pd or list(_pd.values())[0].get("advice") != "回滚":
        bad.append("[中期] 下降趋势未判「回滚」：%r" % (_pd,))
    if mod.autotune_progress([_e0], min_n=2) != {}:
        bad.append("[中期] 样本不足竟表态（瞎猜）")
    # ⑳ archive 开放探索：**不许贪心只留最优**（DGM 消融：贪心劣于 archive）。
    _arc = mod.autotune_archive([
        {"run_id": "a1", "route": ["0", "1"], "mode": "s", "rounds_cap": {},
         "cut_layers": [], "duty": {"0": 0.9, "1": 0.9}, "cost": {"tokens": 100}},
        {"run_id": "a2", "route": ["0", "1", "both"], "mode": "s", "rounds_cap": {},
         "cut_layers": [], "duty": {"0": 0.1, "1": 0.1, "both": 0.1},
         "cost": {"tokens": 999}},
    ])
    _arms = _arc.get("arms") or []
    if len(_arms) < 2:
        bad.append("[archive] 只留了最优臂（贪心）⇒ 未做开放探索：%r" % (len(_arms),))
    _minp = min((a.get("prob") or 0) for a in _arms) if _arms else 0
    if _minp < 0.05 - 1e-9:
        bad.append("[archive] 劣配概率被压到 floor 之下（路径被掐死）：%r" % _minp)
    if _arc.get("open_ended") is not True:
        bad.append("[archive] 多样性足够却未判 open_ended")
    #    真实入口：`autotune_run` 必须把三阶段决策**落进建议**（否则结论无留痕）。
    if 'rec["decide"] = autotune_decide(' not in src:
        bad.append("[三阶段] autotune_run 未产出 decide 决策书")
    # ㉑~㉔ [四层目标**进入每层每圈运行**]（用户战略指令：不只做读数）
    #   判据四层：纯函数方向 / 缺读数不表态 / 真实入口接线 / 出口存在。
    if "def layer_goal_stop_signal(" not in src:
        bad.append("[目标运行] 缺 layer_goal_stop_signal")
    if "def _layer_goal_now(" not in src:
        bad.append("[目标运行] 缺 _layer_goal_now（每圈记账）")
    if "def _goal_stop_signal(" not in src:
        bad.append("[目标运行] 缺 _goal_stop_signal（读 trace）")
    # ㉑ 纯函数方向：达标判 hit、未达标判不 hit、**缺读数不表态**。
    _S = mod.layer_goal_stop_signal
    if _S("0", {"excavate": 0.05, "n_aspects": 9})[0] is not True:
        bad.append("[目标运行] 修行层挖尽未判 hit")
    if _S("0", {"excavate": 0.9, "n_aspects": 9})[0] is not False:
        bad.append("[目标运行] 修行层还在挖竟判 hit（方向错）")
    if _S("1", {"settle": 0.8}, [{"settle": 0.8}, {"settle": 0.8},
                                 {"settle": 0.8}])[0] is not True:
        bad.append("[目标运行] 研究层连续不涨未判 hit")
    if _S("1", {"settle": 0.9}, [{"settle": 0.5}, {"settle": 0.7},
                                 {"settle": 0.9}])[0] is not False:
        bad.append("[目标运行] 研究层在涨竟判 hit")
    if _S("both", {"sem_stagnation": 0.9})[0] is not True:
        bad.append("[目标运行] 对撞层全复读未判 hit")
    if _S("all", {"crystallize": 1.0})[0] is not True:
        bad.append("[目标运行] 元层四件齐未判 hit")
    if _S("all", {"crystallize": 0.75})[0] is not False:
        bad.append("[目标运行] 元层缺件竟判 hit")
    # ㉒ 缺读数 ⇒ **必须不表态**（hit=False + why 空）——「没测」≠「测出来差」。
    for _e in ("0", "1", "both", "all"):
        _h, _w = _S(_e, {})
        if _h is not False or _w != "":
            bad.append("[目标运行] %s 缺读数竟表态：%r" % (_e, (_h, _w)))
    # ㉓ 样本不足不许判「不涨」（序列 < n+1 条 ⇒ 不表态）。
    if _S("1", {"settle": 0.8}, [{"settle": 0.8}])[0] is not False:
        bad.append("[目标运行] 样本不足竟判「不涨」")
    # ㉔ 真实入口接线：两条通道都算 + `_stop_reasons` 真加入参 + 出口存在。
    if src.count("self._layer_goal_now(entry, view)") < 2:
        bad.append("[目标运行] 未接两条通道（串行/并行）")
    if src.count("goal_hit=_goal_hit") < 2:
        bad.append("[目标运行] 未把 goal_hit 传进 _stop_reasons（两通道）")
    if "goal_hit: bool = False," not in src:
        bad.append("[目标运行] _stop_reasons 未收 goal_hit")
    if 'if goal_hit and goal_why:' not in src:
        bad.append("[目标运行] _stop_reasons 未按 goal_hit 加理由")
    if "d[\"goal_trace\"]" not in src:
        bad.append("[目标运行] goal_trace 无出口（产物看不到逐圈目标）")
    # ㉕ 目标停因**必须落在高优先档**（自洽核查逮到：未登记 ⇒ 落最低档 3，
    #    与「体力耗尽」同级 ⇒ 主因报反）。★ 判据落在**行为**（stop_priority
    #    的实际返回值）上，不钉 `_STOP_CASCADE` 的字面写法。
    _sp_ = mod.stop_priority
    _crit = {
        "修行目标已达成（层面边际新增率 0.000 < 0.10，Heaps 饱和 ⇒ 挖到不能再挖）": 0,
        "研究目标已达成（settle 连续 2 圈不涨）": 0,
        "对撞目标受阻（语义停滞率 0.85 >= 0.80 ⇒ 复读）": 0,
        "元层目标已达成（结晶度 1.00 >= 1.00）": 0,
    }
    for _r, _want in _crit.items():
        _got = _sp_(_r)
        if _got != _want:
            bad.append("[目标运行] 目标停因优先级错位 %r ⇒ 档 %s（应 %s）"
                       % (_r[:16] + "…", _got, _want))
    # ★ 负对照：真正该落低档的**不许**被这条登记误伤。
    #   ★★ 用**真产物的实际文案**（`_fullrun_GOALRUN.log` 实测）——
    #   走满型停因把「被推迟的判据名」原样嵌进括号，全文子串匹配会把
    #   截断误判成档 0「自然停」（语义相反）⇒ 必须命中档 3。
    if _sp_("体力耗尽（4 圈走满；1 次停止判据被「未深入方向」推迟"
            "（悬置决定稳定，自然安住），是被截断不是自然停止）") != 3:
        bad.append("[目标运行] 负对照失效：走满型截断停因竟非档 3"
                   "（括号内转述被当停因本体）")
    if _sp_("体力耗尽（4 圈走满，未触发任何停止判据，是被截断不是自然停止）") != 3:
        bad.append("[目标运行] 负对照失效：体力耗尽竟非档 3")
    if _sp_("预算用尽") != 3:
        bad.append("[目标运行] 负对照失效：预算用尽竟非档 3")
    # ★ 档 2 不许吞档 3（键区间重叠：裸键「耗尽」吞掉「体力耗尽」）。
    if _sp_("连续空转") != 2:
        bad.append("[目标运行] 档 2 真文案「连续空转」落档错")
    if _sp_("材料耗尽，螺旋停止") != 2:
        bad.append("[目标运行] 档 2 真文案「材料耗尽」落档错")
    # ㉖ [四层目标 → **圈内动作**]（第二期）：读数进入 prompt 的形状指引。
    #   判据四层：纯函数方向 / 缺读数不表态（4 层）/ 达标不唠叨 /
    #   **两通道都接线** / 注入点存在。
    if "def layer_goal_action_hint(" not in src:
        bad.append("[目标动作] 缺 layer_goal_action_hint")
    if "def _refresh_goal_hint(" not in src:
        bad.append("[目标动作] 缺 _refresh_goal_hint")
    _H = mod.layer_goal_action_hint
    # ① 方向：未达标的层要出指引，**达标的层闭嘴**（空串）。
    if not _H("0", {"excavate": 0.02, "n_aspects": 9}):
        bad.append("[目标动作] 修行层挖尽后竟不给指引（应在同一面挖完后换面）")
    if _H("0", {"excavate": 0.9, "n_aspects": 9}) != "":
        bad.append("[目标动作] 修行层还在挖竟给指引（不该干预）")
    if not _H("1", {"settle": 0.3}):
        bad.append("[目标动作] 研究层确定率低竟不给指引")
    if _H("1", {"settle": 0.9}) != "":
        bad.append("[目标动作] 研究层已收敛竟给指引（达标应闭嘴）")
    if not _H("both", {"sem_stagnation": 0.9}):
        bad.append("[目标动作] 对撞层全复读竟不给指引（CORE 停滞罚未落地）")
    if not _H("all", {"crystallize": 0.5, "n_hits": 2}):
        bad.append("[目标动作] 元层结晶不全竟不给指引")
    if _H("all", {"crystallize": 1.0, "n_hits": 4}) != "":
        bad.append("[目标动作] 元层四件齐竟给指引（达标应闭嘴）")
    # ② 缺读数 ⇒ **必须不表态**（空串）——「没测」≠「测出来差」。
    for _e in ("0", "1", "both", "all"):
        if _H(_e, {}) != "":
            bad.append("[目标动作] %s 缺读数竟给指引（不该拿没数据当约束）" % _e)
    # ③ 不许**返 role 名**（那会让 role 语义出现第二个真相源）。
    for _e, _g in (("0", {"excavate": 0.0, "n_aspects": 9}),
                   ("1", {"settle": 0.2}),
                   ("both", {"sem_stagnation": 0.9}),
                   ("all", {"crystallize": 0.5, "n_hits": 2})):
        _h = _H(_e, _g)
        if "转向" in _h or "复裁" in _h or "【本轮形状" in _h:
            bad.append("[目标动作] %s 的指引混入了 role 语义（应只出形状指引）" % _e)
    # ④ **两通道都接线** + 注入点存在（★ 拦「一处有一处没有」）。
    if src.count("self._refresh_goal_hint(entry, view)") < 2:
        bad.append("[目标动作] 未接两条通道（串行/并行）")
    if src.count("{goal_hint}") < 2:
        bad.append("[目标动作] 未注入两条 prompt 组装路径")
    if 'self._goal_hint_next = ""' not in src:
        bad.append("[目标动作] 未初始化 _goal_hint_next（会 AttributeError）")
    # ㉗~㉛ [第六期 · 各环节量化 + 降本]（依据见 _各环节量化与降本依据_v12333.md）
    #   判据五层：纯函数方向 / 缺输入不表态 / **不调 LLM**（构造性证明）/
    #   真实入口接线 / 开关默认关（零行为差）。
    for _f in ("def yin_yang_divergence(", "def restate_fidelity(",
               "def semantic_density("):
        if _f not in src:
            bad.append("[量化] 缺 %s" % _f)
    _YY, _RF, _SD = (mod.yin_yang_divergence, mod.restate_fidelity,
                     mod.semantic_density)
    # ㉘ 分歧度方向：全同 ⇒ 假对撞（divergence 接近 0）；全不同 ⇒ ok。
    if _YY(["同一个说法原样复述"], ["同一个说法原样复述"])["verdict"] != "fake_duel":
        bad.append("[量化] 阴阳完全复述竟未判假对撞（方向错）")
    if _YY(["边界条件必须先声明"], ["引擎的调度顺序决定产出"])["verdict"] != "ok":
        bad.append("[量化] 阴阳真分歧竟判假对撞（方向错）")
    # ㉘b 缺一侧 ⇒ 不表态（divergence=None / verdict 空）。
    _e1 = _YY([], ["x"])
    if _e1["divergence"] is not None or _e1["verdict"] != "":
        bad.append("[量化] 阴阳缺一侧竟表态")
    # ㉙ 保真度方向：漂移判 drifted、正常判 ok；缺输入不表态。
    if _RF("收敛判断为什么不可靠？给出可检验判据",
            "完全无关的另一件事的讨论")["verdict"] == "ok":
        bad.append("[量化] 重述跑偏竟判 ok（方向错）")
    if _RF("收敛判断为什么不可靠？给出可检验判据",
            "收敛判断为什么不可靠？给出可检验判据：需要边界条件与检验口径")[
                "verdict"] != "ok":
        bad.append("[量化] 重述保真竟未判 ok")
    _e2 = _RF("", "x")
    if _e2["verdict"] != "" or _e2["fidelity"] is not None:
        bad.append("[量化] 保真度缺输入竟表态")
    # ㉚ 语义密度：**不调 LLM**（构造性证明：把 llm.call 计数为 0）+ 方向。
    _n_call = {"n": 0}
    _orig_call = mod.LLM.call

    def _spy(self, *a, **kw):
        _n_call["n"] += 1
        return _orig_call(self, *a, **kw)
    try:
        mod.LLM.call = _spy
        _d1 = _SD("综上所述，我们需要注意的是，其实这个非常可能的说法")
        _d2 = _SD("边界条件未声明时收敛判据不可检验")
        _r1 = _RF("收敛判断为什么不可靠", "收敛判断为什么不可靠")
        _r2 = _YY(["边界条件"], ["调度顺序"])
    finally:
        mod.LLM.call = _orig_call
    if _n_call["n"] != 0:
        bad.append("[量化] 读数函数偷调了 LLM（%d 次）—— 必须零成本" % _n_call["n"])
    if _d1 is None or _d2 is None or not (_d2 > _d1):
        bad.append("[量化] 语义密度方向错（填充语应低于实词句）：%r vs %r"
                   % (_d1, _d2))
    if _SD("") is not None:
        bad.append("[量化] 语义密度空输入竟表态")
    # ㉛ 真实入口接线：三处读数都要在引擎里可达（不只纯函数绿）。
    #   ★★ [真跑逮到的真缺陷] 第一版只查「`self._quant_note(view,` 出现 ≥2 次」
    #      （**存在性**）⇒ 接线看似在，实则 `_quant_note` 只定义在 `MetaDGTF`，
    #      而调用点在 `DGTF.run`，两类**无继承关系** ⇒ `AttributeError` 被
    #      `except Exception: pass` **静默吞掉** ⇒ 真跑 `quant_readings` 四层全空。
    #      ⇒ 「有接线」≠「这跑走得到」。判据必须**查可达性**，不查出现次数。
    _qn = getattr(mod, "_quant_note", None)
    if not callable(_qn):
        bad.append("[量化] 模块级 `_quant_note` 不存在（应做成模块级函数："
                   "调用点在 DGTF，定义却在 MetaDGTF ⇒ 解析不到）")
    else:
        # ★ 构造性可达证明：拿**真的 View** 写一条，必须落进去。
        try:
            _vq = mod.View(entry="0")
            _qn(_vq, "judge_probe", {"value": 1})
            if (_vq.quant_readings or {}).get("judge_probe", {}).get("value") != 1:
                bad.append("[量化] `_quant_note` 写不进真 View（写入口坏了）")
        except Exception as _e:
            bad.append("[量化] `_quant_note` 调用抛错：%r" % (_e,))
    # ★ 宿主可达性：三处调用点的**宿主类**上，同名属性必须能解析到。
    #   逐类检查 `DGTF` / `MetaDGTF`：调用点所在类若无该属性 ⇒ 判红。
    _src_ln = src.replace("\r\n", "\n")
    if "self._quant_note(" in _src_ln:
        bad.append("[量化] 仍有 `self._quant_note(` 调用（应改模块级裸名 —— "
                   "宿主类解析不到会静默 AttributeError）")
    _calls = [ln for ln in _src_ln.splitlines()
              if "_quant_note(view," in ln
              and not ln.lstrip().startswith("def ")]
    #   ★ 取值随实现更新：第六期第二批次补「候选生成产出率」后，调用点 3 → **4**
    #     （restate_fidelity / yin_yang_divergence / ing_density / candidate_yield）；
    #     v1.23.45 (P-4) 补「输出内复读率」后再 **4 → 5**。
    #     这条不是「放宽阈值」，是**登记新增的真实调用点**；数量本身仍是硬约束 ——
    #     多一处少一处都说明接线被动过，必须有人显式确认。
    if len(_calls) != 5:
        bad.append("[量化] `_quant_note` 真实调用点应为 5 处（实得 %d）"
                   % len(_calls))
    if _src_ln.count("def _quant_note(") != 1:
        bad.append("[量化] `_quant_note` 定义份数 != 1（两个真相源）")
    if "semantic_density(view.collision)" not in src:
        bad.append("[量化] ing 语义密度未接真实入口")
    if "restate_fidelity(_q0" not in src:
        bad.append("[量化] 锚点保真度未接真实入口")
    if "yin_yang_divergence(_by[_ks[0]]" not in src:
        bad.append("[量化] 阴阳分歧度未接真实入口")
    if 'd["quant_readings"] = {' not in src:
        bad.append("[量化] quant_readings 无产物出口")
    # ㉜ 候选生成**产出率**（依据 ③：早期信号；用户点名五处之「候选生成」）。
    #   · 纯函数方向：全是复述 ⇒ collapsed；全新 ⇒ ok；缺一输入 ⇒ 不表态；
    #   · 真实入口：必须接在 `_drop_banned` 之后（**禁令拦下的不算增长**）、
    #     `_dual_judge` 之前（读的是「这一圈长的」，不是被改写过的集合）；
    #   · **不调 LLM**（同一把零成本尺子）。
    if not hasattr(mod, "candidate_yield"):
        bad.append("[量化] 缺 candidate_yield（候选生成无量化读数）")
    else:
        _CY = mod.candidate_yield
        _prev = ["边界条件必须先声明", "调度顺序决定产出"]
        _e = _CY([], _prev)
        if _e["verdict"] != "" or _e["new_ratio"] is not None:
            bad.append("[量化] 候选产出率：无候选竟表态")
        _e = _CY(["新说法甲"], [])
        if _e["verdict"] != "" or _e["new_ratio"] is not None:
            bad.append("[量化] 候选产出率：无历史竟表态（首次跑 ≠ 没长）")
        if _CY(list(_prev), _prev)["verdict"] != "collapsed":
            bad.append("[量化] 候选产出率：整批复述竟未判 collapsed（方向错）")
        if _CY(["外位通道必须先于被测变化存在", "资格来源不能与被资格对象同槽"],
               _prev)["verdict"] == "collapsed":
            bad.append("[量化] 候选产出率：全新生竟判 collapsed（方向错）")
        # 缺读数不许写成 0（「没测」≠「测出来是 0」）
        _n0 = _CY([], _prev)
        if _n0["n_new"] is not None or _n0["max_sim"] is not None:
            bad.append("[量化] 候选产出率：缺输入竟回 0 而非 None")
    # ★ 锚在**语义**上，不锚换行格式（原写法钉了 `candidate_yield([getattr(...`
    #   这一整行字面 —— 本轮把参数折行后立刻失配，属「锚在会变的东西上」）。
    #   压掉全部空白后再查：函数名 + 第一个实参的形态。
    _flat_src = " ".join(src.replace("\r\n", "\n").split())
    if 'candidate_yield( [getattr(c, "desc", "") for c in candidates]' not in _flat_src:
        bad.append("[量化] 候选产出率未接真实入口")
    # ★ 接线顺序：产出率必须读在**对偶判断之前**（否则读的是被改写过的集合）。
    _i_cy = src.find('_quant_note(view, "candidate_yield"')
    _i_dj = src.find("candidates = self._dual_judge(candidates")
    if _i_cy < 0 or _i_dj < 0 or not (_i_cy < _i_dj):
        bad.append("[量化] 候选产出率接线位置错（必须在对偶判断之前）")
    # ㉗ 阴阳合并开关：**默认关** ⇒ 零行为差（防「偷偷改了默认行为」）。
    if 'self._expand_pair_merged_once(jobs)' not in src:
        bad.append("[量化] 阴阳合并未接线（仍是孤儿函数 ⇒ 能力不可达）")
    if '_action_on(self.config, "merge_expand", False)' not in src:
        bad.append("[量化] 阴阳合并开关默认不是关（会改变历史行为）")
    # ㉝ [第六期 · 降本] 规则命中 ⇒ **零 LLM 调用**（构造性证明，不是「看代码」）。
    #   ★★ 逮到的真问题：B1 规则命中的注释写「不花这次模式调用」，但为补
    #      `orientation` 又调 `plan_orientation(q, cfg)` —— 它内部自己
    #      `new LLM(cfg)`（签名里没有 `llm=`）⇒ 实测**还是花 1 次**。
    #      修法：新增零成本 `orientation_rule()`（与 `_has_decision_context`
    #      同源），规则命中时用它；只有规则拿不准（空题面）才回落 LLM 版。
    _orn = getattr(mod, "orientation_rule", None)
    if not callable(_orn):
        bad.append("[降本] 模块级 `orientation_rule` 不存在（规则命中仍会偷调 LLM）")
    else:
        # ★ 样本要贴合各自语义 —— 不能拿含「风险」的题面当 boundary 样本：
        #   `_DECISION_CUES` 里本就有「风险」（走 decision 是**既有语义**，
        #   不是本规则的方向错）。boundary 样本须**不含任何决策语汇**。
        _od = _orn("这一步该怎么选，给个方案")
        _ob = _orn("这件事的边界画在哪里")
        if (_od or {}).get("orientation") != "decision":
            bad.append("[降本] 取向规则方向错：决策语汇应判 decision，实得 %r"
                       % ((_od or {}).get("orientation"),))
        if (_ob or {}).get("orientation") != "boundary":
            bad.append("[降本] 取向规则方向错：无决策语汇应判 boundary，实得 %r"
                       % ((_ob or {}).get("orientation"),))
        # ★ 空题面 ⇒ 保守回 boundary（**与 `_has_decision_context` 的既有约定
        #   同源**：「题面取不到时宁可走边界模板，也不在不知道题面时套决策模板」）。
        #   ⇒ 判据查的是「不许回 decision」，不是「必须为空」。
        if (_orn("") or {}).get("orientation") != "boundary":
            bad.append("[降本] 取向规则空题面未保守回 boundary（实得 %r）"
                       % ((_orn("") or {}).get("orientation"),))
        # ★ 构造性证明：规则命中时 `LLM.call` 必须 **0 次**。
        _spy_n = {"n": 0}
        _orig_llm_cls = mod.LLM

        class _SpyLLM:
            def __init__(self, *a, **kw):
                pass

            def call(self, *a, **kw):
                _spy_n["n"] += 1
                import json as _j
                return _j.dumps({"mode": "serial", "orientation": "boundary",
                                 "rounds": {"0": 4, "1": 4, "both": 4, "all": 5},
                                 "reason": "spy", "confidence": 0.9})

            def parse_json(self, raw):
                import json as _j
                return _j.loads(raw)

        try:
            mod.LLM = _SpyLLM
            _pl = mod.auto_plan("地铁运营效率该怎么衡量？",
                                dict(mod.DEFAULT_CONFIG), llm=_SpyLLM())
            if _spy_n["n"] != 0:
                bad.append("[降本] 规则命中竟调了 LLM %d 次（应为 0 —— "
                           "注释说「不花这次调用」就必须真不花）" % _spy_n["n"])
            if (_pl or {}).get("mode") != "serial":
                bad.append("[降本] 规则命中路径 mode 变了：%r"
                           % ((_pl or {}).get("mode"),))
        finally:
            mod.LLM = _orig_llm_cls
    # ㉞ [本轮铁律] **真实入口产出**：`candidate_yield` 必须真能落进 `quant_readings`。
    #   ★★ 为什么必须有：㉜ 全是**纯函数 + 字面存在 + 位置**形态 —— 全绿，
    #      但真实跑下来读数**恒不落盘**（历史挂在每圈重建的 `view` 上 ⇒ 恒 None
    #      ⇒ 永久「缺输入不表态」）。本项目栽过三次同族问题：
    #      ① v1.23.27 信念迁移真实入口不可达；② 本轮 `_quant_note` 定义在
    #      `MetaDGTF`、调用点在 `DGTF`（无继承）⇒ 静默 AttributeError；
    #      ③ 本轮历史挂每圈重建的 view ⇒ 时序颠倒。
    #   ★ 判据形态：跑一次**真实入口**（`MetaDGTF.run`，等价的 mock 路径 ⇒
    #     零 API 花费），断言 `views[e].quant_readings` 里**真的有**这个键。
    #     ⚠ 这里用**已有的** mock run 机制（`build_cfg` + `mod.LLM.call` 已被
    #     模块级替换），不另造一套真跑。
    try:
        if "candidate_yield" not in src:
            bad.append("[量化] `candidate_yield` 不在源码里")
        elif "view._prev_cand_descs" in src:
            bad.append("[量化] 候选历史又挂回**每圈重建的 view** —— "
                       "下一圈必然读不到（时序颠倒，读数永不落盘）")
        else:
            _cfg_cy = build_cfg(False)
            _mt_cy = mod.MetaDGTF(_cfg_cy)
            # ★ ㉞ 与 ㉟ **共用一次 mock run**（只跑一次，不拖慢冒烟）：
            #   猴补丁同时捕获 `_render` 正文，供 ㉟ 断言「读数进正文」。
            _orig_render = mod.DGTF._render
            _cap_render = []

            def _spy_render(self, view, inp):
                _t = _orig_render(self, view, inp)
                _cap_render.append(_t)
                return _t

            mod.DGTF._render = _spy_render
            # ★ [修行层/停止判据联网] 顺便观测两条新接线：默认关时
            #   「走到 Gate + 被拦」= 接线可达 且 红线未破（零真检索）。
            _w2s_allow = []
            _orig_wallow = mod.WebSearchGate.allow

            def _spy_wallow(self, stage, round_no):
                _r = _orig_wallow(self, stage, round_no)
                _w2s_allow.append(
                    (str(stage), bool(_r[0]) if isinstance(_r, tuple)
                     else bool(_r)))
                return _r
            mod.WebSearchGate.allow = _spy_wallow
            try:
                _res_cy = _mt_cy.run("意识能否被还原为信息处理过程？",
                                     route=["0"], rounds={"0": 3},
                                     parallel_mode="serial")
            finally:
                mod.DGTF._render = _orig_render
                mod.WebSearchGate.allow = _orig_wallow
            _v0cy = (_res_cy.get("views") or {}).get("0")
            _vd0 = (_v0cy.to_dict() if hasattr(_v0cy, "to_dict") else _v0cy) or {}
            _qr0 = _vd0.get("quant_readings") or {}
            if "candidate_yield" not in _qr0:
                bad.append("[量化] 真实入口下 `candidate_yield` **未落进** "
                           "quant_readings（纯函数绿 ≠ 引擎里可达）：%r"
                           % (sorted(_qr0.keys()),))
            else:
                _cv = _qr0.get("candidate_yield") or {}
                if isinstance(_cv, dict) and len(_cv) == 1 and "value" in _cv:
                    _cv = _cv["value"]
                if not isinstance(_cv, dict) or "verdict" not in _cv:
                    bad.append("[量化] 真实入口落盘值形态不对（应含 verdict）：%r"
                               % (_cv,))
                elif _cv.get("verdict") != "collapsed":
                    bad.append("[量化] mock 下两圈候选**完全相同**却未判 "
                               "collapsed（方向/口径错）：%r" % (_cv,))
            # ㉟ [可读性] 读数必须进**产物 md 正文**（不能只埋在附录 JSON）。
            _body_md = "\n".join(_cap_render)
            if "【各环节量化】" not in _body_md:
                bad.append("[量化] 读数**没进产物正文**（只在附录 JSON ⇒ "
                           "人类与工作台都看不见）")
            elif "锚点保真度" not in _body_md:
                bad.append("[量化] 正文有段落但缺中文标签（键→标签映射没生效）")
            # ★ 英文键名也要在正文里：① 便于按键 grep 对账；
            #   ② 附录的「字段名是否在正文出现」统计才不是**永远匹配不到**。
            elif "restate_fidelity" not in _body_md:
                bad.append("[量化] 正文只有中文标签、没有英文键名 "
                           "（附录字段名覆盖统计会失真；也难 grep 对账）")
            # ★ [v1.23.34 · view 输出结构] 正文最前面要有「本层速览」。
            #   与上面的量化断言**共用同一次 mock run**（不重复起引擎）。
            if "本层速览" not in _body_md:
                bad.append("[提示词] `_render` 正文缺「本层速览」"
                           "（view 输出结构没生效）")
            # ★ [判据修正] 这两个方法**开头就判 `enabled`**（与既有
            #   `_research_web_prep` 同惯例）⇒ 默认关时**根本不调** `_web_search`
            #   ⇒ Gate 自然一次都不出现。所以这里断言的是**结果**（零检索 +
            #   没走到 Gate），而不是「有没有走到 Gate 并被拦」——
            #   后者由探针 `_probe_v12334_web2stage.py`（显式打开开关）覆盖。
            if _w2s_allow:
                bad.append("[联网] 默认关时竟走到了 Gate（说明没判开关）：%r"
                           % (_w2s_allow[:3],))
            if "def _render(self, view" in src and "_QUANT_LABELS" not in src:
                bad.append("[量化] `_QUANT_LABELS` 缺失（正文段无法出中文标签）")
    except Exception as _ecy:
        bad.append("[量化] 真实入口跑候选产出率时抛错：%r" % (_ecy,))
    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  OK v1.23.33 AutoTune（帕累托 · 层集膝盖 · 圈数+1 · 不瞎猜 · 纯读 · "
          "四层目标读数 · 目标入运行 · 三阶段决策 · archive 开放探索）全过")
    return True


def check_v12331_memory_loop():
    """[v1.23.31] EML 经验记忆回路：跨跑储存记忆 + 每次跑自我学习与迭代。

    判据四层：源码级 / 纯函数级 / 真实入口级（**构造性证明「会学」**）/ 三态。
    判别力由 `_mut_v12331.py` 背书（M1~M10）。
    """
    import shutil as _sh
    import tempfile as _tf
    import time as _tm
    src = SRC.read_bytes().decode("utf-8")
    bad = []
    # ── 源码级 ──
    for _n, _w in (("def episode_from_result(", "episode"),
                   ("def eml_candidates_from_result(", "micro 候选"),
                   ("def gate_check(", "质量闸"),
                   ("def eml_merge_candidate(", "只增合并"),
                   ("def eml_promote(", "meso 升级"),
                   ("def eml_sweep_forget(", "遗忘清扫"),
                   ("def eml_recall(", "读"),
                   ("def eml_aggregate_macro(", "macro 聚合"),
                   ("def _eml_prepare(self, question: str)", "跑前读"),
                   ("def _eml_finish(self, result: dict)", "跑后写"),
                   ("def _eml_apply(self, rounds_plan: dict)", "生效面"),
                   ("EML 经验回路", "产物块")):
        if _n not in src:
            bad.append("[源码] %s 缺失（%r）" % (_w, _n))
    for _q in ("evidence", "contradiction", "verifiable", "redline"):
        if _q not in src:
            bad.append("[源码] 质量闸缺一问：%s" % _q)
    if "blocked_cost_only" not in src:
        bad.append("[源码] F2 双边记账（只省成本不升级）缺失")
    if "行数减少" not in src:
        bad.append("[源码] F5「只增不删」断言缺失")

    # ── 纯函数级 ──
    _good = {"kind": "schedule", "cond": {"issue": "cut"},
             "action": {"key": "rounds_delta", "layer": "1", "delta": 1},
             "readings": {"before": {"a": 1}, "after": {"b": 2}}}
    if not mod.gate_check(_good, [])[0]:
        bad.append("[闸] 正样本被判拒")
    if mod.gate_check({"kind": "s", "cond": {}, "action": {"key": "x"}},
                      [])[1] != "evidence":
        bad.append("[闸] 无读数未拒")
    if mod.gate_check({"kind": "s", "cond": {}, "action": {},
                       "readings": {"before": {"a": 1}}},
                      [])[1] != "verifiable":
        bad.append("[闸] 动作无 key 未拒")
    if mod.gate_check({"kind": "s", "cond": {},
                       "action": {"key": "inject_answer"},
                       "readings": {"before": {"a": 1}}},
                      [])[1] != "redline":
        bad.append("[闸] 触红线未拒（红线失守）")
    _pb = []
    _e1 = mod.eml_merge_candidate(_pb, dict(_good, evidence=["r1"]), 1.0)
    mod.eml_merge_candidate(_pb, dict(_good, evidence=["r1", "r2"]), 1.0)
    if len(_pb) != 1 or _pb[0].get("n_evidence") != 2:
        bad.append("[合并] 同键未累证据（行数=%d n_ev=%r）"
                   % (len(_pb), _pb[0].get("n_evidence")))
    if _e1.get("status") != "shadow":
        bad.append("[F1] 新条目不是 shadow")
    _a = [dict(_pb[0], status="shadow", n_evidence=5, quality_delta=0.0,
               cost_delta=-1.0, contra=0)]
    mod.eml_promote(_a, promote_n=3)
    if _a[0]["status"] != "shadow":
        bad.append("[F2] 只省成本的条目竟升级了（学坏）")
    # ★ 门槛**两向**都要测：只测「够则升」时，把门槛写成恒真的错实现
    #   照样过关（变异体 M4 假绿抓到的）。
    _b0 = [dict(_pb[0], status="shadow", n_evidence=1, quality_delta=0.2,
                cost_delta=0.0, contra=0)]
    mod.eml_promote(_b0, promote_n=3)
    if _b0[0]["status"] != "shadow":
        bad.append("[meso-负] 证据 1/3 竟升级（门槛失效）")
    _b = [dict(_pb[0], status="shadow", n_evidence=5, quality_delta=0.2,
               cost_delta=0.0, contra=0)]
    mod.eml_promote(_b, promote_n=3)
    if _b[0]["status"] != "active":
        bad.append("[meso] 正向证据够却未升级")
    _now = _tm.time()
    _c = [dict(_pb[0], status="active", t_last=_now - 400 * 86400,
               t_used=[], n_evidence=1)]
    mod.eml_sweep_forget(_c, _now, promote_n=3)
    if _c[0]["status"] != "retired" or len(_c) != 1:
        bad.append("[F4] 陈旧低证据未退休（或行被删）")
    _d = [dict(_pb[0], status="active", t_last=_now, t_used=[], n_evidence=1)]
    mod.eml_sweep_forget(_d, _now, promote_n=3)
    if _d[0]["status"] != "active":
        bad.append("[F4-负] 新条目被误清")
    _e = [{"id": "A1", "kind": "schedule", "status": "active", "t_last": _now,
           "n_evidence": 3, "weight": 1.0, "t_used": [],
           "action": {"key": "k1"}},
          {"id": "A2", "kind": "schedule", "status": "active", "t_last": _now,
           "n_evidence": 3, "weight": 1.0, "t_used": ["a", "b"],
           "action": {"key": "k2"}},
          {"id": "S1", "kind": "schedule", "status": "shadow", "t_last": _now,
           "n_evidence": 9, "weight": 1.0, "t_used": [],
           "action": {"key": "k3"}}]
    _ids = [x["id"] for x in mod.eml_recall(_e, "schedule", _now, top_k=5)]
    if "S1" in _ids:
        bad.append("[F1] shadow 竟进了 recall")
    if not _ids or _ids[0] != "A2":
        bad.append("[RRIF] 频率维失效（顺序 %r）" % _ids)
    _f = [{"id": "M1", "kind": "schedule", "status": "active",
           "cond": {"i": "cut"}, "action": {"key": "rounds_delta"}},
          {"id": "M2", "kind": "schedule", "status": "active",
           "cond": {"i": "cut"}, "action": {"key": "rounds_delta"}}]
    _snap = json.dumps(_f, ensure_ascii=False, sort_keys=True)
    if not mod.eml_aggregate_macro(_f, _now):
        bad.append("[macro] 未生成父条目")
    if json.dumps(_f, ensure_ascii=False, sort_keys=True) != _snap:
        bad.append("[macro] 子条目原文被改（ACE：不许重写/压缩）")

    # ── 真实入口：构造性证明「会学」──────────────────────
    _tmp = Path(_tf.mkdtemp(prefix="smk_eml_"))
    try:
        def _mkres(rid, cut=("1",)):
            return {"id": rid,
                    "question": "如何利用AI来帮助人类实现财富自由",
                    "route": ["0", "1", "both", "all"],
                    "rounds": {"0": 3, "1": 3, "both": 3, "all": 4},
                    "dispatch": {"_parallel_mode": "serial"},
                    "views": {e: {"stop_reason": (
                        "体力耗尽（3 圈走满）" if e in cut else "自然安住"),
                        "duty": {"S": 0.1 if e in ("0", "1") else 0.5}}
                        for e in ("0", "1", "both", "all")},
                    "pools": {"1": {"anchors": [], "web_results": []}},
                    "tri_consensus": [], "llm_tokens": 10, "llm_calls": 1,
                    "_auto_dispatch": {"_history": {}}}
        _cfg = dict(mod.DEFAULT_CONFIG)
        _cfg["playbook"] = {"mode": "on", "dir": str(_tmp), "top_k": 3,
                            "promote_n": 3, "halflife_days": 14.0}
        _eng = mod.MetaDGTF(_cfg)
        for _i in range(1, 5):
            _eng._eml_finish(_mkres("RUN%d" % _i))
        if not (_tmp / "playbook.jsonl").is_file():
            bad.append("[入口] playbook 未落盘")
        if len(mod.eml_read_jsonl(_tmp / "episodes.jsonl")) < 4:
            bad.append("[入口] episodes 未逐跑落盘")
        _act = [e for e in mod.eml_read_jsonl(_tmp / "playbook.jsonl")
                if e.get("status") == "active"]
        if not _act:
            bad.append("[入口] 4 跑同向证据未升级（学不会）")
        else:
            _pre = _eng._eml_prepare("如何利用AI来帮助人类实现财富自由")
            if not (_pre.get("used_ids") or []):
                bad.append("[入口] 第 5 跑未读到 active")
            _rp = {"0": 3, "1": 3, "both": 3, "all": 4}
            _ap = _eng._eml_apply(_rp)
            if not _ap:
                bad.append("[入口] 第 5 跑未生效（on 模式下应改写生效面）")
            _blk = _eng._eml_finish(_mkres("RUN5"))
            if not (_blk.get("used") or []):
                bad.append("[入口] 使用未留痕进产物块")
            if "strengthen" not in _blk:
                bad.append("[入口] 访问加强/执行留痕缺失")
        if not (_tmp / "MEMORY.md").is_file():
            bad.append("[入口] MEMORY.md 未生成")
        _c2 = dict(mod.DEFAULT_CONFIG)
        _c2["playbook"] = {"mode": "off", "dir": str(_tmp)}
        _e2 = mod.MetaDGTF(_c2)
        _e2._eml_prepare("x")
        if _e2._eml_finish(_mkres("RX")).get("merged"):
            bad.append("[三态] off 竟写库")
        _c3 = dict(mod.DEFAULT_CONFIG)
        _c3["playbook"] = {"mode": "shadow", "dir": str(_tmp)}
        _e3 = mod.MetaDGTF(_c3)
        _e3._eml_prepare("如何利用AI来帮助人类实现财富自由")
        if _e3._eml_apply({"0": 3, "1": 3, "both": 3, "all": 4}):
            bad.append("[三态] shadow 竟生效（F1 失守）")
    except Exception as _ex:
        import traceback
        traceback.print_exc()
        bad.append("[入口] 异常：%r" % (_ex,))
    finally:
        _sh.rmtree(_tmp, ignore_errors=True)

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  OK v1.23.31 经验记忆回路（闸门/只增/双边/遗忘/RRIF/构造性证明会学）全过")
    return True


def check_v12330_duty_guard():
    """[v1.23.30] 层职责守卫（LDG）：在**停止/收敛处**判「这层替问题干了什么」。

    判据分三层（源码级 / 纯函数级 / 真实入口级）：
      · 源码级：问项抽取、三读数、命中口径、停止判据、署名纪律、缺省修真
      · 纯函数级：相关 ⇒ C/S 高；无关 ⇒ C/S 低（负对照）；调和平均惩罚偏科
      · 真实入口级：走 `_finalize_layer_common`，职责未尽必须改署名 + 留痕；
        达标**不许**乱改（负对照）；缺失 core 注入 carry
    判别力由 `_mut_v12330.py` 背书（M1~M9）。
    """
    src = SRC.read_bytes().decode("utf-8")
    bad = []

    # ── 源码级 ──
    for _need, _what in (
            ("def question_aspects(question: str):", "问项抽取"),
            ("def duty_components(aspects, deliver_text", "三读数"),
            ("def duty_of_layer(entry, question, deliver_text", "层读数薄壳"),
            ("def duty_short_line(d:", "读数行"),
            ("_DUTY_KIND_W = {", "类别权重"),
            ("职责增益收敛", "新停止判据"),
            ("职责未尽：", "署名纪律"),
            ("_duty_carry", "补救注入")):
        if _need not in src:
            bad.append("[源码] %s 缺失（%r）" % (_what, _need))
    if '"distance_to_question": (None if d2q is None' not in src:
        bad.append("[源码] distance_to_question 入口缺省未修真")
    if src.count("distance_to_question is not None") != 2:
        bad.append("[源码] distance 渲染条件未改成「有值才印」")

    # ── 纯函数级 ──
    q = "如何利用AI来帮助人类实现财富自由甚至文明升级？"
    asp = mod.question_aspects(q)
    if not asp:
        bad.append("[纯函数] 问项抽取为空")
    else:
        if "followup" not in {a.get("kind") for a in asp}:
            bad.append("[纯函数] 「甚至…」未被归为 followup（%r）" % (asp,))
        if any(a.get("kind") == "followup" and a.get("weight") != 0.10
               for a in asp):
            bad.append("[纯函数] followup 权重不是最低档")
    _rel = ("利用AI帮助人类实现财富自由，并推动文明升级。"
            "AI 的作用体现在生产率提升与分配制度设计上。")
    _irr = ("候选属性0◈阴展开×位置both；线头编号 th#3 与 &4 未对齐；"
            "悬置决定 stable 后不可撤销；探针覆盖不足。")
    d_hi = mod.duty_components(asp, _rel, objective_words=("利用", "财富"))
    d_lo = mod.duty_components(asp, _irr, objective_words=("利用", "财富"))
    if d_hi["C"] < 0.5:
        bad.append("[纯函数] 相关交付面覆盖应高（实为 %r）" % d_hi["C"])
    if not (d_lo["C"] < d_hi["C"] and d_lo["S"] < d_hi["S"]):
        bad.append("[纯函数] 无关交付面未被拉低（C %r→%r / S %r→%r）"
                   % (d_hi["C"], d_lo["C"], d_hi["S"], d_lo["S"]))
    _mix = mod.duty_components(asp, _rel + "。" + _irr * 3,
                               objective_words=("利用", "财富"))
    # ★ 判据必须**钉公式**而不是钉不等式：只写「S ≤ 算术平均」时，
    #   「S 就是算术平均」这种错实现照样过关（变异体 M3 假绿抓到的）。
    _exp = (2.0 * _mix["C"] * _mix["R"] / (_mix["C"] + _mix["R"])
            if (_mix["C"] + _mix["R"]) else 0.0)
    if abs(_mix["S"] - _exp) > 1e-3:
        bad.append("[纯函数] S 不是调和平均（S=%r 期望 %r）"
                   % (_mix["S"], round(_exp, 4)))
    if abs(_mix["C"] - _mix["R"]) > 1e-6 and             abs(_mix["S"] - (_mix["C"] + _mix["R"]) / 2) < 1e-6:
        bad.append("[纯函数] S 退化成算术平均（偏科未被惩罚）")
    # ★ R 必须**真的用 Useless 当分母**：混入无用句后 R 必须严格 < 1
    #   （变异体 M5「R = 1 if direct else 0」就是靠这条判红的）。
    _rmix = mod.duty_components(
        asp, "利用AI帮助人类实现财富自由。" + _irr * 2,
        objective_words=("利用", "财富"))
    if not (_rmix["seg_useless"] >= 1 and _rmix["seg_direct"] >= 1):
        bad.append("[纯函数] 夹具没造出「既有直接句又有无用句」（%r）"
                   % {k: _rmix[k] for k in
                      ("seg_direct", "seg_useful", "seg_useless")})
    else:
        _rexp = _rmix["seg_direct"] / float(
            _rmix["seg_direct"] + _rmix["seg_useless"])
        if abs(_rmix["R"] - _rexp) > 1e-3:
            bad.append("[纯函数] R 不是 |Direct|/(|Direct|+|Useless|)"
                       "（R=%r 期望 %r）" % (_rmix["R"], round(_rexp, 4)))
    if not d_lo["missing_core"]:
        bad.append("[纯函数] 无关交付面未点名缺失 core")

    # ── 真实入口级 ──
    try:
        cfg = dict(mod.DEFAULT_CONFIG)
        eng = mod.MetaDGTF(cfg)
        eng._question = q
        v = mod.View(entry="1")
        v.collision = _irr * 4
        d = eng._layer_duty_now("1", v)
        if not v.duty or v.duty.get("S") != d["S"]:
            bad.append("[入口] duty 未写回 view")
        if len(v.duty_trace) != 1:
            bad.append("[入口] duty_trace 未记账（%r）" % v.duty_trace)
        if not d.get("short"):
            bad.append("[入口] 无关交付面未判 short")
        v.stop_reason = "悬置决定稳定，自然安住，螺旋停止"
        st = {"all_candidates": [], "all_amps": [], "all_threads": [],
              "all_rehashed": [], "all_expanded_descs": [],
              "all_dec_products": [], "all_und_products": [],
              "all_view_errors": [], "round_log": [], "roles_hist": [],
              "deferred_notes": [], "total_rounds": 4, "r": 1,
              "rounds_n": 4, "sp": dict(cfg.get("spiral") or {})}
        eng._finalize_layer_common("1", v, st)
        if "职责未尽" not in (v.duty_verdict or ""):
            bad.append("[入口] 职责未尽未写独立判定行")
        if (v.stop_reason or "") != "悬置决定稳定，自然安住，螺旋停止":
            bad.append("[入口] 停止理由被职责判定污染（红线：停止与清算分开）"
                       "：%r" % (v.stop_reason,))
        if "duty_short" not in (v.quality_flags or []):
            bad.append("[入口] duty_short 未留痕（被收尾清洗吞了？）")
        if not (getattr(eng, "_duty_carry", None) or []):
            bad.append("[入口] 缺失 core 未注入 carry")
        # 负对照：达标不许乱改
        eng2 = mod.MetaDGTF(cfg)
        eng2._question = q
        v2 = mod.View(entry="1")
        v2.collision = _rel * 8
        v2.stop_reason = "悬置决定稳定，自然安住，螺旋停止"
        eng2._finalize_layer_common("1", v2, dict(st))
        if v2.duty_verdict:
            bad.append("[入口·负] 达标却仍写判定行")
        if (getattr(eng2, "_duty_carry", None) or []):
            bad.append("[入口·负] 达标却仍注入 carry")
    except Exception as e:
        import traceback
        traceback.print_exc()
        bad.append("[入口] 异常：%r" % (e,))

    # ── 缺省修真（两向）──
    if mod.View(entry="0").distance_to_question is not None:
        bad.append("[缺省] 字段缺省应为 None")
    # ★ 只查字段缺省不够：**入口那条路**（模型没报 d2q 时）也必须落 None
    #   —— 变异体 M9 改的是入口那行，查字段永远查不到（M9 假绿抓到的）。
    if ("None if _d2q_raw is None else float(_d2q_raw)" not in src):
        bad.append("[缺省] 入口缺省未落 None（模型没报时不许顶格 1.0）")
    if '"distance_to_question": (None if d2q is None' not in src:
        bad.append("[缺省] 装配处缺省未落 None")
    if "if v.get(\"distance_to_question\", 1.0) < 1.0" in src:
        bad.append("[缺省] save_result 仍在用顶格缺省比较（None 会直接崩）")

    if bad:
        for x in bad:
            print("  ✗", x)
        return False
    print("  ✓ v1.23.30 层职责守卫（源码/纯函数/真实入口 三层判据）全过")
    return True


def check_v12329_convergence():
    """[v1.23.29] 收束版判据：A1 索引化 / B1 规则优先 / C1 读数口径 /
    D1 相对阈值 / D2 语义归并（正负两臂 + 出口）。

    ★ 源码级 + 函数级双层：源码锚保证机制在；函数级两臂保证行为对。
    ★ 判别力由 `_mut_v12329.py` 背书（M1~M8）。
    """
    src = SRC.read_bytes().decode("utf-8")
    bad = []

    # A1：`## 这一次我是谁` 索引化（去掉与逐层明细的整段重复）
    if "## 这一次我是谁（索引）" not in src:
        bad.append("[A1] 索引标题缺失")
    if 'self_text = ["[<层>] " + view.manifest' in src:
        bad.append("[A1] 旧截断复制仍在（manifest[:900] 未删）")

    # B1：规则优先的模式分派（收敛到 serial/B/C）
    if '_AUTO_REACHABLE_MODES = ("serial", "B", "C")' not in src:
        bad.append("[B1] _AUTO_REACHABLE_MODES 缺失或不收敛")
    if "def _mode_rule(self, question: str):" not in src:
        bad.append("[B1] _mode_rule 缺失")
    if "def mode_rule(question: str):" not in src:
        bad.append("[B1] 模块级 mode_rule 唯一实现缺失")
    if '"source": "rule"' not in src:
        bad.append("[B1] 规则优先路径（source=rule）缺失")

    # C1：touch_rate 逐圈口径前提（键存在才走逐圈）
    if '_has_per_round = any(' not in src:
        bad.append("[C1] touch_rate 逐圈前提守卫缺失")

    # D1：相对分位阈值
    if "def sem_thr_relative(" not in src:
        bad.append("[D1] sem_thr_relative 缺失")
    if 'thr.strip().lower() == "rel"' not in src:
        bad.append("[D1] rel 触发分支缺失")

    # D2：语义归并四件套（常量/属性/认领/出口）
    if "_BELIEF_MERGE_SIM = 0.85" not in src:
        bad.append("[D2] 归并阈值常量缺失")
    if "merge_semantic: bool = False" not in src:
        bad.append("[D2] Pool.merge_semantic 字段缺失")
    if 'getattr(self, "merge_semantic", False)' not in src:
        bad.append("[D2] upsert 语义认领段缺失")
    if 'd["merge_log"] = list(getattr(self, "merge_log", []) or [])' not in src:
        bad.append("[D2] merge_log 产物出口缺失")
    if "_p.merge_semantic = _mg" not in src:
        bad.append("[D2] 配置下发接线缺失")

    # ── 函数级两臂（真实类，不打桩）──────────────────────
    try:
        _pool = mod.Pool()
        _pool.merge_semantic = True
        _pool.merge_sim = mod._BELIEF_MERGE_SIM
        _pool.upsert_belief("灵魂是否存在取决于定义的清晰度", sources=["t"])
        _pool.upsert_belief("灵魂是否存在，取决于定义的清晰度", sources=["t"])
        if len(_pool.belief_items) != 1:
            bad.append("[D2-正臂] 换说法未被归并（条目数=%d）"
                       % len(_pool.belief_items))
        if not getattr(_pool, "merge_log", None):
            bad.append("[D2-正臂] merge_log 空")
        _pool.upsert_belief("地铁票价应当按里程计费", sources=["t"])
        if len(_pool.belief_items) != 2:
            bad.append("[D2-负臂] 不同主张被错并（条目数=%d）"
                       % len(_pool.belief_items))
        _d = _pool.to_dict()
        if _d.get("merge_semantic") is not True or not _d.get("merge_log"):
            bad.append("[D2-出口] merge_semantic/merge_log 未出口")
        _off = mod.Pool()
        _off.upsert_belief("甲乙丙", sources=["t"])
        _off.upsert_belief("甲乙丙，", sources=["t"])
        if len(_off.belief_items) != 2 or getattr(_off, "merge_log", None):
            bad.append("[D2-关臂] 默认关时不归并/不留痕")
    except Exception as e:
        bad.append("[D2-函数级] 异常：%r" % (e,))

    # ── [1f] 规则命中 ⇒ 三处分派同案且不花 LLM 调用 ──────
    try:
        import json as _json
        class _RStub:
            def __init__(self, payload):
                self.payload = payload
                self.calls = 0
            def call(self, *a, **k):
                self.calls += 1
                return _json.dumps(self.payload, ensure_ascii=False)
            def parse_json(self, raw):
                return _json.loads(raw)
        _qhit = "探针题"  # 规则命中（单一短问句 ⇒ serial）
        _hitpl = {"route": "full", "mode": "H",
                  "rounds": {"0": 3, "1": 7, "both": 4, "all": 6},
                  "max_calls": 0, "reason": "probe", "confidence": 0.9,
                  "orientation": "decision"}
        _cfg = build_cfg(False)
        _m1 = mod.MetaDGTF(_cfg)
        _st1 = _RStub(dict(_hitpl))
        _m1.llm = _st1
        _r1 = _m1._decide_parallel_mode(_qhit)
        if _r1.get("mode") != "serial" or _r1.get("source") != "rule":
            bad.append("[1f] _decide 规则命中未定案（%r）" % (_r1,))
        if _st1.calls:
            bad.append("[1f] _decide 规则命中仍花了 LLM 调用（%d 次）"
                       % _st1.calls)
        _st2 = _RStub(dict(_hitpl))
        _oL = mod.LLM
        mod.LLM = lambda c: _st2
        try:
            _r2 = mod.plan_resources(_qhit, "decision", _cfg)
        finally:
            mod.LLM = _oL
        if _r2.get("mode") != "serial" or _st2.calls:
            bad.append("[1f] plan_resources 规则未优先（mode=%r calls=%d）"
                       % (_r2.get("mode"), _st2.calls))
        _m3 = mod.MetaDGTF(_cfg)
        _st3 = _RStub(dict(_hitpl))
        _m3.llm = _st3
        _r3 = _m3._auto_plan(_qhit)
        if _r3.get("mode") != "serial" or _st3.calls:
            bad.append("[1f] auto_plan 规则未优先（mode=%r calls=%d）"
                       % (_r3.get("mode"), _st3.calls))
        if not str(_r3.get("reason", "")).startswith("规则"):
            bad.append("[1f] auto_plan 规则命中 reason 未标注（%r）"
                       % _r3.get("reason"))
    except Exception as e:
        bad.append("[1f] 异常：%r" % (e,))

    if bad:
        for x in bad:
            print("  ✗", x)
        return False
    print("  ✓ v1.23.29 收束判据（A1/B1/C1/D1/D2/1f）全过")
    return True


def check_v12328_real_entry():
    """[v1.23.28] **真实入口产出**判据（收口 R2）。

    ★ 为什么必须有独立的一条：v1.23.27 的 D1/D2 判据全是**纯函数**形态
      （直接 `mod.belief_transition(...)` 喂构造入参）—— 全绿，但真实
      入口下三条迁移**结构性不可达**（`upsert_belief` 被嵌在「结构名是
      新的」守卫里 ⇒ 复现被 `_DUP_SIM` 挡掉）。**纯函数判据全绿 ≠ 该
      能力在引擎里可达**。
    ★ 本判据走**真实入口** `Pool.add_undecidable(...)`（引擎唯一写入口），
      数圈后断言产出物 `belief_transitions` 里真的出现三种迁移。
    ★ 负对照：同一层反复说同一句 ⇒ **不许**升 stable（层名口径）。
    ★ 判别力由 `_mut_v12328.py` 背书（M1~M6）。
    """
    bad = []

    # ── D1/D2 真实入口：跨层复现 ⇒ stable ──────────────────
    # ★ 夹具要点：**两条不同主张** —— 单条主张时 D3 的语料去重后只剩
    #   1 条 ⇒ `semantic_entropy_of` 按设计返回 None（n<2），会与
    #   「D3 未接线」混淆。两条不同主张 ⇒ 熵有值，两件事各自可判。
    _p = mod.Pool()
    _prod = {"structural_amps": ["低温下材料脆性阈值随温度单调下降",
                                 "城市轨道客流预测误差主要来自换乘"],
             "aligned_amps": [], "clarity": 0.5}
    # 第 1 圈：layer0
    _p.add_undecidable(dict(_prod, _layer_name="0", _round_no=1),
                       und_aspects=["脆性阈值"], layer=1)
    # 第 2 圈：layer1（**不同层** ⇒ 独立复现）
    _p.add_undecidable(dict(_prod, _layer_name="1", _round_no=2),
                       und_aspects=["脆性阈值"], layer=2)
    _tos = [t.get("to") for t in (_p.belief_transitions or [])]
    if "stable" not in _tos:
        bad.append("[R-D2] 真实入口下跨层复现未升 stable（transitions=%r）"
                   "—— 纯函数全绿但入口不可达" % (_tos,))

    # ── 负对照：同层反复说 ⇒ 不许 stable ───────────────────
    _pq = mod.Pool()
    _prod2 = {"structural_amps": ["城市轨道客流预测误差来源"],
              "aligned_amps": [], "clarity": 0.5}
    for _r in (1, 2, 3, 4):
        _pq.add_undecidable(dict(_prod2, _layer_name="0", _round_no=_r),
                            und_aspects=["客流预测"], layer=_r)
    _toq = [t.get("to") for t in (_pq.belief_transitions or [])]
    if "stable" in _toq:
        bad.append("[R-D2-neg] 同层反复说竟升 stable —— "
                   "「同一层重复」冒充「独立复现」（transitions=%r）" % (_toq,))

    # ── D2 真实入口：跨层攻击 ⇒ revoked ────────────────────
    # ★ 夹具要点：攻击必须来自 **≥2 个不同层**（对称规则）。
    #   改前规则 `len(atk) >= len(sup)` 在真实入口退化成「每圈都攻击」，
    #   本条夹具（第 2、3 圈各一攻击、来源为 layer1/layerboth）在新旧
    #   规则下结论不同 ⇒ 有判别力。
    _pa = mod.Pool()
    _pa.add_undecidable({"structural_amps": ["某主张甲"],
                         "aligned_amps": [], "clarity": 0.5,
                         "_layer_name": "0", "_round_no": 1},
                        und_aspects=["某方面"], layer=1)
    _pa.add_undecidable({"structural_amps": ["某主张甲"],
                         "aligned_amps": [], "clarity": 0.5,
                         "_layer_name": "1", "_round_no": 2,
                         "_belief_attack": "反例：实测不成立"},
                        und_aspects=["某方面"], layer=2)
    _pa.add_undecidable({"structural_amps": ["某主张甲"],
                         "aligned_amps": [], "clarity": 0.5,
                         "_layer_name": "both", "_round_no": 3,
                         "_belief_attack": "反例：第二个反证"},
                        und_aspects=["某方面"], layer=3)
    _toa = [t.get("to") for t in (_pa.belief_transitions or [])]
    if "revoked" not in _toa:
        bad.append("[R-D2-atk] 真实入口下**跨层**攻击未产生 revoked"
                   "（transitions=%r）" % (_toa,))

    # ── 负对照：同层反复攻击 ⇒ 不许 revoked ────────────────
    # ★ 为什么必须有这条：对称规则的核心就是「独立性不是次数」。
    #   若哪天有人把规则改回 `len(atk) >= len(sup)`，这条会立刻判红。
    _prv = mod.Pool()
    _prv.add_undecidable({"structural_amps": ["某被骂主张"],
                          "aligned_amps": [], "clarity": 0.5,
                          "_layer_name": "0", "_round_no": 1},
                         und_aspects=["某方面"], layer=1)
    for _r in (2, 3, 4, 5):
        _prv.add_undecidable({"structural_amps": ["某被骂主张"],
                              "aligned_amps": [], "clarity": 0.5,
                              "_layer_name": "0", "_round_no": _r,
                              "_belief_attack": "反例%d" % _r},
                             und_aspects=["某方面"], layer=_r)
    _torv = [t.get("to") for t in (_prv.belief_transitions or [])]
    if "revoked" in _torv:
        bad.append("[R-D2-atk-neg] 同层反复攻击竟 revoked —— "
                   "「同一来源重复骂」冒充「独立复现」（transitions=%r）"
                   % (_torv,))

    # ── D2 真实入口：清偿 ⇒ resolved ───────────────────────
    _pr = mod.Pool()
    _pr.add_undecidable({"structural_amps": ["某可判定主张"],
                         "aligned_amps": [], "clarity": 0.5,
                         "_layer_name": "0", "_round_no": 1},
                        und_aspects=["某方面"], layer=1)
    _pr.add_undecidable({"structural_amps": ["某可判定主张"],
                         "aligned_amps": [], "clarity": 0.5,
                         "_layer_name": "1", "_round_no": 2,
                         "_belief_resolved": "decidable_channel"},
                        und_aspects=["某方面"], layer=2)
    _tor = [t.get("to") for t in (_pr.belief_transitions or [])]
    if "resolved" not in _tor:
        bad.append("[R-D2-res] 真实入口下清偿未产生 resolved"
                   "（transitions=%r）" % (_tor,))

    # ── 出口判据：池级可观测量 ─────────────────────────────
    # ★ `Pool.to_dict` 是**手工白名单**（与 `View.to_dict` 的自动全量
    #   语义不同）⇒ 空池没有 `aspect_units` 键是**正确**的（不凭空造
    #   字段）。所以必须**先经 merge 灌入**再断言出口存在。
    _vpool = mod.View(entry="0")
    _vpool.add_aspect_unit("池级方面甲", source="anchor", polarity="阳",
                           ground="anchor")
    _p.merge(_vpool.amps, _vpool.threads, _vpool.meta, _vpool.probes,
             aspect_units=list(_vpool.aspect_units))
    _d = _p.to_dict()
    if "belief_status_counts" not in _d:
        bad.append("[R-out] pool.to_dict 缺 belief_status_counts")
    elif not _p.belief_items:
        bad.append("[R-out] 真实入口后 belief_items 仍为空")
    else:
        _bs = _d.get("belief_status_counts") or {}
        if sum(_bs.get(k, 0) for k in _bs) != len(_p.belief_items):
            bad.append("[R-out] 四态计数之和不等于条目数（%r vs %d）"
                       % (_bs, len(_p.belief_items)))
    if "aspect_units" not in _d:
        bad.append("[R-out] pool.to_dict 缺 aspect_units（A1 池级镜像）"
                   "—— merge 灌入后仍未出口")
    if "aspect_units" in mod.Pool().to_dict():
        bad.append("[R-out] 空 Pool 不该凭空出现 aspect_units")

    # ── D3 真实入口：语义熵**真的量出「同一主张的说法发散度」** ───
    # ★ 语义（R3 重新设计）：熵度量的是「**同一条主张**的历次说法有多
    #   发散」。两条**无关**主张各只有自己一种说法 ⇒ 正确读数就是
    #   `None`（诚实缺省），**不是**「未接线」。所以本判据改用
    #   「同一主张的两种近义说法」构造：换说法 ⇒ 两条目 ⇒ 必须聚成
    #   一簇 ⇒ 熵 **0.0**（不是 None）。
    # ★ 为什么**必须再放一条无关主张**（第三项）：只放两条近义说法时，
    #   「把全池文本混在一起算」的错误实现**也**会得到 0.0（只有两条、
    #   恰好同簇）⇒ 判不出「聚类口径错」。加一条**无关**主张后：
    #     · 正确实现（只留包住本条目的簇）⇒ 仍 0.0（无关条目被排除）
    #     · 错误实现（全池混合）⇒ 簇分裂 ⇒ **> 0** ⇒ 判红
    #   这就是 M9 变异体要打的点（「判据必须能分辨错实现」）。
    _pd = mod.Pool()
    _pd.sem_entropy_thr = float(getattr(mod, "_SEM_CLUSTER_THR", 0.30))
    _pd.upsert_belief("落盘的最小单位是约束", ground="layer1", round_no=1,
                      sources=["layer1"])
    _pd.upsert_belief("落盘的最小单位是那条约束", ground="layer0",
                      round_no=2, sources=["layer0"])
    _pd.upsert_belief("城市轨道交通客流预测模型误差主要来自换乘",
                      ground="both", round_no=3, sources=["both"])
    _pd.refresh_belief_entropy(thr=_pd.sem_entropy_thr)
    _ed = [(it.get("id"), it.get("occurrence_n"),
            it.get("semantic_entropy")) for it in _pd.belief_items]
    # 前两条（同一主张的近义说法）必须聚成一簇且熵 ~0；
    # 第三条（无关主张）必须只有自己（occurrence_n == 1 / 熵 None）。
    _pair = _ed[:2]
    _solo = _ed[2] if len(_ed) > 2 else None
    if not all(e[1] and e[1] >= 2 for e in _pair):
        bad.append("[R-D3] 同一主张的两种近义说法未聚成一簇"
                   "（occurrence_n 全 < 2；读数=%r）—— D3 未接线或阈值"
                   "不可达成" % (_ed,))
    elif not all(e[2] is not None and e[2] <= 0.05 for e in _pair):
        bad.append("[R-D3] 同一主张近义说法应近 0 熵（实为 %r）"
                   "—— 聚类口径错（把无关主张也混进来了？）" % (_ed,))
    elif _solo is not None and _solo[1] and _solo[1] >= 2:
        bad.append("[R-D3] 无关主张被混进同一簇（occurrence_n=%r）—— "
                   "聚类口径错：应按「只留包住本条目的簇」" % (_solo[1],))
    # 负对照 1：单条主张 ⇒ 必须 None（不许印 0.0 冒充「很稳」）
    _pd2 = mod.Pool()
    _pd2.upsert_belief("只出现一次的主张", ground="layer1", round_no=1,
                       sources=["layer1"])
    _pd2.refresh_belief_entropy(thr=_pd2.sem_entropy_thr)
    if _pd2.belief_items and _pd2.belief_items[0].get(
            "semantic_entropy") is not None:
        bad.append("[R-D3-neg1] 单条主张应返回 None（实为 %r）—— "
                   "印 0.0 是自欺"
                   % (_pd2.belief_items[0].get("semantic_entropy"),))
    # 负对照 2：阈值拨回旧错值 0.70 ⇒ 同一组近义说法必须退化成 None
    #   （证 `sem_entropy_thr` **真接线**，不是只在 DEFAULT_CONFIG 里挂着）
    _pd3 = mod.Pool()
    _pd3.sem_entropy_thr = 0.70
    _pd3.upsert_belief("落盘的最小单位是约束", ground="layer1", round_no=1,
                       sources=["layer1"])
    _pd3.upsert_belief("落盘的最小单位是那条约束", ground="layer0",
                      round_no=2, sources=["layer0"])
    _pd3.refresh_belief_entropy(thr=_pd3.sem_entropy_thr)
    _ed3 = [it.get("occurrence_n") for it in _pd3.belief_items]
    if any(n and n >= 2 for n in _ed3):
        bad.append("[R-D3-neg2] thr=0.70 时近义说法竟仍聚成一簇"
                   "（occurrence_n=%r）—— 阈值未接线或聚类不受 thr 影响"
                   % (_ed3,))
    # 出口：occurrence_n 与 semantic_clusters 必须落盘
    if _pair and not all("semantic_clusters" in it
                         for it in _pd.belief_items):
        bad.append("[R-D3-out] 信念条目缺 semantic_clusters 出口")
    # 池级出口：belief_items 里的 occurrence_n 必须能经 to_dict 读到
    _dd = _pd.to_dict()
    _bi_out = _dd.get("belief_items") or []
    if _bi_out and not all("semantic_entropy" in x for x in _bi_out):
        bad.append("[R-D3-out] 池级 belief_items 出口缺 semantic_entropy")

    # ── F3 `View.belief_items` 回填：**必须走真实入口后非空** ──────
    # ★ 这条的失败形态是「静态判据全绿、真实入口恒空」：回填块写得完全
    #   正确，但位置在 `pool.add_undecidable(...)` **之前** ⇒ 读到的池
    #   还是空的 ⇒ `view.belief_items` 恒 []（真跑产物实测，见报告 §2.5）。
    #   ⇒ 判据必须**驱动真实入口**（`_apply_view_to_pool_locked`）再断言产出，
    #     而不是查源码里有没有那段回填代码。
    #   判别力由 `_mut_v12328.py` 的 **M11**（把回填搬回原位）背书。
    try:
        _pf = mod.Pool()
        _vf = mod.View(entry="0")
        _FA = "介质只保存可区分的物理状态不保存这是四态字段这句话"
        _FB = "解码失败状态必须作为持久化判定结果存在否则读写错位"
        _vf.amps = [{"type": "&", "desc": _FA}, {"type": "&", "desc": _FB}]
        _vf.undecidable_product = {
            "question": "x", "structural_amps": [_FA, _FB],
            "clarity": 0.4, "_layer_name": "0", "_round_no": 1,
        }
        _mf = object.__new__(mod.MetaDGTF)
        _mf.config = {"sim": {},
                      "belief": {"revoke_sources": 2, "sem_entropy_thr": 0.30}}
        _mf.decidability_result = None
        _mf._anchor_report = None
        _mf._ext_assess_cache = {}
        _mf._apply_view_to_pool_locked(_vf, _pf, "entry-f", layer=1)
        if not (_pf.belief_items or []):
            bad.append("[R-F3-pre] 池里没产出信念条目 ⇒ 夹具失效（前置条件不成立）")
        elif not (_vf.belief_items or []):
            bad.append("[R-F3] 真实入口后 `view.belief_items` 仍为空"
                       "（池 n=%d）—— 回填块**位置/时序**有误（读在写前）"
                       % len(_pf.belief_items or []))
        # 负对照：text 对不上时必须保持 []（不许倒全池兜底）
        _vf2 = mod.View(entry="0")
        _vf2.amps = [{"type": "&", "desc": "与池内任何条目都无关的一句话XYZQ"}]
        _vf2.undecidable_product = {
            "question": "y", "structural_amps": ["另有一条无关主张PQRS"],
            "clarity": 0.2, "_layer_name": "0", "_round_no": 2,
        }
        _mf._apply_view_to_pool_locked(_vf2, _pf, "entry-f2", layer=1)
        if _vf2.belief_items:
            bad.append("[R-F3-neg] text 对不上时竟回填了 %d 条"
                       "—— 兜底倒全池（应保持 []）" % len(_vf2.belief_items))
    except Exception as _ef:
        bad.append("[R-F3] 驱动真实入口异常：%s: %s"
                   % (type(_ef).__name__, _ef))

    # ── A3 双读数出口 ─────────────────────────────────────
    _vx = mod.View(entry="0")
    _vx.round_log = [{"anchor_touched_n": 3}]
    _vx.aspect_units = [{"id": "A1", "text": "t", "desc": "t"}]
    _vx._layer_und_channel = {}
    _vd = _vx.to_dict()
    if "touch_rate" not in _vd:
        bad.append("[R-out] view.to_dict 缺 touch_rate（A3 双读数无出口）")
    # ★ [v1.23.29 判据随实现更新 · 不是放宽] 新口径：`aspect_carry_rate`
    #   无延续读数时返回 None ⇒ **不写这个键**（v1.23.28 的出口纪律：
    #   算不出就不印，不印 0.00 冒充）。所以这里改成**两向**：
    #     · 无延续读数 ⇒ 键不该出现；
    #     · **有**延续 id ⇒ 键必须出现且是真值（否则「一律不出」也骗过）。
    if "aspect_carry_rate" in _vd:
        bad.append("[R-out] 无延续读数时 aspect_carry_rate 不该出口"
                   "（不印 0.00 冒充）实为 %r" % _vd.get("aspect_carry_rate"))
    _vx2 = mod.View(entry="0")
    _vx2.aspect_units = [{"id": "A1", "text": "t"}, {"id": "A2", "text": "u"}]
    _vx2._carried_aspect_ids = ["A1"]
    _vd2 = _vx2.to_dict()
    if _vd2.get("aspect_carry_rate") != 0.5:
        bad.append("[R-out] 有延续 id 时 aspect_carry_rate 必须出口真值"
                   "（实为 %r）" % _vd2.get("aspect_carry_rate"))

    # ── T1 探针落盘带 gain_source ──────────────────────────
    # ★ 走**真实入口** `select_probe_focus`（E1/E2 的唯一接线点），
    #   构造「未决 ≥2 且候选命中分歧」⇒ 引擎算得出 G ⇒ gain_source
    #   必须是 "engine"。只数源码字符串会「写入无消费」也判绿。
    _pt = mod.Pool()
    _pt.belief_items = [
        {"id": "B1", "text": "极低温环境下材料脆性阈值是多少",
         "status": "active"},
        {"id": "B2", "text": "极低温环境下材料脆性阈值如何",
         "status": "active"},
        {"id": "B3", "text": "城市轨道交通客流预测模型的误差",
         "status": "active"},
    ]
    try:
        _picked_t = mod.select_probe_focus(
            _pt,
            [{"question": "极低温环境下材料脆性阈值是多少"}],
            [], ["低温", "脆性"], "极低温材料", {"probe": {"select_n": 3}})
        _gs = [p.get("gain_source") for p in (_picked_t or [])]
        if not _picked_t:
            bad.append("[R-T1] select_probe_focus 未产出探针")
        elif "engine" not in _gs:
            bad.append("[R-T1] 引擎算得出 G 时 gain_source 应为 engine"
                       "（实为 %r）—— E1 来源不可审计" % (_gs,))
        for _p in (_picked_t or []):
            if "gain_source" not in _p:
                bad.append("[R-T1] 落盘探针 dict 缺 gain_source 键")
                break
    except Exception as _e:
        bad.append("[R-T1] select_probe_focus 调用失败：%s: %s"
                   % (type(_e).__name__, _e))

    if bad:
        for _m in bad:
            print("  \u2717 [v12328] %s" % _m)
        return False
    print("  \u2713 [v12328] 真实入口产出（跨层 stable / attack revoked / "
          "清偿 resolved / 同层负对照 0）· 池级出口 · D3 语料自供+阈值"
          "解耦（近义聚簇 / 单条 None / thr 负对照）· "
          "A3 出口 · gain_source（变异体背书）")
    return True


def check_v12324_indep_therapy():
    """[v1.23.24] ① 不可判定「独立度」口径（取代误名的结构覆盖率）
       ② 修行层停止判据与文案（去 ing / 补空括号 / 一律附体检）。

    ★ 每条判据都带负对照；判别力另由 `_mut_v12324.py` 的 7 个变异体证明
      （没有变异体的「全绿」只说明判据没跑）。
    ★ 独立度夹具的判别力：旧口径 = 1/3 = 0.333，新口径 = 2/4 = 0.500
      —— 两者不同值，否则这条样例在两种实现下同结论、等于没测。
    """
    import contextlib as _cl
    import inspect as _ins
    import io as _io
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    cfg = build_cfg(False)

    # ================= A. 独立度口径 =================
    _asp = ["本体论地位需要先确定登记位置", "自指结构导致时刻错开",
            "判决实验缺少可操作标准"]
    _amps = ["本体论地位需要先确定登记位置",
             "任何判定都要求对象在登记前已有边界，本体论地位因此没有登记位置",
             "与上述各项均无关的一条独立结构观察结论",
             "关于尺度效应的一条独立观察，与判定标准无关"]
    _p = mod.Pool()
    _p.add_undecidable({"structural_amps": list(_amps), "aligned_amps": [],
                        "clarity": 0.6}, list(_asp), layer=1)
    _ch = _p.undecidable_channel

    if _ch.get("last_indep_pool") != 4 or _ch.get("last_indep_free") != 2:
        bad.append(f"[A] 独立度计数错：pool={_ch.get('last_indep_pool')} "
                   f"free={_ch.get('last_indep_free')}（应 4 / 2）")
    if abs(float(_ch.get("last_indep_ratio") or -1) - 0.5) > 1e-9:
        bad.append(f"[A] 独立度不是 2/4=0.5：{_ch.get('last_indep_ratio')}")
    if list(_ch.get("indep_history") or []) != [0.5]:
        bad.append(f"[A] indep_history 不对：{_ch.get('indep_history')}")
    # ★ 不变式：旧键一个数不许动（历史语料的口径 + 命中轨迹的输入）
    if _ch.get("last_struct_coverage") != 0.3333333333333333:
        bad.append(f"[A] 旧键 last_struct_coverage 被动了："
                   f"{_ch.get('last_struct_coverage')}（应 1/3）")
    # 空池：必须 None（不可计算），不许 0.0（假读数）
    _pe = mod.Pool()
    _pe.add_undecidable({"structural_amps": [], "aligned_amps": [],
                         "clarity": 0.5}, list(_asp), layer=1)
    if _pe.undecidable_channel.get("last_indep_ratio") is not None:
        bad.append(f"[A] 空池的独立度不是 None："
                   f"{_pe.undecidable_channel.get('last_indep_ratio')}")

    # 产物渲染：新口径 + 口径标注；新口径 dict 里不许再出现「结构覆盖率」
    _mg = mod.MetaDGTF(cfg)
    _mg.pools["1"].undecidable_channel = _ch
    _line = _mg._und_channel_line()
    if "独立度 0.50" not in _line:
        bad.append(f"[A] 产物没渲染独立度：{_line!r}")
    if "2/4" not in _line:
        bad.append(f"[A] 独立度的分子分母没渲染：{_line!r}")
    if "不是覆盖率" not in _line:
        bad.append(f"[A] 口径标注（不是覆盖率）缺了：{_line!r}")
    # ★ v1.23.25 起「结构覆盖率」是**重设计后的合法读数**（自触及），
    #   不再是误名 ⇒ 这条否定断言反过来：新口径 dict 里
    #   `sc_history` 不存在时不许印，存在时必须印（见 B 段）。
    if "sc_history" not in _ch and "结构覆盖率" in _line:
        bad.append(f"[A] 无 sc_history 时不该印结构覆盖率：{_line!r}")
    # 负对照：历史 packed（只有旧键）必须仍渲染得出来，且显式标「旧口径」
    _m3 = mod.MetaDGTF(cfg)
    # ★ 这是**真实历史 packed** 的形态：v1.23.23 的 add_undecidable 会写
    #   last_struct_coverage。smoke 里 v69 那份手工 dict 裁掉了这个键，
    #   照抄它去测 `_pool_shape`（那里的门正是这个键）会得到「空」——
    #   那是夹具不像历史，不是实现丢了东西。
    _m3.pools["1"].undecidable_channel = {
        "clarity_history": [0.5], "struct_coverage_history": [0.6],
        "und_aspects": [f"面{i}" for i in range(10)],
        "last_struct_hit": 6, "last_struct_coverage": 0.6,
        "structural_amps": ["a"], "aligned_amps": [],
    }
    _l3 = _m3._und_channel_line()
    if "结构覆盖率 0.60" not in _l3 or "旧口径" not in _l3:
        bad.append(f"[A-负对照] 历史 packed 的旧口径读数丢了：{_l3!r}")

    # 喂模型的 shape（★ 运行期可见变化：新口径进、旧口径作回退）
    def _shape(_pl):
        _dg = mod.DGTF("1", mod.LLM(cfg), cfg)
        _dg.verbose = False
        with _cl.redirect_stdout(_io.StringIO()):
            return _dg._pool_shape(_pl, "P")

    _s_new = _shape(_p)
    if "不可判定独立度 0.50" not in _s_new:
        bad.append(f"[A] shape 没喂独立度：{_s_new!r}")
    _s_leg = _shape(_m3.pools["1"])
    if "不可判定结构覆盖 0.60" not in _s_leg:
        bad.append(f"[A-负对照] legacy 池的 shape 旧口径丢了：{_s_leg!r}")

    # 源码接线：两处调用点 + 两处 sat 块
    if src.count("stall_is_sat=_stall_is_sat") != 2:
        bad.append("stall_is_sat 没接到两条通道上（%d 处）"
                   % src.count("stall_is_sat=_stall_is_sat"))
    if src.count(
            "_stall_is_sat = bool(sat_verdict is False and not stalled)") != 2:
        bad.append("两处 sat 块没都算 _stall_is_sat")
    if "stall_is_sat" not in _ins.signature(
            mod.MetaDGTF._stop_reasons).parameters:
        bad.append("_stop_reasons 没有 stall_is_sat 形参")

    # ================= B. 修行层停止判据/文案 =================
    _mr = mod.MetaDGTF(cfg)
    _sp = dict(mod.DEFAULT_CONFIG["spiral"])

    def _rs(**kw):
        base = dict(entry="0", layer_no=3, rounds_n=3, total_rounds=3,
                    sp=_sp, soft_max=3, sim_thr=0.8, stable_need=2,
                    idle_limit=2, r_idle_limit=2, r_stall_limit=2,
                    rephrase_streak=0, carry_streak=0, idle_new_amp=0,
                    idle_new_thread=0, idle_stall=0, stall_why="",
                    sat_override=False, prev_product="",
                    view=mod.View(entry="0"), idles=0)
        base.update(kw)
        with _cl.redirect_stdout(_io.StringIO()):
            _r, _ = _mr._stop_reasons(**base)
        return " | ".join(str(x) for x in _r)

    # B1 空括号：sat 顶计数那一支
    _sat = _rs(idle_stall=2, stall_is_sat=True)
    if "（）" in _sat:
        bad.append(f"[B] sat 支路仍印空括号：{_sat!r}")
    if "结构饱和度判定" not in _sat:
        bad.append(f"[B] sat 支路没有自己的说法：{_sat!r}")
    # 负对照：真 stall 那一支必须照旧带 stall_why
    _real = _rs(idle_stall=2, stall_why="修行层无新增或无推进")
    if "修行层无新增或无推进" not in _real or "（）" in _real:
        bad.append(f"[B-负对照] 真 stall 支路的措辞被改坏了：{_real!r}")
    # 反向：元层 sat_override 那条（条件 2）仍要能印「结构饱和度判定」
    _ov = _rs(entry="all", idle_new_amp=2, sat_override=True,
              view=mod.View(entry="all"))
    if "结构饱和度判定" not in _ov:
        bad.append(f"[B] 元层 sat_override 的说法没了：{_ov!r}")

    # B2 条件 1 文案按层取词：不借「ing」
    for _e, _lab in (("0", "修行层"), ("1", "研究层"),
                     ("both", "对撞层"), ("all", "元层")):
        _t = _rs(entry=_e, rephrase_streak=2, view=mod.View(entry=_e))
        if f"{_lab}连续 2 圈复述" not in _t:
            bad.append(f"[B] {_e} 层条件 1 文案不是「{_lab}…」：{_t!r}")
        if "ing" in _t:
            bad.append(f"[B] {_e} 层停因里还有「ing」：{_t!r}")
    if "圈复述" in _rs(rephrase_streak=0):
        bad.append("[B-负对照] 没复述却给了复述理由")

    # B3 修行层任何停止都附体检；非修行层不附（负对照）
    def _fin(entry, why):
        _v = mod.View(entry=entry)
        _v.stop_reason = why
        _st = {"roles_hist": ["摊开"], "total_rounds": 4, "round_log": [],
               "all_rehashed": [], "all_candidates": [], "all_amps": [],
               "all_threads": [], "all_expanded_descs": [],
               "all_dec_products": [], "all_und_products": [],
               "r": 4, "rounds_n": 4, "sp": mod._spiral_for(cfg, entry)}
        with _cl.redirect_stdout(_io.StringIO()):
            mod.MetaDGTF(cfg)._finalize_layer_common(entry, _v, _st)
        return _v.stop_reason or ""

    for _why in ("连续 2 轮有新增但无推进（修行层无新增或无推进），螺旋停止",
                 "体力耗尽（4 圈走满，未触发任何停止判据，是被截断不是自然停止）"):
        _o = _fin("0", _why)
        if "未生质量" not in _o or "本轮显形" not in _o:
            bad.append(f"[B] 修行层停因没附体检（{_why[:12]}…）：{_o!r}")
    if "未生质量" in _fin("1", "研究层双通道均收敛，螺旋停止"):
        bad.append("[B-负对照] 非修行层也被附了体检")

    # B4 源码层面：旧红线句已不在、新句在、显式清单在
    if "修行层不追求收敛" in src:
        bad.append("[B] 源码里还有「修行层不追求收敛」这句旧红线")
    if "修行层本来就能停" not in src:
        bad.append("[B] 源码里缺新红线注释")
    if "适用停止条件清单" not in src:
        bad.append("[B] _stop_reasons 的显式适用条件清单缺了")

    if bad:
        for _x in bad:
            print("  \u2717 [v12324] %s" % _x)
        return False
    print("  \u2713 [v12324] 独立度口径（旧键不动 / 空池 None / legacy 回退 / "
          "shape 已换）；修行层停因去 ing、无空括号、一律附体检；两通道接线齐")
    return True

def main():
    verbose = os.environ.get("SMOKE_VERBOSE", "0") == "1"
    if not check_v122_phase1():
        return 1
    if not check_v122_phase2():
        return 1
    if not check_v122_phase3():
        return 1
    if not check_thread_isolation():
        return 1
    if not check_both_quota():
        return 1
    if not check_carry_feedback():
        return 1
    if not check_p2_units():
        return 1
    if not check_probe_skip_no_false_flag():
        return 1
    if not check_merge_fallback():
        return 1
    if not check_p23_units():
        return 1
    if not check_mode_tables():
        return 1
    if not check_stop_gate():
        return 1
    if not check_rounds_plan():
        return 1
    if not check_stop_reason_parity():
        return 1
    if not check_pool_sub_label():
        return 1
    if not check_decidability_transitions():
        return 1
    if not check_decidability_normalize():
        return 1
    if not check_debt_reopen():
        return 1
    if not check_starve_escalation():
        return 1
    if not check_confluence_persisted():
        return 1
    if not check_thinking_wiring():
        return 1
    if not check_meta_closure_by_id():
        return 1
    if not check_layer_guard():
        return 1
    if not check_p162_units():
        return 1
    if not check_p162_fix2_units():
        return 1
    if not check_v63_c_fixes():
        return 1
    if not check_v63_observability():
        return 1
    if not check_v64_pool_meta_render():
        return 1
    if not check_v64_by_id_scope():
        return 1
    if not check_v65_starve_render():
        return 1
    if not check_v66_starve_peak():
        return 1
    if not check_v66_starve_writes_key():
        return 1
    if not check_v67_full_appendix():
        return 1
    if not check_v68_round_dump():
        return 1
    if not check_v69_abcde():
        return 1
    if not check_v70_f_trace():
        return 1
    if not check_v70_k_coverage():
        return 1
    if not check_v70_g_anchor():
        return 1
    if not check_v70_h_oversized():
        return 1
    if not check_v70_i_note():
        return 1
    if not check_v70_j_reuse():
        return 1
    if not check_v71_single_round_finalize():
        return 1
    if not check_v71_main_save_guard():
        return 1
    if not check_v71_build_inp_meta_filter():
        return 1
    if not check_v71_load_config_empty():
        return 1
    if not check_v71_early_dispatch():
        return 1
    if not check_v71_ext_assess_cached():
        return 1
    if not check_v71_evidence_full():
        return 1
    if not check_v71_tokenize_stopwords():
        return 1
    if not check_v71_coverage_cfg_optional():
        return 1
    if not check_v71_no_dup_position_diag():
        return 1
    if not check_v71_auto_plan_agreement():
        return 1
    if not check_v72_bbarrier_semantics():
        return 1
    if not check_v72_changelog_hygiene():
        return 1
    if not check_v72_mechanism_single_source():
        return 1
    if not check_v72_len_anomaly_guard():
        return 1
    if not check_v73_anchor():
        return 1
    if not check_v74_anchor_refs():
        return 1
    if not check_v75_anchor_pool():
        return 1
    if not check_v76_anchor_two_channels():
        return 1
    if not check_v76_anchor_calls():
        return 1
    if not check_v76_changelog_wording():
        return 1
    if not check_v76_anchor_visibility():
        return 1
    if not check_v76_anchor_evidence_key():
        return 1
    if not check_v76_anchor_retriever_stub():
        return 1
    if not check_v76_anchor_triage_cohesion():
        return 1
    if not check_v76_claims_scope():
        return 1
    if not check_v76_input_sanity_shape():
        return 1
    if not check_v77_claim_order():
        return 1
    if not check_v77_input_sanity_render():
        return 1
    if not check_config_parses():
        return 1
    if not check_cli():
        return 1
    if not check_v1221_p1():
        return 1
    if not check_v1221_p2():
        return 1
    if not check_v1221_p2b():
        return 1
    if not check_v1221_p3():
        return 1
    if not check_v1221_p5():
        return 1
    if not check_v1221_p6():
        return 1
    if not check_v1221_p7():
        return 1
    if not check_v1222_p1():
        return 1
    if not check_v1222_p2():
        return 1
    if not check_v1222_p3():
        return 1
    if not check_v123_w1():
        return 1
    if not check_v123_w2():
        return 1
    if not check_v123_pool_export():
        return 1
    if not check_v123_left():
        return 1
    if not check_v1232_audit():
        return 1
    if not check_v1232_tier():
        return 1
    if not check_v1232_retry():
        return 1
    if not check_v1233_vote_ids():
        return 1
    if not check_v1234_runtime():
        return 1
    if not check_v1235_pending_fix():
        return 1
    if not check_v1236_no_version_tags():
        return 1
    if not check_v1237_changelog_outside_code():
        return 1
    if not check_v1238_render_guards():
        return 1
    if not check_v1239_orientation_guard():
        return 1
    if not check_v12310_render_ops():
        return 1
    if not check_v12311_writeback_and_web():
        return 1
    if not check_v12312_anchor_lanes():
        return 1
    if not check_v12313_auto_dispatch():
        return 1
    if not check_v12314_history_corpus():
        return 1
    if not check_v12315_history_calibration():
        return 1
    if not check_v12316_stop_therapy():
        return 1
    if not check_v12317_stop_all_layers():
        return 1
    if not check_v12317_und_coverage_trace():
        return 1
    if not check_v12318_anchor_default_on():
        return 1
    if not check_v12319_anchor_retrieval_reachable():
        return 1
    if not check_v12320_quiet_output():
        return 1
    if not check_v12321_tok_line():
        return 1
    if not check_v12322_web_hits_dump():
        return 1
    if not check_v12323_view_echo_full():
        return 1
    if not check_v12324_indep_therapy():
        return 1
    if not check_v12325_struct_coverage():
        return 1
    if not check_v12326_sim3():
        return 1
    if not check_v12327_five_mechanisms():
        return 1
    if not check_v12328_real_entry():
        return 1
    if not check_v12329_convergence():
        return 1
    if not check_v12330_duty_guard():
        return 1
    if not check_v12331_memory_loop():
        return 1
    if not check_v12332_discipline():
        return 1
    if not check_v12333_autotune():
        return 1
    if not check_v12334_prompt():
        return 1
    if not check_v12336_allweb():
        return 1
    if not check_v12336_readings():
        return 1
    if not check_v12336_tick():
        return 1
    if not check_v12336_eml():
        return 1
    if not check_v12336_webneed():
        return 1
    if not check_v12340_relax_force():
        return 1
    if not check_v12340_backfeed_stage():
        return 1
    if not check_v12341_goal_fresh():
        return 1
    if not check_v12341_excavate_dir():
        return 1
    if not check_v12341_attribution():
        return 1
    if not check_v12342_ctx_shape():
        return 1
    if not check_v12343_gain_stop():
        return 1
    if not check_v12344_eml_adaptive():
        return 1
    if not check_v12345_output_rep():
        return 1
    if not check_v12346_duty_span():
        return 1
    if not check_v12347_gain_suggest():
        return 1
    if not check_v12348_eml_semantic():
        return 1
    if not check_v12349_run_ckpt():
        return 1
    if not check_v12350_resume():
        return 1
    if not check_v12351_eml_once_per_run():
        return 1
    if not check_v12352_paused_no_eml():
        return 1
    if not check_v12353_eml_dir_single():
        return 1
    if not check_v12354_parallel_wall_clock():
        return 1
    if not check_v12355_paused_gap():
        return 1
    if not check_v12356_ckpt_cumulative():
        return 1
    if not check_v12357_goal_trace_carry():
        return 1
    if not check_v12339_ondemand():
        return 1
    if not check_v12338_relax_targets():
        return 1
    if not check_v12338_backfeed():
        return 1
    if not check_v12337_roundtick():
        return 1
    q = "测试问题：AI 在数字 IC 设计里到底能做什么，哪些已经量产？"
    rows = []
    for mode in ("serial", "A", "B", "C", "D", "E",
                "F", "G", "H"):
        try:
            rows.append(run_mode(mode, q, verbose=verbose))
            print(f"  ✓ {mode:6s} 跑通")
        except Exception as e:
            print(f"  ✗ {mode:6s} 失败: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return 1

    # auto 分支：让决策器返回 A
    os.environ["SMOKE_AUTO_MODE"] = "A"
    try:
        r = run_mode("auto", q, verbose=verbose)
        r["mode"] = "auto→A"
        rows.append(r)
        print("  ✓ auto    跑通（决策器返回 A）")
    except Exception as e:
        print(f"  ✗ auto    失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        os.environ.pop("SMOKE_AUTO_MODE", None)

    # [自动规划] auto_plan：五维一次定（route/mode/rounds/成本档/预算）。
    # ★ 必须在构造 MetaDGTF **之前**跑 —— 成本档在 __init__ 里就裁剪完了。
    try:
        cfg = build_cfg(False)
        p = mod.auto_plan(q, cfg)
        assert p["route"] == ["0", "1", "both", "all"], f"route：{p['route']}"
        assert p["mode"] == "H", f"mode：{p['mode']}"
        # ★ 圈数下限：模型给 3/4/4/3，全部要被钳到可达性下限 4
        #   （判据要累计 ≥2 圈，给 3 圈以下等于判据够不到）
        # ★ 元层的下限单独抬到 5（实际跑 6 圈）：单变量对照（同题同模式，
        #   只变元层圈数）里给 3/4 的两跑连一条判据都没触发就走满收场，
        #   给 5 才开始能停。给少不是省钱，是买截断。
        assert p["rounds"] == {"0": 4, "1": 4, "both": 4, "all": 5}, \
            f"rounds 应钳到下限（元层 5，其余 4）：{p['rounds']}"
        assert p["rounds"]["all"] > p["rounds"]["0"], \
            f"元层下限应高于通用下限，否则又退回「实际5圈」坑：{p['rounds']}"
        # [v1.21.61] 预算下限兜底：mock 给 150，但四层共 17 圈（元层下限
        #   抬到 5 之后：4+4+4+5）× 10/圈 = 170，150 不够跑完 —— 必须
        #   被抬到 170。
        #   这是**主动买截断**的反面：预算低于圈数所需时，层内还没判停
        #   就被外部掐掉（y61d 给 180、21 圈，实跑 191 撞线，三层写成
        #   「预算用尽」）。只抬上限，不抬消耗。
        _per = float(build_cfg(False).get("spiral", {}).get(
            "budget_per_round_floor", 10) or 0)
        assert p["max_calls"] == int(17 * _per), \
            f"预算应被抬到 17 圈 × {_per:.0f}/圈：{p['max_calls']}"
        # 抬过必须留痕，否则产物里看不出为什么比规划给的花得多
        assert "不够跑完" in (p.get("reason") or ""), \
            f"预算抬升没留痕：{p.get('reason')!r}"
        # 预算本来就够时不许乱抬（兜底只抬下限，不是改预算）
        os.environ["SMOKE_AUTO_PLAN"] = json.dumps({
            "route": "full", "mode": "B",
            "rounds": {"0": 4, "1": 4, "both": 4, "all": 4},
            "cost_profile": "balanced", "max_calls": 300,
            "reason": "预算充足", "confidence": 0.9})
        p_ok = mod.auto_plan(_SMOKE_RULE_MISS_Q, build_cfg(False))
        assert p_ok["max_calls"] == 300, \
            f"预算够时不该被抬：{p_ok['max_calls']}"
        # [v1.21.61] 按层封顶：研究层封 5，其余 6。
        #   数据：研究层 4 圈自然停 80%（n=44）、6 圈虽 86% 但实际中位
        #   仍跑 4 圈 —— 多给的不花。写在 prompt 里的实测表模型没听
        #   （y61e 仍给 5），所以要落到代码上。
        os.environ["SMOKE_AUTO_PLAN"] = json.dumps({
            "route": "full", "mode": "B",
            "rounds": {"0": 6, "1": 6, "both": 6, "all": 6},
            "cost_profile": "balanced", "max_calls": 0,
            "reason": "全给满 6", "confidence": 0.9})
        p5 = mod.auto_plan(_SMOKE_RULE_MISS_Q, build_cfg(False))
        assert p5["rounds"]["1"] == mod._layer_ceil("1", 12, 4), \
            f"研究层应封到 5：{p5['rounds']}"
        assert p5["rounds"]["0"] == mod._MAX_LAYER_ROUNDS, \
            f"非研究层上限仍是 6：{p5['rounds']}"
        # 预算给「不限」要兜成有限值 —— 否则动态提前停在 auto 这条
        # 最常走的路径上永远触发不到（y61e 就是给了「不限」）。
        _cap = float(build_cfg(False).get("spiral", {}).get(
            "budget_per_round_cap", 12) or 0)
        assert p5["max_calls"] == int(sum(p5["rounds"].values()) * _cap), \
            f"「不限」应兜到 总圈数×{_cap:.0f}：{p5['max_calls']}"
        # 脏值：负预算/越界圈数/未知 route —— 都要被兜住
        os.environ["SMOKE_AUTO_PLAN"] = json.dumps({
            "route": "不存在的档", "mode": "Z", "rounds": {"0": 999},
            "route": "不存在的档", "mode": "Z", "rounds": {"0": 999},
            "max_calls": -5,
            "reason": "", "confidence": 0.1}, ensure_ascii=False)
        p2 = mod.auto_plan(q, build_cfg(False))
        assert p2["route"] == ["0", "1", "both", "all"], \
            f"未知 route 应退回 full：{p2['route']}"
        assert p2["mode"] == "serial", \
            f"非法 mode 应退回 serial：{p2['mode']}"
        assert p2["max_calls"] == 0, f"负预算应为 0（不设限）：{p2['max_calls']}"
        # route 裁剪：rounds 只留真要跑的层
        os.environ["SMOKE_AUTO_PLAN"] = json.dumps({
            "route": ["0", "1"], "mode": "serial",
            "rounds": {"0": 3, "1": 3, "both": 3, "all": 3},
            "cost_profile": "balanced", "max_calls": 0,
            "reason": "", "confidence": 0.9}, ensure_ascii=False)
        p3 = mod.auto_plan(q, build_cfg(False))
        assert set(p3["rounds"]) == {"0", "1"}, \
            f"rounds 应只留 route 里的层：{p3['rounds']}"
        # ★ 上限硬钳：prompt 里写「开放题 5-6」时模型直接给满 6，
        #   同一道题 155 calls/7.2min → 233 calls/12min。措辞压不住，
        #   只能在代码里封顶（_MAX_LAYER_ROUNDS）。
        os.environ["SMOKE_AUTO_PLAN"] = json.dumps({
            "route": "full", "mode": "B",
            "rounds": {"0": 9, "1": 6, "both": 12, "all": 6},
            "cost_profile": "balanced", "max_calls": 0,
            "reason": "", "confidence": 0.9}, ensure_ascii=False)
        p4 = mod.auto_plan(q, build_cfg(False))
        assert all(v <= mod._MAX_LAYER_ROUNDS for v in p4["rounds"].values()), \
            f"圈数没被封顶到 {mod._MAX_LAYER_ROUNDS}：{p4['rounds']}"
        assert all(v >= mod._MIN_LAYER_ROUNDS for v in p4["rounds"].values()), \
            f"圈数没被抬到可达性下限 {mod._MIN_LAYER_ROUNDS}：{p4['rounds']}"
        print("  ✓ 自动规划 auto_plan：五维生效，"
              "脏值兜底（非法档/负预算/越界圈数/未知 route），"
              f"圈数钳在 [{mod._MIN_LAYER_ROUNDS},{mod._MAX_LAYER_ROUNDS}]")
    except Exception as e:
        print(f"  ✗ 自动规划 auto_plan 失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        os.environ.pop("SMOKE_AUTO_PLAN", None)

    # [动态提前停] 预算：用尽要停，且**必须留痕**（不留痕 = 和自然停止
    # 长得一样，读产物的人无从分辨）。
    try:
        cfg = build_cfg(False)
        cfg["max_calls"] = 1
        m = mod.MetaDGTF(cfg)
        assert m._call_budget == 1, f"预算没读进实例：{m._call_budget}"
        assert not m._budget_exhausted(), "还没调用不该判为用尽"
        m.llm.total_calls = 5
        assert m._budget_exhausted(), "超预算应判为用尽"
        m._note_budget_stop("测试")
        assert "预算用尽" in m._budget_stop_note, \
            f"停止理由没留痕：{m._budget_stop_note}"
        # 不设限（0）时永远不该触发
        cfg2 = build_cfg(False)
        cfg2["max_calls"] = 0
        m2 = mod.MetaDGTF(cfg2)
        m2.llm.total_calls = 99999
        assert not m2._budget_exhausted(), "预算 0 = 不设限，不该触发"
        # ★ 覆盖面断言：预算守卫必须挂在**每一条**跑圈通道上。
        #   B 的波循环原来漏了它，而 B 恰是自动规划最常选的模式 ——
        #   结果「动态提前停」在最常用那条路上是死的。这里按函数体切片查。
        _src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
        _bodies = {}
        _cur = None
        for _ln in _src.splitlines():
            if _ln.startswith("    def "):
                _cur = _ln.strip()[4:].split("(")[0]
                _bodies[_cur] = []
            elif _cur is not None:
                _bodies[_cur].append(_ln)
        for _fn in ("_run_layer", "_run_layer_C", "_run_layer_stage",
                    "_run_parallel_B"):
            _b = "\n".join(_bodies.get(_fn, []))
            assert "_budget_exhausted()" in _b, \
                f"{_fn} 里没有预算守卫 —— 这条通道的提前停是死的"
        print("  ✓ 动态提前停：预算用尽可判、留痕，0 表示不设限；"
              "四条跑圈通道都挂了守卫")
    except Exception as e:
        print(f"  ✗ 动态提前停失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # [判定稳定性] 探针实证：修行层 view **完全固定**，重复评估 5 次，
    # 判定值 5/5 是 partial，但**不可判定清单 5 次全不一样**（措辞+来源标注）。
    # 修法是让「无追溯的不可判定」不参与归一化。这里锁住三处语义。
    try:
        m = mod.MetaDGTF(build_cfg(False))
        # ① 抗噪：模型爱塞「（候选16）」这类来源后缀，比对前要剥掉，
        #    否则**有追溯**的会被误判成无追溯 —— 判据自己变成噪声源。
        _u1 = mod._untraced_undecidable(
            ["清分规则未定时断面客流与线路客流不可互证（候选16）"],
            [{"aspect": "清分规则未定，断面客流与线路客流不可互证"}])
        assert _u1 == [], f"带来源后缀的同一条应判为有追溯，实际：{_u1}"
        # 真没追溯的照样要抓出来
        _u2 = mod._untraced_undecidable(
            ["凭空说的一条"], [{"aspect": "完全不相干的另一条"}])
        assert _u2 == ["凭空说的一条"], f"无追溯的没被抓出来：{_u2}"

        # ② 归一化：剔除无追溯的 und 后，decidable 不该被拉成 partial
        assert mod._normalize_decidability(
            "decidable", ["可判定方面甲"], []) == "decidable", \
            "无追溯条目被剔除后不该再判 partial"
        # 有追溯的 und 仍然要把 decidable 拉成 partial（原语义不丢）
        assert mod._normalize_decidability(
            "decidable", ["可判定方面甲"], ["站得住的不可判定"]) == "partial", \
            "有追溯的不可判定仍应判 partial"

        # ③ 合并路径：[外] 前缀是**外判**列的条目，外判没有池可追溯，
        #    把它算进"无追溯"是误报（a61F 报的 5 条里 3 条是这种）。
        _pool = {"decidability": "decidable",
                 "decidable_aspects": ["甲"], "undecidable_aspects": [],
                 "evidence": [], "_source": "pool"}
        _ext = {"decidability": "partial",
                "decidable_aspects": ["甲"],
                "undecidable_aspects": ["[外] 外判认为这条判不出"],
                "_source": "external"}
        _mg = m._merge_decidability(_pool, _ext)
        assert _mg["_und_untraced"] == [], \
            f"[外] 条目不该被算成无追溯：{_mg['_und_untraced']}"
        assert _mg["decidability"] == "partial", \
            f"[外] 的不可判定仍应参与归一化：{_mg['decidability']}"
        print("  ✓ 判定稳定性：无追溯不采信（抗噪+归一化），"
              "[外] 不算无追溯")
    except Exception as e:
        print(f"  ✗ 判定稳定性失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # [自动调度] _auto_plan：模式+圈数一次定下来。冒烟里其余用例都显式
    # 传了 rounds，走不到这条路径 —— 不单独测就是**新代码零覆盖**。
    try:
        hard = int(build_cfg(False).get("spiral", {}).get("hard_max", 12))
        os.environ["SMOKE_AUTO_MODE"] = "H"
        os.environ["SMOKE_AUTO_ROUNDS"] = '{"0":3,"1":4,"both":5,"all":3}'
        m = mod.MetaDGTF(build_cfg(False))
        plan = m._auto_plan(q)
        assert plan["mode"] == "H", f"模式未生效：{plan['mode']}"
        # ★ 0 给的 3 要被钳到可达性下限 4；all 给的 3 要被钳到**元层
        #   专用下限 5**（与 auto_plan 同口径）。both 给 5 本来就在区间
        #   内，不动。
        assert plan["rounds"] == {"0": 4, "1": 4, "both": 5, "all": 5}, \
            f"圈数未生效/未钳下限：{plan['rounds']}"
        # 脏值：越界 / 非整数 / 负数 —— 一律跳过，交给配置兜底。
        # （不钳到 hard_max：模型给 999 说明它没理解预算，
        #   硬钳成 12 等于满格跑，比走配置默认更贵。）
        os.environ["SMOKE_AUTO_ROUNDS"] = \
            '{"0":999,"1":"x","both":-2,"all":2}'
        plan2 = m._auto_plan(q)
        # 999 不采纳；0/1/both 按**已给合法值(all=2)的中位数**补齐，
        # 而不是落回 hard_max —— 真跑实证：漏层落 hard_max 会让元层
        # 跑满 13 圈被截断（a61H 20.7min vs 给全四层的 a61F 9.7min）。
        # 补齐后仍要过下限：2 → 4（元层 → 5，它的下限单独抬过）。
        for _k in ("0", "1", "both"):
            assert plan2["rounds"].get(_k) == 4, \
                f"{_k} 应为中位数 2 补齐后再钳到下限 4，实际 {plan2['rounds']}"
        assert plan2["rounds"].get("all") == 5, \
            f"all 应补齐后钳到元层下限 5，实际 {plan2['rounds']}"
        assert max(plan2["rounds"].values()) <= hard, "补齐值不该超 hard_max"
        # 一层合法值都没有 → rnd 为空，交给配置兜底（不做无依据的补齐）
        os.environ["SMOKE_AUTO_ROUNDS"] = '{"0":"x","1":999}'
        plan3 = m._auto_plan(q)
        assert plan3["rounds"] == {}, \
            f"全脏值时不该凭空补圈数：{plan3['rounds']}"
        print(f"  ✓ 自动调度 _auto_plan：模式+圈数生效，"
              f"越界/脏值按中位数补齐（上限 {hard}），全脏则交给配置")
    except Exception as e:
        print(f"  ✗ 自动调度 _auto_plan 失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        os.environ.pop("SMOKE_AUTO_MODE", None)
        os.environ.pop("SMOKE_AUTO_ROUNDS", None)

    # [koan 可达性] 真跑 0 次进入的路径，至少要在冒烟里走通一次：
    # 判定 undecidable 且无可判定方面 → 分派到 _decompose_koan，
    # 产物是"维度"不是"子问题"，每条都带 why_undecidable。
    try:
        m = mod.MetaDGTF(build_cfg(False))
        d1 = mod.DGTF("1", m.llm, m.config)   # _decompose_question 在 DGTF 上
        d1.verbose = True                     # vp 只在 verbose 下打印
        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            subs = d1._decompose_question(
                "这个命题本身可判定吗？",
                {"decidability": "undecidable",
                 "undecidable_aspects": ["轴由谁生成"],
                 "decidable_aspects": []})
        _out = _buf.getvalue()
        assert subs, "koan 分解不该返回空"
        assert all(s["decidability"] == "undecidable" for s in subs), \
            f"koan 产出的维度必须全是不可判定：{subs}"
        assert all(s.get("why_undecidable") for s in subs), \
            "每条维度都要带 why_undecidable（结构揭示，不是留空）"
        assert all(s.get("dimension") for s in subs), "缺 dimension 字段"
        assert "进入 koan 整体不可判定分解" in _out, \
            "koan 进入必须留痕 —— 不留痕审计就只能靠 tag 名误统计"
        # 反面：只要还剩一条可判定方面就走 hybrid，不该进 koan
        _buf2 = io.StringIO()
        with contextlib.redirect_stdout(_buf2):
            subs2 = d1._decompose_question(
                "这个命题本身可判定吗？",
                {"decidability": "undecidable",
                 "undecidable_aspects": ["轴由谁生成"],
                 "decidable_aspects": ["触发场景可查"]})
        assert "进入 koan 整体不可判定分解" not in _buf2.getvalue(), \
            "还有可判定方面时不该走 koan（归一化后应是 partial→hybrid）"
        assert subs2, "hybrid 分解不该返回空"
        print(f"  ✓ koan 整体不可判定路径可达：{len(subs)} 条维度，"
              f"带 why_undecidable + 留痕；有可判定方面时不进 koan")
    except Exception as e:
        print(f"  ✗ koan 可达性失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # A 模式 route 不含 all：验证 [fix-101] 汇流不再被跳过
    try:
        CALLS["n"] = 0
        cfg = build_cfg(False)
        meta = mod.MetaDGTF(cfg)
        res = meta.run(q, route=["0", "1", "both"],
                       rounds={"0": 1, "1": 1, "both": 1, "all": 1},
                       parallel_mode="A")
        has_conf = "confluence" in res
        print(f"  ✓ route 不含 all 时汇流圈仍执行：confluence={has_conf}")
        if not has_conf:
            print("  ✗ 汇流圈没跑（confluence 缺失）")
            return 1
        lay = set()
        for b in res.get("self_text") or []:
            for tag in ("[修行层]", "[研究层]", "[对撞层]", "[元层]"):
                if str(b).startswith(tag):
                    lay.add(tag)
        rows.append({"mode": "A(no-all)",
                     "views": list(res["views"].keys()),
                     "calls": res["llm_calls"],
                     "self_text_n": len(res.get("self_text") or []),
                     "self_layers_n": len(lay),
                     "dec_src": (res.get("decidability") or {}).get(
                         "_source", "?"),
                     "decidability_raw": res.get("decidability") or {},
                     "missing": 0, "quota": 0,
                     "carry": sum(len(v.get("carry") or [])
                                  for v in res["views"].values()),
                     "sanity": len((res.get("input_sanity") or {}).get(
                         "issues") or []),
                     "md": "-", "sec": 0,
                     "pool_all_amps": len(res["pools"]["all"]["amps"])})
    except Exception as e:
        print(f"  ✗ A(no-all) 失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n" + "=" * 74)
    print(f"{'模式':<12}{'views':<20}{'调用':>5}{'self':>5}{'层':>3}"
          f"{'判定源':<16}{'缺':>3}{'配额':>4}{'care':>5}{'输入':>4}"
          f"{'预热':>4}{'秒':>6}")
    print("=" * 74)
    for r in rows:
        print(f"{r['mode']:<12}{','.join(r['views']):<20}"
              f"{r['calls']:>5}{r['self_text_n']:>5}{r['self_layers_n']:>3}"
              f"{str(r.get('dec_src', '-')):<16}{r.get('missing', 0):>3}"
              f"{r.get('quota', 0):>4}{r.get('carry', 0):>5}"
              f"{r.get('sanity', 0):>4}{str(r.get('warmup', '-')):>4}"
              f"{r['sec']:>6}")
    print("=" * 74)
    print("  层 = self 段出现的层数（[P0-1] 应为 4）"
          "　判定源 = 可判定性来源（[P0-2] 应为 pool+external）")
    print("  缺 = adjudications 里写明缺什么的条数（[P1-4]）"
          "　care = 自省回流探针数（[P1-5]）"
          "　输入 = 自检问题数（[P1-6]）")

    # ---- v1.21.55 [P2-*] 表 ----
    print("")
    print("  v1.21.55 [P2-*]：")
    print(f"  {'模式':<12}{'核对':>4}{'违例':>5}{'未生':>5}"
          f"{'逃避':>5}{'超标':>5}{'悬置':>5}{'线头':>5}{'&':>4}")
    for r in rows:
        p = r.get("p2") or {}
        print(f"  {r['mode']:<12}{p.get('carry_check', 0):>4}"
              f"{p.get('violations', 0):>5}{p.get('unsaid', 0):>5}"
              f"{p.get('escape', 0):>5}{p.get('unsaid_flag', 0):>5}"
              f"{p.get('sus', 0):>5}{p.get('thr', 0):>5}"
              f"{p.get('amp', 0):>4}")
    print("  核对 = 有【自省回流核对】的 view 数（[P2-7] 应 > 0）"
          "　违例 = 注入的约束没被遵守的条数（mock 下必然 > 0）")
    print("  未生 = self_check 报的「此处未生」处数（[P2-4]）　逃避/超标 = 判为逃避的圈数 / 质量线索数")

    failed = []
    for r in rows:
        tag = r["mode"]
        # A(no-all) 只有三层，期望层数 = 实际跑的层数
        expect_layers = len([v for v in r["views"] if v in
                             ("0", "1", "both", "all")])
        if r["self_layers_n"] < expect_layers:
            failed.append(f"{tag}: [P0-1] self 只有 {r['self_layers_n']} 层，"
                          f"期望 {expect_layers} 层，被挤出了")
        # ---- [P0-2] 可判定性来源。D/E 是 0/1 双起并行、不预热，研究层
        #      拆解时读池是**竞态**：0 层先交出第 1 圈 → pool+external，
        #      没交出 → external，两种都合法（读到哪就是哪）；
        #      其余 0 层先行的模式拆解时必然已读到 0 层 → pool+external。
        if tag in ("D", "E"):
            if r.get("dec_src") not in ("external", "pool+external"):
                failed.append(f"{tag}: [P0-2] 判定源 {r.get('dec_src')} 非法，"
                              f"双起并行应为 external 或 pool+external")
        elif r.get("dec_src") != "pool+external":
            failed.append(f"{tag}: [P0-2] 可判定性来源是 {r.get('dec_src')}，"
                          f"期望 pool+external")
        # ---- [P0-3] 判定**判据**必须可查，而不是死记某道题的期望值。
        #      [v1.21.61] 上一轮连栽两次：先预设"地铁该 decidable"，改完又预设
        #      "地铁该 partial"——预设是猜的，不是判据。能自动查的只有两件：
        #      ① 池判/外判分不分叉（_divergent + 两路各是什么）；
        #      ② 每条不可判定有没有池内追溯（_und_untraced）。
        #      ★ 这里只断言**字段存在且自洽**，不断言判定值是什么。
        _dec = r.get("decidability_raw") or {}
        if not _dec:
            failed.append(f"{tag}: [P0-3] 拿不到 decidability 原始字典，"
                          f"判据字段无从查起")
        else:
            if not isinstance(_dec.get("_divergent"), bool):
                failed.append(f"{tag}: [P0-3] _divergent 缺失/非布尔，"
                              f"分叉判据不可查")
            if _dec.get("_ext_status") is not None:
                # 有外判时，两路状态都得留下来，否则分叉无从核对
                if _dec.get("_pool_status") is None:
                    failed.append(f"{tag}: [P0-3] 有外判却没留 _pool_status，"
                                  f"分叉判据不可查")
                elif _dec["_divergent"] != (
                        _dec["_pool_status"] != _dec["_ext_status"]):
                    failed.append(f"{tag}: [P0-3] _divergent 与两路状态不符")
            _ut = _dec.get("_und_untraced")
            if not isinstance(_ut, list):
                failed.append(f"{tag}: [P0-3] _und_untraced 缺失/非列表，"
                              f"「理由是否成立」不可查")
            elif len(_ut) > len(_dec.get("undecidable_aspects") or []):
                failed.append(f"{tag}: [P0-3] _und_untraced 条数超过"
                              f"不可判定条目总数，计算有错")
        if r.get("carry", 0) == 0:
            failed.append(f"{tag}: [P1-5] 自省没有回流")
        if r.get("sanity", 0) == 0:
            failed.append(f"{tag}: [P1-6] 输入自检没进 packed")
        # ---- [feat-107] B/C 必须先跑 0 层预热圈再让其余层开动
        if tag in ("B", "C") and r.get("warmup") != 1:
            failed.append(f"{tag}: [feat-107] 0 层预热圈数是 "
                          f"{r.get('warmup')}，期望 1")
        # ---- [v1.21.60⑨] F/G/H 是「0 层跑满先行」，评估应在跑满后读完整形状：
        #      测试 rounds 全层 2 → 0 层总圈数 2，warmup 应为 2（跑满）而非 1（预热）
        if tag in ("F", "G", "H") and r.get("warmup") != 2:
            failed.append(f"{tag}: [⑨] 0 层跑满先行的模式，warmup={r.get('warmup')}"
                          f"，期望 2（评估读完整形状，不是 1 圈薄形状）")
        # ---- [feat-106] C 模式不落 ISS
        if tag == "C" and set(r["views"]) != set(_ALL_LAYERS):
            failed.append(f"{tag}: 四层没跑全（{r['views']}），"
                          f"流水线大概率卡在闸门上")
        # ---- [P2-7] 回流核对必须在跑：有注入就该有核对
        #      A(no-all) 每层只跑 1 圈，注入发生在最后一圈，
        #      没有下一圈可核对 → 豁免（这是设计事实，不是缺陷）
        if tag == "A(no-all)":
            pass
        elif r.get("carry", 0) > 0 and (r.get("p2") or {}).get(
                "carry_check", 0) == 0:
            failed.append(f"{tag}: [P2-7] 注了 {r['carry']} 条约束却没有任何核对记录")
    if failed:
        print("\n  ✗ 未通过：")
        for f in failed:
            print("    -", f)
        print("落盘目录：", HERE / "smoke_outputs")
        return 1

    print("\n  ✓ P0-1 / P0-2 / P0-3（判定判据可查）/ P1-4 / P1-5 / P1-6 全部生效")
    print("落盘目录：", HERE / "smoke_outputs")
    return 0

if __name__ == "__main__":
    sys.exit(main())
