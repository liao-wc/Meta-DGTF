# -*- coding: utf-8 -*-
"""成本归因判据：每个 LLM 调用都必须能被 `llm_by_stage` 归因。

为什么需要这一组
----------------
改造前实测（一跑 HTTP431）：`llm_by_stage` 里 `unknown` 36 calls / 395,942 tokens /
243,112 ms —— 占该跑 **55% tokens、57% calls、绝大多数墙钟**，却无法指认是哪个环节。
成本看不见就没法优化，任何「省钱」结论都只能靠猜。

判据分三层（缺一层都会假绿）：
  1. **覆盖（一类判据）**：最新引擎里所有 `*.llm.call(...)` 必须带 `stage=`
     —— 锚在 AST 而不是源码字面量，未来任何新增调用点漏标都会被抓住。
  2. **行为不变（构造性证明）**：与上一版逐调用对比，**除 stage 外的参数逐字相同**、
     调用点数量相同 ⇒ 证明「只加标签，不改调用」。
  3. **落桶正确**：新 stage 必须归 `ops`（归进 eval 会把自测量虚高，
     把任务成本说小 —— 与「宁少算自测量」的约定相反）。

另有负对照：把坏样本喂给第 1 层判据，必须判红 —— 否则「全绿」只说明判据没牙。
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

V2 = pathlib.Path(__file__).resolve().parent
ENG = V2 / "engine"
sys.path.insert(0, str(V2.parent))

PASS, FAIL = [], []

#: 本改造引入的具名 stage（与 patch 一致；改这里必须同步改引擎）
EXPECTED_STAGES = {
    "expand_pair",
    "expand_pair_merged",
    "expand_pair_merged_fixup",
    "he_amps",
}

#: ★ 改造前的最后一个版本 —— 负对照的**固定基座**。
#:   不能用「上一版」：这个判据要证明的是「改造前确实有盲区」，
#:   而「上一版」会随着后续每一次改版向前滚动，滚到改造后就把判据测没了
#:   （实测踩过：V2.2.6 那轮「上一版」已是修好的 V2.2.5，负对照假红）。
#:   旧版按项目约定只读保留，不会消失；真消失了应当由人决定，判 FAIL 而不是静默跳过。
BASELINE_BEFORE_FIX = "Meta-DGTF-V2.2.4.py"


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("  OK  " if ok else "  FAIL") + " " + name +
          (("  — " + str(detail)) if detail else ""))


def _engine_files():
    """按文件名里的版本号排序（版本从文件名推导，不写死在判据里）。"""
    out = []
    for p in ENG.glob("Meta-DGTF-V*.py"):
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
        if m:
            out.append((tuple(int(x) for x in m.groups()), p))
    return sorted(out)


def _llm_calls(tree):
    """抽取所有 `*.llm.call(...)` 调用，返回 [(lineno, func_name, args_src, kwargs)]。

    args_src：位置参数的源码串（逐字比较用）；kwargs：关键字名集合
    （带 `stage` 的关键字**不进**集合 —— 那是本改造唯一允许的差异）。
    """
    funcs = []          # (name, depth) —— 用于定位调用点所属函数

    class V(ast.NodeVisitor):
        def __init__(self):
            self.stack = []
            self.out = []

        def visit_FunctionDef(self, node):
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            self.stack.append("<cls:" + node.name + ">")
            self.generic_visit(node)
            self.stack.pop()

        def visit_Call(self, node):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == "call":
                base = getattr(f.value, "attr", getattr(f.value, "id", ""))
                if base in ("llm", "client", "LLM"):
                    args_src = []
                    for a in node.args:
                        try:
                            args_src.append(ast.unparse(a))
                        except Exception:
                            args_src.append("<unparse-fail>")
                    kwargs = {k.arg for k in node.keywords if k.arg}
                    stage_vals = [ast.unparse(k.value) for k in node.keywords
                                  if k.arg == "stage"]
                    self.out.append({
                        "line": node.lineno,
                        "func": self.stack[-1] if self.stack else "<module>",
                        "args": args_src,
                        "kwargs": tuple(sorted(kwargs - {"stage"})),
                        "stage": stage_vals[0] if stage_vals else None,
                    })
            self.generic_visit(node)

    v = V()
    v.visit(tree)
    return v.out


def _missing_stage(src):
    """静态判据本体（可被负对照直接调用）。返回缺 stage 的调用点列表。"""
    tree = ast.parse(src)
    return [c for c in _llm_calls(tree) if not c["stage"]]


def main():
    files = _engine_files()
    check("找到引擎版本文件", len(files) >= 1, [p.name for _, p in files])
    if not files:
        print("\nPASS %d / FAIL %d" % (len(PASS), len(FAIL)))
        return 1

    _, latest = files[-1]
    src_latest = latest.read_text(encoding="utf-8")
    print("  最新引擎：%s" % latest.name)

    # ── 1. 覆盖率（一类判据）─────────────────────────────────
    missing = _missing_stage(src_latest)
    check("★ 所有 llm.call 都带 stage（未知成本不再产生）",
          not missing,
          "缺 %d 处：%s" % (len(missing),
                           [(c["line"], c["func"]) for c in missing][:6]))

    calls = _llm_calls(ast.parse(src_latest))
    check("调用点数量合理（>0）", len(calls) > 0, len(calls))

    # ── 3. 落桶正确 ────────────────────────────────────────
    from dgtf_v2 import fine_check as _fc  # noqa: F401  （确认包可导入）
    buckets = {}
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_eng_latest", latest)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_eng_latest"] = mod
        spec.loader.exec_module(mod)
        for st in EXPECTED_STAGES:
            buckets[st] = mod.cost_bucket(st)
    except Exception as e:  # 引擎是重模块；导入失败要说清楚，不能让判据静默变绿
        check("引擎可导入以核对 cost_bucket", False, "%s: %s" % (type(e).__name__, e))
    else:
        check("引擎可导入以核对 cost_bucket", True)
        check("★ 新 stage 归 ops（不算自测量）",
              all(v == "ops" for v in buckets.values()), buckets)

    # ── 2. 行为不变（构造性证明）─────────────────────────────
    if len(files) < 2:
        check("有上一版可比对", False, "只有一个版本文件")
    else:
        _, prev = files[-2]
        prev_calls = _llm_calls(ast.parse(prev.read_text(encoding="utf-8")))
        check("与上一版调用点数相同（没增删调用）",
              len(prev_calls) == len(calls),
              "%s vs %s" % (len(prev_calls), len(calls)))

        def sig(c):
            return (c["func"], tuple(c["args"]), c["kwargs"])

        prev_sigs = sorted(sig(c) for c in prev_calls)
        curr_sigs = sorted(sig(c) for c in calls)
        check("★ 除 stage 外参数逐字相同（只加标签不改调用）",
              prev_sigs == curr_sigs,
              "" if prev_sigs == curr_sigs else "调用签名集合不一致")

        # ★ 这一条同样锚在**改造前基座**而不是上一版：
        #   它要证明的是「当初漏标的那些点现在都补上了」。
        #   用上一版会把判据滑到「本轮有没有新增漏标」，改版几次后就测空了。
        _base = ENG / BASELINE_BEFORE_FIX
        if _base.exists():
            base_calls = _llm_calls(ast.parse(_base.read_text(encoding="utf-8")))
            base_missing = {sig(c) for c in base_calls if not c["stage"]}
            now_filled = {sig(c) for c in calls
                          if c["stage"] and sig(c) in base_missing}
            check("原先未标记的调用点已全部补标",
                  bool(base_missing) and base_missing <= now_filled,
                  "基座缺 %d、未补 %d" % (len(base_missing),
                                          len(base_missing - now_filled)))
        else:
            check("原先未标记的调用点已全部补标", False,
                  "基座 %s 不存在" % BASELINE_BEFORE_FIX)

    # ── 4. 新 stage 名真的落在引擎里（不是只在测试里）────────
    for st in sorted(EXPECTED_STAGES):
        check("stage %r 出现在引擎源码" % st,
              ('"%s"' % st) in src_latest)

    # ── 负对照：判据必须能被坏样本触发 ───────────────────────
    bad = 'def f(self):\n    return self.llm.call(a, b, 0.3, 100)\n'
    check("★ 负对照：漏标样本被判红（判据有牙）",
          len(_missing_stage(bad)) == 1,
          _missing_stage(bad))

    # ★ 更强的负对照：用**改造前的真版本**当坏样本。
    #   只喂人造样本，可能只证明「字符串匹配能跑」；喂真版本才证明
    #   这条判据在真实代码上确实会红（改造前正是 4 处漏标）。
    base = ENG / BASELINE_BEFORE_FIX
    if base.exists():
        base_missing = len(_missing_stage(base.read_text(encoding="utf-8")))
        check("★ 负对照：改造前真代码被判红（判据在真实改动上有牙）",
              base_missing > 0,
              "%s 缺 %d 处" % (base.name, base_missing))
    else:
        check("★ 负对照：改造前真代码被判红（判据在真实改动上有牙）",
              False, "基座 %s 不存在 —— 旧版不应被删，请人工确认" % BASELINE_BEFORE_FIX)

    print("\nPASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print("  - " + f)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
