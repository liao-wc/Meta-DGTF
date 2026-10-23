#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dgtf_app 同步 v1.23.29→33：给新增/遗漏配置键补中文标签（`params._KEY_CN`）。

依据（skill `dgtf-app-frontend`）：
  ★★ 参数项标签统一「键（中文说明）」；说明表在 `dgtf_app/params.py` 的 `_KEY_CN`，
     未登记会让参数面板露出英文键名（selftest「参数标签统一」判据会红）。

本轮缺失 19 键：17 个来自 v1.23.29~33 新增（duty/playbook/stop/belief.merge_*/auto.bandit），
2 个是更早版本新增时漏登记（probe.marginal_floor / belief.revoke_sources）。
"""
from pathlib import Path

p = Path("dgtf_app/params.py")
b = p.read_bytes()
is_crlf = b.count(b"\r\n") > 0 and b.count(b"\r\n") == b.count(b"\n")
s = b.decode("utf-8").replace("\r\n", "\n")

NEW = {
    "auto.bandit.c": "预算 bandit 的探索系数 c（UCB 宽度；越大越爱探索）",
    "auto.bandit.cost_w": "预算 bandit 的成本权重（奖励里扣多少成本；默认 0.3）",
    "auto.bandit.enabled": "预算 bandit 总开关（默认关；开机后探索会故意选较差档）",
    "probe.marginal_floor": "探针边际增益下限（≥此值才算有增益；0=分支恒不触发）",
    "belief.merge_semantic": "语义归并开关（默认关；开=「换说法」记为一次复现）",
    "belief.merge_sim": "语义归并阈值（默认 0.85，近乎逐字才算，宁可漏并）",
    "belief.revoke_sources": "信念撤销所需的**不同**攻击来源数（与 stable 对称）",
    "belief.sem_entropy_thr": "语义熵聚类阈值（0.30；填 rel 改用本批相对分位）",
    "duty.floor": "层职责度下限（低于它不许署「自然安住」，并点名缺的 core）",
    "duty.patience": "职责增益收敛所需连续圈数（ΔS<τ 连续几圈算推不动）",
    "duty.remedy_rounds": "职责未尽时的定向补救圈数（并入下游 carry；0=关）",
    "duty.tau": "职责边际增益阈值 τ（连续低于它记「推不动」）",
    "playbook.dir": "经验记忆库目录（默认空=仓库根 dgtf_memory/）",
    "playbook.halflife_days": "记忆半衰期（天）：检索排序与遗忘共用（默认 14）",
    "playbook.learn_from_anon": "是否收无 run_id 的跑次（默认否，防测试替生产刷票）",
    "playbook.mode": "经验记忆模式：off 不读不写 / shadow 只记不生效 / on 生效",
    "playbook.promote_n": "同向证据达几条才 shadow→active（默认 3）",
    "playbook.top_k": "每次读几条经验（默认 3）",
    "stop.anytime_alpha": "anytime-valid 停止的 δ（默认 0=关；>0 才启用该停因）",
}

# 找到 _KEY_CN 的字面量起点，插在它的第一个条目之前（保持文风与缩进）
anchor = "_KEY_CN = {"
assert s.count(anchor) == 1, s.count(anchor)
i = s.index(anchor)
j = s.index("\n", i) + 1          # 字典首行之后
lines = []
for k, v in NEW.items():
    if ('"%s":' % k) in s:
        continue
    lines.append('    "%s": "%s",' % (k, v))
assert lines, "没有需要新增的标签（都已在表内）"
s = s[:j] + "\n".join(lines) + "\n" + s[j:]

import ast
ast.parse(s)
p.write_bytes((s.replace("\n", "\r\n") if is_crlf else s).encode("utf-8"))
print("已补 %d 条中文标签（CRLF=%s）" % (len(lines), is_crlf))
