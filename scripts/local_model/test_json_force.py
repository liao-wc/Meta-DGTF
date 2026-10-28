# -*- coding: utf-8 -*-
"""[V2.2.16] JSON 约束解码的**零 GPU**判据（纯函数 + 三处接线 + 变异体）。

为什么需要它
------------
0.5B 本地底座在 json_mode 调用上 0% 以 { 开头、全部撞 max_new。V2.2.16 的三段接线：
  引擎 LLM.call 把 json_mode 摊到 extra_body（与 stage 同一条通道）
  → shim 透传给服务（也兼容 response_format=json_object）
  → 服务首 token 只允许 { 开头、JSON 一闭合即停。
纯函数在 gates.py（json_done / json_first_token_ids）；本文件零 torch/零 HTTP/零 GPU。
每条接线判据都配变异体（把被禁写法喂给同一检查函数 ⇒ 必须判红）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dgtf_local_llm import gates  # noqa: E402

P, F = [], []
LBR, RBR = chr(123), chr(125)
Q = chr(34)


def ck(name, cond, info=""):
    (P if cond else F).append(name)
    print(("PASS " if cond else "FAIL ") + name + (" :: " + str(info) if not cond else ""))


def _read(p):
    return Path(p).read_text(encoding="utf-8-sig")


SERVICE = _read(ROOT / "dgtf_local_llm/service.py")
SHIM = _read(ROOT / "scripts/local_model/openai_shim.py")


def _highest_engine():
    d = ROOT / "dgtf_engine/dgtf_v2/engine"
    cands = list(d.glob("Meta-DGTF-V*.py"))

    def ver(p):
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    cands.sort(key=ver)
    return cands[-1], ver(cands[-1])


ENGINE, ENG_VER = _highest_engine()
ENG = _read(ENGINE)


# ── A 纯函数 json_done ─────────────────────────────────────
print("── A json_done 纯函数 ──")
_obj = LBR + Q + "a" + Q + ":" + "1" + RBR
_done_cases = [
    (_obj, True),
    (LBR + Q + "a" + Q + ":1", False),
    (LBR + Q + "a" + Q + ":" + LBR + Q + "b" + Q + ":2" + RBR + RBR, True),
    (LBR + Q + "a" + Q + ":" + Q + RBR + Q + RBR, True),
    (LBR + Q + "a" + Q + ":" + Q + "x", False),
    (chr(96) * 3 + "json\n" + _obj + "\n" + chr(96) * 3, True),
    ("hello " + _obj, False),
    ("", False),
    (_obj + " trailing", True),
]
for i, (txt, want) in enumerate(_done_cases, 1):
    got = gates.json_done(txt)
    ck("A%d json_done(%r) == %s" % (i, txt[:34], want), got is want, got)
ck("A10 两向守卫：未闭合必须 False、闭合必须 True",
   gates.json_done(LBR + Q + "a" + Q + ":1") is False
   and gates.json_done(_obj) is True)


# ── B 纯函数 json_first_token_ids ──────────────────────────
print("── B json_first_token_ids 纯函数 ──")
_items = [(1, LBR), (2, " " + LBR), (3, "\n" + LBR),
          (4, "["), (5, "json"), (6, LBR + "abc"), (7, Q), (8, RBR)]
_ids = gates.json_first_token_ids(_items)
ck("B1 只有 { 开头的 token 入选（含空格/换行变体）", _ids == [1, 2, 3, 6], _ids)
ck("B2 空输入 ⇒ 空表（不抛异常）", gates.json_first_token_ids([]) == [])
ck("B3 非法 id 不炸", gates.json_first_token_ids([("x", LBR)]) == [])


# ── C 服务接线 ─────────────────────────────────────────────
print("── C service.py 接线 ──")
ck("C1 service 从 gates import 两个纯函数",
   "json_done" in SERVICE and "json_first_token_ids" in SERVICE)
ck("C2 generate_graph 接受 json_mode 参数",
   re.search(r"def generate_graph\([^)]*json_mode", SERVICE, re.S) is not None)
ck("C3 慢路径 generate 接受 json_mode 参数",
   re.search(r"def generate\([^)]*json_mode", SERVICE, re.S) is not None)
ck("C4 首 token 约束落到 logits（masked_fill + -inf）",
   "masked_fill(~_lead_mask" in SERVICE and 'float("-inf")' in SERVICE)
ck("C5 闭合即停接线（generate_graph 里调 json_done）",
   "if json_done(_jt):" in SERVICE)
ck("C6 _handle 解析并透传 json_mode（两条路径都传）",
   SERVICE.count("json_mode=json_mode") >= 2)
ck("C7 回包带 json_mode（可分辨）", '"json_mode": bool(json_mode)' in SERVICE)
ck("C8 缓存 key 含 json_mode（不复用错态结果）",
   re.search(r'"temperature", "repetition_penalty", "json_mode"', SERVICE) is not None)
ck("C9 指标有 json_forced_generations（约束真生效的证据出口）",
   "json_forced_generations" in SERVICE)


# ── D shim 接线 ───────────────────────────────────────────
print("── D openai_shim.py 接线 ──")
ck("D1 call_upstream 接受 json_mode",
   re.search(r"def call_upstream\([^)]*json_mode", SHIM, re.S) is not None)
ck("D2 请求体带 json_mode（服务端才收得到）",
   re.search('"json_mode": bool\(json_mode\)', SHIM) is not None)
ck("D3 兼容 response_format=json_object", "json_object" in SHIM)
ck("D4 回包 dgtf_local 留痕 json_mode",
   re.search(r'"dgtf_local": \{[^}]*"json_mode"', SHIM, re.S) is not None)


# ── E 引擎接线（最高版） ──────────────────────────────────
print("── E 引擎接线（%s）──" % ENGINE.name)
ck("E1 引擎版本 >= 2.2.16", ENG_VER >= (2, 2, 16), ENG_VER)
ck("E2 LLM.call 把 json_mode 摊进 extra_body",
   re.search(r'if json_mode:\n\s+_eb = dict\(kwargs\.get\("extra_body"\) or \{\}\)'
             r'\n\s+_eb\["json_mode"\] = True', ENG) is not None)
_pos_stage = ENG.find('"stage"] = _stage_tx')
_pos_json = ENG.find('"json_mode"] = True')
ck("E3 该声明在 stage 之后（同一 extra_body，不覆盖 stage）",
   _pos_stage > 0 and _pos_json > _pos_stage, (_pos_stage, _pos_json))


# ── F 变异体：同一检查逻辑必须能判红 ─────────────────────
print("── F 变异体（有牙证明）──")


def _wired(src_service, src_shim, src_engine) -> dict:
    return {
        "service_mask": "masked_fill(~_lead_mask" in src_service,
        "service_stop": "if json_done(_jt):" in src_service,
        "shim_pass": re.search('"json_mode": bool\(json_mode\)', src_shim) is not None,
        "engine_decl": re.search(r'_eb\["json_mode"\] = True', src_engine) is not None,
    }


_ok = _wired(SERVICE, SHIM, ENG)
ck("F0 真实源码四项全过（否则 F1–F4 没有对照）", all(_ok.values()), _ok)
ck("F1 变异体：删掉首 token 约束 ⇒ 判红",
   _wired(SERVICE.replace("masked_fill(~_lead_mask", "masked_fill(~_never"),
          SHIM, ENG)["service_mask"] is False)
ck("F2 变异体：删掉闭合即停 ⇒ 判红",
   _wired(SERVICE.replace("if json_done(_jt):", "if False:"),
          SHIM, ENG)["service_stop"] is False)
ck("F3 变异体：shim 不透传 json_mode ⇒ 判红",
   _wired(SERVICE, SHIM.replace('"json_mode": bool(json_mode),', ""),
          ENG)["shim_pass"] is False)
ck("F4 变异体：引擎不声明 json_mode ⇒ 判红",
   _wired(SERVICE, SHIM, ENG.replace('_eb["json_mode"] = True', "pass"))
   ["engine_decl"] is False)

print("")
print("PASS %d / FAIL %d" % (len(P), len(F)))
raise SystemExit(1 if F else 0)
