# -*- coding: utf-8 -*-
"""[V2.2.16] 从 V2.2.15 生成 V2.2.16：版本号 + 补丁说明 + json_mode 显式声明。"""
import py_compile
from pathlib import Path

ENG = Path("dgtf_engine/dgtf_v2/engine")
SRC = ENG / "Meta-DGTF-V2.2.15.py"
DST = ENG / "Meta-DGTF-V2.2.16.py"

raw = SRC.read_bytes()
assert raw[:3] != b"\xef\xbb\xbf"
assert raw.count(b"\n") == raw.count(b"\r\n")
text = raw.decode("utf-8").replace("\r\n", "\n")

REPL = []

REPL.append(("Meta-DGTF-道生三阶模型 · V2.2.15\n",
             "Meta-DGTF-道生三阶模型 · V2.2.16\n"))

REPL.append((
    "★ V2.2.15 补丁（stage 登记闭环 + 本地链路结构优化）：",
    "★ V2.2.16 补丁（JSON 期望显式声明：本地约束解码通道）：\n"
    "     json_mode=True 的调用（dual_judge / he_amps / probe_* / phase_probe /\n"
    "     self_check / decompose_* / assess_* 等 12+ 处）此前只把 JSON 期望写成\n"
    "     response_format（OpenAI 语义）与一句 system 提示；本地 shim 不看它，\n"
    "     服务端也没有解码级约束 ⇒ 0.5B 在长 prompt 下 **0% 以 { 开头**、全部\n"
    "     撞 max_new（224）：解析不出结构、每跑几十次 json_repair、墙钟被拖长。\n"
    "     本版在 LLM.call 把 json_mode 经 extra_body 显式摊到请求顶层（与 stage\n"
    "     同一条已打通的通道）：shim 透传给服务，服务端做「首 token 只允许 {\n"
    "     开头 + JSON 一闭合即停」。云端忽略未知字段 ⇒ 云档零行为差。\n"
    "     判据：tests_json_force.py（纯函数 + 接线 + 变异体）、test_graph_decode\n"
    "     G11/G12（显式 JSON 通道/首 token 约束）。\n"
    "\n"
    "★ V2.2.15 补丁（stage 登记闭环 + 本地链路结构优化）："))

REPL.append(('__version__ = "2.2.15"', '__version__ = "2.2.16"'))

REPL.append((
    '        _stage_tx = str(cost_stage or stage or "").strip()\n'
    '        if _stage_tx:\n'
    '            _eb = dict(kwargs.get("extra_body") or {})\n'
    '            _eb["stage"] = _stage_tx\n'
    '            kwargs["extra_body"] = _eb\n',
    '        _stage_tx = str(cost_stage or stage or "").strip()\n'
    '        if _stage_tx:\n'
    '            _eb = dict(kwargs.get("extra_body") or {})\n'
    '            _eb["stage"] = _stage_tx\n'
    '            kwargs["extra_body"] = _eb\n'
    '        # ★ [V2.2.16] JSON 期望显式声明（与 stage 同一条通道）：本地 shim 读它\n'
    '        #   做「首 token 只允许 { 开头 + 闭合即停」；云端忽略未知字段 ⇒ 零影响。\n'
    '        if json_mode:\n'
    '            _eb = dict(kwargs.get("extra_body") or {})\n'
    '            _eb["json_mode"] = True\n'
    '            kwargs["extra_body"] = _eb\n'))

for i, (old, new) in enumerate(REPL, 1):
    n = text.count(old)
    assert n == 1, "锚点 %d 命中 %d 次（应为 1）" % (i, n)
    text = text.replace(old, new)

out = text.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)
chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0
assert chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(DST), doraise=True)
print("OK:", DST.name, len(chk), "bytes")
