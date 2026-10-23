# -*- coding: utf-8 -*-
"""[v1.23.1] 出厂配置同步：dgtf_config.yaml → 本版（补 web_search 两个新键）。

幂等；yaml 保持纯 CRLF；写完证明 load_config 行为**逐字不变**。
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML = HERE / "dgtf_config.yaml"
BAK = HERE / "_bak_dgtf_config.pre_v1231"
NEW = "v1.23.1"

raw = YAML.read_bytes()
s = raw.decode("utf-8")
assert s.count("\r\n") == s.count("\n"), "yaml 不是纯 CRLF"
s = s.replace("\r\n", "\n")
ls = s.split("\n")

if ls[1] == "# 元 DGTF · %s 配置文件" % NEW:
    print("== 已同步到 %s，跳过 ==" % NEW)
    sys.exit(0)

# ---- 1 头部版本 ----
_i = [i for i, l in enumerate(ls) if l == "# 元 DGTF · v1.23.0 配置文件"]
assert len(_i) == 1, "头部版本行命中 %d 次" % len(_i)
ls[_i[0]] = "# 元 DGTF · %s 配置文件" % NEW

# ---- 2 升级段 ----
UPGRADE = [
    "#",
    "# 【v1.23.0 → v1.23.1】遗留收尾：两个联网新键（纯加性）",
    "#   · tier_proposal: false            ← 联网结果的 tier **提案**（待审）。",
    "#     ★ 默认 false = 行为与 v1.23.0 逐字相同（零副作用）。",
    "#     ★ 即便打开也只写建议（pool.web_tier_proposals + [W-TIER?] 留痕），",
    "#       **绝不**改 item 的 tier、**绝不**进任何判定路径 ——",
    "#       首次出现的新域名进待审队列，由人确认后才谈 tier 生效。",
    "#   · domain_tier_rules: [...]        ← 提案依据表（子串 → tier，越小越硬）。",
    "#     未知域名保守取 3（> tier_floor 2 ⇒ 进不了引用表）。",
    "#   ★ 同时修正 round_no 口径：圈内传**真圈号**，拆解前置为 0 ——",
    "#     原先所有环节的 round 都是「拆解序号」（每跑恒 1），三层配额的",
    "#     per_stage_round 实际退化成「每跑」。此项**不涉及配置键**。",
]
_a = [i for i, l in enumerate(ls) if l == "#"]
assert _a, "找不到 banner 后的 `#` 行"
_i0 = _a[0]
ls[_i0 + 1:_i0 + 1] = UPGRADE

# ---- 3 web_search 段补两键 ----
ANCH = "  auto_disable_after_failures: 3"
_j = [i for i, l in enumerate(ls) if l == ANCH]
assert len(_j) == 1, "anchor 命中 %d 次" % len(_j)
ADD = [
    "",
    "  # 【tier 提案】[v1.23.1 遗留2] 是否给联网结果提「建议 tier」。",
    "  #   ★ 默认 false = 与 v1.23.0 逐字相同（零副作用）。",
    "  #   ★ 即便 true 也只写**待审**建议：绝不改 item 的 tier、",
    "  #     绝不进任何判定路径 —— 由人确认后才谈 tier 生效。",
    "  tier_proposal: false",
    "",
    "  # 【域名启发式】提案依据表：`[子串, tier]`，tier 越小越硬。",
    "  #   未知域名保守取 3（> 默认 tier_floor 2 ⇒ 进不了引用表）。",
    "  domain_tier_rules:",
    "    - [\".gov.cn\", 1]",
    "    - [\".gov\", 1]",
    "    - [\".edu\", 2]",
    "    - [\"iso.org\", 1]",
    "    - [\"standard\", 1]",
    "    - [\"wikipedia.org\", 3]",
    "    - [\"blog\", 4]",
    "    - [\"forum\", 4]",
]
ls[_j[0] + 1:_j[0] + 1] = ADD

s2 = "\n".join(ls)
out = s2.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert out.count(b"\r") == out.count(b"\r\n"), "出现裸 CR"

if not BAK.exists():
    shutil.copy2(YAML, BAK)
YAML.write_bytes(out)
print("OK: 出厂 yaml 已同步 → %s（备份 %s）" % (NEW, BAK.name))
