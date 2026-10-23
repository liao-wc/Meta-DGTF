# 依赖与模型安全

## App 运行时

App server 主要使用 Python 标准库，不把本地模型权重打进仓库。

本地 BGE embedding 服务需要：

    torch
    transformers

安装与锁定以 local_model/envs/dgtf_llm_env 的实际环境为准：

    local_model\envs\dgtf_llm_env\Scripts\python.exe -c "import torch,transformers;print(torch.__version__,transformers.__version__)"

## 依赖原则

- 不提交模型权重、训练环境、运行态日志。
- 新增第三方依赖时，必须写明用途、版本和来源。
- 依赖升级先跑 CI 和本地门禁。
- 不使用来历不明的 fork 或非官方 wheel。
- GitHub Actions 必须固定到完整 commit SHA。

## 本地模型来源

见 local_model/MODEL_SOURCES.md。

## 模型加载风险

transformers 的 trust_remote_code=True 会执行模型仓库自带 Python 代码。
只应对可信来源开启；下载后应校验 revision 与 SHA256，不要直接加载陌生模型仓库。

## 发布包

release-artifact 工作流：

- 排除 local_model/models、local_model/envs
- 排除 dgtf_memory、outputs、cache、archive
- 生成并附上 SHA256SUMS
