# 接管目标完成状态（2026-10-22）

## 核心目标

- [x] DSH 接管：源码/文档/配置/测试可读写；git add/commit/tag/版本迭代；push/密钥/ACL 保持人工确认。
- [x] 提案：pending=0；全部有结论与证据。
- [x] App 可上线：HTTPS/鉴权/CSRF/Host/上传与 JSON 上限/超时/401/孤儿任务/原子写/日志保留/scratch 清理/前端错误提示/上线检查单。
- [x] 引擎准确与深度：fact gate、process/answer 分离、answer_summary/depth、否定结论审计、答案相关性/URL 门。
- [x] 全自动帕累托：后台自动选优 + 任务级 auto_policy 圈数执行。
- [x] 本地模型更多权重：自动策略实测 last_strategy=local_model，并影响任务圈数预算。
- [x] 正向真实跑：len 69 calls/652846 tokens/约12min；answer_ready=true、process_ready=4/4、answer_quality=verified、gaps=[]；app score=85 A。
- [x] 门禁：fast_gate 12/0、selftest 371/0、依赖审计 78/0、HTTP 200。

## 版本

- app：2.0.0（app-V2.0.0）
- engine：2.0.0（V2.0.0；F5 生成完成）
- 最新提交：8da4977
- pending 提案：0
- auto_strategy：local_model

## 人工/外部边界

- git push / 远端仓库 / 凭据 / ACL / 生产部署 / 服务账户：仍需人工确认。
- 真实联网质量受搜索源影响；算法层已用答案门/相关性门兜底，不再把噪声冒充事实。

## 用户复核项完成记录（2026-10-23）

- [x] 本机打开 App：已通过 show_access_url 打开；认证页面关键控件存在，dgtf_app/selftest.py PASS 371/0。
- [x] 浏览器 favicon 与桌面快捷方式图标统一为 dgtf_app/static/dgtf.ico；桌面 .lnk 与快速 .url 均指向该图标。
- [x] python scripts/cleanup_runtime.py --apply：删除 4 个 __pycache__，未动 outputs/dgtf_memory。
- [x] auto_policy vs profile A/B：auto_policy 90 calls/881364 tokens/1164.7s，verified 4/4；profile auto 116 calls/1073702 tokens，1201.6s 超时无 packed。报告 reports/goal_ab_auto_policy_20261023.md。
- [ ] git push：远端 github.com:443 连接失败（无法访问），未推送。
- [ ] 生产部署：无远端部署目标；本机 App 继续运行在生产入口 https://127.0.0.1:8765/。


---

## V2.1.0 收束状态（2026-10-23）

- 版本：V2.1.0（历史谱系融合）
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.1.0.py
- App：2.1.0
- 历史融合：178 个版本 / 17 条能力轴 / readiness 1.00
- 门禁：fast_gate 12/0、V2 tests 33/33、App selftest 371/0、pip check 0 broken
- 文档：docs/history/、docs/releases/V2.1.0.md、V2.1.0-收束报告.md
- 历史仓库名：GitHub 仓库名仅 ASCII，使用 Meta-DGTF；完整中文名用于描述和文档
