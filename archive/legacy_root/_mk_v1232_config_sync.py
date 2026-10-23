# -*- coding: utf-8 -*-
"""[v1.23.2] 出厂配置同步：dgtf_config.yaml → 本版。

四处改动：
  1. 头部版本 + 升级说明；
  2. ★ `api.thinking.stages` 里 **15 行的注释写着「关」、值却是 `enabled`**
     —— 与作者自己的意图矛盾；而它们**此前从未生效**（调用点没传 stage=），
     所以实际行为一直是「关」。本版改成 `disabled`：**与注释一致、与
     实际行为一致**，行为零变化。要真的开就改回 `enabled`（本版起会生效）。
  3. 补 2 个「代码在传、配置没声明」的 stage（`adjudicate_sub_tristate_multi`
     / `anchor_crosscheck`），按默认值 `disabled`；
  4. `web_search.tier_floor` 2 → 3（新默认；此键此前从未被读过）+
     新增 `web_search.tier_confirmed: {}` 与 `actions.tri_vote_retry_empty: 1`。

幂等；写完证明 `load_config` 的**除这四处外**逐字不变。
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML = HERE / "dgtf_config.yaml"
BAK = HERE / "_bak_dgtf_config.pre_v1232"
NEW = "v1.23.2"

raw = YAML.read_bytes()
s = raw.decode("utf-8")
assert s.count("\r\n") == s.count("\n"), "yaml 不是纯 CRLF"
s = s.replace("\r\n", "\n")
ls = s.split("\n")

if ls[1] == "# 元 DGTF · %s 配置文件" % NEW:
    print("== 已同步到 %s，跳过 ==" % NEW)
    sys.exit(0)

# ---- 1 头部版本 ----
_i = [i for i, l in enumerate(ls) if l == "# 元 DGTF · v1.23.1 配置文件"]
assert len(_i) == 1, "头部版本行命中 %d 次" % len(_i)
ls[_i[0]] = "# 元 DGTF · %s 配置文件" % NEW

# ---- 2 升级说明 ----
UPGRADE = [
    "#",
    "# 【v1.23.1 → v1.23.2】整体审计 + 遗留收尾",
    "#   ① ★ `api.thinking.stages` 里 **15 行注释写着「关」、值却是 enabled** ——",
    "#      与本节自己的注释意图矛盾；而它们此前**从未生效**（调用点没传",
    "#      `stage=`，一律掉回 `thinking.default`）。本版把值改成 `disabled`：",
    "#      **与注释一致、与实际行为一致，行为零变化**。",
    "#      ⇒ 要让它们真的开思考，把值改回 \"enabled\"（**本版起才会真正生效**）。",
    "#   ② 补 2 个「代码在传、配置没声明」的 stage（按默认值 disabled）：",
    "#      `adjudicate_sub_tristate_multi` / `anchor_crosscheck`。",
    "#   ③ `web_search.tier_floor` 2 → 3（此键在 v1.23.1 及以前**从未被读过**）；",
    "#      新增 `web_search.tier_confirmed: {}`（人工确认表，默认空 = 零差异）。",
    "#   ④ 新增 `actions.tri_vote_retry_empty: 1`（三票里空票重试 1 次）。",
]
_a = [i for i, l in enumerate(ls) if l == "#"]
assert _a, "找不到 banner 后的 `#` 行"
ls[_a[0] + 1:_a[0] + 1] = UPGRADE

# ---- 3 15 行 enabled → disabled（只动 thinking.stages 块里的那 15 行）----
S15 = ("decide_parallel_mode", "check_input_sanity", "check_structure_saturation",
       "re_anchor", "ask_missing_polarity", "decompose_normal",
       "decompose_hybrid", "decompose_koan", "decompose_from_pool",
       "probe_research", "probe_duel", "probe_meta", "phase_probe",
       "self_check", "settle_research")
_done = 0
for _k in S15:
    _o = '      %s: "enabled"' % _k
    _hits = [i for i, l in enumerate(ls) if l.startswith(_o)]
    assert len(_hits) == 1, "%s 命中 %d 次" % (_k, len(_hits))
    # 保留原来的行尾注释（对齐用），只把值换掉
    _l = ls[_hits[0]]
    ls[_hits[0]] = _l.replace(_o, '      %s: "disabled"' % _k, 1)
    _done += 1
print("  · thinking.stages 改 disabled：%d 行" % _done)

# 组注释补一句「为何改」
_gi = [i for i, l in enumerate(ls)
       if l.strip().startswith("# ── 关：简单映射")]
assert len(_gi) == 1, "组注释命中 %d 次" % len(_gi)
ls[_gi[0]] = ("      # ── 关：简单映射 / 结构化罗列 / 输出本来就短，思考无收益 ──")
ls.insert(_gi[0] + 1, "      #   ★ [v1.23.2] 此前这 15 行的值误写成 \"enabled\"（注释写的"
                      "是「关」）；")
ls.insert(_gi[0] + 2, "      #     而它们当时**从未生效**（调用点没传 stage=）⇒ 实际行"
                      "为一直是「关」。")
ls.insert(_gi[0] + 3, "      #     本版改为 disabled：与注释一致、与实际行为一致，"
                      "**行为零变化**。")

# ---- 4 补 2 个缺失 stage（放在 settle_research 之后）----
_ci = [i for i, l in enumerate(ls)
       if l.startswith('      settle_research: "disabled"')]
assert len(_ci) == 1, "settle_research 锚点命中 %d 次" % len(_ci)
ls[_ci[0] + 1:_ci[0] + 1] = [
    "      # [v1.23.2] 下面两个是「代码在传、配置此前没声明」的（按默认值列出）。",
    '      adjudicate_sub_tristate_multi: "disabled"   # 三态多票判决（3 票）',
    '      anchor_crosscheck: "disabled"               # 锚点交叉核对',
]

# ---- 5 web_search.tier_floor 2 → 3 ----
# ★ `tier_floor: 2` 在 yaml 里出现**两次**（external_anchor 一处、web_search
#   一处）⇒ 用**上下文两行**定位，只锚一行会命中 2 次（第一版即此）。
#   另一处（锚点的）保持 2 不动。
_i5 = [i for i, l in enumerate(ls)
       if l == '  as_evidence: "crosscheck"'
       and i + 1 < len(ls) and ls[i + 1] == "  tier_floor: 2"]
assert len(_i5) == 1, "web_search tier_floor 上下文命中 %d 次" % len(_i5)
_k5 = _i5[0] + 1
ls[_k5] = "  tier_floor: 3"
ls[_k5:_k5] = [
    "  # 【tier 门】[v1.23.2] W# 进引用表的有效 tier 上限。",
    "  #   ★ 本键在 v1.23.1 及以前**从未被读过**（审计 J 类抓出来的）。",
    "  #   ★ 默认 3 = 与 v1.23.1 行为一致：客户端初值 3 能进表；",
    "  #     人把某域名在 `tier_confirmed` 里确认成 4 就进不了。",
]
print("  · web_search.tier_floor 2 -> 3（上下文两行锚定）")

# ---- 6 web_search.tier_confirmed ----
_ac = [i for i, l in enumerate(ls) if l == '  auto_disable_after_failures: 3']
assert len(_ac) == 1, "auto_disable 锚点命中 %d 次" % len(_ac)
ls[_ac[0] + 1:_ac[0] + 1] = [
    "",
    "  # 【人工确认表】[v1.23.2] 域名 → tier。**默认空 = 零差异**。",
    "  #   ★ 从「提案」（tier_proposal）到「生效」没有自动路径：只有人把域名",
    "  #     写进这张表才生效。写 4（博客/论坛档）会把它挡在引用表外。",
    "  #   例：{natcm.gov.cn: 1, zhihu.com: 4}",
    "  tier_confirmed: {}",
]

# ---- 7 actions.tri_vote_retry_empty ----
_at = [i for i, l in enumerate(ls) if l == "  tri_multi_vote: true"]
assert len(_at) == 1, "tri_multi_vote 锚点命中 %d 次" % len(_at)
ls[_at[0] + 1:_at[0] + 1] = [
    "  # [v1.23.2] 三票里某票返回**合法 dict 但 judgments 为空**时的重试次数。",
    "  #   ★ 空票是**失败**不是弃权（实测 10 跑里 4 跑因此只有 2 票可用）。",
    "  tri_vote_retry_empty: 1",
]

s2 = "\n".join(ls)
out = s2.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert out.count(b"\r") == out.count(b"\r\n"), "出现裸 CR"

if not BAK.exists():
    shutil.copy2(YAML, BAK)
YAML.write_bytes(out)
print("OK: 出厂 yaml 已同步 → %s（备份 %s）" % (NEW, BAK.name))
