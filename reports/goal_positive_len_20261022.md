# 正向真实跑验收：len()

- task：20261022_201438_3f066b
- output：20261022_202654_Python中len函数的作用
- question：Python 中 len() 函数的作用是什么？
- llm_calls：69
- llm_tokens：652846
- 耗时：约 12 分钟

## 结果

```text
answer_ready = true
raw_answer_ready = true
process_ready = true
standard_all = true
layers_standard = 4/4
answer_quality = verified
evidence_gaps = []
depth = 4297 chars / citations 8 / claims 4
app score = 85.0 / grade A
```

答案：The `len()` function returns the number of items in an object. ...

这是第一条同时满足：真实模型跑、四层过程门、答案 verified、app A 级的正向样本。

## 说明

- 该跑使用本轮修复后的答案相关性/泛化词/首部加权代码。
- 软 flags 仍保留在接口里，但不再把 verified 对外质量压成 D。
