# -*- coding: utf-8 -*-
"""self_memory 上下文压缩判据（Round 8）。

覆盖：
  · 默认配置 self_memory_max_chars=0（零行为差）；
  · 超上限 → 只保留最近 N 字 + 压缩标记，旧内容不出现；
  · 未超限 / 上限=0 / 负数 / 非法值 → 原样（fail-open）；
  · use_self=False → 空串；
  · 引擎源码含 CLI 开关与配置注释。
"""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "engine" / "Meta-DGTF-V2.2.3.py"
P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n +
          (" :: " + str(info) if info and not ok else ""))


def load_mod():
    spec = importlib.util.spec_from_file_location("engine_mem_test", str(ENGINE))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["engine_mem_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def fake(mem, cap=None, use_self=True, raw_cap=False):
    out_cfg = {} if cap is None else {"self_memory_max_chars": cap}
    if raw_cap:
        out_cfg = {"self_memory_max_chars": raw_cap}
    return SimpleNamespace(use_self=use_self, self_memory=mem,
                           config={"output": out_cfg})


def main():
    mod = load_mod()
    out_cfg = (mod.DEFAULT_CONFIG.get("output") or {})
    ck("DEFAULT_CONFIG.output.self_memory_max_chars 默认 0（零行为差）",
       out_cfg.get("self_memory_max_chars") == 0,
       out_cfg.get("self_memory_max_chars"))

    mem = "A" * 3000 + "B" * 3000
    block_full = mod.DGTF._self_block(fake(mem, cap=None))
    ck("默认（cap=0）→ 完整记忆原样出现（含最旧 A 段）",
       "A" * 3000 in block_full and "B" * 3000 in block_full,
       len(block_full))

    block_cap = mod.DGTF._self_block(fake(mem, cap=1200))
    ck("超限 → 只保留最近 1200 字（B 段尾部）",
       block_cap.rstrip().endswith("B" * 1200), block_cap[-80:])
    ck("超限 → 最旧 A 段被压缩掉",
       "A" * 3000 not in block_cap and "A" * 100 not in block_cap)
    ck("超限 → 含压缩标记与字数说明",
       "已压缩" in block_cap and "6000" in block_cap
       and "1200" in block_cap, block_cap[:80])
    ck("超限 → 渲染长度受控（≤ cap + 标记 ~120 字）",
       len(block_cap) <= 1200 + 160, len(block_cap))

    short = "S" * 500
    b_short = mod.DGTF._self_block(fake(short, cap=1200))
    ck("未超限 → 原样（不裁剪）", b_short.count("S") == 500 and "已压缩" not in b_short)

    b_zero = mod.DGTF._self_block(fake(mem, cap=0))
    ck("cap=0 → 不压缩", b_zero == block_full)

    b_neg = mod.DGTF._self_block(fake(mem, cap=-5))
    ck("cap 负数 → 不压缩（fail-open）", b_neg == block_full)

    b_bad = mod.DGTF._self_block(fake(mem, raw_cap="abc"))
    ck("cap 非法字符串 → 不压缩（fail-open）", b_bad == block_full)

    b_off = mod.DGTF._self_block(fake(mem, cap=1200, use_self=False))
    ck("use_self=False → 空串", b_off == "")

    src = ENGINE.read_text(encoding="utf-8", errors="replace")
    ck("CLI --self-memory-max-chars 存在", "--self-memory-max-chars" in src)
    ck("配置注释含「上下文压缩」", "上下文压缩" in src)

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
