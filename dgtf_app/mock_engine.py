# -*- coding: utf-8 -*-
"""mock 引擎：模拟真引擎的分层跑圈日志与产物，**零 API 花费**。

用途：应用开发验证与界面演示。CLI 与真引擎兼容——
`python mock_engine.py "问题" [--rounds N --route ...]`（额外参数一律忽略）。
"""

from __future__ import annotations

import datetime
import random
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = PROJECT_ROOT / "outputs"

_LAYERS = [("修行", "0"), ("研究", "1"), ("对撞", "both"), ("元", "all")]


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    question = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "（空问题）"
    log("[mock] 问题：" + question)
    log("[mock] 引擎：mock_engine（不调用任何 API、零花费）")

    stop_kind = {}
    rounds_run = {}
    for name, _tag in _LAYERS:
        rounds = random.randint(1, 3)
        rounds_run[name] = rounds
        for r in range(1, rounds + 1):
            log(f"[{name}层] 第 {r} 圈：锚点重述 → 阴阳展开 → 对撞 → 沉淀 & → 探针回归 → 渲染")
            time.sleep(0.6)
            # 模拟真引擎在 verbose / show_ing / show_manifest 下的两类"大块"，
            # 供应用层过滤验证：后台不应看到它们（原始仍进归档 log）。
            log("╔" + "═" * 50 + "╗")
            log(f"║ 圈全量留痕 · entry=0 · 第 {r} 圈 · 摊开")
            log("╚" + "═" * 50 + "╝")
            log("   ├ candidates：list 3 项")
            log("   │   [mock 字段正文，不应出现在后台]")
            log("   └ 全量留痕结束")
            log("┌" + "─" * 50)
            log("│ 【ing 全文】")
            log("├" + "─" * 50)
            log("│ （mock 对撞正文，不应出现在后台）")
            log("└" + "─" * 50)
            log("┌" + "─" * 50)
            log("│ 【view 全文】")
            log("├" + "─" * 50)
            log("│ （mock 显形正文，不应出现在后台）")
            log("└" + "─" * 50)
        stop_kind[name] = "自然"
        log(f"[{name}层] 停止：结构饱和度判定连续无新维度（mock）")

    ts = datetime.datetime.now()
    safe = "".join(c for c in question if c not in r'\/:*?"<>|').strip()[:20] or "mock"
    out = OUTPUTS / f"{ts:%Y%m%d_%H%M%S}_{safe}.md"

    body = f"""# 元 DGTF · {question}

**时间**: {ts.isoformat()}

**分层目标**：
  - 修行层（显形过程 · objective=manifest）：& 4 / 线头 5 / 悬置 1 / 探针 3
  - 研究层（逼近真理 · objective=truth）：覆盖率 41% · distance 0.4
  - 对撞层（第三者 · objective=collision）：third ✓ · 张力 3
  - 元层（闭环清算 · objective=closure）：clean True · 未交代 0 类

**调度**：{rounds_run['修行']}圈 → {rounds_run['研究']}圈 → {rounds_run['对撞']}圈 → {rounds_run['元']}圈

**停止**：自然 4 层 / 被截断（体力耗尽）0 层

**实际停圈**：修行 {rounds_run['修行']} 圈 / 研究 {rounds_run['研究']} 圈 / 对撞 {rounds_run['对撞']} 圈 / 元 {rounds_run['元']} 圈

**并行模式**：模式 B（mock）

**取向**：boundary（mock）

**可判定性**: partial

**理由**: 这是 mock 产物，仅用于应用链路验证，不代表任何真实结论。

## 一、这是 mock 产物

本文件由 `dgtf_app/mock_engine.py` 生成，用于验证 Web 应用的
「提交 → 实时日志 → 完成 → 历史检索」整条链路，**不消耗任何 API 额度**。

## 二、原问题

{question}
"""
    OUTPUTS.mkdir(exist_ok=True)
    out.write_text(body, encoding="utf-8")
    log(f"[mock] 产物已落盘：{out.name}")
    log("[mock] 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
