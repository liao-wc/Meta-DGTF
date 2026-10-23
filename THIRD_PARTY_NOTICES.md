# Third-Party Notices

本仓库代码采用 Apache License 2.0，详见 LICENSE 与 NOTICE。
以下组件不因本项目 Apache-2.0 许可证而改变其自身许可证。

## 本地模型（权重不随本仓库分发）

| 组件 | 目录 | 上游许可证（请以实际 model card 为准） |
|---|---|---|
| BGE small zh v1.5 | local_model/models/bge-small-zh-v1.5 | MIT（BAAI/bge-small-zh-v1.5） |
| Qwen2.5-0.5B-Instruct | local_model/models/Qwen2.5-0.5B-Instruct | Apache-2.0（Qwen/Qwen2.5-0.5B-Instruct） |
| Qwen2.5-1.5B-Instruct | local_model/models/Qwen2.5-1.5B-Instruct | Apache-2.0（Qwen/Qwen2.5-1.5B-Instruct） |
| DeepSeek-R1-Distill-Qwen-1.5B | local_model/models/DeepSeek-R1-Distill-Qwen-1.5B | MIT（deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B） |
| LoRA / merged 模型 | llm_sft、*-merged-v1 | 继承对应上游模型许可证 |

使用或再分发模型权重前，必须阅读并遵守上游仓库的 LICENSE 和 model card。

## Python 运行时（可选，本地环境）

| 组件 | 许可证 |
|---|---|
| Python | PSF License |
| openai | MIT |
| python-dotenv | BSD-3-Clause |
| PyYAML | MIT |
| jieba | MIT |
| PyTorch | BSD-3-Clause |
| Transformers | Apache-2.0 |
| Accelerate | Apache-2.0 |
| PEFT | Apache-2.0 |
| Datasets | Apache-2.0 |
| pandas | BSD-3-Clause |
| sentencepiece | Apache-2.0 |
| NumPy | BSD-3-Clause |

## GitHub Actions

工作流使用 actions/checkout、actions/setup-python、actions/dependency-review-action、
actions/download-artifact、anchore/sbom-action、sigstore/cosign-installer、
softprops/action-gh-release。它们遵循各自仓库许可证，不属于本仓库再分发内容。

## 第三方数据与文档

本仓库的文档、benchmark 题目、截图和历史归档可能包含第三方材料。
发布或再分发前，请确认其版权和许可；无法确认的内容不要对外发布。

本文件不构成法律意见。
