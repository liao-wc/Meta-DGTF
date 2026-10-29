# -*- coding: utf-8 -*-
"""[V2.2.29 / App 2.0.54] 引擎零行为差 + 发布说明 + CHANGELOG。"""
from pathlib import Path
import py_compile

ENG = Path("dgtf_engine/dgtf_v2/engine")
SRC = ENG / "Meta-DGTF-V2.2.28.py"
DST = ENG / "Meta-DGTF-V2.2.29.py"
raw = SRC.read_bytes()
assert raw[:3] != b"\xef\xbb\xbf" and raw.count(b"\n") == raw.count(b"\r\n")
t = raw.decode("utf-8").replace("\r\n", "\n")


def rep(a, b):
    global t
    c = t.count(a); assert c == 1, (c, a[:60]); t = t.replace(a, b)


rep("Meta-DGTF-道生三阶模型 · V2.2.28\n", "Meta-DGTF-道生三阶模型 · V2.2.29\n")
rep('__version__ = "2.2.28"', '__version__ = "2.2.29"')
rep("★ V2.2.28 补丁（预算层级 → 运行期 token 硬上限；引擎侧零行为差）：",
"""★ V2.2.29 补丁（预算层级 → 运行期墙钟硬上限；引擎侧零行为差）：
      本版为 App 发版：warn/critical 档把估算墙钟×1.5 写入 --max-minutes（显式优先），
      引擎复用 V2.2.22 起的 --max-minutes 预算机制。

★ V2.2.28 补丁（预算层级 → 运行期 token 硬上限；引擎侧零行为差）：""")
out = t.replace("\n", "\r\n").encode("utf-8")
DST.write_bytes(out)
chk = DST.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(DST), doraise=True)
print("OK", DST.name, len(chk))

v29 = """# Meta-DGTF 引擎 V2.2.29 + App 2.0.54 发布说明（2026-10-29）

> 类型：PATCH。主题：预算层级 → 运行期墙钟硬上限（与 token 上限成对）+ dual_judge 热缓存验证。
> 引擎侧零行为差（复用 V2.2.22 起的 --max-minutes）。

## 1. 墙钟硬上限（动态依赖）

- 预算 warn/critical 时：plan.max_minutes = ceil(估算 tokens / 600 tokens/s × 1.5 / 60)，
  最低 1 分钟；写入 plan.max_minutes 与 plan.dynamic_opt.budget_cap.max_minutes；
- apply_plan 透传 opts.max_minutes → engine_runner → 引擎 --max-minutes（优雅停/层间降档）；
- 显式 opts.max_minutes 永远优先；ok/quality 档不设上限（0=不限）；
- 与 V2.2.28 的 token 上限成对：预算紧时同时限制 token 与墙钟两条边界。

## 2. dual_judge 热缓存验证（有界，约 ¥0.14）

同配置连续两跑（cache 模式，route=0/rounds=0:1/fast/web off）：
- run1（冷）：10 calls / 29,848 tokens / 59.7s / cache_entries=81；
- run2（热）：10 calls / 30,436 tokens / 62.5s / cache_entries=94；
- 差值：+588 tokens、calls 相同 —— 该题型（事实/fast/单层）下 judge cache 未显著省 token；
  判断缓存命中可减少 judge 重算但占比小/被其他阶段波动覆盖。保留 cache 作为可选档，
  不再默认期待单题 token 收益；证据 docs/dual_judge_warmcache_20261029.json。

## 3. 判据

- test_dynamic_opt 60 → 64 项：warn 档 max_minutes（>0 且等于 budget_cap）、ok 档不设限、
  显式 max_minutes 优先、apply_plan/build_cmd 透传 --max-minutes。
- 回归：fused_optimal 30、fused_full_chain 16、daosheng_unified 27、auto_mode_local 12。

## 4. 验收

fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82。

## 5. 边界

- 墙钟上限按 600 tokens/s 保守速率折算（模型口径，非精确耗时）；
- 冷/热 judge cache 单题未见 token 收益（如实记录）；本地 0.5B 仅链路验证。
"""
Path("docs/releases/V2.2.29.md").write_text(v29, encoding="utf-8")
print("OK V2.2.29 note")

