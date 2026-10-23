# 本地模型目录

- `models/`：从 `D:\dgtf_models` 迁入的基座与合并模型。
- `envs/dgtf_llm_env/`：从 `D:\dgtf_llm_env` 迁入的 Python 3.13 训练/推理环境。

这两个目录体积大且与机器绑定，已加入 `.gitignore`，不进入 Git；运行时代码通过项目相对路径引用。

迁移日期：2026-10-23。
