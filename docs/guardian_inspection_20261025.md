# DSH 守护自动巡检报告（2026-10-25）

## 检查项

- 守护状态：enabled=true，interval=3600s，last_error 为空，checks=18，thread_running=true，takeover 开启；
- 任务队列：54 行；未关闭占位/空标题=0；App 运行态 running/queued=0；
- 提案：197 条，pending=0，high 未关闭=0（expired 156 / superseded 18 / rejected 12 / applied 6 / failed 4 / rolled_back 1）；
- 依赖：app Python 与 local_model 环境 pip check 均为 0 broken；
- 工作区：巡检开始时 git status 干净，HEAD=8b46ebb；
- 最近日志：最新 App run 日志无错误；历史 20261025_010851 有 1800s 超时记录（已定位为 M4 被行为融合覆盖 + 项目背景注入所致，前一版本已修复）；
- 门禁：fast_gate 12/0；V2 39/39（534 项检查）；App selftest 371/0；verify PASS；loop 6/0；precheck 5/5。

## 修复项

1. 巡检发现 loop B / precheck G5 因最新联网遥测跑 20261025_022430_11等于几.packed.json（answer_quality=needs_evidence）失败；
2. 补跑一条质量门 verified 的 B 模式真跑 20261025_041804_为什么城市热岛...packed.json（quality 0.9513、verified、flags 2）恢复最近运行质量基线；
3. loop E 的联网遥测由 20261025_022430（web_enabled=True、search=6）满足，窗口 8 份中联网活动 1 份；
4. 无 pending 提案需要修复/关闭；
5. 补充 CHANGELOG 中 App 2.0.12 / 2.0.13 记录。

## 验证结果

- loop：PASS 6 / FAIL 0
- precheck：PASS 5 / FAIL 0
- fast_gate：PASS 12 / FAIL 0
- V2：39/39，checks 534
- App selftest：371/0
- pip check：两环境 0 broken
- 路径校验：RESULT PASS
- App 运行态：app 2.0.13 / engine 2.2.2，running 任务 0

## 待人工确认风险

- 本次巡检只做本地 git commit，未执行 git push（守护模式禁止）；如需要请人工推送；
- 最新质量跑 tokens 1,768,649、wall 约 31min，属长跑样本；不影响质量门但成本需注意；
- 历史 App 超时任务的部分中间产物保留在 dgtf_app/runs/ 与 outputs/，未删除（删除项目数据被禁止）。
