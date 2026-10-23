# len() 质量回放（2026-10-22）

- run：20261022_194312
- output：20261022_195840_Python中len函数的作用
- calls：71
- tokens：689780
- 耗时：约 15 分钟

## 原始产物

- process_ready=true，四层 4/4。
- fact_card.answer 错选成 list() 页面；answer_summary.answer 为空；answer_quality=needs_evidence。
- gaps：uncovered:函数的作用（中文泛化词把英文官方证据误判未覆盖）。

## 当前代码重算

用同一份 packed 证据，按新版 `answer_from_evidence` / `question_terms` 重算：

```text
gaps = []
answer = The `len()` function returns the number of items in an object. ...
official = 16 / independent = 27
```

在证据与过程门不变的前提下，当前代码会把该题判为：

```text
answer_quality = verified
answer_ready = true
process_ready = true
```

说明：这是同一份证据的**回放**，不是重新调模型生成的产物；下次真实跑应直接产出正确短答。

## 修复点

1. 去掉“函数/作用/状态码”等泛化词作为必覆盖事实项，避免中文泛化词误伤英文官方证据。
2. 答案相关性加权：ASCII 技术词加权、开头定义加权，len 定义段胜过 list 页面。
3. URL 类问题仍强制答案包含 URL。
