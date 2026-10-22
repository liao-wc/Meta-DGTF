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

- server.py 默认 HTTPS；--http 或 DGTF_HTTP=1 可回退 HTTP。
- 自动用 OpenSSL 生成/复用 dgtf_memory/tls 自签名证书，TLS1.2+，SAN localhost/127.0.0.1。
- HTTPS 下启用 HSTS，CSRF/口令 cookie 增加 Secure。
- DSH 工作台客户端支持 DGTF_APP_BASE=https://127.0.0.1。
- 实测：主服务 https://127.0.0.1:8765/api/health 200；HSTS 存在；HTTPS + CSRF POST 正常；dsh_tool 经 HTTPS 返回 403（假令牌，TLS 连通正常）。
- 切换 HTTPS 后 dgtf_app/selftest.py 371/0、依赖链审计 58/0 均通过。
- 自签名证书已导入 CurrentUser\Root（证书 CN=localhost，SAN=DNS:localhost,IP:127.0.0.1，CA:TRUE，到期 2029-01-24）；Edge headless 无证书错误加载应用，Invoke-WebRequest 无跳过校验 200。
- 新增 scripts/trust_https_cert.ps1，供其他设备/新用户信任本机证书。

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
- 长真实跑压力：一次默认真实任务运行超过 300 秒仍未结束，已取消并记录。
- 任务级 timeout_s 已加入 engine_runner：传 opts.timeout_s 后到点自动终止并标 timeout/cancelled/partial；用 timeout_s=0.01 实测自动终止。

## 7. 模型训练

- scheduler 小模型真实训练：385 行、285 训练/100 测试、122 runs。
- quality MAE 0.11181，R2 0.29343；baseline MAE 0.18037，R2 -0.00417。
- LoRA 训练：HF 直连超时，改用 hf-mirror 后成功加载 Qwen2.5-0.5B-Instruct，1 epoch 完成。
  - train_loss=0.055，val_loss=0.1308，epoch 135.7 秒。
  - 评估：route_exact=0.429，round_mae=1.5，n=14。
  - 产物：llm_sft/_audit_lora（adapter + tokenizer + metrics.json）。
  - 训练脚本已加 HF_ENDPOINT 前置和离线缓存回退。
- 外部波动：HF 直连超时，hf-mirror 可用；说明镜像/离线回退路径有效。

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

- HTTPS 已默认启用：`python dgtf_app/server.py` 默认 HTTPS；`--http` 或 `DGTF_HTTP=1` 回退 HTTP。证书为自签名，浏览器会提示一次。
- 长真实引擎跑可用任务级 timeout_s 控制；默认不设上限，需按预算显式传。
- 更多供应商故障注入、全量长时压力、前端交互全按钮回归仍可继续。

## 11. 交付物

- 出站网络策略：dgtf_v2/net_policy.py
- HTTPS/DSH 网络配置：dgtf_app/server.py
- Git 安全提交范围：dgtf_app/server.py:_git_commit_scoped
- LoRA 训练兜底：train_llm_lora.py
- 验证报告：docs/validation_report_2026-10-22.md
- 依赖链审计：docs/dependency_chain_audit.md
