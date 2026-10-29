# -*- coding: utf-8 -*-
"""[V2.2.25 / App 2.0.50] 引擎零行为差 + 发布说明 + CHANGELOG。"""
from pathlib import Path
import py_compile

ENG = Path("dgtf_engine/dgtf_v2/engine")
SRC = ENG / "Meta-DGTF-V2.2.24.py"
DST = ENG / "Meta-DGTF-V2.2.25.py"
raw = SRC.read_bytes()
assert raw[:3] != b"\xef\xbb\xbf" and raw.count(b"\n") == raw.count(b"\r\n")
t = raw.decode("utf-8").replace("\r\n", "\n")


def rep(a, b):
    global t
    c = t.count(a)
    assert c == 1, "锚点 %d: %r" % (c, a[:60])
    t = t.replace(a, b)


rep("Meta-DGTF-道生三阶模型 · V2.2.24\n", "Meta-DGTF-道生三阶模型 · V2.2.25\n")
rep('__version__ = "2.2.24"', '__version__ = "2.2.25"')
rep("★ V2.2.24 补丁（动态配置优化 + 动态依赖调整；引擎侧零行为差）：",
"""★ V2.2.25 补丁（动态配置细化：多圈档候选 + 缓存命中感知；引擎侧零行为差）：
      本版为 App 发版：fast 档枚举 fast/economy/critical 圈数，按成本约束与质量估算
      多目标选择；精确缓存命中按 10% 成本计入可行域；plan.dynamic_opt 增加 route/cache 读数。

★ V2.2.24 补丁（动态配置优化 + 动态依赖调整；引擎侧零行为差）：""")
out = t.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)
chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(DST), doraise=True)
print("OK", DST.name, len(chk))

v25 = """# Meta-DGTF 引擎 V2.2.25 + App 2.0.50 发布说明（2026-10-29）

> 类型：PATCH。主题：动态配置细化（多圈档多目标 + 缓存命中感知）+ 剩余预算有界 A/B。
> 引擎侧零行为差（V2.2.25 仅版本/说明）。

## 1. 多圈档候选（真正的多目标选择）

- fast 档不再按预算层级硬编码一档圈数，而是枚举 fast / economy / critical 三档，
  每档估算 quality/tokens/cost，在成本约束（余额×预留）内选质量最高者；
- 质量估算改为圈数线性折扣：q = base - (1-factor)*0.03（不同低圈档不再同分）；
- fast 档质量下限对齐实测（min(项目下限, 0.90)），避免项目 0.95 造成假 fallback；
- quality 档保持 auto/quality_first 高圈，不被低圈候选干扰。

## 2. 缓存命中感知

- cache.exact=True 时，候选成本按 10% 计（近似零成本），可行域放宽，
  低余额下也能选质量更高的档；plan.dynamic_opt 增加 cache_hit / route 读数；
- 缓存预判提前到动态配置之前（同一份 cache_prediction 复用，不重复计算）。

## 3. 剩余预算有界 A/B（真实云端，2 臂）

同一问题（成年人正常心率是多少次每分钟？）、同 route=0 / rounds=0:1 / web off，
仅预算假设不同：

| 臂 | 预算层级 | 动态选择 | 实际 | 质量 |
|---|---|---|---|---|
| A-ok | ok（¥50） | quality 档 B / rounds auto / est ¥2.79 | 13 calls / 76,306 tokens ≈¥0.15 | verified |
| B-warn | warn（¥3） | fast 档 / economy 圈 / est ¥1.00 | 11 calls / 64,907 tokens ≈¥0.13 | verified |

- 结论：同一任务在资源收紧时自动降档且仍 verified；实际成本远低于整单四层估算
  （显式 route/rounds 锁定时估算偏保守）→ 下一轮做 route 子集感知成本模型。
- 证据：docs/dynamic_budget_ab_20261029.json（不写入生产质量统计）。
- 本轮花费约 ¥0.28；两臂均 done。

## 4. 判据

- test_dynamic_opt 28 → 36 项：多圈档枚举/降档、缓存命中放宽、route 审计、
  fail-open 只审计不改配置、fast 下限对齐、变异体。
- 回归：fused_optimal 30、fused_full_chain 16、daosheng_unified 27、auto_mode_local 12。

## 5. 验收

fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；probe 81/81。

## 6. 兼容性与边界

- 显式 opts 永远优先；余额未知 fail-open 只审计、不改原配置；
- 缓存命中放宽仅影响可行域与成本估算，不改变缓存未命中路径；
- 成本估算仍按整单口径（route 子集感知留待下一轮）；本地 0.5B 仅链路验证。
"""
Path("docs/releases/V2.2.25.md").write_text(v25, encoding="utf-8")
print("OK V2.2.25 note")

