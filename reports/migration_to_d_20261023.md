# 项目迁移到 D 盘记录（2026-10-23）

## 新路径

```text
D:\元DGTF-多模并行架构
```

旧路径 `C:\Users\18432\Desktop\元DGTF-多模并行架构` 的源码已迁移；仅剩 54 个被系统进程占用的运行态缓存文件，重启或关闭占用后可删除。

## 本地模型归类

```text
D:\元DGTF-多模并行架构\local_model\models
  bge-small-zh-v1.5
  DeepSeek-R1-Distill-Qwen-1.5B
  DeepSeek-R1-Distill-Qwen-1.5B-merged-v1
  Qwen2.5-0.5B-Instruct
  Qwen2.5-0.5B-Instruct-merged-v1
  Qwen2.5-1.5B-Instruct

D:\元DGTF-多模并行架构\local_model\envs\dgtf_llm_env
```

模型约 14.08GB，环境约 4.43GB；均已加入 `.gitignore`，本地保留不入库。

## 路径更新

- server.py、rag_embed_service.py、build_rag_index.py 的默认模型/环境路径已改为 D 盘项目内路径。
- llm_predict.py、eval_llm_lora.py、merge_lora.py、rag_query.py 等默认路径已更新。
- llm_sft adapter 配置中的 base_model 路径已更新。
- 桌面快捷方式、快速入口、计划任务已改为 D 盘路径。

## 验证

```text
verify_project_paths.py: PASS 12/12
App health: HTTP 200 / app 1.5.24 / engine 1.30.4
fast_gate: PASS 12/0
selftest: PASS 371/0
local model: llm_predict.py 返回合法 JSON
Git remote main = 15a03c3 (迁移提交)
```

## 使用

```powershell
cd "D:\元DGTF-多模并行架构"
.\scripts\start_app.cmd
```

或双击桌面 `元DGTF-个人工作台`。
