# -*- coding: utf-8 -*-
"""[V2.2.24 / App 2.0.49] 引擎版本零行为差 + 发布说明。"""
from pathlib import Path
import py_compile

ENG = Path("dgtf_engine/dgtf_v2/engine")
SRC = ENG / "Meta-DGTF-V2.2.23.py"
DST = ENG / "Meta-DGTF-V2.2.24.py"
raw = SRC.read_bytes()
assert raw[:3] != b"\xef\xbb\xbf" and raw.count(b"\n") == raw.count(b"\r\n")
t = raw.decode("utf-8").replace("\r\n", "\n")


def rep(a, b):
    global t
    c = t.count(a)
    assert c == 1, "锚点 %d: %r" % (c, a[:60])
    t = t.replace(a, b)


rep("Meta-DGTF-道生三阶模型 · V2.2.23\n", "Meta-DGTF-道生三阶模型 · V2.2.24\n")
rep('__version__ = "2.2.23"', '__version__ = "2.2.24"')
rep("★ V2.2.23 补丁（route 安全门；引擎侧零行为差）：",
"""★ V2.2.24 补丁（动态配置优化 + 动态依赖调整；引擎侧零行为差）：
      本版为 App 发版：道生 plan 新增 route 依赖闭包（both 补 0/1，all 补 both/0/1）与
      预算×质量×成本多目标动态配置（plan.dynamic_opt）；引擎参数通道复用 V2.2.23。

★ V2.2.23 补丁（route 安全门；引擎侧零行为差）：""")
out = t.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)
chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(DST), doraise=True)
print("OK", DST.name, len(chk))

v24 = """# Meta-DGTF 引擎 V2.2.24 + App 2.0.49 发布说明（2026-10-29）

> 类型：PATCH。主题：全链路全流程动态配置优化 + 动态依赖调整。
> 引擎侧零行为差（V2.2.24 仅版本/说明）；重心在 App 侧道生 plan。

## 1. 动态依赖调整（route 依赖闭包）

- 新规则：both 需要 0/1 的上游产物；all 需要 both/0/1（引擎已有内容依赖表）。
- daosheng plan 在 route 策略（union/preset/predict）之后执行依赖闭包：
  - 预测/preset 只给 [both] => 自动补 0、1；
  - 只给 [all] => 补 both、0、1；
  - 单层 [1] 不被强加依赖（保持省层语义）；
- plan 新增 route_dependency_added 读数；补依赖时写 warnings。

## 2. 全链路动态配置优化（预算 × 质量 × 成本多目标）

dynamic_config()（纯函数，可单测）在每次任务规划时：

1. 取当前资源：余额/预留比例/预算层级（ok/degrade/warn/critical）、历史 tokens 中位、
   场景类型与质量下限（项目/quality_first=0.95，其它=0.90）；
2. 枚举候选：rounds 档（fast 实测档 / economy / critical / quality_first 高圈）×
   web（事实/选项强制 on，其余按场景）× 当前 engine_mode；
3. 估算每档 quality/tokens/cost（MODES 实测 + web 增量 + 圈数缩放）；
4. 约束筛选：cost <= 余额 × reserve_ratio（默认只花一半，留安全垫）、quality >= 下限；
5. 选择：可行解中质量最高、成本最低（regret=0 对候选集）；无解则最低成本兜底并显式告警；
6. 落盘 plan.dynamic_opt = {budget_level, candidates, chosen, applied, why, ...}；
   applied 只覆盖 rounds（显式 opts.rounds 永远优先），web=auto 时只记录不落 opts。

预算层级行为：

| budget_level | 动态配置动作 |
|---|---|
| ok（余额 >=8 元） | 保持质量档；quality_first 时可用 rounds_quality |
| degrade（4-8 元） | fast 档 + 实测 rounds_fast |
| warn（1-4 元） | fast 档 + rounds_economy（0:1,1:2,both:1,all:1） |
| critical（<1.2 元或 <估算成本×1.2） | rounds_critical（全 1 圈）+ 无解兜底告警 |

## 3. 判据

- 新增 scripts/local_model/test_dynamic_opt.py（28 项，进一键验收 strict）：
  依赖闭包 A1-A6；预算/质量/成本 B1-B10（含预留比例、层级降档、单调降本、fail-open）；
  plan 接线 C1-C6；apply_plan 到 build_cmd D1-D3；变异体 E1-E3。
- 回归：fused_optimal 30、fused_full_chain 16、daosheng_unified 27、auto_mode_local 12。

## 4. 验收

fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；probe 81/81。

## 5. 兼容性与边界

- 显式 opts（rounds/web）永远优先；web=auto 保持引擎自决语义不变；
- 余额未知 fail-open，不因查询失败拒任务；
- 预算层级只降圈/降档，不盲砍层（route 安全门仍默认四层）；
- 估算基于历史中位与实测增量，非精确账单；实测偏差记录在 dynamic_opt.est_* 供复盘。
"""
Path("docs/releases/V2.2.24.md").write_text(v24, encoding="utf-8")
print("OK V2.2.24 release note")

