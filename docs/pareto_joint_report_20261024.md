# 三组件联动帕累托报告（2026-10-24）

生成：scripts/pareto_report.py（只读扫描 + 端点探测）

## 1. 引擎真跑（同日、四层）

| run | quality | tokens | calls | wall(s) | flags |
|---|---|---|---|---|---|
| 20261024_160020 | 0.9089 | 969376 | 89 | 1889.7 | 1 |
| 20261024_163455 | 0.9900 | 997457 | 107 | 1920.6 | 0 |
| 20261024_171058 | 0.9514 | 1210815 | 134 | 2116.9 | 0 |
| 20261024_175452 | 0.9800 | 1844908 | 154 | 2933.3 | 1 |

非支配点：20261024_160020、20261024_163455

## 2. 组件读数（本机实测）

App 端点 p50：health 5.3ms、chats 3.8ms、events(full) 313.5ms
BGE：ok=True dev=cuda dim=512 cache={"size": 4, "max": 1024, "hits": 16, "misses": 4}
BGE embed：冷 107.3ms、热 p50 1.9ms

## 3. 联动选档（预算 1000000 tokens、质量 >= 0.90）

- 推荐：20261024_163455（满足预算与质量下限，质量最高）
- quality=0.9900、tokens=997457、calls=107、wall=1920.6s
- 联动选档结果：{"row": {"id": "20261024_163455", "question": "为什么城市热岛效应在夜间比白天更明显？", "route": ["0", "1", "both", "all"], "rounds": {"0": 3, "1": 2, "both": 2, "all": 3}, "answer_ready": true, "process_ready": true, "answer_quality": "verified", "coverage": 0.9, "standard_all": true, "flags": [], "tokens": 997457, "calls": 107, "web_enabled": false, "tools_calls": 0, "elapsed": 1920.6, "quality": 0.99}, "reason": "满足预算与质量下限，质量最高", "require_web": false, "app": {"health": {"p50_ms": 5.3, "max_ms": 572.2}, "chats": {"p50_ms": 3.8, "max_ms": 337.2}, "events_full": {"p50_ms": 313.5, "max_ms": 352.2}}, "local": {"health": {"ok": true, "model": "D:/Meta-DGTF-道生三阶模型/local_model/models/bge-small-zh-v1.5", "dev": "cuda", "dim": 512, "cache": {"size": 4, "max": 1024, "hits": 16, "misses": 4}}, "embed_cold": {"p50_ms": 107.3, "max_ms": 107.3}, "embed_hot": {"p50_ms": 1.9, "max_ms": 2.4}}, "joint_tokens": 997457, "joint_elapsed": 1920.6, "joint_quality": 0.99}

## 4. 结论与边界

- 三目标（quality↑ / tokens↓ / wall↓）下非支配点仍是 run6 与 run7；
  run7 用 +30.9s / +28k tokens 换 +0.081 quality，J1 推荐 run7。
- App health/chats/events 与 BGE 查询均为毫秒级，相对引擎分钟级可忽略；
  联动瓶颈在引擎 LLM 墙钟，不在 App/BGE。
- 本地 BGE 质量（24 语料/10 查询）recall@1=1.0、MRR=1.0；LLM 质量代理弱，不进答案主路径。
- 边界：质量/成本为同日同题数据，跨题不可直接比较；3 层 route 负例已归档。
