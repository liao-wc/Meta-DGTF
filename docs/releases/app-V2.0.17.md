# App V2.0.17 发布说明（补丁）

日期：2026-10-25
类型：PATCH（App；引擎 V2.2.2 不变）

## 变更：质量策略全自动

按要求移除前端“质量策略”可选按钮，改为后端自动判定：

- 项目相关问题（含 Meta-DGTF/DGTF/四层/EML/DSH 等项目标记）→ auto:verified（注入项目背景，默认 web off）；
- 其它通用题 → auto:stable（不注入背景、默认 web off）；
- 联网/失败重试改为 opt-in：只有 API 显式传 quality_policy=web/web-retry（或 web=on/fused_ground_web）才启用。

接口仍保留 quality_policy 字段，默认 auto；前端不再发送选择值。响应回显实际生效策略（auto:verified / auto:web-retry / auto:stable）。

## 验证

- py_compile 0；App 2.0.17 重启；
- 三类问题 cmd 检查：项目题注入背景、通用事实题与 why 题均 --web off；
- 前端已无 quality-policy 控件。
