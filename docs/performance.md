# 性能与链路延迟（app V1.4.0）

## 四层真跑

| 任务 | 预算 | calls | tokens | 耗时 | 四层收尾 |
|---|---:|---:|---:|---:|---|
| 20261021_142938 | 1.2M | 139 | 1,168,936 | 2525.7s | all 层 token 截断 |
| 20261021_155104 | 2.0M | 179 | 1,492,368 | 1788.3s | 四层自然收尾 |
| 20261021_183508 | 2.0M | 160 | 1,402,738 | 1895.6s | 四层进入；1 层空转，质量覆盖 0.5169 |

- 2M 真跑吞吐约 834 tokens/s（含 API 延迟）；四层全部进入；
- all 层 4 圈自然停止；coverage 0.9766；
- 成本约 ¥6.02；
- 结论：预算提高到 2M 后四层可自然收尾，无需截断；引擎未改。

## app 关键接口（本机，采样）

| 接口 | 延迟 |
|---|---:|
| /api/project/context（BGE+BM25） | 50ms |
| /api/quality/<task> | 25ms |
| /api/schedule/policy | 20ms |
| /api/dsh/chats | 7ms |
| /api/schedule/llm/status | 3ms |
| /api/consistency | 184ms |
| /api/health（首调冷启动） | 632ms |

## 优化点

- 项目上下文文档按 mtime/size 缓存；
- BGE embedding 常驻服务 127.0.0.1:8771，避免每任务加载模型（10s → 0.3s）；
- 单实例锁避免重复启动 embedding 抢占 GPU；
- 查询向量缓存；
- 引擎 side 无改动，2M 真跑自然收尾。
