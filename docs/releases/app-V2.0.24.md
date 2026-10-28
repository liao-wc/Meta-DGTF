# App V2.0.24 发布说明

日期：2026-10-25
类型：MINOR（App；引擎同步升级到 V2.2.3）
上一版：App 2.0.23

## 主题

新增「**道生专属模式**」（`mode="daosheng"`）：面向 Meta-DGTF 项目自身的质量优先
调度预设，并把 **App / 引擎 / 本地模型** 三者的读数汇成一份可审计计划（plan），
引入预算守卫与本地模型三级回退。普通任务路径保持不变（默认 `mode="auto"`）。

## 新增

| 文件 | 说明 |
|---|---|
| `configs/道生专属模式.yaml` | 专属模式预设：App plan 数据源 + 引擎可识别子集 |
| `dgtf_app/daosheng_mode.py` | plan 生成器：模式/联网/质量策略/预算守卫/本地模型回退/记忆注入 |
| `scripts/app_daosheng_check.py` | 专属模式契约检查（10/10） |
| `docs/app_daosheng_mode.md` | 模式定义、plan 字段、回退链 |

## 行为

- `POST /api/tasks` 新增 `mode` 字段：`daosheng` / `auto`（默认）/ `standard`；
  `auto` 对项目相关题自动分流到 daosheng，其它题走既有 quality_policy 全自动链路。
- 201 响应新增 `mode`：`{id, requested, tier, policy, engine_mode, reason,
  context_injected, budget_guard, plan}`；`GET /api/tasks`、单任务、retry/resume
  三处都回显（重试不丢）。
- 预算守卫：读真实余额（失败 fail-open，绝不拒任务）；余额 < ¥8 自动降
  `daosheng_fast`（低圈/thinking off），< ¥4 仍建任务但 plan 告警。
- 本地模型：优先调用 `http://127.0.0.1:8772` HTTP 服务（stage=route，1.5s 总预算），
  不可达→子进程（若存在）→规则，三级回退；绝不阻塞建任务。
- 记忆注入：从 `dgtf_memory/MEMORY.md + playbook.jsonl + episodes.jsonl` 取
  相关性摘要（≤1600 字，mtime 缓存），只对道生模式注入；普通任务不受影响。
- 引擎能力探测：V2.2.3 出现后自动透传 `--self-check-mode / --stage-thinking` 等新键；
  旧引擎不传（不会崩）。
- 前端只读展示「模式 · 策略」标签，无新按钮（延续 2.0.17+ 的少按钮原则）。

## 验证

- `python dgtf_app/selftest.py`：**PASS 444 / FAIL 0**（基线 371 + ★T3 新增 73）。
- `python scripts/app_daosheng_check.py`：**10 / 10 PASS**。
- mock 端到端 `POST /api/tasks mode=daosheng` → **201**（真实 API 0 次）。
- V2.2.3 加载 `configs/道生专属模式.yaml` 实测生效
  （self_check_mode/dual_judge_mode/parallel_mode/runtime 键均按预设）。
- 预算守卫真实路径实测读到余额（balance_source=runner）。

## 已知边界

- 本地模型 8772 当前为 0.5B 演示适配器（60 样本/1 epoch），self_check_min p50
  6.3s；其决策字段质量尚待 eval 数字，本轮**不默认接管**质量档的决策字段。
- 道生模式质量档 rounds=auto（不硬编码高圈），真实一次约 1.27M tokens / ¥2~4；
  预算守卫触发时自动降级。


## 补丁（同日）：DSH 本对话读取失败自愈

现象：App DSH 视图显示“读取失败：signal is aborted without reason”，
/api/dsh/current/events?full=1 返回 502。

根因：
- DSH GUI 端口变为 61044，App 进程内 DSH_WEB_URL 仍是旧值，且
  _dsh_current_web_base 的兜底端口列表不含 61044；
- 前端 api() 对 DSH 整段事件读取只等 30s，Abort 后直接暴露浏览器原文。

修复：
- dgtf_memory/dsh_web_url.txt 写入当前 DSH URL，并作为第一优先级；
- 兜底端口加入 61044/61045；
- 探测成功后自动回写 dsh_web_url.txt（端口变化后自愈）；
- DSH current events/messages 前端超时 30s→90s；
- Abort 时显示“读取超时…正在自动重试”，轮询继续自愈。

验证：写入当前 URL 后 /api/dsh/current/events?full=1&limit=100
返回 200（307ms，100 events）；App 视图下一次 700ms 轮询即可恢复。


## 交互修正：点击 DSH Agent 只切换模式

