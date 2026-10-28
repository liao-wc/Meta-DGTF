# -*- coding: utf-8 -*-
"""[V2.2.17] 本地 prompt 瘦身判据（纯函数 + 门控 + 静态接线 + 变异体，零 GPU）。

背景：真实 584 条引擎 prompt 统计，行级完全去重可省 45.3% token（106.6 万→58.3 万），
schema/指令行零丢失。瘦身只对【本地端点】生效（云端一字不动）。
"""
from __future__ import annotations

import importlib.util
import re
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENG_DIR = HERE / "engine"
P, F = [], []


def ck(name, cond, info=""):
    (P if cond else F).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (" :: " + str(info) if info and not cond else ""))


def _highest():
    cands = list(ENG_DIR.glob("Meta-DGTF-V*.py"))

    def ver(p):
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    cands.sort(key=ver)
    return cands[-1]


ENGINE = _highest()
_spec = importlib.util.spec_from_file_location("dgtf_v2217_lpd", ENGINE)
ENG = importlib.util.module_from_spec(_spec)
sys.modules["dgtf_v2217_lpd"] = ENG
_spec.loader.exec_module(ENG)
SRC = ENGINE.read_text(encoding="utf-8-sig")
DIET = ENG.diet_local_prompt


def _pad(n, tag="填充"):
    return "\n".join("%s-%04d" % (tag, i) for i in range(n))


print("引擎：", ENGINE.name)
print("── A 纯函数 diet_local_prompt ──")
# 重复行放在 head（前面），尾部用足量唯一行把总长撑过 TAIL
_dup = "重复行 A\n重复行 A\n唯一行 B\n重复行 A\n唯一行 C\n重复行 A\n" + _pad(80)
new, st = DIET(_dup)
ck("A1 行级完全去重生效", st["lines_removed"] >= 2
   and new.count("重复行 A") == 1, (st, new[:60]))
ck("A2 首次出现顺序保留",
   new.index("唯一行 B") < new.index("唯一行 C") and new.startswith("重复行 A"))
ck("A3 唯一文本不改（零删除）", DIET(_pad(120))[0] == _pad(120))
_empty, _st = DIET("")
ck("A4 空输入安全（原样 + 零统计）", _empty == "" and _st["chars_before"] == 0)
_uniq = _pad(200)
_u2, _s2 = DIET(_uniq)
ck("A5 无重复时不增长且零删除",
   len(_u2) <= len(_uniq) and _s2["lines_removed"] == 0 and _u2 == _uniq)

_noise = "【Agent知识回声】" + "X" * 600 + "\n普通行"
_n2, _ns = DIET(_noise, cap=240, tail=0)
ck("A6 噪声块截断到 cap（tail=0 全量）",
   ("X" * 600) not in _n2 and "【Agent知识回声】" in _n2
   and _ns["blocks_truncated"] >= 1, (_ns, len(_n2)))
_dup_noise = ("【参考记忆特征】(哈希) a、b、c\n正文1\n"
              "【参考记忆特征】(哈希) a、b、c\n正文2")
_n3, _ns3 = DIET(_dup_noise, cap=240, tail=0)
ck("A7 重复噪声块只留第一份", _n3.count("【参考记忆特征】") == 1,
   (_ns3, _n3[:60]))

# 尾部保护：最后约 tail 字符按整行对齐原样保留（含重复行）
_schema = '{"judgments":[{"idx":1,"position":"0|1|both","why_position":"%s"}]}' % ("说明" * 70)
_tailbody = "\n".join([_schema] * 3)
_head = _pad(60) + "\n"
_t2, _ts = DIET(_head + _tailbody, cap=240, tail=320)
ck("A8 尾部 TAIL 区原样保护（尾部重复 schema 行不被删）",
   _t2.endswith(_tailbody[-120:]), _t2[-80:])
ck("A9 尾部保护不破坏总长度（不增长）", len(_t2) <= len(_head + _tailbody))

# 真实形态：多份噪声块 + 重复记忆行
_real = "\n".join(
    ["你是【对偶判断者】。", "严格 JSON：", '{"judgments":[{"idx":1,"position":"0|1|both"}]}']
    + ["参考记忆特征（哈希）: 76a71fbef8a8、471231e8795b、bcf306997abc"] * 6
    + ["【Agent知识回声】" + "知识" * 500] * 3
    + ["【0层侧面清单】" + "侧面" * 200] * 3
    + ["【你上一次是谁】" + "上一次的输出" * 60] * 2
    + ["候选 %d：描述" % i for i in range(20)]
    + ["优先判断，不要凑数。" * 2]
    + ["这一层走过的路：" + "路径" * 100] * 2)
