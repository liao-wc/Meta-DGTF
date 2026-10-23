# 本地模型目录

- `models/`：从 `D:\dgtf_models` 迁入的基座与合并模型。
- `envs/dgtf_llm_env/`：从 `D:\dgtf_llm_env` 迁入的 Python 3.13 训练/推理环境。

这两个目录体积大且与机器绑定，已加入 `.gitignore`，不进入 Git；运行时代码通过项目相对路径引用。

迁移日期：2026-10-23。

## 当前项目版本（V2.2.0）

- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.0.py
- App：V2.0.0（本次未改动）
- 本地模型运行时通过项目相对路径和 DGTF_LLM_* 环境变量引用
- 训练/评估/合并脚本：scripts/local_model/
- 微调产物：llm_sft/
- 模型来源与许可：MODEL_SOURCES.md
- 权重校验：MODEL_CHECKSUMS.md

V2.2.0 不训练模型；行为级融合只作用于调度/阈值，不改变本地模型权重。
本地模型依赖检查：

    local_model\envs\dgtf_llm_env\Scripts\python.exe -m pip check
