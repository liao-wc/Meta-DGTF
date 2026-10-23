# -*- coding: utf-8 -*-
"""dgtf_app/mock_engine.py 同步：把真引擎新增的**量化读数**格式照抄过来。

## 为什么
mock 的注释写着「格式**照抄真引擎**」—— 但本轮真引擎新增了：
  ① 日志侧：候选产出率偏低时的 `⚑` 告警行；
  ② 产物侧：每层正文的【各环节量化】段。
mock 没有 ⇒ **承诺失效**（同一份格式两处定义 ⇒ 必然漂移）。

## 改什么（最小改动，不改变 mock 的结构）
  · 日志：第 ≥2 圈时打一行 `⚑` 告警（照抄真引擎 `vp` 的**缩进与措辞**）；
  · 产物：每层明细末尾加【各环节量化】小段（照抄真引擎的**键名+中文标签**格式）。
★ 只补「真引擎一定会出现」的那部分（告警只在 collapsed 时出现，mock 每层都
  mock 成 collapsed 是**伪造**吗？—— 不是：mock 本来就是**构造**的样例数据，
  作用是覆盖 app 的渲染路径，不是模拟真实分布。这里明确标注 `(mock)`。）
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "dgtf_app" / "mock_engine.py"

OLD1 = '''            log(f"[tok] calls={_calls} tokens={_toks}")
            time.sleep(0.6)'''
NEW1 = '''            log(f"[tok] calls={_calls} tokens={_toks}")
            # ★ [照抄真引擎 · 第六期] 候选产出率偏低时的告警行（真引擎的 `vp`
            #   只在 `collapsed` 时打这一行，缩进 3 空格 + `⚑`）。第 1 圈没有
            #   上一圈可比 ⇒ 真引擎**不表态**，mock 同样只在 r>=2 时打。
            if r >= 2:
                log("   ⚑ 候选产出率偏低 0.00（最高相似 1.00）——这一圈基本是复述，"
                    "对偶判断可能在为无信息量付费（mock）")
            time.sleep(0.6)'''

OLD2 = '''### 修行层 `0`

（mock）修行层明细：& 4 / 线头 5 / 悬置 1。

### 研究层 `1`

（mock）研究层明细：覆盖率 41%。

### 对撞层 `both`

（mock）对撞层明细：第三者 ✓ / 张力 3。

### 元层 `all`

（mock）元层明细：clean True / 未交代 0 类。
'''
NEW2 = '''### 修行层 `0`

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
'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\r\n") == 0, "mock_engine.py 应为 LF-only"
    s = raw.decode("utf-8")
    for old, new in ((OLD1, NEW1), (OLD2, NEW2)):
        assert s.count(old) == 1, "锚点命中 %d 次：%r" % (s.count(old), old[:40])
        s = s.replace(old, new, 1)
    P.write_bytes(s.encode("utf-8"))
    print("OK mock_engine.py 已同步，行数 %d" % s.count("\n"))


main()
