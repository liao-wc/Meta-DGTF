# -*- coding: utf-8 -*-
"""[V2.2.15] 从 V2.2.14 生成 V2.2.15：版本号 + 补丁说明 + stage 登记（K4）。"""
import py_compile
from pathlib import Path

ENG = Path("dgtf_engine/dgtf_v2/engine")
SRC = ENG / "Meta-DGTF-V2.2.14.py"
DST = ENG / "Meta-DGTF-V2.2.15.py"

raw = SRC.read_bytes()
assert raw[:3] != b"\xef\xbb\xbf", "引擎文件应无 BOM"
assert raw.count(b"\n") == raw.count(b"\r\n"), "预期纯 CRLF"
text = raw.decode("utf-8").replace("\r\n", "\n")

REPL = []

# 1) 标题版本
REPL.append(("Meta-DGTF-道生三阶模型 · V2.2.14\n",
             "Meta-DGTF-道生三阶模型 · V2.2.15\n"))

# 2) 补丁说明（插在 V2.2.14 段之前）
REPL.append((
    "★ V2.2.14 补丁（re_anchor few-shot）：",
    "★ V2.2.15 补丁（stage 登记闭环 + 本地链路结构优化）：\n"
    "     (1) 审计 K4 闭环：expand_pair / expand_pair_merged /\n"
    "         expand_pair_merged_fixup / ing / he_amps / manifest 六个 stage 在\n"
    "         DEFAULT_CONFIG.api.thinking.stages 里补登记（值 = thinking.default\n"
    "         = \"disabled\" ⇒ 与「未声明时掉回 default」逐字等价，零行为差）。\n"
    "         此前审计口径「代码里传的字面 stage 都必须在配置里声明」自 V2.2.4\n"
    "         起一直是红的（8 个调用点、6 个名字），根因是这些调用只借 stage\n"
    "         做成本归因/思考档位，从未在配置里登记。\n"
    "     (2) 本地链路（服务侧，见 dgtf_local_llm/service.py）：底座 fp32\n"
    "         （1660Ti/TU116 无 tensor core，fp16 Linear 命中 cutlass wmma\n"
    "         仿真核 0.5ms/次）⇒ 单 token graph replay 59→28ms；CUDA graph\n"
    "         支持 temp>0 采样与重复惩罚（此前只有 temp==0 能走 graph，而引擎\n"
    "         绝大多数调用 temp 0.2~0.9 ⇒ 全落慢路径）；base stage 显式禁用\n"
    "         适配器（此前沿用上一次 set_adapter ⇒ 底座输出被别的 LoRA 污染，\n"
    "         实测 re_anchor 多吐 \"anchorText\" 幻觉键）；graph 按「LoRA stage\n"
    "         各一张 + base 共用一张」复用（graph 数 ~18→5，显存 −70%）。\n"
    "\n"
    "★ V2.2.14 补丁（re_anchor few-shot）："))

# 3) __version__
REPL.append(('__version__ = "2.2.14"', '__version__ = "2.2.15"'))

# 4) thinking.stages 补登记（K4）
REPL.append((
    '                "tool_preflight": "disabled",\n'
    '            },',
    '                "tool_preflight": "disabled",\n'
    '                # ★ [V2.2.15 · 审计 K4] 这 6 个 stage 有调用点传字面量、\n'
    '                #   但此前未登记 ⇒ 静默掉回 thinking.default。\n'
    '                #   登记值 = default("disabled") ⇒ 与未声明时逐字等价。\n'
    '                "expand_pair": "disabled",\n'
    '                "expand_pair_merged": "disabled",\n'
    '                "expand_pair_merged_fixup": "disabled",\n'
    '                "ing": "disabled",\n'
    '                "he_amps": "disabled",\n'
    '                "manifest": "disabled",\n'
    '            },'))

for i, (old, new) in enumerate(REPL, 1):
    n = text.count(old)
    assert n == 1, "锚点 %d 命中 %d 次（应为 1）" % (i, n)
    text = text.replace(old, new)

out = text.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)
chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0, "出现 \\r\\r\\n 污染"
assert chk.count(b"\n") == chk.count(b"\r\n"), "不是纯 CRLF"
py_compile.compile(str(DST), doraise=True)
print("OK:", DST.name, len(chk), "bytes, CRLF=", chk.count(b"\r\n"))
