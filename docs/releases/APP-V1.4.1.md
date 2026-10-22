# 元DGTF app V1.4.1 发布说明

日期：2026-10-21
类型：patch

## 变更

- “联网”与“刷新技术知识”合并为单一“知识检索”入口；
- 按钮和自由查询均走 DSH 知识检索会话，展示检索/爬取/质量筛选/入库过程；
- 官方/权威/最新/高置信/高相关优先，低价值源降权；
- 本地资料库描述更新：anchors 证据参与 RAG，不训练、不外发、可删除；
- 首屏欢迎语/输入框再上移（padding-bottom 36→52px）；
- 修复首屏可见性：移除面板打开时的 visibility 隐藏规则，静态资源加版本号。

## 修复

- 首屏以输入框为基准居中后整体下移约 30px；固定 --home-shift=-20px，避免反复测量漂移；
- Agent 技术知识库标题描述换行，不再遮挡 chip/标题；
- API 对 501/502/503 自动重试一次，错误文案改为“接口暂不可用（501）”；
- 回形针悬停说明更新为本地资料库/RAG 语义；
- 静态资源版本 v=1.4.10。
- Agent 顶部说明恢复原背景（透明），时间紧随描述；字体 12→11.5；
- Agent 工具栏按钮统一为与任务标签一致的描边胶囊样式；
- GitHub 状态描述字号 10.5px；
- 静态资源 v=1.4.12；
- Agent 说明改为面板 title（不显式显示），时间不再单独显示；
- `main` 状态、GitHub Desktop、提交当前变更移到自洽审计标签后同一排，字号与按钮一致（12px）；
- Agent 工具栏按钮与任务标签统一描边胶囊；
- 高级参数分组按钮英文 key 映射为中文（全开开关/自动调参/信念/主张缺口/职责开关/外部输入/最大 Token/剧本/调度器/仿真/停止条件）；
- 高级参数底栏按钮统一 12.5px 胶囊。
- 静态资源 v=1.4.13；
- 高级参数分组从 21 个合并为 8 类（任务指令/模型与接口/运行与调度/联网与资料/四层与收尾/记忆与探针/动作与职责/输出），参数项不变；按钮用大白话，进入分组标题恢复原 label；
- 侧边栏按钮自适应间距 8–16px → 11–20px；Agent 置顶，产物库/本地资料库/联网检索库置底；
- 侧栏环境信息恢复紧凑行格式，引擎/DeepSeek/Tavily/本地 LLM/Agent/产物每行同一绿灯；
- 侧栏头部/状态整体上移并左对齐（元DGTF、引擎、DeepSeek、Tavily、本地 LLM、Agent、产物）；
- 每行统一绿灯，行距紧凑；按钮区上移折中，避免压住“产物”行；
- 侧栏状态行统一单行（DeepSeek/Tavily 与引擎一致），整体再上移、行距再缩小；按钮再上移；元DGTF 头部居中；
- 侧栏头部→状态、状态→按钮两段间隔拉大且相等；DeepSeek/Tavily 标签改为“模型 DeepSeek / 联网 Tavily”；
- 侧栏状态整体再上移，头部→状态与状态→按钮间距等距；标签改为“模型 DeepSeek / 联网 Tavily”；
- 侧栏状态信息水平居中并上移，按钮同步上移相同距离；
- 状态改为“模型 DeepSeek / 联网 Tavily”不写已配置；灯按真实可用性绿/灰，30s 实时刷新；标签统一白色；
- 侧栏状态可用灯与标签统一蓝色，值统一白色等宽；
- 侧栏状态可用灯恢复绿色，标签蓝色；DeepSeek/Tavily 等值统一白/等宽同引擎值格式；
- 侧栏状态值统一加粗高亮（白字/等宽/发光），标签蓝色、灯绿色；
- 侧栏状态值改为纯文本统一渲染，避免局部加粗/字体不一致；
- 侧栏状态值对 CJK 也强制加粗高亮（描边 + 光晕），解决“元/个底座/默认/就绪/守护运行/份”不显粗；
- 侧栏状态值去掉高亮（保留加粗白字），标签统一蓝色高亮；
- 侧栏状态值不加粗，标签加粗；
- 标签不加粗；状态区字号/行距再缩小、整体上移，按钮同步上移；
- 状态区字号/行距再缩小，整体与按钮再同步上移；
- 侧边栏向右展开宽度略增（1440 视口 240→260px）；
- 侧栏状态字号 9px、行距 14px，标签常规不加粗；
- 侧栏状态与按钮整体下移一点点，标签保持不加粗；
- 侧栏状态与按钮再整体下移一点点；
- 侧栏按钮整体再下移一点点；
- 静态资源 v=1.4.61；
- DSH Agent 修复必须 fast_gate + 针对性验收都通过才提交；不通过带失败信息回到同一 DSH 会话继续修，最多 3 轮，仍不过则不提交；
- DSH Agent 面板新增「常驻守护」开关：开启启动队列守护 + Autopilot；默认关闭；
- Autopilot 按分类/优先级/计划质量自动分流安全提案，高风险留人工；自动修复走 DSH→fast_gate→验收→提交，知识检索作为学习材料；
- 自动修复前自动确认安全 pending；关闭常驻时点「自动修复提案」同样先分流；人工确认的高风险项可再次提交自动修复；
- 每次修复/提案记录 DSH 会话 conversation_id，可追溯；修复串行、DSH 会话并发；
- 安全加固（v=1.4.62）：Host 白名单、Origin/Referer 校验、CSRF、安全响应头；DSH 敏感路径运行时拦截 + 密钥输出脱敏；自动修复安全审查不通过不提交；app 启动自动拉起本地 BGE embedding 服务。
- 所有 DSH Agent 调用统一走 _run_dsh_agent 会话留痕：事件实时写入 dsh_conversations（dshrun-*），DSH 会话页可回看过程与结果；
- 真跑验收（2026-10-22）：DSH 实际新建探针文件 → 工作台 fast_gate 12/12 → 针对性验收 371/0 → 安全审查 0 发现 → 只提交计划内文件；暴露并修复 fast_gate 的 GBK/UTF-8 子进程误判，以及自动提交误收运行期临时文件的问题。
- DSH 受控工作台工具：每次 run 短期令牌，开放 fast_gate / acceptance / status / project / proposals / queue 固定动作；DSH 可自行查看门禁、本次改动、队列与提案，最终提交仍由工作台复核。
- 元DGTF 验收：smoke_test.py 退出码 0（PASS 22 / FAIL 0，审计 AUDIT 70/0）；app selftest 371/0；fast_gate 12/0；依赖链审计 41/0；DSH 直连工作台 project 实测 ok。
- DSH 权限四档与工作台对齐：只读 / 读写工作区 / 完全访问 / 自动审查；只读实测写入被拒，完全访问与自动审查实测可运行；权限选择 localStorage 持久化；静态资源 v=1.4.65。
- CSRF 令牌跨 app 重启持久化，旧标签页不再因服务重启报“CSRF token 缺失或无效”；前端 403 自动刷新令牌重试；静态资源 v=1.4.67。
- 侧栏状态：Agent 就绪不再要求守护进程运行（守护关闭时显示 DSH 就绪 · 守护关闭）；新增“应用 v1.4.1”状态行。
- 常驻守卫真实验收：开启后 thread_running=true、daemon=running；安全探针自动 pending→confirmed→applied，DSH 会话 dshrun-1792617190441，fast_gate 12/0、验收通过、安全审查通过、只提交 docs/autopilot_probe.md；关闭后 enabled/thread/daemon 全部 false。
- 自动学习/提案/修复真实验收：手动“学习刷新”知识条目 37→43；自动从队列生成 proposal 并自动 confirmed；提案学习超时改为本地知识兜底，不阻塞修复；自动修复探针 applied，DSH 会话 dshrun-1792618962733，fast_gate 12/0、验收通过、安全审查通过、只提交计划内文件。
- Agent 配置新增“学习刷新 / 从队列发起提案 / 项目自主审视 / 自学习提案”手动触发按钮，和自动周期共用节流记录。
- 无待处理提案时自学习：读取项目现状 + 知识库/检索材料，由 DSH 自提优化/修复提案；提案带 source=self_learning、self_learned=true、自学习材料字数、HEAD/时间；UI 显示“自学习”标记；经安全评估决定自动修复或待人工确认。
- server.py 安全边界：自动修复仍拒绝 server.py/dsh_tool.py；用户人工确认后可修，但必须保留 CSRF/Host/CSP/权限/工作台令牌等关键安全结构（security_invariants），新增代码仍过密钥/危险执行扫描；.env/.ssh/.git/依赖清单依旧硬拒绝。
- 提案库新增“拆分提案”：把含 提案1/提案2 的复合计划拆成独立 pending 提案，父提案标 expired/split_into_children；根目录批量清理词（归档/清理/删除/批量/根目录/历史版本）自动转人工。自学习复合提案已拆为 server.py 与根目录清理两条独立提案。
- 点击提案卡片或“拆分提案”会先进入 DSH Agent 会话做只读分析（涉及文件/风险/是否适合自动修复/拆分建议），分析完成后再由用户确认；拆分按钮分析后弹确认，确认才真正拆分。静态资源 v=1.4.72。
- 提案排序：pending/confirmed 优先，其余按最近处理时间倒序；任务/结果/知识/DSH会话/DSH产物库同样“活跃或新建优先，其余按最新”。
- 提案新增“不修复”和“已另行处理”：分别标记 rejected / superseded，保留原因、时间和会话；已关闭提案不再自动修复。用户分析后决定不修，或让 DSH 自定义修复后，点“已另行处理”即可关闭原提案。
- rejected/superseded 提案支持“重新打开”：恢复 pending、刷新 ts 参与最新排序，并在 reopen_history 保留上次关闭原因/时间；静态资源 v=1.4.74。
- DSH 会话库改用实时 conversations：正在运行的会话即时可见（运行中/排队/中断/完成/失败），修复 DSH 会话在 Agent 面板只显示“已完成 runs”、运行中缺失/状态错误的问题；运行事件每秒热存，点会话可直接续聊。
- 会话切换加固：切换时先停旧轮询、关闭面板、清空旧视图；旧会话的异步响应/轮询不能覆盖新会话；静态资源 v=1.4.76。
- 运行中会话可见性/状态：启动时 reconcile 遗留 queued/running 为 interrupted；会话列表和快照发现无 worker 的 running 自动改 interrupted；Agent 面板 DSH 会话每 3 秒实时刷新；状态明确显示 运行中/排队/中断/完成/失败，不再把中断显示成运行中或完成。
- 库动作透明化：Agent 面板新增“最近动作”记录（刷新/学习/提案/确认/拒绝/重开/拆分/提交任务等，成功失败+时间），每个库标题显示更新时间/条数/读数异常；动作记录持久化 localStorage；静态资源 v=1.4.79。
- API 自洽修复：任务空标题/重复改为 400；缺失 conversation/session/proposal/artifact 改 404；未知常驻动作 400；PUT/DELETE/PATCH 统一 405 JSON，不再返回 HTML 501。
- UI 自洽：移除被 CSP 拦截的 Google Fonts 外链，改本地 favicon；提案数量按“非过期”显示并标注总数；DSH 会话/产物不再只显示前30条，数量与列表一致；提案汇总增加“失败/可重试”计数；最终静态资源 v=1.4.82。
- 资料库链路真测：导入/重复导入/列表/删除全通，删除路径穿越（../、绝对路径、Windows 路径）均 404，不会越界删除。
- 出站网络防护：新增 dgtf_v2/net_policy.py，对由外部检索结果驱动的 URL 做 http(s) 白名单、私网/回环/链路本地/云元数据阻断、重定向逐跳校验、端口限制、25MB 上限；论文 PDF 下载改走安全 opener；知识检索结果中的私网/危险链接在服务端和前端双层拦截。
- DSH 联网授权：新增 /api/dsh/network-policy 与 Agent 配置“联网：关闭/授权公开网站”；关闭时提示禁止联网，授权后提示只允许公开网站、禁止内网/回环/元数据/凭据上传，并把网页内容视为不可信数据；状态落盘 dgtf_memory/dsh_network.json。
- HTTPS：server.py 新增 --https，自动用 OpenSSL 生成/复用 dgtf_memory/tls 自签名证书（TLS1.2+，SAN localhost/127.0.0.1）；HTTPS 下发送 HSTS，CSRF/口令 cookie 加 Secure；DSH 工作台客户端支持 DGTF_APP_BASE=https://127.0.0.1。静态资源 v=1.4.85。
- 常驻守护状态自洽：停止后写 agent_daemon.app.state=stopped；Autopilot 关闭时不再用“日志还新”推断 running；完整自动周期实测（临时安全文档提案，缩短 interval=10s）：自动确认→DSH 修复→fast_gate 12/0→验收→提交→applied，测试提交已回退。
- UI Git 提交安全范围：/api/git/commit 不再 git add -A；只提交源码/文档（复用 _commit_scope），dgtf_memory/产物/日志/缓存/已暂存运行文件拒绝或排除；隔离 worktree 真测 commit 与 proposal rollback 均通过，运行记录未进入提交。静态资源 v=1.4.86。
- 模型训练：HF 直连超时后经 hf-mirror 成功加载 Qwen2.5-0.5B-Instruct；LoRA 1 epoch train_loss=0.055/val_loss=0.1308，eval route_exact=0.429/round_mae=1.5，产物 llm_sft/_audit_lora；train_llm_lora.py 前置 HF_ENDPOINT 并支持离线缓存回退。
- 引擎长跑保护：新增任务级 opts.timeout_s；到点自动 kill 并标记 timeout/cancelled/partial，真实长跑可用预算上限。
- HTTPS 默认化：server.py 默认 HTTPS；`--http` 或 `DGTF_HTTP=1` 可显式回退 HTTP（兼容旧测试/客户端）。默认启动：python dgtf_app/server.py；HTTPS 证书仍为 dgtf_memory/tls 自签名。
- 本地证书信任：新增 scripts/trust_https_cert.ps1，用 certutil 把 dgtf_memory/tls/cert.pem 加入当前用户 Root 存储；仅信任这一张自签名证书；加入后重启浏览器即可不再出现“连接不是专用连接”。
- 前后端映射审计：新增任务/结果/知识/DSH 会话/提案字段契约与动作透明化钩子检查，依赖链审计 PASS 48 / FAIL 0。
- 知识检索真跑：POST /api/agent/knowledge/agent-search（query=RAG 检索 引用 技术，limit=1）48.8 秒返回 1 条高质量结果并创建 dshknow 会话；知识检索/去重完成信息写入“最近动作”；静态资源 v=1.4.83。
- HTTP keep-alive 自洽：POST body 在路由前一次性读取并缓存，所有 POST 路由（包括不读 JSON 的 reopen/split/confirm）不再把 body 留在连接里；修复浏览器控制台偶发 "{}GET" → 501 Unsupported method。同一连接 POST reopen 后 GET health 已实测 200。
- HTTP 方法自洽：HEAD 返回 405+Allow、OPTIONS 返回 204+Allow、PUT/DELETE/PATCH 返回 405 JSON+Allow；不再落到 BaseHTTPRequestHandler 的 HTML 501。
- 失败提案处理：卡片显示失败原因；提供“重新打开/重试修复”“不修复”“已另行处理”；重开会把上次 result/acceptance/security/attempts 存入 last_failure，状态恢复 pending，重新走安全评估。rejected/superseded/failed/rolled_back 都可重新打开。
- 自学习真实验收：手动触发生成 prop-1792620206762（自学习标记，方案含 server.py 与根目录清理），分诊 docs/P2，安全评估因 sensitive_term:server.py 判定人工确认，未自动提交。静态资源 v=1.4.69。
- Agent 面板刷新改为刷新全部库（队列/结果/知识/DSH会话/DSH产物/提案/运行/V2/审计/资料库/联网库）；
- DSH Agent 配置下拉选项修正深色背景/浅色文字对比；
- DSH 修复提案安全评估扩大：敏感路径、危险命令、网络/提权/编码命令、敏感文件变更均转人工或拒绝提交。
- 提案/自审模式允许读取项目文件核对现状（仍不改源码）；DSH 默认 workspace-write/PTC 与面板配置一致。
- 修复提案自动分诊：分类(quality_signal/probe_quality/fact_correctness/agent_runtime/process_gap/eml_experiment/verification/docs/noise) + 优先级 P0-P3；
- 每次分诊写 `dgtf_memory/dsh_proposals/_index.json`（计数/分类/优先级/项目 HEAD/队列规模）并保留 `triage_history`；
- 新增实时项目对账：关键文件修复后自动把旧提案标为 fixed_*；提案页显示分类、优先级、分诊原因与过期原因统计。
- 修复提案页默认隐藏已过期/去重项，仅显示待处理；
- 分诊结果：89 条 → 75 过期/去重、10 已应用、3 失败、1 已回退，待处理 0。
- 修复提案分诊：pending>24h / confirmed>72h / 夹具空跑 / 无意义标题 / 同标题重复 → 标记 expired；列表按 ts 排序；
- Agent 队列来源闸：夹具 RS4/空 run_id 不入队，append_task 去重并拒绝空/乱码/自指标题；清理队列 48→38；
- 引擎事实措辞改为「官方记录日期」，避免把更新日断言成发布日；
- probe_link 仅对 id 形态 link 做悬空判定，消除散文 link 误报。
- 恢复回形针/DSH Agent 悬停描述；所有按钮自动获得统一 `.tip` 悬停说明；侧栏气泡右移到刚超出侧边栏。
- 去掉 Agent 面板悬停描述、面板 title 原生气泡；回形针去掉 data-tip 与浏览器 title 不透明气泡。
- 状态行内部灯/标签/值左右间隔拉大。
- 侧栏状态模型名改为 DeepSeek-Flash；高级参数按钮名称专业化重命名（仍按元DGTF 原配置组细分，参数不动）；
- 侧栏 Agent → DSH Agent；高级参数恢复元DGTF 原有细分按钮（不合并），按钮中文重命名，组内参数名不动；
- DSH Agent 改为 stdout 逐行流式读取并实时 emit：对话运行中即可看到思考/工具/回复事件，不再等进程退出才显示；
- 验证：真实对话在 running 状态已收到事件，最终 done。

## 验证

- 知识检索实测：刷新 2 条（quality 11.7/8.7）；自由查询 1 条相关；
- DSH 会话过程可见，知识库入库；
- app 版本 1.4.1，静态资源 v=1.4.3。