a50 = """# App 2.0.50 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.25（零行为差）。
> 主题：动态配置细化（多圈档多目标 + 缓存命中感知）+ 剩余预算有界 A/B。

## 1. 变更

- dynamic_config：fast 档枚举 fast/economy/critical 三档圈数，按成本约束+质量估算选择；
  质量随圈数线性折扣；fast 档质量下限对齐实测 0.90（项目 quality 档仍 0.95）。
- 缓存命中感知：精确命中按 10% 成本计入可行域，低余额也能选质量更高档；
  动态配置前移缓存预判，复用同一份结果。
- plan.dynamic_opt 增加 route / cache_hit 读数；fail-open（余额未知）只审计不改配置。

## 2. 剩余预算 A/B（真实云端 2 臂）

同题同 route/rounds，仅预算不同：ok 档选 quality B，warn 档选 fast+economy 圈；
两臂均 done 且 answer_quality=verified；实际约 ¥0.15/¥0.13（合计约 ¥0.28）。
证据：docs/dynamic_budget_ab_20261029.json。

## 3. 判据与验收

- test_dynamic_opt 36 项（多圈档/缓存/fail-open/route/变异体）；
- 一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；App selftest 455/0；
  V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 81/81。

## 4. 兼容性

- 显式任务参数优先；余额未知 fail-open；quality 档不受低圈候选影响；
- 成本估算仍整单口径（route 子集感知下一轮）。
"""
Path("docs/releases/app-V2.0.50.md").write_text(a50, encoding="utf-8")
print("OK app-V2.0.50 note")

Path("V2.2.25-发布报告.md").write_text("""# V2.2.25 + App 2.0.50 发布报告

本轮把动态配置细化为真正的多目标选择：
- fast 档枚举 fast/economy/critical 三档圈数，成本约束（余额×预留）内选质量最高；
  质量随圈数线性折扣；fast 下限对齐实测 0.90，避免项目 0.95 假 fallback；
- 缓存命中感知：精确命中按 10% 成本计入可行域；plan.dynamic_opt 增 route/cache_hit；
  fail-open（余额未知）只审计不改配置。
- 剩余预算有界 A/B（真实云端 2 臂，合计约 ¥0.28）：同题同 route/rounds，ok 档选 quality B、
  warn 档选 fast+economy，两臂均 done 且 verified；实际成本远低于整单估算（route/rounds 锁定）。
- 判据：test_dynamic_opt 36 项（+8）；回归 fused_optimal 30 / fused_full_chain 16 /
  daosheng_unified 27 / auto_mode_local 12。
验收：fast_gate 16/16、V2 71/71（1208）、App selftest 455/0、一键验收 PASS 30 / SKIP 0 / FAIL 0、
e2e 18/18、probe 81/81、发布流程门 pre/post 全 PASS。
详见 docs/releases/V2.2.25.md 与 docs/releases/app-V2.0.50.md。
""", encoding="utf-8")
Path("V2.2.25-收束报告.md").write_text("""# V2.2.25 + App 2.0.50 收束报告

收束状态：引擎 V2.2.25、App 2.0.50、本地服务（8772）适配器 self_check=v8b / self_check_min=v9b / dual_judge=judge_v3 / route=qwen05b_v1；发布流程门 PASS（N/A 均带原因）。
本轮主线：动态配置细化（多圈档多目标 + 缓存命中感知）+ 剩余预算有界 A/B（2 臂约 ¥0.28，均 verified）。
判据：test_dynamic_opt 36（新增 8）；V2 71/71（1208）；App selftest 455/0；一键验收 30/30。
边界：成本估算仍整单口径（route 子集感知下一轮）；显式 opts 优先；余额未知 fail-open 只审计。
""", encoding="utf-8")
print("OK root reports")

entry = """【V2.2.25（2026-10-29，PATCH · 动态配置细化 + 缓存命中感知；同发 App 2.0.50）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.25.py（__version__=2.2.25；引擎侧零行为差）；
  App 2.0.50。
- ★ 多圈档多目标：fast 档枚举 fast/economy/critical 三档圈数，在成本约束（余额×预留）内
  选质量最高者；质量随圈数线性折扣；fast 档质量下限对齐实测 0.90（项目 quality 仍 0.95）；
  quality 档不受低圈候选干扰。
- ★ 缓存命中感知：精确命中按 10% 成本计入可行域；缓存预判前移复用；plan.dynamic_opt
  增加 route / cache_hit 读数；余额未知 fail-open 只审计不改配置（不再误改 rounds）。
- ★ 剩余预算有界 A/B（真实云端 2 臂，合计约 ¥0.28）：同题同 route=0/rounds=0:1/web off，
  ok 档（¥50 假设）→ quality B / auto 圈，实际 13 calls / 76,306 tokens 约 ¥0.15，verified；
  warn 档（¥3）→ fast + economy 圈，实际 11 calls / 64,907 tokens 约 ¥0.13，verified。
  结论：资源收紧自动降档且仍 verified；实际成本远低于整单估算（为 route 子集成本模型留证据）。
- 判据：test_dynamic_opt 28→36 项；回归 fused_optimal 30 / fused_full_chain 16 /
  daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 81/81；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：显式 opts 永远优先；余额未知 fail-open 只审计；quality 档不受影响。
- 标签：V2.2.25 / engine-V2.2.25 / app-V2.0.50。

"""
CH = Path("CHANGELOG.md")
old = CH.read_text(encoding="utf-8")
CH.write_text(entry + old, encoding="utf-8")
print("OK CHANGELOG")
