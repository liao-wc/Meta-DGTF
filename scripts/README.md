# scripts/ 工具清单（2026-10-26）

> 所有命令在本仓库根目录执行；先设置 `$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"`。
> 零 API 成本项标 **[零成本]**；真实跑次会消耗 DeepSeek 余额。

## 1. 一键验收与护栏

| 命令 | 用途 |
|---|---|
| `python scripts/final_acceptance.py` **[零成本]** | **一条命令跑全部 8 项护栏**（fast_gate/V2/重放/过程门/plan/dual_judge/compare_eval/矩阵） |
| `python scripts/final_acceptance.py --with-service` **[零成本]** | 同上 + 本地服务单发检查（服务需在线） |
| `python fast_gate.py` **[零成本]** | 单文件引擎快检 12/12 |
| `python scripts/run_v2_tests.py` **[零成本]** | V2 全量判据 51 文件（806 checks） |
| `python scripts/lead_offline_fact_replay.py` **[零成本]** | 离线重放 124 packs + **回归护栏**（answered≥80 等，失败 exit 1） |
| `python scripts/lead_process_gate_audit.py` **[零成本]** | 过程门审计 85 packs + **护栏**（未修复行=0 等） |
| `python scripts/app_plan_matrix_check.py` **[零成本]** | App plan 不变量 18 项 |
| `python scripts/app_dual_judge_guard_check.py` **[零成本]** | dual_judge local 防护 7 项 |
| `python scripts/update_scenario_matrix.py` **[零成本]** | 场景矩阵 live 对照 + **一致性护栏**（\|Δ\|≤0.06） |
| `python scripts/local_model/test_compare_eval.py` **[零成本]** | 模型评测对比脚本自检 5 项 |

## 2. 真实跑次（消耗 API 余额）

| 命令 | 用途 |
|---|---|
| `python scripts/ab_bench.py run --tag <tag> --question "<题>" --config configs/道生专属模式.yaml --thinking off --web on` | 标准跑次记录（fast+web 成本档 ≈¥2–3） |
| `python scripts/ab_bench.py scan` / `pair <a> <b>` | 历史跑次汇总 / 两跑次对照 |
| `python scripts/app_fast_e2e.py "<题>" daosheng_fast` | App 端到端真实任务（≈¥3），产物写 `outputs/_lead_audit/` |
| `python scripts/lead_offline_pack_audit.py` **[零成本]** | 已存 pack 的离线指标提取 |
| `python scripts/lead_offline_fact_replay.py` **[零成本]** | 见护栏 |

## 3. App 服务与自检

| 命令 | 用途 |
|---|---|
| `$env:DGTF_APP_MOCK="1"; python dgtf_app/server.py --port 8768 --http --token lead-token-3 --no-agent-daemon` | mock App 服务（自检用） |
| `$env:DGTF_ACCESS_TOKEN="lead-token-3"; python dgtf_app/selftest.py --base http://127.0.0.1:8768` **[零成本]** | App 自检 444/0 |
| `python scripts/check_local_service.py` **[零成本]** | 本地 0.5B 服务 health/metrics/单发（含延迟分位数） |
| `python scripts/app_local_metrics_check.py --sim` **[零成本]** | busy→云端回退模拟验证 6/6 |
| `python scripts/app_local_metrics_check.py --real-busy` | 真实并发注入 + 回退验证（需服务在线） |

## 4. 本地模型训练/评测

| 命令 | 用途 |
|---|---|
| `local_model\envs\dgtf_llm_env\Scripts\python.exe scripts/local_model/train_dgtf_stage_lora.py --stage self_check --variant mixed --max-train 230 --epochs 2 --max-len 1900 --drop-truncated --lr 8e-5 --save-every 100 --val-subset 16` | 0.5B LoRA 训练（GPU，零 API） |
| `python scripts/local_model/eval_and_compare.py --adapter llm_sft/<cand> --out llm_sft/eval_<cand>.json --baseline llm_sft/eval_dgtf_stage_05b_v6_limit30.json --limit-scmin 30` | **候选评测 + SWITCH/KEEP 判定** |
| `python scripts/local_model/compare_eval.py <cand>.json <base>.json` | 两个 eval JSON 指标对比 + 判定 |
| `python scripts/local_model/eval_dgtf_stage.py --limit-scmin 30 --out <json>` | 直接跑 30 条 held-out 评测（GPU） |
| `python scripts/local_model/build_dgtf_stage_dataset.py` | 构建 stage 数据集 |

## 5. 事实/过程子系统（引擎 V2 模块）

| 命令 | 用途 |
|---|---|
| `python scripts/update_scenario_matrix.py` **[零成本]** | 见护栏（同时更新 `docs/scenario_matrix_live.json`） |
| `python scripts/lead_process_gate_audit.py` **[零成本]** | 过程门审计（输出 `docs/process_gate_audit_*.json`） |

## 6. 其他

| 命令 | 用途 |
|---|---|
| `python scripts/check_local_service.py --concurrency 4` | 并发串行化/排队实测 |
| `python scripts/start_app.ps1` / `stop_local_llm.ps1` 等 | 启停脚本（见文件头注释） |