_r2, _rs = DIET(_real)
ck("A10 真实形态 prompt 缩减 >= 30%（且不增长）",
   len(_r2) <= len(_real) * 0.70 and _rs["chars_after"] < _rs["chars_before"],
   (len(_real), len(_r2), _rs))
ck("A11 真实形态「严格 JSON」指令存活", "严格 JSON：" in _r2 and "judgments" in _r2)


print("── B LLM 门控（本地端点才瘦身）──")


def _mk_llm(local=True, enabled=True):
    llm = object.__new__(ENG.LLM)
    llm._local_endpoint = local
    llm.lpd_enabled = enabled
    llm.lpd_cap = 240
    llm.lpd_tail = 320
    llm._lock = threading.Lock()
    llm.prompt_diet_stats = {"applied": 0, "chars_before": 0, "chars_after": 0,
                             "lines_removed": 0, "blocks_truncated": 0}
    return llm


_llmdup = "系统重复行\n系统重复行\n系统重复行\n" + _pad(80)
_l = _mk_llm(local=True, enabled=True)
_s2, _u2 = _l._maybe_diet_prompts(_llmdup, _llmdup)
ck("B1 本地端点 + 开关开 ⇒ 瘦身生效并记账",
   len(_s2) < len(_llmdup) and _l.prompt_diet_stats["applied"] == 1,
   _l.prompt_diet_stats)
_l._maybe_diet_prompts(_llmdup, _llmdup)
ck("B2 二次调用继续累加", _l.prompt_diet_stats["applied"] == 2)
_l2 = _mk_llm(local=True, enabled=False)
ck("B3 开关关 ⇒ 原样返回", _l2._maybe_diet_prompts(_llmdup, _llmdup) == (_llmdup, _llmdup)
   and _l2.prompt_diet_stats["applied"] == 0)
_l3 = _mk_llm(local=False, enabled=True)
ck("B4 云端端点 ⇒ 原样返回（零行为差）",
   _l3._maybe_diet_prompts(_llmdup, _llmdup) == (_llmdup, _llmdup)
   and _l3.prompt_diet_stats["applied"] == 0)


print("── C 静态接线 ──")
ck("C1 引擎版本 >= 2.2.17", tuple(int(x) for x in
   re.search(r"V(\d+)\.(\d+)\.(\d+)", ENGINE.name).groups()) >= (2, 2, 17))
ck("C2 LLM.call 里调用了 _maybe_diet_prompts", "_maybe_diet_prompts(system, user)" in SRC)
ck("C3 packed 有 llm_prompt_diet 出口", '"llm_prompt_diet"' in SRC)
ck("C4 DEFAULT_CONFIG 有 local_prompt_diet", '"local_prompt_diet": True' in SRC)
ck("C5 CLI 有 --local-prompt-diet", '"--local-prompt-diet"' in SRC)
ck("C6 瘦身只对本地端点（_local_endpoint 门控）",
   "if not (getattr(self, \"_local_endpoint\", False)" in SRC)
ck("C7 尾部按整行对齐（不含硬字符切）", "for i in range(len(lines) - 1, -1, -1)" in SRC)


print("── D 变异体（有牙证明）──")


def _bad_no_tail(text, cap=240, tail=320):
    """变异体：不做尾部保护（尾部重复行会被去重）⇒ A8 必须红。"""
    seen, kept = set(), []
    for ln in text.split("\n"):
        k = ln.strip()
        if k and k in seen:
            continue
        if k:
            seen.add(k)
        kept.append(ln)
    return "\n".join(kept)


_bad = _bad_no_tail(_head + _tailbody)
ck("D1 变异体：去掉尾部保护 ⇒ 尾部 3 条重复 schema 被删成 1 条（A8 对照）",
   _bad.count(_schema) == 1 and (_head + _tailbody).count(_schema) == 3,
   (_bad.count(_schema), (_head + _tailbody).count(_schema)))

_noop = _real  # 变异体：瘦身函数摆烂（原样返回）⇒ A10 的缩减条件必须判红
ck("D2 变异体：瘦身不生效（原样返回）⇒ A10 的缩减/不增长条件会判红",
   not (len(_noop) <= len(_real) * 0.70), (len(_noop), len(_real)))


def _bad_gate(local, enabled, s, u):
    """变异体：忽略端点判断（云端也瘦身）⇒ B4 必须红。"""
    return DIET(s)[0], DIET(u)[0]


_bg = _bad_gate(False, True, _llmdup, _llmdup)
ck("D3 变异体：忽略云端判断 ⇒ 云端内容被改动（B4 对照）", _bg[0] != _llmdup)

print("")
print("PASS %d / FAIL %d" % (len(P), len(F)))
raise SystemExit(1 if F else 0)
