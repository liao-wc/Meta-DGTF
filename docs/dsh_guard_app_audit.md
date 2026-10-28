# DSH 守护接入 App 全方位检查

时间：2026-10-26

## 接入内容

守护任务新增固定段 【App 全方位检查】，每轮巡检必须：

1. 运行 python scripts/app_full_check.py --json-out docs/app_audit_latest.json；
2. 检查鉴权、路径穿越、静态资源缓存版本、核心 API、任务队列、提案、
   活动状态、V2、本地模型服务、服务日志、V2 auto-apply dry-run；
3. 失败项按最小安全改动修复，并重跑 app_full_check / fast_gate / selftest；
4. 不能安全修复的写入人工确认风险；
5. 报告必须包含 App 检查项、失败项、修复项与验证结果。

## 检查脚本

scripts/app_full_check.py：

- 只读 HTTP/文件检查；
- 可选 --json-out 落盘；
- 任一硬失败 exit 1；warning 不阻断；
- 包含守护接线自检：server.py 必须含 App 全方位检查段与 app_full_check.py 引用。

## 当前结果

- App 检查：PASS，30 项
- 路径穿越：401/404 拦截
- 无 token：401
- 静态资源：200 且缓存版本一致
- 服务日志：无 Traceback
- 任务队列：0
- V2 auto-apply dry-run：PASS
