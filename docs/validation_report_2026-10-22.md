# 元DGTF 扩展目标验证报告（2026-10-22）

## 1. 本轮范围

- 常驻守护完整自动周期（缩短周期）
- 真实 UI Git 提交 / 回滚
- 引擎压力与真实跑
- 外部网络/供应商波动
- 前端/后端联网安全
- DSH Agent 联网授权
- HTTPS
- 模型训练/小模型训练
- 运行反馈学习
- 前端到后端字段契约

## 2. 出站网络与 DSH 授权

- 新增 dgtf_v2/net_policy.py：http(s) only、私网/回环/链路本地/云元数据阻断、重定向逐跳校验、端口限制、25MB 上限。
- 论文 PDF 下载、知识检索结果链接走安全过滤。
- 前端 publicUrl() 二次拦截 localhost/私网/云元数据链接。
- /api/dsh/network-policy + Agent 配置“联网：关闭/授权公开网站”；默认关闭。
- 关闭时提示禁止联网；授权时只允许公开网站检索/抓取，网页内容按不可信数据处理。
- 实测：localhost、169.254.169.254、file://、userinfo URL 均被拦截；公开 https 通过。

## 3. HTTPS

- server.py 新增 --https。
- 自动用 OpenSSL 生成/复用 dgtf_memory/tls 自签名证书，TLS1.2+，SAN localhost/127.0.0.1。
- HTTPS 下启用 HSTS，CSRF/口令 cookie 增加 Secure。
- DSH 工作台客户端支持 DGTF_APP_BASE=https://127.0.0.1。
- 实测：https://127.0.0.1:8766/api/health 200；HSTS 存在；HTTPS + CSRF POST 正常；dsh_tool 经 HTTPS 返回 403（假令牌，TLS 连通正常）。

## 4. 常驻完整自动周期

- 缩短 interval=10s，临时安全文档提案。
- 自动确认 → DSH 修复 → fast_gate 12/0 → 验收 → 自动提交 → applied。
- 测试提交 3e9f584 已回退，当前 HEAD 恢复。
- 修复停止后 daemon 状态仍显示 running：增加 agent_daemon.app.state=stopped，Autopilot 关闭时不再用日志新鲜度推断 running。
- 当前 AP/daemon 均 false。

## 5. 真实 UI Git 提交/回滚

在隔离 git worktree 中完成：

- /api/git/commit 提交测试文件，HEAD=05c7d67。
- 临时 applied 提案调用 /api/dsh/proposals/<id>/rollback，git revert 成功，HEAD=46b4c18。
- 该过程不改主工作区。

随后修复真实风险：

- /api/git/commit 不再 git add -A。
- 只提交源码/文档，dgtf_memory/产物/日志/缓存被排除或拒绝。
- 隔离 worktree 再次实测：staged 仅 dgtf_app/server.py + docs 探针，dgtf_memory/runtime_probe.txt 未进入提交。

## 6. 引擎压力与真实跑

### 并发 mock 压力

5 个 mock 任务并发：

- 总耗时 12.8 秒
- 5/5 done
- 每个任务四层产物：修行/研究/对撞/元
- head/stats 均存在
- 无 error

### 真实跑

- 受控真实跑：route=0、rounds=1、mock=false、project_context=false，90.3 秒完成，输出与 layers 正常。
- 长真实跑压力：一次默认真实任务运行超过 300 秒仍未结束，已取消并记录；说明长跑需要预算/超时控制，属于下一轮优化项。

## 7. 模型训练

- scheduler 小模型真实训练：385 行、285 训练/100 测试、122 runs。
- quality MAE 0.11181，R2 0.29343；baseline MAE 0.18037，R2 -0.00417。
- LoRA 训练：当前 HuggingFace 网络不可达，且本地 Qwen 缓存不完整；训练脚本已加入在线失败后回退本地缓存与 --offline 参数，但本机无完整基座权重，未能完成 LoRA 训练。这是外部模型依赖限制。

## 8. 运行反馈学习

- 创建真实 quality_flag 任务。
- POST /api/agent/run：triaged=1，结果写入结果库，action=生成诊断报告，交人工/下一跑观察。
- 证明“任务→消费者→结果/反馈”链路可运行。

## 9. 回归测试

- dgtf_app/selftest.py：PASS 371 / FAIL 0
- fast_gate.py：PASS 12 / FAIL 0
- 依赖链审计：PASS 58 / FAIL 0
- RAG embedding：running
- 应用版本 1.4.1，静态资源 v=1.4.86

## 10. 遗留/下一轮

- HTTPS 目前是 --https 启用，尚未改变默认 HTTP 启动策略。
- LoRA 训练需可用的 HuggingFace 网络或完整本地基座权重。
- 长真实引擎跑需要 timeout/预算上限。
- 其余高成本模型训练、更多供应商故障注入待继续。
