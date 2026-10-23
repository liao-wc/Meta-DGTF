# -*- coding: utf-8 -*-
"""[v1.23.0 W1] 出厂配置同步：dgtf_config.yaml → 本版（含 web_search 全部键）。
幂等；yaml 保持纯 CRLF；写完证明 load_config 行为不变。
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML = HERE / "dgtf_config.yaml"
NEW = "v1.23.0"

raw = YAML.read_bytes()
s = raw.decode("utf-8")
assert s.count("\r\n") == s.count("\n"), "yaml 不是纯 CRLF"
s = s.replace("\r\n", "\n")
if f"元 DGTF · {NEW} 配置文件" in s.split("\n")[1]:
    print("== 已同步到 %s，跳过 ==" % NEW); sys.exit(0)

ls = s.split("\n")

# ---- 1 头部版本 ----
_i = [i for i, l in enumerate(ls) if l.startswith("# 元 DGTF · v1.22.2 配置文件")]
assert len(_i) == 1, "头部版本行命中 %d 次" % len(_i)
ls[_i[0]] = "# 元 DGTF · %s 配置文件" % NEW

# ---- 2 升级段（插在 banner 后的第一个 `#` 之后）----
UPGRADE = [
    "#",
    "# 【v1.22.2 → v1.23.0 W1】核心联网（W 系列）基础设施",
    "#   ★ 本 Phase **不接入任何环节**：所有键都「只配不接」，改动是纯加性。",
    "#   新增段 `web_search`（20 个键，全部默认值写在此文件里）：",
    "#     enabled: false                  ← 全局总闸。**默认关 = 零调用**。",
    "#     backend / api_key_env / timeout_seconds / max_retries /",
    "#     backoff_seconds / cache_ttl_hours",
    "#     quota.{per_stage_round, per_stage_total, per_run_total}",
    "#                                     ← 配额**三层**，三层都过才允许调用。",
    "#     stages.{practice_term_calibration, research_decompose,",
    "#             research_evidence, research_precedent, duel_arbitration,",
    "#             meta_clean_check, stop_criteria}",
    "#                                     ← 按**环节**授权（不是全局 ON/OFF）。",
    "#       修行层 term_calibration 与 stop_criteria 默认 false。",
    "#     as_evidence / tier_floor         ← 引用授权（与 external_anchor 同名",
    "#                                       但**独立**，两段互不影响）。",
    "#     auto_disable_after_failures: 3   ← 连续失败 3 次 → 本跑联网关闭，",
    "#                                       留痕 [W-DISABLED]。",
    "#   怎么退回旧行为：什么都不用改 —— enabled 默认 false，行为与 v1.22.2 相同。",
    "#   另：检索缓存落 `cache/websearch/`，**与锚点的 `cache/anchors/` 分开**。",
]
_a = [i for i, l in enumerate(ls) if l == "#"]
assert _a, "找不到 banner 后的 `#` 行"
_i0 = _a[0]
ls[_i0 + 1:_i0 + 1] = UPGRADE

# ---- 3 插入 web_search 段（放在 external_anchor 之后、spiral 之前）----
WS = [
    "",
    "# ============================================================",
    "# [v1.23.0 W1] 核心联网（W 系列）· 基础设施。★ 默认全关，纯加性。",
    "#   它是什么：运行时**发起**的检索。与 external_anchor（事先落盘的冻结",
    "#   事实快照）是两件事；编号 W# 与 X# **不互换**。",
    "#   红线：检索结果只作**参照** —— 不进 view.candidates、不进 _ing、",
    "#   不进对撞第三者；失败走独立 logger（dgtf.websearch, propagate=False）。",
    "# ============================================================",
    "web_search:",
    "  # 【用途】全局总闸。【默认】false —— 不显式打开就是**零调用**。",
    "  enabled: false",
    "",
    "  # 【用途】检索后端（key 走环境变量，不落盘本文件）。",
    "  backend: \"tavily\"",
    "  api_key_env: \"TAVILY_API_KEY\"",
    "",
    "  # 【用途】单次请求超时（秒）/ 重试次数 / 线性退避基数（秒）。",
    "  timeout_seconds: 30",
    "  max_retries: 2",
    "  backoff_seconds: 1.8",
    "",
    "  # 【用途】检索结果缓存小时数（sha256 落 cache/websearch/）。",
    "  cache_ttl_hours: 24",
    "",
    "  # 【配额三层】每环节每圈 / 每环节全程 / 每跑总。三层都过才允许调用。",
    "  quota:",
    "    per_stage_round: 2",
    "    per_stage_total: 8",
    "    per_run_total: 30",
    "",
    "  # 【环节授权】逐环节开关（不是全局 ON/OFF）。",
    "  #   修行层与停止判据**默认关** —— 修行层联网会污染",
    "  #   「输入是形状不是数据」这条宪法级特性。",
    "  stages:",
    "    practice_term_calibration: false",
    "    research_decompose: true",
    "    research_evidence: true",
    "    research_precedent: true",
    "    duel_arbitration: true",
    "    meta_clean_check: true",
    "    stop_criteria: false",
    "",
    "  # 【引用授权】off / record / crosscheck / evidence / gate。",
    "  as_evidence: \"crosscheck\"",
    "  tier_floor: 2",
    "",
    "  # 【失败降级】连续失败达到此值 → 本跑联网关闭（留痕 [W-DISABLED]）。",
    "  auto_disable_after_failures: 3",
    "",
]
_sp = [i for i, l in enumerate(ls) if l == "spiral:"]
assert len(_sp) == 1, "`spiral:` 顶层行命中 %d 次（期望 1）" % len(_sp)
ls[_sp[0]:_sp[0]] = WS

s2 = "\n".join(ls)
out = s2.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert out.count(b"\r") == out.count(b"\r\n"), "出现裸 CR"

shutil.copy2(YAML, HERE / "_bak_dgtf_config.pre_v1230")
YAML.write_bytes(out)
print("OK: 出厂 yaml 已同步 → %s（备份 _bak_dgtf_config.pre_v1230）" % NEW)
