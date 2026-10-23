# Contributing

1. 按分类创建 Issue：App / Engine / Local Model / Docs / Ops / Deploy。
2. 变更前先复现并记录证据。
3. PR 必须通过 CI 和仓库分类检查。
4. 不提交 `dgtf_memory/`、模型权重、`.env`、TLS 私钥和本地日志。
5. 版本与 CHANGELOG 同步更新。
6. 提交必须使用 DCO sign-off：`git commit -s`，表示你有权提交该代码/数据。
7. 提交第三方代码或模型相关内容前，先更新 `THIRD_PARTY_NOTICES.md`。
8. 安全相关问题不要开公开 Issue，使用 GitHub Private Vulnerability Reporting。
9. 不接受来源不明的二进制、模型权重、数据集或大段第三方文本。
