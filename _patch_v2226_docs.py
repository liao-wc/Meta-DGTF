# -*- coding: utf-8 -*-
"""[V2.2.26 / App 2.0.51] 发布说明 + CHANGELOG。"""
from pathlib import Path

v26 = """# Meta-DGTF 引擎 V2.2.26 + App 2.0.51 发布说明（2026-10-29）

> 类型：PATCH。主题：route 子集感知动态成本模型（3 臂有界云实测校准）。
> 引擎侧零行为差（V2.2.26 仅版本/说明）；重心在 App 侧 dynamic_config。

## 1. 问题

V2.2.25 的动态配置按"整单四层"估算 token/成本：显式 route=0 或 rounds=0:1 的任务
会被高估约 2-20 倍，低余额时误判不可行 → 可能错过本可跑的高质量档。

## 2. 修法：层子集 × 圈数 可加成本模型

用 3 臂**有界**云实测（fast/web off/thinking off，每臂 max_tokens=150000）校准：

| 臂 | 配置 | 实测 tokens |
|---|---|---|
| R1 | route=1, rounds=1 | 37,119（15 calls） |
| R2 | route=0,1, rounds=0:1,1:1 | 62,180（22 calls） |
| R3 | route=0, rounds=0:2 | 63,240（17 calls） |

拟合：u0=31,620/圈、u1=37,119/圈；两层 0/1 重叠系数 0.905（R2 误差 0.05%）；
both/all 单位由 fast 整单实测（816,983 tokens，默认圈数 2,3,2,2）反解
（uB=137,654、uA=183,539）；其他 mode 按 MODES tokens 比例缩放；事实题 web on ×1.12。
本轮三臂合计实际花费约 ¥0.32（有界）。

模型对校准点的误差：R1/R3 0%、R2 0.05%、整单 fast 0%（定义域闭合）。

## 3. 接线

- dynamic_config 候选成本改用 route 子集模型（route/rounds 取自候选本身）；
- plan.dynamic_opt 标注 cost_model=route_subset_rounds.v1；
- 可行域保留 ±10% 估算容差（预算线附近优先保留质量更高档）；
- 校准证据：docs/dynamic_cost_calibration_20261029.json（不写入生产质量统计）。

## 4. 判据

- test_dynamic_opt 36 → 46 项：单层/两层/整单/B 模式/web 增量、校准证据一致性、
  route=0 任务子集成本接线、cost_model 标注。
- 回归：fused_optimal 30、fused_full_chain 16、daosheng_unified 27、auto_mode_local 12。

## 5. 验收

fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 81/81。

## 6. 边界

- 模型校准口径是引擎 CLI（fast/web off）；App 全流程另含自省/质量门开销，
  A/B 实测 token 仍高于模型（下轮用 App 路径继续校准）；
- both/all 单位由整单反解（单层 both/all 未单独实测）；本地 0.5B 仅链路验证。
"""
Path("docs/releases/V2.2.26.md").write_text(v26, encoding="utf-8")
print("OK V2.2.26 note")

a51 = """# App 2.0.51 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.26（零行为差）。
> 主题：route 子集感知动态成本模型。

## 1. 变更

- dynamic_config 成本估算改为 层子集 × 圈数 可加模型（3 臂云实测校准）；
- 单层 0/1、两层 0/1、整单四层、B/serial 比例、事实题 web 增量均有校准点；
- 候选成本按自身 route/rounds 估算（显式省层/低圈任务不再被整单口径高估）；
- 可行域保留 ±10% 估算容差；plan.dynamic_opt 标注 cost_model。

## 2. 预算使用

本轮 3 臂校准合计约 ¥0.32（有界 max_tokens=150000/臂）；
证据：docs/dynamic_cost_calibration_20261029.json。

## 3. 判据与验收

- test_dynamic_opt 46 项；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 81/81。

## 4. 兼容性

- 显式 opts 优先；余额未知 fail-open 只审计；quality 档不受影响；
- App 路径额外开销（自省/质量门）尚未纳入模型（下轮 App 路径校准）。
"""
Path("docs/releases/app-V2.0.51.md").write_text(a51, encoding="utf-8")
print("OK app-V2.0.51 note")

