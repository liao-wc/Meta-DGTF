# App V2.0.9 发布说明（补丁）

日期：2026-10-24
类型：PATCH（App / 本地模型服务；引擎 V2.2.2 不变）

## 本地模型优化（承接「本地模型帕累托最优」）

**BGE embedding 文本级 LRU 缓存**：
- 相同文本重复请求直接命中缓存（向量逐位一致），只对未命中文本走模型推理；
- 缓存上限默认 1024 条（环境变量 DGTF_EMBED_CACHE_MAX 可调），/health 返回 hits/misses/size；
- 实测：同一文本首访冷 ~240ms（含 CUDA 预热），命中 p50 ~13ms；3 条批量冷 59.2ms → 热 20.8ms；
- 质量不变（缓存向量就是原向量），属于纯时延改进。

## 变更

- APP_VERSION 2.0.8 → 2.0.9；静态缓存串 ?v=2.0.9-dshlive；
- 服务重启方式：杀掉 rag_embed_service 旧进程后由 App 的 _ensure_rag_embed 自动拉起（或手工启动）。

## 验证

- py_compile 0；/health cache 统计正常（hits/misses 递增）；
- App 重启后 health=2.0.9、engine=2.2.2；selftest 371/0。

## 边界

- 缓存只优化重复文本的时延，不改变 embedding 语义；
- 不涉及引擎、任务数据与会话数据。
