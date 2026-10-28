# App V2.0.36（2026-10-28，就绪原因出口 + 溯源指纹）

## 主题
V2.2.8–V2.2.11 收束：产物落盘崩溃修复（0 层渲染兜底 + 应急落盘）、成本归因
三批盲区清零（unknown 桶消除）、`answer_ready_reason` 三出口同源、
provenance 版本指纹动态推导、e2e 产物隔离与本地链路提速（900s+ → 16~70s）。

## 改动
- 引擎 V2.2.8~V2.2.11（`dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.11.py`）：
  · V2.2.8：`save_result` 不再因 0 层非标准结构整份丢产物（.get 兜底 + 整块
    try/except 留痕 + `_emergency_dump` 写 `outputs/_crash/`）。
  · V2.2.9/V2.2.10：`LLM.call` 新增独立 `cost_stage`；三批共补 25+ 处调用点
    stage/cost_stage ⇒ 产物 `llm_by_stage` 无 `unknown` 桶。
  · V2.2.11：`answer_ready_reason` 此前只写 decision_trace 一个出口（answer_ready
    有三个），实测 85 个未就绪包里 73 个 quality 里是空 ⇒ 一致性护栏把
    verified+!ready(无原因) 判成矛盾。现三出口同源；未就绪且仍空时由
    过程合同/原始就绪/答案质量/题型拼可指认兜底原因。
- `dgtf_v2/provenance.py`：engine_file 与 engine_version 两处硬编码且自相矛盾
  （file=V2.2.4 / version=V2.2.3）⇒ 改为 `__main__.__file__` 优先、否则引擎目录
  最高版本；version 从同一文件名推导，结构上不可能再对不上。
- 本地链路：`gates.py` 建 stage 生成长度唯一表（`cap_max_new` 只压不抬），
  服务与 shim 共用；shim 透传 503 排队信息；服务加载前先占端口（冲突 exit 2）。
  整跑 900s+ → 16~70s（丢 CUDA graph 快路径的慢路径 150ms/token 是根因）。
- e2e 产物隔离：`scripts/local_model/e2e_app_local.py` 落 `outputs/_e2e_local/`
  （链路验证样本是本地 0.5B，不代表生产质量，不再混进生产统计）。
- 判据：新增 `tests_ready_reason.py`（14 项）、`tests_save_robust.py`（17 项）、
  `tests_cost_stage.py`（18 项，E1 锚修正为 provenance 判版 + E1b 有牙自检）、
  `tests_provenance.py` P5~P9、`scripts/local_model/test_max_new_cap.py`（21 项）、
  `e2e_app_local.py`（18 项，走 App 真入口）。

## 验证
- `final_acceptance.py` **21/21 PASS · ALL GUARDS PASS**（此前 19/21）。
- `v2_tests` 61/61（976+ checks）；`fast_gate` 12/12；e2e 18/18（16~53s）。
- 真跑产物：provenance=V2.2.11（文件与版本同源）、`quality.answer_ready_reason`
  非空且三出口一致、`llm_by_stage` 无 `unknown` 桶。
- 旧引擎历史样本 unknown 调用数 8971（显式记录，不改写历史）。
- 归档（用户批准）：14 个今早 e2e 文件 `outputs/` → `outputs/_e2e_local/`
  （回退：`mv outputs/_e2e_local/20261028_08* outputs/`）。
