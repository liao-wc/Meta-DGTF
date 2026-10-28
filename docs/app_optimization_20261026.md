# App 检查优化记录（2026-10-26）

## 1. V2 旧策略 route/rounds

问题：旧自动策略留下 route=1、rounds=4、template=1:r4，但 V2 shadow 同 run 内各模板 quality 相同，模板胜者不可识别。

处理：
- 备份 schedule_policy.json；
- route 恢复 0,1,both,all；
- rounds 恢复 2（保守）；
- template 清空；
- template_identifiable=false；
- auto_strategy/auto_template 保持冻结，auto_frozen_reason 留痕。

结果：
    route=0,1,both,all
    rounds=2
    template=''
    自动策略冻结

## 2. llm_predict.py 子进程回退缺失

问题：旧回退链固定尝试根目录 llm_predict.py，但文件不存在，产生虚假子进程错误。

处理：
- predict_route_rounds 在默认子进程回退时检查 llm_predict.py；
- 文件缺失则跳过 subprocess，直接 rules；
- 自检 T3 同步改为条件期望（缺失时 http→rules）。

结果：
    attempts = http, rules
    不再出现 llm_predict.py 不存在错误

### 2.1 补充：server.py 侧同类问题（已修）

问题：server.py 的 `_llm_predict_local` 仍直接 `subprocess` 跑根目录 `llm_predict.py`（该文件已在 `archive/legacy_root/`），
且不做存在性检查 ⇒ `/api/schedule/llm/predict|apply`、`auto_llm`、hybrid 全部只回「无 JSON 输出」，真实原因被掩盖。
另 `_RAG_QUERY_SCRIPT = <root>/rag_query.py` 也已归档（该处原本有存在性检查、走 BM25 回退，无实际报错，仅补注释）。

处理：
- `_llm_predict_local` 改为「常驻服务 8772（stage=route）优先 → 仅当 llm_predict.py 存在才走子进程 → 否则明确报错」；
- 不可用时返回 `本地推理服务不可用（…）；llm_predict.py 已归档…` + 启动提示，不再假跑子进程；
- `_llm_status` 增加 `service` / `script` / `predict_ok`，状态不再虚报可用；
- `_LLM_PY/_LLM_MODEL/_LLM_BACKENDS` 默认值改为相对 `__file__` 定位（保留 DGTF_LLM_* 环境变量覆盖）。

结果：
    /api/schedule/llm/predict → source=http，route/rounds 正常返回
    llm_predict.py 缺失时 → 明确的 unavailable 原因 + hint

同批修复的同类「指向已移动/已升级文件」问题：
- `_proposal_project_context` 写死 `Meta-DGTF-V2.2.2.py` → 跟随 `engine_runner.find_engine()`；
  4 处按 `Meta-DGTF-V1.30.0.py` / `dgtf_v2/agent_bridge.py` 取的 mtime 判据恒为 0（静默失效），改为语义键 `engine` / `agent_bridge`；
- `_targeted_acceptance` 的引擎文件名白名单写死版本 → 改按路径前缀 / 文件名形态匹配；
- `_PROJECT_BRIEF`、engine_runner 兜底默认值、`scripts/verify_project_paths.py`、CI 编译步骤：版本改动态发现；
- `dgtf_app/rag_embed_service.py` BGE 模型默认路径写死盘符 → 改相对 `__file__`。

## 3. cancelled 历史任务

问题：App 内存任务列表中存在多条 cancelled 测试任务。

处理：
- 确认无 running/queued 任务后重启 App；
- 内存任务表清空；历史日志仍保留在 dgtf_app/runs 供审计。

结果：
    /api/tasks = 0

## 4. 附带优化

- /api/config 产物统计缓存 5s→30s；冷启动实测约 22ms；
- 本地 route 超时日志改为“预算过紧→规则回退”，不再误报“服务不可达”；
- V2 面板可见时 10s 刷新；
- V2 模板不可识别时禁止自动写全局策略。

## 验证

- App selftest：PASS 444 / FAIL 0
- node --check app.js：PASS
- py_compile server.py / daosheng_mode.py：PASS
- 鉴权：无 token 401
- 路径穿越：404
- 静态资源：200
- V2 auto-apply：不可识别时拒绝、策略文件未变

## 待人工确认

- 是否启用本地 route（需把 total_timeout_s 提到约 5–6s，并做 A/B）；
- 是否回滚旧 schedule_policy 中其他影子字段；
- 工作区未提交变更与 push 仍由用户确认。
