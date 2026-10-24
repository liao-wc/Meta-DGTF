# App V2.0.22 发布说明（补丁）

日期：2026-10-25
类型：PATCH（App；引擎 V2.2.2 不变）

## 新机制：语义答案缓存

- 在精确缓存基础上，对同 web/parallel、近期 verified 的 packed 用本地 BGE 向量比较；
- 仅当问题向量余弦 ≥ 0.98 且问题类型一致（fact/非 fact）时复用，避免跨类型误用；
- 命中返回 cache_hit=true、semantic_cache=true、cache_similarity；
- 默认 use_semantic_cache=true，可 API 传 use_semantic_cache=false 关闭；精确缓存始终优先。

## 验证

- py_compile 0；App 2.0.22 重启；
- “1+1 等于几？”（多空格）请求显式 web，命中已验证 pack；
- 无匹配时回退精确缓存/正常启动引擎。
