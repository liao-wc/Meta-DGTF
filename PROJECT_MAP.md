# 元DGTF 项目文件地图

| 分类 | 物理位置 | 说明 |
|---|---|---|
| app | `dgtf_app/`、`scripts/start_app.*`、`scripts/open_app.*` | Web 工作台与启动器 |
| engine | `dgtf_v2/`、`bench/`、`configs/`、根目录 `元DGTF-V*.py`、`fast_gate.py` | 引擎、评测、配置 |
| local_model | `local_model/models/`、`local_model/envs/dgtf_llm_env/`、`llm_sft/` | 本地模型权重、训练/推理环境、适配器 |
| docs | `docs/`、`reports/`、`audits/` | 设计、报告、审计 |
| ops | `scripts/`、`.github/` | 启动、部署、仓库管理 |
| runtime | `dgtf_memory/` | 运行态状态，默认不入库 |
| archive | `archive/` | 历史 scratch / 实验产物 |
| legacy | 根目录 `_*.py` 等历史脚本 | 保留兼容引用，逐步归档 |

## DSH 管理

```text
python scripts/dsh_repo_classify.py classify
powershell -File scripts/dsh_repo_manage.ps1
```
