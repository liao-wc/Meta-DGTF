# -*- coding: utf-8 -*-
"""stage 覆盖判据（V2.2.13b）：引擎发出的每个 stage 必须登记在 gates 表里。

为什么需要这条判据
------------------
本地链路的 stage 通道（引擎 extra_body → shim 显式优先 → service 放行）
打通后，**未登记 stage 不再被 400 拒绝**，而是走 base model +
`DEFAULT_MAX_NEW_FALLBACK=64` 的兜底长度。64 只够小 JSON 决策 ——
主生成 stage（decompose_* / probe_* / expand_pair*）落 64 ⇒ JSON 截断、
amps 抽不出、修行层目标读数「存量为 0」。V2.2.12 的 expand_pair_merged
就是这么炸过一次。

⇒ 凡是引擎源码里出现的 stage 字面量，必须出现在
`dgtf_local_llm/gates.DEFAULT_MAX_NEW` 或 `LORA_STAGES` 里。
未来新加 stage 不登记，这条判据直接判红 —— 否则它又会**静默**落 64。

有牙设计：
  · 引擎文件**动态发现**（最高版本），不钉字面量（钉了下一版就过期）；
  · 至少要抽到 25 个不同字面量 —— 抽取正则坏了/文件读不到 ⇒ 红，
    而不是「查了 0 个、全绿」；
  · 自带变异体：把一个未登记 stage 喂给同一套抽取+核对逻辑，
    必须报缺失（证明核对逻辑有牙，不是恒绿）。

零 torch / 零 API：引擎文件只当**文本**读，不 import。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from dgtf_local_llm.gates import DEFAULT_MAX_NEW, LORA_STAGES  # noqa: E402

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


#: `stage="x"` / `stage='y'` / `cost_stage="z"` / `cost_stage='w'`。
#: \b 挡住 `_stage_tx` / `req["stage"]` 这类非赋值/属性场景；
#: 引号内只认 [a-z0-9_]（stage 清洗后的合法字符集）。
_STAGE_RE = re.compile(
    r"\b(?:cost_)?stage\s*=\s*[\"']([a-z0-9_]+)[\"']")


def extract_stage_literals(src: str):
    """从引擎源码文本抽取 stage 字面量（保持出现顺序，含重复）。"""
    return _STAGE_RE.findall(src)


def missing_from_table(literals):
    """返回不在登记表里的 stage（按首现顺序去重）。"""
    known = set(DEFAULT_MAX_NEW) | set(LORA_STAGES)
    seen, miss = set(), []
    for s in literals:
        if s not in known and s not in seen:
            seen.add(s)
            miss.append(s)
    return miss


def find_engine_file() -> Path:
    """当前最高版引擎文件（动态发现，绝不写死版本号）。"""
    eng_dir = ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
    best, best_ver = None, (0, 0, 0)
    for f in eng_dir.glob("Meta-DGTF-V*.py"):
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)\.py$", f.name)
        if not m:
            continue
        ver = tuple(int(x) for x in m.groups())
        if ver > best_ver:
            best, best_ver = f, ver
    return best


def main() -> int:
    # ── A 抽取器本体（合成样本：四形态都要抓到，无关形态不误抓）──
    lit = extract_stage_literals(
        'raw = self.llm.call(system, user, 0.3, 500, json_mode=True,\n'
        '                    stage=_thinking_stage(self.config, \'arg_not_stage\'),\n'
        '                    cost_stage=\'re_anchor\')\n'
        'raws[label] = self.llm.call(prompt, user, 0.9, 1500,\n'
        '                           stage="expand_pair")\n'
        'resp = self.llm.call(system, user, stage=None, model=None)\n'
        '_stage_tx = str(cost_stage or stage or "")\n'
        'req["stage"] = _stage_s\n')
    ck("A1 抽取：cost_stage='…' 单引号形态",
       "re_anchor" in lit, lit)
    ck("A2 抽取：stage=\"…\" 双引号形态",
       "expand_pair" in lit, lit)
    ck("A3 抽取：函数实参（_thinking_stage 的第二参）**不**被当成赋值",
       "arg_not_stage" not in lit, lit)
    ck("A4 抽取：stage=None / stage 变量 / req[\"stage\"]= / _stage_tx 不产生字面量",
       set(lit) == {"re_anchor", "expand_pair"}, lit)

    # ── B 变异体：未登记 stage 必须被核对逻辑报出来（有牙证明）──
    mut = extract_stage_literals('x = self.llm.call(a, b, stage="brand_new_stage")')
    ck("B1 变异体：未登记 stage 被抽取到",
       mut == ["brand_new_stage"], mut)
    ck("B2 变异体：核对逻辑报缺失（不是恒绿）",
       missing_from_table(mut) == ["brand_new_stage"],
       missing_from_table(mut))
    ck("B3 变异体：已登记 stage 不误报",
       missing_from_table(["expand_pair_merged", "self_check"]) == [])

    # ── C 真实引擎：全覆盖 ──────────────────────────────
    eng = find_engine_file()
    ck("C1 引擎文件动态发现成功（最高版）",
       eng is not None and eng.is_file(),
       str(eng))
    if eng is None:
        print("TOTAL PASS %d / FAIL %d" % (len(P), len(F)))
        return 1
    src = eng.read_text(encoding="utf-8", errors="replace")
    lits = extract_stage_literals(src)
    uniq = sorted(set(lits))
    ck("C2 字面量数量有牙（≥25 个不同 stage，抽取器坏了就红）",
       len(uniq) >= 25, f"{len(uniq)} 个: {uniq[:8]}…")
    miss = missing_from_table(lits)
    ck("C3 引擎全部 stage 字面量都已登记（缺一即红）",
       not miss, f"缺: {miss}")
    ck("C4 LoRA 四件套都在 DEFAULT_MAX_NEW（两表一致）",
       all(s in DEFAULT_MAX_NEW for s in LORA_STAGES),
       [s for s in LORA_STAGES if s not in DEFAULT_MAX_NEW])

    print("引擎文件: %s (%d 处赋值 / %d 个不同 stage)"
          % (eng.name, len(lits), len(uniq)))
    print("TOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
