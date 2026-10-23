#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段1] 生成 bench 题库与 gold 精标。

严格照抄任务书 Step 1.1 / 1.2 的字段与取值：
- 顶层：id / domain / question / orientation / budget（+ 注释行）
- budget：profile: balanced · max_calls: 180 · rounds: "0:5,1:5,both:5,all:6" · mode: serial
  ★ rounds 是**字符串**（CLI 直传 --rounds），不是 dict。
- domain ∈ eng/biz/med/law/org/tech；orientation ∈ decision/boundary

幂等：直接覆盖同名文件。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QDIR = HERE / "bench" / "questions"
GDIR = HERE / "bench" / "gold"

# id, domain, 主题, question, orientation
QUESTIONS = [
    ("eng_001", "eng", "老城区内涝",
     "老城区暴雨内涝频发，排水系统要不要整体翻新，怎么定优先级", "decision"),
    ("eng_002", "eng", "地铁运营效率",
     "早高峰地铁站台拥挤越来越严重，运营效率该怎么提升", "boundary"),
    ("eng_003", "eng", "桥梁维护优先级",
     "在役桥梁数量多、预算有限，维护优先级怎么排", "decision"),
    ("eng_004", "eng", "地下管廊改造",
     "老城区地下管线反复开挖，要不要改成综合管廊", "decision"),
    ("biz_001", "biz", "现金流自动化",
     "一家现金流紧张的中小制造企业，该先裁员还是先砍产线", "decision"),
    ("biz_002", "biz", "出海定价",
     "产品要出海，定价按成本加成还是按当地竞品锚定", "decision"),
    ("biz_003", "biz", "供应链多源",
     "关键元器件只有一家供应商，要不要强行多源化", "decision"),
    ("med_001", "med", "社区医院远程监测",
     "社区医院人力有限，慢性病管理推远程监测还是加派人手上门随访", "decision"),
    ("med_002", "med", "慢病随访分层",
     "慢病随访人数太多随访质量下降，分层策略怎么定", "decision"),
    ("med_003", "med", "急救资源调度",
     "城区急救车响应时间不均衡，调度该怎么改", "boundary"),
    ("law_001", "law", "GDPR 跨境",
     "业务要接欧洲用户，数据跨境传输怎么合规落地", "decision"),
    ("law_002", "law", "数据共享边界",
     "集团内部各子公司数据共享的合法边界在哪里", "boundary"),
    ("law_003", "law", "合同自动审查",
     "法务人手不足，合同能不能用模型自动审查，风险怎么控", "decision"),
    ("org_001", "org", "多部门共享数据",
     "多个部门各自建系统、数据不互通，要不要强行统一平台", "decision"),
    ("org_002", "org", "组织内推",
     "内部推荐招人质量下滑，内推机制该怎么改", "decision"),
    ("org_003", "org", "跨团队协作",
     "跨团队协作长期卡在交接环节，边界责任该怎么划", "boundary"),
    ("tech_001", "tech", "订单不超卖",
     "订单系统要保证不超卖又要不卡顿，下单链路怎么设计", "decision"),
    ("tech_002", "tech", "CAP 取舍",
     "分布式订单系统在 CAP 约束下该牺牲哪一端", "decision"),
    ("tech_003", "tech", "分布式 ID",
     "业务量上涨，主键自增成瓶颈，分布式 ID 方案怎么选", "decision"),
    ("tech_004", "tech", "灰度发布回滚",
     "灰度发布出错时回滚边界该怎么定义", "boundary"),
]

Q_TMPL = """# [v122 bench] {i} · {topic}
id: {i}
domain: {d}
question: "{q}"
orientation: {o}
budget:
  profile: balanced
  max_calls: 180
  rounds: "0:5,1:5,both:5,all:6"
  mode: serial
"""

GOLD_TMPL = """# [v122 bench] gold · {i}
id: {i}
decidability_gold:
  adjudicators: 3
  final: partial
  dec_aspects:
    - "{da1}"
    - "{da2}"
  und_aspects:
    - "{ua1}"
practice_target:
  min_amps: 3
  min_threads: 2
  min_suspensions: 1
  max_ing_rephrase: 0.3
  min_anchor_touch_rate: 0.4
research_target:
  min_answered: 3
  max_distance: 0.5
  min_evidence_traced: 0.8
  must_mention:
    - "{mm1}"
  must_not_mention:
    - "{mn1}"
collision_target:
  min_third_party: 1
  min_tensions: 2
meta_target:
  meta_clean: true
  min_coverage: 0.6
action_rubric:
  min_actions: 3
  required_fields_per_action:
    - verb
    - object
    - owner_role
    - deadline_hint
    - acceptance
  must_have_fallback: true
  must_have_not_do_list: true
anchor_gold: []
"""

GOLD_FILL = {
    "eng_001": dict(
        da1="已建成排水管网的总量与瓶颈段位置可查", da2="翻新后内涝频次的下降幅度可设指标",
        ua1="整体翻新的总投资与施工期社会成本没有权威口径",
        mm1="调蓄容积", mn1="一刀切全面翻新"),
    "biz_001": dict(
        da1="两条路径的现金消耗曲线可以按月建模", da2="裁员补偿与产线处置价可询价",
        ua1="订单恢复的概率不可判定，只能给情景",
        mm1="现金消耗速率", mn1="先裁员一定更快"),
    "tech_001": dict(
        da1="库存扣减的一致性方案可选可测", da2="超卖率与 P99 延迟都是可观测指标",
        ua1="业务能接受的超卖率上限是管理决策，不是技术事实",
        mm1="幂等", mn1="用分布式锁一刀切"),
}


def main() -> int:
    QDIR.mkdir(parents=True, exist_ok=True)
    GDIR.mkdir(parents=True, exist_ok=True)
    for i, d, topic, q, o in QUESTIONS:
        # YAML 双引号串里若有 " 需转义；这里题目文本不含引号
        assert '"' not in q, f"{i} 题目含双引号，会破坏 YAML"
        (QDIR / f"{i}.yaml").write_bytes(
            Q_TMPL.format(i=i, d=d, topic=topic, q=q, o=o).encode("utf-8"))
    for gid, f in GOLD_FILL.items():
        (GDIR / f"{gid}.yaml").write_bytes(
            GOLD_TMPL.format(i=gid, **f).encode("utf-8"))
    nq = len(list(QDIR.glob("*.yaml")))
    ng = len(list(GDIR.glob("*.yaml")))
    print(f"bench/questions: {nq} 个；bench/gold: {ng} 个")
    assert nq >= 20, f"题库不足 20：{nq}"
    assert ng >= 3, f"gold 不足 3：{ng}"
    return 0


if __name__ == "__main__":
    sys.exit(main())
