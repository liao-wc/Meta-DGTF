# 发布流程 runbook（2026-10-31 · V2.2.103 现行版）

> 目的：把「预同步 → 验收 → 后同步 → 门禁」固定成可复跑顺序，
> 防 V2.2.102 那类 README/快照/证据不同步导致的验收自伤。

## 1. 标准顺序（每次发版）

```powershell
cd "D:\Meta-DGTF-道生三阶模型"
$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"
$env:PYTHONPATH="$PWD;$PWD\dgtf_engine;$PWD\dgtf_app"

# 0) 收尾：保证工作区干净（失败证据不计入发布提交）
git status --porcelain

# 1) 证据链（顺序敏感：probe → V2 → selftest → sync → fast_gate → sync）
python scripts/local_model/probe_layer_goals.py
python scripts/run_v2_tests.py --timeout 240
python scripts/app_selftest_gate.py
python scripts/sync_readme_numbers.py --write
python scripts/sync_snapshot_numbers.py --write
python fast_gate.py
python scripts/sync_readme_numbers.py --write
python scripts/sync_snapshot_numbers.py --write
python scripts/sync_readme_numbers.py --check
python scripts/sync_snapshot_numbers.py --check

# 2) 预同步后再跑验收（否则 acceptance 首步 fast_gate 会因数字不同步失败）
python scripts/final_acceptance.py --with-service
python scripts/sync_readme_numbers.py --write
python scripts/sync_snapshot_numbers.py --write

# 3) 发布门（pre → commit+tag → post）
python scripts/release_process_check.py --pre-tag
# git commit / git tag Vx.y.z / engine-Vx.y.z
python scripts/release_process_check.py --post-tag --evidence outputs/_lead_audit/release_process_posttag.json

# 4) 后门禁证据提交（dirty 只应是 docs/*_latest.json 类）
git status --porcelain
```

## 2. 常见故障与处置

| 现象 | 根因 | 处置 |
|---|---|---|
| acceptance 首步 fast_gate FAIL（readme_numbers/snapshot_numbers） | README/快照/证据数字不同步 | 先跑两个 sync --write，再验收 |
| app_selftest 启动超时（rc=1，0/0） | 临时 server 启动抖动 | 重跑 app_selftest_gate.py（曾一次 459/0 恢复） |
| dsh_loop_check B 把本地包当最新真跑 | 本地验证产物写进 outputs/ | 精确路径删除；本地 e2e 写临时目录 |
| 发布门「状态快照含本版」FAIL | 跨日/未建当日快照 | 建 docs/项目状态快照_YYYYMMDD.md 并含本版 |
| README ↔ V2 checks 数字 FAIL | checks 数变化（新增单测） | 由 sync_readme_numbers --write 修正 |

## 3. 不要做的事

- 不要用宽通配符清理 outputs/（2026-10-31 已发生一次误删，见状态快照）；
- 不要在验收运行中改引擎/脚本（证据与实现会错位）；
- 不要把本地 unverified 包留在 outputs/；
- 不要手写 README/快照数字（一律走 sync）。
