# App V2.0.12 发布说明（补丁）

日期：2026-10-25
类型：PATCH（App；引擎 V2.2.2 不变）

## 修复：M4 auto-fused 选档被 behavior fusion 覆盖

真实链路实测发现：App 默认任务由 M4 选中 B（web off / quality 优先），
但引擎 behavior_fusion=auto 随后把 web / thinking 强制打开，实际变成
“联网 + thinking high”，墙钟和成本显著上升。

修复：
- M4 选档后显式落引擎参数：behavior_fusion=off、web、thinking、effort，
  用户显式参数优先（setdefault）；
- 自动 policy 的四层圈数不再覆盖 M4 选档（auto_fused 时跳过 auto_policy 圈数）；
- engine_runner 新增 behavior_fusion 参数透传（--behavior-fusion）；
- /api/tasks 响应 mode_fusion 增加 applied_opts。

## 验证

- py_compile 0；App 2.0.12 重启；
- 真实任务启动后立即读 cmd：--parallel B / --web off / --behavior-fusion off，
  且无 auto_policy 的 0:4 圈数强制；
- 任务创建后立即取消，无残留运行进程；
- selftest 371/0。
