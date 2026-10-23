# Open Source Governance

## 维护者

- 仓库所有者：liao-wc
- 变更范围：App、Engine、Local Model、文档、运维与发布

## 版本

- App 使用 1.5.x
- Engine 使用 1.30.x
- 版本标签：app-vX.Y.Z、engine-vX.Y.Z
- 发布说明与 CHANGELOG 必须同步

## 发布门禁

发布前必须：

1. fast_gate 通过
2. selftest 通过
3. CI 通过
4. 仓库分类检查通过
5. 确认无新增密钥和运行态数据
6. 生成 SHA256SUMS

## 安全

- 使用 GitHub Private Vulnerability Reporting
- 不公开披露未修复漏洞细节
- 收到报告后 7 天内确认
- 密钥泄露立即轮换并清理历史

## 贡献

- 外部贡献先开 Issue
- PR 必须说明分类、验证和风险
- 不接受来源不明的模型权重、二进制或第三方代码
- 贡献者需确认有权提交相关代码和数据
