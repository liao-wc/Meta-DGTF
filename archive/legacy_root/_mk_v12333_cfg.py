#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.33：DEFAULT_CONFIG 两个 opt-in 键 + yaml 同步（头部/升级段）。"""
from pathlib import Path
import ast

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

b = SRC.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n") and b.count(b"\r\r\n") == 0
s = b.decode("utf-8").replace("\r\n", "\n")

# ① DEFAULT_CONFIG：stop.anytime_alpha + auto.bandit
old = '''    "playbook": {'''
new = '''    "stop": {
        # [anytime-valid 可配] δ（默认 **0.0 = 关**）。>0 时启用一条新停止判据
        #   「结构增长已 anytime-valid 地判停」：「结构仍在长」的 0/1 序列，
        #   其**随时看随时停仍有效**的均值下界跌破 0.5 ⇒ 可停。
        #   ★ 为什么需要：本项目每圈边跑边判 = optional stopping，用固定样本
        #     公式在「边跑边看」下有效性不成立（假阳率暴涨）。
        #     依据：stitched Hoeffding 置信序列（Howard et al. 2021）。
        "anytime_alpha": 0.0,
    },

    "playbook": {'''
assert s.count(old) == 1
s = s.replace(old, new, 1)

old2 = '''        "history_halflife_days": 14'''
if old2 not in s:
    old2 = '"history_halflife_days": 14'
assert s.count(old2) >= 1, "auto 段锚点未找到"
s = s.replace(old2,
               '''"history_halflife_days": 14,
        # [预算 bandit 可配] 默认 **关**（enabled=false）⇒ 出厂零行为差。
        #   enabled=true 时用 UCB1-with-cost 在「每层圈数上限」三档
        #   （3/4/6）间选择：奖励 = 职责度中位 − cost_w ×（tokens/1000）。
        #   ★ 探索会**故意选已知较差的档**，因此每次探索选择都在产物留痕
        #     （否则用户看到「这次为什么跑得差」会查无原因）。
        "bandit": {
            "enabled": False,
            "cost_w": 0.3,
            "c": 1.0,
        }''', 1)

ast.parse(s)
SRC.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("DEFAULT_CONFIG 两键已加；AST OK")

# ② yaml：头部版本 + 升级段 + 两个键
p = HERE / "dgtf_config.yaml"
yb = p.read_bytes()
is_crlf = yb.count(b"\r\n") == yb.count(b"\n") and yb.count(b"\r\n") > 0
y = yb.decode("utf-8").replace("\r\n", "\n")
y = y.replace("# 元 DGTF · v1.23.32 配置文件", "# 元 DGTF · v1.23.33 配置文件", 1)
_up = """# 【v1.23.32 → v1.23.33】机制级吸收：把「随时看随时停」变成有保证的事
#   ① **anytime-valid 停止**（`stop.anytime_alpha`，默认 **0 = 关**）：
#      本项目每圈边跑边判 = optional stopping，原先**无任何有效性保证**。
#      >0 时启用 stitched Hoeffding 置信序列（Howard et al. 2021）：
#      「结构仍在长」的 0/1 序列，其**对任意停时都成立**的均值下界跌破 0.5
#      ⇒ 追加一条停止理由。★ 默认关 ⇒ 出厂零行为差。
#   ② **发散检测 + 回滚指针**（**只出读数与指针，不改停止行为**）：
#      三态（收敛/停滞/发散）+ 历史最佳圈的**指针**；★ 被回滚的圈**不删**
#      （红线「失败留痕」）。
#   ③ **预算 bandit**（`auto.bandit.enabled`，默认 **false**）：UCB1-with-cost
#      在三档圈数上限间选择，奖励 = 职责度中位 − cost_w×成本。
#      ★ 探索会故意选较差档 ⇒ 必须显式打开，且每次探索都在产物留痕。
#   ④ **compact 内部面预算**（率失真）：只出**读数与政策**，**不自动压缩**
#      —— ACE 的反面数据：把 1.8 万 token 压到 122 token ⇒ 准确率 66.7→57.1。
#   ⑤ **锚点离线解析验证**（refchecker 思路：按可审计表面判）+
#      **内部批判**（史学：域名类型 → 立场/利益倾向提示）。
#   ⑥ **分级证明标准 + 谁主张谁举证**（法学）：causal 要 beyond_reasonable_doubt、
#      numerical/predictive 要 clear_and_convincing、其余 preponderance。
#   ⑦ **裁决维度拆分**（逻辑/事实/边界/后果）—— 红线「自省是另一个视角」。
#   ⑧ **信念陈旧度读数**：age ≥ 3 圈未再确认 ⇒ 提示；★ **不改四态**。
# 【v1.23.31 → v1.23.32】学科吸收"""
y = y.replace("# 【v1.23.31 → v1.23.32】学科吸收", _up, 1)
_yk = """playbook:
  mode: shadow"""
assert y.count(_yk) == 1
y = y.replace(_yk, """# 【v1.23.33】两个 opt-in 开关（默认都关 ⇒ 零行为差）。
#   stop.anytime_alpha: 0.0 = 关；>0 才启用 anytime-valid 停止判据（δ）。
#   auto.bandit.enabled: false = 关；true 才用预算 bandit 选圈数上限档。
stop:
  anytime_alpha: 0.0

playbook:
  mode: shadow""", 1)
p.write_bytes((y.replace("\n", "\r\n") if is_crlf else y).encode("utf-8"))
print("yaml 已同步（头部 + 升级段 + stop 段）")
