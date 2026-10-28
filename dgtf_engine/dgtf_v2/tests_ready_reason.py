# -*- coding: utf-8 -*-
"""就绪原因（`answer_ready_reason`）的**出口完整性**判据。

缺陷（实测 208 个产物包）
------------------------
`answer_ready` 有 3 个出口：`decision_trace` / `quality` / `answer_summary`。
但 `answer_ready_reason` 此前**只写进第一个**。实测：

    answer_ready=False 的包 85 个
      └ 73 个：reason 只在 decision_trace，quality 里是空字符串
      └ 12 个：两处都空

后果：读 `quality` 的消费者（outputs 一致性护栏 / App 产物索引 / bench）
永远看不到「为什么没就绪」⇒ 产物说「不能答」却不给原因，护栏判
`verified + !ready(无原因)` 为矛盾。

为什么这是「出口」问题而不是「没写」
------------------------------------
引擎其实**写了**原因（73 个都在 dt 里），只是 `_q0.update({...})` 的键列表里
漏了 `answer_ready_reason`。所以修法不是去补判定逻辑，而是**把已有读数同步到
另外两个出口**，并对「仍未就绪且原因仍空」给可指认的兜底（过程合同 / 原始就绪 /
答案质量 / 题型）。

本判据要钉住的四件事
--------------------
A. 静态：三出口同源（dt / quality / answer_summary 都被赋同一个 `_rr0`）
B. 位置：同步发生在**答案门之后**（答案门是最后一个能把 answer_ready 打成
   False 的地方；放前面会漏掉答案门降级的原因）—— 位置也是判据的一部分
C. 变异体：删掉 quality 那一行 ⇒ A 必须判红（证明 A 有牙，不是恒绿）
D. 真实产物：V2.2.11 及之后产出的包，未就绪必须带 quality 原因（且必须有
   这类包存在，否则判据恒绿 = 没判据）
"""
from __future__ import annotations

import ast
import glob
import json
import pathlib
import re

V2 = pathlib.Path(__file__).resolve().parent
ROOT = V2.parent.parent          # dgtf_v2 -> dgtf_engine -> 仓库根
ENG = V2 / "engine"

PASS: list[str] = []
FAIL: list[str] = []


def ck(n, ok, info=""):
    (PASS if ok else FAIL).append(n)
    print(("✓ " if ok else "✗ ") + n + (("  — " + str(info)) if info else ""))


def _latest():
    vs = []
    for p in ENG.glob("Meta-DGTF-V*.py"):
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
        if m:
            vs.append((tuple(int(x) for x in m.groups()), p))
    if not vs:
        raise SystemExit("❌ 找不到引擎文件")
    return sorted(vs)[-1][1]


PATH = _latest()
SRC = PATH.read_text(encoding="utf-8", errors="replace")
print(f"   被测引擎：{PATH.name}")
VER = tuple(int(x) for x in re.search(r"V(\d+)\.(\d+)\.(\d+)", PATH.name).groups())

# ───────────────── A. 三出口同源（点名登记，不模糊匹配） ─────────────────
OUTLETS = ('_dt0["answer_ready_reason"] = _rr0',
           '_q0["answer_ready_reason"] = _rr0',
           '_asum0["answer_ready_reason"] = _rr0')


def outlets_present(src: str) -> dict[str, int]:
    return {o: src.count(o) for o in OUTLETS}


present = outlets_present(SRC)
ck("A1 ★ `answer_ready_reason` 三个出口都被赋同一个 `_rr0`（dt / quality / summary）",
   all(v == 1 for v in present.values()), str(present))

# ★ 有牙自检：能定位到那段代码在不在。全是 0 说明实现被改没了，不是「通过」。
ck("A1b 有牙自检：三出口赋值在源码里**找得到**（不是靠兜底恒绿）",
   sum(present.values()) == 3, str(present))

