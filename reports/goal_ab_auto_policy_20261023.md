# auto_policy vs profile 质量/成本 A/B

同一问题：Python 中 len() 函数的作用是什么？
- 引擎：1.30.4
- 配置：方案F-帕累托最优.yaml
- timeout：1200s
- max_tokens：200000
- 启动时间：2026-10-23 08:05:05

## 分组

| 分组 | task | 设置 | 结果 | 调用 | tokens | 时长 |
|---|---|---|---|---|---|---|
| Baseline | 20261023_080505_779173 | auto_policy=false（profile auto） | cancelled（超时，无 packed） | 116 | 1,073,702 | 1201.6s |
| Treatment | 20261023_080505_65ac4f | auto_policy=true，rounds=0:2,1:2,both:2,all:2 | done，verified | 90 | 881,364 | 1164.7s |

## 质量

Treatment：

```text
answer_ready=true
process_ready=true
layers_standard=4/4
answer_quality=verified
evidence_gaps=[]
depth=5200 chars / citations 6 / claims 4
```

Baseline 在 1200s 内未完成，被自动终止，只有 partial `.元.md`，没有 packed 质量结果。

## 结论

- 本组同题同配置下，auto_policy 完成并 verified；profile auto 超时无结果。
- auto_policy 少 26 次调用（-22.4%）、少 192,338 tokens（-17.9%），早结束 36.9s。
- 两组都接近 20 分钟上限；单靠 auto_policy 不能解决长任务耗时，仍需题型/预算自适应。
- 这是单题 A/B，不代表所有题型；结论需更多样本复核。
