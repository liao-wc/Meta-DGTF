# 项目流程门与发版回执（2026-10-28 · V2.2.18）

> 本文件记录「项目流程不能漏」的落地方式与**本轮完整流程执行回执**。
> 机器可读证据：docs/release_process_latest.json（pre-tag）+
> outputs/_lead_audit/release_process_posttag.json（post-tag；outputs/ 不入库）。

## 1. 为什么要做

README §六 与 docs/README 维护约定列出的发版动作此前只有部分被机器执行：
- App selftest 不在 acceptance 里（靠人手）；
- fast_gate / V2 / acceptance 不写证据 ⇒ 无法证明「门是这次跑的」，也无法核对
  README「当前版本实测」数字是否漂移（本轮就查出 README 仍写着 23/23）；
- 8 处版本声明（引擎/配置/NAMING/README/PROJECT_MAP/PROJECT_LAYOUT/Pages/文档）
  任一处漏改无人发现；三标签策略、DSH 闭环、完整性路径没有统一入口。

## 2. 门与证据出口

| 组件 | 职责 | 证据 |
|---|---|---|
| scripts/release_process_check.py | 版本 8 处一致 / 发布产物 / 证据新鲜度(<24h) / README 数字逐项相等 / 三标签(pre/post) / 完整性路径 / DSH 闭环(N/A 带原因) | docs/release_process_latest.json |
| fast_gate.py | 16 项快速门（含 release_process_selftest） | docs/fast_gate_latest.json |
| scripts/run_v2_tests.py | V2 全量 | docs/v2_tests_latest.json |
| scripts/app_selftest_gate.py | 自起临时 App server 跑 selftest（不碰用户 8765；起不来 exit=2=没跑） | docs/app_selftest_latest.json |
| scripts/final_acceptance.py | 一键验收三态（新增 app_selftest 步骤） | docs/acceptance_latest.json |
| scripts/tests_release_process.py | 门自身的构造性判据（21 项，12 变异体） | 进 fast_gate |

## 3. 本轮（V2.2.18）执行回执

### 3.1 门禁与验收

| 项 | 结果 | 证据 |
|---|---|---|
| fast_gate | PASS 16 / FAIL 0（audit70 71/0） | docs/fast_gate_latest.json |
| V2 全量 | 70/70（1163 checks，SKIP 0） | docs/v2_tests_latest.json |
| App selftest（自动门） | PASS 455 / FAIL 0 | docs/app_selftest_latest.json |
| 一键验收 --with-service | PASS 25 / SKIP 0 / FAIL 0（25 steps） | docs/acceptance_latest.json |
| 四层目标探针 | 81/81（四 case 共 182 calls，冷缓存 585.3s；四层结论不变） | outputs/_e2e_local/_layer_goals_probe_latest.json |
| 发布流程门 pre-tag | **PASS 30 / FAIL 0 / N/A 5**（N/A：V2.2.18/engine-V2.2.18 待打标签 2 项 + DSH 证据陈旧/用户实例不可达/退出码 3 项，原因均显式） | docs/release_process_latest.json |
| 发布流程门 post-tag | 打标签后复核（本轮结果见收束报告与 outputs/_lead_audit/release_process_posttag.json） | 不入库 |

### 3.2 可复跑的过程检查

| 检查 | 结果 |
|---|---|
| file_integrity_check | bad=0 |
| verify_project_paths | PASS |
| dsh_loop_check | PASS 4 / FAIL 2→N/A（生产包早于引擎修复=证据陈旧；用户 App 实例不可达=环境依赖） |
| 历史融合 readiness | 1.00 / continuity_ok=True |
| pareto_flow | 可复跑（历史真跑前沿） |
| pip check（主环境 + 本地模型环境） | 0 broken |

### 3.3 标签

- V2.2.18 / engine-V2.2.18（本轮）；
- App 2.0.37 未变：app-V2.0.37 沿用 V2.2.15 发布提交的标签，**不移动已发布标签**。

## 4. 语义边界

- N/A ≠ PASS：每条 N/A 必须带可指认原因（本机零 API 预算未复跑生产档 / 用户 App
  实例不可达 / 干净 checkout 无 outputs 回放数据）。
- 证据 <24h：长时间不发版的 checkout 上本门会红 —— 这是有意的「证据陈旧 = 未复跑」。
- 本门证明「流程动作做了、证据新鲜、数字不漂」，**不证明内容质量**；质量仍由四层合同/
  答案门/真跑读数负责。
