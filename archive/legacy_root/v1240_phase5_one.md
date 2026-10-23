# Phase 5 · F3 1 层 AnswerSetPackage

状态：**已完成**：分层 5/5 + 四层 full-4 204700 通过；actions.one_v2 默认 true。

## 机制

1 层只交“筛选/研究”，不交行动：

- 每条子问题一个合法三态标签：decidable / partial / undecidable；
- decidable 必须带 citations/evidence；
- 1 层不得出现 actions/not_do（越权属于 all）；
- 输出结构化 answers + coverage + tri_distribution + citations_ok + no_actions + contract_completeness + gaps。

三态一致率只是**标签定义/诊断**，不作质量门；F3 质量看 coverage + citations + 越权 0。

## 代码

- dgtf_v2/layers_one.py：AnswerSetPackage / assemble_answer_set
- dgtf_v2/tests_one.py：10 判据
- 引擎 actions.one_v2（默认 true）→ packed.one_contract；不改 views
- 预设 configs/方案J-1V2-pilot.yaml（one_v2=true，all_v2=false，retest=false）

## 判据

    python dgtf_v2/tests_one.py
    # 10 / 10

## 真实跑（只跑 1 层，151716）

用户指定：F3 直接跑 1 层，不跑 0/both/all，省成本。

- 28 calls / 110,034 tokens；route=['1']；
- packed.one_contract.ok=**true**、gaps=[]、contract_completeness=**1.0**；
- answers=6；tri_distribution 2/2/2；coverage(contract)=.6667；
- citations_ok=**true**（2 条 decidable 都带证据）；
- no_actions=**true**（1 层无 actions/not_do）；
- core_duty 1 层：subs=6、decidable=2、**cited=2**、overreach=0、gaps=0、ok=true；
- quality.coverage=.6176；tri 仍为标签诊断（tri_state [0,0]），不作门。

修复过程：首跑 145949 发现 decidable 子问题缺 citations（one_contract.ok=false）；已把 1 层 
decidable_product.evidence 只读下放到 decidable 子问题，重跑通过；core_duty cited=2 与 
one_contract.citations_ok 对齐。

## flag off 回滚（152307）

- 25 calls / 94,798 tokens；route=['1']；
- packed 无 one_contract（契约关闭）；
- core_duty 1 层仍 ok、cited=2、overreach=0、gaps=0；
- 对比 on：28 calls / 110,034 tokens，多 3 calls / 15,236 tokens 是契约组装本身，无 LLM 行为差。

结论：**F3 分层 5/5 + 四层 full-4 通过；flag off 回滚通过；默认 true**。

## 放行条件

1. one_contract.ok=true、contract_completeness=1.0、no_actions=true；
2. core_duty 1 层 overreach=0、gaps=0；
3. bench coverage 不低于 F2 同题；
4. flag off 回滚到 F2 行为；
5. 分层 5/5 与四层 full-4 均已通过；默认 true。
