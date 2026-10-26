# docs 索引（2026-10-27，Round 133）

> 本文件是 docs/ 的**当前入口**；历史轮次文档保留原样，数字以本索引列出的当前文档为准。

## 当前必读
| 文档 | 用途 |
|---|---|
| `README.md`（仓库根） | 总览/快速开始/验收命令 |
| `docs/最终交付说明-20261026.md` | 交付范围与验收口径（最新数字） |
| `docs/验收总览-20261026.md` | 一键验收 16 项明细 |
| `docs/最终综合报告-20261026.md` | 项目总报告（Round 1–113 + 后续增补） |
| `docs/known_boundaries_20261026.md` | 已知边界与轮次更新（§1–§25） |
| `docs/项目问题分析_20261027.md` | 基于 360 产物的项目问题分析与修复记录 |
| `docs/产物问题审计_20261027.md` | 产物逐项审计（P0–P3） |
| `docs/budget_ledger_20261026.md` | 预算台账（¥10 阶段上限） |
| `docs/ab_summary_20261027.md` | A/B 结果摘要（按 quality_band 分带） |
| `docs/releases/` | App 版本发布说明（app-V2.0.2 … V2.0.35） |
| `docs/patches/` | dual_judge local 补丁（已合并，历史证据） |

## 历史归档（勿引数字）
`final_status.md`、`goal_master_plan.md`、`v1240_*`、`ab_evidence_20261025.md`（按轮次历史记录）、
`app_engine_mapping.md`、`app_release_process.md` 等。

## 维护约定
- App 代码改动 → `python scripts/app_release.py --version <x> --cache-tag <tag>` + `app_version_check.py`；
- 引擎/判据改动 → `fast_gate.py` + `scripts/run_v2_tests.py` + `final_acceptance.py`；
- 新增文档须在本索引登记；数字以 CHANGELOG 与 known_boundaries 最新节为准。
