# -*- coding: utf-8 -*-
"""补丁：V2.2.4 → V2.2.5（成本归因收敛）。

改动（全部为「只加标签，不改调用」）：
  1) 标题与 __version__ → 2.2.5
  2) docstring 增 V2.2.5 段
  3) 4 个未标记 stage 的 LLM 调用点补具名 stage（展开/& 生成）

铁律：read_bytes → 断言 CRLF==LF → 转 LF → 替换（每项断言命中==1）
      → 转回 CRLF → write_bytes → 自检 \r\r\n == 0。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENG = ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
SRC = ENG / "Meta-DGTF-V2.2.4.py"
DST = ENG / "Meta-DGTF-V2.2.5.py"

# (说明, 旧串, 新串)
EDITS = [
    (
        "标题版本",
        "Meta-DGTF-道生三阶模型 · V2.2.4",
        "Meta-DGTF-道生三阶模型 · V2.2.5",
    ),
    (
        "版本号",
        '__version__ = "2.2.4"',
        '__version__ = "2.2.5"',
    ),
    (
        "docstring 增段",
        "★ V2.2.4 补丁（默认零行为差，全部 opt-in）：本地档对接 CUDA graph"
        "（贪心解码/批量合批/",
        "★ V2.2.5 补丁（零行为差，只补归因）：对撞层展开与 & 生成共 4 个调用点\n"
        "  原先不带 stage，在 llm_by_stage 里全部落进 unknown（实测一跑占 55% tokens、\n"
        "  243s 墙钟却无法归因）。现补具名 stage（expand_pair / expand_pair_merged /\n"
        "  expand_pair_merged_fixup / he_amps），调用参数、次数、输出一个字不动；\n"
        "  仅使成本可归因。所有产出的读取方按「未知键降级为键名」兼容，无需同步改。\n\n"
        "★ V2.2.4 补丁（默认零行为差，全部 opt-in）：本地档对接 CUDA graph"
        "（贪心解码/批量合批/",
    ),
    (
        "展开-并行提交",
        "ex.submit(self.llm.call, prompt, user, 0.9, 1500): label",
        'ex.submit(self.llm.call, prompt, user, 0.9, 1500,\n'
        '                              stage="expand_pair"): label',
    ),
    (
        "展开-串行",
        "raws[label] = self.llm.call(prompt, user, 0.9, 1500)",
        'raws[label] = self.llm.call(prompt, user, 0.9, 1500,\n'
        '                                               stage="expand_pair")',
    ),
    (
        "合并展开",
        "raw = self.llm.call(merged_system, user0, 0.9, 2600)",
        'raw = self.llm.call(merged_system, user0, 0.9, 2600,\n'
        '                               stage="expand_pair_merged")',
    ),
    (
        "合并展开-补跑",
        "seg1 = self.llm.call(prompt1, user1, 0.9, 1500) or",
        'seg1 = self.llm.call(prompt1, user1, 0.9, 1500,\n'
        '                                     stage="expand_pair_merged_fixup") or',
    ),
    (
        "& 候选生成",
        "raw = self.llm.call(system, user, 0.3, 2500, json_mode=True)",
        'raw = self.llm.call(system, user, 0.3, 2500, json_mode=True,\n'
        '                                stage="he_amps")',
    ),
]


def main() -> int:
    raw = SRC.read_bytes()
    crlf, lf = raw.count(b"\r\n"), raw.count(b"\n")
    assert crlf == lf, f"源文件不是纯 CRLF: CRLF={crlf} LF={lf}"
    text = raw.decode("utf-8").replace("\r\n", "\n")

    for i, (name, old, new) in enumerate(EDITS, 1):
        n = text.count(old)
        assert n == 1, f"[{i}] {name}: 锚点命中 {n} 次（要求恰好 1）"
        text = text.replace(old, new, 1)
        print(f"  [{i}] OK {name}")

    out = text.replace("\n", "\r\n")
    DST.write_bytes(out.encode("utf-8"))

    # 自检
    chk = DST.read_bytes()
    c2, l2 = chk.count(b"\r\n"), chk.count(b"\n")
    assert c2 == l2, f"输出不是纯 CRLF: {c2} vs {l2}"
    assert chk.count(b"\r\r\n") == 0, "出现 \\r\\r\\n（write_text 事故）"
    assert b'"2.2.5"' in chk
    print(f"\n写出 {DST.name}: {len(chk)} bytes / {c2} 行 / 纯 CRLF OK / \\r\\r\\n=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
