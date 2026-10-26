# dual_judge local 合并方案（worktree → 主引擎）

> 状态：**已实现（worktree 分支）**，主引擎待合并。合并必须等
> `dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.3.py` 在主工作树**干净**（无并发会话未提交改动）。

## 1. 资产位置

| 内容 | 位置 |
|---|---|
| 引擎补丁（含 local 档） | 分支 `dual-judge-local` 提交 `430763e` |
| 离线判据 T1–T6 | 同分支 `2b76fad` → `scripts/local_model/test_dual_judge_local.py` |
| 导出补丁 | `docs/patches/0001-*.patch`（引擎）、`0002-*.patch`（判据）、`0003-*.patch`（性能调优；Round 101） |
| 性能调优 | prompt 收缩（描述截 120 字、总长 ≤6000）、timeout 120s、max_new_tokens 320、回退计数 |
| 真跑证据 | v95-dual-local / local2 / local3（见 ab_evidence §88） |

## 2. 合并步骤（可控）

1. 确认主引擎干净：
   `git status --short -- dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.3.py`（应为空）；
2. **已全量校验（Round 102）**：在 HEAD 024ecd6 的临时 worktree 依次 apply
   0001→0002→0003，全部成功、编译通过、T1–T8 **8/8 PASS**；校验后临时工作树已删除。
3. 合并前复核基线：
   `git apply --check docs/patches/0001-*.patch`；
3. 应用：
   `git apply docs/patches/0001-*.patch`（引擎）+ 复制
   `docs/patches/test_dual_judge_local.py` 到 `scripts/local_model/`；
4. 门禁：`python fast_gate.py`、`python scripts/run_v2_tests.py`、
   `python scripts/local_model/test_dual_judge_local.py`；
5. 一次真跑（余额允许时）：
   `--dual-judge-mode local --local-llm-url http://127.0.0.1:8772/generate`，
   期望 verified、日志无「本地双判失败」（或少量超时回退）；
6. 更新 App：`daosheng_mode` 的 dual_judge local 防护保留（本地吞吐未达标前，
   App 预设仍回退 llm）；引擎 CLI 已可显式用 local；
7. 提交 + 更新 CHANGELOG/验收总览。

## 3. 已知限制

- 本地 judge 吞吐不足：19 次请求中 9 次超时回退（p95 service 47s，并发排队）；
- 优化方向：判官 prompt 收缩（候选列表截断/摘要）、max_new_tokens 降档、
  专训更小 judge 适配器、单飞队列（service busy 快速失败 → 回退 llm）；
- 在吞吐达标前 **不改变默认**（llm），local 保持 opt-in。

## 4. 一键合并（Round 120）

`powershell
python scripts/merge_dual_judge_local.py --check-only   # 临时 worktree 全量校验（当前 PASS）
python scripts/merge_dual_judge_local.py --commit       # 主引擎干净时 apply+Gates+提交
`
