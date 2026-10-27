# docs 索引（2026-10-27，Round 162 收束同步）

> 本文件是 docs/ 的**当前入口**；历史轮次文档保留原样，数字以本索引、`docs/项目状态快照_20261027.md`、
> `CHANGELOG.md` 与 `docs/known_boundaries_20261026.md` §0 为准。

## 当前必读
| 文档 | 用途 |
|---|---|
| `docs/项目状态快照_20261027.md` | **一页看全**：验收/运行态/成果/边界/复跑命令 |
| `docs/全链路检查_20261027.md` | **全链路检查报告**：静态/路径/门禁/服务/App/产物（离线 PASS） |
| `README.md`（仓库根） | 总览/快速开始/验收命令 |
| `docs/最终交付说明-20261026.md` | 交付范围与验收口径（已同步 18/18） |
| `docs/验收总览-20261026.md` | 一键验收 18 项明细（已同步 Round 162） |
| `docs/最终综合报告-20261026.md` | 项目总报告（Round 1–161 + 收束同步） |
| `docs/known_boundaries_20261026.md` | 已知边界（§0 当前状态 + §1–§51 轮次快照） |
| `docs/项目问题分析_20261027.md` | 问题分析与修复记录（§1–§三十六） |
| `docs/budget_ledger_20261026.md` | 预算台账（¥20 阶段：已用 ≈¥19.5、剩余 ≈¥0.5） |
| `docs/ab_summary_20261027.md` | A/B 结果摘要（最新 rows=166 / questions=83 / verified=125） |
| `docs/local_model_daosheng.md` | 本地模型文档（顶部 2026-10-27 同步段；历史轮次保留） |
| `docs/产物问题审计_20261027.md` | 产物逐项审计（Round 128 历史快照，数字以最新快照为准） |
| `docs/releases/` | App 版本发布说明（app-V2.0.2 … V2.0.35） |
| `docs/patches/` | dual_judge local 补丁（已合并，历史证据） |

## 历史归档（勿引数字）
`final_status.md`、`goal_master_plan.md`、`v1240_*`、`ab_evidence_20261025.md`（按轮次历史记录）、
`app_engine_mapping.md`、`app_release_process.md` 等。

## 维护约定
- App 代码改动 → `python scripts/app_release.py --version <x> --cache-tag <tag>` + `app_version_check.py`；
- 引擎/判据改动 → `fast_gate.py` + `scripts/run_v2_tests.py` + `final_acceptance.py`；
- 新增文档须在本索引登记；每次收束/版本变更同步更新 `docs/项目状态快照_*.md` 与本文索引。
