# dual_judge local 档接入方案（待执行；当前引擎文件被并发会话占用）

> 状态：**BLOCKED（Round 50/86/87/88 记录）** —— 引擎单文件
> `dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.3.py` 的 `git status: M`
> （其它会话改动），按"不覆盖、不回退、不格式化别人文件"约定**不强行编辑**。
> 本方案已离线写好，等引擎工作树干净后按步骤应用。

## 1. 目标

- 引擎支持 `--dual-judge-mode local`（与 `self_check` 的 local 档对称）；
- 本地 judge 用 `dgtf_local_llm/service.py`（8772，stage=`dual_judge`）或进程内
  LocalEngine（`llm_sft/adapter_dgtf_judge_05b_v2`）；
- 本地不可用/超时/低置信 ⇒ **确定性回退 llm**（fail-open，不阻塞）；
- App 层 `dual_judge local 防护`保持（Round 58：预设写 local 时回退 llm + warning）。

## 2. 现状定位（已实测）

- CLI：`Meta-DGTF-V2.2.3.py:32252`
  `parser.add_argument("--dual-judge-mode", default=None, choices=["llm","cache","auto"], ...)`
- `self_check` local 的调用链可作为模板：搜索 `self_check_mode == "local"` /
  `_local_self_check` / `--local-llm-url` 附近实现（约 7.2k/15.3k/23.4k 行）。
- 本地服务已支持 stage=`dual_judge`（`ADAPTER_CANDIDATES` 有 judge 适配器，
  `/generate {"stage":"dual_judge", ...}`）；`/metrics` 可观测。
- 本地 judge 适配器：`llm_sft/adapter_dgtf_judge_05b_v2`（存在）。

## 3. 改动点（建议 3 处，最小 diff）

1. `choices=["llm","cache","auto"]` → `["llm","cache","auto","local"]`；
2. 在双判执行函数（找到 `dual_judge_mode` 消费点）增加分支：
   - `local`：组装同样的 judge prompt → 调本地服务 `/generate`（stage=dual_judge）；
   - 超时（建议 8–20s 按题）/连接失败/JSON 非法 ⇒ 回退 `llm` 并记
     `dual_judge_mode_via="local-fallback-llm"`（trace 可审计）；
   - 成功则用本地裁决结果（结构先验与 cache 档一致）。
3. 帮助文本/README/CHANGELOG 同步。

## 4. 离线判据（先写，再真跑）

| 判据 | 内容 |
|---|---|
| T1 | `--dual-judge-mode local` 参数被接受（argparse 不再报 invalid choice） |
| T2 | 本地可用时使用本地裁决（stub 服务返回固定 JSON） |
| T3 | 本地超时/500 ⇒ 自动回退 llm，答案不中断 |
| T4 | 回退时 trace/flags 记录 `local-fallback-llm` |
| T5 | `--dual-judge-mode llm/cache/auto` 行为不变（回归） |

## 5. 真跑验收（应用后，1 次）

- 题目：`HTTP 404状态码表示什么？`（fast+web）；
- 预期：`verified/ready=True`；tokens 与 llm 档同阶；trace 显示
  `dual_judge_mode_via=local`（或 fallback 记录）；
- 对比基线：`v85-dual-cache`（0.9464/verified，646,078 tok/247s）与
  fact `web_on_fast`（0.9472/558,195 tok/174s）；
- 只变好才切换默认。

## 6. 预算

- 本地调用零 API；真跑 1 次 ≈ ¥1–3（fast+web）。
- 当前余额 ≈¥100（保留 ≥50 策略），满足。
