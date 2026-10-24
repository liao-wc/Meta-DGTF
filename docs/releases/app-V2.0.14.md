# App V2.0.14 发布说明（补丁）

日期：2026-10-25
类型：PATCH（App；引擎 V2.2.2 不变）

## 实验：通用事实题官方联网接地（opt-in）

实测质量-墙钟取舍：
- 无背景、无联网：310.7s / 588,205 tokens / quality 0.8374 / answer_quality=unverified；
- 无背景、加官方联网：320.8s / 765,619 tokens / quality 0.9783 / answer_quality=**verified**（search=5/fetch=3）；
- 有项目背景、无联网：1800s 超时 / 1.92M tokens（修复前长跑）。

实现：
- 结论：默认不启用。实测显式 web 可通过官方证据到 verified，但同一配置默认变体出现 no_official_source（quality 0.49/needs_evidence），联网质量不稳定；
- 保留 opt-in：fused_ground_web=true 时对通用事实题自动 web=on；显式 web 参数仍优先；
- 项目相关问题仍注入背景、不自动改 web；显式 web 参数优先；
- mode_fusion 响应增加 grounding_web 字段。

## 验证

- py_compile 0；App 2.0.14 重启；
- 待默认链路复跑确认（下一步）。


## 复跑数据（2026-10-25）

| 变体 | wall(s) | tokens | quality | answer_quality |
|---|---|---|---|---|
| 无背景、无联网 | 310.7 | 588,205 | 0.8374 | unverified |
| 无背景、显式联网（首次） | 320.8 | 765,619 | 0.9783 | verified |
| 无背景、默认联网（失败样本） | 280.4 | 731,619 | 0.4900 | needs_evidence（no_official_source） |
| 无背景、显式联网（重试） | 330.9 | 747,263 | 0.9263 | verified |
| 有项目背景、无联网 | 约1800超时 | 1.92M | 0.9598 | verified |

结论：事实题联网接地可把默认质量从 unverified 提升到 verified，但官方源抓取有波动，因此保持 opt-in（fused_ground_web=true 或显式 web=on），默认仍稳定 web off。
