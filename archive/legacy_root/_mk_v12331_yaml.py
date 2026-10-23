#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.31：出厂 yaml 同步（头部版本 + 升级段 + playbook 段）。"""
from pathlib import Path
import importlib.util
import sys

HERE = Path(__file__).resolve().parent
p = HERE / "dgtf_config.yaml"
b = p.read_bytes()
s = b.decode("utf-8").replace("\r\n", "\n")


def rep(old, new, what, expect=1):
    global s
    n = s.count(old)
    assert n == expect, "%s: %d" % (what, n)
    s = s.replace(old, new)


rep("# 元 DGTF · v1.23.30 配置文件", "# 元 DGTF · v1.23.31 配置文件", "头部版本")

rep("# 【v1.23.29 → v1.23.30】层职责守卫（LDG）",
    """# 【v1.23.30 → v1.23.31】EML 经验记忆回路：跨跑**储存记忆** + 每次跑自我学习
#   ★ 缺口：原来只有「版本记忆」（CHANGELOG）和「统计记忆」（auto 读历史读数），
#     没有**经验层**（哪类做法有效）与**闭环**（跑完写回 → 下次生效 → 再验证）。
#   ★ 三段：读（recall）→ 用（apply + 留痕）→ 写（consolidate）
#     + 一道**质量闸**（MRRL Layer B 四问：证据 / 矛盾 / 可验证 / 红线）。
#   ★ 新增 `playbook` 配置段（**默认 mode=shadow ⇒ 出厂零行为差**）：
#     · off    ：不读不写（完全关）；
#     · shadow ：**出厂默认**，只记不生效（先观察，$\ref{eq}$ 不冒险）；
#     · on     ：生效 —— 只改写**调度与守卫阈值**（rounds / duty.floor），
#                **绝不注入答案内容**（红线「输入是形状不是数据」）。
#     · dir / top_k / promote_n / halflife_days：库目录 / 每次读几条 /
#       同向证据几次才 shadow→active / 检索与遗忘共用的半衰期。
#   ★ 学坏防线五条：① 新条目一律 shadow；② 双边记账（只省成本 ⇒ 不许升级）；
#     ③ 一键 off/shadow/on；④ 遗忘清扫（只改状态位）；⑤ append-only（只增不删）。
#   ★ 前沿依据：ACE（arXiv 2510.04618，**不重写、只增量**——实测压缩会把
#     66.7 掉到 57.1）/ LiveRAG'25（评测口径）/ MRRL（质量闸+多级反思+遗忘）/
#     NAACL'25 子问题覆盖；开源对照：llmace、evermind（RRIF 四维）、
#     agentmemory（procedural execution-tracking）、MemoryMCP（访问加强）。
# 【v1.23.29 → v1.23.30】层职责守卫（LDG）""", "升级段")

rep("""duty:
  floor: 0.35
  tau: 0.02
  patience: 2
  remedy_rounds: 1
""", """duty:
  floor: 0.35
  tau: 0.02
  patience: 2
  remedy_rounds: 1

# 【v1.23.31】EML 经验记忆回路 —— 记忆库默认落在仓库根 `dgtf_memory/`。
#   mode：
#     off    = 不读不写（完全关）
#     shadow = **出厂默认**：跑完照常记录 episode 与候选经验（过闸后进
#              `shadow` 状态），但**不生效** ⇒ 行为与 off 逐字相同，
#              差别只在「留下了库」。先观察几跑再切 on，是刻意的保守。
#     on     = 生效：只改写 **调度**（截断过的层 +1 圈）与 **守卫阈值**
#              （duty.floor）。★ 绝不注入答案内容。
#   top_k / promote_n：每次读几条 / 同向证据几次才 shadow→active（默认 3）。
#   halflife_days：检索排序（RRIF 的 recency 维）与遗忘清扫共用（默认 14）。
playbook:
  mode: shadow
  dir: ""
  top_k: 3
  promote_n: 3
  halflife_days: 14.0
""", "playbook 段")

p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("yaml 同步完成")

spec = importlib.util.spec_from_file_location("m", HERE / "元DGTF-V1.23.31.py")
m = importlib.util.module_from_spec(spec)
sys.modules["m"] = m
spec.loader.exec_module(m)
import yaml
yc = yaml.safe_load(Path(p).read_text(encoding="utf-8"))
diffs = []


def walk(d, y, pre=""):
    for k, v in d.items():
        if k not in y:
            diffs.append(pre + k)
        elif isinstance(v, dict):
            walk(v, y[k], pre + k + ".")


for k, v in m.DEFAULT_CONFIG.items():
    walk({k: v}, yc)
print("出厂 yaml 缺键：", diffs if diffs else 0)
print("playbook 段：", yc.get("playbook"))
