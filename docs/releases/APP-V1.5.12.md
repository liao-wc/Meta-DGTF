# APP V1.5.12 发布说明

## 主题

引擎 v1.30.1 质量门接入与上线 P1 收束。

## 改动

- 引擎升级 v1.30.1：事实卡闭环收紧、process_ledger citations 修正、md 决策动作读 packed、bench 结构化 rubric。
- app 质量 API 增加 answer_ready/answer_quality/process_ready/standard_all/answer_summary/decision_actions/not_do。
- V2 模板统计按 run/template 去重并使用全量窗口，推荐结果不再随 limit 漂移。
- 上线安全修复：启动日志不打印口令、POST 先鉴权再读 body、32MB JSON/200MB 上传上限、孤儿回收 app_pid 归属、Git 提交范围收紧、真实任务默认 3600s 超时。
- 版本/静态资源 1.5.12；依赖链审计同步。

## 验证

- fast_gate 12/0
- selftest 371/0
- 依赖链审计 78/0
- app HTTP 200；engine 1.30.1；app 1.5.12

## 边界

- git push/force、密钥、账户/ACL、不可逆外部操作仍保留人工确认。
- 事实门更严格后，部分旧产物会从 answered 降为 needs_evidence。
