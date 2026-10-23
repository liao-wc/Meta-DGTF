# GitHub 仓库管理

## 分类

- App：`dgtf_app/`、启动器
- Engine：`dgtf_engine/dgtf_v2/`、`元DGTF-V*.py`、`bench/`
- Local Model：`local_model/`、`llm_sft/`
- Docs：`docs/`、`reports/`
- Ops：`.github/`、`scripts/`

## 自动流程

- `repo-classification`：分类报告
- `ci`：App/Engine/Local Model 轻量检查
- `release-artifact`：tag 时打包发布源码（排除本地模型权重）
- `post-commit` + `dsh_repo_manage.ps1`：提交后自动推送

## 部署边界

GitHub 仓库保存源码和发布包；App 是 Python 服务，需要服务器/容器/隧道运行，GitHub Pages 不能直接运行该后端。
