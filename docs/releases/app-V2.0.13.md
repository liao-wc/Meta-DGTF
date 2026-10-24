# App V2.0.13 发布说明（补丁）

日期：2026-10-25
类型：PATCH（App；引擎 V2.2.2 不变）

## 修复：M4 默认链条圈数/背景失控

真实默认任务（M4=B，behavior_fusion=off，web=off）实测：
- 无 rounds 提示：5/6/4/7 圈、154 calls、1.92M tokens、wall 1613.8s；
- 修复后给 0:1,1:1,both:1,all:1 提示仍超 1800s 超时（项目背景注入把 1+1 拖成四层长跑）。

修复：
1. M4 选档后显式设置 rounds 提示（用户显式 rounds 优先），applied_opts 增加 rounds；
2. 项目背景按相关性注入：仅当问题含 Meta-DGTF/DGTF/道生三阶/四层/EML/DSH/route/rounds 等项目标记时才注入；
   通用任务不再注入无关背景（显式 project_context=true 仍可强制）；
3. behavior_fusion=off、web/thinking/effort 显式落参（沿用 2.0.12）。

## 验证

- py_compile 0；
- 真实任务 cmd 含 --rounds 0:1,1:1,both:1,all:1 / --web off / --behavior-fusion off；
- 通用任务 cmd 不含项目背景前缀；项目相关问题仍注入；
- 完整复跑：310.7s / 588,205 tokens / 90 calls / 2/2/2/2 圈；
  quality 0.8374、answer_ready=true、answer_quality=unverified、duty_short；
  对照修复前：1800s 超时、1.38M+ tokens、5/6/4/7 圈、quality 0.9598（带项目背景）；
- 结论：默认通用任务墙钟从超时降到 5.2min；项目相关问题仍注入背景，质量优先可显式传 project_context/rounds。