a54 = """# App 2.0.54 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.29（零行为差）。
> 主题：预算层级 → 运行期墙钟硬上限 + dual_judge 热缓存验证。

## 1. 变更

- 预算 warn/critical 时：plan.max_minutes = 估算 tokens/600×1.5 折算分钟（最低 1 分钟），
  apply_plan 透传 --max-minutes；显式 opts.max_minutes 优先，ok 档不设限；
- plan.dynamic_opt.budget_cap 同时记录 max_tokens/max_minutes（可审计）；
- dual_judge 热缓存连续两跑验证：run2 比 run1 +588 tokens、calls 相同（单题无显著收益），
  保留 cache 为可选档，证据 docs/dual_judge_warmcache_20261029.json。

## 2. 预算使用

本轮热缓存验证 2 跑合计约 ¥0.14（每跑 max_tokens=150000）。

## 3. 判据与验收

- test_dynamic_opt 64 项（+4）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 显式任务参数优先；ok/quality 档不设时间/ token 上限；项目/quality_first 不降评审。
"""
Path("docs/releases/app-V2.0.54.md").write_text(a54, encoding="utf-8")
print("OK app-V2.0.54 note")

Path("V2.2.29-发布报告.md").write_text("""# V2.2.29 + App 2.0.54 发布报告

本轮把预算边界补齐为"token + 墙钟"成对限制：warn/critical 档 plan.max_minutes =
估算 tokens/600×1.5 折算分钟（最低 1），apply_plan 透传 --max-minutes；显式优先、ok 档不设限；
budget_cap 同时记录两条边界。并做 dual_judge 热缓存连续两跑验证（约 ¥0.14）：
run1 冷 29,848 tokens / run2 热 30,436 tokens（+588，calls 相同）——单题未见显著 token 收益，
如实记录并保留 cache 为可选档。
判据 test_dynamic_opt 60→64；验收 fast_gate 16/16、V2 71/71（1208）、App selftest 455/0、
一键验收 PASS 30 / SKIP 0 / FAIL 0、e2e 18/18、probe 82/82、发布流程门 pre/post 全 PASS。
详见 docs/releases/V2.2.29.md 与 docs/releases/app-V2.0.54.md。
""", encoding="utf-8")
Path("V2.2.29-收束报告.md").write_text("""# V2.2.29 + App 2.0.54 收束报告

收束状态：引擎 V2.2.29、App 2.0.54、本地服务（8772）适配器 self_check=v8b / self_check_min=v9b / dual_judge=judge_v3 / route=qwen05b_v1；发布流程门 PASS（N/A 均带原因）。
本轮主线：预算层级 → 运行期墙钟硬上限（与 token 上限成对）+ dual_judge 热缓存验证（单题无显著 token 收益，如实记录）。
判据：test_dynamic_opt 64（+4）；V2 71/71（1208）；App selftest 455/0；一键验收 30/30。
边界：墙钟按 600 tokens/s 保守折算；judge cache 单题收益不显著；本地 0.5B 仅链路验证。
""", encoding="utf-8")
print("OK root reports")

entry = """【V2.2.29（2026-10-29，PATCH · 预算层级→运行期墙钟硬上限；同发 App 2.0.54）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.29.py（__version__=2.2.29；引擎侧零行为差）；
  App 2.0.54。
- ★ 墙钟硬上限：warn/critical 档 plan.max_minutes = ceil(估算 tokens/600×1.5/60)（最低 1），
  apply_plan 透传 --max-minutes；显式 opts.max_minutes 优先，ok 档不设限；
  plan.dynamic_opt.budget_cap 同时记录 max_tokens/max_minutes（与 V2.2.28 成对）。
- ★ dual_judge 热缓存验证（约 ¥0.14）：同配置连续两跑 run1 冷 29,848 tokens / run2 热
  30,436 tokens（+588、calls 相同）——该题型下单题 token 收益不显著，如实记录；
  保留 cache 为可选档，不再默认期待单题收益。
- 判据：test_dynamic_opt 60→64（warn 墙钟上限/ok 不设限/显式优先/apply_plan+build_cmd）；
  回归 fused_optimal 30 / fused_full_chain 16 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：显式参数优先；ok 档不设时间/token 上限；项目/quality_first 不降评审。
- 标签：V2.2.29 / engine-V2.2.29 / app-V2.0.54。

"""
CH = Path("CHANGELOG.md")
old = CH.read_text(encoding="utf-8")
CH.write_text(entry + old, encoding="utf-8")
print("OK CHANGELOG")
