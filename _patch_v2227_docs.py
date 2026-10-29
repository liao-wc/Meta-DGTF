# -*- coding: utf-8 -*-
"""[V2.2.27 / App 2.0.52] 发布说明 + CHANGELOG。"""
from pathlib import Path

v27 = """# Meta-DGTF 引擎 V2.2.27 + App 2.0.52 发布说明（2026-10-29）

> 类型：PATCH。主题：App 全流程开销校准 + 有效 route 成本 + 阶段动态路由 + 引擎依赖闭包。
> 引擎侧有实际变更（route 依赖闭包），其余在 App 侧。

## 1. App 全流程开销校准（1 臂有界云实测）

问题：V2.2.26 成本模型是引擎 CLI 口径；App 全流程（自省/质量门/归档）还有额外开销。
实测：同题 route=0/rounds=0:1/web off/fast，App 路径实际 34,727 tokens vs 引擎模型 31,620
→ app_path_overhead = 1.098 ≈ 1.10（成本约 ¥0.07）。已计入 dynamic_config 候选 token 估算。

## 2. 有效 route 成本

原实现用 plan 的预设 route 估算成本；显式 opts.route=0 的任务仍按四层估算（高估）。
现在改用"有效 route"（显式 opts.route 优先），plan.dynamic_opt.route 记录实际生效 route；
省层任务成本估算与真实调用一致。

## 3. 阶段动态路由（dual_judge）

预算 warn/critical 且非项目/非 quality_first 时，dual_judge 走 cache（降本），
写 plan.dynamic_opt.applied.dual_judge_mode 与 stage_routing，apply_plan 透传；
项目题/quality_first/ok 档保持原评审档。

## 4. 引擎 route 依赖闭包（V2.2.27 引擎实际变更）

显式 --route 出现 both 缺 0/1、all 缺 both/0/1 时，引擎自动补全并打印"层依赖闭包"；
单层/无 both/all 的省层 route 不受影响。与 App 侧依赖闭包同口径，直连 CLI 也不断链。

## 5. 判据

- test_dynamic_opt 46 → 54 项：App 开销系数（证据一致）、有效 route 成本、阶段路由
  （warn 缓存/项目不降级/ok 不降级）、引擎闭包 helper 与 main 接线。
- 回归：fused_optimal 30、fused_full_chain 16、daosheng_unified 27、auto_mode_local 12。

## 6. 验收

fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 81/81。

## 7. 边界

- App 开销系数来自 1 臂实测（事实题/单层），多类型任务可能不同（后续继续累计样本）；
- dual_judge=cache 只在预算紧张且非项目/quality_first 时启用；
- 成本估算仍是模型口径，实际账单以 API 为准。
"""
Path("docs/releases/V2.2.27.md").write_text(v27, encoding="utf-8")
print("OK V2.2.27 note")

a52 = """# App 2.0.52 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.27（含 route 依赖闭包实际变更）。
> 主题：App 全流程开销校准 + 有效 route 成本 + 阶段动态路由。

## 1. 变更

- App 路径开销系数 1.10（1 臂有界云实测 34,727/31,620=1.098）计入动态成本估算；
- 成本估算改用"有效 route"（显式 opts.route 优先），省层任务不再被高估；
- 阶段动态路由：warn/critical 非项目/非 quality_first 时 dual_judge=cache，
  plan.dynamic_opt.applied/stage_routing 可审计；ok 档/项目题保持原评审档。

## 2. 预算使用

本轮 1 臂 App 路径校准约 ¥0.07（max_tokens=150000）；
证据：docs/app_path_cost_calibration_20261029.json。

## 3. 判据与验收

- test_dynamic_opt 54 项（+8）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 81/81。

## 4. 兼容性

- 显式任务参数优先；余额未知 fail-open；项目题/quality_first 不降评审；
- 引擎 V2.2.27 route 依赖闭包只补缺，不改既有四层 intent。
"""
Path("docs/releases/app-V2.0.52.md").write_text(a52, encoding="utf-8")
print("OK app-V2.0.52 note")

Path("V2.2.27-发布报告.md").write_text("""# V2.2.27 + App 2.0.52 发布报告

本轮把动态成本模型从引擎 CLI 口径推到 App 全流程口径，并补引擎侧依赖闭环：
- 1 臂有界云校准（约 ¥0.07）：App 路径 34,727 tokens / 引擎模型 31,620 → app_overhead≈1.10；
- 成本估算改用有效 route（显式 opts.route 优先），省层任务不再按四层高估；
- 阶段动态路由：warn/critical 非项目/quality_first → dual_judge=cache（可审计）；
- 引擎 V2.2.27：显式 route 出现 both/all 缺依赖时自动补全并告警（单层不受影响）。
判据：test_dynamic_opt 46→54；验收 fast_gate 16/16、V2 71/71（1208）、App selftest 455/0、
一键验收 PASS 30 / SKIP 0 / FAIL 0、e2e 18/18、probe 81/81、发布流程门 pre/post 全 PASS。
详见 docs/releases/V2.2.27.md 与 docs/releases/app-V2.0.52.md。
""", encoding="utf-8")
Path("V2.2.27-收束报告.md").write_text("""# V2.2.27 + App 2.0.52 收束报告

收束状态：引擎 V2.2.27、App 2.0.52、本地服务（8772）适配器 self_check=v8b / self_check_min=v9b / dual_judge=judge_v3 / route=qwen05b_v1；发布流程门 PASS（N/A 均带原因）。
本轮主线：App 路径开销校准（1 臂约 ¥0.07，系数 1.10）+ 有效 route 成本 + 阶段动态路由（dual_judge=cache）+ 引擎 route 依赖闭包。
判据：test_dynamic_opt 54（新增 8）；V2 71/71（1208）；App selftest 455/0；一键验收 30/30。
边界：开销系数来自 1 臂实测；dual_judge=cache 仅预算紧张且非项目/quality_first；成本估算为模型口径。
""", encoding="utf-8")
print("OK root reports")

entry = """【V2.2.27（2026-10-29，PATCH · App 全流程开销校准 + 有效 route 成本 + 阶段动态路由；同发 App 2.0.52）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.27.py（__version__=2.2.27）；
  App 2.0.52。
- ★ App 全流程开销：1 臂有界云校准（约 ¥0.07）：App 实际 34,727 tokens vs 引擎模型
  31,620 → app_overhead≈1.10，已计入 dynamic_config 候选 token/成本。
- ★ 有效 route 成本：成本估算改用显式 opts.route（优先）而非预设 route；省层任务不再被
  四层口径高估；plan.dynamic_opt.route 记录实际生效 route。
- ★ 阶段动态路由：预算 warn/critical 且非项目/非 quality_first 时 dual_judge=cache，
  plan.dynamic_opt.applied/stage_routing 可审计；ok 档/项目题/quality_first 保持原评审档。
- ★ 引擎 V2.2.27 实际变更：显式 --route 出现 both 缺 0/1、all 缺 both/0/1 时自动补全
  并打印"层依赖闭包"；单层/无 both/all 的省层 route 不受影响。
- 判据：test_dynamic_opt 46→54（App 开销证据、有效 route、阶段路由、引擎闭包 helper/main）；
  回归 fused_optimal 30 / fused_full_chain 16 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 81/81；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：显式 opts 优先；余额未知 fail-open；项目/quality_first 不降评审。
- 标签：V2.2.27 / engine-V2.2.27 / app-V2.0.52。

"""
CH = Path("CHANGELOG.md")
old = CH.read_text(encoding="utf-8")
CH.write_text(entry + old, encoding="utf-8")
print("OK CHANGELOG")
