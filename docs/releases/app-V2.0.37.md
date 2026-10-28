# App V2.0.37（2026-10-28，本地链路全生命周期 + 动态读数）

## 主题
APP → 引擎 → 本地模型 动态全链路：App 自己承担两段本地服务的生命周期与可观测性，
并新增「本地全链路档」预设。云档默认行为不变。

## 改动
- `dgtf_app/local_chain.py`（新增，纯标准库、可独立单测）：
  · **两段守护**：8772 本地推理服务（`dgtf_local_llm/service.py`）+ 8773 OpenAI 适配层
    （`scripts/local_model/openai_shim.py`）纳入同一 watchdog；硬掉线（连不上/无响应）
    失败 2 次后按 120/300/600/900/1800s 指数退避重启；**loading（模型加载中，进程活着）
    不重启**；迁移必记 + 抑制计数日志节流（`outputs/_lead_audit/local_chain_watchdog.log`）。
  · 修掉旧 watchdog 隐性 bug：重启命令直跑 `service.py` 会 ModuleNotFoundError（从未成功过），
    改为 venv `python -m dgtf_local_llm.service`；8773 用 App 的 python 起 shim。
  · `--local-chain-watchdog auto|on|off`（env `DGTF_APP_LOCAL_CHAIN_WATCHDOG`）；默认 auto =
    首次读数后按需守护（与旧 8772-only 懒启动同节奏）；off 时读数仍可用、只不重启。
- `/api/health` 新增 `local_chain`：service_ok / shim_ok / reachable / service_status /
  queue_depth / gpu_mem / shim_stage_channel / engine_path+version / endpoint_kind(cloud|local) /
  watchdog(mode,ticks,failures,restarts) / preset；读不到 = null + reasons（False=已测掉线，
  None=未测出，两向可分）；侧栏 `llm.chain` 同源且保留旧键。
- `configs/本地模型-全链路.yaml`（新增，生成器与文件逐字一致）：endpoint=127.0.0.1:8773/v1、
  model=local、web off、answer_gates block=false、save_dir=outputs/_e2e_local；走既有
  profile/_config 通道（POST /api/tasks opts.profile 或 /api/schedule/preview），无需新机制。
- `scripts/local_model/start_local_llm.ps1` / `stop_local_llm.ps1`：新增 `-Shim`/`-ShimPort`
  （默认行为不变：只管理 8772）。
- `dgtf_app/selftest.py`：新增 `check_local_chain` 11 项（基线 444 → 455）。
- `dgtf_app/params.py`：补 output.answer_gates.enabled/block 两条中文标签（HEAD 上预存在的
  标签判据红，纯展示文本、不改行为，可独立回滚）。

## 验证
- `python dgtf_app/test_local_chain.py` → **PASS 43 / FAIL 0**，含 8 个变异体（删 shim 目标 /
  shim_ok 写死 True / 退避固定 / 关日志节流 / 预设指回云 / health 丢 shim 字段 / 掉线不重启 /
  loading 也重启）全部被抓到。
- 临时 server（8799/HTTP/--local-chain-watchdog off）+ `selftest.py --base` → **PASS 455 / FAIL 0**。
- 默认 auto 模式实机：`mode=auto`、`ticks=1`、`local_chain.ok=True`、`endpoint_kind=cloud`
  （云档未被改成 local）、restarts=0（服务健康不误重启）。
- 4 个 py 文件 py_compile 通过；两个 ps1 Parser errors=0；预设与生成器逐字相同。

## 边界
- 未做破坏性真机自愈实测（遵守 session 约定不动 Lead 正在用的 8772/8773）：用真 HTTP 端口 +
  注入 start_fn 构造性证明；下次 8773 真挂可查 watchdog 日志。
- App 前端暂无 profile 下拉（API 通道与预设已通；UI 选择器另立）。
