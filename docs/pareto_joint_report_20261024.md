# 三组件联动帕累托报告（2026-10-24）

生成：scripts/pareto_report.py（只读扫描 + 端点探测）

## 1. 引擎真跑（同日、四层）

| run | quality | tokens | calls | wall(s) | flags |
|---|---|---|---|---|---|
| 20261024_160020 | 0.9089 | 969376 | 89 | 1889.7 | 1 |
| 20261024_163455 | 0.9900 | 997457 | 107 | 1920.6 | 0 |
| 20261024_171058 | 0.9514 | 1210815 | 134 | 2116.9 | 0 |
| 20261024_175452 | 0.9800 | 1844908 | 154 | 2933.3 | 1 |
| 20261024_193452 | 0.9300 | 816983 | 106 | 782.6 | 2 |
| 20261024_195354 | 0.9458 | 1131199 | 115 | 2033.7 | 1 |

非支配点（quality/tokens/calls）：20261024_160020、20261024_163455、20261024_193452
墙钟三目标非支配点（quality/tokens/wall）：20261024_163455、20261024_193452

## 2. 组件读数（本机实测）

App 端点 p50：health 20.3ms、chats 16.7ms、events(full) 268.8ms
BGE：ok=True dev=cuda dim=512 cache={"size": 184, "max": 1024, "hits": 653, "misses": 184}
BGE embed：冷 30.4ms、热 p50 2.0ms

## 3. 联动选档（预算 1000000 tokens、质量 >= 0.90、wall <= 900.0s）

- 质量最大档：20261024_163455（满足预算与质量下限，质量最高）
- quality=0.9900、tokens=997457、calls=107、wall=1920.6s
- 联动选档（含 wall 约束）：20261024_193452（满足预算与质量下限，质量最高）quality=0.9300 tokens=816983 wall=782.6s
- 完整选档 JSON：{"row": {"id": "20261024_193452", "question": "为什么城市热岛效应在夜间比白天更明显？", "route": ["0", "1", "both", "all"], "rounds": {"0": 3, "1": 2, "both": 2, "all": 3}, "answer_ready": true, "process_ready": true, "answer_quality": "verified", "coverage": 0.5, "standard_all": true, "flags": ["ing_rephrased_direct(72%)", "ing_rephrased_direct(73%)"], "tokens": 816983, "calls": 106, "web_enabled": false, "tools_calls": 0, "elapsed": 782.6, "quality": 0.93}, "reason": "满足预算与质量下限，质量最高", "require_web": false, "app": {"health": {"p50_ms": 20.3, "max_ms": 499.5}, "chats": {"p50_ms": 16.7, "max_ms": 218.6}, "events_full": {"p50_ms": 268.8, "max_ms": 295.6}}, "local": {"health": {"ok": true, "model": "D:/Meta-DGTF-道生三阶模型/local_model/models/bge-small-zh-v1.5", "dev": "cuda", "dim": 512, "cache": {"size": 184, "max": 1024, "hits": 653, "misses": 184}}, "embed_cold": {"p50_ms": 30.4, "max_ms": 30.4}, "embed_hot": {"p50_ms": 2.0, "max_ms": 15.5}}, "joint_tokens": 816983, "joint_elapsed": 782.6, "joint_quality": 0.93}

## 4. 结论与边界

- 三目标（quality↑ / tokens↓ / wall↓）下非支配点仍是 run6 与 run7；
  run7 用 +30.9s / +28k tokens 换 +0.081 quality，J1 推荐 run7。
- App health/chats/events 与 BGE 查询均为毫秒级，相对引擎分钟级可忽略；
  联动瓶颈在引擎 LLM 墙钟，不在 App/BGE。
- 本地 BGE 质量（24 语料/10 查询）recall@1=1.0、MRR=1.0；LLM 质量代理弱，不进答案主路径。
- 边界：质量/成本为同日同题数据，跨题不可直接比较；3 层 route 负例已归档。
