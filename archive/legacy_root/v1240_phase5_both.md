# Phase 5 · F4 both 原生论证契约

状态：**已完成**：分层 6/6 + 四层 full-4 204724 通过；actions.both_v2 默认 true。

## 代码

- dgtf_v2/layers_both.py：BothArgumentPackage / assemble_both_package
- dgtf_v2/tests_both.py：10 / 10
- 引擎 actions.both_v2（默认 true）→ packed.both_argument；原生 graph 写 packed，不改 views
- 预设 configs/方案K-BothV2-pilot.yaml

## 判定

- native=True 只认 both_view.argument_graph 自带 synthesis/defeated/undecided；
- 任何一项靠 manifest/collision/adjudications/threads 映射补齐 → native=False、synthesis_origin="bridge"、gap "bridge_only"；
- 形式 completeness 可 1.0 但 ok=False，落实“契约形式通过 ≠ 语义通过”。

## 真实回放

45 份带 views.both 的历史 packed：**native=False 45/45**，44 份 completeness=1.0。  
## 真实跑（1+both，160157）

- 44 calls / 164,651 tokens；route=['1','both']；
- packed.both_argument.ok=**true**、native=**true**、synthesis_origin="native"；
- contract_completeness=**1.0**、gaps=[]；
- argument_graph：synthesis/defeated/undecided/conflict_resolution 均由 both 层产物直接落，不经 bridge。

## flag off 回滚（161136）

- 44 calls / 173,664 tokens；route=['1','both']；
- packed 无 both_argument（F4 关闭）；
- views 仍只有 1/both，桥接行为不变。

结论：**F4 分层 6/6 + 四层 full-4 通过；flag off 回滚通过；默认 true**。

## 放行条件

1. 原生 argument_graph 三件套齐全且 native=true；
2. 冲突解决读数非空；
3. core_duty both overreach=0、gaps=0；
4. 分层 6/6 与四层 full-4 均已通过；flag off 回滚通过；默认 true。
