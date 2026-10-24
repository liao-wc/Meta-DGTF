# App V2.0.15 发布说明（补丁）

日期：2026-10-25
类型：PATCH（App；引擎 V2.2.2 不变）

## 新功能：质量策略选择

把“通用任务是否注入项目背景/是否联网接地”的取舍暴露为任务启动策略：

- auto（默认）：按问题相关性注入背景；通用任务默认 web off；
- stable：不注入项目背景、默认不联网，约 5.2min，answer_ready=true，answer_quality 可能 unverified；
- web：通用事实题自动 web=on（fused_ground_web），约 5.3min，verified 概率高但官方源抓取有波动；
- verified：强制注入项目背景（较慢，约 26min 级），质量更稳。

接口：
- POST /api/tasks 新增 quality_policy；
- 响应回显 quality_policy；
- 前端运行栏新增“质量策略”下拉。

默认保持 auto/stable 的稳定档，避免联网抓取波动影响默认质量门。

## 验证

- 真实任务 cmd 检查：stable→--web off、web→--web on、verified→项目背景前缀；
- 三者均 --parallel B / --behavior-fusion off / --rounds 0:1...；任务创建后立即取消，无残留。