# 三行必须在同一个 `if _rr0:` 块里（AST 验证，防止被拆散到不同分支）
tree = ast.parse(SRC)
same_block = False
for node in ast.walk(tree):
    if not isinstance(node, ast.If):
        continue
    try:
        test_src = ast.unparse(node.test)
    except Exception:  # noqa: BLE001
        continue
    if test_src.strip() != "_rr0":
        continue
    # ast.unparse 一律输出**单引号**，源码锚点是双引号 ⇒ 比对前先把引号归一。
    body_src = "\n".join(ast.unparse(s) for s in node.body).replace("'", '"')
    same_block = all(o in body_src for o in OUTLETS)
    break
ck("A2 三行赋值在同一个 `if _rr0:` 块里（不会被拆到不同分支各自为政）",
   same_block, "块定位" + ("" if same_block else "失败"))

# ───────────────── B. 位置：在答案门之后 ─────────────────
# 答案门（`_ag_why`）是最后一个能把 answer_ready 打成 False 的地方。
# 同步段放它前面 ⇒ 答案门降级的原因不会被同步 ⇒ 又回到「dt 有、quality 没有」。
i_gate = SRC.find("_dt0[\"answer_ready_reason\"] = _ag_why(_ag)")
i_sync = SRC.find('_dt0["answer_ready_reason"] = _rr0')
ck("B1 有牙自检：定位得到「答案门写原因」与「统一出口同步」两处",
   i_gate > 0 and i_sync > 0, f"gate@{i_gate} sync@{i_sync}")
ck("B2 ★ 同步在答案门**之后**（答案门降级的原因也能同步出去）",
   i_gate > 0 and i_sync > i_gate, f"{i_gate} < {i_sync}")

# ───────────────── C. 兜底原因必须可指认（不许空话） ─────────────────
i_fb = SRC.find("_rr0 = (\"未就绪：过程合同=")
ck("C1 兜底原因存在（未就绪且原因仍空时给出，而不是留空）", i_fb > 0)
for token, desc in (("_process_ok", "过程合同"), ("raw_answer_ready", "原始就绪"),
                    ("answer_quality", "答案质量"), ("question_type", "题型")):
    ck(f"C2 兜底原因带上了「{desc}」（可指认，不是\"未知原因\"）",
       i_fb > 0 and token in SRC[i_fb:i_fb + 400], token)

# ───────────────── D. 变异体：删掉 quality 出口 ⇒ A 必须判红 ─────────────────
mutated = SRC.replace('_q0["answer_ready_reason"] = _rr0\n', "", 1)
ck("D1 变异体真的插进去了（否则测的是原版，假绿）",
   mutated != SRC and mutated.count('_q0["answer_ready_reason"] = _rr0') == 0)
ck("D2 ★ 删掉 quality 出口后，A1 必须判红（证明 A1 有牙）",
   not all(v == 1 for v in outlets_present(mutated).values()),
   str(outlets_present(mutated)))

# ───────────────── E. 真实产物回验（不是纯函数全绿就算数） ─────────────────
pack_dirs = [str(ROOT / "outputs" / "*.packed.json"),
             str(ROOT / "outputs" / "_e2e_local" / "*.packed.json")]
_new, _bad = [], []
for pat in pack_dirs:
    for f in glob.glob(pat):
        try:
            d = json.loads(pathlib.Path(f).read_text(encoding="utf-8",
                                                     errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        pv = str(((d.get("provenance") or {}).get("engine_version")) or "")
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", pv)
        if not m:
            continue
        vt = tuple(int(x) for x in m.groups())
        if vt < VER:
            continue
        _new.append(pathlib.Path(f).name)
        q = d.get("quality") or {}
        if q.get("answer_ready") is False:
            if not str(q.get("answer_ready_reason") or "").strip():
                _bad.append(pathlib.Path(f).name)
ck("E1 有牙自检：存在 V%s.%s.%s 及之后产出的产物包（否则本组恒绿 = 没判据）"
   % VER, len(_new) >= 1, f"{len(_new)} 个：{_new[:2]}")
ck("E2 ★ 真实产物：未就绪的包 `quality.answer_ready_reason` 非空",
   not _bad, f"缺原因：{_bad[:4]}")

print("\n%d/%d 通过" % (len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败：", FAIL)
    raise SystemExit(1)
