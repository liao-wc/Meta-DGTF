# 元DGTF 工作台（本地 Web 应用）

给元DGTF 引擎套的一层人用界面：**提问 → 后台跑 → 实时进度 → 读产物**，
外加一个可检索的**历史产物库**。

零额外依赖（Python 标准库 + 原生前端），**不改动引擎主文件**。

---

## 快速开始

```bash
# 1) 启动服务（默认 http://127.0.0.1:8765）
python dgtf_app/server.py

# 2) 浏览器打开
#    http://127.0.0.1:8765
```

**先试演练模式**：勾选「演练模式（mock）」再点「开始深究」——
几秒出结果、不花钱，用来确认界面与链路可用。

---

## 真实运行

- 需要项目根 `.env` 里有 `DGTF_API_KEY`（可选 `TAVILY_API_KEY` 走联网检索）。
- 真实一次跑 **约 30–45 分钟、几十万 token、约 ¥4–9**（DeepSeek 计价）。
  启动前界面会弹确认；任务在服务端后台跑，**可以关掉页面**，回来再看。
- 引擎取项目根下**版本号最高**的 `元DGTF-V*.py`；用环境变量
  `DGTF_APP_ENGINE` 可指定某个版本，`DGTF_APP_MAX_CONCURRENT` 调并发上限（默认 3）。

---

## 目录结构

```
dgtf_app/
  server.py          # HTTP 服务（仅监听 127.0.0.1）
  engine_runner.py   # 任务管理器：启动/监控引擎子进程、增量读日志、定位产物
  outputs_index.py   # 产物索引：扫描 outputs/*.md，解析头部元数据，检索
  mock_engine.py     # 演练引擎：模拟分层日志 + 产物，零花费
  selftest.py        # 端到端自检（跑完自动清理自己的 mock 产物）
  static/            # 前端（index.html / app.js / style.css）
  runs/              # 每个任务的运行日志 <id>.log
```

---

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET  | `/` | 应用首页 |
| GET  | `/api/config` | 引擎版本、凭据状态（不泄露值）、产物统计 |
| GET  | `/api/tasks` | 任务列表 |
| POST | `/api/tasks` | 新建任务 `{question, opts}` |
| GET  | `/api/tasks/<id>` | 单任务状态 |
| GET  | `/api/tasks/<id>/log?offset=N` | 日志增量（按字节偏移） |
| POST | `/api/tasks/<id>/cancel` | 取消任务 |
| GET  | `/api/tasks/<id>/result` | 产物正文 |
| GET  | `/api/outputs?q=&body=&days=&decidability=&orientation=` | 历史产物检索 |
| GET  | `/api/outputs/facets` | 筛选项集合 |
| GET  | `/api/outputs/<name>` | 单份产物正文 |

---

## 自检

```bash
python dgtf_app/server.py &        # 先起服务
python dgtf_app/selftest.py        # 13 项端到端断言
```

---

## 说明

- **产物库只读** `outputs/`，不写、不改。
- **安全**：服务只绑 `127.0.0.1`；`.env` 里的密钥只注入子进程环境，
  不返回给前端、不落日志。
- **不碰引擎**：本目录是独立的应用层，引擎主文件的 CRLF / 补丁流程与它无关。
- **后台日志只看进度**：引擎自 **v1.23.20** 起就把「全量留痕」与「ing·view 全文」
  两类大块**默认关掉**（`output.dump_rounds` / `show_ing` / `show_manifest`），
  stdout 只留进度；应用层再叠一层折叠做**兜底**（对旧版引擎同样有效）。
- **运行中 vs 跑完**：运行中显示原始日志（看得见过程），跑完自动收成折叠版；
  日志面板右下角有「展开 / 收起日志」按钮切换高度。
- **运行归档**：每次任务结束（成功 / 失败 / 取消）会把**完整运行日志**写为
  `outputs/<产物名>.run.log`、**运行元信息**写为 `outputs/<产物名>.run.json`，
  任务卡上可直接点开查看。
- **自检残留**：`selftest.py` 会自动清理自己产生的 mock 产物；但在沙箱隔离环境
  运行时，清理可能不落真实盘，必要时手工删 `outputs/*自检*` 与 `outputs/*.run.log|json`。