按用户反馈，点击「DSH Agent」不再直接进入/恢复会话：

- 点击仅切换 dshMode（占位提示、当前任务绑定、历史栏）；
- 不自动恢复 localStorage 会话，也不自动 openDshCurrentLiveView；
- 用户发送第一条消息时，startDshCurrentRun 才进入当前 DSH 对话/创建视图；
- 历史会话仍可从 dsh 历史栏手动打开。

验证：app.js 语法检查通过；toggleDshMode 内已无 openDshCurrentLiveView()/loadDshConversation() 自动调用；发送路径保留。


## 交互修正：首屏提示语与输入左对齐

- 提示语改为：可以给Meta-DGTF发消息，我们一起去探索吧
- textarea#question 的 text-align 由 center 改为 left；输入光标随之左对齐；
- index.html placeholder、app.js Q_PLACEHOLDER、selftest 断言同步更新。


## 交互修正：占位语、回车发送、Ctrl+回车换行、发送键提示

- 首屏提示语：给Meta-DGTF发消息 我们一起探索吧 ....
- 输入框内：Enter = 发送；Ctrl/Cmd+Enter、Shift+Enter、Alt+Enter = 换行；
- 全局 Ctrl/Cmd+Enter 在输入框内不再抢发送；
- 发送键悬停标题改为「开始深究」（去掉快捷键括号）。


## 新功能：输入框粘贴图片/文件（双通道）

- 普通模式粘贴：直接调用既有 /api/library/import（App 资料库导入）；
- DSH Agent 模式粘贴：调用新增 /api/dsh/attach，保存到 dgtf_memory/dsh_attachments，
  并把本机路径回填输入框；DSH Agent 可直接读取这些附件路径；
- 支持多文件/剪贴板图片，单文件上限 50MB，最多 20 个；
- 纯文本粘贴不拦截，保持原行为。


- 兼容旧服务进程：若 /api/dsh/attach 尚未加载（404），DSH 模式会自动回退到
  /api/library/import，并把 dgtf_app/anchors/<saved_as> 路径回填输入框。


- DSH 粘贴附件不再回填原始路径文本，改为 composer 内白色缩略图/文件卡预览（可点 × 移除）；
  发送时自动把附件路径作为【粘贴附件】上下文并入 DSH 消息。


- 普通模式粘贴也使用 composer 内缩略图/文件卡预览（后台走 App 资料库导入，不再弹“已导入 0 个”小窗）；
  发送成功后自动清空预览；DSH 模式仍额外把附件路径并入消息。


- 点开粘贴附件卡可查看：图片直接放大；文本/导入的 anchors 文件读取内容；
  新增 /api/attachments/view（仅允许 anchors / dsh_attachments 两个目录）。


- 首屏移除“深度思考 / 智能搜索”两个胶囊：默认交给引擎 auto 自决；
  需要强制开启时在高级参数里设置 thinking / web。


- 首屏输入框：placeholder 提示语**居中**，用户输入内容与光标保持左对齐。


- 首屏提示语改为“给Meta-DGTF发消息，我们一起去探索吧”；
  空闲时在 20 个跨领域热门问题与 CTA 之间按 8–18s 随机间隔轮询。


- 首屏欢迎语改为以文字为基准居中（logo 放文字左侧）；
- 输入框基础提示“给Meta-DGTF发消息，我们一起探索吧”左对齐，轮询问题居中；
- 热门问题按领域随机，每次切换不同领域，6–12s 不定期更新。


- 欢迎语与热门问题整体右移一点点；基础提示与热门问题每 10 秒交替显示；
- 热门问题按领域随机（连续不同领域），并按“近期热门 > 用户兴趣 > 未解之谜 > 玄幻/科幻”加权。


- 热门话题改为“DSH Agent 写入 dgtf_memory/hot_topics.json，App 接口只读文件”：
  接口不再扫会话/不做关键词统计；DSH Agent 用 scripts/write_hot_topics.py 原子写入。


- 提示语整体右移 12px；基础提示改为“给Meta-DGTF发消息，一起去探索吧......”；
  轮询周期改为 12 秒，并增加最近 12 条问题去重，降低重复感。


- 基础提示改为“发给Meta-DGTF，一起去探索吧......”；欢迎语 logo 与文字间距 12px → 6px。


- 基础提示改为“发给Meta-DGTF 一起去探索吧 ...”；欢迎语与输入框整体上移 22px。


- 任务完成后，点击左上角“完成”徽章可回到首屏。

- 热门领域问题由 DSH 守护自动接管：巡检时检查 hot_topics.json 年龄，超过 6 小时则在巡检任务中要求 DSH 更新。
