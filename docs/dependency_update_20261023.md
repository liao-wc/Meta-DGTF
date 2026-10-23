# 依赖核对与同步（2026-10-23）

## Python 运行时

解释器：Python 3.13.15

| 包 | 锁定版本 | 本机实测 | 用途 |
|---|---|---|---|
| openai | 3.3.1 | 3.3.1 | LLM API |
| python-dotenv | 1.2.3 | 1.2.3 | .env 加载 |
| PyYAML | 6.0.3 | 6.0.3 | 配置 |
| jieba | 0.42.1 | 0.42.1 | 中文分词（可选） |

清单：`requirements.txt`

## 本地模型环境

目录：`local_model/envs/dgtf_llm_env`

| 包 | 锁定版本 | 本机实测 |
|---|---|---|
| torch | 2.14.1 | 2.14.1+cu126 |
| transformers | 5.20.2 | 5.20.2 |
| accelerate | 1.15.0 | 1.15.0 |
| numpy | 2.5.4 | 2.5.4 |
| peft | 0.21.2 | 0.21.2 |
| datasets | 5.1.0 | 5.1.0 |
| pandas | 3.0.6 | 3.0.6 |
| sentencepiece | 0.2.2 | 0.2.2 |

清单：`requirements-local-model.txt`

## 校验

    python -m pip check
    local_model\envs\dgtf_llm_env\Scripts\python.exe -m pip check

结果：No broken requirements found.

## GitHub Actions

当前固定依赖：

    actions/checkout v7.0.1
    actions/setup-python v5.6.0
    actions/dependency-review-action v4.7.1
    actions/download-artifact v8.0.2
    anchore/sbom-action v0.24.3
    sigstore/cosign-installer v4.1.2
    softprops/action-gh-release v2.2.1

- Actions 全部固定到完整 commit SHA。
- Dependabot 每周检查 `github-actions` 与 `pip` 生态。
- 新增运行时依赖时，同时更新 `requirements.txt` 与本文档。

## 门禁

依赖或路径调整后必须通过：

    python fast_gate.py
    python dgtf_app/selftest.py
    python -m py_compile dgtf_engine/dgtf_v2/engine/元DGTF-V2.0.0.py