Path("V2.2.26-发布报告.md").write_text("""# V2.2.26 + App 2.0.51 发布报告

本轮解决动态配置成本估算的"整单口径"偏差：用 3 臂有界云实测（R1 route=1/rounds=1、
R2 route=0,1/rounds 1+1、R3 route=0/rounds=2；合计约 ¥0.32）校准层子集 × 圈数可加模型。
u0=31,620、u1=37,119；两层重叠系数 0.905（R2 误差 0.05%）；both/all 由整单 816,983 反解；
其他 mode 按 MODES 比例；事实 web ×1.12。dynamic_config 候选成本改用该模型，
plan.dynamic_opt 标注 cost_model=route_subset_rounds.v1，可行域保留 ±10% 容差。
判据 test_dynamic_opt 36→46；验收 fast_gate 16/16、V2 71/71（1208）、App selftest 455/0、
一键验收 PASS 30 / SKIP 0 / FAIL 0、e2e 18/18、probe 81/81、发布流程门 pre/post 全 PASS。
详见 docs/releases/V2.2.26.md 与 docs/releases/app-V2.0.51.md。
""", encoding="utf-8")
Path("V2.2.26-收束报告.md").write_text("""# V2.2.26 + App 2.0.51 收束报告

收束状态：引擎 V2.2.26、App 2.0.51、本地服务（8772）适配器 self_check=v8b / self_check_min=v9b / dual_judge=judge_v3 / route=qwen05b_v1；发布流程门 PASS（N/A 均带原因）。
本轮主线：route 子集感知动态成本模型（3 臂有界云实测约 ¥0.32 校准；R2 误差 0.05%，整单口径闭合）。
判据：test_dynamic_opt 46（新增 10）；V2 71/71（1208）；App selftest 455/0；一键验收 30/30。
边界：模型为引擎 CLI 口径；App 全流程开销（自省/质量门）下轮用 App 路径校准；both/all 由整单反解。
""", encoding="utf-8")
print("OK root reports")

entry = """【V2.2.26（2026-10-29，PATCH · route 子集感知动态成本模型；同发 App 2.0.51）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.26.py（__version__=2.2.26；引擎侧零行为差）；
  App 2.0.51。
- ★ 问题：V2.2.25 动态配置按整单四层估算成本，显式 route=0 / rounds=0:1 会被高估 2-20 倍，
  低余额误判不可行。
- ★ 修法：3 臂有界云实测校准（合计约 ¥0.32）：R1 route=1/rounds=1=37,119 tokens；
  R2 route=0,1/rounds 1+1=62,180（可加预测误差 0.05%）；R3 route=0/rounds=2=63,240。
  拟合 u0=31,620/圈、u1=37,119/圈；两层重叠系数 0.905；both/all 由整单 816,983 反解
  （uB=137,654/uA=183,539）；其他 mode 按 MODES 比例；事实题 web on ×1.12。
  dynamic_config 候选成本改用该模型（route/rounds 取自候选本身），
  plan.dynamic_opt 标注 cost_model=route_subset_rounds.v1，可行域保留 ±10% 容差。
- 判据：test_dynamic_opt 36→46（单层/两层/整单/B 模式/web 增量、校准证据、route=0 接线、
  cost_model）；回归 fused_optimal 30 / fused_full_chain 16 / daosheng_unified 27 /
  auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 81/81；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：显式 opts 优先；余额未知 fail-open 只审计；quality 档不受影响。
- 标签：V2.2.26 / engine-V2.2.26 / app-V2.0.51。

"""
CH = Path("CHANGELOG.md")
old = CH.read_text(encoding="utf-8")
CH.write_text(entry + old, encoding="utf-8")
print("OK CHANGELOG")
