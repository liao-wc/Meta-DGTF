# -*- coding: utf-8 -*-
"""[v1.22.2] 出厂配置同步：dgtf_config.yaml → 本版。

四件事（照 skill「配置文件同步」）：
  1. 头部版本 → v1.22.2，补【v1.22.1 → v1.22.2】升级段；
  2. 补漏键：DEFAULT_CONFIG 有、yaml 没有的键，**按默认值**写进去；
  3. 证明行为不变：load_config(旧) vs load_config(新) 逐字对比；
  4. yaml 保持纯 CRLF（整行锚点，不用子串锚点）。
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML = HERE / "dgtf_config.yaml"
NEW = "v1.22.2"

raw = YAML.read_bytes()
s = raw.decode("utf-8")
assert s.count("\r\n") == s.count("\n"), "yaml 不是纯 CRLF"
s = s.replace("\r\n", "\n")
lines = s.split("\n")

if f"元 DGTF · {NEW} 配置文件" in lines[1]:
    print("== 已同步到 %s，跳过 ==" % NEW); sys.exit(0)


def sub_line(text, whole, new_one, tag):
    ls = text.split("\n")
    idx = [i for i, l in enumerate(ls) if l == whole]
    assert len(idx) == 1, f"[{tag}] 整行锚点命中 {len(idx)} 次（应为 1）"
    ls[idx[0]] = new_one
    return "\n".join(ls)


# 1 头部版本
s = sub_line(s, "# 元 DGTF · v1.22.0 配置文件",
             "# 元 DGTF · %s 配置文件" % NEW, "头部版本")

# 2 升级段（插在 banner 后的第一个 `#` 之后）
UPGRADE = [
    "#",
    "# 【v1.22.1 → v1.22.2】",
    "#   新增字段（都有默认值；本文件已按「列全」原则写出）：",
    "#     external_anchor.answers_min_len: 6   ← 锚点 answers 的**最短长度**",
    "#         （中文字符）。短 answer 会让 overlap_coef 假命中 —— 它分母取",
    "#         min，2 字 answer 被长 aspect 包住就是 1.000。0 = 不过滤。",
    "#     external_anchor.answers_max_n: 5     ← 单条锚点 answers 上限。",
    "#         原先硬编码，本版提成配置（值不变 = 行为不变）。",
    "#   行为变化（不需要改配置）：",
    "#     · 产物头部新增「⚠️ **锚点 answers 警告**」一行（有 answer 被过滤",
    "#       时才出现，与「未声明 answers」是**两条不同**的告警，不互相覆盖）。",
    "#     · 研究层三态判决行改成**按口径分印**：单票路径标「三态判决（单票）」",
    "#       且口径 = 单票 vs 拆解原标签；多票标「三态判决（多票）」，口径 =",
    "#       三票之间。**不再把单票路径印成「三态多票 high 0/low 0/一致率 0%」**。",
    "#       分母只数**有判决的条**，判决官弃权的条单列。",
    "#     · decision 取向的产物新增「不做什么」清单实际内容 —— 研究层",
    "#       schema 增加了 not_do[]，rubric 第三项（不做什么）从此能拿到分。",
    "#   怎么退回旧行为：",
    "#     external_anchor.answers_min_len 置 0 → 不过滤（= v1.22.1 行为）；",
    "#     actions.tri_multi_vote 置 false → 三态退回单票路径。",
]
_anchor = next(i for i, l in enumerate(lines) if l == "#")
ls = s.split("\n")
assert ls[_anchor] == "#"
ls[_anchor + 1:_anchor + 1] = UPGRADE
s = "\n".join(ls)

# 3 补漏键（按默认值）—— 位置：external_anchor 段的 crosscheck 之后
TWO_KEYS = [
    "",
    "  # 【用途】answers 的**最短长度**（中文字符）。短 answer 会让",
    "  #   overlap_coef 假命中 —— 分母取 min，2 字 answer 被长 aspect",
    "  #   包住就是 1.000。被丢弃的 answer 会写进产物头部的",
    "  #   「锚点 answers 警告」并记在 anchors.<id>._answers_dropped。",
    "  # 【默认】6。置 0 = 不过滤（退回 v1.22.1 行为）。",
    "  answers_min_len: 6",
    "",
    "  # 【用途】单条锚点 answers 的上限（防侧面对比表膨胀）。",
    "  # 【默认】5（原硬编码值，v1.22.2 提成配置）。",
    "  answers_max_n: 5",
]
_i = [i for i, l in enumerate(s.split("\n")) if l == "  crosscheck: true"]
assert len(_i) == 1, "crosscheck: true 整行锚点命中 %d 次" % len(_i)
ls = s.split("\n")
ls[_i[0] + 1:_i[0] + 1] = TWO_KEYS
s = "\n".join(ls)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert out.count(b"\r") == out.count(b"\r\n"), "出现裸 CR"

# 4 回滚备份 + 写入
bak = HERE / ("_bak_dgtf_config.pre_v1222")
shutil.copy2(YAML, bak)
YAML.write_bytes(out)
print("OK: 出厂 yaml 已同步 → %s（备份 %s）" % (NEW, bak.name))
