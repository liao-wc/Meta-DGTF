# App V2.0.23 发布说明（补丁）

日期：2026-10-25
类型：PATCH（App；引擎 V2.2.2 不变）

## 变更：联网检索/爬取策略全自动

- 项目相关问题 → auto:verified（注入项目背景，web off）；
- 通用事实题 → auto:web-retry：自动 web on，首次 unverified/needs_evidence 自动补跑一次 web；
- 其它通用题 → auto:stable（不注入背景、默认 web off）；
- 已有已验证答案/语义缓存优先，命中时零 LLM；
- 前端无策略按钮，全部后端自动判定。

## 验证

- py_compile 0；App 2.0.23 重启；
- 通用事实题默认 web on、quality_retry=true；
- why 题仍 web off；项目题注入背景。
