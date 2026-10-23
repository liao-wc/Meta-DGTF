# 仓库分类与自动管理

DSH 把仓库按逻辑分类管理：

| 分类 | 用途 |
|---|---|
| app | 本地 Web 工作台、启动器、前端 |
| engine | 元DGTF 引擎、dgtf_v2、评测、配置 |
| local_model | 本地模型训练/服务/调度相关 |
| docs | 设计、发布、报告、审计 |
| ops | 启动/部署/仓库管理脚本 |
| runtime | 运行态状态（默认不应提交） |
| archive | 临时目录/历史 scratch |
| legacy | 根目录历史脚本/产物 |
| other | 未归类 |

## 自动操作

- 每次 push / PR 运行 GitHub Actions `repo-classification`。
- 自动生成 `reports/repo_classification.md` 与 `.json`。
- CI 对 `runtime`、`archive` 被 tracked 给出警告。
- 本地 commit 后，`.git/hooks/post-commit` 自动运行 `dsh_repo_manage.ps1` 推送已提交内容。

## 本地命令

```powershell
python scripts/dsh_repo_classify.py classify
python scripts/dsh_repo_classify.py check
python scripts/dsh_repo_classify.py status
```

## 边界

当前分类**不移动物理路径**，避免破坏 元DGTF 引擎/应用的 import 与历史脚本引用。后续归档需要单独做兼容性验证。

分类清单：

```text
.github/repo_manifest.json
```
