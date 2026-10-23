# -*- coding: utf-8 -*-
"""
长期任务 2 收尾：`♻` 与 `☯` 两个零触发机制的**可达性负对照**。

背景（v1.21.75 扫描，244 份真跑日志）：这两个标记**一次都没打出来过**。
「零触发」有三种解释，分不开就不能下结论：
  ① 条件不可达 → 真该死
  ② 条件窄但在特定情形成立 → 留着
  ③ 机制压根没工作 → 重写

判据是**负对照**：喂一个该触发的输入，看它触不触发。

  ♻  `_phase_probe` 里的「至少碰一个」重试：
     条件 = 该圈 engagements/suspensions/probes **三者全空** 且 非最后一圈
  ☯  `_decompose_question` 走 koan 分支：
     条件 = **归一化后** status == "undecidable"（即模型给出 undecidable
     标签 **且** decidable_aspects 为空 —— 只要有可判定方面，
     `_normalize_decidability` 就会把它降成 partial，走 hybrid）

本探针用 mock 的 LLM 走**生产入口**（不连网、不花钱）。
"""
import importlib.util
import io
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.77.py"


def load_dotenv(p: Path) -> None:
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    load_dotenv(HERE / ".env")
    spec = importlib.util.spec_from_file_location("d77c", str(SRC))
    m = importlib.util.module_from_spec(spec)
    sys.modules["d77c"] = m
    spec.loader.exec_module(m)

    cfg = m.load_config(str(HERE / "dgtf_config.yaml"))
    out_lines = []

    def mk(entry="1"):
        o = object.__new__(m.DGTF)
        o.entry = entry
        o.config = cfg
        o.verbose = True
        o.vp = lambda s="": out_lines.append(str(s))
        o._self_block = lambda: ""
        return o

    ok = True

    # ---------------- ☯ 负对照：全判不出的输入 ----------------
    print("=== ☯ 负对照：归一化后仍 undecidable（应进 koan）===")
    out_lines.clear()
    d = mk("1")
    d.llm = m.LLM(cfg)
    seen = {"called": False}

    def fake_call(system, user, *a, **k):
        seen["called"] = True
        return '{"dimensions": [{"id": 1, "dimension": "X", ' \
               '"why_undecidable": "Y", "what_can_probe": "Z"}]}'

    d.llm.call = fake_call
    r = d._decompose_question("某自指难题", {
        "decidability": "undecidable",
        "decidable_aspects": [],
        "undecidable_aspects": ["自指循环", "无共同参照系"]})
    hit = any("☯" in x for x in out_lines)
    print(f"  走了 koan 分支 : {hit}")
    print(f"  调了 LLM       : {seen['called']}")
    print(f"  返回子问题数   : {len(r or [])}")
    if not hit:
        print("  ✗ 喂了「全判不出」都没进 koan —— 该路径不可达")
        ok = False
    else:
        print("  ✓ 可达：条件成立时确实进 koan（机制有效，只是条件罕见）")

    # 正对照：有可判定方面时**不该**进 koan（应走 hybrid）
    print("\n=== ☯ 正对照：有可判定方面（应走 hybrid，不进 koan）===")
    out_lines.clear()
    d2 = mk("1")
    d2.llm = m.LLM(cfg)
    d2.llm.call = lambda system, user, *a, **k: \
        '{"sub_questions": [{"question": "q1", "decidability": "decidable"}]}'
    d2._decompose_question("混合问题", {
        "decidability": "undecidable",
        "decidable_aspects": ["这条能查"],
        "undecidable_aspects": ["这条判不出"]})
    hit2 = any("☯" in x for x in out_lines)
    print(f"  进了 koan（不该）: {hit2}")
    if hit2:
        print("  ✗ 有可判定方面也进 koan —— 归一化没挡住")
        ok = False
    else:
        print("  ✓ 归一化把它降成 partial，走了 hybrid")

    # ---------------- ♻ 负对照：一圈什么都没碰 ----------------
    print("\n=== ♻ 负对照：engagements/suspensions/probes 全空 + 非最后一圈 ===")
    out_lines.clear()
    # ★ 用**真实构造**的 DGTF（手写桩会一路缺属性：phase / _self_block …）。
    cfg0 = dict(cfg)
    cfg0["actions"] = dict(cfg0.get("actions") or {})
    cfg0["actions"]["probe_research"] = True
    d3 = m.DGTF("0", m.LLM(cfg0), cfg0)
    d3.verbose = True
    d3.vp = lambda s="": out_lines.append(str(s))
    calls = {"n": 0}

    def fake2(system, user, *a, **k):
        calls["n"] += 1
        return "{}"          # 空 JSON → probes/threads/engagements 全空

    d3.llm.call = fake2

    # ★ 用真实的 View dataclass（手写桩漏字段 → 一路 AttributeError：
    #   实测连补两轮仍缺 reconfirmations / upstream_untouched）。
    v = m.View(entry="0")
    # _phase_probe 有一道提前返回：residue/target_text/active_susp 全空就直接
    # `return []`，到不了重试逻辑。所以给一条 residue。
    v.amps = [{"desc": "自动化产线的固定成本在淡季无法按比例收缩"}]
    pool = m.Pool()
    # ★ 用**真实的 Input dataclass**，不手写桩 —— 手写桩漏字段会一路 AttributeError
    #   （实测连补两轮仍缺 upstream_untouched）。
    inp = m.Input(question="测试", is_last_round=False, pool=pool,
                  round_no=1, round_role="")
    try:
        with redirect_stdout(io.StringIO()):
            d3._phase_probe(v, inp, pool)
        hit3 = any("♻" in x for x in out_lines)
        print(f"  LLM 调用次数   : {calls['n']}（=2 说明重试发生了）")
        print(f"  打了 ♻ 标记     : {hit3}")
        if not hit3:
            print("  ✗ 一圈什么都没碰也没重试 —— 该路径不可达")
            ok = False
        else:
            print("  ✓ 可达：条件成立时确实重试（机制有效）")
    except Exception as e:
        print(f"  ⚠ 探针没跑通（{type(e).__name__}: {e}）—— 不算可达，也不算不可达")
        print("    需要手工确认 `_phase_probe` 的依赖；本项记为「未证」")
        ok = False

    print("\n=== 判定 ===")
    if ok:
        print("  ✓ 两个机制都**可达**，只是真跑里条件罕见 → 处置：保留（不是砍）")
    else:
        print("  ✗ 有机制不可达或未证 —— 见上")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