app49 = """# App 2.0.49 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.24（零行为差）。
> 主题：全链路动态配置优化 + 动态依赖调整（route 闭包）。

## 1. 变更

- daosheng plan 新增 route 依赖闭包：both 补 0/1，all 补 both/0/1；单层不强加依赖；
  plan 记录 route_dependency_added，补依赖写 warnings。
- 新增 dynamic_config（daosheng_mode）：余额 × 质量下限 × 成本多目标枚举与选择，
  按 budget_level（ok/degrade/warn/critical）自动降圈；plan 落 dynamic_opt，
  mode_summary 带 budget_level + dynamic 摘要。
- applied 仅覆盖 rounds（显式 opts.rounds 优先）；web=auto 不落 opts（交给引擎自决）。

## 2. 判据与验收

- test_dynamic_opt 28 项（进一键验收 strict）；
- 一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；App selftest 455/0；
  V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 81/81。

## 3. 兼容性

- 显式任务参数优先；余额未知 fail-open；预算只降圈/降档，不砍层；
- 旧引擎能力门控/参数通道不变（V2.2.24 引擎零行为差）。
"""
Path("docs/releases/app-V2.0.49.md").write_text(app49, encoding="utf-8")
print("OK app-V2.0.49 note")

Path("V2.2.24-发布报告.md").write_text("""# V2.2.24 + App 2.0.49 发布报告

本轮实现全链路动态配置优化 + 动态依赖调整：
- 依赖闭包：both 补 0/1，all 补 both/0/1（单层不强加依赖），plan 记录 route_dependency_added；
- dynamic_config：余额/预留/预算层级 × 质量下限 × 成本多目标枚举，audit 落 plan.dynamic_opt；
  ok/degrade/warn/critical 分别使用质量档/实测 fast 档/economy/critical 圈数；
  applied 只覆盖 rounds，显式 opts 优先，web=auto 不落 opts；
- 判据：test_dynamic_opt 28 项（依赖/多目标/接线/变异体），进一键验收 strict。
验收：fast_gate 16/16、V2 71/71（1208）、App selftest 455/0、一键验收 PASS 30 / SKIP 0 / FAIL 0、
e2e 18/18、probe 81/81、发布流程门 pre/post 全 PASS。
详见 docs/releases/V2.2.24.md 与 docs/releases/app-V2.0.49.md。
""", encoding="utf-8")
Path("V2.2.24-收束报告.md").write_text("""# V2.2.24 + App 2.0.49 收束报告

收束状态：引擎 V2.2.24、App 2.0.49、本地服务（8772）适配器 self_check=v8b / self_check_min=v9b / dual_judge=judge_v3 / route=qwen05b_v1；发布流程门 PASS（N/A 均带原因）。
本轮主线：动态依赖调整（route 闭包）+ 全链路动态配置优化（预算×质量×成本多目标，budget_level 降圈）。
判据：test_dynamic_opt 28（新增 strict）；V2 71/71（1208）；App selftest 455/0；一键验收 30/30。
边界：估算基于历史中位/实测增量；预算只降圈/降档不砍层；显式 opts 永远优先；本地 0.5B 仅链路验证。
""", encoding="utf-8")
print("OK root reports")
