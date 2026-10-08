# DGTF 收束前并行真跑结果 02:55 — 执行记录

## 2026-10-01 02:55 运行

批次 `v60_parallel.log` 显示「=== 结束 2026-10-01 02:52:01 ===」，3/3 全 OK（koan2 26.5min / koan1 33.5min / reclass 54.2min）。

三 run 结果（只读核对，未改文件未重跑）：
- 最终判定：koan1=partial、reclass=partial、koan2=partial（全部 partial）
- koan 进入（`不可判定结构拆解者` 角色）：**3/3 均 0 次**
- 分解分布：koan1 6 子问题(可判定3/不可判定3)、reclass 6(3/3)、koan2 6(4/2)——全走 hybrid 路径
- 复债痕迹（可判定性变更轨迹/重新挂账/可判定性转移成立）：**3/3 均 0 次**

结论：① koan 没进得去（`_decompose_koan` 零触发，全归一化成 partial 走 hybrid）；② reclassification 入口未生效（decidability_log 空）。

已核实关键词与源码一致（`不可判定结构拆解者` 在 6053 行是 koan 角色 system prompt；`可判定性变更轨迹` 仅在 `decidability_log` 有 applied 项时写出，故 0=确实无复债）。reclass 日志中的「挂账/确认债务」是「延迟债务」机制，与「复债」是两码事。
