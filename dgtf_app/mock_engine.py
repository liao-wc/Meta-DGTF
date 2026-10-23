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
    # ── 启动信息（★ R37：日志开头须先亮「载入调度配置」等，再进层循环）──────────
    #   格式**照抄真引擎**（`元DGTF-V1.23.22.py` 开头那段）—— 应用层按「名称：内容」
    #   规范渲染（蓝标签 + 绿内容、整行居中），冒号一律全角「：」、行首不加缩进。
    #   这段落在 `layers.split_log()` 的 `__head__` 桶里（第一行层界之前），
    #   app.js 的 `renderTasks` 会把它渲染成日志开头块（`.rl-boot`）。
    log("载入调度配置：dgtf_config.yaml（出厂） + 无用户覆盖")
    log("调度：0 → 1 → both → all")
    log("螺旋上限（每层圈数）：{'0': 3, '1': 3, 'both': 2, 'all': 1}")
    log("并行模式：严格串行（来自配置）")
    log("回来通道：content、context、self")
    log("运行期总控：联网 关 | 思考 关（0 个环节开档 / 25 关）| 强度 low")
    log("落盘目录：outputs/")
    log("")
    log("[mock] 问题：" + question)
    log("[mock] 引擎：mock_engine（不调用任何 API、零花费）")

    stop_kind = {}
    rounds_run = {}
    _calls = 0
    _toks = 0
    for name, _tag in _LAYERS:
        rounds = random.randint(1, 3)
        rounds_run[name] = rounds
        for r in range(1, rounds + 1):
            # 与真引擎同款的层进度条（分层就靠这行切）
            log("")
            log("━" * 60)
            log(f"━━━ {name} · 第 {r}/{rounds} 圈 · 摊开 · view ━━━")
            log("━" * 60)
            log(f"   （mock）{name}层第 {r} 圈：锚点重述 → 阴阳展开 → 对撞 → 沉淀 & → 探针回归")
            # ★ 补几行**真跑格式**的日志（轮次标记 / 名称：内容同行 / [N]+属性 块）——
            #   让应用层的「日志语义排版」在验收台里也被真实覆盖（只靠 mock 老格式测不到）。
            log(f"   ↻ 第 {r}/{rounds} 圈 · 摊开")
            log("   🧭 四象限对齐：low（匹配率 11%，1 对张力）")
            log("   [1] （mock）候选一：用来验「序号 + 属性 + 内容」合并")
            log("       属性=1◈（来源：阳展开，非判断）")
            log("       位置=1（mock）")
            # 模拟 v1.23.21 的实时读数列；放在进度条**之后**，好归到本层
            _calls += random.randint(2, 5)
            _toks += random.randint(2000, 6000)
            log(f"[tok] calls={_calls} tokens={_toks}")
            # ★ [照抄真引擎 · 第六期] 候选产出率偏低时的告警行（真引擎的 `vp`
            #   只在 `collapsed` 时打这一行，缩进 3 空格 + `⚑`）。第 1 圈没有
            #   上一圈可比 ⇒ 真引擎**不表态**，mock 同样只在 r>=2 时打。
            if r >= 2:
                log("   ⚑ 候选产出率偏低 0.00（最高相似 1.00）——这一圈基本是复述，"
                    "对偶判断可能在为无信息量付费（mock）")
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

## 附：逐层明细

### 修行层 `0`

（mock）修行层明细：& 4 / 线头 5 / 悬置 1。

【各环节量化】（零成本读数；缺输入一律不给）
  · 锚点保真度（restate_fidelity）：ok（coverage=0.93、ratio=0.9、fidelity=0.9）
  · 阴阳分歧度（yin_yang_divergence）：ok（divergence=0.56）
  · ing 语义密度（ing_density）：ok（value=0.82、chars=1084）
  · 候选产出率（candidate_yield）：collapsed（n_new=0、new_ratio=0.0、max_sim=1.0）

### 研究层 `1`

（mock）研究层明细：覆盖率 41%。

【各环节量化】（零成本读数；缺输入一律不给）
  · 锚点保真度（restate_fidelity）：ok（coverage=0.88、ratio=0.9、fidelity=0.9）
  · 阴阳分歧度（yin_yang_divergence）：ok（divergence=0.42）
  · ing 语义密度（ing_density）：ok（value=0.79、chars=962）

### 对撞层 `both`

（mock）对撞层明细：第三者 ✓ / 张力 3。

【各环节量化】（零成本读数；缺输入一律不给）
  · 锚点保真度（restate_fidelity）：ok（coverage=0.90、ratio=0.9、fidelity=0.9）
  · 阴阳分歧度（yin_yang_divergence）：ok（divergence=0.61）
  · ing 语义密度（ing_density）：ok（value=0.84、chars=1203）
  · 候选产出率（candidate_yield）：ok（n_new=2、new_ratio=0.67、max_sim=0.55）

### 元层 `all`

（mock）元层明细：clean True / 未交代 0 类。

【各环节量化】（零成本读数；缺输入一律不给）
  · 锚点保真度（restate_fidelity）：ok（coverage=0.95、ratio=1.0、fidelity=1.0）
  · ing 语义密度（ing_density）：ok（value=0.86、chars=744）
"""
    OUTPUTS.mkdir(exist_ok=True)
    out.write_text(body, encoding="utf-8")
    log(f"[mock] 产物已落盘：{out.name}")
    log("[mock] 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
