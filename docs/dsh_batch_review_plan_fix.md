# DSH 批量自审空方案修复

日期：2026-10-22
范围：`dgtf_app/server.py`、`dgtf_app/static/app.js`、`dgtf_app/static/index.html`

## 现象

- 提案库出现大量 `plan = "DSH 批量自审：待针对该任务补充具体方案。"` 的提案。
- 这些提案被确认后，修复链路仍以该占位句作为修复指令，造成逐条空跑；
  工作台实际收到的指令就是「按以下已确认提案执行修复：DSH 批量自审：待针对该任务补充具体方案。」

## 根因

1. `_auto_cycle_all` 一次把最多 80 个任务塞进一个提案请求，模型输出容易截断；
   `_extract_json` 解析失败时，代码用占位句兜底并仍以 `pending` 落库。
2. 占位提案没有「不可执行」标记：`/confirm` 可确认，`_autofix_workflow`、
   `/autofix/stream`、`/approve(/stream)` 都会把它交给 DSH。
3. `_auto_cycle_all` 判断已有提案时只统计 `pending/applied`，不含 `confirmed`，
   占位提案被确认后同一任务还会重复生成新提案。

## 修复

1. 新增 `_is_placeholder_plan()`：空方案或含占位标记即判定为不可执行。
2. 生成端 `_auto_cycle_all`：
   - 每批最多 12 条、每轮最多 24 条，要求输出「涉及文件、步骤、验证」的结构化方案；
   - 只接受长度 ≥ 40 且非占位的方案；
   - 没有具体方案的任务写入返回值的 `needs_plan`，不再落占位提案；
   - 已有提案统计加入 `confirmed`，避免重复生成。
3. 单条提案 `_auto_proposal`：DSH 未给出可执行方案时不落提案；
   方案过短（< 40 字）同样拒绝，与批量生成口径一致。
4. 确认端 `/api/dsh/proposals/<id>/confirm`：占位方案返回 400 `plan_placeholder`。
5. 修复端：
   - `_repair_with_acceptance` 入口直接拒绝占位方案，不调用 DSH；
   - `/approve`、`/approve/stream` 提前返回错误；
   - `_autofix_workflow`、`/autofix/stream` 先把占位 confirmed 提案退回 `pending`，再修复其余提案。
6. 分诊 `_proposal_triage`：占位但未过期的提案保留原状态，打 `plan_gap` 标记，
   原因记为 `plan_placeholder`，便于界面识别，不直接丢弃。
7. 新增 `POST /api/dsh/proposals/<id>/plan`：补写具体方案；已确认的提案退回 `pending`
   重新确认，旧方案保留在 `plan_history`。
8. 前端：提案卡片显示「方案待补」标记与「补充方案」按钮，静态资源版本升至 `1.4.89`。

## 存量数据

- 现有占位提案（pending/confirmed）不删除、不改写为 `failed`。自动分诊
  （`_proposal_triage`）只给它们打 `plan_gap=True`、原因记 `plan_placeholder`
  或 `plan_too_short`，**保留** 原 `pending/confirmed` 状态，便于界面显示
  「方案待补」。
- 真正把占位 confirmed 退回 `pending` 的有两处：自动修复入口
  `_demote_placeholder_confirmations()`（`/autofix`、常驻 autopilot 共用），
  以及补方案接口 `POST /api/dsh/proposals/<id>/plan`。退回后需用户补充方案
  并重新确认，不会自动改写方案内容。
- 任务队列中的原始任务保持不变，可由后续批量自审重新生成具体方案。

## 第二轮补齐（2026-10-22）

第一轮修复后复查发现仍有入口能绕过「空/占位/过短方案不进入修复」的口径，
本轮只补这些遗漏，不改变安全审查与提交权限：

1. 旧入口 `POST /api/dsh/autorepair`：原来直接用 DSH 文本落 `pending` 提案，
   现改为复用 `_auto_proposal()`，空、过短（<40 字）、占位方案均不落提案，
   返回值明确给出 `error`，不再制造新的占位 pending。
2. `POST /api/dsh/proposals/autofix/stream`：不再自己构造提示词并
   `auto_repair=True` 让 DSH 直接提交，改为与批量修复共用
   `_repair_with_acceptance()`（fast_gate + 针对性验收通过后才由工作台提交）；
   循环内再次检查方案，竞态下被改写为空/过短的 confirmed 提案退回 `pending`。
3. `_demote_placeholder_confirmations()`：把「过短（<40 字）」与占位一并视为
   不可执行，退回 `pending`，原因分别记 `manual_plan_placeholder` /
   `manual_plan_too_short`。
4. `_proposal_triage()`：`plan_gap` 判定同步覆盖过短方案，原因记
   `plan_too_short`；仍保留原 `pending/confirmed` 状态，便于界面显示「方案待补」。
5. `POST /api/dsh/proposals/<id>/plan`：补写方案的最小长度由 20 提到 40，
   与批量生成、确认、修复端一致。
6. `_split_proposal()`：拆分片段同样要求 ≥40 字且非占位，避免拆出可确认的
   空/占位子提案。
7. `_autofix_workflow()`：保留用户已确认的 `approver="user"` 标记，避免重跑时
   被 `dsh_auto` 覆盖后失去人工确认口径。

## 复核记录（2026-10-22）

- 复核了生成、确认、修复、分诊、补方案、前端六条链路，确认占位方案在
  上述每个入口都被拦截；`_autopilot_decision` 对 `confirmed` 的快速放行
  由 `_demote_placeholder_confirmations()` 在修复前兜底，不会直接送 DSH。
- 复核时存量占位提案为 30 条 `pending`、1 条 `failed`（均在磁盘上），属运行中的
  旧进程尚未重载本次代码；重启工作台后自动分诊会补 `plan_gap`，界面显示「方案待补」。
- 第一轮只收紧 `_auto_proposal` 的最短方案校验，第二轮补齐旧 autorepair 入口、
  `/autofix/stream`、分诊、拆分、补方案与批量修复入口；未改动引擎与 `dgtf_v2`，
  不触及事实谓词、probe 闭合等其它在办提案。

## 验证

- `python -m py_compile dgtf_app/server.py`：通过。
- 受控门禁（2026-10-22 第二轮）：
  - `python dgtf_app/dsh_tool.py fast_gate`：`FAST GATE PASS 12 / FAIL 0`。
  - `python dgtf_app/dsh_tool.py acceptance`：`PASS 371 / FAIL 0`。
- 纯函数检查（第一轮）：空串、空白、占位句均判 True；含文件/步骤/验证的方案判 False，
  且 `_plan_paths` 能抽出 `dgtf_app/server.py`、`dgtf_app/selftest.py`。
- 最终验收与提交以工作台统一执行为准。

## 边界

- 不改变提案的提交权限与安全审查流程；占位或过短方案只是不再进入修复。
- 已确认提案退回 `pending` 需要用户补充方案并重新确认，不会自动改写方案内容。
- 前端未做浏览器点击级自动化；静态结构由应用自检与人工核对覆盖。
